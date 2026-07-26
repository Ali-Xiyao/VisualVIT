from __future__ import annotations

from scripts import run_r31_confidence_consensus as r31


def _rows(uniform: list[str], regularized: list[str]):
    rows = []
    for seed, first, second in zip(
        r31.TRAINING_SEEDS, uniform, regularized, strict=True
    ):
        base = {
            "patient_id": "p1",
            "observation_id": "o1",
            "training_seed": seed,
            "derangement_id": 0,
            "target": "Stable",
            "weight": 1.0,
        }
        rows.append(
            {**base, "system": "uniform_fusion", "prediction": first}
        )
        rows.append(
            {
                **base,
                "system": "regularized_multiscale",
                "prediction": second,
            }
        )
    return rows


def test_unanimous_regularized_takes_precedence() -> None:
    rows, audit = r31.add_consensus_rows(
        _rows(
            ["Stable", "Stable", "Improved"],
            ["Worse", "Worse", "Worse"],
        )
    )
    predictions = {
        row["prediction"]
        for row in rows
        if row["system"] == "confidence_consensus"
    }
    assert predictions == {"Worse"}
    assert audit["regularized_unanimous_rate"] == 1.0


def test_nonunanimous_regularized_falls_back_to_uniform_majority() -> None:
    rows, audit = r31.add_consensus_rows(
        _rows(
            ["Improved", "Stable", "Improved"],
            ["Worse", "Stable", "Worse"],
        )
    )
    predictions = {
        row["prediction"]
        for row in rows
        if row["system"] == "confidence_consensus"
    }
    assert predictions == {"Improved"}
    assert audit["regularized_unanimous_rate"] == 0.0


def test_three_way_tie_uses_frozen_label_order() -> None:
    assert r31.majority(["Worse", "Improved", "Stable"]) == "Stable"
