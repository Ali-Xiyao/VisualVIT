from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import random
from typing import Any, Iterable

from visualvit.cmcp import transition_examples


SCHEMA = "visualvit.r37-1.fresh-holdout.v1"
STATUS = "READY_R37_1_FRESH_HOLDOUT"
RULESET_VERSION = "r37-report-transition-v4.1"
SPLIT_SEED = 37_101
SOURCE_ELIGIBLE_PATIENTS = 12_102
VALIDATION_PATIENTS = 1_815


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(
                json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n"
            )


def repartition_row(
    row: dict[str, Any],
    *,
    partition: str,
) -> dict[str, Any]:
    return {**row, "partition": partition}


def build_holdout(
    *,
    source_root: Path,
    output_root: Path,
) -> dict[str, Any]:
    if output_root.exists():
        raise FileExistsError(f"R37.1 output root must be fresh: {output_root}")
    source_audit = read_json(source_root / "r37_transition_audit.json")
    if source_audit.get("ruleset_version") != RULESET_VERSION:
        raise ValueError("source transition ruleset drift")
    if any(
        source_audit.get(key) is not False
        for key in (
            "protected_outcomes_read",
            "chextemporal_silver_used",
        )
    ):
        raise PermissionError("source transition firewall drift")

    source_rows = read_jsonl(source_root / "r37_pretrain_manifest.jsonl")
    old_calibration_rows = read_jsonl(
        source_root / "r37_internal_calibration_manifest.jsonl"
    )
    source_examples = transition_examples(source_rows)
    eligible_patients = sorted(
        {str(item["patient_id"]) for item in source_examples}
    )
    if len(eligible_patients) != SOURCE_ELIGIBLE_PATIENTS:
        raise ValueError(
            "eligible source-patient count drift: "
            f"expected {SOURCE_ELIGIBLE_PATIENTS}, "
            f"got {len(eligible_patients)}"
        )

    shuffled = list(eligible_patients)
    random.Random(SPLIT_SEED).shuffle(shuffled)
    validation_patients = frozenset(shuffled[:VALIDATION_PATIENTS])
    training_patients = frozenset(shuffled[VALIDATION_PATIENTS:])
    if validation_patients & training_patients:
        raise AssertionError("R37.1 patient split overlaps")

    old_calibration_patients = {
        str(row["patient_id"]) for row in old_calibration_rows
    }
    if old_calibration_patients & (
        validation_patients | training_patients
    ):
        raise ValueError("old R37 calibration overlaps old pretraining source")

    training_rows = [
        repartition_row(row, partition="pretrain")
        for row in source_rows
        if str(row["patient_id"]) not in validation_patients
    ]
    validation_rows = [
        repartition_row(row, partition="internal_calibration")
        for row in source_rows
        if str(row["patient_id"]) in validation_patients
    ]
    training_examples = transition_examples(training_rows)
    validation_examples = transition_examples(validation_rows)
    if {
        str(item["patient_id"]) for item in training_examples
    } & {
        str(item["patient_id"]) for item in validation_examples
    }:
        raise AssertionError("R37.1 transition examples overlap by patient")

    output_root.mkdir(parents=True)
    write_jsonl(output_root / "r37_pretrain_manifest.jsonl", training_rows)
    write_jsonl(
        output_root / "r37_internal_calibration_manifest.jsonl",
        validation_rows,
    )
    roster = {
        "schema": SCHEMA,
        "status": STATUS,
        "split_seed": SPLIT_SEED,
        "selection": (
            "sort eligible old-pretrain patient IDs, shuffle once with "
            "Python random.Random(37101), hold out first 1815"
        ),
        "source_eligible_patients": len(eligible_patients),
        "training_patients": len(training_patients),
        "validation_patients": len(validation_patients),
        "old_calibration_patients_excluded": len(old_calibration_patients),
        "validation_patient_ids": sorted(validation_patients),
        "protected_outcomes_read": False,
        "sealed_test_read": False,
        "gold_outcomes_read": False,
        "source_hashes_recomputed": False,
        "per_shard_hashes_computed": False,
    }
    write_json(output_root / "r37_1_fresh_holdout_roster.json", roster)

    training_counts = Counter(
        str(item["label"]) for item in training_examples
    )
    validation_counts = Counter(
        str(item["label"]) for item in validation_examples
    )
    audit = {
        "schema": SCHEMA,
        "status": STATUS,
        "ruleset_version": RULESET_VERSION,
        "formal_training_unlocked": True,
        "source_partition": "R37 pretrain only",
        "split_seed": SPLIT_SEED,
        "source_pair_rows": len(source_rows),
        "training_pair_rows": len(training_rows),
        "validation_pair_rows": len(validation_rows),
        "source_eligible_patients": len(eligible_patients),
        "training_patients": len(training_patients),
        "validation_patients": len(validation_patients),
        "old_calibration_patients_excluded": len(old_calibration_patients),
        "training_examples": len(training_examples),
        "validation_examples": len(validation_examples),
        "training_label_counts": dict(sorted(training_counts.items())),
        "validation_label_counts": dict(sorted(validation_counts.items())),
        "patient_disjoint": True,
        "old_calibration_excluded": True,
        "one_shot_validation": True,
        "protected_outcomes_read": False,
        "sealed_test_read": False,
        "gold_outcomes_read": False,
        "source_hashes_recomputed": False,
        "per_shard_hashes_computed": False,
        "scientific_claim_allowed": False,
    }
    write_json(output_root / "r37_transition_audit.json", audit)
    return audit


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the frozen fresh-patient R37.1 holdout"
    )
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = build_holdout(
        source_root=args.source_root,
        output_root=args.output_root,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
