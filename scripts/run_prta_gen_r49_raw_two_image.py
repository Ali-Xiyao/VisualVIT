from __future__ import annotations

# ruff: noqa: E402

import argparse
import json
import os
from pathlib import Path
import sys
import time
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE))
sys.path.insert(0, str(WORKSPACE / "src"))

import torch

from scripts.audit_prta_gen_r44_independent_support import sha256_file
from scripts.build_prta_gen_r40b_smoke_cohort import read_json, write_json
from scripts.run_prta_gen_r40b_overfit_smoke import parse_generated_object
from scripts.run_prta_gen_r41a_progression_sft import PROGRESSION_CLASSES
from scripts.run_prta_gen_r48_b3_raw_two_image import _metrics, select_shard


CONFIG_STATUS = "FROZEN_PRTA_GEN_R49_UNIFIED_THREE_WAY"


def _verify(path: Path, expected_bytes: int, expected_sha256: str) -> None:
    if (
        not path.is_file()
        or path.stat().st_size != expected_bytes
        or sha256_file(path) != expected_sha256
    ):
        raise PermissionError(f"R49 authority drift: {path}")


def validate_authority(config_path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    config = read_json(config_path)
    if config.get("status") != CONFIG_STATUS:
        raise PermissionError("R49 raw config is not frozen")
    authority = config["authority"]
    for prefix in ("r40_component_config", "r45_training_config"):
        _verify(
            WORKSPACE / authority[prefix],
            int(authority[f"{prefix}_bytes"]),
            str(authority[f"{prefix}_sha256"]),
        )
    roster_path = Path(authority["roster"])
    _verify(
        roster_path,
        int(authority["roster_bytes"]),
        str(authority["roster_sha256"]),
    )
    roster = read_json(roster_path)
    if (
        roster.get("status") != authority["roster_status"]
        or roster.get("one_row_per_patient") is not True
        or roster.get("patient_sets_disjoint") is not True
    ):
        raise PermissionError("R49 raw roster contract drift")
    rows = [
        row
        for partition in authority["evaluation_partitions"]
        for row in roster["partitions"][partition]["rows"]
    ]
    if (
        len(rows) != int(authority["evaluation_rows"])
        or len({str(row["patient_id"]) for row in rows}) != len(rows)
    ):
        raise PermissionError("R49 raw evaluation cohort drift")
    for row in rows:
        for key in ("prior_path", "current_path"):
            path = Path(row[key])
            if not path.is_file() or path.suffix.lower() != ".jpg":
                raise FileNotFoundError(path)
    model = config["model"]
    model_path = Path(model["path"])
    for name, bytes_key, hash_key in (
        ("config.json", "config_bytes", "config_sha256"),
        ("preprocessor_config.json", "preprocessor_config_bytes", "preprocessor_config_sha256"),
        ("model.safetensors.index.json", "weight_index_bytes", "weight_index_sha256"),
    ):
        _verify(model_path / name, int(model[bytes_key]), str(model[hash_key]))
    weight_index = read_json(model_path / "model.safetensors.index.json")
    for shard_name in set(weight_index["weight_map"].values()):
        if not (model_path / shard_name).is_file():
            raise FileNotFoundError(model_path / shard_name)
    return config, rows


def preflight(config_path: Path) -> dict[str, Any]:
    config, rows = validate_authority(config_path)
    shard_count = int(config["execution"]["raw_shard_count"])
    counts = [len(select_shard(rows, index, shard_count)) for index in range(shard_count)]
    root = Path(config["runtime"]["raw_root"])
    if root.exists():
        raise FileExistsError("R49 raw root must be fresh")
    shared = str(config["prompt"]["shared_task"])
    if "{finding}" not in shared:
        raise PermissionError("R49 shared task template drift")
    return {
        "schema": "visualvit.prta-gen.r49-raw-preflight.v1",
        "status": config["result_statuses"]["raw_preflight_pass"],
        "protocol_id": config["protocol_id"],
        "rows": len(rows),
        "shard_counts": counts,
        "all_images_present": True,
        "model_shards_present": True,
        "shared_task_contract_present": True,
        "raw_root_fresh": True,
        "gpu_inference_started": False,
    }


def run_shard(
    config_path: Path,
    device_name: str,
    shard_index: int,
    shard_count: int,
) -> dict[str, Any]:
    config, rows = validate_authority(config_path)
    selected = select_shard(rows, shard_index, shard_count)
    if len({str(row["progression"]) for _, row in selected}) != len(PROGRESSION_CLASSES):
        raise PermissionError("R49 raw shard lacks complete class support")
    output = Path(config["runtime"]["raw_root"]) / f"shard_{shard_index}_of_{shard_count}"
    if output.exists():
        raise FileExistsError(output)
    output.mkdir(parents=True, exist_ok=False)
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    device = torch.device(device_name)
    if device.type != "cuda" or not torch.cuda.is_available():
        raise RuntimeError("R49 raw requires explicit CUDA")
    torch.cuda.set_device(device)
    torch.empty(1, device=device)
    torch.cuda.reset_peak_memory_stats(device)
    from qwen_vl_utils import process_vision_info
    from transformers import AutoProcessor, Qwen3VLForConditionalGeneration

    model_config = config["model"]
    processor = AutoProcessor.from_pretrained(
        model_config["path"],
        local_files_only=True,
        min_pixels=int(model_config["min_pixels"]),
        max_pixels=int(model_config["max_pixels"]),
    )
    load_start = time.perf_counter()
    model = Qwen3VLForConditionalGeneration.from_pretrained(
        model_config["path"],
        local_files_only=True,
        trust_remote_code=False,
        dtype=torch.bfloat16,
        attn_implementation=model_config["attention_implementation"],
        low_cpu_mem_usage=True,
    ).to(device)
    model.requires_grad_(False)
    model.eval()
    model.config.use_cache = True
    torch.cuda.synchronize(device)
    load_seconds = time.perf_counter() - load_start
    if any(parameter.requires_grad for parameter in model.parameters()):
        raise PermissionError("R49 raw Qwen is not frozen")
    expected_keys = list(config["target"]["schema_keys_in_order"])
    progression_values = set(config["target"]["progression_values"])
    class_to_index = {label: index for index, label in enumerate(PROGRESSION_CLASSES)}
    records: list[dict[str, Any]] = []
    generation_seconds = 0.0
    total_input_tokens = 0
    total_vision_grid_tokens = 0
    user_template = str(config["prompt"]["raw_modality_prefix"]) + str(
        config["prompt"]["shared_task"]
    )
    for row_index, row in selected:
        messages = [
            {"role": "system", "content": config["prompt"]["system"]},
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": str(row["prior_path"])},
                    {"type": "image", "image": str(row["current_path"])},
                    {"type": "text", "text": user_template.format(finding=str(row["finding"]))},
                ],
            },
        ]
        prompt = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        image_inputs, video_inputs = process_vision_info(messages)
        inputs = processor(
            text=[prompt],
            images=image_inputs,
            videos=video_inputs,
            padding=True,
            return_tensors="pt",
        ).to(device)
        total_input_tokens += int(inputs["input_ids"].shape[-1])
        grid = inputs.get("image_grid_thw")
        if grid is None or int(grid.shape[0]) != 2:
            raise PermissionError("R49 raw image-grid count drift")
        total_vision_grid_tokens += int(grid.prod(dim=1).sum().item())
        started = time.perf_counter()
        with torch.inference_mode():
            generated = model.generate(
                **inputs,
                max_new_tokens=int(config["target"]["max_target_tokens"]),
                do_sample=bool(model_config["do_sample"]),
                use_cache=True,
                pad_token_id=processor.tokenizer.pad_token_id,
                eos_token_id=processor.tokenizer.eos_token_id,
            )
        torch.cuda.synchronize(device)
        generation_seconds += time.perf_counter() - started
        trimmed = generated[:, inputs["input_ids"].shape[-1] :]
        text = processor.batch_decode(
            trimmed,
            skip_special_tokens=True,
            clean_up_tokenization_spaces=False,
        )[0].strip()
        parsed = parse_generated_object(
            text, expected_keys=expected_keys, progression_values=progression_values
        )
        finding_correct = parsed is not None and parsed["finding"] == str(row["finding"])
        prediction = class_to_index[parsed["progression"]] if finding_correct else -1
        records.append(
            {
                "row_index": row_index,
                "example_id": str(row["example_id"]),
                "target": class_to_index[str(row["progression"])],
                "prediction": prediction,
                "schema_valid": parsed is not None,
                "finding_correct": finding_correct,
                "generated_text": text,
            }
        )
    targets = [int(record["target"]) for record in records]
    predictions = [int(record["prediction"]) for record in records]
    metrics = _metrics(targets, predictions)
    metrics["schema_validity"] = sum(bool(record["schema_valid"]) for record in records) / len(records)
    metrics["finding_echo_accuracy"] = sum(bool(record["finding_correct"]) for record in records) / len(records)
    result = {
        "schema": "visualvit.prta-gen.r49-raw-shard.v1",
        "status": config["result_statuses"]["raw_shard_complete"],
        "protocol_id": config["protocol_id"],
        "shard_index": shard_index,
        "shard_count": shard_count,
        "device": device_name,
        "device_name": torch.cuda.get_device_name(device),
        "model_trainable_parameters": 0,
        "image_order": ["prior", "current"],
        "complete_images_used": True,
        "pixel_inputs_used": True,
        "shared_task": config["prompt"]["shared_task"],
        "rows": records,
        "metrics": metrics,
        "cost": {
            "load_seconds": load_seconds,
            "generation_seconds": generation_seconds,
            "peak_cuda_allocated_bytes": int(torch.cuda.max_memory_allocated(device)),
            "total_input_tokens": total_input_tokens,
            "total_vision_grid_tokens": total_vision_grid_tokens,
        },
        "gold_outcomes_read": False,
        "external_outcomes_read": False,
        "clinical_claim_allowed": False,
    }
    write_json(output / "result.json", result)
    return result


def receipt_summary(result: dict[str, Any]) -> dict[str, Any]:
    summary = dict(result)
    if isinstance(summary.get("rows"), list):
        summary["rows"] = {
            "count": len(result["rows"]),
            "valid": sum(bool(row["schema_valid"]) for row in result["rows"]),
        }
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Run R49 raw two-image Qwen")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--device")
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--shard-count", type=int, default=2)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    if args.preflight_only:
        result = preflight(args.config)
    else:
        if args.device is None:
            raise ValueError("R49 raw run requires --device")
        result = run_shard(
            args.config, str(args.device), args.shard_index, args.shard_count
        )
    print(json.dumps(receipt_summary(result), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
