from __future__ import annotations

# ruff: noqa: E402

import argparse
from collections import Counter
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from typing import Any, Iterable

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE))
sys.path.insert(0, str(WORKSPACE / "src"))

import pandas as pd

from visualvit.gold_quarantine import (
    GoldAccessEvent,
    append_access_event,
    canonical_manifest,
    normalize_patient_id,
)


LABELS = ("Stable", "Improved", "Worse", "New", "Resolved")
MASTER_PATIENT_COUNT = 2383
EXPECTED_GOLD_QUARANTINE_OVERLAP = 26
SPLIT_COUNTS = {"train": 1574, "dev": 300, "sealed_vlm_test": 483}
MIN_LABEL_PATIENTS = {"train": 100, "dev": 25, "sealed_vlm_test": 25}
R31_COHORT = Path(
    r"F:\VisualVIT_runtime\050_routeC\r31_confidence_consensus"
    r"\cohort_v1\cohort.json"
)
SILVER_FINDINGS = Path(
    r"F:\VisualVIT_runtime\050_routeC\r29_contextual_transition"
    r"\inputs_81fd9cdd\silver_findings.parquet"
)
MIMIC_METADATA = Path(
    r"H:\Xiyao_Wang\000_Public Dataset\mimic_cxr_other"
    r"\mimic-cxr-2.0.0-metadata.csv.gz"
)
IMAGE_ROOT = Path(
    r"H:\Xiyao_Wang\000_Public Dataset\mimic-cxr\mimic-cxr"
    r"\mimic-cxr-images\files"
)
OFFICIAL_GOLD = (
    WORKSPACE
    / "data/official/chextemporal_81fd9cdd/gold_progression_pairs.parquet"
)
OFFICIAL_GOLD_BBOX = (
    WORKSPACE / "data/official/chextemporal_81fd9cdd/gold_bboxes.parquet"
)
CI_GOLD_ROOT = Path(
    r"F:\VisualVIT_runtime\050_routeC\data\chest_imagenome"
    r"\chest-imagenome-dataset-1.0.0\gold_dataset"
)
CI_GOLD_FILES = (
    CI_GOLD_ROOT / "gold_object_comparison_with_coordinates.txt",
    CI_GOLD_ROOT / "gold_object_attribute_with_coordinates.txt",
)
PROTOCOL_PATH = (
    WORKSPACE
    / "docs/superpowers/specs/2026-07-26-r32-tier-cxr-vlm-protocol-v1.1.md"
)
OUTPUT_ROOT_DEFAULT = Path(
    r"F:\VisualVIT_runtime\050_routeC\r32_tier_cxr_vlm\cohort_v1"
)


def stable_hash(*parts: object) -> str:
    return hashlib.sha256(
        "|".join(str(part) for part in parts).encode("utf-8")
    ).hexdigest()


def canonical_sha256(value: Any) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def assign_patients(patients: Iterable[str]) -> dict[str, str]:
    ordered = sorted(
        {normalize_patient_id(patient) for patient in patients},
        key=lambda value: stable_hash("r32-tier-patient-v1", value),
    )
    if len(ordered) != sum(SPLIT_COUNTS.values()):
        raise ValueError(
            f"R32 requires exactly {sum(SPLIT_COUNTS.values())} patients; "
            f"got {len(ordered)}"
        )
    result = {}
    offset = 0
    for split, count in SPLIT_COUNTS.items():
        for patient in ordered[offset : offset + count]:
            result[patient] = split
        offset += count
    return result


def _read_tsv_patient_ids(path: Path) -> set[str]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if reader.fieldnames is None or "patient_id" not in reader.fieldnames:
            raise ValueError(f"{path} has no patient_id column")
        return {
            normalize_patient_id(row["patient_id"])
            for row in reader
            if row.get("patient_id")
        }


def build_gold_quarantine(
    access_log: Path,
) -> tuple[dict[str, object], dict[str, set[str]]]:
    official = pd.concat(
        (
            pd.read_parquet(OFFICIAL_GOLD, columns=["dataset", "patient_id"]),
            pd.read_parquet(
                OFFICIAL_GOLD_BBOX, columns=["dataset", "patient_id"]
            ),
        ),
        ignore_index=True,
    ).drop_duplicates()
    append_access_event(
        access_log,
        GoldAccessEvent(
            source="chextemporal_official_gold",
            fields=("dataset", "patient_id"),
            purpose="R32 patient quarantine",
            row_count=len(official),
        ),
    )
    source_to_patients: dict[str, set[str]] = {}
    for dataset, group in official.groupby("dataset"):
        source_to_patients[f"chextemporal_{dataset}"] = {
            normalize_patient_id(value) for value in group["patient_id"]
        }

    ci_patients = set()
    for path in CI_GOLD_FILES:
        current = _read_tsv_patient_ids(path)
        ci_patients.update(current)
        append_access_event(
            access_log,
            GoldAccessEvent(
                source=f"chest_imagenome:{path.name}",
                fields=("patient_id",),
                purpose="R32 patient quarantine",
                row_count=len(current),
            ),
        )
    source_to_patients["chest_imagenome_mimic"] = ci_patients
    return canonical_manifest(source_to_patients), source_to_patients


def patient_sets(records: list[dict[str, Any]]) -> dict[str, set[str]]:
    return {
        split: {
            str(row["patient_id"])
            for row in records
            if row["partition"] == split
        }
        for split in SPLIT_COUNTS
    }


def cross_split_overlap(
    records: list[dict[str, Any]], field: str
) -> int:
    values = {
        split: {
            str(row[field])
            for row in records
            if row["partition"] == split
        }
        for split in SPLIT_COUNTS
    }
    names = list(values)
    return sum(
        len(values[names[left]] & values[names[right]])
        for left in range(len(names))
        for right in range(left + 1, len(names))
    )


def audit_records(
    records: list[dict[str, Any]],
    *,
    active_gold_overlap: int,
    quarantined_master_patients: int,
    missing_images: int,
) -> dict[str, Any]:
    patients = patient_sets(records)
    label_patients = {
        split: {
            label: len(
                {
                    row["patient_id"]
                    for row in records
                    if row["partition"] == split
                    and row["progression"] == label
                }
            )
            for label in LABELS
        }
        for split in SPLIT_COUNTS
    }
    checks = {
        "exact_patient_counts": {
            split: len(patients[split]) == count
            for split, count in SPLIT_COUNTS.items()
        },
        "patient_overlap": cross_split_overlap(records, "patient_id") == 0,
        "prior_study_overlap": cross_split_overlap(
            records, "prior_study_id"
        )
        == 0,
        "current_study_overlap": cross_split_overlap(
            records, "current_study_id"
        )
        == 0,
        "prior_image_overlap": cross_split_overlap(
            records, "prior_dicom_id"
        )
        == 0,
        "current_image_overlap": cross_split_overlap(
            records, "current_dicom_id"
        )
        == 0,
        "gold_patient_overlap": active_gold_overlap == 0,
        "missing_images": missing_images == 0,
        "five_label_support": {
            split: all(
                label_patients[split][label] >= MIN_LABEL_PATIENTS[split]
                for label in LABELS
            )
            for split in SPLIT_COUNTS
        },
    }
    flat_checks = [
        value
        for item in checks.values()
        for value in (item.values() if isinstance(item, dict) else (item,))
    ]
    return {
        "status": "PASS" if all(flat_checks) else "FAIL",
        "checks": checks,
        "partition_patient_counts": {
            split: len(value) for split, value in patients.items()
        },
        "partition_row_counts": dict(
            Counter(str(row["partition"]) for row in records)
        ),
        "partition_label_row_counts": {
            split: dict(
                Counter(
                    str(row["progression"])
                    for row in records
                    if row["partition"] == split
                )
            )
            for split in SPLIT_COUNTS
        },
        "partition_label_patient_counts": label_patients,
        "minimum_label_patient_support": MIN_LABEL_PATIENTS,
        "active_gold_patient_overlap": active_gold_overlap,
        "quarantined_master_patients": quarantined_master_patients,
        "missing_images": missing_images,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the frozen R32 five-class master cohort"
    )
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT_DEFAULT)
    return parser.parse_args()


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )


def main() -> int:
    args = parse_args()
    if args.output_root.exists():
        raise FileExistsError(f"output root must be fresh: {args.output_root}")
    args.output_root.mkdir(parents=True, exist_ok=False)
    access_log = args.output_root / "gold_access_log.jsonl"
    quarantine, source_to_gold = build_gold_quarantine(access_log)
    _write_json(args.output_root / "gold_quarantine_manifest.json", quarantine)
    (args.output_root / "gold_patient_ids.sha256").write_text(
        str(quarantine["manifest_sha256"]) + "\n", encoding="ascii"
    )

    r31_rows = json.loads(R31_COHORT.read_text(encoding="utf-8"))
    reserve_patients = {
        normalize_patient_id(row["patient_id"])
        for row in r31_rows
        if row["partition"] == "sealed_reserve"
    }
    gold_mimic = (
        source_to_gold.get("chextemporal_mimic", set())
        | source_to_gold.get("chest_imagenome_mimic", set())
    )
    overlap = reserve_patients & gold_mimic
    if len(reserve_patients) != MASTER_PATIENT_COUNT:
        raise RuntimeError(
            f"R31 reserve drift: {len(reserve_patients)} != "
            f"{MASTER_PATIENT_COUNT}"
        )
    if len(overlap) != EXPECTED_GOLD_QUARANTINE_OVERLAP:
        raise RuntimeError(
            f"gold quarantine overlap drift: {len(overlap)} != "
            f"{EXPECTED_GOLD_QUARANTINE_OVERLAP}"
        )
    eligible_patients = reserve_patients - gold_mimic
    assignment = assign_patients(eligible_patients)

    findings = pd.read_parquet(SILVER_FINDINGS)
    findings = findings[
        findings["dataset"].eq("mimic")
        & findings["progression"].isin(LABELS)
        & findings["patient_id"].map(normalize_patient_id).isin(
            eligible_patients
        )
    ].copy()
    findings["patient_id"] = findings["patient_id"].map(normalize_patient_id)
    findings["partition"] = findings["patient_id"].map(assignment)
    findings["prior_dicom_id"] = findings["parent_image_prev"].map(
        lambda value: Path(str(value)).stem
    )
    findings["current_dicom_id"] = findings["parent_image_curr"].map(
        lambda value: Path(str(value)).stem
    )

    metadata = pd.read_csv(
        MIMIC_METADATA,
        usecols=["dicom_id", "subject_id", "study_id", "ViewPosition"],
        dtype={"dicom_id": str, "subject_id": str, "study_id": str},
    )
    metadata_index = metadata.set_index("dicom_id").to_dict("index")
    missing_metadata = ~findings["prior_dicom_id"].isin(metadata_index) | ~findings[
        "current_dicom_id"
    ].isin(metadata_index)
    if bool(missing_metadata.any()):
        raise RuntimeError(
            f"eligible rows with missing MIMIC metadata: "
            f"{int(missing_metadata.sum())}"
        )

    records = []
    for row in findings.itertuples(index=False):
        prior_meta = metadata_index[row.prior_dicom_id]
        current_meta = metadata_index[row.current_dicom_id]
        prior_path = IMAGE_ROOT / Path(row.parent_image_prev).relative_to(
            "mimic"
        )
        current_path = IMAGE_ROOT / Path(row.parent_image_curr).relative_to(
            "mimic"
        )
        records.append(
            {
                "record_id": stable_hash(
                    "r32-tier-record-v1",
                    row.patient_id,
                    row.study_id_prev,
                    row.study_id_curr,
                    row.finding_token,
                    row.anatomy,
                ),
                "patient_id": row.patient_id,
                "subject_id": re.sub(r"\D", "", row.patient_id),
                "partition": row.partition,
                "prior_study_id": str(row.study_id_prev).replace("study", ""),
                "current_study_id": str(row.study_id_curr).replace("study", ""),
                "prior_dicom_id": row.prior_dicom_id,
                "current_dicom_id": row.current_dicom_id,
                "prior_path": str(prior_path),
                "current_path": str(current_path),
                "finding_token": str(row.finding_token).lower(),
                "finding": str(row.finding),
                "anatomy": str(row.anatomy),
                "progression": str(row.progression),
                "prior_view": str(prior_meta["ViewPosition"]),
                "current_view": str(current_meta["ViewPosition"]),
            }
        )
    records.sort(
        key=lambda row: (
            list(SPLIT_COUNTS).index(row["partition"]),
            row["patient_id"],
            row["record_id"],
        )
    )
    unique_paths = {
        str(row[field])
        for row in records
        for field in ("prior_path", "current_path")
    }
    missing_paths = [path for path in unique_paths if not os.path.isfile(path)]
    audit = audit_records(
        records,
        active_gold_overlap=len(
            {str(row["patient_id"]) for row in records} & gold_mimic
        ),
        quarantined_master_patients=len(overlap),
        missing_images=len(missing_paths),
    )

    train_dev = [
        row for row in records if row["partition"] in {"train", "dev"}
    ]
    sealed_manifest = [
        {key: value for key, value in row.items() if key != "progression"}
        for row in records
        if row["partition"] == "sealed_vlm_test"
    ]
    sealed_labels = [
        {
            "record_id": row["record_id"],
            "patient_id": row["patient_id"],
            "progression": row["progression"],
        }
        for row in records
        if row["partition"] == "sealed_vlm_test"
    ]
    _write_json(args.output_root / "train_dev_cohort.json", train_dev)
    _write_json(args.output_root / "sealed_vlm_test_manifest.json", sealed_manifest)
    _write_json(args.output_root / "sealed_vlm_test_labels.json", sealed_labels)
    _write_json(args.output_root / "cohort_audit.json", audit)

    manifest_base = {
        "schema": "visualvit.r32.cohort-manifest.v1",
        "status": (
            "PASS_R32_COHORT_FREEZE"
            if audit["status"] == "PASS"
            else "STOP_R32_COHORT"
        ),
        "protocol": {
            "path": str(PROTOCOL_PATH),
            "sha256": sha256_file(PROTOCOL_PATH),
        },
        "source_lineage": {
            "r31_cohort": str(R31_COHORT),
            "eligible_reserve_patients": len(reserve_patients),
            "gold_quarantined_reserve_patients": len(overlap),
            "post_quarantine_patients": len(eligible_patients),
            "silver_findings": str(SILVER_FINDINGS),
            "dataset_revision": (
                "81fd9cdd9b1208d8f8bd39d7a914c9b72fed8d79"
            ),
        },
        "split_counts": SPLIT_COUNTS,
        "record_counts": {
            "train_dev": len(train_dev),
            "sealed_test_manifest": len(sealed_manifest),
            "sealed_test_labels": len(sealed_labels),
        },
        "sealed_test_revealed": False,
        "gold_outcomes_read": False,
        "formal_predictions_generated": False,
        "lightweight_provenance": True,
    }
    manifest_base["cohort_identifier"] = canonical_sha256(
        {
            "train_dev": train_dev,
            "sealed_manifest": sealed_manifest,
            "sealed_label_count": len(sealed_labels),
        }
    )
    _write_json(args.output_root / "cohort_manifest.json", manifest_base)
    print(
        json.dumps(
            {"manifest": manifest_base, "audit": audit},
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if audit["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
