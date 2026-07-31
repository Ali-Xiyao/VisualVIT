from __future__ import annotations

# ruff: noqa: E402

import argparse
from collections import defaultdict
import json
from pathlib import Path
import sys
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE))
sys.path.insert(0, str(WORKSPACE / "src"))

import numpy as np

from scripts.build_prta_gen_r40b_smoke_cohort import read_json, write_json
from scripts.build_prta_gen_r41a_roster import CONFIG_STATUS
from scripts.run_prta_gen_r41a_progression_sft import (
    EVALUATION_ARMS,
    MODEL_ARMS,
)


def _expected_config_status(config: dict[str, Any]) -> str:
    if config.get("stage_tag") == "R44A":
        return "FROZEN_PRTA_GEN_R44A_CROSS_SOURCE_SILVER_SFT"
    return CONFIG_STATUS


def _patient_confusions(
    patient_ids: list[str],
    targets: list[int],
    predictions: list[int],
    *,
    class_count: int,
) -> tuple[list[str], np.ndarray]:
    if not (
        len(patient_ids) == len(targets) == len(predictions)
    ) or not patient_ids:
        raise ValueError("R41A bootstrap arrays must be aligned and non-empty")
    patients = sorted(set(patient_ids))
    patient_to_index = {value: index for index, value in enumerate(patients)}
    matrices = np.zeros(
        (len(patients), class_count, class_count + 1), dtype=np.int64
    )
    for patient, target, prediction in zip(
        patient_ids, targets, predictions, strict=True
    ):
        if not 0 <= target < class_count:
            raise ValueError("R41A bootstrap target exceeds class registry")
        if prediction == -1:
            prediction_index = class_count
        elif 0 <= prediction < class_count:
            prediction_index = prediction
        else:
            raise ValueError("R41A bootstrap prediction exceeds registry")
        matrices[patient_to_index[patient], target, prediction_index] += 1
    return patients, matrices


def _macro_f1_from_confusion(confusion: np.ndarray) -> float:
    class_count = confusion.shape[0]
    scores = []
    for label in range(class_count):
        true_positive = float(confusion[label, label])
        false_positive = float(confusion[:, label].sum() - true_positive)
        false_negative = float(confusion[label, :].sum() - true_positive)
        denominator = 2.0 * true_positive + false_positive + false_negative
        scores.append(0.0 if denominator == 0.0 else 2.0 * true_positive / denominator)
    return float(np.mean(scores))


def paired_patient_bootstrap_with_invalid(
    *,
    patient_ids: list[str],
    targets: list[int],
    primary_predictions: list[int],
    control_predictions: list[int],
    class_count: int,
    replicates: int,
    seed: int,
) -> dict[str, Any]:
    patients, primary = _patient_confusions(
        patient_ids,
        targets,
        primary_predictions,
        class_count=class_count,
    )
    control_patients, control = _patient_confusions(
        patient_ids,
        targets,
        control_predictions,
        class_count=class_count,
    )
    if patients != control_patients:
        raise ValueError("R41A paired-bootstrap patient registries differ")
    rng = np.random.default_rng(seed)
    samples = rng.integers(
        0, len(patients), size=(replicates, len(patients))
    )
    effects = np.empty(replicates, dtype=np.float64)
    for index, sampled in enumerate(samples):
        effects[index] = _macro_f1_from_confusion(
            primary[sampled].sum(axis=0)
        ) - _macro_f1_from_confusion(control[sampled].sum(axis=0))
    point = _macro_f1_from_confusion(
        primary.sum(axis=0)
    ) - _macro_f1_from_confusion(control.sum(axis=0))
    lower, upper = np.quantile(effects, [0.025, 0.975])
    return {
        "effect_pp": 100.0 * point,
        "ci95_lower_pp": 100.0 * float(lower),
        "ci95_upper_pp": 100.0 * float(upper),
        "replicates": replicates,
        "seed": seed,
        "unit": "patient_cluster",
        "patients": len(patients),
        "invalid_predictions_supported": True,
    }


def _validate_result(
    config: dict[str, Any],
    result: dict[str, Any],
    *,
    seed: int,
    model_arm: str,
) -> None:
    if (
        result.get("status") != config["result_statuses"]["arm_complete"]
        or result.get("protocol_id") != config["protocol_id"]
        or result.get("study_tier") != config["study_tier"]
        or int(result.get("seed", -1)) != seed
        or result.get("model_arm") != model_arm
        or result.get("classes") != config["target"]["progression_values"]
        or result.get("training_rows") != config["roster"]["train_patients"]
        or result.get("training_patients")
        != config["roster"]["train_patients"]
        or result.get("development_rows")
        != config["roster"]["development_patients"]
        or result.get("development_patients")
        != config["roster"]["development_patients"]
        or result.get("optimizer_updates")
        != config["training"]["expected_optimizer_updates"]
        or result.get("exact64_tokens_used") is not True
        or result.get("free_greedy_generation_evaluated") is not True
        or result.get("pixel_inputs_used") is not False
        or result.get("qwen_free_generation_survival_unlocked") is not False
        or result.get("r42_unlocked") is not False
        or result.get("scientific_claim_allowed") is not False
        or result.get("protected_300_dev_read") is not False
        or result.get("revealed_483_test_read") is not False
        or result.get("gold_outcomes_read") is not False
        or result.get("external_outcomes_read") is not False
    ):
        raise PermissionError(f"R41A Seed {seed}/{model_arm} receipt drift")
    if set(result["metrics"]) != set(EVALUATION_ARMS):
        raise PermissionError("R41A evaluation-arm result drift")
    if set(result["predictions"]) != set(EVALUATION_ARMS):
        raise PermissionError("R41A prediction-arm result drift")
    if result["cache_equivalence_audit"]["passed"] is not True:
        raise PermissionError("R41A cache-equivalence receipt drift")
    audit = result["trainable_parameter_audit"]
    if (
        audit["trainable_boundary_pass"] is not True
        or audit["unexpected_trainable_parameter_count"] != 0
        or (
            model_arm == "g0_projector_only"
            and audit["trainable_parameters"] != 0
        )
        or (
            model_arm == "g1_attention_lora"
            and audit["trainable_parameters"] <= 0
        )
    ):
        raise PermissionError("R41A trainable-boundary receipt drift")
    checkpoint = Path(str(result.get("checkpoint", "")))
    if (
        not checkpoint.is_file()
        or checkpoint.stat().st_size != result.get("checkpoint_bytes")
    ):
        raise FileNotFoundError("R41A checkpoint receipt drift")


def evaluate_gate(
    config: dict[str, Any],
    results: dict[int, dict[str, dict[str, Any]]],
    comparisons: dict[str, Any],
) -> tuple[bool, list[dict[str, Any]]]:
    gate = config["gate"]
    failures = []
    for seed in config["training"]["seeds"]:
        g1 = results[int(seed)]["g1_attention_lora"]["metrics"]["true_pair"]
        checks = (
            (
                "g1_true_macro_f1",
                float(g1["macro_f1"]),
                float(gate["all_seed_g1_true_macro_f1_at_least"]),
            ),
            (
                "g1_schema_validity",
                float(g1["schema_validity"]),
                float(gate["all_seed_g1_schema_validity_at_least"]),
            ),
            (
                "g1_finding_echo_accuracy",
                float(g1["finding_echo_accuracy"]),
                float(gate["all_seed_g1_finding_echo_accuracy_at_least"]),
            ),
        )
        for name, observed, required in checks:
            if observed < required:
                failures.append(
                    {
                        "seed": int(seed),
                        "gate": name,
                        "observed": observed,
                        "required_at_least": required,
                    }
                )
        for label, recall in g1["per_class_recall"].items():
            required = float(
                gate["all_seed_g1_all_class_recall_at_least"]
            )
            if float(recall) < required:
                failures.append(
                    {
                        "seed": int(seed),
                        "gate": "g1_per_class_recall",
                        "class": label,
                        "observed": float(recall),
                        "required_at_least": required,
                    }
                )
        for control in config["evaluation"]["required_primary_controls"]:
            comparison = comparisons["g1_true_vs_control"][str(seed)][control]
            required_effect = float(
                gate[
                    "all_seed_g1_required_control_effects_at_least_pp"
                ]
            )
            if float(comparison["effect_pp"]) < required_effect:
                failures.append(
                    {
                        "seed": int(seed),
                        "gate": f"g1_effect_vs_{control}",
                        "observed_pp": float(comparison["effect_pp"]),
                        "required_at_least_pp": required_effect,
                    }
                )
            lower_floor = float(
                gate[
                    "all_seed_g1_required_control_ci95_lower_above_pp"
                ]
            )
            if float(comparison["ci95_lower_pp"]) <= lower_floor:
                failures.append(
                    {
                        "seed": int(seed),
                        "gate": f"g1_ci95_lower_vs_{control}",
                        "observed_pp": float(comparison["ci95_lower_pp"]),
                        "required_strictly_above_pp": lower_floor,
                    }
                )
        model_effect = comparisons["g1_true_vs_g0_true"][str(seed)]
        required_model_effect = float(
            gate["all_seed_g1_minus_g0_effect_at_least_pp"]
        )
        if float(model_effect["effect_pp"]) < required_model_effect:
            failures.append(
                {
                    "seed": int(seed),
                    "gate": "g1_minus_g0_true_macro_f1",
                    "observed_pp": float(model_effect["effect_pp"]),
                    "required_at_least_pp": required_model_effect,
                }
            )
    return not failures, failures


def aggregate(
    *, config_path: Path, roster_path: Path
) -> dict[str, Any]:
    config = read_json(config_path)
    if config.get("status") != _expected_config_status(config):
        raise PermissionError("R41A config is not frozen")
    roster = read_json(roster_path)
    if (
        roster.get("status") != config["result_statuses"]["roster_pass"]
        or roster.get("protocol_id") != config["protocol_id"]
        or roster.get("patient_sets_disjoint") is not True
        or roster.get("development_outcomes_read") is not False
        or roster.get("protected_300_dev_read") is not False
        or roster.get("revealed_483_test_read") is not False
        or roster.get("gold_outcomes_read") is not False
        or roster.get("external_outcomes_read") is not False
    ):
        raise PermissionError("R41A aggregate roster drift")
    root = Path(config["runtime"]["root"])
    results: dict[int, dict[str, dict[str, Any]]] = defaultdict(dict)
    for raw_seed in config["training"]["seeds"]:
        seed = int(raw_seed)
        for model_arm in MODEL_ARMS:
            result = read_json(
                root / f"seed_{seed}" / model_arm / "result.json"
            )
            _validate_result(
                config, result, seed=seed, model_arm=model_arm
            )
            results[seed][model_arm] = result
    reference = results[int(config["training"]["seeds"][0])][
        "g0_projector_only"
    ]
    alignment_keys = (
        "development_patient_ids",
        "development_example_ids",
        "targets",
        "classes",
    )
    for seed_results in results.values():
        for result in seed_results.values():
            if any(result[key] != reference[key] for key in alignment_keys):
                raise ValueError("R41A arm-result alignment drift")
    replicates = int(
        config["evaluation"]["patient_cluster_bootstrap_replicates"]
    )
    bootstrap_seed = int(
        config["evaluation"]["patient_cluster_bootstrap_seed"]
    )
    comparisons: dict[str, Any] = {
        "g1_true_vs_control": {},
        "g1_true_vs_g0_true": {},
    }
    for seed, seed_results in results.items():
        g1 = seed_results["g1_attention_lora"]
        g0 = seed_results["g0_projector_only"]
        comparisons["g1_true_vs_control"][str(seed)] = {}
        for control in ("current_only", "query_only", "prior_shuffle"):
            comparisons["g1_true_vs_control"][str(seed)][control] = (
                paired_patient_bootstrap_with_invalid(
                    patient_ids=g1["development_patient_ids"],
                    targets=g1["targets"],
                    primary_predictions=g1["predictions"]["true_pair"],
                    control_predictions=g1["predictions"][control],
                    class_count=len(g1["classes"]),
                    replicates=replicates,
                    seed=bootstrap_seed,
                )
            )
        comparisons["g1_true_vs_g0_true"][str(seed)] = (
            paired_patient_bootstrap_with_invalid(
                patient_ids=g1["development_patient_ids"],
                targets=g1["targets"],
                primary_predictions=g1["predictions"]["true_pair"],
                control_predictions=g0["predictions"]["true_pair"],
                class_count=len(g1["classes"]),
                replicates=replicates,
                seed=bootstrap_seed,
            )
        )
    passed, failures = evaluate_gate(config, results, comparisons)
    output_path = root / "aggregate.json"
    if output_path.exists():
        raise FileExistsError(f"R41A aggregate must be fresh: {output_path}")
    seed_metrics = {
        str(seed): {
            model_arm: result["metrics"]
            for model_arm, result in seed_results.items()
        }
        for seed, seed_results in results.items()
    }
    downstream_unlock_allowed = bool(
        config["gate"].get("downstream_unlock_allowed", True)
    )
    result = {
        "schema": config.get("runtime_contract", {}).get(
            "aggregate_schema",
            "visualvit.prta-gen.r41a-aggregate.v1",
        ),
        "status": (
            config["result_statuses"]["aggregate_go"]
            if passed
            else config["result_statuses"]["aggregate_stop"]
        ),
        "protocol_id": config["protocol_id"],
        "study_tier": config["study_tier"],
        "seeds": [int(value) for value in config["training"]["seeds"]],
        "model_arms": list(MODEL_ARMS),
        "evaluation_arms": list(EVALUATION_ARMS),
        "classes": reference["classes"],
        "development_patients": len(
            set(reference["development_patient_ids"])
        ),
        "seed_metrics": seed_metrics,
        "comparisons": comparisons,
        "gate_passed": passed,
        "gate_failures": failures,
        "qwen_free_generation_survival_unlocked": (
            passed and downstream_unlock_allowed
        ),
        "r42_unlocked": passed and downstream_unlock_allowed,
        "r43_unlocked": False,
        "laterality_generation_unlocked": False,
        "anatomy_generation_unlocked": False,
        "degree_generation_unlocked": False,
        "evidence_generation_unlocked": False,
        "independent_scientific_confirmation": False,
        "scientific_claim_allowed": False,
        "protected_300_dev_read": False,
        "revealed_483_test_read": False,
        "gold_outcomes_read": False,
        "external_outcomes_read": False,
    }
    if config.get("stage_tag") == "R44A":
        result["cross_source_silver_survival_supported"] = passed
    write_json(output_path, result)
    return result


def receipt_summary(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": result["schema"],
        "status": result["status"],
        "protocol_id": result["protocol_id"],
        "study_tier": result["study_tier"],
        "seeds": result["seeds"],
        "development_patients": result["development_patients"],
        "seed_metrics": result["seed_metrics"],
        "comparisons": result["comparisons"],
        "gate_passed": result["gate_passed"],
        "gate_failure_count": len(result["gate_failures"]),
        "qwen_free_generation_survival_unlocked": result[
            "qwen_free_generation_survival_unlocked"
        ],
        "r42_unlocked": result["r42_unlocked"],
        "r43_unlocked": result["r43_unlocked"],
        "scientific_claim_allowed": result["scientific_claim_allowed"],
        "protected_300_dev_read": result["protected_300_dev_read"],
        "revealed_483_test_read": result["revealed_483_test_read"],
        "gold_outcomes_read": result["gold_outcomes_read"],
        "external_outcomes_read": result["external_outcomes_read"],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Aggregate the frozen R41A progression-only SFT study"
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--roster", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = aggregate(config_path=args.config, roster_path=args.roster)
    print(json.dumps(receipt_summary(result), indent=2, sort_keys=True))
    return 0 if result["gate_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
