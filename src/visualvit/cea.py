from __future__ import annotations

from typing import Any

import torch
from torch import Tensor


def jensen_shannon_causal_score(
    source_probabilities: Tensor,
    current_only_probabilities: Tensor,
) -> Tensor:
    """Measure temporal evidence as confidence-weighted JS divergence."""

    if (
        source_probabilities.ndim != 2
        or source_probabilities.shape != current_only_probabilities.shape
        or source_probabilities.shape[1] < 2
    ):
        raise ValueError("CEA probabilities must be aligned [N,C] tensors")
    if not bool(
        torch.isfinite(source_probabilities).all()
        and torch.isfinite(current_only_probabilities).all()
    ):
        raise ValueError("CEA probabilities must be finite")
    tolerance = 1e-5
    if bool(
        source_probabilities.lt(0).any()
        or current_only_probabilities.lt(0).any()
        or (source_probabilities.sum(dim=-1) - 1).abs().gt(tolerance).any()
        or (current_only_probabilities.sum(dim=-1) - 1)
        .abs()
        .gt(tolerance)
        .any()
    ):
        raise ValueError("CEA inputs must be probability distributions")
    epsilon = torch.finfo(source_probabilities.dtype).eps
    source = source_probabilities.clamp_min(epsilon)
    current = current_only_probabilities.clamp_min(epsilon)
    mixture = 0.5 * (source + current)
    divergence = 0.5 * (
        (source * (source.log() - mixture.log())).sum(dim=-1)
        + (current * (current.log() - mixture.log())).sum(dim=-1)
    )
    confidence = source_probabilities.amax(dim=-1)
    score = divergence.clamp_min(0) * confidence
    if not bool(torch.isfinite(score).all()):
        raise FloatingPointError("CEA score is non-finite")
    return score


def arbitrate_predictions(
    *,
    baseline_predictions: list[int],
    structured_predictions: list[int],
    scores: Tensor,
    threshold: float,
) -> dict[str, Any]:
    """Override the baseline only on registered high-evidence examples."""

    if (
        len(baseline_predictions) != len(structured_predictions)
        or len(baseline_predictions) != len(scores)
        or not baseline_predictions
    ):
        raise ValueError("CEA arbitration inputs must align and be non-empty")
    if threshold < 0:
        raise ValueError("CEA threshold must be non-negative")
    eligible = scores.ge(float(threshold)).cpu().tolist()
    predictions = [
        int(structured) if bool(use_head) else int(baseline)
        for baseline, structured, use_head in zip(
            baseline_predictions,
            structured_predictions,
            eligible,
            strict=True,
        )
    ]
    changed = [
        bool(use_head) and int(structured) != int(baseline)
        for baseline, structured, use_head in zip(
            baseline_predictions,
            structured_predictions,
            eligible,
            strict=True,
        )
    ]
    low_evidence = [not bool(value) for value in eligible]
    agreement = (
        sum(
            prediction == baseline
            for prediction, baseline, is_low in zip(
                predictions,
                baseline_predictions,
                low_evidence,
                strict=True,
            )
            if is_low
        )
        / sum(low_evidence)
        if any(low_evidence)
        else 1.0
    )
    return {
        "predictions": predictions,
        "eligible": [bool(value) for value in eligible],
        "changed": changed,
        "eligible_coverage": sum(eligible) / len(eligible),
        "actual_override_rate": sum(changed) / len(changed),
        "low_evidence_baseline_agreement": agreement,
    }


def select_shared_quantile(
    candidates: dict[str, list[dict[str, float]]],
) -> dict[str, float]:
    """Select one preregistered quantile across all Seeds."""

    if not candidates:
        raise ValueError("CEA candidate registry is empty")
    rows = []
    for quantile, seed_rows in candidates.items():
        if not seed_rows:
            raise ValueError("CEA candidate has no Seed rows")
        rows.append(
            {
                "quantile": float(quantile),
                "mean_macro_f1": sum(
                    float(row["macro_f1"]) for row in seed_rows
                )
                / len(seed_rows),
                "mean_actual_override_rate": sum(
                    float(row["actual_override_rate"]) for row in seed_rows
                )
                / len(seed_rows),
            }
        )
    rows.sort(
        key=lambda row: (
            -row["mean_macro_f1"],
            row["mean_actual_override_rate"],
            -row["quantile"],
        )
    )
    return rows[0]
