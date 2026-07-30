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


CONFIG_STATUS = "FROZEN_PRTA_GEN_R41A_PROGRESSION_SFT"
ROSTER_STATUS = "PASS_PRTA_GEN_R41A_ROSTER_SUPPORT"


def stable_key(namespace: str, value: str) -> str:
    return hashlib.sha256(f"{namespace}|{value}".encode()).hexdigest()


def _false_firewalls(value: dict[str, Any]) -> bool:
    return all(
        value.get(key) is False
        for key in (
            "protected_300_dev_read",
            "revealed_483_test_read",
            "gold_outcomes_read",
            "external_outcomes_read",
        )
        if key in value
    )


def validate_authority(config: dict[str, Any]) -> dict[str, Any]:
    if config.get("status") != CONFIG_STATUS:
        raise PermissionError("R41A config is not frozen")
    predecessor_spec = config["closed_predecessor"]
    predecessor = read_json(Path(predecessor_spec["aggregate"]))
    if (
        predecessor.get("status") != predecessor_spec["required_status"]
        or predecessor.get("gate_passed")
        is not predecessor_spec["required_gate_passed"]
        or predecessor.get("qwen_free_generation_unlocked")
        is not predecessor_spec["qwen_free_generation_was_unlocked"]
        or predecessor.get("r41_qwen_sft_unlocked")
        is not predecessor_spec["r41_qwen_sft_was_unlocked"]
        or not _false_firewalls(predecessor)
    ):
        raise PermissionError("R41A predecessor receipt drift")
    source = config["source"]
    parent = read_json(Path(source["roster"]))
    if (
        parent.get("status") != source["required_roster_status"]
        or parent.get("patient_sets_disjoint") is not True
        or not _false_firewalls(parent)
    ):
        raise PermissionError("R41A parent roster drift")
    token_index = read_json(Path(source["token_index"]))
    if (
        token_index.get("status") != source["required_token_status"]
        or token_index.get("scope") != "training"
        or token_index.get("labels_in_cache") is not False
        or token_index.get("sentences_in_cache") is not False
        or not _false_firewalls(token_index)
    ):
        raise PermissionError("R41A token-cache firewall drift")
    excluded: set[str] = set()
    cohort_receipts = []
    for spec in source["exclude_cohorts"]:
        cohort = read_json(Path(spec["path"]))
        if (
            cohort.get("status") != spec["required_status"]
            or cohort.get("row_count") != 32
            or cohort.get("patient_count") != 32
            or not _false_firewalls(cohort)
        ):
            raise PermissionError("R41A historical-cohort receipt drift")
        patients = {str(row["patient_id"]) for row in cohort["rows"]}
        if len(patients) != 32 or excluded & patients:
            raise PermissionError("R41A historical cohorts overlap")
        excluded.update(patients)
        cohort_receipts.append(
            {"status": cohort["status"], "patient_count": len(patients)}
        )
    r40c = read_json(Path(source["exclude_r40c_roster"]))
    if (
        r40c.get("status") != source["required_r40c_roster_status"]
        or r40c.get("patient_sets_disjoint") is not True
        or r40c.get("one_row_per_patient") is not True
        or not _false_firewalls(r40c)
    ):
        raise PermissionError("R41A R40C roster receipt drift")
    r40c_patients = {
        str(row["patient_id"])
        for partition in ("train", "development")
        for row in r40c["partitions"][partition]["rows"]
    }
    if len(r40c_patients) != 1500 or excluded & r40c_patients:
        raise PermissionError("R41A R40C exclusion drift")
    excluded.update(r40c_patients)
    expected = int(source["expected_excluded_patient_count"])
    if len(excluded) != expected:
        raise ValueError(
            f"R41A excluded-patient drift: {len(excluded)} != {expected}"
        )
    fit_patients = {
        str(value)
        for value in parent["partitions"][source["partition"]]["patient_ids"]
    }
    if excluded - fit_patients:
        raise PermissionError("R41A exclusion escaped parent fit partition")
    return {
        "fit_patients": fit_patients,
        "excluded_patients": excluded,
        "cohort_receipts": cohort_receipts,
        "r40c_patient_count": len(r40c_patients),
    }


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


def select_rows(
    rows: list[dict[str, Any]],
    *,
    fit_patients: set[str],
    excluded_patients: set[str],
    namespace: str,
    class_order: list[str],
    partition_counts: dict[str, dict[str, int]],
) -> dict[str, list[dict[str, Any]]]:
    if set(class_order) != set(PROGRESSION_CLASSES):
        raise ValueError("R41A progression class-order drift")
    used = set(excluded_patients)
    selected = {partition: [] for partition in partition_counts}
    for partition in ("development", "train"):
        counts = partition_counts[partition]
        if set(counts) != set(PROGRESSION_CLASSES):
            raise ValueError("R41A partition class-count drift")
        for label in class_order:
            eligible = sorted(
                (
                    row
                    for row in rows
                    if str(row["progression"]) == label
                    and str(row["patient_id"]) in fit_patients
                    and str(row["patient_id"]) not in used
                ),
                key=lambda row: stable_key(
                    f"{namespace}|{partition}|{label}",
                    str(row["example_id"]),
                ),
            )
            class_rows = []
            for row in eligible:
                patient = str(row["patient_id"])
                if patient in used:
                    continue
                class_rows.append(row)
                used.add(patient)
                if len(class_rows) == int(counts[label]):
                    break
            if len(class_rows) != int(counts[label]):
                raise ValueError(
                    f"insufficient R41A support for {partition}/{label}: "
                    f"{len(class_rows)} < {counts[label]}"
                )
            selected[partition].extend(class_rows)
        selected[partition].sort(
            key=lambda row: stable_key(
                f"{namespace}|{partition}|final", str(row["example_id"])
            )
        )
    return selected


def _partition_counts(config: dict[str, Any]) -> dict[str, dict[str, int]]:
    return {
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


def preflight(config_path: Path) -> dict[str, Any]:
    config = read_json(config_path)
    authority = validate_authority(config)
    rows = read_targets(Path(config["source"]["targets"]))
    selected = select_rows(
        rows,
        fit_patients=authority["fit_patients"],
        excluded_patients=authority["excluded_patients"],
        namespace=str(config["roster"]["namespace"]),
        class_order=[str(value) for value in config["roster"]["class_order"]],
        partition_counts=_partition_counts(config),
    )
    selected_patients = {
        partition: {str(row["patient_id"]) for row in values}
        for partition, values in selected.items()
    }
    if selected_patients["train"] & selected_patients["development"]:
        raise PermissionError("R41A preflight partitions overlap")
    inventory = support_inventory(
        rows,
        fit_patients=authority["fit_patients"],
        excluded_patients=authority["excluded_patients"],
    )
    resolved_reserve = (
        int(inventory["unique_patient_support"]["Resolved"])
        - int(config["roster"]["train_class_counts"]["Resolved"])
        - int(config["roster"]["development_class_counts"]["Resolved"])
    )
    if resolved_reserve < int(
        config["roster"]["minimum_unselected_resolved_patient_reserve"]
    ):
        raise ValueError("R41A Resolved reserve is below the frozen minimum")
    return {
        "schema": "visualvit.prta-gen.r41a-preflight.v1",
        "status": "PASS_PRTA_GEN_R41A_PREFLIGHT",
        "protocol_id": config["protocol_id"],
        "inventory": inventory,
        "selected_counts_in_memory_only": {
            partition: len(values) for partition, values in selected.items()
        },
        "resolved_patient_reserve": resolved_reserve,
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
        raise FileExistsError(f"R41A roster output must be fresh: {output_path}")
    config = read_json(config_path)
    authority = validate_authority(config)
    rows = read_targets(Path(config["source"]["targets"]))
    selected = select_rows(
        rows,
        fit_patients=authority["fit_patients"],
        excluded_patients=authority["excluded_patients"],
        namespace=str(config["roster"]["namespace"]),
        class_order=[str(value) for value in config["roster"]["class_order"]],
        partition_counts=_partition_counts(config),
    )
    partitions = {}
    all_selected: set[str] = set()
    for partition, values in selected.items():
        serialized = [
            {
                "example_id": str(row["example_id"]),
                "patient_id": str(row["patient_id"]),
                "finding": str(row["finding"]),
                "progression": str(row["progression"]),
            }
            for row in values
        ]
        patients = {row["patient_id"] for row in serialized}
        if patients & all_selected:
            raise PermissionError("R41A selected partitions overlap")
        all_selected.update(patients)
        partitions[partition] = {
            "rows": serialized,
            "row_count": len(serialized),
            "patient_count": len(patients),
            "progression_class_counts": dict(
                sorted(Counter(row["progression"] for row in serialized).items())
            ),
        }
    inventory = support_inventory(
        rows,
        fit_patients=authority["fit_patients"],
        excluded_patients=authority["excluded_patients"],
    )
    result = {
        "schema": "visualvit.prta-gen.r41a-roster.v1",
        "status": config["result_statuses"]["roster_pass"],
        "protocol_id": config["protocol_id"],
        "namespace": config["roster"]["namespace"],
        "assignment": config["roster"]["assignment"],
        "partitions": partitions,
        "inventory": inventory,
        "excluded_observed_patient_count": len(
            authority["excluded_patients"]
        ),
        "excluded_observed_patients_absent": not bool(
            all_selected & authority["excluded_patients"]
        ),
        "resolved_patient_reserve": (
            int(inventory["unique_patient_support"]["Resolved"])
            - int(config["roster"]["train_class_counts"]["Resolved"])
            - int(config["roster"]["development_class_counts"]["Resolved"])
        ),
        "patient_sets_disjoint": True,
        "one_row_per_patient": all(
            payload["row_count"] == payload["patient_count"]
            for payload in partitions.values()
        ),
        "resplit_allowed": False,
        "development_outcomes_read": False,
        "r40c_outcomes_used_for_roster_selection": False,
        "protected_300_dev_read": False,
        "revealed_483_test_read": False,
        "gold_outcomes_read": False,
        "external_outcomes_read": False,
        "scientific_claim_allowed": False,
    }
    counts = _partition_counts(config)
    for partition, expected_counts in counts.items():
        payload = result["partitions"][partition]
        expected_patients = int(config["roster"][f"{partition}_patients"])
        if (
            payload["row_count"] != expected_patients
            or payload["patient_count"] != expected_patients
            or payload["progression_class_counts"]
            != dict(sorted(expected_counts.items()))
        ):
            raise ValueError(f"R41A {partition} roster drift")
    if result["resolved_patient_reserve"] < int(
        config["roster"]["minimum_unselected_resolved_patient_reserve"]
    ):
        raise ValueError("R41A Resolved reserve drift")
    write_json(output_path, result)
    return result


def receipt_summary(result: dict[str, Any]) -> dict[str, Any]:
    summary = {
        key: value for key, value in result.items() if key != "partitions"
    }
    if "partitions" in result:
        summary["partitions"] = {
            partition: {
                key: value
                for key, value in payload.items()
                if key != "rows"
            }
            for partition, payload in result["partitions"].items()
        }
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Preflight or build the frozen R41A patient roster"
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.preflight_only:
        if args.output is not None:
            raise ValueError("R41A preflight must not receive --output")
        result = preflight(args.config)
    else:
        if args.output is None:
            raise ValueError("R41A roster build requires --output")
        result = build_roster(args.config, args.output)
    print(json.dumps(receipt_summary(result), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
