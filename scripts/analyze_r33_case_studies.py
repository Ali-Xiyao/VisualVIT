from __future__ import annotations

# ruff: noqa: E402

import argparse
from collections import Counter, defaultdict
import csv
import json
from pathlib import Path
import sys
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE / "src"))
sys.path.insert(0, str(WORKSPACE))

import torch
from torch import Tensor

from scripts.run_r33_token_survival import weighted_confusion


FEATURES_DEFAULT = Path(
    r"F:\VisualVIT_runtime\050_routeC\r33_token_survival"
    r"\features_v1\token_features.pt"
)
PREDICTIONS_DEFAULT = Path(
    r"F:\VisualVIT_runtime\050_routeC\r33_token_survival"
    r"\nested_oof_v1\r33_oof_predictions.pt"
)
COHORT_DEFAULT = Path(
    r"F:\VisualVIT_runtime\050_routeC\r32_tier_cxr_vlm"
    r"\cohort_v1\train_dev_cohort.json"
)
OUTPUT_DEFAULT = Path(
    r"F:\VisualVIT_runtime\050_routeC\r33a_case_study"
    r"\failure_registry_v1"
)
LABELS = ("Stable", "Improved", "Worse")
SEEDS = (17, 29, 43)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the train-only R33 failure case registry"
    )
    parser.add_argument("--features", type=Path, default=FEATURES_DEFAULT)
    parser.add_argument("--predictions", type=Path, default=PREDICTIONS_DEFAULT)
    parser.add_argument("--cohort", type=Path, default=COHORT_DEFAULT)
    parser.add_argument("--output", type=Path, default=OUTPUT_DEFAULT)
    return parser.parse_args()


def archetype_counts(labels: Tensor, robust: Tensor, rich: Tensor) -> dict[str, Tensor]:
    if robust.shape != rich.shape or robust.ndim != 2:
        raise ValueError("robust/rich predictions must be [seed, row]")
    if labels.shape != (robust.shape[1],):
        raise ValueError("label shape mismatch")
    robust_correct = robust.eq(labels[None])
    rich_correct = rich.eq(labels[None])
    return {
        "both_correct": (robust_correct & rich_correct).sum(dim=0),
        "rich_helped": ((~robust_correct) & rich_correct).sum(dim=0),
        "rich_harmed": (robust_correct & (~rich_correct)).sum(dim=0),
        "both_wrong": ((~robust_correct) & (~rich_correct)).sum(dim=0),
        "prediction_disagreement": robust.ne(rich).sum(dim=0),
    }


def dominant_archetype(counts: dict[str, Tensor], row: int) -> str:
    priority = ("rich_helped", "rich_harmed", "both_wrong", "both_correct")
    best = max(int(counts[name][row]) for name in priority)
    return next(name for name in priority if int(counts[name][row]) == best)


def summarize_group(
    indices: list[int],
    labels: Tensor,
    robust: Tensor,
    rich: Tensor,
    route: Tensor,
) -> dict[str, Any]:
    index = torch.tensor(indices, dtype=torch.long)
    robust_correct = robust[:, index].eq(labels[index][None])
    rich_correct = rich[:, index].eq(labels[index][None])
    helped = (~robust_correct) & rich_correct
    harmed = robust_correct & (~rich_correct)
    selected = route[index][None].expand_as(helped)
    units = helped.numel()
    return {
        "records": len(indices),
        "seed_record_units": units,
        "rich_helped_units": int(helped.sum()),
        "rich_harmed_units": int(harmed.sum()),
        "rich_helped_rate": float(helped.float().mean()),
        "rich_harmed_rate": float(harmed.float().mean()),
        "route_coverage": float(selected.float().mean()),
        "route_help_capture": (
            float((selected & helped).sum() / helped.sum()) if helped.any() else None
        ),
        "route_harm_exposure": (
            float((selected & harmed).sum() / harmed.sum()) if harmed.any() else None
        ),
        "selected_help_minus_harm_units": int(
            (selected & helped).sum() - (selected & harmed).sum()
        ),
    }


def main() -> int:
    args = parse_args()
    if args.output.exists():
        raise FileExistsError(f"output must be fresh: {args.output}")
    feature_payload = torch.load(args.features, map_location="cpu", weights_only=False)
    prediction_payload = torch.load(
        args.predictions, map_location="cpu", weights_only=False
    )
    records = feature_payload["records"]
    if [row["record_id"] for row in records] != prediction_payload["record_ids"]:
        raise RuntimeError("feature/prediction record alignment failed")
    if (
        feature_payload["sealed_test_records_read"]
        or feature_payload["sealed_test_images_read"]
    ):
        raise RuntimeError("R33A case study cannot use sealed data")

    train_global = [
        index for index, row in enumerate(records) if row["partition"] == "train"
    ]
    if len({str(records[index]["patient_id"]) for index in train_global}) != 1574:
        raise RuntimeError("train-only patient count drift")
    labels_global = prediction_payload["labels"]
    robust_global = prediction_payload["predictions"]["P3"]
    rich_global = prediction_payload["predictions"]["P4"]
    tier_global = prediction_payload["predictions"]["P6"]
    route_global = prediction_payload["consensus_route"]
    random_global = prediction_payload["random_routes"]

    take = torch.tensor(train_global, dtype=torch.long)
    labels = labels_global[take]
    robust = robust_global[:, take]
    rich = rich_global[:, take]
    tier = tier_global[:, take]
    route = route_global[take]
    random_route = random_global[:, take]
    train_records = [records[index] for index in train_global]
    patient_ids = [str(row["patient_id"]) for row in train_records]
    counts = archetype_counts(labels, robust, rich)

    cohort_rows = json.loads(args.cohort.read_text(encoding="utf-8"))
    cohort_by_id = {str(row["record_id"]): row for row in cohort_rows}
    case_rows: list[dict[str, Any]] = []
    for row_index, record in enumerate(train_records):
        record_id = str(record["record_id"])
        source = cohort_by_id.get(record_id, {})
        row = {
            "record_id": record_id,
            "patient_id": str(record["patient_id"]),
            "finding_token": str(record["finding_token"]),
            "progression": str(record["progression"]),
            "fold": int(prediction_payload["folds"][take[row_index]]),
            "dominant_archetype": dominant_archetype(counts, row_index),
            **{
                f"{name}_seeds": int(value[row_index]) for name, value in counts.items()
            },
            "hard_route_rich": bool(route[row_index]),
            "robust_predictions": [
                LABELS[int(value)] for value in robust[:, row_index]
            ],
            "rich_predictions": [LABELS[int(value)] for value in rich[:, row_index]],
            "tier_predictions": [LABELS[int(value)] for value in tier[:, row_index]],
        }
        for field in (
            "prior_dicom_id",
            "current_dicom_id",
            "prior_image_path",
            "current_image_path",
        ):
            if field in source:
                row[field] = source[field]
        case_rows.append(row)

    group_indices: dict[str, list[int]] = defaultdict(list)
    for index, row in enumerate(train_records):
        group_indices[f"label::{row['progression']}"].append(index)
        group_indices[f"finding::{row['finding_token']}"].append(index)
    group_results = {
        group: summarize_group(indices, labels, robust, rich, route)
        for group, indices in sorted(group_indices.items())
    }

    ranked_cases: dict[str, list[dict[str, Any]]] = {}
    for archetype in ("rich_helped", "rich_harmed", "both_wrong"):
        ranked = sorted(
            case_rows,
            key=lambda row: (
                -int(row[f"{archetype}_seeds"]),
                -int(row["prediction_disagreement_seeds"]),
                row["record_id"],
            ),
        )
        ranked_cases[archetype] = [
            row for row in ranked if int(row[f"{archetype}_seeds"]) > 0
        ][:20]

    overall = summarize_group(
        list(range(len(train_records))), labels, robust, rich, route
    )
    robust_metrics = weighted_confusion(labels, robust, patient_ids)
    rich_metrics = weighted_confusion(labels, rich, patient_ids)
    tier_metrics = weighted_confusion(labels, tier, patient_ids)
    oracle = robust.clone()
    repair = rich.eq(labels[None]) & robust.ne(labels[None])
    oracle[repair] = rich[repair]
    oracle_metrics = weighted_confusion(labels, oracle, patient_ids)
    robust_correct = robust.eq(labels[None])
    rich_correct = rich.eq(labels[None])
    helped = (~robust_correct) & rich_correct
    harmed = robust_correct & (~rich_correct)
    selected = route[None].expand_as(helped)
    random_selected = random_route

    summary = {
        "schema": "visualvit.r33a.train-case-study.v1",
        "status": "PASS_R33A_TRAIN_ONLY_CASE_REGISTRY",
        "scope": "r32_train_partition_only",
        "records": len(train_records),
        "patients": len(set(patient_ids)),
        "seeds": SEEDS,
        "dev_case_outcomes_inspected": False,
        "sealed_test_records_read": False,
        "sealed_test_images_read": False,
        "gold_outcomes_read": False,
        "metrics": {
            "robust_macro_f1": robust_metrics["macro_f1"],
            "rich_macro_f1": rich_metrics["macro_f1"],
            "tier_macro_f1": tier_metrics["macro_f1"],
            "case_oracle_macro_f1": oracle_metrics["macro_f1"],
            "case_oracle_minus_robust_pp": 100
            * (float(oracle_metrics["macro_f1"]) - float(robust_metrics["macro_f1"])),
        },
        "overall": overall,
        "hard_route": {
            "selected_help_units": int((selected & helped).sum()),
            "selected_harm_units": int((selected & harmed).sum()),
            "net_selected_help_minus_harm": int(
                (selected & helped).sum() - (selected & harmed).sum()
            ),
            "help_precision_among_help_or_harm": float(
                (selected & helped).sum()
                / ((selected & helped).sum() + (selected & harmed).sum())
            ),
        },
        "matched_random_route": {
            "selected_help_units": int((random_selected & helped).sum()),
            "selected_harm_units": int((random_selected & harmed).sum()),
            "net_selected_help_minus_harm": int(
                (random_selected & helped).sum() - (random_selected & harmed).sum()
            ),
        },
        "groups": group_results,
        "representative_cases": ranked_cases,
        "archetype_record_counts": dict(
            Counter(row["dominant_archetype"] for row in case_rows)
        ),
    }

    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / "case_study_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
    )
    fieldnames = sorted({key for row in case_rows for key in row})
    with (args.output / "case_registry.csv").open(
        "x", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in case_rows:
            writer.writerow(
                {
                    key: (
                        json.dumps(value) if isinstance(value, (list, dict)) else value
                    )
                    for key, value in row.items()
                }
            )
    print(
        json.dumps(
            {
                "status": summary["status"],
                "records": summary["records"],
                "patients": summary["patients"],
                "metrics": summary["metrics"],
                "overall": summary["overall"],
                "hard_route": summary["hard_route"],
                "matched_random_route": summary["matched_random_route"],
                "output": str(args.output),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
