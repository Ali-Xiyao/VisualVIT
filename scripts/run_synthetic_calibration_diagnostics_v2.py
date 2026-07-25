from __future__ import annotations

# ruff: noqa: E402

import argparse
import copy
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import sys
import time
from typing import Any, Iterable

import torch
from torch import Tensor, nn

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE))
sys.path.insert(0, str(WORKSPACE / "src"))

from scripts.run_capes_ci_synthetic_overfit import (
    FrozenRelationCausalLM,
    _build_model,
    _prompt,
    _state_hash,
)
from scripts.run_synthetic_calibration_grid import (
    CalibrationBatch,
    DEFAULT_SEED_BANK,
    _b4_pair_audit,
    _evaluate_plan,
    _freeze_unused_matcher,
    _json_hash,
    _shared_allocation,
    _train_system,
    audit_anchor_batch,
    make_anchor_batch,
)
from visualvit.matching import anatomy_compatible_derangement
from visualvit.model import CAPESCIModel
from visualvit.schemas import AllocationPlan, MatchPlan, ProjectedTokenBundle


PROTOCOL_VERSION = "CAPES_CI_POST_FAILURE_DIAGNOSTICS_V2_2026_07_19"
EVIDENCE_CLASS = "POST_FAILURE_ENGINEERING_DIAGNOSTIC_NONCONFIRMATORY"
FROZEN_VLM_SEED = 91_001
SYSTEM_NAMES = ("B4a_deranged", "B4b_oracle", "learned_soft")
LABEL_NAMES = ("stable", "worse", "improved", "new", "resolved")
TRAIN_DATA_SEED = 3_401
INNER_DEV_DATA_SEED = 4_401
DEV_DATA_SEED = 5_401
TRAIN_CASES_PER_CLASS = 2
INNER_DEV_CASES_PER_CLASS = 1
DEV_CASES_PER_CLASS = 2
FEATURE_DIM = 12
HIDDEN_SIZE = 16
LEARNING_RATE = 2e-2


@dataclass(frozen=True)
class DiagnosticModeSpec:
    name: str
    parent: str
    steps: int
    changed_factor: str
    neutralize_global_entity_payloads: bool


MODE_SPECS = {
    "D1": DiagnosticModeSpec(
        name="D1",
        parent="S075",
        steps=80,
        changed_factor="frozen_toy_vlm_seed_only",
        neutralize_global_entity_payloads=False,
    ),
    "D2": DiagnosticModeSpec(
        name="D2",
        parent="D1",
        steps=500,
        changed_factor="training_steps_80_to_500_only",
        neutralize_global_entity_payloads=False,
    ),
    "D3": DiagnosticModeSpec(
        name="D3",
        parent="D2",
        steps=500,
        changed_factor="global_and_entity_payloads_to_shared_neutral_only",
        neutralize_global_entity_payloads=True,
    ),
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run one fail-closed CAPES-CI v2 post-failure diagnostic (D1/D2/D3)."
        )
    )
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--mode", choices=tuple(MODE_SPECS), required=True)
    parser.add_argument("--seeds", type=int, nargs="+", default=list(DEFAULT_SEED_BANK))
    parser.add_argument(
        "--d2-summary",
        type=Path,
        default=None,
        help="Required for a registered D3 run; must prove D2 train competence.",
    )
    parser.add_argument("--device", choices=("cpu",), default="cpu")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--smoke",
        action="store_true",
        help=(
            "Run one optimization step as a non-diagnostic implementation smoke. "
            "This can never satisfy a D1/D2/D3 gate."
        ),
    )
    return parser


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    return build_parser().parse_args(argv)


def _named_tensor_hash(items: Iterable[tuple[str, Tensor]]) -> str:
    digest = hashlib.sha256()
    count = 0
    for name, value in sorted(items, key=lambda item: item[0]):
        count += 1
        digest.update(name.encode("utf-8"))
        contiguous = value.detach().to("cpu").contiguous()
        digest.update(str(contiguous.dtype).encode("ascii"))
        digest.update(str(tuple(contiguous.shape)).encode("ascii"))
        digest.update(contiguous.numpy().tobytes())
    if count == 0:
        raise ValueError("cannot hash an empty tensor collection")
    return digest.hexdigest()


def _trainable_state_hash(module: nn.Module) -> str:
    return _named_tensor_hash(
        (name, parameter)
        for name, parameter in module.named_parameters()
        if parameter.requires_grad
    )


def _frozen_vlm_hash(model: CAPESCIModel) -> str:
    return _state_hash(model.vlm_adapter.model)


def _build_seed_factorized_model(
    *, trainable_seed: int, feature_dim: int, hidden_size: int
) -> CAPESCIModel:
    """Initialize trainable modules and the frozen toy VLM from separate seeds."""

    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(trainable_seed)
        model = _build_model(feature_dim, hidden_size)
        torch.manual_seed(FROZEN_VLM_SEED)
        fixed_vlm = FrozenRelationCausalLM(hidden_size=hidden_size)
        model.vlm_adapter.model.load_state_dict(fixed_vlm.state_dict(), strict=True)
    return model


def _tensor_hash(value: Tensor, name: str = "tensor") -> str:
    return _named_tensor_hash(((name, value),))


def _install_global_entity_neutralization(
    model: CAPESCIModel, neutral_payload: Tensor
) -> torch.utils.hooks.RemovableHandle:
    """Replace projected slots 0:32 with one fixed, shared neutral payload."""

    fixed_neutral = neutral_payload.detach().clone()

    def hook(
        _module: nn.Module,
        _inputs: tuple[Any, ...],
        output: ProjectedTokenBundle,
    ) -> ProjectedTokenBundle:
        embeddings = output.embeddings.clone()
        neutral = fixed_neutral.to(
            device=embeddings.device, dtype=embeddings.dtype
        ).view(1, 1, -1)
        embeddings[:, :32] = neutral
        audit = dict(output.audit)
        audit.update(
            {
                "diagnostic_global_entity_payload_neutralized": True,
                "diagnostic_neutralized_slot_range": (0, 32),
                "diagnostic_neutral_payload_sha256": _tensor_hash(
                    fixed_neutral, "neutral_payload"
                ),
            }
        )
        replaced = ProjectedTokenBundle(
            embeddings=embeddings,
            token_types=output.token_types,
            valid_mask=output.valid_mask,
            attention_mask=output.attention_mask,
            position_ids=output.position_ids,
            audit=audit,
        )
        replaced.validate(token_budget=64)
        return replaced

    return model.projector.register_forward_hook(hook)


def _forward_with_plan(
    *,
    model: CAPESCIModel,
    batch: CalibrationBatch,
    plan: MatchPlan,
    allocation: AllocationPlan,
) -> dict[str, Any]:
    model.eval()
    prompt = _prompt(int(batch.labels.numel()), torch.device(batch.labels.device))
    with torch.inference_mode():
        return model(
            batch.regions,
            prompt,
            assignment_mode="provided",
            provided_plan=plan,
            allocation_plan=allocation,
        )


def _neutralization_contract_audit(
    *,
    base_model: CAPESCIModel,
    batch: CalibrationBatch,
    plan: MatchPlan,
    allocation: AllocationPlan,
) -> dict[str, Any]:
    """Prove D3 changes only projected global/entity payload content."""

    plain = copy.deepcopy(base_model)
    neutralized = copy.deepcopy(base_model)
    neutral_payload = base_model.projector.neutral_embedding.detach().clone()
    before_hash = _state_hash(neutralized)
    handle = _install_global_entity_neutralization(neutralized, neutral_payload)
    try:
        plain_output = _forward_with_plan(
            model=plain, batch=batch, plan=plan, allocation=allocation
        )
        neutral_output = _forward_with_plan(
            model=neutralized, batch=batch, plan=plan, allocation=allocation
        )
    finally:
        handle.remove()

    plain_projected = plain_output["projected_token_bundle"]
    neutral_projected = neutral_output["projected_token_bundle"]
    expected = neutral_payload.view(1, 1, -1).expand(
        neutral_projected.embeddings.shape[0], 32, -1
    )
    raw_plain = plain_output["token_bundle"]
    raw_neutral = neutral_output["token_bundle"]
    checks = {
        "complete_state_unchanged_by_hook": before_hash == _state_hash(neutralized),
        "exact_64_projected_tokens": neutral_projected.embeddings.shape[1] == 64,
        "global_entity_slots_equal_one_neutral_payload": torch.equal(
            neutral_projected.embeddings[:, :32], expected
        ),
        "global_entity_payload_actually_changed": not torch.equal(
            plain_projected.embeddings[:, :32],
            neutral_projected.embeddings[:, :32],
        ),
        "relation_and_reserved_payloads_bitwise_unchanged": torch.equal(
            plain_projected.embeddings[:, 32:],
            neutral_projected.embeddings[:, 32:],
        ),
        "raw_token_contents_unchanged": torch.equal(
            raw_plain.tokens, raw_neutral.tokens
        ),
        "token_types_unchanged": torch.equal(
            plain_projected.token_types, neutral_projected.token_types
        ),
        "valid_masks_unchanged": torch.equal(
            plain_projected.valid_mask, neutral_projected.valid_mask
        ),
        "physical_attention_unchanged": torch.equal(
            plain_projected.attention_mask, neutral_projected.attention_mask
        ),
        "position_ids_unchanged": torch.equal(
            plain_projected.position_ids, neutral_projected.position_ids
        ),
    }
    return {
        "checks": checks,
        "pass": all(checks.values()),
        "neutral_payload_sha256": _tensor_hash(neutral_payload, "neutral_payload"),
        "neutralized_slots": {"start_inclusive": 0, "stop_exclusive": 32},
        "preserved_slots": {"start_inclusive": 32, "stop_exclusive": 64},
    }


def _payload_audit(
    *,
    model: CAPESCIModel,
    batch: CalibrationBatch,
    plan: MatchPlan,
    allocation: AllocationPlan,
    neutral_payload: Tensor,
) -> dict[str, Any]:
    output = _forward_with_plan(
        model=model, batch=batch, plan=plan, allocation=allocation
    )
    projected = output["projected_token_bundle"]
    expected = neutral_payload.to(
        projected.embeddings.device, projected.embeddings.dtype
    ).view(1, 1, -1)
    expected = expected.expand(projected.embeddings.shape[0], 32, -1)
    checks = {
        "exact_64_projected_tokens": projected.embeddings.shape[1] == 64,
        "global_entity_payloads_neutral": torch.equal(
            projected.embeddings[:, :32], expected
        ),
        "physical_attention_all_one": bool((projected.attention_mask == 1).all()),
        "three_position_axes_equal": torch.equal(
            projected.position_ids[0], projected.position_ids[1]
        )
        and torch.equal(projected.position_ids[0], projected.position_ids[2]),
        "finite_payloads": bool(torch.isfinite(projected.embeddings).all()),
    }
    return {
        "checks": checks,
        "pass": all(checks.values()),
        "neutral_payload_sha256": _tensor_hash(neutral_payload, "neutral_payload"),
    }


def _add_five_label_metrics(result: dict[str, Any]) -> None:
    targets = result["raw"]["targets"]
    predictions = result["raw"]["predictions"]
    per_label: dict[str, dict[str, float | int]] = {}
    for label_index, label_name in enumerate(LABEL_NAMES):
        true_positive = sum(
            int(target == label_index and prediction == label_index)
            for target, prediction in zip(targets, predictions, strict=True)
        )
        false_positive = sum(
            int(target != label_index and prediction == label_index)
            for target, prediction in zip(targets, predictions, strict=True)
        )
        support = sum(int(target == label_index) for target in targets)
        precision = (
            true_positive / (true_positive + false_positive)
            if true_positive + false_positive > 0
            else 0.0
        )
        recall = true_positive / support if support > 0 else 0.0
        f1 = (
            2.0 * precision * recall / (precision + recall)
            if precision + recall > 0
            else 0.0
        )
        per_label[label_name] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": support,
        }
    result["label_metrics"].update(
        {
            "label_order": list(LABEL_NAMES),
            "per_label": per_label,
            "all_five_labels_present": all(
                metrics["support"] > 0 for metrics in per_label.values()
            ),
        }
    )


def _state_hash_record(model: CAPESCIModel) -> dict[str, str]:
    return {
        "frozen_vlm_sha256": _frozen_vlm_hash(model),
        "trainable_sha256": _trainable_state_hash(model),
        "complete_sha256": _state_hash(model),
    }


def _mode_config(args: argparse.Namespace) -> dict[str, Any]:
    spec = MODE_SPECS[args.mode]
    return {
        "protocol_version": PROTOCOL_VERSION,
        "mode": spec.name,
        "parent": spec.parent,
        "changed_factor": spec.changed_factor,
        "registered_steps": spec.steps,
        "actual_steps": 1 if args.smoke else spec.steps,
        "frozen_vlm_seed": FROZEN_VLM_SEED,
        "trainable_seed_bank": list(args.seeds),
        "train_data_seed": TRAIN_DATA_SEED,
        "inner_dev_data_seed": INNER_DEV_DATA_SEED,
        "dev_data_seed": DEV_DATA_SEED,
        "train_cases_per_class": TRAIN_CASES_PER_CLASS,
        "inner_dev_cases_per_class": INNER_DEV_CASES_PER_CLASS,
        "dev_cases_per_class": DEV_CASES_PER_CLASS,
        "feature_dim": FEATURE_DIM,
        "hidden_size": HIDDEN_SIZE,
        "learning_rate": LEARNING_RATE,
        "neutralize_global_entity_payloads": (spec.neutralize_global_entity_payloads),
        "device": args.device,
        "dry_run": bool(args.dry_run),
        "smoke": bool(args.smoke),
        "formal_test": "SEALED",
    }


def _shared_parent_config(config: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "frozen_vlm_seed",
        "trainable_seed_bank",
        "train_data_seed",
        "inner_dev_data_seed",
        "dev_data_seed",
        "train_cases_per_class",
        "inner_dev_cases_per_class",
        "dev_cases_per_class",
        "feature_dim",
        "hidden_size",
        "learning_rate",
        "device",
    )
    return {key: config[key] for key in keys}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _source_hashes() -> dict[str, Any]:
    paths = {
        "v2_runner": Path(__file__).resolve(),
        "v1_runner": WORKSPACE / "scripts" / "run_synthetic_calibration_grid.py",
        "v2_protocol": (
            WORKSPACE / "refine-logs" / "CALIBRATION_PROTOCOL_V2_2026-07-19.md"
        ),
    }
    hashes = {name: _sha256_file(path) for name, path in paths.items()}
    return {**hashes, "manifest_sha256": _json_hash(hashes)}


def _validate_args(args: argparse.Namespace) -> None:
    if not args.seeds or len(args.seeds) != len(set(args.seeds)):
        raise ValueError("seeds must be a non-empty unique ordered list")
    if args.dry_run and args.smoke:
        raise ValueError("dry-run and smoke are mutually exclusive")
    if args.smoke and len(args.seeds) != 1:
        raise ValueError("smoke requires exactly one training seed")
    if args.mode != "D3" and args.d2_summary is not None:
        raise ValueError("--d2-summary is valid only for D3")


def _d3_prerequisite_audit(
    args: argparse.Namespace,
    shared_parent_config_sha256: str,
) -> dict[str, Any]:
    if args.mode != "D3":
        return {
            "required": False,
            "pass": True,
            "reason": "not_applicable",
            "training_allowed": True,
        }
    if args.smoke:
        return {
            "required": True,
            "pass": False,
            "reason": "explicit_non_diagnostic_smoke_bypass",
            "training_allowed": True,
            "diagnostic_evaluable": False,
        }
    if args.dry_run:
        return {
            "required": True,
            "pass": False,
            "reason": "dry_run_does_not_open_training_gate",
            "training_allowed": False,
            "diagnostic_evaluable": False,
        }
    if args.d2_summary is None:
        return {
            "required": True,
            "pass": False,
            "reason": "missing_d2_summary",
            "training_allowed": False,
        }
    if not args.d2_summary.is_file():
        return {
            "required": True,
            "pass": False,
            "reason": "d2_summary_not_found",
            "path": str(args.d2_summary),
            "training_allowed": False,
        }
    try:
        parent = json.loads(args.d2_summary.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return {
            "required": True,
            "pass": False,
            "reason": "d2_summary_unreadable",
            "error_type": type(error).__name__,
            "training_allowed": False,
        }
    checks = {
        "protocol_version_matches": parent.get("protocol_version") == PROTOCOL_VERSION,
        "mode_is_D2": parent.get("mode") == "D2",
        "status_complete": parent.get("status") == "COMPLETE",
        "evidence_class_matches": parent.get("evidence_class") == EVIDENCE_CLASS,
        "exact_registered_seed_bank": parent.get("config", {}).get(
            "trainable_seed_bank"
        )
        == list(DEFAULT_SEED_BANK),
        "shared_parent_config_matches": parent.get("shared_parent_config_sha256")
        == shared_parent_config_sha256,
        "D2_train_competence_pass": parent.get("competence_gate", {}).get("pass")
        is True,
        "formal_test_sealed": parent.get("config", {}).get("formal_test") == "SEALED",
    }
    passed = all(checks.values())
    return {
        "required": True,
        "pass": passed,
        "reason": "qualified_D2_parent" if passed else "D2_parent_not_qualified",
        "checks": checks,
        "path": str(args.d2_summary.resolve()),
        "summary_sha256": _sha256_file(args.d2_summary),
        "training_allowed": passed,
    }


def _evaluate_system(
    *,
    name: str,
    model: CAPESCIModel,
    batch: CalibrationBatch,
    plan: MatchPlan,
    allocation: AllocationPlan,
) -> dict[str, Any]:
    result = _evaluate_plan(
        name=name,
        model=model,
        batch=batch,
        plan=plan,
        allocation=allocation,
        prompt=_prompt(int(batch.labels.numel()), torch.device(batch.labels.device)),
        evidence_class=EVIDENCE_CLASS,
    )
    _add_five_label_metrics(result)
    return result


def _train_one_seed(
    *,
    seed: int,
    args: argparse.Namespace,
    train: CalibrationBatch,
    dev: CalibrationBatch,
    config_sha256: str,
    source_manifest_sha256: str,
) -> dict[str, Any]:
    started = time.perf_counter()
    spec = MODE_SPECS[args.mode]
    steps = 1 if args.smoke else spec.steps
    base_model = _build_seed_factorized_model(
        trainable_seed=seed,
        feature_dim=FEATURE_DIM,
        hidden_size=HIDDEN_SIZE,
    ).to(args.device)
    base_initial_hashes = _state_hash_record(base_model)
    train_allocation = _shared_allocation(base_model, train.regions)
    dev_allocation = _shared_allocation(base_model, dev.regions)
    train_prompt = _prompt(int(train.labels.numel()), torch.device(args.device))

    train_derangement_seed = 200_000 + seed
    dev_derangement_seed = 300_000 + seed
    train_plans: dict[str, MatchPlan | None] = {
        "B4a_deranged": anatomy_compatible_derangement(
            train.regions, train.oracle, seed=train_derangement_seed
        ),
        "B4b_oracle": train.oracle,
        "learned_soft": None,
    }
    dev_b4a = anatomy_compatible_derangement(
        dev.regions, dev.oracle, seed=dev_derangement_seed
    )
    models = {name: copy.deepcopy(base_model) for name in SYSTEM_NAMES}
    neutral_payload = base_model.projector.neutral_embedding.detach().clone()
    hook_handles: list[torch.utils.hooks.RemovableHandle] = []
    if spec.neutralize_global_entity_payloads:
        hook_handles.extend(
            _install_global_entity_neutralization(model, neutral_payload)
            for model in models.values()
        )

    initial_hashes: dict[str, dict[str, str]] = {}
    for name, model in models.items():
        if train_plans[name] is not None:
            _freeze_unused_matcher(model)
        initial_hashes[name] = _state_hash_record(model)

    training_records = {
        name: _train_system(
            model=models[name],
            system_name=name,
            seed=seed,
            batch=train,
            allocation=train_allocation,
            prompt=train_prompt,
            steps=steps,
            learning_rate=LEARNING_RATE,
            provided_plan=train_plans[name],
        )
        for name in SYSTEM_NAMES
    }

    with torch.inference_mode():
        learned_train = models["learned_soft"].matcher.soft_plan(train.regions)
        learned_dev = models["learned_soft"].matcher.soft_plan(dev.regions)
    evaluated_train_plans = {
        "B4a_deranged": train_plans["B4a_deranged"],
        "B4b_oracle": train.oracle,
        "learned_soft": learned_train,
    }
    evaluated_dev_plans = {
        "B4a_deranged": dev_b4a,
        "B4b_oracle": dev.oracle,
        "learned_soft": learned_dev,
    }
    train_metrics = {
        name: _evaluate_system(
            name=f"{name}_train",
            model=models[name],
            batch=train,
            plan=evaluated_train_plans[name],
            allocation=train_allocation,
        )
        for name in SYSTEM_NAMES
    }
    dev_metrics = {
        name: _evaluate_system(
            name=f"{name}_development",
            model=models[name],
            batch=dev,
            plan=evaluated_dev_plans[name],
            allocation=dev_allocation,
        )
        for name in SYSTEM_NAMES
    }
    final_hashes = {name: _state_hash_record(model) for name, model in models.items()}
    for name in SYSTEM_NAMES:
        training_records[name]["state_hashes"] = {
            "initial": initial_hashes[name],
            "final": final_hashes[name],
            "frozen_vlm_unchanged": initial_hashes[name]["frozen_vlm_sha256"]
            == final_hashes[name]["frozen_vlm_sha256"],
        }

    b4_pair_audit = _b4_pair_audit(
        base_model=base_model,
        batch=train,
        allocation=train_allocation,
        prompt=train_prompt,
        deranged=train_plans["B4a_deranged"],
        oracle=train.oracle,
        record_a=training_records["B4a_deranged"],
        record_b=training_records["B4b_oracle"],
    )
    payload_audits: dict[str, dict[str, dict[str, Any]]] | None = None
    if spec.neutralize_global_entity_payloads:
        payload_audits = {
            name: {
                "train": _payload_audit(
                    model=models[name],
                    batch=train,
                    plan=evaluated_train_plans[name],
                    allocation=train_allocation,
                    neutral_payload=neutral_payload,
                ),
                "development": _payload_audit(
                    model=models[name],
                    batch=dev,
                    plan=evaluated_dev_plans[name],
                    allocation=dev_allocation,
                    neutral_payload=neutral_payload,
                ),
            }
            for name in SYSTEM_NAMES
        }

    train_b4a = train_metrics["B4a_deranged"]["label_metrics"]["case_balanced_macro_f1"]
    train_b4b = train_metrics["B4b_oracle"]["label_metrics"]["case_balanced_macro_f1"]
    dev_b4a_metric = dev_metrics["B4a_deranged"]["label_metrics"][
        "case_balanced_macro_f1"
    ]
    dev_b4b_metric = dev_metrics["B4b_oracle"]["label_metrics"][
        "case_balanced_macro_f1"
    ]
    technical_checks = {
        "all_train_evaluations_complete": all(
            result["status"] == "COMPLETE" for result in train_metrics.values()
        ),
        "all_development_evaluations_complete": all(
            result["status"] == "COMPLETE" for result in dev_metrics.values()
        ),
        "B4_pair_contract_pass": b4_pair_audit["pass"],
        "B4_trainable_initial_hash_equal": initial_hashes["B4a_deranged"][
            "trainable_sha256"
        ]
        == initial_hashes["B4b_oracle"]["trainable_sha256"],
        "B4_complete_initial_hash_equal": initial_hashes["B4a_deranged"][
            "complete_sha256"
        ]
        == initial_hashes["B4b_oracle"]["complete_sha256"],
        "all_system_frozen_vlm_hash_equal": len(
            {hashes["frozen_vlm_sha256"] for hashes in initial_hashes.values()}
        )
        == 1,
        "frozen_vlm_unchanged_after_training": all(
            initial_hashes[name]["frozen_vlm_sha256"]
            == final_hashes[name]["frozen_vlm_sha256"]
            for name in SYSTEM_NAMES
        ),
        "exact_registered_steps_or_explicit_smoke": all(
            record["steps"] == steps for record in training_records.values()
        ),
        "D3_payload_neutralization_pass": payload_audits is None
        or all(
            split_audit["pass"]
            for system_audit in payload_audits.values()
            for split_audit in system_audit.values()
        ),
        "formal_test_used": False,
    }
    status = "SMOKE_COMPLETE" if args.smoke else "COMPLETE"
    if not all(
        value for key, value in technical_checks.items() if key != "formal_test_used"
    ):
        status = "FAIL"

    for handle in hook_handles:
        handle.remove()
    return {
        "seed": seed,
        "status": status,
        "evidence_class": EVIDENCE_CLASS,
        "formal_claim_allowed": False,
        "formal_ablation_claim_allowed": False,
        "diagnostic_evaluable": not args.smoke,
        "config_sha256": config_sha256,
        "source_manifest_sha256": source_manifest_sha256,
        "base_initial_state_hashes": base_initial_hashes,
        "training_system_records": training_records,
        "metrics": {"train": train_metrics, "development": dev_metrics},
        "effects": {
            "train_delta_bind_percentage_points": 100.0 * (train_b4b - train_b4a),
            "development_delta_bind_percentage_points": 100.0
            * (dev_b4b_metric - dev_b4a_metric),
            "effect_source": "separately_trained_B4_systems",
        },
        "B4_pair_audit": b4_pair_audit,
        "payload_neutrality_audits": payload_audits,
        "state_hashes": {
            "initial": initial_hashes,
            "final": final_hashes,
        },
        "derangement": {
            "count": 1,
            "train_seed": train_derangement_seed,
            "development_seed": dev_derangement_seed,
            "formal_D_requirement_met": False,
        },
        "technical_checks": technical_checks,
        "walltime_seconds": time.perf_counter() - started,
    }


def _aggregate(seed_results: list[dict[str, Any]]) -> dict[str, Any]:
    split_metrics: dict[str, dict[str, Any]] = {}
    for split in ("train", "development"):
        split_metrics[split] = {}
        for system in SYSTEM_NAMES:
            values = [
                result["metrics"][split][system]["label_metrics"][
                    "case_balanced_macro_f1"
                ]
                for result in seed_results
            ]
            split_metrics[split][system] = {
                "case_balanced_macro_f1_values": values,
                "mean_case_balanced_macro_f1": sum(values) / len(values),
            }
    train_delta = [
        result["effects"]["train_delta_bind_percentage_points"]
        for result in seed_results
    ]
    dev_delta = [
        result["effects"]["development_delta_bind_percentage_points"]
        for result in seed_results
    ]
    frozen_hashes = [
        result["base_initial_state_hashes"]["frozen_vlm_sha256"]
        for result in seed_results
    ]
    trainable_hashes = [
        result["base_initial_state_hashes"]["trainable_sha256"]
        for result in seed_results
    ]
    complete_hashes = [
        result["base_initial_state_hashes"]["complete_sha256"]
        for result in seed_results
    ]
    return {
        "ordered_seeds": [result["seed"] for result in seed_results],
        "seed_count": len(seed_results),
        "metrics": split_metrics,
        "effects": {
            "train_delta_bind_percentage_points": {
                "values": train_delta,
                "mean": sum(train_delta) / len(train_delta),
            },
            "development_delta_bind_percentage_points": {
                "values": dev_delta,
                "mean": sum(dev_delta) / len(dev_delta),
            },
        },
        "state_hash_audit": {
            "frozen_vlm_hashes": frozen_hashes,
            "fixed_vlm_hash_equal_across_training_seeds": len(set(frozen_hashes)) == 1,
            "trainable_initial_hashes": trainable_hashes,
            "trainable_hash_difference_evaluated": len(seed_results) >= 2,
            "trainable_initial_hashes_differ_across_training_seeds": (
                len(seed_results) < 2
                or len(set(trainable_hashes)) == len(trainable_hashes)
            ),
            "complete_initial_hashes": complete_hashes,
            "B4_initial_hash_equal_within_every_seed": all(
                result["technical_checks"]["B4_trainable_initial_hash_equal"]
                and result["technical_checks"]["B4_complete_initial_hash_equal"]
                for result in seed_results
            ),
        },
        "all_seed_technical_status_complete": all(
            result["status"] in {"COMPLETE", "SMOKE_COMPLETE"}
            for result in seed_results
        ),
    }


def _competence_gate(
    *, args: argparse.Namespace, aggregate: dict[str, Any]
) -> dict[str, Any]:
    values = aggregate["metrics"]["train"]["B4b_oracle"][
        "case_balanced_macro_f1_values"
    ]
    exact_bank = tuple(args.seeds) == DEFAULT_SEED_BANK
    if args.mode != "D2":
        status = "NOT_APPLICABLE"
    elif args.smoke or not exact_bank:
        status = "NOT_EVALUABLE_INCOMPLETE_REGISTERED_SEED_BANK"
    elif any(value < 0.80 for value in values):
        status = "NOT_EVALUABLE_READOUT_INCOMPETENT"
    else:
        status = "PASS_D3_ELIGIBILITY"
    return {
        "name": "D2_train_competence",
        "status": status,
        "pass": status == "PASS_D3_ELIGIBILITY",
        "evaluated": args.mode == "D2" and not args.smoke and exact_bank,
        "B4b_train_macro_f1_values": values,
        "D3_eligibility_threshold_every_seed": 0.80,
        "strict_train_fit_threshold_every_seed": 0.95,
        "strict_train_fit_achieved_every_seed": all(value >= 0.95 for value in values),
        "hard_stop_threshold_any_seed_below": 0.80,
        "formal_claim_allowed": False,
    }


def _diagnostic_gate(
    *, args: argparse.Namespace, aggregate: dict[str, Any]
) -> dict[str, Any]:
    exact_bank = tuple(args.seeds) == DEFAULT_SEED_BANK
    dev_delta = aggregate["effects"]["development_delta_bind_percentage_points"]
    evaluated = not args.smoke and exact_bank
    if args.mode == "D3":
        criteria = {
            "exact_registered_seed_bank": exact_bank,
            "delta_bind_positive_every_seed": all(
                value > 0 for value in dev_delta["values"]
            ),
            "mean_delta_bind_at_least_5pp": dev_delta["mean"] >= 5.0,
        }
    else:
        criteria = {"exact_registered_seed_bank": exact_bank}
    return {
        "name": f"{args.mode}_engineering_diagnostic",
        "evaluated": evaluated,
        "pass": args.mode == "D3" and evaluated and all(criteria.values()),
        "criteria": criteria,
        "formal_claim_allowed": False,
        "cannot_repair_or_relabel_S075": True,
    }


def run_diagnostics(args: argparse.Namespace) -> dict[str, Any]:
    _validate_args(args)
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    started = time.perf_counter()
    config = _mode_config(args)
    config_sha256 = _json_hash(config)
    shared_parent = _shared_parent_config(config)
    shared_parent_config_sha256 = _json_hash(shared_parent)
    source_hashes = _source_hashes()
    prerequisite = _d3_prerequisite_audit(args, shared_parent_config_sha256)
    device = torch.device(args.device)
    train = make_anchor_batch(
        cases_per_class=TRAIN_CASES_PER_CLASS,
        feature_dim=FEATURE_DIM,
        seed=TRAIN_DATA_SEED,
        split="train",
        namespace=1,
    ).to(device)
    inner_dev = make_anchor_batch(
        cases_per_class=INNER_DEV_CASES_PER_CLASS,
        feature_dim=FEATURE_DIM,
        seed=INNER_DEV_DATA_SEED,
        split="development-inner",
        namespace=2,
    ).to(device)
    dev = make_anchor_batch(
        cases_per_class=DEV_CASES_PER_CLASS,
        feature_dim=FEATURE_DIM,
        seed=DEV_DATA_SEED,
        split="development",
        namespace=3,
    ).to(device)
    data_audits = {
        "train": audit_anchor_batch(train, derangement_seed=7_101),
        "development_inner": audit_anchor_batch(inner_dev, derangement_seed=7_103),
        "development": audit_anchor_batch(dev, derangement_seed=7_109),
    }
    data_checks_pass = all(
        all(audit["checks"].values()) for audit in data_audits.values()
    )
    neutralization_contract = None
    if MODE_SPECS[args.mode].neutralize_global_entity_payloads:
        audit_model = _build_seed_factorized_model(
            trainable_seed=args.seeds[0],
            feature_dim=FEATURE_DIM,
            hidden_size=HIDDEN_SIZE,
        ).to(device)
        audit_allocation = _shared_allocation(audit_model, train.regions)
        neutralization_contract = _neutralization_contract_audit(
            base_model=audit_model,
            batch=train,
            plan=train.oracle,
            allocation=audit_allocation,
        )

    common = {
        "protocol_version": PROTOCOL_VERSION,
        "mode": args.mode,
        "evidence_class": EVIDENCE_CLASS,
        "formal_claim_allowed": False,
        "formal_ablation_claim_allowed": False,
        "original_S075_status_mutable": False,
        "claim_boundary": (
            "D1-D3 are post-failure engineering diagnostics only; none can "
            "repair or relabel S075, unlock a formal run, or use the sealed test."
        ),
        "config": config,
        "config_sha256": config_sha256,
        "shared_parent_config": shared_parent,
        "shared_parent_config_sha256": shared_parent_config_sha256,
        "source_hashes": source_hashes,
        "data_audits": data_audits,
        "D3_prerequisite_audit": prerequisite,
        "D3_neutralization_contract_audit": neutralization_contract,
    }
    if args.dry_run:
        dry_checks = {
            "data_contract_pass": data_checks_pass,
            "D3_neutralization_contract_pass": neutralization_contract is None
            or neutralization_contract["pass"],
            "formal_test_used": False,
        }
        return {
            **common,
            "status": "DRY_RUN_VALIDATED"
            if dry_checks["data_contract_pass"]
            and dry_checks["D3_neutralization_contract_pass"]
            else "FAIL",
            "training_allowed": False,
            "dry_run_checks": dry_checks,
            "seed_results": [],
            "aggregate": None,
            "competence_gate": None,
            "diagnostic_gate": None,
            "walltime_seconds": time.perf_counter() - started,
        }
    if not prerequisite["training_allowed"]:
        return {
            **common,
            "status": "FAIL_PREREQUISITE",
            "training_allowed": False,
            "seed_results": [],
            "aggregate": None,
            "competence_gate": None,
            "diagnostic_gate": None,
            "walltime_seconds": time.perf_counter() - started,
        }

    seed_results = [
        _train_one_seed(
            seed=seed,
            args=args,
            train=train,
            dev=dev,
            config_sha256=config_sha256,
            source_manifest_sha256=source_hashes["manifest_sha256"],
        )
        for seed in args.seeds
    ]
    aggregate = _aggregate(seed_results)
    competence_gate = _competence_gate(args=args, aggregate=aggregate)
    diagnostic_gate = _diagnostic_gate(args=args, aggregate=aggregate)
    status = "SMOKE_COMPLETE" if args.smoke else "COMPLETE"
    technical_pass = (
        data_checks_pass
        and aggregate["all_seed_technical_status_complete"]
        and aggregate["state_hash_audit"]["fixed_vlm_hash_equal_across_training_seeds"]
        and aggregate["state_hash_audit"][
            "trainable_initial_hashes_differ_across_training_seeds"
        ]
        and (neutralization_contract is None or neutralization_contract["pass"])
    )
    if not technical_pass:
        status = "FAIL"
    return {
        **common,
        "status": status,
        "status_semantics": (
            "COMPLETE/SMOKE_COMPLETE means technical execution only; inspect "
            "competence_gate and diagnostic_gate separately."
        ),
        "training_allowed": True,
        "diagnostic_evaluable": not args.smoke
        and tuple(args.seeds) == DEFAULT_SEED_BANK,
        "seed_results": seed_results,
        "aggregate": aggregate,
        "competence_gate": competence_gate,
        "diagnostic_gate": diagnostic_gate,
        "walltime_seconds": time.perf_counter() - started,
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.run_dir.exists():
        raise FileExistsError(args.run_dir)
    summary = run_diagnostics(args)
    args.run_dir.mkdir(parents=True)
    for seed_result in summary["seed_results"]:
        path = args.run_dir / f"seed_{seed_result['seed']}.json"
        path.write_text(
            json.dumps(seed_result, indent=2, sort_keys=True), encoding="utf-8"
        )
    summary_path = args.run_dir / "summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps(summary, sort_keys=True))
    print(f"RESULT_DIR={args.run_dir.resolve()}")
    return (
        0
        if summary["status"] in {"COMPLETE", "SMOKE_COMPLETE", "DRY_RUN_VALIDATED"}
        else 2
    )


if __name__ == "__main__":
    raise SystemExit(main())
