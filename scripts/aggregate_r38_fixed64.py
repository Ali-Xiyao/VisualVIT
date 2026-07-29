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

from scripts.r38_common import (
    DEFAULT_R38_CONFIG,
    load_r38_config,
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
        description="Aggregate the frozen R38 fixed-64 survival gate"
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_R38_CONFIG)
    return parser.parse_args()


def aggregate_payload(
    results: list[dict[str, Any]],
    config: dict[str, Any],
    upstream: dict[str, Any],
) -> dict[str, Any]:
    ordered = sorted(results, key=lambda item: int(item["seed"]))
    if [int(item["seed"]) for item in ordered] != [17, 29, 43]:
        raise ValueError("R38 seed roster drift")
    if any(
        item.get("status") != "PASS_R38_FIXED64_SEED_SURVIVAL"
        or item.get("sealed_483_test_read") is not False
        or item.get("gold_outcomes_read") is not False
        or item.get("source_hashes_recomputed") is not False
        or item.get("per_shard_hashes_computed") is not False
        or item.get("checkpoint_hashes_recomputed") is not False
        or item["token_audit"].get("token_count") != 64
        or item["token_audit"].get("sample_level_routing") is not False
        or item["token_audit"].get("labels_or_probe_logits_in_tokens") is not False
        for item in ordered
    ):
        raise PermissionError("R38 seed result status/firewall drift")
    reference = ordered[0]
    for item in ordered[1:]:
        if (
            item["record_ids"] != reference["record_ids"]
            or item["patient_ids"] != reference["patient_ids"]
            or item["target_labels"] != reference["target_labels"]
        ):
            raise ValueError("R38 row order drift")
    reveal_root = Path(config["upstream_qualification"]).parent
    r37c_results = [
        read_json(
            reveal_root / "evaluations" / f"seed_{seed}" / "result.json"
        )
        for seed in (17, 29, 43)
    ]
    bootstrap = patient_bootstrap_mean_seed_difference(
        patient_ids=reference["patient_ids"],
        targets=reference["target_labels"],
        true_predictions_by_seed=[
            item["predictions"]["fixed64_true"] for item in ordered
        ],
        control_predictions_by_seed=[
            item["predictions"]["a0_true"] for item in r37c_results
        ],
        class_count=len(PROGRESSION_LABELS),
        replicates=int(config["gate"]["bootstrap_replicates"]),
        seed=int(config["gate"]["bootstrap_seed"]),
    )
    gate = three_seed_survival_gate(
        bootstrap["observed_seed_differences_pp"],
        pooled_ci_lower_pp=float(bootstrap["ci95_lower_pp"]),
        minimum_gain_pp=float(config["gate"]["minimum_gain_pp"]),
    )
    packed_effect = [
        float(item["metrics"]["fixed64_true_minus_current_pp"])
        for item in ordered
    ]
    uncompressed_effect = [
        float(item["metrics"]["uncompressed_true_minus_current_pp"])
        for item in ordered
    ]
    retention_by_seed = [
        packed / uncompressed
        for packed, uncompressed in zip(
            packed_effect, uncompressed_effect, strict=True
        )
    ]
    retention_mean = (
        sum(packed_effect) / sum(uncompressed_effect)
    )
    retention_gate = {
        "passed": (
            retention_mean
            >= float(
                config["gate"]["correct_prior_effect_retention_minimum"]
            )
            and all(value >= 0 for value in retention_by_seed)
        ),
        "retention_ratio": retention_mean,
        "retention_by_seed": retention_by_seed,
        "minimum": config["gate"][
            "correct_prior_effect_retention_minimum"
        ],
        "fixed64_effect_pp_by_seed": packed_effect,
        "uncompressed_effect_pp_by_seed": uncompressed_effect,
    }
    token_gate = {
        "passed": all(
            item["token_audit"]["token_layout_valid"]
            and item["token_audit"]["physical_attention_all_one"]
            and item["token_audit"]["reserved_tokens_shared_zero"]
            and item["token_audit"][
                "maximum_transition_embedding_absolute_difference"
            ]
            <= 1e-5
            for item in ordered
        ),
        "maximum_transition_embedding_absolute_difference_by_seed": [
            item["token_audit"][
                "maximum_transition_embedding_absolute_difference"
            ]
            for item in ordered
        ],
    }
    passed = bool(gate["passed"] and retention_gate["passed"] and token_gate["passed"])
    return {
        "schema": "visualvit.r38.fixed64-survival-qualification.v1",
        "status": (
            "GO_R38_FIXED64_SURVIVAL"
            if passed
            else "STOP_R38_FIXED64_SURVIVAL"
        ),
        "scientific_go": passed,
        "candidate_id": config["candidate_id"],
        "seeds": [17, 29, 43],
        "patients": len(set(reference["patient_ids"])),
        "rows": len(reference["patient_ids"]),
        "fixed64_vs_frozen_a0": {
            "bootstrap": bootstrap,
            "gate": gate,
        },
        "correct_prior_effect_retention": retention_gate,
        "token_audit_gate": token_gate,
        "upstream_r37c_status": upstream["status"],
        "protected_300_dev_read": True,
        "sealed_483_test_read": False,
        "gold_outcomes_read": False,
        "source_hashes_recomputed": False,
        "per_shard_hashes_computed": False,
        "checkpoint_hashes_recomputed": False,
        "r39_unlocked": passed,
        "stop_chain": not passed,
    }


def main() -> int:
    args = parse_args()
    config = load_r38_config(args.config)
    output_root = Path(config["output_root"])
    output = output_root / "qualification.json"
    if output.exists():
        raise FileExistsError(f"R38 qualification must be fresh: {output}")
    upstream = read_json(Path(config["upstream_qualification"]))
    payload = aggregate_payload(
        [
            read_json(output_root / f"seed_{seed}" / "result.json")
            for seed in (17, 29, 43)
        ],
        config,
        upstream,
    )
    write_json(output, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["scientific_go"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
