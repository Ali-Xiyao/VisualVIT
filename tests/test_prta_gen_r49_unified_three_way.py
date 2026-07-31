from __future__ import annotations

import json
from pathlib import Path

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
