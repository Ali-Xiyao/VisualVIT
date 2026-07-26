from __future__ import annotations

from visualvit.real_progression import (
    build_pair_and_entity_manifests,
    classification_metrics,
    deterministic_patient_folds,
    fold_audit,
    hierarchical_patient_bootstrap,
    progression_rows_from_predictions,
)


def _records() -> list[dict[str, str]]:
    labels = ("Improved", "Stable", "Worse")
    return [
        {
            "patient_id": f"p{patient}",
            "progression": labels[(patient + row) % len(labels)],
        }
        for patient in range(12)
        for row in range(3)
    ]


def test_patient_folds_are_deterministic_and_disjoint() -> None:
    records = _records()
    first = deterministic_patient_folds(
        records, labels=("Improved", "Stable", "Worse"), fold_count=3
    )
    second = deterministic_patient_folds(
        list(reversed(records)),
        labels=("Improved", "Stable", "Worse"),
        fold_count=3,
    )
    assert first == second
    audit = fold_audit(
        records,
        first,
        labels=("Improved", "Stable", "Worse"),
        fold_count=3,
    )
    assert audit["patient_disjoint"]
    assert audit["rows"] == 36
    assert sum(item["rows"] for item in audit["folds"]) == 36


def test_patient_balanced_metrics_do_not_overweight_large_patient() -> None:
    rows = [
        {"patient_id": "large", "target": "Stable", "prediction": "Stable"},
        {"patient_id": "large", "target": "Stable", "prediction": "Stable"},
        {"patient_id": "large", "target": "Stable", "prediction": "Stable"},
        {"patient_id": "small1", "target": "Improved", "prediction": "Improved"},
        {"patient_id": "small2", "target": "Worse", "prediction": "Worse"},
    ]
    result = classification_metrics(rows, labels=("Improved", "Stable", "Worse"))
    assert result["patient_balanced"]["macro_f1"] == 1.0
    assert result["patient_balanced"]["support"] == {
        "Improved": 1.0,
        "Stable": 1.0,
        "Worse": 1.0,
    }


def test_hierarchical_bootstrap_preserves_exact_zero_contrast() -> None:
    systems = ("a", "b")
    seeds = (17, 29, 43)
    derangements = (1, 2, 3)
    labels = ("Improved", "Stable", "Worse")
    rows = []
    for system in systems:
        for seed in seeds:
            for derangement in derangements:
                for patient in range(30):
                    label = labels[patient % len(labels)]
                    rows.append(
                        {
                            "system": system,
                            "training_seed": seed,
                            "derangement_id": derangement,
                            "patient_id": f"p{patient}",
                            "observation_id": f"o{patient}",
                            "target": label,
                            "prediction": label,
                            "weight": 1.0,
                        }
                    )
    result = hierarchical_patient_bootstrap(
        rows,
        labels=labels,
        systems=systems,
        seeds=seeds,
        derangements=derangements,
        contrasts={"b_minus_a": ("b", "a")},
        invariant_systems=systems,
        replicates=200,
    )
    assert result["inference_valid"]
    assert result["contrasts"]["b_minus_a"]["point"] == 0.0
    assert result["contrasts"]["b_minus_a"]["interval"] == {
        "lower": 0.0,
        "upper": 0.0,
        "level": 0.95,
    }


def test_progression_predictions_consume_record_progression_as_target() -> None:
    records = [
        {
            "qualification_id": "q1",
            "patient_id": "p1",
            "progression": "Stable",
        },
        {
            "qualification_id": "q2",
            "patient_id": "p2",
            "progression": "Improved",
        },
        {
            "qualification_id": "q3",
            "patient_id": "p3",
            "progression": "Worse",
        },
        {
            "qualification_id": "q4",
            "patient_id": "p4",
            "progression": "Stable",
        },
    ]
    predictions = {
        "q1": "Stable",
        "q2": "Improved",
        "q3": "Worse",
        "q4": "Stable",
    }

    rows = progression_rows_from_predictions(
        records,
        predictions,
        labels=("Improved", "Stable", "Worse"),
    )

    assert [row["target"] for row in rows] == [
        "Stable",
        "Improved",
        "Worse",
        "Stable",
    ]
    assert classification_metrics(
        rows, labels=("Improved", "Stable", "Worse")
    )["ordinary"]["macro_f1"] == 1.0

    records[0]["progression"] = "Worse"
    changed = progression_rows_from_predictions(
        records,
        predictions,
        labels=("Improved", "Stable", "Worse"),
    )
    assert changed[0]["target"] == "Worse"
    assert classification_metrics(
        changed, labels=("Improved", "Stable", "Worse")
    )["ordinary"]["macro_f1"] < 1.0


def test_progression_predictions_fail_closed_on_missing_or_extra_ids() -> None:
    records = [
        {
            "qualification_id": "q1",
            "patient_id": "p1",
            "progression": "Stable",
        }
    ]
    labels = ("Improved", "Stable", "Worse")

    for predictions in ({}, {"q1": "Stable", "q2": "Worse"}):
        try:
            progression_rows_from_predictions(records, predictions, labels=labels)
        except ValueError as error:
            assert "prediction ids" in str(error)
        else:
            raise AssertionError("mismatched prediction ids must fail closed")


def test_pair_and_entity_manifests_separate_independent_units() -> None:
    records = [
        {
            "qualification_id": "q2",
            "patient_id": "p1",
            "prior_dicom_id": "d1",
            "current_dicom_id": "d2",
            "anatomy": "right lung",
            "label_name": "opacity",
            "progression": "Worse",
        },
        {
            "qualification_id": "q1",
            "patient_id": "p1",
            "prior_dicom_id": "d1",
            "current_dicom_id": "d2",
            "anatomy": "left lung",
            "label_name": "effusion",
            "progression": "Stable",
        },
        {
            "qualification_id": "q3",
            "patient_id": "p2",
            "prior_dicom_id": "d3",
            "current_dicom_id": "d4",
            "anatomy": "heart",
            "label_name": "enlarged",
            "progression": "Improved",
        },
    ]

    pairs, entities = build_pair_and_entity_manifests(records)

    assert len(pairs) == 2
    assert len(entities) == 3
    assert pairs[0]["entity_count"] == 2
    assert pairs[0]["progression_counts"] == {"Stable": 1, "Worse": 1}
    assert [item["qualification_id"] for item in entities] == ["q1", "q2", "q3"]
    assert entities[0]["pair_id"] == entities[1]["pair_id"]
    assert entities[2]["pair_id"] != entities[0]["pair_id"]
