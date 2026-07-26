from __future__ import annotations

# ruff: noqa: E402

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any, Iterable
import zipfile

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE))
sys.path.insert(0, str(WORKSPACE / "src"))

import pandas as pd

from scripts import audit_r26_binding_identifiability as r27


LABELS = ("Stable", "Improved", "Worse")
ACTIVE_COUNTS = {"train": 700, "dev": 200, "test": 300}
ROW_CAP = 12
SILVER_ROOT = Path(
    r"F:\VisualVIT_runtime\050_routeC\r29_contextual_transition"
    r"\inputs_81fd9cdd"
)
FINDINGS_PATH = SILVER_ROOT / "silver_findings.parquet"
STUDIES_PATH = SILVER_ROOT / "silver_studies.parquet"
FINDINGS_SHA256 = (
    "31237f859d940d6b03748c845ec7c1c791b1837ba6e46e88e69bca7f45e3c807"
)
STUDIES_SHA256 = (
    "b53e5a491850e5d839158847efcdae6ca840bef0070ed9598fd2021e0fc148a2"
)
CI_ROOT = Path(
    r"F:\VisualVIT_runtime\050_routeC\data\chest_imagenome"
    r"\chest-imagenome-dataset-1.0.0"
)
SCENE_ZIP = CI_ROOT / "silver_dataset" / "scene_graph.zip"
MIMIC_METADATA = Path(
    r"H:\Xiyao_Wang\000_Public Dataset\mimic_cxr_other"
    r"\mimic-cxr-2.0.0-metadata.csv.gz"
)
IMAGE_ROOT = Path(
    r"H:\Xiyao_Wang\000_Public Dataset\mimic-cxr\mimic-cxr"
    r"\mimic-cxr-images\files"
)
OUTPUT_ROOT_DEFAULT = Path(
    r"F:\VisualVIT_runtime\050_routeC\r29_contextual_transition\cohort_v1_1"
)
PROTOCOL_PATH = (
    WORKSPACE
    / "docs/superpowers/specs/2026-07-26-r29-fresh-silver-context-repair-v1.1.md"
)
PROTOCOL_SHA256 = (
    "e2e1f00f2ba66dcf11fd8583e0818b87496a213f8db3877f41c0967403450be8"
)
EXCLUSION_PATHS = {
    "r24_mimic": (
        WORKSPACE
        / "artifacts/real_qualification/chextemporal_mimic_matcher_v3"
        / "process_a/cohort.json"
    ),
    "r25": (
        WORKSPACE
        / "artifacts/r25_1_semantic_repair/manifests/pair_manifest.json"
    ),
    "r26": Path(
        r"F:\VisualVIT_runtime\050_routeC\r26_c1_oracle_binding"
        r"\run_v1\cohort.json"
    ),
}


def stable_hash(*parts: object) -> str:
    payload = "|".join(str(part) for part in parts).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def numeric_patient(value: object) -> str:
    result = re.sub(r"\D", "", str(value))
    if not result:
        raise ValueError(f"patient id has no numeric component: {value}")
    return result


def dicom_from_parent(path: str) -> str:
    return Path(path).stem


def scene_name(dicom_id: str) -> str:
    return f"scene_graph/{dicom_id}_SceneGraph.json"


def load_excluded_patients() -> tuple[set[str], dict[str, Any]]:
    excluded: set[str] = set()
    audit = {}
    for name, path in EXCLUSION_PATHS.items():
        rows = r27.read_json(path, list)
        patients = {numeric_patient(row["patient_id"]) for row in rows}
        excluded.update(patients)
        audit[name] = {
            "path": str(path),
            "sha256": r27.sha256_file(path),
            "patients": len(patients),
        }
    audit["union_patients"] = len(excluded)
    return excluded, audit


def choose_partitions(patients: Iterable[str]) -> dict[str, str]:
    ordered = sorted(
        patients, key=lambda value: stable_hash("r29-patient-v1", value)
    )
    assignment = {}
    offset = 0
    for split, count in ACTIVE_COUNTS.items():
        for patient in ordered[offset : offset + count]:
            assignment[patient] = split
        offset += count
    for patient in ordered[offset:]:
        assignment[patient] = "sealed_reserve"
    return assignment


def select_rows(frame: pd.DataFrame) -> pd.DataFrame:
    rows = frame.copy()
    rows["row_hash"] = rows.apply(
        lambda row: stable_hash(
            "r29-row-v1",
            row["patient_id"],
            row["study_id_prev"],
            row["study_id_curr"],
            row["finding_token"],
            row["anatomy"],
        ),
        axis=1,
    )
    rows = rows.sort_values(["patient_id", "row_hash"], kind="stable")
    active = rows[rows["partition"].ne("sealed_reserve")]
    active = active.groupby("patient_id", sort=False).head(ROW_CAP)
    reserve = rows[rows["partition"].eq("sealed_reserve")]
    return pd.concat((active, reserve), ignore_index=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build frozen R29 silver cohort")
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT_DEFAULT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.output_root.exists():
        raise FileExistsError(f"output root must be fresh: {args.output_root}")
    if r27.sha256_file(FINDINGS_PATH) != FINDINGS_SHA256:
        raise RuntimeError("silver findings hash mismatch")
    if r27.sha256_file(STUDIES_PATH) != STUDIES_SHA256:
        raise RuntimeError("silver studies hash mismatch")
    if r27.sha256_file(PROTOCOL_PATH) != PROTOCOL_SHA256:
        raise RuntimeError("R29 protocol hash mismatch")

    excluded, exclusion_audit = load_excluded_patients()
    frame = pd.read_parquet(FINDINGS_PATH)
    frame = frame[
        frame["dataset"].eq("mimic") & frame["progression"].isin(LABELS)
    ].copy()
    frame["subject_num"] = frame["patient_id"].map(numeric_patient)
    frame = frame[~frame["subject_num"].isin(excluded)].copy()

    metadata = pd.read_csv(
        MIMIC_METADATA,
        usecols=["dicom_id", "subject_id", "study_id", "ViewPosition"],
    )
    metadata["dicom_id"] = metadata["dicom_id"].astype(str)
    metadata_index = metadata.set_index("dicom_id").to_dict("index")
    with zipfile.ZipFile(SCENE_ZIP) as archive:
        scene_names = set(archive.namelist())

    frame["prior_dicom_id"] = frame["parent_image_prev"].map(dicom_from_parent)
    frame["current_dicom_id"] = frame["parent_image_curr"].map(dicom_from_parent)
    complete = (
        frame["prior_dicom_id"].isin(metadata_index)
        & frame["current_dicom_id"].isin(metadata_index)
        & frame["prior_dicom_id"].map(scene_name).isin(scene_names)
        & frame["current_dicom_id"].map(scene_name).isin(scene_names)
    )
    frame = frame[complete].copy()
    assignment = choose_partitions(frame["patient_id"].unique())
    frame["partition"] = frame["patient_id"].map(assignment)
    frame = select_rows(frame)

    records = []
    for row in frame.itertuples(index=False):
        prior_meta = metadata_index[row.prior_dicom_id]
        current_meta = metadata_index[row.current_dicom_id]
        if str(prior_meta["subject_id"]) != row.subject_num:
            raise RuntimeError("prior subject mismatch")
        if str(current_meta["subject_id"]) != row.subject_num:
            raise RuntimeError("current subject mismatch")
        records.append(
            {
                "record_id": stable_hash(
                    "r29-record-v1",
                    row.patient_id,
                    row.study_id_prev,
                    row.study_id_curr,
                    row.finding_token,
                    row.anatomy,
                ),
                "patient_id": row.patient_id,
                "subject_id": row.subject_num,
                "partition": row.partition,
                "prior_study_id": str(row.study_id_prev).replace("study", ""),
                "current_study_id": str(row.study_id_curr).replace("study", ""),
                "prior_dicom_id": row.prior_dicom_id,
                "current_dicom_id": row.current_dicom_id,
                "prior_path": str(
                    IMAGE_ROOT / Path(row.parent_image_prev).relative_to("mimic")
                ),
                "current_path": str(
                    IMAGE_ROOT / Path(row.parent_image_curr).relative_to("mimic")
                ),
                "prior_scene": scene_name(row.prior_dicom_id),
                "current_scene": scene_name(row.current_dicom_id),
                "finding_token": str(row.finding_token).lower(),
                "finding": str(row.finding),
                "anatomy": str(row.anatomy),
                "progression": str(row.progression),
                "prior_view": str(prior_meta["ViewPosition"]),
                "current_view": str(current_meta["ViewPosition"]),
            }
        )

    active = [row for row in records if row["partition"] != "sealed_reserve"]
    patient_sets = {
        split: {row["patient_id"] for row in records if row["partition"] == split}
        for split in (*ACTIVE_COUNTS, "sealed_reserve")
    }
    if any(
        patient_sets[left] & patient_sets[right]
        for left in patient_sets
        for right in patient_sets
        if left < right
    ):
        raise RuntimeError("R29 partitions are not patient-disjoint")
    if {numeric_patient(row["patient_id"]) for row in active} & excluded:
        raise RuntimeError("prior patient leaked into R29 active cohort")
    missing_images = [
        row["record_id"]
        for row in active
        if not Path(row["prior_path"]).is_file()
        or not Path(row["current_path"]).is_file()
    ]
    if missing_images:
        raise RuntimeError(f"active cohort has missing images: {len(missing_images)}")

    args.output_root.mkdir(parents=True, exist_ok=False)
    r27.write_json_exclusive(args.output_root / "cohort.json", records)
    audit = {
        "protocol": {
            "path": str(PROTOCOL_PATH),
            "sha256": PROTOCOL_SHA256,
        },
        "inputs": {
            "silver_findings": {
                "path": str(FINDINGS_PATH),
                "sha256": FINDINGS_SHA256,
            },
            "silver_studies": {
                "path": str(STUDIES_PATH),
                "sha256": STUDIES_SHA256,
            },
            "scene_zip": {
                "path": str(SCENE_ZIP),
                "sha256": r27.sha256_file(SCENE_ZIP),
            },
            "metadata": {
                "path": str(MIMIC_METADATA),
                "sha256": r27.sha256_file(MIMIC_METADATA),
            },
        },
        "exclusions": exclusion_audit,
        "row_cap": ROW_CAP,
        "partition_patient_counts": {
            split: len(patients) for split, patients in patient_sets.items()
        },
        "partition_row_counts": {
            split: sum(row["partition"] == split for row in records)
            for split in patient_sets
        },
        "partition_label_counts": {
            split: {
                label: sum(
                    row["partition"] == split and row["progression"] == label
                    for row in records
                )
                for label in LABELS
            }
            for split in patient_sets
        },
        "active_records": len(active),
        "active_patients": len(
            {row["patient_id"] for row in active}
        ),
        "patient_disjoint": True,
        "prior_patient_overlap": 0,
        "missing_images": 0,
    }
    r27.write_json_exclusive(args.output_root / "cohort_audit.json", audit)
    manifest_base = {
        "status": "PASS_R29_FRESH_COHORT_FREEZE",
        "cohort_sha256": r27.sha256_file(args.output_root / "cohort.json"),
        "audit_sha256": r27.sha256_file(args.output_root / "cohort_audit.json"),
        "builder_sha256": r27.sha256_file(Path(__file__)),
        "protocol_sha256": audit["protocol"]["sha256"],
    }
    manifest = dict(manifest_base)
    manifest["manifest_payload_sha256"] = r27.canonical_sha256(manifest_base)
    r27.write_json_exclusive(args.output_root / "artifact_manifest.json", manifest)
    print(json.dumps({"manifest": manifest, "audit": audit}, indent=2))


if __name__ == "__main__":
    main()
