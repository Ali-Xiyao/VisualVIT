import pytest
import torch

from scripts.run_prta_gen_r40a_probe import (
    align_targets,
    query_only_features,
    select_field_rows,
    validate_args,
)


def test_validate_args_is_fail_closed():
    config = {
        "supported_probe_classes": {
            "laterality": ["Left", "Right", "Bilateral"]
        },
        "probe": {"seeds": [17, 29, 43]},
    }
    assert validate_args(config, field="laterality", seed=17) == (
        "Left",
        "Right",
        "Bilateral",
    )
    with pytest.raises(ValueError, match="unregistered"):
        validate_args(config, field="degree", seed=17)
    with pytest.raises(ValueError, match="seed drift"):
        validate_args(config, field="laterality", seed=7)


def test_alignment_requires_exact_example_and_patient_order():
    rows = [
        {"example_id": "b", "patient_id": "patient-b"},
        {"example_id": "a", "patient_id": "patient-a"},
    ]
    aligned = align_targets(
        ["a", "b"], ["patient-a", "patient-b"], rows
    )
    assert [row["example_id"] for row in aligned] == ["a", "b"]
    with pytest.raises(ValueError, match="patient order drift"):
        align_targets(["a", "b"], ["patient-b", "patient-a"], rows)


def test_query_only_is_finding_one_hot_and_field_selection_matches_features():
    rows = [
        {
            "example_id": "a",
            "patient_id": "p1",
            "finding": "Edema",
            "laterality": "Left",
        },
        {
            "example_id": "b",
            "patient_id": "p2",
            "finding": "Pneumothorax",
            "laterality": "Unspecified",
        },
        {
            "example_id": "c",
            "patient_id": "p3",
            "finding": "Edema",
            "laterality": "Right",
        },
    ]
    query = query_only_features(rows, ("Edema", "Pneumothorax"))
    features = {
        "true_pair": torch.arange(12).view(3, 4).float(),
        "query_only": query,
    }
    selected_rows, selected_features, targets = select_field_rows(
        rows,
        features,
        field="laterality",
        classes=("Left", "Right", "Bilateral"),
    )

    assert query.tolist() == [[1, 0], [0, 1], [1, 0]]
    assert [row["example_id"] for row in selected_rows] == ["a", "c"]
    assert selected_features["true_pair"].shape == (2, 4)
    assert targets.tolist() == [0, 1]
