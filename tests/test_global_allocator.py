from dataclasses import replace

import pytest
import torch

from visualvit.allocator import DeterministicGlobalAllocator, apply_allocation
from visualvit.schemas import RelationCandidates


def _make_candidates(
    source_count: int,
    *,
    batch_size: int = 2,
    feature_dim: int = 3,
) -> RelationCandidates:
    values = torch.arange(
        batch_size * source_count * feature_dim,
        dtype=torch.float32,
    ).reshape(batch_size, source_count, feature_dim)
    source_index = torch.arange(source_count).expand(batch_size, -1)
    batch_offset = torch.arange(batch_size)[:, None] * 10_000
    valid = torch.ones(batch_size, source_count, dtype=torch.bool)
    return RelationCandidates(
        entity_features=values,
        relation_features=-values,
        valid_mask=valid,
        unary_scores=(source_count - source_index).to(torch.float32),
        anatomy_ids=(source_index % 13).to(torch.long),
        temporal_ids=(source_index % 2).to(torch.long),
        source_ids=(batch_offset + source_index + 100).to(torch.long),
        relation_mass=valid.to(torch.float32),
    )


def _permute_sources(
    candidates: RelationCandidates,
    permutation: torch.Tensor,
) -> RelationCandidates:
    return RelationCandidates(
        entity_features=candidates.entity_features[:, permutation],
        relation_features=candidates.relation_features[:, permutation],
        valid_mask=candidates.valid_mask[:, permutation],
        unary_scores=candidates.unary_scores[:, permutation],
        anatomy_ids=candidates.anatomy_ids[:, permutation],
        temporal_ids=candidates.temporal_ids[:, permutation],
        source_ids=candidates.source_ids[:, permutation],
        relation_mass=candidates.relation_mass[:, permutation],
    )


def test_v1_constructor_accepts_28_slot_aliases_only():
    assert DeterministicGlobalAllocator(max_slots=28).max_slots == 28
    assert DeterministicGlobalAllocator(num_slots=28).max_slots == 28
    with pytest.raises(ValueError, match="exactly 28"):
        DeterministicGlobalAllocator(max_slots=27)


@pytest.mark.parametrize("source_count", [0, 1, 28, 29, 58, 137])
def test_fixed_shape_exact_column_mass_and_overflow(source_count: int):
    candidates = _make_candidates(source_count)
    plan = DeterministicGlobalAllocator()(candidates)

    assert plan.weights.shape == (2, 28, source_count)
    assert plan.slot_valid.shape == (2, 28)
    assert plan.selected_source_ids.shape == (2, 28)
    assert torch.equal(
        plan.weights.sum(dim=1), candidates.valid_mask.to(plan.weights.dtype)
    )

    expected_valid_slots = min(source_count, 28)
    expected_overflow_sources = max(source_count - 27, 0) if source_count > 28 else 0
    assert torch.all(plan.slot_valid.sum(dim=1) == expected_valid_slots)
    assert torch.all(plan.overflow_mask.sum(dim=1) == expected_overflow_sources)
    assert torch.all(plan.selected_source_ids[~plan.slot_valid] == -1)

    if source_count <= 28:
        assert not bool(plan.overflow_mask.any())
        assert torch.all(plan.slot_mass[plan.slot_valid] == 1)
    else:
        assert torch.all(plan.slot_mass[:, :27] == 1)
        assert torch.all(plan.slot_mass[:, 27] == source_count - 27)
        assert torch.all(plan.selected_source_ids[:, 27] == -2)


def test_invalid_sources_never_consume_slots_or_overflow_mass():
    candidates = _make_candidates(40, batch_size=1)
    valid = torch.zeros_like(candidates.valid_mask)
    valid[:, ::2] = True
    scores = candidates.unary_scores.clone()
    scores[:, 1::2] = 1_000_000  # invalid sources would otherwise rank first
    candidates = replace(
        candidates,
        valid_mask=valid,
        unary_scores=scores,
        relation_mass=valid.to(torch.float32),
    )

    plan = DeterministicGlobalAllocator()(candidates)

    column_mass = plan.weights.sum(dim=1)
    assert torch.all(column_mass[candidates.valid_mask] == 1)
    assert torch.all(column_mass[~candidates.valid_mask] == 0)
    assert not bool(plan.overflow_mask.any())
    assert int(plan.slot_valid.sum()) == 20
    selected = set(plan.selected_source_ids[plan.slot_valid].tolist())
    assert selected == set(candidates.source_ids[candidates.valid_mask].tolist())


def test_overflow_depends_on_valid_count_not_padded_source_width():
    candidates = _make_candidates(35)
    valid = torch.zeros_like(candidates.valid_mask)
    valid[0, :28] = True
    valid[1, :29] = True
    scores = candidates.unary_scores.clone()
    scores[~valid] = 1_000_000
    candidates = replace(
        candidates,
        valid_mask=valid,
        unary_scores=scores,
        relation_mass=valid.to(torch.float32),
    )

    plan = DeterministicGlobalAllocator()(candidates)

    assert not bool(plan.overflow_mask[0].any())
    assert plan.selected_source_ids[0, -1].item() >= 0
    assert int(plan.overflow_mask[1].sum()) == 2
    assert plan.selected_source_ids[1, -1].item() == -2


def test_overflow_provenance_and_mass_normalized_application():
    candidates = _make_candidates(29, batch_size=1, feature_dim=2)
    candidates = replace(
        candidates,
        anatomy_ids=torch.zeros_like(candidates.anatomy_ids),
        temporal_ids=torch.zeros_like(candidates.temporal_ids),
    )
    features = torch.stack(
        [torch.arange(29, dtype=torch.float32), torch.arange(29) * 10.0],
        dim=-1,
    ).unsqueeze(0)
    plan = DeterministicGlobalAllocator()(candidates)

    assert torch.equal(
        plan.overflow_mask,
        torch.tensor([[False] * 27 + [True, True]]),
    )
    assert plan.selected_source_ids[0, -1].item() == -2
    slots, mass = apply_allocation(features, plan)
    assert mass[0, -1].item() == 2
    assert torch.allclose(slots[0, -1], torch.tensor([27.5, 275.0]))

    source_mass = torch.ones(1, 29)
    source_mass[0, 28] = 3
    weighted_slots, weighted_mass = apply_allocation(
        features,
        plan,
        source_mass=source_mass,
    )
    assert weighted_mass[0, -1].item() == 4
    assert torch.allclose(weighted_slots[0, -1], torch.tensor([27.75, 277.5]))


def test_anatomy_coverage_precedes_second_source_from_same_group():
    candidates = _make_candidates(3, batch_size=1)
    candidates = replace(
        candidates,
        unary_scores=torch.tensor([[100.0, 99.0, 1.0]]),
        anatomy_ids=torch.tensor([[0, 0, 1]]),
        temporal_ids=torch.zeros(1, 3, dtype=torch.long),
        source_ids=torch.tensor([[10, 11, 12]]),
    )

    plan = DeterministicGlobalAllocator()(candidates)

    assert plan.selected_source_ids[0, :3].tolist() == [10, 12, 11]


def test_ties_use_anatomy_temporal_side_and_stable_source_id():
    candidates = _make_candidates(6, batch_size=1)
    candidates = replace(
        candidates,
        unary_scores=torch.ones(1, 6),
        anatomy_ids=torch.tensor([[1, 0, 1, 0, 0, 1]]),
        temporal_ids=torch.tensor([[1, 1, 0, 1, 0, 0]]),
        source_ids=torch.tensor([[50, 10, 40, 20, 30, 60]]),
    )

    plan = DeterministicGlobalAllocator()(candidates)

    assert plan.selected_source_ids[0, :6].tolist() == [30, 40, 10, 20, 60, 50]


def test_source_permutation_is_equivariant_even_with_ties():
    candidates = _make_candidates(58, batch_size=1)
    candidates = replace(
        candidates,
        unary_scores=(candidates.source_ids % 5).to(torch.float32),
    )
    permutation = torch.randperm(58, generator=torch.Generator().manual_seed(19))
    inverse = torch.argsort(permutation)

    original = DeterministicGlobalAllocator()(candidates)
    permuted = DeterministicGlobalAllocator()(_permute_sources(candidates, permutation))

    assert torch.equal(original.weights, permuted.weights[:, :, inverse])
    assert torch.equal(original.overflow_mask, permuted.overflow_mask[:, inverse])
    assert torch.equal(original.slot_valid, permuted.slot_valid)
    assert torch.equal(original.slot_mass, permuted.slot_mass)
    assert torch.equal(original.selected_source_ids, permuted.selected_source_ids)


def test_relation_assignment_values_cannot_change_allocation():
    candidates = _make_candidates(58, batch_size=1)
    changed = replace(
        candidates,
        relation_features=torch.randn_like(candidates.relation_features) * 1000,
        relation_mass=torch.linspace(0.0, 1.0, 58).unsqueeze(0),
    )

    first = DeterministicGlobalAllocator()(candidates)
    second = DeterministicGlobalAllocator()(changed)

    for field in (
        "weights",
        "slot_valid",
        "slot_mass",
        "source_valid",
        "selected_source_ids",
        "overflow_mask",
    ):
        assert torch.equal(getattr(first, field), getattr(second, field))


def test_duplicate_valid_source_ids_are_rejected():
    candidates = _make_candidates(2, batch_size=1)
    candidates = replace(candidates, source_ids=torch.tensor([[7, 7]]))

    with pytest.raises(ValueError, match="source IDs"):
        DeterministicGlobalAllocator()(candidates)


@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA is unavailable")
def test_cpu_gpu_allocation_is_exactly_deterministic():
    candidates = _make_candidates(137, batch_size=2)
    cpu_plan = DeterministicGlobalAllocator()(candidates)
    gpu_plan = DeterministicGlobalAllocator()(candidates.to("cuda")).to("cpu")

    for field in (
        "weights",
        "slot_valid",
        "slot_mass",
        "source_valid",
        "selected_source_ids",
        "overflow_mask",
    ):
        assert torch.equal(getattr(cpu_plan, field), getattr(gpu_plan, field))
