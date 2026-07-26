from __future__ import annotations

# ruff: noqa: E402

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE))
sys.path.insert(0, str(WORKSPACE / "src"))

from scripts import audit_r26_binding_identifiability as r27
from scripts import build_r29_fresh_silver_cohort as r29


LABELS = r29.LABELS
ACTIVE_COUNTS = {"train": 1500, "dev": 400, "test": 600}
ROW_CAP = 12
R29_COHORT = (
    Path(
        r"F:\VisualVIT_runtime\050_routeC\r29_contextual_transition"
        r"\cohort_v1_1"
    )
    / "cohort.json"
)
R29_COHORT_SHA256 = (
    "0a52d2c84c99c9c3cdc91063b801eb3c0d1304dfa454c16e55c86edbd2197d6e"
)
PROTOCOL_PATH = (
    WORKSPACE
    / "docs/superpowers/specs/2026-07-26-r30-regularized-multiscale-v1.md"
)
PROTOCOL_SHA256 = (
    "3089ec66f1fab4ff06f8ff0f8c3be09db1dde79edbc928ae3632718541bd2d17"
)
OUTPUT_ROOT_DEFAULT = Path(
    r"F:\VisualVIT_runtime\050_routeC\r30_regularized_multiscale\cohort_v1_1"
)


def stable_hash(*parts: object) -> str:
    payload = "|".join(str(part) for part in parts).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build patient-disjoint R30 cohort from R29 sealed reserve"
    )
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT_DEFAULT)
    return parser.parse_args()


def assign_patients(patients: list[str]) -> dict[str, str]:
    ordered = sorted(
        patients, key=lambda value: stable_hash("r30-patient-v1", value)
    )
    result = {}
    offset = 0
    for partition, count in ACTIVE_COUNTS.items():
        for patient in ordered[offset : offset + count]:
            result[patient] = partition
        offset += count
    for patient in ordered[offset:]:
        result[patient] = "sealed_reserve"
    return result


def build_records(source: list[dict[str, Any]]) -> list[dict[str, Any]]:
    reserve = [
        dict(row) for row in source if row["partition"] == "sealed_reserve"
    ]
    by_patient: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in reserve:
        by_patient[str(row["patient_id"])].append(row)
    assignments = assign_patients(list(by_patient))
    output = []
    for patient, rows in by_patient.items():
        partition = assignments[patient]
        ordered = sorted(
            rows,
            key=lambda row: stable_hash("r30-row-v1", row["record_id"]),
        )
        if partition != "sealed_reserve":
            ordered = ordered[:ROW_CAP]
        for row in ordered:
            row["partition"] = partition
            output.append(row)
    partition_order = {
        "train": 0,
        "dev": 1,
        "test": 2,
        "sealed_reserve": 3,
    }
    return sorted(
        output,
        key=lambda row: (
            partition_order[row["partition"]],
            row["patient_id"],
            row["record_id"],
        ),
    )


def audit_records(
    source: list[dict[str, Any]], records: list[dict[str, Any]]
) -> dict[str, Any]:
    prior_active = {
        str(row["patient_id"])
        for row in source
        if row["partition"] != "sealed_reserve"
    }
    partition_patients = {
        partition: {
            str(row["patient_id"])
            for row in records
            if row["partition"] == partition
        }
        for partition in (*ACTIVE_COUNTS, "sealed_reserve")
    }
    active_sets = [partition_patients[name] for name in ACTIVE_COUNTS]
    patient_disjoint = all(
        not (left & right)
        for index, left in enumerate(active_sets)
        for right in active_sets[index + 1 :]
    )
    counts = Counter(row["partition"] for row in records)
    label_counts = {
        partition: dict(
            Counter(
                row["progression"]
                for row in records
                if row["partition"] == partition
            )
        )
        for partition in (*ACTIVE_COUNTS, "sealed_reserve")
    }
    active = [
        row for row in records if row["partition"] != "sealed_reserve"
    ]
    missing = sum(
        not Path(row[f"{side}_path"]).is_file()
        for row in active
        for side in ("prior", "current")
    )
    return {
        "protocol": {
            "path": str(PROTOCOL_PATH),
            "sha256": PROTOCOL_SHA256,
        },
        "r29_source": {
            "path": str(R29_COHORT),
            "sha256": R29_COHORT_SHA256,
            "eligible_reserve_patients": len(
                {
                    row["patient_id"]
                    for row in source
                    if row["partition"] == "sealed_reserve"
                }
            ),
        },
        "row_cap": ROW_CAP,
        "partition_patient_counts": {
            name: len(value) for name, value in partition_patients.items()
        },
        "partition_row_counts": dict(counts),
        "partition_label_counts": label_counts,
        "active_records": len(active),
        "active_patients": len(
            {str(row["patient_id"]) for row in active}
        ),
        "patient_disjoint": patient_disjoint,
        "r29_active_patient_overlap": len(
            prior_active
            & {str(row["patient_id"]) for row in active}
        ),
        "missing_images": missing,
    }


def main() -> None:
    args = parse_args()
    if args.output_root.exists():
        raise FileExistsError(f"output root must be fresh: {args.output_root}")
    if r27.sha256_file(R29_COHORT) != R29_COHORT_SHA256:
        raise RuntimeError("R29 cohort hash mismatch")
    if r27.sha256_file(PROTOCOL_PATH) != PROTOCOL_SHA256:
        raise RuntimeError("R30 protocol hash mismatch")
    source = r27.read_json(R29_COHORT, list)
    records = build_records(source)
    audit = audit_records(source, records)
    expected = {**ACTIVE_COUNTS, "sealed_reserve": 4383}
    if audit["partition_patient_counts"] != expected:
        raise RuntimeError("unexpected R30 patient partition counts")
    if (
        not audit["patient_disjoint"]
        or audit["r29_active_patient_overlap"]
        or audit["missing_images"]
    ):
        raise RuntimeError("R30 cohort integrity gate failed")
    if any(
        set(audit["partition_label_counts"][partition]) != set(LABELS)
        for partition in ACTIVE_COUNTS
    ):
        raise RuntimeError("R30 active partition missing a label")
    args.output_root.mkdir(parents=True, exist_ok=False)
    r27.write_json_exclusive(args.output_root / "cohort.json", records)
    r27.write_json_exclusive(args.output_root / "cohort_audit.json", audit)
    manifest_base = {
        "status": "PASS_R30_FRESH_COHORT_FREEZE",
        "cohort_sha256": r27.sha256_file(args.output_root / "cohort.json"),
        "audit_sha256": r27.sha256_file(
            args.output_root / "cohort_audit.json"
        ),
        "builder_sha256": r27.sha256_file(Path(__file__)),
        "protocol_sha256": PROTOCOL_SHA256,
    }
    manifest = dict(manifest_base)
    manifest["manifest_payload_sha256"] = r27.canonical_sha256(manifest_base)
    r27.write_json_exclusive(
        args.output_root / "cohort_manifest.json", manifest
    )
    print(json.dumps({"manifest": manifest, "audit": audit}, indent=2))


if __name__ == "__main__":
    main()
