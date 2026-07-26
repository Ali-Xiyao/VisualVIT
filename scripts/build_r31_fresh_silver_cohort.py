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
from scripts import build_r30_fresh_silver_cohort as r30


LABELS = r30.LABELS
ACTIVE_COUNTS = {"train": 1200, "dev": 300, "test": 500}
ROW_CAP = 12
R30_COHORT = (
    Path(
        r"F:\VisualVIT_runtime\050_routeC\r30_regularized_multiscale"
        r"\cohort_v1_1"
    )
    / "cohort.json"
)
R30_COHORT_SHA256 = (
    "219132709955c5612abd39b5eade618bf3fc69eeb5a520ef6b41196fd41b437f"
)
PROTOCOL_PATH = (
    WORKSPACE
    / "docs/superpowers/specs/2026-07-26-r31-confidence-consensus-v1.md"
)
PROTOCOL_SHA256 = (
    "c0133ee12ac5031527469e9c0377dd2293827251dd1717a678d16faf3c03d162"
)
OUTPUT_ROOT_DEFAULT = Path(
    r"F:\VisualVIT_runtime\050_routeC\r31_confidence_consensus\cohort_v1"
)


def stable_hash(*parts: object) -> str:
    return hashlib.sha256(
        "|".join(str(part) for part in parts).encode()
    ).hexdigest()


def assign_patients(patients: list[str]) -> dict[str, str]:
    ordered = sorted(
        patients, key=lambda value: stable_hash("r31-patient-v1", value)
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
    by_patient: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in source:
        if row["partition"] == "sealed_reserve":
            by_patient[str(row["patient_id"])].append(dict(row))
    assignments = assign_patients(list(by_patient))
    output = []
    for patient, rows in by_patient.items():
        partition = assignments[patient]
        ordered = sorted(
            rows,
            key=lambda row: stable_hash("r31-row-v1", row["record_id"]),
        )
        if partition != "sealed_reserve":
            ordered = ordered[:ROW_CAP]
        for row in ordered:
            row["partition"] = partition
            output.append(row)
    order = {"train": 0, "dev": 1, "test": 2, "sealed_reserve": 3}
    return sorted(
        output,
        key=lambda row: (
            order[row["partition"]],
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
    partitions = (*ACTIVE_COUNTS, "sealed_reserve")
    patient_sets = {
        name: {
            str(row["patient_id"])
            for row in records
            if row["partition"] == name
        }
        for name in partitions
    }
    active_sets = [patient_sets[name] for name in ACTIVE_COUNTS]
    active = [
        row for row in records if row["partition"] != "sealed_reserve"
    ]
    return {
        "protocol": {
            "path": str(PROTOCOL_PATH),
            "sha256": PROTOCOL_SHA256,
        },
        "r30_source": {
            "path": str(R30_COHORT),
            "sha256": R30_COHORT_SHA256,
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
            name: len(value) for name, value in patient_sets.items()
        },
        "partition_row_counts": dict(
            Counter(row["partition"] for row in records)
        ),
        "partition_label_counts": {
            name: dict(
                Counter(
                    row["progression"]
                    for row in records
                    if row["partition"] == name
                )
            )
            for name in partitions
        },
        "active_records": len(active),
        "active_patients": len(
            {str(row["patient_id"]) for row in active}
        ),
        "patient_disjoint": all(
            not (left & right)
            for index, left in enumerate(active_sets)
            for right in active_sets[index + 1 :]
        ),
        "r30_active_patient_overlap": len(
            prior_active
            & {str(row["patient_id"]) for row in active}
        ),
        "missing_images": sum(
            not Path(row[f"{side}_path"]).is_file()
            for row in active
            for side in ("prior", "current")
        ),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build frozen R31 cohort")
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT_DEFAULT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.output_root.exists():
        raise FileExistsError(f"output root must be fresh: {args.output_root}")
    if r27.sha256_file(R30_COHORT) != R30_COHORT_SHA256:
        raise RuntimeError("R30 cohort hash mismatch")
    if r27.sha256_file(PROTOCOL_PATH) != PROTOCOL_SHA256:
        raise RuntimeError("R31 protocol hash mismatch")
    source = r27.read_json(R30_COHORT, list)
    records = build_records(source)
    audit = audit_records(source, records)
    if audit["partition_patient_counts"] != {
        **ACTIVE_COUNTS,
        "sealed_reserve": 2383,
    }:
        raise RuntimeError("unexpected R31 patient counts")
    if (
        not audit["patient_disjoint"]
        or audit["r30_active_patient_overlap"]
        or audit["missing_images"]
    ):
        raise RuntimeError("R31 cohort integrity gate failed")
    if any(
        set(audit["partition_label_counts"][name]) != set(LABELS)
        for name in ACTIVE_COUNTS
    ):
        raise RuntimeError("R31 active partition missing label")
    args.output_root.mkdir(parents=True, exist_ok=False)
    r27.write_json_exclusive(args.output_root / "cohort.json", records)
    r27.write_json_exclusive(args.output_root / "cohort_audit.json", audit)
    base = {
        "status": "PASS_R31_FRESH_COHORT_FREEZE",
        "cohort_sha256": r27.sha256_file(args.output_root / "cohort.json"),
        "audit_sha256": r27.sha256_file(
            args.output_root / "cohort_audit.json"
        ),
        "builder_sha256": r27.sha256_file(Path(__file__)),
        "protocol_sha256": PROTOCOL_SHA256,
    }
    manifest = {
        **base,
        "manifest_payload_sha256": r27.canonical_sha256(base),
    }
    r27.write_json_exclusive(
        args.output_root / "cohort_manifest.json", manifest
    )
    print(json.dumps({"manifest": manifest, "audit": audit}, indent=2))


if __name__ == "__main__":
    main()
