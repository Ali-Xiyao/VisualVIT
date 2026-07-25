from __future__ import annotations

from visualvit.real_progression import (
    classification_metrics,
    deterministic_patient_folds,
    fold_audit,
    hierarchical_patient_bootstrap,
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
