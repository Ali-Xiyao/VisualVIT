from __future__ import annotations

# ruff: noqa: E402

import argparse
import json
from pathlib import Path
import sys
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE))
sys.path.insert(0, str(WORKSPACE / "src"))

from scripts.aggregate_prta_gen_r41a_progression_sft import (
    paired_patient_bootstrap_with_invalid,
)
from scripts.build_prta_gen_r40b_smoke_cohort import read_json, write_json
from scripts.run_prta_gen_r45_cdeb_discovery import (
    CONFIG_STATUS,
    EVALUATION_ARMS,
)


def validate_result(
    config: dict[str, Any],
    result: dict[str, Any],
    *,
    seed: int,
    method: str,
) -> None:
    if (
        result.get("status") != config["result_statuses"]["arm_complete"]
        or result.get("protocol_id") != config["protocol_id"]
        or result.get("study_tier") != config["study_tier"]
        or result.get("seed") != seed
        or result.get("method") != method
        or result.get("method_spec") != config["methods"][method]
        or result.get("classes") != config["target"]["progression_values"]
        or result.get("training_rows") != 2500
        or result.get("training_patients") != 2500
        or result.get("development_rows") != 500
        or result.get("development_patients") != 500
        or result.get("optimizer_updates")
        != config["training"]["expected_optimizer_updates"]
        or result.get("qwen_trainable_parameters") != 0
        or result.get("exact64_tokens_used") is not True
        or result.get("qualified_positions_preserved") != [0, 60]
        or result.get("cdeb_evidence_positions") != [60, 61, 62, 63]
        or result.get("free_greedy_generation_evaluated") is not True
        or result.get("pixel_inputs_used") is not False
        or result.get("qualification_unlocked") is not False
        or result.get("confirmation_unlocked") is not False
        or result.get("qualification_outcomes_read") is not False
        or result.get("confirmation_outcomes_read") is not False
        or result.get("gold_outcomes_read") is not False
        or result.get("external_outcomes_read") is not False
        or result.get("scientific_claim_allowed") is not False
        or result.get("cache_equivalence_audit", {}).get("passed") is not True
        or set(result.get("metrics", {})) != set(EVALUATION_ARMS)
        or set(result.get("predictions", {})) != set(EVALUATION_ARMS)
    ):
        raise PermissionError(f"R45 discovery result drift: {seed}/{method}")
    auxiliary_expected = config["methods"][method][
        "auxiliary_loss_enabled"
    ]
    if auxiliary_expected != bool(result.get("auxiliary_metrics")):
        raise PermissionError("R45 auxiliary-result registry drift")
    checkpoint = Path(str(result.get("checkpoint", "")))
    if (
        not checkpoint.is_file()
        or checkpoint.stat().st_size != result.get("checkpoint_bytes")
    ):
        raise FileNotFoundError("R45 checkpoint receipt drift")


def evaluate_gate(
    config: dict[str, Any],
    results: dict[str, dict[str, Any]],
    comparisons: dict[str, Any],
) -> tuple[bool, list[dict[str, Any]]]:
    gate = config["discovery_gate"]
    full = results["full_cdeb"]
    metrics = full["metrics"]["true_pair"]
    failures: list[dict[str, Any]] = []
    scalar_checks = (
        (
            "full_true_macro_f1",
            float(metrics["macro_f1"]),
            float(gate["full_true_macro_f1_at_least"]),
        ),
        (
            "full_schema_validity",
            float(metrics["schema_validity"]),
            float(gate["full_schema_validity_at_least"]),
        ),
        (
            "full_finding_echo_accuracy",
            float(metrics["finding_echo_accuracy"]),
            float(gate["full_finding_echo_accuracy_at_least"]),
        ),
        (
            "full_auxiliary_true_macro_f1",
            float(full["auxiliary_metrics"]["true_pair"]["macro_f1"]),
            float(gate["full_auxiliary_true_macro_f1_at_least"]),
        ),
    )
    for name, observed, required in scalar_checks:
        if observed < required:
            failures.append(
                {
                    "gate": name,
                    "observed": observed,
                    "required_at_least": required,
                }
            )
    recall_floor = float(gate["full_all_class_recall_at_least"])
    for label, observed in metrics["per_class_recall"].items():
        if float(observed) < recall_floor:
            failures.append(
                {
                    "gate": "full_per_class_recall",
                    "class": label,
                    "observed": float(observed),
                    "required_at_least": recall_floor,
                }
            )
    effect_checks = (
        (
            "full_true_minus_prior_shuffle",
            float(comparisons["full_true_vs_prior_shuffle"]["effect_pp"]),
            float(
                gate[
                    "full_true_minus_prior_shuffle_macro_f1_at_least_pp"
                ]
            ),
        ),
        (
            "full_true_minus_baseline_true",
            float(comparisons["full_true_vs_baseline_true"]["effect_pp"]),
            float(
                gate[
                    "full_true_minus_baseline_true_macro_f1_at_least_pp"
                ]
            ),
        ),
        (
            "full_true_minus_no_delta_true",
            float(comparisons["full_true_vs_no_delta_true"]["effect_pp"]),
            float(
                gate[
                    "full_true_minus_no_delta_true_macro_f1_at_least_pp"
                ]
            ),
        ),
    )
    for name, observed, required in effect_checks:
        if observed < required:
            failures.append(
                {
                    "gate": name,
                    "observed_pp": observed,
                    "required_at_least_pp": required,
                }
            )
    agreement = float(full["true_prior_shuffle_same_prediction_rate"])
    maximum = float(
        gate["full_true_prior_shuffle_same_prediction_at_most"]
    )
    if agreement > maximum:
        failures.append(
            {
                "gate": "full_true_prior_shuffle_same_prediction",
                "observed": agreement,
                "required_at_most": maximum,
            }
        )
    return not failures, failures


def aggregate(config_path: Path) -> dict[str, Any]:
    config = read_json(config_path)
    if config.get("status") != CONFIG_STATUS:
        raise PermissionError("R45 discovery config is not frozen")
    seeds = [int(value) for value in config["training"]["discovery_seeds"]]
    if seeds != [17]:
        raise PermissionError("R45 discovery Seed registry drift")
    methods = [str(value) for value in config["methods"]["order"]]
    root = Path(config["runtime"]["discovery_root"])
    results: dict[str, dict[str, Any]] = {}
    for method in methods:
        result = read_json(root / "seed_17" / method / "result.json")
        validate_result(config, result, seed=17, method=method)
        results[method] = result
    reference = results[methods[0]]
    for result in results.values():
        for key in (
            "development_patient_ids",
            "development_example_ids",
            "targets",
            "classes",
        ):
            if result[key] != reference[key]:
                raise ValueError("R45 discovery result alignment drift")
    full = results["full_cdeb"]
    replicates = int(
        config["evaluation"]["patient_cluster_bootstrap_replicates"]
    )
    bootstrap_seed = int(
        config["evaluation"]["patient_cluster_bootstrap_seed"]
    )

    def compare(control: list[int]) -> dict[str, Any]:
        return paired_patient_bootstrap_with_invalid(
            patient_ids=full["development_patient_ids"],
            targets=full["targets"],
            primary_predictions=full["predictions"]["true_pair"],
            control_predictions=control,
            class_count=len(full["classes"]),
            replicates=replicates,
            seed=bootstrap_seed,
        )

    comparisons = {
        "full_true_vs_prior_shuffle": compare(
            full["predictions"]["prior_shuffle"]
        ),
        "full_true_vs_baseline_true": compare(
            results["baseline_projector"]["predictions"]["true_pair"]
        ),
        "full_true_vs_no_delta_true": compare(
            results["no_delta_evidence"]["predictions"]["true_pair"]
        ),
    }
    passed, failures = evaluate_gate(config, results, comparisons)
    output_path = root / "aggregate.json"
    if output_path.exists():
        raise FileExistsError("R45 discovery aggregate must be fresh")
    result = {
        "schema": "visualvit.prta-gen.r45-cdeb-discovery-aggregate.v1",
        "status": (
            config["result_statuses"]["aggregate_go"]
            if passed
            else config["result_statuses"]["aggregate_stop"]
        ),
        "protocol_id": config["protocol_id"],
        "study_tier": config["study_tier"],
        "seed": 17,
        "methods": methods,
        "evaluation_arms": list(EVALUATION_ARMS),
        "classes": reference["classes"],
        "development_patients": 500,
        "method_metrics": {
            method: result["metrics"] for method, result in results.items()
        },
        "auxiliary_metrics": {
            method: result["auxiliary_metrics"]
            for method, result in results.items()
        },
        "true_prior_shuffle_same_prediction_rate": {
            method: result["true_prior_shuffle_same_prediction_rate"]
            for method, result in results.items()
        },
        "comparisons": comparisons,
        "gate_passed": passed,
        "gate_failures": failures,
        "selected_method": (
            config["discovery_gate"]["selected_method"] if passed else None
        ),
        "qualification_unlocked": passed,
        "qualification_tokens_materialized": False,
        "confirmation_unlocked": False,
        "confirmation_tokens_materialized": False,
        "qualification_outcomes_read": False,
        "confirmation_outcomes_read": False,
        "r42_unlocked": False,
        "r43_unlocked": False,
        "gold_outcomes_read": False,
        "external_outcomes_read": False,
        "scientific_claim_allowed": False,
    }
    write_json(output_path, result)
    return result


def receipt_summary(result: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in result.items()
        if key not in {"gate_failures"}
    } | {"gate_failure_count": len(result["gate_failures"])}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Aggregate the frozen R45 CDEB discovery study"
    )
    parser.add_argument("--config", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = aggregate(args.config)
    print(json.dumps(receipt_summary(result), indent=2, sort_keys=True))
    return 0 if result["gate_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
