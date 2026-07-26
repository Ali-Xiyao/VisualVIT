from __future__ import annotations

from collections import Counter

from scripts import build_r31_fresh_silver_cohort as r31


def _row(patient: str, index: int, partition: str = "sealed_reserve"):
    return {
        "patient_id": patient,
        "record_id": f"{patient}-{index}",
        "partition": partition,
        "progression": r31.LABELS[index % 3],
        "prior_path": __file__,
        "current_path": __file__,
    }


def test_assignment_counts_and_order_invariance() -> None:
    patients = [f"patient{index:05d}" for index in range(2500)]
    first = r31.assign_patients(patients)
    assert first == r31.assign_patients(list(reversed(patients)))
    assert Counter(first.values()) == {
        "train": 1200,
        "dev": 300,
        "test": 500,
        "sealed_reserve": 500,
    }


def test_only_reserve_is_reassigned_and_active_rows_are_capped() -> None:
    source = [_row("old_active", 0, "test")]
    source.extend(
        _row(f"patient{patient:05d}", index)
        for patient in range(2100)
        for index in range(13)
    )
    records = r31.build_records(source)
    assert "old_active" not in {row["patient_id"] for row in records}
    active_counts = Counter(
        row["patient_id"]
        for row in records
        if row["partition"] != "sealed_reserve"
    )
    assert len(active_counts) == 2000
    assert set(active_counts.values()) == {12}
