from __future__ import annotations

# ruff: noqa: E402

import argparse
import json
from pathlib import Path
import sys
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE / "src"))

from visualvit.prta import PROGRESSION_LABELS
from visualvit.qualification import (
    PATIENT_BOOTSTRAP_REPLICATES,
    PATIENT_BOOTSTRAP_SEED,
    patient_bootstrap_mean_seed_difference,
    three_seed_survival_gate,
)


FROZEN_SEEDS = (17, 29, 43)
INVERSION_CONSISTENCY_MINIMUM = 0.90
STATE_RETENTION_COSINE_MINIMUM = 0.99


def read_result(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("protected_outcomes_read") is not False:
        raise ValueError(f"protected outcome firewall failed: {path}")
    if payload.get("sealed_test_read") is not False:
        raise ValueError(f"sealed-test firewall failed: {path}")
    if payload.get("gold_outcomes_read") is not False:
        raise ValueError(f"gold-outcome firewall failed: {path}")
    return payload


def normalized_predictions(
    payload: dict[str, Any], *, control: str
) -> dict[str, Any]:
    if "calibration" in payload:
        calibration = payload["calibration"]
        if control == "current_only":
            return {
                "patient_ids": calibration["patient_ids"],
                "targets": calibration["target_labels"],
                "true": calibration["true_pair_predictions"],
                "control": calibration["current_only_predictions"],
            }
        if control == "cmcp":
            cmcp = calibration["cmcp"]
            return {
                "patient_ids": cmcp["patient_ids"],
                "targets": cmcp["target_labels"],
                "true": cmcp["true_pair_predictions"],
                "control": cmcp["control_predictions"],
            }
    if control != "current_only":
        raise ValueError(f"{payload.get('variant')} has no {control} control")
    return {
        "patient_ids": payload["calibration_patient_ids"],
        "targets": payload["target_labels"],
        "true": payload["predictions"]["true_pair"],
        "control": payload["predictions"]["current_only"],
    }


def validate_formal_results(
    payloads: list[dict[str, Any]],
    *,
    variant: str,
    schema: str,
    status: str,
    r37_1: bool = False,
) -> list[dict[str, Any]]:
    ordered = sorted(payloads, key=lambda item: int(item["seed"]))
    seeds = tuple(int(item["seed"]) for item in ordered)
    if seeds != FROZEN_SEEDS:
        raise ValueError(f"expected frozen seeds {FROZEN_SEEDS}, got {seeds}")
    if any(
        item.get("variant") != variant
        or item.get("schema") != schema
        or item.get("status") != status
        or not item.get("formal")
        or not item.get("formal_training_unlocked", False)
        or item.get("scientific_claim_allowed") is not False
        or item.get("protected_outcomes_read") is not False
        or item.get("sealed_test_read") is not False
        or item.get("gold_outcomes_read") is not False
        or item.get("source_hashes_recomputed") is not False
        or bool(item.get("r37_1", False)) is not r37_1
        for item in ordered
    ):
        raise PermissionError(
            f"qualification requires firewall-clean formal {variant} results"
        )
    return ordered


def formal_diagnostic_gate(
    ordered: list[dict[str, Any]],
) -> dict[str, Any]:
    inversion = [
        float(
            item["calibration"]["qualification_diagnostics"][
                "inversion_consistency_rate"
            ]
        )
        for item in ordered
    ]
    state_retention = [
        float(
            item["calibration"]["qualification_diagnostics"][
                "state_retention_cosine_mean"
            ]
        )
        for item in ordered
    ]
    return {
        "passed": (
            all(value >= INVERSION_CONSISTENCY_MINIMUM for value in inversion)
            and all(
                value >= STATE_RETENTION_COSINE_MINIMUM
                for value in state_retention
            )
        ),
        "inversion_consistency_by_seed": inversion,
        "inversion_consistency_minimum": INVERSION_CONSISTENCY_MINIMUM,
        "state_retention_cosine_by_seed": state_retention,
        "state_retention_cosine_minimum": STATE_RETENTION_COSINE_MINIMUM,
    }


def aggregate_a6_vs_a0(
    a6_payloads: list[dict[str, Any]],
    a0_payloads: list[dict[str, Any]],
    *,
    r37_1: bool = False,
) -> dict[str, Any]:
    if len(a6_payloads) != 3 or len(a0_payloads) != 3:
        raise ValueError("R37 A6/A0 aggregation requires three results each")
    a6_ordered = validate_formal_results(
        a6_payloads,
        variant="A6",
        schema=(
            "visualvit.r37-1.prta-formal-training.v1"
            if r37_1
            else "visualvit.r37.prta-formal-training.v1"
        ),
        status=(
            "PASS_R37_1_PRTA_FORMAL_TRAINING"
            if r37_1
            else "PASS_R37_PRTA_FORMAL_TRAINING"
        ),
        r37_1=r37_1,
    )
    a0_ordered = validate_formal_results(
        a0_payloads,
        variant="A0",
        schema=(
            "visualvit.r37-1.a0-formal-probe.v1"
            if r37_1
            else "visualvit.r37.a0-formal-probe.v1"
        ),
        status=(
            "PASS_R37_1_A0_FORMAL_PROBE"
            if r37_1
            else "PASS_R37_A0_FORMAL_PROBE"
        ),
        r37_1=r37_1,
    )
    a6_rows = [
        normalized_predictions(item, control="current_only")
        for item in a6_ordered
    ]
    a0_rows = [
        normalized_predictions(item, control="current_only")
        for item in a0_ordered
    ]
    patient_ids = a6_rows[0]["patient_ids"]
    targets = a6_rows[0]["targets"]
    for item in [*a6_rows[1:], *a0_rows]:
        if item["patient_ids"] != patient_ids or item["targets"] != targets:
            raise ValueError("A6/A0 calibration row order drift")
    bootstrap = patient_bootstrap_mean_seed_difference(
        patient_ids=patient_ids,
        targets=targets,
        true_predictions_by_seed=[item["true"] for item in a6_rows],
        control_predictions_by_seed=[item["true"] for item in a0_rows],
        class_count=len(PROGRESSION_LABELS),
        replicates=PATIENT_BOOTSTRAP_REPLICATES,
        seed=PATIENT_BOOTSTRAP_SEED,
    )
    gate = three_seed_survival_gate(
        bootstrap["observed_seed_differences_pp"],
        pooled_ci_lower_pp=float(bootstrap["ci95_lower_pp"]),
    )
    return {
        "schema": (
            "visualvit.r37-1.a6-vs-a0-qualification.v1"
            if r37_1
            else "visualvit.r37.a6-vs-a0-qualification.v1"
        ),
        "status": (
            (
                "PASS_R37_1_INTERNAL_A6_VS_A0_GATE"
                if r37_1
                else "PASS_R37_INTERNAL_A6_VS_A0_GATE"
            )
            if gate["passed"]
            else (
                "STOP_R37_1_INTERNAL_A6_VS_A0_GATE"
                if r37_1
                else "STOP_R37_INTERNAL_A6_VS_A0_GATE"
            )
        ),
        "r37_1": r37_1,
        "variant": "A6",
        "control": "A0",
        "formal": True,
        "seeds": list(FROZEN_SEEDS),
        "bootstrap": bootstrap,
        "gate": gate,
        "protected_outcomes_read": False,
        "sealed_test_read": False,
        "gold_outcomes_read": False,
        "source_hashes_recomputed": False,
        "scientific_claim_allowed": False,
    }


def aggregate(
    payloads: list[dict[str, Any]],
    *,
    control: str,
    require_formal: bool,
    baseline_payloads: list[dict[str, Any]] | None = None,
    r37_1: bool = False,
) -> dict[str, Any]:
    if control == "a0":
        if not require_formal:
            raise ValueError("A6 versus A0 is a formal-only gate")
        if baseline_payloads is None:
            raise ValueError("A6 versus A0 requires baseline results")
        return aggregate_a6_vs_a0(
            payloads, baseline_payloads, r37_1=r37_1
        )
    if len(payloads) != 3:
        raise ValueError("R37 aggregation requires exactly three results")
    ordered = sorted(payloads, key=lambda item: int(item["seed"]))
    seeds = tuple(int(item["seed"]) for item in ordered)
    if seeds != FROZEN_SEEDS:
        raise ValueError(f"expected frozen seeds {FROZEN_SEEDS}, got {seeds}")
    variants = {str(item["variant"]) for item in ordered}
    if len(variants) != 1:
        raise ValueError(f"variant drift across seeds: {variants}")
    if require_formal:
        ordered = validate_formal_results(
            ordered,
            variant="A6",
            schema=(
                "visualvit.r37-1.prta-formal-training.v1"
                if r37_1
                else "visualvit.r37.prta-formal-training.v1"
            ),
            status=(
                "PASS_R37_1_PRTA_FORMAL_TRAINING"
                if r37_1
                else "PASS_R37_PRTA_FORMAL_TRAINING"
            ),
            r37_1=r37_1,
        )

    normalized = [
        normalized_predictions(item, control=control) for item in ordered
    ]
    patient_ids = normalized[0]["patient_ids"]
    targets = normalized[0]["targets"]
    for item in normalized[1:]:
        if item["patient_ids"] != patient_ids or item["targets"] != targets:
            raise ValueError("calibration row order drift across seeds")
    bootstrap = patient_bootstrap_mean_seed_difference(
        patient_ids=patient_ids,
        targets=targets,
        true_predictions_by_seed=[item["true"] for item in normalized],
        control_predictions_by_seed=[
            item["control"] for item in normalized
        ],
        class_count=len(PROGRESSION_LABELS),
        replicates=PATIENT_BOOTSTRAP_REPLICATES,
        seed=PATIENT_BOOTSTRAP_SEED,
    )
    gate = three_seed_survival_gate(
        bootstrap["observed_seed_differences_pp"],
        pooled_ci_lower_pp=float(bootstrap["ci95_lower_pp"]),
    )
    diagnostic_gate = (
        formal_diagnostic_gate(ordered) if require_formal else None
    )
    passed = gate["passed"] and (
        diagnostic_gate is None or diagnostic_gate["passed"]
    )
    return {
        "schema": (
            "visualvit.r37-1.internal-qualification.v1"
            if r37_1
            else "visualvit.r37.internal-qualification.v1"
        ),
        "status": (
            (
                "PASS_R37_1_INTERNAL_CONTROL_GATE"
                if r37_1
                else "PASS_R37_INTERNAL_CONTROL_GATE"
            )
            if passed
            else (
                "STOP_R37_1_INTERNAL_CONTROL_GATE"
                if r37_1
                else "STOP_R37_INTERNAL_CONTROL_GATE"
            )
        ),
        "r37_1": r37_1,
        "variant": variants.pop(),
        "control": control,
        "formal": require_formal,
        "seeds": list(seeds),
        "bootstrap": bootstrap,
        "gate": gate,
        "diagnostic_gate": diagnostic_gate,
        "protected_outcomes_read": False,
        "sealed_test_read": False,
        "gold_outcomes_read": False,
        "source_hashes_recomputed": False,
        "scientific_claim_allowed": False,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Aggregate the frozen three-seed R37 internal control gate"
    )
    parser.add_argument(
        "--result",
        type=Path,
        action="append",
        required=True,
        help="repeat exactly three times for seeds 17, 29, and 43",
    )
    parser.add_argument(
        "--control",
        choices=("current_only", "cmcp", "a0"),
        default="current_only",
    )
    parser.add_argument(
        "--baseline-result",
        type=Path,
        action="append",
        help="repeat three times for formal A0 when --control a0",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--allow-engineering",
        action="store_true",
        help="diagnostic only; output remains non-formal",
    )
    parser.add_argument(
        "--r37-1",
        action="store_true",
        help="require R37.1 fresh-holdout schemas and statuses",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.output.exists():
        raise FileExistsError(f"output must be fresh: {args.output}")
    payload = aggregate(
        [read_result(path) for path in args.result],
        control=args.control,
        require_formal=not args.allow_engineering,
        baseline_payloads=(
            [read_result(path) for path in args.baseline_result]
            if args.baseline_result
            else None
        ),
        r37_1=args.r37_1,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["status"].startswith("PASS_") else 2


if __name__ == "__main__":
    raise SystemExit(main())
