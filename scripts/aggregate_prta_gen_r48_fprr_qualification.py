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


def aggregate(config_path: Path) -> dict[str, Any]:
    config = read_json(config_path)
    root = Path(config["runtime"]["discovery_root"])
    output = root / "aggregate.json"
    if output.exists():
        raise FileExistsError("R48 qualification aggregate must be fresh")
    baseline = read_json(root / "baseline" / "result.json")
    if (
        baseline.get("status") != config["result_statuses"]["baseline_complete"]
        or baseline.get("qwen_trainable_parameters") != 0
        or baseline.get("projector_trainable_parameters") != 0
        or baseline.get("cache_equivalence_audit", {}).get("passed") is not True
    ):
        raise PermissionError("R48 baseline receipt drift")
    metrics = baseline["metrics"]
    patient_ids = baseline["development_patient_ids"]
    targets = baseline["targets"]
    replicates = int(
        config["evaluation"]["patient_cluster_bootstrap_replicates"]
    )
    seed = int(config["evaluation"]["patient_cluster_bootstrap_seed"])
    comparisons = {}
    for offset, arm in enumerate(("prior_shuffle", "current_only")):
        comparisons[f"true_vs_{arm}"] = (
            paired_patient_bootstrap_with_invalid(
                patient_ids=patient_ids,
                targets=targets,
                primary_predictions=baseline["predictions"]["true_pair"],
                control_predictions=baseline["predictions"][arm],
                class_count=len(config["target"]["progression_values"]),
                replicates=replicates,
                seed=seed + offset,
            )
        )
    gate = config["qualification_gate"]
    failures = []
    checks = (
        (
            "true_macro_f1",
            float(metrics["true_pair"]["macro_f1"]),
            float(gate["true_macro_f1_at_least"]),
            "at_least",
        ),
        (
            "true_minus_prior_shuffle",
            float(comparisons["true_vs_prior_shuffle"]["effect_pp"]),
            float(gate["true_minus_prior_shuffle_at_least_pp"]),
            "at_least",
        ),
        (
            "true_minus_prior_shuffle_ci95_lower",
            float(comparisons["true_vs_prior_shuffle"]["ci95_lower_pp"]),
            float(gate["true_minus_prior_shuffle_ci95_lower_above_pp"]),
            "above",
        ),
        (
            "true_minus_current_only",
            float(comparisons["true_vs_current_only"]["effect_pp"]),
            float(gate["true_minus_current_only_at_least_pp"]),
            "at_least",
        ),
        (
            "true_minus_current_only_ci95_lower",
            float(comparisons["true_vs_current_only"]["ci95_lower_pp"]),
            float(gate["true_minus_current_only_ci95_lower_above_pp"]),
            "above",
        ),
        (
            "true_minus_query_only",
            100.0
            * (
                float(metrics["true_pair"]["macro_f1"])
                - float(metrics["query_only"]["macro_f1"])
            ),
            float(gate["true_minus_query_only_at_least_pp"]),
            "at_least",
        ),
    )
    for name, observed, required, direction in checks:
        failed = (
            observed < required
            if direction == "at_least"
            else observed <= required
        )
        if failed:
            failures.append(
                {
                    "gate": name,
                    "observed": observed,
                    f"required_{direction}": required,
                }
            )
    floor = float(gate["all_class_recall_at_least"])
    for label, observed in metrics["true_pair"]["per_class_recall"].items():
        if float(observed) < floor:
            failures.append(
                {
                    "gate": "true_per_class_recall",
                    "class": label,
                    "observed": float(observed),
                    "required_at_least": floor,
                }
            )
    passed = not failures
    result = {
        "schema": "visualvit.prta-gen.r48-fprr-qualification-aggregate.v1",
        "status": (
            config["result_statuses"]["qualification_go"]
            if passed
            else config["result_statuses"]["qualification_stop"]
        ),
        "protocol_id": config["protocol_id"],
        "metrics": metrics,
        "comparisons": comparisons,
        "gate_passed": passed,
        "gate_failure_count": len(failures),
        "gate_failures": failures,
        "confirmation_unlocked": passed,
        "confirmation_tokens_materialized": False,
        "confirmation_outcomes_read": False,
        "gold_outcomes_read": False,
        "external_outcomes_read": False,
        "scientific_claim_allowed": False,
    }
    write_json(output, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Aggregate R48 qualification")
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    result = aggregate(args.config)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
