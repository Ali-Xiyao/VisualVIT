from __future__ import annotations

import torch

from visualvit.context_transition import (
    expand_box,
    fit_transition_head,
    map_anatomy,
    pair_interactions,
    union_box,
)


def test_anatomy_aliases_and_fallback_are_deterministic() -> None:
    available = {
        "left lung",
        "right lung",
        "left lower lung zone",
        "right lower lung zone",
        "cardiac silhouette",
    }
    assert map_anatomy("left lower lung", available) == [
        "left lower lung zone"
    ]
    assert map_anatomy("cardiac silhouette", available) == [
        "cardiac silhouette"
    ]
    assert map_anatomy("unknown structure", available) == [
        "left lung",
        "right lung",
    ]
    coarse = {"left lung", "right lung", "cardiac silhouette"}
    assert map_anatomy("right lower lung, left lower lung", coarse) == [
        "right lung",
        "left lung",
    ]
    sparse = {"left upper lung zone", "right costophrenic angle"}
    assert map_anatomy("right lower lung, left lower lung", sparse) == [
        "right costophrenic angle",
        "left upper lung zone",
    ]


def test_union_and_expansion_contract() -> None:
    objects = [
        {"bbox_name": "left lung", "x1": 100, "y1": 20, "x2": 170, "y2": 180},
        {"bbox_name": "right lung", "x1": 30, "y1": 25, "x2": 100, "y2": 175},
    ]
    exact = union_box(objects, ["left lung", "right lung"])
    assert exact == (30.0, 20.0, 170.0, 180.0)
    context = expand_box(exact)
    assert context[0] <= exact[0] and context[2] >= exact[2]
    assert all(0 <= value <= 224 for value in context)


def test_pair_interactions_shape_and_finite() -> None:
    prior = torch.arange(8, dtype=torch.float32)
    current = torch.arange(8, dtype=torch.float32).flip(0)
    value = pair_interactions(prior, current)
    assert value.shape == (40,)
    assert torch.isfinite(value).all()


def test_transition_head_overfits_separable_toy() -> None:
    targets = torch.arange(3).repeat_interleave(20)
    values = torch.nn.functional.one_hot(targets, num_classes=3).float()
    logits, fit = fit_transition_head(
        values,
        targets,
        values,
        seed=17,
        class_count=3,
        steps=150,
    )
    assert fit["finite"] is True
    assert float((logits.argmax(-1) == targets).float().mean()) >= 0.95
