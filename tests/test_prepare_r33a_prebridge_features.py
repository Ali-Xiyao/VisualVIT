import torch

from scripts.prepare_r33a_prebridge_features import (
    FEATURE_DIM,
    PREBRIDGE_WIDTH,
    assemble_prebridge,
    prebridge_projection,
)


def test_prebridge_has_fixed_blocks_and_rich_fraction():
    batch = 3
    widths = {"query": 7, "state": 9, "global": 11, "local": 13, "relation": 15}
    matrices = {
        name: prebridge_projection(
            width,
            seed=100 + offset,
            device=torch.device("cpu"),
        )
        for offset, (name, width) in enumerate(widths.items())
    }
    sources = {name: torch.randn(batch, width) for name, width in widths.items()}
    robust = assemble_prebridge(
        sources["query"],
        sources["state"],
        sources["global"],
        sources["local"],
        sources["relation"],
        matrices,
        rich=False,
    )
    rich = assemble_prebridge(
        sources["query"],
        sources["state"],
        sources["global"],
        sources["local"],
        sources["relation"],
        matrices,
        rich=True,
    )
    assert robust.shape == rich.shape == (batch, FEATURE_DIM)
    assert torch.equal(robust[:, : 5 * PREBRIDGE_WIDTH], rich[:, : 5 * PREBRIDGE_WIDTH])
    assert torch.allclose(robust[:, -2], torch.full((batch,), 4 / 12))
    assert torch.equal(rich[:, -2], torch.ones(batch))
