from copy import deepcopy
import json

import pytest
import torch

from visualvit.matching import InvariantPartialOTMatcher
from visualvit.r6_structural_audits import (
    R6_REQUIRED_PER_CASE_EVIDENCE,
    R6_STRUCTURAL_AUDIT_SCHEMA_VERSION,
    R6_STRUCTURAL_CASE_IDS,
    canonical_sha256,
    run_r6_structural_audits,
    validate_r6_structural_audit,
)


def _matcher() -> InvariantPartialOTMatcher:
    return InvariantPartialOTMatcher(
        feature_dim=18,
        identity_views=((2, 8), (8, 14)),
        temperature=0.05,
        sinkhorn_iterations=256,
    )


def _reseal(report: dict[str, object]) -> None:
    report["ordered_microcase_projection_sha256"] = canonical_sha256(
        [
            {"case_id": case_id, "evidence": report["microcases"][case_id]}
            for case_id in report["required_case_ids"]
        ]
    )
    _reseal_audit(report)


def _reseal_audit(report: dict[str, object]) -> None:
    report["audit_sha256"] = canonical_sha256(
        {key: value for key, value in report.items() if key != "audit_sha256"}
    )


def test_r6_structural_audit_runs_exact_eight_cases_without_mutation() -> None:
    matcher = _matcher()
    before = {
        name: value.detach().clone() for name, value in matcher.state_dict().items()
    }
    report = run_r6_structural_audits(matcher)

    assert report["schema_version"] == R6_STRUCTURAL_AUDIT_SCHEMA_VERSION
    assert report["passed"]
    assert report["required_case_ids"] == list(R6_STRUCTURAL_CASE_IDS)
    assert report["required_per_case_evidence"] == list(R6_REQUIRED_PER_CASE_EVIDENCE)
    assert list(report["microcases"]) == list(R6_STRUCTURAL_CASE_IDS)
    assert report["ordered_microcase_projection_sha256"] == canonical_sha256(
        [
            {"case_id": case_id, "evidence": report["microcases"][case_id]}
            for case_id in report["required_case_ids"]
        ]
    )
    for case in report["microcases"].values():
        assert set(case) == set(R6_REQUIRED_PER_CASE_EVIDENCE)
        assert case["input_sha256_before"] == case["input_sha256_after"]
        assert case["expected_plan_exact"]["hard_plan_matches_expected"]
        assert case["feasibility_residuals"]["hard_optimality_gap"] == 0.0
        assert case["feasibility_residuals"]["lexicographic_tie_selected"]
        assert all(
            case["completion_counts"][key]
            for key in (
                "hard_covers_every_prior_once",
                "hard_covers_every_current_once",
                "persistent_death_birth_partition_exact",
                "no_duplicate_real_current",
            )
        )
    gradient = report["registered_gradient_audit"]
    assert gradient["registered_parameter_names"] == [
        "view_weight_logits[0]",
        "view_weight_logits[1]",
        "residual_coefficient",
        "prior_null_utility",
        "current_null_utility",
    ]
    assert gradient["finite_gradients"]
    assert gradient["nonzero_expected_gradient_each_trainable_parameter"]
    assert gradient["forbidden_input_or_query_gradient"]
    assert gradient["optimizer_owner_exact"]
    assert matcher.state_dict().keys() == before.keys()
    assert all(
        torch.equal(matcher.state_dict()[name], value) for name, value in before.items()
    )


def test_r6_structural_audit_survives_sorted_json_round_trip() -> None:
    report = run_r6_structural_audits(_matcher())
    loaded = json.loads(json.dumps(report, sort_keys=True))

    assert list(loaded["microcases"]) != list(R6_STRUCTURAL_CASE_IDS)
    assert loaded["required_case_ids"] == list(R6_STRUCTURAL_CASE_IDS)
    validate_r6_structural_audit(loaded)


def test_r6_structural_audit_exact_expected_plans_cover_all_case_classes() -> None:
    cases = run_r6_structural_audits(_matcher())["microcases"]
    assert cases["one_persistent_1x1"]["completion_counts"]["persistent_count"] == 1
    assert cases["one_death_1x0"]["completion_counts"]["death_count"] == 1
    assert cases["one_birth_0x1"]["completion_counts"]["birth_count"] == 1
    assert cases["collision_2x1"]["completion_counts"] == {
        "valid_prior_count": 2,
        "valid_current_count": 1,
        "persistent_count": 1,
        "death_count": 1,
        "birth_count": 0,
        "hard_covers_every_prior_once": True,
        "hard_covers_every_current_once": True,
        "persistent_death_birth_partition_exact": True,
        "no_duplicate_real_current": True,
    }
    crossing = cases["crossing_2x2"]["expected_plan_exact"]["hard_transport"]
    assert crossing[:2] == [[0.0, 1.0, 0.0], [1.0, 0.0, 0.0]]
    tied = cases["tied_utility_2x2"]["expected_plan_exact"]
    assert tied["hard_transport"] == tied["expected_hard_transport"]
    mixed = cases["mixed_persistent_death_birth_2x2"]["completion_counts"]
    assert (mixed["persistent_count"], mixed["death_count"], mixed["birth_count"]) == (
        1,
        1,
        1,
    )
    forbidden = cases["anatomy_forbidden_edge"]["feasibility_residuals"]
    assert forbidden["forbidden_hard_mass"] == 0.0
    assert forbidden["forbidden_soft_mass"] == 0.0


def test_validator_recomputes_optimality_after_attacker_reseals() -> None:
    report = run_r6_structural_audits(_matcher())
    tampered = deepcopy(report)
    tampered["microcases"]["collision_2x1"]["feasibility_residuals"][
        "selected_utility"
    ] += 0.25
    _reseal(tampered)
    with pytest.raises(ValueError, match="selected_utility is not derivable"):
        validate_r6_structural_audit(tampered)


def test_validator_recomputes_completion_counts_after_attacker_reseals() -> None:
    report = run_r6_structural_audits(_matcher())
    tampered = deepcopy(report)
    tampered["microcases"]["mixed_persistent_death_birth_2x2"]["completion_counts"][
        "birth_count"
    ] = 0
    _reseal(tampered)
    with pytest.raises(ValueError, match="completion counts are not derivable"):
        validate_r6_structural_audit(tampered)


def test_validator_recomputes_nested_hashes_and_detects_input_mutation() -> None:
    report = run_r6_structural_audits(_matcher())
    tampered = deepcopy(report)
    tampered["microcases"]["crossing_2x2"]["input_sha256_after"] = "0" * 64
    _reseal(tampered)
    with pytest.raises(ValueError, match="input-after hash mismatch"):
        validate_r6_structural_audit(tampered)


def test_validator_rejects_wrong_tie_plan_even_when_resealed() -> None:
    report = run_r6_structural_audits(_matcher())
    tampered = deepcopy(report)
    tied = tampered["microcases"]["tied_utility_2x2"]
    alternative = [
        [0.0, 1.0, 0.0],
        [1.0, 0.0, 0.0],
        [0.0, 0.0, 0.0],
    ]
    tied["expected_plan_exact"]["hard_transport"] = alternative
    tied["expected_plan_exact"]["expected_hard_transport"] = alternative
    tied["hard_plan_sha256"] = canonical_sha256(alternative)
    _reseal(tampered)
    with pytest.raises(ValueError, match="lexicographic_tie_selected is not derivable"):
        validate_r6_structural_audit(tampered)


def test_validator_rejects_gradient_tamper_even_when_resealed() -> None:
    report = run_r6_structural_audits(_matcher())
    tampered = deepcopy(report)
    tampered["registered_gradient_audit"]["gradients"]["residual_coefficient"][
        "value"
    ] = 0.0
    _reseal(tampered)
    with pytest.raises(ValueError, match="nonzero flag mismatch"):
        validate_r6_structural_audit(tampered)


def test_validator_rejects_missing_case_evidence_and_extra_schema_key() -> None:
    report = run_r6_structural_audits(_matcher())
    missing = deepcopy(report)
    del missing["microcases"]["one_birth_0x1"]["gradient_audit"]
    _reseal(missing)
    with pytest.raises(ValueError, match="schema mismatch"):
        validate_r6_structural_audit(missing)

    extra = deepcopy(report)
    extra["microcases"]["one_birth_0x1"]["unexpected"] = True
    _reseal(extra)
    with pytest.raises(ValueError, match="schema mismatch"):
        validate_r6_structural_audit(extra)


def test_validator_rejects_missing_and_extra_microcase_ids() -> None:
    report = run_r6_structural_audits(_matcher())

    missing = deepcopy(report)
    del missing["microcases"]["one_birth_0x1"]
    with pytest.raises(ValueError, match="schema mismatch"):
        validate_r6_structural_audit(missing)

    extra = deepcopy(report)
    extra["microcases"]["unexpected_case"] = deepcopy(
        extra["microcases"]["one_birth_0x1"]
    )
    _reseal(extra)
    with pytest.raises(ValueError, match="schema mismatch"):
        validate_r6_structural_audit(extra)


def test_validator_rejects_required_case_ids_mutation() -> None:
    report = run_r6_structural_audits(_matcher())
    tampered = deepcopy(report)
    tampered["required_case_ids"] = list(reversed(tampered["required_case_ids"]))
    _reseal(tampered)

    with pytest.raises(ValueError, match="required structural case IDs mismatch"):
        validate_r6_structural_audit(tampered)


def test_validator_rejects_ordered_microcase_projection_tamper() -> None:
    report = run_r6_structural_audits(_matcher())
    tampered = deepcopy(report)
    tampered["ordered_microcase_projection_sha256"] = "0" * 64
    _reseal_audit(tampered)

    with pytest.raises(
        ValueError, match="ordered structural microcase projection SHA-256 mismatch"
    ):
        validate_r6_structural_audit(tampered)


def test_r6_structural_audit_rejects_nonfinite_report_and_matcher() -> None:
    report = run_r6_structural_audits(_matcher())
    nonfinite_report = deepcopy(report)
    nonfinite_report["microcases"]["one_persistent_1x1"]["feasibility_residuals"][
        "hard_optimality_gap"
    ] = float("nan")
    with pytest.raises(ValueError, match="non-finite"):
        validate_r6_structural_audit(nonfinite_report)

    matcher = _matcher()
    matcher.residual_coefficient.data.fill_(float("nan"))
    with pytest.raises(ValueError, match="non-finite at step 0"):
        run_r6_structural_audits(matcher)


def test_r6_structural_audit_fails_closed_on_non_r6_parameter_shape() -> None:
    matcher = InvariantPartialOTMatcher(feature_dim=8, identity_views=((2, 8),))
    with pytest.raises(ValueError, match="exactly two identity views"):
        run_r6_structural_audits(matcher)
