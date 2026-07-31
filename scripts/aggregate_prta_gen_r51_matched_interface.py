from __future__ import annotations

# ruff: noqa: E402

import argparse
import json
from pathlib import Path
import sys
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE))
sys.path.insert(0, str(WORKSPACE / "src"))

from scripts.build_prta_gen_r40b_smoke_cohort import read_json, write_json
from scripts.r51_common import sha256_file, validate_authority
from visualvit.qualification import patient_bootstrap_mean_seed_difference


DEFAULT_CONFIG = (
    WORKSPACE / "configs" / "prta_gen" / "prta_gen_r51_matched_interface_v1.json"
)


def _load_results(
    config: dict[str, Any], evaluation_rows: list[dict[str, Any]]
) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]]]:
    seeds = [int(value) for value in config["training"]["seeds"]]
    arms = [str(value) for value in config["evaluation"]["arms"]]
    by_arm: dict[str, list[dict[str, Any]]] = {}
    receipts: list[dict[str, Any]] = []
    for arm in arms:
        values = []
        for seed in seeds:
            path = Path(config["runtime"]["runs"]) / f"seed_{seed}" / arm / "result.json"
            result = read_json(path)
            if (
                result.get("status") != config["result_statuses"]["arm_complete"]
                or result.get("protocol_id") != config["protocol_id"]
                or result.get("arm") != arm
                or result.get("seed") != seed
                or result.get("evaluation_rows") != len(evaluation_rows)
                or result.get("qwen_trainable_parameters") != 0
                or result.get("translation_trainable_parameters") != 0
            ):
                raise PermissionError(f"R51 arm result drift: {path}")
            values.append(result)
            receipts.append(
                {
                    "path": str(path),
                    "bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                    "arm": arm,
                    "seed": seed,
                }
            )
        by_arm[arm] = values
    return by_arm, receipts


def aggregate(config_path: Path) -> dict[str, Any]:
    config, _, evaluation_rows = validate_authority(
        config_path, require_pinned_caches=True
    )
    output = Path(config["runtime"]["aggregate"])
    if output.exists():
        raise FileExistsError(f"R51 aggregate must be fresh: {output}")
    by_arm, receipts = _load_results(config, evaluation_rows)
    expected_patients = [str(row["patient_id"]) for row in evaluation_rows]
    expected_examples = [str(row["example_id"]) for row in evaluation_rows]
    flattened = [result for values in by_arm.values() for result in values]
    targets = flattened[0]["targets"]
    if any(
        result["evaluation_patient_ids"] != expected_patients
        or result["evaluation_example_ids"] != expected_examples
        or result["targets"] != targets
        for result in flattened
    ):
        raise PermissionError("R51 cross-arm row/target parity failed")
    seeds = [int(value) for value in config["training"]["seeds"]]
    for index, seed in enumerate(seeds):
        hashes = {
            by_arm[arm][index]["projector_initialization_sha256"]
            for arm in by_arm
        }
        if len(hashes) != 1:
            raise PermissionError(f"R51 shared initialization drift for seed {seed}")
    summaries: dict[str, Any] = {}
    predictions: dict[str, list[list[int]]] = {}
    for arm, values in by_arm.items():
        macro = [float(value["metrics"]["macro_f1"]) for value in values]
        accuracy = [float(value["metrics"]["progression_accuracy"]) for value in values]
        predictions[arm] = [list(value["predictions"]) for value in values]
        summaries[arm] = {
            "macro_f1_by_seed": macro,
            "macro_f1_mean": sum(macro) / len(macro),
            "accuracy_by_seed": accuracy,
            "accuracy_mean": sum(accuracy) / len(accuracy),
            "schema_validity_by_seed": [
                float(value["metrics"]["schema_validity"]) for value in values
            ],
            "finding_echo_accuracy_by_seed": [
                float(value["metrics"]["finding_echo_accuracy"]) for value in values
            ],
            "per_class_recall_by_seed": [
                value["metrics"]["per_class_recall"] for value in values
            ],
            "projector_trainable_parameters": int(
                values[0]["projector_trainable_parameters"]
            ),
            "qwen_trainable_parameters": 0,
            "translation_trainable_parameters": 0,
            "elapsed_seconds_by_seed": [float(value["elapsed_seconds"]) for value in values],
            "peak_cuda_allocated_bytes_by_seed": [
                int(value["peak_cuda_allocated_bytes"]) for value in values
            ],
            "method_provenance": values[0]["method_provenance"],
        }
    comparisons: dict[str, Any] = {}
    contrasts = (
        ("tila_exact64", "prta_exact64"),
        ("b2_exact64", "prta_exact64"),
        ("tila_exact64", "b2_exact64"),
    )
    for index, (left, right) in enumerate(contrasts):
        comparisons[f"{left}_minus_{right}"] = patient_bootstrap_mean_seed_difference(
            patient_ids=expected_patients,
            targets=targets,
            true_predictions_by_seed=predictions[left],
            control_predictions_by_seed=predictions[right],
            class_count=5,
            replicates=int(config["evaluation"]["paired_patient_bootstrap_replicates"]),
            seed=int(config["evaluation"]["paired_patient_bootstrap_seed"]) + index,
            expected_seed_count=len(seeds),
        )
    result = {
        "schema": "visualvit.prta-gen.r51-matched-interface-aggregate.v1",
        "status": config["result_statuses"]["aggregate_complete"],
        "protocol_id": config["protocol_id"],
        "study_tier": config["study_tier"],
        "patients": len(expected_patients),
        "same_patients_targets_prompt_projector_qwen": True,
        "methods": summaries,
        "comparisons": comparisons,
        "result_receipts": receipts,
        "fresh_evaluation_model_outcomes_read_once": True,
        "method_or_seed_selection_from_results_allowed": False,
        "protected_300_dev_read": False,
        "revealed_483_test_read": False,
        "gold_outcomes_read": False,
        "external_outcomes_read": False,
        "clinical_claim_allowed": False,
        "independent_external_confirmation_claim_allowed": False,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    write_json(output, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Aggregate frozen R51 results")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    result = aggregate(args.config)
    print(
        json.dumps(
            {
                "status": result["status"],
                "patients": result["patients"],
                "macro_f1_means": {
                    arm: value["macro_f1_mean"]
                    for arm, value in result["methods"].items()
                },
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
