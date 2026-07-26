from __future__ import annotations

from dataclasses import dataclass
import math

import torch
from torch import Tensor, nn

from .schemas import TokenBundle


TYPE_QUERY = 0
TYPE_STATE = 1
TYPE_GLOBAL_TRANSITION = 2
TYPE_LOCAL_TRANSITION = 3
TYPE_RELATION = 4
TYPE_RESERVED = 5
TOKEN_LAYOUT = (4, 12, 16, 16, 12, 4)
TOKEN_BUDGET = sum(TOKEN_LAYOUT)


@dataclass(frozen=True)
class TierBundlePair:
    robust: TokenBundle
    rich: TokenBundle

    def validate(self) -> None:
        self.robust.validate(token_budget=TOKEN_BUDGET)
        self.rich.validate(token_budget=TOKEN_BUDGET)
        if not torch.equal(self.robust.token_types, self.rich.token_types):
            raise ValueError("robust/rich token type layouts must match")
        if self.robust.tokens.shape != self.rich.tokens.shape:
            raise ValueError("robust/rich physical token shapes must match")


def fixed_token_types(device: torch.device | None = None) -> Tensor:
    return torch.tensor(
        [TYPE_QUERY] * TOKEN_LAYOUT[0]
        + [TYPE_STATE] * TOKEN_LAYOUT[1]
        + [TYPE_GLOBAL_TRANSITION] * TOKEN_LAYOUT[2]
        + [TYPE_LOCAL_TRANSITION] * TOKEN_LAYOUT[3]
        + [TYPE_RELATION] * TOKEN_LAYOUT[4]
        + [TYPE_RESERVED] * TOKEN_LAYOUT[5],
        dtype=torch.long,
        device=device,
    )


class HierarchicalTemporalTokenBuilder(nn.Module):
    """Build matched robust/rich fixed-64 bundles from frozen patch features."""

    def __init__(self, feature_dim: int, query_dim: int | None = None) -> None:
        super().__init__()
        if feature_dim <= 0:
            raise ValueError("feature_dim must be positive")
        query_dim = feature_dim if query_dim is None else query_dim
        if query_dim <= 0:
            raise ValueError("query_dim must be positive")
        self.feature_dim = feature_dim
        self.query_projection = nn.Linear(query_dim, feature_dim)
        self.patch_key = nn.Linear(feature_dim, feature_dim, bias=False)
        self.global_slots = nn.Linear(5 * feature_dim, 16 * feature_dim)
        self.local_slots = nn.Linear(5 * feature_dim, 16 * feature_dim)
        self.relation_slots = nn.Linear(5 * feature_dim + 2, 12 * feature_dim)
        self.state_norm = nn.LayerNorm(feature_dim)
        self.output_norm = nn.LayerNorm(feature_dim)

    @staticmethod
    def _validate_inputs(
        prior_patches: Tensor, current_patches: Tensor, finding_query: Tensor
    ) -> None:
        if prior_patches.ndim != 3 or current_patches.ndim != 3:
            raise ValueError("patch tensors must have shape [B, N, D]")
        if finding_query.ndim != 2:
            raise ValueError("finding_query must have shape [B, Dq]")
        if prior_patches.shape[0] != current_patches.shape[0]:
            raise ValueError("prior/current batch sizes must match")
        if prior_patches.shape[0] != finding_query.shape[0]:
            raise ValueError("patch/query batch sizes must match")
        if prior_patches.shape[2] != current_patches.shape[2]:
            raise ValueError("prior/current feature widths must match")
        if prior_patches.shape[1] == 0 or current_patches.shape[1] == 0:
            raise ValueError("each timepoint needs at least one patch")
        if not bool(
            torch.isfinite(prior_patches).all()
            and torch.isfinite(current_patches).all()
            and torch.isfinite(finding_query).all()
        ):
            raise ValueError("token inputs must be finite")

    def _query_attention(self, patches: Tensor, query: Tensor) -> Tensor:
        keys = self.patch_key(patches)
        return torch.softmax(
            torch.einsum("bd,bnd->bn", query, keys)
            / math.sqrt(self.feature_dim),
            dim=-1,
        )

    @staticmethod
    def _weighted_pool(patches: Tensor, weights: Tensor) -> Tensor:
        return torch.einsum("bn,bnd->bd", weights, patches)

    @staticmethod
    def _interaction(prior: Tensor, current: Tensor) -> Tensor:
        return torch.cat(
            (
                prior,
                current,
                current - prior,
                (current - prior).abs(),
                prior * current,
            ),
            dim=-1,
        )

    @staticmethod
    def _top_patches(
        patches: Tensor, weights: Tensor, count: int
    ) -> tuple[Tensor, Tensor]:
        available = patches.shape[1]
        top_count = min(count, available)
        indices = weights.topk(top_count, dim=-1).indices
        gathered = patches.gather(
            1, indices.unsqueeze(-1).expand(-1, -1, patches.shape[-1])
        )
        gathered_weights = weights.gather(1, indices)
        if top_count < count:
            pad = count - top_count
            gathered = torch.cat(
                (gathered, gathered[:, -1:].expand(-1, pad, -1)), dim=1
            )
            gathered_weights = torch.cat(
                (
                    gathered_weights,
                    torch.zeros(
                        patches.shape[0],
                        pad,
                        dtype=weights.dtype,
                        device=weights.device,
                    ),
                ),
                dim=1,
            )
        return gathered, gathered_weights

    def forward(
        self,
        prior_patches: Tensor,
        current_patches: Tensor,
        finding_query: Tensor,
    ) -> TierBundlePair:
        self._validate_inputs(prior_patches, current_patches, finding_query)
        if prior_patches.shape[-1] != self.feature_dim:
            raise ValueError(
                f"expected feature_dim={self.feature_dim}, "
                f"got {prior_patches.shape[-1]}"
            )
        batch_size = prior_patches.shape[0]
        query = self.query_projection(finding_query)
        prior_attention = self._query_attention(prior_patches, query)
        current_attention = self._query_attention(current_patches, query)
        prior_global = prior_patches.mean(dim=1)
        current_global = current_patches.mean(dim=1)
        prior_local = self._weighted_pool(prior_patches, prior_attention)
        current_local = self._weighted_pool(current_patches, current_attention)

        query_tokens = torch.stack(
            (
                query,
                prior_global,
                current_global,
                current_global - prior_global,
            ),
            dim=1,
        )
        state_tokens, state_confidence = self._top_patches(
            current_patches, current_attention, TOKEN_LAYOUT[1]
        )
        state_tokens = self.state_norm(state_tokens)
        global_tokens = self.global_slots(
            self._interaction(prior_global, current_global)
        ).view(batch_size, TOKEN_LAYOUT[2], self.feature_dim)
        coarse_local_tokens = self.local_slots(
            self._interaction(prior_local, current_local)
        ).view(batch_size, TOKEN_LAYOUT[3], self.feature_dim)

        rich_prior, rich_prior_conf = self._top_patches(
            prior_patches, prior_attention, TOKEN_LAYOUT[3]
        )
        rich_current, rich_current_conf = self._top_patches(
            current_patches, current_attention, TOKEN_LAYOUT[3]
        )
        rich_local_tokens = (
            rich_current
            - rich_prior
            + 0.5 * (rich_current - rich_prior).abs()
            + 0.25 * rich_prior * rich_current
        )

        correspondence_logits = torch.einsum(
            "bnd,bmd->bnm", self.patch_key(prior_patches), current_patches
        ) / math.sqrt(self.feature_dim)
        correspondence = torch.softmax(correspondence_logits, dim=-1)
        matched_current = correspondence @ current_patches
        entropy = -(
            correspondence.clamp_min(1e-8).log() * correspondence
        ).sum(dim=-1) / math.log(max(2, current_patches.shape[1]))
        relation_relevance = prior_attention
        relation_input = torch.cat(
            (
                prior_patches,
                matched_current,
                matched_current - prior_patches,
                (matched_current - prior_patches).abs(),
                prior_patches * matched_current,
                entropy.unsqueeze(-1),
                relation_relevance.unsqueeze(-1),
            ),
            dim=-1,
        )
        relation_summary = torch.einsum(
            "bn,bnf->bf", relation_relevance, relation_input
        )
        rich_relation = self.relation_slots(relation_summary).view(
            batch_size, TOKEN_LAYOUT[4], self.feature_dim
        )
        coarse_relation = self.relation_slots(
            torch.cat(
                (
                    self._interaction(prior_local, current_local),
                    torch.zeros(
                        batch_size,
                        2,
                        dtype=prior_patches.dtype,
                        device=prior_patches.device,
                    ),
                ),
                dim=-1,
            )
        ).view(batch_size, TOKEN_LAYOUT[4], self.feature_dim)

        reserved = torch.zeros(
            batch_size,
            TOKEN_LAYOUT[5],
            self.feature_dim,
            dtype=prior_patches.dtype,
            device=prior_patches.device,
        )
        robust_tokens = torch.cat(
            (
                query_tokens,
                state_tokens,
                global_tokens,
                coarse_local_tokens,
                coarse_relation,
                reserved,
            ),
            dim=1,
        )
        rich_tokens = torch.cat(
            (
                query_tokens,
                state_tokens,
                global_tokens,
                rich_local_tokens,
                rich_relation,
                reserved,
            ),
            dim=1,
        )
        robust_tokens = self.output_norm(robust_tokens)
        rich_tokens = self.output_norm(rich_tokens)
        token_types = fixed_token_types(prior_patches.device)
        robust_valid = torch.ones(
            batch_size, TOKEN_BUDGET, dtype=torch.bool, device=prior_patches.device
        )
        rich_valid = robust_valid.clone()
        robust_valid[:, 52:60] = False
        robust_valid[:, 60:64] = False
        rich_valid[:, 60:64] = False
        confidence = torch.ones(
            batch_size,
            TOKEN_BUDGET,
            dtype=prior_patches.dtype,
            device=prior_patches.device,
        )
        confidence[:, 4:16] = state_confidence
        confidence[:, 32:48] = (
            rich_prior_conf + rich_current_conf
        ) / 2
        temporal_ids = torch.full(
            (batch_size, TOKEN_BUDGET),
            -1,
            dtype=torch.long,
            device=prior_patches.device,
        )
        temporal_ids[:, 4:16] = 1
        temporal_ids[:, 16:32] = 1
        temporal_ids[:, 32:60] = 1
        anatomy_ids = torch.full_like(temporal_ids, -1)
        source_ids = torch.arange(
            TOKEN_BUDGET, dtype=torch.long, device=prior_patches.device
        ).view(1, -1).expand(batch_size, -1)
        assignment = torch.zeros(
            batch_size, 1, 1, dtype=prior_patches.dtype, device=prior_patches.device
        )

        def make(tokens: Tensor, valid: Tensor) -> TokenBundle:
            return TokenBundle(
                tokens=tokens,
                token_types=token_types,
                valid_mask=valid,
                assignment=assignment,
                anatomy_ids=anatomy_ids,
                temporal_ids=temporal_ids,
                confidence=confidence,
                slot_mass=valid.to(tokens.dtype),
                source_ids=source_ids,
            )

        result = TierBundlePair(
            robust=make(robust_tokens, robust_valid),
            rich=make(rich_tokens, rich_valid),
        )
        result.validate()
        return result
