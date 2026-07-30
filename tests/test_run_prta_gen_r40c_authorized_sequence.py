from pathlib import Path

import pytest

from scripts.run_prta_gen_r40c_authorized_sequence import (
    validate_aggregate,
    validate_seed_result,
)


def _config() -> dict:
    return {
        "protocol_id": "r40c",
        "study_tier": "internal_development_generalization",
        "training": {
            "seeds": [17, 29, 43],
            "expected_updates_per_arm": 800,
        },
        "roster": {
            "train_patients": 1000,
            "development_patients": 500,
        },
        "head": {"parameter_count": 499973},
        "gate": {
            "structured_schema_validity": 1.0,
            "structured_finding_echo_accuracy": 1.0,
        },
        "result_statuses": {
            "aggregate_go": "GO_PRTA_GEN_R40C_INTERNAL_GENERALIZATION",
            "aggregate_stop": "STOP_PRTA_GEN_R40C_INTERNAL_GENERALIZATION",
        },
    }


def _seed_result(checkpoint: Path) -> dict:
    checkpoint.write_bytes(b"checkpoint")
    return {
        "status": "PASS_PRTA_GEN_R40C_SEED_EVALUATION",
        "protocol_id": "r40c",
        "seed": 17,
        "training_rows": 1000,
        "training_patients": 1000,
        "development_rows": 500,
        "development_patients": 500,
        "parameter_count": 499973,
        "normalization_fit_on_training_only": True,
        "exact64_tokens_used": True,
        "pixel_inputs_used": False,
        "qwen_free_generation_unlocked": False,
        "r41_qwen_sft_unlocked": False,
        "scientific_claim_allowed": False,
        "protected_300_dev_read": False,
        "revealed_483_test_read": False,
        "gold_outcomes_read": False,
        "external_outcomes_read": False,
        "structured": {
            "schema_validity": 1.0,
            "finding_echo_accuracy": 1.0,
        },
        "training_audits": {
            arm: {
                "updates": 800,
                "normalization_fit_on_training_only": True,
            }
            for arm in (
                "true_pair",
                "current_only",
                "query_only",
                "prior_shuffle",
            )
        },
        "checkpoint": str(checkpoint),
        "checkpoint_bytes": checkpoint.stat().st_size,
        "metrics": {
            "true_pair": {"macro_f1": 0.4},
            "effects_pp": {"query_only": 3.0, "prior_shuffle": 4.0},
        },
        "peak_cuda_allocated_bytes": 1234,
    }


def test_validate_seed_result_returns_scalar_receipt(tmp_path):
    receipt = validate_seed_result(
        _config(),
        seed=17,
        result=_seed_result(tmp_path / "checkpoint.pt"),
    )
    assert receipt["status"] == "PASS_PRTA_GEN_R40C_SEED_EVALUATION"
    assert receipt["true_pair_macro_f1"] == 0.4
    assert receipt["checkpoint_bytes"] == len(b"checkpoint")


def test_validate_seed_result_fails_closed_on_protected_read(tmp_path):
    result = _seed_result(tmp_path / "checkpoint.pt")
    result["gold_outcomes_read"] = True
    with pytest.raises(PermissionError, match="receipt drift"):
        validate_seed_result(_config(), seed=17, result=result)


@pytest.mark.parametrize(
    ("gate_passed", "status"),
    [
        (True, "GO_PRTA_GEN_R40C_INTERNAL_GENERALIZATION"),
        (False, "STOP_PRTA_GEN_R40C_INTERNAL_GENERALIZATION"),
    ],
)
def test_validate_aggregate_accepts_registered_terminal_states(
    gate_passed,
    status,
):
    receipt = validate_aggregate(
        _config(),
        {
            "status": status,
            "protocol_id": "r40c",
            "study_tier": "internal_development_generalization",
            "seeds": [17, 29, 43],
            "gate_passed": gate_passed,
            "gate_failures": [] if gate_passed else ["seed failure"],
            "development_patients": 500,
            "qwen_free_generation_unlocked": False,
            "r41_qwen_sft_unlocked": False,
            "scientific_claim_allowed": False,
            "protected_300_dev_read": False,
            "revealed_483_test_read": False,
            "gold_outcomes_read": False,
            "external_outcomes_read": False,
        },
    )
    assert receipt["status"] == status
    assert receipt["gate_passed"] is gate_passed
