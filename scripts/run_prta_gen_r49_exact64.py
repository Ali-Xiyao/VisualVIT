from __future__ import annotations

# ruff: noqa: E402

import argparse
import copy
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

from scripts.audit_prta_gen_r44_independent_support import sha256_file
from scripts.build_prta_gen_r40b_smoke_cohort import read_json, write_json
from scripts.r39_common import token_bundle
from scripts.run_prta_gen_r40b_overfit_smoke import (
    build_prompt_ids,
    build_sft_tensors,
    parse_generated_object,
)
from scripts.run_prta_gen_r40c_structured_generalization import load_token_variants
from scripts.run_prta_gen_r41a_progression_sft import per_class_recall, target_text
from visualvit.prta_gen import PROGRESSION_CLASSES
from visualvit.qualification import macro_f1
from visualvit.qwen_adapter import GenerativeVLMAdapter
from visualvit.tier_token_projector import TierTokenProjector


CONFIG_STATUS = "FROZEN_PRTA_GEN_R49_UNIFIED_THREE_WAY"
EXACT64_ARMS = ("naive_exact64", "prta_exact64")


def _verify(path: Path, expected_bytes: int, expected_sha256: str) -> None:
    if (
        not path.is_file()
        or path.stat().st_size != expected_bytes
        or sha256_file(path) != expected_sha256
    ):
        raise PermissionError(f"R49 authority drift: {path}")


def _rows(roster: dict[str, Any], partitions: list[str]) -> list[dict[str, Any]]:
    rows = [
        row
        for partition in partitions
        for row in roster["partitions"][partition]["rows"]
    ]
    if len({str(row["patient_id"]) for row in rows}) != len(rows):
        raise ValueError("R49 patient overlap or duplicate row")
    return rows


def _prompt_config(config: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(config)
    prompt = result["prompt"]
    prompt["user_prefix"] = (
        str(prompt["exact64_modality_prefix"])
        + str(prompt["shared_task"])
        + str(prompt["exact64_modality_suffix"])
    )
    return result


def validate_authority(
    config_path: Path,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    config = read_json(config_path)
    if config.get("status") != CONFIG_STATUS:
        raise PermissionError("R49 exact64 config is not frozen")
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
        raise PermissionError("R49 roster contract drift")
    training_rows = _rows(roster, [str(authority["training_partition"])])
    evaluation_rows = _rows(
        roster, [str(value) for value in authority["evaluation_partitions"]]
    )
    if (
        len(training_rows) != int(authority["training_rows"])
        or len(evaluation_rows) != int(authority["evaluation_rows"])
        or {str(row["patient_id"]) for row in training_rows}
        & {str(row["patient_id"]) for row in evaluation_rows}
    ):
        raise PermissionError("R49 train/evaluation roster drift")
    naive = config["naive_exact64"]
    if naive["token_index_bytes"] is None or naive["token_index_sha256"] is None:
        raise PermissionError("R49 naive token index has not been hash-pinned")
    _verify(
        Path(naive["token_index"]),
        int(naive["token_index_bytes"]),
        str(naive["token_index_sha256"]),
    )
    naive_index = read_json(Path(naive["token_index"]))
    if (
        naive_index.get("status") != naive["required_token_status"]
        or naive_index.get("protocol_id") != config["protocol_id"]
        or naive_index.get("roster_sha256") != authority["roster_sha256"]
        or naive_index.get("rows") != naive["cache_rows"]
        or naive_index.get("patch_positions") != naive["patch_positions"]
        or naive_index.get("reserved_positions_exact_zero") is not True
    ):
        raise PermissionError("R49 naive token-index contract drift")
    for source in config["prta_exact64"]["token_indices"]:
        path = Path(source["path"])
        _verify(path, int(source["bytes"]), str(source["sha256"]))
        index = read_json(path)
        if index.get("status") != source["status"]:
            raise PermissionError("R49 PRTA token-index status drift")
    model = config["model"]
    model_path = Path(model["path"])
    for name, bytes_key, hash_key in (
        ("config.json", "config_bytes", "config_sha256"),
        ("preprocessor_config.json", "preprocessor_config_bytes", "preprocessor_config_sha256"),
        ("model.safetensors.index.json", "weight_index_bytes", "weight_index_sha256"),
    ):
        _verify(model_path / name, int(model[bytes_key]), str(model[hash_key]))
    return config, roster, training_rows, evaluation_rows


def _load_arm_tokens(
    config: dict[str, Any],
    arm: str,
    rows: list[dict[str, Any]],
) -> dict[str, Tensor]:
    requested = {str(row["example_id"]) for row in rows}
    tokens: dict[str, Tensor] = {}
    patients: dict[str, str] = {}
    findings: dict[str, str] = {}
    if arm == "naive_exact64":
        sources = [
            {
                "path": config["naive_exact64"]["token_index"],
                "token_key": config["naive_exact64"]["token_key"],
            }
        ]
    elif arm == "prta_exact64":
        sources = [
            {
                "path": source["path"],
                "token_key": config["prta_exact64"]["token_key"],
            }
            for source in config["prta_exact64"]["token_indices"]
        ]
    else:
        raise ValueError("unknown R49 exact64 arm")
    remaining = set(requested)
    for source in sources:
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
            raise ValueError("R49 token source overlap")
        tokens.update(loaded["source"])
        patients.update(patient_receipt)
        findings.update(finding_receipt)
        remaining -= take
    if remaining:
        raise ValueError(f"R49 token source missing {len(remaining)} rows")
    for row in rows:
        example_id = str(row["example_id"])
        tensor = tokens[example_id]
        if (
            patients[example_id] != str(row["patient_id"])
            or findings[example_id] != str(row["finding"])
            or tuple(tensor.shape) != (64, 768)
            or not bool(tensor[60:64].eq(0).all())
        ):
            raise ValueError("R49 roster/token alignment drift")
    return tokens


def _metrics(rows: list[dict[str, Any]], predictions: list[int]) -> dict[str, Any]:
    class_to_index = {label: index for index, label in enumerate(PROGRESSION_CLASSES)}
    targets = [class_to_index[str(row["progression"])] for row in rows]
    recalls = per_class_recall(targets, predictions, class_count=len(PROGRESSION_CLASSES))
    return {
        "row_count": len(rows),
        "progression_accuracy": sum(
            target == prediction
            for target, prediction in zip(targets, predictions, strict=True)
        )
        / len(rows),
        "macro_f1": macro_f1(targets, predictions, class_count=len(PROGRESSION_CLASSES)),
        "per_class_recall": {
            label: recalls[index] for index, label in enumerate(PROGRESSION_CLASSES)
        },
    }


def _state_sha256(module: torch.nn.Module) -> str:
    digest = hashlib.sha256()
    for name, tensor in module.state_dict().items():
        digest.update(name.encode("utf-8"))
        digest.update(tensor.detach().cpu().contiguous().numpy().tobytes())
    return digest.hexdigest().upper()


def stable_epoch_key(namespace: str, seed: int, epoch: int, example_id: str) -> str:
    return hashlib.sha256(
        f"{namespace}|{seed}|{epoch}|{example_id}".encode("utf-8")
    ).hexdigest()


def preflight(config_path: Path) -> dict[str, Any]:
    config, _, training_rows, evaluation_rows = validate_authority(config_path)
    for arm in EXACT64_ARMS:
        output = Path(config["runtime"]["exact64_root"]) / f"seed_17/{arm}"
        if output.exists():
            raise FileExistsError(f"R49 exact64 output is not fresh: {output}")
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(
        config["model"]["path"], local_files_only=True, trust_remote_code=False
    )
    placeholder = int(tokenizer.convert_tokens_to_ids(config["model"]["sentinel_token"]))
    if placeholder != int(config["model"]["placeholder_token_id"]):
        raise ValueError("R49 sentinel token drift")
    prompt_config = _prompt_config(config)
    if str(config["prompt"]["shared_task"]) not in prompt_config["prompt"]["user_prefix"]:
        raise PermissionError("R49 shared task contract missing")
    return {
        "schema": "visualvit.prta-gen.r49-exact64-runner-preflight.v1",
        "status": config["result_statuses"]["runner_preflight_pass"],
        "protocol_id": config["protocol_id"],
        "training_rows": len(training_rows),
        "evaluation_rows": len(evaluation_rows),
        "arms": list(EXACT64_ARMS),
        "placeholder_token_id": placeholder,
        "shared_task_contract_present": True,
        "all_outputs_fresh": True,
        "gpu_training_started": False,
    }


def evaluate(
    *,
    adapter: GenerativeVLMAdapter,
    projector: TierTokenProjector,
    tokenizer: Any,
    config: dict[str, Any],
    rows: list[dict[str, Any]],
    tokens: dict[str, Tensor],
    device: torch.device,
) -> tuple[dict[str, Any], list[int]]:
    adapter.eval()
    projector.eval()
    expected_keys = [str(value) for value in config["target"]["schema_keys_in_order"]]
    progression_values = {str(value) for value in config["target"]["progression_values"]}
    class_to_index = {label: index for index, label in enumerate(PROGRESSION_CLASSES)}
    predictions: list[int] = []
    valid = 0
    finding_correct = 0
    with torch.no_grad():
        for row in rows:
            source = tokens[str(row["example_id"])].unsqueeze(0).to(
                device=device, dtype=torch.float32
            )
            projected = projector(token_bundle(source))
            prompt = build_prompt_ids(tokenizer, config, finding=str(row["finding"])).to(device)
            generated, audit = adapter.generate_text(
                prompt,
                projected,
                max_new_tokens=int(config["target"]["max_target_tokens"]),
                eos_token_id=tokenizer.eos_token_id,
                pad_token_id=tokenizer.pad_token_id,
                return_audit=True,
            )
            if (
                audit["visual_injection_calls"] != 1
                or audit["subsequent_placeholder_replacements"] != 0
                or audit["pixel_inputs_used"] is not False
            ):
                raise PermissionError("R49 exact64 injection audit failed")
            text = tokenizer.decode(generated[0].detach().cpu().tolist(), skip_special_tokens=True)
            parsed = parse_generated_object(
                text, expected_keys=expected_keys, progression_values=progression_values
            )
            finding_ok = parsed is not None and parsed["finding"] == str(row["finding"])
            valid += parsed is not None
            finding_correct += finding_ok
            predictions.append(class_to_index[parsed["progression"]] if finding_ok else -1)
    metrics = _metrics(rows, predictions)
    metrics.update(
        {
            "schema_validity": valid / len(rows),
            "finding_echo_accuracy": finding_correct / len(rows),
            "invalid_or_wrong_finding_predictions": sum(value < 0 for value in predictions),
        }
    )
    return metrics, predictions


def run_arm(config_path: Path, seed: int, arm: str, device_name: str) -> dict[str, Any]:
    config, _, training_rows, evaluation_rows = validate_authority(config_path)
    if seed not in [int(value) for value in config["training"]["seeds"]]:
        raise ValueError("R49 seed is not registered")
    if arm not in EXACT64_ARMS:
        raise ValueError("R49 exact64 arm is not registered")
    output = Path(config["runtime"]["exact64_root"]) / f"seed_{seed}" / arm
    if output.exists():
        raise FileExistsError(output)
    all_rows = training_rows + evaluation_rows
    tokens = _load_arm_tokens(config, arm, all_rows)
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    device = torch.device(device_name)
    if device.type != "cuda" or not torch.cuda.is_available():
        raise RuntimeError("R49 exact64 requires explicit CUDA")
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
    placeholder = int(tokenizer.convert_tokens_to_ids(config["model"]["sentinel_token"]))
    if placeholder != int(config["model"]["placeholder_token_id"]):
        raise ValueError("R49 sentinel token drift")
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
        raise PermissionError("R49 Qwen must remain frozen")
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
                raise FloatingPointError("R49 exact64 training contract failed")
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
        raise ValueError("R49 optimizer update-count drift")
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
    cache_audit = adapter.audit_first_step_cache_equivalence(first_prompt, first_projected)
    if cache_audit["passed"] is not True:
        raise PermissionError("R49 cache-equivalence audit failed")
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
            "schema": "visualvit.prta-gen.r49-exact64-checkpoint.v1",
            "seed": seed,
            "arm": arm,
            "projector": projector.state_dict(),
        },
        checkpoint,
    )
    class_to_index = {label: index for index, label in enumerate(PROGRESSION_CLASSES)}
    result = {
        "schema": "visualvit.prta-gen.r49-exact64-arm.v1",
        "status": config["result_statuses"]["exact64_arm_complete"],
        "protocol_id": config["protocol_id"],
        "arm": arm,
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
            parameter.numel() for parameter in projector.parameters() if parameter.requires_grad
        ),
        "cache_equivalence_audit": cache_audit,
        "checkpoint": str(checkpoint),
        "checkpoint_bytes": checkpoint.stat().st_size,
        "exact64_tokens_used": True,
        "pixel_inputs_used": False,
        "shared_task": config["prompt"]["shared_task"],
        "elapsed_seconds": time.perf_counter() - started,
        "peak_cuda_allocated_bytes": int(torch.cuda.max_memory_allocated(device)),
        "gold_outcomes_read": False,
        "external_outcomes_read": False,
        "clinical_claim_allowed": False,
    }
    write_json(output / "result.json", result)
    return result


def receipt_summary(result: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in result.items()
        if key
        not in {
            "evaluation_patient_ids",
            "evaluation_example_ids",
            "targets",
            "predictions",
        }
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one R49 exact-64 arm")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--arm")
    parser.add_argument("--device")
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    if args.preflight_only:
        result = preflight(args.config)
    else:
        if args.seed is None or args.arm is None or args.device is None:
            raise ValueError("R49 exact64 run requires seed, arm, and device")
        result = run_arm(args.config, args.seed, str(args.arm), str(args.device))
    print(json.dumps(receipt_summary(result), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
