from __future__ import annotations

from dataclasses import FrozenInstanceError
import inspect

import pytest
import torch

from visualvit.baselines import (
    BalancedSinkhorn,
    BalancedSinkhornBaseline,
    DevelopmentFrozenThreshold,
    HungarianRejectBaseline,
)
from visualvit.schemas import RegionBatch
from visualvit.tokenizer import build_soft_relation_candidates


def _regions(
    prior_anatomy: list[int],
    current_anatomy: list[int],
    *,
    prior_valid: list[bool] | None = None,
    current_valid: list[bool] | None = None,
) -> RegionBatch:
    prior_count = len(prior_anatomy)
    current_count = len(current_anatomy)
    feature_dim = 3
    return RegionBatch(
        prior_features=torch.arange(
            prior_count * feature_dim, dtype=torch.float32
        ).reshape(1, prior_count, feature_dim),
        current_features=(
            torch.arange(current_count * feature_dim, dtype=torch.float32).reshape(
                1, current_count, feature_dim
            )
            / 5.0
        ),
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
        prior_entity_ids=torch.arange(prior_count).unsqueeze(0),
        current_entity_ids=(torch.arange(current_count) + 100).unsqueeze(0),
    )


def _contract(regions: RegionBatch, cost: torch.Tensor, support: torch.Tensor):
    return (
        cost,
        support,
        regions.prior_valid.to(cost.dtype),
        regions.current_valid.to(cost.dtype),
    )


def _threshold(value: float = 1.0) -> DevelopmentFrozenThreshold:
    return DevelopmentFrozenThreshold(
        value=value,
        source_split="development-v1",
        selection_rule="maximize dev macro-F1, lower threshold wins ties",
    )


def test_baselines_share_contract_and_do_not_accept_oracle_cardinality() -> None:
    expected = ["self", "cost", "support", "prior_marginal", "current_marginal"]
    assert (
        list(inspect.signature(HungarianRejectBaseline.forward).parameters) == expected
    )
    assert (
        list(inspect.signature(BalancedSinkhornBaseline.forward).parameters) == expected
    )
    assert (
        "match_count"
        not in inspect.signature(HungarianRejectBaseline.forward).parameters
    )
    assert (
        "match_count"
        not in inspect.signature(BalancedSinkhornBaseline.forward).parameters
    )


def test_development_threshold_is_frozen_and_rejects_non_dev_provenance() -> None:
    frozen = _threshold(0.75)
    with pytest.raises(FrozenInstanceError):
        frozen.value = 0.2
    with pytest.raises(ValueError, match="development/validation"):
        DevelopmentFrozenThreshold(0.75, source_split="formal-test")
    with pytest.raises(TypeError, match="DevelopmentFrozenThreshold"):
        HungarianRejectBaseline(0.75)  # type: ignore[arg-type]


def test_hungarian_rejects_threshold_and_unsupported_edges() -> None:
    regions = _regions([0, 1, 2], [0, 1, 2])
    cost = torch.tensor([[[0.1, 0.7, 0.2], [0.8, 1.0, 0.3], [0.4, 0.2, 1.2]]])
    support = torch.tensor(
        [[[True, False, False], [False, True, False], [False, False, True]]]
    )
    plan = HungarianRejectBaseline(_threshold(1.0))(*_contract(regions, cost, support))
    assert plan.transport[0, 0, 0] == 1
    assert plan.transport[0, 1, 3] == 1  # cost == threshold is rejected.
    assert plan.transport[0, 2, 3] == 1
    assert plan.transport[0, 3, 1] == 1
    assert plan.transport[0, 3, 2] == 1
    plan.validate_hard(regions)
    assert float(plan.diagnostics["max_support_violation"]) == 0.0
    assert int(plan.diagnostics["rejected_supported_edges"]) == 2


def test_hungarian_is_global_deterministic_and_relation_path_compatible() -> None:
    regions = _regions([0, 0], [0, 0])
    # Greedy selects 0.0 then 0.9; global optional matching selects 0.1 + 0.1.
    cost = torch.tensor([[[0.0, 0.1], [0.1, 0.9]]])
    support = torch.ones_like(cost, dtype=torch.bool)
    matcher = HungarianRejectBaseline(_threshold(1.0))
    first = matcher(*_contract(regions, cost, support))
    second = matcher(*_contract(regions, cost, support))
    assert torch.equal(first.transport, second.transport)
    assert first.transport[0, 0, 1] == 1
    assert first.transport[0, 1, 0] == 1
    candidates = build_soft_relation_candidates(regions, first)
    candidates.validate()
    assert candidates.entity_features.shape[1] == 4


def test_hungarian_ties_are_repeatable_and_permutation_equivariant_off_ties() -> None:
    regions = _regions([0, 0], [0, 0])
    support = torch.ones(1, 2, 2, dtype=torch.bool)
    tied_cost = torch.zeros(1, 2, 2)
    matcher = HungarianRejectBaseline(_threshold(1.0))
    tied_first = matcher(*_contract(regions, tied_cost, support)).transport
    tied_second = matcher(*_contract(regions, tied_cost, support)).transport
    assert torch.equal(tied_first, tied_second)
    assert torch.equal(tied_first[0, :2, :2], torch.eye(2))

    unique_cost = torch.tensor([[[0.05, 0.8], [0.9, 0.1]]])
    original = matcher(*_contract(regions, unique_cost, support)).transport
    prior_permutation = torch.tensor([1, 0])
    current_permutation = torch.tensor([1, 0])
    permuted = matcher(
        unique_cost[:, prior_permutation][:, :, current_permutation],
        support[:, prior_permutation][:, :, current_permutation],
        regions.prior_valid.float()[:, prior_permutation],
        regions.current_valid.float()[:, current_permutation],
    ).transport
    assert torch.equal(
        permuted[:, :2, :2],
        original[:, :2, :2][:, prior_permutation][:, :, current_permutation],
    )


@pytest.mark.parametrize("prior_count,current_count", [(0, 0), (0, 2), (3, 0)])
def test_hungarian_handles_empty_endpoint_sets(
    prior_count: int, current_count: int
) -> None:
    cost = torch.empty(1, prior_count, current_count)
    support = torch.empty(1, prior_count, current_count, dtype=torch.bool)
    prior = torch.ones(1, prior_count)
    current = torch.ones(1, current_count)
    plan = HungarianRejectBaseline(_threshold())(cost, support, prior, current)
    assert plan.transport.shape == (1, prior_count + 1, current_count + 1)
    assert torch.isfinite(plan.transport).all()
    assert float(plan.diagnostics["max_null_residual"]) == 0.0


def test_sinkhorn_accepts_joint_empty_and_rejects_one_sided_mass() -> None:
    empty = BalancedSinkhornBaseline()(
        torch.empty(1, 0, 0),
        torch.empty(1, 0, 0, dtype=torch.bool),
        torch.empty(1, 0),
        torch.empty(1, 0),
    )
    assert empty.transport.shape == (1, 1, 1)
    assert torch.count_nonzero(empty.transport) == 0

    with pytest.raises(ValueError, match="equal prior/current total mass"):
        BalancedSinkhornBaseline()(
            torch.empty(1, 0, 2),
            torch.empty(1, 0, 2, dtype=torch.bool),
            torch.empty(1, 0),
            torch.ones(1, 2),
        )


def test_sinkhorn_balances_mass_prefers_low_cost_and_is_deterministic() -> None:
    assert BalancedSinkhorn is BalancedSinkhornBaseline
    regions = _regions([0, 0], [0, 0])
    cost = torch.tensor([[[0.0, 1.0], [1.0, 0.0]]])
    support = torch.ones_like(cost, dtype=torch.bool)
    matcher = BalancedSinkhornBaseline(epsilon=0.1, iterations=128)
    first = matcher(*_contract(regions, cost, support))
    second = matcher(*_contract(regions, cost, support))
    real = first.transport[0, :2, :2]
    assert torch.equal(first.transport, second.transport)
    assert real[0, 0] > real[0, 1]
    assert real[1, 1] > real[1, 0]
    assert torch.allclose(real.sum(-1), torch.ones(2), atol=1e-5)
    assert torch.allclose(real.sum(-2), torch.ones(2), atol=1e-5)
    assert torch.count_nonzero(first.transport[0, :2, 2]) == 0
    assert torch.count_nonzero(first.transport[0, 2, :2]) == 0
    assert first.diagnostics["null_mass_policy"] == (
        "forbidden; birth/death cells exactly zero"
    )
    assert "uniform positive marginals" in first.diagnostics["marginal_convention"]
    first.validate(regions)
    candidates = build_soft_relation_candidates(regions, first)
    candidates.validate()


def test_sinkhorn_allows_different_endpoint_counts_with_equal_uniform_total() -> None:
    cost = torch.tensor([[[0.0, 0.4, 0.8], [0.9, 0.3, 0.1]]])
    support = torch.ones_like(cost, dtype=torch.bool)
    prior = torch.tensor([[1.0, 1.0]])
    current = torch.full((1, 3), 2.0 / 3.0)
    plan = BalancedSinkhornBaseline(epsilon=0.4, iterations=192)(
        cost, support, prior, current
    )
    real = plan.transport[:, :2, :3]
    assert torch.allclose(real.sum(dim=-1), prior, atol=1e-6)
    assert torch.allclose(real.sum(dim=-2), current, atol=1e-6)
    assert torch.count_nonzero(plan.transport[:, :2, 3]) == 0
    assert torch.count_nonzero(plan.transport[:, 2, :3]) == 0
    assert torch.allclose(plan.diagnostics["prior_uniform_mass"], torch.tensor([1.0]))
    assert torch.allclose(
        plan.diagnostics["current_uniform_mass"], torch.tensor([2.0 / 3.0])
    )


def test_sinkhorn_mask_ties_permutation_and_zero_null_mass() -> None:
    regions = _regions([0, 0, 1], [0, 0, 1])
    cost = torch.zeros(1, 3, 3)
    support = torch.tensor(
        [
            [
                [True, True, False],
                [True, True, False],
                [False, False, True],
            ]
        ]
    )
    matcher = BalancedSinkhornBaseline(epsilon=0.3, iterations=128)
    original = matcher(*_contract(regions, cost, support))
    real = original.transport[0, :3, :3]
    assert torch.allclose(real[:2, :2], torch.full((2, 2), 0.5), atol=1e-6)
    assert real[2, 2] == pytest.approx(1.0)
    assert torch.count_nonzero(real.masked_select(~support[0])) == 0
    assert torch.count_nonzero(original.transport[0, :3, 3]) == 0
    assert torch.count_nonzero(original.transport[0, 3, :3]) == 0

    prior_permutation = torch.tensor([2, 0, 1])
    current_permutation = torch.tensor([2, 1, 0])
    permuted = matcher(
        cost[:, prior_permutation][:, :, current_permutation],
        support[:, prior_permutation][:, :, current_permutation],
        regions.prior_valid.float()[:, prior_permutation],
        regions.current_valid.float()[:, current_permutation],
    ).transport
    assert torch.allclose(
        permuted[:, :3, :3],
        original.transport[:, :3, :3][:, prior_permutation][:, :, current_permutation],
        atol=1e-6,
    )
    assert float(original.diagnostics["max_balanced_prior_residual"]) <= 1e-6
    assert float(original.diagnostics["max_balanced_current_residual"]) <= 1e-6
    assert float(original.diagnostics["max_null_residual"]) == 0.0


def test_sinkhorn_is_differentiable_with_finite_nonzero_cost_gradient() -> None:
    cost = torch.tensor([[[0.2, 0.7], [0.6, 0.1]]], requires_grad=True)
    support = torch.ones_like(cost, dtype=torch.bool)
    prior = torch.ones(1, 2)
    current = torch.ones(1, 2)
    plan = BalancedSinkhornBaseline(epsilon=0.4, iterations=96)(
        cost, support, prior, current
    )
    weights = torch.tensor([[[0.1, 0.8], [1.2, 0.3]]])
    loss = (plan.transport[:, :2, :2] * weights).sum()
    loss.backward()
    assert cost.grad is not None
    assert torch.isfinite(cost.grad).all()
    assert torch.count_nonzero(cost.grad) > 0


def test_contract_rejects_masked_leakage_and_nonbinary_hungarian_marginal() -> None:
    cost = torch.tensor([[[0.0, float("inf")], [float("inf"), 0.0]]])
    support = torch.tensor([[[True, False], [False, True]]])
    prior = torch.ones(1, 2)
    current = torch.ones(1, 2)
    sinkhorn = BalancedSinkhornBaseline()
    plan = sinkhorn(cost, support, prior, current)
    assert plan.transport[0, 0, 1] == 0
    assert torch.count_nonzero(plan.transport[:, :2, 2]) == 0
    assert torch.count_nonzero(plan.transport[:, 2, :2]) == 0
    with pytest.raises(ValueError, match="binary"):
        HungarianRejectBaseline(_threshold())(
            cost,
            support,
            torch.tensor([[0.5, 0.5]]),
            torch.tensor([[0.5, 0.5]]),
        )


def test_sinkhorn_rejects_nonuniform_unequal_and_support_infeasible_contracts() -> None:
    matcher = BalancedSinkhornBaseline()
    with pytest.raises(ValueError, match="equal prior/current total mass"):
        matcher(
            torch.zeros(1, 2, 3),
            torch.ones(1, 2, 3, dtype=torch.bool),
            torch.ones(1, 2),
            torch.ones(1, 3),
        )

    with pytest.raises(ValueError, match="prior_marginal must be uniform"):
        matcher(
            torch.zeros(1, 2, 2),
            torch.ones(1, 2, 2, dtype=torch.bool),
            torch.tensor([[0.5, 1.5]]),
            torch.ones(1, 2),
        )

    # Every endpoint has an incident edge and totals agree, but rows 0/1 can
    # only deliver two units into a single unit-capacity current endpoint.
    infeasible_support = torch.tensor(
        [[[True, False, False], [True, False, False], [True, True, True]]]
    )
    with pytest.raises(ValueError, match="support cannot realize"):
        matcher(
            torch.zeros(1, 3, 3),
            infeasible_support,
            torch.ones(1, 3),
            torch.ones(1, 3),
        )
