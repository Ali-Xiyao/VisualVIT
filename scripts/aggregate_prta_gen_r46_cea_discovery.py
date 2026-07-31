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
from scripts.run_prta_gen_r46_cea_discovery import (
    CONFIG_STATUS,
    HEAD_ARMS,
)
from visualvit.cea import select_shared_quantile


def _validate_common_firewall(result: dict[str, Any]) -> bool:
    return (
        result.get("r45_qualification_tokens_materialized") is False
        and result.get("r45_confirmation_tokens_materialized") is False
        and result.get("r45_qualification_outcomes_read") is False
        and result.get("r45_confirmation_outcomes_read") is False
        and result.get("gold_outcomes_read") is False
        and result.get("external_outcomes_read") is False
        and result.get("scientific_claim_allowed") is False
    )


def validate_baseline(
    config: dict[str, Any], result: dict[str, Any]
) -> None:
    if (
        result.get("status") != config["result_statuses"]["baseline_complete"]
        or result.get("protocol_id") != config["protocol_id"]
        or result.get("study_tier") != config["study_tier"]
        or result.get("classes") != config["target"]["progression_values"]
        or set(result.get("metrics", {})) != set(
            config["evaluation"]["generator_arms"]
        )
        or set(result.get("predictions", {})) != set(
            config["evaluation"]["generator_arms"]
        )
        or len(result.get("targets", [])) != 250
        or result.get("qwen_trainable_parameters") != 0
        or result.get("projector_trainable_parameters") != 0
        or result.get("cache_equivalence_audit", {}).get("passed") is not True
        or result.get("exact64_tokens_used") is not True
        or result.get("free_greedy_generation_evaluated") is not True
        or result.get("pixel_inputs_used") is not False
        or not _validate_common_firewall(result)
    ):
        raise PermissionError("R46 baseline result drift")


def validate_seed(
    config: dict[str, Any],
    result: dict[str, Any],
    *,
    seed: int,
    baseline: dict[str, Any],
) -> None:
    expected_keys = {
        f"{float(value):.2f}"
        for value in config["arbitration"][
            "candidate_override_coverage_quantiles"
        ]
    }
    if (
        result.get("status") != config["result_statuses"]["seed_complete"]
        or result.get("protocol_id") != config["protocol_id"]
        or result.get("study_tier") != config["study_tier"]
        or result.get("seed") != seed
        or result.get("classes") != config["target"]["progression_values"]
        or result.get("training_rows") != 2500
        or result.get("training_patients") != 2500
        or result.get("development_rows") != 250
        or result.get("development_patients") != 250
        or result.get("development_patient_ids")
        != baseline["development_patient_ids"]
        or result.get("development_example_ids")
        != baseline["development_example_ids"]
        or result.get("targets") != baseline["targets"]
        or set(result.get("structured_predictions", {})) != set(HEAD_ARMS)
        or set(result.get("structured_metrics", {})) != set(HEAD_ARMS)
        or set(result.get("arbitration_candidates", {})) != expected_keys
        or result.get("training_audit", {}).get("updates")
        != config["training"]["expected_updates_per_seed"]
        or result.get("exact64_tokens_used") is not True
        or result.get("qwen_loaded") is not False
        or result.get("qwen_trainable_parameters") != 0
        or result.get("schema_validity") != 1.0
        or result.get("finding_echo_accuracy") != 1.0
        or not _validate_common_firewall(result)
    ):
        raise PermissionError(f"R46 Seed result drift: {seed}")
    checkpoint = Path(str(result.get("checkpoint", "")))
    if (
        not checkpoint.is_file()
        or checkpoint.stat().st_size != result.get("checkpoint_bytes")
    ):
        raise FileNotFoundError(f"R46 Seed checkpoint drift: {seed}")


def _gate_failures(
    config: dict[str, Any],
    *,
    seeds: list[int],
    seed_results: dict[int, dict[str, Any]],
    selected_key: str,
    baseline: dict[str, Any],
    comparisons: dict[str, Any],
) -> list[dict[str, Any]]:
    gate = config["discovery_gate"]
    failures: list[dict[str, Any]] = []
    baseline_f1 = float(baseline["metrics"]["true_pair"]["macro_f1"])
    cea_f1s = []
    shuffle_f1s = []
    coverages = []
    overrides = []
    agreements = []
    for seed in seeds:
        result = seed_results[seed]
        structured_f1 = float(
            result["structured_metrics"]["true_pair"]["macro_f1"]
        )
        candidate = result["arbitration_candidates"][selected_key]
        true_arm = candidate["arms"]["true_pair"]
        shuffle_arm = candidate["arms"]["prior_shuffle"]
        cea_f1 = float(true_arm["metrics"]["macro_f1"])
        shuffle_f1 = float(shuffle_arm["metrics"]["macro_f1"])
        cea_f1s.append(cea_f1)
        shuffle_f1s.append(shuffle_f1)
        coverages.append(float(true_arm["eligible_coverage"]))
        overrides.append(float(true_arm["actual_override_rate"]))
        agreements.append(
            float(true_arm["low_evidence_baseline_agreement"])
        )
        checks = (
            (
                "structured_true_macro_f1",
                structured_f1,
                float(gate["all_seed_structured_true_macro_f1_at_least"]),
            ),
            (
                "cea_true_macro_f1",
                cea_f1,
                float(gate["all_seed_cea_true_macro_f1_at_least"]),
            ),
            (
                "cea_minus_baseline_true",
                100.0 * (cea_f1 - baseline_f1),
                float(
                    gate[
                        "all_seed_cea_minus_baseline_true_macro_f1_at_least_pp"
                    ]
                ),
            ),
        )
        for name, observed, required in checks:
            if observed < required:
                failures.append(
                    {
                        "gate": name,
                        "seed": seed,
                        "observed": observed,
                        "required_at_least": required,
                    }
                )
        recall_floor = float(
            gate["all_seed_cea_all_class_recall_at_least"]
        )
        for label, observed in true_arm["metrics"][
            "per_class_recall"
        ].items():
            if float(observed) < recall_floor:
                failures.append(
                    {
                        "gate": "cea_per_class_recall",
                        "seed": seed,
                        "class": label,
                        "observed": float(observed),
                        "required_at_least": recall_floor,
                    }
                )
    mean_cea = sum(cea_f1s) / len(cea_f1s)
    mean_shuffle = sum(shuffle_f1s) / len(shuffle_f1s)
    mean_coverage = sum(coverages) / len(coverages)
    mean_override = sum(overrides) / len(overrides)
    aggregate_checks = (
        (
            "mean_cea_minus_baseline_true",
            100.0 * (mean_cea - baseline_f1),
            float(
                gate[
                    "mean_cea_minus_baseline_true_macro_f1_at_least_pp"
                ]
            ),
            "at_least",
        ),
        (
            "mean_cea_true_minus_prior_shuffle",
            100.0 * (mean_cea - mean_shuffle),
            float(gate["mean_cea_true_minus_prior_shuffle_at_least_pp"]),
            "at_least",
        ),
        (
            "mean_eligible_coverage_minimum",
            mean_coverage,
            float(gate["mean_eligible_coverage_at_least"]),
            "at_least",
        ),
        (
            "mean_eligible_coverage_maximum",
            mean_coverage,
            float(gate["mean_eligible_coverage_at_most"]),
            "at_most",
        ),
        (
            "mean_actual_override_rate_minimum",
            mean_override,
            float(gate["mean_actual_override_rate_at_least"]),
            "at_least",
        ),
        (
            "mean_actual_override_rate_maximum",
            mean_override,
            float(gate["mean_actual_override_rate_at_most"]),
            "at_most",
        ),
        (
            "low_evidence_baseline_agreement",
            min(agreements),
            float(gate["low_evidence_baseline_agreement"]),
            "at_least",
        ),
    )
    for name, observed, required, direction in aggregate_checks:
        failed = (
            observed < required
            if direction == "at_least"
            else observed > required
        )
        if failed:
            failures.append(
                {
                    "gate": name,
                    "observed": observed,
                    f"required_{direction}": required,
                }
            )
    ci_checks = (
        (
            "pooled_cea_minus_baseline_ci95_lower",
            float(comparisons["cea_true_vs_baseline"]["ci95_lower_pp"]),
            float(
                gate["pooled_cea_minus_baseline_ci95_lower_above_pp"]
            ),
        ),
        (
            "pooled_cea_true_minus_prior_shuffle_ci95_lower",
            float(
                comparisons["cea_true_vs_prior_shuffle"]["ci95_lower_pp"]
            ),
            float(
                gate[
                    "pooled_cea_true_minus_prior_shuffle_ci95_lower_above_pp"
                ]
            ),
        ),
    )
    for name, observed, required in ci_checks:
        if observed <= required:
            failures.append(
                {
                    "gate": name,
                    "observed_pp": observed,
                    "required_above_pp": required,
                }
            )
    return failures


def aggregate(config_path: Path) -> dict[str, Any]:
    config = read_json(config_path)
    if config.get("status") != CONFIG_STATUS:
        raise PermissionError("R46 discovery config is not frozen")
    root = Path(config["runtime"]["discovery_root"])
    output_path = root / "aggregate.json"
    if output_path.exists():
        raise FileExistsError("R46 aggregate must be fresh")
    baseline = read_json(root / "baseline" / "result.json")
    validate_baseline(config, baseline)
    seeds = [int(value) for value in config["training"]["seeds"]]
    seed_results = {
        seed: read_json(root / f"seed_{seed}" / "result.json")
        for seed in seeds
    }
    for seed, result in seed_results.items():
        validate_seed(
            config,
            result,
            seed=seed,
            baseline=baseline,
        )
    candidates: dict[str, list[dict[str, float]]] = {}
    for key in seed_results[seeds[0]]["arbitration_candidates"]:
        candidates[key] = [
            {
                "macro_f1": float(
                    seed_results[seed]["arbitration_candidates"][key][
                        "arms"
                    ]["true_pair"]["metrics"]["macro_f1"]
                ),
                "actual_override_rate": float(
                    seed_results[seed]["arbitration_candidates"][key][
                        "arms"
                    ]["true_pair"]["actual_override_rate"]
                ),
            }
            for seed in seeds
        ]
    selected = select_shared_quantile(candidates)
    selected_key = f"{selected['quantile']:.2f}"
    patient_ids = baseline["development_patient_ids"] * len(seeds)
    targets = baseline["targets"] * len(seeds)
    cea_true = [
        prediction
        for seed in seeds
        for prediction in seed_results[seed][
            "arbitration_candidates"
        ][selected_key]["arms"]["true_pair"]["predictions"]
    ]
    baseline_true = baseline["predictions"]["true_pair"] * len(seeds)
    cea_shuffle = [
        prediction
        for seed in seeds
        for prediction in seed_results[seed][
            "arbitration_candidates"
        ][selected_key]["arms"]["prior_shuffle"]["predictions"]
    ]
    replicates = int(
        config["evaluation"]["patient_cluster_bootstrap_replicates"]
    )
    bootstrap_seed = int(
        config["evaluation"]["patient_cluster_bootstrap_seed"]
    )
    comparisons = {
        "cea_true_vs_baseline": paired_patient_bootstrap_with_invalid(
            patient_ids=patient_ids,
            targets=targets,
            primary_predictions=cea_true,
            control_predictions=baseline_true,
            class_count=len(config["target"]["progression_values"]),
            replicates=replicates,
            seed=bootstrap_seed,
        ),
        "cea_true_vs_prior_shuffle": paired_patient_bootstrap_with_invalid(
            patient_ids=patient_ids,
            targets=targets,
            primary_predictions=cea_true,
            control_predictions=cea_shuffle,
            class_count=len(config["target"]["progression_values"]),
            replicates=replicates,
            seed=bootstrap_seed + 1,
        ),
    }
    failures = _gate_failures(
        config,
        seeds=seeds,
        seed_results=seed_results,
        selected_key=selected_key,
        baseline=baseline,
        comparisons=comparisons,
    )
    passed = not failures
    selected_seed_results = {
        str(seed): seed_results[seed]["arbitration_candidates"][selected_key]
        for seed in seeds
    }
    result = {
        "schema": "visualvit.prta-gen.r46-cea-discovery-aggregate.v1",
        "status": (
            config["result_statuses"]["aggregate_go"]
            if passed
            else config["result_statuses"]["aggregate_stop"]
        ),
        "protocol_id": config["protocol_id"],
        "study_tier": config["study_tier"],
        "seeds": seeds,
        "classes": baseline["classes"],
        "development_patients": 250,
        "selected_quantile": selected["quantile"],
        "selected_quantile_key": selected_key,
        "selection_summary": selected,
        "baseline_metrics": baseline["metrics"],
        "structured_metrics": {
            str(seed): seed_results[seed]["structured_metrics"]
            for seed in seeds
        },
        "selected_seed_results": selected_seed_results,
        "comparisons": comparisons,
        "gate_passed": passed,
        "gate_failure_count": len(failures),
        "gate_failures": failures,
        "qualification_unlocked": passed,
        "confirmation_unlocked": False,
        "r45_qualification_tokens_materialized": False,
        "r45_confirmation_tokens_materialized": False,
        "r45_qualification_outcomes_read": False,
        "r45_confirmation_outcomes_read": False,
        "protected_300_dev_read": False,
        "revealed_483_test_read": False,
        "gold_outcomes_read": False,
        "external_outcomes_read": False,
        "r42_unlocked": False,
        "r43_unlocked": False,
        "scientific_claim_allowed": False,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(output_path, result)
    return result


def receipt_summary(result: dict[str, Any]) -> dict[str, Any]:
    summary = dict(result)
    if "selected_seed_results" in summary:
        summary["selected_seed_results"] = {
            seed: {
                "quantile": value["quantile"],
                "threshold": value["threshold"],
                "true_pair": {
                    key: metric
                    for key, metric in value["arms"]["true_pair"].items()
                    if key
                    not in {"predictions", "eligible", "changed"}
                },
                "prior_shuffle": {
                    key: metric
                    for key, metric in value["arms"]["prior_shuffle"].items()
                    if key
                    not in {"predictions", "eligible", "changed"}
                },
            }
            for seed, value in result["selected_seed_results"].items()
        }
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Aggregate frozen R46 CEA discovery"
    )
    parser.add_argument("--config", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = aggregate(args.config)
    print(json.dumps(receipt_summary(result), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
