from pathlib import Path

import pytest

from scripts.aggregate_prta_gen_r41a_progression_sft import (
    evaluate_gate,
    paired_patient_bootstrap_with_invalid,
)
from scripts.aggregate_prta_gen_r42a_grounding_reversal import (
    evaluate_gate as evaluate_r42a_gate,
)
from scripts.audit_prta_gen_r43_confirmatory_readiness import (
    conservative_mde_pp,
)
from scripts.build_prta_gen_r41a_roster import (
    receipt_summary as roster_receipt_summary,
    select_rows,
)
from scripts.run_prta_gen_r41a_authorized_sequence import (
    validate_aggregate,
    validate_arm_result,
)
from scripts.run_prta_gen_r41a_progression_sft import (
    per_class_recall,
    target_text,
)
from scripts.run_prta_gen_r41_r43_authorized_chain import (
    _validate_stage_status,
)
from scripts.run_prta_gen_r42a_grounding_reversal import (
    preflight as r42a_preflight,
    reversed_target_text,
)


CLASSES = ["Stable", "Improved", "Worse", "New", "Resolved"]


def test_select_rows_is_patient_disjoint_and_balanced():
    rows = []
    for class_index, label in enumerate(CLASSES):
        for index in range(4):
            rows.append(
                {
                    "example_id": f"e-{class_index}-{index}",
                    "patient_id": f"p-{class_index}-{index}",
                    "finding": "Edema",
                    "progression": label,
                }
            )
    selected = select_rows(
        rows,
        fit_patients={row["patient_id"] for row in rows},
        excluded_patients=set(),
        namespace="test",
        class_order=list(reversed(CLASSES)),
        partition_counts={
            "train": {label: 2 for label in CLASSES},
            "development": {label: 1 for label in CLASSES},
        },
    )
    train = {row["patient_id"] for row in selected["train"]}
    development = {
        row["patient_id"] for row in selected["development"]
    }
    assert len(train) == 10
    assert len(development) == 5
    assert not train & development


def test_roster_receipt_summary_removes_rows():
    summary = roster_receipt_summary(
        {
            "status": "PASS",
            "partitions": {
                "train": {
                    "rows": [{"patient_id": "secret"}],
                    "row_count": 1,
                }
            },
        }
    )
    assert summary["partitions"]["train"] == {"row_count": 1}


def test_target_text_and_invalid_prediction_metrics():
    assert target_text(
        {"finding": "Edema", "progression": "Worse"}
    ) == '{"finding":"Edema","progression":"Worse"}'
    assert per_class_recall(
        [0, 1, 2, 3, 4], [0, 1, -1, 3, 4], class_count=5
    ) == [1.0, 1.0, 0.0, 1.0, 1.0]
    comparison = paired_patient_bootstrap_with_invalid(
        patient_ids=[f"p{index}" for index in range(5)],
        targets=[0, 1, 2, 3, 4],
        primary_predictions=[0, 1, 2, 3, 4],
        control_predictions=[-1, -1, -1, -1, -1],
        class_count=5,
        replicates=100,
        seed=41,
    )
    assert comparison["effect_pp"] == pytest.approx(100.0)
    assert comparison["invalid_predictions_supported"] is True


def _gate_config() -> dict:
    return {
        "training": {"seeds": [17]},
        "evaluation": {
            "required_primary_controls": ["query_only", "prior_shuffle"]
        },
        "gate": {
            "all_seed_g1_true_macro_f1_at_least": 0.3,
            "all_seed_g1_all_class_recall_at_least": 0.12,
            "all_seed_g1_schema_validity_at_least": 0.99,
            "all_seed_g1_finding_echo_accuracy_at_least": 0.99,
            "all_seed_g1_required_control_effects_at_least_pp": 2.0,
            "all_seed_g1_required_control_ci95_lower_above_pp": 0.0,
            "all_seed_g1_minus_g0_effect_at_least_pp": 1.0,
        },
    }


def test_gate_requires_all_seed_controls_and_g1_improvement():
    results = {
        17: {
            "g1_attention_lora": {
                "metrics": {
                    "true_pair": {
                        "macro_f1": 0.4,
                        "schema_validity": 1.0,
                        "finding_echo_accuracy": 1.0,
                        "per_class_recall": {
                            label: 0.2 for label in CLASSES
                        },
                    }
                }
            }
        }
    }
    comparisons = {
        "g1_true_vs_control": {
            "17": {
                "query_only": {"effect_pp": 3.0, "ci95_lower_pp": 0.1},
                "prior_shuffle": {"effect_pp": 4.0, "ci95_lower_pp": 0.2},
            }
        },
        "g1_true_vs_g0_true": {
            "17": {"effect_pp": 1.1, "ci95_lower_pp": -1.0}
        },
    }
    assert evaluate_gate(_gate_config(), results, comparisons) == (True, [])
    comparisons["g1_true_vs_g0_true"]["17"]["effect_pp"] = 0.9
    passed, failures = evaluate_gate(
        _gate_config(), results, comparisons
    )
    assert passed is False
    assert failures[0]["gate"] == "g1_minus_g0_true_macro_f1"


def _sequence_config() -> dict:
    return {
        "protocol_id": "r41a",
        "study_tier": "internal",
        "roster": {"train_patients": 375, "development_patients": 125},
        "training": {
            "seeds": [17, 29, 43],
            "expected_optimizer_updates": 36,
        },
        "result_statuses": {
            "aggregate_go": "GO",
            "aggregate_stop": "STOP",
        },
    }


def _arm_result(checkpoint: Path) -> dict:
    checkpoint.write_bytes(b"checkpoint")
    return {
        "status": "PASS_PRTA_GEN_R41A_ARM_EVALUATION",
        "protocol_id": "r41a",
        "seed": 17,
        "model_arm": "g0_projector_only",
        "training_rows": 375,
        "development_rows": 125,
        "optimizer_updates": 36,
        "exact64_tokens_used": True,
        "free_greedy_generation_evaluated": True,
        "pixel_inputs_used": False,
        "qwen_free_generation_survival_unlocked": False,
        "r42_unlocked": False,
        "scientific_claim_allowed": False,
        "protected_300_dev_read": False,
        "revealed_483_test_read": False,
        "gold_outcomes_read": False,
        "external_outcomes_read": False,
        "checkpoint": str(checkpoint),
        "checkpoint_bytes": checkpoint.stat().st_size,
        "metrics": {
            "true_pair": {
                "macro_f1": 0.4,
                "schema_validity": 1.0,
                "finding_echo_accuracy": 1.0,
            }
        },
        "peak_cuda_allocated_bytes": 123,
    }


def test_sequence_receipts_are_scalar_and_fail_closed(tmp_path):
    result = _arm_result(tmp_path / "checkpoint.pt")
    receipt = validate_arm_result(
        _sequence_config(),
        seed=17,
        model_arm="g0_projector_only",
        result=result,
    )
    assert receipt["true_pair_macro_f1"] == 0.4
    result["gold_outcomes_read"] = True
    with pytest.raises(PermissionError, match="receipt drift"):
        validate_arm_result(
            _sequence_config(),
            seed=17,
            model_arm="g0_projector_only",
            result=result,
        )


@pytest.mark.parametrize(
    ("passed", "status"), [(True, "GO"), (False, "STOP")]
)
def test_validate_aggregate_accepts_registered_terminal_states(
    passed, status
):
    receipt = validate_aggregate(
        _sequence_config(),
        {
            "status": status,
            "protocol_id": "r41a",
            "study_tier": "internal",
            "seeds": [17, 29, 43],
            "gate_passed": passed,
            "gate_failures": [] if passed else ["failure"],
            "development_patients": 125,
            "qwen_free_generation_survival_unlocked": passed,
            "r42_unlocked": passed,
            "r43_unlocked": False,
            "scientific_claim_allowed": False,
            "protected_300_dev_read": False,
            "revealed_483_test_read": False,
            "gold_outcomes_read": False,
            "external_outcomes_read": False,
        },
    )
    assert receipt["status"] == status
    assert receipt["gate_passed"] is passed


def test_r42a_reversal_mapping_is_rendered_and_preflight_is_static():
    mapping = {
        "Stable": "Stable",
        "Improved": "Worse",
        "Worse": "Improved",
        "New": "Resolved",
        "Resolved": "New",
    }
    assert reversed_target_text(
        {"finding": "Edema", "progression": "New"}, mapping
    ) == '{"finding":"Edema","progression":"Resolved"}'
    receipt = r42a_preflight(
        Path("configs/prta_gen/prta_gen_r42a_grounding_reversal_v1.json")
    )
    assert receipt["status"] == "PASS_PRTA_GEN_R42A_RUNNER_PREFLIGHT"
    assert receipt["reversal_mapping_involutive"] is True
    assert receipt["expected_optimizer_updates"] == 12


@pytest.mark.parametrize(
    ("stage", "passed", "terminal"),
    [
        (
            "R41A",
            True,
            "GO_PRTA_GEN_R41A_PROGRESSION_SFT_SURVIVAL",
        ),
        (
            "R41A",
            False,
            "STOP_PRTA_GEN_R41A_PROGRESSION_SFT_SURVIVAL",
        ),
        (
            "R42A",
            True,
            "GO_PRTA_GEN_R42A_GROUNDING_REVERSAL_SURVIVAL",
        ),
        (
            "R42A",
            False,
            "STOP_PRTA_GEN_R42A_GROUNDING_REVERSAL_SURVIVAL",
        ),
    ],
)
def test_master_chain_accepts_only_registered_stage_terminals(
    stage, passed, terminal
):
    observed = {
        "status": terminal,
        "aggregate_receipt": {"gate_passed": passed},
    }
    assert _validate_stage_status(stage, observed) == (passed, terminal)


def test_r42a_gate_requires_reversal_preference_controls_and_baseline_gain():
    config = {
        "training": {"seeds": [17]},
        "evaluation": {
            "primary_training_arm": "g_cmcp_plus_reversal",
            "required_primary_controls": ["query_only", "prior_shuffle"],
        },
        "gate": {
            "all_seed_primary_true_macro_f1_at_least": 0.3,
            "all_seed_primary_all_class_recall_at_least": 0.12,
            "all_seed_primary_schema_validity_at_least": 0.95,
            "all_seed_primary_finding_echo_accuracy_at_least": 0.95,
            "all_seed_correct_prior_preference_strictly_above": 0.5,
            "all_seed_required_control_effects_at_least_pp": 2.0,
            "all_seed_required_control_ci95_lower_above_pp": 0.0,
            "all_seed_reversal_mapped_accuracy_at_least": 0.9,
            "all_seed_primary_minus_r41a_effect_at_least_pp": 1.0,
        },
    }
    results = {
        17: {
            "g_cmcp_plus_reversal": {
                "metrics": {
                    "true_pair": {
                        "macro_f1": 0.4,
                        "schema_validity": 1.0,
                        "finding_echo_accuracy": 1.0,
                        "per_class_recall": {
                            label: 0.2 for label in CLASSES
                        },
                    },
                    "time_reversed": {"progression_accuracy": 0.92},
                },
                "correct_prior_preference": {
                    "correct_prior_preference": 0.6
                },
            }
        }
    }
    comparisons = {
        "primary_true_vs_control": {
            "17": {
                "query_only": {"effect_pp": 3.0, "ci95_lower_pp": 0.1},
                "prior_shuffle": {"effect_pp": 4.0, "ci95_lower_pp": 0.2},
            }
        },
        "primary_true_vs_r41a_true": {"17": {"effect_pp": 1.1}},
    }
    assert evaluate_r42a_gate(config, results, comparisons) == (True, [])
    results[17]["g_cmcp_plus_reversal"]["metrics"]["time_reversed"][
        "progression_accuracy"
    ] = 0.89
    passed, failures = evaluate_r42a_gate(config, results, comparisons)
    assert passed is False
    assert failures[0]["gate"] == "reversal_mapped_accuracy"


def test_r43_conservative_mde_matches_registered_readiness_boundary():
    assert conservative_mde_pp(16) == pytest.approx(35.0198125)
    assert conservative_mde_pp(0) is None
