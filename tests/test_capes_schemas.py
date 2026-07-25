import pytest
import torch

from visualvit.schemas import (
    AllocationPlan,
    MatchPlan,
    ProjectedTokenBundle,
    RegionBatch,
    RelationCandidates,
    TokenBundle,
)


def _regions(*, metadata: bool = False) -> RegionBatch:
    kwargs = {}
    if metadata:
        kwargs = {
            "prior_boxes": torch.zeros(1, 2, 4),
            "current_boxes": torch.zeros(1, 2, 4),
            "prior_confidence": torch.tensor([[0.9, 0.8]]),
            "current_confidence": torch.tensor([[0.7, 0.6]]),
            "prior_source_ids": torch.tensor([[10, 11]]),
            "current_source_ids": torch.tensor([[20, 21]]),
            "time_delta_days": torch.tensor([31.0]),
        }
    return RegionBatch(
        prior_features=torch.randn(1, 2, 4),
        current_features=torch.randn(1, 2, 4),
        prior_valid=torch.ones(1, 2, dtype=torch.bool),
        current_valid=torch.ones(1, 2, dtype=torch.bool),
        prior_anatomy=torch.tensor([[0, 1]]),
        current_anatomy=torch.tensor([[0, 1]]),
        prior_entity_ids=torch.tensor([[100, 101]]),
        current_entity_ids=torch.tensor([[100, 102]]),
        **kwargs,
    )


def _fractional_plan(*, metadata: bool = False) -> MatchPlan:
    real = torch.tensor([[[0.5, 0.2], [0.1, 0.4]]])
    transport = torch.zeros(1, 3, 3)
    transport[:, :2, :2] = real
    transport[:, :2, 2] = torch.tensor([[0.3, 0.5]])
    transport[:, 2, :2] = torch.tensor([[0.4, 0.4]])
    kwargs = {}
    if metadata:
        kwargs = {
            "edge_logits": torch.randn(1, 2, 2),
            "prior_null_logits": torch.randn(1, 2),
            "current_null_logits": torch.randn(1, 2),
            "diagnostics": {"iterations": 8, "objective_soft": torch.tensor(1.5)},
        }
    return MatchPlan(transport=transport, mode="soft", **kwargs)


def test_region_batch_metadata_is_optional_validated_and_moved():
    historical = _regions()
    historical.validate()

    regions = _regions(metadata=True)
    regions.validate()
    moved = regions.to("cpu")
    assert moved is not regions
    assert moved.prior_boxes is not None
    assert moved.prior_source_ids is not None
    assert moved.prior_source_ids.dtype is torch.long

    regions.prior_boxes = torch.zeros(1, 2, 5)
    with pytest.raises(ValueError, match="prior_boxes"):
        regions.validate()


def test_match_plan_checks_soft_mass_and_optional_logits():
    regions = _regions()
    plan = _fractional_plan(metadata=True)
    plan.validate(regions)
    with pytest.raises(ValueError, match="fractional transport"):
        plan.validate_hard(regions)

    wrong_mass = _fractional_plan()
    wrong_mass.transport[0, 0, 2] += 0.1
    with pytest.raises(ValueError, match="death mass"):
        wrong_mass.validate(regions)

    wrong_dustbin = _fractional_plan()
    wrong_dustbin.transport[0, 2, 2] = 1e-8
    with pytest.raises(ValueError, match="exactly zero"):
        wrong_dustbin.validate(regions)


def test_relation_candidates_validate_shapes_dtypes_and_invalid_mass():
    candidates = RelationCandidates(
        entity_features=torch.randn(1, 3, 4),
        relation_features=torch.randn(1, 3, 4),
        valid_mask=torch.tensor([[True, True, False]]),
        unary_scores=torch.tensor([[0.9, 0.4, 0.0]]),
        anatomy_ids=torch.tensor([[1, 2, -1]]),
        temporal_ids=torch.tensor([[0, 1, 1]]),
        source_ids=torch.tensor([[10, 20, -1]]),
        relation_mass=torch.tensor([[1.0, 0.25, 0.0]]),
    )
    candidates.validate()
    assert candidates.to("cpu").source_ids.dtype is torch.long

    candidates.relation_mass[0, 2] = 0.5
    with pytest.raises(ValueError, match="invalid relation candidates"):
        candidates.validate()


def _allocation(
    source_count: int, candidate_count: int | None = None
) -> AllocationPlan:
    n = candidate_count or source_count
    weights = torch.zeros(1, 28, n)
    selected = torch.full((1, 28), -1, dtype=torch.long)
    overflow = torch.zeros(1, n, dtype=torch.bool)
    if source_count <= 28:
        for index in range(source_count):
            weights[0, index, index] = 1
            selected[0, index] = 100 + index
    else:
        for index in range(27):
            weights[0, index, index] = 1
            selected[0, index] = 100 + index
        weights[0, -1, 27:source_count] = 1
        selected[0, -1] = -2
        overflow[0, 27:source_count] = True
    source_valid = torch.zeros(1, n, dtype=torch.bool)
    source_valid[0, :source_count] = True
    slot_mass = weights.sum(dim=-1)
    return AllocationPlan(
        weights=weights,
        slot_valid=slot_mass > 0,
        slot_mass=slot_mass,
        source_valid=source_valid,
        selected_source_ids=selected,
        overflow_mask=overflow,
    )


def test_allocation_plan_accepts_padding_and_audits_overflow():
    padded = _allocation(source_count=20, candidate_count=40)
    padded.validate()
    assert not padded.overflow_mask.any()

    overflow = _allocation(source_count=30)
    overflow.validate()
    assert overflow.slot_mass[0, -1] == 3
    assert overflow.selected_source_ids[0, -1] == -2

    overflow.weights[0, 0, 29] = 1
    with pytest.raises(ValueError, match="column mass one"):
        overflow.validate()


def test_token_bundle_metadata_remains_backward_compatible():
    historical = TokenBundle(
        tokens=torch.zeros(2, 64, 8),
        token_types=torch.arange(64, dtype=torch.long),
        valid_mask=torch.ones(2, 64, dtype=torch.bool),
        assignment=torch.zeros(2, 2, 2),
    )
    historical.validate()

    metadata = torch.zeros(2, 64)
    bundle = TokenBundle(
        tokens=historical.tokens,
        token_types=historical.token_types.expand(2, -1).clone(),
        valid_mask=historical.valid_mask,
        assignment=historical.assignment,
        anatomy_ids=metadata.long(),
        temporal_ids=metadata.long(),
        confidence=metadata,
        slot_mass=metadata,
        source_ids=metadata.long(),
    )
    bundle.validate()
    assert bundle.to("cpu").confidence is not None


def test_projected_bundle_requires_physical_attention_and_equal_position_axes():
    axis = torch.arange(64, dtype=torch.long).view(1, 64).expand(2, -1)
    bundle = ProjectedTokenBundle(
        embeddings=torch.randn(2, 64, 16),
        token_types=torch.zeros(64, dtype=torch.long),
        valid_mask=torch.zeros(2, 64, dtype=torch.bool),
        attention_mask=torch.ones(2, 64, dtype=torch.long),
        position_ids=axis.unsqueeze(0).expand(3, -1, -1).clone(),
        audit={"placeholder_count": 64, "tensor": torch.tensor(1.0)},
    )
    bundle.validate()
    assert bundle.to("cpu").audit["tensor"].device.type == "cpu"

    bundle.attention_mask[0, 0] = 0
    with pytest.raises(ValueError, match="every physical token"):
        bundle.validate()
