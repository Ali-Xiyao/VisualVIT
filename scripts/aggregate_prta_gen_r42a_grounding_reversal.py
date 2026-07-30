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

from scripts.aggregate_prta_gen_r41a_progression_sft import (
    paired_patient_bootstrap_with_invalid,
)
from scripts.build_prta_gen_r40b_smoke_cohort import read_json, write_json
from scripts.run_prta_gen_r42a_grounding_reversal import (
    ARM_STATUS,
    CONFIG_STATUS,
    FORWARD_ARMS,
    TRAINING_ARMS,
)


def _validate_result(
    config: dict[str, Any],
    result: dict[str, Any],
    *,
    seed: int,
    training_arm: str,
) -> None:
    if (
        result.get("status") != ARM_STATUS
        or result.get("protocol_id") != config["protocol_id"]
        or result.get("study_tier") != config["study_tier"]
        or int(result.get("seed", -1)) != seed
        or result.get("training_arm") != training_arm
        or result.get("classes") != config["target"]["progression_values"]
        or result.get("training_rows") != 375
        or result.get("training_patients") != 375
        or result.get("development_rows") != 125
        or result.get("development_patients") != 125
        or result.get("optimizer_updates")
        != config["training"]["expected_optimizer_updates"]
        or result.get("exact64_tokens_used") is not True
        or result.get("reverse_tokens_recomputed_by_input_swap") is not True
        or result.get("heuristic_token_permutation_used") is not False
        or result.get("free_greedy_generation_evaluated") is not True
        or result.get("pixel_inputs_used") is not False
        or result.get("r43_unlocked") is not False
        or result.get("scientific_claim_allowed") is not False
        or result.get("protected_300_dev_read") is not False
        or result.get("revealed_483_test_read") is not False
        or result.get("gold_outcomes_read") is not False
        or result.get("external_outcomes_read") is not False
    ):
        raise PermissionError(
            f"R42A Seed {seed}/{training_arm} receipt drift"
        )
    expected_metrics = {*FORWARD_ARMS, "time_reversed"}
    if set(result["metrics"]) != expected_metrics:
        raise PermissionError("R42A metric-arm receipt drift")
    if set(result["predictions"]) != expected_metrics:
        raise PermissionError("R42A prediction-arm receipt drift")
    checkpoint = Path(str(result.get("checkpoint", "")))
    if (
        not checkpoint.is_file()
        or checkpoint.stat().st_size != result.get("checkpoint_bytes")
    ):
        raise FileNotFoundError("R42A checkpoint receipt drift")


def evaluate_gate(
    config: dict[str, Any],
    results: dict[int, dict[str, dict[str, Any]]],
    comparisons: dict[str, Any],
) -> tuple[bool, list[dict[str, Any]]]:
    gate = config["gate"]
    primary_arm = config["evaluation"]["primary_training_arm"]
    failures = []
    for raw_seed in config["training"]["seeds"]:
        seed = int(raw_seed)
        primary = results[seed][primary_arm]
        true_metrics = primary["metrics"]["true_pair"]
        checks = (
            (
                "true_macro_f1",
                true_metrics["macro_f1"],
                gate["all_seed_primary_true_macro_f1_at_least"],
            ),
            (
                "schema_validity",
                true_metrics["schema_validity"],
                gate["all_seed_primary_schema_validity_at_least"],
            ),
            (
                "finding_echo_accuracy",
                true_metrics["finding_echo_accuracy"],
                gate["all_seed_primary_finding_echo_accuracy_at_least"],
            ),
            (
                "correct_prior_preference",
                primary["correct_prior_preference"][
                    "correct_prior_preference"
                ],
                gate["all_seed_correct_prior_preference_strictly_above"],
            ),
            (
                "reversal_mapped_accuracy",
                primary["metrics"]["time_reversed"]["progression_accuracy"],
                gate["all_seed_reversal_mapped_accuracy_at_least"],
            ),
        )
        for name, observed_value, required_value in checks:
            observed = float(observed_value)
            required = float(required_value)
            strict = name == "correct_prior_preference"
            failed = observed <= required if strict else observed < required
            if failed:
                failures.append(
                    {
                        "seed": seed,
                        "gate": name,
                        "observed": observed,
                        (
                            "required_strictly_above"
                            if strict
                            else "required_at_least"
                        ): required,
                    }
                )
        for label, recall in true_metrics["per_class_recall"].items():
            required = float(
                gate["all_seed_primary_all_class_recall_at_least"]
            )
            if float(recall) < required:
                failures.append(
                    {
                        "seed": seed,
                        "gate": "per_class_recall",
                        "class": label,
                        "observed": float(recall),
                        "required_at_least": required,
                    }
                )
        for control in config["evaluation"]["required_primary_controls"]:
            comparison = comparisons["primary_true_vs_control"][str(seed)][
                control
            ]
            effect_floor = float(
                gate["all_seed_required_control_effects_at_least_pp"]
            )
            if float(comparison["effect_pp"]) < effect_floor:
                failures.append(
                    {
                        "seed": seed,
                        "gate": f"effect_vs_{control}",
                        "observed_pp": float(comparison["effect_pp"]),
                        "required_at_least_pp": effect_floor,
                    }
                )
            ci_floor = float(
                gate["all_seed_required_control_ci95_lower_above_pp"]
            )
            if float(comparison["ci95_lower_pp"]) <= ci_floor:
                failures.append(
                    {
                        "seed": seed,
                        "gate": f"ci95_lower_vs_{control}",
                        "observed_pp": float(comparison["ci95_lower_pp"]),
                        "required_strictly_above_pp": ci_floor,
                    }
                )
        baseline_effect = comparisons["primary_true_vs_r41a_true"][str(seed)]
        baseline_floor = float(
            gate["all_seed_primary_minus_r41a_effect_at_least_pp"]
        )
        if float(baseline_effect["effect_pp"]) < baseline_floor:
            failures.append(
                {
                    "seed": seed,
                    "gate": "primary_minus_r41a_true_macro_f1",
                    "observed_pp": float(baseline_effect["effect_pp"]),
                    "required_at_least_pp": baseline_floor,
                }
            )
    return not failures, failures


def aggregate(*, config_path: Path) -> dict[str, Any]:
    config = read_json(config_path)
    if config.get("status") != CONFIG_STATUS:
        raise PermissionError("R42A config is not frozen")
    predecessor = read_json(Path(config["closed_predecessor"]["aggregate"]))
    if (
        predecessor.get("status")
        != config["closed_predecessor"]["required_status"]
        or predecessor.get("gate_passed") is not True
        or predecessor.get("r42_unlocked") is not True
    ):
        raise PermissionError("R42A aggregate predecessor drift")
    r41_config = read_json(WORKSPACE / config["source"]["r41_config"])
    r41_root = Path(r41_config["runtime"]["root"])
    root = Path(config["runtime"]["root"])
    results: dict[int, dict[str, dict[str, Any]]] = defaultdict(dict)
    r41_results = {}
    for raw_seed in config["training"]["seeds"]:
        seed = int(raw_seed)
        for training_arm in TRAINING_ARMS:
            result = read_json(
                root / f"seed_{seed}" / training_arm / "result.json"
            )
            _validate_result(
                config, result, seed=seed, training_arm=training_arm
            )
            results[seed][training_arm] = result
        r41_result = read_json(
            r41_root
            / f"seed_{seed}"
            / "g1_attention_lora"
            / "result.json"
        )
        if (
            r41_result.get("status")
            != r41_config["result_statuses"]["arm_complete"]
            or r41_result.get("seed") != seed
            or r41_result.get("model_arm") != "g1_attention_lora"
        ):
            raise PermissionError("R42A R41A baseline receipt drift")
        r41_results[seed] = r41_result
    reference = results[int(config["training"]["seeds"][0])][TRAINING_ARMS[0]]
    alignment_keys = (
        "development_patient_ids",
        "development_example_ids",
        "targets",
        "classes",
    )
    for seed, seed_results in results.items():
        for result in (*seed_results.values(), r41_results[seed]):
            if any(result[key] != reference[key] for key in alignment_keys):
                raise ValueError("R42A result alignment drift")
    replicates = int(
        config["evaluation"]["patient_cluster_bootstrap_replicates"]
    )
    bootstrap_seed = int(
        config["evaluation"]["patient_cluster_bootstrap_seed"]
    )
    primary_arm = config["evaluation"]["primary_training_arm"]
    comparisons: dict[str, Any] = {
        "primary_true_vs_control": {},
        "primary_true_vs_r41a_true": {},
    }
    for seed, seed_results in results.items():
        primary = seed_results[primary_arm]
        comparisons["primary_true_vs_control"][str(seed)] = {}
        for control in ("current_only", "query_only", "prior_shuffle"):
            comparisons["primary_true_vs_control"][str(seed)][control] = (
                paired_patient_bootstrap_with_invalid(
                    patient_ids=primary["development_patient_ids"],
                    targets=primary["targets"],
                    primary_predictions=primary["predictions"]["true_pair"],
                    control_predictions=primary["predictions"][control],
                    class_count=len(primary["classes"]),
                    replicates=replicates,
                    seed=bootstrap_seed,
                )
            )
        comparisons["primary_true_vs_r41a_true"][str(seed)] = (
            paired_patient_bootstrap_with_invalid(
                patient_ids=primary["development_patient_ids"],
                targets=primary["targets"],
                primary_predictions=primary["predictions"]["true_pair"],
                control_predictions=r41_results[seed]["predictions"][
                    "true_pair"
                ],
                class_count=len(primary["classes"]),
                replicates=replicates,
                seed=bootstrap_seed,
            )
        )
    passed, failures = evaluate_gate(config, results, comparisons)
    output_path = root / "aggregate.json"
    if output_path.exists():
        raise FileExistsError(f"R42A aggregate must be fresh: {output_path}")
    result = {
        "schema": "visualvit.prta-gen.r42a-aggregate.v1",
        "status": (
            config["result_statuses"]["aggregate_go"]
            if passed
            else config["result_statuses"]["aggregate_stop"]
        ),
        "protocol_id": config["protocol_id"],
        "study_tier": config["study_tier"],
        "seeds": [int(value) for value in config["training"]["seeds"]],
        "training_arms": list(TRAINING_ARMS),
        "primary_training_arm": primary_arm,
        "development_patients": len(
            set(reference["development_patient_ids"])
        ),
        "seed_metrics": {
            str(seed): {
                arm: {
                    "metrics": arm_result["metrics"],
                    "correct_prior_preference": arm_result[
                        "correct_prior_preference"
                    ],
                }
                for arm, arm_result in seed_results.items()
            }
            for seed, seed_results in results.items()
        },
        "comparisons": comparisons,
        "gate_passed": passed,
        "gate_failures": failures,
        "r43_readiness_unlocked": passed,
        "evidence_grounded_sentence_generation_claimed": False,
        "independent_scientific_confirmation": False,
        "scientific_claim_allowed": False,
        "protected_300_dev_read": False,
        "revealed_483_test_read": False,
        "gold_outcomes_read": False,
        "external_outcomes_read": False,
    }
    write_json(output_path, result)
    return result


def receipt_summary(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": result["schema"],
        "status": result["status"],
        "protocol_id": result["protocol_id"],
        "study_tier": result["study_tier"],
        "seeds": result["seeds"],
        "training_arms": result["training_arms"],
        "primary_training_arm": result["primary_training_arm"],
        "development_patients": result["development_patients"],
        "seed_metrics": result["seed_metrics"],
        "comparisons": result["comparisons"],
        "gate_passed": result["gate_passed"],
        "gate_failure_count": len(result["gate_failures"]),
        "r43_readiness_unlocked": result["r43_readiness_unlocked"],
        "scientific_claim_allowed": result["scientific_claim_allowed"],
        "protected_300_dev_read": result["protected_300_dev_read"],
        "revealed_483_test_read": result["revealed_483_test_read"],
        "gold_outcomes_read": result["gold_outcomes_read"],
        "external_outcomes_read": result["external_outcomes_read"],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Aggregate the frozen R42A grounding/reversal study"
    )
    parser.add_argument("--config", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = aggregate(config_path=args.config)
    print(json.dumps(receipt_summary(result), indent=2, sort_keys=True))
    return 0 if result["gate_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
