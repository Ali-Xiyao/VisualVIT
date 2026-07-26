from __future__ import annotations

import hashlib
from typing import Iterable

import torch
from torch import Tensor

from .schemas import TokenBundle


def hard_consensus_route(probe_logits: Tensor) -> Tensor:
    """Return rich=True only when all registered probe predictions agree."""

    if probe_logits.ndim != 3:
        raise ValueError("probe_logits must have shape [K, B, C]")
    if probe_logits.shape[0] != 3:
        raise ValueError("the primary hard gate requires exactly three probes")
    if probe_logits.shape[-1] < 2:
        raise ValueError("probe_logits need at least two classes")
    if not bool(torch.isfinite(probe_logits).all()):
        raise ValueError("probe_logits must be finite")
    predictions = probe_logits.argmax(dim=-1)
    return predictions.eq(predictions[:1]).all(dim=0)


def select_bundle(
    robust: TokenBundle, rich: TokenBundle, route: Tensor
) -> TokenBundle:
    robust.validate()
    rich.validate()
    if robust.tokens.shape != rich.tokens.shape:
        raise ValueError("robust/rich token shapes must match")
    if not torch.equal(robust.token_types, rich.token_types):
        raise ValueError("robust/rich token layouts must match")
    batch_size = robust.tokens.shape[0]
    if tuple(route.shape) != (batch_size,) or route.dtype is not torch.bool:
        raise ValueError("route must be a bool tensor with shape [B]")
    choose = route.view(-1, 1, 1)
    choose_meta = route.view(-1, 1)

    def optional(name: str):
        left = getattr(robust, name)
        right = getattr(rich, name)
        if left is None or right is None:
            if left is not None or right is not None:
                raise ValueError(f"robust/rich {name} presence must match")
            return None
        return torch.where(choose_meta, right, left)

    return TokenBundle(
        tokens=torch.where(choose, rich.tokens, robust.tokens),
        token_types=robust.token_types,
        valid_mask=torch.where(
            choose_meta, rich.valid_mask, robust.valid_mask
        ),
        assignment=torch.where(choose, rich.assignment, robust.assignment),
        anatomy_ids=optional("anatomy_ids"),
        temporal_ids=optional("temporal_ids"),
        confidence=optional("confidence"),
        slot_mass=optional("slot_mass"),
        source_ids=optional("source_ids"),
    )


def matched_random_route(route: Tensor, seed: int) -> Tensor:
    """Randomize case identity while preserving exact rich coverage."""

    if route.ndim != 1 or route.dtype is not torch.bool:
        raise ValueError("route must be a one-dimensional bool tensor")
    generator = torch.Generator(device="cpu").manual_seed(seed)
    permutation = torch.randperm(route.numel(), generator=generator).to(
        route.device
    )
    return route[permutation]


def patient_fold(patient_id: object, fold_count: int = 5) -> int:
    if fold_count <= 1:
        raise ValueError("fold_count must be greater than one")
    payload = f"r33-oof-fold-v1|{patient_id}".encode("utf-8")
    return int(hashlib.sha256(payload).hexdigest(), 16) % fold_count


def fold_assignment(
    patient_ids: Iterable[object], fold_count: int = 5
) -> dict[str, int]:
    return {
        str(patient): patient_fold(patient, fold_count)
        for patient in sorted({str(value) for value in patient_ids})
    }


def assert_oof_routes(
    rows: Iterable[dict[str, object]],
    assignment: dict[str, int],
) -> None:
    for row in rows:
        patient = str(row["patient_id"])
        predicted_fold = int(row["predicted_fold"])
        trained_folds = {int(value) for value in row["trained_folds"]}  # type: ignore[arg-type]
        if assignment.get(patient) != predicted_fold:
            raise ValueError("route predicted_fold does not match patient fold")
        if predicted_fold in trained_folds:
            raise ValueError("in-sample route detected")

