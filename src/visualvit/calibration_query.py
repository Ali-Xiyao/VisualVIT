from __future__ import annotations

from dataclasses import dataclass, fields, replace
import hashlib
from itertools import permutations
import math
from typing import Any, Mapping, Sequence

import torch
from torch import Tensor
import torch.nn.functional as F

from .schemas import MatchPlan, ProjectedTokenBundle, RegionBatch


LABEL_STABLE = 0
LABEL_WORSE = 1
LABEL_IMPROVED = 2
LABEL_NEW = 3
LABEL_RESOLVED = 4
LABEL_COUNT = 5

QUERY_MARKER_CHANNEL = 0
STATE_CHANNEL = 1
STATE_VALUES = (-1.0, 0.0, 1.0)
REGISTERED_DERANGEMENT_SEEDS = (81_001, 81_002, 81_003)
QUERY_GROUP_SIZE = 6

GLOBAL_TOKENS = 4
ENTITY_TOKENS = 28
RELATION_TOKENS = 28
RESERVED_TOKENS = 4
TOKEN_BUDGET = GLOBAL_TOKENS + ENTITY_TOKENS + RELATION_TOKENS + RESERVED_TOKENS
QUERY_RELATION_SLOT = GLOBAL_TOKENS + ENTITY_TOKENS

FROZEN_SPLIT_CASES_PER_LABEL = {
    "train": 16,
    "inner_development": 8,
    "development": 24,
}
FROZEN_SPLIT_SEEDS = {
    "train": 63_401,
    "inner_development": 64_401,
    "development": 65_401,
}
FROZEN_R2_SPLIT_SEEDS = {
    "train": 73_401,
    "inner_development": 74_401,
    "development": 75_401,
}


class QueryAnchorQualificationError(ValueError):
    """Raised when a v2 structural gate must fail closed."""


def _require_long(name: str, value: Tensor) -> None:
    if value.dtype is not torch.long:
        raise TypeError(f"{name} must be torch.long")


def _require_bool(name: str, value: Tensor) -> None:
    if value.dtype is not torch.bool:
        raise TypeError(f"{name} must be torch.bool")


def _oracle_plan_from_hidden_ids(
    regions: RegionBatch,
    prior_gold_ids: Tensor,
    current_gold_ids: Tensor,
    *,
    mode: str = "hidden_gold_oracle",
) -> MatchPlan:
    """Build an oracle without ever copying hidden IDs into ``RegionBatch``."""

    regions.validate()
    batch, prior_count, _ = regions.prior_features.shape
    current_count = regions.current_features.shape[1]
    if tuple(prior_gold_ids.shape) != (batch, prior_count):
        raise ValueError("prior_gold_ids has the wrong shape")
    if tuple(current_gold_ids.shape) != (batch, current_count):
        raise ValueError("current_gold_ids has the wrong shape")
    _require_long("prior_gold_ids", prior_gold_ids)
    _require_long("current_gold_ids", current_gold_ids)

    transport = regions.prior_features.new_zeros(
        (batch, prior_count + 1, current_count + 1)
    )
    for batch_index in range(batch):
        current_lookup: dict[int, int] = {}
        for current_index in range(current_count):
            if not bool(regions.current_valid[batch_index, current_index]):
                continue
            gold_id = int(current_gold_ids[batch_index, current_index])
            if gold_id in current_lookup:
                raise ValueError(f"duplicate hidden current gold ID {gold_id}")
            current_lookup[gold_id] = current_index

        used_current: set[int] = set()
        for prior_index in range(prior_count):
            if not bool(regions.prior_valid[batch_index, prior_index]):
                continue
            gold_id = int(prior_gold_ids[batch_index, prior_index])
            current_index = current_lookup.get(gold_id)
            if current_index is None:
                transport[batch_index, prior_index, current_count] = 1.0
                continue
            if current_index in used_current:
                raise ValueError("hidden oracle is not one-to-one")
            used_current.add(current_index)
            transport[batch_index, prior_index, current_index] = 1.0

        for current_index in range(current_count):
            if bool(regions.current_valid[batch_index, current_index]) and (
                current_index not in used_current
            ):
                transport[batch_index, prior_count, current_index] = 1.0

    plan = MatchPlan(transport=transport, mode=mode)
    plan.validate_hard(regions)
    return plan


@dataclass
class HiddenQueryOracle:
    """Gold-only identity and five-label state, kept outside model-visible data."""

    prior_gold_ids: Tensor
    current_gold_ids: Tensor
    labels: Tensor
    plan: MatchPlan

    def validate(self, regions: RegionBatch) -> None:
        batch, prior_count, _ = regions.prior_features.shape
        current_count = regions.current_features.shape[1]
        if tuple(self.prior_gold_ids.shape) != (batch, prior_count):
            raise ValueError("prior_gold_ids has the wrong shape")
        if tuple(self.current_gold_ids.shape) != (batch, current_count):
            raise ValueError("current_gold_ids has the wrong shape")
        if tuple(self.labels.shape) != (batch,):
            raise ValueError("labels must have shape [B]")
        _require_long("prior_gold_ids", self.prior_gold_ids)
        _require_long("current_gold_ids", self.current_gold_ids)
        _require_long("labels", self.labels)
        if bool(((self.labels < 0) | (self.labels >= LABEL_COUNT)).any()):
            raise ValueError("labels must be in [0, 4]")
        self.plan.validate_hard(regions)
        expected = _oracle_plan_from_hidden_ids(
            regions,
            self.prior_gold_ids,
            self.current_gold_ids,
        )
        if not torch.equal(self.plan.transport, expected.transport):
            raise ValueError("oracle plan is inconsistent with hidden gold IDs")

    def to(self, device: torch.device | str) -> "HiddenQueryOracle":
        return HiddenQueryOracle(
            prior_gold_ids=self.prior_gold_ids.to(device),
            current_gold_ids=self.current_gold_ids.to(device),
            labels=self.labels.to(device),
            plan=self.plan.to(device),
        )


@dataclass
class QueryAnchorBatch:
    """V2 query-conditioned anchor with a strict visible/gold information wall."""

    regions: RegionBatch
    prior_query_marker: Tensor
    current_query_marker: Tensor
    prior_carrier_control: Tensor
    current_carrier_control: Tensor
    counterbalance_index: Tensor
    oracle: HiddenQueryOracle

    @property
    def prior_states(self) -> Tensor:
        return self.regions.prior_features[..., STATE_CHANNEL]

    @property
    def current_states(self) -> Tensor:
        return self.regions.current_features[..., STATE_CHANNEL]

    @property
    def persistent_main_mask(self) -> Tensor:
        """Cases entering M_pers: stable, worse and improved only."""

        return self.oracle.labels <= LABEL_IMPROVED

    @property
    def null_control_mask(self) -> Tensor:
        """New/resolved controls, explicitly outside the persistent estimand."""

        return self.oracle.labels >= LABEL_NEW

    def validate(self) -> None:
        self.regions.validate()
        self.oracle.validate(self.regions)
        batch, prior_count, feature_dim = self.regions.prior_features.shape
        current_count = self.regions.current_features.shape[1]
        if feature_dim <= STATE_CHANNEL:
            raise ValueError("features do not contain marker and state channels")
        for name, value, shape in (
            ("prior_query_marker", self.prior_query_marker, (batch, prior_count)),
            (
                "current_query_marker",
                self.current_query_marker,
                (batch, current_count),
            ),
            ("prior_carrier_control", self.prior_carrier_control, (batch, prior_count)),
            (
                "current_carrier_control",
                self.current_carrier_control,
                (batch, current_count),
            ),
        ):
            if tuple(value.shape) != shape:
                raise ValueError(f"{name} must have shape {shape}")
            _require_bool(name, value)
        if tuple(self.counterbalance_index.shape) != (batch,):
            raise ValueError("counterbalance_index must have shape [B]")
        _require_long("counterbalance_index", self.counterbalance_index)

        marker_count = self.prior_query_marker.sum(
            dim=-1
        ) + self.current_query_marker.sum(dim=-1)
        if not torch.equal(marker_count, torch.ones_like(marker_count)):
            raise ValueError("each case must expose exactly one query marker")
        if not torch.equal(
            self.prior_carrier_control.sum(dim=-1),
            torch.ones(
                batch, dtype=torch.long, device=self.prior_carrier_control.device
            ),
        ) or not torch.equal(
            self.current_carrier_control.sum(dim=-1),
            torch.ones(
                batch,
                dtype=torch.long,
                device=self.current_carrier_control.device,
            ),
        ):
            raise ValueError("each case must reserve exactly one carrier-control pair")
        if not torch.equal(
            self.regions.prior_features[..., QUERY_MARKER_CHANNEL],
            self.prior_query_marker.to(self.regions.prior_features.dtype),
        ):
            raise ValueError("prior visible marker channel is inconsistent")
        if not torch.equal(
            self.regions.current_features[..., QUERY_MARKER_CHANNEL],
            self.current_query_marker.to(self.regions.current_features.dtype),
        ):
            raise ValueError("current visible marker channel is inconsistent")
        if not bool(
            torch.isin(
                self.prior_states,
                self.prior_states.new_tensor(STATE_VALUES),
            ).all()
        ) or not bool(
            torch.isin(
                self.current_states,
                self.current_states.new_tensor(STATE_VALUES),
            ).all()
        ):
            raise ValueError("anchor states must be exactly -1, 0 or +1")

        prior_visible = self.regions.prior_entity_ids
        current_visible = self.regions.current_entity_ids
        for batch_index in range(batch):
            prior_namespace = set(prior_visible[batch_index].tolist())
            current_namespace = set(current_visible[batch_index].tolist())
            if prior_namespace & current_namespace:
                raise ValueError(
                    "model-visible prior/current ID namespaces must be disjoint"
                )

        real = self.oracle.plan.transport[:, :prior_count, :current_count]
        death = self.oracle.plan.transport[:, :prior_count, current_count]
        birth = self.oracle.plan.transport[:, prior_count, :current_count]
        for batch_index, label_tensor in enumerate(self.oracle.labels):
            label = int(label_tensor)
            if label == LABEL_NEW:
                if int(self.current_query_marker[batch_index].sum()) != 1:
                    raise ValueError("new must query a current-side endpoint")
                current_index = int(
                    torch.nonzero(
                        self.current_query_marker[batch_index], as_tuple=False
                    ).item()
                )
                if float(birth[batch_index, current_index]) != 1.0:
                    raise ValueError("new query endpoint must be a true birth")
                continue

            if int(self.prior_query_marker[batch_index].sum()) != 1:
                raise ValueError("non-new labels must query a prior-side endpoint")
            prior_index = int(
                torch.nonzero(
                    self.prior_query_marker[batch_index], as_tuple=False
                ).item()
            )
            if label == LABEL_RESOLVED:
                if float(death[batch_index, prior_index]) != 1.0:
                    raise ValueError("resolved query endpoint must be a true death")
                continue

            if float(self.prior_states[batch_index, prior_index]) != 0.0:
                raise ValueError("queried persistent prior state must be exactly zero")

            query_anatomy = int(self.regions.prior_anatomy[batch_index, prior_index])
            compatible_persistent = 0
            for candidate_prior in range(prior_count):
                if (
                    int(self.regions.prior_anatomy[batch_index, candidate_prior])
                    != query_anatomy
                ):
                    continue
                if bool(real[batch_index, candidate_prior].any()):
                    compatible_persistent += 1
            if compatible_persistent != QUERY_GROUP_SIZE:
                raise ValueError(
                    "persistent query compatibility group must contain exactly six endpoints"
                )

            hits = torch.nonzero(real[batch_index, prior_index] > 0.5).flatten()
            if len(hits) != 1:
                raise ValueError("persistent query must have one oracle current match")
            current_state = float(self.current_states[batch_index, int(hits.item())])
            expected_state = {
                LABEL_STABLE: 0.0,
                LABEL_WORSE: 1.0,
                LABEL_IMPROVED: -1.0,
            }[label]
            if current_state != expected_state:
                raise ValueError("persistent query transition disagrees with its label")

        carrier_death = death * self.prior_carrier_control.to(death.dtype)
        carrier_birth = birth * self.current_carrier_control.to(birth.dtype)
        if not torch.equal(
            carrier_death.sum(dim=-1), torch.ones(batch, device=death.device)
        ):
            raise ValueError("reserved prior carrier must be one oracle death")
        if not torch.equal(
            carrier_birth.sum(dim=-1), torch.ones(batch, device=birth.device)
        ):
            raise ValueError("reserved current carrier must be one oracle birth")
        background_death = death * (~self.prior_carrier_control).to(death.dtype)
        background_birth = birth * (~self.current_carrier_control).to(birth.dtype)
        if not torch.equal(
            background_death.sum(dim=-1), torch.ones(batch, device=death.device)
        ) or not torch.equal(
            background_birth.sum(dim=-1), torch.ones(batch, device=birth.device)
        ):
            raise ValueError(
                "every case must have one background death and one background birth"
            )
        new_mask = self.oracle.labels == LABEL_NEW
        resolved_mask = self.oracle.labels == LABEL_RESOLVED
        if bool(new_mask.any()) and not torch.equal(
            self.current_query_marker[new_mask], self.current_carrier_control[new_mask]
        ):
            raise ValueError("new must query the registered current carrier")
        if bool(resolved_mask.any()) and not torch.equal(
            self.prior_query_marker[resolved_mask],
            self.prior_carrier_control[resolved_mask],
        ):
            raise ValueError("resolved must query the registered prior carrier")

        separation = audit_hidden_id_separation(self, validate=False)
        if not separation["passed"]:
            raise ValueError("hidden/model-visible ID separation audit failed")

    def to(self, device: torch.device | str) -> "QueryAnchorBatch":
        return QueryAnchorBatch(
            regions=self.regions.to(device),
            prior_query_marker=self.prior_query_marker.to(device),
            current_query_marker=self.current_query_marker.to(device),
            prior_carrier_control=self.prior_carrier_control.to(device),
            current_carrier_control=self.current_carrier_control.to(device),
            counterbalance_index=self.counterbalance_index.to(device),
            oracle=self.oracle.to(device),
        )


@dataclass
class QueryTokenContract:
    """Physical exact-64 skeleton with only one query relation payload enabled."""

    tokens: Tensor
    valid_mask: Tensor
    attention_mask: Tensor
    token_types: Tensor
    position_ids: Tensor
    query_relation_slot: Tensor
    neutral_embedding: Tensor

    def validate(self) -> None:
        if self.tokens.ndim != 3:
            raise ValueError("tokens must have shape [B, 64, D]")
        batch, token_count, token_dim = self.tokens.shape
        if token_count != TOKEN_BUDGET or token_dim < 6:
            raise ValueError("query tokens require exactly 64 tokens and D>=6")
        if tuple(self.valid_mask.shape) != (batch, TOKEN_BUDGET):
            raise ValueError("valid_mask must have shape [B, 64]")
        _require_bool("valid_mask", self.valid_mask)
        if not bool(self.valid_mask.all()):
            raise ValueError("all 64 physical token positions must remain present")
        if tuple(self.attention_mask.shape) != (batch, TOKEN_BUDGET):
            raise ValueError("attention_mask must have shape [B, 64]")
        if not bool((self.attention_mask == 1).all()):
            raise ValueError("attention_mask must be one at all 64 positions")
        if tuple(self.token_types.shape) != (TOKEN_BUDGET,):
            raise ValueError("token_types must have shape [64]")
        _require_long("token_types", self.token_types)
        if tuple(self.position_ids.shape) != (3, batch, TOKEN_BUDGET):
            raise ValueError("position_ids must have shape [3, B, 64]")
        _require_long("position_ids", self.position_ids)
        expected_positions = torch.arange(
            TOKEN_BUDGET,
            device=self.position_ids.device,
            dtype=torch.long,
        ).expand(batch, -1)
        if not all(
            torch.equal(self.position_ids[axis], expected_positions)
            for axis in range(3)
        ):
            raise ValueError(
                "all three position axes must be the physical 0..63 sequence"
            )
        if tuple(self.query_relation_slot.shape) != (batch,):
            raise ValueError("query_relation_slot must have shape [B]")
        _require_long("query_relation_slot", self.query_relation_slot)
        if not bool((self.query_relation_slot == QUERY_RELATION_SLOT).all()):
            raise ValueError("query relation must use the stable visible-marker slot")
        if not bool(torch.isfinite(self.tokens).all()):
            raise ValueError("query tokens contain non-finite values")
        if tuple(self.neutral_embedding.shape) != (token_dim,):
            raise ValueError("neutral_embedding must have shape [D]")
        if self.neutral_embedding.requires_grad:
            raise ValueError("literal neutral embedding cannot be trainable")
        if bool((self.neutral_embedding != 0).any()):
            raise ValueError("neutral embedding must be the literal zero vector")

        allowed = torch.zeros_like(self.tokens, dtype=torch.bool)
        allowed[:, QUERY_RELATION_SLOT, :] = True
        if bool((self.tokens.masked_select(~allowed) != 0).any()):
            raise ValueError("all non-query token payloads must be exactly neutral")

    def to_projected_bundle(self) -> ProjectedTokenBundle:
        """Enter the production exact-64 adapter schema without a side path."""

        self.validate()
        bundle = ProjectedTokenBundle(
            embeddings=self.tokens,
            token_types=self.token_types,
            valid_mask=self.valid_mask,
            attention_mask=self.attention_mask,
            position_ids=self.position_ids,
            audit={
                "query_anchor_gate": True,
                "literal_zero_nonquery_payloads": True,
                "query_relation_slot": QUERY_RELATION_SLOT,
                "physical_token_count": TOKEN_BUDGET,
            },
        )
        bundle.validate(token_budget=TOKEN_BUDGET)
        return bundle


def _identity_codes(count: int, width: int, generator: torch.Generator) -> Tensor:
    codes = torch.randn(count, width, generator=generator)
    return F.normalize(codes, dim=-1)


def make_query_anchor_batch(
    *,
    cases_per_label: int = 16,
    seed: int = 63_401,
    feature_dim: int = 10,
) -> QueryAnchorBatch:
    """Construct an exactly counterbalanced, identity-dependent five-label anchor.

    Every case contains twelve persistent endpoints (exactly six in each anatomy
    group), two deaths and two births.  The first death/birth pair is a fixed,
    model-hidden carrier-control pair used by new/resolved; the second pair is
    the identical background null structure for every label.  Visible IDs use
    opaque, disjoint sentinel namespaces; the only cross-time equality relation
    lives in :class:`HiddenQueryOracle`.
    """

    if cases_per_label <= 0:
        raise ValueError("cases_per_label must be positive")
    if feature_dim < 6:
        raise ValueError("feature_dim must be at least six")

    generator = torch.Generator(device="cpu")
    generator.manual_seed(seed)
    persistent_count = 12
    null_count = 2
    endpoint_count = persistent_count + null_count
    identity_width = feature_dim - 2
    # The query group has the minimal feasible six endpoints: two at each
    # current state.  Whichever state is consumed by the oracle edge, a second
    # endpoint at that state remains available and D=3 can select three
    # distinct wrong targets at -1/0/+1 without changing either side's state
    # marginal.  The query source is sampled before labels are instantiated.
    prior_query_group_states = torch.zeros(QUERY_GROUP_SIZE)
    current_query_group_states = torch.tensor([-1.0, -1.0, 0.0, 0.0, 1.0, 1.0])
    second_group_states = torch.tensor([-1.0, -1.0, 0.0, 0.0, 1.0, 1.0])
    death_states = torch.tensor([-1.0, 1.0])
    anatomy_template = torch.tensor([0] * 6 + [1] * 6 + [0, 0])

    prior_features_rows: list[Tensor] = []
    current_features_rows: list[Tensor] = []
    prior_anatomy_rows: list[Tensor] = []
    current_anatomy_rows: list[Tensor] = []
    prior_marker_rows: list[Tensor] = []
    current_marker_rows: list[Tensor] = []
    prior_carrier_rows: list[Tensor] = []
    current_carrier_rows: list[Tensor] = []
    prior_gold_rows: list[Tensor] = []
    current_gold_rows: list[Tensor] = []
    labels: list[int] = []
    counterbalance_indices: list[int] = []

    case_number = 0
    for replicate in range(cases_per_label):
        # A replicate block shares unordered visible material across all labels.
        codes = _identity_codes(endpoint_count + null_count, identity_width, generator)
        prior_permutation = torch.randperm(endpoint_count, generator=generator)
        current_permutation = torch.randperm(endpoint_count, generator=generator)
        query_prior_index = replicate % QUERY_GROUP_SIZE
        for label in range(LABEL_COUNT):
            persistent_state = {
                LABEL_STABLE: 0.0,
                LABEL_WORSE: 1.0,
                LABEL_IMPROVED: -1.0,
                LABEL_NEW: 0.0,
                LABEL_RESOLVED: 0.0,
            }[label]
            # Current state marginals are literal constants across labels.
            # Only the cross-time identity mapping changes which current state
            # is bound to the pre-label query source.
            if label <= LABEL_IMPROVED:
                target_candidates = torch.nonzero(
                    current_query_group_states == persistent_state,
                    as_tuple=False,
                ).flatten()
                target_current_index = int(
                    target_candidates[(replicate // QUERY_GROUP_SIZE) % 2]
                )
                remaining_prior = [
                    index
                    for index in range(QUERY_GROUP_SIZE)
                    if index != query_prior_index
                ]
                remaining_current = [
                    index
                    for index in range(QUERY_GROUP_SIZE)
                    if index != target_current_index
                ]
                query_mapping = {
                    query_prior_index: target_current_index,
                    **dict(zip(remaining_prior, remaining_current, strict=True)),
                }
            else:
                query_mapping = {index: index for index in range(QUERY_GROUP_SIZE)}
            mapping: dict[int, int] = {
                **query_mapping,
                **{index: index for index in range(QUERY_GROUP_SIZE, persistent_count)},
            }

            birth_states = torch.tensor([-1.0, 1.0])
            prior_state_template = torch.cat(
                (prior_query_group_states, second_group_states, death_states)
            )
            current_state_template = torch.cat(
                (current_query_group_states, second_group_states, birth_states)
            )

            prior_features = torch.zeros(endpoint_count, feature_dim)
            current_features = torch.zeros(endpoint_count, feature_dim)
            prior_features[:, STATE_CHANNEL] = prior_state_template
            current_features[:, STATE_CHANNEL] = current_state_template
            prior_features[:, 2:] = codes[:endpoint_count]
            for prior_index, current_index in mapping.items():
                current_features[current_index, 2:] = codes[prior_index]
            for birth_offset in range(null_count):
                current_features[persistent_count + birth_offset, 2:] = codes[
                    endpoint_count + birth_offset
                ]

            prior_marker = torch.zeros(endpoint_count, dtype=torch.bool)
            current_marker = torch.zeros(endpoint_count, dtype=torch.bool)
            if label == LABEL_NEW:
                current_marker[persistent_count] = True
            elif label == LABEL_RESOLVED:
                prior_marker[persistent_count] = True
            else:
                prior_marker[query_prior_index] = True
            prior_features[:, QUERY_MARKER_CHANNEL] = prior_marker
            current_features[:, QUERY_MARKER_CHANNEL] = current_marker

            prior_carrier = torch.zeros(endpoint_count, dtype=torch.bool)
            current_carrier = torch.zeros(endpoint_count, dtype=torch.bool)
            prior_carrier[persistent_count] = True
            current_carrier[persistent_count] = True

            gold_base = (case_number + 1) * 100
            prior_gold = torch.arange(endpoint_count, dtype=torch.long) + gold_base
            current_gold = torch.arange(endpoint_count, dtype=torch.long) + (
                gold_base + endpoint_count
            )
            for prior_index, current_index in mapping.items():
                current_gold[current_index] = prior_gold[prior_index]

            prior_features_rows.append(prior_features[prior_permutation])
            current_features_rows.append(current_features[current_permutation])
            prior_anatomy_rows.append(anatomy_template[prior_permutation])
            current_anatomy_rows.append(anatomy_template[current_permutation])
            prior_marker_rows.append(prior_marker[prior_permutation])
            current_marker_rows.append(current_marker[current_permutation])
            prior_carrier_rows.append(prior_carrier[prior_permutation])
            current_carrier_rows.append(current_carrier[current_permutation])
            prior_gold_rows.append(prior_gold[prior_permutation])
            current_gold_rows.append(current_gold[current_permutation])
            labels.append(label)
            counterbalance_indices.append(replicate % 3)
            case_number += 1

    prior_features_tensor = torch.stack(prior_features_rows)
    current_features_tensor = torch.stack(current_features_rows)
    prior_anatomy_tensor = torch.stack(prior_anatomy_rows)
    current_anatomy_tensor = torch.stack(current_anatomy_rows)
    prior_gold_tensor = torch.stack(prior_gold_rows)
    current_gold_tensor = torch.stack(current_gold_rows)
    batch_size = len(labels)
    # Opaque prior/current sentinel namespaces cannot expose equality, order,
    # label or hidden identity through their values.
    prior_visible = torch.full((batch_size, endpoint_count), -1, dtype=torch.long)
    current_visible = torch.full((batch_size, endpoint_count), -2, dtype=torch.long)
    regions = RegionBatch(
        prior_features=prior_features_tensor,
        current_features=current_features_tensor,
        prior_valid=torch.ones(batch_size, endpoint_count, dtype=torch.bool),
        current_valid=torch.ones(batch_size, endpoint_count, dtype=torch.bool),
        prior_anatomy=prior_anatomy_tensor,
        current_anatomy=current_anatomy_tensor,
        prior_entity_ids=prior_visible,
        current_entity_ids=current_visible,
    )
    oracle = HiddenQueryOracle(
        prior_gold_ids=prior_gold_tensor,
        current_gold_ids=current_gold_tensor,
        labels=torch.tensor(labels, dtype=torch.long),
        plan=_oracle_plan_from_hidden_ids(
            regions, prior_gold_tensor, current_gold_tensor
        ),
    )
    result = QueryAnchorBatch(
        regions=regions,
        prior_query_marker=torch.stack(prior_marker_rows),
        current_query_marker=torch.stack(current_marker_rows),
        prior_carrier_control=torch.stack(prior_carrier_rows),
        current_carrier_control=torch.stack(current_carrier_rows),
        counterbalance_index=torch.tensor(counterbalance_indices, dtype=torch.long),
        oracle=oracle,
    )
    result.validate()
    return result


def make_frozen_query_anchor_split(
    split: str,
    *,
    feature_dim: int = 10,
) -> QueryAnchorBatch:
    """Materialize one split under the frozen 16/8/24-per-label contract."""

    if split not in FROZEN_SPLIT_CASES_PER_LABEL:
        choices = ", ".join(FROZEN_SPLIT_CASES_PER_LABEL)
        raise ValueError(f"split must be one of: {choices}")
    return make_query_anchor_batch(
        cases_per_label=FROZEN_SPLIT_CASES_PER_LABEL[split],
        seed=FROZEN_SPLIT_SEEDS[split],
        feature_dim=feature_dim,
    )


def _orthogonal_rotation(width: int, generator: torch.Generator) -> Tensor:
    matrix = torch.randn(width, width, generator=generator)
    orthogonal, triangular = torch.linalg.qr(matrix)
    signs = torch.diagonal(triangular).sign()
    signs[signs == 0] = 1
    return orthogonal * signs.unsqueeze(0)


def _global_assignment_similarity(query_to_state: Sequence[int]) -> Tensor:
    """Return the closed-form R2 6x6 hard-negative similarity gadget."""

    if sorted(int(state) for state in query_to_state) != [0, 1, 2]:
        raise ValueError("query_to_state must be a permutation of 0, 1, 2")
    similarity = torch.zeros(6, 6, dtype=torch.float64)
    high = 3.0
    low = -2.0
    guard = 10.0
    compensation = math.sqrt(35.0)
    for state in range(3):
        true_column = 2 * state
        wrong_column = true_column + 1
        for query in range(3):
            assigned = int(query_to_state[query]) == state
            similarity[query, true_column] = high if assigned else low
            similarity[query, wrong_column] = low if assigned else high
        similarity[3:, true_column] = compensation
        similarity[3 + state, wrong_column] = guard
    column_norm_squared = similarity.square().sum(dim=0)
    if not torch.allclose(
        column_norm_squared,
        torch.full_like(column_norm_squared, 122.0),
        atol=1e-6,
        rtol=0,
    ):
        raise RuntimeError("R2 gadget columns must have equal squared norm 122")
    return similarity


def make_global_assignment_query_anchor_batch(
    *,
    cases_per_label: int = 16,
    seed: int = 73_401,
    feature_dim: int = 18,
) -> QueryAnchorBatch:
    """Construct the R2 anchor that requires global one-to-one assignment.

    Each anatomy contains three query-like rows and three guard rows.  Within
    every current state, each visible query row sees exactly the same local
    similarity multiset ``{-2, +3}``.  Equal-norm hard negatives are claimed by
    guard rows only under the global one-to-one solve, leaving the correct
    state-specific column for the queried row.  A fresh joint orthogonal
    rotation per replicate prevents coordinate memorization while preserving
    all dot products.
    """

    if cases_per_label <= 0:
        raise ValueError("cases_per_label must be positive")
    if feature_dim < 18:
        raise ValueError("R2 feature_dim must be at least eighteen")
    generator = torch.Generator(device="cpu").manual_seed(seed)
    persistent_count = 12
    null_count = 2
    endpoint_count = persistent_count + null_count
    block_width = 6
    current_block_states = torch.tensor([-1.0, -1.0, 0.0, 0.0, 1.0, 1.0])
    anatomy_template = torch.tensor([0] * 6 + [1] * 6 + [0, 0])

    prior_features_rows: list[Tensor] = []
    current_features_rows: list[Tensor] = []
    prior_anatomy_rows: list[Tensor] = []
    current_anatomy_rows: list[Tensor] = []
    prior_marker_rows: list[Tensor] = []
    current_marker_rows: list[Tensor] = []
    prior_carrier_rows: list[Tensor] = []
    current_carrier_rows: list[Tensor] = []
    prior_gold_rows: list[Tensor] = []
    current_gold_rows: list[Tensor] = []
    labels: list[int] = []
    counterbalance_indices: list[int] = []

    case_number = 0
    for replicate in range(cases_per_label):
        rotations = (
            _orthogonal_rotation(block_width, generator),
            _orthogonal_rotation(block_width, generator),
        )
        prior_permutation = torch.randperm(endpoint_count, generator=generator)
        current_permutation = torch.randperm(endpoint_count, generator=generator)
        # Freeze the queried identity before any label is selected.  Persistent
        # labels may change only the hidden query-to-state assignment, never
        # which prior row carries the query marker.
        query_row = replicate % 3
        background_shift = (replicate // 3) % 3
        background_query_to_state = tuple(
            (query - query_row + background_shift) % 3 for query in range(3)
        )
        second_query_to_state = tuple(
            (query + ((replicate // 3) % 3)) % 3 for query in range(3)
        )
        for label in range(LABEL_COUNT):
            if label <= LABEL_IMPROVED:
                target_state = {
                    LABEL_STABLE: 1,
                    LABEL_WORSE: 2,
                    LABEL_IMPROVED: 0,
                }[label]
                query_to_state = tuple(
                    (query - query_row + target_state) % 3 for query in range(3)
                )
            else:
                query_to_state = background_query_to_state

            prior_features = torch.zeros(endpoint_count, feature_dim)
            current_features = torch.zeros(endpoint_count, feature_dim)
            prior_features[:persistent_count, STATE_CHANNEL] = 0.0
            current_features[:6, STATE_CHANNEL] = current_block_states
            current_features[6:12, STATE_CHANNEL] = current_block_states
            prior_features[12:, STATE_CHANNEL] = torch.tensor([-1.0, 1.0])
            current_features[12:, STATE_CHANNEL] = torch.tensor([-1.0, 1.0])

            mappings: dict[int, int] = {}
            for block, block_mapping in enumerate(
                (query_to_state, second_query_to_state)
            ):
                offset = block * 6
                rotation = rotations[block]
                feature_start = 2 + block * block_width
                feature_stop = feature_start + block_width
                prior_features[offset : offset + 6, feature_start:feature_stop] = (
                    rotation
                )
                similarity = _global_assignment_similarity(block_mapping)
                current_features[offset : offset + 6, feature_start:feature_stop] = (
                    similarity.T.to(rotation.dtype) / math.sqrt(122.0)
                ) @ rotation
                for query in range(3):
                    mappings[offset + query] = offset + 2 * block_mapping[query]
                for state in range(3):
                    mappings[offset + 3 + state] = offset + 2 * state + 1

            prior_features[12, 14] = 1.0
            prior_features[13, 15] = 1.0
            current_features[12, 16] = 1.0
            current_features[13, 17] = 1.0

            prior_marker = torch.zeros(endpoint_count, dtype=torch.bool)
            current_marker = torch.zeros(endpoint_count, dtype=torch.bool)
            if label == LABEL_NEW:
                current_marker[12] = True
            elif label == LABEL_RESOLVED:
                prior_marker[12] = True
            else:
                prior_marker[query_row] = True
            prior_features[:, QUERY_MARKER_CHANNEL] = prior_marker
            current_features[:, QUERY_MARKER_CHANNEL] = current_marker

            prior_carrier = torch.zeros(endpoint_count, dtype=torch.bool)
            current_carrier = torch.zeros(endpoint_count, dtype=torch.bool)
            prior_carrier[12] = True
            current_carrier[12] = True

            gold_base = (case_number + 1) * 100
            prior_gold = torch.arange(endpoint_count, dtype=torch.long) + gold_base
            current_gold = torch.arange(endpoint_count, dtype=torch.long) + (
                gold_base + endpoint_count
            )
            for prior_index, current_index in mappings.items():
                current_gold[current_index] = prior_gold[prior_index]

            prior_features_rows.append(prior_features[prior_permutation])
            current_features_rows.append(current_features[current_permutation])
            prior_anatomy_rows.append(anatomy_template[prior_permutation])
            current_anatomy_rows.append(anatomy_template[current_permutation])
            prior_marker_rows.append(prior_marker[prior_permutation])
            current_marker_rows.append(current_marker[current_permutation])
            prior_carrier_rows.append(prior_carrier[prior_permutation])
            current_carrier_rows.append(current_carrier[current_permutation])
            prior_gold_rows.append(prior_gold[prior_permutation])
            current_gold_rows.append(current_gold[current_permutation])
            labels.append(label)
            counterbalance_indices.append(replicate % 3)
            case_number += 1

    batch_size = len(labels)
    regions = RegionBatch(
        prior_features=torch.stack(prior_features_rows),
        current_features=torch.stack(current_features_rows),
        prior_valid=torch.ones(batch_size, endpoint_count, dtype=torch.bool),
        current_valid=torch.ones(batch_size, endpoint_count, dtype=torch.bool),
        prior_anatomy=torch.stack(prior_anatomy_rows),
        current_anatomy=torch.stack(current_anatomy_rows),
        prior_entity_ids=torch.full((batch_size, endpoint_count), -1, dtype=torch.long),
        current_entity_ids=torch.full(
            (batch_size, endpoint_count), -2, dtype=torch.long
        ),
    )
    prior_gold_tensor = torch.stack(prior_gold_rows)
    current_gold_tensor = torch.stack(current_gold_rows)
    oracle = HiddenQueryOracle(
        prior_gold_ids=prior_gold_tensor,
        current_gold_ids=current_gold_tensor,
        labels=torch.tensor(labels, dtype=torch.long),
        plan=_oracle_plan_from_hidden_ids(
            regions, prior_gold_tensor, current_gold_tensor
        ),
    )
    result = QueryAnchorBatch(
        regions=regions,
        prior_query_marker=torch.stack(prior_marker_rows),
        current_query_marker=torch.stack(current_marker_rows),
        prior_carrier_control=torch.stack(prior_carrier_rows),
        current_carrier_control=torch.stack(current_carrier_rows),
        counterbalance_index=torch.tensor(counterbalance_indices, dtype=torch.long),
        oracle=oracle,
    )
    result.validate()
    return result


def make_frozen_global_assignment_query_anchor_split(
    split: str,
    *,
    feature_dim: int = 18,
) -> QueryAnchorBatch:
    if split not in FROZEN_SPLIT_CASES_PER_LABEL:
        choices = ", ".join(FROZEN_SPLIT_CASES_PER_LABEL)
        raise ValueError(f"split must be one of: {choices}")
    return make_global_assignment_query_anchor_batch(
        cases_per_label=FROZEN_SPLIT_CASES_PER_LABEL[split],
        seed=FROZEN_R2_SPLIT_SEEDS[split],
        feature_dim=feature_dim,
    )


def build_query_relation_tokens(
    regions: RegionBatch,
    prior_query_marker: Tensor,
    current_query_marker: Tensor,
    plan: MatchPlan,
    *,
    token_dim: int = 8,
) -> QueryTokenContract:
    """Apply the v2 gate: one visible-query relation payload, 63 neutral payloads."""

    regions.validate()
    plan.validate(regions)
    if token_dim < 6:
        raise ValueError("token_dim must be at least six")
    batch_size, prior_count, _ = regions.prior_features.shape
    current_count = regions.current_features.shape[1]
    if tuple(prior_query_marker.shape) != (batch_size, prior_count):
        raise ValueError("prior_query_marker has the wrong shape")
    if tuple(current_query_marker.shape) != (batch_size, current_count):
        raise ValueError("current_query_marker has the wrong shape")
    _require_bool("prior_query_marker", prior_query_marker)
    _require_bool("current_query_marker", current_query_marker)
    marker_count = prior_query_marker.sum(-1) + current_query_marker.sum(-1)
    if not torch.equal(marker_count, torch.ones_like(marker_count)):
        raise ValueError("each case must provide exactly one binary query marker")
    if not torch.equal(
        regions.prior_features[..., QUERY_MARKER_CHANNEL],
        prior_query_marker.to(regions.prior_features.dtype),
    ) or not torch.equal(
        regions.current_features[..., QUERY_MARKER_CHANNEL],
        current_query_marker.to(regions.current_features.dtype),
    ):
        raise ValueError("query markers disagree with visible feature channels")

    prior_states = regions.prior_features[..., STATE_CHANNEL]
    current_states = regions.current_features[..., STATE_CHANNEL]
    tokens = regions.prior_features.new_zeros((batch_size, TOKEN_BUDGET, token_dim))
    for batch_index in range(batch_size):
        payload = tokens[batch_index, QUERY_RELATION_SLOT]
        payload[0] = 1.0
        prior_hits = torch.nonzero(
            prior_query_marker[batch_index], as_tuple=False
        ).flatten()
        if len(prior_hits) == 1:
            prior_index = int(prior_hits.item())
            real_row = plan.transport[batch_index, prior_index, :current_count]
            real_mass = real_row.sum()
            payload[1] = prior_states[batch_index, prior_index]
            payload[2] = (real_row * current_states[batch_index]).sum()
            payload[3] = real_mass
            payload[4] = plan.transport[batch_index, prior_index, current_count]
        else:
            current_index = int(
                torch.nonzero(current_query_marker[batch_index], as_tuple=False).item()
            )
            payload[2] = current_states[batch_index, current_index]
            payload[5] = plan.transport[batch_index, prior_count, current_index]

    token_types = torch.cat(
        (
            torch.zeros(GLOBAL_TOKENS, dtype=torch.long),
            torch.ones(ENTITY_TOKENS, dtype=torch.long),
            torch.full((RELATION_TOKENS,), 2, dtype=torch.long),
            torch.full((RESERVED_TOKENS,), 3, dtype=torch.long),
        )
    ).to(tokens.device)
    contract = QueryTokenContract(
        tokens=tokens,
        valid_mask=torch.ones(
            batch_size, TOKEN_BUDGET, dtype=torch.bool, device=tokens.device
        ),
        attention_mask=torch.ones(
            batch_size, TOKEN_BUDGET, dtype=torch.long, device=tokens.device
        ),
        token_types=token_types,
        position_ids=torch.arange(TOKEN_BUDGET, dtype=torch.long, device=tokens.device)
        .expand(3, batch_size, -1)
        .clone(),
        query_relation_slot=torch.full(
            (batch_size,), QUERY_RELATION_SLOT, dtype=torch.long, device=tokens.device
        ),
        neutral_embedding=torch.zeros(
            token_dim, dtype=tokens.dtype, device=tokens.device, requires_grad=False
        ),
    )
    contract.validate()
    return contract


def decode_query_relation_tokens(contract: QueryTokenContract) -> Tensor:
    """Decode a hard oracle query payload into the registered five labels."""

    contract.validate()
    payloads = contract.tokens[:, QUERY_RELATION_SLOT]
    predictions: list[int] = []
    for payload in payloads:
        real_mass = float(payload[3])
        death_mass = float(payload[4])
        birth_mass = float(payload[5])
        indicators = (real_mass > 0.5, death_mass > 0.5, birth_mass > 0.5)
        if sum(indicators) != 1:
            raise QueryAnchorQualificationError(
                "oracle decoder requires exactly one hard real/death/birth event"
            )
        if birth_mass > 0.5:
            predictions.append(LABEL_NEW)
        elif death_mass > 0.5:
            predictions.append(LABEL_RESOLVED)
        else:
            prior_state = float(payload[1])
            current_state = float(payload[2])
            if prior_state != 0.0:
                raise QueryAnchorQualificationError(
                    "persistent oracle query prior state is not zero"
                )
            if current_state == 0.0:
                predictions.append(LABEL_STABLE)
            elif current_state == 1.0:
                predictions.append(LABEL_WORSE)
            elif current_state == -1.0:
                predictions.append(LABEL_IMPROVED)
            else:
                raise QueryAnchorQualificationError(
                    "persistent oracle current state is outside {-1, 0, +1}"
                )
    return torch.tensor(predictions, dtype=torch.long, device=contract.tokens.device)


def oracle_decode_labels(
    regions: RegionBatch,
    prior_query_marker: Tensor,
    current_query_marker: Tensor,
    oracle_assignment: MatchPlan,
) -> Tensor:
    """Decode using only model-visible tensors plus an assignment plan."""

    tokens = build_query_relation_tokens(
        regions,
        prior_query_marker,
        current_query_marker,
        oracle_assignment,
    )
    return decode_query_relation_tokens(tokens)


def _complete_group_derangement(
    pairs: Sequence[tuple[int, int]],
    *,
    forced_query: tuple[int, float] | None,
    current_states: Tensor,
    salt: int,
) -> dict[int, int]:
    original = {prior_index: current_index for prior_index, current_index in pairs}
    currents = sorted(original.values())
    query_prior = forced_query[0] if forced_query is not None else None
    desired_state = forced_query[1] if forced_query is not None else None
    candidate_permutations = list(permutations(currents))
    if candidate_permutations:
        rotation = abs(int(salt)) % len(candidate_permutations)
        candidate_permutations = (
            candidate_permutations[rotation:] + candidate_permutations[:rotation]
        )
    priors = [prior_index for prior_index, _ in pairs]
    for candidate in candidate_permutations:
        proposal = dict(zip(priors, candidate, strict=True))
        if any(proposal[prior] == original[prior] for prior in priors):
            continue
        if query_prior is not None and float(
            current_states[proposal[query_prior]]
        ) != float(desired_state):
            continue
        return proposal
    raise QueryAnchorQualificationError(
        "no anatomy-compatible zero-fixed-point derangement satisfies the balance"
    )


def build_balanced_derangement_bank(
    batch: QueryAnchorBatch,
    derangement_seeds: Sequence[int],
) -> dict[int, MatchPlan]:
    """Build crossed B4a plans with exact wrong-query-state counterbalancing."""

    batch.validate()
    seeds = tuple(int(seed) for seed in derangement_seeds)
    if len(seeds) != len(REGISTERED_DERANGEMENT_SEEDS) or set(seeds) != set(
        REGISTERED_DERANGEMENT_SEEDS
    ):
        raise QueryAnchorQualificationError(
            "NOT_EVALUABLE_DERANGEMENT_DESIGN: seeds must be exactly "
            f"{REGISTERED_DERANGEMENT_SEEDS}"
        )
    wrong_state_by_seed = dict(
        zip(REGISTERED_DERANGEMENT_SEEDS, STATE_VALUES, strict=True)
    )
    batch_size, prior_count, _ = batch.regions.prior_features.shape
    current_count = batch.regions.current_features.shape[1]
    bank: dict[int, MatchPlan] = {}
    for seed in REGISTERED_DERANGEMENT_SEEDS:
        transport = batch.oracle.plan.transport.clone()
        for batch_index in range(batch_size):
            anatomy_groups: dict[int, list[tuple[int, int]]] = {}
            for prior_index in range(prior_count):
                hits = torch.nonzero(
                    batch.oracle.plan.transport[
                        batch_index, prior_index, :current_count
                    ]
                    > 0.5,
                    as_tuple=False,
                ).flatten()
                if len(hits) != 1:
                    continue
                current_index = int(hits.item())
                anatomy = int(batch.regions.prior_anatomy[batch_index, prior_index])
                if anatomy != int(
                    batch.regions.current_anatomy[batch_index, current_index]
                ):
                    raise QueryAnchorQualificationError(
                        "oracle persistent edge crosses anatomy"
                    )
                anatomy_groups.setdefault(anatomy, []).append(
                    (prior_index, current_index)
                )

            label = int(batch.oracle.labels[batch_index])
            query_prior_hits = torch.nonzero(
                batch.prior_query_marker[batch_index], as_tuple=False
            ).flatten()
            persistent_query = label in (
                LABEL_STABLE,
                LABEL_WORSE,
                LABEL_IMPROVED,
            )
            query_prior = int(query_prior_hits.item()) if persistent_query else None
            desired_wrong_state = wrong_state_by_seed[seed]

            for anatomy, pairs in sorted(anatomy_groups.items()):
                if len(pairs) < 2:
                    raise QueryAnchorQualificationError(
                        f"anatomy group {anatomy} is not derangeable"
                    )
                forced = None
                if query_prior is not None and any(
                    prior_index == query_prior for prior_index, _ in pairs
                ):
                    forced = (query_prior, desired_wrong_state)
                proposal = _complete_group_derangement(
                    pairs,
                    forced_query=forced,
                    current_states=batch.current_states[batch_index],
                    salt=seed + batch_index * 101 + anatomy * 17,
                )
                for prior_index, _ in pairs:
                    transport[batch_index, prior_index, :current_count] = 0.0
                    transport[batch_index, prior_index, proposal[prior_index]] = 1.0

        plan = MatchPlan(transport=transport, mode=f"query_deranged_seed_{seed}")
        plan.validate_hard(batch.regions)
        bank[seed] = plan
    return bank


def audit_wrong_query_counterbalance(
    batch: QueryAnchorBatch,
    plans: Mapping[int, MatchPlan],
) -> dict[str, Any]:
    """Audit wrong-query states per persistent label and crossed derangement."""

    batch.validate()
    _, prior_count, _ = batch.regions.prior_features.shape
    current_count = batch.regions.current_features.shape[1]
    counts: dict[str, dict[str, dict[str, int]]] = {}
    query_targets: dict[int, list[int]] = {}
    zero_fixed = True
    null_sets_preserved = True
    oracle_real = batch.oracle.plan.transport[:, :prior_count, :current_count]
    for seed, plan in plans.items():
        plan.validate_hard(batch.regions)
        real = plan.transport[:, :prior_count, :current_count]
        zero_fixed = zero_fixed and not bool(((real > 0.5) & (oracle_real > 0.5)).any())
        null_sets_preserved = (
            null_sets_preserved
            and torch.equal(
                plan.transport[:, :prior_count, current_count],
                batch.oracle.plan.transport[:, :prior_count, current_count],
            )
            and torch.equal(
                plan.transport[:, prior_count, :current_count],
                batch.oracle.plan.transport[:, prior_count, :current_count],
            )
        )
        seed_counts: dict[str, dict[str, int]] = {}
        for label in (LABEL_STABLE, LABEL_WORSE, LABEL_IMPROVED):
            label_counts = {str(state): 0 for state in STATE_VALUES}
            cases = torch.nonzero(
                batch.oracle.labels == label, as_tuple=False
            ).flatten()
            for batch_index_tensor in cases:
                batch_index = int(batch_index_tensor)
                prior_index = int(
                    torch.nonzero(
                        batch.prior_query_marker[batch_index], as_tuple=False
                    ).item()
                )
                current_index = int(
                    torch.nonzero(
                        real[batch_index, prior_index] > 0.5, as_tuple=False
                    ).item()
                )
                state = str(float(batch.current_states[batch_index, current_index]))
                label_counts[state] += 1
                query_targets.setdefault(batch_index, []).append(current_index)
            seed_counts[str(label)] = label_counts
        counts[str(seed)] = seed_counts

    # For each crossed cell, all three persistent labels see the same wrong
    # state distribution. Across D=3, every persistent case must visit three
    # different wrong endpoints.
    exact = True
    for seed_counts in counts.values():
        distributions = [
            tuple(label_counts[str(state)] for state in STATE_VALUES)
            for label_counts in seed_counts.values()
        ]
        exact = exact and len(set(distributions)) == 1
    distinct_query_targets = len(plans) == 3 and all(
        len(targets) == 3 and len(set(targets)) == 3
        for targets in query_targets.values()
    )
    plan_hashes = {
        str(seed): hashlib.sha256(
            plan.transport.detach().cpu().contiguous().numpy().tobytes()
        ).hexdigest()
        for seed, plan in plans.items()
    }
    distinct_plan_hashes = len(plans) == 3 and len(set(plan_hashes.values())) == 3
    return {
        "passed": bool(
            exact
            and distinct_query_targets
            and distinct_plan_hashes
            and zero_fixed
            and null_sets_preserved
        ),
        "wrong_query_state_counts": counts,
        "exact_per_label_and_derangement": exact,
        "three_distinct_wrong_targets_per_case": distinct_query_targets,
        "plan_hashes": plan_hashes,
        "three_distinct_plan_hashes": distinct_plan_hashes,
        "zero_fixed_points": zero_fixed,
        "null_sets_preserved": null_sets_preserved,
    }


def _marginal_signature(
    batch: QueryAnchorBatch, index: int, mode: str
) -> tuple[Any, ...]:
    def side_signature(
        features: Tensor,
        anatomy: Tensor,
    ) -> tuple[Any, ...]:
        # Cover every model-visible feature channel while remaining explicitly
        # assignment-independent: only per-side permutation-invariant moments
        # and anatomy counts are exposed.  Cross-time equality joins or
        # pairwise attention belong to matching systems, not this control.
        moments = torch.cat(
            (
                features.mean(dim=0),
                features.std(dim=0, unbiased=False),
                features.amin(dim=0),
                features.amax(dim=0),
            )
        )
        rounded_moments = tuple(round(float(value), 6) for value in moments)
        anatomy_counts = torch.bincount(anatomy.cpu(), minlength=2)
        return rounded_moments + tuple(int(value) for value in anatomy_counts)

    current = side_signature(
        batch.regions.current_features[index],
        batch.regions.current_anatomy[index],
    )
    if mode == "current_only":
        return current
    if mode != "prior_current":
        raise ValueError("mode must be current_only or prior_current")
    prior = side_signature(
        batch.regions.prior_features[index],
        batch.regions.prior_anatomy[index],
    )
    return (prior, current)


def _macro_f1(
    predictions: Tensor, targets: Tensor, *, label_count: int = LABEL_COUNT
) -> float:
    values: list[float] = []
    for label in range(label_count):
        pred_positive = predictions == label
        gold_positive = targets == label
        tp = int((pred_positive & gold_positive).sum())
        fp = int((pred_positive & ~gold_positive).sum())
        fn = int((~pred_positive & gold_positive).sum())
        denominator = 2 * tp + fp + fn
        values.append((2 * tp / denominator) if denominator else 0.0)
    return sum(values) / label_count


def _best_signature_predictions(
    signatures: Sequence[tuple[Any, ...]], labels: Tensor, *, label_count: int
) -> tuple[Tensor, bool]:
    groups: dict[tuple[Any, ...], list[int]] = {}
    for index, signature in enumerate(signatures):
        groups.setdefault(signature, []).append(index)
    predictions = torch.empty_like(labels)
    deterministic = True
    for indices in groups.values():
        group_labels = labels[indices]
        counts = torch.bincount(group_labels, minlength=label_count)
        prediction = int(torch.argmax(counts))
        predictions[indices] = prediction
        deterministic = deterministic and int((counts > 0).sum()) == 1
    return predictions, deterministic


def _repeat_supported_signature_attack(
    signatures: Sequence[tuple[Any, ...]], labels: Tensor, *, label_count: int
) -> tuple[Tensor, bool, bool, str]:
    """Run only lookup attacks whose keys recur beyond a single sample.

    A nearest-table lookup over continuous, one-off QR coordinates has perfect
    in-sample accuracy by construction and no out-of-sample meaning.  We retain
    the exact full-signature attack when every key repeats, and also test every
    scalar coordinate so direct label channels remain fail-closed.
    """

    def flatten(value: Any) -> tuple[Any, ...]:
        if isinstance(value, tuple):
            return tuple(item for child in value for item in flatten(child))
        return (value,)

    flattened = [flatten(signature) for signature in signatures]
    candidates: list[tuple[str, list[tuple[Any, ...]]]] = [
        ("full_signature", list(signatures))
    ]
    if flattened:
        for coordinate in range(len(flattened[0])):
            candidates.append(
                (
                    f"scalar_coordinate_{coordinate}",
                    [(signature[coordinate],) for signature in flattened],
                )
            )

    best_predictions = torch.zeros_like(labels)
    best_macro_f1 = _macro_f1(best_predictions, labels, label_count=label_count)
    best_deterministic = False
    best_name = "constant_fallback"
    evaluable = False
    for name, keys in candidates:
        counts: dict[tuple[Any, ...], int] = {}
        for key in keys:
            counts[key] = counts.get(key, 0) + 1
        if not counts or min(counts.values()) < 2:
            continue
        evaluable = True
        predictions, deterministic = _best_signature_predictions(
            keys, labels, label_count=label_count
        )
        macro_f1 = _macro_f1(predictions, labels, label_count=label_count)
        if macro_f1 > best_macro_f1:
            best_predictions = predictions
            best_macro_f1 = macro_f1
            best_deterministic = deterministic
            best_name = name
    return best_predictions, best_deterministic, evaluable, best_name


def _pooled_state_kernel_predictions(
    batch: QueryAnchorBatch,
    persistent_indices: Tensor,
    *,
    anatomy_conditioned: bool,
    kernel: str = "linear",
) -> Tensor:
    """Deterministic no-pair-axis attack using separately pooled visible sets."""

    prior_identity = batch.regions.prior_features[persistent_indices, :, 2:]
    current_identity = batch.regions.current_features[persistent_indices, :, 2:]
    prior_marker = batch.prior_query_marker[persistent_indices]
    query = (prior_identity * prior_marker.to(prior_identity.dtype).unsqueeze(-1)).sum(
        dim=1
    )
    query_anatomy = (
        batch.regions.prior_anatomy[persistent_indices]
        * prior_marker.to(batch.regions.prior_anatomy.dtype)
    ).sum(dim=1)
    similarities = (current_identity * query.unsqueeze(1)).sum(dim=-1)
    scores: list[Tensor] = []
    for state in (-1.0, 0.0, 1.0):
        mask = batch.current_states[persistent_indices].eq(state)
        if anatomy_conditioned:
            mask = mask & batch.regions.current_anatomy[persistent_indices].eq(
                query_anatomy.unsqueeze(-1)
            )
        if kernel == "linear":
            score = (similarities * mask.to(similarities.dtype)).sum(dim=-1)
        elif kernel == "poly2":
            score = (similarities.square() * mask.to(similarities.dtype)).sum(dim=-1)
        elif kernel == "poly3":
            score = (similarities.pow(3) * mask.to(similarities.dtype)).sum(dim=-1)
        elif kernel.startswith("rbf_"):
            bandwidth = float(kernel.removeprefix("rbf_"))
            values = torch.exp(-((1.0 - similarities).square()) / (2.0 * bandwidth**2))
            score = (values * mask.to(values.dtype)).sum(dim=-1)
        elif kernel.startswith("logsumexp_"):
            temperature = float(kernel.removeprefix("logsumexp_"))
            masked = torch.where(
                mask,
                similarities / temperature,
                torch.full_like(similarities, -torch.inf),
            )
            score = temperature * torch.logsumexp(masked, dim=-1)
        else:
            raise ValueError(f"unknown pooled kernel: {kernel}")
        scores.append(score)
    stacked_scores = torch.stack(scores, dim=-1)
    # The R2 gadget is analytically tied across states.  Canonicalize numerical
    # QR/matmul noise before deterministic tie-breaking so chance fluctuations
    # cannot masquerade as a marginal bypass.
    canonical_scores = torch.round(stacked_scores * 1_000_000.0) / 1_000_000.0
    state_index = canonical_scores.argmax(dim=-1)
    index_to_label = torch.tensor(
        [LABEL_IMPROVED, LABEL_STABLE, LABEL_WORSE],
        dtype=torch.long,
        device=state_index.device,
    )
    return index_to_label[state_index]


def _confusion_matrix(
    predictions: Tensor, targets: Tensor, label_count: int
) -> list[list[int]]:
    matrix = torch.zeros(label_count, label_count, dtype=torch.long)
    for target, prediction in zip(targets.cpu(), predictions.cpu(), strict=True):
        matrix[int(target), int(prediction)] += 1
    return matrix.tolist()


def audit_marginal_non_identifiability(
    batch: QueryAnchorBatch,
    *,
    maximum_macro_f1: float = 0.45,
) -> dict[str, Any]:
    """Audit all visible feature marginals without cross-time pairwise matching."""

    batch.validate()
    if not 0.0 < maximum_macro_f1 < 1.0:
        raise ValueError("maximum_macro_f1 must be in (0, 1)")
    results: dict[str, dict[str, Any]] = {}
    persistent_indices = torch.nonzero(
        batch.persistent_main_mask, as_tuple=False
    ).flatten()
    persistent_labels = batch.oracle.labels[persistent_indices]
    for mode in ("current_only", "prior_current"):
        signatures = [
            _marginal_signature(batch, int(index), mode) for index in persistent_indices
        ]
        predictions, deterministic, lookup_evaluable, attack_name = (
            _repeat_supported_signature_attack(
                signatures, persistent_labels, label_count=3
            )
        )
        macro_f1 = _macro_f1(predictions, persistent_labels, label_count=3)
        results[mode] = {
            "deterministic_reconstruction_possible": deterministic,
            "best_signature_macro_f1": macro_f1,
            "signature_count": len(set(signatures)),
            "repeat_supported_lookup_evaluable": lookup_evaluable,
            "selected_repeat_supported_attack": attack_name,
        }
    signature_controls_pass = all(
        not result["deterministic_reconstruction_possible"]
        and result["best_signature_macro_f1"] <= maximum_macro_f1
        for result in results.values()
    )
    pooled_attacks: dict[str, dict[str, Any]] = {}
    kernel_bank = (
        "linear",
        "poly2",
        "poly3",
        "rbf_0.25",
        "rbf_0.5",
        "rbf_1.0",
        "rbf_2.0",
        "logsumexp_0.25",
        "logsumexp_0.5",
        "logsumexp_1.0",
        "logsumexp_2.0",
    )
    for anatomy_name, anatomy_conditioned in (
        ("state_conditioned", False),
        ("anatomy_state_conditioned", True),
    ):
        for kernel in kernel_bank:
            name = (
                f"{anatomy_name}_kernel_mean"
                if kernel == "linear"
                else f"{anatomy_name}_{kernel}"
            )
            predictions = _pooled_state_kernel_predictions(
                batch,
                persistent_indices,
                anatomy_conditioned=anatomy_conditioned,
                kernel=kernel,
            )
            macro_f1 = _macro_f1(predictions, persistent_labels, label_count=3)
            pooled_attacks[name] = {
                "kernel": kernel,
                "macro_f1": macro_f1,
                "accuracy": float((predictions == persistent_labels).float().mean()),
                "confusion_matrix": _confusion_matrix(
                    predictions, persistent_labels, label_count=3
                ),
                "passed": macro_f1 <= maximum_macro_f1,
                "uses_pair_axis": False,
                "permutation_invariant_per_side": True,
            }
    passed = signature_controls_pass and all(
        result["passed"] for result in pooled_attacks.values()
    )
    return {
        "passed": passed,
        "maximum_macro_f1": maximum_macro_f1,
        "controls": results,
        "pooled_bypass_attacks": pooled_attacks,
        "maximum_observed_macro_f1": max(
            [
                *(result["best_signature_macro_f1"] for result in results.values()),
                *(result["macro_f1"] for result in pooled_attacks.values()),
            ]
        ),
        "scope": (
            "finite preregistered persistent-three-label marginal-bypass stress "
            "suite; architecture-relative, not information-theoretic"
        ),
        "feature_channels_covered": batch.regions.prior_features.shape[-1],
    }


def audit_distractor_counterbalance(batch: QueryAnchorBatch) -> dict[str, Any]:
    """Require identical state/anatomy marginal multisets in every case."""

    batch.validate()
    signatures = [
        (
            tuple(
                sorted(
                    zip(
                        batch.regions.prior_anatomy[index].tolist(),
                        batch.prior_states[index].tolist(),
                        strict=True,
                    )
                )
            ),
            tuple(
                sorted(
                    zip(
                        batch.regions.current_anatomy[index].tolist(),
                        batch.current_states[index].tolist(),
                        strict=True,
                    )
                )
            ),
        )
        for index in range(batch.oracle.labels.shape[0])
    ]
    label_counts = torch.bincount(batch.oracle.labels, minlength=LABEL_COUNT)
    states_equal = len(set(signatures)) == 1
    labels_equal = int(torch.unique(label_counts).numel()) == 1
    return {
        "passed": states_equal and labels_equal,
        "state_anatomy_marginals_identical": states_equal,
        "label_counts_exactly_balanced": labels_equal,
        "label_counts": label_counts.tolist(),
    }


def audit_hidden_id_separation(
    batch: QueryAnchorBatch,
    *,
    validate: bool = True,
) -> dict[str, Any]:
    """Fail if model-visible IDs can bijectively reconstruct hidden gold IDs."""

    if validate:
        batch.regions.validate()
    visible = torch.cat(
        (
            batch.regions.prior_entity_ids.flatten(),
            batch.regions.current_entity_ids.flatten(),
        )
    ).cpu()
    hidden = torch.cat(
        (
            batch.oracle.prior_gold_ids.flatten(),
            batch.oracle.current_gold_ids.flatten(),
        )
    ).cpu()
    mapping: dict[int, set[int]] = {}
    reverse: dict[int, set[int]] = {}
    for visible_id, hidden_id in zip(visible.tolist(), hidden.tolist(), strict=True):
        mapping.setdefault(int(visible_id), set()).add(int(hidden_id))
        reverse.setdefault(int(hidden_id), set()).add(int(visible_id))
    hidden_from_visible_functional = all(
        len(values) == 1 for values in mapping.values()
    )
    one_to_one = hidden_from_visible_functional and all(
        len(values) == 1 for values in reverse.values()
    )
    prior_visible_values = set(batch.regions.prior_entity_ids.flatten().tolist())
    current_visible_values = set(batch.regions.current_entity_ids.flatten().tolist())
    visible_namespaces_disjoint = not bool(
        prior_visible_values & current_visible_values
    )
    equality_join_gold_links = 0
    prior_count = batch.regions.prior_features.shape[1]
    current_count = batch.regions.current_features.shape[1]
    for batch_index in range(batch.regions.prior_features.shape[0]):
        for prior_index in range(prior_count):
            for current_index in range(current_count):
                if int(batch.regions.prior_entity_ids[batch_index, prior_index]) != int(
                    batch.regions.current_entity_ids[batch_index, current_index]
                ):
                    continue
                if (
                    float(
                        batch.oracle.plan.transport[
                            batch_index, prior_index, current_index
                        ]
                    )
                    > 0.5
                ):
                    equality_join_gold_links += 1
    hidden_not_exposed = not torch.equal(visible, hidden)
    passed = (
        visible_namespaces_disjoint
        and equality_join_gold_links == 0
        and hidden_not_exposed
        and not one_to_one
    )
    return {
        "passed": passed,
        "visible_namespaces_disjoint": visible_namespaces_disjoint,
        "equality_join_gold_links": equality_join_gold_links,
        "hidden_ids_not_exposed": hidden_not_exposed,
        "hidden_from_visible_functional": hidden_from_visible_functional,
        "bijective_reconstruction_possible": one_to_one,
    }


def relabel_hidden_gold_ids(
    batch: QueryAnchorBatch,
    *,
    seed: int,
) -> QueryAnchorBatch:
    """Apply a per-case hidden-ID bijection while leaving visible data untouched."""

    batch.validate()
    generator = torch.Generator(device="cpu")
    generator.manual_seed(seed)
    prior = batch.oracle.prior_gold_ids.detach().cpu().clone()
    current = batch.oracle.current_gold_ids.detach().cpu().clone()
    for batch_index in range(prior.shape[0]):
        unique_ids = sorted(
            set(prior[batch_index].tolist()) | set(current[batch_index].tolist())
        )
        permutation = torch.randperm(len(unique_ids), generator=generator).tolist()
        replacement = {
            old_id: (batch_index + 1) * 1_000_000 + permutation[index]
            for index, old_id in enumerate(unique_ids)
        }
        prior[batch_index] = torch.tensor(
            [replacement[int(value)] for value in prior[batch_index]],
            dtype=torch.long,
        )
        current[batch_index] = torch.tensor(
            [replacement[int(value)] for value in current[batch_index]],
            dtype=torch.long,
        )
    prior = prior.to(batch.oracle.prior_gold_ids.device)
    current = current.to(batch.oracle.current_gold_ids.device)
    oracle = HiddenQueryOracle(
        prior_gold_ids=prior,
        current_gold_ids=current,
        labels=batch.oracle.labels.clone(),
        plan=_oracle_plan_from_hidden_ids(
            batch.regions,
            prior,
            current,
            mode=f"hidden_gold_relabel_seed_{seed}",
        ),
    )
    relabeled = replace(batch, oracle=oracle)
    relabeled.validate()
    return relabeled


def _bitwise_equal(left: Any, right: Any) -> bool:
    if isinstance(left, Tensor) and isinstance(right, Tensor):
        return (
            left.dtype == right.dtype
            and left.device == right.device
            and tuple(left.shape) == tuple(right.shape)
            and torch.equal(left, right)
        )
    if isinstance(left, MatchPlan) and isinstance(right, MatchPlan):
        return all(
            _bitwise_equal(getattr(left, name), getattr(right, name))
            for name in (
                "transport",
                "edge_logits",
                "prior_null_logits",
                "current_null_logits",
                "diagnostics",
            )
        )
    if isinstance(left, Mapping) and isinstance(right, Mapping):
        return set(left) == set(right) and all(
            _bitwise_equal(left[key], right[key]) for key in left
        )
    if isinstance(left, (tuple, list)) and isinstance(right, type(left)):
        return len(left) == len(right) and all(
            _bitwise_equal(a, b) for a, b in zip(left, right, strict=True)
        )
    if left is None or right is None:
        return left is right
    if isinstance(left, float) and isinstance(right, float):
        return math.isfinite(left) and math.isfinite(right) and left == right
    return left == right


def _regions_bitwise_equal(left: RegionBatch, right: RegionBatch) -> bool:
    return all(
        _bitwise_equal(getattr(left, field.name), getattr(right, field.name))
        for field in fields(RegionBatch)
    )


def audit_gold_id_relabel_invariance(
    original: QueryAnchorBatch,
    relabeled: QueryAnchorBatch,
    *,
    outputs_before: Mapping[str, Any] | None = None,
    outputs_after: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Verify plans, baseline costs and scores stay bitwise ID-relabel invariant."""

    original.validate()
    relabeled.validate()
    if (outputs_before is None) != (outputs_after is None):
        raise ValueError("both output mappings must be provided together")
    checks = {
        "hidden_ids_actually_changed": not torch.equal(
            original.oracle.prior_gold_ids, relabeled.oracle.prior_gold_ids
        )
        and not torch.equal(
            original.oracle.current_gold_ids, relabeled.oracle.current_gold_ids
        ),
        "model_visible_regions_bitwise_equal": _regions_bitwise_equal(
            original.regions, relabeled.regions
        ),
        "query_markers_bitwise_equal": torch.equal(
            original.prior_query_marker, relabeled.prior_query_marker
        )
        and torch.equal(original.current_query_marker, relabeled.current_query_marker),
        "oracle_transport_equal": torch.equal(
            original.oracle.plan.transport, relabeled.oracle.plan.transport
        ),
        "labels_equal": torch.equal(original.oracle.labels, relabeled.oracle.labels),
        "named_outputs_bitwise_equal": True,
    }
    if outputs_before is not None and outputs_after is not None:
        checks["named_outputs_bitwise_equal"] = _bitwise_equal(
            outputs_before, outputs_after
        )
    return {"passed": all(checks.values()), "checks": checks}


def require_mechanism_gate_support(
    development_labels: Tensor,
    derangement_seeds: Sequence[int],
    *,
    derangement_audit: Mapping[str, Any] | None,
    minimum_per_label: int = 24,
) -> dict[str, Any]:
    """Fail closed unless the exact crossed D=3 design and support are audited."""

    if development_labels.ndim != 1:
        raise QueryAnchorQualificationError(
            "development labels must be one-dimensional"
        )
    _require_long("development_labels", development_labels)
    if minimum_per_label <= 0:
        raise ValueError("minimum_per_label must be positive")
    seeds = tuple(int(seed) for seed in derangement_seeds)
    if len(seeds) != len(REGISTERED_DERANGEMENT_SEEDS) or set(seeds) != set(
        REGISTERED_DERANGEMENT_SEEDS
    ):
        raise QueryAnchorQualificationError(
            "NOT_EVALUABLE_DERANGEMENT_SUPPORT: mechanism gate requires the exact "
            f"registered seeds {REGISTERED_DERANGEMENT_SEEDS}"
        )
    if derangement_audit is None or derangement_audit.get("passed") is not True:
        raise QueryAnchorQualificationError(
            "NOT_EVALUABLE_DERANGEMENT_AUDIT: wrong-target, fixed-point, null-set "
            "and plan-hash checks must all pass"
        )
    if bool(((development_labels < 0) | (development_labels >= LABEL_COUNT)).any()):
        raise QueryAnchorQualificationError("development labels must be in [0, 4]")
    counts = torch.bincount(development_labels.cpu(), minlength=LABEL_COUNT)
    if bool((counts < minimum_per_label).any()):
        raise QueryAnchorQualificationError(
            "NOT_EVALUABLE_DEVELOPMENT_SUPPORT: every label is under-supported"
        )
    return {
        "status": "QUALIFIED",
        "registered_derangement_seeds": list(REGISTERED_DERANGEMENT_SEEDS),
        "derangement_count": len(REGISTERED_DERANGEMENT_SEEDS),
        "derangement_audit_passed": True,
        "minimum_per_label": minimum_per_label,
        "per_label_counts": counts.tolist(),
    }


def require_positive_recovery_denominator(delta_bind: float) -> float:
    """Recovery is undefined, rather than failed, for a nonpositive denominator."""

    if not math.isfinite(delta_bind) or delta_bind <= 0.0:
        raise QueryAnchorQualificationError(
            "NOT_EVALUABLE_RECOVERY_DENOMINATOR: Delta_bind must be positive"
        )
    return float(delta_bind)
