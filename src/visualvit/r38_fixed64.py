from __future__ import annotations

from dataclasses import dataclass

import torch
from torch import Tensor


R38_TOKEN_LAYOUT = (
    ("query_control", 4),
    ("state", 12),
    ("global_transition", 16),
    ("local_transition", 16),
    ("relation_context", 12),
    ("reserved", 4),
)
R38_TOKEN_COUNT = 64


@dataclass(frozen=True)
class Fixed64Bundle:
    tokens: Tensor
    token_type_ids: Tensor
    physical_attention: Tensor
    logical_validity: Tensor


def mean_preserving_reduce(tokens: Tensor, output_tokens: int) -> Tensor:
    if tokens.ndim != 3:
        raise ValueError("tokens must have shape [B, N, D]")
    if not 0 < output_tokens <= tokens.shape[1]:
        raise ValueError("output token count must be within input length")
    input_tokens = tokens.shape[1]
    groups = []
    for index in range(output_tokens):
        start = input_tokens * index // output_tokens
        end = input_tokens * (index + 1) // output_tokens
        if end <= start:
            raise RuntimeError("mean-preserving group is empty")
        groups.append(
            tokens[:, start:end].sum(dim=1)
            * (float(output_tokens) / float(input_tokens))
        )
    output = torch.stack(groups, dim=1)
    if output.shape != (
        tokens.shape[0],
        output_tokens,
        tokens.shape[2],
    ):
        raise RuntimeError("mean-preserving reducer shape drift")
    return output


def pack_fixed64(
    *,
    finding_query: Tensor,
    state_tokens: Tensor,
    transition_tokens: Tensor,
    aligned_prior_tokens: Tensor,
) -> Fixed64Bundle:
    if finding_query.ndim != 2:
        raise ValueError("finding query must have shape [B, D]")
    batch, width = finding_query.shape
    for name, value in (
        ("state", state_tokens),
        ("transition", transition_tokens),
        ("aligned_prior", aligned_prior_tokens),
    ):
        if value.ndim != 3 or value.shape[0] != batch or value.shape[2] != width:
            raise ValueError(f"{name} token shape drift")
    query = finding_query[:, None, :].expand(-1, 4, -1)
    state = mean_preserving_reduce(state_tokens, 12)
    global_transition = mean_preserving_reduce(transition_tokens, 16)
    centered_transition = transition_tokens - transition_tokens.mean(
        dim=1, keepdim=True
    )
    local_transition = mean_preserving_reduce(centered_transition, 16)
    relation = mean_preserving_reduce(aligned_prior_tokens, 12)
    reserved = torch.zeros(
        batch,
        4,
        width,
        device=finding_query.device,
        dtype=finding_query.dtype,
    )
    tokens = torch.cat(
        (
            query,
            state,
            global_transition,
            local_transition,
            relation,
            reserved,
        ),
        dim=1,
    )
    if tokens.shape != (batch, R38_TOKEN_COUNT, width):
        raise RuntimeError("R38 fixed-64 layout drift")
    type_values = [
        type_id
        for type_id, (_, count) in enumerate(R38_TOKEN_LAYOUT)
        for _ in range(count)
    ]
    token_type_ids = torch.tensor(
        type_values, dtype=torch.long, device=tokens.device
    )[None].expand(batch, -1)
    physical_attention = torch.ones(
        batch, R38_TOKEN_COUNT, dtype=torch.bool, device=tokens.device
    )
    logical_validity = torch.cat(
        (
            torch.ones(
                batch,
                R38_TOKEN_COUNT - 4,
                dtype=torch.bool,
                device=tokens.device,
            ),
            torch.zeros(batch, 4, dtype=torch.bool, device=tokens.device),
        ),
        dim=1,
    )
    return Fixed64Bundle(
        tokens=tokens,
        token_type_ids=token_type_ids,
        physical_attention=physical_attention,
        logical_validity=logical_validity,
    )


def global_transition_tokens(bundle: Fixed64Bundle) -> Tensor:
    return bundle.tokens[:, 16:32]
