from __future__ import annotations

# ruff: noqa: E402

import argparse
from itertools import chain
import json
from pathlib import Path
import sys
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE))
sys.path.insert(0, str(WORKSPACE / "src"))

from scripts.audit_prta_gen_r44_independent_support import sha256_file
from scripts.r50_common import (
    METHODS,
    read_json,
    validate_authority,
    write_json,
)
from visualvit.qualification import patient_bootstrap_mean_seed_difference


DEFAULT_CONFIG = (
    WORKSPACE / "configs" / "prta_gen" / "prta_gen_r50_method_benchmark_v1.json"
)


def _load_results(
    config: dict[str, Any],
) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]]]:
    seeds = [int(value) for value in config["training"]["seeds"]]
    by_method: dict[str, list[dict[str, Any]]] = {}
    receipts: list[dict[str, Any]] = []
    for method in METHODS:
        values = []
        for seed in seeds:
            path = (
                Path(config["runtime"]["runs"])
                / method
                / f"seed_{seed}"
                / "result.json"
            )
            result = read_json(path)
            if (
                result.get("status")
                != config["result_statuses"]["method_pass"]
                or result.get("protocol_id") != config["protocol_id"]
                or result.get("method") != method
                or result.get("seed") != seed
                or result.get("evaluation_rows")
                != int(config["authority"]["evaluation_rows"])
            ):
                raise PermissionError(f"R50 method result drift: {path}")
            values.append(result)
            receipts.append(
                {
                    "path": str(path),
                    "bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                    "method": method,
                    "seed": seed,
                }
            )
        by_method[method] = values
    return by_method, receipts


def aggregate(config_path: Path) -> dict[str, Any]:
    config, _, _, evaluation_rows = validate_authority(config_path)
    output = Path(config["runtime"]["aggregate"])
    if output.exists():
        raise FileExistsError(f"R50 aggregate must be fresh: {output}")
    by_method, receipts = _load_results(config)
    flattened = list(chain.from_iterable(by_method.values()))
    expected_patients = [str(row["patient_id"]) for row in evaluation_rows]
    expected_examples = [str(row["example_id"]) for row in evaluation_rows]
    first_targets = flattened[0]["targets"]
    if any(
        result["evaluation_patient_ids"] != expected_patients
        or result["evaluation_example_ids"] != expected_examples
        or result["targets"] != first_targets
        for result in flattened
    ):
        raise PermissionError("R50 cross-method evaluation parity failed")

    prta = read_json(Path(config["r49_references"]["prta_exact64_result"]["path"]))
    if (
        prta["evaluation_patient_ids"] != expected_patients
        or prta["evaluation_example_ids"] != expected_examples
        or prta["targets"] != first_targets
    ):
        raise PermissionError("R50-to-R49 paired-row parity failed")
    predictions: dict[str, list[list[int]]] = {
        method: [result["predictions"]["primary"] for result in results]
        for method, results in by_method.items()
    }
    predictions["r49_prta_exact64"] = [prta["predictions"]] * len(
        config["training"]["seeds"]
    )
    summaries: dict[str, Any] = {}
    for method, results in by_method.items():
        macro_f1_values = [float(result["metrics"]["macro_f1"]) for result in results]
        accuracy_values = [float(result["metrics"]["accuracy"]) for result in results]
        summaries[method] = {
            "macro_f1_by_seed": macro_f1_values,
            "macro_f1_mean": sum(macro_f1_values) / len(macro_f1_values),
            "accuracy_by_seed": accuracy_values,
            "accuracy_mean": sum(accuracy_values) / len(accuracy_values),
            "mapped_prediction_consistency_by_seed": [
                float(result["metrics"]["mapped_prediction_consistency"])
                for result in results
            ],
            "trainable_parameters": int(results[0]["trainable_parameters"]),
            "elapsed_seconds_by_seed": [
                float(result["elapsed_seconds"]) for result in results
            ],
            "peak_cuda_allocated_bytes_by_seed": [
                int(result["peak_cuda_allocated_bytes"]) for result in results
            ],
            "reproduction_label": results[0]["reproduction_label"],
        }
    comparisons: dict[str, Any] = {}
    base_seed = int(config["comparison"]["bootstrap_seed"])
    for index, (left, right) in enumerate(
        config["comparison"]["registered_contrasts"]
    ):
        comparisons[f"{left}_minus_{right}"] = patient_bootstrap_mean_seed_difference(
            patient_ids=expected_patients,
            targets=first_targets,
            true_predictions_by_seed=predictions[left],
            control_predictions_by_seed=predictions[right],
            class_count=5,
            replicates=int(config["comparison"]["bootstrap_replicates"]),
            seed=base_seed + index,
            expected_seed_count=len(config["training"]["seeds"]),
        )
        comparisons[f"{left}_minus_{right}"]["cross_interface_descriptive"] = (
            right == "r49_prta_exact64"
        )
    result = {
        "schema": "visualvit.prta-gen.r50-method-benchmark-aggregate.v1",
        "status": config["result_statuses"]["aggregate_complete"],
        "protocol_id": config["protocol_id"],
        "study_tier": config["study_tier"],
        "posthoc_internal_benchmark": True,
        "independent_confirmation_claim_allowed": False,
        "clinical_claim_allowed": False,
        "patients": len(expected_patients),
        "same_patients_and_targets": True,
        "methods": summaries,
        "r49_prta_exact64": {
            "macro_f1": float(prta["metrics"]["macro_f1"]),
            "accuracy": float(prta["metrics"]["progression_accuracy"]),
            "interface": "frozen_Qwen_exact64_JSON_generation",
            "directly_capacity_matched_to_r50_classifiers": False,
        },
        "comparisons": comparisons,
        "result_receipts": receipts,
        "protected_483_test_read": False,
        "gold_outcomes_read": False,
        "external_outcomes_read": False,
        "method_selection_from_results_allowed": False,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    write_json(output, result)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Aggregate R50 methods")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    return parser.parse_args()


def main() -> int:
    result = aggregate(parse_args().config)
    print(
        json.dumps(
            {
                "status": result["status"],
                "patients": result["patients"],
                "macro_f1_means": {
                    method: value["macro_f1_mean"]
                    for method, value in result["methods"].items()
                },
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
