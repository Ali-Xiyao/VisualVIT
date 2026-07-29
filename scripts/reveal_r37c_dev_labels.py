from __future__ import annotations

# ruff: noqa: E402

import argparse
from collections import Counter
import json
from pathlib import Path
import sys

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE))
sys.path.insert(0, str(WORKSPACE / "src"))

from scripts.r37c_common import (
    DEFAULT_CANDIDATE,
    load_candidate,
    read_json,
    validate_dev_structure,
    write_json,
)
from visualvit.prta import PROGRESSION_LABELS


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Perform the one-shot R37C 300-dev label reveal"
    )
    parser.add_argument("--candidate", type=Path, default=DEFAULT_CANDIDATE)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    candidate = load_candidate(args.candidate)
    one_shot = candidate["r37c_one_shot"]
    cache_root = Path(one_shot["structural_cache_root"])
    reveal_root = Path(one_shot["protected_reveal_root"])
    if reveal_root.exists():
        raise FileExistsError(
            f"one-shot reveal root must be fresh: {reveal_root}"
        )
    cache_manifest = read_json(cache_root / "cache_manifest.json")
    if (
        cache_manifest.get("status") != "PASS_R37_BLOCK8_FORMAL_CACHE"
        or cache_manifest.get("protected_outcomes_read") is not False
    ):
        raise PermissionError("R37C structural cache is not a firewall-clean PASS")
    structure = read_json(cache_root / "dev_structure.json")
    validate_dev_structure(structure, candidate)
    expected_ids = {str(item["record_id"]) for item in structure}

    mixed_rows = read_json(Path(one_shot["source"]))
    labels = [
        {
            "record_id": str(row["record_id"]),
            "progression": str(row["progression"]),
        }
        for row in mixed_rows
        if str(row.get("partition")) == str(one_shot["partition"])
    ]
    del mixed_rows
    observed_ids = {item["record_id"] for item in labels}
    if len(labels) != len(observed_ids) or observed_ids != expected_ids:
        raise ValueError("one-shot protected label alignment drift")
    if any(item["progression"] not in PROGRESSION_LABELS for item in labels):
        raise ValueError("R37C protected label vocabulary drift")
    labels.sort(key=lambda item: item["record_id"])

    reveal_root.mkdir(parents=True, exist_ok=False)
    write_json(reveal_root / "protected_dev_labels.json", labels)
    receipt = {
        "schema": "visualvit.r37c.one-shot-dev-reveal.v1",
        "status": "PASS_R37C_ONE_SHOT_DEV_REVEAL",
        "candidate_id": candidate["candidate_id"],
        "reveal_count": 1,
        "rows": len(labels),
        "patients": len({str(item["patient_id"]) for item in structure}),
        "label_support": dict(Counter(item["progression"] for item in labels)),
        "protected_outcomes_read": True,
        "sealed_483_test_read": False,
        "gold_outcomes_read": False,
        "source_hashes_recomputed": False,
        "per_shard_hashes_computed": False,
        "candidate_or_gate_changed_after_exposure": False,
        "protocol_deviation": candidate["protocol_deviation"],
    }
    write_json(reveal_root / "reveal_receipt.json", receipt)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
