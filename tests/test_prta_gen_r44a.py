from pathlib import Path

import pytest

from scripts.build_prta_gen_r44a_roster import (
    image_id,
    receipt_summary,
    resolve_image_path,
    select_rows,
)
from scripts.cache_prta_gen_r44a_tokens import (
    image_inventory,
    prior_shuffle_assignment,
)
from scripts.run_prta_gen_r41a_authorized_sequence import validate_aggregate


CLASSES = ["Stable", "Improved", "Worse", "New", "Resolved"]


def make_rows() -> list[dict]:
    rows = []
    for class_index, label in enumerate(CLASSES):
        for index in range(4):
            rows.append(
                {
                    "patient_id": f"p-{class_index}-{index}",
                    "study_id_curr": f"s-{class_index}-{index}",
                    "finding": "Edema",
                    "progression": label,
                }
            )
    return rows


def test_r44a_selection_is_balanced_and_patient_disjoint():
    selected = select_rows(
        make_rows(),
        namespace="test",
        class_order=list(reversed(CLASSES)),
        partition_counts={
            "train": {label: 2 for label in CLASSES},
            "development": {label: 1 for label in CLASSES},
        },
    )
    train = {row["patient_id"] for row in selected["train"]}
    development = {
        row["patient_id"] for row in selected["development"]
    }
    assert len(train) == 10
    assert len(development) == 5
    assert not train & development


def test_r44a_selection_fails_closed_on_rare_class():
    rows = [
        row
        for row in make_rows()
        if row["progression"] != "Resolved"
        or row["patient_id"].endswith("-0")
    ]
    with pytest.raises(ValueError, match="insufficient R44A support"):
        select_rows(
            rows,
            namespace="test",
            class_order=list(reversed(CLASSES)),
            partition_counts={
                "train": {label: 1 for label in CLASSES},
                "development": {label: 1 for label in CLASSES},
            },
        )


def test_r44a_image_paths_and_ids_are_stable(tmp_path: Path):
    raw = "chexpert/train/patient00001/study1/view1_frontal.jpg"
    resolved = resolve_image_path(tmp_path, raw)
    assert resolved == (
        tmp_path / "train/patient00001/study1/view1_frontal.jpg"
    )
    assert image_id(raw) == image_id(raw.replace("/", "\\"))


def test_r44a_roster_summary_hides_rows():
    summary = receipt_summary(
        {
            "status": "PASS",
            "partitions": {
                "train": {
                    "rows": [{"patient_id": "secret"}],
                    "row_count": 1,
                }
            },
        }
    )
    assert summary["partitions"]["train"] == {"row_count": 1}
    assert "secret" not in str(summary)


def test_r44a_image_inventory_deduplicates_and_rejects_drift():
    rows = [
        {
            "prior_image_id": "a",
            "prior_path": "a.jpg",
            "current_image_id": "b",
            "current_path": "b.jpg",
        },
        {
            "prior_image_id": "a",
            "prior_path": "a.jpg",
            "current_image_id": "c",
            "current_path": "c.jpg",
        },
    ]
    assert image_inventory(rows) == [
        {"dicom_id": "a", "path": "a.jpg"},
        {"dicom_id": "b", "path": "b.jpg"},
        {"dicom_id": "c", "path": "c.jpg"},
    ]
    rows[1]["prior_path"] = "different.jpg"
    with pytest.raises(ValueError, match="multiple paths"):
        image_inventory(rows)


def test_r44a_prior_shuffle_is_same_finding_cross_patient():
    rows = []
    for finding in ("Edema", "Pneumonia"):
        for index in range(3):
            rows.append(
                {
                    "example_id": f"{finding}-{index}",
                    "patient_id": f"{finding}-p-{index}",
                    "finding": finding,
                    "prior_image_id": f"{finding}-prior-{index}",
                }
            )
    assigned = prior_shuffle_assignment(
        rows, seed=44, namespace="test"
    )
    by_prior = {
        row["prior_image_id"]: row for row in rows
    }
    for row in rows:
        donor = by_prior[assigned[row["example_id"]]]
        assert donor["finding"] == row["finding"]
        assert donor["patient_id"] != row["patient_id"]


def test_r44a_go_does_not_unlock_closed_r42_chain():
    config = {
        "protocol_id": "r44a",
        "study_tier": "cross-source-silver",
        "training": {"seeds": [17, 29, 43]},
        "gate": {"downstream_unlock_allowed": False},
        "result_statuses": {
            "aggregate_go": "GO_R44A",
            "aggregate_stop": "STOP_R44A",
        },
    }
    receipt = validate_aggregate(
        config,
        {
            "status": "GO_R44A",
            "protocol_id": "r44a",
            "study_tier": "cross-source-silver",
            "seeds": [17, 29, 43],
            "gate_passed": True,
            "gate_failures": [],
            "development_patients": 250,
            "qwen_free_generation_survival_unlocked": False,
            "r42_unlocked": False,
            "r43_unlocked": False,
            "scientific_claim_allowed": False,
            "protected_300_dev_read": False,
            "revealed_483_test_read": False,
            "gold_outcomes_read": False,
            "external_outcomes_read": False,
        },
    )
    assert receipt["gate_passed"] is True
    assert receipt["r42_unlocked"] is False
