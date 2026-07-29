from __future__ import annotations

# ruff: noqa: E402

import argparse
import json
from pathlib import Path
import sys
import time

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE))
sys.path.insert(0, str(WORKSPACE / "src"))

import torch

from scripts.r39_common import (
    DEFAULT_R39_CONFIG,
    build_prompt,
    iter_token_rows,
    load_r39_config,
    read_json,
    token_bundle,
    write_json,
)
from visualvit.qwen_adapter import PROGRESSION_LABELS
from visualvit.tier_cxr_vlm import TierCXRAdapter
from visualvit.tier_token_projector import TierTokenProjector


PREDICTION_KEYS = (
    "a6_true_pair",
    "a0_frozen_difference",
    "a6_current_only",
    "a6_prior_shuffle",
    "query_only",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Freeze one outcome-blind R39 sealed prediction set"
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_R39_CONFIG)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--device", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_r39_config(args.config)
    if args.seed not in config["training"]["seeds"]:
        raise ValueError("R39 sealed-prediction seed drift")
    token_index = read_json(
        Path(config["runtime"]["sealed_token_cache"])
        / f"seed_{args.seed}"
        / "index.json"
    )
    required_variants = {
        "a6_true_pair",
        "a6_current_only",
        "a0_frozen_difference",
        "a6_prior_shuffle",
    }
    if (
        token_index.get("status") != "PASS_R39_FIXED64_TOKEN_CACHE"
        or token_index.get("scope") != "sealed"
        or token_index.get("labels_in_cache") is not False
        or set(token_index.get("cached_variants", ())) != required_variants
    ):
        raise PermissionError("R39 sealed token-cache firewall drift")
    projector_root = (
        Path(config["runtime"]["projectors"]) / f"seed_{args.seed}"
    )
    projector_result = read_json(projector_root / "result.json")
    if (
        projector_result.get("status") != "PASS_R39_PROJECTOR_TRAINING"
        or projector_result.get("sealed_483_test_labels_read") is not False
        or projector_result.get("gold_outcomes_read") is not False
    ):
        raise PermissionError("R39 projector is not a firewall-clean PASS")
    output_root = (
        Path(config["runtime"]["root"])
        / "predictions"
        / f"seed_{args.seed}"
    )
    if output_root.exists():
        raise FileExistsError(
            f"R39 sealed prediction output must be fresh: {output_root}"
        )

    device = torch.device(args.device)
    torch.cuda.set_device(device)
    torch.cuda.reset_peak_memory_stats(device)
    import transformers
    from transformers import AutoTokenizer, Qwen3VLForConditionalGeneration

    tokenizer = AutoTokenizer.from_pretrained(
        config["model"]["path"],
        local_files_only=True,
        trust_remote_code=False,
    )
    placeholder_id = int(
        tokenizer.convert_tokens_to_ids(
            config["interface"]["sentinel_token"]
        )
    )
    if placeholder_id != int(config["interface"]["placeholder_token_id"]):
        raise ValueError("R39 sealed-prediction sentinel drift")
    model = Qwen3VLForConditionalGeneration.from_pretrained(
        config["model"]["path"],
        dtype=torch.bfloat16,
        attn_implementation=config["model"]["attention_implementation"],
        local_files_only=True,
        trust_remote_code=False,
        low_cpu_mem_usage=True,
    ).to(device)
    model.eval().requires_grad_(False)
    projector = TierTokenProjector(
        input_dim=config["interface"]["input_width"],
        hidden_size=config["model"]["hidden_size"],
    ).to(device)
    checkpoint = torch.load(
        projector_root / "checkpoint.pt",
        map_location="cpu",
        weights_only=True,
    )
    if (
        checkpoint.get("schema")
        != "visualvit.r39.projector-checkpoint.v1"
        or int(checkpoint.get("seed")) != args.seed
    ):
        raise ValueError("R39 projector checkpoint metadata drift")
    projector.load_state_dict(checkpoint["projector"], strict=True)
    projector.eval()
    adapter = TierCXRAdapter.from_tokenizer(
        model, tokenizer, placeholder_id
    ).to(device)
    adapter.eval()

    predictions = {key: [] for key in PREDICTION_KEYS}
    record_ids: list[str] = []
    patient_ids: list[str] = []
    started = time.perf_counter()
    audit = None
    with torch.inference_mode():
        for row in iter_token_rows(token_index):
            true_tokens = row["true_tokens"].unsqueeze(0).to(
                device=device, dtype=torch.float32
            )
            branch_tokens = torch.cat(
                (
                    true_tokens,
                    row["a0_tokens"].unsqueeze(0).to(
                        device=device, dtype=torch.float32
                    ),
                    row["current_tokens"].unsqueeze(0).to(
                        device=device, dtype=torch.float32
                    ),
                    row["shuffled_tokens"].unsqueeze(0).to(
                        device=device, dtype=torch.float32
                    ),
                    torch.zeros_like(true_tokens),
                ),
                dim=0,
            )
            projected = projector(token_bundle(branch_tokens))
            prompt_row = build_prompt(
                tokenizer,
                template=config["interface"]["prompt"],
                finding=row["finding"],
                placeholder_token_id=placeholder_id,
            ).to(device)
            scores, audit = adapter.score_labels_vectorized(
                prompt_row.expand(len(PREDICTION_KEYS), -1),
                projected,
                return_audit=True,
            )
            predicted = scores.argmax(dim=-1).cpu().tolist()
            for key, value in zip(
                PREDICTION_KEYS, predicted, strict=True
            ):
                predictions[key].append(int(value))
            record_ids.append(row["record_id"])
            patient_ids.append(row["patient_id"])
    if (
        len(record_ids) != int(config["sealed_test"]["expected_rows"])
        or len(set(patient_ids))
        != int(config["sealed_test"]["expected_patients"])
        or audit is None
        or audit["pixel_inputs_used"] is not False
        or audit["model_frozen"] is not True
        or tuple(audit["labels"]) != tuple(PROGRESSION_LABELS)
    ):
        raise RuntimeError("R39 sealed prediction audit failed")
    result = {
        "schema": "visualvit.r39.outcome-blind-sealed-predictions.v1",
        "status": "PASS_R39_OUTCOME_BLIND_SEALED_PREDICTIONS",
        "candidate_id": config["candidate_id"],
        "seed": args.seed,
        "rows": len(record_ids),
        "patients": len(set(patient_ids)),
        "record_ids": record_ids,
        "patient_ids": patient_ids,
        "predictions": predictions,
        "prediction_keys": list(PREDICTION_KEYS),
        "label_order": list(PROGRESSION_LABELS),
        "all_predictions_frozen_before_label_reveal": True,
        "vlm_all_frozen": True,
        "pixel_inputs_used": False,
        "token_budget": 64,
        "sealed_483_test_labels_read": False,
        "gold_outcomes_read": False,
        "source_hashes_recomputed": False,
        "per_shard_hashes_computed": False,
        "checkpoint_hashes_recomputed": False,
        "transformers_version": transformers.__version__,
        "peak_cuda_allocated_bytes": torch.cuda.max_memory_allocated(device),
        "elapsed_seconds": time.perf_counter() - started,
    }
    output_root.mkdir(parents=True, exist_ok=False)
    write_json(output_root / "result.json", result)
    print(
        json.dumps(
            {
                "status": result["status"],
                "seed": args.seed,
                "rows": result["rows"],
                "patients": result["patients"],
                "elapsed_seconds": result["elapsed_seconds"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
