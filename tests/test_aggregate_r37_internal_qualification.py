import pytest

from scripts.aggregate_r37_internal_qualification import aggregate


def _payload(seed: int, *, formal: bool = True):
    return {
        "variant": "A6",
        "seed": seed,
        "formal": formal,
        "formal_training_unlocked": formal,
        "protected_outcomes_read": False,
        "calibration": {
            "patient_ids": ["p1", "p1", "p2", "p2"],
            "target_labels": [0, 1, 0, 1],
            "true_pair_predictions": [0, 1, 0, 1],
            "current_only_predictions": [1, 0, 1, 0],
            "cmcp": {
                "patient_ids": ["p1", "p2"],
                "target_labels": [0, 1],
                "true_pair_predictions": [0, 1],
                "control_predictions": [1, 0],
            },
        },
    }


def test_aggregate_passes_strong_three_seed_control():
    result = aggregate(
        [_payload(seed) for seed in (17, 29, 43)],
        control="current_only",
        require_formal=True,
    )
    assert result["status"] == "PASS_R37_INTERNAL_CONTROL_GATE"
    assert result["gate"]["all_three_seeds_positive"]


def test_aggregate_fails_closed_on_seed_or_formal_drift():
    with pytest.raises(ValueError, match="frozen seeds"):
        aggregate(
            [_payload(seed) for seed in (17, 29, 44)],
            control="current_only",
            require_formal=True,
        )
    with pytest.raises(PermissionError, match="formal"):
        aggregate(
            [_payload(seed, formal=False) for seed in (17, 29, 43)],
            control="current_only",
            require_formal=True,
        )
