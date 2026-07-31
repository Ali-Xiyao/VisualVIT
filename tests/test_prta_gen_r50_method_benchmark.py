from __future__ import annotations

# ruff: noqa: E402

import json
from pathlib import Path
import sys

import torch

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE))
sys.path.insert(0, str(WORKSPACE / "src"))

from scripts.r50_common import METHODS, epoch_order
from visualvit.r50_method_baselines import (
    INVERSION_INDEX,
    TACTemporalFusionAdapted,
    invert_class_tensor,
    siamese_signed_abs_features,
    tila_bice_tcl_loss,
    tila_combined_probabilities,
)


CONFIG = (
    WORKSPACE
    / "configs"
    / "prta_gen"
    / "prta_gen_r50_method_benchmark_v1.json"
)


def test_r50_authority_freezes_four_labeled_methods_before_runtime() -> None:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    assert config["status"] == "FROZEN_PRTA_GEN_R50_METHOD_BENCHMARK"
    assert tuple(config["methods"]) == METHODS
    assert config["frozen_after_r49_outcomes_visible"] is True
    assert config["independent_confirmation_claim_allowed"] is False
    assert config["training"]["seeds"] == [17, 29, 43]
    assert config["training"]["epochs"] == 50
    assert config["training"]["tila_tcl_start_epoch_one_based"] == 21
    assert config["training"]["tila_tcl_weight"] == 50.0
    assert config["comparison"]["method_selection_from_r50_outcomes_allowed"] is False
    assert config["cache"]["labels_in_cache"] is False


def test_five_class_inversion_is_an_involution() -> None:
    values = torch.arange(10, dtype=torch.float32).reshape(2, 5)
    inverted = invert_class_tensor(values)
    assert inverted.tolist() == values[:, INVERSION_INDEX].tolist()
    assert torch.equal(invert_class_tensor(inverted), values)


def test_siamese_signed_absolute_features_are_directional() -> None:
    prior = torch.tensor([[1.0, 0.0]])
    current = torch.tensor([[0.0, 1.0]])
    forward = siamese_signed_abs_features(prior, current)
    reversed_ = siamese_signed_abs_features(current, prior)
    assert forward.shape == (1, 8)
    assert not torch.equal(forward, reversed_)
    assert torch.allclose(forward[:, 6:], reversed_[:, 6:])


def test_tila_loss_and_combined_scoring_respect_inversion() -> None:
    forward = torch.tensor([[8.0, 0.0, 0.0, 0.0, 0.0]])
    reversed_ = forward.index_select(-1, torch.tensor(INVERSION_INDEX))
    targets = torch.tensor([0])
    loss, pieces = tila_bice_tcl_loss(
        forward, reversed_, targets, tcl_weight=50.0
    )
    combined = tila_combined_probabilities(forward, reversed_)
    assert loss.item() < 0.01
    assert pieces["tcl"].item() == 0.0
    assert combined.argmax(dim=-1).item() == 0


def test_tac_adapted_preserves_shape_and_uses_temporal_order() -> None:
    torch.manual_seed(7)
    model = TACTemporalFusionAdapted(width=16, heads=4, dropout=0.0).eval()
    prior = torch.randn(2, 5, 16)
    current = torch.randn(2, 5, 16)
    forward = model(prior, current)
    reversed_ = model(current, prior)
    assert forward.shape == (2, 16)
    assert torch.allclose(forward.norm(dim=-1), torch.ones(2), atol=1e-5)
    assert not torch.allclose(forward, reversed_)


def test_epoch_order_is_seeded_and_method_independent() -> None:
    rows = [{"example_id": str(index)} for index in range(20)]
    first = epoch_order(rows, namespace="r50", seed=17, epoch=2)
    second = epoch_order(rows, namespace="r50", seed=17, epoch=2)
    different = epoch_order(rows, namespace="r50", seed=29, epoch=2)
    assert first == second
    assert first != different
    assert sorted(first) == list(range(20))
