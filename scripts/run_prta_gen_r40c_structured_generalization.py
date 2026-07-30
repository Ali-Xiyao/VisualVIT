from __future__ import annotations

# ruff: noqa: E402

import argparse
import json
import math
from pathlib import Path
import sys
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE))
sys.path.insert(0, str(WORKSPACE / "src"))

import torch
from torch import Tensor
import torch.nn.functional as F

from scripts.build_prta_gen_r40b_smoke_cohort import read_json, write_json
from scripts.build_prta_gen_r40c_roster import (
    CONFIG_STATUS,
    ROSTER_STATUS,
    preflight as roster_preflight,
    validate_authority,
)
from scripts.run_prta_gen_r40b4_structured_head_smoke import structured_text
from visualvit.prta_gen import (
    PROGRESSION_CLASSES,
    ProgressionDecisionHead,
    exact64_semantic_mean_features,
)
from visualvit.qualification import macro_f1


SEED_STATUS = "PASS_PRTA_GEN_R40C_SEED_EVALUATION"
ARMS = ("true_pair", "current_only", "query_only", "prior_shuffle")


def padded_query_features(
    rows: list[dict[str, Any]],
    *,
    findings: list[str],
    input_width: int,
) -> Tensor:
    if len(findings) != 12 or len(set(findings)) != len(findings):
        raise ValueError("R40C finding registry must contain 12 unique values")
    finding_to_index = {
        finding: index for index, finding in enumerate(findings)
    }
    unknown = {str(row["finding"]) for row in rows} - set(findings)
    if unknown:
        raise ValueError(f"R40C unregistered findings: {sorted(unknown)}")
    values = torch.zeros((len(rows), input_width), dtype=torch.float32)
    indices = torch.tensor(
        [finding_to_index[str(row["finding"])] for row in rows],
        dtype=torch.long,
    )
    values[torch.arange(len(rows)), indices] = 1.0
    return values


def per_class_recall(
    targets: list[int], predictions: list[int], *, class_count: int
) -> list[float]:
    if len(targets) != len(predictions) or not targets:
        raise ValueError("R40C recall inputs must be aligned and non-empty")
    recalls = []
    for class_index in range(class_count):
        positives = sum(value == class_index for value in targets)
        if positives == 0:
            raise ValueError("R40C recall requires every class")
        true_positives = sum(
            target == class_index and prediction == class_index
            for target, prediction in zip(targets, predictions, strict=True)
        )
        recalls.append(true_positives / positives)
    return recalls


def load_token_variants(
    token_index: dict[str, Any],
    *,
    example_ids: set[str],
    token_keys: dict[str, str],
) -> tuple[
    dict[str, dict[str, Tensor]],
    dict[str, str],
    dict[str, str],
]:
    selected: dict[str, dict[str, Tensor]] = {
        arm: {} for arm in token_keys
    }
    patient_receipt: dict[str, str] = {}
    finding_receipt: dict[str, str] = {}
    for shard_entry in token_index["shards"]:
        shard = torch.load(
            shard_entry["path"], map_location="cpu", weights_only=True
        )
        for position, raw_example_id in enumerate(shard["example_ids"]):
            example_id = str(raw_example_id)
            if example_id not in example_ids:
                continue
            if example_id in patient_receipt:
                raise ValueError(f"duplicate R40C token example: {example_id}")
            patient_receipt[example_id] = str(shard["patient_ids"][position])
            finding_receipt[example_id] = str(shard["findings"][position])
            for arm, key in token_keys.items():
                tensor = shard[key][position]
                if tuple(tensor.shape) != (64, 768):
                    raise ValueError("R40C source token shape drift")
                if not bool(torch.isfinite(tensor).all()):
                    raise ValueError("R40C source tokens are non-finite")
                selected[arm][example_id] = tensor.float()
    if set(patient_receipt) != example_ids:
        missing = len(example_ids - set(patient_receipt))
        raise ValueError(f"R40C token cache misses {missing} examples")
    return selected, patient_receipt, finding_receipt


def train_head_arm(
    *,
    training_features: Tensor,
    training_targets: Tensor,
    development_features: Tensor,
    development_targets: Tensor,
    seed: int,
    hidden_width: int,
    class_count: int,
    epochs: int,
    batch_size: int,
    learning_rate: float,
    weight_decay: float,
    gradient_clip_norm: float,
    device: torch.device,
) -> tuple[ProgressionDecisionHead, Tensor, Tensor, list[int], dict[str, Any]]:
    if (
        training_features.ndim != 2
        or development_features.ndim != 2
        or training_features.shape[1] != development_features.shape[1]
        or len(training_features) != len(training_targets)
        or len(development_features) != len(development_targets)
    ):
        raise ValueError("R40C arm tensors are misaligned")
    feature_mean = training_features.mean(dim=0, keepdim=True)
    feature_std = training_features.std(
        dim=0, unbiased=False, keepdim=True
    ).clamp_min(1e-6)
    training_normalized = (training_features - feature_mean) / feature_std
    development_normalized = (
        development_features - feature_mean
    ) / feature_std
    torch.manual_seed(seed)
    if device.type == "cuda":
        torch.cuda.manual_seed_all(seed)
    head = ProgressionDecisionHead(
        input_width=int(training_features.shape[1]),
        hidden_width=hidden_width,
        class_count=class_count,
    ).to(device)
    optimizer = torch.optim.AdamW(
        head.parameters(),
        lr=learning_rate,
        weight_decay=weight_decay,
    )
    generator = torch.Generator(device="cpu")
    generator.manual_seed(seed)
    train_x = training_normalized.to(device)
    train_y = training_targets.to(device)
    with torch.no_grad():
        initial_loss = float(F.cross_entropy(head(train_x), train_y).cpu())
    history = []
    updates = 0
    for epoch in range(1, epochs + 1):
        order = torch.randperm(len(train_y), generator=generator)
        head.train()
        epoch_loss = 0.0
        for start in range(0, len(order), batch_size):
            indices = order[start : start + batch_size].to(device)
            logits = head(train_x.index_select(0, indices))
            loss = F.cross_entropy(logits, train_y.index_select(0, indices))
            if not bool(torch.isfinite(loss)):
                raise FloatingPointError("non-finite R40C training loss")
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(
                head.parameters(), gradient_clip_norm
            )
            optimizer.step()
            epoch_loss += float(loss.detach().cpu()) * len(indices)
            updates += 1
        if epoch % 10 == 0 or epoch == epochs:
            history.append(
                {"epoch": epoch, "loss": epoch_loss / len(train_y)}
            )
    head.eval()
    with torch.no_grad():
        final_training_loss = float(
            F.cross_entropy(head(train_x), train_y).cpu()
        )
        development_logits = head(development_normalized.to(device))
        development_loss = float(
            F.cross_entropy(
                development_logits, development_targets.to(device)
            ).cpu()
        )
        predictions = development_logits.argmax(dim=-1).cpu().tolist()
    return (
        head,
        feature_mean,
        feature_std,
        [int(value) for value in predictions],
        {
            "initial_training_loss": initial_loss,
            "final_training_loss": final_training_loss,
            "development_loss": development_loss,
            "updates": updates,
            "history": history,
            "normalization_fit_on_training_only": True,
        },
    )


def _rows_from_roster(
    roster: dict[str, Any], partition: str
) -> list[dict[str, Any]]:
    rows = list(roster["partitions"][partition]["rows"])
    expected = int(roster["partitions"][partition]["row_count"])
    if len(rows) != expected:
        raise ValueError(f"R40C {partition} roster row-count drift")
    return rows


def run_seed(
    *,
    config_path: Path,
    roster_path: Path,
    seed: int,
    device_name: str,
) -> dict[str, Any]:
    config = read_json(config_path)
    if config.get("status") != CONFIG_STATUS:
        raise PermissionError("R40C config is not frozen")
    if seed not in [int(value) for value in config["training"]["seeds"]]:
        raise ValueError("R40C seed is not registered")
    validate_authority(config)
    roster = read_json(roster_path)
    if (
        roster.get("status") != ROSTER_STATUS
        or roster.get("protocol_id") != config["protocol_id"]
        or roster.get("patient_sets_disjoint") is not True
        or roster.get("one_row_per_patient") is not True
        or roster.get("excluded_observed_patient_count") != 160
        or roster.get("excluded_observed_patients_absent") is not True
        or roster.get("development_outcomes_read") is not False
        or roster.get("protected_300_dev_read") is not False
        or roster.get("revealed_483_test_read") is not False
        or roster.get("gold_outcomes_read") is not False
    ):
        raise PermissionError("R40C roster receipt drift")
    output_root = Path(config["runtime"]["root"]) / f"seed_{seed}"
    if output_root.exists():
        raise FileExistsError(f"R40C Seed output must be fresh: {output_root}")
    token_index = read_json(Path(config["source"]["token_index"]))
    training_rows = _rows_from_roster(roster, "train")
    development_rows = _rows_from_roster(roster, "development")
    all_rows = training_rows + development_rows
    example_ids = {str(row["example_id"]) for row in all_rows}
    token_keys = {
        str(arm): str(key)
        for arm, key in config["source"]["token_variants"].items()
    }
    loaded, patient_receipt, finding_receipt = load_token_variants(
        token_index,
        example_ids=example_ids,
        token_keys=token_keys,
    )
    for row in all_rows:
        example_id = str(row["example_id"])
        if (
            patient_receipt[example_id] != str(row["patient_id"])
            or finding_receipt[example_id] != str(row["finding"])
        ):
            raise ValueError("R40C roster/token alignment drift")
    input_width = int(config["head"]["input_width"])
    all_features = {
        arm: exact64_semantic_mean_features(
            torch.stack([loaded[arm][str(row["example_id"])] for row in all_rows])
        )
        for arm in token_keys
    }
    all_features["query_only"] = padded_query_features(
        all_rows,
        findings=[str(value) for value in config["target"]["finding_values"]],
        input_width=input_width,
    )
    if any(
        tuple(features.shape) != (len(all_rows), input_width)
        for features in all_features.values()
    ):
        raise ValueError("R40C arm feature-width drift")
    class_to_index = {
        label: index for index, label in enumerate(PROGRESSION_CLASSES)
    }
    all_targets = torch.tensor(
        [class_to_index[str(row["progression"])] for row in all_rows],
        dtype=torch.long,
    )
    training_count = len(training_rows)
    training_targets = all_targets[:training_count]
    development_targets = all_targets[training_count:]
    device = torch.device(device_name)
    if device.type != "cuda" or not torch.cuda.is_available():
        raise RuntimeError("R40C formal Seed evaluation requires CUDA")
    torch.cuda.set_device(device)
    torch.cuda.reset_peak_memory_stats(device)
    training_spec = config["training"]
    arms = [str(value) for value in training_spec["arms"]]
    if tuple(arms) != ARMS:
        raise ValueError("R40C arm registry drift")
    predictions: dict[str, list[int]] = {}
    metrics: dict[str, Any] = {}
    audits: dict[str, Any] = {}
    true_head = None
    true_mean = None
    true_std = None
    for arm in arms:
        head, mean, std, arm_predictions, audit = train_head_arm(
            training_features=all_features[arm][:training_count],
            training_targets=training_targets,
            development_features=all_features[arm][training_count:],
            development_targets=development_targets,
            seed=seed,
            hidden_width=int(config["head"]["hidden_width"]),
            class_count=int(config["head"]["class_count"]),
            epochs=int(training_spec["epochs"]),
            batch_size=int(training_spec["batch_size"]),
            learning_rate=float(training_spec["learning_rate"]),
            weight_decay=float(training_spec["weight_decay"]),
            gradient_clip_norm=float(
                training_spec["gradient_clip_norm"]
            ),
            device=device,
        )
        if audit["updates"] != int(training_spec["expected_updates_per_arm"]):
            raise ValueError("R40C registered update-count drift")
        predictions[arm] = arm_predictions
        target_list = development_targets.tolist()
        recalls = per_class_recall(
            target_list, arm_predictions, class_count=len(PROGRESSION_CLASSES)
        )
        metrics[arm] = {
            "macro_f1": macro_f1(
                target_list,
                arm_predictions,
                class_count=len(PROGRESSION_CLASSES),
            ),
            "per_class_recall": {
                label: recalls[index]
                for index, label in enumerate(PROGRESSION_CLASSES)
            },
        }
        audits[arm] = audit
        if arm == "true_pair":
            true_head, true_mean, true_std = head, mean, std
    if true_head is None or true_mean is None or true_std is None:
        raise RuntimeError("R40C true-pair arm was not trained")
    target_list = development_targets.tolist()
    metrics["effects_pp"] = {
        arm: 100.0
        * (metrics["true_pair"]["macro_f1"] - metrics[arm]["macro_f1"])
        for arm in ("current_only", "query_only", "prior_shuffle")
    }
    counterfactuals = {}
    with torch.no_grad():
        for arm in ("current_only", "prior_shuffle"):
            normalized = (
                all_features[arm][training_count:] - true_mean
            ) / true_std
            values = true_head(normalized.to(device)).argmax(dim=-1)
            counterfactuals[arm] = [int(value) for value in values.cpu()]
    structured_outputs = []
    for row, prediction in zip(
        development_rows, predictions["true_pair"], strict=True
    ):
        progression = PROGRESSION_CLASSES[prediction]
        text = structured_text(str(row["finding"]), progression)
        parsed = json.loads(text)
        structured_outputs.append(
            {
                "example_id": str(row["example_id"]),
                "generated_text": text,
                "schema_valid": list(parsed) == ["finding", "progression"],
                "finding_correct": parsed["finding"] == str(row["finding"]),
                "progression_correct": progression
                == str(row["progression"]),
            }
        )
    schema_validity = sum(
        row["schema_valid"] for row in structured_outputs
    ) / len(structured_outputs)
    finding_accuracy = sum(
        row["finding_correct"] for row in structured_outputs
    ) / len(structured_outputs)
    output_root.mkdir(parents=True, exist_ok=False)
    checkpoint = output_root / "true_pair_checkpoint.pt"
    torch.save(
        {
            "schema": "visualvit.prta-gen.r40c-head-checkpoint.v1",
            "seed": seed,
            "head": true_head.state_dict(),
            "feature_mean": true_mean,
            "feature_std": true_std,
            "classes": PROGRESSION_CLASSES,
        },
        checkpoint,
    )
    result = {
        "schema": "visualvit.prta-gen.r40c-seed-result.v1",
        "status": config["result_statuses"]["seed_complete"],
        "protocol_id": config["protocol_id"],
        "seed": seed,
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
        "targets": target_list,
        "predictions": predictions,
        "true_head_counterfactual_predictions": counterfactuals,
        "metrics": metrics,
        "training_audits": audits,
        "structured": {
            "schema_validity": schema_validity,
            "finding_echo_accuracy": finding_accuracy,
            "outputs": structured_outputs,
        },
        "parameter_count": sum(
            parameter.numel() for parameter in true_head.parameters()
        ),
        "checkpoint": str(checkpoint),
        "checkpoint_bytes": checkpoint.stat().st_size,
        "exact64_tokens_used": True,
        "semantic_layout": "4/12/16/16/12/4",
        "normalization_fit_on_training_only": True,
        "pixel_inputs_used": False,
        "qwen_free_generation_unlocked": False,
        "r41_qwen_sft_unlocked": False,
        "scientific_claim_allowed": False,
        "protected_300_dev_read": False,
        "revealed_483_test_read": False,
        "gold_outcomes_read": False,
        "external_outcomes_read": False,
        "peak_cuda_allocated_bytes": torch.cuda.max_memory_allocated(device),
    }
    write_json(output_root / "result.json", result)
    return result


def preflight(config_path: Path) -> dict[str, Any]:
    config = read_json(config_path)
    roster_receipt = roster_preflight(config_path)
    head = ProgressionDecisionHead(
        input_width=int(config["head"]["input_width"]),
        hidden_width=int(config["head"]["hidden_width"]),
        class_count=int(config["head"]["class_count"]),
    )
    parameter_count = sum(parameter.numel() for parameter in head.parameters())
    if parameter_count != int(config["head"]["parameter_count"]):
        raise ValueError("R40C head parameter-count drift")
    training = config["training"]
    expected_updates = math.ceil(
        int(config["roster"]["train_patients"])
        / int(training["batch_size"])
    ) * int(training["epochs"])
    if expected_updates != int(training["expected_updates_per_arm"]):
        raise ValueError("R40C expected update-count drift")
    synthetic_rows = [
        {"finding": value} for value in config["target"]["finding_values"]
    ]
    query = padded_query_features(
        synthetic_rows,
        findings=[str(value) for value in config["target"]["finding_values"]],
        input_width=int(config["head"]["input_width"]),
    )
    if tuple(head(query).shape) != (12, 5):
        raise ValueError("R40C query-control dry-run drift")
    return {
        "schema": "visualvit.prta-gen.r40c-runner-preflight.v1",
        "status": "PASS_PRTA_GEN_R40C_RUNNER_PREFLIGHT",
        "protocol_id": config["protocol_id"],
        "roster_preflight_status": roster_receipt["status"],
        "parameter_count": parameter_count,
        "expected_updates_per_arm": expected_updates,
        "arms": list(ARMS),
        "seeds": [int(value) for value in training["seeds"]],
        "query_control_shape": list(query.shape),
        "real_roster_written": False,
        "gpu_training_started": False,
        "protected_300_dev_read": False,
        "revealed_483_test_read": False,
        "gold_outcomes_read": False,
        "external_outcomes_read": False,
        "scientific_claim_allowed": False,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Preflight or run one frozen R40C Seed"
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--roster", type=Path)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--device")
    parser.add_argument("--preflight-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.preflight_only:
        if any(value is not None for value in (args.roster, args.seed, args.device)):
            raise ValueError("R40C preflight accepts only --config")
        result = preflight(args.config)
    else:
        if args.roster is None or args.seed is None or args.device is None:
            raise ValueError("R40C Seed run requires roster, seed, and device")
        result = run_seed(
            config_path=args.config,
            roster_path=args.roster,
            seed=args.seed,
            device_name=args.device,
        )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
