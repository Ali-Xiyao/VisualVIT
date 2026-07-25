import torch
import pytest

from visualvit.matching import (
    InvariantPartialOTMatcher,
    ProjectedCosineMatcher,
    anatomy_compatible_derangement,
    assignment_accuracy,
)
from visualvit.synthetic import labeled_relation_rows, make_synthetic_batch
from visualvit.schemas import MatchPlan, RegionBatch
from visualvit.tokenizer import build_relation_slots


def test_oracle_and_deranged_partial_semantics():
    synthetic = make_synthetic_batch(num_cases=3, seed=7)
    regions = synthetic.regions
    oracle = synthetic.oracle
    oracle.validate(regions)

    rp = regions.prior_features.shape[1]
    rc = regions.current_features.shape[1]
    assert torch.all(oracle.transport[:, rp, rc] == 0)
    assert torch.all(oracle.transport[:, :rp, :].sum(-1) == 1)
    assert torch.all(oracle.transport[:, :, :rc].sum(-2) == 1)
    assert torch.all(oracle.transport[:, :rp, rc].sum(-1) == 2)
    assert torch.all(oracle.transport[:, rp, :rc].sum(-1) == 2)

    deranged = anatomy_compatible_derangement(regions, oracle, seed=17)
    deranged.validate(regions)
    assert not torch.equal(deranged.transport, oracle.transport)
    assert torch.equal(deranged.transport.sum(-1), oracle.transport.sum(-1))
    assert torch.equal(deranged.transport.sum(-2), oracle.transport.sum(-2))

    for batch_index in range(regions.prior_features.shape[0]):
        for prior_index in range(rp):
            gold_current = int(oracle.transport[batch_index, prior_index].argmax())
            wrong_current = int(deranged.transport[batch_index, prior_index].argmax())
            if gold_current < rc:
                assert wrong_current != gold_current
                assert (
                    regions.prior_anatomy[batch_index, prior_index]
                    == regions.current_anatomy[batch_index, wrong_current]
                )


def test_projected_matcher_hard_plan_is_valid():
    synthetic = make_synthetic_batch(num_cases=4, seed=11)
    matcher = ProjectedCosineMatcher(feature_dim=24, projection_dim=12)
    plan = matcher.hard_plan(synthetic.regions, match_count=synthetic.persistent_count)
    plan.validate(synthetic.regions)
    assert 0.0 <= assignment_accuracy(plan, synthetic.oracle, synthetic.regions) <= 1.0


def test_fractional_plan_cannot_enter_hard_tokenizer():
    synthetic = make_synthetic_batch(num_cases=1, seed=31)
    soft = synthetic.oracle.transport.clone()
    rp = synthetic.regions.prior_features.shape[1]
    rc = synthetic.regions.current_features.shape[1]
    persistent_rows = [i for i in range(rp) if int(soft[0, i, :rc].sum().item()) == 1]
    first, second = persistent_rows[:2]
    first_col = int(soft[0, first, :rc].argmax())
    second_col = int(soft[0, second, :rc].argmax())
    soft[0, first, :rc] = 0
    soft[0, second, :rc] = 0
    soft[0, first, first_col] = 0.5
    soft[0, first, second_col] = 0.5
    soft[0, second, first_col] = 0.5
    soft[0, second, second_col] = 0.5
    plan = MatchPlan(soft, mode="fractional_test")
    plan.validate(synthetic.regions)
    with pytest.raises(ValueError, match="fractional transport"):
        build_relation_slots(synthetic.regions, plan)


def test_synthetic_birth_mismatch_is_not_oracle_filtered():
    synthetic = make_synthetic_batch(num_cases=1, seed=37)
    wrong = synthetic.oracle.transport.clone()
    rp = synthetic.regions.prior_features.shape[1]
    rc = synthetic.regions.current_features.shape[1]

    persistent_prior = int(torch.nonzero(wrong[0, :rp, :rc].sum(-1) == 1)[0].item())
    death_prior = int(torch.nonzero(wrong[0, :rp, rc] == 1)[0].item())
    persistent_current = int(
        torch.nonzero(wrong[0, persistent_prior, :rc] == 1)[0].item()
    )
    gold_birth_current = int(torch.nonzero(wrong[0, rp, :rc] == 1)[0].item())

    wrong[0, persistent_prior, persistent_current] = 0
    wrong[0, death_prior, rc] = 0
    wrong[0, rp, gold_birth_current] = 0
    wrong[0, persistent_prior, rc] = 1
    wrong[0, death_prior, gold_birth_current] = 1
    wrong[0, rp, persistent_current] = 1
    wrong_plan = MatchPlan(wrong, mode="wrong_birth_set")
    wrong_plan.validate_hard(synthetic.regions)

    with pytest.raises(ValueError, match="exact birth set"):
        labeled_relation_rows(synthetic, wrong_plan)


def _identity_fixture() -> RegionBatch:
    prior_identity = torch.tensor([[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]])
    current_identity = torch.tensor(
        [[[0.0, 0.0, 1.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]]
    )
    prior = torch.cat(
        (
            torch.tensor([[[1.0, -1.0], [0.0, 2.0], [1.0, 3.0]]]),
            prior_identity,
        ),
        dim=-1,
    )
    current = torch.cat(
        (
            torch.tensor([[[-2.0, 1.0], [4.0, 0.0], [9.0, -3.0]]]),
            current_identity,
        ),
        dim=-1,
    )
    valid = torch.ones((1, 3), dtype=torch.bool)
    anatomy = torch.zeros((1, 3), dtype=torch.long)
    entity_ids = torch.arange(3, dtype=torch.long).unsqueeze(0)
    return RegionBatch(
        prior_features=prior,
        current_features=current,
        prior_valid=valid,
        current_valid=valid.clone(),
        prior_anatomy=anatomy,
        current_anatomy=anatomy.clone(),
        prior_entity_ids=entity_ids,
        current_entity_ids=entity_ids.clone(),
    )


def _replace_features(
    regions: RegionBatch, prior_features: torch.Tensor, current_features: torch.Tensor
) -> RegionBatch:
    return RegionBatch(
        prior_features=prior_features,
        current_features=current_features,
        prior_valid=regions.prior_valid,
        current_valid=regions.current_valid,
        prior_anatomy=regions.prior_anatomy,
        current_anatomy=regions.current_anatomy,
        prior_entity_ids=regions.prior_entity_ids,
        current_entity_ids=regions.current_entity_ids,
    )


def test_invariant_partial_ot_ignores_state_and_is_rotation_invariant():
    regions = _identity_fixture()
    matcher = InvariantPartialOTMatcher(feature_dim=5, sinkhorn_iterations=128)
    edge, death, birth = matcher.compute_utilities(regions)

    changed = _replace_features(
        regions,
        torch.cat(
            (
                torch.randn_like(regions.prior_features[..., :2]) * 100,
                regions.prior_features[..., 2:],
            ),
            dim=-1,
        ),
        torch.cat(
            (
                torch.randn_like(regions.current_features[..., :2]) * 100,
                regions.current_features[..., 2:],
            ),
            dim=-1,
        ),
    )
    changed_edge, changed_death, changed_birth = matcher.compute_utilities(changed)
    assert torch.equal(edge, changed_edge)
    assert torch.equal(death, changed_death)
    assert torch.equal(birth, changed_birth)

    generator = torch.Generator().manual_seed(13)
    orthogonal, _ = torch.linalg.qr(torch.randn(3, 3, generator=generator))
    rotated = _replace_features(
        regions,
        torch.cat(
            (
                regions.prior_features[..., :2],
                regions.prior_features[..., 2:] @ orthogonal,
            ),
            dim=-1,
        ),
        torch.cat(
            (
                regions.current_features[..., :2],
                regions.current_features[..., 2:] @ orthogonal,
            ),
            dim=-1,
        ),
    )
    rotated_edge, _, _ = matcher.compute_utilities(rotated)
    assert torch.allclose(edge, rotated_edge, atol=1e-6, rtol=0)
    assert torch.allclose(
        matcher.soft_plan(regions).transport,
        matcher.soft_plan(rotated).transport,
        atol=1e-6,
        rtol=0,
    )
    assert torch.equal(
        matcher.hard_plan(regions).transport,
        matcher.hard_plan(rotated).transport,
    )


def test_invariant_partial_ot_is_equivariant_to_endpoint_permutations():
    regions = _identity_fixture()
    matcher = InvariantPartialOTMatcher(feature_dim=5, sinkhorn_iterations=128)
    prior_order = torch.tensor([2, 0, 1])
    current_order = torch.tensor([1, 2, 0])
    permuted = RegionBatch(
        prior_features=regions.prior_features[:, prior_order],
        current_features=regions.current_features[:, current_order],
        prior_valid=regions.prior_valid[:, prior_order],
        current_valid=regions.current_valid[:, current_order],
        prior_anatomy=regions.prior_anatomy[:, prior_order],
        current_anatomy=regions.current_anatomy[:, current_order],
        prior_entity_ids=regions.prior_entity_ids[:, prior_order],
        current_entity_ids=regions.current_entity_ids[:, current_order],
    )
    original = matcher.soft_plan(regions).transport[0, :3, :3]
    reordered = matcher.soft_plan(permuted).transport[0, :3, :3]
    assert torch.allclose(
        reordered,
        original[prior_order][:, current_order],
        atol=1e-6,
        rtol=0,
    )
    original_hard = matcher.hard_plan(regions).transport[0, :3, :3]
    reordered_hard = matcher.hard_plan(permuted).transport[0, :3, :3]
    assert torch.equal(
        reordered_hard,
        original_hard[prior_order][:, current_order],
    )


def test_invariant_partial_ot_residual_is_bounded_and_preserves_order():
    matcher = InvariantPartialOTMatcher(feature_dim=5, residual_cap=0.02)
    matcher.residual_coefficient.data.fill_(3.0)
    cosine = torch.linspace(-1.0, 1.0, 257)
    residual = matcher.residual(cosine)
    utility = cosine + residual
    assert bool((residual.abs() < matcher.residual_cap).all())
    assert bool((utility[1:] > utility[:-1]).all())


def test_invariant_partial_ot_view_weights_change_two_view_global_assignment():
    prior_identity = torch.tensor([[[1.0, 0.0, 1.0, 0.0], [0.0, 1.0, 0.0, 1.0]]])
    current_identity = torch.tensor([[[1.0, 0.0, 0.0, 1.0], [0.0, 1.0, 1.0, 0.0]]])
    state = torch.zeros((1, 2, 2))
    regions = RegionBatch(
        prior_features=torch.cat((state, prior_identity), dim=-1),
        current_features=torch.cat((state, current_identity), dim=-1),
        prior_valid=torch.ones((1, 2), dtype=torch.bool),
        current_valid=torch.ones((1, 2), dtype=torch.bool),
        prior_anatomy=torch.zeros((1, 2), dtype=torch.long),
        current_anatomy=torch.zeros((1, 2), dtype=torch.long),
        prior_entity_ids=torch.arange(2, dtype=torch.long).unsqueeze(0),
        current_entity_ids=torch.arange(2, dtype=torch.long).unsqueeze(0),
    )
    matcher = InvariantPartialOTMatcher(feature_dim=6, identity_views=((2, 4), (4, 6)))
    matcher.view_weight_logits.data.copy_(torch.tensor([6.0, -6.0]))
    first_view_plan = matcher.hard_plan(regions)
    first_view_utility = first_view_plan.edge_logits.detach().clone()
    matcher.view_weight_logits.data.copy_(torch.tensor([-6.0, 6.0]))
    second_view_plan = matcher.hard_plan(regions)
    assert torch.equal(first_view_plan.transport[0, :2, :2], torch.eye(2))
    assert torch.equal(
        second_view_plan.transport[0, :2, :2], torch.flip(torch.eye(2), dims=(1,))
    )
    assert not torch.equal(first_view_utility, second_view_plan.edge_logits)
    weights = matcher.normalized_view_weights()
    assert bool((weights >= 0).all())
    assert torch.allclose(weights.sum(), torch.tensor(1.0))

    query_state_changed = _replace_features(
        regions,
        torch.cat((torch.full_like(state, 99.0), prior_identity), dim=-1),
        torch.cat((torch.full_like(state, -99.0), current_identity), dim=-1),
    )
    changed_utility = matcher.compute_utilities(query_state_changed)[0]
    assert torch.equal(second_view_plan.edge_logits, changed_utility)
    changed_utility[0, 0, 0].backward()
    assert matcher.view_weight_logits.grad is not None
    assert bool(matcher.view_weight_logits.grad.abs().sum() > 0)


def test_invariant_partial_ot_soft_and_hard_share_utilities_and_support():
    regions = _identity_fixture()
    matcher = InvariantPartialOTMatcher(
        feature_dim=5,
        temperature=0.05,
        sinkhorn_iterations=256,
    )
    soft = matcher.soft_plan(regions)
    hard = matcher.hard_plan(regions)
    soft.validate(regions, atol=1e-5)
    hard.validate_hard(regions)
    assert torch.equal(soft.edge_logits, hard.edge_logits)
    assert torch.equal(soft.prior_null_logits, hard.prior_null_logits)
    assert torch.equal(soft.current_null_logits, hard.current_null_logits)
    assert torch.equal(
        hard.transport[0, :3, :3].argmax(dim=-1), torch.tensor([1, 2, 0])
    )
    assert "objective_soft" in soft.diagnostics
    assert "objective_hard" not in soft.diagnostics
    assert "objective_hard" in hard.diagnostics
    assert "objective_soft" not in hard.diagnostics
    assert (
        soft.diagnostics["optimization_objective"]
        != hard.diagnostics["optimization_objective"]
    )

    weighted_mass = (
        soft.transport[:, :3, :3]
        * torch.tensor([[[0.1, 0.2, 0.4], [0.5, 0.3, 0.7], [0.8, 0.6, 0.9]]])
    ).sum()
    weighted_mass.backward()
    assert matcher.residual_coefficient.grad is not None
    assert matcher.prior_null_utility.grad is not None
    assert matcher.current_null_utility.grad is not None


def test_invariant_partial_ot_soft_and_hard_share_forbidden_support():
    regions = _identity_fixture()
    constrained = RegionBatch(
        prior_features=regions.prior_features,
        current_features=regions.current_features,
        prior_valid=regions.prior_valid,
        current_valid=regions.current_valid,
        prior_anatomy=regions.prior_anatomy,
        current_anatomy=torch.tensor([[0, 1, 0]]),
        prior_entity_ids=regions.prior_entity_ids,
        current_entity_ids=regions.current_entity_ids,
    )
    matcher = InvariantPartialOTMatcher(feature_dim=5, sinkhorn_iterations=256)
    soft = matcher.soft_plan(constrained)
    hard = matcher.hard_plan(constrained)

    assert torch.count_nonzero(soft.transport[0, :3, 1]) == 0
    assert torch.count_nonzero(hard.transport[0, :3, 1]) == 0
    soft.validate(constrained, atol=matcher.feasibility_tolerance)
    hard.validate_hard(constrained, atol=matcher.feasibility_tolerance)


@pytest.mark.parametrize(
    "null_utility_cap", [0.0, -0.1, 1.0, float("inf"), float("nan")]
)
def test_invariant_partial_ot_rejects_unsafe_null_utility_caps(null_utility_cap):
    with pytest.raises(ValueError, match="null_utility_cap"):
        InvariantPartialOTMatcher(
            feature_dim=5,
            null_utility_cap=null_utility_cap,
        )


def test_invariant_partial_ot_null_utilities_are_bounded_and_differentiable():
    matcher = InvariantPartialOTMatcher(feature_dim=5, null_utility_cap=0.1)
    matcher.prior_null_utility.data.fill_(1e6)
    matcher.current_null_utility.data.fill_(-1e6)

    effective_death, effective_birth = matcher.effective_null_utilities()
    assert float(effective_death) == pytest.approx(0.1)
    assert float(effective_birth) == pytest.approx(-0.1)
    typed_cap = effective_death.new_tensor(matcher.null_utility_cap)
    assert bool(effective_death.abs() <= typed_cap)
    assert bool(effective_birth.abs() <= typed_cap)

    matcher.zero_grad(set_to_none=True)
    matcher.prior_null_utility.data.fill_(0.25)
    matcher.current_null_utility.data.fill_(-0.25)
    effective_death, effective_birth = matcher.effective_null_utilities()
    (effective_death - effective_birth).backward()
    assert matcher.prior_null_utility.grad is not None
    assert matcher.current_null_utility.grad is not None
    assert float(matcher.prior_null_utility.grad) > 0
    assert float(matcher.current_null_utility.grad) < 0


def test_invariant_partial_ot_bounded_nulls_ignore_query_and_produce_legal_plans():
    regions = _identity_fixture()
    matcher = InvariantPartialOTMatcher(
        feature_dim=5,
        null_utility_cap=0.1,
        sinkhorn_iterations=256,
    )
    matcher.prior_null_utility.data.fill_(20.0)
    matcher.current_null_utility.data.fill_(-20.0)
    edge, death, birth = matcher.compute_utilities(regions)

    changed = _replace_features(
        regions,
        torch.cat(
            (
                torch.full_like(regions.prior_features[..., :2], 1e6),
                regions.prior_features[..., 2:],
            ),
            dim=-1,
        ),
        torch.cat(
            (
                torch.full_like(regions.current_features[..., :2], -1e6),
                regions.current_features[..., 2:],
            ),
            dim=-1,
        ),
    )
    changed_edge, changed_death, changed_birth = matcher.compute_utilities(changed)
    assert torch.equal(edge, changed_edge)
    assert torch.equal(death, changed_death)
    assert torch.equal(birth, changed_birth)

    soft = matcher.soft_plan(changed)
    hard = matcher.hard_plan(changed)
    soft.validate(changed, atol=matcher.feasibility_tolerance)
    hard.validate_hard(changed, atol=matcher.feasibility_tolerance)
    assert torch.equal(soft.edge_logits, hard.edge_logits)
    assert torch.equal(soft.prior_null_logits, hard.prior_null_logits)
    assert torch.equal(soft.current_null_logits, hard.current_null_logits)
    assert soft.diagnostics["null_utility_cap"] == pytest.approx(0.1)
    diagnostic_cap = soft.prior_null_logits.new_tensor(
        soft.diagnostics["null_utility_cap"]
    )
    assert bool(
        soft.diagnostics["effective_prior_null_utility"].abs() <= diagnostic_cap
    )
    assert bool(
        soft.diagnostics["effective_current_null_utility"].abs() <= diagnostic_cap
    )


def test_invariant_partial_ot_represents_both_null_sides_without_real_mass():
    regions = _identity_fixture()
    no_current = RegionBatch(
        prior_features=regions.prior_features,
        current_features=regions.current_features,
        prior_valid=regions.prior_valid,
        current_valid=torch.zeros_like(regions.current_valid),
        prior_anatomy=regions.prior_anatomy,
        current_anatomy=regions.current_anatomy,
        prior_entity_ids=regions.prior_entity_ids,
        current_entity_ids=regions.current_entity_ids,
    )
    no_prior = RegionBatch(
        prior_features=regions.prior_features,
        current_features=regions.current_features,
        prior_valid=torch.zeros_like(regions.prior_valid),
        current_valid=regions.current_valid,
        prior_anatomy=regions.prior_anatomy,
        current_anatomy=regions.current_anatomy,
        prior_entity_ids=regions.prior_entity_ids,
        current_entity_ids=regions.current_entity_ids,
    )
    matcher = InvariantPartialOTMatcher(feature_dim=5)
    death_plan = matcher.soft_plan(no_current)
    birth_plan = matcher.soft_plan(no_prior)
    assert torch.equal(death_plan.transport[0, :3, 3], torch.ones(3))
    assert torch.equal(birth_plan.transport[0, 3, :3], torch.ones(3))
    assert torch.count_nonzero(death_plan.transport[0, :3, :3]) == 0
    assert torch.count_nonzero(birth_plan.transport[0, :3, :3]) == 0
