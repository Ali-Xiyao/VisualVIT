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
from scripts.analyze_prta_gen_r46_cea_failure_cases import (
    consensus_prediction,
)
from scripts.build_prta_gen_r40b_smoke_cohort import read_json, write_json
from scripts.run_prta_gen_r45_cdeb_discovery import (
    _metrics as classification_metrics,
)


CONFIG_STATUS = "FROZEN_PRTA_GEN_R47_UCC_DISCOVERY"
SEEDS = (17, 29, 43)


def aggregate(config_path: Path) -> dict[str, Any]:
    config = read_json(config_path)
    if config.get("status") != CONFIG_STATUS:
        raise PermissionError("R47 config is not frozen")
    root = Path(config["runtime"]["discovery_root"])
    output_path = root / "aggregate.json"
    if output_path.exists():
        raise FileExistsError("R47 aggregate must be fresh")
    baseline = read_json(root / "baseline" / "result.json")
    seed_results = {
        seed: read_json(root / f"seed_{seed}" / "result.json")
        for seed in SEEDS
    }
    if (
        baseline.get("status") != config["result_statuses"]["baseline_complete"]
        or baseline.get("protocol_id") != config["protocol_id"]
        or baseline.get("qwen_trainable_parameters") != 0
        or baseline.get("projector_trainable_parameters") != 0
        or baseline.get("cache_equivalence_audit", {}).get("passed") is not True
    ):
        raise PermissionError("R47 baseline receipt drift")
    for seed, result in seed_results.items():
        if (
            result.get("status") != config["result_statuses"]["seed_complete"]
            or result.get("protocol_id") != config["protocol_id"]
            or result.get("seed") != seed
            or result.get("targets") != baseline["targets"]
            or result.get("development_example_ids")
            != baseline["development_example_ids"]
            or result.get("training_audit", {}).get("updates")
            != config["training"]["expected_updates_per_seed"]
            or result.get("qwen_loaded") is not False
        ):
            raise PermissionError(f"R47 Seed receipt drift: {seed}")
    roster = read_json(Path(config["authority"]["roster"]))
    rows = list(roster["partitions"]["development"]["rows"])
    targets = [int(value) for value in baseline["targets"]]
    if len(rows) != len(targets) or len(rows) != 500:
        raise ValueError("R47 roster/result count drift")
    true_predictions = []
    shuffle_predictions = []
    true_overrides = []
    shuffle_overrides = []
    true_heads = {
        seed: seed_results[seed]["structured_predictions"]["true_pair"]
        for seed in SEEDS
    }
    current_heads = {
        seed: seed_results[seed]["structured_predictions"]["current_only"]
        for seed in SEEDS
    }
    shuffle_heads = {
        seed: seed_results[seed]["structured_predictions"]["prior_shuffle"]
        for seed in SEEDS
    }
    for index in range(len(rows)):
        true_value, true_override = consensus_prediction(
            baseline=int(baseline["predictions"]["true_pair"][index]),
            true_predictions=[
                int(true_heads[seed][index]) for seed in SEEDS
            ],
            current_predictions=[
                int(current_heads[seed][index]) for seed in SEEDS
            ],
            minimum_true_votes=int(config["ucc"]["minimum_true_seed_votes"]),
            minimum_causal_votes=int(
                config["ucc"]["minimum_current_only_disagreement_votes"]
            ),
        )
        shuffle_value, shuffle_override = consensus_prediction(
            baseline=int(baseline["predictions"]["prior_shuffle"][index]),
            true_predictions=[
                int(shuffle_heads[seed][index]) for seed in SEEDS
            ],
            current_predictions=[
                int(current_heads[seed][index]) for seed in SEEDS
            ],
            minimum_true_votes=int(config["ucc"]["minimum_true_seed_votes"]),
            minimum_causal_votes=int(
                config["ucc"]["minimum_current_only_disagreement_votes"]
            ),
        )
        true_predictions.append(true_value)
        shuffle_predictions.append(shuffle_value)
        true_overrides.append(true_override)
        shuffle_overrides.append(shuffle_override)
    true_metrics = classification_metrics(rows, true_predictions)
    shuffle_metrics = classification_metrics(rows, shuffle_predictions)
    baseline_true = [
        int(value) for value in baseline["predictions"]["true_pair"]
    ]
    recovered = sum(
        override and base != target and prediction == target
        for target, base, prediction, override in zip(
            targets,
            baseline_true,
            true_predictions,
            true_overrides,
            strict=True,
        )
    )
    regressed = sum(
        override and base == target and prediction != target
        for target, base, prediction, override in zip(
            targets,
            baseline_true,
            true_predictions,
            true_overrides,
            strict=True,
        )
    )
    replicates = int(
        config["evaluation"]["patient_cluster_bootstrap_replicates"]
    )
    bootstrap_seed = int(
        config["evaluation"]["patient_cluster_bootstrap_seed"]
    )
    comparisons = {
        "ucc_true_vs_baseline": paired_patient_bootstrap_with_invalid(
            patient_ids=baseline["development_patient_ids"],
            targets=targets,
            primary_predictions=true_predictions,
            control_predictions=baseline_true,
            class_count=len(config["target"]["progression_values"]),
            replicates=replicates,
            seed=bootstrap_seed,
        ),
        "ucc_true_vs_prior_shuffle": paired_patient_bootstrap_with_invalid(
            patient_ids=baseline["development_patient_ids"],
            targets=targets,
            primary_predictions=true_predictions,
            control_predictions=shuffle_predictions,
            class_count=len(config["target"]["progression_values"]),
            replicates=replicates,
            seed=bootstrap_seed + 1,
        ),
    }
    gate = config["discovery_gate"]
    override_rate = sum(true_overrides) / len(true_overrides)
    net_recovery = recovered - regressed
    failures: list[dict[str, Any]] = []
    scalar_checks = (
        (
            "ucc_true_macro_f1",
            float(true_metrics["macro_f1"]),
            float(gate["ucc_true_macro_f1_at_least"]),
            "at_least",
        ),
        (
            "ucc_minus_baseline",
            float(comparisons["ucc_true_vs_baseline"]["effect_pp"]),
            float(gate["ucc_minus_baseline_macro_f1_at_least_pp"]),
            "at_least",
        ),
        (
            "ucc_minus_baseline_ci95_lower",
            float(comparisons["ucc_true_vs_baseline"]["ci95_lower_pp"]),
            float(gate["ucc_minus_baseline_ci95_lower_above_pp"]),
            "above",
        ),
        (
            "ucc_true_minus_prior_shuffle",
            float(comparisons["ucc_true_vs_prior_shuffle"]["effect_pp"]),
            float(gate["ucc_true_minus_prior_shuffle_at_least_pp"]),
            "at_least",
        ),
        (
            "ucc_true_minus_prior_shuffle_ci95_lower",
            float(comparisons["ucc_true_vs_prior_shuffle"]["ci95_lower_pp"]),
            float(gate["ucc_true_minus_prior_shuffle_ci95_lower_above_pp"]),
            "above",
        ),
        (
            "override_rate_minimum",
            override_rate,
            float(gate["override_rate_at_least"]),
            "at_least",
        ),
        (
            "override_rate_maximum",
            override_rate,
            float(gate["override_rate_at_most"]),
            "at_most",
        ),
        (
            "net_recovery",
            float(net_recovery),
            float(gate["net_recovery_at_least"]),
            "at_least",
        ),
    )
    for name, observed, required, direction in scalar_checks:
        failed = {
            "at_least": observed < required,
            "at_most": observed > required,
            "above": observed <= required,
        }[direction]
        if failed:
            failures.append(
                {
                    "gate": name,
                    "observed": observed,
                    f"required_{direction}": required,
                }
            )
    recall_floor = float(gate["ucc_all_class_recall_at_least"])
    for label, observed in true_metrics["per_class_recall"].items():
        if float(observed) < recall_floor:
            failures.append(
                {
                    "gate": "ucc_per_class_recall",
                    "class": label,
                    "observed": float(observed),
                    "required_at_least": recall_floor,
                }
            )
    passed = not failures
    result = {
        "schema": "visualvit.prta-gen.r47-ucc-discovery-aggregate.v1",
        "status": (
            config["result_statuses"]["aggregate_go"]
            if passed
            else config["result_statuses"]["aggregate_stop"]
        ),
        "protocol_id": config["protocol_id"],
        "study_tier": config["study_tier"],
        "seeds": list(SEEDS),
        "development_patients": len(rows),
        "baseline_metrics": baseline["metrics"],
        "structured_metrics": {
            str(seed): seed_results[seed]["structured_metrics"]
            for seed in SEEDS
        },
        "ucc_true_metrics": true_metrics,
        "ucc_prior_shuffle_metrics": shuffle_metrics,
        "true_override_count": sum(true_overrides),
        "true_override_rate": override_rate,
        "shuffle_override_count": sum(shuffle_overrides),
        "shuffle_override_rate": sum(shuffle_overrides) / len(shuffle_overrides),
        "recovered_count": recovered,
        "regressed_count": regressed,
        "net_recovery": net_recovery,
        "low_evidence_baseline_agreement": 1.0,
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
        "gold_outcomes_read": False,
        "external_outcomes_read": False,
        "scientific_claim_allowed": False,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(output_path, result)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Aggregate frozen R47 UCC discovery"
    )
    parser.add_argument("--config", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = aggregate(args.config)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
