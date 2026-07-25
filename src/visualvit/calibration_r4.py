from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, fields
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
from .schemas import MatchPlan, RegionBatch


FEATURE_DIM = 18
ENDPOINTS_PER_ANATOMY = 6
ANATOMY_COUNT = 2
ENDPOINT_COUNT = ENDPOINTS_PER_ANATOMY * ANATOMY_COUNT
IDENTITY_VIEW_SLICES = ((2, 8), (8, 14))
NULL_SUPPORT_SLICE = (14, 18)
LEARNED_FEASIBLE_VIEW_WEIGHTS = (0.95, 0.05)

FROZEN_R4_COUNTERBALANCE_GROUPS = {
    "train": 4,
    "inner_development": 2,
    "development": 6,
}
FROZEN_R4_SPLIT_SEEDS = {
    "train": 83_401,
    "inner_development": 84_401,
    "development": 85_401,
}
FROZEN_R4_CLEAN_SPLIT_SEEDS = {
    "train": 86_401,
    "inner_development": 87_401,
    "development": 88_401,
}

_PERMUTATIONS_6 = torch.tensor(
    tuple(permutations(range(ENDPOINTS_PER_ANATOMY))), dtype=torch.long
)
_LABEL_TO_TARGET_STATE = {
    LABEL_STABLE: 1,
    LABEL_WORSE: 2,
    LABEL_IMPROVED: 0,
}
_STATE_TO_LABEL = {0.0: LABEL_STABLE, 1.0: LABEL_WORSE, -1.0: LABEL_IMPROVED}


def _orthogonal_rotation(width: int, generator: torch.Generator) -> Tensor:
    matrix = torch.randn(width, width, generator=generator, dtype=torch.float64)
    orthogonal, triangular = torch.linalg.qr(matrix)
    signs = torch.diagonal(triangular).sign()
    signs[signs == 0] = 1
    return (orthogonal * signs.unsqueeze(0)).float()


def _tensor_hash(*values: Tensor) -> str:
    digest = hashlib.sha256()
    for value in values:
        cpu = value.detach().cpu().contiguous()
        digest.update(str(cpu.dtype).encode("ascii"))
        digest.update(str(tuple(cpu.shape)).encode("ascii"))
        digest.update(cpu.numpy().tobytes())
    return digest.hexdigest()


@dataclass
class R4HiddenOracle:
    """Gold-only assignments and design indices, outside matcher-visible data."""

    gold_mapping: Tensor
    cyclic_mapping: Tensor
    labels: Tensor
    prelabel_group: Tensor

    def validate(self, regions: RegionBatch) -> None:
        batch = regions.prior_features.shape[0]
        expected_mapping_shape = (batch, ENDPOINT_COUNT)
        if tuple(self.gold_mapping.shape) != expected_mapping_shape:
            raise ValueError("gold_mapping has the wrong shape")
        if tuple(self.cyclic_mapping.shape) != expected_mapping_shape:
            raise ValueError("cyclic_mapping has the wrong shape")
        if tuple(self.labels.shape) != (batch,):
            raise ValueError("labels must have shape [B]")
        if tuple(self.prelabel_group.shape) != (batch,):
            raise ValueError("prelabel_group must have shape [B]")
        for name in ("gold_mapping", "cyclic_mapping", "labels", "prelabel_group"):
            if getattr(self, name).dtype is not torch.long:
                raise TypeError(f"{name} must be torch.long")
        if not bool(torch.isin(self.labels, self.labels.new_tensor((0, 1, 2))).all()):
            raise ValueError("R4 challenge contains only stable/worse/improved")

        for case in range(batch):
            gold = self.gold_mapping[case]
            cyclic = self.cyclic_mapping[case]
            if sorted(gold.tolist()) != list(range(ENDPOINT_COUNT)):
                raise ValueError("gold_mapping must be a permutation")
            if sorted(cyclic.tolist()) != list(range(ENDPOINT_COUNT)):
                raise ValueError("cyclic_mapping must be a permutation")
            prior_anatomy = regions.prior_anatomy[case]
            current_anatomy = regions.current_anatomy[case]
            for anatomy in range(ANATOMY_COUNT):
                prior_indices = torch.nonzero(prior_anatomy == anatomy).flatten()
                expected = gold[prior_indices.roll(-1)]
                if not torch.equal(cyclic[prior_indices], expected):
                    raise ValueError("view-2 mapping must be a within-anatomy 6-cycle")
                if not torch.equal(
                    current_anatomy[cyclic[prior_indices]],
                    torch.full_like(prior_indices, anatomy),
                ):
                    raise ValueError("cyclic mapping crosses anatomy support")
            query = int(torch.nonzero(regions.prior_features[case, :, 0] == 1).item())
            target = int(gold[query])
            state = float(regions.current_features[case, target, 1])
            if _STATE_TO_LABEL.get(state) != int(self.labels[case]):
                raise ValueError("gold query transition disagrees with its label")


@dataclass
class R4ChallengeBatch:
    """R4 anti-equivalence fixture with an explicit visible/oracle wall."""

    regions: RegionBatch
    oracle: R4HiddenOracle

    def validate(self) -> None:
        self.regions.validate()
        batch, prior_count, feature_dim = self.regions.prior_features.shape
        current_count = self.regions.current_features.shape[1]
        if (prior_count, current_count, feature_dim) != (
            ENDPOINT_COUNT,
            ENDPOINT_COUNT,
            FEATURE_DIM,
        ):
            raise ValueError("R4 challenge requires [B, 12, 18] features per side")
        if not bool(
            self.regions.prior_valid.all() and self.regions.current_valid.all()
        ):
            raise ValueError("R4 challenge endpoints must all be valid")
        if not torch.equal(
            self.regions.prior_entity_ids,
            torch.full_like(self.regions.prior_entity_ids, -1),
        ) or not torch.equal(
            self.regions.current_entity_ids,
            torch.full_like(self.regions.current_entity_ids, -2),
        ):
            raise ValueError("visible entity IDs must remain side-only sentinels")
        marker_count = self.regions.prior_features[..., 0].sum(dim=-1)
        if not torch.equal(marker_count, torch.ones(batch)):
            raise ValueError("each case must expose one fixed prior query marker")
        if bool((self.regions.current_features[..., 0] != 0).any()):
            raise ValueError("the challenge query must be on the prior side")
        null_start, null_stop = NULL_SUPPORT_SLICE
        if bool(
            (self.regions.prior_features[..., null_start:null_stop] != 0).any()
            or (self.regions.current_features[..., null_start:null_stop] != 0).any()
        ):
            raise ValueError("reserved null-support channels must be zero")
        for start, stop in IDENTITY_VIEW_SLICES:
            prior_norm = self.regions.prior_features[..., start:stop].norm(dim=-1)
            current_norm = self.regions.current_features[..., start:stop].norm(dim=-1)
            if not torch.allclose(prior_norm, torch.ones_like(prior_norm), atol=1e-6):
                raise ValueError("prior identity-view vectors must have unit norm")
            if not torch.allclose(
                current_norm, torch.ones_like(current_norm), atol=1e-6
            ):
                raise ValueError("current identity-view vectors must have unit norm")
        self.oracle.validate(self.regions)


@dataclass
class R4CleanHiddenOracle:
    """Gold five-label partial assignment, isolated from clean visible inputs."""

    plan: MatchPlan
    labels: Tensor
    prelabel_group: Tensor

    def validate(self, regions: RegionBatch) -> None:
        batch, prior_count, _ = regions.prior_features.shape
        current_count = regions.current_features.shape[1]
        if (prior_count, current_count) != (14, 14):
            raise ValueError("R4 clean requires fourteen endpoints per side")
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
            raise ValueError("R4 clean labels must be in [0, 4]")
        self.plan.validate_hard(regions)
        real = self.plan.transport[:, :prior_count, :current_count]
        death = self.plan.transport[:, :prior_count, current_count]
        birth = self.plan.transport[:, prior_count, :current_count]
        if not torch.equal(real.sum(dim=(-2, -1)), torch.full((batch,), 12.0)):
            raise ValueError("each clean case must contain twelve persistent matches")
        if not torch.equal(death.sum(dim=-1), torch.full((batch,), 2.0)):
            raise ValueError("each clean case must contain two deaths")
        if not torch.equal(birth.sum(dim=-1), torch.full((batch,), 2.0)):
            raise ValueError("each clean case must contain two births")


@dataclass
class R4CleanBatch:
    """Two-view clean fixture sharing the challenge matcher's 18-D interface."""

    regions: RegionBatch
    oracle: R4CleanHiddenOracle

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

    @property
    def null_control_mask(self) -> Tensor:
        return self.oracle.labels >= 3

    def validate(self) -> None:
        self.regions.validate()
        batch, prior_count, feature_dim = self.regions.prior_features.shape
        current_count = self.regions.current_features.shape[1]
        if (prior_count, current_count, feature_dim) != (14, 14, FEATURE_DIM):
            raise ValueError("R4 clean requires [B, 14, 18] features per side")
        if not bool(
            self.regions.prior_valid.all() and self.regions.current_valid.all()
        ):
            raise ValueError("R4 clean endpoints must all be valid")
        if not torch.equal(
            self.regions.prior_entity_ids,
            torch.full_like(self.regions.prior_entity_ids, -1),
        ) or not torch.equal(
            self.regions.current_entity_ids,
            torch.full_like(self.regions.current_entity_ids, -2),
        ):
            raise ValueError("visible entity IDs must remain side-only sentinels")
        marker_count = self.regions.prior_features[..., 0].sum(
            dim=-1
        ) + self.regions.current_features[..., 0].sum(dim=-1)
        if not torch.equal(marker_count, torch.ones(batch)):
            raise ValueError("each clean case must expose exactly one query marker")

        null_start, null_stop = NULL_SUPPORT_SLICE
        prior_null = self.regions.prior_features[..., null_start:null_stop]
        current_null = self.regions.current_features[..., null_start:null_stop]
        expected_prior = torch.zeros_like(prior_null)
        expected_current = torch.zeros_like(current_null)
        for case in range(batch):
            anatomy0_prior = int(
                torch.nonzero(
                    (self.regions.prior_anatomy[case] == 0)
                    & (self.regions.prior_features[case, :, 14] == 1)
                ).item()
            )
            anatomy1_prior = int(
                torch.nonzero(
                    (self.regions.prior_anatomy[case] == 1)
                    & (self.regions.prior_features[case, :, 15] == 1)
                ).item()
            )
            anatomy0_current = int(
                torch.nonzero(
                    (self.regions.current_anatomy[case] == 0)
                    & (self.regions.current_features[case, :, 16] == 1)
                ).item()
            )
            anatomy1_current = int(
                torch.nonzero(
                    (self.regions.current_anatomy[case] == 1)
                    & (self.regions.current_features[case, :, 17] == 1)
                ).item()
            )
            expected_prior[case, anatomy0_prior, 0] = 1
            expected_prior[case, anatomy1_prior, 1] = 1
            expected_current[case, anatomy0_current, 2] = 1
            expected_current[case, anatomy1_current, 3] = 1
        if not torch.equal(prior_null, expected_prior) or not torch.equal(
            current_null, expected_current
        ):
            raise ValueError(
                "14:18 must encode directional anatomy-specific null support"
            )

        null_rows_prior = prior_null.sum(dim=-1) > 0
        null_rows_current = current_null.sum(dim=-1) > 0
        for start, stop in IDENTITY_VIEW_SLICES:
            prior_norm = self.regions.prior_features[..., start:stop].norm(dim=-1)
            current_norm = self.regions.current_features[..., start:stop].norm(dim=-1)
            if not torch.allclose(
                prior_norm.masked_select(~null_rows_prior),
                torch.ones_like(prior_norm.masked_select(~null_rows_prior)),
                atol=1e-6,
            ) or not torch.allclose(
                current_norm.masked_select(~null_rows_current),
                torch.ones_like(current_norm.masked_select(~null_rows_current)),
                atol=1e-6,
            ):
                raise ValueError(
                    "persistent clean identity-view vectors must have unit norm"
                )
            if bool(
                (prior_norm.masked_select(null_rows_prior) != 0).any()
                or (current_norm.masked_select(null_rows_current) != 0).any()
            ):
                raise ValueError(
                    "clean null endpoints must be neutral in identity views"
                )
        self.oracle.validate(self.regions)


def _partial_plan_from_mapping(
    regions: RegionBatch, gold_mapping: Tensor, current_birth: Tensor, *, mode: str
) -> MatchPlan:
    batch, prior_count, _ = regions.prior_features.shape
    current_count = regions.current_features.shape[1]
    transport = regions.prior_features.new_zeros(
        (batch, prior_count + 1, current_count + 1)
    )
    for case in range(batch):
        for prior in range(prior_count):
            target = int(gold_mapping[case, prior])
            if target == current_count:
                transport[case, prior, current_count] = 1
            else:
                transport[case, prior, target] = 1
        transport[case, prior_count, current_birth[case]] = 1
    plan = MatchPlan(transport=transport, mode=mode)
    plan.validate_hard(regions)
    return plan


def make_r4_anti_equivalence_challenge(
    *, counterbalance_groups: int = 2, seed: int = 83_401
) -> R4ChallengeBatch:
    """Build a balanced two-view challenge where fixed view equivalence fails.

    View 1 is the R2 global-assignment gadget.  View 2 realizes a strong
    within-anatomy cyclic derangement.  Every nuisance group contains all three
    pre-label query identities, so each one-sided visible signature occurs with
    every persistent label even though the cross-time relation identifies it.
    """

    if counterbalance_groups <= 0:
        raise ValueError("counterbalance_groups must be positive")
    generator = torch.Generator(device="cpu").manual_seed(seed)
    current_state_template = torch.tensor(
        [-1.0, -1.0, 0.0, 0.0, 1.0, 1.0] * ANATOMY_COUNT
    )
    anatomy_template = torch.tensor(
        [anatomy for anatomy in range(ANATOMY_COUNT) for _ in range(6)],
        dtype=torch.long,
    )

    prior_rows: list[Tensor] = []
    current_rows: list[Tensor] = []
    prior_anatomy_rows: list[Tensor] = []
    current_anatomy_rows: list[Tensor] = []
    gold_rows: list[Tensor] = []
    cyclic_rows: list[Tensor] = []
    labels: list[int] = []
    prelabel_groups: list[int] = []

    for nuisance_group in range(counterbalance_groups):
        rotations = tuple(
            tuple(_orthogonal_rotation(6, generator) for _ in range(2))
            for _ in range(ANATOMY_COUNT)
        )
        prior_permutation = torch.randperm(ENDPOINT_COUNT, generator=generator)
        current_permutation = torch.randperm(ENDPOINT_COUNT, generator=generator)
        inverse_current = torch.empty_like(current_permutation)
        inverse_current[current_permutation] = torch.arange(ENDPOINT_COUNT)

        # query_identity is selected before the label loop and is unchanged
        # across the three labels sharing a prelabel_group.
        for query_identity in range(3):
            for label in (LABEL_STABLE, LABEL_WORSE, LABEL_IMPROVED):
                prior = torch.zeros(ENDPOINT_COUNT, FEATURE_DIM)
                current = torch.zeros(ENDPOINT_COUNT, FEATURE_DIM)
                prior[:, 1] = 0.0
                current[:, 1] = current_state_template
                prior[query_identity, 0] = 1.0

                gold_original = torch.empty(ENDPOINT_COUNT, dtype=torch.long)
                for anatomy in range(ANATOMY_COUNT):
                    offset = anatomy * ENDPOINTS_PER_ANATOMY
                    if anatomy == 0:
                        target_state = _LABEL_TO_TARGET_STATE[label]
                        shift = (target_state - query_identity) % 3
                    else:
                        shift = nuisance_group % 3
                    query_to_state = tuple((query + shift) % 3 for query in range(3))
                    similarity = _global_assignment_similarity(query_to_state).float()

                    view1_start, view1_stop = IDENTITY_VIEW_SLICES[0]
                    view1_rotation = rotations[anatomy][0]
                    prior[offset : offset + 6, view1_start:view1_stop] = view1_rotation
                    current[offset : offset + 6, view1_start:view1_stop] = (
                        similarity.T / math.sqrt(122.0)
                    ) @ view1_rotation
                    for query in range(3):
                        gold_original[offset + query] = (
                            offset + 2 * query_to_state[query]
                        )
                    for state in range(3):
                        gold_original[offset + 3 + state] = offset + 2 * state + 1

                gold_visible = inverse_current[gold_original[prior_permutation]]
                cyclic_visible = torch.empty_like(gold_visible)
                visible_prior_anatomy = anatomy_template[prior_permutation]
                for anatomy in range(ANATOMY_COUNT):
                    visible_indices = torch.nonzero(
                        visible_prior_anatomy == anatomy
                    ).flatten()
                    cyclic_visible[visible_indices] = gold_visible[
                        visible_indices.roll(-1)
                    ]

                # Build view 2 directly in visible row order.  Its cosine-one
                # edges are exactly the registered cyclic derangement.
                view2_start, view2_stop = IDENTITY_VIEW_SLICES[1]
                prior_visible = prior[prior_permutation]
                current_visible = current[current_permutation]
                for anatomy in range(ANATOMY_COUNT):
                    prior_indices = torch.nonzero(
                        visible_prior_anatomy == anatomy
                    ).flatten()
                    rotation = rotations[anatomy][1]
                    prior_visible[prior_indices, view2_start:view2_stop] = rotation
                    for local_index, prior_index in enumerate(prior_indices.tolist()):
                        target = int(cyclic_visible[prior_index])
                        current_visible[target, view2_start:view2_stop] = rotation[
                            local_index
                        ]

                prior_rows.append(prior_visible)
                current_rows.append(current_visible)
                prior_anatomy_rows.append(visible_prior_anatomy)
                current_anatomy_rows.append(anatomy_template[current_permutation])
                gold_rows.append(gold_visible)
                cyclic_rows.append(cyclic_visible)
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
    result = R4ChallengeBatch(
        regions=regions,
        oracle=R4HiddenOracle(
            gold_mapping=torch.stack(gold_rows),
            cyclic_mapping=torch.stack(cyclic_rows),
            labels=torch.tensor(labels, dtype=torch.long),
            prelabel_group=torch.tensor(prelabel_groups, dtype=torch.long),
        ),
    )
    result.validate()
    return result


def make_frozen_r4_challenge_split(split: str) -> R4ChallengeBatch:
    if split not in FROZEN_R4_COUNTERBALANCE_GROUPS:
        choices = ", ".join(FROZEN_R4_COUNTERBALANCE_GROUPS)
        raise ValueError(f"split must be one of: {choices}")
    return make_r4_anti_equivalence_challenge(
        counterbalance_groups=FROZEN_R4_COUNTERBALANCE_GROUPS[split],
        seed=FROZEN_R4_SPLIT_SEEDS[split],
    )


def make_r4_clean_batch(
    *, counterbalance_groups: int = 2, seed: int = 86_401
) -> R4CleanBatch:
    """Build the five-label clean fixture with two semantically aligned views."""

    if counterbalance_groups <= 0:
        raise ValueError("counterbalance_groups must be positive")
    generator = torch.Generator(device="cpu").manual_seed(seed)
    anatomy_template = torch.tensor([0] * 6 + [1] * 6 + [0, 1])
    current_state_template = torch.tensor(
        [-1.0, -1.0, 0.0, 0.0, 1.0, 1.0] * 2 + [0.0, 0.0]
    )
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
            tuple(_orthogonal_rotation(6, generator) for _ in range(2))
            for _ in range(ANATOMY_COUNT)
        )
        prior_permutation = torch.randperm(14, generator=generator)
        current_permutation = torch.randperm(14, generator=generator)
        inverse_current = torch.empty_like(current_permutation)
        inverse_current[current_permutation] = torch.arange(14)

        # The persistent query identity is fixed outside the label loop.  The
        # new/resolved controls necessarily move the visible marker to the
        # registered birth/death carrier and stay outside the persistent gate.
        for query_identity in range(3):
            for label in range(5):
                prior = torch.zeros(14, FEATURE_DIM)
                current = torch.zeros(14, FEATURE_DIM)
                current[:, 1] = current_state_template
                prior[12, 14] = 1.0
                prior[13, 15] = 1.0
                current[12, 16] = 1.0
                current[13, 17] = 1.0

                gold_original = torch.full((14,), 14, dtype=torch.long)
                for anatomy in range(ANATOMY_COUNT):
                    offset = anatomy * 6
                    if anatomy == 0 and label <= LABEL_IMPROVED:
                        target_state = _LABEL_TO_TARGET_STATE[label]
                        shift = (target_state - query_identity) % 3
                    elif anatomy == 0:
                        shift = (nuisance_group - query_identity) % 3
                    else:
                        shift = nuisance_group % 3
                    query_to_state = tuple((query + shift) % 3 for query in range(3))
                    similarity = _global_assignment_similarity(query_to_state).float()
                    for view_index, (start, stop) in enumerate(IDENTITY_VIEW_SLICES):
                        rotation = rotations[anatomy][view_index]
                        prior[offset : offset + 6, start:stop] = rotation
                        current[offset : offset + 6, start:stop] = (
                            similarity.T / math.sqrt(122.0)
                        ) @ rotation
                    for query in range(3):
                        gold_original[offset + query] = (
                            offset + 2 * query_to_state[query]
                        )
                    for state in range(3):
                        gold_original[offset + 3 + state] = offset + 2 * state + 1

                if label == 3:
                    current[12, 0] = 1.0
                elif label == 4:
                    prior[12, 0] = 1.0
                else:
                    prior[query_identity, 0] = 1.0

                gold_visible = torch.full((14,), 14, dtype=torch.long)
                for visible_prior, original_prior in enumerate(
                    prior_permutation.tolist()
                ):
                    original_target = int(gold_original[original_prior])
                    if original_target < 14:
                        gold_visible[visible_prior] = inverse_current[original_target]
                birth_visible = inverse_current[torch.tensor([12, 13])]

                prior_rows.append(prior[prior_permutation])
                current_rows.append(current[current_permutation])
                prior_anatomy_rows.append(anatomy_template[prior_permutation])
                current_anatomy_rows.append(anatomy_template[current_permutation])
                gold_rows.append(gold_visible)
                birth_rows.append(birth_visible)
                labels.append(label)
                prelabel_groups.append(nuisance_group * 3 + query_identity)

    batch_size = len(labels)
    regions = RegionBatch(
        prior_features=torch.stack(prior_rows),
        current_features=torch.stack(current_rows),
        prior_valid=torch.ones(batch_size, 14, dtype=torch.bool),
        current_valid=torch.ones(batch_size, 14, dtype=torch.bool),
        prior_anatomy=torch.stack(prior_anatomy_rows),
        current_anatomy=torch.stack(current_anatomy_rows),
        prior_entity_ids=torch.full((batch_size, 14), -1, dtype=torch.long),
        current_entity_ids=torch.full((batch_size, 14), -2, dtype=torch.long),
    )
    gold_mapping = torch.stack(gold_rows)
    current_birth = torch.stack(birth_rows)
    result = R4CleanBatch(
        regions=regions,
        oracle=R4CleanHiddenOracle(
            plan=_partial_plan_from_mapping(
                regions, gold_mapping, current_birth, mode="r4_clean_hidden_oracle"
            ),
            labels=torch.tensor(labels, dtype=torch.long),
            prelabel_group=torch.tensor(prelabel_groups, dtype=torch.long),
        ),
    )
    result.validate()
    decoded = decode_clean_query_labels(result, result.oracle.plan)
    if not torch.equal(decoded, result.oracle.labels):
        raise RuntimeError("R4 clean generator produced an inconsistent query label")
    return result


def make_frozen_r4_clean_split(split: str) -> R4CleanBatch:
    if split not in FROZEN_R4_COUNTERBALANCE_GROUPS:
        choices = ", ".join(FROZEN_R4_COUNTERBALANCE_GROUPS)
        raise ValueError(f"split must be one of: {choices}")
    return make_r4_clean_batch(
        counterbalance_groups=FROZEN_R4_COUNTERBALANCE_GROUPS[split],
        seed=FROZEN_R4_CLEAN_SPLIT_SEEDS[split],
    )


def pairwise_view_cosines(
    regions: RegionBatch,
    *,
    view_slices: Sequence[tuple[int, int]] = IDENTITY_VIEW_SLICES,
) -> Tensor:
    """Return anatomy-masked per-view cosine utilities [B, V, Rp, Rc]."""

    regions.validate()
    utilities = []
    for start, stop in view_slices:
        prior = F.normalize(regions.prior_features[..., start:stop], dim=-1)
        current = F.normalize(regions.current_features[..., start:stop], dim=-1)
        utilities.append(torch.einsum("bid,bjd->bij", prior, current))
    result = torch.stack(utilities, dim=1)
    support = regions.prior_anatomy.unsqueeze(-1) == regions.current_anatomy.unsqueeze(
        -2
    )
    return result.masked_fill(~support.unsqueeze(1), -1_000.0)


def global_assignment_from_similarity(
    similarity: Tensor, regions: RegionBatch
) -> Tensor:
    """Solve each six-endpoint anatomy block by exact permutation enumeration."""

    batch, prior_count, current_count = similarity.shape
    if (prior_count, current_count) != (ENDPOINT_COUNT, ENDPOINT_COUNT):
        raise ValueError("R4 assignment requires a [B, 12, 12] similarity tensor")
    mappings = torch.empty(batch, ENDPOINT_COUNT, dtype=torch.long)
    permutations6 = _PERMUTATIONS_6.to(similarity.device)
    local_rows = torch.arange(ENDPOINTS_PER_ANATOMY, device=similarity.device)
    for case in range(batch):
        for anatomy in range(ANATOMY_COUNT):
            prior_indices = torch.nonzero(
                regions.prior_anatomy[case] == anatomy
            ).flatten()
            current_indices = torch.nonzero(
                regions.current_anatomy[case] == anatomy
            ).flatten()
            block = similarity[case][prior_indices][:, current_indices]
            objectives = block[local_rows, permutations6].sum(dim=-1)
            best = permutations6[int(objectives.argmax())]
            mappings[case, prior_indices.cpu()] = current_indices[best].cpu()
    return mappings


def weighted_global_mapping(
    batch: R4ChallengeBatch, view_weights: Sequence[float]
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


def fixed_concatenated_mapping(batch: R4ChallengeBatch) -> tuple[Tensor, Tensor]:
    """Evaluate the fixed concatenated-cosine baseline over both identity views."""

    features = []
    for side in (batch.regions.prior_features, batch.regions.current_features):
        features.append(
            torch.cat(
                [side[..., start:stop] for start, stop in IDENTITY_VIEW_SLICES], dim=-1
            )
        )
    prior, current = (F.normalize(value, dim=-1) for value in features)
    similarity = torch.einsum("bid,bjd->bij", prior, current)
    support = batch.regions.prior_anatomy.unsqueeze(
        -1
    ) == batch.regions.current_anatomy.unsqueeze(-2)
    similarity = similarity.masked_fill(~support, -1_000.0)
    return global_assignment_from_similarity(similarity, batch.regions), similarity


def decode_query_labels(batch: R4ChallengeBatch, mapping: Tensor) -> Tensor:
    predictions = []
    for case in range(mapping.shape[0]):
        query = int(torch.nonzero(batch.regions.prior_features[case, :, 0] == 1).item())
        target = int(mapping[case, query])
        state = float(batch.regions.current_features[case, target, 1])
        predictions.append(_STATE_TO_LABEL[state])
    return torch.tensor(predictions, dtype=torch.long)


def challenge_oracle_plan(batch: R4ChallengeBatch) -> MatchPlan:
    batch.validate()
    current_birth = torch.zeros(
        (batch.oracle.gold_mapping.shape[0], 0), dtype=torch.long
    )
    return _partial_plan_from_mapping(
        batch.regions,
        batch.oracle.gold_mapping,
        current_birth,
        mode="r4_challenge_hidden_oracle",
    )


def decode_clean_query_labels(batch: R4CleanBatch, plan: MatchPlan) -> Tensor:
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
                raise ValueError("current-side clean query must be a hard birth")
            predictions.append(3)
            continue
        if len(prior_hits) != 1:
            raise ValueError("clean query marker must select exactly one endpoint")
        prior = int(prior_hits.item())
        if float(plan.transport[case, prior, current_count]) == 1.0:
            predictions.append(4)
            continue
        targets = torch.nonzero(
            plan.transport[case, prior, :current_count] == 1
        ).flatten()
        if len(targets) != 1:
            raise ValueError("persistent clean query must have one hard real match")
        state = float(batch.current_states[case, int(targets.item())])
        predictions.append(_STATE_TO_LABEL[state])
    return torch.tensor(predictions, dtype=torch.long)


def _side_signature(regions: RegionBatch, case: int, side: str) -> str:
    if side == "prior":
        return _tensor_hash(
            regions.prior_features[case],
            regions.prior_valid[case],
            regions.prior_anatomy[case],
            regions.prior_entity_ids[case],
        )
    if side == "current":
        return _tensor_hash(
            regions.current_features[case],
            regions.current_valid[case],
            regions.current_anatomy[case],
            regions.current_entity_ids[case],
        )
    raise ValueError("side must be prior or current")


def r4_visible_hash(regions: RegionBatch) -> str:
    """Hash only tensors admitted through the registered visible interface."""

    return _tensor_hash(
        regions.prior_features,
        regions.current_features,
        regions.prior_valid,
        regions.current_valid,
        regions.prior_anatomy,
        regions.current_anatomy,
        regions.prior_entity_ids,
        regions.current_entity_ids,
    )


def r4_hidden_oracle_hash(oracle: R4HiddenOracle) -> str:
    return _tensor_hash(
        oracle.gold_mapping,
        oracle.cyclic_mapping,
        oracle.labels,
        oracle.prelabel_group,
    )


def r4_clean_hidden_oracle_hash(oracle: R4CleanHiddenOracle) -> str:
    return _tensor_hash(
        oracle.plan.transport,
        oracle.labels,
        oracle.prelabel_group,
    )


def _clean_side_signature(
    batch: R4CleanBatch, case: int, side: str, *, ignore_query_marker: bool
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


def _clean_balanced_signature_audit(
    batch: R4CleanBatch,
    side: str,
    labels: Sequence[int],
    *,
    ignore_query_marker: bool,
) -> dict[str, Any]:
    label_tuple = tuple(int(label) for label in labels)
    signatures = {
        label: Counter(
            _clean_side_signature(
                batch, case, side, ignore_query_marker=ignore_query_marker
            )
            for case in torch.nonzero(batch.oracle.labels == label).flatten().tolist()
        )
        for label in label_tuple
    }
    exact = all(
        signatures[label] == signatures[label_tuple[0]] for label in label_tuple[1:]
    )
    all_signatures = set().union(*(set(counts) for counts in signatures.values()))
    correct = sum(
        max(signatures[label][signature] for label in label_tuple)
        for signature in all_signatures
    )
    upper_bound = correct / sum(
        len(counts)
        for counts in (
            torch.nonzero(batch.oracle.labels == label).flatten()
            for label in label_tuple
        )
    )
    expected = 1.0 / len(label_tuple)
    return {
        "passed": exact and abs(upper_bound - expected) < 1e-12,
        "labels": list(label_tuple),
        "query_marker_removed": ignore_query_marker,
        "exact_signature_counts_per_label": exact,
        "deterministic_signature_accuracy_upper_bound": upper_bound,
        "signature_multiset_hashes": {
            str(label): hashlib.sha256(
                repr(sorted(signatures[label].items())).encode("ascii")
            ).hexdigest()
            for label in label_tuple
        },
    }


def _clean_persistent_mapping(batch: R4CleanBatch, similarity: Tensor) -> Tensor:
    batch_size = similarity.shape[0]
    mapping = torch.full((batch_size, 14), 14, dtype=torch.long)
    null_start, null_stop = NULL_SUPPORT_SLICE
    prior_is_null = (
        batch.regions.prior_features[..., null_start:null_stop].abs().sum(dim=-1) > 0
    )
    current_is_null = (
        batch.regions.current_features[..., null_start:null_stop].abs().sum(dim=-1) > 0
    )
    permutations6 = _PERMUTATIONS_6.to(similarity.device)
    local_rows = torch.arange(6, device=similarity.device)
    for case in range(batch_size):
        for anatomy in range(ANATOMY_COUNT):
            priors = torch.nonzero(
                (batch.regions.prior_anatomy[case] == anatomy) & ~prior_is_null[case]
            ).flatten()
            currents = torch.nonzero(
                (batch.regions.current_anatomy[case] == anatomy)
                & ~current_is_null[case]
            ).flatten()
            block = similarity[case][priors][:, currents]
            objective = block[local_rows, permutations6].sum(dim=-1)
            selected = permutations6[int(objective.argmax())]
            mapping[case, priors.cpu()] = currents[selected].cpu()
    return mapping


def _one_sided_audit(batch: R4ChallengeBatch, side: str) -> dict[str, Any]:
    signatures_by_label = {
        label: Counter(
            _side_signature(batch.regions, case, side)
            for case in torch.nonzero(batch.oracle.labels == label).flatten().tolist()
        )
        for label in (LABEL_STABLE, LABEL_WORSE, LABEL_IMPROVED)
    }
    exact = all(
        signatures_by_label[label] == signatures_by_label[LABEL_STABLE]
        for label in (LABEL_WORSE, LABEL_IMPROVED)
    )
    all_signatures = set().union(
        *(set(counts) for counts in signatures_by_label.values())
    )
    correct = sum(
        max(signatures_by_label[label][signature] for label in signatures_by_label)
        for signature in all_signatures
    )
    accuracy = correct / len(batch.oracle.labels)
    return {
        "passed": exact and abs(accuracy - 1.0 / 3.0) < 1e-12,
        "exact_signature_counts_per_label": exact,
        "deterministic_signature_accuracy_upper_bound": accuracy,
        "unique_signature_count": len(all_signatures),
        "signature_multiset_hashes": {
            str(label): hashlib.sha256(
                repr(sorted(signatures_by_label[label].items())).encode("ascii")
            ).hexdigest()
            for label in signatures_by_label
        },
    }


def audit_r4_challenge(batch: R4ChallengeBatch) -> dict[str, Any]:
    """Return the registered analytic separation, information wall, and hashes."""

    batch.validate()
    view_utilities = pairwise_view_cosines(batch.regions)
    view1_mapping = global_assignment_from_similarity(
        view_utilities[:, 0], batch.regions
    )
    view2_mapping = global_assignment_from_similarity(
        view_utilities[:, 1], batch.regions
    )
    equal_mapping, equal_utility = weighted_global_mapping(batch, (0.5, 0.5))
    learned_mapping, learned_utility = weighted_global_mapping(
        batch, LEARNED_FEASIBLE_VIEW_WEIGHTS
    )
    concat_mapping, concat_utility = fixed_concatenated_mapping(batch)
    gold = batch.oracle.gold_mapping

    prelabel_fixed = True
    for group in batch.oracle.prelabel_group.unique().tolist():
        cases = torch.nonzero(batch.oracle.prelabel_group == group).flatten()
        if len(cases) != 3 or set(batch.oracle.labels[cases].tolist()) != {0, 1, 2}:
            prelabel_fixed = False
            break
        reference = int(cases[0])
        for case_tensor in cases[1:]:
            case = int(case_tensor)
            prelabel_fixed &= torch.equal(
                batch.regions.prior_features[reference],
                batch.regions.prior_features[case],
            )

    visible_field_names = {field.name for field in fields(RegionBatch)}
    forbidden = sorted(
        name
        for name in visible_field_names
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

    def mapping_rate(mapping: Tensor) -> float:
        return float((mapping == gold).all(dim=-1).float().mean())

    def label_rate(mapping: Tensor) -> float:
        return float(
            (decode_query_labels(batch, mapping) == batch.oracle.labels).float().mean()
        )

    return {
        "passed": bool(
            prelabel_fixed
            and not forbidden
            and hidden_ids_absent
            and mapping_rate(view1_mapping) == 1.0
            and mapping_rate(view2_mapping) == 0.0
            and mapping_rate(equal_mapping) == 0.0
            and mapping_rate(concat_mapping) == 0.0
            and mapping_rate(learned_mapping) == 1.0
            and _one_sided_audit(batch, "prior")["passed"]
            and _one_sided_audit(batch, "current")["passed"]
        ),
        "feature_contract": {
            "feature_dim": FEATURE_DIM,
            "identity_view_slices": [list(value) for value in IDENTITY_VIEW_SLICES],
            "null_support_slice": list(NULL_SUPPORT_SLICE),
            "anatomy_count": ANATOMY_COUNT,
            "endpoints_per_anatomy": ENDPOINTS_PER_ANATOMY,
        },
        "information_wall": {
            "passed": not forbidden and hidden_ids_absent,
            "forbidden_visible_schema_fields": forbidden,
            "side_only_entity_id_sentinels": [-1, -2],
            "hidden_identity_values_absent": hidden_ids_absent,
            "oracle_cardinality_field_absent": "cardinality" not in visible_field_names,
        },
        "prelabel_query": {"passed": bool(prelabel_fixed)},
        "one_sided_marginals": {
            "prior": _one_sided_audit(batch, "prior"),
            "current": _one_sided_audit(batch, "current"),
        },
        "view_weight_utility": {
            "oracle_view_weights": [1.0, 0.0],
            "oracle_view_exact_mapping_rate": mapping_rate(view1_mapping),
            "cyclic_view_exact_derangement_rate": float(
                (view2_mapping == batch.oracle.cyclic_mapping)
                .all(dim=-1)
                .float()
                .mean()
            ),
            "equal_weights": [0.5, 0.5],
            "equal_weight_exact_mapping_rate": mapping_rate(equal_mapping),
            "equal_weight_query_label_accuracy": label_rate(equal_mapping),
            "fixed_concatenated_exact_mapping_rate": mapping_rate(concat_mapping),
            "fixed_concatenated_query_label_accuracy": label_rate(concat_mapping),
            "learned_feasible_weights": list(LEARNED_FEASIBLE_VIEW_WEIGHTS),
            "learned_weight_exact_mapping_rate": mapping_rate(learned_mapping),
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
            "visible": r4_visible_hash(batch.regions),
            "hidden_oracle": r4_hidden_oracle_hash(batch.oracle),
        },
    }


def audit_r4_clean(batch: R4CleanBatch) -> dict[str, Any]:
    """Audit clean two-view agreement, five-label decoding, and marginals."""

    batch.validate()
    utilities = pairwise_view_cosines(batch.regions)
    mappings = tuple(
        _clean_persistent_mapping(batch, utilities[:, view]) for view in range(2)
    )
    oracle_real = batch.oracle.plan.transport[:, :14, :14]
    oracle_mapping = torch.full((len(batch.oracle.labels), 14), 14, dtype=torch.long)
    for case in range(len(batch.oracle.labels)):
        for prior in range(14):
            targets = torch.nonzero(oracle_real[case, prior] == 1).flatten()
            if len(targets) == 1:
                oracle_mapping[case, prior] = int(targets.item())
    persistent = oracle_mapping < 14
    view_rates = [
        float((mapping[persistent] == oracle_mapping[persistent]).float().mean())
        for mapping in mappings
    ]
    five_label_marginals = {
        side: _clean_balanced_signature_audit(
            batch, side, range(5), ignore_query_marker=True
        )
        for side in ("prior", "current")
    }
    persistent_marginals = {
        side: _clean_balanced_signature_audit(
            batch,
            side,
            (LABEL_STABLE, LABEL_WORSE, LABEL_IMPROVED),
            ignore_query_marker=False,
        )
        for side in ("prior", "current")
    }
    decoded = decode_clean_query_labels(batch, batch.oracle.plan)
    label_counts = torch.bincount(batch.oracle.labels, minlength=5)
    prelabel_fixed = True
    for group in batch.oracle.prelabel_group.unique().tolist():
        cases = torch.nonzero(
            (batch.oracle.prelabel_group == group) & batch.persistent_main_mask
        ).flatten()
        if len(cases) != 3 or set(batch.oracle.labels[cases].tolist()) != {0, 1, 2}:
            prelabel_fixed = False
            break
        reference = int(cases[0])
        for case_tensor in cases[1:]:
            case = int(case_tensor)
            prelabel_fixed &= torch.equal(
                batch.prior_query_marker[reference],
                batch.prior_query_marker[case],
            )
            prelabel_fixed &= torch.equal(
                batch.regions.prior_features[reference],
                batch.regions.prior_features[case],
            )

    null_start, null_stop = NULL_SUPPORT_SLICE
    prior_null = batch.regions.prior_features[..., null_start:null_stop]
    current_null = batch.regions.current_features[..., null_start:null_stop]
    directional_null = bool(
        (prior_null[..., :2].sum(dim=(-2, -1)) == 2).all()
        and (prior_null[..., 2:].sum(dim=(-2, -1)) == 0).all()
        and (current_null[..., :2].sum(dim=(-2, -1)) == 0).all()
        and (current_null[..., 2:].sum(dim=(-2, -1)) == 2).all()
    )
    return {
        "passed": bool(
            all(rate == 1.0 for rate in view_rates)
            and torch.equal(decoded, batch.oracle.labels)
            and bool((label_counts == label_counts[0]).all())
            and prelabel_fixed
            and directional_null
            and all(value["passed"] for value in five_label_marginals.values())
            and all(value["passed"] for value in persistent_marginals.values())
        ),
        "feature_contract": {
            "feature_dim": FEATURE_DIM,
            "identity_view_slices": [list(value) for value in IDENTITY_VIEW_SLICES],
            "null_support_slice": list(NULL_SUPPORT_SLICE),
            "persistent_endpoints": 12,
            "prior_null_endpoints": 2,
            "current_null_endpoints": 2,
        },
        "view_agreement": {
            "view_exact_persistent_mapping_rates": view_rates,
            "same_gold_global_mapping": view_rates == [1.0, 1.0],
        },
        "directional_null_support": {"passed": directional_null},
        "five_label_query": {
            "passed": torch.equal(decoded, batch.oracle.labels),
            "label_counts": label_counts.tolist(),
            "persistent_query_prelabel_fixed": bool(prelabel_fixed),
            "null_controls_outside_persistent_estimand": True,
        },
        "one_sided_marginals": {
            "all_five_without_query_marker": five_label_marginals,
            "persistent_three_with_query_marker": persistent_marginals,
        },
        "hashes": {
            "visible": r4_visible_hash(batch.regions),
            "hidden_oracle": r4_clean_hidden_oracle_hash(batch.oracle),
        },
    }
