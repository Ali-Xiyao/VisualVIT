from __future__ import annotations

import pytest
import torch

from visualvit.matching import oracle_plan_from_entity_ids
from visualvit.real_qualification import (
    annotation_canvas_size,
    correspondence_support,
    entity_ids,
    greedy_plan_from_utilities,
    map_annotation_box,
    match_sufficient_statistics,
    metrics_from_sufficient_statistics,
    patient_cluster_bootstrap,
    plan_objective,
)
from visualvit.schemas import MatchPlan, RegionBatch


def _regions() -> RegionBatch:
    prior_ids, current_ids = entity_ids(["Box1", "Box2"], ["Box1", "Box3"])
    return RegionBatch(
        prior_features=torch.tensor([[[0.0, 0.0, 1.0], [0.0, 0.0, 2.0]]]),
        current_features=torch.tensor([[[0.0, 0.0, 1.0], [0.0, 0.0, 3.0]]]),
        prior_valid=torch.ones(1, 2, dtype=torch.bool),
        current_valid=torch.ones(1, 2, dtype=torch.bool),
        prior_anatomy=torch.zeros(1, 2, dtype=torch.long),
        current_anatomy=torch.zeros(1, 2, dtype=torch.long),
        prior_entity_ids=prior_ids.unsqueeze(0),
        current_entity_ids=current_ids.unsqueeze(0),
    )


def test_aspect_preserving_annotation_canvas_maps_each_axis_separately() -> None:
    width, height = annotation_canvas_size(rows=3000, columns=2000)
    assert width == pytest.approx(1024.0)
    assert height == pytest.approx(1536.0)

    mapped = map_annotation_box(
        {"label": "Box1", "x1": 256, "y1": 384, "x2": 768, "y2": 1152},
        rows=3000,
        columns=2000,
    )
    assert (mapped.x1, mapped.y1, mapped.x2, mapped.y2) == pytest.approx(
        (56.0, 56.0, 168.0, 168.0)
    )
    assert mapped.geometry() == pytest.approx((0.5, 0.5, 0.5, 0.5))


def test_invalid_annotation_box_fails_instead_of_silent_clipping() -> None:
    with pytest.raises(ValueError, match="outside"):
        map_annotation_box(
            {"label": "Box1", "x1": 0, "y1": 0, "x2": 1025, "y2": 20},
            rows=1024,
            columns=1024,
        )
    with pytest.raises(ValueError, match="nonpositive"):
        map_annotation_box(
            {"label": "Box1", "x1": 20, "y1": 0, "x2": 20, "y2": 20},
            rows=1024,
            columns=1024,
        )


def test_correspondence_support_requires_unique_labels_and_correct_null_side() -> None:
    support = correspondence_support(
        "New",
        ["Box1"],
        ["Box1", "Box2"],
    )
    assert support == {
        "shared": ["Box1"],
        "deaths": [],
        "births": ["Box2"],
        "compatible": True,
    }
    assert not correspondence_support("Resolved", ["Box1"], ["Box1"])["compatible"]
    with pytest.raises(ValueError, match="unique"):
        correspondence_support("Stable", ["Box1", "Box1"], ["Box1"])


def test_match_statistics_cover_persistent_death_and_birth_events() -> None:
    regions = _regions()
    gold = oracle_plan_from_entity_ids(regions)
    perfect = match_sufficient_statistics(gold, gold, regions)
    perfect_metrics = metrics_from_sufficient_statistics(perfect)
    assert perfect_metrics == {
        "persistent_edge_precision": 1.0,
        "persistent_edge_recall": 1.0,
        "persistent_edge_f1": 1.0,
        "exact_row_recovery": 1.0,
        "three_event_macro_f1": 1.0,
    }

    wrong_transport = torch.zeros_like(gold.transport)
    wrong_transport[0, 0, 1] = 1
    wrong_transport[0, 1, 2] = 1
    wrong_transport[0, 2, 0] = 1
    wrong = MatchPlan(wrong_transport, mode="wrong")
    statistics = match_sufficient_statistics(wrong, gold, regions)
    metrics = metrics_from_sufficient_statistics(statistics)
    assert statistics["edge_tp"] == 0
    assert statistics["edge_fp"] == 1
    assert statistics["edge_fn"] == 1
    assert metrics["persistent_edge_f1"] == 0.0
    assert metrics["exact_row_recovery"] == 0.0


def test_patient_bootstrap_resamples_whole_patient_clusters() -> None:
    regions = _regions()
    gold = oracle_plan_from_entity_ids(regions)
    perfect = match_sufficient_statistics(gold, gold, regions)
    patient_statistics = {"p1": [perfect, perfect], "p2": [perfect]}

    result = patient_cluster_bootstrap(
        patient_statistics,
        seed=20260724,
        replicates=100,
        randomized_patient_statistics=patient_statistics,
    )

    assert result["patient_count"] == 2
    assert result["replicates"] == 100
    assert result["point"]["persistent_edge_f1"] == 1.0
    assert result["percentile_95_ci"]["persistent_edge_f1"] == {
        "lower": 1.0,
        "upper": 1.0,
    }
    assert result["persistent_edge_f1_delta"] == {
        "point": 0.0,
        "lower": 0.0,
        "upper": 0.0,
    }


def test_greedy_baseline_is_feasible_and_uses_same_objective() -> None:
    regions = _regions()
    edges = torch.tensor([[[0.9, 0.8], [0.7, -0.2]]])
    prior_null = torch.zeros(1, 2)
    current_null = torch.zeros(1, 2)

    greedy = greedy_plan_from_utilities(
        regions,
        edges,
        prior_null,
        current_null,
    )

    assert greedy.transport[0, 0, 0] == 1
    assert greedy.transport[0, 1, 2] == 1
    assert plan_objective(
        greedy,
        regions,
        edges,
        prior_null,
        current_null,
    ) == pytest.approx(0.9)
