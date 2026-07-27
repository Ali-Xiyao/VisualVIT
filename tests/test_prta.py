import torch
from torch import nn

from visualvit.prta import (
    PRTATemporalAdapter,
    cmcp_margin_loss,
    invert_progression_logits,
    state_preservation_loss,
    temporal_inversion_loss,
    transition_alignment_loss,
)


def tiny_model():
    return PRTATemporalAdapter(
        [nn.Linear(16, 16, bias=False) for _ in range(4)],
        width=16,
        heads=4,
        adapter_rank=4,
        state_tokens=3,
        transition_tokens=5,
    )


def test_prta_shapes_and_frozen_base():
    model = tiny_model()
    prior = torch.randn(2, 7, 16)
    current = torch.randn(2, 7, 16)
    query = torch.randn(2, 16)
    output = model(prior, current, query)
    assert output.state_tokens.shape == (2, 3, 16)
    assert output.transition_tokens.shape == (2, 5, 16)
    assert output.state_embedding.shape == (2, 16)
    assert output.transition_embedding.shape == (2, 16)
    assert output.aligned_prior_tokens.shape == (2, 7, 16)
    assert all(
        not parameter.requires_grad
        for parameter in model.tail.frozen_blocks.parameters()
    )
    assert any(
        parameter.requires_grad for parameter in model.tail.adapters.parameters()
    )


def test_backward_reaches_adapter_but_not_frozen_blocks():
    model = tiny_model()
    output = model(
        torch.randn(2, 7, 16),
        torch.randn(2, 7, 16),
        torch.randn(2, 16),
    )
    output.transition_embedding.sum().backward()
    assert all(
        parameter.grad is None
        for parameter in model.tail.frozen_blocks.parameters()
    )
    assert all(
        any(parameter.grad is not None for parameter in adapter.parameters())
        for adapter in model.tail.adapters
    )


def test_transition_alignment_prefers_matching_pairs():
    embeddings = torch.eye(4)
    aligned = transition_alignment_loss(embeddings, embeddings)
    permuted = transition_alignment_loss(embeddings, embeddings.flip(0))
    assert aligned < permuted


def test_cmcp_margin_is_zero_when_true_pair_wins_by_margin():
    target = torch.tensor([[1.0, 0.0]])
    true = target.clone()
    counterfactual = torch.tensor([[0.0, 1.0]])
    assert cmcp_margin_loss(true, counterfactual, target).item() == 0.0
    assert cmcp_margin_loss(counterfactual, true, target).item() > 0.0


def test_inversion_mapping_and_loss():
    logits = torch.tensor([[1.0, 2.0, 3.0, 4.0, 5.0]])
    assert torch.equal(
        invert_progression_logits(logits),
        torch.tensor([[1.0, 3.0, 2.0, 5.0, 4.0]]),
    )
    assert temporal_inversion_loss(
        logits, invert_progression_logits(logits)
    ).item() < 1e-6


def test_state_preservation_is_zero_for_identical_vectors():
    state = torch.randn(3, 8)
    assert state_preservation_loss(state, state).abs().item() < 1e-6
