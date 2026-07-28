import json

import pytest

from scripts.analyze_r37_inversion_failures import build_case_study
from visualvit.cmcp import transition_examples


def write_fixture(tmp_path, *, protected=False):
    transition_root = tmp_path / "transitions"
    transition_root.mkdir()
    rows = [
        {
            "pair_id": f"pair-{index}",
            "patient_id": f"patient-{index}",
            "partition": "internal_calibration",
            "interval_days": 10 + index,
            "prior_view": "PA",
            "current_view": "PA",
            "prior_dicom_id": f"prior-{index}",
            "current_dicom_id": f"current-{index}",
            "transition_supervision": [
                {
                    "finding": "Edema",
                    "label": label,
                }
            ],
        }
        for index, label in enumerate(("Stable", "Improved"))
    ]
    manifest = transition_root / "r37_internal_calibration_manifest.jsonl"
    manifest.write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )
    examples = sorted(
        transition_examples(rows),
        key=lambda item: (item["patient_id"], item["example_id"]),
    )
    result_paths = {}
    for seed, inverted in ((17, [0, 2]), (29, [1, 2])):
        payload = {
            "schema": "visualvit.r37.prta-formal-training.v1",
            "status": "PASS_R37_PRTA_FORMAL_TRAINING",
            "formal": True,
            "variant": "A6",
            "seed": seed,
            "protected_outcomes_read": protected,
            "sealed_test_read": False,
            "gold_outcomes_read": False,
            "source_hashes_recomputed": False,
            "scientific_claim_allowed": False,
            "calibration": {
                "examples": 2,
                "patient_ids": [
                    str(item["patient_id"]) for item in examples
                ],
                "target_labels": [0, 1],
                "true_pair_predictions": [0, 1],
                "inverted_predictions": inverted,
            },
        }
        path = tmp_path / f"seed-{seed}.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        result_paths[seed] = path
    return transition_root, result_paths


def test_case_study_reports_failure_and_cross_seed_overlap(tmp_path):
    transition_root, result_paths = write_fixture(tmp_path)
    result = build_case_study(
        transition_root=transition_root,
        result_paths=result_paths,
    )

    assert result["status"] == "STOP_R37_INVERSION_CONSISTENCY"
    assert result["descriptive_only"]
    assert result["observed_calibration_reuse_allowed"] is False
    assert result["seeds"][0]["inversion_consistency_rate"] == 1.0
    assert result["seeds"][1]["inversion_consistency_rate"] == 0.5
    assert result["cross_seed_failure_overlap"]["union_rows"] == 1
    assert result["cross_seed_failure_overlap"]["intersection_rows"] == 0


def test_case_study_rejects_protected_outcome_drift(tmp_path):
    transition_root, result_paths = write_fixture(
        tmp_path, protected=True
    )
    with pytest.raises(ValueError, match="protected_outcomes"):
        build_case_study(
            transition_root=transition_root,
            result_paths=result_paths,
        )
