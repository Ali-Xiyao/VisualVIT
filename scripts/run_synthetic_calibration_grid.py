from __future__ import annotations

# ruff: noqa: E402

import argparse
import copy
from dataclasses import dataclass
import hashlib
import inspect
import json
import math
from pathlib import Path
import sys
import time
from typing import Any, Iterable

import torch
from torch import Tensor
import torch.nn.functional as F

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE))
sys.path.insert(0, str(WORKSPACE / "src"))

from scripts.run_capes_ci_synthetic_overfit import (
    _build_model,
    _null_deleted_plan,
    _prompt,
    _state_hash,
)
from visualvit.baselines import (
    BalancedSinkhornBaseline,
    DevelopmentFrozenThreshold,
    HungarianRejectBaseline,
)
from visualvit.matching import (
    anatomy_compatible_derangement,
    oracle_plan_from_entity_ids,
)
from visualvit.metrics import macro_f1
from visualvit.model import CAPESCIModel
from visualvit.schemas import AllocationPlan, MatchPlan, RegionBatch
from visualvit.tokenizer import build_soft_relation_candidates


EVIDENCE_CLASS = "ENGINEERING_CALIBRATION_NONCONFIRMATORY"
INTERVENTION_EVIDENCE_CLASS = "ENGINEERING_INTERVENTION_NOT_FORMAL_ABLATION"
DEFAULT_SEED_BANK = (17, 29, 43)
DEFAULT_THRESHOLD_GRID = (-2.0, -1.0, -0.5, 0.0, 0.5, 1.0, 2.0)
METHOD_NAMES = (
    "B4a_deranged",
    "B4b_oracle",
    "learned_soft",
    "learned_hard",
    "hungarian_dev_frozen_reject",
    "balanced_sinkhorn_no_null",
    "A1_identity_masking",
    "A2_null_deletion",
)


@dataclass
class CalibrationBatch:
    regions: RegionBatch
    oracle: MatchPlan
    labels: Tensor
    split: str

    def to(self, device: torch.device | str) -> "CalibrationBatch":
        return CalibrationBatch(
            regions=self.regions.to(device),
            oracle=self.oracle.to(device),
            labels=self.labels.to(device),
            split=self.split,
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the non-confirmatory CAPES-CI synthetic anchor grid."
    )
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--seeds", type=int, nargs="+", default=list(DEFAULT_SEED_BANK))
    parser.add_argument("--train-data-seed", type=int, default=3401)
    parser.add_argument("--inner-dev-data-seed", type=int, default=4401)
    parser.add_argument("--dev-data-seed", type=int, default=5401)
    parser.add_argument("--train-cases-per-class", type=int, default=2)
    parser.add_argument("--inner-dev-cases-per-class", type=int, default=1)
    parser.add_argument("--dev-cases-per-class", type=int, default=2)
    parser.add_argument("--feature-dim", type=int, default=12)
    parser.add_argument("--hidden-size", type=int, default=16)
    parser.add_argument("--steps", type=int, default=80)
    parser.add_argument("--learning-rate", type=float, default=2e-2)
    parser.add_argument(
        "--threshold-grid",
        type=float,
        nargs="+",
        default=list(DEFAULT_THRESHOLD_GRID),
    )
    parser.add_argument("--sinkhorn-epsilon", type=float, default=0.25)
    parser.add_argument("--sinkhorn-iterations", type=int, default=2048)
    parser.add_argument("--device", choices=("cpu",), default="cpu")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    return build_parser().parse_args(argv)


def _region_kwargs(regions: RegionBatch) -> dict[str, Tensor | None]:
    return {
        name: getattr(regions, name)
        for name in (
            "prior_features",
            "current_features",
            "prior_valid",
            "current_valid",
            "prior_anatomy",
            "current_anatomy",
            "prior_entity_ids",
            "current_entity_ids",
            "prior_boxes",
            "current_boxes",
            "prior_confidence",
            "current_confidence",
            "prior_source_ids",
            "current_source_ids",
            "time_delta_days",
        )
    }


def make_anchor_batch(
    *,
    cases_per_class: int,
    feature_dim: int,
    seed: int,
    split: str = "synthetic",
    namespace: int = 0,
) -> CalibrationBatch:
    """Generate balanced five-label cases with derangeable anatomy groups.

    Each case has two anatomy groups and three endpoints per group.  Stable,
    worse and improved cases have six persistent entities.  New/resolved cases
    replace one endpoint with a same-anatomy birth/death pair, leaving at least
    two persistent endpoints in that group and equal prior/current cardinality.
    """

    if cases_per_class <= 0:
        raise ValueError("cases_per_class must be positive")
    if feature_dim < 8:
        raise ValueError("feature_dim must be at least eight")
    if not split:
        raise ValueError("split must be non-empty")
    generator = torch.Generator(device="cpu").manual_seed(seed)
    labels = torch.arange(5, dtype=torch.long).repeat_interleave(cases_per_class)
    batch_size = int(labels.numel())
    endpoint_count = 6
    identity_dim = feature_dim // 2
    state_dim = feature_dim - identity_dim

    prior_features = torch.empty(batch_size, endpoint_count, feature_dim)
    current_features = torch.empty_like(prior_features)
    prior_anatomy = torch.empty(batch_size, endpoint_count, dtype=torch.long)
    current_anatomy = torch.empty_like(prior_anatomy)
    prior_ids = torch.empty(batch_size, endpoint_count, dtype=torch.long)
    current_ids = torch.empty_like(prior_ids)
    prior_source_ids = torch.empty_like(prior_ids)
    current_source_ids = torch.empty_like(prior_ids)
    base_anatomy = torch.tensor([0, 0, 0, 1, 1, 1], dtype=torch.long)

    for case_index, label_tensor in enumerate(labels):
        label = int(label_tensor.item())
        identity = (
            F.normalize(
                torch.randn(endpoint_count + 1, identity_dim, generator=generator),
                dim=-1,
            )
            * 3.0
        )
        prior_state = 0.15 * torch.randn(endpoint_count, state_dim, generator=generator)
        current_state = prior_state + 0.02 * torch.randn(
            endpoint_count, state_dim, generator=generator
        )
        prior_identity = identity[:endpoint_count]
        current_identity = prior_identity + 0.02 * torch.randn(
            endpoint_count, identity_dim, generator=generator
        )
        entity_base = namespace * 1_000_000 + case_index * 100
        entity_prior = torch.arange(endpoint_count, dtype=torch.long) + entity_base
        entity_current = entity_prior.clone()

        if label == 0:  # stable
            current_state[0, 0] = prior_state[0, 0]
        elif label == 1:  # worse
            current_state[0, 0] = prior_state[0, 0] + 2.5
        elif label == 2:  # improved
            current_state[0, 0] = prior_state[0, 0] - 2.5
        elif label == 3:  # new: same-anatomy birth replaces a death
            current_identity[0] = identity[-1]
            entity_current[0] = entity_base + 50
            prior_state[0, 0] = 0.0
            current_state[0, 0] = 3.0
        else:  # resolved: same-anatomy birth replaces the resolved endpoint
            current_identity[0] = identity[-1]
            entity_current[0] = entity_base + 50
            prior_state[0, 0] = 3.0
            current_state[0, 0] = 0.0

        prior = torch.cat((prior_identity, prior_state), dim=-1)
        current = torch.cat((current_identity, current_state), dim=-1)
        prior_permutation = torch.randperm(endpoint_count, generator=generator)
        current_permutation = torch.randperm(endpoint_count, generator=generator)
        prior_features[case_index] = prior[prior_permutation]
        current_features[case_index] = current[current_permutation]
        prior_anatomy[case_index] = base_anatomy[prior_permutation]
        current_anatomy[case_index] = base_anatomy[current_permutation]
        prior_ids[case_index] = entity_prior[prior_permutation]
        current_ids[case_index] = entity_current[current_permutation]
        prior_source_ids[case_index] = torch.arange(endpoint_count)[prior_permutation]
        current_source_ids[case_index] = (
            torch.arange(endpoint_count)[current_permutation] + endpoint_count
        )

    valid = torch.ones(batch_size, endpoint_count, dtype=torch.bool)
    confidence = torch.ones(batch_size, endpoint_count)
    regions = RegionBatch(
        prior_features=prior_features,
        current_features=current_features,
        prior_valid=valid.clone(),
        current_valid=valid.clone(),
        prior_anatomy=prior_anatomy,
        current_anatomy=current_anatomy,
        prior_entity_ids=prior_ids,
        current_entity_ids=current_ids,
        prior_confidence=confidence.clone(),
        current_confidence=confidence.clone(),
        prior_source_ids=prior_source_ids,
        current_source_ids=current_source_ids,
        time_delta_days=torch.full((batch_size,), 30.0),
    )
    regions.validate()
    oracle = oracle_plan_from_entity_ids(regions)
    oracle.validate_hard(regions)
    return CalibrationBatch(regions=regions, oracle=oracle, labels=labels, split=split)


def _anatomy_support(regions: RegionBatch) -> Tensor:
    return (
        regions.prior_valid[:, :, None]
        & regions.current_valid[:, None, :]
        & (regions.prior_anatomy[:, :, None] == regions.current_anatomy[:, None, :])
    )


def _all_null_plan(regions: RegionBatch) -> MatchPlan:
    batch, prior_count, _ = regions.prior_features.shape
    current_count = regions.current_features.shape[1]
    transport = regions.prior_features.new_zeros(
        (batch, prior_count + 1, current_count + 1)
    )
    transport[:, :prior_count, current_count] = regions.prior_valid.to(transport.dtype)
    transport[:, prior_count, :current_count] = regions.current_valid.to(
        transport.dtype
    )
    plan = MatchPlan(transport=transport, mode="assignment_independent_all_null_anchor")
    plan.validate_hard(regions)
    return plan


def _shared_allocation(model: CAPESCIModel, regions: RegionBatch) -> AllocationPlan:
    candidates = build_soft_relation_candidates(regions, _all_null_plan(regions))
    return model.allocator(candidates)


def _tensor_digest(items: Iterable[tuple[str, Tensor]]) -> str:
    digest = hashlib.sha256()
    for name, value in sorted(items, key=lambda item: item[0]):
        contiguous = value.detach().to("cpu").contiguous()
        digest.update(name.encode("utf-8"))
        digest.update(str(contiguous.dtype).encode("ascii"))
        digest.update(str(tuple(contiguous.shape)).encode("ascii"))
        digest.update(contiguous.numpy().tobytes())
    return digest.hexdigest()


def _plan_hash(plan: MatchPlan) -> str:
    return _tensor_digest((("transport", plan.transport),))


def _allocation_hash(plan: AllocationPlan) -> str:
    return _tensor_digest(
        (
            ("weights", plan.weights),
            ("slot_valid", plan.slot_valid),
            ("slot_mass", plan.slot_mass),
            ("source_valid", plan.source_valid),
            ("selected_source_ids", plan.selected_source_ids),
            ("overflow_mask", plan.overflow_mask),
        )
    )


def _batch_hash(batch: CalibrationBatch) -> str:
    tensors: list[tuple[str, Tensor]] = []
    for name, value in _region_kwargs(batch.regions).items():
        if value is not None:
            tensors.append((name, value))
    tensors.extend((("oracle", batch.oracle.transport), ("labels", batch.labels)))
    return _tensor_digest(tensors)


def _json_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _source_manifest() -> dict[str, Any]:
    relative_paths = (
        "scripts/run_synthetic_calibration_grid.py",
        "scripts/run_capes_ci_synthetic_overfit.py",
        "src/visualvit/allocator.py",
        "src/visualvit/baselines.py",
        "src/visualvit/matching.py",
        "src/visualvit/model.py",
        "src/visualvit/projector.py",
        "src/visualvit/qwen_adapter.py",
        "src/visualvit/schemas.py",
        "src/visualvit/tokenizer.py",
    )
    files = {
        relative: hashlib.sha256((WORKSPACE / relative).read_bytes()).hexdigest()
        for relative in relative_paths
    }
    return {"files": files, "manifest_sha256": _json_hash(files)}


def _assignment_metrics(predicted: MatchPlan, oracle: MatchPlan) -> dict[str, Any]:
    prior_count = oracle.transport.shape[1] - 1
    current_count = oracle.transport.shape[2] - 1
    components = {
        "persistent": (
            predicted.transport[:, :prior_count, :current_count],
            oracle.transport[:, :prior_count, :current_count],
        ),
        "death": (
            predicted.transport[:, :prior_count, current_count],
            oracle.transport[:, :prior_count, current_count],
        ),
        "birth": (
            predicted.transport[:, prior_count, :current_count],
            oracle.transport[:, prior_count, :current_count],
        ),
    }
    result: dict[str, Any] = {"metric_convention": "transport-mass overlap"}
    f1_values: list[float] = []
    for name, (prediction, target) in components.items():
        overlap = float((prediction * target).sum().detach().cpu())
        predicted_mass = float(prediction.sum().detach().cpu())
        target_mass = float(target.sum().detach().cpu())
        precision = overlap / predicted_mass if predicted_mass > 0 else 0.0
        recall = overlap / target_mass if target_mass > 0 else 0.0
        f1 = (
            2.0 * precision * recall / (precision + recall)
            if precision + recall > 0
            else 0.0
        )
        result[name] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "overlap_mass": overlap,
            "predicted_mass": predicted_mass,
            "target_mass": target_mass,
        }
        f1_values.append(f1)
    result["macro_f1"] = sum(f1_values) / len(f1_values)
    return result


def _mask_identity_features(regions: RegionBatch) -> RegionBatch:
    identity_dim = regions.prior_features.shape[-1] // 2
    fields = _region_kwargs(regions)
    prior = regions.prior_features.clone()
    current = regions.current_features.clone()
    prior[..., :identity_dim] = 0
    current[..., :identity_dim] = 0
    fields["prior_features"] = prior
    fields["current_features"] = current
    masked = RegionBatch(**fields)
    masked.validate()
    return masked


def _cosine_cost_contract(
    regions: RegionBatch,
) -> tuple[Tensor, Tensor, Tensor, Tensor]:
    """Return the shared oracle-free deterministic baseline contract."""

    prior = F.normalize(regions.prior_features, dim=-1)
    current = F.normalize(regions.current_features, dim=-1)
    cost = 1.0 - torch.einsum("brd,bsd->brs", prior, current)
    support = _anatomy_support(regions)
    prior_marginal = regions.prior_valid.to(cost.dtype)
    current_marginal = regions.current_valid.to(cost.dtype)
    return cost.detach(), support, prior_marginal, current_marginal


def _contract_hash(
    cost: Tensor,
    support: Tensor,
    prior_marginal: Tensor,
    current_marginal: Tensor,
) -> str:
    return _tensor_digest(
        (
            ("cost", cost),
            ("support", support),
            ("prior_marginal", prior_marginal),
            ("current_marginal", current_marginal),
        )
    )


def audit_anchor_batch(
    batch: CalibrationBatch, *, derangement_seed: int = 7001
) -> dict[str, Any]:
    regions = batch.regions
    oracle = batch.oracle
    deranged = anatomy_compatible_derangement(regions, oracle, seed=derangement_seed)
    prior_count = regions.prior_features.shape[1]
    current_count = regions.current_features.shape[1]
    oracle_real = oracle.transport[:, :prior_count, :current_count]
    deranged_real = deranged.transport[:, :prior_count, :current_count]
    persistent_group_counts: list[list[int]] = []
    for batch_index in range(regions.prior_features.shape[0]):
        case_counts: list[int] = []
        anatomy_values = torch.unique(regions.prior_anatomy[batch_index]).tolist()
        for anatomy in sorted(int(value) for value in anatomy_values):
            rows = regions.prior_anatomy[batch_index].eq(anatomy)
            count = int(oracle_real[batch_index, rows].sum().item())
            case_counts.append(count)
        persistent_group_counts.append(case_counts)

    support = _anatomy_support(regions)
    marginal_prior = regions.prior_valid.to(regions.prior_features.dtype)
    marginal_current = regions.current_valid.to(regions.current_features.dtype)
    balanced = BalancedSinkhornBaseline(epsilon=0.5, iterations=64)(
        torch.zeros_like(support, dtype=regions.prior_features.dtype),
        support,
        marginal_prior,
        marginal_current,
    )
    balanced.validate(regions)
    label_counts = torch.bincount(batch.labels, minlength=5).tolist()
    checks = {
        "five_labels_balanced": len(set(label_counts)) == 1 and label_counts[0] > 0,
        "prior_current_endpoint_counts_equal": prior_count == current_count,
        "every_anatomy_group_has_two_persistent": all(
            count >= 2 for case in persistent_group_counts for count in case
        ),
        "b4_zero_fixed_point": float((oracle_real * deranged_real).sum()) == 0.0,
        "b4_null_sets_fixed": torch.equal(
            oracle.transport[:, :prior_count, current_count],
            deranged.transport[:, :prior_count, current_count],
        )
        and torch.equal(
            oracle.transport[:, prior_count, :current_count],
            deranged.transport[:, prior_count, :current_count],
        ),
        "balanced_support_feasible": True,
        "balanced_null_mass_exact_zero": int(
            torch.count_nonzero(balanced.transport[:, :prior_count, current_count])
            + torch.count_nonzero(balanced.transport[:, prior_count, :current_count])
        )
        == 0,
    }
    return {
        "split": batch.split,
        "batch_sha256": _batch_hash(batch),
        "case_count": int(batch.labels.numel()),
        "label_counts": label_counts,
        "persistent_per_anatomy_group": persistent_group_counts,
        "checks": checks,
        "deranged_plan_sha256": _plan_hash(deranged),
    }


def _evaluate_plan(
    *,
    name: str,
    model: CAPESCIModel,
    batch: CalibrationBatch,
    plan: MatchPlan,
    allocation: AllocationPlan,
    prompt: Tensor,
    evidence_class: str = EVIDENCE_CLASS,
) -> dict[str, Any]:
    started = time.perf_counter()
    plan.validate(batch.regions, atol=1e-6)
    with torch.inference_mode():
        output = model(
            batch.regions,
            prompt,
            assignment_mode="provided",
            provided_plan=plan,
            allocation_plan=allocation,
        )
    scores = output["label_scores"]
    predictions = scores.argmax(dim=-1)
    adapter = output["audits"]["adapter"]
    placeholder_count = adapter["placeholder_count"].detach().cpu().tolist()
    audits = {
        "exact_64_tokens": int(output["token_bundle"].tokens.shape[1]) == 64,
        "placeholder_count": placeholder_count,
        "all_placeholder_counts_64": placeholder_count
        == [64] * int(batch.labels.numel()),
        "no_pixel_path": output["audits"]["pixel_inputs_used"] is False
        and adapter["pixel_inputs_used"] is False,
        "frozen_vlm": output["audits"]["trainable_parameters"]["frozen_vlm"]
        and adapter["model_frozen"],
        "finite_scores": bool(torch.isfinite(scores).all()),
        "physical_attention_validated_by_adapter": True,
        "allocation_sha256": _allocation_hash(output["allocation_plan"]),
    }
    return {
        "name": name,
        "status": "COMPLETE"
        if all(
            bool(value)
            for key, value in audits.items()
            if key
            in {
                "exact_64_tokens",
                "all_placeholder_counts_64",
                "no_pixel_path",
                "frozen_vlm",
                "finite_scores",
                "physical_attention_validated_by_adapter",
            }
        )
        else "FAIL",
        "evidence_class": evidence_class,
        "formal_ablation": False,
        "assignment": _assignment_metrics(plan, batch.oracle),
        "label_metrics": {
            "case_balanced_macro_f1": macro_f1(predictions, batch.labels, 5),
            "accuracy": float(predictions.eq(batch.labels).float().mean().cpu()),
        },
        "raw": {
            "targets": batch.labels.detach().cpu().tolist(),
            "predictions": predictions.detach().cpu().tolist(),
            "scores": scores.detach().cpu().tolist(),
        },
        "audits": audits,
        "plan_mode": plan.mode,
        "plan_sha256": _plan_hash(plan),
        "walltime_seconds": time.perf_counter() - started,
    }


def _select_hungarian_threshold(
    inner_dev: CalibrationBatch,
    threshold_grid: tuple[float, ...],
) -> tuple[DevelopmentFrozenThreshold, dict[str, Any]]:
    contract = _cosine_cost_contract(inner_dev.regions)
    cost, support, prior_marginal, current_marginal = contract
    candidates: list[dict[str, float]] = []
    for threshold in threshold_grid:
        frozen = DevelopmentFrozenThreshold(
            value=threshold,
            source_split="development-inner-synthetic",
            selection_rule=(
                "maximize development-inner assignment macro-F1 over the fixed grid; "
                "lower threshold wins exact ties"
            ),
        )
        plan = HungarianRejectBaseline(frozen)(*contract)
        metrics = _assignment_metrics(plan, inner_dev.oracle)
        candidates.append(
            {
                "threshold": threshold,
                "assignment_macro_f1": float(metrics["macro_f1"]),
            }
        )
    selected = max(
        candidates,
        key=lambda row: (row["assignment_macro_f1"], -row["threshold"]),
    )
    frozen = DevelopmentFrozenThreshold(
        value=selected["threshold"],
        source_split="development-inner-synthetic",
        selection_rule=(
            "maximize development-inner assignment macro-F1 over the fixed grid; "
            "lower threshold wins exact ties"
        ),
    )
    provenance = {
        "selected_threshold": frozen.value,
        "source_split": frozen.source_split,
        "selection_rule": frozen.selection_rule,
        "fixed_grid": list(threshold_grid),
        "grid_scores": candidates,
        "oracle_use": "metric-only after oracle-free plan construction",
        "cost_source": "deterministic cosine distance over frozen region features",
        "null_head_used": False,
        "formal_test_used": False,
        "contract_sha256": _contract_hash(*contract),
    }
    return frozen, provenance


def _balanced_plan_with_feasibility(
    contract: tuple[Tensor, Tensor, Tensor, Tensor],
    *,
    epsilon: float,
    iterations: int,
) -> tuple[MatchPlan | None, dict[str, Any]]:
    cost, support, prior_marginal, current_marginal = contract
    baseline = BalancedSinkhornBaseline(
        epsilon=epsilon,
        iterations=iterations,
        convergence_tolerance=1e-6,
        feasibility_tolerance=1e-6,
    )
    failures: list[dict[str, Any]] = []
    for case_index in range(cost.shape[0]):
        try:
            baseline(
                cost[case_index : case_index + 1],
                support[case_index : case_index + 1],
                prior_marginal[case_index : case_index + 1],
                current_marginal[case_index : case_index + 1],
            )
        except (RuntimeError, ValueError) as error:
            failures.append({"case_index": case_index, "error": str(error)})
    feasible_cases = cost.shape[0] - len(failures)
    feasibility = {
        "case_count": int(cost.shape[0]),
        "feasible_cases": feasible_cases,
        "feasible_rate": feasible_cases / max(int(cost.shape[0]), 1),
        "failures": failures,
        "null_fallback_used": False,
    }
    if failures:
        return None, feasibility
    plan = baseline(cost, support, prior_marginal, current_marginal)
    prior_count = prior_marginal.shape[1]
    current_count = current_marginal.shape[1]
    feasibility["null_mass"] = float(
        plan.transport[:, :prior_count, current_count].sum()
        + plan.transport[:, prior_count, :current_count].sum()
    )
    return plan, feasibility


def _freeze_unused_matcher(model: CAPESCIModel) -> None:
    model.matcher.requires_grad_(False)
    model.matcher.eval()


def _train_system(
    *,
    model: CAPESCIModel,
    system_name: str,
    seed: int,
    batch: CalibrationBatch,
    allocation: AllocationPlan,
    prompt: Tensor,
    steps: int,
    learning_rate: float,
    provided_plan: MatchPlan | None,
) -> dict[str, Any]:
    fixed_assignment = provided_plan is not None
    if fixed_assignment:
        provided_plan.validate(batch.regions, atol=1e-6)
        _freeze_unused_matcher(model)
    torch.manual_seed(seed)
    initial_state_sha256 = _state_hash(model)
    model.train()
    trainable_names = [
        name for name, parameter in model.named_parameters() if parameter.requires_grad
    ]
    parameters = [
        parameter for parameter in model.parameters() if parameter.requires_grad
    ]
    if not parameters:
        raise RuntimeError(f"{system_name} has no trainable parameters")
    optimizer_spec = {
        "class": "AdamW",
        "learning_rate": learning_rate,
        "weight_decay": 0.0,
        "parameter_names": trainable_names,
        "scheduler": None,
    }
    optimizer = torch.optim.AdamW(parameters, lr=learning_rate, weight_decay=0.0)
    losses: list[float] = []
    started = time.perf_counter()
    for _ in range(steps):
        optimizer.zero_grad(set_to_none=True)
        output = model(
            batch.regions,
            prompt,
            assignment_mode="provided" if fixed_assignment else "learned_soft",
            provided_plan=provided_plan,
            allocation_plan=allocation,
        )
        loss = F.cross_entropy(output["label_scores"], batch.labels)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(parameters, max_norm=10.0)
        optimizer.step()
        losses.append(float(loss.detach().cpu()))
    model.eval()
    return {
        "system_name": system_name,
        "initial_state_sha256": initial_state_sha256,
        "final_state_sha256": _state_hash(model),
        "training_seed": seed,
        "steps": steps,
        "initial_loss": losses[0],
        "final_loss": losses[-1],
        "input_sha256": _batch_hash(batch),
        "allocation_sha256": _allocation_hash(allocation),
        "prompt_sha256": _tensor_digest((("prompt", prompt),)),
        "assignment_sha256": _plan_hash(provided_plan)
        if provided_plan is not None
        else None,
        "assignment_mode": "provided_fixed"
        if fixed_assignment
        else "learned_soft_dynamic",
        "matcher_frozen": not any(
            parameter.requires_grad for parameter in model.matcher.parameters()
        ),
        "optimizer": optimizer_spec,
        "optimizer_spec_sha256": _json_hash(optimizer_spec),
        "sample_order": "fixed full-batch order; no shuffle",
        "training_fit_is_formal_ablation": False,
        "walltime_seconds": time.perf_counter() - started,
    }


def _b4_pair_audit(
    *,
    base_model: CAPESCIModel,
    batch: CalibrationBatch,
    allocation: AllocationPlan,
    prompt: Tensor,
    deranged: MatchPlan,
    oracle: MatchPlan,
    record_a: dict[str, Any],
    record_b: dict[str, Any],
) -> dict[str, Any]:
    with torch.inference_mode():
        _, _, bundle_a, _ = base_model.encode_relations(
            batch.regions,
            assignment_mode="provided",
            provided_plan=deranged,
            allocation_plan=allocation,
        )
        _, _, bundle_b, _ = base_model.encode_relations(
            batch.regions,
            assignment_mode="provided",
            provided_plan=oracle,
            allocation_plan=allocation,
        )
    prior_count = batch.regions.prior_features.shape[1]
    current_count = batch.regions.current_features.shape[1]
    checks = {
        "same_initial_state": record_a["initial_state_sha256"]
        == record_b["initial_state_sha256"],
        "same_input": record_a["input_sha256"] == record_b["input_sha256"],
        "same_allocation": record_a["allocation_sha256"]
        == record_b["allocation_sha256"],
        "same_prompt": record_a["prompt_sha256"] == record_b["prompt_sha256"],
        "same_optimizer": record_a["optimizer_spec_sha256"]
        == record_b["optimizer_spec_sha256"],
        "same_steps": record_a["steps"] == record_b["steps"],
        "same_training_seed": record_a["training_seed"] == record_b["training_seed"],
        "matcher_frozen_both": record_a["matcher_frozen"]
        and record_b["matcher_frozen"],
        "assignment_hash_differs": record_a["assignment_sha256"]
        != record_b["assignment_sha256"],
        "null_sets_equal": torch.equal(
            deranged.transport[:, :prior_count, current_count],
            oracle.transport[:, :prior_count, current_count],
        )
        and torch.equal(
            deranged.transport[:, prior_count, :current_count],
            oracle.transport[:, prior_count, :current_count],
        ),
        "token_layout_equal": torch.equal(bundle_a.token_types, bundle_b.token_types)
        and torch.equal(bundle_a.valid_mask, bundle_b.valid_mask)
        and torch.equal(bundle_a.source_ids, bundle_b.source_ids),
        "assignment_independent_tokens_equal": torch.equal(
            bundle_a.tokens[:, :32], bundle_b.tokens[:, :32]
        ),
        "relation_tokens_differ": not torch.equal(
            bundle_a.tokens[:, 32:60], bundle_b.tokens[:, 32:60]
        ),
    }
    return {
        "checks": checks,
        "pass": all(checks.values()),
        "allowed_difference": (
            "provided assignment hash and relation-token/final-state values causally "
            "downstream of assignment"
        ),
        "final_state_difference_allowed": True,
        "B4a_final_state_sha256": record_a["final_state_sha256"],
        "B4b_final_state_sha256": record_b["final_state_sha256"],
        "allocation_sha256": _allocation_hash(allocation),
        "prompt_sha256": _tensor_digest((("prompt", prompt),)),
    }


def _train_one_seed(
    *,
    seed: int,
    args: argparse.Namespace,
    train: CalibrationBatch,
    inner_dev: CalibrationBatch,
    dev: CalibrationBatch,
    config_sha256: str,
    source_manifest_sha256: str,
) -> dict[str, Any]:
    seed_started = time.perf_counter()
    torch.manual_seed(seed)
    base_model = _build_model(args.feature_dim, args.hidden_size).to(args.device)
    base_initial_state_sha256 = _state_hash(base_model)
    train_allocation = _shared_allocation(base_model, train.regions)
    dev_allocation = _shared_allocation(base_model, dev.regions)
    train_prompt = _prompt(int(train.labels.numel()), torch.device(args.device))
    dev_prompt = _prompt(int(dev.labels.numel()), torch.device(args.device))

    threshold, threshold_provenance = _select_hungarian_threshold(
        inner_dev, tuple(args.threshold_grid)
    )
    train_contract = _cosine_cost_contract(train.regions)
    dev_contract = _cosine_cost_contract(dev.regions)
    hungarian_train = HungarianRejectBaseline(threshold)(*train_contract)
    hungarian_dev = HungarianRejectBaseline(threshold)(*dev_contract)
    balanced_train, balanced_train_feasibility = _balanced_plan_with_feasibility(
        train_contract,
        epsilon=args.sinkhorn_epsilon,
        iterations=args.sinkhorn_iterations,
    )
    balanced_dev, balanced_dev_feasibility = _balanced_plan_with_feasibility(
        dev_contract,
        epsilon=args.sinkhorn_epsilon,
        iterations=args.sinkhorn_iterations,
    )
    if balanced_train is None or balanced_dev is None:
        raise RuntimeError(
            "anchor support failed strict balanced no-null feasibility; no fallback"
        )

    train_derangement_seed = 200_000 + seed
    dev_derangement_seed = 300_000 + seed
    train_b4a = anatomy_compatible_derangement(
        train.regions, train.oracle, seed=train_derangement_seed
    )
    dev_b4a = anatomy_compatible_derangement(
        dev.regions, dev.oracle, seed=dev_derangement_seed
    )
    models = {
        name: copy.deepcopy(base_model)
        for name in (
            "B4a_deranged",
            "B4b_oracle",
            "learned_soft",
            "hungarian_dev_frozen_reject",
            "balanced_sinkhorn_no_null",
        )
    }
    training_specs = {
        "B4a_deranged": train_b4a,
        "B4b_oracle": train.oracle,
        "learned_soft": None,
        "hungarian_dev_frozen_reject": hungarian_train,
        "balanced_sinkhorn_no_null": balanced_train,
    }
    training_records = {
        name: _train_system(
            model=models[name],
            system_name=name,
            seed=seed,
            batch=train,
            allocation=train_allocation,
            prompt=train_prompt,
            steps=args.steps,
            learning_rate=args.learning_rate,
            provided_plan=provided_plan,
        )
        for name, provided_plan in training_specs.items()
    }
    b4_pair_audit = _b4_pair_audit(
        base_model=base_model,
        batch=train,
        allocation=train_allocation,
        prompt=train_prompt,
        deranged=train_b4a,
        oracle=train.oracle,
        record_a=training_records["B4a_deranged"],
        record_b=training_records["B4b_oracle"],
    )

    allocation_sha256 = _allocation_hash(dev_allocation)
    oracle_allocation = base_model.allocator(
        build_soft_relation_candidates(dev.regions, dev.oracle)
    )
    allocation_oracle_invariant = (
        _allocation_hash(oracle_allocation) == allocation_sha256
    )
    learned_model = models["learned_soft"]
    with torch.inference_mode():
        learned_soft = learned_model.matcher.soft_plan(dev.regions)
        learned_hard = learned_model.matcher.hard_plan(dev.regions)
    masked_regions = _mask_identity_features(dev.regions)
    with torch.inference_mode():
        identity_masked_plan = learned_model.matcher.soft_plan(masked_regions)
    identity_masked_batch = CalibrationBatch(
        regions=masked_regions,
        oracle=dev.oracle,
        labels=dev.labels,
        split=dev.split,
    )
    null_deleted = _null_deleted_plan(dev.regions, dev.oracle)

    controlled_training_systems = {
        "B4a_deranged": _evaluate_plan(
            name="B4a_deranged",
            model=models["B4a_deranged"],
            batch=dev,
            plan=dev_b4a,
            allocation=dev_allocation,
            prompt=dev_prompt,
        ),
        "B4b_oracle": _evaluate_plan(
            name="B4b_oracle",
            model=models["B4b_oracle"],
            batch=dev,
            plan=dev.oracle,
            allocation=dev_allocation,
            prompt=dev_prompt,
        ),
        "learned_soft": _evaluate_plan(
            name="learned_soft",
            model=learned_model,
            batch=dev,
            plan=learned_soft,
            allocation=dev_allocation,
            prompt=dev_prompt,
        ),
    }
    for name, result in controlled_training_systems.items():
        result["training"] = training_records[name]
        result["system_role"] = "controlled_training_system"

    diagnostic_evaluations = {
        "learned_hard": _evaluate_plan(
            name="learned_hard",
            model=learned_model,
            batch=dev,
            plan=learned_hard,
            allocation=dev_allocation,
            prompt=dev_prompt,
        )
    }
    diagnostic_evaluations["learned_hard"]["training_reference"] = "learned_soft"
    diagnostic_evaluations["learned_hard"]["system_role"] = "diagnostic_evaluation"

    independent_baseline_systems = {
        "hungarian_dev_frozen_reject": _evaluate_plan(
            name="hungarian_dev_frozen_reject",
            model=models["hungarian_dev_frozen_reject"],
            batch=dev,
            plan=hungarian_dev,
            allocation=dev_allocation,
            prompt=dev_prompt,
        ),
        "balanced_sinkhorn_no_null": _evaluate_plan(
            name="balanced_sinkhorn_no_null",
            model=models["balanced_sinkhorn_no_null"],
            batch=dev,
            plan=balanced_dev,
            allocation=dev_allocation,
            prompt=dev_prompt,
        ),
    }
    for name, result in independent_baseline_systems.items():
        result["training"] = training_records[name]
        result["system_role"] = "independently_trained_baseline"
        result["cost_source"] = (
            "deterministic cosine distance over frozen region features"
        )
        result["null_head_used"] = False
    independent_baseline_systems["balanced_sinkhorn_no_null"]["feasibility"] = {
        "train": balanced_train_feasibility,
        "development": balanced_dev_feasibility,
    }

    engineering_interventions = {
        "A1_identity_masking": _evaluate_plan(
            name="A1_identity_masking",
            model=learned_model,
            batch=identity_masked_batch,
            plan=identity_masked_plan,
            allocation=dev_allocation,
            prompt=dev_prompt,
            evidence_class=INTERVENTION_EVIDENCE_CLASS,
        ),
        "A2_null_deletion": _evaluate_plan(
            name="A2_null_deletion",
            model=models["B4b_oracle"],
            batch=dev,
            plan=null_deleted,
            allocation=dev_allocation,
            prompt=dev_prompt,
            evidence_class=INTERVENTION_EVIDENCE_CLASS,
        ),
    }
    engineering_interventions["A1_identity_masking"]["reference_system"] = (
        "learned_soft"
    )
    engineering_interventions["A2_null_deletion"]["reference_system"] = "B4b_oracle"
    for result in engineering_interventions.values():
        result["system_role"] = "inference_or_input_engineering_intervention"

    all_results = {
        **controlled_training_systems,
        **diagnostic_evaluations,
        **independent_baseline_systems,
        **engineering_interventions,
    }
    b4a_metric = controlled_training_systems["B4a_deranged"]["label_metrics"][
        "case_balanced_macro_f1"
    ]
    b4b_metric = controlled_training_systems["B4b_oracle"]["label_metrics"][
        "case_balanced_macro_f1"
    ]
    learned_metric = controlled_training_systems["learned_soft"]["label_metrics"][
        "case_balanced_macro_f1"
    ]
    denominator = b4b_metric - b4a_metric
    recovery = (learned_metric - b4a_metric) / denominator if denominator > 0 else None
    all_methods_complete = all(
        method["status"] == "COMPLETE" for method in all_results.values()
    )
    exact_audits = all(
        method["audits"]["exact_64_tokens"]
        and method["audits"]["all_placeholder_counts_64"]
        and method["audits"]["no_pixel_path"]
        and method["audits"]["frozen_vlm"]
        and method["audits"]["finite_scores"]
        for method in all_results.values()
    )
    all_allocations_shared = all(
        method["audits"]["allocation_sha256"] == allocation_sha256
        for method in all_results.values()
    )
    initial_state_all_systems_equal = (
        len({record["initial_state_sha256"] for record in training_records.values()})
        == 1
    )
    balanced_ok = (
        balanced_train_feasibility["feasible_rate"] == 1.0
        and balanced_dev_feasibility["feasible_rate"] == 1.0
        and balanced_train_feasibility.get("null_mass") == 0.0
        and balanced_dev_feasibility.get("null_mass") == 0.0
    )
    return {
        "seed": seed,
        "status": "COMPLETE"
        if all_methods_complete
        and exact_audits
        and all_allocations_shared
        and balanced_ok
        and b4_pair_audit["pass"]
        and initial_state_all_systems_equal
        else "FAIL",
        "status_semantics": "technical execution only; not a mechanism survival verdict",
        "evidence_class": EVIDENCE_CLASS,
        "formal_claim_allowed": False,
        "formal_ablation_claim_allowed": False,
        "config_sha256": config_sha256,
        "source_manifest_sha256": source_manifest_sha256,
        "base_initial_state_sha256": base_initial_state_sha256,
        "training_system_records": training_records,
        "controlled_training_systems": controlled_training_systems,
        "diagnostic_evaluations": diagnostic_evaluations,
        "independent_baseline_systems": independent_baseline_systems,
        "engineering_interventions": engineering_interventions,
        "threshold_provenance": threshold_provenance,
        "derangement_count": 1,
        "train_derangement_seed": train_derangement_seed,
        "development_derangement_seed": dev_derangement_seed,
        "formal_D_requirement_met": False,
        "not_formal_D_requirement": (
            "engineering calibration uses D=1; formal protocol requires D>=3"
        ),
        "B4_pair_audit": b4_pair_audit,
        "shared_allocation_sha256": allocation_sha256,
        "allocation_source": "assignment-independent all-null source-universe anchor",
        "allocation_oracle_invariant_audit": allocation_oracle_invariant,
        "baseline_contract": {
            "source": "deterministic cosine distance over frozen region features",
            "null_head_used": False,
            "train_sha256": _contract_hash(*train_contract),
            "development_sha256": _contract_hash(*dev_contract),
            "identical_for_hungarian_and_sinkhorn": True,
        },
        "balanced_feasibility": {
            "train": balanced_train_feasibility,
            "development": balanced_dev_feasibility,
        },
        "effects": {
            "delta_bind_percentage_points": 100.0 * denominator,
            "binding_denominator": denominator,
            "binding_denominator_positive": denominator > 0,
            "recovery": recovery,
            "recovery_defined_only_for_positive_denominator": True,
            "effect_source": (
                "separately trained controlled systems sharing the frozen B4 pair contract"
            ),
            "A1_identity_masking_macro_f1_change": engineering_interventions[
                "A1_identity_masking"
            ]["label_metrics"]["case_balanced_macro_f1"]
            - learned_metric,
            "A2_null_deletion_macro_f1_change": engineering_interventions[
                "A2_null_deletion"
            ]["label_metrics"]["case_balanced_macro_f1"]
            - b4b_metric,
            "interventions_excluded_from_delta_bind_and_recovery": True,
        },
        "checks": {
            "all_methods_complete": all_methods_complete,
            "exact64_no_pixel_frozen_finite": exact_audits,
            "same_allocation_every_method": all_allocations_shared,
            "allocation_oracle_invariant": allocation_oracle_invariant,
            "all_training_systems_same_initial_state": initial_state_all_systems_equal,
            "B4_pair_contract_pass": b4_pair_audit["pass"],
            "balanced_no_null_feasible": balanced_ok,
            "baseline_cost_oracle_free": True,
            "baseline_null_head_used": False,
            "oracle_cardinality_argument_used": False,
            "formal_test_used": False,
        },
        "walltime_seconds": time.perf_counter() - seed_started,
    }


def _validate_args(args: argparse.Namespace) -> None:
    if not args.seeds or len(set(args.seeds)) != len(args.seeds):
        raise ValueError("seeds must be a non-empty unique ordered list")
    for name in (
        "train_cases_per_class",
        "inner_dev_cases_per_class",
        "dev_cases_per_class",
    ):
        if getattr(args, name) <= 0:
            raise ValueError(f"{name} must be positive")
    if args.feature_dim < 8 or args.hidden_size <= 0:
        raise ValueError("feature_dim must be >=8 and hidden_size must be positive")
    if args.steps < 0 or (args.steps == 0 and not args.dry_run):
        raise ValueError("steps must be positive except in dry-run mode")
    if args.learning_rate <= 0 or not math.isfinite(args.learning_rate):
        raise ValueError("learning_rate must be finite and positive")
    if not args.threshold_grid or any(
        not math.isfinite(value) for value in args.threshold_grid
    ):
        raise ValueError("threshold_grid must contain finite values")
    if len(set(args.threshold_grid)) != len(args.threshold_grid):
        raise ValueError("threshold_grid values must be unique")
    if args.sinkhorn_epsilon <= 0 or not math.isfinite(args.sinkhorn_epsilon):
        raise ValueError("sinkhorn_epsilon must be finite and positive")
    if args.sinkhorn_iterations <= 0:
        raise ValueError("sinkhorn_iterations must be positive")


def _config(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "seed_bank": list(args.seeds),
        "train_data_seed": args.train_data_seed,
        "inner_dev_data_seed": args.inner_dev_data_seed,
        "dev_data_seed": args.dev_data_seed,
        "train_cases_per_class": args.train_cases_per_class,
        "inner_dev_cases_per_class": args.inner_dev_cases_per_class,
        "dev_cases_per_class": args.dev_cases_per_class,
        "feature_dim": args.feature_dim,
        "hidden_size": args.hidden_size,
        "steps": args.steps,
        "learning_rate": args.learning_rate,
        "threshold_grid": list(args.threshold_grid),
        "sinkhorn_epsilon": args.sinkhorn_epsilon,
        "sinkhorn_iterations": args.sinkhorn_iterations,
        "derangement_count": 1,
        "formal_D_requirement_met": False,
        "not_formal_D_requirement": "engineering D=1; formal protocol requires D>=3",
        "device": args.device,
        "dry_run": args.dry_run,
    }


def _method_result(seed_result: dict[str, Any], method: str) -> dict[str, Any]:
    for group in (
        "controlled_training_systems",
        "diagnostic_evaluations",
        "independent_baseline_systems",
        "engineering_interventions",
    ):
        if method in seed_result[group]:
            return seed_result[group][method]
    raise KeyError(method)


def run_calibration(args: argparse.Namespace) -> dict[str, Any]:
    _validate_args(args)
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    started = time.perf_counter()
    device = torch.device(args.device)
    train = make_anchor_batch(
        cases_per_class=args.train_cases_per_class,
        feature_dim=args.feature_dim,
        seed=args.train_data_seed,
        split="train",
        namespace=1,
    ).to(device)
    inner_dev = make_anchor_batch(
        cases_per_class=args.inner_dev_cases_per_class,
        feature_dim=args.feature_dim,
        seed=args.inner_dev_data_seed,
        split="development-inner",
        namespace=2,
    ).to(device)
    dev = make_anchor_batch(
        cases_per_class=args.dev_cases_per_class,
        feature_dim=args.feature_dim,
        seed=args.dev_data_seed,
        split="development",
        namespace=3,
    ).to(device)
    data_audits = {
        "train": audit_anchor_batch(train, derangement_seed=7101),
        "development_inner": audit_anchor_batch(inner_dev, derangement_seed=7103),
        "development": audit_anchor_batch(dev, derangement_seed=7109),
    }
    data_checks_pass = all(
        all(audit["checks"].values()) for audit in data_audits.values()
    )
    config = _config(args)
    config_sha256 = _json_hash(config)
    source = _source_manifest()
    learned_signature = tuple(inspect.signature(CAPESCIModel.forward).parameters.keys())
    baseline_signatures = {
        name: tuple(inspect.signature(cls.forward).parameters.keys())
        for name, cls in (
            ("hungarian", HungarianRejectBaseline),
            ("balanced_sinkhorn", BalancedSinkhornBaseline),
        )
    }
    common = {
        "evidence_class": EVIDENCE_CLASS,
        "formal_claim_allowed": False,
        "formal_ablation_claim_allowed": False,
        "claim_boundary": (
            "Synthetic train/development engineering calibration only; training fit "
            "and A1/A2 interventions are not formal ablation evidence."
        ),
        "config": config,
        "config_sha256": config_sha256,
        "source_hashes": source,
        "data_audits": data_audits,
        "api_audit": {
            "learned_forward_parameters": learned_signature,
            "baseline_forward_parameters": baseline_signatures,
            "oracle_cardinality_in_learned_api": "match_count" in learned_signature,
            "oracle_cardinality_in_baseline_api": any(
                "match_count" in signature for signature in baseline_signatures.values()
            ),
            "pixel_argument_supplied": False,
        },
    }
    if args.dry_run:
        return {
            **common,
            "status": "DRY_RUN_VALIDATED" if data_checks_pass else "FAIL",
            "seed_results": [],
            "aggregate": None,
            "walltime_seconds": time.perf_counter() - started,
        }

    seed_results = [
        _train_one_seed(
            seed=seed,
            args=args,
            train=train,
            inner_dev=inner_dev,
            dev=dev,
            config_sha256=config_sha256,
            source_manifest_sha256=source["manifest_sha256"],
        )
        for seed in args.seeds
    ]
    delta_values = [
        result["effects"]["delta_bind_percentage_points"] for result in seed_results
    ]
    recovery_values = [
        result["effects"]["recovery"]
        for result in seed_results
        if result["effects"]["recovery"] is not None
    ]
    method_macro_f1 = {
        method: [
            _method_result(result, method)["label_metrics"]["case_balanced_macro_f1"]
            for result in seed_results
            if _method_result(result, method)["status"] == "COMPLETE"
        ]
        for method in METHOD_NAMES
    }
    a1_changes = [
        result["effects"]["A1_identity_masking_macro_f1_change"]
        for result in seed_results
    ]
    a2_changes = [
        result["effects"]["A2_null_deletion_macro_f1_change"] for result in seed_results
    ]
    mean_delta = sum(delta_values) / len(delta_values)
    mean_recovery = (
        sum(recovery_values) / len(recovery_values) if recovery_values else None
    )
    mechanism_criteria = {
        "exact_default_three_seed_bank": tuple(args.seeds) == DEFAULT_SEED_BANK,
        "all_seed_technical_status_complete": all(
            result["status"] == "COMPLETE" for result in seed_results
        ),
        "delta_bind_positive_every_seed": all(value > 0 for value in delta_values),
        "mean_delta_bind_at_least_5pp": mean_delta >= 5.0,
        "recovery_qualified_every_seed": len(recovery_values) == len(seed_results),
        "mean_recovery_at_least_0_60": mean_recovery is not None
        and mean_recovery >= 0.60,
        "A1_expected_direction_every_seed": all(value < 0 for value in a1_changes),
        "A2_expected_direction_every_seed": all(value < 0 for value in a2_changes),
    }
    mechanism_gate = {
        "name": "three-seed engineering mechanism gate",
        "evaluated": tuple(args.seeds) == DEFAULT_SEED_BANK,
        "pass": tuple(args.seeds) == DEFAULT_SEED_BANK
        and all(mechanism_criteria.values()),
        "criteria": mechanism_criteria,
        "derangement_count": 1,
        "formal_D_requirement_met": False,
        "formal_claim_allowed": False,
        "interpretation": (
            "Non-confirmatory engineering gate only; D=1 does not satisfy formal D>=3."
        ),
    }
    aggregate = {
        "seed_count": len(seed_results),
        "ordered_seeds": list(args.seeds),
        "delta_bind_percentage_points": {
            "values": delta_values,
            "mean": mean_delta,
        },
        "recovery": {
            "values_for_positive_denominators_only": recovery_values,
            "qualified_seed_count": len(recovery_values),
            "mean": mean_recovery,
        },
        "method_case_balanced_macro_f1": {
            method: {
                "values": values,
                "mean": sum(values) / len(values) if values else None,
            }
            for method, values in method_macro_f1.items()
        },
        "balanced_feasible_rate": sum(
            result["balanced_feasibility"]["development"]["feasible_rate"]
            for result in seed_results
        )
        / len(seed_results),
        "independent_reinitialization": len(
            {result["base_initial_state_sha256"] for result in seed_results}
        )
        == len(seed_results),
        "all_seed_technical_status_complete": all(
            result["status"] == "COMPLETE" for result in seed_results
        ),
        "mechanism_gate": mechanism_gate,
    }
    return {
        **common,
        "status": "COMPLETE"
        if data_checks_pass and aggregate["all_seed_technical_status_complete"]
        else "FAIL",
        "status_semantics": (
            "COMPLETE means technical execution only; inspect mechanism_gate separately."
        ),
        "seed_results": seed_results,
        "aggregate": aggregate,
        "mechanism_gate": mechanism_gate,
        "walltime_seconds": time.perf_counter() - started,
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.run_dir.exists():
        raise FileExistsError(args.run_dir)
    summary = run_calibration(args)
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
    return 0 if summary["status"] in {"COMPLETE", "DRY_RUN_VALIDATED"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
