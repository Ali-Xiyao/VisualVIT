from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

from visualvit.cmcp import transition_examples
from visualvit.prta import PROGRESSION_LABELS


SCHEMA = "visualvit.r40.outcome-independent-roster.v1"
STATUS = "READY_R40_OUTCOME_INDEPENDENT_ROSTER"
RULESET_VERSION = "r37-report-transition-v4.1"


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


def roster_order(namespace: str, seed: int, patient_id: str) -> str:
    return hashlib.sha256(
        f"{namespace}|{seed}|{patient_id}".encode("utf-8")
    ).hexdigest()


def repartition(
    rows: Iterable[dict[str, Any]],
    *,
    development_patients: frozenset[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    training_rows = []
    development_rows = []
    for row in rows:
        patient_id = str(row["patient_id"])
        if patient_id in development_patients:
            development_rows.append(
                {**row, "partition": "internal_calibration"}
            )
        else:
            training_rows.append({**row, "partition": "pretrain"})
    return training_rows, development_rows


def build_roster(
    *,
    config_path: Path,
    output_root: Path | None = None,
) -> dict[str, Any]:
    config = read_json(config_path)
    if config.get("status") != "FROZEN_R40_OUTCOME_INDEPENDENT_PROTOCOL":
        raise PermissionError("R40 protocol is not frozen")
    roster_config = config["roster"]
    source_root = Path(roster_config["source_root"])
    target_root = (
        Path(roster_config["output_root"])
        if output_root is None
        else Path(output_root)
    )
    if target_root.exists():
        raise FileExistsError(f"R40 roster output must be fresh: {target_root}")

    source_audit = read_json(source_root / "r37_transition_audit.json")
    required_source = {
        "status": roster_config["source_status"],
        "ruleset_version": RULESET_VERSION,
        "patient_disjoint": True,
        "old_calibration_excluded": True,
        "one_shot_validation": True,
        "protected_outcomes_read": False,
        "sealed_test_read": False,
        "gold_outcomes_read": False,
        "source_hashes_recomputed": False,
        "per_shard_hashes_computed": False,
    }
    observed_source = {
        key: source_audit.get(key) for key in required_source
    }
    if observed_source != required_source:
        raise PermissionError(
            "R40 source roster/firewall drift: "
            f"expected {required_source}, got {observed_source}"
        )

    source_rows = read_jsonl(source_root / "r37_pretrain_manifest.jsonl")
    source_examples = transition_examples(source_rows)
    patient_ids = sorted(
        {str(item["patient_id"]) for item in source_examples}
    )
    expected_patients = int(roster_config["source_training_patients"])
    if len(patient_ids) != expected_patients:
        raise ValueError(
            "R40 source patient-count drift: "
            f"expected {expected_patients}, got {len(patient_ids)}"
        )
    development_count = int(roster_config["development_patients"])
    if not 0 < development_count < len(patient_ids):
        raise ValueError("invalid R40 development patient count")
    namespace = str(roster_config["selection_namespace"])
    split_seed = int(roster_config["selection_seed"])
    ordered = sorted(
        patient_ids,
        key=lambda patient_id: (
            roster_order(namespace, split_seed, patient_id),
            patient_id,
        ),
    )
    development_patients = frozenset(ordered[:development_count])
    training_patients = frozenset(ordered[development_count:])
    if training_patients & development_patients:
        raise AssertionError("R40 patient split overlaps")

    training_rows, development_rows = repartition(
        source_rows,
        development_patients=development_patients,
    )
    training_examples = transition_examples(training_rows)
    development_examples = transition_examples(development_rows)
    if {
        str(item["patient_id"]) for item in training_examples
    } & {
        str(item["patient_id"]) for item in development_examples
    }:
        raise AssertionError("R40 example partitions overlap by patient")

    training_counts = Counter(
        str(item["label"]) for item in training_examples
    )
    development_counts = Counter(
        str(item["label"]) for item in development_examples
    )
    minimum_train = int(roster_config["minimum_train_examples_per_label"])
    minimum_development = int(
        roster_config["minimum_development_examples_per_label"]
    )
    label_support_pass = all(
        training_counts[label] >= minimum_train
        and development_counts[label] >= minimum_development
        for label in PROGRESSION_LABELS
    )

    cmcp_payload = read_json(Path(config["shared_artifacts"]["cmcp_index"]))
    if cmcp_payload.get("status") != "PASS_R37A_CMCP_COVERAGE":
        raise PermissionError("frozen CMCP index is not qualified")
    cmcp_examples = {
        str(item["target_example_id"]) for item in cmcp_payload["matches"]
    }
    dynamic_examples = [
        item
        for item in (*training_examples, *development_examples)
        if str(item["label"]) != "Stable"
    ]
    cmcp_missing = sorted(
        str(item["example_id"])
        for item in dynamic_examples
        if str(item["example_id"]) not in cmcp_examples
    )
    cmcp_coverage_pass = not cmcp_missing

    target_root.mkdir(parents=True)
    write_jsonl(target_root / "r37_pretrain_manifest.jsonl", training_rows)
    write_jsonl(
        target_root / "r37_internal_calibration_manifest.jsonl",
        development_rows,
    )
    roster = {
        "schema": SCHEMA,
        "status": (
            STATUS
            if label_support_pass and cmcp_coverage_pass
            else "STOP_R40_ROSTER_SUPPORT"
        ),
        "protocol_id": config["protocol_id"],
        "selection_namespace": namespace,
        "selection_seed": split_seed,
        "selection_rule": roster_config["selection_rule"],
        "source_patients": len(patient_ids),
        "training_patients": len(training_patients),
        "development_patients": len(development_patients),
        "development_patient_ids": sorted(development_patients),
        "protected_300_dev_read": False,
        "revealed_483_test_read": False,
        "gold_outcomes_read": False,
        "source_hashes_recomputed": False,
        "per_shard_hashes_computed": False,
        "checkpoint_hashes_recomputed": False,
    }
    write_json(target_root / "r40_roster.json", roster)
    audit = {
        **roster,
        "ruleset_version": RULESET_VERSION,
        "formal_training_unlocked": bool(
            label_support_pass and cmcp_coverage_pass
        ),
        "source_partition": "R37.1 training only",
        "training_pair_rows": len(training_rows),
        "development_pair_rows": len(development_rows),
        "training_examples": len(training_examples),
        "development_examples": len(development_examples),
        "training_label_counts": dict(sorted(training_counts.items())),
        "development_label_counts": dict(
            sorted(development_counts.items())
        ),
        "minimum_train_examples_per_label": minimum_train,
        "minimum_development_examples_per_label": minimum_development,
        "label_support_pass": label_support_pass,
        "patient_disjoint": True,
        "previous_r37_1_validation_excluded": True,
        "one_shot_development": True,
        "cmcp_dynamic_examples": len(dynamic_examples),
        "cmcp_missing_examples": len(cmcp_missing),
        "cmcp_coverage_pass": cmcp_coverage_pass,
        "scientific_claim_allowed": False,
    }
    write_json(target_root / "r37_transition_audit.json", audit)
    return audit


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the frozen outcome-independent R40 roster"
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-root", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = build_roster(
        config_path=args.config,
        output_root=args.output_root,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == STATUS else 2


if __name__ == "__main__":
    raise SystemExit(main())
