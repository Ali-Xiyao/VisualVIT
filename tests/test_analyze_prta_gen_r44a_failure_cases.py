from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from scripts.analyze_prta_gen_r44a_failure_cases import (
    CASE_STATUS,
    EVALUATION_ARMS,
    EXPECTED_CLASSES,
    MODEL_ARMS,
    SEEDS,
    build_case_study,
    classification_metrics,
)


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def make_fixture(
    tmp_path: Path,
) -> tuple[dict[tuple[int, str], Path], Path, str]:
    classes = list(EXPECTED_CLASSES)
    targets = [index % len(classes) for index in range(250)]
    example_ids = [f"example-{index:03d}" for index in range(250)]
    patient_ids = [f"patient-{index:03d}" for index in range(250)]
    result_paths = {}
    for seed in SEEDS:
        for model_arm in MODEL_ARMS:
            offset = 0 if model_arm == "g0_projector_only" else seed % 5
            predictions = {
                "true_pair": [
                    target
                    if index % 4
                    else (target + offset + 1) % len(classes)
                    for index, target in enumerate(targets)
                ],
                "current_only": [
                    target if index % 3 else (target + 1) % len(classes)
                    for index, target in enumerate(targets)
                ],
                "query_only": [
                    (target + 2) % len(classes) for target in targets
                ],
                "prior_shuffle": [
                    target if index % 5 else (target + 3) % len(classes)
                    for index, target in enumerate(targets)
                ],
            }
            metrics = {}
            for evaluation_arm in EVALUATION_ARMS:
                computed = classification_metrics(
                    targets, predictions[evaluation_arm], classes
                )
                metrics[evaluation_arm] = {
                    **computed,
                    "row_count": 250,
                    "schema_validity": 1.0,
                    "finding_echo_accuracy": 1.0,
                    "invalid_or_wrong_finding_predictions": 0,
                }
            result = {
                "schema": "visualvit.prta-gen.r44a-arm-result.v1",
                "status": "PASS_PRTA_GEN_R44A_ARM_EVALUATION",
                "protocol_id": "prta-gen-r44a-cross-source-silver-sft-v1",
                "study_tier": (
                    "cross_source_silver_progression_only_sft_survival"
                ),
                "seed": seed,
                "model_arm": model_arm,
                "development_rows": 250,
                "development_patients": 250,
                "training_rows": 1000,
                "training_patients": 1000,
                "optimizer_updates": 94,
                "exact64_tokens_used": True,
                "pixel_inputs_used": False,
                "protected_300_dev_read": False,
                "revealed_483_test_read": False,
                "gold_outcomes_read": False,
                "external_outcomes_read": False,
                "r42_unlocked": False,
                "qwen_free_generation_survival_unlocked": False,
                "scientific_claim_allowed": False,
                "classes": classes,
                "targets": targets,
                "development_example_ids": example_ids,
                "development_patient_ids": patient_ids,
                "predictions": predictions,
                "metrics": metrics,
            }
            path = tmp_path / f"seed_{seed}_{model_arm}.json"
            write_json(path, result)
            result_paths[(seed, model_arm)] = path
    roster = {
        "schema": "visualvit.prta-gen.r44a-roster.v1",
        "status": "PASS_PRTA_GEN_R44A_ROSTER_SUPPORT",
        "protocol_id": "prta-gen-r44a-cross-source-silver-sft-v1",
        "one_row_per_patient": True,
        "patient_sets_disjoint": True,
        "selected_images_complete": True,
        "resplit_allowed": False,
        "development_outcomes_read": False,
        "protected_300_dev_read": False,
        "revealed_483_test_read": False,
        "gold_outcomes_read": False,
        "external_outcomes_read": False,
        "r40c_outcomes_used_for_roster_selection": False,
        "r41a_outcomes_used_for_roster_selection": False,
        "r41a_development_reused": False,
        "scientific_claim_allowed": False,
        "partitions": {
            "train": {
                "rows": [
                    {
                        "example_id": f"train-example-{index:04d}",
                        "patient_id": f"train-patient-{index:04d}",
                        "finding": "Edema",
                        "progression": classes[index % len(classes)],
                    }
                    for index in range(1000)
                ]
            },
            "development": {
                "rows": [
                    {
                        "example_id": example_id,
                        "patient_id": patient_id,
                        "finding": f"Finding {index % 3}",
                        "progression": classes[targets[index]],
                    }
                    for index, (example_id, patient_id) in enumerate(
                        zip(example_ids, patient_ids, strict=True)
                    )
                ]
            },
        },
    }
    roster_path = tmp_path / "roster.json"
    write_json(roster_path, roster)
    return result_paths, roster_path, sha256_file(roster_path)


def recursive_keys(value: Any) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            keys.add(str(key))
            keys.update(recursive_keys(item))
    elif isinstance(value, list):
        for item in value:
            keys.update(recursive_keys(item))
    return keys


def test_case_study_is_identity_free_and_mechanism_focused(
    tmp_path: Path,
) -> None:
    result_paths, roster_path, roster_hash = make_fixture(tmp_path)
    payload = build_case_study(
        result_paths=result_paths,
        roster_path=roster_path,
        roster_sha256=roster_hash,
        per_pattern=2,
    )
    assert payload["status"] == CASE_STATUS
    assert payload["rows"] == payload["patients"] == 250
    assert payload["descriptive_only"] is True
    assert payload["new_training_started"] is False
    assert (
        payload["observed_development_reuse_for_selection_allowed"] is False
    )
    for summary in payload["seed_summaries"]:
        comparison = summary["g1_true_pair_vs_controls"]["prior_shuffle"]
        assert 0.0 <= comparison["same_prediction_rate"] <= 1.0
        assert (
            comparison["changed_prediction_rows"]
            + comparison["same_prediction_rows"]
            == 250
        )
        migration = summary["g0_to_g1_true_pair_migration"]
        assert sum(migration["category_counts"].values()) == 250
    assert sum(
        payload["cross_seed_g1_true_shuffle_changed_seed_count"].values()
    ) == 250
    assert not {
        "example_id",
        "patient_id",
        "development_example_ids",
        "development_patient_ids",
    } & recursive_keys(payload)
    assert all(
        case["case_id"].startswith("CASE-")
        and case["reuse_for_selection_allowed"] is False
        for case in payload["anonymized_cases"]
    )


def test_rejects_cross_result_alignment_drift(tmp_path: Path) -> None:
    result_paths, roster_path, roster_hash = make_fixture(tmp_path)
    path = result_paths[(29, "g1_attention_lora")]
    result = json.loads(path.read_text(encoding="utf-8"))
    result["development_example_ids"][0] = "different"
    write_json(path, result)
    with pytest.raises(ValueError, match="alignment drift"):
        build_case_study(
            result_paths=result_paths,
            roster_path=roster_path,
            roster_sha256=roster_hash,
        )


def test_rejects_result_firewall_drift(tmp_path: Path) -> None:
    result_paths, roster_path, roster_hash = make_fixture(tmp_path)
    path = result_paths[(17, "g0_projector_only")]
    result = json.loads(path.read_text(encoding="utf-8"))
    result["gold_outcomes_read"] = True
    write_json(path, result)
    with pytest.raises(PermissionError, match="firewall/schema drift"):
        build_case_study(
            result_paths=result_paths,
            roster_path=roster_path,
            roster_sha256=roster_hash,
        )


def test_rejects_metric_drift(tmp_path: Path) -> None:
    result_paths, roster_path, roster_hash = make_fixture(tmp_path)
    path = result_paths[(43, "g1_attention_lora")]
    result = json.loads(path.read_text(encoding="utf-8"))
    result["metrics"]["true_pair"]["macro_f1"] += 0.01
    write_json(path, result)
    with pytest.raises(ValueError, match="metric drift"):
        build_case_study(
            result_paths=result_paths,
            roster_path=roster_path,
            roster_sha256=roster_hash,
        )


def test_rejects_roster_hash_drift(tmp_path: Path) -> None:
    result_paths, roster_path, roster_hash = make_fixture(tmp_path)
    roster = json.loads(roster_path.read_text(encoding="utf-8"))
    roster["namespace"] = "mutated"
    write_json(roster_path, roster)
    with pytest.raises(ValueError, match="SHA-256 drift"):
        build_case_study(
            result_paths=result_paths,
            roster_path=roster_path,
            roster_sha256=roster_hash,
        )
