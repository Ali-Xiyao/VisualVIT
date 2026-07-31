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

from scripts.build_prta_gen_r40b_smoke_cohort import read_json, write_json
from scripts.r51_common import sha256_file, validate_authority
from scripts.run_prta_gen_r40c_structured_generalization import (
    per_class_recall,
    train_head_arm,
)
from scripts.run_prta_gen_r49_exact64 import _state_sha256
from scripts.run_prta_gen_r51_matched_interface import _load_arm_tokens
from visualvit.prta_gen import PROGRESSION_CLASSES, ProgressionDecisionHead
from visualvit.qualification import macro_f1


DEFAULT_CONFIG = (
    WORKSPACE / "configs" / "prta_gen" / "prta_gen_r52_matched_direct_head_v1.json"
)
FROZEN_STATUS = "FROZEN_PRTA_GEN_R52_MATCHED_DIRECT_HEAD"


def flatten_active_exact64(tokens: Tensor) -> Tensor:
    if tokens.ndim != 3 or tuple(tokens.shape[1:]) != (64, 768):
        raise ValueError("R52 exact64 tensor must have shape [B,64,768]")
    if not bool(torch.isfinite(tokens).all()):
        raise FloatingPointError("R52 exact64 tensor is non-finite")
    if not bool(tokens[:, 60:64].eq(0).all()):
        raise PermissionError("R52 reserved token positions must remain zero")
    return tokens[:, :60].float().reshape(len(tokens), 60 * 768)


def _verify_file(path: Path, expected_bytes: int, expected_sha256: str) -> None:
    if (
        not path.is_file()
        or path.stat().st_size != expected_bytes
        or sha256_file(path) != expected_sha256
    ):
        raise PermissionError(f"R52 authority drift: {path}")


def validate_r52_authority(
    config_path: Path,
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    config = read_json(config_path)
    if config.get("status") != FROZEN_STATUS:
        raise PermissionError("R52 config is not frozen")
    source = config["source"]
    r51_path = WORKSPACE / source["r51_config"]
    _verify_file(
        r51_path,
        int(source["r51_config_bytes"]),
        str(source["r51_config_sha256"]),
    )
    r51_config, training_rows, evaluation_rows = validate_authority(
        r51_path, require_pinned_caches=True
    )
    if (
        r51_config.get("status") != source["required_r51_status"]
        or r51_config.get("protocol_id") != source["required_r51_protocol_id"]
        or len(training_rows) != int(source["training_rows"])
        or len(evaluation_rows) != int(source["evaluation_rows"])
    ):
        raise PermissionError("R52 R51 source contract drift")
    methods = config["methods"]
    head = config["head"]
    training = config["training"]
    if (
        methods["order"] != config["evaluation"]["arms"]
        or methods["order"] != r51_config["evaluation"]["arms"]
        or head["active_positions"] != [0, 60]
        or head["reserved_positions_ignored"] != [60, 64]
        or int(head["input_width"]) != 60 * 768
        or head["arm_specific_trainable_adapter_allowed"] is not False
        or training["early_stopping"] is not False
        or training["checkpoint_selection"] is not False
        or config["disclosure"]["any_r52_direct_head_outcome_visible_before_freeze"]
        is not False
    ):
        raise PermissionError("R52 matched-head contract drift")
    return config, r51_config, training_rows, evaluation_rows


def _head_for_seed(config: dict[str, Any], seed: int) -> ProgressionDecisionHead:
    torch.manual_seed(seed)
    return ProgressionDecisionHead(
        input_width=int(config["head"]["input_width"]),
        hidden_width=int(config["head"]["hidden_width"]),
        class_count=int(config["head"]["class_count"]),
    )


def preflight(config_path: Path) -> dict[str, Any]:
    config, r51_config, training_rows, evaluation_rows = validate_r52_authority(
        config_path
    )
    root = Path(config["runtime"]["root"])
    if root.exists():
        raise FileExistsError(f"R52 runtime must be fresh: {root}")
    audit_rows = [training_rows[0], evaluation_rows[0]]
    feature_shapes: dict[str, list[int]] = {}
    for arm in config["evaluation"]["arms"]:
        loaded = _load_arm_tokens(r51_config, str(arm), audit_rows)
        features = flatten_active_exact64(
            torch.stack([loaded[str(row["example_id"])] for row in audit_rows])
        )
        feature_shapes[str(arm)] = list(features.shape)
    hashes: dict[str, str] = {}
    parameter_counts: set[int] = set()
    for seed in config["training"]["seeds"]:
        head = _head_for_seed(config, int(seed))
        hashes[str(seed)] = _state_sha256(head)
        parameter_counts.add(sum(p.numel() for p in head.parameters()))
    if parameter_counts != {int(config["head"]["parameter_count"])}:
        raise PermissionError("R52 direct-head parameter-count drift")
    return {
        "schema": "visualvit.prta-gen.r52-runner-preflight.v1",
        "status": config["result_statuses"]["preflight_pass"],
        "protocol_id": config["protocol_id"],
        "training_rows": len(training_rows),
        "evaluation_rows": len(evaluation_rows),
        "arms": config["evaluation"]["arms"],
        "seeds": config["training"]["seeds"],
        "feature_shapes": feature_shapes,
        "shared_initialization_hashes": hashes,
        "head_trainable_parameters": next(iter(parameter_counts)),
        "arm_specific_trainable_parameters": 0,
        "all_outputs_fresh": True,
        "r52_model_outcomes_read": False,
        "gpu_training_started": False,
    }


def run_arm(config_path: Path, *, arm: str, seed: int, device_name: str) -> dict[str, Any]:
    config, r51_config, training_rows, evaluation_rows = validate_r52_authority(
        config_path
    )
    if arm not in config["evaluation"]["arms"]:
        raise ValueError("R52 arm is not registered")
    if seed not in [int(value) for value in config["training"]["seeds"]]:
        raise ValueError("R52 seed is not registered")
    output = Path(config["runtime"]["runs"]) / f"seed_{seed}" / arm
    if output.exists():
        raise FileExistsError(f"R52 arm output must be fresh: {output}")
    all_rows = training_rows + evaluation_rows
    loaded = _load_arm_tokens(r51_config, arm, all_rows)
    features = flatten_active_exact64(
        torch.stack([loaded[str(row["example_id"])] for row in all_rows])
    )
    class_to_index = {name: index for index, name in enumerate(PROGRESSION_CLASSES)}
    targets = torch.tensor(
        [class_to_index[str(row["progression"])] for row in all_rows],
        dtype=torch.long,
    )
    training_count = len(training_rows)
    device = torch.device(device_name)
    if device.type != "cuda" or not torch.cuda.is_available():
        raise RuntimeError("R52 formal direct-head run requires explicit CUDA")
    torch.cuda.set_device(device)
    torch.cuda.reset_peak_memory_stats(device)
    audit_head = _head_for_seed(config, seed)
    initialization_sha256 = _state_sha256(audit_head)
    del audit_head
    spec = config["training"]
    started = time.perf_counter()
    head, mean, std, predictions, training_audit = train_head_arm(
        training_features=features[:training_count],
        training_targets=targets[:training_count],
        development_features=features[training_count:],
        development_targets=targets[training_count:],
        seed=seed,
        hidden_width=int(config["head"]["hidden_width"]),
        class_count=int(config["head"]["class_count"]),
        epochs=int(spec["epochs"]),
        batch_size=int(spec["batch_size"]),
        learning_rate=float(spec["learning_rate"]),
        weight_decay=float(spec["weight_decay"]),
        gradient_clip_norm=float(spec["gradient_clip_norm"]),
        device=device,
    )
    if int(training_audit["updates"]) != int(spec["expected_updates_per_arm"]):
        raise PermissionError("R52 optimizer update-count drift")
    target_values = [int(value) for value in targets[training_count:].tolist()]
    recalls = per_class_recall(target_values, predictions, class_count=5)
    metrics = {
        "macro_f1": macro_f1(target_values, predictions, class_count=5),
        "accuracy": sum(
            target == prediction
            for target, prediction in zip(target_values, predictions, strict=True)
        )
        / len(target_values),
        "per_class_recall": {
            label: recalls[index] for index, label in enumerate(PROGRESSION_CLASSES)
        },
        "row_count": len(evaluation_rows),
    }
    output.mkdir(parents=True, exist_ok=False)
    checkpoint = output / "direct_head_checkpoint.pt"
    torch.save(
        {
            "schema": "visualvit.prta-gen.r52-direct-head-checkpoint.v1",
            "protocol_id": config["protocol_id"],
            "arm": arm,
            "seed": seed,
            "head": head.state_dict(),
            "feature_mean": mean,
            "feature_std": std,
        },
        checkpoint,
    )
    result = {
        "schema": "visualvit.prta-gen.r52-matched-direct-head-arm.v1",
        "status": config["result_statuses"]["arm_complete"],
        "protocol_id": config["protocol_id"],
        "arm": arm,
        "method_provenance": config["methods"][arm]["provenance"],
        "seed": seed,
        "classes": list(PROGRESSION_CLASSES),
        "training_rows": len(training_rows),
        "training_example_ids_sha256": hashlib.sha256(
            "\n".join(str(row["example_id"]) for row in training_rows).encode()
        ).hexdigest().upper(),
        "evaluation_rows": len(evaluation_rows),
        "evaluation_patient_ids": [str(row["patient_id"]) for row in evaluation_rows],
        "evaluation_example_ids": [str(row["example_id"]) for row in evaluation_rows],
        "targets": target_values,
        "predictions": predictions,
        "metrics": metrics,
        "training_audit": training_audit,
        "head_initialization_sha256": initialization_sha256,
        "head_trainable_parameters": sum(p.numel() for p in head.parameters()),
        "arm_specific_trainable_parameters": 0,
        "exact64_active_positions_flattened": [0, 60],
        "reserved_positions_ignored": [60, 64],
        "checkpoint": str(checkpoint),
        "checkpoint_bytes": checkpoint.stat().st_size,
        "elapsed_seconds": time.perf_counter() - started,
        "peak_cuda_allocated_bytes": int(torch.cuda.max_memory_allocated(device)),
        "same_patients_head_training_contract": True,
        "r52_model_outcomes_read_once": True,
        "protected_300_dev_read": False,
        "revealed_483_test_read": False,
        "gold_outcomes_read": False,
        "external_outcomes_read": False,
        "clinical_claim_allowed": False,
    }
    write_json(output / "result.json", result)
    return result


def receipt_summary(result: dict[str, Any]) -> dict[str, Any]:
    hidden = {"evaluation_patient_ids", "evaluation_example_ids", "targets", "predictions"}
    return {key: value for key, value in result.items() if key not in hidden}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run frozen R52 matched direct head")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--arm")
    parser.add_argument("--seed", type=int)
    parser.add_argument("--device")
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    if args.preflight_only:
        result = preflight(args.config)
    else:
        if args.arm is None or args.seed is None or args.device is None:
            raise ValueError("R52 run requires arm, seed, and device")
        result = run_arm(
            args.config, arm=str(args.arm), seed=int(args.seed), device_name=str(args.device)
        )
    print(json.dumps(receipt_summary(result), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
