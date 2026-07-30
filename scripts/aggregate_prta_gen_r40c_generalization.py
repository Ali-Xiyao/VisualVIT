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

from scripts.aggregate_prta_gen_r40a_field import paired_patient_bootstrap
from scripts.build_prta_gen_r40b_smoke_cohort import read_json, write_json
from scripts.build_prta_gen_r40c_roster import CONFIG_STATUS, ROSTER_STATUS
from scripts.run_prta_gen_r40c_structured_generalization import (
    ARMS,
    SEED_STATUS,
)


def evaluate_gate(
    config: dict[str, Any],
    results: list[dict[str, Any]],
    comparisons: dict[str, Any],
) -> tuple[bool, list[dict[str, Any]]]:
    gate = config["gate"]
    required_controls = [
        str(value)
        for value in config["evaluation"]["required_primary_controls"]
    ]
    failures = []
    for result in results:
        seed = str(result["seed"])
        true_metrics = result["metrics"]["true_pair"]
        macro_f1 = float(true_metrics["macro_f1"])
        if macro_f1 < float(gate["all_seed_true_macro_f1_at_least"]):
            failures.append(
                {
                    "seed": int(seed),
                    "gate": "true_macro_f1",
                    "observed": macro_f1,
                    "required": float(
                        gate["all_seed_true_macro_f1_at_least"]
                    ),
                }
            )
        for label, recall in true_metrics["per_class_recall"].items():
            if float(recall) < float(
                gate["all_seed_all_class_recall_at_least"]
            ):
                failures.append(
                    {
                        "seed": int(seed),
                        "gate": "per_class_recall",
                        "class": label,
                        "observed": float(recall),
                        "required": float(
                            gate["all_seed_all_class_recall_at_least"]
                        ),
                    }
                )
        structured = result["structured"]
        for metric_name, gate_name in (
            ("schema_validity", "structured_schema_validity"),
            ("finding_echo_accuracy", "structured_finding_echo_accuracy"),
        ):
            if float(structured[metric_name]) != float(gate[gate_name]):
                failures.append(
                    {
                        "seed": int(seed),
                        "gate": metric_name,
                        "observed": float(structured[metric_name]),
                        "required": float(gate[gate_name]),
                    }
                )
        for control in required_controls:
            comparison = comparisons[control][seed]
            if float(comparison["effect_pp"]) < float(
                gate["all_seed_required_control_effects_at_least_pp"]
            ):
                failures.append(
                    {
                        "seed": int(seed),
                        "gate": f"effect_vs_{control}",
                        "observed": float(comparison["effect_pp"]),
                        "required": float(
                            gate[
                                "all_seed_required_control_effects_at_least_pp"
                            ]
                        ),
                    }
                )
            if float(comparison["ci95_lower_pp"]) <= float(
                gate["all_seed_required_control_ci95_lower_above_pp"]
            ):
                failures.append(
                    {
                        "seed": int(seed),
                        "gate": f"ci95_lower_vs_{control}",
                        "observed": float(comparison["ci95_lower_pp"]),
                        "required_strictly_above": float(
                            gate[
                                "all_seed_required_control_ci95_lower_above_pp"
                            ]
                        ),
                    }
                )
    return not failures, failures


def aggregate(
    *,
    config_path: Path,
    roster_path: Path,
) -> dict[str, Any]:
    config = read_json(config_path)
    if config.get("status") != CONFIG_STATUS:
        raise PermissionError("R40C config is not frozen")
    roster = read_json(roster_path)
    if (
        roster.get("status") != ROSTER_STATUS
        or roster.get("protocol_id") != config["protocol_id"]
        or roster.get("patient_sets_disjoint") is not True
        or roster.get("development_outcomes_read") is not False
        or roster.get("protected_300_dev_read") is not False
        or roster.get("revealed_483_test_read") is not False
        or roster.get("gold_outcomes_read") is not False
    ):
        raise PermissionError("R40C aggregate roster drift")
    seeds = [int(value) for value in config["training"]["seeds"]]
    root = Path(config["runtime"]["root"])
    results = [
        read_json(root / f"seed_{seed}" / "result.json") for seed in seeds
    ]
    for seed, result in zip(seeds, results, strict=True):
        if (
            result.get("status") != SEED_STATUS
            or result.get("protocol_id") != config["protocol_id"]
            or int(result.get("seed", -1)) != seed
            or result.get("normalization_fit_on_training_only") is not True
            or result.get("parameter_count")
            != int(config["head"]["parameter_count"])
            or result.get("qwen_free_generation_unlocked") is not False
            or result.get("scientific_claim_allowed") is not False
            or result.get("protected_300_dev_read") is not False
            or result.get("revealed_483_test_read") is not False
            or result.get("gold_outcomes_read") is not False
        ):
            raise PermissionError("R40C Seed result drift")
    reference = results[0]
    for result in results[1:]:
        if any(
            result[key] != reference[key]
            for key in (
                "classes",
                "development_patient_ids",
                "development_example_ids",
                "targets",
            )
        ):
            raise ValueError("R40C Seed-result alignment drift")
    replicates = int(
        config["evaluation"]["patient_cluster_bootstrap_replicates"]
    )
    bootstrap_seed = int(
        config["evaluation"]["patient_cluster_bootstrap_seed"]
    )
    comparisons: dict[str, Any] = defaultdict(dict)
    for result in results:
        seed_key = str(result["seed"])
        for control in ("current_only", "query_only", "prior_shuffle"):
            comparisons[control][seed_key] = paired_patient_bootstrap(
                patient_ids=result["development_patient_ids"],
                targets=result["targets"],
                true_predictions=result["predictions"]["true_pair"],
                control_predictions=result["predictions"][control],
                class_count=len(result["classes"]),
                replicates=replicates,
                seed=bootstrap_seed,
            )
    passed, failures = evaluate_gate(config, results, comparisons)
    output_path = root / "aggregate.json"
    if output_path.exists():
        raise FileExistsError(f"R40C aggregate must be fresh: {output_path}")
    aggregate_result = {
        "schema": "visualvit.prta-gen.r40c-aggregate.v1",
        "status": (
            config["result_statuses"]["aggregate_go"]
            if passed
            else config["result_statuses"]["aggregate_stop"]
        ),
        "protocol_id": config["protocol_id"],
        "study_tier": config["study_tier"],
        "seeds": seeds,
        "classes": reference["classes"],
        "arms": list(ARMS),
        "development_patients": len(
            set(reference["development_patient_ids"])
        ),
        "seed_metrics": {
            str(result["seed"]): result["metrics"] for result in results
        },
        "comparisons": dict(comparisons),
        "gate_passed": passed,
        "gate_failures": failures,
        "independent_confirmation_planning_unlocked": passed,
        "qwen_free_generation_unlocked": False,
        "laterality_generation_unlocked": False,
        "anatomy_generation_unlocked": False,
        "degree_generation_unlocked": False,
        "evidence_generation_unlocked": False,
        "r41_qwen_sft_unlocked": False,
        "scientific_claim_allowed": False,
        "protected_300_dev_read": False,
        "revealed_483_test_read": False,
        "gold_outcomes_read": False,
        "external_outcomes_read": False,
    }
    write_json(output_path, aggregate_result)
    return aggregate_result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Aggregate the frozen three-Seed R40C evaluation"
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--roster", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = aggregate(config_path=args.config, roster_path=args.roster)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["gate_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
