from __future__ import annotations

import torch

from scripts.r39_common import token_bundle
from visualvit.cdeb import (
    CausalDeltaEvidenceBottleneck,
    EVIDENCE_POSITIONS,
    inject_cdeb_evidence,
)
from visualvit.tier_token_projector import TierTokenProjector


def make_model(feature_mode: str = "delta") -> CausalDeltaEvidenceBottleneck:
    return CausalDeltaEvidenceBottleneck(
        feature_mean=torch.zeros(1, 3840),
        feature_std=torch.ones(1, 3840),
        feature_mode=feature_mode,
        qwen_hidden_size=32,
    )


def test_cdeb_delta_features_ignore_reserve_positions() -> None:
    model = make_model()
    true = torch.randn(2, 64, 768)
    current = torch.randn(2, 64, 768)
    first = model.decision_features(true, current)
    true[:, 60:] = 1000
    current[:, 60:] = -1000
    second = model.decision_features(true, current)
    assert torch.equal(first, second)


def test_cdeb_distribution_and_evidence_contract() -> None:
    model = make_model()
    logits, distribution, evidence = model(
        torch.randn(3, 64, 768),
        torch.randn(3, 64, 768),
    )
    assert logits.shape == (3, 5)
    assert distribution.shape == (3, 5)
    assert torch.allclose(distribution.sum(dim=-1), torch.ones(3))
    assert evidence.shape == (3, 4, 32)
    assert torch.isfinite(evidence).all()


def test_no_delta_arm_uses_true_pair_features() -> None:
    model = make_model(feature_mode="true_pair")
    true = torch.randn(2, 64, 768)
    first = model.decision_features(true, torch.randn(2, 64, 768))
    second = model.decision_features(true, torch.randn(2, 64, 768))
    assert torch.equal(first, second)


def test_injection_changes_only_registered_reserve_embeddings() -> None:
    projector = TierTokenProjector(input_dim=768, hidden_size=32)
    base = projector(token_bundle(torch.randn(2, 64, 768)))
    evidence = torch.randn(2, 4, 32)
    injected = inject_cdeb_evidence(base, evidence, enabled=True)
    assert torch.equal(
        injected.embeddings[:, :60], base.embeddings[:, :60]
    )
    assert torch.equal(
        injected.embeddings[:, EVIDENCE_POSITIONS], evidence
    )
    assert injected.valid_mask[:, EVIDENCE_POSITIONS].all()
    assert injected.audit["cdeb_evidence_enabled"] is True
    assert injected.attention_mask.eq(1).all()


def test_delta_no_bridge_preserves_neutral_projection() -> None:
    projector = TierTokenProjector(input_dim=768, hidden_size=32)
    base = projector(token_bundle(torch.randn(2, 64, 768)))
    output = inject_cdeb_evidence(
        base, torch.randn(2, 4, 32), enabled=False
    )
    assert output.embeddings.data_ptr() == base.embeddings.data_ptr()
    assert torch.equal(output.valid_mask, base.valid_mask)
    assert output.audit["cdeb_evidence_enabled"] is False
