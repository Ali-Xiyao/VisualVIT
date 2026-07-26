from __future__ import annotations

import torch

from scripts import run_r30_regularized_multiscale as r30


def test_projection_preserves_scale_blocks_and_query() -> None:
    raw = {
        name: torch.arange(80, dtype=torch.float32).reshape(10, 8)
        for name in ("global", "exact", "context")
    }
    query = torch.eye(10, 4)
    geometry = torch.ones(10, 3)
    values, hashes = r30.project_multiscale(
        raw, query, geometry, seed=17
    )
    assert values.shape == (10, 3 * r30.PROJECTION_DIM + 7)
    assert set(hashes) == {"global", "exact", "context"}
    assert torch.equal(values[:, -7:-3], query)
    assert torch.equal(values[:, -3:], geometry)


def test_sample_weights_balance_patients_and_classes() -> None:
    records = [
        {"patient_id": "a"},
        {"patient_id": "a"},
        {"patient_id": "b"},
        {"patient_id": "c"},
    ]
    indices = torch.arange(4)
    targets = torch.tensor([0, 0, 1, 2])
    weights = r30.sample_weights(records, indices, targets)
    assert weights.shape == (4,)
    assert weights[0] == weights[1]
    assert weights[2] == weights[3]
    assert weights[2] == 4 * weights[0]
