from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from scripts.audit_prta_gen_r44_independent_support import (
    audit_chextemporal_support,
)


CLASSES = ["Stable", "Improved", "Worse", "New", "Resolved"]


def make_frame(tmp_path: Path) -> pd.DataFrame:
    rows = []
    image_root = tmp_path / "images"
    image_root.mkdir()
    for class_index, progression in enumerate(CLASSES):
        for row_index in range(4):
            patient = f"p-{class_index}-{row_index}"
            prior = f"{patient}-prior.jpg"
            current = f"{patient}-current.jpg"
            (image_root / prior).touch()
            (image_root / current).touch()
            rows.append(
                {
                    "dataset": "chexpert",
                    "patient_id": patient,
                    "study_id_curr": f"curr-{patient}",
                    "study_id_prev": f"prev-{patient}",
                    "finding": "Edema",
                    "progression": progression,
                    "parent_image_curr": current,
                    "parent_image_prev": prior,
                }
            )
    return pd.DataFrame(rows)


def test_support_audit_is_patient_disjoint_and_scalar(
    tmp_path: Path,
) -> None:
    frame = make_frame(tmp_path)
    result = audit_chextemporal_support(
        frame=frame,
        gold_patients={"p-0-0"},
        image_root=tmp_path / "images",
        dataset_filter="chexpert",
        classes=CLASSES,
        class_order=["Resolved", "New", "Improved", "Worse", "Stable"],
        namespace="test",
        partition_counts={
            "train": {label: 1 for label in CLASSES},
            "development": {label: 1 for label in CLASSES},
        },
    )
    assert result["missing_image_references"] == 0
    assert result["indexed_parent_image_files"] == 40
    assert result["gold_patients_absent"] is True
    assert result["patient_partitions_disjoint"] is True
    assert result["selected_counts_in_memory_only"]["train"]["rows"] == 5
    assert (
        result["selected_counts_in_memory_only"]["development"]["rows"] == 5
    )
    assert "patient_id" not in str(result)


def test_support_audit_resolves_chexpert_prefix(tmp_path: Path) -> None:
    frame = make_frame(tmp_path)
    frame["parent_image_curr"] = (
        "chexpert/" + frame["parent_image_curr"].astype(str)
    )
    frame["parent_image_prev"] = (
        "chexpert/" + frame["parent_image_prev"].astype(str)
    )
    result = audit_chextemporal_support(
        frame=frame,
        gold_patients=set(),
        image_root=tmp_path / "images",
        dataset_filter="chexpert",
        classes=CLASSES,
        class_order=["Resolved", "New", "Improved", "Worse", "Stable"],
        namespace="test",
        partition_counts={
            "train": {label: 1 for label in CLASSES},
            "development": {label: 1 for label in CLASSES},
        },
    )
    assert result["support_sufficient"] is True
    assert result["missing_image_references"] == 0


def test_support_audit_rejects_missing_image(tmp_path: Path) -> None:
    frame = make_frame(tmp_path)
    (tmp_path / "images" / "p-4-0-current.jpg").unlink()
    result = audit_chextemporal_support(
        frame=frame,
        gold_patients=set(),
        image_root=tmp_path / "images",
        dataset_filter="chexpert",
        classes=CLASSES,
        class_order=[
            "Resolved",
            "New",
            "Improved",
            "Worse",
            "Stable",
        ],
        namespace="test",
        partition_counts={
            "train": {label: 2 for label in CLASSES},
            "development": {label: 2 for label in CLASSES},
        },
    )
    assert result["support_sufficient"] is False
    assert result["support_gate_failures"] == [
        "insufficient_patient_disjoint_class_support"
    ]
    assert result["selected_counts_in_memory_only"]["train"]["rows"] == 0


def test_support_audit_rejects_progression_registry_drift(
    tmp_path: Path,
) -> None:
    frame = make_frame(tmp_path)
    frame.loc[0, "progression"] = "Unknown"
    with pytest.raises(ValueError, match="progression registry drift"):
        audit_chextemporal_support(
            frame=frame,
            gold_patients=set(),
            image_root=tmp_path / "images",
            dataset_filter="chexpert",
            classes=CLASSES,
            class_order=[
                "Resolved",
                "New",
                "Improved",
                "Worse",
                "Stable",
            ],
            namespace="test",
            partition_counts={
                "train": {label: 1 for label in CLASSES},
                "development": {label: 1 for label in CLASSES},
            },
        )
