from __future__ import annotations

# ruff: noqa: E402

import argparse
import json
import math
from pathlib import Path
import re
import sys
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE / "src"))

import pandas as pd

from visualvit.gold_quarantine import GoldAccessEvent, append_access_event


GOLD_PAIRS = (
    WORKSPACE
    / "data/official/chextemporal_81fd9cdd/gold_progression_pairs.parquet"
)
R24_CHEXPERT = (
    WORKSPACE
    / "artifacts/real_progression/chextemporal_chexpert_pilot_v1/cohort.json"
)
R24_MIMIC = (
    WORKSPACE
    / "artifacts/real_qualification/chextemporal_mimic_matcher_v3/process_a"
    / "cohort.json"
)
CHEXPERT_ROOT = Path(
    r"H:\Xiyao_Wang\000_Public Dataset\CheXpert-v1.0-small"
)
MIMIC_ROOT = Path(
    r"H:\Xiyao_Wang\000_Public Dataset\mimic-cxr\mimic-cxr"
    r"\mimic-cxr-images\files"
)
REXGRADIENT_ROOT = Path(
    r"H:\Xiyao_Wang\000_Public Dataset\ReXGradient"
)
COHORT_ROOT = Path(
    r"F:\VisualVIT_runtime\050_routeC\r32_tier_cxr_vlm\cohort_v1"
)
OUTPUT_DEFAULT = (
    Path(r"F:\VisualVIT_runtime\050_routeC\r32_tier_cxr_vlm")
    / "gold_external_support_audit_v1.json"
)


def normalize_numeric(value: object) -> str:
    numeric = re.sub(r"\D", "", str(value))
    return str(int(numeric)) if numeric else str(value).strip().lower()


def historical_patient_ids(path: Path) -> set[str]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    return {normalize_numeric(row["patient_id"]) for row in rows}


def resolve_image(dataset: str, relative: str) -> Path | None:
    if dataset == "chexpert":
        candidates = (
            CHEXPERT_ROOT / "train" / relative,
            CHEXPERT_ROOT / "valid" / relative,
        )
    elif dataset == "mimic":
        parts = Path(relative).parts
        patient = parts[0].replace("patient", "p")
        study = parts[1].replace("study", "s")
        candidates = (
            MIMIC_ROOT / f"p{patient[1:3]}" / patient / study / parts[-1],
        )
    elif dataset == "rexgradient":
        candidates = (REXGRADIENT_ROOT / relative,)
    else:
        raise ValueError(f"unknown gold dataset: {dataset}")
    return next((path for path in candidates if path.is_file()), None)


def conservative_mde_pp(patient_count: int) -> float | None:
    if patient_count <= 0:
        return None
    # Worst-case paired Bernoulli normal approximation, alpha=.05, power=.80.
    return 100.0 * (1.959964 + 0.841621) * 0.5 / math.sqrt(patient_count)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit R32 gold/external image availability without outcomes"
    )
    parser.add_argument("--output", type=Path, default=OUTPUT_DEFAULT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    frame = pd.read_parquet(
        GOLD_PAIRS,
        columns=[
            "dataset",
            "patient_id",
            "img_path_prev",
            "img_path_curr",
        ],
    )
    append_access_event(
        COHORT_ROOT / "gold_access_log.jsonl",
        GoldAccessEvent(
            source="chextemporal_official_gold",
            fields=(
                "dataset",
                "patient_id",
                "img_path_prev",
                "img_path_curr",
            ),
            purpose="R32 parent-image availability audit",
            row_count=len(frame),
        ),
    )
    frame["normalized_patient"] = frame["patient_id"].map(normalize_numeric)
    used = {
        "chexpert": historical_patient_ids(R24_CHEXPERT),
        "mimic": historical_patient_ids(R24_MIMIC),
        "rexgradient": set(),
    }
    sources: dict[str, Any] = {}
    available_union: set[str] = set()
    for dataset, group in frame.groupby("dataset"):
        dataset = str(dataset)
        all_patients = set(group["normalized_patient"])
        untouched = all_patients - used[dataset]
        untouched_rows = group[group["normalized_patient"].isin(untouched)]
        per_patient: dict[str, list[bool]] = {
            patient: [] for patient in untouched
        }
        resolved_images = set()
        missing_images = set()
        for row in untouched_rows.itertuples(index=False):
            for relative in (row.img_path_prev, row.img_path_curr):
                resolved = resolve_image(dataset, str(relative))
                per_patient[str(row.normalized_patient)].append(
                    resolved is not None
                )
                if resolved is None:
                    missing_images.add(str(relative))
                else:
                    resolved_images.add(str(resolved))
        available_patients = {
            patient
            for patient, values in per_patient.items()
            if values and all(values)
        }
        available_union.update(
            f"{dataset}:{patient}" for patient in available_patients
        )
        sources[dataset] = {
            "official_patients": len(all_patients),
            "historically_used_patients": len(all_patients & used[dataset]),
            "untouched_patients": len(untouched),
            "untouched_patients_with_all_parent_images": len(
                available_patients
            ),
            "resolved_unique_images": len(resolved_images),
            "missing_unique_image_paths": len(missing_images),
            "root": str(
                {
                    "chexpert": CHEXPERT_ROOT,
                    "mimic": MIMIC_ROOT,
                    "rexgradient": REXGRADIENT_ROOT,
                }[dataset]
            ),
            "conservative_mde_pp": conservative_mde_pp(
                len(available_patients)
            ),
        }
    available_count = len(available_union)
    result = {
        "schema": "visualvit.r32.gold-external-support.v1",
        "status": "PASS_R32_GOLD_AVAILABILITY_AUDIT_LIMITED",
        "outcomes_read": False,
        "metrics_read": False,
        "predictions_generated": False,
        "sources": sources,
        "available_untouched_gold_patients": available_count,
        "overall_conservative_mde_pp": conservative_mde_pp(available_count),
        "confirmatory_plus_2pp_power_ready": False,
        "r35_status": "BLOCKED_PENDING_INDEPENDENT_EXPERT_LABELS",
        "interpretation": (
            "Locally available untouched official gold is descriptive only. "
            "Do not tune on it or claim a +2 pp confirmatory endpoint."
        ),
    }
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
