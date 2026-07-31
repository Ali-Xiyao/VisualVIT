from __future__ import annotations

import torch

from scripts.run_prta_gen_r45_cdeb_discovery import (
    _arm_tokens,
    fit_feature_normalization,
    receipt_summary,
    stable_epoch_key,
)

def test_r45_stable_epoch_key_is_method_specific() -> None:
    first = stable_epoch_key(17, "full_cdeb", 0, "example")
    assert first == stable_epoch_key(17, "full_cdeb", 0, "example")
    assert first != stable_epoch_key(17, "baseline_projector", 0, "example")


def test_r45_query_only_uses_zero_source_and_reference() -> None:
    row = {"example_id": "a"}
    loaded = {
        "true_pair": {"a": torch.ones(64, 768)},
        "current_only": {"a": torch.ones(64, 768) * 2},
        "prior_shuffle": {"a": torch.ones(64, 768) * 3},
    }
    source, reference = _arm_tokens(row, loaded, "query_only")
    assert source.eq(0).all()
    assert reference.eq(0).all()


def test_r45_delta_normalization_is_fit_on_training_rows() -> None:
    rows = [{"example_id": "a"}, {"example_id": "b"}]
    loaded = {
        "true_pair": {
            "a": torch.ones(64, 768) * 3,
            "b": torch.ones(64, 768) * 7,
        },
        "current_only": {
            "a": torch.ones(64, 768),
            "b": torch.ones(64, 768) * 3,
        },
    }
    mean, std = fit_feature_normalization(rows, loaded, mode="delta")
    assert mean.shape == (1, 3840)
    assert std.shape == (1, 3840)
    assert torch.allclose(mean, torch.full_like(mean, 3.0))
    assert torch.allclose(std, torch.full_like(std, 1.0))


def test_r45_receipt_summary_hides_alignment_arrays() -> None:
    summary = receipt_summary(
        {
            "status": "PASS",
            "development_patient_ids": ["secret"],
            "development_example_ids": ["secret"],
            "targets": [1],
            "predictions": {"true_pair": [1]},
            "metrics": {"true_pair": {"macro_f1": 1.0}},
        }
    )
    assert "secret" not in str(summary)
    assert "targets" not in summary
    assert "predictions" not in summary
