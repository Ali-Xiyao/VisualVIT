import torch

from visualvit.hierarchical_temporal_tokens import (
    HierarchicalTemporalTokenBuilder,
    TOKEN_BUDGET,
    fixed_token_types,
)
from visualvit.tier_token_projector import TierTokenProjector


def test_robust_rich_have_identical_exact_64_layout_and_no_label_inputs():
    torch.manual_seed(5)
    builder = HierarchicalTemporalTokenBuilder(feature_dim=8, query_dim=6)
    pair = builder(
        torch.randn(3, 17, 8),
        torch.randn(3, 17, 8),
        torch.randn(3, 6),
    )
    assert pair.robust.tokens.shape == (3, TOKEN_BUDGET, 8)
    assert pair.rich.tokens.shape == (3, TOKEN_BUDGET, 8)
    assert torch.equal(pair.robust.token_types, fixed_token_types())
    assert torch.equal(pair.robust.token_types, pair.rich.token_types)
    assert pair.robust.assignment.shape == (3, 1, 1)


def test_tier_projector_keeps_all_physical_attention_and_shared_neutral():
    torch.manual_seed(7)
    pair = HierarchicalTemporalTokenBuilder(8)(
        torch.randn(2, 10, 8),
        torch.randn(2, 10, 8),
        torch.randn(2, 8),
    )
    projector = TierTokenProjector(8, 12)
    robust = projector(pair.robust)
    rich = projector(pair.rich)
    assert bool(robust.attention_mask.eq(1).all())
    assert bool(rich.attention_mask.eq(1).all())
    assert robust.audit["neutral_is_shared"] is True
    assert rich.audit["neutral_is_shared"] is True
    assert robust.embeddings.shape == rich.embeddings.shape == (2, 64, 12)
