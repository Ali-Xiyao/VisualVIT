from __future__ import annotations

import math
import os
import time
from typing import Any, Literal, Sequence

import torch
from torch import nn


EXPERT_NAMES = ("state_expert", "global_expert", "binding_expert")


def set_determinism(seed: int) -> None:
    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.use_deterministic_algorithms(True)


def signed_random_projection(
    values: torch.Tensor,
    *,
    output_dim: int,
    seed: int,
) -> tuple[torch.Tensor, str]:
    if values.ndim != 2 or values.shape[1] == 0:
        raise ValueError("projection input must be a non-empty 2-D tensor")
    if output_dim < 1:
        raise ValueError("projection output dimension must be positive")
    generator = torch.Generator(device="cpu")
    generator.manual_seed(seed)
    signs = (
        torch.randint(
            0,
            2,
            (values.shape[1], output_dim),
            generator=generator,
            dtype=torch.int8,
        ).float()
        * 2.0
        - 1.0
    ) / math.sqrt(output_dim)
    projected = values.float() @ signs
    digest = torch.tensor(signs.shape, dtype=torch.int64).numpy().tobytes()
    import hashlib

    hasher = hashlib.sha256()
    hasher.update(digest)
    hasher.update(signs.numpy().tobytes())
    return projected, hasher.hexdigest()


class LinearExpert(nn.Module):
    def __init__(self, input_dim: int, class_count: int) -> None:
        super().__init__()
        self.norm = nn.LayerNorm(input_dim, elementwise_affine=False)
        self.linear = nn.Linear(input_dim, class_count)

    def forward(self, value: torch.Tensor) -> torch.Tensor:
        return self.linear(self.norm(value))


class ExpertBundle(nn.Module):
    def __init__(
        self, input_dims: Sequence[int], class_count: int
    ) -> None:
        super().__init__()
        self.experts = nn.ModuleList(
            LinearExpert(input_dim, class_count) for input_dim in input_dims
        )

    def forward(self, values: Sequence[torch.Tensor]) -> torch.Tensor:
        if len(values) != len(self.experts):
            raise ValueError("one input tensor is required per expert")
        return torch.stack(
            [model(value) for model, value in zip(self.experts, values, strict=True)],
            dim=1,
        )


class LinearRouter(nn.Module):
    def __init__(self, input_dim: int, expert_count: int) -> None:
        super().__init__()
        self.norm = nn.LayerNorm(input_dim, elementwise_affine=False)
        self.linear = nn.Linear(input_dim, expert_count)

    def forward(self, value: torch.Tensor) -> torch.Tensor:
        return self.linear(self.norm(value))


class NonlinearRouter(nn.Module):
    def __init__(
        self, input_dim: int, expert_count: int, hidden_dim: int = 32
    ) -> None:
        super().__init__()
        self.norm = nn.LayerNorm(input_dim, elementwise_affine=False)
        self.hidden = nn.Linear(input_dim, hidden_dim)
        self.output = nn.Linear(hidden_dim, expert_count)

    def forward(self, value: torch.Tensor) -> torch.Tensor:
        return self.output(nn.functional.gelu(self.hidden(self.norm(value))))


def class_weights(targets: torch.Tensor, class_count: int) -> torch.Tensor:
    counts = torch.bincount(targets, minlength=class_count).float()
    if bool((counts == 0).any()):
        raise RuntimeError("training partition is missing a registered label")
    return counts.sum() / (class_count * counts)


def fit_expert_bundle(
    train_values: Sequence[torch.Tensor],
    train_targets: torch.Tensor,
    test_values: Sequence[torch.Tensor],
    *,
    seed: int,
    class_count: int,
    steps: int,
    learning_rate: float,
    weight_decay: float = 1e-4,
    device: torch.device | str = "cpu",
) -> tuple[torch.Tensor, dict[str, Any]]:
    set_determinism(seed)
    device = torch.device(device)
    model = ExpertBundle(
        [int(value.shape[1]) for value in train_values], class_count
    ).to(device)
    train_device = [value.to(device) for value in train_values]
    test_device = [value.to(device) for value in test_values]
    targets = train_targets.to(device)
    weights = class_weights(train_targets, class_count).to(device)
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=learning_rate, weight_decay=weight_decay
    )
    start = time.perf_counter()
    final_losses = [float("nan")] * len(train_values)
    for _ in range(steps):
        optimizer.zero_grad(set_to_none=True)
        logits = model(train_device)
        losses = [
            nn.functional.cross_entropy(
                logits[:, index], targets, weight=weights
            )
            for index in range(logits.shape[1])
        ]
        loss = torch.stack(losses).mean()
        loss.backward()
        optimizer.step()
        final_losses = [float(value.detach().cpu()) for value in losses]
    with torch.inference_mode():
        train_logits = model(train_device)
        test_logits = model(test_device).cpu()
    train_accuracy = [
        float(
            (train_logits[:, index].argmax(-1) == targets)
            .float()
            .mean()
            .cpu()
        )
        for index in range(train_logits.shape[1])
    ]
    return test_logits, {
        "seed": seed,
        "final_losses": final_losses,
        "train_accuracy": train_accuracy,
        "runtime_seconds": time.perf_counter() - start,
        "parameter_count": sum(
            parameter.numel() for parameter in model.parameters()
        ),
        "finite": all(math.isfinite(value) for value in final_losses)
        and bool(torch.isfinite(test_logits).all()),
    }


def expert_router_features(
    base_features: torch.Tensor, expert_logits: torch.Tensor
) -> torch.Tensor:
    if base_features.ndim != 2:
        raise ValueError("base router features must be 2-D")
    if expert_logits.ndim != 3:
        raise ValueError("expert logits must have shape [N, experts, classes]")
    if base_features.shape[0] != expert_logits.shape[0]:
        raise ValueError("router base features and logits must align")
    probabilities = expert_logits.softmax(-1)
    entropy = -(
        probabilities * probabilities.clamp_min(1e-8).log()
    ).sum(-1)
    top2 = probabilities.topk(k=2, dim=-1).values
    maximum = top2[..., 0]
    margin = top2[..., 0] - top2[..., 1]
    return torch.cat(
        (
            base_features.float(),
            expert_logits.flatten(1).float(),
            entropy.float(),
            maximum.float(),
            margin.float(),
        ),
        dim=1,
    )


def fit_router(
    train_base: torch.Tensor,
    train_expert_logits: torch.Tensor,
    train_targets: torch.Tensor,
    test_base: torch.Tensor,
    test_expert_logits: torch.Tensor,
    *,
    kind: Literal["linear", "nonlinear"],
    seed: int,
    steps: int,
    learning_rate: float,
    weight_decay: float = 1e-4,
    device: torch.device | str = "cpu",
) -> tuple[torch.Tensor, torch.Tensor, dict[str, Any]]:
    set_determinism(seed)
    device = torch.device(device)
    train_features = expert_router_features(
        train_base, train_expert_logits
    ).to(device)
    test_features = expert_router_features(
        test_base, test_expert_logits
    ).to(device)
    train_logits = train_expert_logits.to(device)
    test_logits = test_expert_logits.to(device)
    targets = train_targets.to(device)
    if kind == "linear":
        model: nn.Module = LinearRouter(
            train_features.shape[1], train_logits.shape[1]
        )
    elif kind == "nonlinear":
        model = NonlinearRouter(
            train_features.shape[1], train_logits.shape[1], hidden_dim=32
        )
    else:
        raise ValueError(f"unknown router kind: {kind}")
    model = model.to(device)
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=learning_rate, weight_decay=weight_decay
    )
    weights = class_weights(train_targets, train_logits.shape[-1]).to(device)
    start = time.perf_counter()
    final_loss = float("nan")
    for _ in range(steps):
        optimizer.zero_grad(set_to_none=True)
        route_weights = model(train_features).softmax(-1)
        mixture = torch.einsum("ne,nec->nc", route_weights, train_logits)
        loss = nn.functional.cross_entropy(mixture, targets, weight=weights)
        loss.backward()
        optimizer.step()
        final_loss = float(loss.detach().cpu())
    with torch.inference_mode():
        train_route = model(train_features).softmax(-1)
        train_mixture = torch.einsum("ne,nec->nc", train_route, train_logits)
        test_route = model(test_features).softmax(-1)
        test_mixture = torch.einsum("ne,nec->nc", test_route, test_logits)
    return test_mixture.cpu(), test_route.cpu(), {
        "kind": kind,
        "seed": seed,
        "final_loss": final_loss,
        "train_accuracy": float(
            (train_mixture.argmax(-1) == targets).float().mean().cpu()
        ),
        "mean_train_weights": [
            float(value) for value in train_route.mean(0).cpu()
        ],
        "mean_test_weights": [
            float(value) for value in test_route.mean(0).cpu()
        ],
        "runtime_seconds": time.perf_counter() - start,
        "parameter_count": sum(
            parameter.numel() for parameter in model.parameters()
        ),
        "finite": math.isfinite(final_loss)
        and bool(torch.isfinite(test_mixture).all())
        and bool(torch.isfinite(test_route).all()),
    }


def uniform_fusion(expert_logits: torch.Tensor) -> torch.Tensor:
    if expert_logits.ndim != 3 or expert_logits.shape[1] != len(EXPERT_NAMES):
        raise ValueError("uniform fusion requires three expert logit blocks")
    return expert_logits.mean(dim=1)


__all__ = [
    "EXPERT_NAMES",
    "ExpertBundle",
    "LinearExpert",
    "LinearRouter",
    "NonlinearRouter",
    "class_weights",
    "expert_router_features",
    "fit_expert_bundle",
    "fit_router",
    "set_determinism",
    "signed_random_projection",
    "uniform_fusion",
]
