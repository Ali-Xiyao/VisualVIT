import pytest

from scripts.cache_prta_gen_r40a_tokens import (
    prior_shuffle_assignment,
    select_rows,
    stable_order,
)


def rows():
    return [
        {
            "example_id": f"example-{index}",
            "patient_id": f"patient-{index}",
            "finding": "Edema",
            "prior_dicom_id": f"prior-{index}",
        }
        for index in range(5)
    ]


def test_prior_shuffle_is_deterministic_cross_patient_and_complete():
    first = prior_shuffle_assignment(rows(), seed=40011)
    second = prior_shuffle_assignment(rows(), seed=40011)

    assert first == second
    assert set(first) == {row["example_id"] for row in rows()}
    original = {row["example_id"]: row["prior_dicom_id"] for row in rows()}
    assert all(first[key] != original[key] for key in first)


def test_prior_shuffle_requires_two_patients_per_finding():
    duplicate_patient = rows()
    for row in duplicate_patient:
        row["patient_id"] = "one-patient"

    with pytest.raises(ValueError, match="two patients"):
        prior_shuffle_assignment(duplicate_patient, seed=40011)


def test_smoke_selection_is_outcome_independent_and_fixed_size():
    selected = select_rows(rows(), smoke_rows=3)
    expected = sorted(
        rows(),
        key=lambda row: (
            stable_order(
                "prta-gen-r40a-token-smoke-v1",
                0,
                row["example_id"],
            ),
            row["example_id"],
        ),
    )[:3]

    assert selected == expected
    with pytest.raises(ValueError, match="invalid smoke"):
        select_rows(rows(), smoke_rows=6)
