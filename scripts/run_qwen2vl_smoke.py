from __future__ import annotations

# ruff: noqa: E402

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import torch
from transformers import AutoProcessor, Qwen2VLForConditionalGeneration
from qwen_vl_utils import process_vision_info

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE / "src"))

from visualvit.constrained_output import parse_progression_output

EVIDENCE_CLASS = "NON_CONFIRMATORY_PROXY"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_shards(model_path: Path) -> dict[str, Any]:
    index_path = model_path / "model.safetensors.index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    shard_names = sorted(set(index["weight_map"].values()))
    shards = []
    for name in shard_names:
        path = model_path / name
        if not path.is_file():
            raise FileNotFoundError(path)
        shards.append({"name": name, "bytes": path.stat().st_size})
    return {
        "index_path": str(index_path),
        "index_sha256": sha256_file(index_path),
        "metadata_total_size": int(index.get("metadata", {}).get("total_size", 0)),
        "shards": shards,
        "all_shards_present": True,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--model-path",
        type=Path,
        default=Path(r"H:\Xiyao_Wang\001_models\Qwen2-VL-7B-Instruct"),
    )
    parser.add_argument(
        "--images",
        type=Path,
        nargs=2,
        default=[
            Path(
                r"H:\Xiyao_Wang\000_Public Dataset\CheXpert-v1.0-small\train"
                r"\patient00002\study1\view1_frontal.jpg"
            ),
            Path(
                r"H:\Xiyao_Wang\000_Public Dataset\CheXpert-v1.0-small\train"
                r"\patient00002\study2\view1_frontal.jpg"
            ),
        ],
    )
    parser.add_argument("--device", default="cuda:1")
    parser.add_argument("--max-new-tokens", type=int, default=16)
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path(r"F:\VisualVIT_runtime\050_routeC\runs"),
    )
    parser.add_argument("--run-id", default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    if not args.model_path.is_dir():
        raise FileNotFoundError(args.model_path)
    for image_path in args.images:
        if not image_path.is_file():
            raise FileNotFoundError(image_path)
    if not torch.cuda.is_available():
        raise RuntimeError("Qwen2-VL smoke requires CUDA")

    device = torch.device(args.device)
    torch.cuda.set_device(device)
    # Windows/PyTorch may reject reset_peak_memory_stats before the selected
    # device has created its first CUDA context.
    torch.empty(1, device=device)
    run_id = args.run_id or (
        f"qwen2vl_{args.model_path.name}_" + datetime.now().strftime("%Y%m%dT%H%M%S")
    )
    run_dir = args.output_root / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    shard_report = verify_shards(args.model_path)

    processor = AutoProcessor.from_pretrained(
        args.model_path,
        local_files_only=True,
        min_pixels=256 * 28 * 28,
        max_pixels=512 * 28 * 28,
    )
    messages = [
        {
            "role": "system",
            "content": (
                "You are running a constrained interface test. Return exactly one "
                "line and no explanation. The line must be one of: ANSWER: new, "
                "ANSWER: resolved, ANSWER: worse, ANSWER: improved, ANSWER: stable."
            ),
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "image": str(args.images[0]),
                },
                {
                    "type": "image",
                    "image": str(args.images[1]),
                },
                {
                    "type": "text",
                    "text": (
                        "Image 1 is prior and Image 2 is current. Choose the single "
                        "best progression label. Output exactly: ANSWER: <label>"
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
    )
    input_shapes = {
        key: list(value.shape)
        for key, value in inputs.items()
        if isinstance(value, torch.Tensor)
    }

    torch.cuda.reset_peak_memory_stats(device)
    load_start = time.perf_counter()
    model = Qwen2VLForConditionalGeneration.from_pretrained(
        args.model_path,
        local_files_only=True,
        dtype=torch.bfloat16,
        device_map={"": str(device)},
        attn_implementation="sdpa",
    )
    model.eval()
    torch.cuda.synchronize(device)
    load_seconds = time.perf_counter() - load_start

    inputs = inputs.to(device)
    generation_start = time.perf_counter()
    with torch.inference_mode():
        generated = model.generate(
            **inputs,
            max_new_tokens=args.max_new_tokens,
            do_sample=False,
            use_cache=True,
        )
    torch.cuda.synchronize(device)
    generation_seconds = time.perf_counter() - generation_start

    trimmed = [
        output[len(input_ids) :]
        for input_ids, output in zip(inputs.input_ids, generated)
    ]
    raw_output = processor.batch_decode(
        trimmed,
        skip_special_tokens=True,
        clean_up_tokenization_spaces=False,
    )[0].strip()
    try:
        parsed_output = parse_progression_output(raw_output)
        adapter_schema_pass = True
        canonical_output = parsed_output.canonical
        literal_prefix_compliance = parsed_output.literal_prefix_compliance
    except ValueError:
        adapter_schema_pass = False
        canonical_output = None
        literal_prefix_compliance = False
    peak_vram = int(torch.cuda.max_memory_allocated(device))
    checks = {
        "offline_shards_complete": shard_report["all_shards_present"],
        "two_image_grids": input_shapes.get("image_grid_thw", [0])[0] == 2,
        "strict_adapter_schema": adapter_schema_pass,
        "canonical_output_schema": (
            canonical_output is not None and canonical_output.startswith("ANSWER: ")
        ),
        "h_drive_output_forbidden": not str(run_dir).lower().startswith("h:"),
    }
    summary = {
        "evidence_class": EVIDENCE_CLASS,
        "formal_claim_allowed": False,
        "run_id": run_id,
        "status": "PASS" if all(checks.values()) else "FAIL",
        "model_path": str(args.model_path),
        "model_shards": shard_report,
        "images": [
            {
                "path": str(path),
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
            }
            for path in args.images
        ],
        "requested_prompt_contract": "^ANSWER: (new|resolved|worse|improved|stable)$",
        "frozen_adapter_contract": (
            "^(?:ANSWER:\\s*)?(new|resolved|worse|improved|stable)$"
        ),
        "raw_output": raw_output,
        "canonical_output": canonical_output,
        "literal_prefix_compliance": literal_prefix_compliance,
        "adapter_note": (
            "The non-confirmatory pilot showed local 2B and 7B emit an exact "
            "allowed bare label. The adapter accepts only a bare allowed label "
            "or the requested literal prefix, canonicalizes it, and raises on "
            "all other text; there is no default-class fallback."
        ),
        "input_shapes": input_shapes,
        "load_seconds": load_seconds,
        "generation_seconds": generation_seconds,
        "peak_vram_bytes": peak_vram,
        "device": str(device),
        "device_name": torch.cuda.get_device_name(device),
        "checks": checks,
    }
    summary_path = run_dir / "summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps(summary, sort_keys=True))
    print(f"RESULT_DIR={run_dir}")
    return 0 if summary["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
