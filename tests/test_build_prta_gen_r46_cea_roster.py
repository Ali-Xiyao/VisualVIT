from __future__ import annotations

from scripts.build_prta_gen_r46_cea_roster import receipt_summary
from scripts.build_prta_gen_r45_cdeb_roster import select_rows


CLASSES = ["Stable", "Improved", "Worse", "New", "Resolved"]


def test_r46_selection_is_balanced_after_r45_exclusion() -> None:
    rows = [
        {
            "patient_id": f"{label}-{index}",
            "study_id_curr": f"study-{label}-{index}",
            "finding": "Edema",
            "progression": label,
        }
        for label in CLASSES
        for index in range(3)
    ]
    excluded = {f"{label}-0" for label in CLASSES}
    eligible = [
        row for row in rows if row["patient_id"] not in excluded
    ]
    selected = select_rows(
        eligible,
        namespace="r46-test",
        partition_order=["development"],
        class_order=list(reversed(CLASSES)),
        counts={"development": {label: 1 for label in CLASSES}},
    )["development"]
    assert len(selected) == 5
    assert {row["progression"] for row in selected} == set(CLASSES)
    assert not ({row["patient_id"] for row in selected} & excluded)


def test_r46_receipt_summary_hides_development_rows() -> None:
    summary = receipt_summary(
        {
            "status": "PASS",
            "partitions": {
                "development": {
                    "rows": [{"patient_id": "secret"}],
                    "row_count": 1,
                }
            },
        }
    )
    assert summary["partitions"]["development"] == {"row_count": 1}
    assert "secret" not in str(summary)
