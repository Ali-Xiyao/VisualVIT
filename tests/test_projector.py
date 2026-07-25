from dataclasses import replace

import pytest
import torch

from visualvit.projector import RelationProjector
from visualvit.schemas import TokenBundle


def _bundle(batch_size: int = 2, feature_dim: int = 6) -> TokenBundle:
    torch.manual_seed(11)
    token_types = torch.tensor(
        [0] * 4 + [1] * 28 + [2] * 28 + [3] * 4, dtype=torch.long
    )
    valid_mask = torch.zeros(batch_size, 64, dtype=torch.bool)
    valid_mask[:, :10] = True
    valid_mask[:, 32:37] = True
    # Even if a caller marks reserved positions logically valid, they remain
    # neutral and cannot become sample-label carriers.
    valid_mask[:, -4:] = True
    anatomy_ids = torch.full((batch_size, 64), -1, dtype=torch.long)
    anatomy_ids[:, 4:10] = torch.arange(6)
    temporal_ids = torch.full((batch_size, 64), -1, dtype=torch.long)
    temporal_ids[:, 4:7] = 0
    temporal_ids[:, 7:10] = 1
    confidence = torch.zeros(batch_size, 64)
    confidence[:, :10] = 0.75
    slot_mass = valid_mask.to(torch.float32)
    source_ids = torch.arange(64).view(1, 64).expand(batch_size, -1).clone()
    return TokenBundle(
        tokens=torch.randn(batch_size, 64, feature_dim),
        token_types=token_types,
        valid_mask=valid_mask,
        assignment=torch.zeros(batch_size, 1, 1),
        anatomy_ids=anatomy_ids,
        temporal_ids=temporal_ids,
        confidence=confidence,
        slot_mass=slot_mass,
        source_ids=source_ids,
    )


def test_projector_keeps_64_physical_tokens_and_neutral_fills_invalid_slots():
    bundle = _bundle()
    projector = RelationProjector(input_dim=6, hidden_size=12)
    projected = projector(bundle)
    projected.validate()

    assert projected.embeddings.shape == (2, 64, 12)
    assert torch.equal(projected.token_types, bundle.token_types)
    assert torch.equal(projected.valid_mask, bundle.valid_mask)
    assert torch.equal(projected.attention_mask, torch.ones(2, 64, dtype=torch.long))
    assert projected.position_ids.shape == (3, 2, 64)
    assert torch.equal(projected.position_ids[0], projected.position_ids[1])
    assert torch.equal(projected.position_ids[0], projected.position_ids[2])

    reserved = bundle.token_types.eq(3).unsqueeze(0).expand(2, -1)
    neutral_mask = ~bundle.valid_mask | reserved
    neutral_values = projected.embeddings[neutral_mask]
    expected = projector.neutral_embedding.expand_as(neutral_values)
    assert torch.equal(neutral_values, expected)
    assert projected.audit["neutral_is_shared"]
    assert projected.audit["source_ids_embedded"] is False


def test_projector_embeds_allowed_metadata_but_source_ids_are_audit_only():
    bundle = _bundle(batch_size=1)
    projector = RelationProjector(input_dim=6, hidden_size=12)
    baseline = projector(bundle).embeddings

    changed_anatomy = bundle.anatomy_ids.clone()
    changed_anatomy[0, 4] = 21
    metadata_changed = projector(
        replace(bundle, anatomy_ids=changed_anatomy)
    ).embeddings
    assert not torch.allclose(baseline[:, 4], metadata_changed[:, 4])

    changed_sources = bundle.source_ids.clone()
    changed_sources[0, 4] = 999_999
    source_changed = projector(replace(bundle, source_ids=changed_sources)).embeddings
    assert torch.equal(baseline, source_changed)


def test_projector_accepts_shared_batched_types_and_rejects_layout_drift():
    bundle = _bundle()
    projector = RelationProjector(input_dim=6, hidden_size=12)
    shared_types = bundle.token_types.view(1, -1).expand(2, -1).clone()
    projected = projector(replace(bundle, token_types=shared_types))
    assert projected.token_types.shape == (64,)

    drifted_types = shared_types.clone()
    drifted_types[1, 5] = 2
    with pytest.raises(ValueError, match="share one layout"):
        projector(replace(bundle, token_types=drifted_types))


def test_projector_is_differentiable_and_metadata_ranges_fail_closed():
    bundle = _bundle(batch_size=1)
    projector = RelationProjector(input_dim=6, hidden_size=12)
    projected = projector(bundle)
    weights = torch.linspace(0.1, 1.2, 12)
    loss = (projected.embeddings * weights).square().mean()
    loss.backward()
    gradients = [parameter.grad for parameter in projector.parameters()]
    assert any(
        gradient is not None
        and bool(torch.isfinite(gradient).all())
        and bool(gradient.abs().sum() > 0)
        for gradient in gradients
    )

    invalid_anatomy = bundle.anatomy_ids.clone()
    invalid_anatomy[0, 4] = 512
    with pytest.raises(ValueError, match="outside"):
        projector(replace(bundle, anatomy_ids=invalid_anatomy))
