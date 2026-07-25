from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, fields
from functools import lru_cache
import hashlib
from itertools import permutations
import math
from typing import Any, Sequence

import torch
from torch import Tensor
import torch.nn.functional as F

from .calibration_query import (
    LABEL_IMPROVED,
    LABEL_STABLE,
    LABEL_WORSE,
    _global_assignment_similarity,
)
from .calibration_r4 import (
    fixed_concatenated_mapping,
    global_assignment_from_similarity,
    pairwise_view_cosines,
    r4_visible_hash,
)
from .schemas import MatchPlan, RegionBatch


FEATURE_DIM = 18
ANATOMY_COUNT = 2
PERSISTENT_PER_ANATOMY = 6
PERSISTENT_COUNT = ANATOMY_COUNT * PERSISTENT_PER_ANATOMY
ENDPOINT_COUNT = PERSISTENT_COUNT + ANATOMY_COUNT
IDENTITY_VIEW_SLICES = ((2, 8), (8, 14))
NULL_SUPPORT_SLICE = (14, 18)
LEARNED_FEASIBLE_VIEW_WEIGHTS = (0.95, 0.05)
FROZEN_NULL_UTILITY_CAP = 0.1
FROZEN_RESIDUAL_CAP = 0.02
SIMPLEX_OFF_DIAGONAL_COSINE = -1.0 / 5.0
FLOAT32_COSINE_ERROR_CAP = 5.0e-7

FROZEN_R5_COUNTERBALANCE_GROUPS = {
    "train": 4,
    "inner_development": 2,
    "development": 6,
}
FROZEN_R5_CHALLENGE_SPLIT_SEEDS = {
    "train": 93_501,
    "inner_development": 94_501,
    "development": 95_501,
}
FROZEN_R5_CLEAN_SPLIT_SEEDS = {
    "train": 96_501,
    "inner_development": 97_501,
    "development": 98_501,
}

_LABEL_TO_TARGET_STATE = {
    LABEL_STABLE: 1,
    LABEL_WORSE: 2,
    LABEL_IMPROVED: 0,
}
_STATE_TO_LABEL = {0.0: LABEL_STABLE, 1.0: LABEL_WORSE, -1.0: LABEL_IMPROVED}
_PERMUTATIONS_6 = torch.tensor(
    tuple(permutations(range(PERSISTENT_PER_ANATOMY))), dtype=torch.long
)


def _orthogonal_rotation(width: int, generator: torch.Generator) -> Tensor:
    matrix = torch.randn(width, width, generator=generator, dtype=torch.float64)
    orthogonal, triangular = torch.linalg.qr(matrix)
    signs = torch.diagonal(triangular).sign()
    signs[signs == 0] = 1
    return (orthogonal * signs.unsqueeze(0)).float()


def _simplex_and_null_axis() -> tuple[Tensor, Tensor]:
    identity = torch.eye(PERSISTENT_PER_ANATOMY)
    centered = identity - identity.mean(dim=0, keepdim=True)
    simplex = F.normalize(centered, dim=-1)
    null_axis = torch.full(
        (PERSISTENT_PER_ANATOMY,),
        1.0 / math.sqrt(PERSISTENT_PER_ANATOMY),
    )
    return simplex, null_axis


def _tensor_hash(*values: Tensor) -> str:
    digest = hashlib.sha256()
    for value in values:
        cpu = value.detach().cpu().contiguous()
        digest.update(str(cpu.dtype).encode("ascii"))
        digest.update(str(tuple(cpu.shape)).encode("ascii"))
        digest.update(cpu.numpy().tobytes())
    return digest.hexdigest()


@dataclass
class R5HiddenOracle:
    """Gold and frozen distractor assignments, outside matcher-visible data."""

    gold_mapping: Tensor
    distractor_mapping: Tensor
    labels: Tensor
    prelabel_group: Tensor

    def validate(self, regions: RegionBatch) -> None:
        batch = regions.prior_features.shape[0]
        expected = (batch, PERSISTENT_COUNT)
        if tuple(self.gold_mapping.shape) != expected:
            raise ValueError("gold_mapping has the wrong shape")
        if tuple(self.distractor_mapping.shape) != expected:
            raise ValueError("distractor_mapping has the wrong shape")
        if tuple(self.labels.shape) != (batch,) or tuple(self.prelabel_group.shape) != (
            batch,
        ):
            raise ValueError("labels and prelabel_group must have shape [B]")
        for name in (
            "gold_mapping",
            "distractor_mapping",
            "labels",
            "prelabel_group",
        ):
            if getattr(self, name).dtype is not torch.long:
                raise TypeError(f"{name} must be torch.long")
        if not bool(torch.isin(self.labels, self.labels.new_tensor((0, 1, 2))).all()):
            raise ValueError("R5 challenge contains only persistent labels")

        for case in range(batch):
            gold = self.gold_mapping[case]
            distractor = self.distractor_mapping[case]
            if sorted(gold.tolist()) != list(range(PERSISTENT_COUNT)):
                raise ValueError("gold_mapping must be a permutation")
            if sorted(distractor.tolist()) != list(range(PERSISTENT_COUNT)):
                raise ValueError("distractor_mapping must be a permutation")
            if bool((gold == distractor).any()):
                raise ValueError("frozen distractor must be disjoint from gold")
            for anatomy in range(ANATOMY_COUNT):
                priors = torch.nonzero(regions.prior_anatomy[case] == anatomy).flatten()
                targets = distractor[priors]
                if not bool((regions.current_anatomy[case, targets] == anatomy).all()):
                    raise ValueError("distractor mapping crosses anatomy support")

        nuisance_groups = torch.div(self.prelabel_group, 3, rounding_mode="floor")
        for group in nuisance_groups.unique().tolist():
            cases = torch.nonzero(nuisance_groups == group).flatten()
            reference = self.distractor_mapping[int(cases[0])]
            if not all(
                torch.equal(reference, self.distractor_mapping[int(case)])
                for case in cases[1:]
            ):
                raise ValueError("distractor mapping must be frozen before labels")


@dataclass
class R5ChallengeBatch:
    """Anti-equivalence fixture with label-independent frozen view 2."""

    regions: RegionBatch
    oracle: R5HiddenOracle

    def validate(self) -> None:
        self.regions.validate()
        batch, prior_count, feature_dim = self.regions.prior_features.shape
        current_count = self.regions.current_features.shape[1]
        if (prior_count, current_count, feature_dim) != (
            PERSISTENT_COUNT,
            PERSISTENT_COUNT,
            FEATURE_DIM,
        ):
            raise ValueError("R5 challenge requires [B, 12, 18] features per side")
        if not bool(
            self.regions.prior_valid.all() and self.regions.current_valid.all()
        ):
            raise ValueError("R5 challenge endpoints must all be valid")
        if not torch.equal(
            self.regions.prior_entity_ids,
            torch.full_like(self.regions.prior_entity_ids, -1),
        ) or not torch.equal(
            self.regions.current_entity_ids,
            torch.full_like(self.regions.current_entity_ids, -2),
        ):
            raise ValueError("visible entity IDs must remain side-only sentinels")
        if not torch.equal(
            self.regions.prior_features[..., 0].sum(dim=-1), torch.ones(batch)
        ) or bool((self.regions.current_features[..., 0] != 0).any()):
            raise ValueError("challenge must expose one prior-side query marker")
        if bool(
            (self.regions.prior_features[..., slice(*NULL_SUPPORT_SLICE)] != 0).any()
            or (
                self.regions.current_features[..., slice(*NULL_SUPPORT_SLICE)] != 0
            ).any()
        ):
            raise ValueError("challenge null-support channels must be zero")
        for start, stop in IDENTITY_VIEW_SLICES:
            prior_norm = self.regions.prior_features[..., start:stop].norm(dim=-1)
            current_norm = self.regions.current_features[..., start:stop].norm(dim=-1)
            if not torch.allclose(prior_norm, torch.ones_like(prior_norm), atol=1e-6):
                raise ValueError("prior challenge identities must have unit norm")
            if not torch.allclose(
                current_norm, torch.ones_like(current_norm), atol=1e-6
            ):
                raise ValueError("current challenge identities must have unit norm")
        self.oracle.validate(self.regions)


@dataclass
class R5CleanHiddenOracle:
    """Gold five-label partial assignment, never exposed to the matcher."""

    plan: MatchPlan
    labels: Tensor
    prelabel_group: Tensor

    def validate(self, regions: RegionBatch) -> None:
        batch, prior_count, _ = regions.prior_features.shape
        current_count = regions.current_features.shape[1]
        if (prior_count, current_count) != (ENDPOINT_COUNT, ENDPOINT_COUNT):
            raise ValueError("R5 clean requires fourteen endpoints per side")
        if tuple(self.labels.shape) != (batch,):
            raise ValueError("labels must have shape [B]")
        if tuple(self.prelabel_group.shape) != (batch,):
            raise ValueError("prelabel_group must have shape [B]")
        if (
            self.labels.dtype is not torch.long
            or self.prelabel_group.dtype is not torch.long
        ):
            raise TypeError("clean labels and prelabel_group must be torch.long")
        if not bool(torch.isin(self.labels, self.labels.new_tensor(range(5))).all()):
            raise ValueError("R5 clean labels must be in [0, 4]")

        self.plan.validate_hard(regions)
        real = self.plan.transport[:, :prior_count, :current_count]
        death = self.plan.transport[:, :prior_count, current_count]
        birth = self.plan.transport[:, prior_count, :current_count]
        if not torch.equal(
            real.sum(dim=(-2, -1)), torch.full((batch,), float(PERSISTENT_COUNT))
        ):
            raise ValueError("each clean case must contain twelve persistent matches")
        if not torch.equal(death.sum(dim=-1), torch.full((batch,), 2.0)):
            raise ValueError("each clean case must contain two deaths")
        if not torch.equal(birth.sum(dim=-1), torch.full((batch,), 2.0)):
            raise ValueError("each clean case must contain two births")


@dataclass
class R5CleanBatch:
    """Clean two-view fixture with a strictly separated partial assignment."""

    regions: RegionBatch
    oracle: R5CleanHiddenOracle

    @property
    def prior_query_marker(self) -> Tensor:
        return self.regions.prior_features[..., 0].bool()

    @property
    def current_query_marker(self) -> Tensor:
        return self.regions.current_features[..., 0].bool()

    @property
    def prior_states(self) -> Tensor:
        return self.regions.prior_features[..., 1]

    @property
    def current_states(self) -> Tensor:
        return self.regions.current_features[..., 1]

    @property
    def persistent_main_mask(self) -> Tensor:
        return self.oracle.labels <= LABEL_IMPROVED

    def validate(self) -> None:
        self.regions.validate()
        batch, prior_count, feature_dim = self.regions.prior_features.shape
        current_count = self.regions.current_features.shape[1]
        if (prior_count, current_count, feature_dim) != (
            ENDPOINT_COUNT,
            ENDPOINT_COUNT,
            FEATURE_DIM,
        ):
            raise ValueError("R5 clean requires [B, 14, 18] features per side")
        if not bool(
            self.regions.prior_valid.all() and self.regions.current_valid.all()
        ):
            raise ValueError("R5 clean endpoints must all be valid")
        if not torch.equal(
            self.regions.prior_entity_ids,
            torch.full_like(self.regions.prior_entity_ids, -1),
        ) or not torch.equal(
            self.regions.current_entity_ids,
            torch.full_like(self.regions.current_entity_ids, -2),
        ):
            raise ValueError("visible entity IDs must remain side-only sentinels")

        marker_count = self.prior_query_marker.sum(
            dim=-1
        ) + self.current_query_marker.sum(dim=-1)
        if not torch.equal(marker_count, torch.ones(batch, dtype=torch.long)):
            raise ValueError("each clean case must expose exactly one query marker")

        null_start, null_stop = NULL_SUPPORT_SLICE
        prior_support = self.regions.prior_features[..., null_start:null_stop]
        current_support = self.regions.current_features[..., null_start:null_stop]
        prior_null = prior_support.abs().sum(dim=-1) > 0
        current_null = current_support.abs().sum(dim=-1) > 0
        if not bool(
            (prior_null.sum(dim=-1) == ANATOMY_COUNT).all()
            and (current_null.sum(dim=-1) == ANATOMY_COUNT).all()
        ):
            raise ValueError("each side must expose one null endpoint per anatomy")
        if not bool(
            (prior_support[..., 2:] == 0).all()
            and (current_support[..., :2] == 0).all()
            and (prior_support.sum(dim=(-2, -1)) == 2).all()
            and (current_support.sum(dim=(-2, -1)) == 2).all()
        ):
            raise ValueError("14:18 must encode directional two-sided null support")

        for start, stop in IDENTITY_VIEW_SLICES:
            prior_norm = self.regions.prior_features[..., start:stop].norm(dim=-1)
            current_norm = self.regions.current_features[..., start:stop].norm(dim=-1)
            if not torch.allclose(prior_norm, torch.ones_like(prior_norm), atol=1e-6):
                raise ValueError("all prior identity-view vectors must have unit norm")
            if not torch.allclose(
                current_norm, torch.ones_like(current_norm), atol=1e-6
            ):
                raise ValueError(
                    "all current identity-view vectors must have unit norm"
                )
        self.oracle.validate(self.regions)


def _partial_plan(
    regions: RegionBatch, gold_mapping: Tensor, current_birth: Tensor
) -> MatchPlan:
    batch, prior_count, _ = regions.prior_features.shape
    current_count = regions.current_features.shape[1]
    transport = regions.prior_features.new_zeros(
        (batch, prior_count + 1, current_count + 1)
    )
    for case in range(batch):
        for prior in range(prior_count):
            target = int(gold_mapping[case, prior])
            transport[case, prior, target] = 1
        transport[case, prior_count, current_birth[case]] = 1
    plan = MatchPlan(transport=transport, mode="r5_clean_hidden_oracle")
    plan.validate_hard(regions)
    return plan


def make_r5_clean_batch(
    *, counterbalance_groups: int = 2, seed: int = 96_501
) -> R5CleanBatch:
    """Build a balanced five-label clean fixture with robust null separation."""

    if counterbalance_groups <= 0:
        raise ValueError("counterbalance_groups must be positive")
    generator = torch.Generator(device="cpu").manual_seed(seed)
    simplex, null_axis = _simplex_and_null_axis()
    anatomy_template = torch.tensor([0] * 6 + [1] * 6 + [0, 1])
    state_template = torch.tensor([-1.0, -1.0, 0.0, 0.0, 1.0, 1.0] * 2 + [0.0, 0.0])

    prior_rows: list[Tensor] = []
    current_rows: list[Tensor] = []
    prior_anatomy_rows: list[Tensor] = []
    current_anatomy_rows: list[Tensor] = []
    gold_rows: list[Tensor] = []
    birth_rows: list[Tensor] = []
    labels: list[int] = []
    prelabel_groups: list[int] = []

    for nuisance_group in range(counterbalance_groups):
        rotations = tuple(
            tuple(_orthogonal_rotation(6, generator) for _ in IDENTITY_VIEW_SLICES)
            for _ in range(ANATOMY_COUNT)
        )
        prior_permutation = torch.randperm(ENDPOINT_COUNT, generator=generator)
        current_permutation = torch.randperm(ENDPOINT_COUNT, generator=generator)
        inverse_current = torch.empty_like(current_permutation)
        inverse_current[current_permutation] = torch.arange(ENDPOINT_COUNT)

        for query_identity in range(3):
            for label in range(5):
                prior = torch.zeros(ENDPOINT_COUNT, FEATURE_DIM)
                current = torch.zeros(ENDPOINT_COUNT, FEATURE_DIM)
                current[:, 1] = state_template
                prior[12, 14] = 1
                prior[13, 15] = 1
                current[12, 16] = 1
                current[13, 17] = 1
                gold_original = torch.full(
                    (ENDPOINT_COUNT,), ENDPOINT_COUNT, dtype=torch.long
                )

                for anatomy in range(ANATOMY_COUNT):
                    offset = anatomy * PERSISTENT_PER_ANATOMY
                    if anatomy == 0 and label <= LABEL_IMPROVED:
                        target_state = _LABEL_TO_TARGET_STATE[label]
                        shift = (target_state - query_identity) % 3
                    elif anatomy == 0:
                        shift = (nuisance_group - query_identity) % 3
                    else:
                        shift = nuisance_group % 3
                    query_to_state = tuple((query + shift) % 3 for query in range(3))
                    for query in range(3):
                        gold_original[offset + query] = (
                            offset + 2 * query_to_state[query]
                        )
                    for state in range(3):
                        gold_original[offset + 3 + state] = offset + 2 * state + 1

                    null_index = PERSISTENT_COUNT + anatomy
                    for view_index, (start, stop) in enumerate(IDENTITY_VIEW_SLICES):
                        rotation = rotations[anatomy][view_index]
                        identities = simplex @ rotation
                        prior[offset : offset + 6, start:stop] = identities
                        for source in range(PERSISTENT_PER_ANATOMY):
                            target = int(gold_original[offset + source])
                            current[target, start:stop] = identities[source]
                        prior[null_index, start:stop] = null_axis @ rotation
                        current[null_index, start:stop] = -(null_axis @ rotation)

                if label == 3:
                    current[12, 0] = 1
                elif label == 4:
                    prior[12, 0] = 1
                else:
                    prior[query_identity, 0] = 1

                gold_visible = torch.full(
                    (ENDPOINT_COUNT,), ENDPOINT_COUNT, dtype=torch.long
                )
                for visible_prior, original_prior in enumerate(
                    prior_permutation.tolist()
                ):
                    target = int(gold_original[original_prior])
                    if target < ENDPOINT_COUNT:
                        gold_visible[visible_prior] = inverse_current[target]

                prior_rows.append(prior[prior_permutation])
                current_rows.append(current[current_permutation])
                prior_anatomy_rows.append(anatomy_template[prior_permutation])
                current_anatomy_rows.append(anatomy_template[current_permutation])
                gold_rows.append(gold_visible)
                birth_rows.append(inverse_current[torch.tensor([12, 13])])
                labels.append(label)
                prelabel_groups.append(nuisance_group * 3 + query_identity)

    batch_size = len(labels)
    regions = RegionBatch(
        prior_features=torch.stack(prior_rows),
        current_features=torch.stack(current_rows),
        prior_valid=torch.ones(batch_size, ENDPOINT_COUNT, dtype=torch.bool),
        current_valid=torch.ones(batch_size, ENDPOINT_COUNT, dtype=torch.bool),
        prior_anatomy=torch.stack(prior_anatomy_rows),
        current_anatomy=torch.stack(current_anatomy_rows),
        prior_entity_ids=torch.full((batch_size, ENDPOINT_COUNT), -1, dtype=torch.long),
        current_entity_ids=torch.full(
            (batch_size, ENDPOINT_COUNT), -2, dtype=torch.long
        ),
    )
    result = R5CleanBatch(
        regions=regions,
        oracle=R5CleanHiddenOracle(
            plan=_partial_plan(
                regions, torch.stack(gold_rows), torch.stack(birth_rows)
            ),
            labels=torch.tensor(labels, dtype=torch.long),
            prelabel_group=torch.tensor(prelabel_groups, dtype=torch.long),
        ),
    )
    result.validate()
    if not torch.equal(
        decode_r5_clean_query_labels(result, result.oracle.plan), result.oracle.labels
    ):
        raise RuntimeError("R5 clean generator produced inconsistent query labels")
    return result


def make_frozen_r5_clean_split(split: str) -> R5CleanBatch:
    if split not in FROZEN_R5_COUNTERBALANCE_GROUPS:
        choices = ", ".join(FROZEN_R5_COUNTERBALANCE_GROUPS)
        raise ValueError(f"split must be one of: {choices}")
    return make_r5_clean_batch(
        counterbalance_groups=FROZEN_R5_COUNTERBALANCE_GROUPS[split],
        seed=FROZEN_R5_CLEAN_SPLIT_SEEDS[split],
    )


def make_r5_anti_equivalence_challenge(
    *, counterbalance_groups: int = 2, seed: int = 93_501
) -> R5ChallengeBatch:
    """Build a challenge whose distractor view is frozen before labels.

    Within each anatomy, view 2 maps the three query-role prior rows to the
    three guard-role current columns and the guard-role prior rows to cyclically
    shifted query-role current columns.  This cross-role permutation is fixed
    before the query/label loop and is disjoint from every possible gold map.
    """

    if counterbalance_groups <= 0:
        raise ValueError("counterbalance_groups must be positive")
    generator = torch.Generator(device="cpu").manual_seed(seed)
    state_template = torch.tensor([-1.0, -1.0, 0.0, 0.0, 1.0, 1.0] * 2)
    anatomy_template = torch.tensor([0] * 6 + [1] * 6, dtype=torch.long)

    prior_rows: list[Tensor] = []
    current_rows: list[Tensor] = []
    prior_anatomy_rows: list[Tensor] = []
    current_anatomy_rows: list[Tensor] = []
    gold_rows: list[Tensor] = []
    distractor_rows: list[Tensor] = []
    labels: list[int] = []
    prelabel_groups: list[int] = []

    for nuisance_group in range(counterbalance_groups):
        rotations = tuple(
            tuple(_orthogonal_rotation(6, generator) for _ in IDENTITY_VIEW_SLICES)
            for _ in range(ANATOMY_COUNT)
        )
        prior_permutation = torch.randperm(PERSISTENT_COUNT, generator=generator)
        current_permutation = torch.randperm(PERSISTENT_COUNT, generator=generator)
        inverse_current = torch.empty_like(current_permutation)
        inverse_current[current_permutation] = torch.arange(PERSISTENT_COUNT)

        distractor_original = torch.empty(PERSISTENT_COUNT, dtype=torch.long)
        for anatomy in range(ANATOMY_COUNT):
            offset = anatomy * PERSISTENT_PER_ANATOMY
            for query_role in range(3):
                distractor_original[offset + query_role] = offset + 2 * query_role + 1
            for guard_role in range(3):
                distractor_original[offset + 3 + guard_role] = offset + 2 * (
                    (guard_role + 1) % 3
                )
        distractor_visible = inverse_current[distractor_original[prior_permutation]]
        visible_prior_anatomy = anatomy_template[prior_permutation]

        for query_identity in range(3):
            for label in (LABEL_STABLE, LABEL_WORSE, LABEL_IMPROVED):
                prior = torch.zeros(PERSISTENT_COUNT, FEATURE_DIM)
                current = torch.zeros(PERSISTENT_COUNT, FEATURE_DIM)
                current[:, 1] = state_template
                prior[query_identity, 0] = 1
                gold_original = torch.empty(PERSISTENT_COUNT, dtype=torch.long)

                for anatomy in range(ANATOMY_COUNT):
                    offset = anatomy * PERSISTENT_PER_ANATOMY
                    if anatomy == 0:
                        target_state = _LABEL_TO_TARGET_STATE[label]
                        shift = (target_state - query_identity) % 3
                    else:
                        shift = nuisance_group % 3
                    query_to_state = tuple((query + shift) % 3 for query in range(3))
                    similarity = _global_assignment_similarity(query_to_state).float()
                    start, stop = IDENTITY_VIEW_SLICES[0]
                    rotation = rotations[anatomy][0]
                    prior[offset : offset + 6, start:stop] = rotation
                    current[offset : offset + 6, start:stop] = (
                        similarity.T / math.sqrt(122.0)
                    ) @ rotation
                    for query_role in range(3):
                        gold_original[offset + query_role] = (
                            offset + 2 * query_to_state[query_role]
                        )
                    for state in range(3):
                        gold_original[offset + 3 + state] = offset + 2 * state + 1

                prior_visible = prior[prior_permutation]
                current_visible = current[current_permutation]
                start, stop = IDENTITY_VIEW_SLICES[1]
                for anatomy in range(ANATOMY_COUNT):
                    prior_indices = torch.nonzero(
                        visible_prior_anatomy == anatomy
                    ).flatten()
                    rotation = rotations[anatomy][1]
                    prior_visible[prior_indices, start:stop] = rotation
                    for local_index, prior_index in enumerate(prior_indices.tolist()):
                        target = int(distractor_visible[prior_index])
                        current_visible[target, start:stop] = rotation[local_index]

                prior_rows.append(prior_visible)
                current_rows.append(current_visible)
                prior_anatomy_rows.append(visible_prior_anatomy)
                current_anatomy_rows.append(anatomy_template[current_permutation])
                gold_rows.append(inverse_current[gold_original[prior_permutation]])
                distractor_rows.append(distractor_visible.clone())
                labels.append(label)
                prelabel_groups.append(nuisance_group * 3 + query_identity)

    batch_size = len(labels)
    result = R5ChallengeBatch(
        regions=RegionBatch(
            prior_features=torch.stack(prior_rows),
            current_features=torch.stack(current_rows),
            prior_valid=torch.ones(batch_size, PERSISTENT_COUNT, dtype=torch.bool),
            current_valid=torch.ones(batch_size, PERSISTENT_COUNT, dtype=torch.bool),
            prior_anatomy=torch.stack(prior_anatomy_rows),
            current_anatomy=torch.stack(current_anatomy_rows),
            prior_entity_ids=torch.full(
                (batch_size, PERSISTENT_COUNT), -1, dtype=torch.long
            ),
            current_entity_ids=torch.full(
                (batch_size, PERSISTENT_COUNT), -2, dtype=torch.long
            ),
        ),
        oracle=R5HiddenOracle(
            gold_mapping=torch.stack(gold_rows),
            distractor_mapping=torch.stack(distractor_rows),
            labels=torch.tensor(labels, dtype=torch.long),
            prelabel_group=torch.tensor(prelabel_groups, dtype=torch.long),
        ),
    )
    result.validate()
    return result


def make_frozen_r5_challenge_split(split: str) -> R5ChallengeBatch:
    if split not in FROZEN_R5_COUNTERBALANCE_GROUPS:
        choices = ", ".join(FROZEN_R5_COUNTERBALANCE_GROUPS)
        raise ValueError(f"split must be one of: {choices}")
    return make_r5_anti_equivalence_challenge(
        counterbalance_groups=FROZEN_R5_COUNTERBALANCE_GROUPS[split],
        seed=FROZEN_R5_CHALLENGE_SPLIT_SEEDS[split],
    )


def weighted_global_mapping(
    batch: R5ChallengeBatch, view_weights: Sequence[float]
) -> tuple[Tensor, Tensor]:
    batch.validate()
    weights = torch.tensor(
        tuple(view_weights), dtype=batch.regions.prior_features.dtype
    )
    if tuple(weights.shape) != (len(IDENTITY_VIEW_SLICES),):
        raise ValueError("one weight is required per identity view")
    if not bool(torch.isfinite(weights).all()) or bool((weights < 0).any()):
        raise ValueError("view weights must be finite and non-negative")
    if float(weights.sum()) <= 0:
        raise ValueError("view weights must have positive total")
    weights = weights / weights.sum()
    utilities = pairwise_view_cosines(batch.regions)
    combined = (utilities * weights.view(1, -1, 1, 1)).sum(dim=1)
    return global_assignment_from_similarity(combined, batch.regions), combined


def decode_query_labels(batch: R5ChallengeBatch, mapping: Tensor) -> Tensor:
    predictions = []
    for case in range(mapping.shape[0]):
        query = int(torch.nonzero(batch.regions.prior_features[case, :, 0] == 1).item())
        target = int(mapping[case, query])
        state = float(batch.regions.current_features[case, target, 1])
        predictions.append(_STATE_TO_LABEL[state])
    return torch.tensor(predictions, dtype=torch.long)


def challenge_oracle_plan(batch: R5ChallengeBatch) -> MatchPlan:
    batch.validate()
    batch_size = batch.oracle.gold_mapping.shape[0]
    transport = batch.regions.prior_features.new_zeros(
        (batch_size, PERSISTENT_COUNT + 1, PERSISTENT_COUNT + 1)
    )
    rows = torch.arange(PERSISTENT_COUNT)
    for case in range(batch_size):
        transport[case, rows, batch.oracle.gold_mapping[case]] = 1
    plan = MatchPlan(transport=transport, mode="r5_challenge_hidden_oracle")
    plan.validate_hard(batch.regions)
    return plan


def decode_r5_clean_query_labels(batch: R5CleanBatch, plan: MatchPlan) -> Tensor:
    batch.validate()
    plan.validate_hard(batch.regions)
    prior_count = batch.regions.prior_features.shape[1]
    current_count = batch.regions.current_features.shape[1]
    predictions = []
    for case in range(batch.oracle.labels.shape[0]):
        prior_hits = torch.nonzero(batch.prior_query_marker[case]).flatten()
        current_hits = torch.nonzero(batch.current_query_marker[case]).flatten()
        if len(current_hits) == 1:
            current = int(current_hits.item())
            if float(plan.transport[case, prior_count, current]) != 1.0:
                raise ValueError("current-side query must be a hard birth")
            predictions.append(3)
            continue
        if len(prior_hits) != 1:
            raise ValueError("clean query marker must select one endpoint")
        prior = int(prior_hits.item())
        if float(plan.transport[case, prior, current_count]) == 1.0:
            predictions.append(4)
            continue
        targets = torch.nonzero(
            plan.transport[case, prior, :current_count] == 1
        ).flatten()
        if len(targets) != 1:
            raise ValueError("persistent query must have one real match")
        state = float(batch.current_states[case, int(targets.item())])
        predictions.append(_STATE_TO_LABEL[state])
    return torch.tensor(predictions, dtype=torch.long)


@lru_cache(maxsize=1)
def enumerate_r5_clean_assignment_certificate() -> dict[str, Any]:
    """Exhaust one canonical anatomy block over every partial bijection.

    The two identity views have the same cosine matrix, so all simplex view
    weights reduce to this matrix.  Null utilities are independent scalars in
    ``[-cap, cap]`` and the residual has one shared coefficient in
    ``[-residual_cap, residual_cap]``.  Taking the adverse sign of both terms
    for each competitor gives a conservative lower bound valid everywhere in
    the frozen parameter box.
    """

    size = PERSISTENT_PER_ANATOMY + 1
    cosine = [[0.0 for _ in range(size)] for _ in range(size)]
    for prior in range(PERSISTENT_PER_ANATOMY):
        for current in range(PERSISTENT_PER_ANATOMY):
            cosine[prior][current] = (
                1.0 if prior == current else SIMPLEX_OFF_DIAGONAL_COSINE
            )
    cosine[-1][-1] = -1.0

    gold_base = float(PERSISTENT_PER_ANATOMY)
    gold_tanh = PERSISTENT_PER_ANATOMY * math.tanh(1.0)
    gold_pairs = tuple((index, index) for index in range(PERSISTENT_PER_ANATOMY))
    minimum = math.inf
    minimum_competitor: tuple[tuple[int, int], ...] = ()
    assignment_count = 0
    selected: list[tuple[int, int]] = []

    def visit(
        prior: int, available: tuple[int, ...], base: float, tanh_sum: float
    ) -> None:
        nonlocal assignment_count, minimum, minimum_competitor
        if prior == size:
            assignment_count += 1
            pairs = tuple(selected)
            if pairs == gold_pairs:
                return
            matched = len(pairs)
            robust_gap = (
                gold_base
                - base
                - FROZEN_RESIDUAL_CAP * abs(gold_tanh - tanh_sum)
                - 2.0 * FROZEN_NULL_UTILITY_CAP * abs(matched - PERSISTENT_PER_ANATOMY)
            )
            if robust_gap < minimum:
                minimum = robust_gap
                minimum_competitor = pairs
            return

        visit(prior + 1, available, base, tanh_sum)
        for position, current in enumerate(available):
            value = cosine[prior][current]
            selected.append((prior, current))
            visit(
                prior + 1,
                available[:position] + available[position + 1 :],
                base + value,
                tanh_sum + math.tanh(value),
            )
            selected.pop()

    visit(0, tuple(range(size)), 0.0, 0.0)
    numerical_deduction = (
        (2 * PERSISTENT_PER_ANATOMY + 1)
        * (1.0 + FROZEN_RESIDUAL_CAP)
        * FLOAT32_COSINE_ERROR_CAP
    )
    certified_minimum = minimum - numerical_deduction
    return {
        "passed": certified_minimum > 0,
        "anatomy_constrained": True,
        "view_weight_domain": "two-view probability simplex",
        "views_have_identical_cosine_matrix": True,
        "null_utility_cap": FROZEN_NULL_UTILITY_CAP,
        "residual_cap": FROZEN_RESIDUAL_CAP,
        "partial_assignments_enumerated": assignment_count,
        "gold_real_edges_per_anatomy": PERSISTENT_PER_ANATOMY,
        "analytic_minimum_gap_before_numerical_deduction": minimum,
        "float32_cosine_error_cap_per_edge": FLOAT32_COSINE_ERROR_CAP,
        "float32_worst_case_gap_deduction": numerical_deduction,
        "minimum_robust_gap_lower_bound_per_anatomy": certified_minimum,
        "minimum_competitor_pairs": [list(pair) for pair in minimum_competitor],
        "full_case_lower_bound": certified_minimum,
    }


def _side_signature(
    batch: R5CleanBatch, case: int, side: str, *, ignore_query_marker: bool
) -> str:
    if side == "prior":
        features = batch.regions.prior_features[case].clone()
        valid = batch.regions.prior_valid[case]
        anatomy = batch.regions.prior_anatomy[case]
        entity_ids = batch.regions.prior_entity_ids[case]
    elif side == "current":
        features = batch.regions.current_features[case].clone()
        valid = batch.regions.current_valid[case]
        anatomy = batch.regions.current_anatomy[case]
        entity_ids = batch.regions.current_entity_ids[case]
    else:
        raise ValueError("side must be prior or current")
    if ignore_query_marker:
        features[:, 0] = 0
    return _tensor_hash(features, valid, anatomy, entity_ids)


def _balanced_one_sided_audit(
    batch: R5CleanBatch,
    side: str,
    labels: Sequence[int],
    *,
    ignore_query_marker: bool,
) -> dict[str, Any]:
    label_tuple = tuple(int(label) for label in labels)
    signatures = {
        label: Counter(
            _side_signature(batch, case, side, ignore_query_marker=ignore_query_marker)
            for case in torch.nonzero(batch.oracle.labels == label).flatten().tolist()
        )
        for label in label_tuple
    }
    exact = all(
        signatures[label] == signatures[label_tuple[0]] for label in label_tuple[1:]
    )
    all_signatures = set().union(*(set(value) for value in signatures.values()))
    correct = sum(
        max(signatures[label][signature] for label in label_tuple)
        for signature in all_signatures
    )
    total = sum(int((batch.oracle.labels == label).sum()) for label in label_tuple)
    upper_bound = correct / total
    expected = 1.0 / len(label_tuple)
    return {
        "passed": exact and abs(upper_bound - expected) < 1e-12,
        "scope": "single_side_no_pair_axis",
        "pair_axis_used": False,
        "labels": list(label_tuple),
        "query_marker_removed": ignore_query_marker,
        "exact_signature_counts_per_label": exact,
        "deterministic_signature_accuracy_upper_bound": upper_bound,
    }


def r5_clean_hidden_oracle_hash(oracle: R5CleanHiddenOracle) -> str:
    return _tensor_hash(oracle.plan.transport, oracle.labels, oracle.prelabel_group)


def audit_r5_clean(batch: R5CleanBatch) -> dict[str, Any]:
    batch.validate()
    utilities = pairwise_view_cosines(batch.regions, view_slices=IDENTITY_VIEW_SLICES)
    prior_count = batch.regions.prior_features.shape[1]
    current_count = batch.regions.current_features.shape[1]
    real = batch.oracle.plan.transport[:, :prior_count, :current_count].bool()
    death = batch.oracle.plan.transport[:, :prior_count, current_count].bool()
    birth = batch.oracle.plan.transport[:, prior_count, :current_count].bool()
    persistent_gold = [
        float(utilities[:, view].masked_select(real).min()) for view in range(2)
    ]

    prior_null = death
    current_null = birth
    null_null_values = []
    persistent_null_values = []
    maximum_ideal_cosine_errors = []
    anatomy_support = batch.regions.prior_anatomy.unsqueeze(
        -1
    ) == batch.regions.current_anatomy.unsqueeze(-2)
    for view in range(2):
        view_utility = utilities[:, view]
        null_null = prior_null.unsqueeze(-1) & current_null.unsqueeze(-2)
        cross = (prior_null.unsqueeze(-1) ^ current_null.unsqueeze(-2)) & (
            anatomy_support
        )
        null_null_values.append(float(view_utility.masked_select(null_null).max()))
        persistent_null_values.append(
            float(view_utility.masked_select(cross).abs().max())
        )
        ideal = torch.full_like(view_utility, SIMPLEX_OFF_DIAGONAL_COSINE)
        ideal.masked_fill_(real, 1.0)
        ideal.masked_fill_(cross, 0.0)
        ideal.masked_fill_(null_null & anatomy_support, -1.0)
        maximum_ideal_cosine_errors.append(
            float((view_utility - ideal).abs().masked_select(anatomy_support).max())
        )

    decoded = decode_r5_clean_query_labels(batch, batch.oracle.plan)
    label_counts = torch.bincount(batch.oracle.labels, minlength=5)
    five_label_marginals = {
        side: _balanced_one_sided_audit(batch, side, range(5), ignore_query_marker=True)
        for side in ("prior", "current")
    }
    persistent_marginals = {
        side: _balanced_one_sided_audit(
            batch,
            side,
            (LABEL_STABLE, LABEL_WORSE, LABEL_IMPROVED),
            ignore_query_marker=False,
        )
        for side in ("prior", "current")
    }
    certificate = enumerate_r5_clean_assignment_certificate()
    geometry_passed = bool(
        all(abs(value - 1.0) < 1e-6 for value in persistent_gold)
        and all(abs(value + 1.0) < 1e-6 for value in null_null_values)
        and all(value < 1e-6 for value in persistent_null_values)
        and all(
            value <= FLOAT32_COSINE_ERROR_CAP for value in maximum_ideal_cosine_errors
        )
    )
    return {
        "passed": bool(
            geometry_passed
            and certificate["passed"]
            and torch.equal(decoded, batch.oracle.labels)
            and bool((label_counts == label_counts[0]).all())
            and all(value["passed"] for value in five_label_marginals.values())
            and all(value["passed"] for value in persistent_marginals.values())
        ),
        "feature_contract": {
            "feature_dim": FEATURE_DIM,
            "identity_view_slices": [list(value) for value in IDENTITY_VIEW_SLICES],
            "null_support_slice": list(NULL_SUPPORT_SLICE),
            "query_state_excluded_from_matcher_views": True,
        },
        "two_sided_partial_assignment": {
            "persistent_per_case": real.sum(dim=(-2, -1)).unique().tolist(),
            "deaths_per_case": death.sum(dim=-1).unique().tolist(),
            "births_per_case": birth.sum(dim=-1).unique().tolist(),
        },
        "identity_geometry": {
            "passed": geometry_passed,
            "gold_cosines_by_view": persistent_gold,
            "null_null_cosines_by_view": null_null_values,
            "maximum_absolute_persistent_null_cosine_by_view": persistent_null_values,
            "maximum_ideal_cosine_error_by_view": maximum_ideal_cosine_errors,
            "frozen_float32_cosine_error_cap": FLOAT32_COSINE_ERROR_CAP,
            "simplex_off_diagonal_cosine": SIMPLEX_OFF_DIAGONAL_COSINE,
        },
        "assignment_certificate": certificate,
        "five_label_query": {
            "passed": torch.equal(decoded, batch.oracle.labels),
            "label_counts": label_counts.tolist(),
        },
        "one_sided_marginals": {
            "all_five_without_query_marker": five_label_marginals,
            "persistent_three_with_query_marker": persistent_marginals,
        },
        "hashes": {
            "visible": r4_visible_hash(batch.regions),
            "hidden_oracle": r5_clean_hidden_oracle_hash(batch.oracle),
        },
    }


def _challenge_side_signature(batch: R5ChallengeBatch, case: int, side: str) -> str:
    if side == "prior":
        return _tensor_hash(
            batch.regions.prior_features[case],
            batch.regions.prior_valid[case],
            batch.regions.prior_anatomy[case],
            batch.regions.prior_entity_ids[case],
        )
    if side == "current":
        return _tensor_hash(
            batch.regions.current_features[case],
            batch.regions.current_valid[case],
            batch.regions.current_anatomy[case],
            batch.regions.current_entity_ids[case],
        )
    raise ValueError("side must be prior or current")


def _challenge_one_sided_audit(batch: R5ChallengeBatch, side: str) -> dict[str, Any]:
    signatures = {
        label: Counter(
            _challenge_side_signature(batch, case, side)
            for case in torch.nonzero(batch.oracle.labels == label).flatten().tolist()
        )
        for label in (LABEL_STABLE, LABEL_WORSE, LABEL_IMPROVED)
    }
    exact = signatures[0] == signatures[1] == signatures[2]
    all_signatures = set().union(*(set(value) for value in signatures.values()))
    correct = sum(
        max(signatures[label][signature] for label in signatures)
        for signature in all_signatures
    )
    upper_bound = correct / len(batch.oracle.labels)
    return {
        "passed": exact and abs(upper_bound - 1.0 / 3.0) < 1e-12,
        "scope": "single_side_no_pair_axis",
        "pair_axis_used": False,
        "exact_signature_counts_per_label": exact,
        "deterministic_signature_accuracy_upper_bound": upper_bound,
    }


def _query_row_argmax_state_signatures(
    batch: R5ChallengeBatch,
) -> tuple[list[tuple[tuple[float, ...], ...]], list[list[tuple[float, ...]]]]:
    utilities = pairwise_view_cosines(batch.regions)
    combined: list[tuple[tuple[float, ...], ...]] = []
    per_view: list[list[tuple[float, ...]]] = [[], []]
    for case in range(len(batch.oracle.labels)):
        query = int(torch.nonzero(batch.regions.prior_features[case, :, 0] == 1).item())
        anatomy = int(batch.regions.prior_anatomy[case, query])
        compatible = batch.regions.current_anatomy[case] == anatomy
        case_signature = []
        for view in range(len(IDENTITY_VIEW_SLICES)):
            row = utilities[case, view, query]
            maximum = row.masked_select(compatible).max()
            targets = torch.nonzero(
                compatible & torch.isclose(row, maximum, atol=1e-6, rtol=0)
            ).flatten()
            states = tuple(
                sorted(
                    float(batch.regions.current_features[case, target, 1])
                    for target in targets.tolist()
                )
            )
            per_view[view].append(states)
            case_signature.append(states)
        combined.append(tuple(case_signature))
    return combined, per_view


def _signature_independence(
    signatures: Sequence[Any], labels: Tensor
) -> dict[str, Any]:
    counts = {
        label: Counter(
            signature
            for signature, observed in zip(signatures, labels.tolist(), strict=True)
            if observed == label
        )
        for label in (LABEL_STABLE, LABEL_WORSE, LABEL_IMPROVED)
    }
    exact = counts[0] == counts[1] == counts[2]
    support = set().union(*(set(value) for value in counts.values()))
    correct = sum(
        max(counts[label][signature] for label in counts) for signature in support
    )
    upper_bound = correct / len(labels)
    return {
        "passed": exact and abs(upper_bound - 1.0 / 3.0) < 1e-12,
        "exact_signature_counts_per_label": exact,
        "deterministic_accuracy_upper_bound": upper_bound,
        "signature_count": len(support),
    }


def _macro_f1(predictions: Tensor, labels: Tensor) -> float:
    scores = []
    for label in (LABEL_STABLE, LABEL_WORSE, LABEL_IMPROVED):
        predicted = predictions == label
        gold = labels == label
        true_positive = int((predicted & gold).sum())
        false_positive = int((predicted & ~gold).sum())
        false_negative = int((~predicted & gold).sum())
        denominator = 2 * true_positive + false_positive + false_negative
        scores.append(0.0 if denominator == 0 else 2 * true_positive / denominator)
    return sum(scores) / len(scores)


def audit_r5_row_local_train_to_development_attack() -> dict[str, Any]:
    """Fit a signature lookup on train and evaluate it unchanged on development."""

    train = make_frozen_r5_challenge_split("train")
    development = make_frozen_r5_challenge_split("development")
    train_signatures, _ = _query_row_argmax_state_signatures(train)
    development_signatures, _ = _query_row_argmax_state_signatures(development)
    counts: dict[Any, Counter[int]] = {}
    for signature, label in zip(
        train_signatures, train.oracle.labels.tolist(), strict=True
    ):
        counts.setdefault(signature, Counter())[label] += 1

    unseen = [
        signature for signature in development_signatures if signature not in counts
    ]
    predictions = []
    for signature in development_signatures:
        if signature not in counts:
            predictions.append(LABEL_STABLE)
            continue
        maximum = max(counts[signature].values())
        predictions.append(
            min(label for label, count in counts[signature].items() if count == maximum)
        )
    predicted = torch.tensor(predictions, dtype=torch.long)
    accuracy = float((predicted == development.oracle.labels).float().mean())
    macro_f1 = _macro_f1(predicted, development.oracle.labels)
    return {
        "passed": bool(
            not unseen and accuracy <= 1.0 / 3.0 + 1e-7 and macro_f1 <= 1.0 / 3.0 + 1e-7
        ),
        "train_split_visible_hash": r4_visible_hash(train.regions),
        "development_split_visible_hash": r4_visible_hash(development.regions),
        "unseen_development_signature_count": len(unseen),
        "development_accuracy": accuracy,
        "development_macro_f1": macro_f1,
    }


def r5_challenge_hidden_oracle_hash(oracle: R5HiddenOracle) -> str:
    return _tensor_hash(
        oracle.gold_mapping,
        oracle.distractor_mapping,
        oracle.labels,
        oracle.prelabel_group,
    )


def _full_fixture_hash(visible_hash: str, hidden_hash: str) -> str:
    return hashlib.sha256(f"{visible_hash}:{hidden_hash}".encode("ascii")).hexdigest()


def audit_r5_challenge(batch: R5ChallengeBatch) -> dict[str, Any]:
    """Audit separation, row-local independence, and global competition."""

    batch.validate()
    utilities = pairwise_view_cosines(batch.regions)
    view1_mapping = global_assignment_from_similarity(utilities[:, 0], batch.regions)
    view2_mapping = global_assignment_from_similarity(utilities[:, 1], batch.regions)
    equal_mapping, equal_utility = weighted_global_mapping(batch, (0.5, 0.5))
    learned_mapping, learned_utility = weighted_global_mapping(
        batch, LEARNED_FEASIBLE_VIEW_WEIGHTS
    )
    concat_mapping, concat_utility = fixed_concatenated_mapping(batch)

    def mapping_rate(mapping: Tensor, target: Tensor) -> float:
        return float((mapping == target).all(dim=-1).float().mean())

    def label_rate(mapping: Tensor) -> float:
        return float(
            (decode_query_labels(batch, mapping) == batch.oracle.labels).float().mean()
        )

    prelabel_fixed = True
    for group in batch.oracle.prelabel_group.unique().tolist():
        cases = torch.nonzero(batch.oracle.prelabel_group == group).flatten()
        if len(cases) != 3 or set(batch.oracle.labels[cases].tolist()) != {0, 1, 2}:
            prelabel_fixed = False
            break
        reference = int(cases[0])
        prelabel_fixed &= all(
            torch.equal(
                batch.regions.prior_features[reference],
                batch.regions.prior_features[int(case)],
            )
            for case in cases[1:]
        )

    visible_names = {field.name for field in fields(RegionBatch)}
    forbidden = sorted(
        name
        for name in visible_names
        if any(token in name for token in ("gold", "oracle", "label", "cardinality"))
    )
    hidden_ids_absent = bool(
        batch.regions.prior_source_ids is None
        and batch.regions.current_source_ids is None
        and torch.equal(
            batch.regions.prior_entity_ids,
            torch.full_like(batch.regions.prior_entity_ids, -1),
        )
        and torch.equal(
            batch.regions.current_entity_ids,
            torch.full_like(batch.regions.current_entity_ids, -2),
        )
    )
    marginals = {
        side: _challenge_one_sided_audit(batch, side) for side in ("prior", "current")
    }

    minimum_gap = math.inf
    collision_blocks = 0
    query_ambiguous = 0
    query_gold_in_maximum = 0
    for case in range(utilities.shape[0]):
        query = int(torch.nonzero(batch.regions.prior_features[case, :, 0] == 1).item())
        for anatomy in range(ANATOMY_COUNT):
            priors = torch.nonzero(
                batch.regions.prior_anatomy[case] == anatomy
            ).flatten()
            currents = torch.nonzero(
                batch.regions.current_anatomy[case] == anatomy
            ).flatten()
            block = utilities[case, 0][priors][:, currents]
            greedy = block.argmax(dim=-1)
            collision_blocks += int(greedy.unique().numel() < PERSISTENT_PER_ANATOMY)
            objectives = block[
                torch.arange(PERSISTENT_PER_ANATOMY).unsqueeze(0), _PERMUTATIONS_6
            ].sum(dim=-1)
            best_two = torch.topk(objectives, k=2).values
            minimum_gap = min(minimum_gap, float(best_two[0] - best_two[1]))

        query_row = utilities[case, 0, query]
        support = (
            batch.regions.current_anatomy[case]
            == batch.regions.prior_anatomy[case, query]
        )
        maximum = query_row.masked_select(support).max()
        maxima = torch.nonzero(
            support & torch.isclose(query_row, maximum, atol=1e-6, rtol=0)
        ).flatten()
        states = {
            float(batch.regions.current_features[case, target, 1])
            for target in maxima.tolist()
        }
        query_ambiguous += int(states == {-1.0, 0.0, 1.0})
        query_gold_in_maximum += int(
            int(batch.oracle.gold_mapping[case, query]) in maxima
        )

    combined_signatures, per_view_signatures = _query_row_argmax_state_signatures(batch)
    row_local = {
        f"view_{view + 1}": _signature_independence(
            per_view_signatures[view], batch.oracle.labels
        )
        for view in range(len(IDENTITY_VIEW_SLICES))
    }
    row_local["combined_views"] = _signature_independence(
        combined_signatures, batch.oracle.labels
    )
    train_to_development = audit_r5_row_local_train_to_development_attack()
    expected_blocks = utilities.shape[0] * ANATOMY_COUNT
    expected_cases = utilities.shape[0]
    competition_passed = bool(
        collision_blocks == expected_blocks
        and query_ambiguous == expected_cases
        and query_gold_in_maximum == expected_cases
        and mapping_rate(view1_mapping, batch.oracle.gold_mapping) == 1.0
        and minimum_gap > 0
    )
    row_local_passed = all(value["passed"] for value in row_local.values())
    frozen_distractor_passed = bool(
        mapping_rate(view2_mapping, batch.oracle.distractor_mapping) == 1.0
        and mapping_rate(view2_mapping, batch.oracle.gold_mapping) == 0.0
        and not bool(
            (batch.oracle.distractor_mapping == batch.oracle.gold_mapping).any()
        )
    )
    visible_hash = r4_visible_hash(batch.regions)
    hidden_hash = r5_challenge_hidden_oracle_hash(batch.oracle)

    return {
        "passed": bool(
            prelabel_fixed
            and not forbidden
            and hidden_ids_absent
            and all(value["passed"] for value in marginals.values())
            and frozen_distractor_passed
            and mapping_rate(equal_mapping, batch.oracle.gold_mapping) == 0.0
            and mapping_rate(concat_mapping, batch.oracle.gold_mapping) == 0.0
            and mapping_rate(learned_mapping, batch.oracle.gold_mapping) == 1.0
            and competition_passed
            and row_local_passed
            and train_to_development["passed"]
        ),
        "feature_contract": {
            "feature_dim": FEATURE_DIM,
            "identity_view_slices": [list(value) for value in IDENTITY_VIEW_SLICES],
            "null_support_slice": list(NULL_SUPPORT_SLICE),
            "query_state_excluded_from_matcher_views": True,
        },
        "information_wall": {
            "passed": not forbidden and hidden_ids_absent,
            "forbidden_visible_schema_fields": forbidden,
            "hidden_identity_values_absent": hidden_ids_absent,
        },
        "prelabel_query": {"passed": bool(prelabel_fixed)},
        "one_sided_marginals": marginals,
        "frozen_distractor": {
            "passed": frozen_distractor_passed,
            "construction": "query-to-guard; guard-to-cyclic-query",
            "frozen_before_query_and_label_loop": True,
            "exact_distractor_mapping_rate": mapping_rate(
                view2_mapping, batch.oracle.distractor_mapping
            ),
            "gold_edge_overlap_count": int(
                (batch.oracle.distractor_mapping == batch.oracle.gold_mapping).sum()
            ),
            "query_label_accuracy": label_rate(view2_mapping),
        },
        "row_local_query_argmax_state": {
            "passed": row_local_passed,
            **row_local,
            "train_to_development_attack": train_to_development,
        },
        "global_column_competition": {
            "passed": competition_passed,
            "collision_blocks": collision_blocks,
            "total_blocks": expected_blocks,
            "query_rows_ambiguous_across_all_three_states": query_ambiguous,
            "query_rows_with_gold_among_local_maxima": query_gold_in_maximum,
            "total_query_rows": expected_cases,
            "hungarian_view1_exact_mapping_rate": mapping_rate(
                view1_mapping, batch.oracle.gold_mapping
            ),
            "minimum_best_vs_second_assignment_gap": minimum_gap,
        },
        "view_weight_utility": {
            "view1_exact_gold_mapping_rate": mapping_rate(
                view1_mapping, batch.oracle.gold_mapping
            ),
            "view2_exact_distractor_mapping_rate": mapping_rate(
                view2_mapping, batch.oracle.distractor_mapping
            ),
            "equal_weights": [0.5, 0.5],
            "equal_weight_exact_mapping_rate": mapping_rate(
                equal_mapping, batch.oracle.gold_mapping
            ),
            "equal_weight_query_label_accuracy": label_rate(equal_mapping),
            "fixed_concatenated_exact_mapping_rate": mapping_rate(
                concat_mapping, batch.oracle.gold_mapping
            ),
            "fixed_concatenated_query_label_accuracy": label_rate(concat_mapping),
            "learned_feasible_weights": list(LEARNED_FEASIBLE_VIEW_WEIGHTS),
            "learned_weight_exact_mapping_rate": mapping_rate(
                learned_mapping, batch.oracle.gold_mapping
            ),
            "learned_weight_query_label_accuracy": label_rate(learned_mapping),
            "equal_vs_concatenated_max_utility_error": float(
                (equal_utility - concat_utility).abs().max()
            ),
            "learned_vs_equal_utility_hashes": {
                "equal": _tensor_hash(equal_utility),
                "learned": _tensor_hash(learned_utility),
            },
        },
        "hashes": {
            "visible": visible_hash,
            "hidden_oracle": hidden_hash,
            "full_fixture": _full_fixture_hash(visible_hash, hidden_hash),
        },
    }


__all__ = [
    "ANATOMY_COUNT",
    "ENDPOINT_COUNT",
    "FEATURE_DIM",
    "FLOAT32_COSINE_ERROR_CAP",
    "FROZEN_NULL_UTILITY_CAP",
    "FROZEN_RESIDUAL_CAP",
    "IDENTITY_VIEW_SLICES",
    "LEARNED_FEASIBLE_VIEW_WEIGHTS",
    "NULL_SUPPORT_SLICE",
    "R5ChallengeBatch",
    "R5CleanBatch",
    "R5CleanHiddenOracle",
    "R5HiddenOracle",
    "audit_r5_challenge",
    "audit_r5_clean",
    "audit_r5_row_local_train_to_development_attack",
    "challenge_oracle_plan",
    "decode_query_labels",
    "decode_r5_clean_query_labels",
    "enumerate_r5_clean_assignment_certificate",
    "make_frozen_r5_challenge_split",
    "make_frozen_r5_clean_split",
    "make_r5_anti_equivalence_challenge",
    "make_r5_clean_batch",
    "pairwise_view_cosines",
    "r4_visible_hash",
    "r5_challenge_hidden_oracle_hash",
    "weighted_global_mapping",
]
