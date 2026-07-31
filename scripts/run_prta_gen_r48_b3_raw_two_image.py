from __future__ import annotations

# ruff: noqa: E402

import argparse
import json
import os
from pathlib import Path
import sys
import time
from typing import Any

import torch

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE))
sys.path.insert(0, str(WORKSPACE / "src"))

from scripts.audit_prta_gen_r44_independent_support import sha256_file
from scripts.build_prta_gen_r40b_smoke_cohort import read_json, write_json
from scripts.run_prta_gen_r40b_overfit_smoke import parse_generated_object
from scripts.run_prta_gen_r41a_progression_sft import (
    PROGRESSION_CLASSES,
    macro_f1,
)


CONFIG_STATUS = "FROZEN_PRTA_GEN_R48_B3_RAW_TWO_IMAGE_QUALIFICATION"


def select_shard(
    rows: list[dict[str, Any]], shard_index: int, shard_count: int
) -> list[tuple[int, dict[str, Any]]]:
    if shard_count < 1 or not 0 <= shard_index < shard_count:
        raise ValueError("invalid shard index/count")
    return [
        (index, row)
        for index, row in enumerate(rows)
        if index % shard_count == shard_index
    ]


def _verify_file(
    path: Path, *, expected_bytes: int, expected_sha256: str
) -> None:
    if (
        not path.is_file()
        or path.stat().st_size != expected_bytes
        or sha256_file(path) != expected_sha256
    ):
        raise PermissionError(f"authority drift: {path.name}")


def validate_authority(config_path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    config = read_json(config_path)
    if config.get("status") != CONFIG_STATUS:
        raise PermissionError("raw two-image config is not frozen")
    authority = config["authority"]
    for prefix in (
        "r40_b3_config",
        "roster",
        "fprr_baseline_result",
        "fprr_aggregate",
    ):
        _verify_file(
            Path(authority[prefix]),
            expected_bytes=int(authority[f"{prefix}_bytes"]),
            expected_sha256=str(authority[f"{prefix}_sha256"]),
        )
    roster = read_json(Path(authority["roster"]))
    fprr = read_json(Path(authority["fprr_aggregate"]))
    if (
        roster.get("status") != authority["roster_status"]
        or fprr.get("status") != authority["fprr_aggregate_status"]
        or fprr.get("gate_passed") is not True
    ):
        raise PermissionError("raw two-image upstream status drift")
    rows = list(roster["partitions"][authority["partition"]]["rows"])
    if (
        len(rows) != int(authority["expected_rows"])
        or len({str(row["patient_id"]) for row in rows}) != len(rows)
    ):
        raise PermissionError("raw two-image cohort drift")
    for row in rows:
        for key in ("prior_path", "current_path"):
            path = Path(row[key])
            if not path.is_file() or path.suffix.lower() != ".jpg":
                raise FileNotFoundError(path)
    model = config["model"]
    model_path = Path(model["path"])
    for name, bytes_key, hash_key in (
        ("config.json", "config_bytes", "config_sha256"),
        (
            "preprocessor_config.json",
            "preprocessor_config_bytes",
            "preprocessor_config_sha256",
        ),
        (
            "model.safetensors.index.json",
            "weight_index_bytes",
            "weight_index_sha256",
        ),
    ):
        _verify_file(
            model_path / name,
            expected_bytes=int(model[bytes_key]),
            expected_sha256=str(model[hash_key]),
        )
    weight_index = read_json(model_path / "model.safetensors.index.json")
    for shard_name in set(weight_index["weight_map"].values()):
        if not (model_path / shard_name).is_file():
            raise FileNotFoundError(model_path / shard_name)
    return config, rows


def preflight(config_path: Path) -> dict[str, Any]:
    config, rows = validate_authority(config_path)
    shard_count = int(config["execution"]["formal_shard_count"])
    counts = [
        len(select_shard(rows, index, shard_count))
        for index in range(shard_count)
    ]
    roots = (
        Path(config["runtime"]["smoke_root"]),
        Path(config["runtime"]["formal_root"]),
    )
    if any(root.exists() for root in roots):
        raise FileExistsError("raw two-image runtime roots must be fresh")
    return {
        "schema": "visualvit.prta-gen.r48-b3-raw-two-image-preflight.v1",
        "status": config["result_statuses"]["preflight_pass"],
        "protocol_id": config["protocol_id"],
        "rows": len(rows),
        "shard_counts": counts,
        "all_images_present": True,
        "model_shards_present": True,
        "runtime_roots_fresh": True,
        "training_started": False,
        "confirmation_outcomes_read": False,
    }


def _metrics(targets: list[int], predictions: list[int]) -> dict[str, Any]:
    recalls: list[float | None] = []
    supports: list[int] = []
    for class_index in range(len(PROGRESSION_CLASSES)):
        support = sum(target == class_index for target in targets)
        supports.append(support)
        recalls.append(
            (
                sum(
                    target == class_index and prediction == class_index
                    for target, prediction in zip(
                        targets, predictions, strict=True
                    )
                )
                / support
            )
            if support
            else None
        )
    count = len(targets)
    return {
        "row_count": count,
        "progression_accuracy": sum(
            target == prediction
            for target, prediction in zip(targets, predictions, strict=True)
        )
        / count,
        "macro_f1": macro_f1(
            targets, predictions, class_count=len(PROGRESSION_CLASSES)
        ),
        "per_class_recall": {
            label: recalls[index]
            for index, label in enumerate(PROGRESSION_CLASSES)
        },
        "per_class_support": {
            label: supports[index]
            for index, label in enumerate(PROGRESSION_CLASSES)
        },
        "invalid_or_wrong_finding_predictions": sum(
            prediction < 0 for prediction in predictions
        ),
    }


def run_shard(
    *,
    config_path: Path,
    device_name: str,
    shard_index: int,
    shard_count: int,
    smoke: bool,
) -> dict[str, Any]:
    config, rows = validate_authority(config_path)
    selected = select_shard(rows, shard_index, shard_count)
    if smoke:
        selected = selected[: int(config["execution"]["smoke_rows_per_shard"])]
    elif len(
        {str(row["progression"]) for _, row in selected}
    ) != len(PROGRESSION_CLASSES):
        raise PermissionError("formal raw shard lacks complete class support")
    root_key = "smoke_root" if smoke else "formal_root"
    output_dir = (
        Path(config["runtime"][root_key])
        / f"shard_{shard_index}_of_{shard_count}"
    )
    if output_dir.exists():
        raise FileExistsError(output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    device = torch.device(device_name)
    if device.type != "cuda" or not torch.cuda.is_available():
        raise RuntimeError("raw two-image baseline requires explicit CUDA")
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
        raise PermissionError("raw two-image Qwen is not frozen")

    expected_keys = list(config["target"]["schema_keys_in_order"])
    progression_values = set(config["target"]["progression_values"])
    class_to_index = {
        label: index for index, label in enumerate(PROGRESSION_CLASSES)
    }
    records: list[dict[str, Any]] = []
    generation_seconds = 0.0
    total_input_tokens = 0
    total_vision_grid_tokens = 0
    for row_index, row in selected:
        messages = [
            {
                "role": "system",
                "content": config["prompt"]["system"],
            },
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": str(row["prior_path"])},
                    {"type": "image", "image": str(row["current_path"])},
                    {
                        "type": "text",
                        "text": config["prompt"]["user_text"].format(
                            finding=str(row["finding"])
                        ),
                    },
                ],
            },
        ]
        prompt = processor.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
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
            raise PermissionError("raw two-image grid-count drift")
        total_vision_grid_tokens += int(grid.prod(dim=1).sum().item())
        start = time.perf_counter()
        with torch.inference_mode():
            generated = model.generate(
                **inputs,
                max_new_tokens=int(config["target"]["max_new_tokens"]),
                do_sample=bool(model_config["do_sample"]),
                use_cache=True,
                pad_token_id=processor.tokenizer.pad_token_id,
                eos_token_id=processor.tokenizer.eos_token_id,
            )
        torch.cuda.synchronize(device)
        generation_seconds += time.perf_counter() - start
        trimmed = generated[:, inputs["input_ids"].shape[-1] :]
        text = processor.batch_decode(
            trimmed,
            skip_special_tokens=True,
            clean_up_tokenization_spaces=False,
        )[0].strip()
        parsed = parse_generated_object(
            text,
            expected_keys=expected_keys,
            progression_values=progression_values,
        )
        finding_correct = (
            parsed is not None and parsed["finding"] == str(row["finding"])
        )
        prediction = (
            class_to_index[parsed["progression"]]
            if finding_correct
            else -1
        )
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
    count = len(records)
    metrics["schema_validity"] = sum(
        bool(record["schema_valid"]) for record in records
    ) / count
    metrics["finding_echo_accuracy"] = sum(
        bool(record["finding_correct"]) for record in records
    ) / count
    result = {
        "schema": "visualvit.prta-gen.r48-b3-raw-two-image-shard.v1",
        "status": config["result_statuses"][
            "smoke_complete" if smoke else "formal_shard_complete"
        ],
        "protocol_id": config["protocol_id"],
        "mode": "smoke" if smoke else "formal",
        "shard_index": shard_index,
        "shard_count": shard_count,
        "device": device_name,
        "device_name": torch.cuda.get_device_name(device),
        "model_trainable_parameters": 0,
        "image_order": ["prior", "current"],
        "complete_images_used": True,
        "pixel_inputs_used": True,
        "rows": records,
        "metrics": metrics,
        "cost": {
            "load_seconds": load_seconds,
            "generation_seconds": generation_seconds,
            "peak_cuda_allocated_bytes": int(
                torch.cuda.max_memory_allocated(device)
            ),
            "total_input_tokens": total_input_tokens,
            "total_vision_grid_tokens": total_vision_grid_tokens,
        },
        "confirmation_outcomes_read": False,
        "gold_outcomes_read": False,
        "external_outcomes_read": False,
        "scientific_claim_allowed": False,
    }
    write_json(output_dir / "result.json", result)
    return result


def receipt_summary(result: dict[str, Any]) -> dict[str, Any]:
    summary = dict(result)
    if isinstance(summary.get("rows"), list):
        summary["rows"] = {
            "count": len(result["rows"]),
            "valid": sum(
                bool(row["schema_valid"]) for row in result["rows"]
            ),
        }
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Run raw two-image Qwen3-VL")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--device")
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--shard-count", type=int, default=2)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    result = (
        preflight(args.config)
        if args.preflight_only
        else run_shard(
            config_path=args.config,
            device_name=str(args.device),
            shard_index=args.shard_index,
            shard_count=args.shard_count,
            smoke=args.smoke,
        )
    )
    print(json.dumps(receipt_summary(result), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
