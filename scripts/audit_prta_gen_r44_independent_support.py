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

from scripts.build_prta_gen_r40b_smoke_cohort import read_json, read_targets
from scripts.build_prta_gen_r41a_roster import (
    support_inventory,
    validate_authority,
)


CONFIG_STATUS = "FROZEN_PRTA_GEN_R44_INDEPENDENT_SUPPORT_AUDIT"
PASS_STATUS = "PASS_PRTA_GEN_R44_INDEPENDENT_SUPPORT"
STOP_STATUS = "STOP_PRTA_GEN_R44_INDEPENDENT_SUPPORT"
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


class InsufficientSupportError(ValueError):
    """Raised when the frozen class/partition counts cannot be filled."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def stable_key(namespace: str, row: dict[str, Any]) -> str:
    raw = "|".join(
        (
            namespace,
            str(row["patient_id"]),
            str(row["study_id_curr"]),
            str(row["finding"]),
        )
    )
    return hashlib.sha256(raw.encode()).hexdigest()


def resolve_parent_image(root: Path, raw_path: str) -> Path | None:
    normalized = raw_path.replace("\\", "/").lstrip("/")
    candidates = [root / normalized]
    for prefix in ("chexpert/", "CheXpert-v1.0-small/"):
        if normalized.lower().startswith(prefix.lower()):
            candidates.append(root / normalized[len(prefix) :])
    candidates.append(root.parent / normalized)
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def validate_closed_r41a(config: dict[str, Any]) -> dict[str, Any]:
    spec = config["closed_r41a"]
    aggregate = read_json(Path(spec["aggregate"]))
    roster_path = Path(spec["roster"])
    roster = read_json(roster_path)
    case_path = Path(spec["case_study"])
    case_study = read_json(case_path)
    checks = {
        "aggregate_status": aggregate.get("status")
        == spec["required_status"],
        "aggregate_failed": aggregate.get("gate_passed") is False,
        "aggregate_r42_locked": aggregate.get("r42_unlocked") is False,
        "roster_status": roster.get("status")
        == spec["required_roster_status"],
        "roster_hash": sha256_file(roster_path)
        == spec["roster_sha256"],
        "case_status": case_study.get("status")
        == spec["required_case_status"],
        "case_hash": sha256_file(case_path)
        == spec["case_study_sha256"],
        "case_reuse_forbidden": case_study.get(
            "observed_development_reuse_for_selection_allowed"
        )
        is False,
        "case_scientific_claim": case_study.get("scientific_claim_allowed")
        is False,
    }
    failed = sorted(name for name, passed in checks.items() if not passed)
    if failed:
        raise PermissionError(f"R44 closed-R41A authority drift: {failed}")
    return roster


def audit_r40_remaining(config: dict[str, Any]) -> dict[str, Any]:
    lineage = config["r40_lineage"]
    r41_config_path = WORKSPACE / lineage["r41_config"]
    r41_config = read_json(r41_config_path)
    authority = validate_authority(r41_config)
    r41_roster = read_json(Path(r41_config["runtime"]["roster"]))
    used = set(authority["excluded_patients"])
    for partition in ("train", "development"):
        used.update(
            str(row["patient_id"])
            for row in r41_roster["partitions"][partition]["rows"]
        )
    rows = read_targets(Path(r41_config["source"]["targets"]))
    inventory = support_inventory(
        rows,
        fit_patients=authority["fit_patients"],
        excluded_patients=used,
    )
    expected_support = {
        str(key): int(value)
        for key, value in lineage[
            "expected_remaining_unique_patient_support"
        ].items()
    }
    if (
        inventory["remaining_patients"]
        != int(lineage["expected_remaining_fit_patients"])
        or inventory["unique_patient_support"] != expected_support
    ):
        raise ValueError("R44 R40-lineage scalar inventory drift")
    return {
        **inventory,
        "five_class_support_available": all(
            value > 1 for value in expected_support.values()
        ),
    }


def select_patient_disjoint_rows(
    rows: list[dict[str, Any]],
    *,
    namespace: str,
    class_order: list[str],
    partition_counts: dict[str, dict[str, int]],
) -> dict[str, list[dict[str, Any]]]:
    used: set[str] = set()
    selected = {partition: [] for partition in partition_counts}
    for partition in ("development", "train"):
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
            required = int(partition_counts[partition][label])
            chosen = []
            for row in candidates:
                patient = str(row["patient_id"])
                if patient in used:
                    continue
                chosen.append(row)
                used.add(patient)
                if len(chosen) == required:
                    break
            if len(chosen) != required:
                raise InsufficientSupportError(
                    f"insufficient R44 support for {partition}/{label}: "
                    f"{len(chosen)} < {required}"
                )
            selected[partition].extend(chosen)
    return selected


def audit_chextemporal_support(
    *,
    frame: pd.DataFrame,
    gold_patients: set[str],
    image_root: Path,
    dataset_filter: str,
    classes: list[str],
    class_order: list[str],
    namespace: str,
    partition_counts: dict[str, dict[str, int]],
) -> dict[str, Any]:
    missing_columns = sorted(REQUIRED_COLUMNS - set(frame.columns))
    if missing_columns:
        raise ValueError(f"CheXTemporal columns missing: {missing_columns}")
    if set(classes) != set(class_order):
        raise ValueError("R44 class registry/order drift")
    source = frame.loc[
        frame["dataset"].astype(str).str.lower() == dataset_filter.lower(),
        sorted(REQUIRED_COLUMNS),
    ].copy()
    if set(source["progression"].astype(str)) - set(classes):
        raise ValueError("R44 progression registry drift")
    source["patient_id"] = source["patient_id"].astype(str)
    source = source.loc[~source["patient_id"].isin(gold_patients)]
    path_cache: dict[str, bool] = {}

    def available(raw: Any) -> bool:
        value = str(raw)
        if value not in path_cache:
            path_cache[value] = (
                resolve_parent_image(image_root, value) is not None
            )
        return path_cache[value]

    current_available = source["parent_image_curr"].map(available)
    prior_available = source["parent_image_prev"].map(available)
    complete = source.loc[current_available & prior_available]
    rows = complete.to_dict(orient="records")
    unique_support = {
        label: int(
            complete.loc[
                complete["progression"].astype(str) == label, "patient_id"
            ].nunique()
        )
        for label in classes
    }
    support_failures: list[str] = []
    try:
        selected = select_patient_disjoint_rows(
            rows,
            namespace=namespace,
            class_order=class_order,
            partition_counts=partition_counts,
        )
    except InsufficientSupportError:
        selected = {partition: [] for partition in partition_counts}
        support_failures.append("insufficient_patient_disjoint_class_support")
    selected_patients = {
        partition: {
            str(row["patient_id"]) for row in partition_rows
        }
        for partition, partition_rows in selected.items()
    }
    if selected_patients["train"] & selected_patients["development"]:
        raise PermissionError("R44 selected partitions overlap")
    if any(
        patients & gold_patients for patients in selected_patients.values()
    ):
        raise PermissionError("R44 selected a protected gold patient")
    return {
        "dataset": dataset_filter,
        "source_rows": len(source),
        "source_patients": int(source["patient_id"].nunique()),
        "image_complete_rows": len(complete),
        "image_complete_patients": int(complete["patient_id"].nunique()),
        "missing_image_references": int(
            (~current_available).sum() + (~prior_available).sum()
        ),
        "unique_patient_support": unique_support,
        "excluded_gold_patients": len(gold_patients),
        "support_gate_failures": support_failures,
        "support_sufficient": not support_failures,
        "selected_counts_in_memory_only": {
            partition: {
                "rows": len(partition_rows),
                "patients": len(selected_patients[partition]),
                "class_counts": dict(
                    sorted(
                        Counter(
                            str(row["progression"])
                            for row in partition_rows
                        ).items()
                    )
                ),
            }
            for partition, partition_rows in selected.items()
        },
        "patient_partitions_disjoint": True,
        "gold_patients_absent": True,
        "selected_rows_image_complete": True,
        "roster_written": False,
    }


def audit(config_path: Path) -> dict[str, Any]:
    config = read_json(config_path)
    if config.get("status") != CONFIG_STATUS:
        raise PermissionError("R44 support config is not frozen")
    validate_closed_r41a(config)
    r40_inventory = audit_r40_remaining(config)
    silver = config["chextemporal_silver"]
    silver_path = Path(silver["local_file"])
    if not silver_path.is_file():
        return {
            "schema": "visualvit.prta-gen.r44-independent-support-result.v1",
            "status": STOP_STATUS,
            "protocol_id": config["protocol_id"],
            "gate_passed": False,
            "gate_failures": ["chextemporal_silver_file_missing"],
            "r40_remaining": r40_inventory,
            "chextemporal_silver_file_present": False,
            "roster_written": False,
            "gpu_training_started": False,
            "protected_300_dev_read": False,
            "revealed_483_test_read": False,
            "gold_outcomes_read": False,
            "external_outcomes_read": False,
            "scientific_claim_allowed": False,
        }
    if (
        silver_path.stat().st_size != int(silver["required_file_bytes"])
        or sha256_file(silver_path) != silver["required_file_sha256"]
    ):
        raise ValueError("CheXTemporal silver file bytes/hash drift")
    gold_path = WORKSPACE / silver["gold_registry"]
    gold = pd.read_parquet(
        gold_path,
        columns=list(silver["gold_registry_columns_allowed"]),
    )
    gold_patients = set(
        gold.loc[
            gold["dataset"].astype(str).str.lower()
            == str(silver["dataset_filter"]).lower(),
            "patient_id",
        ].astype(str)
    )
    frame = pd.read_parquet(
        silver_path, columns=sorted(REQUIRED_COLUMNS)
    )
    gate = config["support_gate"]
    partition_counts = {
        "train": {
            str(key): int(value)
            for key, value in gate["train_class_counts"].items()
        },
        "development": {
            str(key): int(value)
            for key, value in gate[
                "development_class_counts"
            ].items()
        },
    }
    support = audit_chextemporal_support(
        frame=frame,
        gold_patients=gold_patients,
        image_root=Path(silver["parent_image_root"]),
        dataset_filter=str(silver["dataset_filter"]),
        classes=[str(value) for value in gate["classes"]],
        class_order=[str(value) for value in gate["class_order"]],
        namespace=str(gate["namespace"]),
        partition_counts=partition_counts,
    )
    checks = {
        "r40_remaining_is_not_five_class": r40_inventory[
            "five_class_support_available"
        ]
        is False,
        "chextemporal_support_sufficient": support["support_sufficient"]
        is True,
        "selected_rows_image_complete": support[
            "selected_rows_image_complete"
        ]
        is True,
        "chextemporal_gold_patients_absent": support[
            "gold_patients_absent"
        ]
        is True,
        "chextemporal_partitions_disjoint": support[
            "patient_partitions_disjoint"
        ]
        is True,
        "roster_not_written": support["roster_written"] is False,
    }
    failures = sorted(name for name, passed in checks.items() if not passed)
    passed = not failures
    return {
        "schema": "visualvit.prta-gen.r44-independent-support-result.v1",
        "status": PASS_STATUS if passed else STOP_STATUS,
        "protocol_id": config["protocol_id"],
        "gate_passed": passed,
        "gate_failures": failures,
        "r40_remaining": r40_inventory,
        "chextemporal": support,
        "chextemporal_silver_file_present": True,
        "chextemporal_silver_file_sha256": sha256_file(silver_path),
        "roster_written": False,
        "gpu_training_started": False,
        "r42_unlocked": False,
        "r43_unlocked": False,
        "protected_300_dev_read": False,
        "revealed_483_test_read": False,
        "gold_outcomes_read": False,
        "external_outcomes_read": False,
        "scientific_claim_allowed": False,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit independent five-class support for PRTA-Gen R44"
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.preflight_only and args.output is not None:
        raise ValueError("R44 preflight must not receive --output")
    if not args.preflight_only and args.output is None:
        raise ValueError("R44 audit requires --output")
    result = audit(args.config)
    if not args.preflight_only:
        assert args.output is not None
        if args.output.exists():
            raise FileExistsError(
                f"R44 support audit output must be fresh: {args.output}"
            )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.output.with_suffix(args.output.suffix + ".tmp")
        temporary.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(args.output)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["gate_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
