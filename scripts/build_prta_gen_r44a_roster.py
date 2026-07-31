from __future__ import annotations

# ruff: noqa: E402

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

import pandas as pd

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE))
sys.path.insert(0, str(WORKSPACE / "src"))

from scripts.audit_prta_gen_r44_independent_support import (
    index_parent_images,
    parent_image_is_indexed,
    sha256_file,
)
from scripts.build_prta_gen_r40b_smoke_cohort import read_json, write_json
from visualvit.prta_gen import PROGRESSION_CLASSES


CONFIG_STATUS = "FROZEN_PRTA_GEN_R44A_CROSS_SOURCE_SILVER_SFT"
ROSTER_STATUS = "PASS_PRTA_GEN_R44A_ROSTER_SUPPORT"
REQUIRED_COLUMNS = {
    "dataset",
    "patient_id",
    "study_id_curr",
    "study_id_prev",
    "finding",
    "progression",
    "parent_image_curr",
    "parent_image_prev",
}


def stable_key(namespace: str, row: dict[str, Any]) -> str:
    value = "|".join(
        (
            namespace,
            str(row["patient_id"]),
            str(row["study_id_curr"]),
            str(row["finding"]),
        )
    )
    return hashlib.sha256(value.encode()).hexdigest()


def image_id(raw_path: str) -> str:
    normalized = raw_path.replace("\\", "/").lstrip("/").casefold()
    return hashlib.sha256(f"r44a-image|{normalized}".encode()).hexdigest()


def resolve_image_path(root: Path, raw_path: str) -> Path:
    normalized = raw_path.replace("\\", "/").lstrip("/")
    for prefix in ("chexpert/", f"{root.name}/"):
        if normalized.casefold().startswith(prefix.casefold()):
            normalized = normalized[len(prefix) :]
            break
    return root / Path(normalized)


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
        raise PermissionError("R44A config is not frozen")
    support_spec = config["closed_support"]
    support_path = Path(support_spec["audit"])
    support = read_json(support_path)
    if (
        sha256_file(support_path) != support_spec["required_sha256"]
        or support.get("status") != support_spec["required_status"]
        or support.get("gate_passed")
        is not support_spec["required_gate_passed"]
        or support["chextemporal"]["dataset"]
        != support_spec["required_dataset"]
        or support["chextemporal"]["source_patients"]
        != support_spec["required_source_patients"]
        or support["chextemporal"]["image_complete_rows"]
        != support_spec["required_image_complete_rows"]
        or support.get("roster_written") is not False
        or support.get("gpu_training_started") is not False
        or not _false_firewalls(support)
    ):
        raise PermissionError("R44A support-audit authority drift")
    r41_spec = config["closed_r41a"]
    r41_path = Path(r41_spec["aggregate"])
    r41 = read_json(r41_path)
    if (
        sha256_file(r41_path) != r41_spec["required_sha256"]
        or r41.get("status") != r41_spec["required_status"]
        or r41.get("gate_passed") is not r41_spec["required_gate_passed"]
        or r41.get("r42_unlocked") is not False
        or not _false_firewalls(r41)
    ):
        raise PermissionError("R44A closed-R41A authority drift")
    source = config["source"]
    silver_path = Path(source["silver_file"])
    gold_path = WORKSPACE / source["gold_registry"]
    if (
        not silver_path.is_file()
        or silver_path.stat().st_size != source["silver_file_bytes"]
        or sha256_file(silver_path) != source["silver_file_sha256"]
    ):
        raise PermissionError("R44A silver source drift")
    if (
        not gold_path.is_file()
        or gold_path.stat().st_size != source["gold_registry_bytes"]
        or sha256_file(gold_path) != source["gold_registry_sha256"]
    ):
        raise PermissionError("R44A gold exclusion registry drift")
    image_root = Path(source["parent_image_root"])
    if not image_root.is_dir():
        raise FileNotFoundError("R44A CheXpert image root is absent")
    if config["target"]["finding_values"] != source["allowed_findings"]:
        raise PermissionError("R44A inherited finding registry drift")
    return {
        "silver_path": silver_path,
        "gold_path": gold_path,
        "image_root": image_root,
    }


def load_eligible_rows(
    config: dict[str, Any], authority: dict[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    source = config["source"]
    gold = pd.read_parquet(
        authority["gold_path"],
        columns=list(source["gold_registry_columns_allowed"]),
    )
    dataset_filter = str(source["dataset_filter"])
    gold_patients = set(
        gold.loc[
            gold["dataset"].astype(str).str.lower()
            == dataset_filter.lower(),
            "patient_id",
        ].astype(str)
    )
    frame = pd.read_parquet(
        authority["silver_path"], columns=sorted(REQUIRED_COLUMNS)
    )
    frame = frame.loc[
        frame["dataset"].astype(str).str.lower()
        == dataset_filter.lower()
    ].copy()
    frame["patient_id"] = frame["patient_id"].astype(str)
    source_rows = len(frame)
    frame = frame.loc[~frame["patient_id"].isin(gold_patients)]
    frame = frame.loc[
        frame["finding"].astype(str).isin(source["allowed_findings"])
    ]
    observed_progression = set(frame["progression"].astype(str))
    if observed_progression - set(PROGRESSION_CLASSES):
        raise ValueError("R44A progression registry drift")
    rows = frame.to_dict(orient="records")
    return rows, {
        "source_rows": source_rows,
        "eligible_rows": len(rows),
        "eligible_patients": int(frame["patient_id"].nunique()),
        "excluded_gold_patients": len(gold_patients),
        "unique_patient_support": {
            label: int(
                frame.loc[
                    frame["progression"].astype(str) == label,
                    "patient_id",
                ].nunique()
            )
            for label in PROGRESSION_CLASSES
        },
    }


def _partition_counts(
    config: dict[str, Any]
) -> dict[str, dict[str, int]]:
    return {
        partition: {
            str(key): int(value)
            for key, value in config["roster"][
                f"{partition}_class_counts"
            ].items()
        }
        for partition in ("train", "development")
    }


def select_rows(
    rows: list[dict[str, Any]],
    *,
    namespace: str,
    class_order: list[str],
    partition_counts: dict[str, dict[str, int]],
) -> dict[str, list[dict[str, Any]]]:
    if set(class_order) != set(PROGRESSION_CLASSES):
        raise ValueError("R44A progression class-order drift")
    used: set[str] = set()
    selected = {partition: [] for partition in partition_counts}
    for partition in ("development", "train"):
        counts = partition_counts[partition]
        if set(counts) != set(PROGRESSION_CLASSES):
            raise ValueError("R44A partition class-count drift")
        for label in class_order:
            candidates = sorted(
                (
                    row
                    for row in rows
                    if str(row["progression"]) == label
                    and str(row["patient_id"]) not in used
                ),
                key=lambda row: stable_key(
                    f"{namespace}|{partition}|{label}", row
                ),
            )
            chosen = []
            for row in candidates:
                patient = str(row["patient_id"])
                if patient in used:
                    continue
                chosen.append(row)
                used.add(patient)
                if len(chosen) == counts[label]:
                    break
            if len(chosen) != counts[label]:
                raise ValueError(
                    f"insufficient R44A support for {partition}/{label}: "
                    f"{len(chosen)} < {counts[label]}"
                )
            selected[partition].extend(chosen)
        selected[partition].sort(
            key=lambda row: stable_key(
                f"{namespace}|{partition}|final", row
            )
        )
    return selected


def _selection(
    config: dict[str, Any]
) -> tuple[
    dict[str, list[dict[str, Any]]],
    dict[str, Any],
    dict[str, Any],
]:
    authority = validate_authority(config)
    rows, inventory = load_eligible_rows(config, authority)
    selected = select_rows(
        rows,
        namespace=str(config["roster"]["namespace"]),
        class_order=[
            str(value) for value in config["roster"]["class_order"]
        ],
        partition_counts=_partition_counts(config),
    )
    selected_patients = {
        str(row["patient_id"])
        for values in selected.values()
        for row in values
    }
    resolved_patients = {
        str(row["patient_id"])
        for row in rows
        if str(row["progression"]) == "Resolved"
    }
    resolved_reserve = len(resolved_patients - selected_patients)
    if resolved_reserve < int(
        config["roster"]["minimum_unselected_resolved_patient_reserve"]
    ):
        raise ValueError("R44A Resolved reserve is below frozen minimum")
    indexed = index_parent_images(authority["image_root"])
    selected_raw_paths = [
        str(row[key])
        for values in selected.values()
        for row in values
        for key in ("parent_image_prev", "parent_image_curr")
    ]
    missing = [
        value
        for value in selected_raw_paths
        if not parent_image_is_indexed(
            root=authority["image_root"],
            indexed=indexed,
            raw_path=value,
        )
    ]
    if missing:
        raise FileNotFoundError(
            f"R44A selected image references missing: {len(missing)}"
        )
    receipts = {
        "resolved_patient_reserve": resolved_reserve,
        "indexed_parent_image_files": len(indexed),
        "selected_image_references": len(selected_raw_paths),
        "selected_images_complete": True,
    }
    return selected, inventory, {**authority, **receipts}


def preflight(config_path: Path) -> dict[str, Any]:
    config = read_json(config_path)
    selected, inventory, authority = _selection(config)
    patient_sets = {
        partition: {str(row["patient_id"]) for row in rows}
        for partition, rows in selected.items()
    }
    if patient_sets["train"] & patient_sets["development"]:
        raise PermissionError("R44A preflight partitions overlap")
    return {
        "schema": "visualvit.prta-gen.r44a-roster-preflight.v1",
        "status": "PASS_PRTA_GEN_R44A_ROSTER_PREFLIGHT",
        "protocol_id": config["protocol_id"],
        "inventory": inventory,
        "selected_counts_in_memory_only": {
            partition: len(rows) for partition, rows in selected.items()
        },
        "resolved_patient_reserve": authority[
            "resolved_patient_reserve"
        ],
        "selected_images_complete": True,
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
        raise FileExistsError(f"R44A roster output must be fresh: {output_path}")
    config = read_json(config_path)
    selected, inventory, authority = _selection(config)
    root = authority["image_root"]
    partitions: dict[str, Any] = {}
    all_patients: set[str] = set()
    for partition, rows in selected.items():
        serialized = []
        for row in rows:
            prior_raw = str(row["parent_image_prev"])
            current_raw = str(row["parent_image_curr"])
            serialized.append(
                {
                    "example_id": stable_key(
                        str(config["roster"]["namespace"]), row
                    ),
                    "patient_id": str(row["patient_id"]),
                    "finding": str(row["finding"]),
                    "progression": str(row["progression"]),
                    "prior_study_id": str(row["study_id_prev"]),
                    "current_study_id": str(row["study_id_curr"]),
                    "prior_image_id": image_id(prior_raw),
                    "current_image_id": image_id(current_raw),
                    "prior_path": str(resolve_image_path(root, prior_raw)),
                    "current_path": str(resolve_image_path(root, current_raw)),
                }
            )
        patients = {row["patient_id"] for row in serialized}
        if patients & all_patients:
            raise PermissionError("R44A selected partitions overlap")
        all_patients.update(patients)
        partitions[partition] = {
            "rows": serialized,
            "row_count": len(serialized),
            "patient_count": len(patients),
            "progression_class_counts": dict(
                sorted(Counter(row["progression"] for row in serialized).items())
            ),
        }
    result = {
        "schema": "visualvit.prta-gen.r44a-roster.v1",
        "status": config["result_statuses"]["roster_pass"],
        "protocol_id": config["protocol_id"],
        "namespace": config["roster"]["namespace"],
        "assignment": config["roster"]["assignment"],
        "partitions": partitions,
        "inventory": inventory,
        "excluded_observed_patient_count": inventory[
            "excluded_gold_patients"
        ],
        "excluded_observed_patients_absent": True,
        "resolved_patient_reserve": authority[
            "resolved_patient_reserve"
        ],
        "patient_sets_disjoint": True,
        "one_row_per_patient": all(
            value["row_count"] == value["patient_count"]
            for value in partitions.values()
        ),
        "selected_images_complete": True,
        "resplit_allowed": False,
        "development_outcomes_read": False,
        "r40c_outcomes_used_for_roster_selection": False,
        "r41a_development_reused": False,
        "r41a_outcomes_used_for_roster_selection": False,
        "protected_300_dev_read": False,
        "revealed_483_test_read": False,
        "gold_outcomes_read": False,
        "external_outcomes_read": False,
        "scientific_claim_allowed": False,
    }
    counts = _partition_counts(config)
    for partition, expected_counts in counts.items():
        payload = partitions[partition]
        expected = int(config["roster"][f"{partition}_patients"])
        if (
            payload["row_count"] != expected
            or payload["patient_count"] != expected
            or payload["progression_class_counts"]
            != dict(sorted(expected_counts.items()))
        ):
            raise ValueError(f"R44A {partition} roster drift")
    output_path.parent.mkdir(parents=True, exist_ok=True)
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
        description="Preflight or build the frozen R44A patient roster"
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.preflight_only:
        if args.output is not None:
            raise ValueError("R44A preflight must not receive --output")
        result = preflight(args.config)
    else:
        if args.output is None:
            raise ValueError("R44A roster build requires --output")
        result = build_roster(args.config, args.output)
    print(json.dumps(receipt_summary(result), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
