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

from scripts.aggregate_prta_gen_r41a_progression_sft import (
    paired_patient_bootstrap_with_invalid,
)
from scripts.build_prta_gen_r40b_smoke_cohort import read_json, write_json
from scripts.run_prta_gen_r48_b3_raw_two_image import _metrics


CONFIG_STATUS = "FROZEN_PRTA_GEN_R49_UNIFIED_THREE_WAY"


def _supported(comparison: dict[str, Any]) -> bool:
    return (
        float(comparison["effect_pp"]) > 0.0
        and float(comparison["ci95_lower_pp"]) > 0.0
    )


def aggregate(config_path: Path) -> dict[str, Any]:
    config = read_json(config_path)
    if config.get("status") != CONFIG_STATUS:
        raise PermissionError("R49 aggregate config is not frozen")
    output = Path(config["runtime"]["aggregate"])
    if output.exists():
        raise FileExistsError("R49 aggregate must be fresh")
    seed = int(config["training"]["seeds"][0])
    exact_root = Path(config["runtime"]["exact64_root"]) / f"seed_{seed}"
    exact = {
        arm: read_json(exact_root / arm / "result.json")
        for arm in ("naive_exact64", "prta_exact64")
    }
    for arm, result in exact.items():
        if (
            result.get("status") != config["result_statuses"]["exact64_arm_complete"]
            or result.get("protocol_id") != config["protocol_id"]
            or result.get("arm") != arm
            or result.get("seed") != seed
            or result.get("qwen_trainable_parameters") != 0
            or result.get("exact64_tokens_used") is not True
            or result.get("pixel_inputs_used") is not False
            or result.get("shared_task") != config["prompt"]["shared_task"]
        ):
            raise PermissionError(f"R49 {arm} result drift")
    if (
        exact["naive_exact64"]["projector_initialization_sha256"]
        != exact["prta_exact64"]["projector_initialization_sha256"]
        or exact["naive_exact64"]["training_example_ids_sha256"]
        != exact["prta_exact64"]["training_example_ids_sha256"]
        or exact["naive_exact64"]["projector_trainable_parameters"]
        != exact["prta_exact64"]["projector_trainable_parameters"]
    ):
        raise PermissionError("R49 exact64 capacity/initialization/order mismatch")
    shard_count = int(config["execution"]["raw_shard_count"])
    raw_root = Path(config["runtime"]["raw_root"])
    shards = [
        read_json(raw_root / f"shard_{index}_of_{shard_count}" / "result.json")
        for index in range(shard_count)
    ]
    for index, shard in enumerate(shards):
        if (
            shard.get("status") != config["result_statuses"]["raw_shard_complete"]
            or shard.get("protocol_id") != config["protocol_id"]
            or shard.get("shard_index") != index
            or shard.get("shard_count") != shard_count
            or shard.get("model_trainable_parameters") != 0
            or shard.get("pixel_inputs_used") is not True
            or shard.get("shared_task") != config["prompt"]["shared_task"]
        ):
            raise PermissionError("R49 raw shard drift")
    records = sorted(
        [record for shard in shards for record in shard["rows"]],
        key=lambda record: int(record["row_index"]),
    )
    expected_rows = int(config["authority"]["evaluation_rows"])
    if [int(record["row_index"]) for record in records] != list(range(expected_rows)):
        raise PermissionError("R49 raw shard coverage drift")
    example_ids = [str(record["example_id"]) for record in records]
    targets = [int(record["target"]) for record in records]
    patient_ids = [str(value) for value in exact["prta_exact64"]["evaluation_patient_ids"]]
    for result in exact.values():
        if (
            result["evaluation_example_ids"] != example_ids
            or [int(value) for value in result["targets"]] != targets
            or result["evaluation_patient_ids"] != patient_ids
        ):
            raise PermissionError("R49 three-way example/target order mismatch")
    if len(set(patient_ids)) != expected_rows:
        raise PermissionError("R49 evaluation patients are not unique")
    raw_predictions = [int(record["prediction"]) for record in records]
    raw_metrics = _metrics(targets, raw_predictions)
    raw_metrics["schema_validity"] = sum(
        bool(record["schema_valid"]) for record in records
    ) / expected_rows
    raw_metrics["finding_echo_accuracy"] = sum(
        bool(record["finding_correct"]) for record in records
    ) / expected_rows
    predictions = {
        "raw_two_image_qwen": raw_predictions,
        "naive_exact64": [int(value) for value in exact["naive_exact64"]["predictions"]],
        "prta_exact64": [int(value) for value in exact["prta_exact64"]["predictions"]],
    }
    metrics = {
        "raw_two_image_qwen": raw_metrics,
        "naive_exact64": exact["naive_exact64"]["metrics"],
        "prta_exact64": exact["prta_exact64"]["metrics"],
    }
    statistics = config["evaluation"]
    prta_minus_raw = paired_patient_bootstrap_with_invalid(
        patient_ids=patient_ids,
        targets=targets,
        primary_predictions=predictions["prta_exact64"],
        control_predictions=predictions["raw_two_image_qwen"],
        class_count=len(config["target"]["progression_values"]),
        replicates=int(statistics["paired_patient_bootstrap_replicates"]),
        seed=int(statistics["paired_patient_bootstrap_seed"]),
    )
    prta_minus_naive = paired_patient_bootstrap_with_invalid(
        patient_ids=patient_ids,
        targets=targets,
        primary_predictions=predictions["prta_exact64"],
        control_predictions=predictions["naive_exact64"],
        class_count=len(config["target"]["progression_values"]),
        replicates=int(statistics["paired_patient_bootstrap_replicates"]),
        seed=int(statistics["paired_patient_bootstrap_seed"]) + 1,
    )
    result = {
        "schema": "visualvit.prta-gen.r49-unified-three-way-aggregate.v1",
        "status": config["result_statuses"]["aggregate_complete"],
        "protocol_id": config["protocol_id"],
        "study_tier": config["study_tier"],
        "patients": expected_rows,
        "evaluation_partitions": config["authority"]["evaluation_partitions"],
        "same_patients": True,
        "same_targets": True,
        "same_frozen_qwen": True,
        "same_semantic_task_and_output_contract": True,
        "serialized_multimodal_prompts_identical": False,
        "exact64_same_token_budget": True,
        "exact64_same_projector_capacity": True,
        "exact64_same_projector_initialization": True,
        "exact64_same_training_order": True,
        "metrics": metrics,
        "comparisons": {
            "prta_exact64_minus_raw_two_image_qwen": prta_minus_raw,
            "prta_exact64_minus_naive_exact64": prta_minus_naive,
        },
        "answers": {
            "prta_better_than_raw_two_image_supported": _supported(prta_minus_raw),
            "prta_better_than_naive_exact64_supported": _supported(prta_minus_naive),
            "cross_time_alignment_gain_supported": _supported(prta_minus_naive),
        },
        "cost": {
            "raw_generation_seconds_sum": sum(
                float(shard["cost"]["generation_seconds"]) for shard in shards
            ),
            "raw_parallel_wall_upper_bound_seconds": max(
                float(shard["cost"]["generation_seconds"]) for shard in shards
            ),
            "raw_total_vision_grid_tokens": sum(
                int(shard["cost"]["total_vision_grid_tokens"]) for shard in shards
            ),
            "raw_compute_matched_to_exact64": False,
            "naive_elapsed_seconds": exact["naive_exact64"]["elapsed_seconds"],
            "prta_elapsed_seconds": exact["prta_exact64"]["elapsed_seconds"],
        },
        "posthoc_case_study": True,
        "independent_confirmation_claim_allowed": False,
        "gold_outcomes_read": False,
        "external_outcomes_read": False,
        "clinical_claim_allowed": False,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    write_json(output, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Aggregate R49 unified three-way comparison")
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    result = aggregate(args.config)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
