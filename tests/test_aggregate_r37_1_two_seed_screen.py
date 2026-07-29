import pytest

from scripts.aggregate_r37_1_two_seed_screen import (
    aggregate_two_seed_screen,
)


def _a6(seed: int):
    return {
        "schema": "visualvit.r37-1.prta-formal-training.v1",
        "status": "PASS_R37_1_PRTA_FORMAL_TRAINING",
        "r37_1": True,
        "variant": "A6",
        "seed": seed,
        "formal": True,
        "formal_training_unlocked": True,
        "scientific_claim_allowed": False,
        "protected_outcomes_read": False,
        "sealed_test_read": False,
        "gold_outcomes_read": False,
        "source_hashes_recomputed": False,
        "calibration": {
            "patient_ids": ["p1", "p1", "p2", "p2"],
            "target_labels": [0, 1, 0, 1],
            "true_pair_predictions": [0, 1, 0, 1],
            "current_only_predictions": [1, 0, 1, 0],
            "cmcp": {
                "patient_ids": ["p1", "p1", "p2", "p2"],
                "target_labels": [0, 1, 0, 1],
                "true_pair_predictions": [0, 1, 0, 1],
                "control_predictions": [1, 0, 1, 0],
            },
            "qualification_diagnostics": {
                "inversion_consistency_rate": 1.0,
                "state_retention_cosine_mean": 0.995,
            },
        },
    }


def _a0(seed: int):
    return {
        "schema": "visualvit.r37-1.a0-formal-probe.v1",
        "status": "PASS_R37_1_A0_FORMAL_PROBE",
        "r37_1": True,
        "variant": "A0",
        "seed": seed,
        "formal": True,
        "formal_training_unlocked": True,
        "scientific_claim_allowed": False,
        "protected_outcomes_read": False,
        "sealed_test_read": False,
        "gold_outcomes_read": False,
        "source_hashes_recomputed": False,
        "calibration_patient_ids": ["p1", "p1", "p2", "p2"],
        "target_labels": [0, 1, 0, 1],
        "predictions": {
            "true_pair": [1, 0, 1, 0],
            "current_only": [1, 0, 1, 0],
        },
    }


def test_two_seed_screen_passes_and_cannot_claim_three_seed_go():
    result = aggregate_two_seed_screen(
        [_a6(17), _a6(29)],
        [_a0(17), _a0(29)],
    )
    assert result["status"] == "PASS_R37_1_TWO_SEED_INTERNAL_SCREEN"
    assert result["seeds"] == [17, 29]
    assert result["bootstrap_replicates"] == 2000
    assert result["bootstrap_seed"] == 37001
    assert result["three_seed_gate_evaluated"] is False
    assert result["scientific_claim_allowed"] is False
    assert all(
        item["gate"]["passed"]
        for item in result["comparisons"].values()
    )


def test_two_seed_screen_fails_closed_on_seed_schema_or_firewall_drift():
    with pytest.raises(ValueError, match="two-screen seeds"):
        aggregate_two_seed_screen(
            [_a6(17), _a6(43)],
            [_a0(17), _a0(29)],
        )

    payloads = [_a6(17), _a6(29)]
    payloads[1]["schema"] = "visualvit.r37.prta-formal-training.v1"
    with pytest.raises(PermissionError, match="firewall-clean"):
        aggregate_two_seed_screen(payloads, [_a0(17), _a0(29)])

    baselines = [_a0(17), _a0(29)]
    baselines[0]["protected_outcomes_read"] = True
    with pytest.raises(PermissionError, match="firewall-clean"):
        aggregate_two_seed_screen([_a6(17), _a6(29)], baselines)


def test_two_seed_screen_rejects_row_order_drift():
    baselines = [_a0(17), _a0(29)]
    baselines[1]["calibration_patient_ids"] = ["p2", "p2", "p1", "p1"]
    with pytest.raises(ValueError, match="row order drift"):
        aggregate_two_seed_screen([_a6(17), _a6(29)], baselines)


def test_two_seed_screen_stops_on_diagnostic_failure():
    payloads = [_a6(17), _a6(29)]
    payloads[1]["calibration"]["qualification_diagnostics"][
        "state_retention_cosine_mean"
    ] = 0.98
    result = aggregate_two_seed_screen(
        payloads,
        [_a0(17), _a0(29)],
    )
    assert result["status"] == "STOP_R37_1_TWO_SEED_INTERNAL_SCREEN"
    assert result["diagnostic_gate"]["passed"] is False
