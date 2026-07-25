from __future__ import annotations

# ruff: noqa: E402

from pathlib import Path
import sys

import pandas as pd
import pytest

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE))

from scripts.audit_chextemporal_annotations import (
    bbox_semantics,
    target_conflict_profile,
    validate_boxes,
)


def _box(label: str, offset: int = 0) -> dict[str, int | str]:
    return {
        "label": label,
        "x1": 1 + offset,
        "y1": 2 + offset,
        "x2": 11 + offset,
        "y2": 12 + offset,
    }


def _row(
    progression: str,
    *,
    patient_id: str = "patient1",
    prior: list[dict[str, int | str]] | None = None,
    current: list[dict[str, int | str]] | None = None,
) -> dict[str, object]:
    return {
        "dataset": "chexpert",
        "patient_id": patient_id,
        "study_id_prev": "study1",
        "study_id_curr": "study2",
        "img_path_prev": f"{patient_id}/study1/prior.jpg",
        "img_path_curr": f"{patient_id}/study2/current.jpg",
        "disease_name": "lung opacity",
        "progression": progression,
        "prior_bboxes": prior or [],
        "current_bboxes": current or [],
    }


def test_conflicting_targets_are_measured_at_exact_model_input_grain() -> None:
    frame = pd.DataFrame(
        [
            _row("Stable"),
            _row("Worse"),
            _row("New", patient_id="patient2"),
        ]
    )

    profile = target_conflict_profile(frame)

    assert profile["prediction_keys"] == 2
    assert profile["conflicting_prediction_keys"] == 1
    assert profile["rows_in_conflicting_prediction_keys"] == 2
    assert profile["deterministic_single_label_correct_ceiling_rows"] == 2
    assert profile["deterministic_single_label_accuracy_ceiling"] == pytest.approx(
        2 / 3
    )


def test_multifocal_new_row_does_not_require_whole_prior_array_empty() -> None:
    prior = [_box("Box1")]
    current = [_box("Box1"), _box("Box2", offset=20)]
    frame = pd.DataFrame(
        [
            _row("Stable", prior=prior, current=current),
            _row("New", prior=prior, current=current),
        ]
    )

    profile = bbox_semantics(frame)

    assert (
        profile["legacy_whole_row_empty_side_mismatch_counts"][
            "new_requires_prior_empty_current_nonempty"
        ]
        == 1
    )
    assert profile["progression_support_incompatible_rows"] == 0
    assert profile["multi_progression_prediction_keys"] == 1
    assert profile["multi_progression_keys_with_identical_full_box_payloads"] == 1


def test_progression_support_check_fails_when_no_compatible_identity_exists() -> None:
    shared = [_box("Box1")]
    frame = pd.DataFrame([_row("New", prior=shared, current=shared)])

    profile = bbox_semantics(frame)

    assert profile["progression_support_incompatible_rows"] == 1
    assert profile["progression_support_incompatible_by_label"] == [
        {"progression": "New", "rows": 1}
    ]


def test_duplicate_correspondence_labels_are_counted_by_row_and_side() -> None:
    frame = pd.DataFrame(
        [
            _row(
                "Stable",
                prior=[_box("Box1"), _box("Box1", offset=20)],
                current=[_box("Box1")],
            )
        ]
    )

    profile = validate_boxes(frame)

    assert profile["duplicate_box_labels_within_side_count"] == 1
    assert profile["rows_with_duplicate_box_labels_within_side"] == 1
    assert profile["rows_with_duplicate_box_labels_by_side"] == {
        "prior_bboxes": 1,
        "current_bboxes": 0,
    }
