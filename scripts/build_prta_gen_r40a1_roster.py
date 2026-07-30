from __future__ import annotations

# ruff: noqa: E402

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE))
sys.path.insert(0, str(WORKSPACE / "src"))

from scripts.cache_prta_gen_r40a_tokens import read_json, read_jsonl


CONFIG_STATUS = "FROZEN_PRTA_GEN_R40A1_CASE_DRIVEN_REPAIR"
ROSTER_PASS = "PASS_PRTA_GEN_R40A1_ROSTER_SUPPORT"
ROSTER_STOP = "STOP_PRTA_GEN_R40A1_ROSTER_SUPPORT"
PROGRESSION_CLASSES = ("Stable", "Improved", "Worse", "New", "Resolved")


def patient_order(patient_ids: set[str], *, namespace: str) -> list[str]:
    return sorted(
        patient_ids,
        key=lambda patient_id: (
            hashlib.sha256(
                f"{namespace}|{patient_id}".encode()
            ).hexdigest(),
            patient_id,
        ),
    )


def build_roster(config_path: Path) -> dict[str, Any]:
    config = read_json(config_path)
    if config.get("status") != CONFIG_STATUS:
        raise PermissionError("R40A.1 case-repair config is not frozen")
    predecessor = read_json(Path(config["closed_predecessor"]["aggregate"]))
    if (
        predecessor.get("status") != "STOP_PRTA_GEN_R40A_FIELD_INFORMATION"
        or predecessor.get("field") != "progression"
        or predecessor.get("field_generation_unlocked") is not False
        or predecessor.get("revealed_483_test_read") is not False
        or predecessor.get("gold_outcomes_read") is not False
    ):
        raise PermissionError("closed R40A predecessor drift")
    case_study = read_json(Path(config["case_study"]["path"]))
    if (
        case_study.get("status")
        != "DESCRIPTIVE_PRTA_GEN_R40A_FAILURE_CASE_STUDY"
        or case_study.get("observed_development_reuse_for_selection_allowed")
        is not False
        or case_study.get("closed_r40a_result_unchanged") is not True
    ):
        raise PermissionError("R40A case-study boundary drift")
    token_index = read_json(Path(config["source"]["token_index"]))
    if (
        token_index.get("status") != "PASS_PRTA_GEN_R40A_TOKEN_CACHE"
        or token_index.get("scope") != "training"
        or token_index.get("smoke_rows") != 0
        or token_index.get("labels_in_cache") is not False
        or token_index.get("sentences_in_cache") is not False
        or token_index.get("protected_300_dev_read") is not False
        or token_index.get("revealed_483_test_read") is not False
        or token_index.get("gold_outcomes_read") is not False
    ):
        raise PermissionError("R40A.1 source token-cache drift")
    rows = read_jsonl(Path(config["source"]["target_rows"]))
    expected_rows = int(config["source"]["expected_rows"])
    expected_patients = int(config["source"]["expected_patients"])
    patients = {str(row["patient_id"]) for row in rows}
    if (
        len(rows) != expected_rows
        or len(patients) != expected_patients
        or int(token_index.get("rows", -1)) != expected_rows
        or int(token_index.get("patients", -1)) != expected_patients
    ):
        raise ValueError("R40A.1 source count drift")
    unknown = {
        str(row["progression"]) for row in rows
    } - set(PROGRESSION_CLASSES)
    if unknown:
        raise ValueError(f"unknown progression targets: {sorted(unknown)}")

    split = config["patient_partitions"]
    ordered = patient_order(patients, namespace=str(split["namespace"]))
    qualification_count = int(split["qualification_patients"])
    discovery_count = int(split["discovery_patients"])
    fit_count = int(split["fit_patients"])
    if qualification_count + discovery_count + fit_count != len(ordered):
        raise ValueError("R40A.1 patient split counts do not cover source")
    partition_patients = {
        "qualification": ordered[:qualification_count],
        "discovery": ordered[
            qualification_count : qualification_count + discovery_count
        ],
        "fit": ordered[qualification_count + discovery_count :],
    }
    patient_to_partition = {
        patient_id: partition
        for partition, ids in partition_patients.items()
        for patient_id in ids
    }
    partition_support: dict[str, Counter[str]] = {
        partition: Counter() for partition in partition_patients
    }
    partition_rows = Counter()
    for row in rows:
        partition = patient_to_partition[str(row["patient_id"])]
        partition_rows[partition] += 1
        partition_support[partition][str(row["progression"])] += 1
    minimums = split["support_minimums"]
    minimum_by_partition = {
        "fit": int(minimums["fit_rows_per_progression_class"]),
        "discovery": int(
            minimums["discovery_rows_per_progression_class"]
        ),
        "qualification": int(
            minimums["qualification_rows_per_progression_class"]
        ),
    }
    failed_support = {
        partition: {
            label: count
            for label in PROGRESSION_CLASSES
            if (count := partition_support[partition][label])
            < minimum_by_partition[partition]
        }
        for partition in partition_patients
    }
    failed_support = {
        partition: counts
        for partition, counts in failed_support.items()
        if counts
    }
    status = ROSTER_STOP if failed_support else ROSTER_PASS
    return {
        "schema": "visualvit.prta-gen.r40a1-roster.v1",
        "status": status,
        "protocol_id": config["protocol_id"],
        "namespace": split["namespace"],
        "assignment": split["assignment"],
        "partitions": {
            partition: {
                "patients": len(ids),
                "rows": int(partition_rows[partition]),
                "patient_ids": ids,
                "progression_support": {
                    label: partition_support[partition][label]
                    for label in PROGRESSION_CLASSES
                },
            }
            for partition, ids in partition_patients.items()
        },
        "failed_support": failed_support,
        "patient_sets_disjoint": (
            len(set().union(*(set(ids) for ids in partition_patients.values())))
            == sum(len(ids) for ids in partition_patients.values())
        ),
        "resplit_allowed": False,
        "discovery_outcomes_read": False,
        "qualification_outcomes_read": False,
        "protected_300_dev_read": False,
        "revealed_483_test_read": False,
        "gold_outcomes_read": False,
        "old_r40a_development_used_for_selection": False,
        "source_hashes_recomputed": False,
        "per_shard_hashes_recomputed": False,
        "checkpoint_hashes_recomputed": False,
        "old_r40_component_queue_resumed": False,
        "scientific_claim_allowed": False,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the frozen PRTA-Gen R40A.1 patient roster"
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.output.exists():
        raise FileExistsError(
            f"R40A.1 roster output must be fresh: {args.output}"
        )
    payload = build_roster(args.config)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(args.output)
    print(
        json.dumps(
            {
                "status": payload["status"],
                "partitions": {
                    key: {
                        "patients": value["patients"],
                        "rows": value["rows"],
                        "progression_support": value[
                            "progression_support"
                        ],
                    }
                    for key, value in payload["partitions"].items()
                },
                "failed_support": payload["failed_support"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if payload["status"] == ROSTER_PASS else 2


if __name__ == "__main__":
    raise SystemExit(main())
