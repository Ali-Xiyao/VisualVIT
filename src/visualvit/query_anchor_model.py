from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import torch
from torch import Tensor, nn

from .calibration_query import QUERY_RELATION_SLOT, QueryTokenContract, TOKEN_BUDGET
from .qwen_adapter import FrozenVLMAdapter
from .schemas import ProjectedTokenBundle


QUERY_PLACEHOLDER_TOKEN_ID = 1
QUERY_LABEL_TOKEN_IDS = {
    "stable": (5,),
    "worse": (6,),
    "improved": (7,),
    "new": (8,),
    "resolved": (9,),
}


class QueryRelationProjector(nn.Module):
    """Project only the registered query payload and keep 63 literal zeros.

    The deterministic initialization is a declared engineering readout, not a
    learned medical prior.  It maps the six public anchor fields
    ``[constant, prior_state, current_state, real, death, birth]`` to the five
    label-logit coordinates.  Parameters remain trainable so B4a, B4b and the
    learned matcher can be optimized from the same exact initial state.
    """

    def __init__(self, input_dim: int = 6, hidden_size: int = 8) -> None:
        super().__init__()
        if input_dim < 6:
            raise ValueError("query projector input_dim must be at least six")
        if hidden_size < 5:
            raise ValueError("query projector hidden_size must be at least five")
        self.input_dim = int(input_dim)
        self.hidden_size = int(hidden_size)
        self.projection = nn.Linear(input_dim, hidden_size)
        self.reset_registered_parameters()

    def reset_registered_parameters(self) -> None:
        with torch.no_grad():
            self.projection.weight.zero_()
            self.projection.bias.zero_()
            # Stable: real edge with current state near zero.
            self.projection.weight[0, 0] = 2.0
            self.projection.weight[0, 3] = 4.0
            # Worse/improved: signed current-state transition on a real edge.
            self.projection.weight[1, 2] = 4.0
            self.projection.weight[1, 3] = 4.0
            self.projection.weight[2, 2] = -4.0
            self.projection.weight[2, 3] = 4.0
            # New/resolved: current-side birth and prior-side death.
            self.projection.weight[3, 5] = 6.0
            self.projection.weight[4, 4] = 6.0

    def forward(self, contract: QueryTokenContract) -> ProjectedTokenBundle:
        contract.validate()
        if contract.tokens.shape[-1] != self.input_dim:
            raise ValueError(
                f"expected query token width {self.input_dim}, "
                f"got {contract.tokens.shape[-1]}"
            )
        raw = contract.tokens[:, QUERY_RELATION_SLOT]
        projected_query = self.projection(raw)
        embeddings = projected_query.new_zeros(
            projected_query.shape[0], TOKEN_BUDGET, self.hidden_size
        )
        embeddings[:, QUERY_RELATION_SLOT] = projected_query
        bundle = ProjectedTokenBundle(
            embeddings=embeddings,
            token_types=contract.token_types,
            valid_mask=contract.valid_mask,
            attention_mask=contract.attention_mask,
            position_ids=contract.position_ids,
            audit={
                "query_anchor_gate": True,
                "registered_analytic_initialization": True,
                "query_relation_slot": QUERY_RELATION_SLOT,
                "literal_zero_nonquery_payloads": True,
                "physical_token_count": TOKEN_BUDGET,
            },
        )
        bundle.validate(token_budget=TOKEN_BUDGET)
        return bundle


class FrozenQueryCausalLM(nn.Module):
    """Frozen causal-LM-shaped readout for the query-anchor survival gate.

    It consumes the same exact-placeholder adapter path as a real frozen VLM.
    The first five query-embedding coordinates become the five registered
    single-token label logits; all other vocabulary entries receive a fixed
    floor.  No case label, hidden ID or oracle cardinality enters this module.
    """

    def __init__(
        self,
        hidden_size: int = 8,
        vocab_size: int = 48,
        *,
        placeholder_start: int = 2,
    ) -> None:
        super().__init__()
        if hidden_size < 5:
            raise ValueError("hidden_size must be at least five")
        if vocab_size <= max(ids[0] for ids in QUERY_LABEL_TOKEN_IDS.values()):
            raise ValueError("vocab_size is too small for registered label IDs")
        self.embedding = nn.Embedding(vocab_size, hidden_size)
        self.hidden_size = int(hidden_size)
        self.vocab_size = int(vocab_size)
        self.placeholder_start = int(placeholder_start)

    def get_input_embeddings(self) -> nn.Module:
        return self.embedding

    def forward(
        self,
        *,
        inputs_embeds: Tensor,
        attention_mask: Tensor,
        position_ids: Tensor,
        use_cache: bool,
        logits_to_keep: int,
        **kwargs: Any,
    ) -> SimpleNamespace:
        if kwargs:
            raise ValueError(f"unexpected frozen-query LM arguments: {sorted(kwargs)}")
        if position_ids.shape != (3, *attention_mask.shape):
            raise ValueError("expected three equal text-like position axes")
        if use_cache is not False or logits_to_keep != 0:
            raise ValueError("query LM requires use_cache=False and logits_to_keep=0")
        stop = self.placeholder_start + TOKEN_BUDGET
        if inputs_embeds.shape[1] < stop:
            raise ValueError(
                "input sequence does not contain the exact placeholder block"
            )
        # The 63 non-query payloads are literal zeros, so summing the physical
        # block recovers only the one registered query relation embedding.
        query_embedding = inputs_embeds[:, self.placeholder_start : stop].sum(dim=1)
        class_logits = query_embedding[:, :5]
        batch, sequence, _ = inputs_embeds.shape
        logits = inputs_embeds.new_full((batch, sequence, self.vocab_size), -12.0)
        label_ids = torch.tensor(
            [ids[0] for ids in QUERY_LABEL_TOKEN_IDS.values()],
            dtype=torch.long,
            device=inputs_embeds.device,
        )
        scatter_index = label_ids.view(1, 1, -1).expand(batch, sequence, -1)
        scatter_source = class_logits[:, None, :].expand(-1, sequence, -1)
        logits = logits.scatter(dim=-1, index=scatter_index, src=scatter_source)
        return SimpleNamespace(logits=logits)


def build_frozen_query_adapter(hidden_size: int = 8) -> FrozenVLMAdapter:
    return FrozenVLMAdapter(
        FrozenQueryCausalLM(hidden_size=hidden_size),
        QUERY_PLACEHOLDER_TOKEN_ID,
        QUERY_LABEL_TOKEN_IDS,
        token_budget=TOKEN_BUDGET,
    )


def query_prompt(batch_size: int, device: torch.device | str = "cpu") -> Tensor:
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")
    row = torch.tensor(
        [2, 3] + [QUERY_PLACEHOLDER_TOKEN_ID] * TOKEN_BUDGET + [4],
        dtype=torch.long,
        device=device,
    )
    return row.unsqueeze(0).expand(batch_size, -1).clone()
