from __future__ import annotations

import torch

from visualvit.r38_fixed64 import (
    R38_TOKEN_LAYOUT,
    global_transition_tokens,
    mean_preserving_reduce,
    pack_fixed64,
)


def test_mean_preserving_reduce_preserves_global_mean() -> None:
    tokens = torch.randn(3, 20, 8)
    reduced = mean_preserving_reduce(tokens, 16)
    assert reduced.shape == (3, 16, 8)
    assert torch.allclose(reduced.mean(1), tokens.mean(1), atol=1e-6)


def test_fixed64_layout_attention_and_neutral_reserved() -> None:
    query = torch.randn(2, 8)
    state = torch.randn(2, 20, 8)
    transition = torch.randn(2, 20, 8)
    aligned = torch.randn(2, 197, 8)
    bundle = pack_fixed64(
        finding_query=query,
        state_tokens=state,
        transition_tokens=transition,
        aligned_prior_tokens=aligned,
    )
    assert bundle.tokens.shape == (2, 64, 8)
    assert bundle.physical_attention.all()
    assert bundle.logical_validity[:, :60].all()
    assert not bundle.logical_validity[:, 60:].any()
    assert bundle.tokens[:, 60:].eq(0).all()
    expected_types = [
        type_id
        for type_id, (_, count) in enumerate(R38_TOKEN_LAYOUT)
        for _ in range(count)
    ]
    assert bundle.token_type_ids[0].tolist() == expected_types
    assert torch.allclose(
        global_transition_tokens(bundle).mean(1),
        transition.mean(1),
        atol=1e-6,
    )


def test_fixed64_packing_has_no_label_or_route_input() -> None:
    argument_names = set(pack_fixed64.__annotations__)
    assert "label" not in argument_names
    assert "logits" not in argument_names
    assert "route" not in argument_names
