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

from scripts.aggregate_r37_internal_qualification import (
    formal_diagnostic_gate,
    normalized_predictions,
    read_result,
)
from visualvit.prta import PROGRESSION_LABELS
from visualvit.qualification import (
    PATIENT_BOOTSTRAP_REPLICATES,
    PATIENT_BOOTSTRAP_SEED,
    patient_bootstrap_mean_seed_difference,
)


TWO_SEEDS = (17, 29)
MINIMUM_GAIN_PP = 2.0


def validate_two_seed_results(
    payloads: list[dict[str, Any]],
    *,
    variant: str,
    schema: str,
    status: str,
) -> list[dict[str, Any]]:
    ordered = sorted(payloads, key=lambda item: int(item["seed"]))
    seeds = tuple(int(item["seed"]) for item in ordered)
    if seeds != TWO_SEEDS:
        raise ValueError(f"expected two-screen seeds {TWO_SEEDS}, got {seeds}")
    if any(
        item.get("variant") != variant
        or item.get("schema") != schema
        or item.get("status") != status
        or item.get("formal") is not True
        or item.get("r37_1") is not True
        or item.get("formal_training_unlocked") is not True
        or item.get("scientific_claim_allowed") is not False
        or item.get("protected_outcomes_read") is not False
        or item.get("sealed_test_read") is not False
        or item.get("gold_outcomes_read") is not False
        or item.get("source_hashes_recomputed") is not False
        for item in ordered
    ):
        raise PermissionError(
            f"two-seed screen requires firewall-clean formal {variant} results"
        )
    return ordered


def two_seed_screen_gate(bootstrap: dict[str, Any]) -> dict[str, Any]:
    differences = [
        float(value)
        for value in bootstrap["observed_seed_differences_pp"]
    ]
    if len(differences) != len(TWO_SEEDS):
        raise ValueError("two-seed gate requires exactly two differences")
    all_at_least_minimum = all(
        value >= MINIMUM_GAIN_PP for value in differences
    )
    ci_lower = float(bootstrap["ci95_lower_pp"])
    return {
        "passed": all_at_least_minimum and ci_lower > 0.0,
        "minimum_gain_pp_per_seed": MINIMUM_GAIN_PP,
        "all_two_seeds_at_least_minimum": all_at_least_minimum,
        "pooled_patient_bootstrap_ci95_lower_pp": ci_lower,
        "pooled_ci_lower_above_zero": ci_lower > 0.0,
        "seed_differences_pp": differences,
    }


def bootstrap_comparison(
    *,
    true_rows: list[dict[str, Any]],
    control_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    patient_ids = true_rows[0]["patient_ids"]
    targets = true_rows[0]["targets"]
    for item in [*true_rows[1:], *control_rows]:
        if item["patient_ids"] != patient_ids or item["targets"] != targets:
            raise ValueError("two-seed comparison row order drift")
    bootstrap = patient_bootstrap_mean_seed_difference(
        patient_ids=patient_ids,
        targets=targets,
        true_predictions_by_seed=[item["true"] for item in true_rows],
        control_predictions_by_seed=[
            item["control"] for item in control_rows
        ],
        class_count=len(PROGRESSION_LABELS),
        replicates=PATIENT_BOOTSTRAP_REPLICATES,
        seed=PATIENT_BOOTSTRAP_SEED,
        expected_seed_count=len(TWO_SEEDS),
    )
    return {
        "bootstrap": bootstrap,
        "gate": two_seed_screen_gate(bootstrap),
    }


def aggregate_two_seed_screen(
    a6_payloads: list[dict[str, Any]],
    a0_payloads: list[dict[str, Any]],
) -> dict[str, Any]:
    a6_ordered = validate_two_seed_results(
        a6_payloads,
        variant="A6",
        schema="visualvit.r37-1.prta-formal-training.v1",
        status="PASS_R37_1_PRTA_FORMAL_TRAINING",
    )
    a0_ordered = validate_two_seed_results(
        a0_payloads,
        variant="A0",
        schema="visualvit.r37-1.a0-formal-probe.v1",
        status="PASS_R37_1_A0_FORMAL_PROBE",
    )

    current_rows = [
        normalized_predictions(item, control="current_only")
        for item in a6_ordered
    ]
    cmcp_rows = [
        normalized_predictions(item, control="cmcp")
        for item in a6_ordered
    ]
    a0_rows = [
        normalized_predictions(item, control="current_only")
        for item in a0_ordered
    ]
    comparisons = {
        "a6_vs_current_only": bootstrap_comparison(
            true_rows=current_rows,
            control_rows=current_rows,
        ),
        "a6_vs_cmcp": bootstrap_comparison(
            true_rows=cmcp_rows,
            control_rows=cmcp_rows,
        ),
        "a6_vs_a0": bootstrap_comparison(
            true_rows=current_rows,
            control_rows=[
                {
                    "patient_ids": item["patient_ids"],
                    "targets": item["targets"],
                    "true": item["true"],
                    "control": item["true"],
                }
                for item in a0_rows
            ],
        ),
    }
    diagnostic_gate = formal_diagnostic_gate(a6_ordered)
    passed = diagnostic_gate["passed"] and all(
        comparison["gate"]["passed"]
        for comparison in comparisons.values()
    )
    return {
        "schema": "visualvit.r37-1.two-seed-internal-screen.v1",
        "status": (
            "PASS_R37_1_TWO_SEED_INTERNAL_SCREEN"
            if passed
            else "STOP_R37_1_TWO_SEED_INTERNAL_SCREEN"
        ),
        "variant": "A6",
        "controls": ["current_only", "cmcp", "A0"],
        "formal_inputs": True,
        "r37_1": True,
        "seeds": list(TWO_SEEDS),
        "bootstrap_replicates": PATIENT_BOOTSTRAP_REPLICATES,
        "bootstrap_seed": PATIENT_BOOTSTRAP_SEED,
        "comparisons": comparisons,
        "diagnostic_gate": diagnostic_gate,
        "three_seed_gate_evaluated": False,
        "seed_43_deferred_by_user": True,
        "descriptive_internal_screen_only": True,
        "protected_outcomes_read": False,
        "sealed_test_read": False,
        "gold_outcomes_read": False,
        "source_hashes_recomputed": False,
        "scientific_claim_allowed": False,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the reduced R37.1 two-seed internal bootstrap screen"
    )
    parser.add_argument(
        "--a6-result",
        type=Path,
        action="append",
        required=True,
        help="repeat for R37.1 A6 seeds 17 and 29",
    )
    parser.add_argument(
        "--a0-result",
        type=Path,
        action="append",
        required=True,
        help="repeat for R37.1 A0 seeds 17 and 29",
    )
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.output.exists():
        raise FileExistsError(f"output must be fresh: {args.output}")
    payload = aggregate_two_seed_screen(
        [read_result(path) for path in args.a6_result],
        [read_result(path) for path in args.a0_result],
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    temporary.replace(args.output)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["status"].startswith("PASS_") else 2


if __name__ == "__main__":
    raise SystemExit(main())
