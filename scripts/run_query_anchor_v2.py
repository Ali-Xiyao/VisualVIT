from __future__ import annotations

# ruff: noqa: E402

import argparse
import copy
from dataclasses import replace
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import sys
import time
from typing import Any, Mapping
import uuid

import torch
from torch import Tensor, nn
import torch.nn.functional as F

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE))
sys.path.insert(0, str(WORKSPACE / "src"))

from visualvit.allocator import DeterministicGlobalAllocator
from visualvit.baselines import (
    BalancedSinkhornBaseline,
    DevelopmentFrozenThreshold,
    HungarianRejectBaseline,
)
from visualvit.calibration_query import (
    LABEL_COUNT,
    LABEL_IMPROVED,
    QUERY_RELATION_SLOT,
    REGISTERED_DERANGEMENT_SEEDS,
    QueryAnchorBatch,
    audit_distractor_counterbalance,
    audit_gold_id_relabel_invariance,
    audit_hidden_id_separation,
    audit_marginal_non_identifiability,
    audit_wrong_query_counterbalance,
    build_balanced_derangement_bank,
    build_query_relation_tokens,
    make_global_assignment_query_anchor_batch,
    make_frozen_global_assignment_query_anchor_split,
    oracle_decode_labels,
    relabel_hidden_gold_ids,
    require_mechanism_gate_support,
)
from visualvit.matching import NullAwareMatchGraph
from visualvit.query_anchor_model import (
    QueryRelationProjector,
    build_frozen_query_adapter,
    query_prompt,
)
from visualvit.schemas import MatchPlan
from visualvit.tokenizer import build_soft_relation_candidates


PROTOCOL_VERSION = "CAPES_CI_QUERY_ANCHOR_V2_R3_2026_07_22"
EVIDENCE_CLASS = "QUERY_GATED_RELATION_MEDIATOR_ENGINEERING_NONCONFIRMATORY"
TRAINABLE_SEEDS = (17, 29, 43)
FROZEN_READOUT_SEED = 91_001
REGISTERED_STEPS = 500
LEARNING_RATE = 2e-2
FEATURE_DIM = 18
QUERY_RAW_DIM = 6
QUERY_HIDDEN_SIZE = 8
LABEL_NAMES = ("stable", "worse", "improved", "new", "resolved")
COMPETENCE_TRAIN_SEED = 76_401
COMPETENCE_DEVELOPMENT_SEED = 77_401
COMPETENCE_SEED_OFFSET = 1_000_000
COMPETENCE_SIGNAL_CHANNELS = (15, 16, 17)
COMPETENCE_SIGNAL_AMPLITUDE = 4.0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the fail-closed CAPES-CI v2 query-conditioned anchor."
    )
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--steps", type=int, default=REGISTERED_STEPS)
    parser.add_argument("--seeds", type=int, nargs="+", default=list(TRAINABLE_SEEDS))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--device", choices=("cpu",), default="cpu")
    return parser


def _json_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _state_hash(module: nn.Module) -> str:
    return _state_dict_hash(module.state_dict())


def _state_dict_hash(state: Mapping[str, Tensor]) -> str:
    digest = hashlib.sha256()
    for name, value in sorted(state.items()):
        digest.update(name.encode("utf-8"))
        contiguous = value.detach().cpu().contiguous()
        digest.update(str(contiguous.dtype).encode("ascii"))
        digest.update(str(tuple(contiguous.shape)).encode("ascii"))
        digest.update(contiguous.numpy().tobytes())
    return digest.hexdigest()


def _tensor_hash(value: Tensor) -> str:
    digest = hashlib.sha256()
    contiguous = value.detach().cpu().contiguous()
    digest.update(str(contiguous.dtype).encode("ascii"))
    digest.update(str(tuple(contiguous.shape)).encode("ascii"))
    digest.update(contiguous.numpy().tobytes())
    return digest.hexdigest()


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _source_manifest() -> dict[str, Any]:
    paths = [
        Path(__file__).resolve(),
        WORKSPACE / "scripts" / "run_query_anchor_v2_reproduction.py",
        *sorted((WORKSPACE / "src" / "visualvit").glob("*.py")),
        WORKSPACE / "refine-logs" / "CALIBRATION_PROTOCOL_R2_2026-07-22.md",
        WORKSPACE / "refine-logs" / "CALIBRATION_PROTOCOL_R3_2026-07-22.md",
        WORKSPACE / "tests" / "test_calibration_query.py",
        WORKSPACE / "tests" / "test_query_anchor_model.py",
        WORKSPACE / "tests" / "test_query_anchor_v2_runner.py",
        WORKSPACE / "pyproject.toml",
    ]
    files = {
        str(path.relative_to(WORKSPACE)).replace("\\", "/"): _file_hash(path)
        for path in paths
    }
    return {"files": files, "sha256": _json_hash(files)}


def _split_manifest(batch: QueryAnchorBatch) -> dict[str, Any]:
    tensors = {
        "regions.prior_features": batch.regions.prior_features,
        "regions.current_features": batch.regions.current_features,
        "regions.prior_valid": batch.regions.prior_valid,
        "regions.current_valid": batch.regions.current_valid,
        "regions.prior_anatomy": batch.regions.prior_anatomy,
        "regions.current_anatomy": batch.regions.current_anatomy,
        "regions.prior_entity_ids": batch.regions.prior_entity_ids,
        "regions.current_entity_ids": batch.regions.current_entity_ids,
        "prior_query_marker": batch.prior_query_marker,
        "current_query_marker": batch.current_query_marker,
        "prior_carrier_control": batch.prior_carrier_control,
        "current_carrier_control": batch.current_carrier_control,
        "counterbalance_index": batch.counterbalance_index,
        "oracle.prior_gold_ids": batch.oracle.prior_gold_ids,
        "oracle.current_gold_ids": batch.oracle.current_gold_ids,
        "oracle.labels": batch.oracle.labels,
        "oracle.plan.transport": batch.oracle.plan.transport,
    }
    tensor_hashes = {name: _tensor_hash(value) for name, value in tensors.items()}
    return {
        "case_count": int(batch.oracle.labels.numel()),
        "ordered_tensor_sha256": tensor_hashes,
        "composite_sha256": _json_hash(tensor_hashes),
    }


def _runtime_environment() -> dict[str, Any]:
    return {
        "python": platform.python_version(),
        "python_executable": str(Path(sys.executable).resolve()),
        "platform": platform.platform(),
        "torch": torch.__version__,
        "torch_num_threads": torch.get_num_threads(),
        "deterministic_algorithms_enabled": torch.are_deterministic_algorithms_enabled(),
        "pythonhashseed": os.environ.get("PYTHONHASHSEED"),
        "omp_num_threads": os.environ.get("OMP_NUM_THREADS"),
        "mkl_num_threads": os.environ.get("MKL_NUM_THREADS"),
    }


def _macro_f1(predictions: Tensor, targets: Tensor, label_count: int) -> float:
    values: list[float] = []
    for label in range(label_count):
        predicted = predictions == label
        gold = targets == label
        tp = int((predicted & gold).sum())
        fp = int((predicted & ~gold).sum())
        fn = int((~predicted & gold).sum())
        denominator = 2 * tp + fp + fn
        values.append(2 * tp / denominator if denominator else 0.0)
    return sum(values) / label_count


def _classification_evidence(predictions: Tensor, targets: Tensor) -> dict[str, Any]:
    return {
        "predictions": predictions.detach().cpu().tolist(),
        "targets": targets.detach().cpu().tolist(),
    }


def _label_metrics(scores: Tensor, labels: Tensor) -> dict[str, Any]:
    predictions = scores.argmax(dim=-1)
    persistent = labels <= LABEL_IMPROVED
    return {
        "five_label_macro_f1": _macro_f1(predictions, labels, LABEL_COUNT),
        "persistent_three_label_macro_f1": _macro_f1(
            predictions[persistent], labels[persistent], 3
        ),
        "accuracy": float((predictions == labels).float().mean()),
        "predictions": predictions.detach().cpu().tolist(),
        "targets": labels.detach().cpu().tolist(),
    }


def _initial_projector(seed: int) -> QueryRelationProjector:
    projector = QueryRelationProjector(
        input_dim=QUERY_RAW_DIM,
        hidden_size=QUERY_HIDDEN_SIZE,
    )
    generator = torch.Generator(device="cpu").manual_seed(seed)
    with torch.no_grad():
        projector.projection.weight.add_(
            0.002
            * torch.randn(
                projector.projection.weight.shape,
                generator=generator,
                dtype=projector.projection.weight.dtype,
            )
        )
        projector.projection.bias.add_(
            0.002
            * torch.randn(
                projector.projection.bias.shape,
                generator=generator,
                dtype=projector.projection.bias.dtype,
            )
        )
    return projector


def _fixed_adapter() -> nn.Module:
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(FROZEN_READOUT_SEED)
        return build_frozen_query_adapter(hidden_size=QUERY_HIDDEN_SIZE)


def _contract(batch: QueryAnchorBatch, plan: MatchPlan):
    return build_query_relation_tokens(
        batch.regions,
        batch.prior_query_marker,
        batch.current_query_marker,
        plan,
        token_dim=QUERY_RAW_DIM,
    )


def _matching_regions(batch: QueryAnchorBatch):
    """Expose identity/anatomy only to matchers; marker/state are readout fields."""

    prior = batch.regions.prior_features.clone()
    current = batch.regions.current_features.clone()
    prior[..., :2] = 0
    current[..., :2] = 0
    return replace(
        batch.regions,
        prior_features=prior,
        current_features=current,
    )


def _cosine_baseline_contract(
    batch: QueryAnchorBatch,
) -> tuple[Tensor, Tensor, Tensor, Tensor, str]:
    regions = _matching_regions(batch)
    prior_identity = F.normalize(regions.prior_features[..., 2:], dim=-1)
    current_identity = F.normalize(regions.current_features[..., 2:], dim=-1)
    cost = 1.0 - torch.einsum("bid,bjd->bij", prior_identity, current_identity)
    prior_persistent = regions.prior_features[..., 2:14].norm(dim=-1) > 0.5
    current_persistent = regions.current_features[..., 2:14].norm(dim=-1) > 0.5
    support = (
        regions.prior_valid.unsqueeze(-1)
        & regions.current_valid.unsqueeze(-2)
        & regions.prior_anatomy.unsqueeze(-1).eq(regions.current_anatomy.unsqueeze(-2))
        & prior_persistent.unsqueeze(-1)
        & current_persistent.unsqueeze(-2)
    )
    prior_marginal = prior_persistent.to(cost.dtype)
    current_marginal = current_persistent.to(cost.dtype)
    contract_hash = _json_hash(
        {
            "cost": _tensor_hash(cost),
            "support": _tensor_hash(support),
            "prior_marginal": _tensor_hash(prior_marginal),
            "current_marginal": _tensor_hash(current_marginal),
        }
    )
    return cost, support, prior_marginal, current_marginal, contract_hash


def _restore_visible_null_residuals(
    plan: MatchPlan,
    batch: QueryAnchorBatch,
    prior_marginal: Tensor,
    current_marginal: Tensor,
) -> MatchPlan:
    transport = plan.transport.clone()
    prior_count = batch.regions.prior_features.shape[1]
    current_count = batch.regions.current_features.shape[1]
    transport[:, :prior_count, current_count] += 1.0 - prior_marginal
    transport[:, prior_count, :current_count] += 1.0 - current_marginal
    restored = MatchPlan(
        transport=transport,
        mode=f"{plan.mode}_visible_null_restored",
        edge_logits=plan.edge_logits,
        prior_null_logits=plan.prior_null_logits,
        current_null_logits=plan.current_null_logits,
        diagnostics=plan.diagnostics,
    )
    restored.validate(batch.regions)
    return restored


def _baseline_query_metrics(batch: QueryAnchorBatch, plan: MatchPlan) -> dict[str, Any]:
    prior_count = batch.regions.prior_features.shape[1]
    current_count = batch.regions.current_features.shape[1]
    predicted = plan.transport[:, :prior_count, :current_count]
    oracle = batch.oracle.plan.transport[:, :prior_count, :current_count]
    hard_correct: list[float] = []
    oracle_mass: list[float] = []
    for case_index in torch.nonzero(batch.persistent_main_mask).flatten().tolist():
        query_prior = int(torch.nonzero(batch.prior_query_marker[case_index]).item())
        oracle_current = int(
            torch.nonzero(oracle[case_index, query_prior] > 0.5).item()
        )
        row = predicted[case_index, query_prior]
        hard_correct.append(float(int(row.argmax()) == oracle_current))
        oracle_mass.append(float(row[oracle_current]))
    return {
        "hard_query_identity_accuracy": sum(hard_correct) / len(hard_correct),
        "mean_oracle_query_mass": sum(oracle_mass) / len(oracle_mass),
        "minimum_oracle_query_mass": min(oracle_mass),
    }


def _global_assignment_baseline_audit(
    splits: Mapping[str, QueryAnchorBatch],
) -> dict[str, Any]:
    threshold = DevelopmentFrozenThreshold(
        1.0,
        source_split="development-inner-synthetic-analytic-prerun",
        selection_rule="R2 analytic positive-similarity threshold frozen pre-run",
    )
    hungarian = HungarianRejectBaseline(threshold)
    sinkhorn = BalancedSinkhornBaseline(epsilon=0.05, iterations=2048)
    results: dict[str, Any] = {}
    for name in ("train", "inner_development", "development"):
        batch = splits[name]
        hard, soft, contract_hash = _global_assignment_baseline_plans(
            batch, hungarian=hungarian, sinkhorn=sinkhorn
        )
        hard_metrics = _baseline_query_metrics(batch, hard)
        soft_metrics = _baseline_query_metrics(batch, soft)
        checks = {
            "hungarian_query_identity_exact": hard_metrics[
                "hard_query_identity_accuracy"
            ]
            == 1.0,
            "sinkhorn_query_argmax_exact": soft_metrics["hard_query_identity_accuracy"]
            == 1.0,
            "sinkhorn_minimum_oracle_mass_at_least_0_90": soft_metrics[
                "minimum_oracle_query_mass"
            ]
            >= 0.90,
        }
        results[name] = {
            "passed": all(checks.values()),
            "checks": checks,
            "contract_sha256": contract_hash,
            "hungarian_plan_sha256": _tensor_hash(hard.transport),
            "sinkhorn_plan_sha256": _tensor_hash(soft.transport),
            "hungarian": hard_metrics,
            "sinkhorn": soft_metrics,
        }
    return {
        "passed": all(result["passed"] for result in results.values()),
        "threshold": {
            "value": threshold.value,
            "source_split": threshold.source_split,
            "selection_rule": threshold.selection_rule,
        },
        "sinkhorn": {"epsilon": 0.05, "iterations": 2048},
        "splits": results,
        "shared_contract_for_hungarian_and_sinkhorn": True,
        "uses_hidden_ids": False,
        "uses_oracle_cardinality": False,
    }


def _global_assignment_baseline_plans(
    batch: QueryAnchorBatch,
    *,
    hungarian: HungarianRejectBaseline | None = None,
    sinkhorn: BalancedSinkhornBaseline | None = None,
) -> tuple[MatchPlan, MatchPlan, str]:
    if hungarian is None:
        hungarian = HungarianRejectBaseline(
            DevelopmentFrozenThreshold(
                1.0,
                source_split="development-inner-synthetic-analytic-prerun",
                selection_rule="R2 analytic positive-similarity threshold frozen pre-run",
            )
        )
    if sinkhorn is None:
        sinkhorn = BalancedSinkhornBaseline(epsilon=0.05, iterations=2048)
    cost, support, prior, current, contract_hash = _cosine_baseline_contract(batch)
    hard_raw = hungarian(cost, support, prior, current)
    soft_raw = sinkhorn(cost, support, prior, current)
    hard = _restore_visible_null_residuals(hard_raw, batch, prior, current)
    soft = _restore_visible_null_residuals(soft_raw, batch, prior, current)
    return hard, soft, contract_hash


def _adapter_scores(
    projector: QueryRelationProjector,
    adapter: nn.Module,
    contract: Any,
    *,
    return_audit: bool = False,
    trace: dict[str, int] | None = None,
    phase: str = "unspecified",
) -> Tensor | tuple[Tensor, dict[str, Any]]:
    """Score labels only through the production exact-64 adapter path."""

    projected = projector(contract)
    prompt = query_prompt(
        projected.embeddings.shape[0], device=projected.embeddings.device
    )
    result = adapter.score_labels(prompt, projected, return_audit=return_audit)
    if trace is not None:
        trace[phase] = trace.get(phase, 0) + 1
    return result


def _adapter_equivalence_audit(
    projector: QueryRelationProjector,
    adapter: nn.Module,
    batch: QueryAnchorBatch,
    plan: MatchPlan,
) -> dict[str, Any]:
    contract = _contract(batch, plan)
    projected = projector(contract)
    direct = projected.embeddings[:, QUERY_RELATION_SLOT, :5]
    adapter_scores, adapter_audit = adapter.score_labels(
        query_prompt(batch.oracle.labels.numel()),
        projected,
        return_audit=True,
    )
    direct_centered = direct - direct[:, :1]
    adapter_centered = adapter_scores - adapter_scores[:, :1]
    max_error = float((direct_centered - adapter_centered).abs().max().detach())
    checks = {
        "centered_scores_equal": max_error <= 1e-6,
        "exact_64_placeholders": adapter_audit["placeholder_count"].eq(64).all().item(),
        "frozen_readout": bool(adapter_audit["model_frozen"]),
        "no_pixels": adapter_audit["pixel_inputs_used"] is False,
        "literal_zero_nonquery": bool(
            torch.count_nonzero(
                projected.embeddings
                * (~_query_slot_mask(projected.embeddings)).to(
                    projected.embeddings.dtype
                )
            )
            == 0
        ),
    }
    return {"passed": all(checks.values()), "checks": checks, "max_error": max_error}


def _query_slot_mask(embeddings: Tensor) -> Tensor:
    mask = torch.zeros_like(embeddings, dtype=torch.bool)
    mask[:, QUERY_RELATION_SLOT] = True
    return mask


def _exact64_execution_audit(
    *,
    trace: Mapping[str, int],
    train_audit: Mapping[str, Any],
    development_audit: Mapping[str, Any],
    frozen_unchanged: bool,
    steps: int,
) -> dict[str, Any]:
    observed = dict(trace)
    checks = {
        "training_call_count_exact": observed.get("training") == steps,
        "final_train_call_count_exact": observed.get("final_train_evaluation") == 1,
        "final_development_call_count_exact": observed.get(
            "final_development_evaluation"
        )
        == 1,
        "total_call_count_exact": sum(observed.values()) == steps + 2,
        "train_placeholders_exact64": bool(
            train_audit["placeholder_count"].eq(64).all()
        ),
        "development_placeholders_exact64": bool(
            development_audit["placeholder_count"].eq(64).all()
        ),
        "no_pixels": bool(
            train_audit["pixel_inputs_used"] is False
            and development_audit["pixel_inputs_used"] is False
        ),
        "model_frozen": bool(
            train_audit["model_frozen"] and development_audit["model_frozen"]
        ),
        "frozen_adapter_unchanged": frozen_unchanged,
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "observed_adapter_score_calls": observed,
        "observed_total_adapter_score_calls": sum(observed.values()),
        "train_placeholder_counts": train_audit["placeholder_count"].tolist(),
        "development_placeholder_counts": development_audit[
            "placeholder_count"
        ].tolist(),
        "pixel_inputs_used": bool(
            train_audit["pixel_inputs_used"] or development_audit["pixel_inputs_used"]
        ),
        "model_frozen": bool(
            train_audit["model_frozen"] and development_audit["model_frozen"]
        ),
    }


def _train_provided(
    *,
    adapter: nn.Module,
    initial_state: Mapping[str, Tensor],
    train_batch: QueryAnchorBatch,
    development_batch: QueryAnchorBatch,
    train_plan: MatchPlan,
    development_plan: MatchPlan,
    steps: int,
) -> dict[str, Any]:
    projector = QueryRelationProjector(QUERY_RAW_DIM, QUERY_HIDDEN_SIZE)
    projector.load_state_dict(initial_state, strict=True)
    initial_hash = _state_hash(projector)
    frozen_before_hash = _state_hash(adapter)
    optimizer = torch.optim.AdamW(
        projector.parameters(), lr=LEARNING_RATE, weight_decay=0.0
    )
    train_contract = _contract(train_batch, train_plan)
    losses: list[float] = []
    adapter_trace: dict[str, int] = {}
    for _ in range(steps):
        optimizer.zero_grad(set_to_none=True)
        scores = _adapter_scores(
            projector,
            adapter,
            train_contract,
            trace=adapter_trace,
            phase="training",
        )
        loss = F.cross_entropy(scores, train_batch.oracle.labels)
        loss.backward()
        optimizer.step()
        losses.append(float(loss.detach()))
    with torch.inference_mode():
        train_scores, train_adapter_audit = _adapter_scores(
            projector,
            adapter,
            train_contract,
            return_audit=True,
            trace=adapter_trace,
            phase="final_train_evaluation",
        )
        development_scores, development_adapter_audit = _adapter_scores(
            projector,
            adapter,
            _contract(development_batch, development_plan),
            return_audit=True,
            trace=adapter_trace,
            phase="final_development_evaluation",
        )
    final_hash = _state_hash(projector)
    frozen_after_hash = _state_hash(adapter)
    frozen_unchanged = frozen_before_hash == frozen_after_hash
    exact64_audit = _exact64_execution_audit(
        trace=adapter_trace,
        train_audit=train_adapter_audit,
        development_audit=development_adapter_audit,
        frozen_unchanged=frozen_unchanged,
        steps=steps,
    )
    return {
        "model": projector,
        "initial_state_sha256": initial_hash,
        "final_state_sha256": final_hash,
        "complete_initial_state_sha256": _json_hash(
            {"frozen_adapter": frozen_before_hash, "projector": initial_hash}
        ),
        "complete_final_state_sha256": _json_hash(
            {"frozen_adapter": frozen_after_hash, "projector": final_hash}
        ),
        "frozen_adapter_before_sha256": frozen_before_hash,
        "frozen_adapter_after_sha256": frozen_after_hash,
        "frozen_adapter_unchanged": frozen_unchanged,
        "initial_loss": losses[0] if losses else None,
        "final_loss": losses[-1] if losses else None,
        "train_plan_sha256": _tensor_hash(train_plan.transport),
        "development_plan_sha256": _tensor_hash(development_plan.transport),
        "exact64_execution_audit": exact64_audit,
        "train": _label_metrics(train_scores, train_batch.oracle.labels),
        "development": _label_metrics(
            development_scores, development_batch.oracle.labels
        ),
    }


def _train_learned(
    *,
    adapter: nn.Module,
    seed: int,
    initial_projector_state: Mapping[str, Tensor],
    train_batch: QueryAnchorBatch,
    development_batch: QueryAnchorBatch,
    steps: int,
) -> dict[str, Any]:
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(seed)
        matcher = NullAwareMatchGraph(
            feature_dim=FEATURE_DIM,
            hidden_dim=16,
            temperature=0.45,
            projection_iterations=20,
        )
    projector = QueryRelationProjector(QUERY_RAW_DIM, QUERY_HIDDEN_SIZE)
    projector.load_state_dict(initial_projector_state, strict=True)
    initial_hashes = {
        "matcher": _state_hash(matcher),
        "projector": _state_hash(projector),
    }
    frozen_before_hash = _state_hash(adapter)
    optimizer = torch.optim.AdamW(
        list(matcher.parameters()) + list(projector.parameters()),
        lr=LEARNING_RATE,
        weight_decay=0.0,
    )
    losses: list[float] = []
    adapter_trace: dict[str, int] = {}
    for _ in range(steps):
        optimizer.zero_grad(set_to_none=True)
        plan = matcher.soft_plan(_matching_regions(train_batch))
        scores = _adapter_scores(
            projector,
            adapter,
            _contract(train_batch, plan),
            trace=adapter_trace,
            phase="training",
        )
        loss = F.cross_entropy(scores, train_batch.oracle.labels)
        loss.backward()
        optimizer.step()
        losses.append(float(loss.detach()))
    with torch.inference_mode():
        train_soft = matcher.soft_plan(_matching_regions(train_batch))
        development_soft = matcher.soft_plan(_matching_regions(development_batch))
        train_scores, train_adapter_audit = _adapter_scores(
            projector,
            adapter,
            _contract(train_batch, train_soft),
            return_audit=True,
            trace=adapter_trace,
            phase="final_train_evaluation",
        )
        development_scores, development_adapter_audit = _adapter_scores(
            projector,
            adapter,
            _contract(development_batch, development_soft),
            return_audit=True,
            trace=adapter_trace,
            phase="final_development_evaluation",
        )
        development_hard = matcher.hard_plan(_matching_regions(development_batch))
    final_hashes = {
        "matcher": _state_hash(matcher),
        "projector": _state_hash(projector),
    }
    frozen_after_hash = _state_hash(adapter)
    frozen_unchanged = frozen_before_hash == frozen_after_hash
    exact64_audit = _exact64_execution_audit(
        trace=adapter_trace,
        train_audit=train_adapter_audit,
        development_audit=development_adapter_audit,
        frozen_unchanged=frozen_unchanged,
        steps=steps,
    )
    return {
        "matcher": matcher,
        "projector": projector,
        "initial_state_sha256": initial_hashes,
        "final_state_sha256": final_hashes,
        "complete_initial_state_sha256": _json_hash(
            {"frozen_adapter": frozen_before_hash, **initial_hashes}
        ),
        "complete_final_state_sha256": _json_hash(
            {"frozen_adapter": frozen_after_hash, **final_hashes}
        ),
        "frozen_adapter_before_sha256": frozen_before_hash,
        "frozen_adapter_after_sha256": frozen_after_hash,
        "frozen_adapter_unchanged": frozen_unchanged,
        "initial_loss": losses[0] if losses else None,
        "final_loss": losses[-1] if losses else None,
        "exact64_execution_audit": exact64_audit,
        "train": _label_metrics(train_scores, train_batch.oracle.labels),
        "development": _label_metrics(
            development_scores, development_batch.oracle.labels
        ),
        "assignment": _assignment_diagnostics(
            development_batch, development_soft, development_hard
        ),
    }


def _assignment_diagnostics(
    batch: QueryAnchorBatch,
    soft: MatchPlan,
    hard: MatchPlan,
) -> dict[str, Any]:
    prior_count = batch.regions.prior_features.shape[1]
    current_count = batch.regions.current_features.shape[1]
    oracle_real = batch.oracle.plan.transport[:, :prior_count, :current_count]
    soft_real = soft.transport[:, :prior_count, :current_count]
    hard_real = hard.transport[:, :prior_count, :current_count]
    persistent_cases = torch.nonzero(batch.persistent_main_mask).flatten().tolist()
    correct: list[float] = []
    oracle_mass: list[float] = []
    brier: list[float] = []
    nll: list[float] = []
    for case_index in persistent_cases:
        query_prior = int(torch.nonzero(batch.prior_query_marker[case_index]).item())
        oracle_current = int(
            torch.nonzero(oracle_real[case_index, query_prior] > 0.5).item()
        )
        predicted = torch.nonzero(
            hard_real[case_index, query_prior] > 0.5, as_tuple=False
        ).flatten()
        correct.append(
            float(len(predicted) == 1 and int(predicted.item()) == oracle_current)
        )
        row = soft_real[case_index, query_prior]
        mass = float(row[oracle_current])
        oracle_mass.append(mass)
        nll.append(-math.log(max(mass, 1e-8)))
        probability_row = row.detach().cpu().tolist()
        brier.append(
            math.fsum(
                (value - (1.0 if column == oracle_current else 0.0)) ** 2
                for column, value in enumerate(probability_row)
            )
            / len(probability_row)
        )
    return {
        "hard_query_identity_accuracy": math.fsum(correct) / len(correct),
        "hard_query_identity_f1": math.fsum(correct) / len(correct),
        "hard_query_identity_chance_reference": 1.0 / 6.0,
        "soft_oracle_query_mass": math.fsum(oracle_mass) / len(oracle_mass),
        "soft_oracle_mass_chance_reference": 1.0 / 6.0,
        "soft_query_nll": math.fsum(nll) / len(nll),
        "soft_query_brier": math.fsum(brier) / len(brier),
    }


def _side_summary(features: Tensor, anatomy: Tensor) -> Tensor:
    moments = torch.cat(
        (
            features.mean(dim=1),
            features.std(dim=1, unbiased=False),
            features.amin(dim=1),
            features.amax(dim=1),
        ),
        dim=-1,
    )
    anatomy_counts = torch.stack(
        ((anatomy == 0).float().mean(dim=1), (anatomy == 1).float().mean(dim=1)),
        dim=-1,
    )
    return torch.cat((moments, anatomy_counts), dim=-1)


def _marginal_features(batch: QueryAnchorBatch, mode: str) -> Tensor:
    current = _side_summary(
        batch.regions.current_features, batch.regions.current_anatomy
    )
    if mode == "current_only":
        return current
    if mode != "prior_current_separate_pooling":
        raise ValueError("unknown marginal-control mode")
    prior = _side_summary(batch.regions.prior_features, batch.regions.prior_anatomy)
    return torch.cat((prior, current), dim=-1)


class _SeparatePoolControl(nn.Module):
    """Permutation-invariant visible-only control with no prior-current pair axis."""

    def __init__(self, mode: str, *, feature_dim: int, hidden_dim: int = 32) -> None:
        super().__init__()
        if mode not in {
            "current_only_deepsets",
            "prior_only_deepsets",
            "prior_current_deepsets",
        }:
            raise ValueError("unknown DeepSets marginal-control mode")
        self.mode = mode
        input_dim = feature_dim + 2

        def encoder() -> nn.Sequential:
            return nn.Sequential(
                nn.Linear(input_dim, hidden_dim),
                nn.GELU(),
                nn.Linear(hidden_dim, hidden_dim),
                nn.GELU(),
            )

        self.prior_encoder = encoder() if mode != "current_only_deepsets" else None
        self.current_encoder = encoder() if mode != "prior_only_deepsets" else None
        side_count = 2 if mode == "prior_current_deepsets" else 1
        self.classifier = nn.Sequential(
            nn.Linear(side_count * hidden_dim * 2, 64),
            nn.GELU(),
            nn.Linear(64, 3),
        )

    @staticmethod
    def _pool(
        features: Tensor,
        anatomy: Tensor,
        valid: Tensor,
        encoder: nn.Module,
    ) -> Tensor:
        anatomy_one_hot = F.one_hot(anatomy, num_classes=2).to(features.dtype)
        encoded = encoder(torch.cat((features, anatomy_one_hot), dim=-1))
        mask = valid.unsqueeze(-1)
        count = mask.sum(dim=1).clamp_min(1).to(encoded.dtype)
        mean = (encoded * mask.to(encoded.dtype)).sum(dim=1) / count
        maximum = torch.where(mask, encoded, torch.full_like(encoded, -torch.inf)).amax(
            dim=1
        )
        maximum = torch.where(
            torch.isfinite(maximum), maximum, torch.zeros_like(maximum)
        )
        return torch.cat((mean, maximum), dim=-1)

    def forward(self, batch: QueryAnchorBatch) -> Tensor:
        sides: list[Tensor] = []
        if self.prior_encoder is not None:
            sides.append(
                self._pool(
                    batch.regions.prior_features,
                    batch.regions.prior_anatomy,
                    batch.regions.prior_valid,
                    self.prior_encoder,
                )
            )
        if self.current_encoder is not None:
            sides.append(
                self._pool(
                    batch.regions.current_features,
                    batch.regions.current_anatomy,
                    batch.regions.current_valid,
                    self.current_encoder,
                )
            )
        return self.classifier(torch.cat(sides, dim=-1))


def _marginal_competence_probe_batch(
    batch: QueryAnchorBatch, mode: str, *, code_shift: int = 0
) -> tuple[QueryAnchorBatch, str]:
    """Inject a three-channel label code into a separate positive-control copy."""

    prior = batch.regions.prior_features.clone()
    current = batch.regions.current_features.clone()
    signal_side = "current" if mode == "current_only_deepsets" else "prior"
    if mode not in {
        "current_only_deepsets",
        "prior_only_deepsets",
        "prior_current_deepsets",
    }:
        raise ValueError("competence probe is defined only for DeepSets controls")
    target = current if signal_side == "current" else prior
    valid = (
        batch.regions.current_valid
        if signal_side == "current"
        else batch.regions.prior_valid
    )
    target[..., list(COMPETENCE_SIGNAL_CHANNELS)] = 0.0
    persistent = batch.persistent_main_mask
    code = (batch.oracle.labels[persistent] + code_shift).remainder(3)
    for row, label in zip(torch.nonzero(persistent).flatten(), code, strict=True):
        channel = COMPETENCE_SIGNAL_CHANNELS[int(label)]
        target[int(row), valid[int(row)], channel] = COMPETENCE_SIGNAL_AMPLITUDE
    return (
        replace(
            batch,
            regions=replace(
                batch.regions,
                prior_features=prior,
                current_features=current,
            ),
        ),
        signal_side,
    )


def _train_marginal_competence_probe(
    *, seed: int, mode: str, steps: int
) -> dict[str, Any]:
    train_batch = make_global_assignment_query_anchor_batch(
        cases_per_label=16, seed=COMPETENCE_TRAIN_SEED, feature_dim=FEATURE_DIM
    )
    development_batch = make_global_assignment_query_anchor_batch(
        cases_per_label=24,
        seed=COMPETENCE_DEVELOPMENT_SEED,
        feature_dim=FEATURE_DIM,
    )
    probe_train, signal_side = _marginal_competence_probe_batch(train_batch, mode)
    probe_development, _ = _marginal_competence_probe_batch(development_batch, mode)
    deranged_development, _ = _marginal_competence_probe_batch(
        development_batch, mode, code_shift=1
    )
    train_mask = train_batch.persistent_main_mask
    development_mask = development_batch.persistent_main_mask
    train_y = train_batch.oracle.labels[train_mask]
    development_y = development_batch.oracle.labels[development_mask]
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(seed + COMPETENCE_SEED_OFFSET)
        classifier = _SeparatePoolControl(
            mode, feature_dim=train_batch.regions.prior_features.shape[-1]
        )
    initial_state_hash = _state_hash(classifier)
    optimizer = torch.optim.AdamW(
        classifier.parameters(), lr=LEARNING_RATE, weight_decay=0.0
    )
    initial_loss: float | None = None
    all_gradients_finite = True
    finite_gradient_steps = 0
    for step in range(steps):
        optimizer.zero_grad(set_to_none=True)
        loss = F.cross_entropy(classifier(probe_train)[train_mask], train_y)
        if step == 0:
            initial_loss = float(loss.detach())
        loss.backward()
        gradients_finite = all(
            parameter.grad is None or bool(torch.isfinite(parameter.grad).all())
            for parameter in classifier.parameters()
        )
        all_gradients_finite = all_gradients_finite and gradients_finite
        finite_gradient_steps += int(gradients_finite)
        optimizer.step()
    with torch.inference_mode():
        train_logits = classifier(probe_train)[train_mask]
        development_logits = classifier(probe_development)[development_mask]
        deranged_predictions = classifier(deranged_development)[
            development_mask
        ].argmax(dim=-1)
        prior_permutation = torch.arange(
            probe_development.regions.prior_features.shape[1] - 1, -1, -1
        )
        current_permutation = torch.roll(
            torch.arange(probe_development.regions.current_features.shape[1]), 3
        )
        permuted = replace(
            probe_development,
            regions=replace(
                probe_development.regions,
                prior_features=probe_development.regions.prior_features[
                    :, prior_permutation
                ],
                current_features=probe_development.regions.current_features[
                    :, current_permutation
                ],
                prior_valid=probe_development.regions.prior_valid[:, prior_permutation],
                current_valid=probe_development.regions.current_valid[
                    :, current_permutation
                ],
                prior_anatomy=probe_development.regions.prior_anatomy[
                    :, prior_permutation
                ],
                current_anatomy=probe_development.regions.current_anatomy[
                    :, current_permutation
                ],
            ),
        )
        permuted_logits = classifier(permuted)[development_mask]
    train_predictions = train_logits.argmax(dim=-1)
    development_predictions = development_logits.argmax(dim=-1)
    logit_differences = (development_logits - permuted_logits).detach().cpu()
    return {
        "signal": "amplitude-4 persistent-label one-hot",
        "signal_side": signal_side,
        "signal_channels": list(COMPETENCE_SIGNAL_CHANNELS),
        "signal_amplitude": COMPETENCE_SIGNAL_AMPLITUDE,
        "uses_separate_feature_copies": True,
        "train_seed": COMPETENCE_TRAIN_SEED,
        "development_seed": COMPETENCE_DEVELOPMENT_SEED,
        "model_seed": seed + COMPETENCE_SEED_OFFSET,
        "train_batch_sha256": _split_manifest(train_batch)["composite_sha256"],
        "development_batch_sha256": _split_manifest(development_batch)[
            "composite_sha256"
        ],
        "probe_train_feature_sha256": _tensor_hash(
            probe_train.regions.prior_features
            if signal_side == "prior"
            else probe_train.regions.current_features
        ),
        "probe_development_feature_sha256": _tensor_hash(
            probe_development.regions.prior_features
            if signal_side == "prior"
            else probe_development.regions.current_features
        ),
        "train_macro_f1": _macro_f1(train_predictions, train_y, 3),
        "development_macro_f1": _macro_f1(development_predictions, development_y, 3),
        "cyclic_code_derangement_macro_f1": _macro_f1(
            deranged_predictions, development_y, 3
        ),
        "permutation_invariance_max_logit_error": float(logit_differences.abs().max()),
        "raw_evidence": {
            "train": _classification_evidence(train_predictions, train_y),
            "development": _classification_evidence(
                development_predictions, development_y
            ),
            "deranged": _classification_evidence(deranged_predictions, development_y),
            "permutation": {
                "shape": list(logit_differences.shape),
                "logit_differences": logit_differences.flatten().tolist(),
            },
        },
        "initial_train_loss": initial_loss,
        "final_train_loss": float(F.cross_entropy(train_logits, train_y)),
        "development_loss": float(F.cross_entropy(development_logits, development_y)),
        "all_gradients_finite": all_gradients_finite,
        "finite_gradient_steps": finite_gradient_steps,
        "initial_state_sha256": initial_state_hash,
        "final_state_sha256": _state_hash(classifier),
    }


def _train_marginal_control(
    *,
    seed: int,
    train_batch: QueryAnchorBatch,
    development_batch: QueryAnchorBatch,
    mode: str,
    steps: int,
) -> dict[str, Any]:
    actual_visible_before = _json_hash(
        {
            "train_prior": _tensor_hash(train_batch.regions.prior_features),
            "train_current": _tensor_hash(train_batch.regions.current_features),
            "development_prior": _tensor_hash(development_batch.regions.prior_features),
            "development_current": _tensor_hash(
                development_batch.regions.current_features
            ),
        }
    )
    train_mask = train_batch.persistent_main_mask
    development_mask = development_batch.persistent_main_mask
    train_y = train_batch.oracle.labels[train_mask]
    development_y = development_batch.oracle.labels[development_mask]
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(seed)
        if mode.endswith("_deepsets"):
            classifier: nn.Module = _SeparatePoolControl(
                mode, feature_dim=train_batch.regions.prior_features.shape[-1]
            )
        else:
            train_x = _marginal_features(train_batch, mode)[train_mask]
            development_x = _marginal_features(development_batch, mode)[
                development_mask
            ]
            classifier = nn.Linear(train_x.shape[-1], 3)
    optimizer = torch.optim.AdamW(
        classifier.parameters(), lr=LEARNING_RATE, weight_decay=0.0
    )
    initial_loss: float | None = None
    final_loss = float("nan")
    all_gradients_finite = True
    finite_gradient_steps = 0
    for step in range(steps):
        optimizer.zero_grad(set_to_none=True)
        train_logits = (
            classifier(train_batch)[train_mask]
            if mode.endswith("_deepsets")
            else classifier(train_x)
        )
        loss = F.cross_entropy(train_logits, train_y)
        if step == 0:
            initial_loss = float(loss.detach())
        loss.backward()
        gradients_finite = all(
            parameter.grad is None or bool(torch.isfinite(parameter.grad).all())
            for parameter in classifier.parameters()
        )
        all_gradients_finite = all_gradients_finite and gradients_finite
        finite_gradient_steps += int(gradients_finite)
        optimizer.step()
        final_loss = float(loss.detach())
    with torch.inference_mode():
        if mode.endswith("_deepsets"):
            train_predictions = classifier(train_batch)[train_mask].argmax(dim=-1)
            development_predictions = classifier(development_batch)[
                development_mask
            ].argmax(dim=-1)
        else:
            train_predictions = classifier(train_x).argmax(dim=-1)
            development_predictions = classifier(development_x).argmax(dim=-1)
    result = {
        "mode": mode,
        "trainable_parameter_count": sum(p.numel() for p in classifier.parameters()),
        "train_macro_f1": _macro_f1(train_predictions, train_y, 3),
        "development_macro_f1": _macro_f1(development_predictions, development_y, 3),
        "raw_evidence": {
            "train": _classification_evidence(train_predictions, train_y),
            "development": _classification_evidence(
                development_predictions, development_y
            ),
        },
        "initial_train_loss": initial_loss,
        "final_train_loss": final_loss,
        "all_gradients_finite": all_gradients_finite,
        "finite_gradient_steps": finite_gradient_steps,
        "state_sha256": _state_hash(classifier),
        "uses_pair_axis": False,
        "permutation_invariant_per_side": True,
    }
    if mode.endswith("_deepsets"):
        result["competence_probe"] = _train_marginal_competence_probe(
            seed=seed,
            mode=mode,
            steps=steps,
        )
    actual_visible_after = _json_hash(
        {
            "train_prior": _tensor_hash(train_batch.regions.prior_features),
            "train_current": _tensor_hash(train_batch.regions.current_features),
            "development_prior": _tensor_hash(development_batch.regions.prior_features),
            "development_current": _tensor_hash(
                development_batch.regions.current_features
            ),
        }
    )
    result["actual_visible_before_sha256"] = actual_visible_before
    result["actual_visible_after_sha256"] = actual_visible_after
    result["actual_visible_unchanged"] = actual_visible_before == actual_visible_after
    return result


def _evaluate_marginal_control_gate(
    controls: Mapping[str, Mapping[str, Mapping[str, Any]]],
    seeds: tuple[int, ...],
    *,
    competence_required: bool,
) -> dict[str, Any]:
    development_checks = {
        str(seed): {
            mode: controls[str(seed)][mode]["development_macro_f1"] <= 0.45
            for mode in controls[str(seed)]
        }
        for seed in seeds
    }
    competence_checks = {
        str(seed): {
            mode: (
                controls[str(seed)][mode]["competence_probe"]["train_macro_f1"] >= 0.99
                and controls[str(seed)][mode]["competence_probe"][
                    "development_macro_f1"
                ]
                >= 0.99
                and controls[str(seed)][mode]["competence_probe"]["final_train_loss"]
                <= 0.05
                and controls[str(seed)][mode]["competence_probe"][
                    "all_gradients_finite"
                ]
                and controls[str(seed)][mode]["competence_probe"][
                    "finite_gradient_steps"
                ]
                == REGISTERED_STEPS
                and controls[str(seed)][mode]["competence_probe"][
                    "permutation_invariance_max_logit_error"
                ]
                <= 1e-4
                and controls[str(seed)][mode]["competence_probe"][
                    "cyclic_code_derangement_macro_f1"
                ]
                <= 0.10
                and controls[str(seed)][mode]["actual_visible_unchanged"]
            )
            for mode in (
                "current_only_deepsets",
                "prior_only_deepsets",
                "prior_current_deepsets",
            )
        }
        for seed in seeds
    }
    bypass_pass = all(
        all(seed_checks.values()) for seed_checks in development_checks.values()
    )
    competence_pass = all(
        all(seed_checks.values()) for seed_checks in competence_checks.values()
    )
    passed = bypass_pass and (competence_pass or not competence_required)
    if not bypass_pass:
        status = "FAIL_ASSIGNMENT_BYPASS"
    elif competence_required and not competence_pass:
        status = "NOT_EVALUABLE_MARGINAL_CONTROL_INCOMPETENT"
    else:
        status = "PASS"
    return {
        "status": status,
        "passed": passed,
        "maximum_persistent_development_macro_f1": 0.45,
        "minimum_deepsets_train_macro_f1": 0.99,
        "minimum_deepsets_development_macro_f1": 0.99,
        "maximum_deepsets_final_train_loss": 0.05,
        "maximum_permutation_invariance_logit_error": 1e-4,
        "maximum_cyclic_code_derangement_macro_f1": 0.10,
        "competence_required": competence_required,
        "development_checks": development_checks,
        "competence_checks": competence_checks,
        "checks": {
            str(seed): {
                mode: development_checks[str(seed)][mode]
                and (
                    competence_checks[str(seed)].get(mode, True)
                    or not competence_required
                )
                for mode in development_checks[str(seed)]
            }
            for seed in seeds
        },
    }


def _strip_models(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            key: _strip_models(item)
            for key, item in value.items()
            if key not in {"model", "matcher", "projector"}
        }
    if isinstance(value, list):
        return [_strip_models(item) for item in value]
    return value


def _canonical_reproduction_payload(summary: Mapping[str, Any]) -> dict[str, Any]:
    """Remove only nondeterministic runtime metadata before exact comparison."""

    return {
        key: copy.deepcopy(value)
        for key, value in summary.items()
        if key not in {"walltime_seconds", "process_identity"}
    }


def _mismatch_paths(left: Any, right: Any, path: str = "$") -> list[str]:
    if type(left) is not type(right):
        return [path]
    if isinstance(left, Mapping):
        paths: list[str] = []
        for key in sorted(set(left) | set(right)):
            child = f"{path}.{key}"
            if key not in left or key not in right:
                paths.append(child)
            else:
                paths.extend(_mismatch_paths(left[key], right[key], child))
        return paths
    if isinstance(left, list):
        if len(left) != len(right):
            return [path]
        paths = []
        for index, (left_item, right_item) in enumerate(zip(left, right, strict=True)):
            paths.extend(_mismatch_paths(left_item, right_item, f"{path}[{index}]"))
        return paths
    return [] if left == right else [path]


def _execution_result_eligible(result: Any, *, steps: int) -> bool:
    if not isinstance(result, Mapping):
        return False
    trace = result.get("exact64_execution_audit")
    if not isinstance(trace, Mapping):
        return False
    observed = trace.get("observed_adapter_score_calls")
    expected = {
        "training": steps,
        "final_train_evaluation": 1,
        "final_development_evaluation": 1,
    }
    required_hashes = (
        "initial_state_sha256",
        "final_state_sha256",
        "complete_initial_state_sha256",
        "complete_final_state_sha256",
        "frozen_adapter_before_sha256",
        "frozen_adapter_after_sha256",
    )
    return bool(
        trace.get("passed") is True
        and observed == expected
        and trace.get("observed_total_adapter_score_calls") == steps + 2
        and trace.get("pixel_inputs_used") is False
        and trace.get("model_frozen") is True
        and set(trace.get("train_placeholder_counts", ())) == {64}
        and set(trace.get("development_placeholder_counts", ())) == {64}
        and result.get("frozen_adapter_unchanged") is True
        and all(result.get(name) for name in required_hashes)
    )


def _marginal_controls_eligible(value: Any) -> bool:
    if not isinstance(value, Mapping) or set(value) != {
        str(seed) for seed in TRAINABLE_SEEDS
    }:
        return False
    modes = {
        "current_only",
        "prior_current_separate_pooling",
        "current_only_deepsets",
        "prior_only_deepsets",
        "prior_current_deepsets",
    }
    expected_side = {
        "current_only_deepsets": "current",
        "prior_only_deepsets": "prior",
        "prior_current_deepsets": "prior",
    }

    def sha256_like(item: Any) -> bool:
        return bool(
            isinstance(item, str)
            and len(item) == 64
            and all(character in "0123456789abcdef" for character in item.lower())
        )

    for seed in TRAINABLE_SEEDS:
        controls = value.get(str(seed))
        if not isinstance(controls, Mapping) or set(controls) != modes:
            return False
        for mode, control in controls.items():
            if not isinstance(control, Mapping):
                return False
            development_f1 = control.get("development_macro_f1")
            if not (
                isinstance(development_f1, (int, float))
                and math.isfinite(development_f1)
                and development_f1 <= 0.45
                and control.get("actual_visible_unchanged") is True
                and control.get("actual_visible_before_sha256")
                == control.get("actual_visible_after_sha256")
                and sha256_like(control.get("actual_visible_before_sha256"))
            ):
                return False
            if not mode.endswith("_deepsets"):
                continue
            probe = control.get("competence_probe")
            if not isinstance(probe, Mapping):
                return False
            checks = (
                probe.get("signal") == "amplitude-4 persistent-label one-hot",
                probe.get("signal_side") == expected_side[mode],
                probe.get("signal_channels") == list(COMPETENCE_SIGNAL_CHANNELS),
                probe.get("signal_amplitude") == COMPETENCE_SIGNAL_AMPLITUDE,
                probe.get("uses_separate_feature_copies") is True,
                probe.get("train_seed") == COMPETENCE_TRAIN_SEED,
                probe.get("development_seed") == COMPETENCE_DEVELOPMENT_SEED,
                probe.get("model_seed") == seed + COMPETENCE_SEED_OFFSET,
                probe.get("train_macro_f1", 0.0) >= 0.99,
                probe.get("development_macro_f1", 0.0) >= 0.99,
                probe.get("final_train_loss", math.inf) <= 0.05,
                probe.get("all_gradients_finite") is True,
                probe.get("finite_gradient_steps") == REGISTERED_STEPS,
                probe.get("permutation_invariance_max_logit_error", math.inf) <= 1e-4,
                probe.get("cyclic_code_derangement_macro_f1", math.inf) <= 0.10,
                sha256_like(probe.get("train_batch_sha256")),
                sha256_like(probe.get("development_batch_sha256")),
                sha256_like(probe.get("probe_train_feature_sha256")),
                sha256_like(probe.get("probe_development_feature_sha256")),
                sha256_like(probe.get("initial_state_sha256")),
                sha256_like(probe.get("final_state_sha256")),
            )
            if not all(checks):
                return False
    return True


def _registered_reproduction_eligibility(summary: Mapping[str, Any]) -> dict[str, Any]:
    config = summary.get("config")
    source_manifest = summary.get("source_manifest")
    split_manifests = summary.get("split_manifests")
    fairness = summary.get("pretraining_fairness")
    identity = summary.get("process_identity")
    environment = summary.get("runtime_environment")
    seeds = tuple(str(seed) for seed in TRAINABLE_SEEDS)
    derangements = tuple(str(seed) for seed in REGISTERED_DERANGEMENT_SEEDS)
    config_registered = bool(
        isinstance(config, Mapping)
        and config.get("trainable_seeds") == list(TRAINABLE_SEEDS)
        and config.get("derangement_seeds") == list(REGISTERED_DERANGEMENT_SEEDS)
        and config.get("actual_steps") == REGISTERED_STEPS
        and config.get("registered_steps") == REGISTERED_STEPS
        and config.get("dry_run") is False
        and config.get("smoke") is False
        and config.get("formal_test") == "SEALED"
        and config.get("protocol_version") == PROTOCOL_VERSION
        and config.get("evidence_class") == EVIDENCE_CLASS
        and config.get("competence_probe")
        == {
            "train_seed": COMPETENCE_TRAIN_SEED,
            "development_seed": COMPETENCE_DEVELOPMENT_SEED,
            "model_seed_offset": COMPETENCE_SEED_OFFSET,
            "signal_channels": list(COMPETENCE_SIGNAL_CHANNELS),
            "signal_amplitude": COMPETENCE_SIGNAL_AMPLITUDE,
            "train_cases_per_label": 16,
            "development_cases_per_label": 24,
        }
    )
    protocol_registered = bool(
        summary.get("protocol_version") == PROTOCOL_VERSION
        and summary.get("evidence_class") == EVIDENCE_CLASS
        and isinstance(config, Mapping)
        and summary.get("config_sha256") == _json_hash(config)
    )
    source_registered = source_manifest == _source_manifest()
    splits_registered = bool(
        isinstance(split_manifests, Mapping)
        and set(split_manifests) == {"train", "inner_development", "development"}
        and all(
            isinstance(split_manifests[name], Mapping)
            and split_manifests[name].get("composite_sha256")
            and split_manifests[name].get("ordered_tensor_sha256")
            for name in split_manifests
        )
    )
    fairness_registered = bool(
        isinstance(fairness, Mapping)
        and fairness.get("frozen_adapter_sha256")
        and fairness.get("trainable_initial_states_distinct_across_seeds") is True
        and set(fairness.get("trainable_initial_state_sha256", {})) == set(seeds)
        and set(fairness.get("split_order_sha256", {}))
        == {"train", "inner_development", "development"}
    )
    process_registered = bool(
        isinstance(identity, Mapping)
        and isinstance(identity.get("pid"), int)
        and identity.get("pid") > 0
        and isinstance(identity.get("instance_uuid"), str)
        and identity.get("instance_uuid")
    )
    environment_registered = bool(
        isinstance(environment, Mapping)
        and environment.get("deterministic_algorithms_enabled") is True
        and environment.get("pythonhashseed") == "0"
        and environment.get("omp_num_threads") == "1"
        and environment.get("mkl_num_threads") == "1"
    )
    gate_objects = {
        "structural_audits": summary.get("structural_audits"),
        "working_oracle_gate": summary.get("working_oracle_gate"),
        "marginal_control_gate": summary.get("marginal_control_gate"),
        "persistent_binding_gate": summary.get("persistent_binding_gate"),
        "learned_recovery_gate": summary.get("learned_recovery_gate"),
        "baseline_noninferiority_gate": summary.get("baseline_noninferiority_gate"),
    }
    gates_registered = all(
        isinstance(gate, Mapping) and gate.get("passed") is True
        for gate in gate_objects.values()
    )
    oracle_results = summary.get("oracle_results")
    b4a_results = summary.get("b4a_results")
    learned_results = summary.get("learned_results")
    baseline_results = summary.get("baseline_results")
    baseline_execution = summary.get("baseline_execution")
    marginal_controls = summary.get("marginal_controls")
    execution_registered = bool(
        isinstance(oracle_results, Mapping)
        and set(oracle_results) == set(seeds)
        and all(
            _execution_result_eligible(oracle_results[seed], steps=REGISTERED_STEPS)
            for seed in seeds
        )
        and isinstance(b4a_results, Mapping)
        and set(b4a_results) == set(seeds)
        and all(
            isinstance(b4a_results[seed], Mapping)
            and set(b4a_results[seed]) == set(derangements)
            and all(
                _execution_result_eligible(
                    b4a_results[seed][derangement], steps=REGISTERED_STEPS
                )
                for derangement in derangements
            )
            for seed in seeds
        )
        and isinstance(learned_results, Mapping)
        and set(learned_results) == set(seeds)
        and all(
            _execution_result_eligible(learned_results[seed], steps=REGISTERED_STEPS)
            for seed in seeds
        )
        and isinstance(baseline_results, Mapping)
        and set(baseline_results) == set(seeds)
        and all(
            isinstance(baseline_results[seed], Mapping)
            and set(baseline_results[seed]) == {"hungarian", "sinkhorn"}
            and all(
                _execution_result_eligible(
                    baseline_results[seed][name], steps=REGISTERED_STEPS
                )
                for name in ("hungarian", "sinkhorn")
            )
            for seed in seeds
        )
        and isinstance(baseline_execution, Mapping)
        and baseline_execution.get("plans_are_seed_invariant") is True
        and baseline_execution.get("train_contract_sha256")
        and baseline_execution.get("development_contract_sha256")
    )
    checks = {
        "awaiting_reproduction_status": summary.get("status")
        == "PASS_GATES_1_TO_6_AWAITING_INDEPENDENT_REPRODUCTION",
        "registered_config_complete": config_registered,
        "protocol_and_config_hash_registered": protocol_registered,
        "source_manifest_complete": source_registered,
        "split_manifests_complete": splits_registered,
        "pretraining_fairness_complete": fairness_registered,
        "process_identity_complete": process_registered,
        "deterministic_environment_complete": environment_registered,
        "gates_1_to_6_explicitly_passed": gates_registered,
        "registered_execution_states_and_traces_complete": execution_registered,
        "marginal_controls_and_competence_probes_complete": (
            _marginal_controls_eligible(marginal_controls)
        ),
        "formal_test_sealed": summary.get("formal_test_used") is False,
        "formal_claim_remains_closed": summary.get("formal_claim_allowed") is False,
        "reproduction_required": summary.get(
            "independent_process_reproduction_required"
        )
        is True,
    }
    return {"passed": all(checks.values()), "checks": checks}


def _valid_uuid(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        uuid.UUID(value)
    except (ValueError, AttributeError):
        return False
    return True


def _compare_independent_reproduction(
    primary: Mapping[str, Any],
    replica: Mapping[str, Any],
    *,
    primary_returncode: int,
    replica_returncode: int,
    primary_expected_pid: int,
    replica_expected_pid: int,
) -> dict[str, Any]:
    primary_payload = _canonical_reproduction_payload(primary)
    replica_payload = _canonical_reproduction_payload(replica)
    primary_sha = _json_hash(primary_payload)
    replica_sha = _json_hash(replica_payload)
    mismatches = _mismatch_paths(primary_payload, replica_payload)
    primary_identity = primary.get("process_identity", {})
    replica_identity = replica.get("process_identity", {})
    primary_eligibility = _registered_reproduction_eligibility(primary)
    replica_eligibility = _registered_reproduction_eligibility(replica)
    checks = {
        "primary_process_exit_zero": primary_returncode == 0,
        "replica_process_exit_zero": replica_returncode == 0,
        "canonical_payload_exact": not mismatches,
        "canonical_sha256_exact": primary_sha == replica_sha,
        "primary_registered_payload_eligible": primary_eligibility["passed"],
        "replica_registered_payload_eligible": replica_eligibility["passed"],
        "process_uuid_valid": _valid_uuid(primary_identity.get("instance_uuid"))
        and _valid_uuid(replica_identity.get("instance_uuid")),
        "independent_process_uuid": primary_identity.get("instance_uuid")
        != replica_identity.get("instance_uuid"),
        "primary_reported_pid_matches_launcher": primary_identity.get("pid")
        == primary_expected_pid,
        "replica_reported_pid_matches_launcher": replica_identity.get("pid")
        == replica_expected_pid,
    }
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "passed": all(checks.values()),
        "checks": checks,
        "primary_canonical_sha256": primary_sha,
        "replica_canonical_sha256": replica_sha,
        "primary_process_returncode": int(primary_returncode),
        "replica_process_returncode": int(replica_returncode),
        "primary_launcher_pid": int(primary_expected_pid),
        "replica_launcher_pid": int(replica_expected_pid),
        "mismatch_count": len(mismatches),
        "mismatch_paths": mismatches,
        "primary_eligibility": primary_eligibility,
        "replica_eligibility": replica_eligibility,
        "comparison_excludes_only": ["walltime_seconds", "process_identity"],
    }


def _structural_audits(
    splits: Mapping[str, QueryAnchorBatch], adapter: nn.Module
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name, batch in splits.items():
        derangements = build_balanced_derangement_bank(
            batch, REGISTERED_DERANGEMENT_SEEDS
        )
        derangement_audit = audit_wrong_query_counterbalance(batch, derangements)
        oracle_decoded = oracle_decode_labels(
            batch.regions,
            batch.prior_query_marker,
            batch.current_query_marker,
            batch.oracle.plan,
        )
        result[name] = {
            "oracle_decoder_exact": bool(
                torch.equal(oracle_decoded, batch.oracle.labels)
            ),
            "distractor_counterbalance": audit_distractor_counterbalance(batch),
            "marginal_structure": audit_marginal_non_identifiability(batch),
            "hidden_id_separation": audit_hidden_id_separation(batch),
            "derangement": derangement_audit,
        }
    development = splits["development"]
    development_derangements = build_balanced_derangement_bank(
        development, REGISTERED_DERANGEMENT_SEEDS
    )
    result["mechanism_support"] = require_mechanism_gate_support(
        development.oracle.labels,
        REGISTERED_DERANGEMENT_SEEDS,
        derangement_audit=audit_wrong_query_counterbalance(
            development, development_derangements
        ),
        minimum_per_label=24,
    )
    projector = _initial_projector(TRAINABLE_SEEDS[0])
    result["adapter_equivalence"] = _adapter_equivalence_audit(
        projector,
        adapter,
        splits["train"],
        splits["train"].oracle.plan,
    )
    relabeled = relabel_hidden_gold_ids(splits["train"], seed=999_991)
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(73_001)
        matcher = NullAwareMatchGraph(FEATURE_DIM, hidden_dim=16)
    before_plan = matcher.soft_plan(_matching_regions(splits["train"]))
    after_plan = matcher.soft_plan(_matching_regions(relabeled))
    allocator = DeterministicGlobalAllocator()
    before_allocation = allocator(
        build_soft_relation_candidates(splits["train"].regions, before_plan)
    )
    after_allocation = allocator(
        build_soft_relation_candidates(relabeled.regions, after_plan)
    )
    before_scores = _adapter_scores(
        projector, adapter, _contract(splits["train"], before_plan)
    )
    after_scores = _adapter_scores(projector, adapter, _contract(relabeled, after_plan))
    result["hidden_id_relabel_invariance"] = audit_gold_id_relabel_invariance(
        splits["train"],
        relabeled,
        outputs_before={
            "learned_plan": before_plan,
            "allocation": before_allocation.weights,
            "scores": before_scores,
        },
        outputs_after={
            "learned_plan": after_plan,
            "allocation": after_allocation.weights,
            "scores": after_scores,
        },
    )
    result["global_assignment_baselines"] = _global_assignment_baseline_audit(splits)
    checks: list[bool] = []
    for name in ("train", "inner_development", "development"):
        split = result[name]
        checks.extend(
            (
                split["oracle_decoder_exact"],
                split["distractor_counterbalance"]["passed"],
                split["marginal_structure"]["passed"],
                split["hidden_id_separation"]["passed"],
                split["derangement"]["passed"],
            )
        )
    checks.extend(
        (
            result["mechanism_support"]["status"] == "QUALIFIED",
            result["adapter_equivalence"]["passed"],
            result["hidden_id_relabel_invariance"]["passed"],
            result["global_assignment_baselines"]["passed"],
        )
    )
    result["passed"] = all(checks)
    return result


def run(args: argparse.Namespace) -> dict[str, Any]:
    torch.use_deterministic_algorithms(True)
    if args.steps <= 0:
        raise ValueError("steps must be positive")
    seeds = tuple(int(seed) for seed in args.seeds)
    if args.smoke and len(seeds) != 1:
        raise ValueError("smoke requires exactly one trainable seed")
    if not args.smoke and seeds != TRAINABLE_SEEDS:
        raise ValueError(f"registered runs require seeds {TRAINABLE_SEEDS}")
    actual_steps = 1 if args.smoke else args.steps
    if not args.smoke and not args.dry_run and args.steps != REGISTERED_STEPS:
        raise ValueError(f"registered runs require exactly {REGISTERED_STEPS} steps")

    start = time.perf_counter()
    splits = {
        name: make_frozen_global_assignment_query_anchor_split(
            name, feature_dim=FEATURE_DIM
        )
        for name in ("train", "inner_development", "development")
    }
    adapter = _fixed_adapter()
    structural = _structural_audits(splits, adapter)
    initial_states = {
        seed: copy.deepcopy(_initial_projector(seed).state_dict()) for seed in seeds
    }
    initial_state_hashes = {
        str(seed): _state_dict_hash(initial_states[seed]) for seed in seeds
    }
    split_manifests = {name: _split_manifest(batch) for name, batch in splits.items()}
    source_manifest = _source_manifest()
    frozen_adapter_sha256 = _state_hash(adapter)
    pretraining_fairness = {
        "frozen_adapter_sha256": frozen_adapter_sha256,
        "trainable_initial_state_sha256": initial_state_hashes,
        "trainable_initial_states_distinct_across_seeds": len(
            set(initial_state_hashes.values())
        )
        == len(initial_state_hashes),
        "split_order_sha256": {
            name: manifest["composite_sha256"]
            for name, manifest in split_manifests.items()
        },
    }
    config = {
        "protocol_version": PROTOCOL_VERSION,
        "evidence_class": EVIDENCE_CLASS,
        "trainable_seeds": list(seeds),
        "frozen_readout_seed": FROZEN_READOUT_SEED,
        "derangement_seeds": list(REGISTERED_DERANGEMENT_SEEDS),
        "registered_steps": REGISTERED_STEPS,
        "actual_steps": actual_steps,
        "learning_rate": LEARNING_RATE,
        "feature_dim": FEATURE_DIM,
        "query_raw_dim": QUERY_RAW_DIM,
        "query_hidden_size": QUERY_HIDDEN_SIZE,
        "competence_probe": {
            "train_seed": COMPETENCE_TRAIN_SEED,
            "development_seed": COMPETENCE_DEVELOPMENT_SEED,
            "model_seed_offset": COMPETENCE_SEED_OFFSET,
            "signal_channels": list(COMPETENCE_SIGNAL_CHANNELS),
            "signal_amplitude": COMPETENCE_SIGNAL_AMPLITUDE,
            "train_cases_per_label": 16,
            "development_cases_per_label": 24,
        },
        "formal_test": "SEALED",
        "device": args.device,
        "smoke": bool(args.smoke),
        "dry_run": bool(args.dry_run),
    }
    base = {
        "protocol_version": PROTOCOL_VERSION,
        "evidence_class": EVIDENCE_CLASS,
        "config": config,
        "config_sha256": _json_hash(config),
        "formal_claim_allowed": False,
        "formal_ablation_claim_allowed": False,
        "full_method_claim_allowed": False,
        "formal_test_used": False,
        "process_identity": {
            "pid": os.getpid(),
            "instance_uuid": str(uuid.uuid4()),
        },
        "runtime_environment": _runtime_environment(),
        "source_manifest": source_manifest,
        "split_manifests": split_manifests,
        "pretraining_fairness": pretraining_fairness,
        "structural_audits": structural,
        "gate_order": [
            "technical_integrity",
            "working_oracle",
            "marginal_control_identifiability",
            "persistent_binding",
            "learned_recovery",
            "baseline_noninferiority",
            "independent_process_reproduction",
        ],
    }
    if args.dry_run:
        return {
            **base,
            "status": "DRY_RUN_VALIDATED" if structural["passed"] else "FAIL",
            "training_allowed": False,
            "walltime_seconds": time.perf_counter() - start,
        }
    if not structural["passed"]:
        return {
            **base,
            "status": "FAIL_TECHNICAL_INTEGRITY",
            "training_allowed": False,
            "walltime_seconds": time.perf_counter() - start,
        }

    train_batch = splits["train"]
    development_batch = splits["development"]
    oracle_results: dict[str, Any] = {}
    for seed in seeds:
        oracle_results[str(seed)] = _train_provided(
            adapter=adapter,
            initial_state=initial_states[seed],
            train_batch=train_batch,
            development_batch=development_batch,
            train_plan=train_batch.oracle.plan,
            development_plan=development_batch.oracle.plan,
            steps=actual_steps,
        )
    oracle_gate_checks = {
        str(seed): {
            "train_five_at_least_0_90": oracle_results[str(seed)]["train"][
                "five_label_macro_f1"
            ]
            >= 0.90,
            "development_five_at_least_0_75": oracle_results[str(seed)]["development"][
                "five_label_macro_f1"
            ]
            >= 0.75,
            "train_persistent_at_least_0_95": oracle_results[str(seed)]["train"][
                "persistent_three_label_macro_f1"
            ]
            >= 0.95,
            "development_persistent_at_least_0_85": oracle_results[str(seed)][
                "development"
            ]["persistent_three_label_macro_f1"]
            >= 0.85,
            "frozen_adapter_unchanged": oracle_results[str(seed)][
                "frozen_adapter_unchanged"
            ],
            "exact64_execution_passed": oracle_results[str(seed)][
                "exact64_execution_audit"
            ]["passed"],
        }
        for seed in seeds
    }
    oracle_pass = all(
        all(seed_checks.values()) for seed_checks in oracle_gate_checks.values()
    )
    working_oracle_gate = {
        "status": "PASS" if oracle_pass else "NOT_EVALUABLE_ANCHOR_INCOMPETENT",
        "passed": oracle_pass,
        "checks": oracle_gate_checks,
    }
    if not oracle_pass and not args.smoke:
        return {
            **base,
            "status": "STOP_WORKING_ORACLE",
            "working_oracle_gate": working_oracle_gate,
            "oracle_results": _strip_models(oracle_results),
            "walltime_seconds": time.perf_counter() - start,
        }

    controls: dict[str, Any] = {}
    for seed in seeds:
        controls[str(seed)] = {
            mode: _train_marginal_control(
                seed=seed,
                train_batch=train_batch,
                development_batch=development_batch,
                mode=mode,
                steps=actual_steps,
            )
            for mode in (
                "current_only",
                "prior_current_separate_pooling",
                "current_only_deepsets",
                "prior_only_deepsets",
                "prior_current_deepsets",
            )
        }
    competence_required = not args.smoke
    marginal_gate = _evaluate_marginal_control_gate(
        controls, seeds, competence_required=competence_required
    )
    controls_pass = marginal_gate["passed"]
    if not controls_pass and not args.smoke:
        return {
            **base,
            "status": "STOP_MARGINAL_CONTROL",
            "working_oracle_gate": working_oracle_gate,
            "marginal_control_gate": marginal_gate,
            "oracle_results": _strip_models(oracle_results),
            "marginal_controls": controls,
            "walltime_seconds": time.perf_counter() - start,
        }

    train_hungarian, train_sinkhorn, train_baseline_contract_hash = (
        _global_assignment_baseline_plans(train_batch)
    )
    development_hungarian, development_sinkhorn, development_baseline_contract_hash = (
        _global_assignment_baseline_plans(development_batch)
    )
    baseline_plans = {
        "hungarian": (train_hungarian, development_hungarian),
        "sinkhorn": (train_sinkhorn, development_sinkhorn),
    }
    baseline_results: dict[str, Any] = {}
    for seed in seeds:
        baseline_results[str(seed)] = {
            name: _train_provided(
                adapter=adapter,
                initial_state=initial_states[seed],
                train_batch=train_batch,
                development_batch=development_batch,
                train_plan=plans[0],
                development_plan=plans[1],
                steps=actual_steps,
            )
            for name, plans in baseline_plans.items()
        }
    baseline_execution = {
        "train_contract_sha256": train_baseline_contract_hash,
        "development_contract_sha256": development_baseline_contract_hash,
        "train_plan_sha256": {
            name: _tensor_hash(plans[0].transport)
            for name, plans in baseline_plans.items()
        },
        "development_plan_sha256": {
            name: _tensor_hash(plans[1].transport)
            for name, plans in baseline_plans.items()
        },
        "seed_plan_sha256": {
            str(seed): {
                name: {
                    "train": baseline_results[str(seed)][name]["train_plan_sha256"],
                    "development": baseline_results[str(seed)][name][
                        "development_plan_sha256"
                    ],
                }
                for name in baseline_plans
            }
            for seed in seeds
        },
    }
    baseline_execution["plans_are_seed_invariant"] = all(
        len(
            {
                baseline_execution["seed_plan_sha256"][str(seed)][name][split]
                for seed in seeds
            }
        )
        == 1
        for name in baseline_plans
        for split in ("train", "development")
    )

    train_derangements = build_balanced_derangement_bank(
        train_batch, REGISTERED_DERANGEMENT_SEEDS
    )
    development_derangements = build_balanced_derangement_bank(
        development_batch, REGISTERED_DERANGEMENT_SEEDS
    )
    b4a_results: dict[str, Any] = {}
    for seed in seeds:
        b4a_results[str(seed)] = {}
        for derangement_seed in REGISTERED_DERANGEMENT_SEEDS:
            b4a_results[str(seed)][str(derangement_seed)] = _train_provided(
                adapter=adapter,
                initial_state=initial_states[seed],
                train_batch=train_batch,
                development_batch=development_batch,
                train_plan=train_derangements[derangement_seed],
                development_plan=development_derangements[derangement_seed],
                steps=actual_steps,
            )
    delta_cells: dict[str, dict[str, float]] = {}
    delta_by_seed: dict[str, float] = {}
    b4_initial_hash_equal: dict[str, bool] = {}
    for seed in seeds:
        key = str(seed)
        oracle_value = oracle_results[key]["development"][
            "persistent_three_label_macro_f1"
        ]
        delta_cells[key] = {}
        b4_initial_hash_equal[key] = all(
            result["initial_state_sha256"]
            == oracle_results[key]["initial_state_sha256"]
            for result in b4a_results[key].values()
        )
        for derangement_seed, result in b4a_results[key].items():
            delta_cells[key][derangement_seed] = 100.0 * (
                oracle_value - result["development"]["persistent_three_label_macro_f1"]
            )
        delta_by_seed[key] = sum(delta_cells[key].values()) / len(delta_cells[key])
    aggregate_delta = sum(delta_by_seed.values()) / len(delta_by_seed)
    binding_checks = {
        key: {
            "mean_D_positive": delta_by_seed[key] > 0.0,
            "at_least_two_of_three_cells_positive": sum(
                value > 0.0 for value in delta_cells[key].values()
            )
            >= 2,
            "B4_initial_hash_equal": b4_initial_hash_equal[key],
            "B4_complete_initial_hash_equal": all(
                result["complete_initial_state_sha256"]
                == oracle_results[key]["complete_initial_state_sha256"]
                for result in b4a_results[key].values()
            ),
            "frozen_adapter_unchanged": oracle_results[key]["frozen_adapter_unchanged"]
            and all(
                result["frozen_adapter_unchanged"]
                for result in b4a_results[key].values()
            ),
            "exact64_execution_passed": oracle_results[key]["exact64_execution_audit"][
                "passed"
            ]
            and all(
                result["exact64_execution_audit"]["passed"]
                for result in b4a_results[key].values()
            ),
        }
        for key in delta_by_seed
    }
    binding_pass = (
        all(all(checks.values()) for checks in binding_checks.values())
        and aggregate_delta >= 5.0
    )
    binding_gate = {
        "status": "PASS" if binding_pass else "FAIL_PERSISTENT_BINDING",
        "passed": binding_pass,
        "delta_cells_percentage_points": delta_cells,
        "delta_by_seed_percentage_points": delta_by_seed,
        "aggregate_delta_bind_percentage_points": aggregate_delta,
        "checks": binding_checks,
    }
    if not binding_pass and not args.smoke:
        return {
            **base,
            "status": "STOP_PERSISTENT_BINDING",
            "working_oracle_gate": working_oracle_gate,
            "marginal_control_gate": marginal_gate,
            "persistent_binding_gate": binding_gate,
            "oracle_results": _strip_models(oracle_results),
            "marginal_controls": controls,
            "baseline_execution": baseline_execution,
            "baseline_results": _strip_models(baseline_results),
            "b4a_results": _strip_models(b4a_results),
            "walltime_seconds": time.perf_counter() - start,
        }

    learned_results: dict[str, Any] = {}
    for seed in seeds:
        learned_results[str(seed)] = _train_learned(
            adapter=adapter,
            seed=seed,
            initial_projector_state=initial_states[seed],
            train_batch=train_batch,
            development_batch=development_batch,
            steps=actual_steps,
        )
    recovery_by_seed: dict[str, float] = {}
    learned_improvement: dict[str, float] = {}
    for seed in seeds:
        key = str(seed)
        a_value = sum(
            result["development"]["persistent_three_label_macro_f1"]
            for result in b4a_results[key].values()
        ) / len(b4a_results[key])
        b_value = oracle_results[key]["development"]["persistent_three_label_macro_f1"]
        l_value = learned_results[key]["development"]["persistent_three_label_macro_f1"]
        denominator = b_value - a_value
        if denominator <= 0.0:
            return {
                **base,
                "status": "STOP_NONPOSITIVE_RECOVERY_DENOMINATOR",
                "working_oracle_gate": working_oracle_gate,
                "marginal_control_gate": marginal_gate,
                "persistent_binding_gate": binding_gate,
                "oracle_results": _strip_models(oracle_results),
                "marginal_controls": controls,
                "baseline_execution": baseline_execution,
                "baseline_results": _strip_models(baseline_results),
                "b4a_results": _strip_models(b4a_results),
                "learned_results": _strip_models(learned_results),
                "failed_seed": seed,
                "recovery_denominator": denominator,
                "walltime_seconds": time.perf_counter() - start,
            }
        recovery_by_seed[key] = (l_value - a_value) / denominator
        learned_improvement[key] = l_value - a_value
    aggregate_recovery = sum(recovery_by_seed.values()) / len(recovery_by_seed)
    identity_hard_by_seed = {
        str(seed): learned_results[str(seed)]["assignment"][
            "hard_query_identity_accuracy"
        ]
        for seed in seeds
    }
    identity_soft_by_seed = {
        str(seed): learned_results[str(seed)]["assignment"]["soft_oracle_query_mass"]
        for seed in seeds
    }
    aggregate_identity_hard = sum(identity_hard_by_seed.values()) / len(
        identity_hard_by_seed
    )
    aggregate_identity_soft = sum(identity_soft_by_seed.values()) / len(
        identity_soft_by_seed
    )
    recovery_pass = (
        aggregate_recovery >= 0.60
        and all(value > 0.0 for value in learned_improvement.values())
        and all(value >= 0.50 for value in identity_hard_by_seed.values())
        and aggregate_identity_hard >= 0.60
        and all(value >= 0.30 for value in identity_soft_by_seed.values())
        and aggregate_identity_soft >= 0.35
        and all(
            result["frozen_adapter_unchanged"] for result in learned_results.values()
        )
        and all(
            result["exact64_execution_audit"]["passed"]
            for result in learned_results.values()
        )
    )
    recovery_gate = {
        "status": "PASS" if recovery_pass else "FAIL_LEARNED_RECOVERY",
        "passed": recovery_pass,
        "recovery_by_seed": recovery_by_seed,
        "aggregate_recovery": aggregate_recovery,
        "learned_improvement_by_seed": learned_improvement,
        "threshold": 0.60,
        "identity_hard_by_seed": identity_hard_by_seed,
        "identity_soft_by_seed": identity_soft_by_seed,
        "aggregate_identity_hard": aggregate_identity_hard,
        "aggregate_identity_soft": aggregate_identity_soft,
        "identity_thresholds": {
            "every_seed_hard_minimum": 0.50,
            "aggregate_hard_minimum": 0.60,
            "every_seed_soft_oracle_mass_minimum": 0.30,
            "aggregate_soft_oracle_mass_minimum": 0.35,
        },
    }
    baseline_development = structural["global_assignment_baselines"]["splits"][
        "development"
    ]
    hungarian_reference = baseline_development["hungarian"][
        "hard_query_identity_accuracy"
    ]
    sinkhorn_reference = baseline_development["sinkhorn"]["mean_oracle_query_mass"]
    noninferiority_checks = {
        "every_seed_hard_within_0_10": all(
            value >= hungarian_reference - 0.10
            for value in identity_hard_by_seed.values()
        ),
        "aggregate_hard_within_0_05": aggregate_identity_hard
        >= hungarian_reference - 0.05,
        "every_seed_soft_within_0_10": all(
            value >= sinkhorn_reference - 0.10
            for value in identity_soft_by_seed.values()
        ),
        "aggregate_soft_within_0_05": aggregate_identity_soft
        >= sinkhorn_reference - 0.05,
        "baseline_readouts_exact64": all(
            result["exact64_execution_audit"]["passed"]
            for seed_results in baseline_results.values()
            for result in seed_results.values()
        ),
    }
    noninferiority_pass = all(noninferiority_checks.values())
    baseline_noninferiority_gate = {
        "status": "PASS" if noninferiority_pass else "FAIL_BASELINE_NONINFERIORITY",
        "passed": noninferiority_pass,
        "checks": noninferiority_checks,
        "hungarian_hard_reference": hungarian_reference,
        "sinkhorn_soft_reference": sinkhorn_reference,
        "margins": {
            "every_seed": 0.10,
            "aggregate": 0.05,
        },
    }
    status = (
        "SMOKE_COMPLETE"
        if args.smoke
        else (
            "PASS_GATES_1_TO_6_AWAITING_INDEPENDENT_REPRODUCTION"
            if recovery_pass and noninferiority_pass
            else (
                "STOP_LEARNED_RECOVERY"
                if not recovery_pass
                else "STOP_BASELINE_NONINFERIORITY"
            )
        )
    )
    return {
        **base,
        "status": status,
        "working_oracle_gate": working_oracle_gate,
        "marginal_control_gate": marginal_gate,
        "persistent_binding_gate": binding_gate,
        "learned_recovery_gate": recovery_gate,
        "baseline_noninferiority_gate": baseline_noninferiority_gate,
        "oracle_results": _strip_models(oracle_results),
        "marginal_controls": controls,
        "baseline_execution": baseline_execution,
        "baseline_results": _strip_models(baseline_results),
        "b4a_results": _strip_models(b4a_results),
        "learned_results": _strip_models(learned_results),
        "independent_process_reproduction_required": not args.smoke,
        "walltime_seconds": time.perf_counter() - start,
    }


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    args.run_dir.mkdir(parents=True, exist_ok=False)
    summary = run(args)
    summary_path = args.run_dir / "summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps(summary, sort_keys=True))
    print(f"RESULT_DIR={args.run_dir.resolve()}")
    return 0 if summary["status"] not in {"FAIL", "FAIL_TECHNICAL_INTEGRITY"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
