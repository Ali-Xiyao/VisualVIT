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
import torch.nn.functional as F

from scripts.r37c_common import load_candidate, merge_structure_and_labels, read_json
from scripts.r39_common import (
    DEFAULT_R39_CONFIG,
    TARGET_TO_VLM,
    build_prompt,
    iter_token_rows,
    load_r39_config,
    patient_class_weights,
    stable_order,
    token_bundle,
    write_json,
)
from visualvit.qwen_adapter import PROGRESSION_LABELS
from visualvit.tier_cxr_vlm import TierCXRAdapter
from visualvit.tier_token_projector import TierTokenProjector


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train one frozen-VLM R39 projector seed"
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_R39_CONFIG)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--device", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_r39_config(args.config)
    training = config["training"]
    if args.seed not in training["seeds"]:
        raise ValueError("R39 projector seed drift")
    output_root = Path(config["runtime"]["projectors"]) / f"seed_{args.seed}"
    if output_root.exists():
        raise FileExistsError(f"R39 projector output must be fresh: {output_root}")
    token_index = read_json(
        Path(config["runtime"]["dev_token_cache"])
        / f"seed_{args.seed}"
        / "index.json"
    )
    if (
        token_index.get("status") != "PASS_R39_FIXED64_TOKEN_CACHE"
        or token_index.get("scope") != "dev"
        or token_index.get("labels_in_cache") is not False
    ):
        raise PermissionError("R39 dev token cache firewall drift")
    candidate = load_candidate(WORKSPACE / config["source_r37_candidate"])
    cache_root = Path(candidate["r37c_one_shot"]["structural_cache_root"])
    reveal_root = Path(candidate["r37c_one_shot"]["protected_reveal_root"])
    rows = merge_structure_and_labels(
        read_json(cache_root / "dev_structure.json"),
        read_json(reveal_root / "protected_dev_labels.json"),
    )
    by_record = {str(row["record_id"]): row for row in rows}
    token_rows = list(iter_token_rows(token_index))
    if {row["record_id"] for row in token_rows} != set(by_record):
        raise ValueError("R39 dev token/label record alignment drift")
    examples = [
        {**row, "label": by_record[row["record_id"]]["label"]}
        for row in token_rows
    ]
    examples.sort(key=lambda row: stable_order(args.seed, row["record_id"]))
    weights = patient_class_weights(examples)

    device = torch.device(args.device)
    torch.cuda.set_device(device)
    torch.cuda.reset_peak_memory_stats(device)
    torch.manual_seed(args.seed)
    torch.cuda.manual_seed_all(args.seed)
    import transformers
    from transformers import AutoTokenizer, Qwen3VLForConditionalGeneration

    tokenizer = AutoTokenizer.from_pretrained(
        config["model"]["path"],
        local_files_only=True,
        trust_remote_code=False,
    )
    sentinel = config["interface"]["sentinel_token"]
    placeholder_id = int(tokenizer.convert_tokens_to_ids(sentinel))
    if (
        placeholder_id != int(config["interface"]["placeholder_token_id"])
        or tokenizer(sentinel, add_special_tokens=False)["input_ids"]
        != [placeholder_id]
    ):
        raise ValueError("R39 sentinel receipt drift")
    model = Qwen3VLForConditionalGeneration.from_pretrained(
        config["model"]["path"],
        dtype=torch.bfloat16,
        attn_implementation=config["model"]["attention_implementation"],
        local_files_only=True,
        trust_remote_code=False,
        low_cpu_mem_usage=True,
    ).to(device)
    model.eval().requires_grad_(False)
    model.config.use_cache = False
    model.gradient_checkpointing_enable(
        gradient_checkpointing_kwargs={"use_reentrant": False}
    )
    torch.manual_seed(args.seed)
    torch.cuda.manual_seed_all(args.seed)
    projector = TierTokenProjector(
        input_dim=config["interface"]["input_width"],
        hidden_size=config["model"]["hidden_size"],
    ).to(device)
    if sum(parameter.numel() for parameter in projector.parameters()) != int(
        config["interface"]["projector_parameter_count"]
    ):
        raise ValueError("R39 projector parameter budget drift")
    adapter = TierCXRAdapter.from_tokenizer(
        model,
        tokenizer,
        placeholder_id,
    ).to(device)
    optimizer = torch.optim.AdamW(
        projector.parameters(),
        lr=float(training["learning_rate"]),
        weight_decay=float(training["weight_decay"]),
    )
    accumulation = int(training["gradient_accumulation"])
    loss_weights = training["loss"]
    optimizer.zero_grad(set_to_none=True)
    started = time.perf_counter()
    running_loss = 0.0
    history = []
    projector.train()
    adapter.train()
    for step, (row, weight) in enumerate(zip(examples, weights, strict=True), 1):
        a6_tokens = row["true_tokens"].unsqueeze(0).to(
            device=device, dtype=torch.float32
        )
        a0_tokens = row["a0_tokens"].unsqueeze(0).to(
            device=device, dtype=torch.float32
        )
        branch_tokens = torch.cat((a6_tokens, a0_tokens), dim=0)
        projected = projector(token_bundle(branch_tokens))
        prompt_row = build_prompt(
            tokenizer,
            template=config["interface"]["prompt"],
            finding=row["finding"],
            placeholder_token_id=placeholder_id,
        ).to(device)
        prompt = prompt_row.expand(2, -1)
        scores, audit = adapter.score_labels_vectorized(
            prompt, projected, return_audit=True
        )
        target = torch.full(
            (2,),
            TARGET_TO_VLM[row["label"]],
            dtype=torch.long,
            device=device,
        )
        branch_loss = F.cross_entropy(scores, target, reduction="none")
        loss = (
            float(loss_weights["a6_selected"]) * branch_loss[0]
            + float(loss_weights["a0_frozen_difference"]) * branch_loss[1]
        ) * float(weight)
        (loss / accumulation).backward()
        if step % accumulation == 0 or step == len(examples):
            torch.nn.utils.clip_grad_norm_(projector.parameters(), 1.0)
            optimizer.step()
            optimizer.zero_grad(set_to_none=True)
        running_loss += float(loss.detach().cpu())
        if step % 100 == 0 or step == len(examples):
            history.append(
                {
                    "step": step,
                    "mean_weighted_loss": running_loss / step,
                    "elapsed_seconds": time.perf_counter() - started,
                }
            )
    frozen_audit = adapter.freeze_audit()
    if (
        not frozen_audit["all_frozen"]
        or audit["pixel_inputs_used"] is not False
        or tuple(PROGRESSION_LABELS)
        != tuple(config["interface"]["label_order"])
    ):
        raise PermissionError("R39 frozen-VLM/no-pixel audit failed")
    output_root.mkdir(parents=True, exist_ok=False)
    checkpoint_path = output_root / "checkpoint.pt"
    torch.save(
        {
            "schema": "visualvit.r39.projector-checkpoint.v1",
            "seed": args.seed,
            "projector": projector.state_dict(),
            "candidate_id": config["candidate_id"],
        },
        checkpoint_path,
    )
    result = {
        "schema": "visualvit.r39.projector-training.v1",
        "status": "PASS_R39_PROJECTOR_TRAINING",
        "seed": args.seed,
        "patients": len({row["patient_id"] for row in examples}),
        "rows": len(examples),
        "epochs": training["epochs"],
        "effective_batch_size": training["effective_batch_size"],
        "loss_weights": loss_weights,
        "history": history,
        "checkpoint": str(checkpoint_path),
        "checkpoint_bytes": checkpoint_path.stat().st_size,
        "projector_parameter_count": sum(
            parameter.numel() for parameter in projector.parameters()
        ),
        "vlm_freeze_audit": frozen_audit,
        "pixel_inputs_used": False,
        "token_budget": 64,
        "label_or_probe_logits_in_tokens": False,
        "sealed_483_test_labels_read": False,
        "gold_outcomes_read": False,
        "source_hashes_recomputed": False,
        "per_shard_hashes_computed": False,
        "model_hashes_recomputed": False,
        "transformers_version": transformers.__version__,
        "peak_cuda_allocated_bytes": torch.cuda.max_memory_allocated(device),
        "elapsed_seconds": time.perf_counter() - started,
    }
    write_json(output_root / "result.json", result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
