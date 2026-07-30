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

from scripts.build_prta_gen_r40b_smoke_cohort import (
    read_json,
    read_targets,
    write_json,
)
from visualvit.prta_gen import PROGRESSION_CLASSES


CONFIG_STATUS = "FROZEN_PRTA_GEN_R40C_STRUCTURED_GENERALIZATION"
ROSTER_STATUS = "PASS_PRTA_GEN_R40C_ROSTER_SUPPORT"


def stable_key(namespace: str, value: str) -> str:
    return hashlib.sha256(f"{namespace}|{value}".encode()).hexdigest()


def _false_firewalls(value: dict[str, Any]) -> bool:
    return all(
        value.get(key) is False
        for key in (
            "protected_300_dev_read",
            "revealed_483_test_read",
            "gold_outcomes_read",
        )
    )


def validate_authority(config: dict[str, Any]) -> dict[str, Any]:
    if config.get("status") != CONFIG_STATUS:
        raise PermissionError("R40C config is not frozen")
    predecessor_spec = config["closed_predecessor"]
    predecessor = read_json(Path(predecessor_spec["result"]))
    if (
        predecessor.get("status") != predecessor_spec["required_status"]
        or predecessor.get("qwen_free_generation_unlocked") is not False
        or predecessor.get("scientific_claim_allowed") is not False
        or not _false_firewalls(predecessor)
    ):
        raise PermissionError("R40C predecessor receipt drift")
    upstream_spec = config["upstream"]
    upstream = read_json(Path(upstream_spec["qualification_aggregate"]))
    if (
        upstream.get("status") != upstream_spec["required_status"]
        or upstream.get("candidate") != upstream_spec["required_candidate"]
        or upstream.get("progression_generation_unlocked") is not True
        or upstream.get("laterality_generation_unlocked") is not False
        or upstream.get("anatomy_generation_unlocked") is not False
        or upstream.get("degree_generation_unlocked") is not False
        or upstream.get("evidence_generation_unlocked") is not False
        or not _false_firewalls(upstream)
    ):
        raise PermissionError("R40C qualification receipt drift")
    source = config["source"]
    parent_roster = read_json(Path(source["roster"]))
    if (
        parent_roster.get("status") != source["required_roster_status"]
        or parent_roster.get("patient_sets_disjoint") is not True
        or not _false_firewalls(parent_roster)
    ):
        raise PermissionError("R40C parent roster drift")
    token_index = read_json(Path(source["token_index"]))
    if (
        token_index.get("status") != source["required_token_status"]
        or token_index.get("scope") != "training"
        or token_index.get("labels_in_cache") is not False
        or token_index.get("sentences_in_cache") is not False
        or not _false_firewalls(token_index)
    ):
        raise PermissionError("R40C token-cache firewall drift")
    excluded_patients: set[str] = set()
    cohort_receipts = []
    for spec in source["exclude_cohorts"]:
        cohort = read_json(Path(spec["path"]))
        if (
            cohort.get("status") != spec["required_status"]
            or cohort.get("row_count") != 32
            or cohort.get("patient_count") != 32
            or cohort.get("scientific_claim_allowed") is not False
            or not _false_firewalls(cohort)
        ):
            raise PermissionError("R40C excluded-cohort receipt drift")
        cohort_patients = {str(row["patient_id"]) for row in cohort["rows"]}
        if len(cohort_patients) != 32 or excluded_patients & cohort_patients:
            raise PermissionError("R40C excluded cohorts overlap")
        excluded_patients.update(cohort_patients)
        cohort_receipts.append(
            {
                "status": cohort["status"],
                "patients": len(cohort_patients),
            }
        )
    expected_excluded = int(source["expected_excluded_patient_count"])
    if len(excluded_patients) != expected_excluded:
        raise ValueError("R40C excluded-patient count drift")
    fit_patients = {
        str(value)
        for value in parent_roster["partitions"][source["partition"]][
            "patient_ids"
        ]
    }
    if excluded_patients - fit_patients:
        raise PermissionError("R40C excluded cohort escaped fit partition")
    return {
        "fit_patients": fit_patients,
        "excluded_patients": excluded_patients,
        "parent_roster": parent_roster,
        "token_index": token_index,
        "cohort_receipts": cohort_receipts,
    }


def select_partition_rows(
    rows: list[dict[str, Any]],
    *,
    fit_patients: set[str],
    excluded_patients: set[str],
    namespace: str,
    class_order: list[str],
    partition_counts: dict[str, dict[str, int]],
) -> dict[str, list[dict[str, Any]]]:
    if set(class_order) != set(PROGRESSION_CLASSES):
        raise ValueError("R40C class-order registry drift")
    used_patients = set(excluded_patients)
    selected: dict[str, list[dict[str, Any]]] = {
        partition: [] for partition in partition_counts
    }
    for partition in ("development", "train"):
        counts = partition_counts[partition]
        if set(counts) != set(PROGRESSION_CLASSES):
            raise ValueError("R40C partition class-count registry drift")
        for label in class_order:
            eligible = sorted(
                (
                    row
                    for row in rows
                    if str(row["progression"]) == label
                    and str(row["patient_id"]) in fit_patients
                    and str(row["patient_id"]) not in used_patients
                ),
                key=lambda row: stable_key(
                    f"{namespace}|{partition}|{label}",
                    str(row["example_id"]),
                ),
            )
            class_rows = []
            for row in eligible:
                patient_id = str(row["patient_id"])
                if patient_id in used_patients:
                    continue
                class_rows.append(row)
                used_patients.add(patient_id)
                if len(class_rows) == int(counts[label]):
                    break
            if len(class_rows) != int(counts[label]):
                raise ValueError(
                    f"insufficient R40C support for {partition}/{label}: "
                    f"{len(class_rows)} < {counts[label]}"
                )
            selected[partition].extend(class_rows)
        selected[partition].sort(
            key=lambda row: stable_key(
                f"{namespace}|{partition}|final",
                str(row["example_id"]),
            )
        )
    return selected


def support_inventory(
    rows: list[dict[str, Any]],
    *,
    fit_patients: set[str],
    excluded_patients: set[str],
) -> dict[str, Any]:
    eligible = [
        row
        for row in rows
        if str(row["patient_id"]) in fit_patients
        and str(row["patient_id"]) not in excluded_patients
    ]
    unique_support = {
        label: len(
            {
                str(row["patient_id"])
                for row in eligible
                if str(row["progression"]) == label
            }
        )
        for label in PROGRESSION_CLASSES
    }
    return {
        "fit_patients": len(fit_patients),
        "excluded_patients": len(excluded_patients),
        "remaining_patients": len(fit_patients - excluded_patients),
        "eligible_rows": len(eligible),
        "unique_patient_support": unique_support,
    }


def preflight(config_path: Path) -> dict[str, Any]:
    config = read_json(config_path)
    authority = validate_authority(config)
    target_rows = read_targets(Path(config["source"]["targets"]))
    partition_counts = {
        "train": {
            str(key): int(value)
            for key, value in config["roster"]["train_class_counts"].items()
        },
        "development": {
            str(key): int(value)
            for key, value in config["roster"][
                "development_class_counts"
            ].items()
        },
    }
    selected = select_partition_rows(
        target_rows,
        fit_patients=authority["fit_patients"],
        excluded_patients=authority["excluded_patients"],
        namespace=str(config["roster"]["namespace"]),
        class_order=[str(value) for value in config["roster"]["class_order"]],
        partition_counts=partition_counts,
    )
    selected_patients = {
        partition: {str(row["patient_id"]) for row in rows}
        for partition, rows in selected.items()
    }
    if selected_patients["train"] & selected_patients["development"]:
        raise PermissionError("R40C preflight partitions overlap")
    return {
        "schema": "visualvit.prta-gen.r40c-preflight.v1",
        "status": "PASS_PRTA_GEN_R40C_PREFLIGHT",
        "protocol_id": config["protocol_id"],
        "inventory": support_inventory(
            target_rows,
            fit_patients=authority["fit_patients"],
            excluded_patients=authority["excluded_patients"],
        ),
        "selected_counts_in_memory_only": {
            partition: len(rows) for partition, rows in selected.items()
        },
        "real_roster_written": False,
        "gpu_training_started": False,
        "protected_300_dev_read": False,
        "revealed_483_test_read": False,
        "gold_outcomes_read": False,
        "external_outcomes_read": False,
        "scientific_claim_allowed": False,
    }


def build_roster(config_path: Path, output_path: Path) -> dict[str, Any]:
    if output_path.exists():
        raise FileExistsError(f"R40C roster output must be fresh: {output_path}")
    config = read_json(config_path)
    authority = validate_authority(config)
    target_rows = read_targets(Path(config["source"]["targets"]))
    partition_counts = {
        "train": {
            str(key): int(value)
            for key, value in config["roster"]["train_class_counts"].items()
        },
        "development": {
            str(key): int(value)
            for key, value in config["roster"][
                "development_class_counts"
            ].items()
        },
    }
    selected = select_partition_rows(
        target_rows,
        fit_patients=authority["fit_patients"],
        excluded_patients=authority["excluded_patients"],
        namespace=str(config["roster"]["namespace"]),
        class_order=[str(value) for value in config["roster"]["class_order"]],
        partition_counts=partition_counts,
    )
    partitions = {}
    all_selected_patients: set[str] = set()
    for partition, rows in selected.items():
        serialized = [
            {
                "example_id": str(row["example_id"]),
                "patient_id": str(row["patient_id"]),
                "finding": str(row["finding"]),
                "progression": str(row["progression"]),
            }
            for row in rows
        ]
        patients = {row["patient_id"] for row in serialized}
        if patients & all_selected_patients:
            raise PermissionError("R40C selected partitions overlap")
        all_selected_patients.update(patients)
        partitions[partition] = {
            "rows": serialized,
            "row_count": len(serialized),
            "patient_count": len(patients),
            "progression_class_counts": dict(
                sorted(Counter(row["progression"] for row in serialized).items())
            ),
        }
    result = {
        "schema": "visualvit.prta-gen.r40c-roster.v1",
        "status": config["result_statuses"]["roster_pass"],
        "protocol_id": config["protocol_id"],
        "namespace": config["roster"]["namespace"],
        "assignment": config["roster"]["assignment"],
        "partitions": partitions,
        "inventory": support_inventory(
            target_rows,
            fit_patients=authority["fit_patients"],
            excluded_patients=authority["excluded_patients"],
        ),
        "excluded_observed_patient_count": len(
            authority["excluded_patients"]
        ),
        "excluded_observed_patients_absent": not bool(
            all_selected_patients & authority["excluded_patients"]
        ),
        "patient_sets_disjoint": True,
        "one_row_per_patient": all(
            payload["row_count"] == payload["patient_count"]
            for payload in partitions.values()
        ),
        "resplit_allowed": False,
        "development_outcomes_read": False,
        "protected_300_dev_read": False,
        "revealed_483_test_read": False,
        "gold_outcomes_read": False,
        "external_outcomes_read": False,
        "scientific_claim_allowed": False,
    }
    for partition, counts in partition_counts.items():
        payload = result["partitions"][partition]
        expected_patients = int(config["roster"][f"{partition}_patients"])
        if (
            payload["row_count"] != expected_patients
            or payload["patient_count"] != expected_patients
            or payload["progression_class_counts"]
            != dict(sorted(counts.items()))
        ):
            raise ValueError(f"R40C {partition} roster drift")
    write_json(output_path, result)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Preflight or build the frozen R40C patient roster"
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.preflight_only:
        if args.output is not None:
            raise ValueError("R40C preflight must not receive --output")
        result = preflight(args.config)
    else:
        if args.output is None:
            raise ValueError("R40C roster build requires --output")
        result = build_roster(args.config, args.output)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
