import torch

from scripts.prepare_r33a_direct_transition_features import (
    SUMMARY_WIDTH,
    assemble_summary,
    pair_interactions,
    projection,
    transition_sources,
)


def test_pair_interactions_are_five_matched_blocks():
    prior = torch.randn(3, 8)
    current = torch.randn(3, 8)
    assert pair_interactions(prior, current).shape == (3, 40)


def test_direct_sources_and_summary_preserve_contract():
    prior = torch.randn(2, 197, 8)
    current = torch.randn(2, 197, 8)
    source = transition_sources(prior, current)
    matrices = {
        "query": projection(4, 1, torch.device("cpu")),
        "state": projection(8, 2, torch.device("cpu")),
        "global": projection(40, 3, torch.device("cpu")),
        "local": projection(40, 4, torch.device("cpu")),
        "relation": projection(40, 5, torch.device("cpu")),
    }
    summary = assemble_summary(
        torch.eye(4)[:2],
        source["state"],
        source["global"],
        source["rich_local"],
        source["rich_relation"],
        matrices,
        rich=True,
    )
    assert summary.shape == (2, SUMMARY_WIDTH)
    assert bool(torch.isfinite(summary).all())
    assert summary[:, 768:].shape == (2, 6)
