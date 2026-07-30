from scripts.aggregate_prta_gen_r40c_generalization import evaluate_gate


def _config():
    return {
        "evaluation": {
            "required_primary_controls": ["query_only", "prior_shuffle"]
        },
        "gate": {
            "all_seed_true_macro_f1_at_least": 0.3,
            "all_seed_all_class_recall_at_least": 0.15,
            "all_seed_required_control_effects_at_least_pp": 2.0,
            "all_seed_required_control_ci95_lower_above_pp": 0.0,
            "structured_schema_validity": 1.0,
            "structured_finding_echo_accuracy": 1.0,
        },
    }


def _result(seed=17):
    return {
        "seed": seed,
        "metrics": {
            "true_pair": {
                "macro_f1": 0.5,
                "per_class_recall": {
                    "Stable": 0.5,
                    "Improved": 0.5,
                    "Worse": 0.5,
                    "New": 0.5,
                    "Resolved": 0.5,
                },
            }
        },
        "structured": {
            "schema_validity": 1.0,
            "finding_echo_accuracy": 1.0,
        },
    }


def _comparisons():
    return {
        "query_only": {
            "17": {"effect_pp": 10.0, "ci95_lower_pp": 3.0}
        },
        "prior_shuffle": {
            "17": {"effect_pp": 8.0, "ci95_lower_pp": 2.0}
        },
    }


def test_evaluate_gate_passes_only_when_every_registered_condition_passes():
    passed, failures = evaluate_gate(
        _config(), [_result()], _comparisons()
    )
    assert passed is True
    assert failures == []


def test_evaluate_gate_reports_class_collapse_and_control_failure():
    result = _result()
    result["metrics"]["true_pair"]["per_class_recall"]["Resolved"] = 0.0
    comparisons = _comparisons()
    comparisons["prior_shuffle"]["17"]["ci95_lower_pp"] = -1.0
    passed, failures = evaluate_gate(_config(), [result], comparisons)
    assert passed is False
    assert {failure["gate"] for failure in failures} == {
        "per_class_recall",
        "ci95_lower_vs_prior_shuffle",
    }
