from __future__ import annotations

from dataclasses import replace

import pytest
import torch

from visualvit.allocator import DeterministicGlobalAllocator
from visualvit.baselines import (
    BalancedSinkhornBaseline,
    DevelopmentFrozenThreshold,
    HungarianRejectBaseline,
)
from visualvit.calibration_query import (
    LABEL_IMPROVED,
    LABEL_NEW,
    LABEL_RESOLVED,
    LABEL_STABLE,
    LABEL_WORSE,
    QUERY_RELATION_SLOT,
    QUERY_GROUP_SIZE,
    REGISTERED_DERANGEMENT_SEEDS,
    STATE_VALUES,
    TOKEN_BUDGET,
    QueryAnchorQualificationError,
    _global_assignment_similarity,
    audit_distractor_counterbalance,
    audit_gold_id_relabel_invariance,
    audit_hidden_id_separation,
    audit_marginal_non_identifiability,
    audit_wrong_query_counterbalance,
    build_balanced_derangement_bank,
    build_query_relation_tokens,
    make_frozen_query_anchor_split,
    make_global_assignment_query_anchor_batch,
    make_query_anchor_batch,
    oracle_decode_labels,
    relabel_hidden_gold_ids,
    require_mechanism_gate_support,
    require_positive_recovery_denominator,
)
from visualvit.matching import NullAwareMatchGraph
from visualvit.tokenizer import build_soft_relation_candidates


DERANGEMENT_SEEDS = REGISTERED_DERANGEMENT_SEEDS


def _query_prior_index(batch: object, case_index: int) -> int:
    marker = batch.prior_query_marker[case_index]
    return int(torch.nonzero(marker, as_tuple=False).item())


def _visible_cosine_cost(batch: object) -> torch.Tensor:
    prior = torch.nn.functional.normalize(batch.regions.prior_features, dim=-1)
    current = torch.nn.functional.normalize(batch.regions.current_features, dim=-1)
    return 1.0 - torch.einsum("brd,bsd->brs", prior, current)


def test_anchor_has_strict_visible_gold_wall_and_registered_label_semantics() -> None:
    batch = make_query_anchor_batch(cases_per_label=3, seed=63_401)
    batch.validate()

    assert torch.bincount(batch.oracle.labels, minlength=5).tolist() == [3] * 5
    assert batch.persistent_main_mask.sum().item() == 9
    assert batch.null_control_mask.sum().item() == 6
    assert torch.equal(
        batch.persistent_main_mask,
        torch.isin(
            batch.oracle.labels,
            torch.tensor([LABEL_STABLE, LABEL_WORSE, LABEL_IMPROVED]),
        ),
    )
    assert torch.equal(
        batch.null_control_mask,
        torch.isin(batch.oracle.labels, torch.tensor([LABEL_NEW, LABEL_RESOLVED])),
    )

    marker_values = torch.cat(
        (batch.prior_query_marker.flatten(), batch.current_query_marker.flatten())
    )
    assert marker_values.dtype is torch.bool
    assert set(marker_values.to(torch.long).tolist()) == {0, 1}
    assert torch.equal(
        batch.prior_query_marker.sum(-1) + batch.current_query_marker.sum(-1),
        torch.ones(batch.oracle.labels.shape[0], dtype=torch.long),
    )

    hidden_audit = audit_hidden_id_separation(batch)
    assert hidden_audit["passed"]
    assert hidden_audit["visible_namespaces_disjoint"]
    assert hidden_audit["equality_join_gold_links"] == 0
    assert not hidden_audit["bijective_reconstruction_possible"]

    rp = batch.regions.prior_features.shape[1]
    rc = batch.regions.current_features.shape[1]
    real = batch.oracle.plan.transport[:, :rp, :rc]
    death = batch.oracle.plan.transport[:, :rp, rc]
    birth = batch.oracle.plan.transport[:, rp, :rc]
    expected_current_state = {
        LABEL_STABLE: 0.0,
        LABEL_WORSE: 1.0,
        LABEL_IMPROVED: -1.0,
    }
    for case_index, label_tensor in enumerate(batch.oracle.labels):
        label = int(label_tensor)
        if label <= LABEL_IMPROVED:
            prior_index = _query_prior_index(batch, case_index)
            assert float(batch.prior_states[case_index, prior_index]) == 0.0
            current_index = int(
                torch.nonzero(real[case_index, prior_index] > 0.5).item()
            )
            assert (
                float(batch.current_states[case_index, current_index])
                == expected_current_state[label]
            )
            query_anatomy = batch.regions.prior_anatomy[case_index, prior_index]
            persistent_in_group = 0
            for candidate in range(rp):
                if (
                    batch.regions.prior_anatomy[case_index, candidate] == query_anatomy
                    and real[case_index, candidate].sum() > 0.5
                ):
                    persistent_in_group += 1
            assert persistent_in_group == QUERY_GROUP_SIZE
        elif label == LABEL_NEW:
            current_index = int(
                torch.nonzero(batch.current_query_marker[case_index]).item()
            )
            assert birth[case_index, current_index] == 1
        else:
            prior_index = _query_prior_index(batch, case_index)
            assert death[case_index, prior_index] == 1

    assert torch.equal(
        batch.prior_carrier_control.sum(-1),
        torch.ones(batch.oracle.labels.shape[0], dtype=torch.long),
    )
    assert torch.equal(
        batch.current_carrier_control.sum(-1),
        torch.ones(batch.oracle.labels.shape[0], dtype=torch.long),
    )
    carrier_death = death * batch.prior_carrier_control
    carrier_birth = birth * batch.current_carrier_control
    background_death = death * (~batch.prior_carrier_control)
    background_birth = birth * (~batch.current_carrier_control)
    assert torch.equal(carrier_death.sum(-1), torch.ones_like(carrier_death.sum(-1)))
    assert torch.equal(carrier_birth.sum(-1), torch.ones_like(carrier_birth.sum(-1)))
    assert torch.equal(
        background_death.sum(-1), torch.ones_like(background_death.sum(-1))
    )
    assert torch.equal(
        background_birth.sum(-1), torch.ones_like(background_birth.sum(-1))
    )

    distractor_audit = audit_distractor_counterbalance(batch)
    assert distractor_audit["passed"]
    assert distractor_audit["state_anatomy_marginals_identical"]
    assert distractor_audit["label_counts_exactly_balanced"]


def test_frozen_inner_development_split_has_8_cases_per_label() -> None:
    batch = make_frozen_query_anchor_split("inner_development")
    assert batch.oracle.labels.shape == (40,)
    assert torch.bincount(batch.oracle.labels, minlength=5).tolist() == [8] * 5


def test_persistent_query_carrier_is_prelabel_and_label_balanced() -> None:
    batch = make_query_anchor_batch(cases_per_label=4, seed=63_419)
    # Generator order is replicate-major. Within each block, the three
    # persistent labels reuse the exact pre-label query carrier and source.
    for replicate in range(4):
        cases = [replicate * 5 + label for label in range(3)]
        query_indices = [_query_prior_index(batch, case) for case in cases]
        assert len(set(query_indices)) == 1
        query_index = query_indices[0]
        for case in cases[1:]:
            assert torch.equal(
                batch.regions.prior_features[cases[0], query_index],
                batch.regions.prior_features[case, query_index],
            )
            assert torch.equal(
                batch.prior_query_marker[cases[0]],
                batch.prior_query_marker[case],
            )
            assert torch.equal(
                batch.regions.prior_valid[cases[0]],
                batch.regions.prior_valid[case],
            )


def test_visible_only_oracle_decoder_is_exact_and_tokens_have_no_side_channel() -> None:
    batch = make_query_anchor_batch(cases_per_label=2, seed=64_401)
    decoded = oracle_decode_labels(
        batch.regions,
        batch.prior_query_marker,
        batch.current_query_marker,
        batch.oracle.plan,
    )
    assert torch.equal(decoded, batch.oracle.labels)

    contract = build_query_relation_tokens(
        batch.regions,
        batch.prior_query_marker,
        batch.current_query_marker,
        batch.oracle.plan,
    )
    contract.validate()
    assert contract.tokens.shape == (10, TOKEN_BUDGET, 8)
    assert not contract.neutral_embedding.requires_grad
    assert torch.count_nonzero(contract.neutral_embedding) == 0
    assert torch.equal(
        contract.query_relation_slot,
        torch.full((10,), QUERY_RELATION_SLOT, dtype=torch.long),
    )
    nonquery = contract.tokens.clone()
    nonquery[:, QUERY_RELATION_SLOT] = 0
    assert torch.count_nonzero(nonquery) == 0

    # Mask, position, type and physical carrier are identical for every label.
    for case_index in range(1, 10):
        assert torch.equal(contract.valid_mask[0], contract.valid_mask[case_index])
        assert torch.equal(
            contract.attention_mask[0], contract.attention_mask[case_index]
        )
        assert torch.equal(
            contract.position_ids[:, 0], contract.position_ids[:, case_index]
        )
    assert contract.token_types.shape == (64,)
    projected = contract.to_projected_bundle()
    projected.validate(token_budget=64)
    assert projected.position_ids.shape == (3, 10, 64)
    assert projected.audit["literal_zero_nonquery_payloads"]


def test_frozen_anchor_is_rejected_by_pooled_marginal_bypass_attacks() -> None:
    batch = make_frozen_query_anchor_split("development")
    audit = audit_marginal_non_identifiability(batch)
    assert not audit["passed"]
    assert "finite preregistered" in audit["scope"]
    assert audit["feature_channels_covered"] == batch.regions.prior_features.shape[-1]
    for control in audit["controls"].values():
        assert not control["deterministic_reconstruction_possible"]
        assert control["best_signature_macro_f1"] <= 0.45
    plain = audit["pooled_bypass_attacks"]["state_conditioned_kernel_mean"]
    anatomy = audit["pooled_bypass_attacks"]["anatomy_state_conditioned_kernel_mean"]
    assert plain["macro_f1"] == pytest.approx(0.8078325728004105)
    assert plain["accuracy"] == pytest.approx(0.8055555555555556)
    assert plain["confusion_matrix"] == [[21, 2, 1], [5, 19, 0], [4, 2, 18]]
    assert anatomy["macro_f1"] == pytest.approx(0.8740017746228926)
    assert not plain["uses_pair_axis"]
    assert plain["permutation_invariant_per_side"]


def test_r2_global_assignment_gadget_separates_local_from_global_matching() -> None:
    similarity = _global_assignment_similarity((0, 1, 2))
    assert similarity.dtype == torch.float64
    assert torch.allclose(
        similarity.square().sum(dim=0),
        torch.full((6,), 122.0, dtype=torch.float64),
        atol=1e-10,
        rtol=0,
    )
    normalized = similarity / (122.0**0.5)
    cost = (1.0 - normalized).unsqueeze(0).float()
    support = torch.ones_like(cost, dtype=torch.bool)
    marginal = torch.ones(1, 6)
    threshold = DevelopmentFrozenThreshold(
        1.0,
        source_split="development-inner-synthetic",
        selection_rule="R2 preregistered visible-cosine threshold",
    )
    hungarian = HungarianRejectBaseline(threshold)(cost, support, marginal, marginal)
    expected = torch.tensor([0, 2, 4, 1, 3, 5])
    hard = hungarian.transport[0, :6, :6].argmax(dim=-1)
    assert torch.equal(hard, expected)

    sinkhorn = BalancedSinkhornBaseline(epsilon=0.05, iterations=2048)(
        cost, support, marginal, marginal
    )
    soft = sinkhorn.transport[0, :6, :6]
    assert torch.equal(soft.argmax(dim=-1), expected)
    oracle_mass = soft[torch.arange(6), expected]
    assert float(oracle_mass.min()) == pytest.approx(0.9425426721572876)
    assert float(oracle_mass.min()) >= 0.90


def test_r2_persistent_query_identity_is_prelabel_and_conditionally_balanced() -> None:
    cases_per_label = 8
    batch = make_global_assignment_query_anchor_batch(
        cases_per_label=cases_per_label, seed=74_401
    )
    marker_positions_by_label: list[list[int]] = [[], [], []]
    for replicate in range(cases_per_label):
        cases = [replicate * 5 + label for label in range(3)]
        query_indices = [_query_prior_index(batch, case) for case in cases]
        assert len(set(query_indices)) == 1
        query_index = query_indices[0]
        for label, case in enumerate(cases):
            marker_positions_by_label[label].append(query_index)
            assert torch.equal(
                batch.prior_query_marker[cases[0]],
                batch.prior_query_marker[case],
            )
            assert torch.equal(
                batch.regions.prior_features[cases[0], query_index],
                batch.regions.prior_features[case, query_index],
            )
            assert torch.equal(
                batch.regions.prior_anatomy[cases[0]],
                batch.regions.prior_anatomy[case],
            )
    assert marker_positions_by_label[0] == marker_positions_by_label[1]
    assert marker_positions_by_label[1] == marker_positions_by_label[2]


def test_r2_anchor_passes_registered_finite_marginal_stress_suite() -> None:
    batch = make_global_assignment_query_anchor_batch(cases_per_label=6, seed=75_401)
    audit = audit_marginal_non_identifiability(batch)
    assert audit["passed"]
    assert audit["maximum_observed_macro_f1"] <= 0.45
    assert audit_distractor_counterbalance(batch)["passed"]
    decoded = oracle_decode_labels(
        batch.regions,
        batch.prior_query_marker,
        batch.current_query_marker,
        batch.oracle.plan,
    )
    assert torch.equal(decoded, batch.oracle.labels)


def test_all_visible_feature_marginal_audit_rejects_direct_label_leak() -> None:
    batch = make_query_anchor_batch(cases_per_label=8, seed=65_401)
    leaked_current = batch.regions.current_features.clone()
    leaked_current[..., -1] = batch.oracle.labels[:, None].to(leaked_current.dtype)
    leaked_regions = replace(batch.regions, current_features=leaked_current)
    leaked = replace(batch, regions=leaked_regions)
    leaked.validate()
    audit = audit_marginal_non_identifiability(leaked)
    assert not audit["passed"]
    assert audit["controls"]["current_only"]["deterministic_reconstruction_possible"]
    assert audit["controls"]["current_only"]["best_signature_macro_f1"] == 1.0


def test_crossed_d3_uses_three_distinct_wrong_targets_and_plan_hashes() -> None:
    batch = make_query_anchor_batch(cases_per_label=3, seed=65_417)
    bank = build_balanced_derangement_bank(batch, DERANGEMENT_SEEDS)
    audit = audit_wrong_query_counterbalance(batch, bank)
    assert audit["passed"]
    assert audit["exact_per_label_and_derangement"]
    assert audit["three_distinct_wrong_targets_per_case"]
    assert audit["three_distinct_plan_hashes"]
    assert len(set(audit["plan_hashes"].values())) == 3
    assert audit["zero_fixed_points"]
    assert audit["null_sets_preserved"]

    # Every persistent query visits -1, 0 and +1 exactly once across D=3.
    rc = batch.regions.current_features.shape[1]
    for case_index in torch.nonzero(batch.persistent_main_mask).flatten().tolist():
        prior_index = _query_prior_index(batch, case_index)
        states = []
        targets = []
        for plan in bank.values():
            current_index = int(
                torch.nonzero(plan.transport[case_index, prior_index, :rc] > 0.5).item()
            )
            targets.append(current_index)
            states.append(float(batch.current_states[case_index, current_index]))
        assert len(set(targets)) == 3
        assert set(states) == set(STATE_VALUES)


def test_derangement_id_mapping_is_invariant_to_seed_input_order() -> None:
    batch = make_query_anchor_batch(cases_per_label=3, seed=65_417)
    forward = build_balanced_derangement_bank(batch, DERANGEMENT_SEEDS)
    reversed_bank = build_balanced_derangement_bank(
        batch, tuple(reversed(DERANGEMENT_SEEDS))
    )
    assert tuple(forward) == DERANGEMENT_SEEDS
    assert tuple(reversed_bank) == DERANGEMENT_SEEDS
    for seed in DERANGEMENT_SEEDS:
        assert torch.equal(
            forward[seed].transport,
            reversed_bank[seed].transport,
        )
    with pytest.raises(QueryAnchorQualificationError, match="exactly"):
        build_balanced_derangement_bank(batch, (1, 2, 3, 4))


def test_hidden_gold_regeneration_leaves_visible_cost_plan_tokens_and_score_bitwise() -> (
    None
):
    batch = make_query_anchor_batch(cases_per_label=2, seed=63_433)
    relabeled = relabel_hidden_gold_ids(batch, seed=999_991)

    before_tokens = build_query_relation_tokens(
        batch.regions,
        batch.prior_query_marker,
        batch.current_query_marker,
        batch.oracle.plan,
    )
    after_tokens = build_query_relation_tokens(
        relabeled.regions,
        relabeled.prior_query_marker,
        relabeled.current_query_marker,
        relabeled.oracle.plan,
    )
    torch.manual_seed(91_001)
    matcher = NullAwareMatchGraph(feature_dim=batch.regions.prior_features.shape[-1])
    learned_before = matcher.soft_plan(batch.regions)
    learned_after = matcher.soft_plan(relabeled.regions)
    allocator = DeterministicGlobalAllocator()
    allocation_before = allocator(
        build_soft_relation_candidates(batch.regions, learned_before)
    )
    allocation_after = allocator(
        build_soft_relation_candidates(relabeled.regions, learned_after)
    )
    outputs_before = {
        "baseline_cost": _visible_cosine_cost(batch),
        "learned_plan": learned_before,
        "allocation": allocation_before.weights,
        "query_tokens": before_tokens.tokens,
        "score": before_tokens.tokens.sum(dim=(-2, -1)),
    }
    outputs_after = {
        "baseline_cost": _visible_cosine_cost(relabeled),
        "learned_plan": learned_after,
        "allocation": allocation_after.weights,
        "query_tokens": after_tokens.tokens,
        "score": after_tokens.tokens.sum(dim=(-2, -1)),
    }
    audit = audit_gold_id_relabel_invariance(
        batch,
        relabeled,
        outputs_before=outputs_before,
        outputs_after=outputs_after,
    )
    assert audit["passed"]
    assert all(audit["checks"].values())


def test_mechanism_support_and_recovery_checks_fail_closed() -> None:
    development_labels = torch.arange(5, dtype=torch.long).repeat_interleave(24)
    development = make_frozen_query_anchor_split("development")
    plans = build_balanced_derangement_bank(development, DERANGEMENT_SEEDS)
    derangement_audit = audit_wrong_query_counterbalance(development, plans)
    qualified = require_mechanism_gate_support(
        development_labels,
        DERANGEMENT_SEEDS,
        derangement_audit=derangement_audit,
        minimum_per_label=24,
    )
    assert qualified["status"] == "QUALIFIED"
    assert qualified["derangement_count"] == 3
    assert qualified["per_label_counts"] == [24] * 5

    with pytest.raises(QueryAnchorQualificationError, match="exact registered"):
        require_mechanism_gate_support(
            development_labels,
            DERANGEMENT_SEEDS[:2],
            derangement_audit=derangement_audit,
            minimum_per_label=24,
        )
    with pytest.raises(QueryAnchorQualificationError, match="exact registered"):
        require_mechanism_gate_support(
            development_labels,
            (1, 2, 3, 4),
            derangement_audit=derangement_audit,
            minimum_per_label=24,
        )
    with pytest.raises(QueryAnchorQualificationError, match="DERANGEMENT_AUDIT"):
        require_mechanism_gate_support(
            development_labels,
            DERANGEMENT_SEEDS,
            derangement_audit=None,
            minimum_per_label=24,
        )
    with pytest.raises(QueryAnchorQualificationError, match="DEVELOPMENT_SUPPORT"):
        require_mechanism_gate_support(
            torch.arange(5, dtype=torch.long).repeat_interleave(2),
            DERANGEMENT_SEEDS,
            derangement_audit=derangement_audit,
            minimum_per_label=24,
        )
    for denominator in (0.0, -0.1, float("nan")):
        with pytest.raises(QueryAnchorQualificationError, match="RECOVERY_DENOMINATOR"):
            require_positive_recovery_denominator(denominator)
    assert require_positive_recovery_denominator(0.01) == 0.01


def test_corrupt_visible_cross_time_id_equality_fails_closed() -> None:
    batch = make_query_anchor_batch(cases_per_label=1, seed=63_437)
    corrupted_ids = batch.regions.current_entity_ids.clone()
    corrupted_ids[0, 0] = batch.regions.prior_entity_ids[0, 0]
    corrupted_regions = replace(batch.regions, current_entity_ids=corrupted_ids)
    corrupted = replace(batch, regions=corrupted_regions)
    with pytest.raises(ValueError, match="namespaces must be disjoint"):
        corrupted.validate()
