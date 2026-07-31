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
from scripts.build_prta_gen_r41a_roster import (
    CONFIG_STATUS,
    preflight as roster_preflight,
    validate_authority,
)
from scripts.r39_common import token_bundle
from scripts.run_prta_gen_r40b_overfit_smoke import (
    build_prompt_ids,
    build_sft_tensors,
    parse_generated_object,
)
from scripts.run_prta_gen_r40c_structured_generalization import (
    load_token_variants,
)
from visualvit.prta_gen import PROGRESSION_CLASSES
from visualvit.qualification import macro_f1
from visualvit.qwen_adapter import GenerativeVLMAdapter, apply_attention_lora
from visualvit.tier_token_projector import TierTokenProjector


ARM_STATUS = "PASS_PRTA_GEN_R41A_ARM_EVALUATION"
MODEL_ARMS = ("g0_projector_only", "g1_attention_lora")
EVALUATION_ARMS = ("true_pair", "current_only", "query_only", "prior_shuffle")


def _expected_config_status(config: dict[str, Any]) -> str:
    if config.get("stage_tag") == "R44A":
        return "FROZEN_PRTA_GEN_R44A_CROSS_SOURCE_SILVER_SFT"
    return CONFIG_STATUS


def _validate_stage_authority(
    config_path: Path, config: dict[str, Any]
) -> None:
    if config.get("stage_tag") == "R44A":
        from scripts.build_prta_gen_r44a_roster import (
            validate_authority as validate_r44a_authority,
        )

        validate_r44a_authority(config)
        return
    validate_authority(config)


def _stage_roster_preflight(
    config_path: Path, config: dict[str, Any]
) -> dict[str, Any]:
    if config.get("stage_tag") == "R44A":
        from scripts.build_prta_gen_r44a_roster import (
            preflight as r44a_roster_preflight,
        )

        return r44a_roster_preflight(config_path)
    return roster_preflight(config_path)


def stable_epoch_key(seed: int, arm: str, epoch: int, example_id: str) -> str:
    return hashlib.sha256(
        f"r41a|{seed}|{arm}|{epoch}|{example_id}".encode()
    ).hexdigest()


def target_text(row: dict[str, Any]) -> str:
    return json.dumps(
        {
            "finding": str(row["finding"]),
            "progression": str(row["progression"]),
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


def per_class_recall(
    targets: list[int], predictions: list[int], *, class_count: int
) -> list[float]:
    if len(targets) != len(predictions) or not targets:
        raise ValueError("R41A recall inputs must be aligned and non-empty")
    recalls = []
    for label in range(class_count):
        positives = sum(value == label for value in targets)
        if positives == 0:
            raise ValueError("R41A recall requires every progression class")
        true_positives = sum(
            target == label and prediction == label
            for target, prediction in zip(targets, predictions, strict=True)
        )
        recalls.append(true_positives / positives)
    return recalls


def _rows_from_roster(
    roster: dict[str, Any], partition: str
) -> list[dict[str, Any]]:
    rows = list(roster["partitions"][partition]["rows"])
    expected = int(roster["partitions"][partition]["row_count"])
    if len(rows) != expected:
        raise ValueError(f"R41A {partition} roster row-count drift")
    return rows


def validate_roster(
    config: dict[str, Any], roster: dict[str, Any]
) -> None:
    if (
        roster.get("status") != config["result_statuses"]["roster_pass"]
        or roster.get("protocol_id") != config["protocol_id"]
        or roster.get("patient_sets_disjoint") is not True
        or roster.get("one_row_per_patient") is not True
        or roster.get("resplit_allowed") is not False
        or roster.get("excluded_observed_patient_count")
        != config["source"]["expected_excluded_patient_count"]
        or roster.get("excluded_observed_patients_absent") is not True
        or roster.get("resolved_patient_reserve")
        < config["roster"]["minimum_unselected_resolved_patient_reserve"]
        or roster.get("development_outcomes_read") is not False
        or roster.get("r40c_outcomes_used_for_roster_selection") is not False
        or roster.get("protected_300_dev_read") is not False
        or roster.get("revealed_483_test_read") is not False
        or roster.get("gold_outcomes_read") is not False
        or roster.get("external_outcomes_read") is not False
    ):
        raise PermissionError("R41A roster receipt drift")
    for partition in ("train", "development"):
        payload = roster["partitions"][partition]
        if (
            payload["patient_count"]
            != config["roster"][f"{partition}_patients"]
            or payload["row_count"]
            != config["roster"][f"{partition}_patients"]
            or payload["progression_class_counts"]
            != config["roster"][f"{partition}_class_counts"]
        ):
            raise PermissionError(f"R41A {partition} roster count drift")


def _trainable_summary(audit: dict[str, Any]) -> dict[str, Any]:
    parameter_count = int(audit["parameter_count"])
    trainable_count = int(audit["trainable_parameter_count"])
    return {
        "total_parameters": parameter_count,
        "trainable_parameters": trainable_count,
        "frozen_parameters": parameter_count - trainable_count,
        "unexpected_trainable_parameter_count": len(
            audit["unexpected_trainable_parameter_names"]
        ),
        "trainable_boundary_pass": bool(audit["trainable_boundary_pass"]),
    }


def evaluate_generation(
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
    expected_keys = [
        str(value) for value in config["target"]["schema_keys_in_order"]
    ]
    progression_values = {
        str(value) for value in config["target"]["progression_values"]
    }
    class_to_index = {
        label: index for index, label in enumerate(PROGRESSION_CLASSES)
    }
    targets = [
        class_to_index[str(row["progression"])] for row in rows
    ]
    predictions: list[int] = []
    valid = 0
    finding_correct = 0
    progression_correct = 0
    with torch.no_grad():
        for row in rows:
            prompt = build_prompt_ids(
                tokenizer, config, finding=str(row["finding"])
            ).to(device)
            source = tokens[str(row["example_id"])].unsqueeze(0).to(
                device=device, dtype=torch.float32
            )
            generated, audit = adapter.generate_text(
                prompt,
                projector(token_bundle(source)),
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
                raise PermissionError("R41A generation injection audit failed")
            text = tokenizer.decode(
                generated[0].detach().cpu().tolist(),
                skip_special_tokens=True,
            )
            parsed = parse_generated_object(
                text,
                expected_keys=expected_keys,
                progression_values=progression_values,
            )
            schema_ok = parsed is not None
            finding_ok = (
                parsed is not None
                and parsed["finding"] == str(row["finding"])
            )
            valid += schema_ok
            finding_correct += finding_ok
            if finding_ok:
                prediction = class_to_index[parsed["progression"]]
            else:
                prediction = -1
            predictions.append(prediction)
            progression_correct += (
                prediction == class_to_index[str(row["progression"])]
            )
    recalls = per_class_recall(
        targets, predictions, class_count=len(PROGRESSION_CLASSES)
    )
    count = len(rows)
    return (
        {
            "row_count": count,
            "schema_validity": valid / count,
            "finding_echo_accuracy": finding_correct / count,
            "progression_accuracy": progression_correct / count,
            "macro_f1": macro_f1(
                targets,
                predictions,
                class_count=len(PROGRESSION_CLASSES),
            ),
            "per_class_recall": {
                label: recalls[index]
                for index, label in enumerate(PROGRESSION_CLASSES)
            },
            "invalid_or_wrong_finding_predictions": sum(
                value < 0 for value in predictions
            ),
        },
        predictions,
    )


def run_arm(
    *,
    config_path: Path,
    roster_path: Path,
    seed: int,
    model_arm: str,
    device_name: str,
) -> dict[str, Any]:
    config = read_json(config_path)
    if config.get("status") != _expected_config_status(config):
        raise PermissionError("R41A config is not frozen")
    if seed not in [int(value) for value in config["training"]["seeds"]]:
        raise ValueError("R41A Seed is not registered")
    if model_arm not in MODEL_ARMS:
        raise ValueError("R41A model arm is not registered")
    _validate_stage_authority(config_path, config)
    roster = read_json(roster_path)
    validate_roster(config, roster)
    output_root = (
        Path(config["runtime"]["root"]) / f"seed_{seed}" / model_arm
    )
    if output_root.exists():
        raise FileExistsError(f"R41A arm output must be fresh: {output_root}")
    training_rows = _rows_from_roster(roster, "train")
    development_rows = _rows_from_roster(roster, "development")
    all_rows = training_rows + development_rows
    token_index = read_json(Path(config["source"]["token_index"]))
    if config.get("stage_tag") == "R44A":
        from scripts.audit_prta_gen_r44_independent_support import sha256_file

        if (
            token_index.get("status")
            != config["source"]["required_token_status"]
            or token_index.get("protocol_id") != config["protocol_id"]
            or token_index.get("roster_sha256") != sha256_file(roster_path)
            or token_index.get("labels_in_cache") is not False
            or token_index.get("sentences_in_cache") is not False
            or token_index.get("pixel_inputs_used_by_qwen") is not False
            or token_index.get("protected_300_dev_read") is not False
            or token_index.get("revealed_483_test_read") is not False
            or token_index.get("gold_outcomes_read") is not False
            or token_index.get("external_outcomes_read") is not False
        ):
            raise PermissionError("R44A token-cache receipt drift")
    token_keys = {
        str(arm): str(key)
        for arm, key in config["source"]["token_variants"].items()
    }
    loaded, patient_receipt, finding_receipt = load_token_variants(
        token_index,
        example_ids={str(row["example_id"]) for row in all_rows},
        token_keys=token_keys,
    )
    for row in all_rows:
        example_id = str(row["example_id"])
        if (
            patient_receipt[example_id] != str(row["patient_id"])
            or finding_receipt[example_id] != str(row["finding"])
        ):
            raise ValueError("R41A roster/token alignment drift")
    loaded["query_only"] = {
        str(row["example_id"]): torch.zeros(
            (64, 768), dtype=torch.float32
        )
        for row in development_rows
    }
    device = torch.device(device_name)
    if device.type != "cuda" or not torch.cuda.is_available():
        raise RuntimeError("R41A arm execution requires an explicit CUDA device")
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
    if (
        placeholder_id != int(config["model"]["placeholder_token_id"])
        or tokenizer(
            config["model"]["sentinel_token"], add_special_tokens=False
        )["input_ids"]
        != [placeholder_id]
    ):
        raise ValueError("R41A sentinel receipt drift")
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
    if model_arm == "g0_projector_only":
        model.requires_grad_(False)
    else:
        lora = config["adapter"]["arms"][model_arm]["lora"]
        model = apply_attention_lora(
            model,
            rank=int(lora["rank"]),
            alpha=int(lora["alpha"]),
            dropout=float(lora["dropout"]),
            target_modules=tuple(lora["target_modules"]),
        )
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
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
    trainable_audit = adapter.trainable_parameter_audit()
    if not trainable_audit["trainable_boundary_pass"]:
        raise PermissionError("R41A unexpected trainable Qwen parameter")
    if model_arm == "g0_projector_only" and int(
        trainable_audit["trainable_parameter_count"]
    ) != 0:
        raise PermissionError("R41A G0 Qwen must be fully frozen")
    if model_arm == "g1_attention_lora" and int(
        trainable_audit["trainable_parameter_count"]
    ) <= 0:
        raise PermissionError("R41A G1 LoRA parameters are absent")
    training = config["training"]
    parameter_groups: list[dict[str, Any]] = [
        {
            "params": list(projector.parameters()),
            "lr": float(training["projector_learning_rate"]),
        }
    ]
    qwen_trainable = [
        parameter for parameter in adapter.parameters() if parameter.requires_grad
    ]
    if qwen_trainable:
        parameter_groups.append(
            {
                "params": qwen_trainable,
                "lr": float(training["lora_learning_rate"]),
            }
        )
    optimizer = torch.optim.AdamW(
        parameter_groups,
        weight_decay=float(training["weight_decay"]),
    )
    accumulation = int(training["gradient_accumulation"])
    optimizer.zero_grad(set_to_none=True)
    history = []
    global_row = 0
    updates = 0
    started = time.perf_counter()
    for epoch in range(int(training["epochs"])):
        adapter.train()
        projector.train()
        ordered = sorted(
            training_rows,
            key=lambda row: stable_epoch_key(
                seed, model_arm, epoch, str(row["example_id"])
            ),
        )
        epoch_loss = 0.0
        for row in ordered:
            global_row += 1
            text = target_text(row)
            _, input_ids, labels = build_sft_tensors(
                tokenizer,
                config,
                finding=str(row["finding"]),
                target_text=text,
            )
            source = loaded["true_pair"][str(row["example_id"])].unsqueeze(0)
            projected = projector(
                token_bundle(source.to(device=device, dtype=torch.float32))
            )
            result = adapter.forward_sft(
                input_ids.to(device),
                projected,
                labels=labels.to(device),
            )
            loss = result["loss"]
            audit = result["audit"]
            if (
                not bool(torch.isfinite(loss))
                or audit["assistant_only_loss"] is not True
                or int(audit["placeholder_count"][0].item()) != 64
                or audit["pixel_inputs_used"] is not False
            ):
                raise FloatingPointError("R41A training contract failed")
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
            epoch_loss += float(loss.detach().cpu())
        history.append(
            {
                "epoch": epoch + 1,
                "mean_loss": epoch_loss / len(ordered),
                "optimizer_updates_completed": updates,
                "elapsed_seconds": time.perf_counter() - started,
            }
        )
    if updates != int(training["expected_optimizer_updates"]):
        raise ValueError("R41A optimizer update-count drift")
    model.gradient_checkpointing_disable()
    model.config.use_cache = True
    first = development_rows[0]
    first_prompt = build_prompt_ids(
        tokenizer, config, finding=str(first["finding"])
    ).to(device)
    first_source = loaded["true_pair"][str(first["example_id"])].unsqueeze(0)
    with torch.no_grad():
        cache_audit = adapter.audit_first_step_cache_equivalence(
            first_prompt,
            projector(
                token_bundle(
                    first_source.to(device=device, dtype=torch.float32)
                )
            ),
        )
    if cache_audit["passed"] is not True:
        raise PermissionError("R41A cached/uncached first-step drift")
    metrics: dict[str, Any] = {}
    predictions: dict[str, list[int]] = {}
    for evaluation_arm in EVALUATION_ARMS:
        arm_metrics, arm_predictions = evaluate_generation(
            adapter=adapter,
            projector=projector,
            tokenizer=tokenizer,
            config=config,
            rows=development_rows,
            tokens=loaded[evaluation_arm],
            device=device,
        )
        metrics[evaluation_arm] = arm_metrics
        predictions[evaluation_arm] = arm_predictions
    output_root.mkdir(parents=True, exist_ok=False)
    checkpoint = output_root / "trainable_checkpoint.pt"
    torch.save(
        {
            "schema": config.get("runtime_contract", {}).get(
                "checkpoint_schema",
                "visualvit.prta-gen.r41a-trainable-checkpoint.v1",
            ),
            "seed": seed,
            "model_arm": model_arm,
            "projector": projector.state_dict(),
            "lora": {
                name: tensor.detach().cpu()
                for name, tensor in adapter.state_dict().items()
                if "lora_" in name
            },
        },
        checkpoint,
    )
    class_to_index = {
        label: index for index, label in enumerate(PROGRESSION_CLASSES)
    }
    result = {
        "schema": config.get("runtime_contract", {}).get(
            "arm_result_schema",
            "visualvit.prta-gen.r41a-arm-result.v1",
        ),
        "status": config["result_statuses"]["arm_complete"],
        "protocol_id": config["protocol_id"],
        "study_tier": config["study_tier"],
        "seed": seed,
        "model_arm": model_arm,
        "classes": PROGRESSION_CLASSES,
        "training_rows": len(training_rows),
        "training_patients": len(
            {str(row["patient_id"]) for row in training_rows}
        ),
        "development_rows": len(development_rows),
        "development_patients": len(
            {str(row["patient_id"]) for row in development_rows}
        ),
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
        "history": history,
        "optimizer_updates": updates,
        "trainable_parameter_audit": _trainable_summary(trainable_audit),
        "projector_parameter_count": sum(
            parameter.numel() for parameter in projector.parameters()
        ),
        "cache_equivalence_audit": cache_audit,
        "checkpoint": str(checkpoint),
        "checkpoint_bytes": checkpoint.stat().st_size,
        "exact64_tokens_used": True,
        "free_greedy_generation_evaluated": True,
        "pixel_inputs_used": False,
        "qwen_free_generation_survival_unlocked": False,
        "r42_unlocked": False,
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
    if config.get("status") != _expected_config_status(config):
        raise PermissionError("R41A config is not frozen")
    roster_receipt = _stage_roster_preflight(config_path, config)
    if tuple(config["training"]["arms"]) != MODEL_ARMS:
        raise ValueError("R41A model-arm registry drift")
    if tuple(config["evaluation"]["arms"]) != EVALUATION_ARMS:
        raise ValueError("R41A evaluation-arm registry drift")
    expected_updates = math.ceil(
        int(config["roster"]["train_patients"])
        * int(config["training"]["epochs"])
        / int(config["training"]["gradient_accumulation"])
    )
    if expected_updates != int(
        config["training"]["expected_optimizer_updates"]
    ):
        raise ValueError("R41A expected optimizer-update drift")
    model_path = Path(config["model"]["path"])
    if not model_path.is_dir():
        raise FileNotFoundError("R41A local Qwen model is absent")
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(
        model_path,
        local_files_only=True,
        trust_remote_code=False,
    )
    placeholder = int(
        tokenizer.convert_tokens_to_ids(config["model"]["sentinel_token"])
    )
    if placeholder != int(config["model"]["placeholder_token_id"]):
        raise ValueError("R41A tokenizer sentinel drift")
    sample = {
        "finding": config["target"]["finding_values"][0],
        "progression": config["target"]["progression_values"][0],
    }
    prompt, input_ids, labels = build_sft_tensors(
        tokenizer,
        config,
        finding=str(sample["finding"]),
        target_text=target_text(sample),
    )
    if (
        int(prompt.eq(placeholder).sum()) != 64
        or input_ids.shape != labels.shape
        or int(labels.ne(-100).sum()) <= 0
    ):
        raise ValueError("R41A tokenizer SFT contract drift")
    return {
        "schema": config.get("runtime_contract", {}).get(
            "runner_preflight_schema",
            "visualvit.prta-gen.r41a-runner-preflight.v1",
        ),
        "status": config["result_statuses"].get(
            "runner_preflight",
            "PASS_PRTA_GEN_R41A_RUNNER_PREFLIGHT",
        ),
        "protocol_id": config["protocol_id"],
        "roster_preflight_status": roster_receipt["status"],
        "model_arms": list(MODEL_ARMS),
        "evaluation_arms": list(EVALUATION_ARMS),
        "seeds": [int(value) for value in config["training"]["seeds"]],
        "expected_optimizer_updates": expected_updates,
        "placeholder_count": int(prompt.eq(placeholder).sum()),
        "assistant_target_tokens": int(labels.ne(-100).sum()),
        "model_local": True,
        "gpu_training_started": False,
        "protected_300_dev_read": False,
        "revealed_483_test_read": False,
        "gold_outcomes_read": False,
        "external_outcomes_read": False,
        "scientific_claim_allowed": False,
    }


def receipt_summary(result: dict[str, Any]) -> dict[str, Any]:
    if "runner-preflight" in str(result.get("schema", "")):
        return dict(result)
    keys = (
        "schema",
        "status",
        "protocol_id",
        "study_tier",
        "seed",
        "model_arm",
        "training_rows",
        "training_patients",
        "development_rows",
        "development_patients",
        "metrics",
        "history",
        "optimizer_updates",
        "trainable_parameter_audit",
        "projector_parameter_count",
        "cache_equivalence_audit",
        "checkpoint",
        "checkpoint_bytes",
        "exact64_tokens_used",
        "free_greedy_generation_evaluated",
        "pixel_inputs_used",
        "qwen_free_generation_survival_unlocked",
        "r42_unlocked",
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
        description="Preflight or run one frozen R41A Seed/model arm"
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--roster", type=Path)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--model-arm")
    parser.add_argument("--device")
    parser.add_argument("--preflight-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.preflight_only:
        if any(
            value is not None
            for value in (
                args.roster,
                args.seed,
                args.model_arm,
                args.device,
            )
        ):
            raise ValueError("R41A preflight accepts only --config")
        result = preflight(args.config)
    else:
        if (
            args.roster is None
            or args.seed is None
            or args.model_arm is None
            or args.device is None
        ):
            raise ValueError(
                "R41A arm run requires roster, seed, model-arm, and device"
            )
        result = run_arm(
            config_path=args.config,
            roster_path=args.roster,
            seed=args.seed,
            model_arm=args.model_arm,
            device_name=args.device,
        )
    print(json.dumps(receipt_summary(result), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
