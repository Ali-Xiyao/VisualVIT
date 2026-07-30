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
sys.path.insert(0, str(WORKSPACE))
sys.path.insert(0, str(WORKSPACE / "src"))

import pandas as pd

from scripts.build_prta_gen_r40b_smoke_cohort import read_json, write_json


CONFIG_STATUS = "FROZEN_PRTA_GEN_R43_CONFIRMATORY_READINESS"


def normalize_numeric(value: object) -> str:
    numeric = re.sub(r"\D", "", str(value))
    return str(int(numeric)) if numeric else str(value).strip().lower()


def historical_patient_ids(path: Path) -> set[str]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    return {normalize_numeric(row["patient_id"]) for row in rows}


def resolve_image(
    dataset: str,
    relative: str,
    *,
    chexpert_root: Path,
    mimic_root: Path,
    rexgradient_root: Path,
) -> Path | None:
    if dataset == "chexpert":
        candidates = (
            chexpert_root / "train" / relative,
            chexpert_root / "valid" / relative,
        )
    elif dataset == "mimic":
        parts = Path(relative).parts
        patient = parts[0].replace("patient", "p")
        study = parts[1].replace("study", "s")
        candidates = (
            mimic_root / f"p{patient[1:3]}" / patient / study / parts[-1],
        )
    elif dataset == "rexgradient":
        candidates = (rexgradient_root / relative,)
    else:
        raise ValueError(f"unknown R43 gold dataset: {dataset}")
    return next((path for path in candidates if path.is_file()), None)


def conservative_mde_pp(patient_count: int) -> float | None:
    if patient_count <= 0:
        return None
    return 100.0 * (1.959964 + 0.841621) * 0.5 / math.sqrt(patient_count)


def audit(config_path: Path, *, require_predecessor: bool) -> dict[str, Any]:
    config = read_json(config_path)
    if config.get("status") != CONFIG_STATUS:
        raise PermissionError("R43 readiness config is not frozen")
    if require_predecessor:
        spec = config["closed_predecessor"]
        predecessor = read_json(Path(spec["aggregate"]))
        if (
            predecessor.get("status") != spec["required_status"]
            or predecessor.get("gate_passed") is not True
            or predecessor.get("r43_readiness_unlocked") is not True
            or predecessor.get("scientific_claim_allowed") is not False
            or predecessor.get("gold_outcomes_read") is not False
            or predecessor.get("external_outcomes_read") is not False
        ):
            raise PermissionError("R43 predecessor receipt drift")
    gold = config["gold"]
    frame = pd.read_parquet(
        WORKSPACE / gold["annotations"],
        columns=list(gold["required_columns"]),
    )
    frame["normalized_patient"] = frame["patient_id"].map(normalize_numeric)
    used = {
        "chexpert": historical_patient_ids(
            WORKSPACE / gold["historical_chexpert_cohort"]
        ),
        "mimic": historical_patient_ids(
            WORKSPACE / gold["historical_mimic_cohort"]
        ),
        "rexgradient": set(),
    }
    roots = {
        "chexpert": Path(gold["chexpert_root"]),
        "mimic": Path(gold["mimic_root"]),
        "rexgradient": Path(gold["rexgradient_root"]),
    }
    sources: dict[str, Any] = {}
    available_count = 0
    for raw_dataset, group in frame.groupby("dataset"):
        dataset = str(raw_dataset)
        patients = set(group["normalized_patient"])
        untouched = patients - used[dataset]
        rows = group[group["normalized_patient"].isin(untouched)]
        per_patient = {patient: [] for patient in untouched}
        missing_paths = 0
        for row in rows.itertuples(index=False):
            for relative in (row.img_path_prev, row.img_path_curr):
                available = (
                    resolve_image(
                        dataset,
                        str(relative),
                        chexpert_root=roots["chexpert"],
                        mimic_root=roots["mimic"],
                        rexgradient_root=roots["rexgradient"],
                    )
                    is not None
                )
                per_patient[str(row.normalized_patient)].append(available)
                missing_paths += not available
        ready_patients = sum(
            bool(values) and all(values) for values in per_patient.values()
        )
        available_count += ready_patients
        sources[dataset] = {
            "official_patients": len(patients),
            "historically_used_patients": len(patients & used[dataset]),
            "untouched_patients": len(untouched),
            "untouched_image_complete_patients": ready_patients,
            "missing_image_references": missing_paths,
        }
    external_root = WORKSPACE / config["external"]["root"]
    external_exists = external_root.is_dir()
    external_image_complete_patients = 0
    independent_labels = False
    required_gold = int(
        gold["minimum_confirmatory_patients_for_plus_2pp_worst_case"]
    )
    required_external = int(
        config["external"]["minimum_image_complete_patients"]
    )
    checks = {
        "gold_confirmatory_plus_2pp_power_ready": available_count
        >= required_gold,
        "external_image_complete_patient_minimum_met": (
            external_image_complete_patients >= required_external
        ),
        "independent_expert_labels_available": independent_labels,
        "all_predecessor_settings_frozen": require_predecessor,
    }
    passed = all(checks.values())
    failures = [
        {"gate": name, "observed": value, "required": True}
        for name, value in checks.items()
        if not value
    ]
    return {
        "schema": "visualvit.prta-gen.r43-confirmatory-readiness-result.v1",
        "status": (
            config["result_statuses"]["ready"]
            if passed
            else config["result_statuses"]["stop"]
        ),
        "protocol_id": config["protocol_id"],
        "predecessor_required_and_validated": require_predecessor,
        "sources": sources,
        "available_untouched_gold_patients": available_count,
        "minimum_confirmatory_gold_patients": required_gold,
        "overall_conservative_mde_pp": conservative_mde_pp(available_count),
        "external_root_exists": external_exists,
        "external_image_complete_patients": external_image_complete_patients,
        "minimum_external_patients": required_external,
        "independent_expert_labels_available": independent_labels,
        "checks": checks,
        "gate_passed": passed,
        "gate_failures": failures,
        "outcomes_read": False,
        "metrics_read": False,
        "predictions_generated": False,
        "gold_outcomes_read": False,
        "external_outcomes_read": False,
        "scientific_claim_allowed": False,
    }


def receipt_summary(result: dict[str, Any]) -> dict[str, Any]:
    return dict(result)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit frozen R43 confirmation readiness without outcomes"
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--preflight-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = audit(
        args.config, require_predecessor=not args.preflight_only
    )
    if not args.preflight_only:
        output_path = read_json(args.config)["runtime"]["result"]
        if Path(output_path).exists():
            raise FileExistsError(
                f"R43 readiness result must be fresh: {output_path}"
            )
        write_json(Path(output_path), result)
    print(json.dumps(receipt_summary(result), indent=2, sort_keys=True))
    return 0 if result["gate_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
