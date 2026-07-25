from __future__ import annotations

from dataclasses import dataclass

import torch
from torch import Tensor

from .matching import oracle_plan_from_entity_ids
from .schemas import MatchPlan, RegionBatch
from .tokenizer import (
    ENTITY_TOKENS,
    GLOBAL_TOKENS,
    RELATION_TOKENS,
    assemble_fixed_budget_tokens,
    build_relation_slots,
)


LABEL_STABLE = 0
LABEL_WORSE = 1
LABEL_IMPROVED = 2
LABEL_NEW = 3
LABEL_RESOLVED = 4
NUM_CLASSES = 5


@dataclass
class SyntheticBatch:
    regions: RegionBatch
    oracle: MatchPlan
    prior_labels: Tensor
    current_is_birth: Tensor
    persistent_count: Tensor

    def to(self, device: torch.device | str) -> "SyntheticBatch":
        fields = {
            name: getattr(self.regions, name).to(device)
            for name in (
                "prior_features",
                "current_features",
                "prior_valid",
                "current_valid",
                "prior_anatomy",
                "current_anatomy",
                "prior_entity_ids",
                "current_entity_ids",
            )
        }
        regions = RegionBatch(**fields)
        oracle = MatchPlan(self.oracle.transport.to(device), self.oracle.mode)
        return SyntheticBatch(
            regions=regions,
            oracle=oracle,
            prior_labels=self.prior_labels.to(device),
            current_is_birth=self.current_is_birth.to(device),
            persistent_count=self.persistent_count.to(device),
        )


def make_synthetic_batch(
    num_cases: int,
    seed: int,
    feature_dim: int = 24,
    persistent: int = 6,
    deaths: int = 2,
    births: int = 2,
) -> SyntheticBatch:
    """Generate identity/state-separated longitudinal fixtures."""

    if feature_dim < 8:
        raise ValueError("feature_dim must be at least 8")
    if persistent % 2 != 0:
        raise ValueError("persistent must be even for two derangeable anatomy groups")
    generator = torch.Generator(device="cpu")
    generator.manual_seed(seed)
    identity_dim = feature_dim // 2
    state_dim = feature_dim - identity_dim
    rp = persistent + deaths
    rc = persistent + births

    prior_features = torch.zeros(num_cases, rp, feature_dim)
    current_features = torch.zeros(num_cases, rc, feature_dim)
    prior_anatomy = torch.zeros(num_cases, rp, dtype=torch.long)
    current_anatomy = torch.zeros(num_cases, rc, dtype=torch.long)
    prior_ids = torch.zeros(num_cases, rp, dtype=torch.long)
    current_ids = torch.zeros(num_cases, rc, dtype=torch.long)
    prior_labels = torch.zeros(num_cases, rp, dtype=torch.long)
    current_is_birth = torch.zeros(num_cases, rc, dtype=torch.bool)

    for case_index in range(num_cases):
        identity = torch.randn(
            persistent + deaths + births, identity_dim, generator=generator
        )
        identity = torch.nn.functional.normalize(identity, dim=-1) * 3.0
        prior_state = torch.randn(rp, state_dim, generator=generator)
        current_state = torch.zeros(rc, state_dim)

        labels = torch.tensor(
            [LABEL_STABLE, LABEL_WORSE, LABEL_IMPROVED] * (persistent // 3 + 1),
            dtype=torch.long,
        )[:persistent]
        labels = labels[torch.randperm(persistent, generator=generator)]
        delta = torch.zeros(persistent)
        delta[labels == LABEL_WORSE] = 1.75
        delta[labels == LABEL_IMPROVED] = -1.75
        current_state[:persistent] = prior_state[:persistent]
        current_state[:persistent, 0] += delta
        current_state[:persistent] += 0.05 * torch.randn(
            persistent, state_dim, generator=generator
        )
        current_state[persistent:] = torch.randn(births, state_dim, generator=generator)

        prior = torch.cat((identity[:rp], prior_state), dim=-1)
        current_identity = torch.cat(
            (
                identity[:persistent]
                + 0.03 * torch.randn(persistent, identity_dim, generator=generator),
                identity[rp : rp + births],
            ),
            dim=0,
        )
        current = torch.cat((current_identity, current_state), dim=-1)

        entity_prior = torch.arange(rp, dtype=torch.long) + case_index * 1000
        entity_current = torch.cat(
            (
                torch.arange(persistent, dtype=torch.long) + case_index * 1000,
                torch.arange(births, dtype=torch.long) + case_index * 1000 + rp,
            )
        )
        anatomy_prior = torch.cat(
            (
                torch.zeros(persistent // 2, dtype=torch.long),
                torch.ones(persistent // 2, dtype=torch.long),
                torch.arange(deaths, dtype=torch.long) + 2,
            )
        )
        anatomy_current = torch.cat(
            (
                torch.zeros(persistent // 2, dtype=torch.long),
                torch.ones(persistent // 2, dtype=torch.long),
                torch.arange(births, dtype=torch.long) + 2,
            )
        )
        case_prior_labels = torch.cat(
            (labels, torch.full((deaths,), LABEL_RESOLVED, dtype=torch.long))
        )
        case_birth = torch.cat(
            (
                torch.zeros(persistent, dtype=torch.bool),
                torch.ones(births, dtype=torch.bool),
            )
        )

        prior_perm = torch.randperm(rp, generator=generator)
        current_perm = torch.randperm(rc, generator=generator)
        prior_features[case_index] = prior[prior_perm]
        current_features[case_index] = current[current_perm]
        prior_anatomy[case_index] = anatomy_prior[prior_perm]
        current_anatomy[case_index] = anatomy_current[current_perm]
        prior_ids[case_index] = entity_prior[prior_perm]
        current_ids[case_index] = entity_current[current_perm]
        prior_labels[case_index] = case_prior_labels[prior_perm]
        current_is_birth[case_index] = case_birth[current_perm]

    regions = RegionBatch(
        prior_features=prior_features,
        current_features=current_features,
        prior_valid=torch.ones(num_cases, rp, dtype=torch.bool),
        current_valid=torch.ones(num_cases, rc, dtype=torch.bool),
        prior_anatomy=prior_anatomy,
        current_anatomy=current_anatomy,
        prior_entity_ids=prior_ids,
        current_entity_ids=current_ids,
    )
    oracle = oracle_plan_from_entity_ids(regions)
    return SyntheticBatch(
        regions=regions,
        oracle=oracle,
        prior_labels=prior_labels,
        current_is_birth=current_is_birth,
        persistent_count=torch.full((num_cases,), persistent, dtype=torch.long),
    )


def labeled_relation_rows(
    synthetic: SyntheticBatch,
    plan: MatchPlan,
) -> tuple[Tensor, Tensor]:
    """Flatten valid relation features and labels for proxy classification."""

    # The classifier consumes the relation slice from the fixed 64-token
    # bundle. This still does not test projector/Qwen injection, but it avoids
    # a bypass around the registered token assembler.
    bundle = assemble_fixed_budget_tokens(synthetic.regions, plan)
    relation_start = GLOBAL_TOKENS + ENTITY_TOKENS
    slots = bundle.tokens[:, relation_start : relation_start + RELATION_TOKENS]
    _, _, records = build_relation_slots(synthetic.regions, plan)
    features: list[Tensor] = []
    labels: list[Tensor] = []
    for batch_index, batch_records in enumerate(records):
        predicted_births = {
            current_index for kind, _, current_index in batch_records if kind == "birth"
        }
        gold_births = {
            current_index
            for current_index in range(synthetic.current_is_birth.shape[1])
            if bool(synthetic.current_is_birth[batch_index, current_index])
        }
        if predicted_births != gold_births:
            raise ValueError(
                "synthetic relation classification requires exact birth set; "
                "false-positive or missed births must not be filtered"
            )
        for slot_index, (kind, prior_index, current_index) in enumerate(batch_records):
            if kind == "birth":
                label = torch.tensor(LABEL_NEW, dtype=torch.long, device=slots.device)
            else:
                label = synthetic.prior_labels[batch_index, prior_index]
            features.append(slots[batch_index, slot_index])
            labels.append(label)
    if not features:
        raise ValueError("no labeled relation rows")
    return torch.stack(features), torch.stack(labels)


def order_swap_label(labels: Tensor) -> Tensor:
    mapping = torch.tensor(
        [LABEL_STABLE, LABEL_IMPROVED, LABEL_WORSE, LABEL_RESOLVED, LABEL_NEW],
        dtype=torch.long,
        device=labels.device,
    )
    return mapping[labels]
