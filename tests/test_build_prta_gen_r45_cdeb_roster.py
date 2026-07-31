from __future__ import annotations

import pytest

from scripts.build_prta_gen_r45_cdeb_roster import (
    _assert_disjoint,
    receipt_summary,
    select_rows,
)


CLASSES = ["Stable", "Improved", "Worse", "New", "Resolved"]
PARTITIONS = ["confirmation", "qualification", "development", "train"]


def make_rows() -> list[dict]:
    rows: list[dict] = []
    for class_index, label in enumerate(CLASSES):
        for index in range(5):
            rows.append(
                {
                    "patient_id": f"p-{class_index}-{index}",
                    "study_id_curr": f"s-{class_index}-{index}",
                    "finding": "Edema",
                    "progression": label,
                }
            )
    return rows


def test_r45_selection_is_balanced_disjoint_and_sealed_first() -> None:
    selected = select_rows(
        make_rows(),
        namespace="test",
        partition_order=PARTITIONS,
        class_order=list(reversed(CLASSES)),
        counts={
            partition: {label: 1 for label in CLASSES}
            for partition in PARTITIONS
        },
    )
    _assert_disjoint(selected)
    assert list(selected) == PARTITIONS
    assert all(len(rows) == 5 for rows in selected.values())
    assert len(
        {
            row["patient_id"]
            for rows in selected.values()
            for row in rows
        }
    ) == 20


def test_r45_selection_rejects_partition_order_drift() -> None:
    with pytest.raises(ValueError, match="partition order"):
        select_rows(
            make_rows(),
            namespace="test",
            partition_order=list(reversed(PARTITIONS)),
            class_order=list(reversed(CLASSES)),
            counts={
                partition: {label: 1 for label in CLASSES}
                for partition in PARTITIONS
            },
        )


def test_r45_selection_fails_closed_on_rare_class() -> None:
    rows = [
        row
        for row in make_rows()
        if row["progression"] != "Resolved"
        or row["patient_id"].endswith("-0")
    ]
    with pytest.raises(ValueError, match="insufficient R45 support"):
        select_rows(
            rows,
            namespace="test",
            partition_order=PARTITIONS,
            class_order=list(reversed(CLASSES)),
            counts={
                partition: {label: 1 for label in CLASSES}
                for partition in PARTITIONS
            },
        )


def test_r45_disjoint_check_rejects_cross_partition_patient() -> None:
    with pytest.raises(PermissionError, match="overlap"):
        _assert_disjoint(
            {
                "confirmation": [{"patient_id": "p1"}],
                "qualification": [{"patient_id": "p1"}],
            }
        )


def test_r45_roster_summary_hides_rows() -> None:
    summary = receipt_summary(
        {
            "status": "PASS",
            "partitions": {
                "qualification": {
                    "rows": [{"patient_id": "secret"}],
                    "row_count": 1,
                }
            },
        }
    )
    assert summary["partitions"]["qualification"] == {"row_count": 1}
    assert "secret" not in str(summary)
