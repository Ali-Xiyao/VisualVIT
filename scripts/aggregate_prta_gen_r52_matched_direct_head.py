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
from scripts.r51_common import sha256_file
from scripts.run_prta_gen_r52_matched_direct_head import validate_r52_authority
from visualvit.qualification import patient_bootstrap_mean_seed_difference


DEFAULT_CONFIG = (
    WORKSPACE / "configs" / "prta_gen" / "prta_gen_r52_matched_direct_head_v1.json"
)


def _load_results(
    config: dict[str, Any], evaluation_rows: list[dict[str, Any]]
) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]]]:
    by_arm: dict[str, list[dict[str, Any]]] = {}
    receipts = []
    for arm in config["evaluation"]["arms"]:
        values = []
        for seed in config["training"]["seeds"]:
            path = Path(config["runtime"]["runs"]) / f"seed_{seed}" / arm / "result.json"
            value = read_json(path)
            if (
                value.get("status") != config["result_statuses"]["arm_complete"]
                or value.get("protocol_id") != config["protocol_id"]
                or value.get("arm") != arm
                or value.get("seed") != seed
                or value.get("evaluation_rows") != len(evaluation_rows)
                or value.get("arm_specific_trainable_parameters") != 0
                or value.get("head_trainable_parameters")
                != int(config["head"]["parameter_count"])
            ):
                raise PermissionError(f"R52 arm result drift: {path}")
            values.append(value)
            receipts.append(
                {
                    "path": str(path),
                    "bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                    "arm": arm,
                    "seed": seed,
                }
            )
        by_arm[str(arm)] = values
    return by_arm, receipts


def aggregate(config_path: Path) -> dict[str, Any]:
    config, _, _, evaluation_rows = validate_r52_authority(config_path)
    output = Path(config["runtime"]["aggregate"])
    if output.exists():
        raise FileExistsError(f"R52 aggregate must be fresh: {output}")
    by_arm, receipts = _load_results(config, evaluation_rows)
    patients = [str(row["patient_id"]) for row in evaluation_rows]
    examples = [str(row["example_id"]) for row in evaluation_rows]
    flat = [result for values in by_arm.values() for result in values]
    targets = flat[0]["targets"]
    if any(
        result["evaluation_patient_ids"] != patients
        or result["evaluation_example_ids"] != examples
        or result["targets"] != targets
        for result in flat
    ):
        raise PermissionError("R52 cross-arm row/target parity failed")
    for index, seed in enumerate(config["training"]["seeds"]):
        hashes = {values[index]["head_initialization_sha256"] for values in by_arm.values()}
        if len(hashes) != 1:
            raise PermissionError(f"R52 shared initialization drift for seed {seed}")
    methods: dict[str, Any] = {}
    predictions: dict[str, list[list[int]]] = {}
    for arm, values in by_arm.items():
        macro = [float(value["metrics"]["macro_f1"]) for value in values]
        accuracy = [float(value["metrics"]["accuracy"]) for value in values]
        predictions[arm] = [list(value["predictions"]) for value in values]
        methods[arm] = {
            "macro_f1_by_seed": macro,
            "macro_f1_mean": sum(macro) / len(macro),
            "accuracy_by_seed": accuracy,
            "accuracy_mean": sum(accuracy) / len(accuracy),
            "per_class_recall_by_seed": [
                value["metrics"]["per_class_recall"] for value in values
            ],
            "head_trainable_parameters": int(values[0]["head_trainable_parameters"]),
            "arm_specific_trainable_parameters": 0,
            "elapsed_seconds_by_seed": [float(value["elapsed_seconds"]) for value in values],
            "peak_cuda_allocated_bytes_by_seed": [
                int(value["peak_cuda_allocated_bytes"]) for value in values
            ],
            "method_provenance": values[0]["method_provenance"],
        }
    contrast_pairs = (
        ("prta_exact64", "tila_exact64"),
        ("prta_exact64", "b2_exact64"),
        ("tila_exact64", "b2_exact64"),
    )
    comparisons: dict[str, Any] = {}
    for offset, (left, right) in enumerate(contrast_pairs):
        comparisons[f"{left}_minus_{right}"] = patient_bootstrap_mean_seed_difference(
            patient_ids=patients,
            targets=targets,
            true_predictions_by_seed=predictions[left],
            control_predictions_by_seed=predictions[right],
            class_count=5,
            replicates=int(config["evaluation"]["paired_patient_bootstrap_replicates"]),
            seed=int(config["evaluation"]["paired_patient_bootstrap_seed"]) + offset,
            expected_seed_count=len(config["training"]["seeds"]),
        )
    primary = [comparisons[name] for name in config["evaluation"]["primary_contrasts"]]
    strict = all(float(value["ci95_lower_pp"]) > 0.0 for value in primary)
    result = {
        "schema": "visualvit.prta-gen.r52-matched-direct-head-aggregate.v1",
        "status": config["result_statuses"]["aggregate_complete"],
        "protocol_id": config["protocol_id"],
        "study_tier": config["study_tier"],
        "patients": len(patients),
        "same_patients_exact64_head_initialization_training": True,
        "methods": methods,
        "comparisons": comparisons,
        "prta_strict_superiority_supported": strict,
        "strict_superiority_rule": config["evaluation"]["strict_prta_superiority_rule"],
        "result_receipts": receipts,
        "historical_results_informed_hypothesis": True,
        "r52_method_or_seed_selection_from_results_allowed": False,
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
    parser = argparse.ArgumentParser(description="Aggregate frozen R52 direct heads")
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
                "prta_strict_superiority_supported": result[
                    "prta_strict_superiority_supported"
                ],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
