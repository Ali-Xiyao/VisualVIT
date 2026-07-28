from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import torch
from torch import nn
import torch.nn.functional as F


PROGRESSION_LABELS = ("Stable", "Improved", "Worse", "New", "Resolved")
INVERSION_INDEX = torch.tensor((0, 2, 1, 4, 3), dtype=torch.long)


@dataclass(frozen=True)
class PRTAVariant:
    identifier: str
    trainable_adapter: bool
    classification: bool
    transition_alignment: bool
    temporal_inversion: bool
    cmcp: bool
    state_preservation: bool
    availability_gated: bool = False


def prta_variant_registry() -> dict[str, PRTAVariant]:
    return {
        "A0": PRTAVariant("A0", False, False, False, False, False, False),
        "A1": PRTAVariant(
            "A1", False, False, False, False, False, False, True
        ),
        "A2": PRTAVariant("A2", True, True, False, False, False, False),
        "A3": PRTAVariant("A3", True, True, True, False, False, False),
        "A4": PRTAVariant("A4", True, True, True, True, False, False),
        "A5": PRTAVariant("A5", True, True, True, False, True, False),
        "A6": PRTAVariant("A6", True, True, True, True, True, True),
        "A7": PRTAVariant(
            "A7", False, False, False, False, False, False, True
        ),
    }


class FrozenBiomedCLIPDifference(nn.Module):
    def __init__(
        self,
        frozen_blocks: Sequence[nn.Module],
        *,
        final_norm: nn.Module,
    ) -> None:
        super().__init__()
        if len(frozen_blocks) != 4:
            raise ValueError("A0 requires exactly BiomedCLIP Blocks 9-12")
        self.frozen_blocks = nn.ModuleList(frozen_blocks)
        self.final_norm = final_norm
        self.eval().requires_grad_(False)

    def train(self, mode: bool = True):
        super().train(False)
        return self

    def encode(self, block8_tokens: torch.Tensor) -> torch.Tensor:
        tokens = block8_tokens
        for block in self.frozen_blocks:
            tokens = block(tokens)
        return self.final_norm(tokens)

    @torch.no_grad()
    def forward(
        self,
        prior_block8: torch.Tensor,
        current_block8: torch.Tensor,
    ) -> torch.Tensor:
        if prior_block8.shape != current_block8.shape:
            raise ValueError("A0 prior/current token shapes differ")
        prior_cls = self.encode(prior_block8)[:, 0]
        current_cls = self.encode(current_block8)[:, 0]
        return F.normalize(current_cls - prior_cls, dim=-1)


class BottleneckAdapter(nn.Module):
    def __init__(
        self,
        width: int,
        rank: int,
        *,
        dropout: float = 0.0,
        initial_scale: float = 1e-3,
    ) -> None:
        super().__init__()
        if rank <= 0 or rank >= width:
            raise ValueError("adapter rank must be within (0, width)")
        self.norm = nn.LayerNorm(width)
        self.down = nn.Linear(width, rank, bias=False)
        self.up = nn.Linear(rank, width, bias=False)
        self.dropout = nn.Dropout(dropout)
        self.scale = nn.Parameter(torch.tensor(float(initial_scale)))
        nn.init.kaiming_uniform_(self.down.weight, a=5**0.5)
        nn.init.zeros_(self.up.weight)

    def forward(self, tokens: torch.Tensor) -> torch.Tensor:
        update = self.up(F.gelu(self.down(self.norm(tokens))))
        return tokens + self.scale * self.dropout(update)


class FrozenTailWithAdapters(nn.Module):
    def __init__(
        self,
        frozen_blocks: Sequence[nn.Module],
        *,
        width: int,
        adapter_rank: int,
        dropout: float = 0.0,
        final_norm: nn.Module | None = None,
    ) -> None:
        super().__init__()
        if len(frozen_blocks) != 4:
            raise ValueError("PRTA requires exactly frozen ViT Blocks 9-12")
        self.frozen_blocks = nn.ModuleList(frozen_blocks)
        for block in self.frozen_blocks:
            block.eval().requires_grad_(False)
        self.final_norm = final_norm if final_norm is not None else nn.Identity()
        self.final_norm.eval().requires_grad_(False)
        self.adapters = nn.ModuleList(
            BottleneckAdapter(width, adapter_rank, dropout=dropout)
            for _ in frozen_blocks
        )

    def train(self, mode: bool = True):
        super().train(mode)
        for block in self.frozen_blocks:
            block.eval()
        self.final_norm.eval()
        return self

    def forward(self, tokens: torch.Tensor) -> torch.Tensor:
        for block, adapter in zip(self.frozen_blocks, self.adapters):
            # Frozen parameters still participate in autograd so gradients can
            # reach adapters inserted before later frozen blocks.
            frozen_output = block(tokens)
            tokens = adapter(frozen_output)
        return self.final_norm(tokens)

    def forward_frozen(self, tokens: torch.Tensor) -> torch.Tensor:
        with torch.no_grad():
            for block in self.frozen_blocks:
                tokens = block(tokens)
            return self.final_norm(tokens)


class QueryResampler(nn.Module):
    def __init__(
        self,
        *,
        width: int,
        heads: int,
        output_tokens: int,
        dropout: float,
    ) -> None:
        super().__init__()
        self.queries = nn.Parameter(torch.empty(output_tokens, width))
        nn.init.normal_(self.queries, std=0.02)
        self.attention = nn.MultiheadAttention(
            width, heads, dropout=dropout, batch_first=True
        )
        self.norm = nn.LayerNorm(width)

    def forward(
        self, source: torch.Tensor, query_condition: torch.Tensor
    ) -> torch.Tensor:
        batch = source.shape[0]
        queries = self.queries.unsqueeze(0).expand(batch, -1, -1)
        queries = queries + query_condition.unsqueeze(1)
        output, _ = self.attention(
            self.norm(queries),
            self.norm(source),
            self.norm(source),
            need_weights=False,
        )
        return queries + output


@dataclass
class PRTAOutput:
    state_tokens: torch.Tensor
    transition_tokens: torch.Tensor
    state_embedding: torch.Tensor
    transition_embedding: torch.Tensor
    aligned_prior_tokens: torch.Tensor
    frozen_current_embedding: torch.Tensor


class PRTATemporalAdapter(nn.Module):
    def __init__(
        self,
        frozen_tail_blocks: Sequence[nn.Module],
        *,
        width: int = 768,
        heads: int = 12,
        adapter_rank: int = 32,
        state_tokens: int = 20,
        transition_tokens: int = 20,
        dropout: float = 0.0,
        frozen_final_norm: nn.Module | None = None,
    ) -> None:
        super().__init__()
        if width % heads:
            raise ValueError("width must be divisible by heads")
        self.tail = FrozenTailWithAdapters(
            frozen_tail_blocks,
            width=width,
            adapter_rank=adapter_rank,
            dropout=dropout,
            final_norm=frozen_final_norm,
        )
        self.query_projection = nn.Sequential(
            nn.LayerNorm(width),
            nn.Linear(width, width),
            nn.GELU(),
            nn.Linear(width, width),
        )
        self.cross_time = nn.MultiheadAttention(
            width, heads, dropout=dropout, batch_first=True
        )
        self.cross_norm = nn.LayerNorm(width)
        self.relation_projection = nn.Sequential(
            nn.LayerNorm(width * 5),
            nn.Linear(width * 5, width * 2),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(width * 2, width),
        )
        self.state_resampler = QueryResampler(
            width=width,
            heads=heads,
            output_tokens=state_tokens,
            dropout=dropout,
        )
        self.transition_resampler = QueryResampler(
            width=width,
            heads=heads,
            output_tokens=transition_tokens,
            dropout=dropout,
        )
        self.state_norm = nn.LayerNorm(width)
        self.transition_norm = nn.LayerNorm(width)

    def forward(
        self,
        prior_block8: torch.Tensor,
        current_block8: torch.Tensor,
        finding_query: torch.Tensor,
    ) -> PRTAOutput:
        if prior_block8.shape != current_block8.shape:
            raise ValueError("prior/current Block-8 token shapes differ")
        if prior_block8.ndim != 3:
            raise ValueError("Block-8 tokens must have shape [B, N, D]")
        if finding_query.shape != (
            prior_block8.shape[0],
            prior_block8.shape[2],
        ):
            raise ValueError("finding query must have shape [B, D]")

        query_condition = self.query_projection(finding_query)
        prior = self.tail(prior_block8)
        current = self.tail(current_block8)
        conditioned_current = current + query_condition.unsqueeze(1)
        conditioned_prior = prior + query_condition.unsqueeze(1)
        aligned_prior, _ = self.cross_time(
            self.cross_norm(conditioned_current),
            self.cross_norm(conditioned_prior),
            self.cross_norm(prior),
            need_weights=False,
        )
        relation = torch.cat(
            (
                current,
                aligned_prior,
                current - aligned_prior,
                (current - aligned_prior).abs(),
                current * aligned_prior,
            ),
            dim=-1,
        )
        transition_source = current + self.relation_projection(relation)
        state_tokens = self.state_resampler(current, query_condition)
        transition_tokens = self.transition_resampler(
            transition_source, query_condition
        )
        state_embedding = F.normalize(
            self.state_norm(state_tokens.mean(dim=1)), dim=-1
        )
        transition_embedding = F.normalize(
            self.transition_norm(transition_tokens.mean(dim=1)), dim=-1
        )
        frozen_current_embedding = F.normalize(
            self.tail.forward_frozen(current_block8).mean(dim=1), dim=-1
        )
        return PRTAOutput(
            state_tokens=state_tokens,
            transition_tokens=transition_tokens,
            state_embedding=state_embedding,
            transition_embedding=transition_embedding,
            aligned_prior_tokens=aligned_prior,
            frozen_current_embedding=frozen_current_embedding,
        )


class PRTATrainingHeads(nn.Module):
    def __init__(
        self,
        *,
        visual_width: int = 768,
        text_width: int = 512,
    ) -> None:
        super().__init__()
        self.finding_projection = nn.Sequential(
            nn.LayerNorm(text_width),
            nn.Linear(text_width, visual_width),
        )
        self.transition_text_projection = nn.Sequential(
            nn.LayerNorm(text_width),
            nn.Linear(text_width, visual_width),
        )
        self.progression_classifier = nn.Sequential(
            nn.LayerNorm(visual_width),
            nn.Linear(visual_width, len(PROGRESSION_LABELS)),
        )

    def finding_query(self, text_embedding: torch.Tensor) -> torch.Tensor:
        return self.finding_projection(text_embedding)

    def transition_text(self, text_embedding: torch.Tensor) -> torch.Tensor:
        return F.normalize(self.transition_text_projection(text_embedding), dim=-1)

    def progression_logits(
        self, transition_embedding: torch.Tensor
    ) -> torch.Tensor:
        return self.progression_classifier(transition_embedding)


def transition_alignment_loss(
    transition_embeddings: torch.Tensor,
    text_embeddings: torch.Tensor,
    *,
    temperature: float = 0.07,
) -> torch.Tensor:
    if transition_embeddings.shape != text_embeddings.shape:
        raise ValueError("transition/text embedding shapes differ")
    if temperature <= 0:
        raise ValueError("temperature must be positive")
    visual = F.normalize(transition_embeddings, dim=-1)
    text = F.normalize(text_embeddings, dim=-1)
    logits = visual @ text.transpose(0, 1) / temperature
    targets = torch.arange(logits.shape[0], device=logits.device)
    return 0.5 * (
        F.cross_entropy(logits, targets)
        + F.cross_entropy(logits.transpose(0, 1), targets)
    )


def cmcp_margin_loss(
    true_transition: torch.Tensor,
    counterfactual_transition: torch.Tensor,
    target_text: torch.Tensor,
    *,
    margin: float = 0.2,
) -> torch.Tensor:
    if not (
        true_transition.shape
        == counterfactual_transition.shape
        == target_text.shape
    ):
        raise ValueError("CMCP embedding shapes differ")
    true_score = F.cosine_similarity(true_transition, target_text, dim=-1)
    counterfactual_score = F.cosine_similarity(
        counterfactual_transition, target_text, dim=-1
    )
    return F.relu(margin - true_score + counterfactual_score).mean()


def invert_progression_logits(logits: torch.Tensor) -> torch.Tensor:
    if logits.shape[-1] != len(PROGRESSION_LABELS):
        raise ValueError("progression logits must contain five classes")
    return logits.index_select(
        -1, INVERSION_INDEX.to(device=logits.device)
    )


def project_equivariant_inversion_logits(
    forward_logits: torch.Tensor,
    reversed_logits: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor]:
    if forward_logits.shape != reversed_logits.shape:
        raise ValueError("forward/reversed logit shapes differ")
    projected_forward = 0.5 * (
        forward_logits + invert_progression_logits(reversed_logits)
    )
    projected_reversed = invert_progression_logits(projected_forward)
    return projected_forward, projected_reversed


def temporal_inversion_loss(
    forward_logits: torch.Tensor, reversed_logits: torch.Tensor
) -> torch.Tensor:
    mapped_forward = invert_progression_logits(forward_logits)
    target = F.softmax(mapped_forward.detach(), dim=-1)
    return F.kl_div(
        F.log_softmax(reversed_logits, dim=-1),
        target,
        reduction="batchmean",
    )


def state_preservation_loss(
    adapted_state: torch.Tensor, frozen_current_state: torch.Tensor
) -> torch.Tensor:
    if adapted_state.shape != frozen_current_state.shape:
        raise ValueError("state-preservation embedding shapes differ")
    return (
        1
        - F.cosine_similarity(
            adapted_state, frozen_current_state.detach(), dim=-1
        )
    ).mean()
