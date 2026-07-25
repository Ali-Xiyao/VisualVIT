from copy import deepcopy
import hashlib
import json
import math
import struct
import uuid

import pytest

from visualvit.matching import InvariantPartialOTMatcher
from visualvit.r6_structural_audits import run_r6_structural_audits
from visualvit.r6_validation import (
    ListSchema,
    LiteralSchema,
    ObjectSchema,
    R6ModeContract,
    R6SummaryContract,
    R6ValidationError,
    ScalarSchema,
    ValidationIssue,
    _validate_structural_report,
    canonical_json,
    canonical_sha256,
    is_lowercase_sha256,
    is_utc_z_timestamp,
    is_uuid4,
    json_pointer_join,
    recompute_average,
    recompute_confusion_matrix,
    validate_average,
    validate_confusion_matrix,
    validate_delta,
    validate_r6_metric_evidence,
    validate_r6_summary,
    validate_schema,
)


GATES = (
    "resolution_freeze",
    "structural_input",
    "fixture_identifiability",
    "transport_competence",
    "anti_equivalence",
    "mediator_recovery",
    "fair_baseline",
    "exact64_bridge",
    "independent_reproduction",
)
GATE_FIELDS = {name: f"{name}_gate" for name in GATES}


def _gate_schema() -> ObjectSchema:
    return ObjectSchema(
        {
            "passed": ScalarSchema("boolean"),
            "status": ScalarSchema("string"),
        }
    )


def _trace_schema(length: int) -> ListSchema:
    return ListSchema(
        ObjectSchema(
            {
                "name": ScalarSchema("string"),
                "status": ScalarSchema("string"),
                "passed": ScalarSchema("boolean"),
            }
        ),
        exact_length=length,
    )


def _access_schema(length: int) -> ListSchema:
    return ListSchema(
        ObjectSchema(
            {
                "schema_version": LiteralSchema("r6_access_v1"),
                "gate": ScalarSchema("string"),
                "content_sha256": ScalarSchema("string", sha256=True),
                "cache_hit": ScalarSchema("boolean"),
            }
        ),
        exact_length=length,
    )


def _schema(gate_prefix: tuple[str, ...], access_length: int) -> ObjectSchema:
    properties = {
        "summary_schema_version": LiteralSchema("r6_summary_v1"),
        "run_uuid": ScalarSchema("string", uuid4=True),
        "start_utc": ScalarSchema("string", utc_z=True),
        "authority_sha256": ScalarSchema("string", sha256=True),
        "gate_order": ListSchema(
            ScalarSchema("string"),
            exact_length=len(GATES),
            exact_values=GATES,
        ),
        "status": ScalarSchema("string"),
        "completed_gates": _trace_schema(len(gate_prefix)),
        "stopped_at_gate": ScalarSchema("string")
        if len(gate_prefix) == 1
        else ScalarSchema("null"),
        "not_run_gates": ListSchema(ScalarSchema("string")),
        "data_access_ledger": _access_schema(access_length),
        "formal_test_used": LiteralSchema(False),
        "formal_claim_allowed": LiteralSchema(False),
        "formal_ablation_claim_allowed": LiteralSchema(False),
        "full_method_claim_allowed": LiteralSchema(False),
    }
    properties.update({GATE_FIELDS[name]: _gate_schema() for name in gate_prefix})
    return ObjectSchema(properties)


def _entry(gate: str) -> dict[str, object]:
    return {
        "schema_version": "r6_access_v1",
        "gate": gate,
        "content_sha256": "a" * 64,
        "cache_hit": False,
    }


def _summary(
    gate_prefix: tuple[str, ...],
    *,
    status: str,
    stopped_at: str | None,
    access: list[dict[str, object]],
) -> dict[str, object]:
    summary: dict[str, object] = {
        "summary_schema_version": "r6_summary_v1",
        "run_uuid": str(uuid.UUID("12345678-1234-4abc-8def-1234567890ab")),
        "start_utc": "2026-07-22T12:34:56.123456Z",
        "authority_sha256": "0" * 64,
        "gate_order": list(GATES),
        "status": status,
        "completed_gates": [],
        "stopped_at_gate": stopped_at,
        "not_run_gates": list(GATES[len(gate_prefix) :]),
        "data_access_ledger": access,
        "formal_test_used": False,
        "formal_claim_allowed": False,
        "formal_ablation_claim_allowed": False,
        "full_method_claim_allowed": False,
    }
    for index, name in enumerate(gate_prefix):
        passed = not (stopped_at == name)
        gate = {"status": "PASS" if passed else "FAIL", "passed": passed}
        summary[GATE_FIELDS[name]] = gate
        summary["completed_gates"].append(
            {"name": name, "status": gate["status"], "passed": passed}
        )
    return summary


def _contract() -> R6SummaryContract:
    access = (_entry("structural_input"),)
    mode_specs = {
        "resolution_stop": (
            (GATES[0],),
            "STOP_R6_RESOLUTION_FREEZE",
            tuple(),
            "stopped",
            GATES[0],
        ),
        "dry_run": (
            GATES[:3],
            "DRY_RUN_VALIDATED_R6",
            access,
            "dry_run",
            None,
        ),
        "smoke": (
            GATES[:8],
            "SMOKE_COMPLETED_R6",
            access,
            "success",
            None,
        ),
        "registered": (
            GATES[:8],
            "R6_REGISTERED_PENDING_REPRODUCTION",
            access,
            "success",
            None,
        ),
    }
    modes = {}
    for mode, (
        prefix,
        status,
        expected_access,
        outcome,
        stopped_at,
    ) in mode_specs.items():
        schema = _schema(prefix, len(expected_access))
        modes[mode] = R6ModeContract(
            schema=schema,
            expected_top_level_keys=frozenset(schema.properties),
            gate_prefix=prefix,
            expected_status=status,
            expected_access_prefix=expected_access,
            outcome=outcome,
            stopped_at_gate=stopped_at,
        )
    return R6SummaryContract(gate_order=GATES, gate_fields=GATE_FIELDS, modes=modes)


def _r7_resolution_stop_contract() -> R6SummaryContract:
    base = _contract()
    r6_mode = base.modes["resolution_stop"]
    r7_mode = R6ModeContract(
        **{
            **r6_mode.__dict__,
            "expected_status": "STOP_R7_RESOLUTION_FREEZE",
        }
    )
    return R6SummaryContract(
        gate_order=base.gate_order,
        gate_fields=base.gate_fields,
        modes={**base.modes, "resolution_stop": r7_mode},
    )


def _valid(mode: str) -> dict[str, object]:
    contract = _contract().modes[mode]
    stopped = contract.stopped_at_gate
    return _summary(
        contract.gate_prefix,
        status=contract.expected_status,
        stopped_at=stopped,
        access=list(contract.expected_access_prefix),
    )


@pytest.mark.parametrize("mode", ["resolution_stop", "dry_run", "smoke", "registered"])
def test_summary_validator_accepts_registered_terminal_families(mode: str) -> None:
    result = validate_r6_summary(_valid(mode), mode, _contract())
    assert result["validated"]
    assert result["status"] == _contract().modes[mode].expected_status
    assert is_lowercase_sha256(result["data_access_prefix_sha256"])


def test_stopped_status_uses_external_r7_mode_contract() -> None:
    contract = _r7_resolution_stop_contract()
    summary = _valid("resolution_stop")
    summary["status"] = "STOP_R7_RESOLUTION_FREEZE"

    result = validate_r6_summary(summary, "resolution_stop", contract)

    assert result["validated"]
    assert result["status"] == "STOP_R7_RESOLUTION_FREEZE"


def test_r7_stop_contract_rejects_forged_legacy_r6_status() -> None:
    summary = _valid("resolution_stop")

    with pytest.raises(R6ValidationError, match="/status"):
        validate_r6_summary(summary, "resolution_stop", _r7_resolution_stop_contract())


def test_recursive_schema_rejects_unknown_and_missing_with_rfc6901_paths() -> None:
    schema = ObjectSchema(
        {"a/b~c": ObjectSchema({"required": ScalarSchema("integer")})}
    )
    payload = {"a/b~c": {"extra": 1}}
    with pytest.raises(R6ValidationError) as caught:
        validate_schema(payload, schema)
    records = [issue.as_dict() for issue in caught.value.issues]
    assert {record["pointer"] for record in records} == {
        "/a~1b~0c/required",
        "/a~1b~0c/extra",
    }
    assert json_pointer_join("/a~1b~0c", "x/y~z") == "/a~1b~0c/x~1y~0z"


@pytest.mark.parametrize("bad", [True, "3", 3.0])
def test_integer_schema_rejects_bool_numeric_string_and_float(bad: object) -> None:
    with pytest.raises(R6ValidationError):
        validate_schema(
            {"count": bad}, ObjectSchema({"count": ScalarSchema("integer", minimum=0)})
        )


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_fails_at_any_depth_and_canonicalization(bad: float) -> None:
    payload = {"nested": [{"value": bad}]}
    schema = ObjectSchema(
        {"nested": ListSchema(ObjectSchema({"value": ScalarSchema("number")}))}
    )
    with pytest.raises(R6ValidationError) as caught:
        validate_schema(payload, schema)
    assert caught.value.issues[0].pointer == "/nested/0/value"
    with pytest.raises(R6ValidationError):
        canonical_json(payload)


def test_sha_uuid_timestamp_validators_are_exact() -> None:
    good_uuid = "12345678-1234-4abc-8def-1234567890ab"
    assert is_lowercase_sha256("f" * 64)
    assert not is_lowercase_sha256("F" * 64)
    assert not is_lowercase_sha256("f" * 63)
    assert is_uuid4(good_uuid)
    assert not is_uuid4(good_uuid.upper())
    assert not is_uuid4("12345678-1234-3abc-8def-1234567890ab")
    assert is_utc_z_timestamp("2026-07-22T12:34:56.123456Z")
    assert not is_utc_z_timestamp("2026-07-22T12:34:56Z")
    assert not is_utc_z_timestamp("2026-07-22T12:34:56.123456+00:00")
    assert not is_utc_z_timestamp("2026-02-30T12:34:56.123456Z")


def test_canonical_json_is_stable_utf8_and_type_strict() -> None:
    left = {"z": "中文", "a": [1, False, None]}
    right = {"a": [1, False, None], "z": "中文"}
    assert canonical_json(left) == canonical_json(right)
    assert canonical_sha256(left) == canonical_sha256(right)
    with pytest.raises(R6ValidationError):
        canonical_json({"not_json": {1, 2}})


def test_resolution_stop_recomputes_status_and_forbids_later_gate() -> None:
    forged = _valid("resolution_stop")
    forged["status"] = "STOP_R6_STRUCTURAL_INPUT"
    with pytest.raises(R6ValidationError, match="/status"):
        validate_r6_summary(forged, "resolution_stop", _contract())

    forged = _valid("resolution_stop")
    forged["structural_input_gate"] = {"status": "PASS", "passed": True}
    schema = _contract().modes["resolution_stop"].schema
    properties = dict(schema.properties)
    properties["structural_input_gate"] = _gate_schema()
    altered_mode = R6ModeContract(
        **{
            **_contract().modes["resolution_stop"].__dict__,
            "schema": ObjectSchema(properties),
            "expected_top_level_keys": frozenset(properties),
        }
    )
    base = _contract()
    malicious_contract = R6SummaryContract(
        gate_order=base.gate_order,
        gate_fields=base.gate_fields,
        modes={**base.modes, "resolution_stop": altered_mode},
    )
    with pytest.raises(R6ValidationError, match="later-stage key forbidden"):
        validate_r6_summary(forged, "resolution_stop", malicious_contract)


def test_stop_trace_must_end_at_first_failure() -> None:
    forged = _valid("resolution_stop")
    forged["resolution_freeze_gate"]["passed"] = True
    forged["completed_gates"][0]["passed"] = True
    with pytest.raises(R6ValidationError, match="first failing gate"):
        validate_r6_summary(forged, "resolution_stop", _contract())


def test_gate_trace_is_recomputed_not_trusted() -> None:
    forged = _valid("dry_run")
    forged["completed_gates"][1]["status"] = "FORGED"
    with pytest.raises(R6ValidationError, match="/completed_gates"):
        validate_r6_summary(forged, "dry_run", _contract())


@pytest.mark.parametrize("mode", ["dry_run", "smoke", "registered"])
def test_success_like_modes_reject_failed_gate(mode: str) -> None:
    forged = _valid(mode)
    gate = _contract().modes[mode].gate_prefix[-1]
    forged[GATE_FIELDS[gate]]["passed"] = False
    forged["completed_gates"][-1]["passed"] = False
    with pytest.raises(R6ValidationError, match="every completed gate passes"):
        validate_r6_summary(forged, mode, _contract())


def test_access_prefix_is_exact_in_value_order_and_length() -> None:
    for mutation in ("value", "order", "extra"):
        forged = _valid("dry_run")
        if mutation == "value":
            forged["data_access_ledger"][0]["gate"] = "transport_competence"
        elif mutation == "order":
            forged["data_access_ledger"] = list(reversed(forged["data_access_ledger"]))
            forged["data_access_ledger"].append(_entry("unexpected"))
        else:
            forged["data_access_ledger"].append(_entry("unexpected"))
        with pytest.raises(R6ValidationError):
            validate_r6_summary(forged, "dry_run", _contract())


def test_unknown_top_level_and_formal_claim_truth_fail_closed() -> None:
    forged = _valid("smoke")
    forged["unknown"] = 1
    with pytest.raises(R6ValidationError, match="unknown key forbidden"):
        validate_r6_summary(forged, "smoke", _contract())
    forged = _valid("smoke")
    forged["formal_claim_allowed"] = True
    with pytest.raises(R6ValidationError):
        validate_r6_summary(forged, "smoke", _contract())


def test_wrong_mode_and_not_run_suffix_fail() -> None:
    with pytest.raises(R6ValidationError, match="registered validation mode"):
        validate_r6_summary(_valid("dry_run"), "unknown", _contract())
    forged = _valid("registered")
    forged["not_run_gates"] = []
    with pytest.raises(R6ValidationError, match="/not_run_gates"):
        validate_r6_summary(forged, "registered", _contract())


def test_confusion_matrix_recomputation_and_malicious_counts() -> None:
    labels = ("a", "b", "c")
    actual = ("a", "a", "b", "c")
    predicted = ("a", "b", "b", "a")
    expected = [[1, 1, 0], [0, 1, 0], [1, 0, 0]]
    assert recompute_confusion_matrix(actual, predicted, labels) == expected
    validate_confusion_matrix(
        expected,
        actual=actual,
        predicted=predicted,
        labels=labels,
        pointer="/metrics/confusion",
    )
    forged = deepcopy(expected)
    forged[0][0] += 1
    with pytest.raises(R6ValidationError, match="/metrics/confusion"):
        validate_confusion_matrix(
            forged,
            actual=actual,
            predicted=predicted,
            labels=labels,
            pointer="/metrics/confusion",
        )
    with pytest.raises(R6ValidationError):
        recompute_confusion_matrix(("a",), ("unknown",), labels)


def test_average_and_delta_are_recomputed_and_bool_is_rejected() -> None:
    values = (0.1, 0.2, 0.3)
    expected = recompute_average(values)
    validate_average(expected, values, pointer="/aggregate/mean")
    with pytest.raises(R6ValidationError, match="/aggregate/mean"):
        validate_average(0.3, values, pointer="/aggregate/mean")
    validate_delta(0.25, minuend=0.75, subtrahend=0.5, pointer="/delta")
    with pytest.raises(R6ValidationError, match="/delta"):
        validate_delta(0.2, minuend=0.75, subtrahend=0.5, pointer="/delta")
    with pytest.raises(R6ValidationError):
        recompute_average((True, 1.0))
    with pytest.raises(R6ValidationError):
        validate_delta(False, minuend=1.0, subtrahend=0.5, pointer="/delta")


def _label_metric_evidence() -> dict[str, object]:
    return {
        "five_label_macro_f1": 1.0,
        "persistent_three_label_macro_f1": 1.0,
        "accuracy": 1.0,
        "predictions": [0, 1, 2, 3, 4],
        "targets": [0, 1, 2, 3, 4],
    }


def _binary_metric_evidence(
    actual: list[int], predicted: list[int]
) -> dict[str, object]:
    tp = sum(a == 1 and p == 1 for a, p in zip(actual, predicted, strict=True))
    fp = sum(a == 0 and p == 1 for a, p in zip(actual, predicted, strict=True))
    fn = sum(a == 1 and p == 0 for a, p in zip(actual, predicted, strict=True))
    tn = sum(a == 0 and p == 0 for a, p in zip(actual, predicted, strict=True))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    specificity = tn / (tn + fp) if tn + fp else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "actual": actual,
        "predicted": predicted,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "positive_support": tp + fn,
        "predicted_positive_support": tp + fp,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "balanced_accuracy": 0.5 * (recall + specificity),
        "non_gating_accuracy": (tp + tn) / len(actual),
    }


def _transport_metric_evidence() -> dict[str, object]:
    death = _binary_metric_evidence([1, 0, 1, 0], [1, 1, 0, 0])
    birth = _binary_metric_evidence([0, 1, 0, 1], [0, 1, 0, 1])
    query_evidence = {
        "hard_query_correct": [1, 0],
        "soft_oracle_query_mass_values": [0.8, 0.2],
        "soft_query_nll_values": [-math.log(0.8), -math.log(0.2)],
        "soft_query_brier_values": [0.04, 0.64],
        "soft_query_probability_rows": [[0.8, 0.2], [0.8, 0.2]],
        "oracle_current_indices": [0, 1],
    }
    return {
        "hard_all_endpoint_assignment_accuracy": 0.5,
        "soft_all_endpoint_oracle_mass": 0.7,
        "row_top1_accuracy": 0.5,
        "null_metrics": {
            "death": death,
            "birth": birth,
            "death_exact_case": 0.0,
            "birth_exact_case": 1.0,
            "null_exact_case": 0.0,
            "macro_f1": 0.75,
            "positive_support_both": True,
            "metric_evidence": {
                "case_count": 2,
                "death_exact_count": 0,
                "birth_exact_count": 2,
                "joint_exact_count": 0,
            },
        },
        "query": {
            "hard_query_identity_accuracy": 0.5,
            "hard_query_identity_f1": 0.5,
            "hard_query_identity_chance_reference": 1.0 / 6.0,
            "soft_oracle_query_mass": 0.5,
            "soft_oracle_mass_chance_reference": 1.0 / 6.0,
            "soft_query_nll": (-math.log(0.8) - math.log(0.2)) / 2,
            "soft_query_brier": 0.34,
        },
        "soft_plan_sha256": "a" * 64,
        "hard_plan_sha256": "b" * 64,
        "metric_evidence": {
            "hard_endpoint_correct": [1, 0],
            "row_top1_actual": [0, 1],
            "row_top1_predicted": [0, 2],
            "soft_endpoint_oracle_mass_values": [0.8, 0.6],
            "soft_endpoint_oracle_mass_denominator": 2.0,
            "query": query_evidence,
        },
    }


def _classification_evidence() -> dict[str, list[int]]:
    return {"predictions": [0, 1, 2], "targets": [0, 1, 2]}


def _marginal_control_evidence(*, competence: bool) -> dict[str, object]:
    result: dict[str, object] = {
        "train_macro_f1": 1.0,
        "development_macro_f1": 1.0,
        "raw_evidence": {
            "train": _classification_evidence(),
            "development": _classification_evidence(),
        },
    }
    if competence:
        result.update(
            {
                "cyclic_code_derangement_macro_f1": 1.0,
                "permutation_invariance_max_logit_error": 0.3,
                "raw_evidence": {
                    "train": _classification_evidence(),
                    "development": _classification_evidence(),
                    "deranged": _classification_evidence(),
                    "permutation": {
                        "shape": [2, 3],
                        "logit_differences": [0.0, -0.1, 0.2, -0.3, 0.1, 0.0],
                    },
                },
            }
        )
    return result


def _local_row_metric_evidence() -> dict[str, object]:
    return {
        "row_top1_accuracy": 2.0 / 3.0,
        "row_top1_actual": [0, 1, 2],
        "row_top1_predicted": [0, 0, 2],
        "row_top1_correct_count": 2,
        "row_top1_support_count": 3,
        "duplicate_current_rows": 1,
        "selected_real_rows": 2,
        "duplicate_current_rate": 0.5,
        "row_probability_sha256": "c" * 64,
        "row_top1_sha256": "d" * 64,
        "birth_mask_sha256": "e" * 64,
    }


def _metric_summary() -> dict[str, object]:
    control = _marginal_control_evidence(competence=False)
    control["competence_probe"] = _marginal_control_evidence(competence=True)
    return {
        "transport_results": {
            "17": {
                "evaluations": {"clean": {"development": _transport_metric_evidence()}}
            }
        },
        "common_oracle_readout_results": {
            "17": {"metrics": {"clean": {"development": _label_metric_evidence()}}}
        },
        "marginal_controls": {"17": {"current_only_deepsets": control}},
        "matched_local_results": {
            "17": {
                "evaluations": {
                    "challenge": {"development": _local_row_metric_evidence()}
                }
            }
        },
    }


def test_metric_evidence_validator_accepts_and_certifies_all_core_families() -> None:
    certificate = validate_r6_metric_evidence(_metric_summary())
    assert certificate["schema_version"] == "visualvit.r6-validation.v4"
    assert certificate["validated"] is True
    assert certificate["checked_block_count"] == 5
    assert is_lowercase_sha256(certificate["metric_evidence_sha256"])
    assert certificate["checked_pointers"] == sorted(certificate["checked_pointers"])


@pytest.mark.parametrize(
    ("mutation", "pointer"),
    [
        (
            "missing",
            "/common_oracle_readout_results/17/metrics/clean/development/targets",
        ),
        ("extra", "/common_oracle_readout_results/17/metrics/clean/development/forged"),
        (
            "wrong_type",
            "/common_oracle_readout_results/17/metrics/clean/development/predictions/0",
        ),
        (
            "arithmetic",
            "/common_oracle_readout_results/17/metrics/clean/development/accuracy",
        ),
    ],
)
def test_label_metric_evidence_is_closed_typed_and_recomputed(
    mutation: str, pointer: str
) -> None:
    summary = _metric_summary()
    metrics = summary["common_oracle_readout_results"]["17"]["metrics"]["clean"][
        "development"
    ]
    if mutation == "missing":
        metrics.pop("targets")
    elif mutation == "extra":
        metrics["forged"] = 1
    elif mutation == "wrong_type":
        metrics["predictions"][0] = True
    else:
        metrics["accuracy"] = 0.8
    with pytest.raises(R6ValidationError) as caught:
        validate_r6_metric_evidence(summary)
    assert pointer in {issue.pointer for issue in caught.value.issues}


def test_binary_and_null_evidence_reject_forged_counts_and_case_arithmetic() -> None:
    summary = _metric_summary()
    null_metrics = summary["transport_results"]["17"]["evaluations"]["clean"][
        "development"
    ]["null_metrics"]
    null_metrics["death"]["tp"] = 2
    null_metrics["metric_evidence"]["birth_exact_count"] = 1
    with pytest.raises(R6ValidationError) as caught:
        validate_r6_metric_evidence(summary)
    pointers = {issue.pointer for issue in caught.value.issues}
    assert (
        "/transport_results/17/evaluations/clean/development/null_metrics/death/tp"
        in pointers
    )
    assert (
        "/transport_results/17/evaluations/clean/development/null_metrics/metric_evidence/birth_exact_count"
        in pointers
    )


def test_transport_evidence_rejects_vector_and_soft_mass_forgery() -> None:
    summary = _metric_summary()
    metrics = summary["transport_results"]["17"]["evaluations"]["clean"]["development"]
    metrics["metric_evidence"]["hard_endpoint_correct"] = [1, 1]
    metrics["soft_all_endpoint_oracle_mass"] = 0.9
    metrics["query"]["soft_query_nll"] = 0.1
    with pytest.raises(R6ValidationError) as caught:
        validate_r6_metric_evidence(summary)
    rules = " ".join(issue.rule for issue in caught.value.issues)
    assert "row comparisons" in rules
    assert "recomputed value 0.7" in rules
    assert "recomputed value 0.9" in rules


def test_transport_evidence_rejects_missing_and_extra_evidence_keys() -> None:
    summary = _metric_summary()
    evidence = summary["transport_results"]["17"]["evaluations"]["clean"][
        "development"
    ]["metric_evidence"]
    evidence.pop("row_top1_actual")
    evidence["unregistered"] = []
    with pytest.raises(R6ValidationError) as caught:
        validate_r6_metric_evidence(summary)
    pointers = {issue.pointer for issue in caught.value.issues}
    base = "/transport_results/17/evaluations/clean/development/metric_evidence"
    assert f"{base}/row_top1_actual" in pointers
    assert f"{base}/unregistered" in pointers


def test_marginal_raw_evidence_recomputes_f1_and_permutation_max_abs() -> None:
    summary = _metric_summary()
    control = summary["marginal_controls"]["17"]["current_only_deepsets"]
    control["development_macro_f1"] = 0.0
    probe = control["competence_probe"]
    probe["permutation_invariance_max_logit_error"] = 0.2
    with pytest.raises(R6ValidationError) as caught:
        validate_r6_metric_evidence(summary)
    pointers = {issue.pointer for issue in caught.value.issues}
    base = "/marginal_controls/17/current_only_deepsets"
    assert f"{base}/development_macro_f1" in pointers
    assert f"{base}/competence_probe/permutation_invariance_max_logit_error" in pointers


def test_deepsets_control_requires_competence_raw_evidence() -> None:
    summary = _metric_summary()
    control = summary["marginal_controls"]["17"]["current_only_deepsets"]
    control.pop("competence_probe")
    with pytest.raises(R6ValidationError) as caught:
        validate_r6_metric_evidence(summary)
    assert any(
        issue.pointer.endswith("/competence_probe") for issue in caught.value.issues
    )


def test_local_row_evidence_recomputes_support_accuracy_and_duplicate_rate() -> None:
    summary = _metric_summary()
    metrics = summary["matched_local_results"]["17"]["evaluations"]["challenge"][
        "development"
    ]
    metrics["row_top1_correct_count"] = 3
    metrics["duplicate_current_rate"] = 0.25
    with pytest.raises(R6ValidationError) as caught:
        validate_r6_metric_evidence(summary)
    pointers = {issue.pointer for issue in caught.value.issues}
    base = "/matched_local_results/17/evaluations/challenge/development"
    assert f"{base}/row_top1_correct_count" in pointers
    assert f"{base}/duplicate_current_rate" in pointers


def test_metric_evidence_validator_allows_pre_metric_gate_summary() -> None:
    certificate = validate_r6_metric_evidence({"status": "DRY_RUN_VALIDATED_R6"})
    assert certificate["checked_block_count"] == 0


def _transport_gate_summary() -> dict[str, object]:
    summary = _metric_summary()
    result = summary["transport_results"]["17"]
    result.update(
        {
            "initialization": {
                **_initialization_evidence(),
            },
            "initial_state_sha256": _initialization_evidence()[
                "runtime_initial_state_sha256"
            ],
            "final_state_sha256": "2" * 64,
            "frozen_state_sha256": "2" * 64,
            "all_gradients_finite": True,
            "optimizer_only_matcher": True,
            "state_unchanged_by_freeze": True,
            "matcher_changed": True,
            "finite_gradient_steps": 5,
            "registered_gradient_steps": 5,
            "nonzero_gradient_steps": 5,
            "optimizer_parameter_names": [
                "current_null_utility",
                "prior_null_utility",
                "residual_coefficient",
                "view_weight_logits",
            ],
            "trainable_parameter_names": [
                "current_null_utility",
                "prior_null_utility",
                "residual_coefficient",
                "view_weight_logits",
            ],
        }
    )
    metrics = result["evaluations"]["clean"]["development"]
    summary["transport_competence_gate"] = {
        "status": "FAIL_TRANSPORT_COMPETENCE",
        "passed": False,
        "hard_by_seed": {"17": 0.5},
        "soft_by_seed": {"17": 0.5},
        "null_metrics_by_seed": {"17": metrics["null_metrics"]},
        "checks": {
            "seed_specific_initial_hashes_distinct": True,
            "initial_hashes_rederive_exactly": True,
            "every_seed_hard_at_least_0_90": False,
            "aggregate_hard_at_least_0_95": False,
            "every_seed_soft_at_least_0_30": True,
            "aggregate_soft_at_least_0_35": True,
            "every_seed_death_precision_exact": False,
            "every_seed_death_recall_exact": False,
            "every_seed_death_f1_exact": False,
            "every_seed_birth_precision_exact": True,
            "every_seed_birth_recall_exact": True,
            "every_seed_birth_f1_exact": True,
            "every_seed_null_exact_case": False,
            "every_seed_has_death_and_birth_support": True,
            "all_transport_gradients_finite": True,
            "optimizer_only_matcher": True,
            "matcher_checkpoint_frozen": True,
        },
    }
    return summary


def _initialization_evidence() -> dict[str, object]:
    values = [0.01, -0.015, 0.012, -0.01, 0.008]
    encoded = struct.pack("<5f", *values)
    names = [
        "residual_coefficient",
        "view_weight_logits.0",
        "view_weight_logits.1",
        "prior_null_utility_raw",
        "current_null_utility_raw",
    ]
    chunks = [
        name.encode() + b"\0torch.float32\0" + encoded[index * 4 : index * 4 + 4]
        for index, name in enumerate(names)
    ]
    parameter_hashes = {
        name: hashlib.sha256(chunk).hexdigest()
        for name, chunk in zip(names, chunks, strict=True)
    }
    raw_hash = hashlib.sha256(b"".join(chunks)).hexdigest()
    runtime_chunks = [
        b"current_null_utility" + b"torch.float32" + b"()" + encoded[16:20],
        b"prior_null_utility" + b"torch.float32" + b"()" + encoded[12:16],
        b"residual_coefficient" + b"torch.float32" + b"()" + encoded[0:4],
        b"view_weight_logits" + b"torch.float32" + b"(2,)" + encoded[4:12],
    ]
    runtime_hash = hashlib.sha256(b"".join(runtime_chunks)).hexdigest()
    unpacked = struct.unpack("<5f", encoded)
    max_view = max(unpacked[1], unpacked[2])
    exp0 = math.exp(unpacked[1] - max_view)
    exp1 = math.exp(unpacked[2] - max_view)
    effective_hash = "f" * 64
    expected_seed = {
        "per_parameter_tensor_sha256": parameter_hashes,
        "raw_initial_state_sha256": raw_hash,
        "effective_initial_state_sha256": effective_hash,
    }
    checks = {
        "literal_vector_hash_exact": True,
        "protocol_literal_values_exact": True,
        "parameter_order_exact": True,
        "per_parameter_hashes_exact": True,
        "raw_state_hash_exact": True,
        "effective_state_hash_exact": True,
        "runtime_state_metadata_exact": True,
        "runtime_state_hash_exact": True,
        "absolute_literal_bound_passed": True,
    }
    return {
        "schema_version": "r24_initialization_evidence_v1",
        "seed": 17,
        "distribution": "normal",
        "std": 0.01,
        "generator": "torch.Generator(device=cpu).manual_seed(seed)",
        "runtime_rule": "load_frozen_literals_do_not_redraw",
        "literal_vector_sha256": hashlib.sha256(encoded).hexdigest(),
        "observed_literal_vector_sha256": hashlib.sha256(encoded).hexdigest(),
        "literal_values": list(unpacked),
        "literal_float32_little_endian_hex": encoded.hex(),
        "parameter_order": names,
        "runtime_parameter_name_mapping": {
            "residual_coefficient": "residual_coefficient",
            "view_weight_logits.0": "view_weight_logits[0]",
            "view_weight_logits.1": "view_weight_logits[1]",
            "prior_null_utility_raw": "prior_null_utility",
            "current_null_utility_raw": "current_null_utility",
        },
        "raw_values": dict(zip(names, unpacked, strict=True)),
        "effective_values": {
            "residual_coefficient_effective": 0.02 * math.tanh(unpacked[0]),
            "view_weights_effective.0": exp0 / (exp0 + exp1),
            "view_weights_effective.1": exp1 / (exp0 + exp1),
            "prior_null_utility_effective": 0.10 * math.tanh(unpacked[3]),
            "current_null_utility_effective": 0.10 * math.tanh(unpacked[4]),
        },
        "per_parameter_tensor_sha256": parameter_hashes,
        "raw_initial_state_sha256": raw_hash,
        "effective_initial_state_sha256": effective_hash,
        "runtime_state_dict_parameter_order": [
            "current_null_utility",
            "prior_null_utility",
            "residual_coefficient",
            "view_weight_logits",
        ],
        "runtime_state_dict_shapes": {
            "current_null_utility": [],
            "prior_null_utility": [],
            "residual_coefficient": [],
            "view_weight_logits": [2],
        },
        "runtime_state_dict_dtype": "torch.float32",
        "runtime_initial_state_sha256": runtime_hash,
        "expected_seed_evidence": expected_seed,
        "checks": checks,
        "passed": True,
        "state_sha256": raw_hash,
    }


def _exact64_audit(phase_prefix: str = "oracle_readout") -> dict[str, object]:
    final_phases = [
        f"{phase_prefix}_final_{stratum}_{split}"
        for stratum in ("clean", "challenge")
        for split in ("train", "development")
    ]
    expected_calls = {
        f"{phase_prefix}_training_{stratum}": 1 for stratum in ("clean", "challenge")
    }
    expected_calls.update({phase: 1 for phase in final_phases})
    checks = {
        "adapter_calls_exact": True,
        "total_adapter_calls_exact": True,
        "all_placeholders_exact64": True,
        "no_pixels": True,
        "frozen_adapter_reported": True,
        "adapter_state_unchanged": True,
        "projector_frozen_after_fit": True,
        "matcher_state_unchanged": True,
    }
    return {
        "passed": True,
        "checks": checks,
        "observed_adapter_score_calls": expected_calls,
        "expected_adapter_score_calls": expected_calls,
        "observed_total_adapter_score_calls": sum(expected_calls.values()),
        "expected_total_adapter_score_calls": sum(expected_calls.values()),
        "placeholder_counts": {phase: [64, 64] for phase in final_phases},
        "phase_evidence": {
            phase: {"pixel_inputs_used": False, "model_frozen": True}
            for phase in final_phases
        },
    }


def _readout_result() -> dict[str, object]:
    return {
        "execution_kind": "oracle_readout",
        "result_schema_version": "r6.result.v1",
        "metrics": {
            stratum: {
                split: _label_metric_evidence() for split in ("train", "development")
            }
            for stratum in ("clean", "challenge")
        },
        "exact64_execution_audit": _exact64_audit(),
        "initial_state_sha256": "1" * 64,
        "final_train_state_sha256": "2" * 64,
        "frozen_state_sha256": "2" * 64,
        "adapter_before_sha256": "3" * 64,
        "adapter_after_sha256": "3" * 64,
        "matcher_before_sha256": None,
        "matcher_after_sha256": None,
        "adapter_unchanged": True,
        "projector_state_unchanged_by_freeze": True,
        "matcher_unchanged": True,
        "matcher_gradients_zero": True,
        "matcher_gradient_non_none_count": 0,
        "matcher_gradient_nonzero_count": 0,
        "finite_gradient_steps": 1,
        "registered_gradient_steps": 1,
        "all_gradients_finite": True,
        "optimizer_parameter_names": ["readout.weight"],
        "trainable_parameter_names": ["readout.weight"],
        "optimizer_only_projector": True,
    }


def _baseline_leaf(phase: str) -> dict[str, object]:
    checks = {
        "single_exact64_call": True,
        "placeholders_exact64": True,
        "no_pixels": True,
        "adapter_frozen": True,
        "projector_unchanged": True,
        "adapter_unchanged": True,
    }
    return {
        "passed": True,
        "checks": checks,
        "metrics": _label_metric_evidence(),
        "observed_adapter_score_calls": {phase: 1},
        "expected_adapter_score_calls": {phase: 1},
        "placeholder_counts": {phase: [64, 64]},
        "phase_evidence": {phase: {"pixel_inputs_used": False, "model_frozen": True}},
        "projector_before_sha256": "7" * 64,
        "projector_after_sha256": "7" * 64,
        "adapter_before_sha256": "8" * 64,
        "adapter_after_sha256": "8" * 64,
        "projector_sha256": "7" * 64,
        "adapter_sha256": "8" * 64,
        "common_oracle_readout_sha256": "9" * 64,
    }


def _comparison(*, exact: bool) -> dict[str, object]:
    return {
        "fields_exact": True,
        "all_exact": exact,
        "all_close": exact,
        "exact_by_field": {"value": exact},
        "close_by_field": {"value": exact},
        "max_abs_error_by_field": {"value": 0.0 if exact else 1.0},
        "value_sha256_by_field": {"value": "a" * 64},
    }


def _counterfactual_report() -> dict[str, object]:
    stages = (
        "matching_regions",
        "token_regions",
        "utilities",
        "soft_plan",
        "plan",
        "relation_candidates",
        "allocation",
        "tokens",
        "projected_tokens",
        "adapter_scores",
        "predictions",
    )
    hidden_comparisons = {stage: _comparison(exact=True) for stage in stages}
    substitution_comparisons = {
        stage: _comparison(
            exact=stage
            in {"matching_regions", "token_regions", "utilities", "soft_plan", "plan"}
        )
        for stage in stages
    }
    substitution_checks = {
        "counterfactual_nonvacuous": True,
        "matching_and_transport_exact": True,
        "full_chain_covered": True,
        "downstream_change_observed": True,
    }
    b4_checks = {
        "b4a_plan_nonidentity": True,
        "shared_input_utility_chain_exact": True,
        "projector_state_bitwise_exact": True,
        "adapter_state_bitwise_exact": True,
        "recursive_diff_nonempty": True,
        "all_non_allowlisted_paths_exact": True,
        "scores_and_predictions_covered": True,
    }
    checks = {
        "hidden_relabel_contract": True,
        "hidden_id_full_chain_invariance": True,
        "endpoint_permutation_full_chain_equivariance": True,
        "query_value_substitution_before_transport": True,
        "forbidden_state_channel_substitution": True,
        "b4a_deranged_vs_b4b_oracle": True,
        "transformed_fixtures_storage_disjoint": True,
        "source_tensors_immutable": True,
    }
    report = {
        "schema_version": "visualvit.r6_counterfactual_audits.v1",
        "status": "PASS_R6_COUNTERFACTUAL_AUDITS",
        "passed": True,
        "checks": checks,
        "forward_boundary": {
            "hidden_oracle_passed_to_matcher": False,
            "hidden_oracle_passed_to_tokenizer": False,
            "hidden_oracle_passed_to_projector": False,
            "hidden_oracle_passed_to_adapter": False,
            "batch_aware_hooks": ["matching_regions", "token_regions"],
        },
        "hidden_id_relabel": {
            "contract": {
                "passed": True,
                "checks": {
                    "counterfactual_nonvacuous": True,
                    "gold_equality_relation_exact": True,
                    "oracle_plan_exact": True,
                    "original_plan_matches_gold_equality": True,
                    "relabeled_plan_matches_gold_equality": True,
                },
                "original_equality_sha256": "1" * 64,
                "relabeled_equality_sha256": "1" * 64,
                "original_ids_sha256": "2" * 64,
                "relabeled_ids_sha256": "3" * 64,
            },
            "full_chain": {
                "passed": True,
                "equality_policy": "exact",
                "checks": {stage: True for stage in stages},
                "comparisons": hidden_comparisons,
            },
        },
        "endpoint_permutation": {
            "passed": True,
            "equality_policy": "close",
            "checks": {
                **{stage: True for stage in stages},
                "prior_permutation_nonidentity": True,
                "current_permutation_nonidentity": True,
            },
            "comparisons": hidden_comparisons,
            "prior_permutation_sha256": "4" * 64,
            "current_permutation_sha256": "5" * 64,
            "prior_permutation": [1, 0],
            "current_permutation": [1, 0],
        },
        "query_value_substitution": {
            "passed": True,
            "checks": substitution_checks,
            "changed_input_paths": ["query"],
            "comparisons": substitution_comparisons,
        },
        "forbidden_state_channel_substitution": {
            "passed": True,
            "checks": substitution_checks,
            "changed_input_paths": ["state"],
            "comparisons": substitution_comparisons,
        },
        "b4a_deranged_vs_b4b_oracle": {
            "passed": True,
            "checks": b4_checks,
            "allowlist": [],
            "diff_entries": [],
            "unexpected_paths": [],
            "observed_allowlist_categories": [],
            "shared_comparisons": {},
            "b4a_trace": {},
            "b4b_trace": {},
            "b4a_assignment_sha256": "b" * 64,
            "b4b_assignment_sha256": "c" * 64,
            "projector_state_sha256": {
                "before": "d" * 64,
                "between": "d" * 64,
                "after": "d" * 64,
            },
            "adapter_state_sha256": {
                "before": "e" * 64,
                "between": "e" * 64,
                "after": "e" * 64,
            },
        },
        "transformed_storage_audit": {
            name: {
                "passed": True,
                "checks": {
                    "same_tensor_path_set": True,
                    "no_source_storage_alias": True,
                },
                "overlapping_paths": [],
                "source_tensor_count": 1,
                "transformed_tensor_count": 1,
            }
            for name in (
                "hidden_id_relabel",
                "endpoint_permutation",
                "query_value_substitution",
                "forbidden_state_channel_substitution",
            )
        },
        "source_tensor_audit": {
            "passed": True,
            "checks": {
                "value_dtype_shape_stride_pointer_exact": True,
                "alias_groups_exact": True,
                "snapshot_hash_exact": True,
            },
            "before": {"alias_groups": [], "snapshot_sha256": "6" * 64},
            "after": {"alias_groups": [], "snapshot_sha256": "6" * 64},
        },
        "reference_trace": {
            stage: {
                "value_sha256_by_field": {"value": "7" * 64},
                "group_sha256": canonical_sha256({"value": "7" * 64}),
            }
            for stage in stages
        },
    }
    report["report_sha256"] = canonical_sha256(report)
    return report


def _bridge_summary() -> dict[str, object]:
    methods = ["main", "local_independent", "hungarian", "sinkhorn"]
    return {
        "formal_test_used": False,
        "fair_baseline_gate": {
            "assignment_metrics": {
                stratum: {
                    method: _transport_metric_evidence()
                    for method in ("hungarian", "sinkhorn")
                }
                for stratum in ("clean", "challenge")
            },
            "exact64_method_order": methods,
        },
        "common_oracle_readout_results": {"17": _readout_result()},
        "mediator_results": {"17": _readout_result()},
        "baseline_results": {
            "17": {
                "clean": {
                    method: _baseline_leaf(f"clean_{method}") for method in methods
                }
            }
        },
        "exact64_bridge_gate": {
            "status": "PASS",
            "passed": True,
            "checks": {
                "oracle_readout_exact64": True,
                "mediator_exact64": True,
                "baseline_exact64": True,
                "baseline_method_order_exact": True,
                "common_oracle_readout_shared": True,
                "no_formal_test": True,
                "r6_counterfactual_repeated_at_exact64": True,
                "r6_counterfactual_hash_exact": True,
            },
            "r6_full_chain_counterfactual": _counterfactual_report(),
        },
    }


def test_gate3_rejects_forged_seed_map_and_threshold_check() -> None:
    summary = _transport_gate_summary()
    summary["transport_competence_gate"]["hard_by_seed"]["17"] = 1.0
    summary["transport_competence_gate"]["checks"]["every_seed_hard_at_least_0_90"] = (
        True
    )
    with pytest.raises(R6ValidationError) as caught:
        validate_r6_metric_evidence(summary)
    pointers = {issue.pointer for issue in caught.value.issues}
    assert "/transport_competence_gate/hard_by_seed" in pointers
    assert "/transport_competence_gate/checks/every_seed_hard_at_least_0_90" in pointers


def test_gate3_execution_evidence_is_fully_recomputed() -> None:
    validate_r6_metric_evidence(_transport_gate_summary())
    summary = _transport_gate_summary()
    result = summary["transport_results"]["17"]
    result["state_unchanged_by_freeze"] = False
    result["finite_gradient_steps"] = 4
    result["initialization"]["literal_float32_little_endian_hex"] = "00" * 20
    summary["transport_competence_gate"]["checks"]["unexpected"] = True
    with pytest.raises(R6ValidationError) as caught:
        validate_r6_metric_evidence(summary)
    pointers = {issue.pointer for issue in caught.value.issues}
    assert "/transport_results/17/state_unchanged_by_freeze" in pointers
    assert "/transport_results/17/all_gradients_finite" in pointers
    assert (
        "/transport_results/17/initialization/literal_float32_little_endian_hex"
        in pointers
    )
    assert "/transport_competence_gate/checks/unexpected" in pointers


def test_gate3_runtime_hash_is_reconstructed_without_cross_domain_comparison() -> None:
    summary = _transport_gate_summary()
    initialization = summary["transport_results"]["17"]["initialization"]
    assert (
        initialization["raw_initial_state_sha256"]
        != initialization["runtime_initial_state_sha256"]
    )
    validate_r6_metric_evidence(summary)

    summary["transport_results"]["17"]["initial_state_sha256"] = initialization[
        "raw_initial_state_sha256"
    ]
    with pytest.raises(R6ValidationError) as caught:
        validate_r6_metric_evidence(summary)
    pointers = {issue.pointer for issue in caught.value.issues}
    assert "/transport_results/17/initial_state_sha256" in pointers
    assert (
        "/transport_competence_gate/checks/initial_hashes_rederive_exactly" in pointers
    )


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("runtime_state_dict_shapes", {"view_weight_logits": [1, 2]}),
        ("runtime_state_dict_parameter_order", ["view_weight_logits"]),
        ("runtime_state_dict_dtype", "torch.float64"),
        ("runtime_initial_state_sha256", "0" * 64),
    ],
)
def test_initialization_runtime_state_contract_rejects_tampering(
    field: str, replacement: object
) -> None:
    summary = _transport_gate_summary()
    summary["transport_results"]["17"]["initialization"][field] = replacement
    with pytest.raises(R6ValidationError) as caught:
        validate_r6_metric_evidence(summary)
    assert any(field in issue.pointer for issue in caught.value.issues)


def test_bridge_cannot_pass_when_one_exact64_leaf_is_false() -> None:
    summary = _bridge_summary()
    summary["baseline_results"]["17"]["clean"]["main"]["passed"] = False
    with pytest.raises(R6ValidationError) as caught:
        validate_r6_metric_evidence(summary)
    pointers = {issue.pointer for issue in caught.value.issues}
    assert "/baseline_results/17/clean/main/passed" in pointers
    assert "/exact64_bridge_gate/checks/baseline_exact64" in pointers
    assert "/exact64_bridge_gate/passed" in pointers


def test_bridge_accepts_production_sorted_json_roundtrip() -> None:
    summary = _bridge_summary()
    roundtripped = json.loads(
        json.dumps(
            summary,
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    )
    certificate = validate_r6_metric_evidence(roundtripped)
    assert certificate["validated"] is True


def test_bridge_rejects_reordered_explicit_method_order() -> None:
    summary = _bridge_summary()
    summary["fair_baseline_gate"]["exact64_method_order"] = [
        "hungarian",
        "local_independent",
        "main",
        "sinkhorn",
    ]
    with pytest.raises(R6ValidationError) as caught:
        validate_r6_metric_evidence(summary)
    pointers = {issue.pointer for issue in caught.value.issues}
    assert "/fair_baseline_gate/exact64_method_order" in pointers
    assert "/exact64_bridge_gate/checks/baseline_method_order_exact" in pointers


@pytest.mark.parametrize("mutation", ["missing", "extra"])
def test_bridge_rejects_nonexact_baseline_method_key_set(mutation: str) -> None:
    summary = _bridge_summary()
    methods = summary["baseline_results"]["17"]["clean"]
    if mutation == "missing":
        del methods["main"]
        expected_pointer = "/baseline_results/17/clean/main"
    else:
        methods["extra"] = _baseline_leaf("clean_extra")
        expected_pointer = "/baseline_results/17/clean/extra"
    with pytest.raises(R6ValidationError) as caught:
        validate_r6_metric_evidence(summary)
    pointers = {issue.pointer for issue in caught.value.issues}
    assert expected_pointer in pointers
    assert "/exact64_bridge_gate/checks/baseline_method_order_exact" in pointers


def test_baseline_leaf_recomputes_raw_exact64_and_state_hashes() -> None:
    summary = _bridge_summary()
    validate_r6_metric_evidence(summary)
    leaf = summary["baseline_results"]["17"]["clean"]["main"]
    phase = next(iter(leaf["placeholder_counts"]))
    leaf["placeholder_counts"][phase][0] = 63
    leaf["projector_after_sha256"] = "6" * 64
    with pytest.raises(R6ValidationError) as caught:
        validate_r6_metric_evidence(summary)
    pointers = {issue.pointer for issue in caught.value.issues}
    base = "/baseline_results/17/clean/main/checks"
    assert f"{base}/placeholders_exact64" in pointers
    assert f"{base}/projector_unchanged" in pointers


def test_oracle_exact64_rejects_phase_map_and_gradient_state_forgery() -> None:
    summary = _bridge_summary()
    result = summary["common_oracle_readout_results"]["17"]
    audit = result["exact64_execution_audit"]
    audit["placeholder_counts"]["unregistered"] = [64]
    result["matcher_gradient_non_none_count"] = 1
    result["matcher_unchanged"] = False
    with pytest.raises(R6ValidationError) as caught:
        validate_r6_metric_evidence(summary)
    pointers = {issue.pointer for issue in caught.value.issues}
    base = "/common_oracle_readout_results/17"
    assert f"{base}/exact64_execution_audit/placeholder_counts" in pointers
    assert f"{base}/matcher_gradients_zero" in pointers
    assert f"{base}/matcher_unchanged" in pointers


def test_gate7_requires_nonempty_registered_counterfactual_report() -> None:
    summary = _bridge_summary()
    summary["exact64_bridge_gate"].pop("r6_full_chain_counterfactual")
    with pytest.raises(R6ValidationError) as caught:
        validate_r6_metric_evidence(summary)
    assert any(
        issue.pointer == "/exact64_bridge_gate/r6_full_chain_counterfactual"
        for issue in caught.value.issues
    )


def test_counterfactual_self_hash_cannot_certify_content_free_payload() -> None:
    summary = _bridge_summary()
    report = summary["exact64_bridge_gate"]["r6_full_chain_counterfactual"]
    report["reference_trace"] = {}
    report["report_sha256"] = canonical_sha256(
        {key: value for key, value in report.items() if key != "report_sha256"}
    )
    with pytest.raises(R6ValidationError) as caught:
        validate_r6_metric_evidence(summary)
    assert any(
        issue.pointer
        == "/exact64_bridge_gate/r6_full_chain_counterfactual/reference_trace"
        for issue in caught.value.issues
    )


def test_structural_self_hash_cannot_certify_content_free_report() -> None:
    empty_report = {
        "schema_version": "visualvit.r6-structural-audits.v3",
        "passed": True,
        "required_case_ids": [],
        "required_per_case_evidence": [],
        "microcases": {},
        "ordered_microcase_projection_sha256": canonical_sha256([]),
        "registered_gradient_audit": {},
    }
    empty_report["audit_sha256"] = canonical_sha256(empty_report)
    summary = {
        "structural_input_gate": {
            "r6_gate1_evidence": {
                "passed": True,
                "checks": {},
                "structural_microcases": empty_report,
                "full_chain_counterfactual": _counterfactual_report(),
                "initialization": {},
            }
        }
    }
    with pytest.raises(R6ValidationError) as caught:
        validate_r6_metric_evidence(summary)
    pointers = {issue.pointer for issue in caught.value.issues}
    assert (
        "/structural_input_gate/r6_gate1_evidence/structural_microcases/required_case_ids"
        in pointers
    )
    assert (
        "/structural_input_gate/r6_gate1_evidence/structural_microcases/microcases/one_persistent_1x1"
        in pointers
    )


@pytest.fixture(scope="module")
def structural_report() -> dict[str, object]:
    matcher = InvariantPartialOTMatcher(
        feature_dim=18,
        identity_views=((2, 8), (8, 14)),
        temperature=0.05,
        sinkhorn_iterations=256,
    )
    return run_r6_structural_audits(matcher)


def _structural_validation(
    report: dict[str, object],
) -> tuple[bool, list[ValidationIssue]]:
    issues: list[ValidationIssue] = []
    passed = _validate_structural_report(report, "/report", issues)
    return passed, issues


def _reseal_structural_report(report: dict[str, object]) -> None:
    report["audit_sha256"] = canonical_sha256(
        {key: value for key, value in report.items() if key != "audit_sha256"}
    )


def test_independent_structural_validator_accepts_sorted_json_round_trip(
    structural_report: dict[str, object],
) -> None:
    loaded = json.loads(json.dumps(structural_report, sort_keys=True))

    passed, issues = _structural_validation(loaded)

    assert passed
    assert issues == []


@pytest.mark.parametrize("mutation", ["missing", "extra"])
def test_independent_structural_validator_rejects_microcase_key_mutation(
    structural_report: dict[str, object], mutation: str
) -> None:
    tampered = deepcopy(structural_report)
    if mutation == "missing":
        del tampered["microcases"]["one_birth_0x1"]
    else:
        tampered["microcases"]["unexpected_case"] = deepcopy(
            tampered["microcases"]["one_birth_0x1"]
        )
    _reseal_structural_report(tampered)

    passed, issues = _structural_validation(tampered)

    assert not passed
    assert any(issue.pointer.startswith("/report/microcases/") for issue in issues)


def test_independent_structural_validator_rejects_required_case_ids_mutation(
    structural_report: dict[str, object],
) -> None:
    tampered = deepcopy(structural_report)
    tampered["required_case_ids"] = list(reversed(tampered["required_case_ids"]))
    _reseal_structural_report(tampered)

    passed, issues = _structural_validation(tampered)

    assert not passed
    assert "/report/required_case_ids" in {issue.pointer for issue in issues}


def test_independent_structural_validator_rejects_ordered_projection_tamper(
    structural_report: dict[str, object],
) -> None:
    tampered = deepcopy(structural_report)
    tampered["ordered_microcase_projection_sha256"] = "0" * 64
    _reseal_structural_report(tampered)

    passed, issues = _structural_validation(tampered)

    assert not passed
    assert "/report/ordered_microcase_projection_sha256" in {
        issue.pointer for issue in issues
    }


def test_matcher_gradient_zero_flag_rejects_nonzero_counts() -> None:
    summary = _bridge_summary()
    summary["mediator_results"]["17"]["matcher_gradient_non_none_count"] = 1
    with pytest.raises(R6ValidationError) as caught:
        validate_r6_metric_evidence(summary)
    assert any(
        issue.pointer == "/mediator_results/17/matcher_gradients_zero"
        for issue in caught.value.issues
    )
