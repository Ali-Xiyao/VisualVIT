from __future__ import annotations

import math
import time
from typing import Any, Literal

import torch
from torch import nn

from visualvit.tier import (
    NonlinearRouter,
    class_weights,
    expert_router_features,
    set_determinism,
)


def fit_scalar_temperatures(
    expert_logits: torch.Tensor,
    targets: torch.Tensor,
    *,
    steps: int = 300,
    learning_rate: float = 0.03,
    device: torch.device | str = "cpu",
) -> tuple[torch.Tensor, dict[str, Any]]:
    if expert_logits.ndim != 3:
        raise ValueError("expert logits must have shape [N, experts, classes]")
    if targets.shape != (expert_logits.shape[0],):
        raise ValueError("temperature targets must align with expert logits")
    set_determinism(20260728)
    device = torch.device(device)
    logits = expert_logits.to(device)
    target_device = targets.to(device)
    log_temperatures = nn.Parameter(
        torch.zeros(expert_logits.shape[1], device=device)
    )
    optimizer = torch.optim.Adam(
        (log_temperatures,), lr=learning_rate
    )
    start = time.perf_counter()
    final_loss = float("nan")
    for _ in range(steps):
        optimizer.zero_grad(set_to_none=True)
        temperatures = log_temperatures.exp()
        calibrated = logits / temperatures[None, :, None]
        losses = [
            nn.functional.cross_entropy(
                calibrated[:, expert_index], target_device
            )
            for expert_index in range(expert_logits.shape[1])
        ]
        loss = torch.stack(losses).mean()
        loss.backward()
        optimizer.step()
        with torch.no_grad():
            log_temperatures.clamp_(-2.0, 2.0)
        final_loss = float(loss.detach().cpu())
    temperatures = log_temperatures.detach().exp().cpu()
    return temperatures, {
        "temperatures": [float(value) for value in temperatures],
        "final_loss": final_loss,
        "runtime_seconds": time.perf_counter() - start,
        "finite": math.isfinite(final_loss)
        and bool(torch.isfinite(temperatures).all())
        and bool((temperatures > 0).all()),
    }


def apply_temperatures(
    expert_logits: torch.Tensor, temperatures: torch.Tensor
) -> torch.Tensor:
    if expert_logits.ndim != 3:
        raise ValueError("expert logits must have shape [N, experts, classes]")
    if temperatures.shape != (expert_logits.shape[1],):
        raise ValueError("one temperature is required per expert")
    if not bool(torch.isfinite(temperatures).all()) or not bool(
        (temperatures > 0).all()
    ):
        raise ValueError("temperatures must be finite and positive")
    return expert_logits / temperatures[None, :, None]


def expert_choice_targets(
    calibrated_logits: torch.Tensor, targets: torch.Tensor
) -> torch.Tensor:
    if calibrated_logits.ndim != 3:
        raise ValueError("expert logits must have shape [N, experts, classes]")
    if targets.shape != (calibrated_logits.shape[0],):
        raise ValueError("choice targets must align with expert logits")
    predictions = calibrated_logits.argmax(-1)
    correct = predictions.eq(targets[:, None])
    first_correct = correct.float().argmax(-1)
    no_correct = ~correct.any(-1)
    target_probability = calibrated_logits.softmax(-1).gather(
        2,
        targets[:, None, None].expand(-1, calibrated_logits.shape[1], 1),
    )[:, :, 0]
    best_probability = target_probability.argmax(-1)
    return torch.where(no_correct, best_probability, first_correct)


def fit_choice_router(
    train_base: torch.Tensor,
    train_calibrated_logits: torch.Tensor,
    train_targets: torch.Tensor,
    test_base: torch.Tensor,
    test_calibrated_logits: torch.Tensor,
    *,
    seed: int,
    steps: int,
    learning_rate: float,
    weight_decay: float = 1e-4,
    device: torch.device | str = "cpu",
) -> tuple[torch.Tensor, dict[str, Any]]:
    set_determinism(seed)
    device = torch.device(device)
    train_features = expert_router_features(
        train_base, train_calibrated_logits
    ).to(device)
    test_features = expert_router_features(
        test_base, test_calibrated_logits
    ).to(device)
    choice_targets = expert_choice_targets(
        train_calibrated_logits, train_targets
    )
    target_device = choice_targets.to(device)
    model = NonlinearRouter(
        train_features.shape[1], train_calibrated_logits.shape[1], hidden_dim=32
    ).to(device)
    weights = class_weights(
        choice_targets, train_calibrated_logits.shape[1]
    ).to(device)
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=learning_rate, weight_decay=weight_decay
    )
    start = time.perf_counter()
    final_loss = float("nan")
    for _ in range(steps):
        optimizer.zero_grad(set_to_none=True)
        route_logits = model(train_features)
        loss = nn.functional.cross_entropy(
            route_logits, target_device, weight=weights
        )
        loss.backward()
        optimizer.step()
        final_loss = float(loss.detach().cpu())
    with torch.inference_mode():
        train_probabilities = model(train_features).softmax(-1)
        test_probabilities = model(test_features).softmax(-1).cpu()
    counts = torch.bincount(
        choice_targets, minlength=train_calibrated_logits.shape[1]
    )
    return test_probabilities, {
        "kind": "nonlinear_choice_supervised",
        "seed": seed,
        "final_loss": final_loss,
        "train_choice_accuracy": float(
            (
                train_probabilities.argmax(-1) == target_device
            ).float().mean().cpu()
        ),
        "choice_target_counts": [int(value) for value in counts],
        "mean_test_probabilities": [
            float(value) for value in test_probabilities.mean(0)
        ],
        "runtime_seconds": time.perf_counter() - start,
        "parameter_count": sum(
            parameter.numel() for parameter in model.parameters()
        ),
        "finite": math.isfinite(final_loss)
        and bool(torch.isfinite(test_probabilities).all()),
    }


def select_routed_logits(
    calibrated_logits: torch.Tensor,
    route_probabilities: torch.Tensor,
    *,
    mode: Literal["hard", "guarded"],
    fallback_expert: int = 1,
    minimum_probability: float = 0.60,
    minimum_margin: float = 0.15,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    if calibrated_logits.ndim != 3:
        raise ValueError("expert logits must have shape [N, experts, classes]")
    if route_probabilities.shape != calibrated_logits.shape[:2]:
        raise ValueError("route probabilities must align with expert logits")
    top2 = route_probabilities.topk(k=2, dim=-1)
    choices = top2.indices[:, 0]
    accepted = torch.ones(len(choices), dtype=torch.bool)
    if mode == "guarded":
        accepted = (top2.values[:, 0] >= minimum_probability) & (
            top2.values[:, 0] - top2.values[:, 1] >= minimum_margin
        )
        choices = torch.where(
            accepted,
            choices,
            torch.full_like(choices, fallback_expert),
        )
    elif mode != "hard":
        raise ValueError(f"unknown routing mode: {mode}")
    selected = calibrated_logits[
        torch.arange(len(calibrated_logits)), choices
    ]
    return selected, choices, accepted


__all__ = [
    "apply_temperatures",
    "expert_choice_targets",
    "fit_choice_router",
    "fit_scalar_temperatures",
    "select_routed_logits",
]
