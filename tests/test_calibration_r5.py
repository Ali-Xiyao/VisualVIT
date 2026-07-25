from __future__ import annotations

from dataclasses import replace

import pytest
import torch

from visualvit.calibration_r5 import (
    FEATURE_DIM,
    FROZEN_NULL_UTILITY_CAP,
    FROZEN_RESIDUAL_CAP,
    IDENTITY_VIEW_SLICES,
    LEARNED_FEASIBLE_VIEW_WEIGHTS,
    NULL_SUPPORT_SLICE,
    audit_r5_challenge,
    audit_r5_clean,
    audit_r5_row_local_train_to_development_attack,
    enumerate_r5_clean_assignment_certificate,
    make_frozen_r5_challenge_split,
    make_frozen_r5_clean_split,
    make_r5_anti_equivalence_challenge,
    make_r5_clean_batch,
    pairwise_view_cosines,
    r4_visible_hash,
    weighted_global_mapping,
)


def test_r5_clean_geometry_removes_the_null_tie() -> None:
    batch = make_r5_clean_batch(counterbalance_groups=1, seed=96_501)
    audit = audit_r5_clean(batch)

    assert audit["passed"]
    assert batch.regions.prior_features.shape == (15, 14, FEATURE_DIM)
    assert IDENTITY_VIEW_SLICES == ((2, 8), (8, 14))
    assert NULL_SUPPORT_SLICE == (14, 18)
    assert audit["identity_geometry"]["passed"]
    assert audit["identity_geometry"]["gold_cosines_by_view"] == pytest.approx(
        [1.0, 1.0], abs=1e-6
    )
    assert audit["identity_geometry"]["null_null_cosines_by_view"] == pytest.approx(
        [-1.0, -1.0], abs=1e-6
    )
    assert (
        max(
            audit["identity_geometry"][
                "maximum_absolute_persistent_null_cosine_by_view"
            ]
        )
        < 1e-6
    )
    assert audit["two_sided_partial_assignment"] == {
        "persistent_per_case": [12],
        "deaths_per_case": [2],
        "births_per_case": [2],
    }


def test_r5_clean_certificate_exhausts_every_partial_bijection() -> None:
    certificate = enumerate_r5_clean_assignment_certificate()

    assert certificate["passed"]
    assert certificate["anatomy_constrained"]
    assert certificate["partial_assignments_enumerated"] == 130_922
    assert certificate["null_utility_cap"] == FROZEN_NULL_UTILITY_CAP == 0.1
    assert certificate["residual_cap"] == FROZEN_RESIDUAL_CAP == 0.02
    assert certificate["views_have_identical_cosine_matrix"]
    assert certificate[
        "analytic_minimum_gap_before_numerical_deduction"
    ] == pytest.approx(0.7847681168808847)
    assert certificate["float32_worst_case_gap_deduction"] > 0
    assert certificate["minimum_robust_gap_lower_bound_per_anatomy"] == pytest.approx(
        0.7847614868808847
    )
    assert certificate["full_case_lower_bound"] > 0.78


def test_r5_clean_views_are_simplex_invariant_and_query_state_sealed() -> None:
    batch = make_r5_clean_batch(counterbalance_groups=1, seed=96_517)
    utilities = pairwise_view_cosines(batch.regions)
    assert torch.allclose(utilities[:, 0], utilities[:, 1], atol=1e-6)

    changed_prior = batch.regions.prior_features.clone()
    changed_current = batch.regions.current_features.clone()
    changed_prior[..., :2] = torch.randn_like(changed_prior[..., :2])
    changed_current[..., :2] = torch.randn_like(changed_current[..., :2])
    changed = replace(
        batch.regions,
        prior_features=changed_prior,
        current_features=changed_current,
    )
    assert torch.equal(
        pairwise_view_cosines(changed), pairwise_view_cosines(batch.regions)
    )


def test_r5_clean_one_sided_audits_have_no_pair_axis_resolution() -> None:
    audit = audit_r5_clean(make_r5_clean_batch(counterbalance_groups=2, seed=96_531))
    for side in ("prior", "current"):
        five = audit["one_sided_marginals"]["all_five_without_query_marker"][side]
        persistent = audit["one_sided_marginals"]["persistent_three_with_query_marker"][
            side
        ]
        assert five["passed"] and persistent["passed"]
        assert five["scope"] == persistent["scope"] == "single_side_no_pair_axis"
        assert not five["pair_axis_used"] and not persistent["pair_axis_used"]
        assert five["deterministic_signature_accuracy_upper_bound"] == pytest.approx(
            0.2
        )
        assert persistent[
            "deterministic_signature_accuracy_upper_bound"
        ] == pytest.approx(1.0 / 3.0)


def test_r5_challenge_requires_global_column_competition() -> None:
    batch = make_r5_anti_equivalence_challenge(counterbalance_groups=2, seed=93_501)
    audit = audit_r5_challenge(batch)
    competition = audit["global_column_competition"]

    assert audit["passed"]
    assert competition["passed"]
    assert competition["collision_blocks"] == competition["total_blocks"]
    assert (
        competition["query_rows_ambiguous_across_all_three_states"]
        == competition["total_query_rows"]
    )
    assert (
        competition["query_rows_with_gold_among_local_maxima"]
        == competition["total_query_rows"]
    )
    assert competition["hungarian_view1_exact_mapping_rate"] == 1.0
    assert competition["minimum_best_vs_second_assignment_gap"] > 0.36
    assert audit["view_weight_utility"]["equal_weight_exact_mapping_rate"] == 0.0

    learned_mapping, _ = weighted_global_mapping(batch, LEARNED_FEASIBLE_VIEW_WEIGHTS)
    assert torch.equal(learned_mapping, batch.oracle.gold_mapping)
    for marginal in audit["one_sided_marginals"].values():
        assert marginal["scope"] == "single_side_no_pair_axis"
        assert not marginal["pair_axis_used"]


def test_r5_challenge_distractor_is_frozen_and_row_local_independent() -> None:
    batch = make_frozen_r5_challenge_split("development")
    audit = audit_r5_challenge(batch)
    distractor = audit["frozen_distractor"]
    row_local = audit["row_local_query_argmax_state"]

    assert distractor["passed"]
    assert distractor["frozen_before_query_and_label_loop"]
    assert distractor["exact_distractor_mapping_rate"] == 1.0
    assert distractor["gold_edge_overlap_count"] == 0
    assert distractor["query_label_accuracy"] == pytest.approx(1.0 / 3.0)
    for name in ("view_1", "view_2", "combined_views"):
        assert row_local[name]["passed"]
        assert row_local[name]["exact_signature_counts_per_label"]
        assert row_local[name]["deterministic_accuracy_upper_bound"] == pytest.approx(
            1.0 / 3.0
        )

    nuisance_groups = torch.div(batch.oracle.prelabel_group, 3, rounding_mode="floor")
    for group in nuisance_groups.unique().tolist():
        cases = torch.nonzero(nuisance_groups == group).flatten()
        reference = batch.oracle.distractor_mapping[int(cases[0])]
        assert all(
            torch.equal(reference, batch.oracle.distractor_mapping[int(case)])
            for case in cases[1:]
        )
    assert not bool(
        (batch.oracle.distractor_mapping == batch.oracle.gold_mapping).any()
    )
    assert set(audit["hashes"]) == {"visible", "hidden_oracle", "full_fixture"}
    assert all(len(value) == 64 for value in audit["hashes"].values())
    assert (
        audit["hashes"]
        == audit_r5_challenge(make_frozen_r5_challenge_split("development"))["hashes"]
    )


def test_r5_row_local_train_to_development_attack_stays_at_chance() -> None:
    attack = audit_r5_row_local_train_to_development_attack()
    assert attack["passed"]
    assert attack["unseen_development_signature_count"] == 0
    assert attack["development_accuracy"] == pytest.approx(1.0 / 3.0)
    assert attack["development_macro_f1"] <= 1.0 / 3.0


def test_r5_three_frozen_splits_are_deterministic_and_distinct() -> None:
    names = ("train", "inner_development", "development")
    challenge_hashes = [
        r4_visible_hash(make_frozen_r5_challenge_split(name).regions) for name in names
    ]
    clean_hashes = [
        r4_visible_hash(make_frozen_r5_clean_split(name).regions) for name in names
    ]

    assert len(set(challenge_hashes)) == 3
    assert len(set(clean_hashes)) == 3
    assert set(challenge_hashes).isdisjoint(clean_hashes)
    assert challenge_hashes[0] == r4_visible_hash(
        make_frozen_r5_challenge_split("train").regions
    )
    assert clean_hashes[0] == r4_visible_hash(
        make_frozen_r5_clean_split("train").regions
    )
    with pytest.raises(ValueError, match="split must be one of"):
        make_frozen_r5_clean_split("test")
