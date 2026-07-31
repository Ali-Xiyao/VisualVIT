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
from scripts.build_prta_gen_r44a_roster import image_id, resolve_image_path
from visualvit.prta_gen import PROGRESSION_CLASSES


CONFIG_STATUS = "FROZEN_PRTA_GEN_R45_CDEB_ROSTER"
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


def _validate_file(spec: dict[str, Any], prefix: str) -> tuple[Path, dict]:
    path = Path(spec[prefix])
    payload = read_json(path)
    if (
        not path.is_file()
        or path.stat().st_size != int(spec[f"{prefix}_bytes"])
        or sha256_file(path) != spec[f"{prefix}_sha256"]
        or payload.get("status") != spec[f"{prefix}_status"]
    ):
        raise PermissionError(f"R45 closed {prefix} authority drift")
    return path, payload


def validate_authority(config: dict[str, Any]) -> dict[str, Any]:
    if config.get("status") != CONFIG_STATUS:
        raise PermissionError("R45 roster config is not frozen")
    closed = config["closed_r44a"]
    roster_path, r44_roster = _validate_file(closed, "roster")
    _, aggregate = _validate_file(closed, "aggregate")
    _, case_study = _validate_file(closed, "case_study")
    if (
        aggregate.get("gate_passed") is not False
        or aggregate.get("r42_unlocked") is not False
        or case_study.get("scientific_claim_allowed") is not False
    ):
        raise PermissionError("R45 closed R44A result boundary drift")
    r44_patients = {
        str(row["patient_id"])
        for partition in ("train", "development")
        for row in r44_roster["partitions"][partition]["rows"]
    }
    if len(r44_patients) != int(closed["required_excluded_patients"]):
        raise PermissionError("R45 R44A exclusion count drift")

    source = config["source"]
    silver_path = Path(source["silver_file"])
    gold_path = WORKSPACE / source["gold_registry"]
    for path, bytes_key, sha_key in (
        (silver_path, "silver_file_bytes", "silver_file_sha256"),
        (gold_path, "gold_registry_bytes", "gold_registry_sha256"),
    ):
        if (
            not path.is_file()
            or path.stat().st_size != int(source[bytes_key])
            or sha256_file(path) != source[sha_key]
        ):
            raise PermissionError(f"R45 source authority drift: {path.name}")
    image_root = Path(source["parent_image_root"])
    if not image_root.is_dir():
        raise FileNotFoundError("R45 CheXpert image root is absent")
    if set(source["allowed_findings"]) == set():
        raise ValueError("R45 finding registry is empty")
    return {
        "silver_path": silver_path,
        "gold_path": gold_path,
        "image_root": image_root,
        "r44_patients": r44_patients,
        "r44_roster_path": roster_path,
    }


def load_image_complete_rows(
    config: dict[str, Any], authority: dict[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, Any], set[str]]:
    source = config["source"]
    gold = pd.read_parquet(
        authority["gold_path"], columns=["dataset", "patient_id"]
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
    excluded = gold_patients | authority["r44_patients"]
    frame = frame.loc[~frame["patient_id"].isin(excluded)]
    frame = frame.loc[
        frame["finding"].astype(str).isin(source["allowed_findings"])
    ]
    observed = set(frame["progression"].astype(str))
    if observed - set(PROGRESSION_CLASSES):
        raise ValueError("R45 progression registry drift")

    indexed = index_parent_images(authority["image_root"])
    cache: dict[str, bool] = {}

    def available(raw: Any) -> bool:
        value = str(raw)
        if value not in cache:
            cache[value] = parent_image_is_indexed(
                root=authority["image_root"],
                indexed=indexed,
                raw_path=value,
            )
        return cache[value]

    complete = frame.loc[
        frame["parent_image_curr"].map(available)
        & frame["parent_image_prev"].map(available)
    ].copy()
    inventory = {
        "source_rows": source_rows,
        "rows_after_historical_exclusions": len(frame),
        "patients_after_historical_exclusions": int(
            frame["patient_id"].nunique()
        ),
        "image_complete_rows": len(complete),
        "image_complete_patients": int(complete["patient_id"].nunique()),
        "indexed_parent_image_files": len(indexed),
        "excluded_gold_patients": len(gold_patients),
        "excluded_r44a_patients": len(authority["r44_patients"]),
        "unique_patient_support": {
            label: int(
                complete.loc[
                    complete["progression"].astype(str) == label,
                    "patient_id",
                ].nunique()
            )
            for label in PROGRESSION_CLASSES
        },
    }
    return complete.to_dict(orient="records"), inventory, indexed


def partition_counts(
    config: dict[str, Any]
) -> dict[str, dict[str, int]]:
    return {
        partition: {
            str(label): int(count)
            for label, count in config["roster"][
                f"{partition}_class_counts"
            ].items()
        }
        for partition in config["roster"]["partition_order"]
    }


def select_rows(
    rows: list[dict[str, Any]],
    *,
    namespace: str,
    partition_order: list[str],
    class_order: list[str],
    counts: dict[str, dict[str, int]],
) -> dict[str, list[dict[str, Any]]]:
    if partition_order != list(counts):
        raise ValueError("R45 partition order/count registry drift")
    if set(class_order) != set(PROGRESSION_CLASSES):
        raise ValueError("R45 progression class-order drift")
    selected = {partition: [] for partition in partition_order}
    used: set[str] = set()
    for partition in partition_order:
        if set(counts[partition]) != set(PROGRESSION_CLASSES):
            raise ValueError("R45 partition class-count drift")
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
            chosen: list[dict[str, Any]] = []
            for row in candidates:
                patient = str(row["patient_id"])
                if patient in used:
                    continue
                chosen.append(row)
                used.add(patient)
                if len(chosen) == counts[partition][label]:
                    break
            if len(chosen) != counts[partition][label]:
                raise ValueError(
                    f"insufficient R45 support for {partition}/{label}: "
                    f"{len(chosen)} < {counts[partition][label]}"
                )
            selected[partition].extend(chosen)
        selected[partition].sort(
            key=lambda row: stable_key(
                f"{namespace}|{partition}|final", row
            )
        )
    return selected


def selection(
    config: dict[str, Any]
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any], dict]:
    authority = validate_authority(config)
    rows, inventory, indexed = load_image_complete_rows(config, authority)
    selected = select_rows(
        rows,
        namespace=str(config["roster"]["namespace"]),
        partition_order=[
            str(value) for value in config["roster"]["partition_order"]
        ],
        class_order=[
            str(value) for value in config["roster"]["class_order"]
        ],
        counts=partition_counts(config),
    )
    selected_patients = {
        str(row["patient_id"])
        for partition_rows in selected.values()
        for row in partition_rows
    }
    resolved_patients = {
        str(row["patient_id"])
        for row in rows
        if str(row["progression"]) == "Resolved"
    }
    reserve = len(resolved_patients - selected_patients)
    if reserve < int(
        config["roster"]["minimum_unselected_resolved_patient_reserve"]
    ):
        raise ValueError("R45 Resolved reserve is below frozen minimum")
    return selected, inventory, {
        **authority,
        "indexed": indexed,
        "resolved_patient_reserve": reserve,
    }


def _assert_disjoint(selected: dict[str, list[dict[str, Any]]]) -> None:
    seen: set[str] = set()
    for partition, rows in selected.items():
        patients = {str(row["patient_id"]) for row in rows}
        if len(patients) != len(rows):
            raise PermissionError(f"R45 duplicate patient in {partition}")
        if patients & seen:
            raise PermissionError("R45 selected partitions overlap")
        seen.update(patients)


def preflight(config_path: Path) -> dict[str, Any]:
    config = read_json(config_path)
    selected, inventory, authority = selection(config)
    _assert_disjoint(selected)
    return {
        "schema": "visualvit.prta-gen.r45-cdeb-roster-preflight.v1",
        "status": config["result_statuses"]["preflight_pass"],
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
        "qualification_outcomes_read": False,
        "confirmation_outcomes_read": False,
        "protected_300_dev_read": False,
        "revealed_483_test_read": False,
        "gold_outcomes_read": False,
        "external_outcomes_read": False,
        "scientific_claim_allowed": False,
    }


def build_roster(config_path: Path, output_path: Path) -> dict[str, Any]:
    if output_path.exists():
        raise FileExistsError(f"R45 roster output must be fresh: {output_path}")
    config = read_json(config_path)
    selected, inventory, authority = selection(config)
    _assert_disjoint(selected)
    root = authority["image_root"]
    partitions: dict[str, Any] = {}
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
        partitions[partition] = {
            "rows": serialized,
            "row_count": len(serialized),
            "patient_count": len(
                {str(row["patient_id"]) for row in serialized}
            ),
            "progression_class_counts": dict(
                sorted(Counter(row["progression"] for row in serialized).items())
            ),
        }
    counts = partition_counts(config)
    for partition, expected_counts in counts.items():
        payload = partitions[partition]
        expected = int(config["roster"][f"{partition}_patients"])
        if (
            payload["row_count"] != expected
            or payload["patient_count"] != expected
            or payload["progression_class_counts"]
            != dict(sorted(expected_counts.items()))
        ):
            raise ValueError(f"R45 {partition} roster drift")
    result = {
        "schema": "visualvit.prta-gen.r45-cdeb-roster.v1",
        "status": config["result_statuses"]["roster_pass"],
        "protocol_id": config["protocol_id"],
        "namespace": config["roster"]["namespace"],
        "assignment": config["roster"]["assignment"],
        "partitions": partitions,
        "inventory": inventory,
        "excluded_r44a_patient_count": len(authority["r44_patients"]),
        "excluded_r44a_patients_absent": True,
        "excluded_gold_patients_absent": True,
        "resolved_patient_reserve": authority[
            "resolved_patient_reserve"
        ],
        "patient_sets_disjoint": True,
        "one_row_per_patient": True,
        "selected_images_complete": True,
        "resplit_allowed": False,
        "development_outcomes_read": False,
        "qualification_outcomes_read": False,
        "confirmation_outcomes_read": False,
        "r44a_outcomes_used_for_roster_selection": False,
        "protected_300_dev_read": False,
        "revealed_483_test_read": False,
        "gold_outcomes_read": False,
        "external_outcomes_read": False,
        "scientific_claim_allowed": False,
    }
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
        description="Preflight or build the frozen R45 CDEB patient roster"
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.preflight_only:
        if args.output is not None:
            raise ValueError("R45 preflight must not receive --output")
        result = preflight(args.config)
    else:
        if args.output is None:
            raise ValueError("R45 roster build requires --output")
        result = build_roster(args.config, args.output)
    print(json.dumps(receipt_summary(result), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
