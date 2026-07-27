from __future__ import annotations

# ruff: noqa: E402

import argparse
from collections import Counter
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Iterable

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE / "src"))

import pandas as pd

from visualvit.gold_quarantine import normalize_patient_id


SCHEMA = "visualvit.r37.longitudinal-pair.v1"
REGISTRY_SCHEMA = "visualvit.r37.forbidden-patients.v1"
AUDIT_SCHEMA = "visualvit.r37.data-audit.v1"
EXPECTED_R32_PATIENTS = {
    "r32_train": 1574,
    "r32_dev": 300,
    "r32_sealed_vlm_test": 483,
}
PAIR_FLOOR = 30_000
BLOCK8_TOKENS_PER_IMAGE = 197
BLOCK8_WIDTH = 768
FP16_BYTES = 2


def stable_hash(*parts: object) -> str:
    return hashlib.sha256(
        "|".join(str(part) for part in parts).encode("utf-8")
    ).hexdigest()


def patient_partition(subject_id: str) -> str:
    score = int(stable_hash("r37-patient-split-v1", subject_id), 16) % 10
    return "internal_calibration" if score == 0 else "pretrain"


def mimic_patient_id(value: object) -> str:
    digits = "".join(character for character in str(value) if character.isdigit())
    if not digits:
        raise ValueError(f"patient identifier has no digits: {value!r}")
    return normalize_patient_id(f"p{int(digits)}")


def image_path(
    root: Path, subject_id: object, study_id: object, dicom_id: object
) -> Path:
    subject = str(int(subject_id))
    study = str(int(study_id))
    return (
        root
        / f"p{subject[:2]}"
        / f"p{subject}"
        / f"s{study}"
        / f"{dicom_id}.jpg"
    )


def report_path(root: Path, subject_id: object, study_id: object) -> Path:
    subject = str(int(subject_id))
    study = str(int(study_id))
    return root / f"p{subject[:2]}" / f"p{subject}" / f"s{study}.txt"


def _load_json(path: Path) -> Any:
    if path.name == "sealed_vlm_test_labels.json":
        raise ValueError("R37 must never open sealed_vlm_test_labels.json")
    return json.loads(path.read_text(encoding="utf-8"))


def build_forbidden_registry(
    *,
    train_dev_path: Path,
    sealed_manifest_path: Path,
    gold_manifest_path: Path,
) -> tuple[dict[str, Any], set[str]]:
    train_dev = _load_json(train_dev_path)
    sealed = _load_json(sealed_manifest_path)
    gold = _load_json(gold_manifest_path)

    sources: dict[str, set[str]] = {
        "r32_train": set(),
        "r32_dev": set(),
        "r32_sealed_vlm_test": set(),
        "gold_quarantine": set(),
    }
    for row in train_dev:
        partition = str(row.get("partition", ""))
        if partition not in {"train", "dev"}:
            raise ValueError(f"unexpected R32 train/dev partition: {partition}")
        sources[f"r32_{partition}"].add(
            normalize_patient_id(str(row["patient_id"]))
        )
    for row in sealed:
        if str(row.get("partition")) != "sealed_vlm_test":
            raise ValueError("sealed manifest contains a non-sealed partition")
        sources["r32_sealed_vlm_test"].add(
            normalize_patient_id(str(row["patient_id"]))
        )
    for value in gold.get("patient_ids", []):
        sources["gold_quarantine"].add(normalize_patient_id(str(value)))

    observed = {name: len(sources[name]) for name in EXPECTED_R32_PATIENTS}
    if observed != EXPECTED_R32_PATIENTS:
        raise RuntimeError(
            f"protected R32 patient-count drift: {observed} != "
            f"{EXPECTED_R32_PATIENTS}"
        )
    r32_names = list(EXPECTED_R32_PATIENTS)
    r32_overlap = sum(
        len(sources[r32_names[left]] & sources[r32_names[right]])
        for left in range(len(r32_names))
        for right in range(left + 1, len(r32_names))
    )
    if r32_overlap:
        raise RuntimeError(f"R32 protected partitions overlap: {r32_overlap}")

    forbidden = set().union(*sources.values())
    registry = {
        "schema": REGISTRY_SCHEMA,
        "status": "PASS_R37_FORBIDDEN_REGISTRY",
        "purpose": "patient exclusion only; no protected outcome access",
        "outcome_fields_read": [],
        "sealed_label_file_opened": False,
        "sources": {
            name: {
                "patient_count": len(values),
                "patient_ids": sorted(values),
            }
            for name, values in sources.items()
        },
        "r32_cross_partition_overlap": r32_overlap,
        "union_patient_count": len(forbidden),
        "patient_ids": sorted(forbidden),
    }
    return registry, forbidden


def select_one_frontal_per_study(
    metadata: pd.DataFrame, official_split: pd.DataFrame
) -> pd.DataFrame:
    merged = metadata.merge(
        official_split,
        on=["dicom_id", "study_id", "subject_id"],
        how="inner",
        validate="one_to_one",
    )
    if int(merged.groupby("subject_id")["split"].nunique().max()) != 1:
        raise ValueError("official MIMIC split leaks patients across partitions")
    merged = merged[merged["split"].eq("train")].copy()
    merged["ViewPosition"] = (
        merged["ViewPosition"].fillna("").astype(str).str.upper()
    )
    merged = merged[merged["ViewPosition"].isin(("PA", "AP"))].copy()
    merged["view_rank"] = merged["ViewPosition"].map({"PA": 0, "AP": 1})
    return (
        merged.sort_values(
            ["subject_id", "study_id", "view_rank", "dicom_id"]
        )
        .drop_duplicates(["subject_id", "study_id"])
        .drop(columns=["view_rank"])
    )


def build_pair_records(
    studies: pd.DataFrame,
    *,
    forbidden_patients: set[str],
    image_root: Path,
    report_root: Path,
    check_paths: bool,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    working = studies.copy()
    working["patient_id"] = working["subject_id"].map(mimic_patient_id)
    excluded_rows = int(working["patient_id"].isin(forbidden_patients).sum())
    working = working[~working["patient_id"].isin(forbidden_patients)].copy()
    working["StudyDate"] = pd.to_numeric(
        working["StudyDate"], errors="coerce"
    ).astype("Int64")
    working["StudyTime"] = pd.to_numeric(
        working["StudyTime"], errors="coerce"
    ).fillna(0)
    working = working.dropna(subset=["StudyDate"])
    working = working.sort_values(
        ["subject_id", "StudyDate", "StudyTime", "study_id", "dicom_id"]
    )

    records: list[dict[str, Any]] = []
    missing_images = 0
    missing_reports = 0
    same_date_pairs = 0
    for subject_id, group in working.groupby("subject_id", sort=False):
        rows = group.to_dict("records")
        for prior, current in zip(rows[:-1], rows[1:]):
            prior_date = datetime.strptime(
                str(int(prior["StudyDate"])), "%Y%m%d"
            ).date()
            current_date = datetime.strptime(
                str(int(current["StudyDate"])), "%Y%m%d"
            ).date()
            interval_days = (current_date - prior_date).days
            if interval_days <= 0:
                same_date_pairs += 1
                continue
            prior_image = image_path(
                image_root,
                subject_id,
                prior["study_id"],
                prior["dicom_id"],
            )
            current_image = image_path(
                image_root,
                subject_id,
                current["study_id"],
                current["dicom_id"],
            )
            prior_report = report_path(
                report_root, subject_id, prior["study_id"]
            )
            current_report = report_path(
                report_root, subject_id, current["study_id"]
            )
            if check_paths:
                image_missing = not prior_image.is_file() or not current_image.is_file()
                report_missing = (
                    not prior_report.is_file() or not current_report.is_file()
                )
                if image_missing:
                    missing_images += 1
                if report_missing:
                    missing_reports += 1
                if image_missing or report_missing:
                    continue
            patient_id = mimic_patient_id(subject_id)
            pair_id = stable_hash(
                "r37-longitudinal-pair-v1",
                patient_id,
                prior["study_id"],
                current["study_id"],
                prior["dicom_id"],
                current["dicom_id"],
            )
            records.append(
                {
                    "schema": SCHEMA,
                    "pair_id": pair_id,
                    "subject_id": str(int(subject_id)),
                    "patient_id": patient_id,
                    "partition": patient_partition(patient_id),
                    "official_split": "train",
                    "prior_study_id": str(int(prior["study_id"])),
                    "current_study_id": str(int(current["study_id"])),
                    "prior_dicom_id": str(prior["dicom_id"]),
                    "current_dicom_id": str(current["dicom_id"]),
                    "prior_date": prior_date.isoformat(),
                    "current_date": current_date.isoformat(),
                    "interval_days": interval_days,
                    "prior_view": str(prior["ViewPosition"]),
                    "current_view": str(current["ViewPosition"]),
                    "prior_path": str(prior_image),
                    "current_path": str(current_image),
                    "prior_report_path": str(prior_report),
                    "current_report_path": str(current_report),
                    "transition_supervision_status": "pending_r37_extraction",
                }
            )
    records.sort(key=lambda row: (row["partition"], row["patient_id"], row["pair_id"]))
    diagnostics = {
        "excluded_frontal_study_rows": excluded_rows,
        "same_or_nonpositive_date_pairs": same_date_pairs,
        "pairs_with_missing_images": missing_images,
        "pairs_with_missing_reports": missing_reports,
    }
    return records, diagnostics


def cross_partition_overlap(
    records: Iterable[dict[str, Any]], field: str
) -> int:
    values: dict[str, set[str]] = {
        "pretrain": set(),
        "internal_calibration": set(),
    }
    for row in records:
        values[str(row["partition"])].add(str(row[field]))
    return len(values["pretrain"] & values["internal_calibration"])


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False),
        encoding="utf-8",
    )


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(
                json.dumps(
                    row, sort_keys=True, ensure_ascii=False, separators=(",", ":")
                )
                + "\n"
            )


def parse_args() -> argparse.Namespace:
    r32 = Path(r"F:\VisualVIT_runtime\050_routeC\r32_tier_cxr_vlm\cohort_v1")
    mimic = Path(r"H:\Xiyao_Wang\000_Public Dataset")
    parser = argparse.ArgumentParser(
        description="Build outcome-firewalled R37 longitudinal manifests"
    )
    parser.add_argument(
        "--metadata",
        type=Path,
        default=mimic / "mimic_cxr_other/mimic-cxr-2.0.0-metadata.csv.gz",
    )
    parser.add_argument(
        "--official-split",
        type=Path,
        default=mimic / "mimic_cxr_other/mimic-cxr-2.0.0-split.csv.gz",
    )
    parser.add_argument(
        "--train-dev",
        type=Path,
        default=r32 / "train_dev_cohort.json",
    )
    parser.add_argument(
        "--sealed-manifest",
        type=Path,
        default=r32 / "sealed_vlm_test_manifest.json",
    )
    parser.add_argument(
        "--gold-manifest",
        type=Path,
        default=r32 / "gold_quarantine_manifest.json",
    )
    parser.add_argument(
        "--image-root",
        type=Path,
        default=mimic / "mimic-cxr/mimic-cxr/mimic-cxr-images/files",
    )
    parser.add_argument(
        "--report-root",
        type=Path,
        default=mimic / "mimic-cxr/mimic-cxr/mimic-cxr-reports/files",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path(
            r"H:\VisualVIT_runtime\050_routeD\r37_prta_cxr\r37a_data_v1"
        ),
    )
    parser.add_argument(
        "--skip-path-check",
        action="store_true",
        help="diagnostic only; formal R37A must not use this flag",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.output_root.exists():
        raise FileExistsError(f"output root must be fresh: {args.output_root}")
    for path in (
        args.metadata,
        args.official_split,
        args.train_dev,
        args.sealed_manifest,
        args.gold_manifest,
    ):
        if not path.is_file():
            raise FileNotFoundError(path)
    for path in (args.image_root, args.report_root):
        if not path.is_dir():
            raise FileNotFoundError(path)

    registry, forbidden = build_forbidden_registry(
        train_dev_path=args.train_dev,
        sealed_manifest_path=args.sealed_manifest,
        gold_manifest_path=args.gold_manifest,
    )
    metadata = pd.read_csv(
        args.metadata,
        usecols=[
            "dicom_id",
            "subject_id",
            "study_id",
            "ViewPosition",
            "StudyDate",
            "StudyTime",
        ],
        dtype={"dicom_id": str, "subject_id": str, "study_id": str},
    )
    official_split = pd.read_csv(
        args.official_split,
        dtype={"dicom_id": str, "subject_id": str, "study_id": str},
    )
    studies = select_one_frontal_per_study(metadata, official_split)
    records, diagnostics = build_pair_records(
        studies,
        forbidden_patients=forbidden,
        image_root=args.image_root,
        report_root=args.report_root,
        check_paths=not args.skip_path_check,
    )
    partitions = {
        name: [row for row in records if row["partition"] == name]
        for name in ("pretrain", "internal_calibration")
    }
    patient_counts = {
        name: len({row["patient_id"] for row in rows})
        for name, rows in partitions.items()
    }
    unique_images = {
        str(row[field])
        for row in records
        for field in ("prior_dicom_id", "current_dicom_id")
    }
    active_patients = {str(row["patient_id"]) for row in records}
    checks = {
        "official_train_only": all(
            row["official_split"] == "train" for row in records
        ),
        "forbidden_patient_overlap_zero": not (active_patients & forbidden),
        "patient_partition_overlap_zero": (
            cross_partition_overlap(records, "patient_id") == 0
        ),
        "study_partition_overlap_zero": (
            cross_partition_overlap(records, "prior_study_id") == 0
            and cross_partition_overlap(records, "current_study_id") == 0
        ),
        "image_partition_overlap_zero": (
            cross_partition_overlap(records, "prior_dicom_id") == 0
            and cross_partition_overlap(records, "current_dicom_id") == 0
        ),
        "positive_intervals_only": all(row["interval_days"] > 0 for row in records),
        "path_checks_enabled": not args.skip_path_check,
        "all_selected_paths_exist": (
            diagnostics["pairs_with_missing_images"] == 0
            and diagnostics["pairs_with_missing_reports"] == 0
        ),
        "pair_floor_met": len(records) >= PAIR_FLOOR,
        "protected_outcomes_not_read": True,
        "sealed_label_file_not_opened": True,
    }
    structural_pass = all(
        value
        for name, value in checks.items()
        if name
        not in {
            "pair_floor_met",
            "all_selected_paths_exist",
        }
    )
    status = (
        "PASS_R37A_STRUCTURAL_COHORT"
        if structural_pass and checks["pair_floor_met"]
        else "STOP_R37A_DATA_SUPPORT"
    )
    cache_bytes = (
        len(unique_images)
        * BLOCK8_TOKENS_PER_IMAGE
        * BLOCK8_WIDTH
        * FP16_BYTES
    )
    audit = {
        "schema": AUDIT_SCHEMA,
        "status": status,
        "protocol": str(
            WORKSPACE
            / "docs/superpowers/specs/2026-07-27-r37-prta-cxr-protocol-v1.md"
        ),
        "lightweight_provenance": True,
        "source_hashes_recomputed": False,
        "protected_outcomes_read": False,
        "sealed_label_file_opened": False,
        "forbidden_union_patient_count": len(forbidden),
        "eligible_pair_count": len(records),
        "partition_pair_counts": {
            name: len(rows) for name, rows in partitions.items()
        },
        "partition_patient_counts": patient_counts,
        "unique_image_count": len(unique_images),
        "estimated_block8_fp16_bytes": cache_bytes,
        "estimated_block8_fp16_gib": cache_bytes / 1024**3,
        "view_pair_counts": dict(
            Counter(
                f"{row['prior_view']}->{row['current_view']}" for row in records
            )
        ),
        "interval_days": {
            "minimum": min((row["interval_days"] for row in records), default=None),
            "median": (
                float(pd.Series([row["interval_days"] for row in records]).median())
                if records
                else None
            ),
            "maximum": max((row["interval_days"] for row in records), default=None),
        },
        "diagnostics": diagnostics,
        "checks": checks,
        "remaining_gates": [
            "transition extraction case-study quality",
            "five-class directional patient support",
            "Block-8 cache reproducibility",
            "CMCP coverage >= 90% of dynamic rows",
        ],
    }

    args.output_root.mkdir(parents=True, exist_ok=False)
    write_json(
        args.output_root / "r37_forbidden_patient_registry.json", registry
    )
    write_jsonl(
        args.output_root / "r37_pretrain_manifest.jsonl",
        partitions["pretrain"],
    )
    write_jsonl(
        args.output_root / "r37_internal_calibration_manifest.jsonl",
        partitions["internal_calibration"],
    )
    write_json(args.output_root / "r37_data_audit.json", audit)
    print(json.dumps(audit, indent=2, sort_keys=True))
    print(f"RESULT_DIR={args.output_root}")
    return 0 if status == "PASS_R37A_STRUCTURAL_COHORT" else 2


if __name__ == "__main__":
    raise SystemExit(main())
