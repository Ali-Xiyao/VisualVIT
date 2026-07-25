from __future__ import annotations

import torch
from torch import Tensor

from .schemas import (
    AllocationPlan,
    MatchPlan,
    RegionBatch,
    RelationCandidates,
    TokenBundle,
)

GLOBAL_TOKENS = 4
ENTITY_TOKENS = 28
RELATION_TOKENS = 28
RESERVED_TOKENS = 4
TOKEN_BUDGET = GLOBAL_TOKENS + ENTITY_TOKENS + RELATION_TOKENS + RESERVED_TOKENS

TYPE_GLOBAL = 0
TYPE_ENTITY = 1
TYPE_RELATION = 2
TYPE_RESERVED = 3


def _relation_vector(prior: Tensor, current: Tensor, relation_type: int) -> Tensor:
    one_hot = torch.zeros(3, dtype=prior.dtype, device=prior.device)
    one_hot[relation_type] = 1.0
    return torch.cat((prior, current, current - prior, prior * current, one_hot))


def build_relation_slots(
    regions: RegionBatch,
    plan: MatchPlan,
    max_slots: int = RELATION_TOKENS,
) -> tuple[Tensor, Tensor, list[list[tuple[str, int, int]]]]:
    """Build ordered prior relations followed by predicted birth relations."""

    plan.validate_hard(regions)
    b, rp, d = regions.prior_features.shape
    rc = regions.current_features.shape[1]
    relation_dim = 4 * d + 3
    slots = torch.zeros(
        b,
        max_slots,
        relation_dim,
        dtype=regions.prior_features.dtype,
        device=regions.prior_features.device,
    )
    valid = torch.zeros(b, max_slots, dtype=torch.bool, device=slots.device)
    records: list[list[tuple[str, int, int]]] = []

    for batch_index in range(b):
        batch_records: list[tuple[str, int, int]] = []
        cursor = 0
        for prior_index in range(rp):
            if not bool(regions.prior_valid[batch_index, prior_index]):
                continue
            if cursor >= max_slots:
                raise ValueError("relation token budget exceeded by prior relations")
            real_hits = torch.nonzero(
                plan.transport[batch_index, prior_index, :rc] > 0.5,
                as_tuple=False,
            ).flatten()
            prior = regions.prior_features[batch_index, prior_index]
            if len(real_hits) == 1:
                current_index = int(real_hits.item())
                current = regions.current_features[batch_index, current_index]
                relation_type = 0
                batch_records.append(("persistent", prior_index, current_index))
            else:
                current_index = -1
                current = torch.zeros_like(prior)
                relation_type = 1
                batch_records.append(("death", prior_index, -1))
            slots[batch_index, cursor] = _relation_vector(prior, current, relation_type)
            valid[batch_index, cursor] = True
            cursor += 1

        birth_hits = torch.nonzero(
            plan.transport[batch_index, rp, :rc] > 0.5,
            as_tuple=False,
        ).flatten()
        for birth_hit in birth_hits:
            if cursor >= max_slots:
                raise ValueError("relation token budget exceeded by birth relations")
            current_index = int(birth_hit.item())
            current = regions.current_features[batch_index, current_index]
            slots[batch_index, cursor] = _relation_vector(
                torch.zeros_like(current), current, 2
            )
            valid[batch_index, cursor] = True
            batch_records.append(("birth", -1, current_index))
            cursor += 1
        records.append(batch_records)

    return slots, valid, records


def _expand_feature(feature: Tensor, output_dim: int) -> Tensor:
    output = torch.zeros(
        *feature.shape[:-1],
        output_dim,
        dtype=feature.dtype,
        device=feature.device,
    )
    output[..., : feature.shape[-1]] = feature
    return output


def assemble_fixed_budget_tokens(
    regions: RegionBatch,
    plan: MatchPlan,
) -> TokenBundle:
    """Assemble exact 4/28/28/4 fixed-budget tokens."""

    regions.validate()
    plan.validate(regions)
    b, rp, d = regions.prior_features.shape
    relation_slots, relation_valid, _ = build_relation_slots(regions, plan)
    token_dim = relation_slots.shape[-1]

    tokens = torch.zeros(
        b,
        TOKEN_BUDGET,
        token_dim,
        dtype=regions.prior_features.dtype,
        device=regions.prior_features.device,
    )
    valid = torch.zeros(b, TOKEN_BUDGET, dtype=torch.bool, device=tokens.device)

    prior_weights = regions.prior_valid.to(tokens.dtype).unsqueeze(-1)
    current_weights = regions.current_valid.to(tokens.dtype).unsqueeze(-1)
    prior_mean = (regions.prior_features * prior_weights).sum(
        dim=1
    ) / prior_weights.sum(dim=1).clamp_min(1.0)
    current_mean = (regions.current_features * current_weights).sum(
        dim=1
    ) / current_weights.sum(dim=1).clamp_min(1.0)
    globals_raw = torch.stack(
        (
            prior_mean,
            current_mean,
            current_mean - prior_mean,
            current_mean * prior_mean,
        ),
        dim=1,
    )
    tokens[:, :GLOBAL_TOKENS] = _expand_feature(globals_raw, token_dim)
    valid[:, :GLOBAL_TOKENS] = True

    entity_start = GLOBAL_TOKENS
    entity_features = torch.cat(
        (regions.prior_features, regions.current_features), dim=1
    )
    entity_valid = torch.cat((regions.prior_valid, regions.current_valid), dim=1)
    if entity_features.shape[1] > ENTITY_TOKENS:
        raise ValueError("entity token budget exceeded")
    entity_end = entity_start + entity_features.shape[1]
    tokens[:, entity_start:entity_end] = _expand_feature(entity_features, token_dim)
    valid[:, entity_start:entity_end] = entity_valid

    relation_start = GLOBAL_TOKENS + ENTITY_TOKENS
    tokens[:, relation_start : relation_start + RELATION_TOKENS] = relation_slots
    valid[:, relation_start : relation_start + RELATION_TOKENS] = relation_valid

    token_types = torch.tensor(
        [TYPE_GLOBAL] * GLOBAL_TOKENS
        + [TYPE_ENTITY] * ENTITY_TOKENS
        + [TYPE_RELATION] * RELATION_TOKENS
        + [TYPE_RESERVED] * RESERVED_TOKENS,
        dtype=torch.long,
        device=tokens.device,
    )
    bundle = TokenBundle(
        tokens=tokens,
        token_types=token_types,
        valid_mask=valid,
        assignment=plan.transport.clone(),
    )
    bundle.validate()
    return bundle


def _optional_observation_tensor(
    value: Tensor | None,
    *,
    valid: Tensor,
    default: float,
    dtype: torch.dtype,
) -> Tensor:
    if value is None:
        result = torch.full(
            valid.shape,
            default,
            dtype=dtype,
            device=valid.device,
        )
    else:
        result = value.to(device=valid.device, dtype=dtype)
    return result * valid.to(dtype)


def _candidate_source_ids(regions: RegionBatch) -> Tensor:
    """Return stable observation IDs without consulting gold entity IDs."""

    b, rp = regions.prior_valid.shape
    rc = regions.current_valid.shape[1]
    if regions.prior_source_ids is None:
        prior = torch.arange(rp, device=regions.prior_valid.device).expand(b, -1)
    else:
        prior = regions.prior_source_ids.to(device=regions.prior_valid.device)
    if regions.current_source_ids is None:
        current = (torch.arange(rc, device=regions.current_valid.device) + rp).expand(
            b, -1
        )
    else:
        current = regions.current_source_ids.to(device=regions.current_valid.device)
    return torch.cat((prior.long(), current.long()), dim=1)


def build_soft_relation_candidates(
    regions: RegionBatch,
    plan: MatchPlan,
) -> RelationCandidates:
    """Build the assignment-independent source universe and soft relations.

    Gold ``*_entity_ids`` are deliberately not read here.  Persistent, death,
    and birth effects enter only through ``plan.transport``.
    """

    plan.validate(regions)
    b, rp, d = regions.prior_features.shape
    rc = regions.current_features.shape[1]
    relation_dim = 4 * d + 3
    real = plan.transport[:, :rp, :rc]
    death = plan.transport[:, :rp, rc]
    birth = plan.transport[:, rp, :rc]

    prior_grid = regions.prior_features[:, :, None, :].expand(-1, -1, rc, -1)
    current_grid = regions.current_features[:, None, :, :].expand(-1, rp, -1, -1)
    relation_type = torch.zeros(
        b,
        rp,
        rc,
        3,
        dtype=regions.prior_features.dtype,
        device=regions.prior_features.device,
    )
    if rc > 0 and rp > 0:
        relation_type[..., 0] = 1.0
    persistent_vectors = torch.cat(
        (
            prior_grid,
            current_grid,
            current_grid - prior_grid,
            prior_grid * current_grid,
            relation_type,
        ),
        dim=-1,
    )
    prior_relations = (real[..., None] * persistent_vectors).sum(dim=2)

    zero_prior = torch.zeros_like(regions.prior_features)
    death_types = torch.zeros(
        b,
        rp,
        3,
        dtype=regions.prior_features.dtype,
        device=regions.prior_features.device,
    )
    if rp > 0:
        death_types[..., 1] = 1.0
    death_vectors = torch.cat(
        (
            regions.prior_features,
            zero_prior,
            -regions.prior_features,
            zero_prior,
            death_types,
        ),
        dim=-1,
    )
    prior_relations = prior_relations + death[..., None] * death_vectors

    zero_current = torch.zeros_like(regions.current_features)
    birth_types = torch.zeros(
        b,
        rc,
        3,
        dtype=regions.current_features.dtype,
        device=regions.current_features.device,
    )
    if rc > 0:
        birth_types[..., 2] = 1.0
    birth_vectors = torch.cat(
        (
            zero_current,
            regions.current_features,
            regions.current_features,
            zero_current,
            birth_types,
        ),
        dim=-1,
    )
    current_relations = birth[..., None] * birth_vectors

    entity_features = torch.cat(
        (
            _expand_feature(regions.prior_features, relation_dim),
            _expand_feature(regions.current_features, relation_dim),
        ),
        dim=1,
    )
    relation_features = torch.cat((prior_relations, current_relations), dim=1)
    valid_mask = torch.cat((regions.prior_valid, regions.current_valid), dim=1)
    valid_float = valid_mask.to(entity_features.dtype)[..., None]
    entity_features = entity_features * valid_float
    relation_features = relation_features * valid_float

    prior_confidence = _optional_observation_tensor(
        regions.prior_confidence,
        valid=regions.prior_valid,
        default=1.0,
        dtype=entity_features.dtype,
    )
    current_confidence = _optional_observation_tensor(
        regions.current_confidence,
        valid=regions.current_valid,
        default=1.0,
        dtype=entity_features.dtype,
    )
    unary_scores = torch.cat((prior_confidence, current_confidence), dim=1)
    anatomy_ids = torch.cat((regions.prior_anatomy, regions.current_anatomy), dim=1)
    temporal_ids = torch.cat(
        (
            torch.zeros_like(regions.prior_anatomy),
            torch.ones_like(regions.current_anatomy),
        ),
        dim=1,
    )
    source_ids = _candidate_source_ids(regions)
    relation_mass = torch.cat(
        (real.sum(dim=-1) + death, birth),
        dim=1,
    ) * valid_mask.to(entity_features.dtype)

    candidates = RelationCandidates(
        entity_features=entity_features,
        relation_features=relation_features,
        valid_mask=valid_mask,
        unary_scores=unary_scores,
        anatomy_ids=anatomy_ids,
        temporal_ids=temporal_ids,
        source_ids=source_ids,
        relation_mass=relation_mass,
    )
    candidates.validate()
    return candidates


def _aggregate_slot_metadata(
    values: Tensor,
    allocation: AllocationPlan,
    *,
    empty_value: int = -1,
    mixed_value: int = -2,
) -> Tensor:
    """Preserve a discrete value only when every source in a slot agrees."""

    b, slots, _ = allocation.weights.shape
    output = torch.full(
        (b, slots),
        empty_value,
        dtype=torch.long,
        device=allocation.weights.device,
    )
    for batch_index in range(b):
        for slot_index in range(slots):
            hits = allocation.weights[batch_index, slot_index] > 0
            if not bool(hits.any()):
                continue
            unique = torch.unique(values[batch_index, hits])
            output[batch_index, slot_index] = (
                unique[0] if unique.numel() == 1 else mixed_value
            )
    return output


def assemble_capes_ci_tokens(
    regions: RegionBatch,
    plan: MatchPlan,
    allocation: AllocationPlan,
) -> TokenBundle:
    """Assemble the CAPES-CI soft/null 4/28/28/4 interface."""

    candidates = build_soft_relation_candidates(regions, plan)
    allocation.validate(slot_count=ENTITY_TOKENS)
    if allocation.weights.shape[0] != candidates.entity_features.shape[0]:
        raise ValueError("allocation batch does not match candidates")
    if allocation.weights.shape[2] != candidates.entity_features.shape[1]:
        raise ValueError("allocation source count does not match candidates")
    if not torch.equal(allocation.source_valid, candidates.valid_mask):
        raise ValueError("allocation source_valid does not match candidates")

    weights = allocation.weights.to(candidates.entity_features.dtype)
    slot_mass = allocation.slot_mass.to(candidates.entity_features.dtype)
    denominator = slot_mass[..., None].clamp_min(1.0)
    entity_slots = (
        torch.einsum("bsn,bnf->bsf", weights, candidates.entity_features) / denominator
    )
    relation_slots = (
        torch.einsum("bsn,bnf->bsf", weights, candidates.relation_features)
        / denominator
    )

    b, _, token_dim = entity_slots.shape
    tokens = torch.zeros(
        b,
        TOKEN_BUDGET,
        token_dim,
        dtype=entity_slots.dtype,
        device=entity_slots.device,
    )
    valid = torch.zeros(b, TOKEN_BUDGET, dtype=torch.bool, device=tokens.device)

    prior_weights = regions.prior_valid.to(tokens.dtype).unsqueeze(-1)
    current_weights = regions.current_valid.to(tokens.dtype).unsqueeze(-1)
    prior_mean = (regions.prior_features * prior_weights).sum(
        dim=1
    ) / prior_weights.sum(dim=1).clamp_min(1.0)
    current_mean = (regions.current_features * current_weights).sum(
        dim=1
    ) / current_weights.sum(dim=1).clamp_min(1.0)
    globals_raw = torch.stack(
        (
            prior_mean,
            current_mean,
            current_mean - prior_mean,
            current_mean * prior_mean,
        ),
        dim=1,
    )
    tokens[:, :GLOBAL_TOKENS] = _expand_feature(globals_raw, token_dim)
    valid[:, :GLOBAL_TOKENS] = True

    entity_start = GLOBAL_TOKENS
    relation_start = entity_start + ENTITY_TOKENS
    tokens[:, entity_start:relation_start] = entity_slots
    tokens[:, relation_start : relation_start + RELATION_TOKENS] = relation_slots
    valid[:, entity_start:relation_start] = allocation.slot_valid
    valid[:, relation_start : relation_start + RELATION_TOKENS] = allocation.slot_valid

    token_types = torch.tensor(
        [TYPE_GLOBAL] * GLOBAL_TOKENS
        + [TYPE_ENTITY] * ENTITY_TOKENS
        + [TYPE_RELATION] * RELATION_TOKENS
        + [TYPE_RESERVED] * RESERVED_TOKENS,
        dtype=torch.long,
        device=tokens.device,
    )
    anatomy_slots = _aggregate_slot_metadata(candidates.anatomy_ids, allocation)
    temporal_slots = _aggregate_slot_metadata(candidates.temporal_ids, allocation)
    allocated_confidence = torch.einsum(
        "bsn,bn->bs", weights, candidates.unary_scores
    ) / slot_mass.clamp_min(1.0)
    allocated_relation_mass = torch.einsum(
        "bsn,bn->bs", weights, candidates.relation_mass
    ) / slot_mass.clamp_min(1.0)

    anatomy_ids = torch.full(
        (b, TOKEN_BUDGET), -1, dtype=torch.long, device=tokens.device
    )
    temporal_ids = torch.full_like(anatomy_ids, -1)
    confidence = torch.zeros(b, TOKEN_BUDGET, dtype=tokens.dtype, device=tokens.device)
    token_slot_mass = torch.zeros_like(confidence)
    source_ids = torch.full_like(anatomy_ids, -1)
    confidence[:, :GLOBAL_TOKENS] = 1.0
    token_slot_mass[:, :GLOBAL_TOKENS] = 1.0
    for start in (entity_start, relation_start):
        stop = start + ENTITY_TOKENS
        anatomy_ids[:, start:stop] = anatomy_slots
        temporal_ids[:, start:stop] = temporal_slots
        confidence[:, start:stop] = (
            allocated_confidence if start == entity_start else allocated_relation_mass
        )
        token_slot_mass[:, start:stop] = slot_mass
        source_ids[:, start:stop] = allocation.selected_source_ids

    bundle = TokenBundle(
        tokens=tokens,
        token_types=token_types,
        valid_mask=valid,
        assignment=plan.transport.clone(),
        anatomy_ids=anatomy_ids,
        temporal_ids=temporal_ids,
        confidence=confidence,
        slot_mass=token_slot_mass,
        source_ids=source_ids,
    )
    bundle.validate()
    return bundle
