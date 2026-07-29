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

from scripts.r37c_common import (
    DEFAULT_CANDIDATE,
    FROZEN_SEEDS,
    load_candidate,
    read_json,
    write_json,
)
from visualvit.prta import PROGRESSION_LABELS
from visualvit.qualification import (
    patient_bootstrap_mean_seed_difference,
    three_seed_survival_gate,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Aggregate the one-shot R37C 300-dev gate"
    )
    parser.add_argument("--candidate", type=Path, default=DEFAULT_CANDIDATE)
    return parser.parse_args()


def validate_results(
    payloads: list[dict[str, Any]], candidate: dict[str, Any]
) -> list[dict[str, Any]]:
    ordered = sorted(payloads, key=lambda item: int(item["seed"]))
    if tuple(int(item["seed"]) for item in ordered) != FROZEN_SEEDS:
        raise ValueError("R37C aggregation seed roster drift")
    for item in ordered:
        if (
            item.get("schema")
            != "visualvit.r37c.one-shot-seed-evaluation.v1"
            or item.get("status")
            != "PASS_R37C_ONE_SHOT_SEED_EVALUATION"
            or item.get("candidate_id") != candidate["candidate_id"]
            or item.get("protected_outcomes_read") is not True
            or item.get("sealed_483_test_read") is not False
            or item.get("gold_outcomes_read") is not False
            or item.get("source_hashes_recomputed") is not False
            or item.get("per_shard_hashes_computed") is not False
            or item.get("checkpoint_hashes_recomputed") is not False
        ):
            raise PermissionError("R37C seed result firewall/status drift")
    reference = ordered[0]
    for item in ordered[1:]:
        if (
            item["record_ids"] != reference["record_ids"]
            or item["patient_ids"] != reference["patient_ids"]
            or item["target_labels"] != reference["target_labels"]
        ):
            raise ValueError("R37C row order/target drift across seeds")
    return ordered


def aggregate_payload(
    payloads: list[dict[str, Any]], candidate: dict[str, Any]
) -> dict[str, Any]:
    ordered = validate_results(payloads, candidate)
    one_shot = candidate["r37c_one_shot"]
    patient_ids = ordered[0]["patient_ids"]
    targets = ordered[0]["target_labels"]

    def comparison(control_key: str) -> dict[str, Any]:
        bootstrap = patient_bootstrap_mean_seed_difference(
            patient_ids=patient_ids,
            targets=targets,
            true_predictions_by_seed=[
                item["predictions"]["a6_true"] for item in ordered
            ],
            control_predictions_by_seed=[
                item["predictions"][control_key] for item in ordered
            ],
            class_count=len(PROGRESSION_LABELS),
            replicates=int(one_shot["bootstrap_replicates"]),
            seed=int(one_shot["bootstrap_seed"]),
        )
        gate = three_seed_survival_gate(
            bootstrap["observed_seed_differences_pp"],
            pooled_ci_lower_pp=float(bootstrap["ci95_lower_pp"]),
            minimum_gain_pp=float(one_shot["minimum_gain_pp"]),
        )
        return {"bootstrap": bootstrap, "gate": gate}

    current = comparison("a6_current_only")
    a0 = comparison("a0_true")
    inversion = [
        float(
            item["qualification_diagnostics"][
                "inversion_consistency_rate"
            ]
        )
        for item in ordered
    ]
    state = [
        float(
            item["qualification_diagnostics"][
                "state_retention_cosine_mean"
            ]
        )
        for item in ordered
    ]
    diagnostic = {
        "passed": (
            all(
                value >= float(one_shot["inversion_consistency_minimum"])
                for value in inversion
            )
            and all(
                value >= float(one_shot["state_retention_cosine_minimum"])
                for value in state
            )
        ),
        "inversion_consistency_by_seed": inversion,
        "inversion_consistency_minimum": one_shot[
            "inversion_consistency_minimum"
        ],
        "state_retention_cosine_by_seed": state,
        "state_retention_cosine_minimum": one_shot[
            "state_retention_cosine_minimum"
        ],
    }
    passed = (
        bool(current["gate"]["passed"])
        and bool(a0["gate"]["passed"])
        and bool(diagnostic["passed"])
    )
    return {
        "schema": "visualvit.r37c.one-shot-dev-qualification.v1",
        "status": (
            "GO_R37C_ONE_SHOT_DEV"
            if passed
            else "STOP_R37C_ONE_SHOT_DEV"
        ),
        "scientific_go": passed,
        "candidate_id": candidate["candidate_id"],
        "seeds": list(FROZEN_SEEDS),
        "patients": len(set(patient_ids)),
        "rows": len(patient_ids),
        "a6_vs_current_only": current,
        "a6_vs_a0": a0,
        "diagnostic_gate": diagnostic,
        "cmcp_role": one_shot["cmcp_role"],
        "protocol_deviation": candidate["protocol_deviation"],
        "protected_outcomes_read": True,
        "sealed_483_test_read": False,
        "gold_outcomes_read": False,
        "source_hashes_recomputed": False,
        "per_shard_hashes_computed": False,
        "checkpoint_hashes_recomputed": False,
        "r38_unlocked": passed,
        "r39_unlocked": False,
        "stop_chain": not passed,
    }


def main() -> int:
    args = parse_args()
    candidate = load_candidate(args.candidate)
    reveal_root = Path(candidate["r37c_one_shot"]["protected_reveal_root"])
    output = reveal_root / "qualification.json"
    if output.exists():
        raise FileExistsError(f"R37C qualification must be fresh: {output}")
    payload = aggregate_payload(
        [
            read_json(
                reveal_root
                / "evaluations"
                / f"seed_{seed}"
                / "result.json"
            )
            for seed in FROZEN_SEEDS
        ],
        candidate,
    )
    write_json(output, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["scientific_go"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
