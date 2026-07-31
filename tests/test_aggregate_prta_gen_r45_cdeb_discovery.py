from __future__ import annotations

from scripts.aggregate_prta_gen_r45_cdeb_discovery import evaluate_gate


def config() -> dict:
    return {
        "discovery_gate": {
            "full_true_macro_f1_at_least": 0.3,
            "full_all_class_recall_at_least": 0.12,
            "full_schema_validity_at_least": 0.99,
            "full_finding_echo_accuracy_at_least": 0.99,
            "full_true_minus_prior_shuffle_macro_f1_at_least_pp": 1.0,
            "full_true_minus_baseline_true_macro_f1_at_least_pp": 1.0,
            "full_true_minus_no_delta_true_macro_f1_at_least_pp": 0.0,
            "full_auxiliary_true_macro_f1_at_least": 0.35,
            "full_true_prior_shuffle_same_prediction_at_most": 0.75,
        }
    }


def results() -> dict:
    return {
        "full_cdeb": {
            "metrics": {
                "true_pair": {
                    "macro_f1": 0.5,
                    "schema_validity": 1.0,
                    "finding_echo_accuracy": 1.0,
                    "per_class_recall": {
                        label: 0.4
                        for label in (
                            "Stable",
                            "Improved",
                            "Worse",
                            "New",
                            "Resolved",
                        )
                    },
                }
            },
            "auxiliary_metrics": {
                "true_pair": {"macro_f1": 0.6}
            },
            "true_prior_shuffle_same_prediction_rate": 0.5,
        }
    }


def comparisons() -> dict:
    return {
        "full_true_vs_prior_shuffle": {"effect_pp": 5.0},
        "full_true_vs_baseline_true": {"effect_pp": 3.0},
        "full_true_vs_no_delta_true": {"effect_pp": 1.0},
    }


def test_r45_discovery_gate_passes_all_registered_checks() -> None:
    passed, failures = evaluate_gate(config(), results(), comparisons())
    assert passed is True
    assert failures == []


def test_r45_discovery_gate_fails_specificity_and_class_floor() -> None:
    observed = results()
    observed["full_cdeb"]["true_prior_shuffle_same_prediction_rate"] = 0.8
    observed["full_cdeb"]["metrics"]["true_pair"]["per_class_recall"][
        "Resolved"
    ] = 0.1
    passed, failures = evaluate_gate(config(), observed, comparisons())
    assert passed is False
    assert {failure["gate"] for failure in failures} == {
        "full_per_class_recall",
        "full_true_prior_shuffle_same_prediction",
    }
