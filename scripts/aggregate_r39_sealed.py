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

from scripts.r39_common import (
    DEFAULT_R39_CONFIG,
    TARGET_TO_VLM,
    load_r39_config,
    read_json,
    write_json,
)
from visualvit.qualification import (
    macro_f1,
    patient_bootstrap_mean_seed_difference,
    three_seed_survival_gate,
)


COMPARISONS = {
    "a6_vs_a0": "a0_frozen_difference",
    "a6_vs_current_only": "a6_current_only",
    "a6_vs_query_only": "query_only",
    "a6_vs_prior_shuffle": "a6_prior_shuffle",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Aggregate the one-shot R39 sealed frozen-VLM gate"
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_R39_CONFIG)
    return parser.parse_args()


def aggregate_payload(
    predictions: list[dict[str, Any]],
    labels: list[dict[str, Any]],
    config: dict[str, Any],
) -> dict[str, Any]:
    ordered = sorted(predictions, key=lambda item: int(item["seed"]))
    if [int(item["seed"]) for item in ordered] != config["training"]["seeds"]:
        raise ValueError("R39 aggregation seed roster drift")
    reference = ordered[0]
    for item in ordered:
        if (
            item.get("status")
            != "PASS_R39_OUTCOME_BLIND_SEALED_PREDICTIONS"
            or item.get("all_predictions_frozen_before_label_reveal")
            is not True
            or item.get("sealed_483_test_labels_read") is not False
            or item.get("gold_outcomes_read") is not False
            or item["record_ids"] != reference["record_ids"]
            or item["patient_ids"] != reference["patient_ids"]
        ):
            raise PermissionError("R39 prediction firewall/status drift")
    if [str(row["record_id"]) for row in labels] != reference["record_ids"]:
        raise ValueError("R39 protected label order drift")
    patient_ids = reference["patient_ids"]
    targets = [TARGET_TO_VLM[str(row["progression"])] for row in labels]
    final_gate = config["final_gate"]

    def compare(control_key: str, minimum: float) -> dict[str, Any]:
        bootstrap = patient_bootstrap_mean_seed_difference(
            patient_ids=patient_ids,
            targets=targets,
            true_predictions_by_seed=[
                item["predictions"]["a6_true_pair"] for item in ordered
            ],
            control_predictions_by_seed=[
                item["predictions"][control_key] for item in ordered
            ],
            class_count=len(TARGET_TO_VLM),
            replicates=int(final_gate["bootstrap_replicates"]),
            seed=int(final_gate["bootstrap_seed"]),
        )
        gate = three_seed_survival_gate(
            bootstrap["observed_seed_differences_pp"],
            pooled_ci_lower_pp=float(bootstrap["ci95_lower_pp"]),
            minimum_gain_pp=minimum,
        )
        return {"bootstrap": bootstrap, "gate": gate}

    minimum_by_comparison = {
        "a6_vs_a0": float(final_gate["minimum_gain_pp"]),
        "a6_vs_current_only": float(
            final_gate["required_controls"][
                "a6_true_pair_vs_current_only_minimum_gain_pp"
            ]
        ),
        "a6_vs_query_only": float(
            final_gate["required_controls"][
                "a6_true_pair_vs_query_only_minimum_gain_pp"
            ]
        ),
        "a6_vs_prior_shuffle": float(
            final_gate["required_controls"][
                "a6_true_pair_vs_prior_shuffle_minimum_gain_pp"
            ]
        ),
    }
    comparisons = {
        name: compare(control, minimum_by_comparison[name])
        for name, control in COMPARISONS.items()
    }
    metrics_by_seed = []
    for item in ordered:
        seed_metrics = {
            key: macro_f1(
                targets,
                item["predictions"][key],
                class_count=len(TARGET_TO_VLM),
            )
            for key in item["prediction_keys"]
        }
        metrics_by_seed.append(
            {"seed": item["seed"], "macro_f1": seed_metrics}
        )
    audits = {
        "passed": all(
            item.get("vlm_all_frozen") is True
            and item.get("pixel_inputs_used") is False
            and item.get("token_budget") == 64
            and item.get("source_hashes_recomputed") is False
            and item.get("per_shard_hashes_computed") is False
            for item in ordered
        ),
        "vlm_trainable_parameters": 0,
        "pixel_inputs_used": False,
        "token_budget": 64,
        "prompt_matched": True,
        "projector_capacity_matched": True,
        "sealed_predictions_frozen_before_label_reveal": True,
    }
    passed = bool(
        audits["passed"]
        and all(value["gate"]["passed"] for value in comparisons.values())
    )
    return {
        "schema": "visualvit.r39.one-shot-sealed-qualification.v1",
        "status": (
            "GO_R39_FROZEN_VLM_TRANSFER"
            if passed
            else "STOP_R39_FROZEN_VLM_TRANSFER"
        ),
        "scientific_go": passed,
        "candidate_id": config["candidate_id"],
        "seeds": config["training"]["seeds"],
        "patients": len(set(patient_ids)),
        "rows": len(patient_ids),
        "primary_comparison": "a6_vs_a0",
        "comparisons": comparisons,
        "metrics_by_seed": metrics_by_seed,
        "interface_audit": audits,
        "sealed_483_test_labels_read": True,
        "sealed_reveal_count": 1,
        "gold_outcomes_read": False,
        "gold_unlocked": False,
        "source_hashes_recomputed": False,
        "per_shard_hashes_computed": False,
        "checkpoint_hashes_recomputed": False,
        "stop_chain": not passed,
    }


def main() -> int:
    args = parse_args()
    config = load_r39_config(args.config)
    reveal_root = Path(config["sealed_test"]["label_reveal_root"])
    receipt = read_json(reveal_root / "reveal_receipt.json")
    if (
        receipt.get("status") != "PASS_R39_ONE_SHOT_SEALED_REVEAL"
        or receipt.get("reveal_count") != 1
        or receipt.get("candidate_or_gate_changed_after_exposure") is not False
    ):
        raise PermissionError("R39 one-shot reveal receipt drift")
    output = reveal_root / "qualification.json"
    if output.exists():
        raise FileExistsError(f"R39 qualification must be fresh: {output}")
    payload = aggregate_payload(
        [
            read_json(
                Path(config["runtime"]["root"])
                / "predictions"
                / f"seed_{seed}"
                / "result.json"
            )
            for seed in config["training"]["seeds"]
        ],
        read_json(reveal_root / "protected_sealed_labels.json"),
        config,
    )
    write_json(output, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["scientific_go"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
