from __future__ import annotations

from collections import defaultdict

import torch
from torch import Tensor, nn

from .schemas import AllocationPlan, RelationCandidates


SLOT_COUNT = 28


class DeterministicGlobalAllocator(nn.Module):
    """Build an assignment-independent, fixed-width source allocation.

    Ranking first takes the highest-confidence valid source from each anatomy
    group.  Those representatives are ordered by confidence and anatomy ID.
    Remaining sources are ordered by confidence, anatomy, temporal side, and
    stable source ID.  No entity/relation feature or relation mass is read.
    """

    def __init__(
        self,
        max_slots: int = SLOT_COUNT,
        *,
        num_slots: int | None = None,
    ) -> None:
        super().__init__()
        if num_slots is not None:
            if max_slots != SLOT_COUNT and max_slots != num_slots:
                raise ValueError("max_slots and num_slots disagree")
            max_slots = num_slots
        if max_slots != SLOT_COUNT:
            raise ValueError("CAPES-CI v1 requires exactly 28 allocation slots")
        self.max_slots = max_slots

    def forward(self, candidates: RelationCandidates) -> AllocationPlan:
        return self.allocate(candidates)

    def allocate(self, candidates: RelationCandidates) -> AllocationPlan:
        candidates.validate()
        batch_size, source_count, _ = candidates.entity_features.shape
        device = candidates.entity_features.device
        dtype = candidates.entity_features.dtype

        weights = torch.zeros(
            batch_size,
            self.max_slots,
            source_count,
            dtype=dtype,
            device=device,
        )
        selected_source_ids = torch.full(
            (batch_size, self.max_slots),
            -1,
            dtype=torch.long,
            device=device,
        )
        overflow_mask = torch.zeros(
            batch_size,
            source_count,
            dtype=torch.bool,
            device=device,
        )

        ranking_inputs = (
            candidates.valid_mask.detach().cpu().tolist(),
            candidates.unary_scores.detach().cpu().tolist(),
            candidates.anatomy_ids.detach().cpu().tolist(),
            candidates.temporal_ids.detach().cpu().tolist(),
            candidates.source_ids.detach().cpu().tolist(),
        )
        for batch_index in range(batch_size):
            order = _coverage_aware_order(
                *(values[batch_index] for values in ranking_inputs)
            )
            if len(order) <= self.max_slots:
                individual_sources = order
                overflow_sources: list[int] = []
            else:
                individual_sources = order[: self.max_slots - 1]
                overflow_sources = order[self.max_slots - 1 :]

            for slot_index, source_index in enumerate(individual_sources):
                weights[batch_index, slot_index, source_index] = 1
                selected_source_ids[batch_index, slot_index] = candidates.source_ids[
                    batch_index, source_index
                ]

            if overflow_sources:
                weights[batch_index, -1, overflow_sources] = 1
                selected_source_ids[batch_index, -1] = -2
                overflow_mask[batch_index, overflow_sources] = True

        slot_mass = weights.sum(dim=-1)
        plan = AllocationPlan(
            weights=weights,
            slot_valid=slot_mass > 0,
            slot_mass=slot_mass,
            source_valid=candidates.valid_mask.clone(),
            selected_source_ids=selected_source_ids,
            overflow_mask=overflow_mask,
        )
        plan.validate(slot_count=self.max_slots)
        return plan


def _coverage_aware_order(
    valid_mask: list[bool],
    unary_scores: list[float],
    anatomy_ids: list[int],
    temporal_ids: list[int],
    source_ids: list[int],
) -> list[int]:
    valid_indices = [index for index, valid in enumerate(valid_mask) if valid]
    valid_source_ids = [int(source_ids[index]) for index in valid_indices]
    if any(source_id < 0 for source_id in valid_source_ids):
        raise ValueError("valid source IDs must be nonnegative")
    if len(valid_source_ids) != len(set(valid_source_ids)):
        raise ValueError("valid source IDs must be unique within each batch item")

    def source_key(index: int) -> tuple[float, int, int, int]:
        return (
            -float(unary_scores[index]),
            int(anatomy_ids[index]),
            int(temporal_ids[index]),
            int(source_ids[index]),
        )

    anatomy_groups: dict[int, list[int]] = defaultdict(list)
    for index in valid_indices:
        anatomy_groups[int(anatomy_ids[index])].append(index)

    representatives = [
        min(indices, key=source_key) for indices in anatomy_groups.values()
    ]
    representatives.sort(
        key=lambda index: (-float(unary_scores[index]), int(anatomy_ids[index]))
    )
    representative_set = set(representatives)
    remaining = sorted(
        (index for index in valid_indices if index not in representative_set),
        key=source_key,
    )
    return representatives + remaining


def apply_allocation(
    features: Tensor,
    plan: AllocationPlan,
    source_mass: Tensor | None = None,
) -> tuple[Tensor, Tensor]:
    """Return mass-normalized slot features and their unnormalized mass.

    By default every valid source has unit mass.  ``source_mass`` is available
    for raw per-source features that require an explicit weighted mean.  The
    relation features in ``RelationCandidates`` are already transport-mass
    weighted and should use the default.
    """

    plan.validate(slot_count=SLOT_COUNT)
    if features.ndim != 3:
        raise ValueError("features must have shape [B, N, F]")
    batch_size, source_count, _ = features.shape
    if tuple(plan.weights.shape) != (batch_size, SLOT_COUNT, source_count):
        raise ValueError(
            "features and allocation plan must have matching batch/source dimensions"
        )
    if not features.is_floating_point():
        raise TypeError("features must be floating point")
    if not bool(torch.isfinite(features).all()):
        raise ValueError("features contain non-finite values")
    if plan.weights.device != features.device:
        raise ValueError("features and allocation plan must be on the same device")

    if source_mass is None:
        mass = plan.source_valid.to(dtype=features.dtype)
    else:
        if tuple(source_mass.shape) != (batch_size, source_count):
            raise ValueError("source_mass must have shape [B, N]")
        if source_mass.device != features.device:
            raise ValueError("source_mass and features must be on the same device")
        if not source_mass.is_floating_point():
            raise TypeError("source_mass must be floating point")
        if not bool(torch.isfinite(source_mass).all()):
            raise ValueError("source_mass contains non-finite values")
        if bool((source_mass < 0).any()):
            raise ValueError("source_mass must be nonnegative")
        mass = source_mass.to(dtype=features.dtype)

    weighted_mass = plan.weights.to(dtype=features.dtype) * mass[:, None, :]
    slot_mass = weighted_mass.sum(dim=-1)
    numerator = torch.einsum("bsn,bnf->bsf", weighted_mass, features)
    positive_mass = slot_mass > 0
    denominator = torch.where(positive_mass, slot_mass, torch.ones_like(slot_mass))
    slot_features = numerator / denominator.unsqueeze(-1)
    slot_features = slot_features.masked_fill(~positive_mass.unsqueeze(-1), 0)
    return slot_features, slot_mass
