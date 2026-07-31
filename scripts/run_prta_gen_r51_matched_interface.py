from __future__ import annotations

# ruff: noqa: E402

import argparse
import hashlib
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
from torch import Tensor

from scripts.build_prta_gen_r40b_smoke_cohort import read_json, write_json
from scripts.r39_common import token_bundle
from scripts.r51_common import validate_authority
from scripts.run_prta_gen_r40b_overfit_smoke import (
    build_prompt_ids,
    build_sft_tensors,
)
from scripts.run_prta_gen_r40c_structured_generalization import load_token_variants
from scripts.run_prta_gen_r41a_progression_sft import target_text
from scripts.run_prta_gen_r49_exact64 import (
    _prompt_config,
    _state_sha256,
    evaluate,
    stable_epoch_key,
)
from visualvit.prta_gen import PROGRESSION_CLASSES
from visualvit.qwen_adapter import GenerativeVLMAdapter
from visualvit.r51_exact64 import normalize_exact64_tokens
from visualvit.tier_token_projector import TierTokenProjector


DEFAULT_CONFIG = (
    WORKSPACE / "configs" / "prta_gen" / "prta_gen_r51_matched_interface_v1.json"
)


def _source_specs(config: dict[str, Any], arm: str) -> list[dict[str, Any]]:
    if arm == "prta_exact64":
        names = ("prta_training", "prta_evaluation")
    elif arm in ("tila_exact64", "b2_exact64"):
        names = (arm,)
    else:
        raise ValueError("unknown R51 matched-interface arm")
    return [config["token_sources"][name] for name in names]


def _load_arm_tokens(
    config: dict[str, Any], arm: str, rows: list[dict[str, Any]]
) -> dict[str, Tensor]:
    requested = {str(row["example_id"]) for row in rows}
    tokens: dict[str, Tensor] = {}
    patients: dict[str, str] = {}
    findings: dict[str, str] = {}
    remaining = set(requested)
    for source in _source_specs(config, arm):
        index = read_json(Path(source["path"]))
        source_ids: set[str] = set()
        for shard in index["shards"]:
            payload = torch.load(shard["path"], map_location="cpu", weights_only=True)
            source_ids.update(str(value) for value in payload["example_ids"])
        take = remaining & source_ids
        if not take:
            continue
        loaded, patient_receipt, finding_receipt = load_token_variants(
            index,
            example_ids=take,
            token_keys={"source": str(source["token_key"])},
        )
        overlap = set(tokens) & set(loaded["source"])
        if overlap:
            raise ValueError("R51 token source overlap")
        tokens.update(loaded["source"])
        patients.update(patient_receipt)
        findings.update(finding_receipt)
        remaining -= take
    if remaining:
        raise ValueError(f"R51 token source missing {len(remaining)} rows")
    normalized: dict[str, Tensor] = {}
    for row in rows:
        example_id = str(row["example_id"])
        tensor = tokens[example_id]
        if (
            patients[example_id] != str(row["patient_id"])
            or findings[example_id] != str(row["finding"])
            or tuple(tensor.shape) != (64, 768)
            or not bool(tensor[60:64].eq(0).all())
        ):
            raise PermissionError("R51 roster/token alignment drift")
        value = normalize_exact64_tokens(tensor.unsqueeze(0))[0].half()
        if not bool(torch.isfinite(value).all() and value[60:64].eq(0).all()):
            raise FloatingPointError("R51 common token normalization failed")
        normalized[example_id] = value
    return normalized


def preflight(config_path: Path) -> dict[str, Any]:
    config, training_rows, evaluation_rows = validate_authority(
        config_path, require_pinned_caches=True
    )
    seeds = [int(value) for value in config["training"]["seeds"]]
    arms = [str(value) for value in config["evaluation"]["arms"]]
    existing = [
        str(Path(config["runtime"]["runs"]) / f"seed_{seed}" / arm)
        for seed in seeds
        for arm in arms
        if (Path(config["runtime"]["runs"]) / f"seed_{seed}" / arm).exists()
    ]
    if existing:
        raise FileExistsError(f"R51 run outputs are not fresh: {existing}")
    audit_rows = [training_rows[0], evaluation_rows[0]]
    for arm in arms:
        loaded = _load_arm_tokens(config, arm, audit_rows)
        if len(loaded) != len(audit_rows):
            raise RuntimeError("R51 token preflight row-count drift")
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(
        config["model"]["path"], local_files_only=True, trust_remote_code=False
    )
    placeholder = int(
        tokenizer.convert_tokens_to_ids(config["model"]["sentinel_token"])
    )
    if placeholder != int(config["model"]["placeholder_token_id"]):
        raise ValueError("R51 sentinel token drift")
    prompt_config = _prompt_config(config)
    if str(config["prompt"]["shared_task"]) not in prompt_config["prompt"]["user_prefix"]:
        raise PermissionError("R51 shared prompt contract missing")
    initialization_hashes: dict[str, str] = {}
    for seed in seeds:
        torch.manual_seed(seed)
        projector = TierTokenProjector(
            input_dim=int(config["model"]["input_width"]),
            hidden_size=int(config["model"]["hidden_size"]),
        )
        initialization_hashes[str(seed)] = _state_sha256(projector)
        del projector
    return {
        "schema": "visualvit.prta-gen.r51-runner-preflight.v1",
        "status": config["result_statuses"]["runner_preflight_pass"],
        "protocol_id": config["protocol_id"],
        "training_rows": len(training_rows),
        "evaluation_rows": len(evaluation_rows),
        "arms": arms,
        "seeds": seeds,
        "placeholder_token_id": placeholder,
        "shared_projector_initialization_hashes": initialization_hashes,
        "all_outputs_fresh": True,
        "qwen_loaded": False,
        "gpu_training_started": False,
        "evaluation_model_outcomes_read": False,
        "protected_300_dev_read": False,
        "revealed_483_test_read": False,
        "gold_outcomes_read": False,
        "external_outcomes_read": False,
    }


def run_arm(config_path: Path, seed: int, arm: str, device_name: str) -> dict[str, Any]:
    config, training_rows, evaluation_rows = validate_authority(
        config_path, require_pinned_caches=True
    )
    if seed not in [int(value) for value in config["training"]["seeds"]]:
        raise ValueError("R51 seed is not registered")
    if arm not in [str(value) for value in config["evaluation"]["arms"]]:
        raise ValueError("R51 arm is not registered")
    output = Path(config["runtime"]["runs"]) / f"seed_{seed}" / arm
    if output.exists():
        raise FileExistsError(output)
    all_rows = training_rows + evaluation_rows
    tokens = _load_arm_tokens(config, arm, all_rows)
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    device = torch.device(device_name)
    if device.type != "cuda" or not torch.cuda.is_available():
        raise RuntimeError("R51 matched-interface run requires explicit CUDA")
    torch.cuda.set_device(device)
    torch.cuda.reset_peak_memory_stats(device)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    from transformers import AutoTokenizer, Qwen3VLForConditionalGeneration

    tokenizer = AutoTokenizer.from_pretrained(
        config["model"]["path"], local_files_only=True, trust_remote_code=False
    )
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token_id = tokenizer.eos_token_id
    placeholder = int(
        tokenizer.convert_tokens_to_ids(config["model"]["sentinel_token"])
    )
    if placeholder != int(config["model"]["placeholder_token_id"]):
        raise ValueError("R51 sentinel token drift")
    model = Qwen3VLForConditionalGeneration.from_pretrained(
        config["model"]["path"],
        dtype=torch.bfloat16,
        attn_implementation=config["model"]["attention_implementation"],
        local_files_only=True,
        trust_remote_code=False,
        low_cpu_mem_usage=True,
    ).to(device)
    model.requires_grad_(False)
    model.config.use_cache = False
    model.gradient_checkpointing_enable(
        gradient_checkpointing_kwargs={"use_reentrant": False}
    )
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    projector = TierTokenProjector(
        input_dim=int(config["model"]["input_width"]),
        hidden_size=int(config["model"]["hidden_size"]),
    ).to(device)
    initialization_sha256 = _state_sha256(projector)
    adapter = GenerativeVLMAdapter(
        model,
        placeholder,
        tokenizer=tokenizer,
        token_budget=int(config["model"]["token_budget"]),
    ).to(device)
    model_audit = adapter.trainable_parameter_audit()
    if (
        model_audit["trainable_boundary_pass"] is not True
        or int(model_audit["trainable_parameter_count"]) != 0
    ):
        raise PermissionError("R51 Qwen must remain frozen")
    prompt_config = _prompt_config(config)
    training = config["training"]
    optimizer = torch.optim.AdamW(
        projector.parameters(),
        lr=float(training["projector_learning_rate"]),
        weight_decay=float(training["weight_decay"]),
    )
    accumulation = int(training["gradient_accumulation"])
    optimizer.zero_grad(set_to_none=True)
    global_row = 0
    updates = 0
    history: list[dict[str, Any]] = []
    started = time.perf_counter()
    for epoch in range(int(training["epochs"])):
        adapter.train()
        projector.train()
        ordered = sorted(
            training_rows,
            key=lambda row: stable_epoch_key(
                str(training["shared_epoch_order_namespace"]),
                seed,
                epoch,
                str(row["example_id"]),
            ),
        )
        epoch_loss = 0.0
        for row in ordered:
            global_row += 1
            _, input_ids, labels = build_sft_tensors(
                tokenizer,
                prompt_config,
                finding=str(row["finding"]),
                target_text=target_text(row),
            )
            source = tokens[str(row["example_id"])].unsqueeze(0).to(
                device=device, dtype=torch.float32
            )
            projected = projector(token_bundle(source))
            result = adapter.forward_sft(
                input_ids.to(device), projected, labels=labels.to(device)
            )
            loss = result["loss"]
            audit = result["audit"]
            if (
                not bool(torch.isfinite(loss))
                or audit["assistant_only_loss"] is not True
                or int(audit["placeholder_count"][0].item()) != 64
                or audit["pixel_inputs_used"] is not False
            ):
                raise FloatingPointError("R51 exact64 training contract failed")
            (loss / accumulation).backward()
            if global_row % accumulation == 0 or global_row == len(training_rows):
                torch.nn.utils.clip_grad_norm_(
                    projector.parameters(), float(training["gradient_clip_norm"])
                )
                optimizer.step()
                optimizer.zero_grad(set_to_none=True)
                updates += 1
            epoch_loss += float(loss.detach().cpu())
        history.append(
            {
                "epoch": epoch + 1,
                "mean_sft_loss": epoch_loss / len(ordered),
                "optimizer_updates_completed": updates,
                "elapsed_seconds": time.perf_counter() - started,
            }
        )
    if updates != int(training["expected_optimizer_updates"]):
        raise ValueError("R51 optimizer update-count drift")
    model.gradient_checkpointing_disable()
    model.config.use_cache = True
    first = evaluation_rows[0]
    first_source = tokens[str(first["example_id"])].unsqueeze(0).to(
        device=device, dtype=torch.float32
    )
    first_projected = projector(token_bundle(first_source))
    first_prompt = build_prompt_ids(
        tokenizer, prompt_config, finding=str(first["finding"])
    ).to(device)
    cache_audit = adapter.audit_first_step_cache_equivalence(
        first_prompt, first_projected
    )
    if cache_audit["passed"] is not True:
        raise PermissionError("R51 cache-equivalence audit failed")
    metrics, predictions = evaluate(
        adapter=adapter,
        projector=projector,
        tokenizer=tokenizer,
        config=prompt_config,
        rows=evaluation_rows,
        tokens=tokens,
        device=device,
    )
    output.mkdir(parents=True, exist_ok=False)
    checkpoint = output / "projector_checkpoint.pt"
    torch.save(
        {
            "schema": "visualvit.prta-gen.r51-matched-interface-checkpoint.v1",
            "seed": seed,
            "arm": arm,
            "projector": projector.state_dict(),
        },
        checkpoint,
    )
    class_to_index = {label: index for index, label in enumerate(PROGRESSION_CLASSES)}
    result = {
        "schema": "visualvit.prta-gen.r51-matched-interface-arm.v1",
        "status": config["result_statuses"]["arm_complete"],
        "protocol_id": config["protocol_id"],
        "arm": arm,
        "method_provenance": config["methods"][arm]["provenance"],
        "translation": config["methods"][arm]["translation"],
        "translation_trainable_parameters": 0,
        "seed": seed,
        "classes": list(PROGRESSION_CLASSES),
        "training_rows": len(training_rows),
        "training_example_ids_sha256": hashlib.sha256(
            "\n".join(str(row["example_id"]) for row in training_rows).encode("utf-8")
        ).hexdigest().upper(),
        "evaluation_rows": len(evaluation_rows),
        "evaluation_patient_ids": [str(row["patient_id"]) for row in evaluation_rows],
        "evaluation_example_ids": [str(row["example_id"]) for row in evaluation_rows],
        "targets": [class_to_index[str(row["progression"])] for row in evaluation_rows],
        "predictions": predictions,
        "metrics": metrics,
        "training_history": history,
        "optimizer_updates": updates,
        "projector_initialization_sha256": initialization_sha256,
        "qwen_trainable_parameters": int(model_audit["trainable_parameter_count"]),
        "projector_trainable_parameters": sum(
            parameter.numel()
            for parameter in projector.parameters()
            if parameter.requires_grad
        ),
        "cache_equivalence_audit": cache_audit,
        "checkpoint": str(checkpoint),
        "checkpoint_bytes": checkpoint.stat().st_size,
        "exact64_tokens_used": True,
        "common_per_token_rms_used": True,
        "pixel_inputs_used": False,
        "shared_task": config["prompt"]["shared_task"],
        "elapsed_seconds": time.perf_counter() - started,
        "peak_cuda_allocated_bytes": int(torch.cuda.max_memory_allocated(device)),
        "evaluation_model_outcomes_read_once": True,
        "protected_300_dev_read": False,
        "revealed_483_test_read": False,
        "gold_outcomes_read": False,
        "external_outcomes_read": False,
        "clinical_claim_allowed": False,
    }
    write_json(output / "result.json", result)
    return result


def receipt_summary(result: dict[str, Any]) -> dict[str, Any]:
    hidden = {
        "evaluation_patient_ids",
        "evaluation_example_ids",
        "targets",
        "predictions",
    }
    return {key: value for key, value in result.items() if key not in hidden}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one frozen R51 matched-interface arm")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--arm")
    parser.add_argument("--device")
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    if args.preflight_only:
        result = preflight(args.config)
    else:
        if args.seed is None or args.arm is None or args.device is None:
            raise ValueError("R51 run requires seed, arm, and device")
        result = run_arm(args.config, args.seed, str(args.arm), str(args.device))
    print(json.dumps(receipt_summary(result), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
