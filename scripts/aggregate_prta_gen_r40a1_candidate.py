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
from scripts.cache_prta_gen_r40a1_features import (
    CONFIG_STATUSES,
    ROSTER_STATUSES,
    candidate_spec,
)
from scripts.cache_prta_gen_r40a_tokens import read_json
from scripts.run_prta_gen_r40a1_probe import RESULT_STATUS


def finalize_early_stop(
    *,
    config_path: Path,
    roster_path: Path,
    candidate_name: str,
    scope: str,
) -> dict[str, Any]:
    config = read_json(config_path)
    if config.get("status") not in CONFIG_STATUSES:
        raise PermissionError("R40A.1 config is not frozen")
    candidate_spec(config, candidate_name)
    if scope != "discovery":
        raise ValueError("early stop is registered only for discovery")
    roster = read_json(roster_path)
    if (
        roster.get("status") not in ROSTER_STATUSES
        or roster.get("qualification_outcomes_read") is not False
        or roster.get("revealed_483_test_read") is not False
        or roster.get("gold_outcomes_read") is not False
    ):
        raise PermissionError("R40A.1 roster firewall drift")
    result_root = roster_path.parent / "probes" / candidate_name / scope
    completed = []
    for seed in config["probe"]["seeds"]:
        path = result_root / f"seed_{seed}" / "result.json"
        if not path.exists():
            break
        result = read_json(path)
        if (
            result.get("status") != RESULT_STATUS
            or result.get("candidate") != candidate_name
            or result.get("scope") != scope
            or int(result.get("seed", -1)) != int(seed)
            or result.get("revealed_483_test_read") is not False
            or result.get("gold_outcomes_read") is not False
            or result.get("old_r40a_development_used_for_selection") is not False
        ):
            raise PermissionError("R40A.1 early-stop result drift")
        completed.append(result)
    if not completed:
        raise ValueError("early stop requires at least one completed Seed")
    gate = config["discovery_gate"]
    minimum_pp = float(gate["all_three_seed_effects_at_least_pp"])
    metric_by_control = {
        "query_only": "true_minus_query_pp",
        "prior_shuffle": "true_minus_shuffle_pp",
    }
    triggers = []
    for result in completed:
        for control in gate["required_controls"]:
            effect = float(result["metrics"][metric_by_control[control]])
            if effect < minimum_pp:
                triggers.append(
                    {
                        "seed": int(result["seed"]),
                        "control": control,
                        "effect_pp": effect,
                        "required_minimum_pp": minimum_pp,
                    }
                )
    if not triggers:
        raise ValueError("completed Seeds do not justify an early STOP")
    output_path = result_root / "aggregate.json"
    if output_path.exists():
        raise FileExistsError(
            f"R40A.1 aggregate output must be fresh: {output_path}"
        )
    completed_seeds = [int(result["seed"]) for result in completed]
    stage_tag = str(config.get("stage_tag", "R40A1"))
    aggregate = {
        "schema": "visualvit.prta-gen.r40a1-candidate-aggregate.v1",
        "status": f"STOP_PRTA_GEN_{stage_tag}_DISCOVERY",
        "protocol_id": config["protocol_id"],
        "candidate": candidate_name,
        "scope": scope,
        "completed_seeds": completed_seeds,
        "skipped_seeds_after_first_failed_gate": [
            int(seed)
            for seed in config["probe"]["seeds"]
            if int(seed) not in completed_seeds
        ],
        "early_stop_triggers": triggers,
        "gate_passed": False,
        "candidate_selected": False,
        "qualification_unlocked": False,
        "progression_generation_unlocked": False,
        "protected_300_dev_read": False,
        "revealed_483_test_read": False,
        "gold_outcomes_read": False,
        "old_r40a_development_used_for_selection": False,
        "scientific_claim_allowed": False,
    }
    output_path.write_text(
        json.dumps(aggregate, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return aggregate


def aggregate_candidate(
    *,
    config_path: Path,
    roster_path: Path,
    candidate_name: str,
    scope: str,
) -> dict[str, Any]:
    config = read_json(config_path)
    if config.get("status") not in CONFIG_STATUSES:
        raise PermissionError("R40A.1 config is not frozen")
    candidate_spec(config, candidate_name)
    roster = read_json(roster_path)
    if (
        roster.get("status") not in ROSTER_STATUSES
        or roster.get("patient_sets_disjoint") is not True
        or roster.get("qualification_outcomes_read") is not False
        or roster.get("revealed_483_test_read") is not False
        or roster.get("gold_outcomes_read") is not False
    ):
        raise PermissionError("R40A.1 roster firewall drift")
    if scope not in {"discovery", "qualification"}:
        raise ValueError("R40A.1 aggregate scope drift")
    seeds = [int(value) for value in config["probe"]["seeds"]]
    result_root = roster_path.parent / "probes" / candidate_name / scope
    results = [
        read_json(result_root / f"seed_{seed}" / "result.json")
        for seed in seeds
    ]
    for seed, result in zip(seeds, results, strict=True):
        if (
            result.get("status") != RESULT_STATUS
            or result.get("candidate") != candidate_name
            or result.get("scope") != scope
            or int(result.get("seed", -1)) != seed
            or result.get("progression_generation_unlocked") is not False
            or result.get("protected_300_dev_read") is not False
            or result.get("revealed_483_test_read") is not False
            or result.get("gold_outcomes_read") is not False
            or result.get("old_r40a_development_used_for_selection") is not False
        ):
            raise PermissionError("R40A.1 seed-result firewall drift")
    reference = results[0]
    for result in results[1:]:
        if any(
            result[key] != reference[key]
            for key in ("classes", "patient_ids", "example_ids", "targets")
        ):
            raise ValueError("R40A.1 seed-result alignment drift")
    comparisons: dict[str, Any] = defaultdict(dict)
    controls = {
        "current_only": "current_only",
        "query_only": "query_only",
        "prior_shuffle": "prior_shuffle",
    }
    replicates = int(config["probe"]["patient_bootstrap_replicates"])
    bootstrap_seed = int(config["probe"]["patient_bootstrap_seed"])
    for result in results:
        seed = str(result["seed"])
        for output_name, prediction_name in controls.items():
            comparisons[output_name][seed] = paired_patient_bootstrap(
                patient_ids=result["patient_ids"],
                targets=result["targets"],
                true_predictions=result["predictions"]["true_pair"],
                control_predictions=result["predictions"][prediction_name],
                class_count=len(result["classes"]),
                replicates=replicates,
                seed=bootstrap_seed,
            )
    gate = config[f"{scope}_gate"]
    minimum_pp = float(gate["all_three_seed_effects_at_least_pp"])
    required_controls = tuple(str(value) for value in gate["required_controls"])
    passed = all(
        comparisons[control][str(seed)]["effect_pp"] >= minimum_pp
        and comparisons[control][str(seed)]["ci95_lower_pp"] > 0.0
        for control in required_controls
        for seed in seeds
    )
    stage_tag = str(config.get("stage_tag", "R40A1"))
    status = (
        f"GO_PRTA_GEN_{stage_tag}_{scope.upper()}"
        if passed
        else f"STOP_PRTA_GEN_{stage_tag}_{scope.upper()}"
    )
    output_path = result_root / "aggregate.json"
    if output_path.exists():
        raise FileExistsError(
            f"R40A.1 aggregate output must be fresh: {output_path}"
        )
    aggregate = {
        "schema": "visualvit.prta-gen.r40a1-candidate-aggregate.v1",
        "status": status,
        "protocol_id": config["protocol_id"],
        "candidate": candidate_name,
        "scope": scope,
        "classes": reference["classes"],
        "seeds": seeds,
        "required_controls": required_controls,
        "minimum_effect_pp": minimum_pp,
        "comparisons": dict(comparisons),
        "gate_passed": passed,
        "candidate_selected": False,
        "qualification_unlocked": False,
        "progression_generation_unlocked": (
            scope == "qualification" and passed
        ),
        "laterality_generation_unlocked": False,
        "anatomy_generation_unlocked": False,
        "degree_generation_unlocked": False,
        "evidence_generation_unlocked": False,
        "protected_300_dev_read": False,
        "revealed_483_test_read": False,
        "gold_outcomes_read": False,
        "old_r40a_development_used_for_selection": False,
        "scientific_claim_allowed": False,
    }
    output_path.write_text(
        json.dumps(aggregate, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return aggregate


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Aggregate a frozen PRTA-Gen R40A.1 candidate"
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--roster", type=Path, required=True)
    parser.add_argument(
        "--candidate",
        choices=(
            "regional_moments_v1",
            "regional_cosine4_v1",
            "semantic_layout_means_v1",
            "semantic_layout_moments_v1",
        ),
        required=True,
    )
    parser.add_argument(
        "--scope", choices=("discovery", "qualification"), required=True
    )
    parser.add_argument("--early-stop", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    function = finalize_early_stop if args.early_stop else aggregate_candidate
    result = function(
        config_path=args.config,
        roster_path=args.roster,
        candidate_name=args.candidate,
        scope=args.scope,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["gate_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
