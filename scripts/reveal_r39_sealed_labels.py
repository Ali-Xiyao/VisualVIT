from __future__ import annotations

# ruff: noqa: E402

import argparse
from collections import Counter
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Perform the one-shot R39 sealed-label reveal"
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_R39_CONFIG)
    return parser.parse_args()


def validate_prediction_freeze(
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    payloads = [
        read_json(
            Path(config["runtime"]["root"])
            / "predictions"
            / f"seed_{seed}"
            / "result.json"
        )
        for seed in config["training"]["seeds"]
    ]
    reference = payloads[0]
    for payload, seed in zip(
        payloads, config["training"]["seeds"], strict=True
    ):
        projector = read_json(
            Path(config["runtime"]["projectors"])
            / f"seed_{seed}"
            / "result.json"
        )
        if (
            payload.get("status")
            != "PASS_R39_OUTCOME_BLIND_SEALED_PREDICTIONS"
            or int(payload.get("seed")) != int(seed)
            or payload.get("all_predictions_frozen_before_label_reveal")
            is not True
            or payload.get("sealed_483_test_labels_read") is not False
            or payload.get("gold_outcomes_read") is not False
            or projector.get("status")
            != "PASS_R39_PROJECTOR_TRAINING"
            or projector.get("sealed_483_test_labels_read") is not False
        ):
            raise PermissionError("R39 pre-reveal freeze receipt drift")
        if (
            payload["record_ids"] != reference["record_ids"]
            or payload["patient_ids"] != reference["patient_ids"]
        ):
            raise ValueError("R39 pre-reveal row order drift")
    return payloads


def main() -> int:
    args = parse_args()
    config = load_r39_config(args.config)
    predictions = validate_prediction_freeze(config)
    reveal_root = Path(config["sealed_test"]["label_reveal_root"])
    if reveal_root.exists():
        raise FileExistsError(
            f"R39 one-shot reveal root must be fresh: {reveal_root}"
        )
    labels = read_json(Path(config["sealed_test"]["protected_labels"]))
    expected_ids = set(predictions[0]["record_ids"])
    observed_ids = [str(row["record_id"]) for row in labels]
    if (
        len(labels) != int(config["sealed_test"]["expected_rows"])
        or len(observed_ids) != len(set(observed_ids))
        or set(observed_ids) != expected_ids
        or len({str(row["patient_id"]) for row in labels})
        != int(config["sealed_test"]["expected_patients"])
        or any(str(row["progression"]) not in TARGET_TO_VLM for row in labels)
    ):
        raise ValueError("R39 protected sealed-label roster drift")
    by_record = {str(row["record_id"]): row for row in labels}
    aligned = [
        {
            "record_id": record_id,
            "patient_id": str(by_record[record_id]["patient_id"]),
            "progression": str(by_record[record_id]["progression"]),
        }
        for record_id in predictions[0]["record_ids"]
    ]
    if [row["patient_id"] for row in aligned] != predictions[0]["patient_ids"]:
        raise ValueError("R39 protected patient alignment drift")
    reveal_root.mkdir(parents=True, exist_ok=False)
    write_json(reveal_root / "protected_sealed_labels.json", aligned)
    receipt = {
        "schema": "visualvit.r39.one-shot-sealed-reveal.v1",
        "status": "PASS_R39_ONE_SHOT_SEALED_REVEAL",
        "candidate_id": config["candidate_id"],
        "reveal_count": 1,
        "rows": len(aligned),
        "patients": len({row["patient_id"] for row in aligned}),
        "label_support": dict(
            Counter(row["progression"] for row in aligned)
        ),
        "all_three_projectors_frozen_before_reveal": True,
        "all_three_prediction_sets_frozen_before_reveal": True,
        "sealed_483_test_labels_read": True,
        "gold_outcomes_read": False,
        "source_hashes_recomputed": False,
        "per_shard_hashes_computed": False,
        "checkpoint_hashes_recomputed": False,
        "candidate_or_gate_changed_after_exposure": False,
    }
    write_json(reveal_root / "reveal_receipt.json", receipt)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
