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


def read_result(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("protected_outcomes_read") is not False:
        raise ValueError(f"protected outcome firewall failed: {path}")
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


def aggregate(
    payloads: list[dict[str, Any]],
    *,
    control: str,
    require_formal: bool,
) -> dict[str, Any]:
    if len(payloads) != 3:
        raise ValueError("R37 aggregation requires exactly three results")
    ordered = sorted(payloads, key=lambda item: int(item["seed"]))
    seeds = tuple(int(item["seed"]) for item in ordered)
    if seeds != FROZEN_SEEDS:
        raise ValueError(f"expected frozen seeds {FROZEN_SEEDS}, got {seeds}")
    variants = {str(item["variant"]) for item in ordered}
    if len(variants) != 1:
        raise ValueError(f"variant drift across seeds: {variants}")
    if require_formal and any(
        not item.get("formal")
        or not item.get("formal_training_unlocked", False)
        for item in ordered
    ):
        raise PermissionError("qualification requires formal human-QA-unlocked runs")

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
    return {
        "schema": "visualvit.r37.internal-qualification.v1",
        "status": (
            "PASS_R37_INTERNAL_CONTROL_GATE"
            if gate["passed"]
            else "STOP_R37_INTERNAL_CONTROL_GATE"
        ),
        "variant": variants.pop(),
        "control": control,
        "formal": require_formal,
        "seeds": list(seeds),
        "bootstrap": bootstrap,
        "gate": gate,
        "protected_outcomes_read": False,
        "source_hashes_recomputed": False,
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
        "--control", choices=("current_only", "cmcp"), default="current_only"
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--allow-engineering",
        action="store_true",
        help="diagnostic only; output remains non-formal",
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
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["status"].startswith("PASS_") else 2


if __name__ == "__main__":
    raise SystemExit(main())
