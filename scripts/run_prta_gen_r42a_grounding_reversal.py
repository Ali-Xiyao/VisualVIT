from __future__ import annotations

# ruff: noqa: E402

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import time
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE))
sys.path.insert(0, str(WORKSPACE / "src"))

import torch
from torch import Tensor

from scripts.build_prta_gen_r40b_smoke_cohort import read_json, write_json
from scripts.cache_prta_gen_r42a_reverse_tokens import REVERSE_CACHE_STATUS
from scripts.r39_common import token_bundle
from scripts.run_prta_gen_r40b_overfit_smoke import (
    build_prompt_ids,
    build_sft_tensors,
    load_selected_tokens,
)
from scripts.run_prta_gen_r40c_structured_generalization import (
    load_token_variants,
)
from scripts.run_prta_gen_r41a_progression_sft import (
    _rows_from_roster,
    evaluate_generation,
    target_text,
    validate_roster,
)
from visualvit.prta_gen import (
    generative_prior_preference_loss,
)
from visualvit.qwen_adapter import GenerativeVLMAdapter, apply_attention_lora
from visualvit.tier_token_projector import TierTokenProjector


CONFIG_STATUS = "FROZEN_PRTA_GEN_R42A_GROUNDING_REVERSAL"
ARM_STATUS = "PASS_PRTA_GEN_R42A_ARM_EVALUATION"
TRAINING_ARMS = ("g_cmcp", "g_cmcp_plus_reversal")
FORWARD_ARMS = ("true_pair", "current_only", "query_only", "prior_shuffle")


def stable_epoch_key(seed: int, arm: str, epoch: int, example_id: str) -> str:
    return hashlib.sha256(
        f"r42a|{seed}|{arm}|{epoch}|{example_id}".encode()
    ).hexdigest()


def reversed_target_text(
    row: dict[str, Any], mapping: dict[str, str]
) -> str:
    progression = str(row["progression"])
    if progression not in mapping:
        raise ValueError("R42A progression is absent from reversal mapping")
    return json.dumps(
        {
            "finding": str(row["finding"]),
            "progression": str(mapping[progression]),
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


def validate_predecessor(config: dict[str, Any]) -> dict[str, Any]:
    if config.get("status") != CONFIG_STATUS:
        raise PermissionError("R42A config is not frozen")
    spec = config["closed_predecessor"]
    predecessor = read_json(Path(spec["aggregate"]))
    if (
        predecessor.get("status") != spec["required_status"]
        or predecessor.get("gate_passed") is not spec["required_gate_passed"]
        or predecessor.get("r42_unlocked") is not spec["required_r42_unlocked"]
        or predecessor.get("scientific_claim_allowed") is not False
        or predecessor.get("protected_300_dev_read") is not False
        or predecessor.get("revealed_483_test_read") is not False
        or predecessor.get("gold_outcomes_read") is not False
        or predecessor.get("external_outcomes_read") is not False
    ):
        raise PermissionError("R42A predecessor receipt drift")
    return predecessor


def _load_reverse_tokens(
    config: dict[str, Any],
    *,
    example_ids: set[str],
) -> tuple[dict[str, Tensor], dict[str, str], dict[str, str]]:
    index = read_json(Path(config["source"]["reverse_token_index"]))
    if (
        index.get("status") != REVERSE_CACHE_STATUS
        or index.get("protocol_id") != config["protocol_id"]
        or index.get("rows") != config["reverse_cache"]["expected_rows"]
        or index.get("patients") != config["reverse_cache"]["expected_patients"]
        or index.get("heuristic_token_permutation_used") is not False
        or index.get("labels_in_cache") is not False
        or index.get("sentences_in_cache") is not False
        or index.get("protected_300_dev_read") is not False
        or index.get("revealed_483_test_read") is not False
        or index.get("gold_outcomes_read") is not False
        or index.get("external_outcomes_read") is not False
    ):
        raise PermissionError("R42A reverse-token cache receipt drift")
    loaded = load_selected_tokens(
        index, example_ids, token_key="reversed_tokens"
    )
    patients = loaded.pop("_patient_receipt")  # type: ignore[arg-type]
    findings = loaded.pop("_finding_receipt")  # type: ignore[arg-type]
    return loaded, patients, findings


def _sequence_score(
    *,
    adapter: GenerativeVLMAdapter,
    projector: TierTokenProjector,
    tokenizer: Any,
    config: dict[str, Any],
    row: dict[str, Any],
    tokens: Tensor,
    device: torch.device,
) -> Tensor:
    prompt = build_prompt_ids(
        tokenizer, config, finding=str(row["finding"])
    ).to(device)
    target_ids = tokenizer(
        target_text(row), add_special_tokens=False
    )["input_ids"]
    if bool(config["target"]["append_eos"]):
        target_ids = [*target_ids, int(tokenizer.eos_token_id)]
    target = torch.tensor([target_ids], dtype=torch.long, device=device)
    score = adapter.score_sequence(
        prompt,
        projector(
            token_bundle(
                tokens.unsqueeze(0).to(device=device, dtype=torch.float32)
            )
        ),
        target,
    )
    return score[0]


def _correct_prior_preference(
    *,
    adapter: GenerativeVLMAdapter,
    projector: TierTokenProjector,
    tokenizer: Any,
    config: dict[str, Any],
    rows: list[dict[str, Any]],
    true_tokens: dict[str, Tensor],
    shuffled_tokens: dict[str, Tensor],
    device: torch.device,
) -> dict[str, float | int]:
    correct = 0
    margins = []
    adapter.eval()
    projector.eval()
    with torch.no_grad():
        for row in rows:
            example_id = str(row["example_id"])
            true_score = _sequence_score(
                adapter=adapter,
                projector=projector,
                tokenizer=tokenizer,
                config=config,
                row=row,
                tokens=true_tokens[example_id],
                device=device,
            )
            shuffled_score = _sequence_score(
                adapter=adapter,
                projector=projector,
                tokenizer=tokenizer,
                config=config,
                row=row,
                tokens=shuffled_tokens[example_id],
                device=device,
            )
            margin = float((true_score - shuffled_score).cpu())
            margins.append(margin)
            correct += margin > 0.0
    return {
        "rows": len(rows),
        "correct_prior_preference": correct / len(rows),
        "mean_true_minus_shuffled_score": sum(margins) / len(margins),
    }


def run_arm(
    *,
    config_path: Path,
    seed: int,
    training_arm: str,
    device_name: str,
) -> dict[str, Any]:
    config = read_json(config_path)
    validate_predecessor(config)
    if seed not in [int(value) for value in config["training"]["seeds"]]:
        raise ValueError("R42A Seed is not registered")
    if training_arm not in TRAINING_ARMS:
        raise ValueError("R42A training arm is not registered")
    r41_config = read_json(WORKSPACE / config["source"]["r41_config"])
    roster = read_json(Path(config["source"]["roster"]))
    validate_roster(r41_config, roster)
    output_root = (
        Path(config["runtime"]["root"]) / f"seed_{seed}" / training_arm
    )
    if output_root.exists():
        raise FileExistsError(f"R42A arm output must be fresh: {output_root}")
    training_rows = _rows_from_roster(roster, "train")
    development_rows = _rows_from_roster(roster, "development")
    all_rows = training_rows + development_rows
    example_ids = {str(row["example_id"]) for row in all_rows}
    forward_index = read_json(Path(config["source"]["forward_token_index"]))
    forward, patients, findings = load_token_variants(
        forward_index,
        example_ids=example_ids,
        token_keys={
            "true_pair": "true_tokens",
            "current_only": "current_tokens",
            "prior_shuffle": "shuffled_tokens",
        },
    )
    reverse, reverse_patients, reverse_findings = _load_reverse_tokens(
        config, example_ids=example_ids
    )
    for row in all_rows:
        example_id = str(row["example_id"])
        expected_patient = str(row["patient_id"])
        expected_finding = str(row["finding"])
        if (
            patients[example_id] != expected_patient
            or findings[example_id] != expected_finding
            or reverse_patients[example_id] != expected_patient
            or reverse_findings[example_id] != expected_finding
        ):
            raise ValueError("R42A roster/token alignment drift")
    forward["query_only"] = {
        str(row["example_id"]): torch.zeros(
            (64, 768), dtype=torch.float32
        )
        for row in development_rows
    }
    device = torch.device(device_name)
    if device.type != "cuda" or not torch.cuda.is_available():
        raise RuntimeError("R42A arm execution requires CUDA")
    torch.cuda.set_device(device)
    torch.cuda.reset_peak_memory_stats(device)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    from transformers import AutoTokenizer, Qwen3VLForConditionalGeneration

    tokenizer = AutoTokenizer.from_pretrained(
        config["model"]["path"],
        local_files_only=True,
        trust_remote_code=False,
    )
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token_id = tokenizer.eos_token_id
    placeholder_id = int(
        tokenizer.convert_tokens_to_ids(config["model"]["sentinel_token"])
    )
    if placeholder_id != int(config["model"]["placeholder_token_id"]):
        raise ValueError("R42A sentinel receipt drift")
    model = Qwen3VLForConditionalGeneration.from_pretrained(
        config["model"]["path"],
        dtype=torch.bfloat16,
        attn_implementation=config["model"]["attention_implementation"],
        local_files_only=True,
        trust_remote_code=False,
        low_cpu_mem_usage=True,
    ).to(device)
    model.config.use_cache = False
    model.gradient_checkpointing_enable(
        gradient_checkpointing_kwargs={"use_reentrant": False}
    )
    lora = config["adapter"]["lora"]
    model = apply_attention_lora(
        model,
        rank=int(lora["rank"]),
        alpha=int(lora["alpha"]),
        dropout=float(lora["dropout"]),
        target_modules=tuple(lora["target_modules"]),
    )
    projector = TierTokenProjector(
        input_dim=int(config["model"]["input_width"]),
        hidden_size=int(config["model"]["hidden_size"]),
    ).to(device)
    adapter = GenerativeVLMAdapter(
        model,
        placeholder_id,
        tokenizer=tokenizer,
        token_budget=int(config["model"]["token_budget"]),
    ).to(device)
    r41_checkpoint_path = (
        Path(r41_config["runtime"]["root"])
        / f"seed_{seed}"
        / "g1_attention_lora"
        / "trainable_checkpoint.pt"
    )
    r41_checkpoint = torch.load(
        r41_checkpoint_path, map_location="cpu", weights_only=True
    )
    if (
        r41_checkpoint.get("seed") != seed
        or r41_checkpoint.get("model_arm") != "g1_attention_lora"
    ):
        raise PermissionError("R42A R41A checkpoint receipt drift")
    projector.load_state_dict(r41_checkpoint["projector"], strict=True)
    incompatible = adapter.load_state_dict(
        r41_checkpoint["lora"], strict=False
    )
    if incompatible.unexpected_keys or any(
        "lora_" in key for key in incompatible.missing_keys
    ):
        raise PermissionError("R42A failed to restore all R41A LoRA tensors")
    trainable_audit = adapter.trainable_parameter_audit()
    if (
        trainable_audit["trainable_boundary_pass"] is not True
        or int(trainable_audit["trainable_parameter_count"]) <= 0
    ):
        raise PermissionError("R42A trainable boundary drift")
    training = config["training"]
    optimizer = torch.optim.AdamW(
        [
            {
                "params": list(projector.parameters()),
                "lr": float(training["projector_learning_rate"]),
            },
            {
                "params": [
                    parameter
                    for parameter in adapter.parameters()
                    if parameter.requires_grad
                ],
                "lr": float(training["lora_learning_rate"]),
            },
        ],
        weight_decay=float(training["weight_decay"]),
    )
    accumulation = int(training["gradient_accumulation"])
    optimizer.zero_grad(set_to_none=True)
    global_row = 0
    updates = 0
    history = []
    started = time.perf_counter()
    mapping = {
        str(key): str(value)
        for key, value in config["target"]["reversal_mapping"].items()
    }
    for epoch in range(int(training["epochs"])):
        adapter.train()
        projector.train()
        ordered = sorted(
            training_rows,
            key=lambda row: stable_epoch_key(
                seed, training_arm, epoch, str(row["example_id"])
            ),
        )
        sums = {"total": 0.0, "sft": 0.0, "g_cmcp": 0.0, "reversal": 0.0}
        for row in ordered:
            global_row += 1
            example_id = str(row["example_id"])
            prompt, input_ids, labels = build_sft_tensors(
                tokenizer,
                config,
                finding=str(row["finding"]),
                target_text=target_text(row),
            )
            true_projected = projector(
                token_bundle(
                    forward["true_pair"][example_id]
                    .unsqueeze(0)
                    .to(device=device, dtype=torch.float32)
                )
            )
            sft = adapter.forward_sft(
                input_ids.to(device),
                true_projected,
                labels=labels.to(device),
            )["loss"]
            target_ids = tokenizer(
                target_text(row), add_special_tokens=False
            )["input_ids"]
            target_ids = [*target_ids, int(tokenizer.eos_token_id)]
            target = torch.tensor(
                [target_ids], dtype=torch.long, device=device
            )
            true_score = adapter.score_sequence(
                prompt.to(device), true_projected, target
            )
            shuffled_projected = projector(
                token_bundle(
                    forward["prior_shuffle"][example_id]
                    .unsqueeze(0)
                    .to(device=device, dtype=torch.float32)
                )
            )
            shuffled_score = adapter.score_sequence(
                prompt.to(device), shuffled_projected, target
            )
            g_cmcp = generative_prior_preference_loss(
                true_score,
                shuffled_score,
                margin=float(training["g_cmcp_margin"]),
            )
            reversal = torch.zeros((), device=device)
            if training_arm == "g_cmcp_plus_reversal":
                _, reverse_input, reverse_labels = build_sft_tensors(
                    tokenizer,
                    config,
                    finding=str(row["finding"]),
                    target_text=reversed_target_text(row, mapping),
                )
                reverse_projected = projector(
                    token_bundle(
                        reverse[example_id]
                        .unsqueeze(0)
                        .to(device=device, dtype=torch.float32)
                    )
                )
                reversal = adapter.forward_sft(
                    reverse_input.to(device),
                    reverse_projected,
                    labels=reverse_labels.to(device),
                )["loss"]
            loss = (
                float(training["sft_weight"]) * sft
                + float(training["g_cmcp_weight"]) * g_cmcp
                + float(training["time_reversal_weight"]) * reversal
            )
            if not bool(torch.isfinite(loss)):
                raise FloatingPointError("R42A training loss is non-finite")
            (loss / accumulation).backward()
            if (
                global_row % accumulation == 0
                or global_row
                == int(training["epochs"]) * len(training_rows)
            ):
                torch.nn.utils.clip_grad_norm_(
                    [
                        parameter
                        for group in optimizer.param_groups
                        for parameter in group["params"]
                    ],
                    float(training["gradient_clip_norm"]),
                )
                optimizer.step()
                optimizer.zero_grad(set_to_none=True)
                updates += 1
            sums["total"] += float(loss.detach().cpu())
            sums["sft"] += float(sft.detach().cpu())
            sums["g_cmcp"] += float(g_cmcp.detach().cpu())
            sums["reversal"] += float(reversal.detach().cpu())
        history.append(
            {
                "epoch": epoch + 1,
                "mean_total_loss": sums["total"] / len(ordered),
                "mean_sft_loss": sums["sft"] / len(ordered),
                "mean_g_cmcp_loss": sums["g_cmcp"] / len(ordered),
                "mean_reversal_loss": sums["reversal"] / len(ordered),
                "optimizer_updates_completed": updates,
                "elapsed_seconds": time.perf_counter() - started,
            }
        )
    if updates != int(training["expected_optimizer_updates"]):
        raise ValueError("R42A optimizer update-count drift")
    model.gradient_checkpointing_disable()
    model.config.use_cache = True
    metrics = {}
    predictions = {}
    for evaluation_arm in FORWARD_ARMS:
        values, predicted = evaluate_generation(
            adapter=adapter,
            projector=projector,
            tokenizer=tokenizer,
            config=config,
            rows=development_rows,
            tokens=forward[evaluation_arm],
            device=device,
        )
        metrics[evaluation_arm] = values
        predictions[evaluation_arm] = predicted
    reversed_rows = [
        {**row, "progression": mapping[str(row["progression"])]}
        for row in development_rows
    ]
    reverse_metrics, reverse_predictions = evaluate_generation(
        adapter=adapter,
        projector=projector,
        tokenizer=tokenizer,
        config=config,
        rows=reversed_rows,
        tokens=reverse,
        device=device,
    )
    metrics["time_reversed"] = reverse_metrics
    predictions["time_reversed"] = reverse_predictions
    preference = _correct_prior_preference(
        adapter=adapter,
        projector=projector,
        tokenizer=tokenizer,
        config=config,
        rows=development_rows,
        true_tokens=forward["true_pair"],
        shuffled_tokens=forward["prior_shuffle"],
        device=device,
    )
    output_root.mkdir(parents=True, exist_ok=False)
    checkpoint_path = output_root / "trainable_checkpoint.pt"
    torch.save(
        {
            "schema": "visualvit.prta-gen.r42a-trainable-checkpoint.v1",
            "seed": seed,
            "training_arm": training_arm,
            "projector": projector.state_dict(),
            "lora": {
                name: tensor.detach().cpu()
                for name, tensor in adapter.state_dict().items()
                if "lora_" in name
            },
        },
        checkpoint_path,
    )
    class_to_index = {
        label: index
        for index, label in enumerate(config["target"]["progression_values"])
    }
    result = {
        "schema": "visualvit.prta-gen.r42a-arm-result.v1",
        "status": config["result_statuses"]["arm_complete"],
        "protocol_id": config["protocol_id"],
        "study_tier": config["study_tier"],
        "seed": seed,
        "training_arm": training_arm,
        "classes": config["target"]["progression_values"],
        "training_rows": len(training_rows),
        "training_patients": len(training_rows),
        "development_rows": len(development_rows),
        "development_patients": len(development_rows),
        "development_patient_ids": [
            str(row["patient_id"]) for row in development_rows
        ],
        "development_example_ids": [
            str(row["example_id"]) for row in development_rows
        ],
        "targets": [
            class_to_index[str(row["progression"])]
            for row in development_rows
        ],
        "predictions": predictions,
        "metrics": metrics,
        "correct_prior_preference": preference,
        "history": history,
        "optimizer_updates": updates,
        "r41_checkpoint": str(r41_checkpoint_path),
        "checkpoint": str(checkpoint_path),
        "checkpoint_bytes": checkpoint_path.stat().st_size,
        "exact64_tokens_used": True,
        "reverse_tokens_recomputed_by_input_swap": True,
        "heuristic_token_permutation_used": False,
        "free_greedy_generation_evaluated": True,
        "pixel_inputs_used": False,
        "r43_unlocked": False,
        "scientific_claim_allowed": False,
        "protected_300_dev_read": False,
        "revealed_483_test_read": False,
        "gold_outcomes_read": False,
        "external_outcomes_read": False,
        "peak_cuda_allocated_bytes": torch.cuda.max_memory_allocated(device),
        "elapsed_seconds": time.perf_counter() - started,
    }
    write_json(output_root / "result.json", result)
    return result


def preflight(config_path: Path) -> dict[str, Any]:
    config = read_json(config_path)
    if config.get("status") != CONFIG_STATUS:
        raise PermissionError("R42A config is not frozen")
    if tuple(config["training"]["arms"]) != TRAINING_ARMS:
        raise ValueError("R42A training-arm registry drift")
    if tuple(config["evaluation"]["forward_arms"]) != FORWARD_ARMS:
        raise ValueError("R42A evaluation-arm registry drift")
    mapping = config["target"]["reversal_mapping"]
    if (
        set(mapping) != set(config["target"]["progression_values"])
        or any(mapping[mapping[value]] != value for value in mapping)
    ):
        raise ValueError("R42A reversal mapping is not an involution")
    expected_updates = math.ceil(
        int(config["reverse_cache"]["expected_rows"] - 125)
        * int(config["training"]["epochs"])
        / int(config["training"]["gradient_accumulation"])
    )
    if expected_updates != int(
        config["training"]["expected_optimizer_updates"]
    ):
        raise ValueError("R42A expected optimizer-update drift")
    return {
        "schema": "visualvit.prta-gen.r42a-runner-preflight.v1",
        "status": "PASS_PRTA_GEN_R42A_RUNNER_PREFLIGHT",
        "protocol_id": config["protocol_id"],
        "training_arms": list(TRAINING_ARMS),
        "forward_evaluation_arms": list(FORWARD_ARMS),
        "seeds": config["training"]["seeds"],
        "expected_optimizer_updates": expected_updates,
        "reversal_mapping_involutive": True,
        "predecessor_result_required_only_at_execution": True,
        "gpu_training_started": False,
        "protected_300_dev_read": False,
        "revealed_483_test_read": False,
        "gold_outcomes_read": False,
        "external_outcomes_read": False,
    }


def receipt_summary(result: dict[str, Any]) -> dict[str, Any]:
    if result.get("schema") == "visualvit.prta-gen.r42a-runner-preflight.v1":
        return dict(result)
    keys = (
        "schema",
        "status",
        "protocol_id",
        "study_tier",
        "seed",
        "training_arm",
        "training_rows",
        "training_patients",
        "development_rows",
        "development_patients",
        "metrics",
        "correct_prior_preference",
        "history",
        "optimizer_updates",
        "r41_checkpoint",
        "checkpoint",
        "checkpoint_bytes",
        "exact64_tokens_used",
        "reverse_tokens_recomputed_by_input_swap",
        "heuristic_token_permutation_used",
        "free_greedy_generation_evaluated",
        "pixel_inputs_used",
        "r43_unlocked",
        "scientific_claim_allowed",
        "protected_300_dev_read",
        "revealed_483_test_read",
        "gold_outcomes_read",
        "external_outcomes_read",
        "peak_cuda_allocated_bytes",
        "elapsed_seconds",
    )
    return {key: result[key] for key in keys if key in result}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Preflight or run one frozen R42A Seed/training arm"
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--training-arm")
    parser.add_argument("--device")
    parser.add_argument("--preflight-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.preflight_only:
        if any(
            value is not None
            for value in (args.seed, args.training_arm, args.device)
        ):
            raise ValueError("R42A preflight accepts only --config")
        result = preflight(args.config)
    else:
        if (
            args.seed is None
            or args.training_arm is None
            or args.device is None
        ):
            raise ValueError(
                "R42A run requires seed, training-arm, and device"
            )
        result = run_arm(
            config_path=args.config,
            seed=args.seed,
            training_arm=args.training_arm,
            device_name=args.device,
        )
    print(json.dumps(receipt_summary(result), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
