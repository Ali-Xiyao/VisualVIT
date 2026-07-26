from __future__ import annotations

# ruff: noqa: E402

import argparse
import hashlib
import json
import os
import platform
import sys
import time
from pathlib import Path
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE / "src"))
os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")

import torch

from visualvit.hierarchical_temporal_tokens import (
    TOKEN_LAYOUT,
    fixed_token_types,
)
from visualvit.qwen_adapter import PROGRESSION_LABELS
from visualvit.schemas import TokenBundle
from visualvit.tier_cxr_vlm import TierCXRAdapter
from visualvit.tier_token_projector import TierTokenProjector


SENTINEL_TOKEN = "<|fim_pad|>"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Offline exact-64 no-pixel Qwen3-VL relation-token smoke"
    )
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--seed", default=2401, type=int)
    parser.add_argument("--input-dim", default=16, type=int)
    parser.add_argument(
        "--dtype", choices=("bfloat16", "float32"), default="bfloat16"
    )
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_prompt(tokenizer: Any, placeholder_token_id: int) -> torch.Tensor:
    prefix = tokenizer(
        "Classify longitudinal chest-radiograph entity progression. "
        "The next 64 physical positions are relation tokens.\n",
        add_special_tokens=True,
    )["input_ids"]
    suffix = tokenizer(
        "\nReturn exactly one label from: stable, worse, improved, new, resolved.\n"
        "Answer:",
        add_special_tokens=False,
    )["input_ids"]
    token_ids = [*prefix, *([placeholder_token_id] * 64), *suffix]
    prompt = torch.tensor([token_ids], dtype=torch.long)
    if int(prompt.eq(placeholder_token_id).sum().item()) != 64:
        raise RuntimeError(
            "prompt construction did not produce exactly 64 placeholders"
        )
    return prompt


def build_token_bundle(
    seed: int,
    input_dim: int,
    device: torch.device,
    dtype: torch.dtype,
) -> TokenBundle:
    generator = torch.Generator(device="cpu").manual_seed(seed)
    tokens = torch.randn(1, 64, input_dim, generator=generator).to(
        device=device, dtype=dtype
    )
    token_types = fixed_token_types(device)
    valid_mask = torch.ones(1, 64, dtype=torch.bool, device=device)
    valid_mask[:, -TOKEN_LAYOUT[-1] :] = False
    anatomy_ids = torch.full((1, 64), -1, dtype=torch.long, device=device)
    anatomy_ids[:, 4:60] = torch.arange(56, device=device).remainder(28)
    temporal_ids = torch.full((1, 64), -1, dtype=torch.long, device=device)
    temporal_ids[:, 32:60] = 1
    confidence = torch.ones(1, 64, dtype=dtype, device=device)
    slot_mass = torch.ones(1, 64, dtype=dtype, device=device)
    source_ids = torch.arange(64, dtype=torch.long, device=device).view(1, -1)
    return TokenBundle(
        tokens=tokens,
        token_types=token_types,
        valid_mask=valid_mask,
        assignment=torch.zeros(1, 1, 1, device=device),
        anatomy_ids=anatomy_ids,
        temporal_ids=temporal_ids,
        confidence=confidence,
        slot_mass=slot_mass,
        source_ids=source_ids,
    )


def json_safe(value: Any) -> Any:
    if isinstance(value, torch.Tensor):
        return value.detach().cpu().tolist()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    return value


def main() -> int:
    args = parse_args()
    started = time.time()
    result: dict[str, Any] = {
        "status": "FAIL",
        "seed": args.seed,
        "model_path": str(args.model.resolve()),
        "token_layout": TOKEN_LAYOUT,
        "token_budget": 64,
        "sentinel_token": SENTINEL_TOKEN,
        "pixel_inputs_used": False,
        "hostname": platform.node(),
        "pid": os.getpid(),
        "torch_version": torch.__version__,
        "dtype": args.dtype,
    }
    try:
        if not args.model.is_dir():
            raise FileNotFoundError(f"model directory not found: {args.model}")
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA is required for the Qwen3-VL survival smoke")

        import transformers
        from transformers import AutoTokenizer, Qwen3VLForConditionalGeneration

        result["transformers_version"] = transformers.__version__
        torch.manual_seed(args.seed)
        torch.cuda.manual_seed_all(args.seed)
        torch.use_deterministic_algorithms(True, warn_only=True)
        torch.backends.cuda.matmul.allow_tf32 = False
        device = torch.device("cuda:0")
        torch.cuda.set_device(device)
        torch.cuda.reset_peak_memory_stats(device)

        tokenizer = AutoTokenizer.from_pretrained(
            args.model,
            local_files_only=True,
            trust_remote_code=False,
        )
        placeholder_token_id = int(tokenizer.convert_tokens_to_ids(SENTINEL_TOKEN))
        sentinel_encoding = tokenizer(SENTINEL_TOKEN, add_special_tokens=False)[
            "input_ids"
        ]
        if sentinel_encoding != [placeholder_token_id]:
            raise RuntimeError(
                f"sentinel must encode to one token; got {sentinel_encoding}"
            )
        forbidden_ids = {
            int(value)
            for value in (
                tokenizer.pad_token_id,
                tokenizer.eos_token_id,
                getattr(tokenizer, "bos_token_id", None),
                getattr(tokenizer, "unk_token_id", None),
            )
            if value is not None
        }
        if placeholder_token_id in forbidden_ids:
            raise RuntimeError("sentinel collides with pad/eos/bos/unk token")

        model_dtype = getattr(torch, args.dtype)
        model = Qwen3VLForConditionalGeneration.from_pretrained(
            args.model,
            dtype=model_dtype,
            attn_implementation="eager",
            local_files_only=True,
            trust_remote_code=False,
            low_cpu_mem_usage=True,
        ).to(device)
        model.eval().requires_grad_(False)
        hidden_size = int(model.config.text_config.hidden_size)
        image_token_id = int(model.config.image_token_id)
        video_token_id = int(model.config.video_token_id)
        if placeholder_token_id in {image_token_id, video_token_id}:
            raise RuntimeError("sentinel collides with a visual token ID")

        projector = TierTokenProjector(
            input_dim=args.input_dim,
            hidden_size=hidden_size,
        ).to(device=device, dtype=model_dtype)
        projector.eval()
        token_bundle = build_token_bundle(
            args.seed,
            args.input_dim,
            device,
            next(projector.parameters()).dtype,
        )
        with torch.no_grad():
            projected = projector(token_bundle)

        prompt = build_prompt(tokenizer, placeholder_token_id).to(device)
        adapter = TierCXRAdapter.from_tokenizer(
            model,
            tokenizer,
            placeholder_token_id,
        ).to(device)
        with torch.no_grad():
            serial_scores = adapter.score_labels(
                prompt,
                projected,
            )
            scores, audit = adapter.score_labels_vectorized(
                prompt,
                projected,
                return_audit=True,
            )

            intervened_tokens = token_bundle.tokens.clone()
            intervened_tokens[:, 32:60] = -intervened_tokens[:, 32:60]
            intervened_bundle = TokenBundle(
                tokens=intervened_tokens,
                token_types=token_bundle.token_types,
                valid_mask=token_bundle.valid_mask,
                assignment=token_bundle.assignment,
                anatomy_ids=token_bundle.anatomy_ids,
                temporal_ids=token_bundle.temporal_ids,
                confidence=token_bundle.confidence,
                slot_mass=token_bundle.slot_mass,
                source_ids=token_bundle.source_ids,
            )
            intervened_projected = projector(intervened_bundle)
            intervened_scores = adapter.score_labels_vectorized(
                prompt, intervened_projected
            )

        score_delta = (scores - intervened_scores).abs().mean()
        vectorized_serial_max_abs_diff = float(
            (scores - serial_scores).abs().max()
        )
        equivalence_atol = 1e-4 if args.dtype == "float32" else 0.25
        same_argmax = int(scores.argmax(dim=-1).item()) == int(
            serial_scores.argmax(dim=-1).item()
        )
        all_finite = bool(
            torch.isfinite(scores).all() and torch.isfinite(intervened_scores).all()
        )
        freeze_audit = adapter.freeze_audit()
        checks = {
            "cuda_available": True,
            "exact_64_placeholders": int(prompt.eq(placeholder_token_id).sum()) == 64,
            "all_64_physical_attention_one": bool(projected.attention_mask.eq(1).all()),
            "position_axes_equal": bool(
                torch.equal(projected.position_ids[0], projected.position_ids[1])
                and torch.equal(projected.position_ids[0], projected.position_ids[2])
            ),
            "no_pixel_inputs": audit["pixel_inputs_used"] is False,
            "model_frozen": bool(freeze_audit["all_frozen"]),
            "five_finite_scores": all_finite and tuple(scores.shape) == (1, 5),
            "relation_intervention_changes_scores": bool(score_delta > 1e-8),
            "vectorized_matches_serial": (
                vectorized_serial_max_abs_diff <= equivalence_atol
                and same_argmax
            ),
        }
        result.update(
            {
                "status": "PASS" if all(checks.values()) else "FAIL",
                "checks": checks,
                "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"),
                "gpu_name": torch.cuda.get_device_name(device),
                "gpu_capability": torch.cuda.get_device_capability(device),
                "model_type": model.config.model_type,
                "hidden_size": hidden_size,
                "image_token_id": image_token_id,
                "video_token_id": video_token_id,
                "placeholder_token_id": placeholder_token_id,
                "label_order": PROGRESSION_LABELS,
                "label_token_ids": {
                    label: adapter.label_token_ids[
                        index, : int(adapter.label_lengths[index])
                    ]
                    for index, label in enumerate(PROGRESSION_LABELS)
                },
                "scores": scores,
                "serial_scores": serial_scores,
                "vectorized_serial_max_abs_diff": (
                    vectorized_serial_max_abs_diff
                ),
                "vectorized_serial_atol": equivalence_atol,
                "vectorized_serial_same_argmax": same_argmax,
                "attention_implementation": "eager",
                "intervened_scores": intervened_scores,
                "mean_absolute_score_delta": float(score_delta),
                "adapter_audit": audit,
                "freeze_audit": freeze_audit,
                "projector_parameter_count": sum(
                    parameter.numel() for parameter in projector.parameters()
                ),
                "peak_cuda_allocated_bytes": torch.cuda.max_memory_allocated(device),
                "peak_cuda_reserved_bytes": torch.cuda.max_memory_reserved(device),
                "config_sha256": sha256_file(args.model / "config.json"),
            }
        )
    except Exception as error:
        result["error_type"] = type(error).__name__
        result["error"] = str(error)
    finally:
        result["elapsed_seconds"] = time.time() - started
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(json_safe(result), indent=2, sort_keys=True),
            encoding="utf-8",
        )

    print(json.dumps(json_safe(result), indent=2, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
