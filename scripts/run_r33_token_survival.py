from __future__ import annotations

# ruff: noqa: E402

import argparse
from collections import Counter
import json
import os
from pathlib import Path
import sys
import time
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE / "src"))
os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")

import torch
from torch import Tensor
from torch.nn import functional as F

from visualvit.perturbation_consensus_router import (
    hard_consensus_route,
    matched_random_route,
    patient_fold,
)


FEATURES_DEFAULT = Path(
    r"F:\VisualVIT_runtime\050_routeC\r33_token_survival"
    r"\features_v1\token_features.pt"
)
OUTPUT_DEFAULT = Path(
    r"F:\VisualVIT_runtime\050_routeC\r33_token_survival"
    r"\nested_oof_v1\r33_token_survival_result.json"
)
LABELS = ("Stable", "Improved", "Worse")
SYSTEMS = ("P0", "P1", "P2", "P3", "P4", "P5", "P6")
SEEDS = (17, 29, 43)
TYPE_SETS = {
    "P0": (0,),
    "P1": (0, 1),
    "P2": (0, 2),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the frozen R33 nested-OOF token-survival gate"
    )
    parser.add_argument("--features", type=Path, default=FEATURES_DEFAULT)
    parser.add_argument("--output", type=Path, default=OUTPUT_DEFAULT)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--bootstrap", type=int, default=10_000)
    return parser.parse_args()


def mask_token_types(features: Tensor, token_types: tuple[int, ...]) -> Tensor:
    """Keep selected type summaries without changing the 774-wide probe."""

    if features.ndim != 2 or features.shape[1] != 774:
        raise ValueError("features must have shape [N, 774]")
    output = torch.zeros_like(features)
    for token_type in token_types:
        if not 0 <= token_type < 6:
            raise ValueError("token type must be in [0, 5]")
        output[:, token_type * 64 : (token_type + 1) * 64] = features[
            :, token_type * 64 : (token_type + 1) * 64
        ]
        max_start = 384 + token_type * 64
        output[:, max_start : max_start + 64] = features[:, max_start : max_start + 64]
        output[:, 768 + token_type] = features[:, 768 + token_type]
    return output


def select_routed(robust: Tensor, rich: Tensor, route: Tensor) -> Tensor:
    if robust.shape != rich.shape:
        raise ValueError("robust/rich feature shapes must match")
    if route.dtype is not torch.bool or tuple(route.shape) != (robust.shape[0],):
        raise ValueError("route must be bool [N]")
    return torch.where(route[:, None], rich, robust)


def training_weights(labels: Tensor, patient_ids: list[str]) -> Tensor:
    """Product of inverse class and inverse rows-per-patient weights."""

    if labels.ndim != 1 or len(patient_ids) != labels.numel():
        raise ValueError("labels and patient_ids must align")
    class_counts = torch.bincount(labels, minlength=len(LABELS)).float()
    if bool(class_counts.eq(0).any()):
        raise ValueError("every class must occur in a training fold")
    patient_counts = Counter(patient_ids)
    weights = torch.tensor(
        [
            1.0 / (float(class_counts[int(label)]) * patient_counts[patient])
            for label, patient in zip(labels.tolist(), patient_ids, strict=True)
        ],
        dtype=torch.float32,
    )
    return weights / weights.mean()


def fit_batched_linear(
    train_features: Tensor,
    train_labels: Tensor,
    sample_weights: Tensor,
    *,
    seed: int,
    device: torch.device,
    epochs: int,
    batch_size: int,
) -> dict[str, Tensor]:
    """Fit independent linear probes batched across the model dimension."""

    if train_features.ndim != 3:
        raise ValueError("train_features must have shape [M, N, D]")
    model_count, row_count, feature_dim = train_features.shape
    if train_labels.shape != (row_count,):
        raise ValueError("train_labels shape mismatch")
    if sample_weights.shape != (row_count,):
        raise ValueError("sample_weights shape mismatch")

    x = train_features.to(device=device, dtype=torch.float32)
    y = train_labels.to(device=device)
    weights_per_row = sample_weights.to(device=device)
    mean = x.mean(dim=1, keepdim=True)
    std = x.std(dim=1, keepdim=True, unbiased=False).clamp_min(1e-6)
    x = (x - mean) / std

    generator = torch.Generator(device="cpu").manual_seed(seed)
    scale = (1.0 / feature_dim) ** 0.5
    weight = (
        torch.randn(model_count, feature_dim, len(LABELS), generator=generator)
        .mul_(scale)
        .to(device)
        .requires_grad_(True)
    )
    bias = torch.zeros(model_count, len(LABELS), device=device, requires_grad=True)
    optimizer = torch.optim.AdamW((weight, bias), lr=1e-4, weight_decay=1e-2)
    for _ in range(epochs):
        permutation = torch.randperm(row_count, generator=generator)
        for start in range(0, row_count, batch_size):
            index = permutation[start : start + batch_size].to(device)
            logits = (
                torch.einsum("mbd,mdc->mbc", x[:, index], weight) + bias[:, None, :]
            )
            losses = F.cross_entropy(
                logits.reshape(-1, len(LABELS)),
                y[index].repeat(model_count),
                reduction="none",
            ).view(model_count, -1)
            batch_weights = weights_per_row[index]
            loss = (
                (losses * batch_weights[None]).sum(dim=1) / batch_weights.sum()
            ).mean()
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            optimizer.step()
    return {
        "weight": weight.detach().cpu(),
        "bias": bias.detach().cpu(),
        "mean": mean.squeeze(1).detach().cpu(),
        "std": std.squeeze(1).detach().cpu(),
    }


def predict_batched_linear(
    models: dict[str, Tensor], features: Tensor, device: torch.device
) -> Tensor:
    if features.ndim != 3:
        raise ValueError("features must have shape [M, N, D]")
    x = features.to(device=device, dtype=torch.float32)
    weight = models["weight"].to(device)
    bias = models["bias"].to(device)
    mean = models["mean"].to(device)
    std = models["std"].to(device)
    with torch.inference_mode():
        logits = (
            torch.einsum("mnd,mdc->mnc", (x - mean[:, None]) / std[:, None], weight)
            + bias[:, None]
        )
    return logits.cpu()


def weighted_confusion(
    labels: Tensor,
    predictions: Tensor,
    patient_ids: list[str],
    probabilities: Tensor | None = None,
) -> dict[str, float | list[list[float]]]:
    """Patient-balanced metrics; predictions may contain a seed dimension."""

    if predictions.ndim == 1:
        predictions = predictions[None]
    if predictions.ndim != 2 or predictions.shape[1] != labels.numel():
        raise ValueError("prediction shape mismatch")
    patient_counts = Counter(patient_ids)
    row_weights = torch.tensor(
        [1.0 / patient_counts[patient] for patient in patient_ids]
    )
    row_weights /= row_weights.sum()
    row_weights /= predictions.shape[0]
    confusion = torch.zeros(len(LABELS), len(LABELS), dtype=torch.float64)
    for seed_index in range(predictions.shape[0]):
        flat = labels * len(LABELS) + predictions[seed_index]
        confusion += torch.bincount(
            flat, weights=row_weights, minlength=len(LABELS) ** 2
        ).view(len(LABELS), len(LABELS))
    tp = confusion.diag()
    precision = tp / confusion.sum(dim=0).clamp_min(1e-12)
    recall = tp / confusion.sum(dim=1).clamp_min(1e-12)
    f1 = 2 * precision * recall / (precision + recall).clamp_min(1e-12)
    result: dict[str, float | list[list[float]]] = {
        "macro_f1": float(f1.mean()),
        "balanced_accuracy": float(recall.mean()),
        "confusion": confusion.tolist(),
    }
    if probabilities is not None:
        if probabilities.ndim == 2:
            probabilities = probabilities[None]
        if tuple(probabilities.shape[:2]) != tuple(predictions.shape):
            raise ValueError("probability shape mismatch")
        expanded_labels = labels[None].expand(predictions.shape[0], -1)
        true_probs = probabilities.gather(2, expanded_labels.unsqueeze(-1)).squeeze(-1)
        expanded_weights = row_weights[None].expand_as(true_probs)
        result["nll"] = float(
            (-(true_probs.clamp_min(1e-12).log()) * expanded_weights).sum()
        )
        confidence, predicted = probabilities.max(dim=-1)
        correct = predicted.eq(expanded_labels).float()
        ece = torch.tensor(0.0)
        for lower in torch.linspace(0, 1, 16)[:-1]:
            upper = lower + 1 / 15
            mask = (confidence >= lower) & (
                (confidence < upper) if upper < 1 else (confidence <= upper)
            )
            bin_weight = (expanded_weights * mask).sum()
            if bin_weight > 0:
                accuracy = (expanded_weights * mask * correct).sum() / bin_weight
                mean_confidence = (
                    expanded_weights * mask * confidence
                ).sum() / bin_weight
                ece += bin_weight * (accuracy - mean_confidence).abs()
        result["ece"] = float(ece)
    return result


def patient_confusions(
    labels: Tensor, predictions: Tensor, patient_ids: list[str]
) -> tuple[list[str], Tensor]:
    """Return [patient, seed, true, predicted] equally weighted matrices."""

    if predictions.ndim == 1:
        predictions = predictions[None]
    patients = sorted(set(patient_ids))
    patient_index = {patient: index for index, patient in enumerate(patients)}
    counts = Counter(patient_ids)
    output = torch.zeros(
        len(patients),
        predictions.shape[0],
        len(LABELS),
        len(LABELS),
        dtype=torch.float64,
    )
    for row, patient in enumerate(patient_ids):
        weight = 1.0 / (counts[patient] * predictions.shape[0])
        for seed_index in range(predictions.shape[0]):
            output[
                patient_index[patient],
                seed_index,
                int(labels[row]),
                int(predictions[seed_index, row]),
            ] += weight
    return patients, output


def macro_f1_from_confusion(confusion: Tensor) -> Tensor:
    tp = confusion.diagonal(dim1=-2, dim2=-1)
    precision = tp / confusion.sum(dim=-2).clamp_min(1e-12)
    recall = tp / confusion.sum(dim=-1).clamp_min(1e-12)
    return (2 * precision * recall / (precision + recall).clamp_min(1e-12)).mean(dim=-1)


def bootstrap_systems(
    labels: Tensor,
    predictions: dict[str, Tensor],
    patient_ids: list[str],
    replicates: int,
    seed: int = 20260933,
) -> dict[str, Any]:
    names = list(predictions)
    patients, first = patient_confusions(labels, predictions[names[0]], patient_ids)
    matrices = [first.sum(dim=1)]
    for name in names[1:]:
        other_patients, matrix = patient_confusions(
            labels, predictions[name], patient_ids
        )
        if other_patients != patients:
            raise RuntimeError("bootstrap patient order drift")
        matrices.append(matrix.sum(dim=1))
    stacked = torch.stack(matrices, dim=1)
    generator = torch.Generator(device="cpu").manual_seed(seed)
    values = {name: torch.empty(replicates, dtype=torch.float64) for name in names}
    for start in range(0, replicates, 250):
        count = min(250, replicates - start)
        draws = torch.randint(
            len(patients),
            (count, len(patients)),
            generator=generator,
        )
        sample_counts = torch.zeros(count, len(patients), dtype=torch.float64)
        sample_counts.scatter_add_(
            1, draws, torch.ones_like(draws, dtype=torch.float64)
        )
        confusion = torch.einsum("bp,psij->bsij", sample_counts, stacked)
        f1 = macro_f1_from_confusion(confusion)
        for system_index, name in enumerate(names):
            values[name][start : start + count] = f1[:, system_index]
    result: dict[str, Any] = {
        "replicates_requested": replicates,
        "replicates_valid": replicates,
        "rng_seed": seed,
        "systems": {},
    }
    robust = values["P3"]
    for name in names:
        delta = values[name] - robust
        result["systems"][name] = {
            "f1_ci95": [
                float(torch.quantile(values[name], 0.025)),
                float(torch.quantile(values[name], 0.975)),
            ],
            "delta_vs_p3_ci95": [
                float(torch.quantile(delta, 0.025)),
                float(torch.quantile(delta, 0.975)),
            ],
        }
    return result


def route_behavior(
    labels: Tensor,
    robust_predictions: Tensor,
    routed_predictions: Tensor,
    routes: Tensor,
    patient_ids: list[str],
) -> dict[str, float]:
    if routes.ndim == 1:
        routes = routes[None].expand_as(robust_predictions)
    counts = Counter(patient_ids)
    weights = torch.tensor([1.0 / counts[patient] for patient in patient_ids])
    weights /= weights.sum() * robust_predictions.shape[0]
    expanded = weights[None]
    robust_correct = robust_predictions.eq(labels[None])
    routed_correct = routed_predictions.eq(labels[None])
    correction = (~robust_correct) & routed_correct
    harm = robust_correct & (~routed_correct)
    return {
        "rich_coverage": float((routes * expanded).sum()),
        "robust_coverage": float(((~routes) * expanded).sum()),
        "override_rate": float(
            (routed_predictions.ne(robust_predictions) * expanded).sum()
        ),
        "correction_rate": float((correction * expanded).sum()),
        "harm_rate": float((harm * expanded).sum()),
        "net_corrected": float(((correction.float() - harm.float()) * expanded).sum()),
    }


def validate_input(payload: dict[str, Any]) -> None:
    required_true = (
        "biomedclip_text_encoder_frozen",
        "builders_frozen",
        "prior_shuffle_cross_patient",
    )
    if payload.get("schema") != "visualvit.r33.token-features.v1":
        raise RuntimeError("unexpected feature schema")
    if payload.get("status") != "PASS_R33_FEATURE_PREPARATION":
        raise RuntimeError("feature preparation did not pass")
    if any(not payload.get(key) for key in required_true):
        raise RuntimeError("frozen feature audit failed")
    if payload.get("sealed_test_records_read") or payload.get(
        "sealed_test_images_read"
    ):
        raise RuntimeError("sealed-test access is forbidden")
    if payload.get("gold_outcomes_read"):
        raise RuntimeError("gold outcomes are forbidden")
    if payload.get("probe_labels_or_logits_in_tokens"):
        raise RuntimeError("label/logit token leakage")
    if payload.get("token_budget") != 64 or payload.get("feature_dim") != 774:
        raise RuntimeError("R33 token contract drift")


def main() -> int:
    args = parse_args()
    if args.output.exists():
        raise FileExistsError(f"output must be fresh: {args.output}")
    if args.epochs != 20 or args.batch_size != 128:
        raise ValueError("R33 protocol fixes epochs=20 and batch_size=128")
    if args.bootstrap != 10_000:
        raise ValueError("R33 protocol requires exactly 10,000 bootstrap draws")
    device = torch.device(args.device)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but unavailable")
    torch.use_deterministic_algorithms(True)
    payload = torch.load(args.features, map_location="cpu", weights_only=False)
    validate_input(payload)
    records = payload["records"]
    if len(records) != 15_698:
        raise RuntimeError("R33 record count drift")
    patient_ids = [str(row["patient_id"]) for row in records]
    if len(set(patient_ids)) != 1_874:
        raise RuntimeError("R33 patient count drift")
    if any(row["partition"] not in {"train", "dev"} for row in records):
        raise RuntimeError("forbidden R33 partition")
    label_index = {label: index for index, label in enumerate(LABELS)}
    labels = torch.tensor(
        [label_index[str(row["progression"])] for row in records],
        dtype=torch.long,
    )
    folds = torch.tensor(
        [patient_fold(patient) for patient in patient_ids], dtype=torch.long
    )
    features = {
        name: {int(seed): value.float() for seed, value in seeded.items()}
        for name, seeded in payload["features"].items()
    }

    row_count = len(records)
    predictions = {
        name: torch.empty(len(SEEDS), row_count, dtype=torch.long) for name in SYSTEMS
    }
    probabilities = {
        name: torch.empty(len(SEEDS), row_count, len(LABELS), dtype=torch.float32)
        for name in SYSTEMS
    }
    shortcut_predictions = {
        name: torch.empty(len(SEEDS), row_count, dtype=torch.long)
        for name in ("P3", "P6")
    }
    shortcut_probabilities = {
        name: torch.empty(len(SEEDS), row_count, len(LABELS), dtype=torch.float32)
        for name in ("P3", "P6")
    }
    consensus_route = torch.empty(row_count, dtype=torch.bool)
    shortcut_route = torch.empty(row_count, dtype=torch.bool)
    random_routes = torch.empty(len(SEEDS), row_count, dtype=torch.bool)
    route_assignment_count = torch.zeros(row_count, dtype=torch.long)
    nested_fit_count = 0
    started = time.perf_counter()

    for outer_fold in range(5):
        outer_train = folds.ne(outer_fold)
        outer_eval = folds.eq(outer_fold)
        train_indices = outer_train.nonzero().flatten()
        eval_indices = outer_eval.nonzero().flatten()
        train_ids = [patient_ids[index] for index in train_indices.tolist()]
        train_weights = training_weights(labels[train_indices], train_ids)

        # Evaluation routes: each of the three builders is fit on all outer
        # training patients and evaluated only on the held-out outer fold.
        aux_train = torch.stack(
            [features["rich"][seed][train_indices] for seed in SEEDS]
        )
        aux_models = fit_batched_linear(
            aux_train,
            labels[train_indices],
            train_weights,
            seed=330_000 + outer_fold,
            device=device,
            epochs=args.epochs,
            batch_size=args.batch_size,
        )
        eval_logits = predict_batched_linear(
            aux_models,
            torch.stack([features["rich"][seed][eval_indices] for seed in SEEDS]),
            device,
        )
        eval_shifted_logits = predict_batched_linear(
            aux_models,
            torch.stack(
                [features["prior_shuffle_rich"][seed][eval_indices] for seed in SEEDS]
            ),
            device,
        )
        consensus_route[eval_indices] = hard_consensus_route(eval_logits)
        shortcut_route[eval_indices] = hard_consensus_route(eval_shifted_logits)
        route_assignment_count[eval_indices] += 1
        nested_fit_count += len(SEEDS)

        # Training routes: every inner fold is predicted by models that omit
        # both the outer evaluation fold and that inner prediction fold.
        training_route = torch.empty(train_indices.numel(), dtype=torch.bool)
        for inner_fold in range(5):
            if inner_fold == outer_fold:
                continue
            inner_eval_global = (outer_train & folds.eq(inner_fold)).nonzero().flatten()
            inner_fit_global = (outer_train & folds.ne(inner_fold)).nonzero().flatten()
            inner_fit_ids = [patient_ids[index] for index in inner_fit_global.tolist()]
            inner_weights = training_weights(labels[inner_fit_global], inner_fit_ids)
            inner_models = fit_batched_linear(
                torch.stack(
                    [features["rich"][seed][inner_fit_global] for seed in SEEDS]
                ),
                labels[inner_fit_global],
                inner_weights,
                seed=331_000 + outer_fold * 10 + inner_fold,
                device=device,
                epochs=args.epochs,
                batch_size=args.batch_size,
            )
            inner_logits = predict_batched_linear(
                inner_models,
                torch.stack(
                    [features["rich"][seed][inner_eval_global] for seed in SEEDS]
                ),
                device,
            )
            local_mask = folds[train_indices].eq(inner_fold)
            if local_mask.sum() != inner_eval_global.numel():
                raise RuntimeError("inner route indexing drift")
            training_route[local_mask] = hard_consensus_route(inner_logits)
            nested_fit_count += len(SEEDS)

        for seed_index, seed in enumerate(SEEDS):
            robust_train = features["robust"][seed][train_indices]
            rich_train = features["rich"][seed][train_indices]
            robust_eval = features["robust"][seed][eval_indices]
            rich_eval = features["rich"][seed][eval_indices]
            random_train = matched_random_route(
                training_route, seed + outer_fold * 1_000
            )
            random_eval = matched_random_route(
                consensus_route[eval_indices],
                seed + outer_fold * 1_000 + 500,
            )
            random_routes[seed_index, eval_indices] = random_eval
            train_systems = torch.stack(
                (
                    mask_token_types(robust_train, TYPE_SETS["P0"]),
                    mask_token_types(robust_train, TYPE_SETS["P1"]),
                    mask_token_types(robust_train, TYPE_SETS["P2"]),
                    robust_train,
                    rich_train,
                    select_routed(robust_train, rich_train, random_train),
                    select_routed(robust_train, rich_train, training_route),
                )
            )
            eval_systems = torch.stack(
                (
                    mask_token_types(robust_eval, TYPE_SETS["P0"]),
                    mask_token_types(robust_eval, TYPE_SETS["P1"]),
                    mask_token_types(robust_eval, TYPE_SETS["P2"]),
                    robust_eval,
                    rich_eval,
                    select_routed(robust_eval, rich_eval, random_eval),
                    select_routed(
                        robust_eval,
                        rich_eval,
                        consensus_route[eval_indices],
                    ),
                )
            )
            final_models = fit_batched_linear(
                train_systems,
                labels[train_indices],
                train_weights,
                seed=seed + outer_fold * 10_000,
                device=device,
                epochs=args.epochs,
                batch_size=args.batch_size,
            )
            logits = predict_batched_linear(final_models, eval_systems, device)
            probs = logits.softmax(dim=-1)
            for system_index, system in enumerate(SYSTEMS):
                predictions[system][seed_index, eval_indices] = logits[
                    system_index
                ].argmax(dim=-1)
                probabilities[system][seed_index, eval_indices] = probs[system_index]

            shifted_robust = features["prior_shuffle_robust"][seed][eval_indices]
            shifted_rich = features["prior_shuffle_rich"][seed][eval_indices]
            shifted_eval = torch.stack(
                (
                    shifted_robust,
                    select_routed(
                        shifted_robust,
                        shifted_rich,
                        shortcut_route[eval_indices],
                    ),
                )
            )
            selected_models = {
                key: value[[3, 6]] for key, value in final_models.items()
            }
            shifted_logits = predict_batched_linear(
                selected_models, shifted_eval, device
            )
            for shifted_index, system in enumerate(("P3", "P6")):
                shortcut_predictions[system][seed_index, eval_indices] = shifted_logits[
                    shifted_index
                ].argmax(dim=-1)
                shortcut_probabilities[system][seed_index, eval_indices] = (
                    shifted_logits[shifted_index].softmax(dim=-1)
                )

    if not bool(route_assignment_count.eq(1).all()):
        raise RuntimeError("each R33 row must receive exactly one OOF route")

    # P7 is a label-reading upper bound that chooses P4 only when doing so
    # repairs P3 (otherwise P3); it is never used as a fitted input.
    oracle_predictions = predictions["P3"].clone()
    oracle_probabilities = probabilities["P3"].clone()
    rich_repairs = predictions["P4"].eq(labels[None]) & predictions["P3"].ne(
        labels[None]
    )
    oracle_predictions[rich_repairs] = predictions["P4"][rich_repairs]
    oracle_probabilities[rich_repairs] = probabilities["P4"][rich_repairs]
    all_predictions = {**predictions, "P7": oracle_predictions}
    all_probabilities = {**probabilities, "P7": oracle_probabilities}

    metrics = {
        system: weighted_confusion(
            labels,
            all_predictions[system],
            patient_ids,
            all_probabilities[system],
        )
        for system in (*SYSTEMS, "P7")
    }
    bootstrap = bootstrap_systems(labels, all_predictions, patient_ids, args.bootstrap)
    seed_results: dict[str, Any] = {}
    for seed_index, seed in enumerate(SEEDS):
        robust = weighted_confusion(labels, predictions["P3"][seed_index], patient_ids)
        rich = weighted_confusion(labels, predictions["P4"][seed_index], patient_ids)
        tier = weighted_confusion(labels, predictions["P6"][seed_index], patient_ids)
        seed_bootstrap = bootstrap_systems(
            labels,
            {
                "P3": predictions["P3"][seed_index],
                "P6": predictions["P6"][seed_index],
            },
            patient_ids,
            args.bootstrap,
            seed=20260933 + seed,
        )
        seed_results[str(seed)] = {
            "robust_f1": robust["macro_f1"],
            "always_rich_f1": rich["macro_f1"],
            "tier_f1": tier["macro_f1"],
            "tier_minus_robust": float(tier["macro_f1"]) - float(robust["macro_f1"]),
            "delta_ci95": seed_bootstrap["systems"]["P6"]["delta_vs_p3_ci95"],
            "route_coverage": route_behavior(
                labels,
                predictions["P3"][seed_index : seed_index + 1],
                predictions["P6"][seed_index : seed_index + 1],
                consensus_route,
                patient_ids,
            )["rich_coverage"],
        }

    shortcut_metrics = {
        system: weighted_confusion(
            labels,
            shortcut_predictions[system],
            patient_ids,
            shortcut_probabilities[system],
        )
        for system in ("P3", "P6")
    }
    shortcut_delta = float(shortcut_metrics["P6"]["macro_f1"]) - float(
        shortcut_metrics["P3"]["macro_f1"]
    )
    primary_delta = float(metrics["P6"]["macro_f1"]) - float(metrics["P3"]["macro_f1"])
    nonoracle_best_system = max(
        SYSTEMS[:-1],
        key=lambda system: float(metrics[system]["macro_f1"]),
    )
    nonoracle_gap = float(metrics["P6"]["macro_f1"]) - float(
        metrics[nonoracle_best_system]["macro_f1"]
    )
    gate_checks = {
        "delta_at_least_2pp": primary_delta >= 0.02,
        "ci_lower_above_zero": bootstrap["systems"]["P6"]["delta_vs_p3_ci95"][0] > 0,
        "all_seed_deltas_positive": all(
            result["tier_minus_robust"] > 0 for result in seed_results.values()
        ),
        "within_1pp_strongest_nonoracle": nonoracle_gap >= -0.01,
        "prior_shuffle_reduces_delta_by_0_5pp": shortcut_delta <= primary_delta - 0.005,
        "query_only_at_least_1pp_below_tier": float(metrics["P6"]["macro_f1"])
        - float(metrics["P0"]["macro_f1"])
        >= 0.01,
        "leakage_and_seal_audits": True,
        "bootstrap_10000_valid": bootstrap["replicates_valid"] == 10_000,
    }
    scientific_pass = all(gate_checks.values())
    status = (
        "PASS_R33_SCIENTIFIC_GATES_AWAIT_REPRODUCTION"
        if scientific_pass
        else "STOP_R33_TOKEN_SURVIVAL"
    )

    prediction_path = args.output.with_name("r33_oof_predictions.pt")
    prediction_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "schema": "visualvit.r33.oof-predictions.v1",
            "record_ids": [row["record_id"] for row in records],
            "labels": labels,
            "folds": folds,
            "predictions": all_predictions,
            "probabilities": all_probabilities,
            "prior_shuffle_predictions": shortcut_predictions,
            "consensus_route": consensus_route,
            "prior_shuffle_route": shortcut_route,
            "random_routes": random_routes,
        },
        prediction_path,
    )
    result = {
        "schema": "visualvit.r33.token-survival-result.v1",
        "status": status,
        "evidence_class": "NON_CONFIRMATORY_TRAIN_DEV_NESTED_OOF",
        "protocol": str(
            WORKSPACE
            / "docs/superpowers/specs"
            / "2026-07-26-r33-token-survival-protocol-v1.md"
        ),
        "features": str(args.features),
        "prediction_artifact": str(prediction_path),
        "record_count": row_count,
        "patient_count": len(set(patient_ids)),
        "fold_patient_counts": {
            str(fold): len(
                {
                    patient
                    for patient, assigned in zip(
                        patient_ids, folds.tolist(), strict=True
                    )
                    if assigned == fold
                }
            )
            for fold in range(5)
        },
        "seeds": SEEDS,
        "epochs": args.epochs,
        "batch_size": args.batch_size,
        "trainable_params_per_probe": 774 * len(LABELS) + len(LABELS),
        "metrics": metrics,
        "bootstrap": bootstrap,
        "seed_results": seed_results,
        "primary_delta": primary_delta,
        "primary_delta_pp": primary_delta * 100,
        "strongest_nonoracle": nonoracle_best_system,
        "tier_gap_to_strongest_nonoracle": nonoracle_gap,
        "prior_shuffle_metrics": shortcut_metrics,
        "prior_shuffle_delta": shortcut_delta,
        "prior_shuffle_delta_pp": shortcut_delta * 100,
        "route_behavior": {
            "hard_consensus": route_behavior(
                labels,
                predictions["P3"],
                predictions["P6"],
                consensus_route,
                patient_ids,
            ),
            "matched_random": route_behavior(
                labels,
                predictions["P3"],
                predictions["P5"],
                random_routes,
                patient_ids,
            ),
        },
        "route_audit": {
            "nested_auxiliary_probe_fits": nested_fit_count,
            "outer_eval_route_fit_folds": 4,
            "inner_training_route_fit_folds": 3,
            "every_row_exactly_one_outer_prediction": True,
            "outer_eval_patients_absent_from_fits": True,
            "training_routes_out_of_fold": True,
        },
        "audits": {
            "exact_64": True,
            "fixed_layout": True,
            "no_label_tokens": True,
            "no_logit_tokens": True,
            "sealed_test_records_read": False,
            "sealed_test_images_read": False,
            "gold_outcomes_read": False,
            "probe_models_frozen_feature_inputs": True,
        },
        "gate_checks": gate_checks,
        "fresh_process_reproduction_required": scientific_pass,
        "fresh_process_reproduced": False,
        "elapsed_seconds": time.perf_counter() - started,
    }
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "status": status,
                "primary_delta_pp": result["primary_delta_pp"],
                "primary_delta_ci95_pp": [
                    value * 100
                    for value in bootstrap["systems"]["P6"]["delta_vs_p3_ci95"]
                ],
                "seed_deltas_pp": {
                    seed: value["tier_minus_robust"] * 100
                    for seed, value in seed_results.items()
                },
                "strongest_nonoracle": nonoracle_best_system,
                "tier_gap_to_strongest_nonoracle_pp": nonoracle_gap * 100,
                "prior_shuffle_delta_pp": shortcut_delta * 100,
                "gate_checks": gate_checks,
                "elapsed_seconds": result["elapsed_seconds"],
                "output": str(args.output),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
