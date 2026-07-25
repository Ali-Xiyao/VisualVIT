from __future__ import annotations

from dataclasses import replace

import pytest
import torch

from visualvit.calibration_r4 import (
    FEATURE_DIM,
    IDENTITY_VIEW_SLICES,
    LEARNED_FEASIBLE_VIEW_WEIGHTS,
    NULL_SUPPORT_SLICE,
    audit_r4_challenge,
    audit_r4_clean,
    challenge_oracle_plan,
    decode_clean_query_labels,
    make_frozen_r4_challenge_split,
    make_r4_anti_equivalence_challenge,
    make_r4_clean_batch,
    pairwise_view_cosines,
    r4_hidden_oracle_hash,
    r4_visible_hash,
    weighted_global_mapping,
)
from visualvit.matching import InvariantPartialOTMatcher


def test_r4_feature_contract_and_information_wall_are_exact() -> None:
    batch = make_r4_anti_equivalence_challenge(counterbalance_groups=2, seed=83_401)
    audit = audit_r4_challenge(batch)

    assert batch.regions.prior_features.shape == (18, 12, FEATURE_DIM)
    assert IDENTITY_VIEW_SLICES == ((2, 8), (8, 14))
    assert NULL_SUPPORT_SLICE == (14, 18)
    assert audit["feature_contract"]["identity_view_slices"] == [[2, 8], [8, 14]]
    assert audit["information_wall"]["passed"]
    assert audit["information_wall"]["hidden_identity_values_absent"]
    assert audit["information_wall"]["oracle_cardinality_field_absent"]
    assert audit["information_wall"]["forbidden_visible_schema_fields"] == []
    assert audit["prelabel_query"]["passed"]

    # Hidden-label edits cannot change the independently hashed visible input.
    changed_oracle = replace(batch.oracle, labels=batch.oracle.labels.roll(1))
    assert r4_visible_hash(batch.regions) == audit["hashes"]["visible"]
    assert r4_hidden_oracle_hash(changed_oracle) != audit["hashes"]["hidden_oracle"]


def test_r4_one_sided_marginals_have_only_chance_label_resolution() -> None:
    audit = audit_r4_challenge(
        make_r4_anti_equivalence_challenge(counterbalance_groups=3, seed=83_417)
    )
    for side in ("prior", "current"):
        marginal = audit["one_sided_marginals"][side]
        assert marginal["passed"]
        assert marginal["exact_signature_counts_per_label"]
        assert marginal[
            "deterministic_signature_accuracy_upper_bound"
        ] == pytest.approx(1.0 / 3.0)
        assert len(set(marginal["signature_multiset_hashes"].values())) == 1


def test_r4_equal_weight_and_fixed_concatenation_fail_but_weighted_global_is_feasible() -> (
    None
):
    batch = make_r4_anti_equivalence_challenge(counterbalance_groups=3, seed=83_431)
    audit = audit_r4_challenge(batch)
    utility = audit["view_weight_utility"]

    assert audit["passed"]
    assert utility["oracle_view_exact_mapping_rate"] == 1.0
    assert utility["cyclic_view_exact_derangement_rate"] == 1.0
    assert utility["equal_weight_exact_mapping_rate"] == 0.0
    assert utility["equal_weight_query_label_accuracy"] <= 1.0 / 3.0
    assert utility["fixed_concatenated_exact_mapping_rate"] == 0.0
    assert utility["fixed_concatenated_query_label_accuracy"] <= 1.0 / 3.0
    assert utility["equal_vs_concatenated_max_utility_error"] < 1e-6
    assert (
        0.0 < LEARNED_FEASIBLE_VIEW_WEIGHTS[1] < LEARNED_FEASIBLE_VIEW_WEIGHTS[0] < 1.0
    )
    assert utility["learned_weight_exact_mapping_rate"] == 1.0
    assert utility["learned_weight_query_label_accuracy"] == 1.0

    learned_mapping, _ = weighted_global_mapping(batch, LEARNED_FEASIBLE_VIEW_WEIGHTS)
    assert torch.equal(learned_mapping, batch.oracle.gold_mapping)


def test_r4_frozen_splits_are_deterministic_and_distinct() -> None:
    train_a = make_frozen_r4_challenge_split("train")
    train_b = make_frozen_r4_challenge_split("train")
    development = make_frozen_r4_challenge_split("development")
    train_audit = audit_r4_challenge(train_a)
    train_b_audit = audit_r4_challenge(train_b)
    development_audit = audit_r4_challenge(development)

    assert train_audit["hashes"] == train_b_audit["hashes"]
    assert train_audit["hashes"]["visible"] != development_audit["hashes"]["visible"]
    assert pairwise_view_cosines(train_a.regions).shape == (36, 2, 12, 12)
    with pytest.raises(ValueError, match="split must be one of"):
        make_frozen_r4_challenge_split("test")


def test_r4_clean_has_two_aligned_unit_views_and_exact_partial_oracle() -> None:
    batch = make_r4_clean_batch(counterbalance_groups=2, seed=86_401)
    audit = audit_r4_clean(batch)
    real = batch.oracle.plan.transport[:, :14, :14]
    death = batch.oracle.plan.transport[:, :14, 14]
    birth = batch.oracle.plan.transport[:, 14, :14]

    assert audit["passed"]
    assert audit["view_agreement"]["same_gold_global_mapping"]
    assert audit["view_agreement"]["view_exact_persistent_mapping_rates"] == [
        1.0,
        1.0,
    ]
    assert audit["directional_null_support"]["passed"]
    assert torch.equal(real.sum(dim=(-2, -1)), torch.full((30,), 12.0))
    assert torch.equal(death.sum(dim=-1), torch.full((30,), 2.0))
    assert torch.equal(birth.sum(dim=-1), torch.full((30,), 2.0))
    assert torch.equal(
        decode_clean_query_labels(batch, batch.oracle.plan), batch.oracle.labels
    )

    null_slice = slice(*NULL_SUPPORT_SLICE)
    for features in (batch.regions.prior_features, batch.regions.current_features):
        null_rows = features[..., null_slice].abs().sum(dim=-1) > 0
        for start, stop in IDENTITY_VIEW_SLICES:
            norms = features[..., start:stop].norm(dim=-1)
            assert torch.allclose(
                norms.masked_select(~null_rows),
                torch.ones_like(norms.masked_select(~null_rows)),
                atol=1e-6,
            )
            assert torch.count_nonzero(norms.masked_select(null_rows)) == 0


def test_r4_clean_five_label_and_persistent_marginal_audits_are_exact() -> None:
    audit = audit_r4_clean(make_r4_clean_batch(counterbalance_groups=2, seed=86_417))
    query = audit["five_label_query"]
    assert query["passed"]
    assert query["label_counts"] == [6, 6, 6, 6, 6]
    assert query["persistent_query_prelabel_fixed"]
    for side in ("prior", "current"):
        five = audit["one_sided_marginals"]["all_five_without_query_marker"][side]
        persistent = audit["one_sided_marginals"]["persistent_three_with_query_marker"][
            side
        ]
        assert five["passed"]
        assert five["deterministic_signature_accuracy_upper_bound"] == pytest.approx(
            0.2
        )
        assert persistent["passed"]
        assert persistent[
            "deterministic_signature_accuracy_upper_bound"
        ] == pytest.approx(1.0 / 3.0)


def test_one_matcher_parameter_witness_solves_r4_clean_and_challenge() -> None:
    clean = make_r4_clean_batch(counterbalance_groups=1, seed=86_401)
    challenge = make_r4_anti_equivalence_challenge(counterbalance_groups=1, seed=83_401)
    matcher = InvariantPartialOTMatcher(
        feature_dim=FEATURE_DIM,
        identity_views=IDENTITY_VIEW_SLICES,
        residual_cap=0.02,
        sinkhorn_iterations=64,
    )
    matcher.view_weight_logits.data.copy_(
        torch.tensor(LEARNED_FEASIBLE_VIEW_WEIGHTS).log()
    )
    matcher.prior_null_utility.data.fill_(0.05)
    matcher.current_null_utility.data.fill_(0.05)

    assert torch.equal(
        matcher.hard_plan(clean.regions).transport, clean.oracle.plan.transport
    )
    assert torch.equal(
        matcher.hard_plan(challenge.regions).transport,
        challenge_oracle_plan(challenge).transport,
    )


def test_joint_soft_training_recovers_clean_and_challenge_with_one_matcher() -> None:
    clean = make_r4_clean_batch(counterbalance_groups=1, seed=86_431)
    challenge = make_r4_anti_equivalence_challenge(counterbalance_groups=1, seed=83_431)
    challenge_target = challenge_oracle_plan(challenge)
    torch.manual_seed(7)
    matcher = InvariantPartialOTMatcher(
        feature_dim=FEATURE_DIM,
        identity_views=IDENTITY_VIEW_SLICES,
        residual_cap=0.02,
        temperature=0.05,
        sinkhorn_iterations=32,
    )
    optimizer = torch.optim.Adam(matcher.parameters(), lr=0.15)
    for _ in range(80):
        optimizer.zero_grad()
        loss = torch.zeros(())
        for batch, target in (
            (clean, clean.oracle.plan),
            (challenge, challenge_target),
        ):
            plan = matcher.soft_plan(batch.regions)
            target_cells = target.transport > 0.5
            loss = (
                loss
                - plan.transport.clamp_min(1e-8)
                .log()
                .masked_select(target_cells)
                .mean()
            )
        loss.backward()
        optimizer.step()

    assert float(matcher.normalized_view_weights()[0]) >= 0.95
    assert torch.equal(
        matcher.hard_plan(clean.regions).transport, clean.oracle.plan.transport
    )
    assert torch.equal(
        matcher.hard_plan(challenge.regions).transport,
        challenge_target.transport,
    )
