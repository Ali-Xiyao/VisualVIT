from __future__ import annotations

# ruff: noqa: E402

import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE))
sys.path.insert(0, str(WORKSPACE / "src"))

import torch
from torch import Tensor
import torch.nn.functional as F

from scripts.audit_prta_gen_r44_independent_support import sha256_file
from scripts.build_prta_gen_r40b_smoke_cohort import read_json, write_json
from scripts.r39_common import token_bundle
from scripts.run_prta_gen_r40b_overfit_smoke import (
    build_prompt_ids,
    build_sft_tensors,
    parse_generated_object,
)
from scripts.run_prta_gen_r40c_structured_generalization import (
    load_token_variants,
)
from scripts.run_prta_gen_r41a_progression_sft import (
    per_class_recall,
    target_text,
)
from visualvit.cdeb import (
    CausalDeltaEvidenceBottleneck,
    inject_cdeb_evidence,
)
from visualvit.prta_gen import (
    PROGRESSION_CLASSES,
    exact64_semantic_mean_features,
)
from visualvit.qualification import macro_f1
from visualvit.qwen_adapter import GenerativeVLMAdapter
from visualvit.tier_token_projector import TierTokenProjector


CONFIG_STATUS = "FROZEN_PRTA_GEN_R45_CDEB_DISCOVERY"
EVALUATION_ARMS = ("true_pair", "current_only", "query_only", "prior_shuffle")


def stable_epoch_key(
    seed: int, method: str, epoch: int, example_id: str
) -> str:
    return hashlib.sha256(
        f"r45-cdeb|{seed}|{method}|{epoch}|{example_id}".encode()
    ).hexdigest()


def _rows(roster: dict[str, Any], partition: str) -> list[dict[str, Any]]:
    rows = list(roster["partitions"][partition]["rows"])
    if len(rows) != int(roster["partitions"][partition]["row_count"]):
        raise ValueError(f"R45 {partition} row-count drift")
    return rows


def validate_authority(
    config: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    if config.get("status") != CONFIG_STATUS:
        raise PermissionError("R45 discovery config is not frozen")
    authority = config["authority"]
    roster_path = Path(authority["roster"])
    if (
        not roster_path.is_file()
        or roster_path.stat().st_size != int(authority["roster_bytes"])
        or sha256_file(roster_path) != authority["roster_sha256"]
    ):
        raise PermissionError("R45 discovery roster authority drift")
    roster = read_json(roster_path)
    if (
        roster.get("status") != authority["roster_status"]
        or roster.get("protocol_id") != config["protocol_id"]
        or roster.get("patient_sets_disjoint") is not True
        or roster.get("one_row_per_patient") is not True
        or roster.get("qualification_outcomes_read") is not False
        or roster.get("confirmation_outcomes_read") is not False
        or roster.get("gold_outcomes_read") is not False
        or roster.get("external_outcomes_read") is not False
    ):
        raise PermissionError("R45 discovery roster receipt drift")
    index_path = Path(config["source"]["token_index"])
    if (
        not index_path.is_file()
        or index_path.stat().st_size
        != int(config["source"]["token_index_bytes"])
        or sha256_file(index_path) != config["source"]["token_index_sha256"]
    ):
        raise PermissionError("R45 discovery token-index authority drift")
    index = read_json(index_path)
    if (
        index.get("status") != config["source"]["required_token_status"]
        or index.get("protocol_id") != config["protocol_id"]
        or index.get("roster_sha256") != authority["roster_sha256"]
        or index.get("rows") != config["cache"]["expected_rows"]
        or index.get("cached_partitions") != ["train", "development"]
        or index.get("labels_in_cache") is not False
        or index.get("sentences_in_cache") is not False
        or index.get("qualification_tokens_materialized") is not False
        or index.get("confirmation_tokens_materialized") is not False
        or index.get("qualification_outcomes_read") is not False
        or index.get("confirmation_outcomes_read") is not False
        or index.get("gold_outcomes_read") is not False
        or index.get("external_outcomes_read") is not False
    ):
        raise PermissionError("R45 discovery token-cache receipt drift")
    return roster, index


def preflight(config_path: Path) -> dict[str, Any]:
    config = read_json(config_path)
    roster, index = validate_authority(config)
    seeds = [int(value) for value in config["training"]["discovery_seeds"]]
    methods = [str(value) for value in config["methods"]["order"]]
    output_root = Path(config["runtime"]["discovery_root"])
    existing = [
        str(output_root / f"seed_{seed}" / method)
        for seed in seeds
        for method in methods
        if (output_root / f"seed_{seed}" / method).exists()
    ]
    if existing:
        raise FileExistsError("R45 discovery method output is not fresh")
    if not index["shards"]:
        raise ValueError("R45 discovery token index has no shards")
    sampled = torch.load(
        index["shards"][0]["path"],
        map_location="cpu",
        weights_only=True,
    )
    required = {
        "example_ids",
        "patient_ids",
        "findings",
        "true_tokens",
        "current_tokens",
        "shuffled_tokens",
    }
    if not required.issubset(sampled):
        raise ValueError("R45 discovery token shard schema drift")
    sampled_rows = len(sampled["example_ids"])
    if (
        sampled_rows == 0
        or len(sampled["patient_ids"]) != sampled_rows
        or len(sampled["findings"]) != sampled_rows
        or any(
            tuple(sampled[key].shape)
            != (sampled_rows, 64, 768)
            for key in (
                "true_tokens",
                "current_tokens",
                "shuffled_tokens",
            )
        )
    ):
        raise ValueError("R45 discovery sampled token-shard shape drift")
    model_path = Path(config["model"]["path"])
    if not model_path.is_dir():
        raise FileNotFoundError("R45 local Qwen model path is absent")
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(
        model_path,
        local_files_only=True,
        trust_remote_code=False,
    )
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
        raise ValueError("R45 preflight sentinel token drift")
    return {
        "schema": "visualvit.prta-gen.r45-cdeb-runner-preflight.v1",
        "status": "PASS_PRTA_GEN_R45_CDEB_RUNNER_PREFLIGHT",
        "protocol_id": config["protocol_id"],
        "seeds": seeds,
        "methods": methods,
        "training_rows": roster["partitions"]["train"]["row_count"],
        "development_rows": roster["partitions"]["development"]["row_count"],
        "token_index_sha256": config["source"]["token_index_sha256"],
        "token_rows": index["rows"],
        "token_shards": index["shard_count"],
        "sampled_shard_rows": sampled_rows,
        "local_qwen_present": True,
        "placeholder_token_id": placeholder_id,
        "all_method_outputs_fresh": True,
        "gpu_training_started": False,
        "qualification_tokens_materialized": False,
        "confirmation_tokens_materialized": False,
        "qualification_outcomes_read": False,
        "confirmation_outcomes_read": False,
        "gold_outcomes_read": False,
        "external_outcomes_read": False,
        "scientific_claim_allowed": False,
    }


def _features_for_mode(
    true_tokens: Tensor, current_tokens: Tensor, mode: str
) -> Tensor:
    true_features = exact64_semantic_mean_features(true_tokens.float())
    if mode == "true_pair":
        return true_features
    if mode == "delta":
        return true_features - exact64_semantic_mean_features(
            current_tokens.float()
        )
    raise ValueError("R45 feature mode drift")


def fit_feature_normalization(
    rows: list[dict[str, Any]],
    loaded: dict[str, dict[str, Tensor]],
    *,
    mode: str,
    chunk_size: int = 128,
) -> tuple[Tensor, Tensor]:
    features = []
    for start in range(0, len(rows), chunk_size):
        batch = rows[start : start + chunk_size]
        true_tokens = torch.stack(
            [loaded["true_pair"][str(row["example_id"])] for row in batch]
        )
        current_tokens = torch.stack(
            [loaded["current_only"][str(row["example_id"])] for row in batch]
        )
        features.append(
            _features_for_mode(true_tokens, current_tokens, mode).cpu()
        )
    stacked = torch.cat(features)
    mean = stacked.mean(dim=0, keepdim=True)
    std = stacked.std(dim=0, unbiased=False, keepdim=True).clamp_min(1e-6)
    if tuple(mean.shape) != (1, 3840) or tuple(std.shape) != (1, 3840):
        raise ValueError("R45 normalization feature-width drift")
    return mean, std


def build_cdeb(
    config: dict[str, Any],
    *,
    feature_mode: str,
    feature_mean: Tensor,
    feature_std: Tensor,
    bridge_enabled: bool,
    device: torch.device,
) -> CausalDeltaEvidenceBottleneck:
    spec = config["cdeb"]
    cdeb = CausalDeltaEvidenceBottleneck(
        feature_mean=feature_mean,
        feature_std=feature_std,
        feature_mode=feature_mode,
        feature_width=int(spec["feature_width"]),
        head_hidden_width=int(spec["head_hidden_width"]),
        class_count=int(spec["class_count"]),
        bridge_hidden_width=int(spec["bridge_hidden_width"]),
        qwen_hidden_size=int(config["model"]["hidden_size"]),
        evidence_token_count=int(spec["evidence_token_count"]),
        temperature=float(spec["temperature"]),
    ).to(device)
    if not bridge_enabled:
        cdeb.evidence_bridge.requires_grad_(False)
        cdeb.evidence_norm.requires_grad_(False)
    return cdeb


def _arm_tokens(
    row: dict[str, Any],
    loaded: dict[str, dict[str, Tensor]],
    arm: str,
) -> tuple[Tensor, Tensor]:
    example_id = str(row["example_id"])
    if arm == "query_only":
        zeros = torch.zeros((64, 768), dtype=torch.float32)
        return zeros, zeros
    source = loaded[arm][example_id]
    current = loaded["current_only"][example_id]
    return source, current


def _metrics(
    rows: list[dict[str, Any]], predictions: list[int]
) -> dict[str, Any]:
    class_to_index = {
        label: index for index, label in enumerate(PROGRESSION_CLASSES)
    }
    targets = [
        class_to_index[str(row["progression"])] for row in rows
    ]
    recalls = per_class_recall(
        targets, predictions, class_count=len(PROGRESSION_CLASSES)
    )
    return {
        "row_count": len(rows),
        "progression_accuracy": sum(
            target == prediction
            for target, prediction in zip(targets, predictions, strict=True)
        )
        / len(rows),
        "macro_f1": macro_f1(
            targets,
            predictions,
            class_count=len(PROGRESSION_CLASSES),
        ),
        "per_class_recall": {
            label: recalls[index]
            for index, label in enumerate(PROGRESSION_CLASSES)
        },
    }


def evaluate(
    *,
    adapter: GenerativeVLMAdapter,
    projector: TierTokenProjector,
    cdeb: CausalDeltaEvidenceBottleneck | None,
    bridge_enabled: bool,
    tokenizer: Any,
    config: dict[str, Any],
    rows: list[dict[str, Any]],
    loaded: dict[str, dict[str, Tensor]],
    device: torch.device,
) -> tuple[dict[str, Any], dict[str, list[int]], dict[str, Any]]:
    adapter.eval()
    projector.eval()
    if cdeb is not None:
        cdeb.eval()
    expected_keys = [
        str(value) for value in config["target"]["schema_keys_in_order"]
    ]
    progression_values = {
        str(value) for value in config["target"]["progression_values"]
    }
    class_to_index = {
        label: index for index, label in enumerate(PROGRESSION_CLASSES)
    }
    metrics: dict[str, Any] = {}
    predictions: dict[str, list[int]] = {}
    auxiliary: dict[str, Any] = {}
    with torch.no_grad():
        for arm in EVALUATION_ARMS:
            arm_predictions: list[int] = []
            auxiliary_predictions: list[int] = []
            valid = 0
            finding_correct = 0
            same_injection_contract = True
            for row in rows:
                source_cpu, current_cpu = _arm_tokens(row, loaded, arm)
                source = source_cpu.unsqueeze(0).to(
                    device=device, dtype=torch.float32
                )
                current = current_cpu.unsqueeze(0).to(
                    device=device, dtype=torch.float32
                )
                projected = projector(token_bundle(source))
                if cdeb is not None:
                    logits, _, evidence = cdeb(source, current)
                    auxiliary_predictions.append(
                        int(logits.argmax(dim=-1).item())
                    )
                    projected = inject_cdeb_evidence(
                        projected, evidence, enabled=bridge_enabled
                    )
                prompt = build_prompt_ids(
                    tokenizer, config, finding=str(row["finding"])
                ).to(device)
                generated, audit = adapter.generate_text(
                    prompt,
                    projected,
                    max_new_tokens=int(config["target"]["max_target_tokens"]),
                    eos_token_id=tokenizer.eos_token_id,
                    pad_token_id=tokenizer.pad_token_id,
                    return_audit=True,
                )
                same_injection_contract = same_injection_contract and (
                    audit["visual_injection_calls"] == 1
                    and audit["subsequent_placeholder_replacements"] == 0
                    and audit["pixel_inputs_used"] is False
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
                schema_ok = parsed is not None
                finding_ok = (
                    parsed is not None
                    and parsed["finding"] == str(row["finding"])
                )
                valid += schema_ok
                finding_correct += finding_ok
                arm_predictions.append(
                    class_to_index[parsed["progression"]]
                    if finding_ok
                    else -1
                )
            if not same_injection_contract:
                raise PermissionError("R45 generation injection audit failed")
            arm_metrics = _metrics(rows, arm_predictions)
            arm_metrics.update(
                {
                    "schema_validity": valid / len(rows),
                    "finding_echo_accuracy": finding_correct / len(rows),
                    "invalid_or_wrong_finding_predictions": sum(
                        value < 0 for value in arm_predictions
                    ),
                }
            )
            metrics[arm] = arm_metrics
            predictions[arm] = arm_predictions
            if cdeb is not None:
                auxiliary[arm] = _metrics(rows, auxiliary_predictions)
    return metrics, predictions, auxiliary


def run_method(
    *,
    config_path: Path,
    seed: int,
    method: str,
    device_name: str,
) -> dict[str, Any]:
    config = read_json(config_path)
    if seed not in [int(value) for value in config["training"]["discovery_seeds"]]:
        raise ValueError("R45 discovery Seed is not registered")
    if method not in config["methods"]["order"]:
        raise ValueError("R45 discovery method is not registered")
    roster, token_index = validate_authority(config)
    output_root = (
        Path(config["runtime"]["discovery_root"])
        / f"seed_{seed}"
        / method
    )
    if output_root.exists():
        raise FileExistsError(f"R45 method output must be fresh: {output_root}")
    training_rows = _rows(roster, "train")
    development_rows = _rows(roster, "development")
    all_rows = training_rows + development_rows
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
            raise ValueError("R45 roster/token alignment drift")
    method_spec = config["methods"][method]
    feature_mode = method_spec["decision_feature_mode"]
    feature_mean = feature_std = None
    if feature_mode is not None:
        feature_mean, feature_std = fit_feature_normalization(
            training_rows, loaded, mode=str(feature_mode)
        )
    device = torch.device(device_name)
    if device.type != "cuda" or not torch.cuda.is_available():
        raise RuntimeError("R45 discovery requires an explicit CUDA device")
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
        raise ValueError("R45 sentinel token drift")
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
    cdeb = None
    if feature_mode is not None:
        assert feature_mean is not None and feature_std is not None
        cdeb = build_cdeb(
            config,
            feature_mode=str(feature_mode),
            feature_mean=feature_mean,
            feature_std=feature_std,
            bridge_enabled=bool(method_spec["evidence_bridge_enabled"]),
            device=device,
        )
    model_audit = adapter.trainable_parameter_audit()
    if (
        model_audit["trainable_boundary_pass"] is not True
        or int(model_audit["trainable_parameter_count"]) != 0
    ):
        raise PermissionError("R45 Qwen must remain fully frozen")
    training = config["training"]
    parameter_groups: list[dict[str, Any]] = [
        {
            "params": list(projector.parameters()),
            "lr": float(training["projector_learning_rate"]),
        }
    ]
    if cdeb is not None:
        cdeb_parameters = [
            parameter for parameter in cdeb.parameters() if parameter.requires_grad
        ]
        parameter_groups.append(
            {
                "params": cdeb_parameters,
                "lr": float(training["cdeb_learning_rate"]),
            }
        )
    optimizer = torch.optim.AdamW(
        parameter_groups,
        weight_decay=float(training["weight_decay"]),
    )
    class_to_index = {
        label: index for index, label in enumerate(PROGRESSION_CLASSES)
    }
    accumulation = int(training["gradient_accumulation"])
    optimizer.zero_grad(set_to_none=True)
    global_row = 0
    updates = 0
    history = []
    started = time.perf_counter()
    for epoch in range(int(training["epochs"])):
        adapter.train()
        projector.train()
        if cdeb is not None:
            cdeb.train()
        ordered = sorted(
            training_rows,
            key=lambda row: stable_epoch_key(
                seed, method, epoch, str(row["example_id"])
            ),
        )
        epoch_sft = 0.0
        epoch_aux = 0.0
        epoch_total = 0.0
        for row in ordered:
            global_row += 1
            _, input_ids, labels = build_sft_tensors(
                tokenizer,
                config,
                finding=str(row["finding"]),
                target_text=target_text(row),
            )
            example_id = str(row["example_id"])
            source = loaded["true_pair"][example_id].unsqueeze(0).to(
                device=device, dtype=torch.float32
            )
            current = loaded["current_only"][example_id].unsqueeze(0).to(
                device=device, dtype=torch.float32
            )
            projected = projector(token_bundle(source))
            auxiliary_loss = torch.zeros((), device=device)
            if cdeb is not None:
                logits, _, evidence = cdeb(source, current)
                target = torch.tensor(
                    [class_to_index[str(row["progression"])]],
                    dtype=torch.long,
                    device=device,
                )
                auxiliary_loss = F.cross_entropy(logits, target)
                projected = inject_cdeb_evidence(
                    projected,
                    evidence,
                    enabled=bool(method_spec["evidence_bridge_enabled"]),
                )
            result = adapter.forward_sft(
                input_ids.to(device),
                projected,
                labels=labels.to(device),
            )
            sft_loss = result["loss"]
            total_loss = (
                float(training["sft_loss_weight"]) * sft_loss
                + float(training["auxiliary_ce_weight"]) * auxiliary_loss
            )
            audit = result["audit"]
            if (
                not bool(torch.isfinite(total_loss))
                or audit["assistant_only_loss"] is not True
                or int(audit["placeholder_count"][0].item()) != 64
                or audit["pixel_inputs_used"] is not False
            ):
                raise FloatingPointError("R45 training contract failed")
            (total_loss / accumulation).backward()
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
            epoch_sft += float(sft_loss.detach().cpu())
            epoch_aux += float(auxiliary_loss.detach().cpu())
            epoch_total += float(total_loss.detach().cpu())
        history.append(
            {
                "epoch": epoch + 1,
                "mean_sft_loss": epoch_sft / len(ordered),
                "mean_auxiliary_loss": epoch_aux / len(ordered),
                "mean_total_loss": epoch_total / len(ordered),
                "optimizer_updates_completed": updates,
                "elapsed_seconds": time.perf_counter() - started,
            }
        )
    if updates != int(training["expected_optimizer_updates"]):
        raise ValueError("R45 optimizer update-count drift")
    model.gradient_checkpointing_disable()
    model.config.use_cache = True
    first = development_rows[0]
    first_source_cpu, first_current_cpu = _arm_tokens(
        first, loaded, "true_pair"
    )
    first_source = first_source_cpu.unsqueeze(0).to(
        device=device, dtype=torch.float32
    )
    first_current = first_current_cpu.unsqueeze(0).to(
        device=device, dtype=torch.float32
    )
    first_projected = projector(token_bundle(first_source))
    if cdeb is not None:
        _, _, first_evidence = cdeb(first_source, first_current)
        first_projected = inject_cdeb_evidence(
            first_projected,
            first_evidence,
            enabled=bool(method_spec["evidence_bridge_enabled"]),
        )
    first_prompt = build_prompt_ids(
        tokenizer, config, finding=str(first["finding"])
    ).to(device)
    cache_audit = adapter.audit_first_step_cache_equivalence(
        first_prompt, first_projected
    )
    if cache_audit["passed"] is not True:
        raise PermissionError("R45 cached/uncached first-step drift")
    metrics, predictions, auxiliary_metrics = evaluate(
        adapter=adapter,
        projector=projector,
        cdeb=cdeb,
        bridge_enabled=bool(method_spec["evidence_bridge_enabled"]),
        tokenizer=tokenizer,
        config=config,
        rows=development_rows,
        loaded=loaded,
        device=device,
    )
    output_root.mkdir(parents=True, exist_ok=False)
    checkpoint_path = output_root / "trainable_checkpoint.pt"
    checkpoint_payload: dict[str, Any] = {
        "schema": "visualvit.prta-gen.r45-cdeb-checkpoint.v1",
        "seed": seed,
        "method": method,
        "projector": projector.state_dict(),
    }
    if cdeb is not None:
        checkpoint_payload["cdeb"] = cdeb.state_dict()
    torch.save(checkpoint_payload, checkpoint_path)
    targets = [
        class_to_index[str(row["progression"])] for row in development_rows
    ]
    same_prediction_rate = sum(
        left == right
        for left, right in zip(
            predictions["true_pair"],
            predictions["prior_shuffle"],
            strict=True,
        )
    ) / len(development_rows)
    result = {
        "schema": "visualvit.prta-gen.r45-cdeb-discovery-arm.v1",
        "status": config["result_statuses"]["arm_complete"],
        "protocol_id": config["protocol_id"],
        "study_tier": config["study_tier"],
        "seed": seed,
        "method": method,
        "method_spec": method_spec,
        "classes": list(PROGRESSION_CLASSES),
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
        "targets": targets,
        "metrics": metrics,
        "predictions": predictions,
        "auxiliary_metrics": auxiliary_metrics,
        "true_prior_shuffle_same_prediction_rate": same_prediction_rate,
        "training_history": history,
        "optimizer_updates": updates,
        "qwen_trainable_parameters": int(
            model_audit["trainable_parameter_count"]
        ),
        "projector_trainable_parameters": sum(
            parameter.numel()
            for parameter in projector.parameters()
            if parameter.requires_grad
        ),
        "cdeb_trainable_parameters": (
            sum(
                parameter.numel()
                for parameter in cdeb.parameters()
                if parameter.requires_grad
            )
            if cdeb is not None
            else 0
        ),
        "cache_equivalence_audit": cache_audit,
        "checkpoint": str(checkpoint_path),
        "checkpoint_bytes": checkpoint_path.stat().st_size,
        "exact64_tokens_used": True,
        "qualified_positions_preserved": [0, 60],
        "cdeb_evidence_positions": [60, 61, 62, 63],
        "free_greedy_generation_evaluated": True,
        "pixel_inputs_used": False,
        "qualification_unlocked": False,
        "confirmation_unlocked": False,
        "qualification_outcomes_read": False,
        "confirmation_outcomes_read": False,
        "gold_outcomes_read": False,
        "external_outcomes_read": False,
        "scientific_claim_allowed": False,
        "peak_cuda_allocated_bytes": torch.cuda.max_memory_allocated(device),
        "elapsed_seconds": time.perf_counter() - started,
    }
    write_json(output_root / "result.json", result)
    return result


def receipt_summary(result: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in result.items()
        if key
        not in {
            "development_patient_ids",
            "development_example_ids",
            "targets",
            "predictions",
        }
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run one frozen R45 CDEB discovery method"
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--method")
    parser.add_argument("--device")
    parser.add_argument("--preflight-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.preflight_only:
        if any(
            value is not None
            for value in (args.seed, args.method, args.device)
        ):
            raise ValueError("R45 runner preflight accepts only --config")
        result = preflight(args.config)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    if args.seed is None or args.method is None or args.device is None:
        raise ValueError("R45 method run requires seed, method, and device")
    result = run_method(
        config_path=args.config,
        seed=args.seed,
        method=args.method,
        device_name=args.device,
    )
    print(json.dumps(receipt_summary(result), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
