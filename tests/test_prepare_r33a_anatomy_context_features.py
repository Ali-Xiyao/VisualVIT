import torch

from scripts.prepare_r33a_anatomy_context_features import (
    anatomy_mask,
    context_mask,
    pool_masked,
)


def test_anatomy_masks_respect_side_and_context_contains_exact():
    left = anatomy_mask("left lower lung").view(14, 14)
    right = anatomy_mask("right lower lung").view(14, 14)
    assert left[:, 7:].sum() > left[:, :7].sum()
    assert right[:, :7].sum() > right[:, 7:].sum()
    exact = anatomy_mask("cardiac silhouette")
    context = context_mask(exact)
    assert bool((context | (~exact)).all())
    assert context.sum() >= exact.sum()
    combined = anatomy_mask("left costophrenic angle, right upper lung").view(14, 14)
    assert combined[:7, :7].any()
    assert combined[9:, 7:].any()


def test_masked_pool_uses_only_registered_support():
    patches = torch.arange(2 * 4 * 3, dtype=torch.float32).view(2, 4, 3)
    mask = torch.tensor([[True, False, False, False], [False, False, True, True]])
    pooled = pool_masked(patches, mask)
    assert torch.equal(pooled[0], patches[0, 0])
    assert torch.equal(pooled[1], patches[1, 2:].mean(0))
