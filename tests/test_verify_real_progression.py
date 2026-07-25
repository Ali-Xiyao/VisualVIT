from __future__ import annotations

from scripts.verify_chextemporal_chexpert_progression_pilot import (
    non_deranged_predictions_invariant,
)


def _registered_predictions() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    systems = (
        "B4b_oracle",
        "learned_region",
        "paired_global",
        "current_only_global",
        "oracle_no_interaction",
    )
    for observation_index in range(90):
        for system in systems:
            for seed in (17, 29, 43):
                for derangement in (81001, 81002, 81003):
                    rows.append(
                        {
                            "observation_id": f"obs-{observation_index}",
                            "system": system,
                            "training_seed": seed,
                            "derangement_id": derangement,
                            "prediction": "Stable",
                        }
                    )
    return rows


def test_non_deranged_predictions_are_invariant() -> None:
    assert non_deranged_predictions_invariant(_registered_predictions())


def test_non_deranged_prediction_drift_fails() -> None:
    rows = _registered_predictions()
    rows[-1]["prediction"] = "Worse"
    assert not non_deranged_predictions_invariant(rows)
