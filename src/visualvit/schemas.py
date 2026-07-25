from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

import torch
from torch import Tensor


def _to_device(value: Any, device: torch.device | str) -> Any:
    if isinstance(value, Tensor):
        return value.to(device)
    if isinstance(value, dict):
        return {key: _to_device(item, device) for key, item in value.items()}
    if isinstance(value, list):
        return [_to_device(item, device) for item in value]
    if isinstance(value, tuple):
        return tuple(_to_device(item, device) for item in value)
    return value


def _require_finite(name: str, value: Tensor) -> None:
    if not bool(torch.isfinite(value).all()):
        raise ValueError(f"{name} contains non-finite values")


def _require_long(name: str, value: Tensor) -> None:
    if value.dtype is not torch.long:
        raise TypeError(f"{name} must be torch.long")


@dataclass
class RegionBatch:
    """Batched prior/current region features with source identity metadata."""

    prior_features: Tensor
    current_features: Tensor
    prior_valid: Tensor
    current_valid: Tensor
    prior_anatomy: Tensor
    current_anatomy: Tensor
    prior_entity_ids: Tensor
    current_entity_ids: Tensor
    prior_boxes: Tensor | None = None
    current_boxes: Tensor | None = None
    prior_confidence: Tensor | None = None
    current_confidence: Tensor | None = None
    prior_source_ids: Tensor | None = None
    current_source_ids: Tensor | None = None
    time_delta_days: Tensor | None = None

    def validate(self) -> None:
        if self.prior_features.ndim != 3 or self.current_features.ndim != 3:
            raise ValueError("features must have shape [B, R, D]")
        b, rp, d = self.prior_features.shape
        bc, rc, dc = self.current_features.shape
        if b != bc or d != dc:
            raise ValueError("prior/current batch and feature dimensions must match")
        expected_prior = (b, rp)
        expected_current = (b, rc)
        for name, value, shape in (
            ("prior_valid", self.prior_valid, expected_prior),
            ("current_valid", self.current_valid, expected_current),
            ("prior_anatomy", self.prior_anatomy, expected_prior),
            ("current_anatomy", self.current_anatomy, expected_current),
            ("prior_entity_ids", self.prior_entity_ids, expected_prior),
            ("current_entity_ids", self.current_entity_ids, expected_current),
        ):
            if tuple(value.shape) != shape:
                raise ValueError(
                    f"{name} must have shape {shape}, got {tuple(value.shape)}"
                )
        if (
            self.prior_valid.dtype is not torch.bool
            or self.current_valid.dtype is not torch.bool
        ):
            raise TypeError("valid masks must be bool")
        _require_finite("prior_features", self.prior_features)
        _require_finite("current_features", self.current_features)

        optional_shapes = (
            ("prior_boxes", self.prior_boxes, (b, rp, 4)),
            ("current_boxes", self.current_boxes, (b, rc, 4)),
            ("prior_confidence", self.prior_confidence, expected_prior),
            ("current_confidence", self.current_confidence, expected_current),
            ("prior_source_ids", self.prior_source_ids, expected_prior),
            ("current_source_ids", self.current_source_ids, expected_current),
            ("time_delta_days", self.time_delta_days, (b,)),
        )
        for name, value, shape in optional_shapes:
            if value is not None and tuple(value.shape) != shape:
                raise ValueError(
                    f"{name} must have shape {shape}, got {tuple(value.shape)}"
                )
        for name in (
            "prior_boxes",
            "current_boxes",
            "prior_confidence",
            "current_confidence",
            "time_delta_days",
        ):
            value = getattr(self, name)
            if value is not None:
                _require_finite(name, value)
        for name in ("prior_source_ids", "current_source_ids"):
            value = getattr(self, name)
            if value is not None:
                _require_long(name, value)

    def to(self, device: torch.device | str) -> "RegionBatch":
        return RegionBatch(
            prior_features=self.prior_features.to(device),
            current_features=self.current_features.to(device),
            prior_valid=self.prior_valid.to(device),
            current_valid=self.current_valid.to(device),
            prior_anatomy=self.prior_anatomy.to(device),
            current_anatomy=self.current_anatomy.to(device),
            prior_entity_ids=self.prior_entity_ids.to(device),
            current_entity_ids=self.current_entity_ids.to(device),
            prior_boxes=_to_device(self.prior_boxes, device),
            current_boxes=_to_device(self.current_boxes, device),
            prior_confidence=_to_device(self.prior_confidence, device),
            current_confidence=_to_device(self.current_confidence, device),
            prior_source_ids=_to_device(self.prior_source_ids, device),
            current_source_ids=_to_device(self.current_source_ids, device),
            time_delta_days=_to_device(self.time_delta_days, device),
        )


@dataclass
class MatchPlan:
    """Partial assignment with final row/column reserved for dustbins."""

    transport: Tensor
    mode: str
    edge_logits: Tensor | None = None
    prior_null_logits: Tensor | None = None
    current_null_logits: Tensor | None = None
    diagnostics: dict[str, Tensor | float | int | str] | None = None

    def validate(self, regions: RegionBatch, atol: float = 1e-6) -> None:
        regions.validate()
        b, rp, _ = regions.prior_features.shape
        rc = regions.current_features.shape[1]
        if tuple(self.transport.shape) != (b, rp + 1, rc + 1):
            raise ValueError(
                f"transport must have shape {(b, rp + 1, rc + 1)}, "
                f"got {tuple(self.transport.shape)}"
            )
        _require_finite("transport", self.transport)
        if bool((self.transport < -atol).any()):
            raise ValueError("transport contains negative mass")
        if bool((self.transport[:, rp, rc] != 0).any()):
            raise ValueError("dustbin-to-dustbin mass must be exactly zero")

        real = self.transport[:, :rp, :rc]
        death = self.transport[:, :rp, rc]
        birth = self.transport[:, rp, :rc]
        prior_mass = regions.prior_valid.to(real.dtype)
        current_mass = regions.current_valid.to(real.dtype)
        expected_death = prior_mass - real.sum(dim=-1)
        expected_birth = current_mass - real.sum(dim=-2)
        if bool((expected_death < -atol).any()):
            raise ValueError("real transport exceeds prior capacity")
        if bool((expected_birth < -atol).any()):
            raise ValueError("real transport exceeds current capacity")
        if not torch.allclose(death, expected_death, atol=atol, rtol=0):
            raise ValueError("death mass does not equal prior residual")
        if not torch.allclose(birth, expected_birth, atol=atol, rtol=0):
            raise ValueError("birth mass does not equal current residual")

        optional_logits = (
            ("edge_logits", self.edge_logits, (b, rp, rc)),
            ("prior_null_logits", self.prior_null_logits, (b, rp)),
            ("current_null_logits", self.current_null_logits, (b, rc)),
        )
        for name, value, shape in optional_logits:
            if value is None:
                continue
            if tuple(value.shape) != shape:
                raise ValueError(
                    f"{name} must have shape {shape}, got {tuple(value.shape)}"
                )
            _require_finite(name, value)
        if self.diagnostics is not None:
            if not isinstance(self.diagnostics, dict):
                raise TypeError("diagnostics must be a dict or None")
            for key, value in self.diagnostics.items():
                if not isinstance(key, str):
                    raise TypeError("diagnostic keys must be strings")
                if isinstance(value, Tensor):
                    _require_finite(f"diagnostics[{key!r}]", value)
                elif isinstance(value, float):
                    if not math.isfinite(value):
                        raise ValueError(f"diagnostics[{key!r}] must be finite")
                elif not isinstance(value, (int, str)):
                    raise TypeError(
                        "diagnostic values must be tensors, floats, ints, or strings"
                    )

    def validate_hard(self, regions: RegionBatch, atol: float = 1e-6) -> None:
        """Additionally require a discrete 0/1 assignment."""

        self.validate(regions, atol=atol)
        near_zero = torch.isclose(
            self.transport,
            torch.zeros_like(self.transport),
            atol=atol,
            rtol=0,
        )
        near_one = torch.isclose(
            self.transport,
            torch.ones_like(self.transport),
            atol=atol,
            rtol=0,
        )
        if not bool((near_zero | near_one).all()):
            raise ValueError(
                "fractional transport cannot use the hard relation tokenizer; "
                "a dedicated soft allocator is required"
            )

    def to(self, device: torch.device | str) -> "MatchPlan":
        return MatchPlan(
            transport=self.transport.to(device),
            mode=self.mode,
            edge_logits=_to_device(self.edge_logits, device),
            prior_null_logits=_to_device(self.prior_null_logits, device),
            current_null_logits=_to_device(self.current_null_logits, device),
            diagnostics=_to_device(self.diagnostics, device),
        )


@dataclass
class RelationCandidates:
    """Assignment-independent source universe and its soft relation features."""

    entity_features: Tensor
    relation_features: Tensor
    valid_mask: Tensor
    unary_scores: Tensor
    anatomy_ids: Tensor
    temporal_ids: Tensor
    source_ids: Tensor
    relation_mass: Tensor

    def validate(self, atol: float = 1e-6) -> None:
        if self.entity_features.ndim != 3:
            raise ValueError("entity_features must have shape [B, N, F]")
        b, n, f = self.entity_features.shape
        if tuple(self.relation_features.shape) != (b, n, f):
            raise ValueError(
                f"relation_features must have shape {(b, n, f)}, "
                f"got {tuple(self.relation_features.shape)}"
            )
        for name, value in (
            ("valid_mask", self.valid_mask),
            ("unary_scores", self.unary_scores),
            ("anatomy_ids", self.anatomy_ids),
            ("temporal_ids", self.temporal_ids),
            ("source_ids", self.source_ids),
            ("relation_mass", self.relation_mass),
        ):
            if tuple(value.shape) != (b, n):
                raise ValueError(
                    f"{name} must have shape {(b, n)}, got {tuple(value.shape)}"
                )
        if self.valid_mask.dtype is not torch.bool:
            raise TypeError("valid_mask must be bool")
        for name in ("anatomy_ids", "temporal_ids", "source_ids"):
            _require_long(name, getattr(self, name))
        _require_finite("entity_features", self.entity_features)
        _require_finite("relation_features", self.relation_features)
        _require_finite("unary_scores", self.unary_scores)
        _require_finite("relation_mass", self.relation_mass)
        if bool((self.relation_mass < -atol).any()):
            raise ValueError("relation_mass contains negative values")
        invalid_mass = self.relation_mass.masked_select(~self.valid_mask)
        if invalid_mass.numel() and not torch.allclose(
            invalid_mass,
            torch.zeros_like(invalid_mass),
            atol=atol,
            rtol=0,
        ):
            raise ValueError("invalid relation candidates must have zero mass")
        if bool(((self.temporal_ids != 0) & (self.temporal_ids != 1)).any()):
            raise ValueError("temporal_ids must contain only 0 (prior) or 1 (current)")

    def to(self, device: torch.device | str) -> "RelationCandidates":
        return RelationCandidates(
            entity_features=self.entity_features.to(device),
            relation_features=self.relation_features.to(device),
            valid_mask=self.valid_mask.to(device),
            unary_scores=self.unary_scores.to(device),
            anatomy_ids=self.anatomy_ids.to(device),
            temporal_ids=self.temporal_ids.to(device),
            source_ids=self.source_ids.to(device),
            relation_mass=self.relation_mass.to(device),
        )


@dataclass
class AllocationPlan:
    """Deterministic mapping from source candidates into fixed entity/relation slots."""

    weights: Tensor
    slot_valid: Tensor
    slot_mass: Tensor
    source_valid: Tensor
    selected_source_ids: Tensor
    overflow_mask: Tensor

    def validate(self, slot_count: int = 28, atol: float = 1e-6) -> None:
        if self.weights.ndim != 3:
            raise ValueError("weights must have shape [B, S, N]")
        b, slots, n = self.weights.shape
        if slots != slot_count:
            raise ValueError(f"allocation must contain {slot_count} slots, got {slots}")
        for name, value, shape in (
            ("slot_valid", self.slot_valid, (b, slots)),
            ("slot_mass", self.slot_mass, (b, slots)),
            ("source_valid", self.source_valid, (b, n)),
            ("selected_source_ids", self.selected_source_ids, (b, slots)),
            ("overflow_mask", self.overflow_mask, (b, n)),
        ):
            if tuple(value.shape) != shape:
                raise ValueError(
                    f"{name} must have shape {shape}, got {tuple(value.shape)}"
                )
        if self.slot_valid.dtype is not torch.bool:
            raise TypeError("slot_valid must be bool")
        if self.source_valid.dtype is not torch.bool:
            raise TypeError("source_valid must be bool")
        if self.overflow_mask.dtype is not torch.bool:
            raise TypeError("overflow_mask must be bool")
        _require_long("selected_source_ids", self.selected_source_ids)
        _require_finite("weights", self.weights)
        _require_finite("slot_mass", self.slot_mass)
        if bool((self.weights < -atol).any()):
            raise ValueError("weights contain negative values")
        if bool((self.slot_mass < -atol).any()):
            raise ValueError("slot_mass contains negative values")

        near_zero = torch.isclose(
            self.weights, torch.zeros_like(self.weights), atol=atol, rtol=0
        )
        near_one = torch.isclose(
            self.weights, torch.ones_like(self.weights), atol=atol, rtol=0
        )
        if not bool((near_zero | near_one).all()):
            raise ValueError("each source must map wholly to one deterministic slot")

        source_mass = self.weights.sum(dim=1)
        expected_source_mass = self.source_valid.to(source_mass.dtype)
        if not torch.allclose(source_mass, expected_source_mass, atol=atol, rtol=0):
            raise ValueError(
                "valid sources must have column mass one and invalid sources zero"
            )
        actual_slot_mass = self.weights.sum(dim=-1)
        if not torch.allclose(
            self.slot_mass.to(actual_slot_mass.dtype),
            actual_slot_mass,
            atol=atol,
            rtol=0,
        ):
            raise ValueError("slot_mass must equal allocation row mass")
        if not torch.equal(self.slot_valid, actual_slot_mass > atol):
            raise ValueError("slot_valid must identify exactly the non-empty slots")
        if bool((self.overflow_mask & ~self.source_valid).any()):
            raise ValueError("overflow_mask cannot select invalid sources")

        empty_slots = ~self.slot_valid
        if bool((self.selected_source_ids.masked_select(empty_slots) != -1).any()):
            raise ValueError("empty slots must use selected_source_ids=-1")
        if slots > 1:
            prior_slots = self.selected_source_ids[:, :-1]
            prior_valid_slots = self.slot_valid[:, :-1]
            if bool((prior_slots.masked_select(prior_valid_slots) < 0).any()):
                raise ValueError(
                    "non-empty individual slots require a non-negative source ID"
                )
            if bool((actual_slot_mass[:, :-1] > 1 + atol).any()):
                raise ValueError("only the final slot may aggregate multiple sources")

        source_count = self.source_valid.sum(dim=-1)
        needs_overflow = source_count > slot_count
        has_overflow = self.overflow_mask.any(dim=-1)
        if not torch.equal(needs_overflow, has_overflow):
            raise ValueError(
                "overflow is required exactly when valid sources exceed slot count"
            )
        last_selected = self.selected_source_ids[:, -1]
        if bool((last_selected.masked_select(has_overflow) != -2).any()):
            raise ValueError("the overflow slot must use selected_source_ids=-2")
        ordinary_last = self.slot_valid[:, -1] & ~has_overflow
        if bool((last_selected.masked_select(ordinary_last) < 0).any()):
            raise ValueError(
                "a non-overflow final slot requires a non-negative source ID"
            )
        if bool(
            (actual_slot_mass[:, -1].masked_select(~has_overflow) > 1 + atol).any()
        ):
            raise ValueError("a non-overflow final slot may contain at most one source")
        last_members = self.weights[:, -1, :] > atol
        if not torch.equal(
            last_members & has_overflow.unsqueeze(-1), self.overflow_mask
        ):
            raise ValueError(
                "overflow_mask must identify sources assigned to the final slot"
            )

    def to(self, device: torch.device | str) -> "AllocationPlan":
        return AllocationPlan(
            weights=self.weights.to(device),
            slot_valid=self.slot_valid.to(device),
            slot_mass=self.slot_mass.to(device),
            source_valid=self.source_valid.to(device),
            selected_source_ids=self.selected_source_ids.to(device),
            overflow_mask=self.overflow_mask.to(device),
        )


@dataclass
class TokenBundle:
    """Fixed-budget relation tokens plus audit metadata."""

    tokens: Tensor
    token_types: Tensor
    valid_mask: Tensor
    assignment: Tensor
    anatomy_ids: Tensor | None = None
    temporal_ids: Tensor | None = None
    confidence: Tensor | None = None
    slot_mass: Tensor | None = None
    source_ids: Tensor | None = None

    def validate(self, token_budget: int = 64) -> None:
        if self.tokens.ndim != 3:
            raise ValueError("tokens must have shape [B, M, D]")
        b, m, _ = self.tokens.shape
        if m != token_budget:
            raise ValueError(f"token budget must be {token_budget}, got {m}")
        if tuple(self.token_types.shape) not in ((m,), (b, m)):
            raise ValueError("token_types must have shape [M] or [B, M]")
        _require_long("token_types", self.token_types)
        if tuple(self.valid_mask.shape) != (b, m):
            raise ValueError("valid_mask must have shape [B, M]")
        if self.valid_mask.dtype is not torch.bool:
            raise TypeError("valid_mask must be bool")
        _require_finite("tokens", self.tokens)

        for name in (
            "anatomy_ids",
            "temporal_ids",
            "confidence",
            "slot_mass",
            "source_ids",
        ):
            value = getattr(self, name)
            if value is not None and tuple(value.shape) != (b, m):
                raise ValueError(
                    f"{name} must have shape {(b, m)}, got {tuple(value.shape)}"
                )
        for name in ("anatomy_ids", "temporal_ids", "source_ids"):
            value = getattr(self, name)
            if value is not None:
                _require_long(name, value)
        for name in ("confidence", "slot_mass"):
            value = getattr(self, name)
            if value is not None:
                _require_finite(name, value)

    def to(self, device: torch.device | str) -> "TokenBundle":
        return TokenBundle(
            tokens=self.tokens.to(device),
            token_types=self.token_types.to(device),
            valid_mask=self.valid_mask.to(device),
            assignment=self.assignment.to(device),
            anatomy_ids=_to_device(self.anatomy_ids, device),
            temporal_ids=_to_device(self.temporal_ids, device),
            confidence=_to_device(self.confidence, device),
            slot_mass=_to_device(self.slot_mass, device),
            source_ids=_to_device(self.source_ids, device),
        )


@dataclass
class ProjectedTokenBundle:
    """Projected fixed-budget tokens ready for exact placeholder injection."""

    embeddings: Tensor
    token_types: Tensor
    valid_mask: Tensor
    attention_mask: Tensor
    position_ids: Tensor
    audit: dict[str, Any]

    def validate(self, token_budget: int = 64) -> None:
        if self.embeddings.ndim != 3:
            raise ValueError("embeddings must have shape [B, M, H_lm]")
        b, m, _ = self.embeddings.shape
        if m != token_budget:
            raise ValueError(f"token budget must be {token_budget}, got {m}")
        if tuple(self.token_types.shape) != (m,):
            raise ValueError("token_types must have shape [M]")
        _require_long("token_types", self.token_types)
        if tuple(self.valid_mask.shape) != (b, m):
            raise ValueError("valid_mask must have shape [B, M]")
        if self.valid_mask.dtype is not torch.bool:
            raise TypeError("valid_mask must be bool")
        if tuple(self.attention_mask.shape) != (b, m):
            raise ValueError("attention_mask must have shape [B, M]")
        if not bool((self.attention_mask == 1).all()):
            raise ValueError(
                "attention_mask must be one at every physical token position"
            )
        if tuple(self.position_ids.shape) != (3, b, m):
            raise ValueError("position_ids must have shape [3, B, M]")
        _require_long("position_ids", self.position_ids)
        if not (
            torch.equal(self.position_ids[0], self.position_ids[1])
            and torch.equal(self.position_ids[0], self.position_ids[2])
        ):
            raise ValueError(
                "the three position-id axes must be equal for text-like tokens"
            )
        _require_finite("embeddings", self.embeddings)
        if not isinstance(self.audit, dict):
            raise TypeError("audit must be a dict")
        if any(not isinstance(key, str) for key in self.audit):
            raise TypeError("audit keys must be strings")

    def to(self, device: torch.device | str) -> "ProjectedTokenBundle":
        return ProjectedTokenBundle(
            embeddings=self.embeddings.to(device),
            token_types=self.token_types.to(device),
            valid_mask=self.valid_mask.to(device),
            attention_mask=self.attention_mask.to(device),
            position_ids=self.position_ids.to(device),
            audit=_to_device(self.audit, device),
        )
