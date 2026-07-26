from __future__ import annotations

from collections import Counter

from scripts import build_r30_fresh_silver_cohort as r30


def _row(patient: str, index: int) -> dict[str, str]:
    return {
        "patient_id": patient,
        "record_id": f"{patient}-{index}",
        "partition": "sealed_reserve",
        "progression": r30.LABELS[index % len(r30.LABELS)],
        "prior_path": __file__,
        "current_path": __file__,
    }


def test_patient_assignment_is_deterministic_and_disjoint() -> None:
    patients = [f"patient{index:05d}" for index in range(3000)]
    first = r30.assign_patients(patients)
    second = r30.assign_patients(list(reversed(patients)))
    assert first == second
    assert Counter(first.values()) == {
        "train": 1500,
        "dev": 400,
        "test": 600,
        "sealed_reserve": 500,
    }


def test_active_row_cap_is_label_free() -> None:
    patients = [f"patient{index:05d}" for index in range(2600)]
    source = [
        _row(patient, index)
        for patient in patients
        for index in range(15)
    ]
    records = r30.build_records(source)
    active = [
        row for row in records if row["partition"] != "sealed_reserve"
    ]
    per_patient = Counter(row["patient_id"] for row in active)
    assert len(per_patient) == 2500
    assert set(per_patient.values()) == {12}


def test_r29_nonreserve_rows_are_never_eligible() -> None:
    source = [
        {**_row("patient_active", 0), "partition": "test"},
        _row("patient_reserve", 0),
    ]
    records = r30.build_records(source)
    assert {row["patient_id"] for row in records} == {"patient_reserve"}
