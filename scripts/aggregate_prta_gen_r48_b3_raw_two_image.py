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


def aggregate(config_path: Path) -> dict[str, Any]:
    config = read_json(config_path)
    root = Path(config["runtime"]["formal_root"])
    output = root / "aggregate.json"
    if output.exists():
        raise FileExistsError("raw two-image aggregate must be fresh")
    shard_count = int(config["execution"]["formal_shard_count"])
    shards = [
        read_json(root / f"shard_{index}_of_{shard_count}" / "result.json")
        for index in range(shard_count)
    ]
    expected_status = config["result_statuses"]["formal_shard_complete"]
    if any(
        shard.get("status") != expected_status
        or shard.get("shard_index") != index
        or shard.get("shard_count") != shard_count
        or shard.get("model_trainable_parameters") != 0
        or shard.get("pixel_inputs_used") is not True
        for index, shard in enumerate(shards)
    ):
        raise PermissionError("raw two-image shard receipt drift")
    records = sorted(
        [record for shard in shards for record in shard["rows"]],
        key=lambda record: int(record["row_index"]),
    )
    expected_rows = int(config["authority"]["expected_rows"])
    if [int(record["row_index"]) for record in records] != list(
        range(expected_rows)
    ):
        raise PermissionError("raw two-image shard coverage drift")
    baseline = read_json(Path(config["authority"]["fprr_baseline_result"]))
    baseline_ids = [str(value) for value in baseline["development_example_ids"]]
    raw_ids = [str(record["example_id"]) for record in records]
    if raw_ids != baseline_ids:
        raise PermissionError("raw/FPRR example-order drift")
    targets = [int(record["target"]) for record in records]
    if targets != [int(value) for value in baseline["targets"]]:
        raise PermissionError("raw/FPRR target drift")
    predictions = [int(record["prediction"]) for record in records]
    metrics = _metrics(targets, predictions)
    metrics["schema_validity"] = sum(
        bool(record["schema_valid"]) for record in records
    ) / expected_rows
    metrics["finding_echo_accuracy"] = sum(
        bool(record["finding_correct"]) for record in records
    ) / expected_rows
    comparison = paired_patient_bootstrap_with_invalid(
        patient_ids=baseline["development_patient_ids"],
        targets=targets,
        primary_predictions=predictions,
        control_predictions=baseline["predictions"]["true_pair"],
        class_count=len(config["target"]["progression_values"]),
        replicates=int(
            config["statistics"]["paired_patient_bootstrap_replicates"]
        ),
        seed=int(config["statistics"]["paired_patient_bootstrap_seed"]),
    )
    result = {
        "schema": "visualvit.prta-gen.r48-b3-raw-two-image-aggregate.v1",
        "status": config["result_statuses"]["aggregate_complete"],
        "protocol_id": config["protocol_id"],
        "metrics": metrics,
        "fprr_true_pair_metrics": baseline["metrics"]["true_pair"],
        "raw_minus_fprr_true_pair": comparison,
        "cost": {
            "generation_seconds_sum": sum(
                float(shard["cost"]["generation_seconds"]) for shard in shards
            ),
            "wall_time_parallel_upper_bound_seconds": max(
                float(shard["cost"]["generation_seconds"]) for shard in shards
            ),
            "peak_cuda_allocated_bytes_max": max(
                int(shard["cost"]["peak_cuda_allocated_bytes"])
                for shard in shards
            ),
            "total_input_tokens": sum(
                int(shard["cost"]["total_input_tokens"]) for shard in shards
            ),
            "total_vision_grid_tokens": sum(
                int(shard["cost"]["total_vision_grid_tokens"])
                for shard in shards
            ),
            "compute_matched_to_fprr": False,
        },
        "development_case_study_only": True,
        "confirmation_outcomes_read": False,
        "gold_outcomes_read": False,
        "external_outcomes_read": False,
        "scientific_claim_allowed": False,
    }
    write_json(output, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Aggregate raw two-image B3")
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    result = aggregate(args.config)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
