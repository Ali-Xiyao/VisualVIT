from __future__ import annotations

# ruff: noqa: E402

import argparse
import hashlib
import json
import platform
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import torch
from torch import Tensor, nn
import torch.nn.functional as F

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE / "src"))

from visualvit.allocator import DeterministicGlobalAllocator
from visualvit.matching import (
    NullAwareMatchGraph,
    anatomy_compatible_derangement,
)
from visualvit.model import CAPESCIModel
from visualvit.projector import RelationProjector
from visualvit.qwen_adapter import FrozenVLMAdapter
from visualvit.schemas import MatchPlan, RegionBatch
from visualvit.synthetic import make_synthetic_batch, order_swap_label
from visualvit.tokenizer import build_soft_relation_candidates


EVIDENCE_CLASS = "SURVIVAL_SYNTHETIC_NON_CONFIRMATORY"
PLACEHOLDER_TOKEN_ID = 1
LABEL_TOKEN_IDS = {
    "stable": (5,),
    "worse": (6,),
    "improved": (7,),
    "new": (8,),
    "resolved": (9,),
}


class FrozenRelationCausalLM(nn.Module):
    """Small deterministic causal LM used only to qualify relation injection."""

    def __init__(self, hidden_size: int = 32, vocab_size: int = 48) -> None:
        super().__init__()
        self.embedding = nn.Embedding(vocab_size, hidden_size)
        self.input_mix = nn.Linear(hidden_size, hidden_size, bias=False)
        self.output_head = nn.Linear(hidden_size, vocab_size, bias=False)

    def get_input_embeddings(self) -> nn.Module:
        return self.embedding

    def forward(
        self,
        *,
        inputs_embeds: Tensor,
        attention_mask: Tensor,
        position_ids: Tensor,
        use_cache: bool,
        logits_to_keep: int,
    ) -> SimpleNamespace:
        if position_ids.shape != (3, *attention_mask.shape):
            raise ValueError("expected three equal text-like position axes")
        if use_cache is not False:
            raise ValueError("survival LM requires use_cache=False")
        if logits_to_keep != 0:
            raise ValueError("survival LM requires full logits_to_keep=0")
        mixed = self.input_mix(inputs_embeds) * attention_mask.unsqueeze(-1)
        hidden = torch.tanh(torch.cumsum(mixed, dim=1))
        return SimpleNamespace(logits=self.output_head(hidden))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=2401)
    parser.add_argument("--data-seed", type=int, default=3401)
    parser.add_argument("--cases-per-class", type=int, default=3)
    parser.add_argument("--feature-dim", type=int, default=12)
    parser.add_argument("--hidden-size", type=int, default=32)
    parser.add_argument("--steps", type=int, default=500)
    parser.add_argument("--learning-rate", type=float, default=2e-2)
    parser.add_argument("--device", default="cpu")
    return parser.parse_args()


def _state_hash(module: nn.Module) -> str:
    digest = hashlib.sha256()
    for name, value in sorted(module.state_dict().items()):
        digest.update(name.encode("utf-8"))
        contiguous = value.detach().to("cpu").contiguous()
        digest.update(str(contiguous.dtype).encode("ascii"))
        digest.update(str(tuple(contiguous.shape)).encode("ascii"))
        digest.update(contiguous.numpy().tobytes())
    return digest.hexdigest()


def _make_progression_cases(
    *,
    cases_per_class: int,
    feature_dim: int,
    seed: int,
) -> tuple[RegionBatch, Tensor]:
    if cases_per_class <= 0:
        raise ValueError("cases_per_class must be positive")
    if feature_dim < 8:
        raise ValueError("feature_dim must be at least eight")
    generator = torch.Generator(device="cpu").manual_seed(seed)
    labels = torch.arange(5, dtype=torch.long).repeat_interleave(cases_per_class)
    batch_size = labels.numel()
    prior = torch.zeros(batch_size, 2, feature_dim)
    current = torch.zeros_like(prior)
    prior_anatomy = torch.empty(batch_size, 2, dtype=torch.long)
    current_anatomy = torch.empty_like(prior_anatomy)
    prior_ids = torch.empty(batch_size, 2, dtype=torch.long)
    current_ids = torch.empty_like(prior_ids)

    for index, label_tensor in enumerate(labels):
        label = int(label_tensor.item())
        target_identity = F.normalize(
            torch.randn(feature_dim // 2, generator=generator), dim=0
        )
        filler_identity = F.normalize(
            torch.randn(feature_dim // 2, generator=generator), dim=0
        )
        prior_target = torch.cat(
            (target_identity * 2.0, torch.zeros(feature_dim - feature_dim // 2))
        )
        current_target = prior_target.clone()
        filler_prior = torch.cat(
            (filler_identity * 2.0, torch.zeros(feature_dim - feature_dim // 2))
        )
        filler_current = filler_prior.clone()
        filler_current[-1] = 0.05

        base_id = index * 100
        prior[index, 1] = filler_prior
        current[index, 1] = filler_current
        prior_anatomy[index, 1] = 1
        current_anatomy[index, 1] = 1
        prior_ids[index, 1] = base_id + 1
        current_ids[index, 1] = base_id + 1

        if label in (0, 1, 2):
            delta = {0: 0.0, 1: 2.5, 2: -2.5}[label]
            current_target[-2] = delta
            prior[index, 0] = prior_target
            current[index, 0] = current_target
            prior_anatomy[index, 0] = 0
            current_anatomy[index, 0] = 0
            prior_ids[index, 0] = base_id
            current_ids[index, 0] = base_id
        elif label == 3:  # new at target anatomy zero
            prior[index, 0] = torch.randn(feature_dim, generator=generator)
            current_target[-2] = 3.0
            current[index, 0] = current_target
            prior_anatomy[index, 0] = 2
            current_anatomy[index, 0] = 0
            prior_ids[index, 0] = base_id + 2
            current_ids[index, 0] = base_id + 3
        else:  # resolved at target anatomy zero
            prior_target[-2] = 3.0
            prior[index, 0] = prior_target
            current[index, 0] = torch.randn(feature_dim, generator=generator)
            prior_anatomy[index, 0] = 0
            current_anatomy[index, 0] = 2
            prior_ids[index, 0] = base_id + 4
            current_ids[index, 0] = base_id + 5

    valid = torch.ones(batch_size, 2, dtype=torch.bool)
    confidence = torch.ones(batch_size, 2)
    prior_source_ids = torch.tensor([[0, 1]], dtype=torch.long).expand(batch_size, -1)
    current_source_ids = torch.tensor([[2, 3]], dtype=torch.long).expand(batch_size, -1)
    regions = RegionBatch(
        prior_features=prior,
        current_features=current,
        prior_valid=valid.clone(),
        current_valid=valid.clone(),
        prior_anatomy=prior_anatomy,
        current_anatomy=current_anatomy,
        prior_entity_ids=prior_ids,
        current_entity_ids=current_ids,
        prior_confidence=confidence.clone(),
        current_confidence=confidence.clone(),
        prior_source_ids=prior_source_ids.clone(),
        current_source_ids=current_source_ids.clone(),
        time_delta_days=torch.full((batch_size,), 30.0),
    )
    regions.validate()
    return regions, labels


def _swap_regions(regions: RegionBatch) -> RegionBatch:
    swapped = RegionBatch(
        prior_features=regions.current_features,
        current_features=regions.prior_features,
        prior_valid=regions.current_valid,
        current_valid=regions.prior_valid,
        prior_anatomy=regions.current_anatomy,
        current_anatomy=regions.prior_anatomy,
        prior_entity_ids=regions.current_entity_ids,
        current_entity_ids=regions.prior_entity_ids,
        prior_boxes=regions.current_boxes,
        current_boxes=regions.prior_boxes,
        prior_confidence=regions.current_confidence,
        current_confidence=regions.prior_confidence,
        prior_source_ids=regions.current_source_ids,
        current_source_ids=regions.prior_source_ids,
        time_delta_days=regions.time_delta_days,
    )
    swapped.validate()
    return swapped


def _concatenate_regions(first: RegionBatch, second: RegionBatch) -> RegionBatch:
    fields: dict[str, Any] = {}
    for name in (
        "prior_features",
        "current_features",
        "prior_valid",
        "current_valid",
        "prior_anatomy",
        "current_anatomy",
        "prior_entity_ids",
        "current_entity_ids",
        "prior_confidence",
        "current_confidence",
        "prior_source_ids",
        "current_source_ids",
        "time_delta_days",
    ):
        first_value = getattr(first, name)
        second_value = getattr(second, name)
        fields[name] = torch.cat((first_value, second_value), dim=0)
    regions = RegionBatch(**fields)
    regions.validate()
    return regions


def _prompt(batch_size: int, device: torch.device) -> Tensor:
    row = torch.tensor(
        [2, 3] + [PLACEHOLDER_TOKEN_ID] * 64 + [4],
        dtype=torch.long,
        device=device,
    )
    return row.unsqueeze(0).expand(batch_size, -1).clone()


def _build_model(feature_dim: int, hidden_size: int) -> CAPESCIModel:
    matcher = NullAwareMatchGraph(
        feature_dim=feature_dim,
        hidden_dim=hidden_size,
        temperature=0.45,
        projection_iterations=20,
    )
    projector = RelationProjector(
        input_dim=4 * feature_dim + 3,
        hidden_size=hidden_size,
    )
    adapter = FrozenVLMAdapter(
        FrozenRelationCausalLM(hidden_size=hidden_size),
        PLACEHOLDER_TOKEN_ID,
        LABEL_TOKEN_IDS,
    )
    return CAPESCIModel(
        matcher,
        projector,
        adapter,
        DeterministicGlobalAllocator(max_slots=28),
    )


def _null_deleted_plan(regions: RegionBatch, oracle: MatchPlan) -> MatchPlan:
    transport = oracle.transport.clone()
    batch, prior_plus, current_plus = transport.shape
    prior_count = prior_plus - 1
    current_count = current_plus - 1
    for batch_index in range(batch):
        deaths = torch.nonzero(
            transport[batch_index, :prior_count, current_count] > 0.5,
            as_tuple=False,
        ).flatten()
        births = torch.nonzero(
            transport[batch_index, prior_count, :current_count] > 0.5,
            as_tuple=False,
        ).flatten()
        if deaths.numel() and births.numel():
            prior_index = int(deaths[0].item())
            current_index = int(births[0].item())
            transport[batch_index, prior_index, current_count] = 0.0
            transport[batch_index, prior_count, current_index] = 0.0
            transport[batch_index, prior_index, current_index] = 1.0
    plan = MatchPlan(transport=transport, mode="null_deleted_intervention")
    plan.validate_hard(regions)
    return plan


def main() -> int:
    args = parse_args()
    if args.run_dir.exists():
        raise FileExistsError(args.run_dir)
    args.run_dir.mkdir(parents=True)
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    torch.manual_seed(args.seed)
    device = torch.device(args.device)

    original_regions, original_labels = _make_progression_cases(
        cases_per_class=args.cases_per_class,
        feature_dim=args.feature_dim,
        seed=args.data_seed,
    )
    swapped_regions = _swap_regions(original_regions)
    swapped_labels = order_swap_label(original_labels)
    training_regions = _concatenate_regions(original_regions, swapped_regions).to(
        device
    )
    training_labels = torch.cat((original_labels, swapped_labels)).to(device)
    prompt = _prompt(training_labels.numel(), device)

    model = _build_model(args.feature_dim, args.hidden_size).to(device)
    model.train()
    optimizer = torch.optim.AdamW(
        [parameter for parameter in model.parameters() if parameter.requires_grad],
        lr=args.learning_rate,
        weight_decay=0.0,
    )
    losses: list[float] = []
    accuracies: list[float] = []
    started = time.perf_counter()
    for _ in range(args.steps):
        optimizer.zero_grad(set_to_none=True)
        output = model(training_regions, prompt, assignment_mode="learned_soft")
        scores = output["label_scores"]
        loss = F.cross_entropy(scores, training_labels)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(
            [parameter for parameter in model.parameters() if parameter.requires_grad],
            max_norm=10.0,
        )
        optimizer.step()
        predictions = scores.argmax(dim=-1)
        losses.append(float(loss.detach().cpu()))
        accuracies.append(
            float(predictions.eq(training_labels).float().mean().detach().cpu())
        )
    elapsed_seconds = time.perf_counter() - started

    model.eval()
    with torch.inference_mode():
        final = model(training_regions, prompt, assignment_mode="learned_soft")
    final_scores = final["label_scores"]
    final_predictions = final_scores.argmax(dim=-1)
    final_loss = float(F.cross_entropy(final_scores, training_labels).cpu())
    original_count = original_labels.numel()
    original_accuracy = float(
        final_predictions[:original_count]
        .eq(training_labels[:original_count])
        .float()
        .mean()
        .cpu()
    )
    swapped_accuracy = float(
        final_predictions[original_count:]
        .eq(training_labels[original_count:])
        .float()
        .mean()
        .cpu()
    )

    intervention_batch = make_synthetic_batch(
        num_cases=4,
        seed=args.data_seed + 91,
        feature_dim=args.feature_dim,
    ).to(device)
    oracle = intervention_batch.oracle
    deranged = anatomy_compatible_derangement(
        intervention_batch.regions, oracle, seed=1701
    )
    candidates = build_soft_relation_candidates(intervention_batch.regions, oracle)
    shared_allocation = model.allocator(candidates)
    intervention_prompt = _prompt(4, device)
    with torch.inference_mode():
        oracle_scores = model(
            intervention_batch.regions,
            intervention_prompt,
            assignment_mode="provided",
            provided_plan=oracle,
            allocation_plan=shared_allocation,
        )["label_scores"]
        deranged_scores = model(
            intervention_batch.regions,
            intervention_prompt,
            assignment_mode="provided",
            provided_plan=deranged,
            allocation_plan=shared_allocation,
        )["label_scores"]
        no_null_scores = model(
            intervention_batch.regions,
            intervention_prompt,
            assignment_mode="provided",
            provided_plan=_null_deleted_plan(intervention_batch.regions, oracle),
            allocation_plan=shared_allocation,
        )["label_scores"]
    assignment_intervention_l1 = float(
        (oracle_scores - deranged_scores).abs().mean().cpu()
    )
    null_intervention_l1 = float((oracle_scores - no_null_scores).abs().mean().cpu())

    state_sha256 = _state_hash(model)
    checkpoint_path = args.run_dir / "model_state.pt"
    torch.save(model.state_dict(), checkpoint_path)
    checks = {
        "balanced_five_labels": torch.bincount(original_labels, minlength=5).tolist()
        == [args.cases_per_class] * 5,
        "full_accuracy_at_least_0_95": float(
            final_predictions.eq(training_labels).float().mean().cpu()
        )
        >= 0.95,
        "original_accuracy_at_least_0_95": original_accuracy >= 0.95,
        "order_swapped_accuracy_at_least_0_95": swapped_accuracy >= 0.95,
        "assignment_intervention_changes_logits": assignment_intervention_l1 > 1e-6,
        "null_intervention_changes_logits": null_intervention_l1 > 1e-6,
        "frozen_vlm": final["audits"]["trainable_parameters"]["frozen_vlm"],
        "no_pixel_path": final["audits"]["pixel_inputs_used"] is False,
        "exact_64_tokens": final["token_bundle"].tokens.shape[1] == 64,
        "finite_final_scores": bool(torch.isfinite(final_scores).all()),
    }
    summary = {
        "evidence_class": EVIDENCE_CLASS,
        "formal_claim_allowed": False,
        "status": "PASS" if all(checks.values()) else "FAIL",
        "config": {
            "seed": args.seed,
            "data_seed": args.data_seed,
            "cases_per_class": args.cases_per_class,
            "feature_dim": args.feature_dim,
            "hidden_size": args.hidden_size,
            "steps": args.steps,
            "learning_rate": args.learning_rate,
            "device": str(device),
        },
        "metrics": {
            "initial_loss": losses[0],
            "final_step_loss": losses[-1],
            "final_eval_loss": final_loss,
            "initial_accuracy": accuracies[0],
            "final_accuracy": float(
                final_predictions.eq(training_labels).float().mean().cpu()
            ),
            "original_accuracy": original_accuracy,
            "order_swapped_accuracy": swapped_accuracy,
            "assignment_intervention_l1": assignment_intervention_l1,
            "null_intervention_l1": null_intervention_l1,
            "elapsed_seconds": elapsed_seconds,
        },
        "predictions": final_predictions.cpu().tolist(),
        "targets": training_labels.cpu().tolist(),
        "checks": checks,
        "model_state_sha256": state_sha256,
        "checkpoint": {
            "path": str(checkpoint_path.resolve()),
            "bytes": checkpoint_path.stat().st_size,
        },
        "environment": {
            "python": platform.python_version(),
            "torch": torch.__version__,
            "platform": platform.platform(),
        },
    }
    summary_path = args.run_dir / "summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps(summary, sort_keys=True))
    print(f"RESULT_DIR={args.run_dir.resolve()}")
    return 0 if summary["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
