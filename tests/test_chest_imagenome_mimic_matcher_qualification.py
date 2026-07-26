from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import torch
from PIL import Image

from scripts import (
    run_chest_imagenome_mimic_matcher_qualification as runner,
)
from scripts import (
    verify_chest_imagenome_mimic_matcher_reproduction as verifier,
)
from visualvit.real_qualification import (
    persistent_label_coverage,
    three_label_from_comparison,
)


def _args(
    *,
    r24_protocol: Path,
    r24_certificate: Path,
    r24_launcher_result: Path,
    r24_real_v3_protocol: Path,
    r24_real_v3_certificate: Path,
) -> Any:
    return type(
        "Args",
        (),
        {
            "r24_protocol": r24_protocol,
            "r24_certificate": r24_certificate,
            "r24_launcher_result": r24_launcher_result,
            "r24_real_v3_protocol": r24_real_v3_protocol,
            "r24_real_v3_certificate": r24_real_v3_certificate,
        },
    )()


def _write_synthetic_green(
    *,
    protocol: Path,
    certificate: Path,
    launcher_result: Path,
    mutation: str | None = None,
) -> dict[str, Any]:
    protocol.write_text("frozen-r24-synthetic", encoding="utf-8")
    gate = {
        "passed": True,
        "checks": {f"check_{index}": True for index in range(11)},
        "mismatch_count": 0,
        "mismatch_paths": [],
        "primary_canonical_sha256": "a" * 64,
        "replica_canonical_sha256": "a" * 64,
        "comparison_excludes_only": runner.R24_EXPECTED_COMPARISON_EXCLUSIONS,
    }
    if mutation == "mismatch":
        gate["mismatch_count"] = 1
        gate["mismatch_paths"] = ["/forged"]
    elif mutation == "failed_check":
        gate["checks"]["check_0"] = False
    certificate.write_text(
        json.dumps(
            {
                "status": "PASS_R24_SYNTHETIC_ENGINEERING",
                "independent_reproduction_gate": gate,
            }
        ),
        encoding="utf-8",
    )
    launcher_result.write_text(
        json.dumps(
            {"exit_code": 0, "retry_attempted": mutation == "retried"}
        ),
        encoding="utf-8",
    )
    return gate


def _write_real_v3_green(
    *,
    protocol: Path,
    certificate: Path,
    mutation: str | None = None,
) -> None:
    protocol.write_text("frozen-r24-real-v3", encoding="utf-8")
    payload: dict[str, Any] = {
        "status": "PASS_Q6_FRESH_PROCESS_REPRODUCTION",
        "qualified": True,
        "formal_claim_allowed": False,
    }
    if mutation == "real_v3_status":
        payload["status"] = "FAIL_Q6_FRESH_PROCESS_REPRODUCTION"
    elif mutation == "real_v3_formal_claim":
        payload["formal_claim_allowed"] = True
    elif mutation == "real_v3_unqualified":
        payload["qualified"] = False
    certificate.write_text(json.dumps(payload), encoding="utf-8")


def _patch_prerequisite_pins(
    monkeypatch: pytest.MonkeyPatch,
    *,
    protocol: Path,
    certificate: Path,
    launcher_result: Path,
    real_v3_protocol: Path,
    real_v3_certificate: Path,
) -> None:
    monkeypatch.setattr(
        runner,
        "R24_PREREQUISITE_PINS",
        {
            "protocol": runner.sha256_file(protocol),
            "certificate": runner.sha256_file(certificate),
            "launcher_result": runner.sha256_file(launcher_result),
        },
    )
    monkeypatch.setattr(
        runner,
        "R24_REAL_V3_PREREQUISITE_PINS",
        {
            "protocol": runner.sha256_file(real_v3_protocol),
            "certificate": runner.sha256_file(real_v3_certificate),
        },
    )


def test_r24_prerequisite_accepts_exact_terminal_green_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    protocol = tmp_path / "r24_protocol.md"
    certificate = tmp_path / "r24_certificate.json"
    launcher_result = tmp_path / "r24_launcher.json"
    real_v3_protocol = tmp_path / "r24_real_v3_protocol.md"
    real_v3_certificate = tmp_path / "r24_real_v3_certificate.json"
    _write_synthetic_green(
        protocol=protocol,
        certificate=certificate,
        launcher_result=launcher_result,
    )
    _write_real_v3_green(
        protocol=real_v3_protocol, certificate=real_v3_certificate
    )
    _patch_prerequisite_pins(
        monkeypatch,
        protocol=protocol,
        certificate=certificate,
        launcher_result=launcher_result,
        real_v3_protocol=real_v3_protocol,
        real_v3_certificate=real_v3_certificate,
    )

    ledger = runner._validate_r24_prerequisite(
        _args(
            r24_protocol=protocol,
            r24_certificate=certificate,
            r24_launcher_result=launcher_result,
            r24_real_v3_protocol=real_v3_protocol,
            r24_real_v3_certificate=real_v3_certificate,
        )
    )

    assert set(ledger) == {"synthetic", "real_v3"}
    assert set(ledger["synthetic"]) == {
        "protocol",
        "certificate",
        "launcher_result",
    }
    assert set(ledger["real_v3"]) == {"protocol", "certificate"}


@pytest.mark.parametrize(
    "mutation",
    ["mismatch", "failed_check", "retried", "real_v3_status",
     "real_v3_formal_claim", "real_v3_unqualified"],
)
def test_r24_prerequisite_mutations_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    protocol = tmp_path / "r24_protocol.md"
    certificate = tmp_path / "r24_certificate.json"
    launcher_result = tmp_path / "r24_launcher.json"
    real_v3_protocol = tmp_path / "r24_real_v3_protocol.md"
    real_v3_certificate = tmp_path / "r24_real_v3_certificate.json"
    _write_synthetic_green(
        protocol=protocol,
        certificate=certificate,
        launcher_result=launcher_result,
        mutation=mutation,
    )
    _write_real_v3_green(
        protocol=real_v3_protocol,
        certificate=real_v3_certificate,
        mutation=mutation,
    )
    _patch_prerequisite_pins(
        monkeypatch,
        protocol=protocol,
        certificate=certificate,
        launcher_result=launcher_result,
        real_v3_protocol=real_v3_protocol,
        real_v3_certificate=real_v3_certificate,
    )

    with pytest.raises(RuntimeError):
        runner._validate_r24_prerequisite(
            _args(
                r24_protocol=protocol,
                r24_certificate=certificate,
                r24_launcher_result=launcher_result,
                r24_real_v3_protocol=real_v3_protocol,
                r24_real_v3_certificate=real_v3_certificate,
            )
        )


def test_real_region_batch_assigns_unique_cross_temporal_source_ids() -> None:
    prior_path = "prior.png"
    current_path = "current.png"
    prior_boxes = [
        {"label": "Box1", "x1": 0.0, "y1": 0.0, "x2": 10.0, "y2": 10.0},
        {"label": "Box2", "x1": 10.0, "y1": 10.0, "x2": 20.0, "y2": 20.0},
    ]
    current_boxes = [
        {"label": "Box1", "x1": 1.0, "y1": 1.0, "x2": 11.0, "y2": 11.0},
        {"label": "Box3", "x1": 20.0, "y1": 20.0, "x2": 30.0, "y2": 30.0},
    ]
    record = {
        "prior_path": prior_path,
        "current_path": current_path,
        "prior_boxes": prior_boxes,
        "current_boxes": current_boxes,
    }
    features = {
        runner._crop_key(prior_path, box): torch.ones(4) for box in prior_boxes
    }
    features.update(
        {
            runner._crop_key(current_path, box): torch.ones(4)
            for box in current_boxes
        }
    )

    regions = runner._region_batch(record, features, "visual_only")
    source_ids = torch.cat(
        (regions.prior_source_ids, regions.current_source_ids), dim=1
    )

    assert source_ids.tolist() == [[0, 1, 2, 3]]
    assert len(source_ids.unique()) == source_ids.numel()
    assert runner._anatomy_constraint_audit(regions) == {
        "configured": True,
        "active_on_batch": False,
        "valid_candidates": 4,
        "compatible_candidates": 4,
        "removed_candidates": 0,
        "reason": (
            "All emitted anatomy ids are identical, so the mask removes no candidates."
        ),
    }


@pytest.mark.parametrize("empty_side", ["prior", "current"])
def test_real_region_batch_supports_two_sided_null_endpoints(
    empty_side: str,
) -> None:
    prior_path = "prior.png"
    current_path = "current.png"
    box = {"label": "Box1", "x1": 0.0, "y1": 0.0, "x2": 10.0, "y2": 10.0}
    record = {
        "prior_path": prior_path,
        "current_path": current_path,
        "prior_boxes": [] if empty_side == "prior" else [box],
        "current_boxes": [] if empty_side == "current" else [box],
    }
    populated_path = current_path if empty_side == "prior" else prior_path
    features = {runner._crop_key(populated_path, box): torch.ones(4)}

    regions = runner._region_batch(record, features, "visual_geometry_equal")

    assert tuple(regions.prior_features.shape) == (
        1,
        len(record["prior_boxes"]),
        10,
    )
    assert tuple(regions.current_features.shape) == (
        1,
        len(record["current_boxes"]),
        10,
    )
    assert tuple(regions.prior_boxes.shape) == (
        1,
        len(record["prior_boxes"]),
        4,
    )
    assert tuple(regions.current_boxes.shape) == (
        1,
        len(record["current_boxes"]),
        4,
    )
    regions.validate()


def test_feature_repeat_uses_same_registered_batch_shape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    image_path = tmp_path / "image.png"
    Image.new("RGB", (224, 224), color=(128, 128, 128)).save(image_path)
    boxes = [
        {
            "label": f"Box{index}",
            "x1": float(index),
            "y1": float(index),
            "x2": float(index + 20),
            "y2": float(index + 20),
        }
        for index in range(3)
    ]
    records = [
        {
            "prior_path": str(image_path),
            "current_path": str(image_path),
            "prior_boxes": boxes,
            "current_boxes": [],
        }
    ]

    class BatchShapeSensitiveEncoder(torch.nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.batch_sizes: list[int] = []

        def forward_features(self, batch: torch.Tensor) -> torch.Tensor:
            self.batch_sizes.append(len(batch))
            value = torch.full(
                (len(batch), 1, 4),
                float(len(batch)),
                dtype=batch.dtype,
                device=batch.device,
            )
            return value

    model = BatchShapeSensitiveEncoder()
    monkeypatch.setattr(torch.cuda, "reset_peak_memory_stats", lambda _device: None)
    monkeypatch.setattr(torch.cuda, "synchronize", lambda _device: None)

    _, ledger, _, repeat_difference = runner._extract_features(
        records,
        model,
        torch.device("cpu"),
        batch_size=2,
    )

    assert len(ledger) == 3
    assert model.batch_sizes == [2, 1, 2]
    assert repeat_difference == 0.0


@pytest.mark.parametrize(
    "comparison,expected",
    [
        ("no change", "Stable"),
        ("improved", "Improved"),
        ("worsened", "Worse"),
        ("  worsened  ", "Worse"),
    ],
)
def test_three_label_mapping_is_closed_vocabulary(
    comparison: str, expected: str
) -> None:
    assert three_label_from_comparison(comparison) == expected
    assert runner.COMPARISON_MAP[comparison.strip()] == expected


@pytest.mark.parametrize(
    "bad_value", ["", "new", "resolved", "New", "RESOLVED", "unknown"]
)
def test_three_label_mapping_rejects_unknown_vocabulary(bad_value: str) -> None:
    with pytest.raises(ValueError, match="unsupported comparison"):
        three_label_from_comparison(bad_value)


def test_coordinate_scaling_verification_accepts_exact_transform() -> None:
    scaling_row = {"ratio": 0.5, "left": 10.0, "top": 20.0}
    box_original = [4.0, 8.0, 12.0, 16.0]
    box_224 = [
        box_original[0] * 0.5 + 10.0,
        box_original[1] * 0.5 + 20.0,
        box_original[2] * 0.5 + 10.0,
        box_original[3] * 0.5 + 20.0,
    ]
    # Should not raise.
    runner._verify_box_scaling(box_224, box_original, scaling_row)


def test_coordinate_scaling_verification_rejects_drift() -> None:
    scaling_row = {"ratio": 0.5, "left": 10.0, "top": 20.0}
    box_original = [4.0, 8.0, 12.0, 16.0]
    box_224 = [
        box_original[0] * 0.5 + 10.0 + 1.0,  # 1px drift, exceeds epsilon
        box_original[1] * 0.5 + 20.0,
        box_original[2] * 0.5 + 10.0,
        box_original[3] * 0.5 + 20.0,
    ]
    with pytest.raises(ValueError, match="scaling verification failed"):
        runner._verify_box_scaling(box_224, box_original, scaling_row)


@pytest.mark.parametrize(
    "box",
    [
        [-1.0, 0.0, 10.0, 10.0],  # x1 negative beyond tolerance
        [0.0, 0.0, 0.0, 10.0],  # zero width
        [10.0, 0.0, 5.0, 10.0],  # x2 < x1
        [0.0, 0.0, 10.0, 230.0],  # y2 beyond 224 + tolerance
    ],
)
def test_box_bounds_validation_rejects_invalid_boxes(box: list[float]) -> None:
    with pytest.raises(ValueError):
        runner._validate_box_bounds(box)


def test_box_bounds_validation_accepts_valid_boxes() -> None:
    runner._validate_box_bounds([0.0, 0.0, 224.0, 224.0])
    runner._validate_box_bounds([10.0, 10.0, 50.5, 60.5])


def _cohort_audit(
    *,
    rows: int = runner.EXPECTED_ROWS,
    patients: int = runner.EXPECTED_PATIENTS,
    pairs: int = runner.EXPECTED_PAIRS,
    label_patient_counts: dict[str, int] | None = None,
) -> dict[str, Any]:
    if label_patient_counts is None:
        label_patient_counts = {
            "Stable": 122,
            "Improved": 45,
            "Worse": 72,
        }
    return {
        "retained_rows": rows,
        "retained_patients": patients,
        "retained_pairs": pairs,
        "label_patient_counts": label_patient_counts,
    }


def _aggregate() -> dict[str, Any]:
    return {
        "visual_geometry_equal": {
            "point": {
                "persistent_edge_f1": 0.99,
                "matching_event_macro_f1": 0.95,
            }
        }
    }


def _mechanics(
    *,
    b4_bootstrap: dict[str, Any] | None,
    global_dominance: bool = True,
    b4_all_passed: bool = True,
) -> dict[str, Any]:
    return {
        "global_objective_never_below_greedy": global_dominance,
        "b4_all_passed": b4_all_passed,
        "b4_bootstrap": b4_bootstrap,
    }


def test_evaluate_gates_q7_underpowered_when_few_patients() -> None:
    b4_bootstrap = {
        "patient_count": 50,  # below Q7_MIN_PATIENTS (100)
        "persistent_edge_f1_delta": {
            "point": 0.8,
            "lower": 0.6,  # > 0, so Q4 passes
            "upper": 0.95,
        },
    }
    gates, first_failed, q7_details = runner._evaluate_gates(
        _cohort_audit(),
        [{"path": "x"}],
        [{"feature_sha256": "abc"}],
        0.0,
        _mechanics(b4_bootstrap=b4_bootstrap),
        _aggregate(),
    )

    assert gates["Q4_MATCHING_SIGNAL"] is True
    assert gates["Q7_MATCHING_POWER_ESTIMATE"] is False
    assert q7_details["effective_unique_patients"] == 50
    assert q7_details["delta_match_lower_pp"] == 60.0
    assert first_failed == "Q7_MATCHING_POWER_ESTIMATE"


def test_evaluate_gates_q7_passes_when_threshold_met() -> None:
    b4_bootstrap = {
        "patient_count": runner.Q7_MIN_PATIENTS,
        "persistent_edge_f1_delta": {
            "point": 0.8,
            "lower": 0.6,
            "upper": 0.95,
        },
    }
    gates, first_failed, _ = runner._evaluate_gates(
        _cohort_audit(),
        [{"path": "x"}],
        [{"feature_sha256": "abc"}],
        0.0,
        _mechanics(b4_bootstrap=b4_bootstrap),
        _aggregate(),
    )

    assert gates["Q7_MATCHING_POWER_ESTIMATE"] is True
    assert first_failed is None


def test_evaluate_gates_q7_fails_when_ci_crosses_zero() -> None:
    b4_bootstrap = {
        "patient_count": 150,
        "persistent_edge_f1_delta": {
            "point": 0.1,
            "lower": -0.05,  # crosses zero
            "upper": 0.2,
        },
    }
    gates, first_failed, _ = runner._evaluate_gates(
        _cohort_audit(),
        [{"path": "x"}],
        [{"feature_sha256": "abc"}],
        0.0,
        _mechanics(b4_bootstrap=b4_bootstrap),
        _aggregate(),
    )

    assert gates["Q4_MATCHING_SIGNAL"] is False
    assert gates["Q7_MATCHING_POWER_ESTIMATE"] is False
    assert first_failed == "Q4_MATCHING_SIGNAL"


def test_evaluate_gates_first_stop_on_q1_cohort_drift() -> None:
    b4_bootstrap = {
        "patient_count": 150,
        "persistent_edge_f1_delta": {"point": 0.8, "lower": 0.6, "upper": 0.95},
    }
    drifted_audit = _cohort_audit(
        rows=1, patients=1, pairs=1, label_patient_counts={"Stable": 1, "Improved": 0, "Worse": 0}
    )
    gates, first_failed, _ = runner._evaluate_gates(
        drifted_audit,
        [{"path": "x"}],
        [{"feature_sha256": "abc"}],
        0.0,
        _mechanics(b4_bootstrap=b4_bootstrap),
        _aggregate(),
    )

    assert gates["Q1_COHORT_GEOMETRY"] is False
    assert first_failed == "Q1_COHORT_GEOMETRY"


def test_metric_namespaces_do_not_claim_progression_evaluation() -> None:
    namespaces = runner._evaluation_namespaces(_aggregate())

    assert namespaces["matching_evaluation"]["status"] == "EVALUATED"
    assert namespaces["matching_evaluation"]["event_labels"] == [
        "persistent",
        "death",
        "birth",
    ]
    assert namespaces["progression_evaluation"] == {
        "status": "NOT_EVALUATED",
        "labels": ["Stable", "Improved", "Worse"],
        "reason": (
            "R25.1 qualifies correspondence only; no progression prediction "
            "head is executed."
        ),
    }
    serialized = json.dumps(namespaces, sort_keys=True)
    assert "progression_macro_f1" not in serialized
    assert "three_event_macro_f1" not in serialized


def test_persistent_label_coverage_counts_distinct_patients() -> None:
    records = [
        {"patient_id": "p1", "progression": "Stable"},
        {"patient_id": "p1", "progression": "Stable"},  # duplicate patient
        {"patient_id": "p2", "progression": "Stable"},
        {"patient_id": "p3", "progression": "Improved"},
        {"patient_id": "p4", "progression": "Worse"},
        {"patient_id": "p4", "progression": "Worse"},
        {"patient_id": "p5", "progression": "Unknown"},  # ignored
    ]

    counts = persistent_label_coverage(records)

    assert counts == {"Stable": 2, "Improved": 1, "Worse": 1}


def test_persistent_label_coverage_zero_fills_missing_labels() -> None:
    records = [{"patient_id": "p1", "progression": "Stable"}]

    counts = persistent_label_coverage(records)

    assert counts == {"Stable": 1, "Improved": 0, "Worse": 0}


def _verifier_summary(
    role: str, pid: int, process_uuid: str
) -> dict[str, object]:
    return {
        "process_id": role,
        "status": "AWAITING_FRESH_PROCESS_REPRODUCTION",
        "evidence_class": "NON_CONFIRMATORY_REAL_DATA_QUALIFICATION",
        "formal_claim_allowed": False,
        "protocol": {"sha256": "r25-protocol"},
        "inputs": {"weights": {"sha256": "weights"}},
        "cohort": {"retained_rows": runner.EXPECTED_ROWS},
        "image_ledger_sha256": "images",
        "feature_ledger_sha256": "features",
        "prediction_sha256": "predictions",
        "aggregate_sha256": "aggregate",
        "evaluation_namespaces": {
            "matching_evaluation": {
                "status": "EVALUATED",
                "event_labels": ["persistent", "death", "birth"],
            },
            "progression_evaluation": {
                "status": "NOT_EVALUATED",
                "labels": ["Stable", "Improved", "Worse"],
            },
        },
        "gates": {"Q0_ASSET_LINEAGE": True},
        "q7_power_estimate": {"delta_lower_pp": 60.0},
        "aggregate": {"metric": 1.0},
        "mechanics": {"b4_all_passed": True},
        "r24_prerequisite": {"synthetic": {"protocol": {"sha256": "x"}}},
        "encoder": {
            "crop_count": 795,
            "repeat_max_abs_difference": 0.0,
            "feature_cache": {"bytes": 1024, "sha256": "cache-hash"},
        },
        "source": {"runner_sha256": "runner"},
        "interpretation_boundary": "boundary",
        "runtime": {
            "pid": pid,
            "process_uuid": process_uuid,
            "bootstrap_seed": runner.BOOTSTRAP_SEED,
            "derangement_seed": runner.DERANGEMENT_SEED,
            "bootstrap_replicates": 10_000,
        },
    }


def test_verifier_certifies_exact_reproduction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = tmp_path / "a.json"
    second = tmp_path / "b.json"
    output = tmp_path / "certificate.json"
    first.write_text(
        json.dumps(_verifier_summary("a", 101, "uuid-a")), encoding="utf-8"
    )
    second.write_text(
        json.dumps(_verifier_summary("b", 202, "uuid-b")), encoding="utf-8"
    )
    monkeypatch.setattr(
        verifier,
        "parse_args",
        lambda: type(
            "Args",
            (),
            {"process_a": first, "process_b": second, "output": output},
        )(),
    )

    assert verifier.main() == 0
    certificate = json.loads(output.read_text(encoding="utf-8"))
    assert certificate["qualified"] is True
    assert certificate["status"] == "PASS_Q6_FRESH_PROCESS_REPRODUCTION"
    assert certificate["checks"]["q7_power_estimate_exact"] is True
    assert certificate["checks"]["r24_prerequisite_exact"] is True
    assert certificate["checks"]["bootstrap_seeds_exact"] is True


def test_verifier_fails_on_q7_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = tmp_path / "a.json"
    second = tmp_path / "b.json"
    output = tmp_path / "certificate.json"
    a = _verifier_summary("a", 101, "uuid-a")
    b = _verifier_summary("b", 202, "uuid-b")
    b["q7_power_estimate"] = {"delta_lower_pp": 5.0}  # drift
    first.write_text(json.dumps(a), encoding="utf-8")
    second.write_text(json.dumps(b), encoding="utf-8")
    monkeypatch.setattr(
        verifier,
        "parse_args",
        lambda: type(
            "Args",
            (),
            {"process_a": first, "process_b": second, "output": output},
        )(),
    )

    assert verifier.main() == 2
    certificate = json.loads(output.read_text(encoding="utf-8"))
    assert certificate["qualified"] is False
    assert certificate["checks"]["q7_power_estimate_exact"] is False
