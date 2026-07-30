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

from scripts.build_prta_gen_r40b_smoke_cohort import (
    COHORT_STATUS,
    CONFIG_STATUSES,
    read_json,
    write_json,
)
from scripts.r39_common import token_bundle
from visualvit.qwen_adapter import GenerativeVLMAdapter, apply_attention_lora
from visualvit.tier_token_projector import TierTokenProjector


PASS_STATUS = "PASS_PRTA_GEN_R40B_OVERFIT_SMOKE"
CONTRACT_STOP = "STOP_PRTA_GEN_R40B_ENGINEERING_CONTRACT"
UNDERFIT_STATUSES = {
    "registered_3epoch_v1": "STOP_R40B_REGISTERED_3EPOCH_UNDERFIT",
    "bounded_overfit_12epoch_v1": "STOP_R40B_BOUNDED_12EPOCH_UNDERFIT",
    "bounded_overfit_24epoch_v1": "STOP_R40B_BOUNDED_24EPOCH_UNDERFIT",
}


def result_status(
    config: dict[str, Any], kind: str, attempt_name: str
) -> str:
    registered = config.get("result_statuses")
    if registered is not None:
        if kind == "underfit":
            return str(registered["underfit_by_attempt"][attempt_name])
        return str(registered[kind])
    if kind == "pass":
        return PASS_STATUS
    if kind == "contract_stop":
        return CONTRACT_STOP
    return UNDERFIT_STATUSES[attempt_name]


def stable_epoch_key(seed: int, epoch: int, example_id: str) -> str:
    return hashlib.sha256(
        f"r40b|{seed}|{epoch}|{example_id}".encode("utf-8")
    ).hexdigest()


def registered_attempt(
    config: dict[str, Any], attempt_name: str
) -> tuple[int, dict[str, Any]]:
    matches = [
        (index, attempt)
        for index, attempt in enumerate(config["attempt_order"])
        if attempt["name"] == attempt_name
    ]
    if len(matches) != 1:
        raise ValueError("unregistered or duplicate R40B attempt")
    return matches[0]


def validate_attempt_authority(
    *,
    config: dict[str, Any],
    attempt_name: str,
    runtime_root: Path,
) -> dict[str, Any]:
    index, attempt = registered_attempt(config, attempt_name)
    if index == 0:
        if "allowed_only_after" in attempt:
            raise ValueError("first R40B attempt cannot require a predecessor")
        return attempt
    previous = config["attempt_order"][index - 1]
    required = attempt.get("allowed_only_after")
    previous_path = runtime_root / previous["name"] / "result.json"
    if not previous_path.exists():
        raise PermissionError(
            f"R40B attempt requires predecessor result: {previous_path}"
        )
    previous_result = read_json(previous_path)
    if previous_result.get("status") != required:
        raise PermissionError(
            "R40B attempt predecessor is not the registered underfit STOP"
        )
    return attempt


def load_selected_tokens(
    token_index: dict[str, Any],
    example_ids: set[str],
    *,
    token_key: str,
) -> dict[str, Tensor]:
    selected: dict[str, Tensor] = {}
    observed_patients: dict[str, str] = {}
    observed_findings: dict[str, str] = {}
    for shard_entry in token_index["shards"]:
        shard = torch.load(
            shard_entry["path"], map_location="cpu", weights_only=True
        )
        ids = [str(value) for value in shard["example_ids"]]
        for position, example_id in enumerate(ids):
            if example_id not in example_ids:
                continue
            if example_id in selected:
                raise ValueError(f"duplicate token example_id: {example_id}")
            tensor = shard[token_key][position]
            if tuple(tensor.shape) != (64, 768):
                raise ValueError("R40B source token shape drift")
            if not bool(torch.isfinite(tensor).all()):
                raise ValueError("R40B source tokens contain non-finite values")
            selected[example_id] = tensor.clone()
            observed_patients[example_id] = str(shard["patient_ids"][position])
            observed_findings[example_id] = str(shard["findings"][position])
        if len(selected) == len(example_ids):
            break
    missing = sorted(example_ids.difference(selected))
    if missing:
        raise ValueError(f"R40B token cache is missing {len(missing)} rows")
    selected["_patient_receipt"] = observed_patients  # type: ignore[assignment]
    selected["_finding_receipt"] = observed_findings  # type: ignore[assignment]
    return selected


def build_prompt_ids(
    tokenizer: Any,
    config: dict[str, Any],
    *,
    finding: str,
) -> Tensor:
    sentinel = str(config["model"]["sentinel_token"])
    visual_text = sentinel * int(config["model"]["token_budget"])
    messages = [
        {"role": "system", "content": str(config["prompt"]["system"])},
        {
            "role": "user",
            "content": (
                str(config["prompt"]["user_prefix"]).format(finding=finding)
                + visual_text
            ),
        },
    ]
    encoded = tokenizer.apply_chat_template(
        messages,
        tokenize=True,
        add_generation_prompt=bool(config["prompt"]["add_generation_prompt"]),
    )
    if isinstance(encoded, dict) or hasattr(encoded, "keys"):
        ids = encoded["input_ids"]
    else:
        ids = encoded
    if (
        not isinstance(ids, (list, tuple))
        or not ids
        or not all(isinstance(value, int) for value in ids)
    ):
        raise TypeError("R40B chat template did not return integer input IDs")
    prompt = torch.tensor([ids], dtype=torch.long)
    placeholder_id = int(config["model"]["placeholder_token_id"])
    expected = int(config["model"]["token_budget"])
    if int(prompt.eq(placeholder_id).sum().item()) != expected:
        raise ValueError("R40B prompt must contain exactly 64 placeholders")
    return prompt


def build_sft_tensors(
    tokenizer: Any,
    config: dict[str, Any],
    *,
    finding: str,
    target_text: str,
) -> tuple[Tensor, Tensor, Tensor]:
    prompt = build_prompt_ids(tokenizer, config, finding=finding)
    target_ids = tokenizer(
        target_text,
        add_special_tokens=False,
    )["input_ids"]
    if bool(config["target"]["append_eos"]):
        if tokenizer.eos_token_id is None:
            raise ValueError("R40B tokenizer must define eos_token_id")
        target_ids = [*target_ids, int(tokenizer.eos_token_id)]
    if not target_ids or len(target_ids) > int(
        config["target"]["max_target_tokens"]
    ):
        raise ValueError("R40B target token-length drift")
    target = torch.tensor([target_ids], dtype=torch.long)
    input_ids = torch.cat((prompt, target), dim=1)
    labels = torch.full_like(input_ids, -100)
    labels[:, prompt.shape[1] :] = target
    return prompt, input_ids, labels


def parse_generated_object(
    text: str,
    *,
    expected_keys: list[str],
    progression_values: set[str],
) -> dict[str, str] | None:
    try:
        value = json.loads(text.strip())
    except json.JSONDecodeError:
        return None
    if (
        not isinstance(value, dict)
        or list(value) != expected_keys
        or not all(isinstance(item, str) for item in value.values())
        or value["progression"] not in progression_values
    ):
        return None
    return {str(key): str(item) for key, item in value.items()}


def teacher_forced_metrics(
    *,
    adapter: GenerativeVLMAdapter,
    projector: TierTokenProjector,
    tokenizer: Any,
    config: dict[str, Any],
    rows: list[dict[str, Any]],
    tokens: dict[str, Tensor],
    device: torch.device,
) -> dict[str, float]:
    adapter.eval()
    projector.eval()
    losses: list[float] = []
    correct = 0
    supervised = 0
    with torch.no_grad():
        for row in rows:
            _, input_ids, labels = build_sft_tensors(
                tokenizer,
                config,
                finding=row["finding"],
                target_text=row["target_text"],
            )
            input_ids = input_ids.to(device)
            labels = labels.to(device)
            source = tokens[row["example_id"]].unsqueeze(0).to(
                device=device, dtype=torch.float32
            )
            projected = projector(token_bundle(source))
            result = adapter.forward_sft(
                input_ids,
                projected,
                labels=labels,
            )
            loss = float(result["loss"].detach().cpu())
            if not math.isfinite(loss):
                raise FloatingPointError("non-finite R40B evaluation loss")
            losses.append(loss)
            shifted_labels = labels[:, 1:]
            supervised_mask = shifted_labels.ne(-100)
            predictions = result["logits"][:, :-1].argmax(dim=-1)
            correct += int(
                predictions[supervised_mask]
                .eq(shifted_labels[supervised_mask])
                .sum()
                .item()
            )
            supervised += int(supervised_mask.sum().item())
    return {
        "mean_loss": sum(losses) / len(losses),
        "token_accuracy": correct / supervised,
        "supervised_tokens": float(supervised),
    }


def generated_metrics(
    *,
    adapter: GenerativeVLMAdapter,
    projector: TierTokenProjector,
    tokenizer: Any,
    config: dict[str, Any],
    rows: list[dict[str, Any]],
    tokens: dict[str, Tensor],
    device: torch.device,
) -> tuple[dict[str, float], list[dict[str, Any]]]:
    adapter.eval()
    projector.eval()
    expected_keys = [str(value) for value in config["target"]["schema_keys_in_order"]]
    progression_values = {
        str(value) for value in config["target"]["progression_values"]
    }
    valid = 0
    finding_correct = 0
    progression_correct = 0
    outputs: list[dict[str, Any]] = []
    with torch.no_grad():
        for row in rows:
            prompt = build_prompt_ids(
                tokenizer, config, finding=row["finding"]
            ).to(device)
            source = tokens[row["example_id"]].unsqueeze(0).to(
                device=device, dtype=torch.float32
            )
            projected = projector(token_bundle(source))
            generated, audit = adapter.generate_text(
                prompt,
                projected,
                max_new_tokens=int(config["target"]["max_target_tokens"]),
                eos_token_id=tokenizer.eos_token_id,
                pad_token_id=tokenizer.pad_token_id,
                return_audit=True,
            )
            text = tokenizer.decode(
                generated[0].detach().cpu().tolist(),
                skip_special_tokens=True,
            )
            parsed = parse_generated_object(
                text,
                expected_keys=expected_keys,
                progression_values=progression_values,
            )
            valid += parsed is not None
            finding_match = (
                parsed is not None and parsed["finding"] == row["finding"]
            )
            progression_match = (
                parsed is not None
                and parsed["progression"] == row["progression"]
            )
            finding_correct += finding_match
            progression_correct += progression_match
            outputs.append(
                {
                    "example_id": row["example_id"],
                    "expected": {
                        "finding": row["finding"],
                        "progression": row["progression"],
                    },
                    "generated_text": text,
                    "schema_valid": parsed is not None,
                    "finding_correct": finding_match,
                    "progression_correct": progression_match,
                    "visual_injection_calls": audit["visual_injection_calls"],
                    "pixel_inputs_used": audit["pixel_inputs_used"],
                }
            )
    count = len(rows)
    return (
        {
            "schema_validity": valid / count,
            "finding_echo_accuracy": finding_correct / count,
            "progression_accuracy": progression_correct / count,
        },
        outputs,
    )


def constrained_generated_metrics(
    *,
    adapter: GenerativeVLMAdapter,
    projector: TierTokenProjector,
    tokenizer: Any,
    config: dict[str, Any],
    rows: list[dict[str, Any]],
    tokens: dict[str, Tensor],
    device: torch.device,
) -> tuple[dict[str, float], list[dict[str, Any]]]:
    adapter.eval()
    projector.eval()
    progressions = [
        str(value) for value in config["target"]["progression_values"]
    ]
    outputs: list[dict[str, Any]] = []
    progression_correct = 0
    with torch.no_grad():
        for row in rows:
            prompt = build_prompt_ids(
                tokenizer, config, finding=row["finding"]
            ).to(device)
            source = tokens[row["example_id"]].unsqueeze(0).to(
                device=device, dtype=torch.float32
            )
            projected = projector(token_bundle(source))
            candidate_scores: dict[str, float] = {}
            candidate_texts: dict[str, str] = {}
            for progression in progressions:
                text = json.dumps(
                    {
                        "finding": row["finding"],
                        "progression": progression,
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                ids = tokenizer(
                    text, add_special_tokens=False
                )["input_ids"]
                if bool(config["target"]["append_eos"]):
                    ids = [*ids, int(tokenizer.eos_token_id)]
                target = torch.tensor([ids], dtype=torch.long, device=device)
                score, audit = adapter.score_sequence(
                    prompt,
                    projected,
                    target,
                    return_audit=True,
                )
                if (
                    int(audit["placeholder_count"][0].item()) != 64
                    or audit["pixel_inputs_used"] is not False
                    or audit["normalization"] != "mean_token_log_likelihood"
                ):
                    raise PermissionError(
                        "R40B.1 constrained scoring audit failed"
                    )
                candidate_scores[progression] = float(score[0].cpu())
                candidate_texts[progression] = text
            selected = max(
                progressions,
                key=lambda progression: (
                    candidate_scores[progression],
                    -progressions.index(progression),
                ),
            )
            correct = selected == row["progression"]
            progression_correct += correct
            outputs.append(
                {
                    "example_id": row["example_id"],
                    "expected": {
                        "finding": row["finding"],
                        "progression": row["progression"],
                    },
                    "generated_text": candidate_texts[selected],
                    "selected_progression": selected,
                    "candidate_scores": candidate_scores,
                    "schema_valid": True,
                    "finding_correct": True,
                    "progression_correct": correct,
                    "visual_injection_calls": 1,
                    "pixel_inputs_used": False,
                    "decoding": "exact_schema_sequence_scoring",
                }
            )
    count = len(rows)
    return (
        {
            "schema_validity": 1.0,
            "finding_echo_accuracy": 1.0,
            "progression_accuracy": progression_correct / count,
        },
        outputs,
    )


def contract_passed(
    *,
    trainable_audit: dict[str, Any],
    cache_audit: dict[str, Any],
    row_audits: list[dict[str, Any]],
) -> bool:
    return bool(
        trainable_audit["trainable_boundary_pass"]
        and not trainable_audit["unexpected_trainable_parameter_names"]
        and cache_audit["passed"]
        and cache_audit["placeholder_count"] == 64
        and cache_audit["pixel_inputs_used"] is False
        and row_audits
        and all(audit["assistant_only_loss"] for audit in row_audits)
        and all(audit["placeholder_count"] == 64 for audit in row_audits)
        and all(audit["pixel_inputs_used"] is False for audit in row_audits)
    )


def gate_passed(
    *,
    config: dict[str, Any],
    initial: dict[str, float],
    final: dict[str, float],
    generated: dict[str, float],
    engineering_contract_passed: bool,
) -> bool:
    gate = config["gate"]
    return bool(
        engineering_contract_passed
        and math.isfinite(initial["mean_loss"])
        and math.isfinite(final["mean_loss"])
        and final["mean_loss"] / initial["mean_loss"]
        <= float(gate["final_to_initial_loss_ratio_at_most"])
        and final["token_accuracy"]
        >= float(gate["teacher_forced_token_accuracy_at_least"])
        and generated["schema_validity"]
        == float(gate["generated_schema_validity"])
        and generated["finding_echo_accuracy"]
        == float(gate["generated_finding_echo_accuracy"])
        and generated["progression_accuracy"]
        == float(gate["generated_progression_accuracy"])
    )


def run_smoke(
    *,
    config_path: Path,
    cohort_path: Path,
    attempt_name: str,
    device_name: str,
) -> dict[str, Any]:
    config = read_json(config_path)
    if config.get("status") not in CONFIG_STATUSES:
        raise PermissionError("R40B config is not frozen")
    runtime_root = Path(config["runtime"]["root"])
    attempt = validate_attempt_authority(
        config=config,
        attempt_name=attempt_name,
        runtime_root=runtime_root,
    )
    output_root = runtime_root / attempt_name
    if output_root.exists():
        raise FileExistsError(f"R40B attempt output must be fresh: {output_root}")
    cohort = read_json(cohort_path)
    expected_cohort_status = (
        COHORT_STATUS
        if str(config.get("stage_tag", "R40B")) == "R40B"
        else f"PASS_PRTA_GEN_{config['stage_tag']}_SMOKE_COHORT"
    )
    if (
        cohort.get("status") != expected_cohort_status
        or cohort.get("protocol_id") != config["protocol_id"]
        or cohort.get("row_count") != int(config["source"]["rows"])
        or cohort.get("one_row_per_patient") is not True
        or cohort.get("protected_300_dev_read") is not False
        or cohort.get("revealed_483_test_read") is not False
        or cohort.get("gold_outcomes_read") is not False
    ):
        raise PermissionError("R40B cohort receipt drift")
    token_index = read_json(Path(config["source"]["token_index"]))
    if (
        token_index.get("status") != config["source"]["required_token_status"]
        or token_index.get("labels_in_cache") is not False
        or token_index.get("sentences_in_cache") is not False
    ):
        raise PermissionError("R40B token-cache receipt drift")
    rows = list(cohort["rows"])
    example_ids = {str(row["example_id"]) for row in rows}
    tokens = load_selected_tokens(
        token_index,
        example_ids,
        token_key=str(config["source"]["token_variant"]),
    )
    patient_receipt = tokens.pop("_patient_receipt")  # type: ignore[arg-type]
    finding_receipt = tokens.pop("_finding_receipt")  # type: ignore[arg-type]
    for row in rows:
        example_id = row["example_id"]
        if (
            patient_receipt[example_id] != row["patient_id"]
            or finding_receipt[example_id] != row["finding"]
        ):
            raise ValueError("R40B cohort/token alignment drift")

    device = torch.device(device_name)
    if device.type != "cuda" or not torch.cuda.is_available():
        raise RuntimeError("R40B smoke requires an explicit CUDA device")
    torch.cuda.set_device(device)
    torch.cuda.reset_peak_memory_stats(device)
    seed = int(attempt["seed"])
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
            config["model"]["sentinel_token"],
            add_special_tokens=False,
        )["input_ids"]
        != [placeholder_id]
    ):
        raise ValueError("R40B sentinel receipt drift")
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
        raise PermissionError("R40B unexpected trainable Qwen parameter")
    initial = teacher_forced_metrics(
        adapter=adapter,
        projector=projector,
        tokenizer=tokenizer,
        config=config,
        rows=rows,
        tokens=tokens,
        device=device,
    )
    optimizer = torch.optim.AdamW(
        [
            {
                "params": list(projector.parameters()),
                "lr": float(attempt["projector_learning_rate"]),
            },
            {
                "params": [
                    parameter
                    for parameter in adapter.parameters()
                    if parameter.requires_grad
                ],
                "lr": float(attempt["lora_learning_rate"]),
            },
        ],
        weight_decay=float(attempt["weight_decay"]),
    )
    accumulation = int(attempt["gradient_accumulation"])
    started = time.perf_counter()
    history: list[dict[str, Any]] = []
    row_audits: list[dict[str, Any]] = []
    optimizer.zero_grad(set_to_none=True)
    global_row = 0
    for epoch in range(int(attempt["epochs"])):
        ordered = sorted(
            rows,
            key=lambda row: stable_epoch_key(
                seed, epoch, str(row["example_id"])
            ),
        )
        epoch_loss = 0.0
        for row in ordered:
            global_row += 1
            _, input_ids, labels = build_sft_tensors(
                tokenizer,
                config,
                finding=row["finding"],
                target_text=row["target_text"],
            )
            input_ids = input_ids.to(device)
            labels = labels.to(device)
            source = tokens[row["example_id"]].unsqueeze(0).to(
                device=device, dtype=torch.float32
            )
            projected = projector(token_bundle(source))
            result = adapter.forward_sft(
                input_ids,
                projected,
                labels=labels,
            )
            loss = result["loss"]
            if not bool(torch.isfinite(loss)):
                raise FloatingPointError("non-finite R40B training loss")
            (loss / accumulation).backward()
            if (
                global_row % accumulation == 0
                or global_row == int(attempt["epochs"]) * len(rows)
            ):
                torch.nn.utils.clip_grad_norm_(
                    [
                        parameter
                        for group in optimizer.param_groups
                        for parameter in group["params"]
                    ],
                    1.0,
                )
                optimizer.step()
                optimizer.zero_grad(set_to_none=True)
            epoch_loss += float(loss.detach().cpu())
            audit = result["audit"]
            row_audits.append(
                {
                    "assistant_only_loss": bool(audit["assistant_only_loss"]),
                    "placeholder_count": int(
                        audit["placeholder_count"][0].item()
                    ),
                    "pixel_inputs_used": bool(audit["pixel_inputs_used"]),
                }
            )
        history.append(
            {
                "epoch": epoch + 1,
                "mean_loss": epoch_loss / len(rows),
                "optimizer_steps_completed": math.ceil(global_row / accumulation),
                "elapsed_seconds": time.perf_counter() - started,
            }
        )
    final = teacher_forced_metrics(
        adapter=adapter,
        projector=projector,
        tokenizer=tokenizer,
        config=config,
        rows=rows,
        tokens=tokens,
        device=device,
    )
    model.gradient_checkpointing_disable()
    model.config.use_cache = True
    first = rows[0]
    first_prompt = build_prompt_ids(
        tokenizer, config, finding=first["finding"]
    ).to(device)
    first_source = tokens[first["example_id"]].unsqueeze(0).to(
        device=device, dtype=torch.float32
    )
    with torch.no_grad():
        cache_audit = adapter.audit_first_step_cache_equivalence(
            first_prompt,
            projector(token_bundle(first_source)),
        )
    decoding_mode = str(config.get("decoding", {}).get("mode", "free_greedy"))
    if decoding_mode == "free_greedy":
        generated, outputs = generated_metrics(
            adapter=adapter,
            projector=projector,
            tokenizer=tokenizer,
            config=config,
            rows=rows,
            tokens=tokens,
            device=device,
        )
    elif decoding_mode == "exact_schema_sequence_scoring":
        generated, outputs = constrained_generated_metrics(
            adapter=adapter,
            projector=projector,
            tokenizer=tokenizer,
            config=config,
            rows=rows,
            tokens=tokens,
            device=device,
        )
    else:
        raise ValueError("unregistered R40B decoding mode")
    engineering_contract = contract_passed(
        trainable_audit=trainable_audit,
        cache_audit=cache_audit,
        row_audits=row_audits,
    )
    passed = gate_passed(
        config=config,
        initial=initial,
        final=final,
        generated=generated,
        engineering_contract_passed=engineering_contract,
    )
    if passed:
        status = result_status(config, "pass", attempt_name)
    elif not engineering_contract:
        status = result_status(config, "contract_stop", attempt_name)
    else:
        status = result_status(config, "underfit", attempt_name)
    output_root.mkdir(parents=True, exist_ok=False)
    checkpoint_path = output_root / "trainable_checkpoint.pt"
    torch.save(
        {
            "schema": "visualvit.prta-gen.r40b-trainable-checkpoint.v1",
            "attempt": attempt_name,
            "projector": projector.state_dict(),
            "lora": {
                name: tensor.detach().cpu()
                for name, tensor in adapter.state_dict().items()
                if "lora_" in name
            },
        },
        checkpoint_path,
    )
    result = {
        "schema": "visualvit.prta-gen.r40b-overfit-smoke-result.v1",
        "status": status,
        "protocol_id": config["protocol_id"],
        "attempt": attempt_name,
        "attempt_settings": attempt,
        "row_count": len(rows),
        "patient_count": len({row["patient_id"] for row in rows}),
        "initial_teacher_forced": initial,
        "final_teacher_forced": final,
        "final_to_initial_loss_ratio": final["mean_loss"] / initial["mean_loss"],
        "generated": generated,
        "decoding_mode": decoding_mode,
        "generated_outputs": outputs,
        "history": history,
        "engineering_contract_passed": engineering_contract,
        "trainable_parameter_audit": trainable_audit,
        "projector_parameter_count": sum(
            parameter.numel() for parameter in projector.parameters()
        ),
        "cache_equivalence_audit": cache_audit,
        "checkpoint": str(checkpoint_path),
        "checkpoint_bytes": checkpoint_path.stat().st_size,
        "token_budget": 64,
        "active_tokens": 60,
        "assistant_only_loss": True,
        "pixel_inputs_used": False,
        "progression_generation_unlocked": passed,
        "other_generation_fields_unlocked": False,
        "r41_unlocked": passed,
        "scientific_claim_allowed": False,
        "protected_300_dev_read": False,
        "revealed_483_test_read": False,
        "gold_outcomes_read": False,
        "external_outcomes_read": False,
        "old_r40a_development_used_for_selection": False,
        "source_hashes_recomputed": False,
        "per_shard_hashes_recomputed": False,
        "checkpoint_hashes_recomputed": False,
        "peak_cuda_allocated_bytes": torch.cuda.max_memory_allocated(device),
        "elapsed_seconds": time.perf_counter() - started,
    }
    write_json(output_root / "result.json", result)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run one registered progression-only R40B overfit attempt"
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--cohort", type=Path, required=True)
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--device", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = run_smoke(
        config_path=args.config,
        cohort_path=args.cohort,
        attempt_name=args.attempt,
        device_name=args.device,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    config = read_json(args.config)
    return (
        0
        if result["status"]
        == result_status(config, "pass", args.attempt)
        else 2
    )


if __name__ == "__main__":
    raise SystemExit(main())
