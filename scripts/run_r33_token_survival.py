from __future__ import annotations

# ruff: noqa: E402

import argparse
from collections import Counter
import json
import math
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
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

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
    parser.add_argument(
        "--scope",
        choices=("train_dev", "train_only"),
        default="train_dev",
        help="train_only is reserved for R33A exploratory case-study runs",
    )
    parser.add_argument(
        "--route-mode",
        choices=("consensus", "benefit"),
        default="consensus",
    )
    parser.add_argument(
        "--probe-type",
        choices=("linear", "mlp", "bridge64"),
        default="linear",
    )
    return parser.parse_args()


def mask_token_types(features: Tensor, token_types: tuple[int, ...]) -> Tensor:
    """Keep selected type summaries without changing the 774-wide probe."""

    if features.ndim != 2:
        raise ValueError("features must be a matrix")
    output = torch.zeros_like(features)
    if features.shape[1] == 774:
        for token_type in token_types:
            if not 0 <= token_type < 6:
                raise ValueError("token type must be in [0, 5]")
            output[:, token_type * 64 : (token_type + 1) * 64] = features[
                :, token_type * 64 : (token_type + 1) * 64
            ]
            max_start = 384 + token_type * 64
            output[:, max_start : max_start + 64] = features[
                :, max_start : max_start + 64
            ]
            output[:, 768 + token_type] = features[:, 768 + token_type]
    elif features.shape[1] == 1286:
        for token_type in token_types:
            if not 0 <= token_type < 5:
                raise ValueError("prebridge token type must be in [0, 4]")
            start = token_type * 256
            output[:, start : start + 256] = features[:, start : start + 256]
            output[:, 1280 + token_type] = features[:, 1280 + token_type]
    else:
        raise ValueError("unsupported feature width")
    return output


def select_routed(robust: Tensor, rich: Tensor, route: Tensor) -> Tensor:
    if robust.shape != rich.shape:
        raise ValueError("robust/rich feature shapes must match")
    if route.dtype is not torch.bool or tuple(route.shape) != (robust.shape[0],):
        raise ValueError("route must be bool [N]")
    return torch.where(route[:, None], rich, robust)


def benefit_router_features(robust_logits: Tensor, rich_logits: Tensor) -> Tensor:
    """Build label-free row features from three robust/rich probe families."""

    if robust_logits.shape != rich_logits.shape:
        raise ValueError("robust/rich logits must have matching shapes")
    if robust_logits.ndim != 3 or robust_logits.shape[0] != len(SEEDS):
        raise ValueError("benefit logits must have shape [3, N, C]")

    def summarize(logits: Tensor) -> tuple[Tensor, ...]:
        probabilities = logits.softmax(dim=-1)
        ordered = probabilities.topk(k=2, dim=-1).values
        entropy = -(probabilities * probabilities.clamp_min(1e-12).log()).sum(dim=-1)
        votes = (
            F.one_hot(probabilities.argmax(dim=-1), num_classes=len(LABELS))
            .float()
            .mean(dim=0)
        )
        return (
            probabilities.permute(1, 0, 2).reshape(probabilities.shape[1], -1),
            entropy.transpose(0, 1),
            ordered[..., 0].transpose(0, 1),
            (ordered[..., 0] - ordered[..., 1]).transpose(0, 1),
            votes,
        )

    robust = summarize(robust_logits)
    rich = summarize(rich_logits)
    return torch.cat(
        (
            robust[0],
            rich[0],
            rich[0] - robust[0],
            *robust[1:],
            *rich[1:],
        ),
        dim=1,
    )


def benefit_router_targets(
    robust_logits: Tensor, rich_logits: Tensor, labels: Tensor
) -> tuple[Tensor, Tensor, Tensor]:
    if labels.shape != (robust_logits.shape[1],):
        raise ValueError("benefit labels must align with logits")
    robust_correct = robust_logits.argmax(-1).eq(labels[None])
    rich_correct = rich_logits.argmax(-1).eq(labels[None])
    helped = ((~robust_correct) & rich_correct).sum(dim=0)
    harmed = (robust_correct & (~rich_correct)).sum(dim=0)
    score = helped - harmed
    return score.gt(0).long(), score.ne(0), score


def fit_benefit_router(
    train_features: Tensor,
    train_targets: Tensor,
    eval_features: Tensor,
    *,
    seed: int,
) -> tuple[Tensor, dict[str, Any]]:
    if train_features.ndim != 2 or eval_features.ndim != 2:
        raise ValueError("router features must be matrices")
    if train_targets.shape != (train_features.shape[0],):
        raise ValueError("router targets must align with training features")
    if set(train_targets.tolist()) != {0, 1}:
        raise RuntimeError("benefit router requires both target classes")
    model = make_pipeline(
        StandardScaler(),
        LogisticRegression(
            C=0.1,
            class_weight="balanced",
            max_iter=1_000,
            random_state=seed,
        ),
    )
    model.fit(train_features.numpy(), train_targets.numpy())
    train_probabilities = torch.from_numpy(
        model.predict_proba(train_features.numpy())[:, 1]
    ).float()
    eval_probabilities = torch.from_numpy(
        model.predict_proba(eval_features.numpy())[:, 1]
    ).float()
    return eval_probabilities.ge(0.5), {
        "seed": seed,
        "train_rows": int(train_features.shape[0]),
        "train_target_rich_rate": float(train_targets.float().mean()),
        "train_accuracy": float(
            train_probabilities.ge(0.5).eq(train_targets.bool()).float().mean()
        ),
        "eval_rich_coverage": float(eval_probabilities.ge(0.5).float().mean()),
        "feature_dim": int(train_features.shape[1]),
        "finite": bool(torch.isfinite(eval_probabilities).all()),
    }


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


def fit_batched_mlp(
    train_features: Tensor,
    train_labels: Tensor,
    sample_weights: Tensor,
    *,
    seed: int,
    device: torch.device,
    epochs: int,
    batch_size: int,
    hidden_dim: int = 128,
) -> dict[str, Tensor]:
    """Fit independent capacity-matched GELU probes in one GPU batch."""

    if train_features.ndim != 3:
        raise ValueError("train_features must have shape [M, N, D]")
    model_count, row_count, feature_dim = train_features.shape
    if train_labels.shape != (row_count,):
        raise ValueError("train_labels shape mismatch")
    x = train_features.to(device=device, dtype=torch.float32)
    y = train_labels.to(device=device)
    weights_per_row = sample_weights.to(device=device)
    mean = x.mean(dim=1, keepdim=True)
    std = x.std(dim=1, keepdim=True, unbiased=False).clamp_min(1e-6)
    x = (x - mean) / std

    generator = torch.Generator(device="cpu").manual_seed(seed)
    hidden_weight = (
        (
            torch.randn(
                model_count,
                feature_dim,
                hidden_dim,
                generator=generator,
            )
            / math.sqrt(feature_dim)
        )
        .to(device)
        .requires_grad_(True)
    )
    hidden_bias = torch.zeros(
        model_count, hidden_dim, device=device, requires_grad=True
    )
    output_weight = (
        (
            torch.randn(
                model_count,
                hidden_dim,
                len(LABELS),
                generator=generator,
            )
            / math.sqrt(hidden_dim)
        )
        .to(device)
        .requires_grad_(True)
    )
    output_bias = torch.zeros(
        model_count, len(LABELS), device=device, requires_grad=True
    )
    optimizer = torch.optim.AdamW(
        (hidden_weight, hidden_bias, output_weight, output_bias),
        lr=1e-4,
        weight_decay=1e-2,
    )
    for _ in range(epochs):
        permutation = torch.randperm(row_count, generator=generator)
        for start in range(0, row_count, batch_size):
            index = permutation[start : start + batch_size].to(device)
            hidden = F.gelu(
                torch.einsum("mbd,mdh->mbh", x[:, index], hidden_weight)
                + hidden_bias[:, None]
            )
            logits = (
                torch.einsum("mbh,mhc->mbc", hidden, output_weight)
                + output_bias[:, None]
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
        "hidden_weight": hidden_weight.detach().cpu(),
        "hidden_bias": hidden_bias.detach().cpu(),
        "output_weight": output_weight.detach().cpu(),
        "output_bias": output_bias.detach().cpu(),
        "mean": mean.squeeze(1).detach().cpu(),
        "std": std.squeeze(1).detach().cpu(),
    }


def predict_batched_mlp(
    models: dict[str, Tensor], features: Tensor, device: torch.device
) -> Tensor:
    if features.ndim != 3:
        raise ValueError("features must have shape [M, N, D]")
    x = features.to(device=device, dtype=torch.float32)
    mean = models["mean"].to(device)
    std = models["std"].to(device)
    with torch.inference_mode():
        hidden = F.gelu(
            torch.einsum(
                "mnd,mdh->mnh",
                (x - mean[:, None]) / std[:, None],
                models["hidden_weight"].to(device),
            )
            + models["hidden_bias"].to(device)[:, None]
        )
        logits = (
            torch.einsum(
                "mnh,mhc->mnc",
                hidden,
                models["output_weight"].to(device),
            )
            + models["output_bias"].to(device)[:, None]
        )
    return logits.cpu()


def fit_batched_bridge64(
    train_features: Tensor,
    train_labels: Tensor,
    sample_weights: Tensor,
    **kwargs: Any,
) -> dict[str, Tensor]:
    return fit_batched_mlp(
        train_features,
        train_labels,
        sample_weights,
        hidden_dim=64,
        **kwargs,
    )


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
    feature_dim = payload.get("feature_dim")
    valid_legacy = feature_dim == 774
    valid_prebridge = (
        feature_dim == 1286
        and payload.get("feature_type_width") == 256
        and payload.get("feature_type_count") == 5
        and payload.get("learned_bridge_width") == 64
    )
    if payload.get("token_budget") != 64 or not (
        valid_legacy or valid_prebridge
    ):
        raise RuntimeError("R33 token contract drift")


def main() -> int:
    args = parse_args()
    if args.route_mode == "benefit" and args.scope != "train_only":
        raise ValueError("benefit routing is restricted to R33A train-only")
    if args.output.exists():
        raise FileExistsError(f"output must be fresh: {args.output}")
    if args.epochs != 20 or args.batch_size != 128:
        raise ValueError("R33 protocol fixes epochs=20 and batch_size=128")
    if args.bootstrap != 10_000:
        raise ValueError("R33 protocol requires exactly 10,000 bootstrap draws")
    device = torch.device(args.device)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but unavailable")
    fit_probe = {
        "linear": fit_batched_linear,
        "mlp": fit_batched_mlp,
        "bridge64": fit_batched_bridge64,
    }[args.probe_type]
    predict_probe = (
        predict_batched_mlp
        if args.probe_type in {"mlp", "bridge64"}
        else predict_batched_linear
    )
    torch.use_deterministic_algorithms(True)
    payload = torch.load(args.features, map_location="cpu", weights_only=False)
    validate_input(payload)
    records = payload["records"]
    if args.scope == "train_only":
        keep = torch.tensor(
            [index for index, row in enumerate(records) if row["partition"] == "train"],
            dtype=torch.long,
        )
        records = [records[index] for index in keep.tolist()]
        payload["features"] = {
            name: {seed: value[keep] for seed, value in seeded.items()}
            for name, seeded in payload["features"].items()
        }
        expected_rows = 13_566
        expected_patients = 1_574
        allowed_partitions = {"train"}
    else:
        expected_rows = 15_698
        expected_patients = 1_874
        allowed_partitions = {"train", "dev"}
    if len(records) != expected_rows:
        raise RuntimeError(f"R33 scope record count drift: {len(records)}")
    patient_ids = [str(row["patient_id"]) for row in records]
    if len(set(patient_ids)) != expected_patients:
        raise RuntimeError("R33 patient count drift")
    if any(row["partition"] not in allowed_partitions for row in records):
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
    benefit_router_audits: list[dict[str, Any]] = []
    nested_fit_count = 0
    started = time.perf_counter()

    for outer_fold in range(5):
        outer_train = folds.ne(outer_fold)
        outer_eval = folds.eq(outer_fold)
        train_indices = outer_train.nonzero().flatten()
        eval_indices = outer_eval.nonzero().flatten()
        train_ids = [patient_ids[index] for index in train_indices.tolist()]
        train_weights = training_weights(labels[train_indices], train_ids)

        # Evaluation route probes are fit on all outer-training patients.
        # Benefit routing fits matched robust and rich probe families; the
        # registered consensus route needs only the three rich probes.
        if args.route_mode == "benefit":
            auxiliary_sources = (
                ("robust", *SEEDS),
                ("rich", *SEEDS),
            )
            aux_train = torch.stack(
                [
                    features[name][seed][train_indices]
                    for name, *seeds in auxiliary_sources
                    for seed in seeds
                ]
            )
            aux_eval = torch.stack(
                [
                    features[name][seed][eval_indices]
                    for name, *seeds in auxiliary_sources
                    for seed in seeds
                ]
            )
            aux_shifted_eval = torch.stack(
                [
                    features[f"prior_shuffle_{name}"][seed][eval_indices]
                    for name, *seeds in auxiliary_sources
                    for seed in seeds
                ]
            )
        else:
            aux_train = torch.stack(
                [features["rich"][seed][train_indices] for seed in SEEDS]
            )
            aux_eval = torch.stack(
                [features["rich"][seed][eval_indices] for seed in SEEDS]
            )
            aux_shifted_eval = torch.stack(
                [features["prior_shuffle_rich"][seed][eval_indices] for seed in SEEDS]
            )
        aux_models = fit_probe(
            aux_train,
            labels[train_indices],
            train_weights,
            seed=330_000 + outer_fold,
            device=device,
            epochs=args.epochs,
            batch_size=args.batch_size,
        )
        eval_logits = predict_probe(aux_models, aux_eval, device)
        eval_shifted_logits = predict_probe(aux_models, aux_shifted_eval, device)
        nested_fit_count += aux_train.shape[0]

        # Training routes: every inner fold is predicted by models that omit
        # both the outer evaluation fold and that inner prediction fold.
        training_aux_logits = torch.empty(
            aux_train.shape[0],
            train_indices.numel(),
            len(LABELS),
            dtype=torch.float32,
        )
        for inner_fold in range(5):
            if inner_fold == outer_fold:
                continue
            inner_eval_global = (outer_train & folds.eq(inner_fold)).nonzero().flatten()
            inner_fit_global = (outer_train & folds.ne(inner_fold)).nonzero().flatten()
            inner_fit_ids = [patient_ids[index] for index in inner_fit_global.tolist()]
            inner_weights = training_weights(labels[inner_fit_global], inner_fit_ids)
            if args.route_mode == "benefit":
                inner_features = torch.stack(
                    [
                        features[name][seed][inner_fit_global]
                        for name, *seeds in auxiliary_sources
                        for seed in seeds
                    ]
                )
                inner_eval_features = torch.stack(
                    [
                        features[name][seed][inner_eval_global]
                        for name, *seeds in auxiliary_sources
                        for seed in seeds
                    ]
                )
            else:
                inner_features = torch.stack(
                    [features["rich"][seed][inner_fit_global] for seed in SEEDS]
                )
                inner_eval_features = torch.stack(
                    [features["rich"][seed][inner_eval_global] for seed in SEEDS]
                )
            inner_models = fit_probe(
                inner_features,
                labels[inner_fit_global],
                inner_weights,
                seed=331_000 + outer_fold * 10 + inner_fold,
                device=device,
                epochs=args.epochs,
                batch_size=args.batch_size,
            )
            inner_logits = predict_probe(inner_models, inner_eval_features, device)
            local_mask = folds[train_indices].eq(inner_fold)
            if local_mask.sum() != inner_eval_global.numel():
                raise RuntimeError("inner route indexing drift")
            training_aux_logits[:, local_mask] = inner_logits
            nested_fit_count += inner_features.shape[0]

        if args.route_mode == "benefit":
            robust_train_logits = training_aux_logits[: len(SEEDS)]
            rich_train_logits = training_aux_logits[len(SEEDS) :]
            router_features = benefit_router_features(
                robust_train_logits, rich_train_logits
            )
            router_targets, decisive, benefit_score = benefit_router_targets(
                robust_train_logits,
                rich_train_logits,
                labels[train_indices],
            )
            training_route = torch.empty(train_indices.numel(), dtype=torch.bool)
            for router_fold in range(5):
                if router_fold == outer_fold:
                    continue
                router_eval = folds[train_indices].eq(router_fold)
                router_fit = (~router_eval) & decisive
                routed, audit = fit_benefit_router(
                    router_features[router_fit],
                    router_targets[router_fit],
                    router_features[router_eval],
                    seed=332_000 + outer_fold * 10 + router_fold,
                )
                training_route[router_eval] = routed
                benefit_router_audits.append(
                    {
                        "outer_fold": outer_fold,
                        "predicted_fold": router_fold,
                        "stage": "cross_fitted_training_route",
                        **audit,
                    }
                )
            final_route_fit = decisive
            eval_router_features = benefit_router_features(
                eval_logits[: len(SEEDS)], eval_logits[len(SEEDS) :]
            )
            shifted_router_features = benefit_router_features(
                eval_shifted_logits[: len(SEEDS)],
                eval_shifted_logits[len(SEEDS) :],
            )
            eval_route, audit = fit_benefit_router(
                router_features[final_route_fit],
                router_targets[final_route_fit],
                eval_router_features,
                seed=333_000 + outer_fold,
            )
            shifted_route, shifted_audit = fit_benefit_router(
                router_features[final_route_fit],
                router_targets[final_route_fit],
                shifted_router_features,
                seed=333_000 + outer_fold,
            )
            consensus_route[eval_indices] = eval_route
            shortcut_route[eval_indices] = shifted_route
            benefit_router_audits.append(
                {
                    "outer_fold": outer_fold,
                    "stage": "outer_eval_route",
                    "decisive_rows": int(decisive.sum()),
                    "benefit_score_positive": int(benefit_score.gt(0).sum()),
                    "benefit_score_negative": int(benefit_score.lt(0).sum()),
                    **audit,
                }
            )
            benefit_router_audits.append(
                {
                    "outer_fold": outer_fold,
                    "stage": "prior_shuffle_route",
                    **shifted_audit,
                }
            )
        else:
            training_route = hard_consensus_route(training_aux_logits)
            consensus_route[eval_indices] = hard_consensus_route(eval_logits)
            shortcut_route[eval_indices] = hard_consensus_route(eval_shifted_logits)
        route_assignment_count[eval_indices] += 1

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
            final_models = fit_probe(
                train_systems,
                labels[train_indices],
                train_weights,
                seed=seed + outer_fold * 10_000,
                device=device,
                epochs=args.epochs,
                batch_size=args.batch_size,
            )
            logits = predict_probe(final_models, eval_systems, device)
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
            shifted_logits = predict_probe(selected_models, shifted_eval, device)
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
    if args.scope == "train_only":
        status = (
            "PASS_R33A_TRAIN_EXPLORATORY_GATES"
            if scientific_pass
            else "STOP_R33A_TRAIN_EXPLORATION"
        )
    else:
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
            "route_mode": args.route_mode,
        },
        prediction_path,
    )
    result = {
        "schema": "visualvit.r33.token-survival-result.v1",
        "status": status,
        "evidence_class": (
            "EXPLORATORY_TRAIN_ONLY_NESTED_OOF"
            if args.scope == "train_only"
            else "NON_CONFIRMATORY_TRAIN_DEV_NESTED_OOF"
        ),
        "scope": args.scope,
        "route_mode": args.route_mode,
        "probe_type": args.probe_type,
        "protocol": str(
            WORKSPACE
            / "docs/superpowers/specs"
            / (
                (
                    "2026-07-26-r33a-attempt-d-anatomy-context-v1.md"
                    if payload.get("variant") == "r33a_anatomy_context_v1"
                    else (
                        "2026-07-26-r33a-attempt-c-token-mlp-v1.md"
                        if args.probe_type == "mlp"
                        else (
                            "2026-07-26-r33a-attempt-b-benefit-router-v1.md"
                            if args.route_mode == "benefit"
                            else "2026-07-26-r33a-attempt-a-protocol-v1.md"
                        )
                    )
                )
                if args.scope == "train_only"
                else "2026-07-26-r33-token-survival-protocol-v1.md"
            )
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
        "trainable_params_per_probe": (
            payload["feature_dim"]
            * (64 if args.probe_type == "bridge64" else 128)
            + (64 if args.probe_type == "bridge64" else 128)
            + (64 if args.probe_type == "bridge64" else 128) * len(LABELS)
            + len(LABELS)
            if args.probe_type in {"mlp", "bridge64"}
            else payload["feature_dim"] * len(LABELS) + len(LABELS)
        ),
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
            "selected_route": route_behavior(
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
            "benefit_router_cross_fitted": args.route_mode == "benefit",
            "benefit_router_audits": benefit_router_audits,
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
        "fresh_process_reproduction_required": (
            scientific_pass and args.scope == "train_dev"
        ),
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
