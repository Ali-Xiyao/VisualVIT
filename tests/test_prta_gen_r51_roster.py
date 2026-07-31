from __future__ import annotations

from scripts.build_prta_gen_r51_roster import receipt_summary
from scripts.build_prta_gen_r45_cdeb_roster import select_rows


CLASSES = ["Stable", "Improved", "Worse", "New", "Resolved"]


def test_r51_selection_excludes_closed_patients_and_balances() -> None:
    rows = [
        {
            "patient_id": f"p-{label}-{index}",
            "study_id_curr": f"s-{label}-{index}",
            "finding": "Edema",
            "progression": label,
        }
        for label in CLASSES
        for index in range(4)
    ]
    excluded = {f"p-{label}-0" for label in CLASSES}
    unused = [row for row in rows if row["patient_id"] not in excluded]
    selected = select_rows(
        unused,
        namespace="r51-test",
        partition_order=["evaluation"],
        class_order=list(reversed(CLASSES)),
        counts={"evaluation": {label: 2 for label in CLASSES}},
    )["evaluation"]
    assert len(selected) == 10
    assert not ({row["patient_id"] for row in selected} & excluded)
    assert {
        label: sum(row["progression"] == label for row in selected)
        for label in CLASSES
    } == {label: 2 for label in CLASSES}


def test_r51_receipt_summary_hides_patient_rows() -> None:
    summary = receipt_summary(
        {
            "status": "PASS",
            "partitions": {
                "evaluation": {
                    "rows": [{"patient_id": "secret"}],
                    "row_count": 1,
                    "patient_count": 1,
                }
            },
        }
    )
    assert summary["partitions"]["evaluation"] == {
        "row_count": 1,
        "patient_count": 1,
    }
    assert "secret" not in str(summary)
