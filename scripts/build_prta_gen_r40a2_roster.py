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

from scripts.build_prta_gen_r40a1_roster import (
    PROGRESSION_CLASSES,
    ROSTER_PASS,
    patient_order,
)
from scripts.cache_prta_gen_r40a_tokens import read_json, read_jsonl


CONFIG_STATUS = "FROZEN_PRTA_GEN_R40A2_LAYOUT_REPAIR"
ROSTER_PASS_V2 = "PASS_PRTA_GEN_R40A2_ROSTER_SUPPORT"
ROSTER_STOP_V2 = "STOP_PRTA_GEN_R40A2_ROSTER_SUPPORT"


def build_roster(config_path: Path) -> dict[str, Any]:
    config = read_json(config_path)
    if config.get("status") != CONFIG_STATUS:
        raise PermissionError("R40A.2 layout-repair config is not frozen")
    selection = read_json(Path(config["closed_predecessor"]["selection"]))
    if (
        selection.get("status")
        != config["closed_predecessor"]["required_status"]
        or selection.get("selected_candidate") is not None
        or selection.get("qualification_unlocked") is not False
        or selection.get("qualification_outcomes_read") is not False
        or selection.get("revealed_483_test_read") is not False
        or selection.get("gold_outcomes_read") is not False
    ):
        raise PermissionError("R40A.1 terminal selection drift")
    split = config["patient_partitions"]
    parent = read_json(Path(split["parent_roster"]))
    if (
        parent.get("status") != ROSTER_PASS
        or parent.get("patient_sets_disjoint") is not True
        or parent.get("qualification_outcomes_read") is not False
        or parent.get("revealed_483_test_read") is not False
        or parent.get("gold_outcomes_read") is not False
    ):
        raise PermissionError("R40A.1 parent roster drift")
    qualification = [
        str(value)
        for value in parent["partitions"]["qualification"]["patient_ids"]
    ]
    excluded_discovery = [
        str(value)
        for value in parent["partitions"]["discovery"]["patient_ids"]
    ]
    parent_fit = {
        str(value) for value in parent["partitions"]["fit"]["patient_ids"]
    }
    ordered_fit = patient_order(
        parent_fit, namespace=str(split["namespace"])
    )
    discovery_count = int(split["discovery_patients"])
    fit_count = int(split["fit_patients"])
    if discovery_count + fit_count != len(ordered_fit):
        raise ValueError("R40A.2 fit/discovery counts do not cover parent fit")
    partition_patients = {
        "qualification": qualification,
        "discovery": ordered_fit[:discovery_count],
        "fit": ordered_fit[discovery_count:],
    }
    if len(qualification) != int(
        split["preserve_parent_qualification_patients"]
    ):
        raise ValueError("R40A.2 qualification count drift")
    if len(excluded_discovery) != int(
        split["exclude_observed_parent_discovery_patients"]
    ):
        raise ValueError("R40A.2 excluded discovery count drift")
    included_sets = [set(value) for value in partition_patients.values()]
    if any(
        included_sets[left] & included_sets[right]
        for left in range(len(included_sets))
        for right in range(left + 1, len(included_sets))
    ):
        raise PermissionError("R40A.2 patient partitions overlap")
    if set(excluded_discovery) & set().union(*included_sets):
        raise PermissionError("observed R40A.1 discovery leaked into R40A.2")

    rows = read_jsonl(Path(config["source"]["target_rows"]))
    if len(rows) != int(config["source"]["expected_rows"]):
        raise ValueError("R40A.2 source row-count drift")
    patient_to_partition = {
        patient_id: partition
        for partition, ids in partition_patients.items()
        for patient_id in ids
    }
    excluded_set = set(excluded_discovery)
    partition_rows = Counter()
    excluded_rows = 0
    support = {
        partition: Counter() for partition in partition_patients
    }
    for row in rows:
        patient_id = str(row["patient_id"])
        if patient_id in excluded_set:
            excluded_rows += 1
            continue
        if patient_id not in patient_to_partition:
            raise ValueError("R40A.2 source patient absent from parent roster")
        partition = patient_to_partition[patient_id]
        label = str(row["progression"])
        if label not in PROGRESSION_CLASSES:
            raise ValueError("R40A.2 progression registry drift")
        partition_rows[partition] += 1
        support[partition][label] += 1
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
            label: support[partition][label]
            for label in PROGRESSION_CLASSES
            if support[partition][label] < minimum_by_partition[partition]
        }
        for partition in partition_patients
    }
    failed_support = {
        key: value for key, value in failed_support.items() if value
    }
    status = ROSTER_STOP_V2 if failed_support else ROSTER_PASS_V2
    return {
        "schema": "visualvit.prta-gen.r40a2-roster.v1",
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
                    label: support[partition][label]
                    for label in PROGRESSION_CLASSES
                },
            }
            for partition, ids in partition_patients.items()
        },
        "excluded_parent_discovery": {
            "patients": len(excluded_discovery),
            "rows": excluded_rows,
            "patient_ids": excluded_discovery,
        },
        "failed_support": failed_support,
        "patient_sets_disjoint": True,
        "qualification_matches_parent": (
            qualification
            == parent["partitions"]["qualification"]["patient_ids"]
        ),
        "parent_discovery_excluded": True,
        "resplit_allowed": False,
        "discovery_outcomes_read": False,
        "qualification_outcomes_read": False,
        "protected_300_dev_read": False,
        "revealed_483_test_read": False,
        "gold_outcomes_read": False,
        "r40a_development_used_for_selection": False,
        "r40a1_discovery_used_for_selection": False,
        "source_hashes_recomputed": False,
        "per_shard_hashes_recomputed": False,
        "checkpoint_hashes_recomputed": False,
        "scientific_claim_allowed": False,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the frozen PRTA-Gen R40A.2 patient roster"
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.output.exists():
        raise FileExistsError(
            f"R40A.2 roster output must be fresh: {args.output}"
        )
    result = build_roster(args.config)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "partitions": {
                    key: {
                        "patients": value["patients"],
                        "rows": value["rows"],
                        "progression_support": value[
                            "progression_support"
                        ],
                    }
                    for key, value in result["partitions"].items()
                },
                "excluded_parent_discovery": {
                    "patients": result["excluded_parent_discovery"][
                        "patients"
                    ],
                    "rows": result["excluded_parent_discovery"]["rows"],
                },
                "failed_support": result["failed_support"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if result["status"] == ROSTER_PASS_V2 else 2


if __name__ == "__main__":
    raise SystemExit(main())
