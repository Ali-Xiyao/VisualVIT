from __future__ import annotations

import json
from pathlib import Path

from scripts.aggregate_prta_gen_r49_three_way import aggregate
from scripts.run_prta_gen_r49_exact64 import _prompt_config, stable_epoch_key
from scripts.run_prta_gen_r49_raw_two_image import select_shard


WORKSPACE = Path(__file__).resolve().parents[1]
CONFIG = WORKSPACE / "configs/prta_gen/prta_gen_r49_unified_three_way_v1.json"


def _config() -> dict:
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def test_r49_three_way_contract_is_matched_and_explicit() -> None:
    config = _config()
    authority = config["authority"]
    naive = config["naive_exact64"]
    assert authority["training_rows"] == 2500
    assert authority["evaluation_partitions"] == ["qualification", "confirmation"]
    assert authority["evaluation_rows"] == 750
    assert config["evaluation"]["arms"] == [
        "raw_two_image_qwen",
        "naive_exact64",
        "prta_exact64",
    ]
    assert naive["patch_positions"] == [
        1 + round(index * 195 / 29) for index in range(30)
    ]
    assert naive["layout"] == "prior_30_then_current_30_then_zero_4"
    assert naive["token_shape"] == [64, 768]
    assert config["training"]["expected_optimizer_updates"] == 79
    assert config["model"]["qwen_frozen"] is True


def test_r49_prompt_parity_is_semantic_not_serialization_claim() -> None:
    config = _config()
    prompt = config["prompt"]
    exact = _prompt_config(config)["prompt"]["user_prefix"]
    raw = prompt["raw_modality_prefix"] + prompt["shared_task"]
    assert prompt["shared_task"] in exact
    assert prompt["shared_task"] in raw
    assert prompt["semantic_task_and_output_contract_identical"] is True
    assert prompt["serialized_multimodal_prompts_identical"] is False


def test_r49_training_order_does_not_depend_on_exact64_arm() -> None:
    namespace = _config()["training"]["shared_epoch_order_namespace"]
    keys = [stable_epoch_key(namespace, 17, 0, value) for value in ("a", "b", "c")]
    assert keys == [stable_epoch_key(namespace, 17, 0, value) for value in ("a", "b", "c")]
    assert len(set(keys)) == 3


def test_r49_raw_modulo_shards_cover_each_row_once() -> None:
    rows = [{"example_id": str(index)} for index in range(11)]
    left = select_shard(rows, 0, 2)
    right = select_shard(rows, 1, 2)
    combined = sorted(left + right, key=lambda item: item[0])
    assert [index for index, _ in combined] == list(range(11))


def test_r49_aggregate_enforces_and_records_three_way_parity(tmp_path: Path) -> None:
    config = _config()
    config["authority"]["evaluation_rows"] = 4
    config["execution"]["raw_shard_count"] = 2
    config["evaluation"]["paired_patient_bootstrap_replicates"] = 20
    config["runtime"]["exact64_root"] = str(tmp_path / "exact64")
    config["runtime"]["raw_root"] = str(tmp_path / "raw")
    config["runtime"]["aggregate"] = str(tmp_path / "aggregate.json")
    shared = config["prompt"]["shared_task"]
    example_ids = [f"e{index}" for index in range(4)]
    patient_ids = [f"p{index}" for index in range(4)]
    targets = [0, 1, 2, 3]
    common = {
        "status": config["result_statuses"]["exact64_arm_complete"],
        "protocol_id": config["protocol_id"],
        "seed": 17,
        "qwen_trainable_parameters": 0,
        "exact64_tokens_used": True,
        "pixel_inputs_used": False,
        "shared_task": shared,
        "projector_initialization_sha256": "same-init",
        "training_example_ids_sha256": "same-order",
        "projector_trainable_parameters": 10,
        "evaluation_patient_ids": patient_ids,
        "evaluation_example_ids": example_ids,
        "targets": targets,
        "elapsed_seconds": 1.0,
    }
    arm_predictions = {
        "naive_exact64": [0, 0, 2, 3],
        "prta_exact64": [0, 1, 2, 3],
    }
    for arm, predictions in arm_predictions.items():
        path = tmp_path / "exact64" / "seed_17" / arm
        path.mkdir(parents=True)
        (path / "result.json").write_text(
            json.dumps(
                {
                    **common,
                    "arm": arm,
                    "predictions": predictions,
                    "metrics": {"macro_f1": 1.0 if arm.startswith("prta") else 0.7},
                }
            ),
            encoding="utf-8",
        )
    raw_predictions = [0, 0, 0, 3]
    for shard_index in range(2):
        path = tmp_path / "raw" / f"shard_{shard_index}_of_2"
        path.mkdir(parents=True)
        rows = [
            {
                "row_index": index,
                "example_id": example_ids[index],
                "target": targets[index],
                "prediction": raw_predictions[index],
                "schema_valid": True,
                "finding_correct": True,
            }
            for index in range(4)
            if index % 2 == shard_index
        ]
        (path / "result.json").write_text(
            json.dumps(
                {
                    "status": config["result_statuses"]["raw_shard_complete"],
                    "protocol_id": config["protocol_id"],
                    "shard_index": shard_index,
                    "shard_count": 2,
                    "model_trainable_parameters": 0,
                    "pixel_inputs_used": True,
                    "shared_task": shared,
                    "rows": rows,
                    "cost": {
                        "generation_seconds": 1.0,
                        "peak_cuda_allocated_bytes": 1,
                        "total_input_tokens": 1,
                        "total_vision_grid_tokens": 1,
                    },
                }
            ),
            encoding="utf-8",
        )
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    result = aggregate(config_path)
    assert result["same_patients"] is True
    assert result["exact64_same_projector_initialization"] is True
    assert (
        result["comparisons"]["prta_exact64_minus_naive_exact64"]["effect_pp"]
        > 0.0
    )
    assert isinstance(
        result["answers"]["prta_better_than_naive_exact64_supported"], bool
    )
