import torch
from torch import nn

from visualvit.prta import (
    PRTATrainingHeads,
    PRTATemporalAdapter,
    cmcp_margin_loss,
    invert_progression_logits,
    state_preservation_loss,
    temporal_inversion_loss,
    transition_alignment_loss,
    prta_variant_registry,
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
    assert output.frozen_current_embedding.shape == (2, 16)
    assert not output.frozen_current_embedding.requires_grad
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


def test_a0_a7_registry_freezes_ablation_semantics():
    variants = prta_variant_registry()
    assert list(variants) == [f"A{index}" for index in range(8)]
    assert variants["A2"].classification
    assert not variants["A2"].transition_alignment
    assert variants["A3"].transition_alignment
    assert variants["A4"].temporal_inversion and not variants["A4"].cmcp
    assert variants["A5"].cmcp and not variants["A5"].temporal_inversion
    assert all(
        (
            variants["A6"].transition_alignment,
            variants["A6"].temporal_inversion,
            variants["A6"].cmcp,
            variants["A6"].state_preservation,
        )
    )
    assert variants["A1"].availability_gated
    assert variants["A7"].availability_gated


def test_training_heads_bridge_biomedclip_text_to_visual_width():
    heads = PRTATrainingHeads(visual_width=16, text_width=8)
    text = torch.randn(3, 8)
    assert heads.finding_query(text).shape == (3, 16)
    projected = heads.transition_text(text)
    assert projected.shape == (3, 16)
    assert torch.allclose(projected.norm(dim=-1), torch.ones(3), atol=1e-6)
    assert heads.progression_logits(projected).shape == (3, 5)
