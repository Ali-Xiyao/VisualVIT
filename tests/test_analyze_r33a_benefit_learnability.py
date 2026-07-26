import torch

from scripts.analyze_r33a_benefit_learnability import (
    finding_interaction_features,
    token_geometry_features,
)


def test_token_geometry_is_row_aligned_and_finite():
    robust = {seed: torch.randn(4, 774) for seed in (17, 29, 43)}
    rich = {seed: value + 0.1 for seed, value in robust.items()}
    result = token_geometry_features(robust, rich)
    assert result.shape[0] == 4
    assert result.shape[1] > 100
    assert bool(torch.isfinite(result).all())


def test_finding_interactions_are_block_sparse():
    base = torch.tensor([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]])
    result = finding_interaction_features(base, ["a", "b", "a"])
    assert result.shape == (3, 8)
    assert result[0, -4:].tolist() == [1.0, 2.0, 0.0, 0.0]
    assert result[1, -4:].tolist() == [0.0, 0.0, 3.0, 4.0]
