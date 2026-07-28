import pytest

from scripts.aggregate_r37_internal_qualification import aggregate


def _payload(seed: int, *, formal: bool = True, r37_1: bool = False):
    return {
        "schema": (
            "visualvit.r37-1.prta-formal-training.v1"
            if r37_1
            else "visualvit.r37.prta-formal-training.v1"
        ),
        "status": (
            "PASS_R37_1_PRTA_FORMAL_TRAINING"
            if r37_1
            else "PASS_R37_PRTA_FORMAL_TRAINING"
        ),
        "r37_1": r37_1,
        "variant": "A6",
        "seed": seed,
        "formal": formal,
        "formal_training_unlocked": formal,
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
                "patient_ids": ["p1", "p2"],
                "target_labels": [0, 1],
                "true_pair_predictions": [0, 1],
                "control_predictions": [1, 0],
            },
            "qualification_diagnostics": {
                "inversion_consistency_rate": 0.95,
                "state_retention_cosine_mean": 0.995,
            },
        },
    }


def _a0_payload(seed: int, *, r37_1: bool = False):
    payload = _payload(seed, r37_1=r37_1)
    payload.pop("calibration")
    payload.update(
        {
            "schema": (
                "visualvit.r37-1.a0-formal-probe.v1"
                if r37_1
                else "visualvit.r37.a0-formal-probe.v1"
            ),
            "status": (
                "PASS_R37_1_A0_FORMAL_PROBE"
                if r37_1
                else "PASS_R37_A0_FORMAL_PROBE"
            ),
            "variant": "A0",
            "calibration_patient_ids": ["p1", "p1", "p2", "p2"],
            "target_labels": [0, 1, 0, 1],
            "predictions": {
                "true_pair": [1, 0, 1, 0],
                "current_only": [1, 0, 1, 0],
            },
        }
    )
    return payload


def test_aggregate_passes_strong_three_seed_control():
    result = aggregate(
        [_payload(seed) for seed in (17, 29, 43)],
        control="current_only",
        require_formal=True,
    )
    assert result["status"] == "PASS_R37_INTERNAL_CONTROL_GATE"
    assert result["gate"]["all_three_seeds_positive"]
    assert result["bootstrap"]["patients"] == 2
    assert result["bootstrap"]["replicates"] == 2000
    assert result["bootstrap"]["seed"] == 37001
    assert result["diagnostic_gate"]["passed"] is True


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


def test_aggregate_fails_closed_on_row_order_or_outcome_firewall_drift():
    payloads = [_payload(seed) for seed in (17, 29, 43)]
    payloads[1]["calibration"]["patient_ids"] = ["p2", "p2", "p1", "p1"]
    with pytest.raises(ValueError, match="row order drift"):
        aggregate(payloads, control="current_only", require_formal=True)

    payloads = [_payload(seed) for seed in (17, 29, 43)]
    payloads[2]["sealed_test_read"] = True
    with pytest.raises(PermissionError, match="firewall-clean"):
        aggregate(payloads, control="current_only", require_formal=True)


def test_engineering_result_cannot_enter_formal_qualification():
    payloads = [_payload(seed) for seed in (17, 29, 43)]
    payloads[0]["schema"] = "visualvit.r37.prta-engineering-smoke.v1"
    payloads[0]["status"] = "PASS_R37_PRTA_ENGINEERING_SMOKE"
    with pytest.raises(PermissionError, match="formal"):
        aggregate(payloads, control="current_only", require_formal=True)


def test_formal_diagnostics_fail_closed():
    payloads = [_payload(seed) for seed in (17, 29, 43)]
    payloads[1]["calibration"]["qualification_diagnostics"][
        "state_retention_cosine_mean"
    ] = 0.98
    result = aggregate(
        payloads, control="current_only", require_formal=True
    )
    assert result["status"] == "STOP_R37_INTERNAL_CONTROL_GATE"
    assert result["gate"]["passed"] is True
    assert result["diagnostic_gate"]["passed"] is False


def test_a6_vs_a0_uses_same_patient_bootstrap_and_row_order():
    result = aggregate(
        [_payload(seed) for seed in (17, 29, 43)],
        control="a0",
        require_formal=True,
        baseline_payloads=[_a0_payload(seed) for seed in (17, 29, 43)],
    )
    assert result["status"] == "PASS_R37_INTERNAL_A6_VS_A0_GATE"
    assert result["bootstrap"]["patients"] == 2
    assert result["bootstrap"]["replicates"] == 2000

    baselines = [_a0_payload(seed) for seed in (17, 29, 43)]
    baselines[2]["calibration_patient_ids"] = ["p2", "p2", "p1", "p1"]
    with pytest.raises(ValueError, match="row order drift"):
        aggregate(
            [_payload(seed) for seed in (17, 29, 43)],
            control="a0",
            require_formal=True,
            baseline_payloads=baselines,
        )


def test_r37_1_uses_fresh_schemas_for_all_formal_gates():
    payloads = [
        _payload(seed, r37_1=True) for seed in (17, 29, 43)
    ]
    current = aggregate(
        payloads,
        control="current_only",
        require_formal=True,
        r37_1=True,
    )
    assert current["status"] == "PASS_R37_1_INTERNAL_CONTROL_GATE"
    assert current["schema"] == "visualvit.r37-1.internal-qualification.v1"
    assert current["r37_1"] is True

    a0 = aggregate(
        payloads,
        control="a0",
        require_formal=True,
        baseline_payloads=[
            _a0_payload(seed, r37_1=True) for seed in (17, 29, 43)
        ],
        r37_1=True,
    )
    assert a0["status"] == "PASS_R37_1_INTERNAL_A6_VS_A0_GATE"
    assert a0["schema"] == "visualvit.r37-1.a6-vs-a0-qualification.v1"

    with pytest.raises(PermissionError, match="formal"):
        aggregate(
            [_payload(seed) for seed in (17, 29, 43)],
            control="current_only",
            require_formal=True,
            r37_1=True,
        )
