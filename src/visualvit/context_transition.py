from __future__ import annotations

import math
import os
import time
from typing import Any, Iterable, Mapping, Sequence

import torch
from torch import nn


BOX_NAMES = (
    "right lung",
    "right upper lung zone",
    "right mid lung zone",
    "right lower lung zone",
    "right hilar structures",
    "right apical zone",
    "right costophrenic angle",
    "right hemidiaphragm",
    "left lung",
    "left upper lung zone",
    "left mid lung zone",
    "left lower lung zone",
    "left hilar structures",
    "left apical zone",
    "left costophrenic angle",
    "left hemidiaphragm",
    "cardiac silhouette",
    "mediastinum",
    "upper mediastinum",
    "aortic arch",
    "trachea",
)


def _normalize_phrase(value: str) -> str:
    return " ".join(
        value.lower()
        .replace("bilateral", "both")
        .replace("bases", "lower lung")
        .replace("base", "lower lung")
        .split()
    )


def _side_names(phrase: str, base: str) -> list[str]:
    if "left" in phrase and "right" not in phrase:
        return [f"left {base}"]
    if "right" in phrase and "left" not in phrase:
        return [f"right {base}"]
    return [f"left {base}", f"right {base}"]


def _pulmonary_fallback(
    phrase: str, available: set[str]
) -> list[str]:
    sides = []
    if "right" in phrase:
        sides.append("right")
    if "left" in phrase:
        sides.append("left")
    if not sides:
        sides = ["left", "right"]
    suffixes = (
        "lung",
        "lower lung zone",
        "mid lung zone",
        "upper lung zone",
        "costophrenic angle",
        "hemidiaphragm",
        "apical zone",
        "hilar structures",
    )
    return [
        name
        for side in sides
        for suffix in suffixes
        if (name := f"{side} {suffix}") in available
    ][:1]


def map_anatomy(anatomy: str, available: Iterable[str]) -> list[str]:
    available_set = {str(value).lower() for value in available}
    mapped: list[str] = []
    for raw_part in str(anatomy).split(","):
        phrase = _normalize_phrase(raw_part)
        candidates: list[str]
        if phrase in available_set:
            candidates = [phrase]
        elif "cardiac" in phrase or "heart" in phrase:
            candidates = ["cardiac silhouette"]
            if "mediast" in phrase:
                candidates.append("mediastinum")
        elif "mediast" in phrase:
            candidates = ["mediastinum"]
        elif "hilar" in phrase or "hilum" in phrase:
            candidates = _side_names(phrase, "hilar structures")
        elif "costophrenic" in phrase:
            candidates = _side_names(phrase, "costophrenic angle")
        elif "hemi" in phrase and "diaphragm" in phrase:
            candidates = _side_names(phrase, "hemidiaphragm")
        elif "apex" in phrase or "apical" in phrase:
            candidates = _side_names(phrase, "apical zone")
        elif "upper" in phrase and "lung" in phrase:
            candidates = _side_names(phrase, "upper lung zone")
        elif "mid" in phrase and "lung" in phrase:
            candidates = _side_names(phrase, "mid lung zone")
        elif "lower" in phrase and "lung" in phrase:
            candidates = _side_names(phrase, "lower lung zone")
        elif "lung" in phrase or "pleur" in phrase or "thorax" in phrase:
            candidates = _side_names(phrase, "lung")
        elif "aortic" in phrase:
            candidates = ["aortic arch"]
        elif "trache" in phrase:
            candidates = ["trachea"]
        else:
            candidates = ["left lung", "right lung"]
        before = len(mapped)
        for candidate in candidates:
            if candidate in available_set and candidate not in mapped:
                mapped.append(candidate)
        if (
            len(mapped) == before
            and any(
                token in phrase
                for token in (
                    "lung",
                    "pleur",
                    "thorax",
                    "costophrenic",
                    "diaphragm",
                    "apex",
                    "apical",
                    "hilar",
                    "hilum",
                )
            )
        ):
            for candidate in _pulmonary_fallback(phrase, available_set):
                if candidate not in mapped:
                    mapped.append(candidate)
    if mapped:
        return mapped
    preferred = [
        name for name in ("left lung", "right lung") if name in available_set
    ]
    if preferred:
        return preferred
    registered = [name for name in BOX_NAMES if name in available_set]
    if registered:
        return registered
    if available_set:
        return [sorted(available_set)[0]]
    raise ValueError("scene graph contains no anatomy objects")


def union_box(
    objects: Sequence[Mapping[str, Any]], names: Sequence[str]
) -> tuple[float, float, float, float]:
    selected = [
        value
        for value in objects
        if str(value["bbox_name"]).lower() in set(names)
    ]
    if not selected:
        raise ValueError("no scene object matched mapped anatomy")
    return (
        min(float(value["x1"]) for value in selected),
        min(float(value["y1"]) for value in selected),
        max(float(value["x2"]) for value in selected),
        max(float(value["y2"]) for value in selected),
    )


def expand_box(
    box: Sequence[float], factor: float = 1.5, limit: float = 224.0
) -> tuple[float, float, float, float]:
    x1, y1, x2, y2 = (float(value) for value in box)
    center_x = (x1 + x2) / 2
    center_y = (y1 + y2) / 2
    width = (x2 - x1) * factor
    height = (y2 - y1) * factor
    return (
        max(0.0, center_x - width / 2),
        max(0.0, center_y - height / 2),
        min(limit, center_x + width / 2),
        min(limit, center_y + height / 2),
    )


def geometry_features(
    exact: Sequence[float],
    context: Sequence[float],
    prior_view: str,
    current_view: str,
) -> torch.Tensor:
    x1, y1, x2, y2 = (float(value) for value in exact)
    cx1, cy1, cx2, cy2 = (float(value) for value in context)
    return torch.tensor(
        (
            (x1 + x2) / 448.0,
            (y1 + y2) / 448.0,
            (x2 - x1) / 224.0,
            (y2 - y1) / 224.0,
            (cx2 - cx1) / 224.0,
            (cy2 - cy1) / 224.0,
            float(str(prior_view).upper() == "AP"),
            float(str(current_view).upper() == "AP"),
            float(str(prior_view).upper() != str(current_view).upper()),
        ),
        dtype=torch.float32,
    )


def pair_interactions(
    prior: torch.Tensor, current: torch.Tensor
) -> torch.Tensor:
    prior = prior.float() / prior.float().norm().clamp_min(1e-8)
    current = current.float() / current.float().norm().clamp_min(1e-8)
    delta = current - prior
    return torch.cat((prior, current, delta, delta.abs(), prior * current))


class TransitionHead(nn.Module):
    def __init__(self, input_dim: int, class_count: int) -> None:
        super().__init__()
        self.norm = nn.LayerNorm(input_dim, elementwise_affine=False)
        self.hidden = nn.Linear(input_dim, 128)
        self.output = nn.Linear(128, class_count)

    def forward(self, value: torch.Tensor) -> torch.Tensor:
        return self.output(nn.functional.gelu(self.hidden(self.norm(value))))


def _class_weights(targets: torch.Tensor, class_count: int) -> torch.Tensor:
    counts = torch.bincount(targets, minlength=class_count).float()
    if bool((counts == 0).any()):
        raise RuntimeError("training data is missing a registered class")
    return counts.sum() / (class_count * counts)


def fit_transition_head(
    train_values: torch.Tensor,
    train_targets: torch.Tensor,
    test_values: torch.Tensor,
    *,
    seed: int,
    class_count: int,
    steps: int = 350,
    learning_rate: float = 0.01,
    weight_decay: float = 1e-4,
    device: str | torch.device = "cpu",
) -> tuple[torch.Tensor, dict[str, Any]]:
    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.use_deterministic_algorithms(True)
    device = torch.device(device)
    model = TransitionHead(train_values.shape[1], class_count).to(device)
    train = train_values.to(device)
    test = test_values.to(device)
    targets = train_targets.to(device)
    weights = _class_weights(train_targets, class_count).to(device)
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=learning_rate, weight_decay=weight_decay
    )
    start = time.perf_counter()
    final_loss = float("nan")
    for _ in range(steps):
        optimizer.zero_grad(set_to_none=True)
        logits = model(train)
        loss = nn.functional.cross_entropy(logits, targets, weight=weights)
        loss.backward()
        optimizer.step()
        final_loss = float(loss.detach().cpu())
    with torch.inference_mode():
        train_logits = model(train)
        test_logits = model(test).cpu()
    return test_logits, {
        "seed": seed,
        "final_loss": final_loss,
        "train_accuracy": float(
            (train_logits.argmax(-1) == targets).float().mean().cpu()
        ),
        "runtime_seconds": time.perf_counter() - start,
        "parameter_count": sum(p.numel() for p in model.parameters()),
        "finite": math.isfinite(final_loss)
        and bool(torch.isfinite(test_logits).all()),
    }


__all__ = [
    "BOX_NAMES",
    "TransitionHead",
    "expand_box",
    "fit_transition_head",
    "geometry_features",
    "map_anatomy",
    "pair_interactions",
    "union_box",
]
