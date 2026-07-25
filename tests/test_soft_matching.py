from __future__ import annotations

import inspect

import pytest
import torch

from visualvit.matching import NullAwareMatchGraph
from visualvit.schemas import MatchPlan, RegionBatch


def _regions(
    prior_anatomy: list[int],
    current_anatomy: list[int],
    *,
    prior_valid: list[bool] | None = None,
    current_valid: list[bool] | None = None,
    feature_dim: int = 4,
) -> RegionBatch:
    prior_count = len(prior_anatomy)
    current_count = len(current_anatomy)
    prior_features = torch.arange(
        max(prior_count * feature_dim, 1), dtype=torch.float32
    )[: prior_count * feature_dim].reshape(1, prior_count, feature_dim)
    current_features = (
        torch.arange(max(current_count * feature_dim, 1), dtype=torch.float32)[
            : current_count * feature_dim
        ].reshape(1, current_count, feature_dim)
        / 7.0
    )
    return RegionBatch(
        prior_features=prior_features,
        current_features=current_features,
        prior_valid=torch.tensor(
            [prior_valid if prior_valid is not None else [True] * prior_count],
            dtype=torch.bool,
        ),
        current_valid=torch.tensor(
            [current_valid if current_valid is not None else [True] * current_count],
            dtype=torch.bool,
        ),
        prior_anatomy=torch.tensor([prior_anatomy], dtype=torch.long),
        current_anatomy=torch.tensor([current_anatomy], dtype=torch.long),
        prior_entity_ids=torch.arange(prior_count, dtype=torch.long).unsqueeze(0),
        current_entity_ids=(
            torch.arange(current_count, dtype=torch.long) + 100
        ).unsqueeze(0),
    )


def _plan_from_benefits(
    regions: RegionBatch,
    benefits: torch.Tensor,
    *,
    hard: bool = True,
) -> tuple[NullAwareMatchGraph, MatchPlan]:
    matcher = NullAwareMatchGraph(
        feature_dim=regions.prior_features.shape[-1],
        hidden_dim=5,
        temperature=0.3,
        projection_iterations=12,
    )
    prior_null = torch.zeros(benefits.shape[0], benefits.shape[1], dtype=benefits.dtype)
    current_null = torch.zeros(
        benefits.shape[0], benefits.shape[2], dtype=benefits.dtype
    )
    plan = matcher.plan_from_utilities(
        regions, benefits, prior_null, current_null, hard=hard
    )
    return matcher, plan


def test_hard_plan_all_persistent() -> None:
    regions = _regions([0, 1, 2], [0, 1, 2])
    benefits = torch.tensor([[[4.0, -3.0, -3.0], [-3.0, 5.0, -3.0], [-3.0, -3.0, 6.0]]])
    _, plan = _plan_from_benefits(regions, benefits)
    real = plan.transport[0, :3, :3]
    assert torch.equal(real, torch.eye(3))
    assert torch.count_nonzero(plan.transport[0, :3, 3]) == 0
    assert torch.count_nonzero(plan.transport[0, 3, :3]) == 0


def test_hard_plan_all_births() -> None:
    regions = _regions(
        [0, 1], [0, 1], prior_valid=[False, False], current_valid=[True, True]
    )
    _, plan = _plan_from_benefits(regions, torch.full((1, 2, 2), 100.0))
    assert torch.count_nonzero(plan.transport[0, :2]) == 0
    assert torch.equal(plan.transport[0, 2, :2], torch.ones(2))


def test_hard_plan_all_deaths() -> None:
    regions = _regions(
        [0, 1], [0, 1], prior_valid=[True, True], current_valid=[False, False]
    )
    _, plan = _plan_from_benefits(regions, torch.full((1, 2, 2), 100.0))
    assert torch.equal(plan.transport[0, :2, 2], torch.ones(2))
    assert torch.count_nonzero(plan.transport[0, 2, :]) == 0


def test_hard_plan_mixed_persistent_birth_and_death() -> None:
    regions = _regions([0, 1, 2], [0, 1, 2])
    benefits = torch.tensor(
        [[[5.0, -4.0, -4.0], [-4.0, 4.0, -4.0], [-4.0, -4.0, -1.0]]]
    )
    _, plan = _plan_from_benefits(regions, benefits)
    assert plan.transport[0, 0, 0] == 1
    assert plan.transport[0, 1, 1] == 1
    assert plan.transport[0, 2, 3] == 1
    assert plan.transport[0, 3, 2] == 1


def test_padding_and_anatomy_masks_are_fail_closed() -> None:
    regions = _regions(
        [0, 1, 2],
        [1, 2, 0],
        prior_valid=[True, True, False],
        current_valid=[True, True, False],
    )
    _, hard = _plan_from_benefits(regions, torch.full((1, 3, 3), 100.0))
    _, soft = _plan_from_benefits(regions, torch.full((1, 3, 3), 100.0), hard=False)
    for plan in (hard, soft):
        real = plan.transport[0, :3, :3]
        assert real[1, 0] > 0
        assert torch.count_nonzero(real[0]) == 0
        assert torch.count_nonzero(real[2]) == 0
        assert torch.count_nonzero(real[:, 1]) == 0
        assert torch.count_nonzero(real[:, 2]) == 0
        plan.validate(regions)


def test_soft_plan_mass_diagnostics_and_finite_values() -> None:
    regions = _regions(
        [0, 0, 1, 2],
        [0, 1, 1],
        prior_valid=[True, True, True, False],
        current_valid=[True, True, False],
    )
    benefits = torch.tensor(
        [[[3.0, -1.0, 9.0], [2.0, 0.5, 9.0], [-2.0, 4.0, 9.0], [9.0, 9.0, 9.0]]]
    )
    matcher, plan = _plan_from_benefits(regions, benefits, hard=False)
    plan.validate(regions, atol=matcher.feasibility_tolerance)
    assert torch.isfinite(plan.transport).all()
    assert torch.all(plan.transport >= 0)

    real = plan.transport[:, :4, :3]
    assert torch.all(real.sum(-1) <= regions.prior_valid.float() + 1e-6)
    assert torch.all(real.sum(-2) <= regions.current_valid.float() + 1e-6)
    assert torch.allclose(
        plan.transport[:, :4, :].sum(-1), regions.prior_valid.float(), atol=1e-6
    )
    assert torch.allclose(
        plan.transport[:, :, :3].sum(-2), regions.current_valid.float(), atol=1e-6
    )

    required = {
        "min_mass",
        "max_prior_residual",
        "max_current_residual",
        "dustbin_dustbin",
        "iterations",
        "temperature",
        "objective_soft",
        "objective_hard",
    }
    assert required <= set(plan.diagnostics)
    assert plan.diagnostics["iterations"] == 12
    assert float(plan.diagnostics["max_prior_residual"]) <= 1e-6
    assert float(plan.diagnostics["max_current_residual"]) <= 1e-6
    assert torch.all(
        plan.diagnostics["objective_hard"] >= plan.diagnostics["objective_soft"] - 1e-6
    )


def test_soft_transport_backpropagates_to_match_and_both_null_heads() -> None:
    torch.manual_seed(4)
    regions = _regions([0, 0, 0], [0, 0, 0])
    matcher = NullAwareMatchGraph(
        feature_dim=4, hidden_dim=7, temperature=0.7, projection_iterations=8
    )
    plan = matcher(regions)
    weights = torch.linspace(
        0.1, 1.7, plan.transport.numel(), dtype=plan.transport.dtype
    ).reshape_as(plan.transport)
    loss = (plan.transport * weights).sum()
    loss.backward()

    for parameter in (
        matcher.prior_projection.weight,
        matcher.current_projection.weight,
        matcher.prior_null_head.weight,
        matcher.current_null_head.weight,
    ):
        assert parameter.grad is not None
        assert torch.isfinite(parameter.grad).all()
        assert torch.count_nonzero(parameter.grad) > 0


def test_soft_transport_is_permutation_equivariant() -> None:
    torch.manual_seed(9)
    regions = _regions(
        [0, 1, 0, 2],
        [1, 0, 2],
        prior_valid=[True, True, True, False],
        current_valid=[True, True, True],
    )
    matcher = NullAwareMatchGraph(feature_dim=4, hidden_dim=6, temperature=0.4)
    original = matcher(regions).transport
    prior_permutation = torch.tensor([2, 0, 3, 1])
    current_permutation = torch.tensor([1, 2, 0])
    permuted_regions = RegionBatch(
        prior_features=regions.prior_features[:, prior_permutation],
        current_features=regions.current_features[:, current_permutation],
        prior_valid=regions.prior_valid[:, prior_permutation],
        current_valid=regions.current_valid[:, current_permutation],
        prior_anatomy=regions.prior_anatomy[:, prior_permutation],
        current_anatomy=regions.current_anatomy[:, current_permutation],
        prior_entity_ids=regions.prior_entity_ids[:, prior_permutation],
        current_entity_ids=regions.current_entity_ids[:, current_permutation],
    )
    permuted = matcher(permuted_regions).transport
    assert torch.allclose(
        permuted[:, :4, :3],
        original[:, :4, :3][:, prior_permutation][:, :, current_permutation],
        atol=1e-6,
    )
    assert torch.allclose(
        permuted[:, :4, 3], original[:, :4, 3][:, prior_permutation], atol=1e-6
    )
    assert torch.allclose(
        permuted[:, 4, :3], original[:, 4, :3][:, current_permutation], atol=1e-6
    )


def test_learned_api_and_outputs_do_not_depend_on_oracle_ids() -> None:
    assert (
        "match_count" not in inspect.signature(NullAwareMatchGraph.forward).parameters
    )
    assert (
        "match_count" not in inspect.signature(NullAwareMatchGraph.hard_plan).parameters
    )

    torch.manual_seed(13)
    regions = _regions([0, 1], [0, 1])
    altered_ids = RegionBatch(
        prior_features=regions.prior_features,
        current_features=regions.current_features,
        prior_valid=regions.prior_valid,
        current_valid=regions.current_valid,
        prior_anatomy=regions.prior_anatomy,
        current_anatomy=regions.current_anatomy,
        prior_entity_ids=torch.tensor([[999, -7]]),
        current_entity_ids=torch.tensor([[42, 42]]),
    )
    matcher = NullAwareMatchGraph(feature_dim=4)
    assert torch.equal(matcher(regions).transport, matcher(altered_ids).transport)
    assert torch.equal(
        matcher(regions, hard=True).transport,
        matcher(altered_ids, hard=True).transport,
    )


def test_hardening_is_deterministic_under_ties() -> None:
    regions = _regions([0, 0], [0, 0])
    benefits = torch.ones(1, 2, 2)
    matcher, first = _plan_from_benefits(regions, benefits)
    second = matcher.plan_from_utilities(
        regions, benefits, torch.zeros(1, 2), torch.zeros(1, 2), hard=True
    )
    assert torch.equal(first.transport, second.transport)
    assert torch.equal(first.transport[0, :2, :2], torch.eye(2))


def test_hardening_finds_global_micro_optimum_and_rejects_bad_edges() -> None:
    regions = _regions([0, 0], [0, 0])
    # Greedy takes 9 + 0.1; the globally optimal optional assignment takes 8 + 8.
    benefits = torch.tensor([[[9.0, 8.0], [8.0, 0.1]]])
    matcher, plan = _plan_from_benefits(regions, benefits)
    assert plan.transport[0, 0, 1] == 1
    assert plan.transport[0, 1, 0] == 1
    assert float(plan.diagnostics["objective_hard"][0]) == pytest.approx(16.0)

    rejected = matcher.plan_from_utilities(
        regions,
        torch.full((1, 2, 2), 10.0),
        torch.full((1, 2), 6.0),
        torch.full((1, 2), 5.0),
        hard=True,
    )
    assert torch.count_nonzero(rejected.transport[0, :2, :2]) == 0
    assert torch.equal(rejected.transport[0, :2, 2], torch.ones(2))
    assert torch.equal(rejected.transport[0, 2, :2], torch.ones(2))
    assert float(rejected.diagnostics["objective_hard"][0]) == pytest.approx(22.0)


@pytest.mark.parametrize(
    "temperature,iterations",
    [(0.0, 2), (float("inf"), 2), (0.2, 0)],
)
def test_invalid_relaxation_configuration_is_rejected(
    temperature: float, iterations: int
) -> None:
    with pytest.raises(ValueError):
        NullAwareMatchGraph(
            feature_dim=4,
            temperature=temperature,
            projection_iterations=iterations,
        )
