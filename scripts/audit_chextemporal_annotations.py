from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from numbers import Real
from pathlib import Path
from typing import Any, Iterable

import pandas as pd


PAIR_FILE = "gold_progression_pairs.parquet"
BBOX_FILE = "gold_bboxes.parquet"
ALLOWED_LABELS = ("Stable", "Worse", "Improved", "New", "Resolved")
ROW_KEY = (
    "dataset",
    "patient_id",
    "study_id_prev",
    "study_id_curr",
    "img_path_prev",
    "img_path_curr",
    "disease_name",
    "progression",
)
PREDICTION_KEY = (
    "dataset",
    "patient_id",
    "study_id_prev",
    "study_id_curr",
    "img_path_prev",
    "img_path_curr",
    "disease_name",
)
PERSISTENT_LABELS = ("Stable", "Worse", "Improved")
ANNOTATION_PROTOCOL_URL = "https://arxiv.org/html/2605.11304#Sx5.SS3"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Profile SHA-pinned CheXTemporal public gold annotations."
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data/official/chextemporal_81fd9cdd"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("reports/data_quality/chextemporal_81fd9cdd_profile.json"),
    )
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rows_by(columns: Iterable[str], frame: pd.DataFrame) -> list[dict[str, Any]]:
    grouped = frame.groupby(list(columns), dropna=False).size().reset_index(name="rows")
    return grouped.to_dict(orient="records")


def null_profile(frame: pd.DataFrame) -> dict[str, dict[str, float | int]]:
    return {
        column: {
            "null_count": int(frame[column].isna().sum()),
            "null_rate": float(frame[column].isna().mean()),
        }
        for column in frame.columns
    }


def boxes(value: Any) -> list[dict[str, Any]]:
    return list(value)


def box_labels(value: Any) -> list[str]:
    return [str(item.get("label")) for item in boxes(value)]


def box_payload_signature(value: Any) -> tuple[tuple[Any, ...], ...]:
    return tuple(
        (
            str(item.get("label")),
            item.get("x1"),
            item.get("y1"),
            item.get("x2"),
            item.get("y2"),
        )
        for item in boxes(value)
    )


def validate_boxes(frame: pd.DataFrame) -> dict[str, Any]:
    invalid_schema = 0
    invalid_geometry = 0
    duplicate_labels = 0
    duplicate_label_rows: set[Any] = set()
    duplicate_label_rows_by_side: dict[str, int] = {}
    total_boxes = 0
    required = {"label", "x1", "x2", "y1", "y2"}
    for column in ("prior_bboxes", "current_bboxes"):
        side_duplicate_rows: set[Any] = set()
        for index, value in frame[column].items():
            items = boxes(value)
            labels = []
            for item in items:
                total_boxes += 1
                if set(item) != required:
                    invalid_schema += 1
                    continue
                labels.append(str(item["label"]))
                coordinates = (item["x1"], item["x2"], item["y1"], item["y2"])
                if not all(isinstance(v, Real) for v in coordinates):
                    invalid_geometry += 1
                    continue
                if (
                    item["x1"] < 0
                    or item["y1"] < 0
                    or item["x2"] <= item["x1"]
                    or item["y2"] <= item["y1"]
                ):
                    invalid_geometry += 1
            duplicate_count = len(labels) - len(set(labels))
            duplicate_labels += duplicate_count
            if duplicate_count:
                duplicate_label_rows.add(index)
                side_duplicate_rows.add(index)
        duplicate_label_rows_by_side[column] = len(side_duplicate_rows)
    return {
        "total_boxes": total_boxes,
        "invalid_schema_count": invalid_schema,
        "invalid_geometry_count": invalid_geometry,
        "duplicate_box_labels_within_side_count": duplicate_labels,
        "rows_with_duplicate_box_labels_within_side": len(duplicate_label_rows),
        "rows_with_duplicate_box_labels_by_side": duplicate_label_rows_by_side,
        "image_bound_check": "NOT_EVALUABLE_WITHOUT_PARENT_IMAGES",
    }


def target_conflict_profile(frame: pd.DataFrame) -> dict[str, Any]:
    target_groups = (
        frame.groupby(list(PREDICTION_KEY), dropna=False)
        .agg(
            rows=("progression", "size"),
            distinct_progression_labels=("progression", "nunique"),
            label_set=("progression", lambda values: "|".join(sorted(set(values)))),
        )
        .reset_index()
    )
    conflicts = target_groups[target_groups["distinct_progression_labels"] > 1]
    per_class_counts = frame.groupby(
        [*PREDICTION_KEY, "progression"], dropna=False
    ).size()
    deterministic_correct_ceiling = int(
        per_class_counts.groupby(level=list(range(len(PREDICTION_KEY)))).max().sum()
    )
    return {
        "prediction_keys": int(len(target_groups)),
        "conflicting_prediction_keys": int(len(conflicts)),
        "rows_in_conflicting_prediction_keys": int(conflicts["rows"].sum()),
        "conflicting_prediction_key_rate": float(len(conflicts) / len(target_groups)),
        "rows_in_conflicting_prediction_key_rate": float(
            conflicts["rows"].sum() / len(frame)
        ),
        "deterministic_single_label_correct_ceiling_rows": deterministic_correct_ceiling,
        "deterministic_single_label_accuracy_ceiling": float(
            deterministic_correct_ceiling / len(frame)
        ),
        "conflict_label_set_counts": rows_by(("label_set",), conflicts),
        "conflict_dataset_counts": rows_by(("dataset",), conflicts),
        "conflict_disease_counts": rows_by(("disease_name",), conflicts),
    }


def progression_has_compatible_box_support(row: pd.Series) -> bool:
    prior_labels = set(box_labels(row["prior_bboxes"]))
    current_labels = set(box_labels(row["current_bboxes"]))
    progression = row["progression"]
    if progression == "New":
        return bool(current_labels - prior_labels)
    if progression == "Resolved":
        return bool(prior_labels - current_labels)
    if progression in PERSISTENT_LABELS:
        return bool(prior_labels & current_labels)
    return False


def bbox_semantics(frame: pd.DataFrame) -> dict[str, Any]:
    prior_lengths = frame["prior_bboxes"].map(len)
    current_lengths = frame["current_bboxes"].map(len)
    shared_counts = frame.apply(
        lambda row: len(
            set(box_labels(row["prior_bboxes"]))
            & set(box_labels(row["current_bboxes"]))
        ),
        axis=1,
    )
    persistent = frame["progression"].isin(PERSISTENT_LABELS)
    new = frame["progression"].eq("New")
    resolved = frame["progression"].eq("Resolved")
    legacy_whole_row_mismatches = {
        "persistent_requires_both_sides_nonempty": int(
            (persistent & ((prior_lengths == 0) | (current_lengths == 0))).sum()
        ),
        "new_requires_prior_empty_current_nonempty": int(
            (new & ((prior_lengths != 0) | (current_lengths == 0))).sum()
        ),
        "resolved_requires_prior_nonempty_current_empty": int(
            (resolved & ((prior_lengths == 0) | (current_lengths != 0))).sum()
        ),
    }
    enriched = frame.assign(
        prior_box_count=prior_lengths,
        current_box_count=current_lengths,
        shared_box_label_count=shared_counts,
        progression_support_compatible=frame.apply(
            progression_has_compatible_box_support, axis=1
        ),
        prior_box_payload_signature=frame["prior_bboxes"].map(box_payload_signature),
        current_box_payload_signature=frame["current_bboxes"].map(
            box_payload_signature
        ),
    )
    candidate = enriched[
        persistent
        & (enriched["prior_box_count"] >= 2)
        & (enriched["current_box_count"] >= 2)
        & (enriched["shared_box_label_count"] >= 2)
    ]
    support_incompatible = enriched[~enriched["progression_support_compatible"]]
    mapping_groups = (
        enriched.groupby(list(PREDICTION_KEY), dropna=False)
        .agg(
            distinct_progression_labels=("progression", "nunique"),
            distinct_prior_payloads=("prior_box_payload_signature", "nunique"),
            distinct_current_payloads=("current_box_payload_signature", "nunique"),
        )
        .reset_index()
    )
    multi_progression = mapping_groups[
        mapping_groups["distinct_progression_labels"] > 1
    ]
    repeated_full_payload = multi_progression[
        (multi_progression["distinct_prior_payloads"] == 1)
        & (multi_progression["distinct_current_payloads"] == 1)
    ]
    return {
        "prior_box_count_distribution": {
            str(key): int(value) for key, value in Counter(prior_lengths).items()
        },
        "current_box_count_distribution": {
            str(key): int(value) for key, value in Counter(current_lengths).items()
        },
        "both_sides_nonempty_rows": int(
            ((prior_lengths > 0) & (current_lengths > 0)).sum()
        ),
        "both_sides_have_at_least_two_boxes_rows": int(
            ((prior_lengths >= 2) & (current_lengths >= 2)).sum()
        ),
        "at_least_two_shared_box_labels_rows": int((shared_counts >= 2).sum()),
        "potential_nontrivial_persistent_rows": int(len(candidate)),
        "potential_nontrivial_persistent_by_label_dataset": rows_by(
            ("progression", "dataset"), candidate
        ),
        "legacy_whole_row_empty_side_mismatch_counts": legacy_whole_row_mismatches,
        "legacy_whole_row_empty_side_rule": (
            "NOT_USED_FOR_VALIDATION: a multifocal case can contain persistent and "
            "new/resolved regions together, so the whole prior/current box array need "
            "not be empty for a New/Resolved progression row."
        ),
        "progression_support_compatibility_rule": {
            "New": "at least one current-only correspondence label",
            "Resolved": "at least one prior-only correspondence label",
            "Stable/Worse/Improved": "at least one label shared across both images",
        },
        "progression_support_incompatible_rows": int(len(support_incompatible)),
        "progression_support_incompatible_by_label": rows_by(
            ("progression",), support_incompatible
        ),
        "multi_progression_prediction_keys": int(len(multi_progression)),
        "multi_progression_keys_with_identical_full_box_payloads": int(
            len(repeated_full_payload)
        ),
        "progression_to_box_identity_mapping": (
            "NOT_IDENTIFIABLE_FOR_MULTI_PROGRESSION_KEYS: every such key repeats "
            "the same complete prior/current box payload on each progression row, "
            "and released box structs have no per-box progression field."
        ),
        "identity_warning": (
            "The paper defines Box1-Box5 as case-local cross-image correspondence "
            "identities, not globally persistent entity IDs. The released data also "
            "contain duplicate labels within a side and omit per-box progression."
        ),
        "annotation_protocol_source": ANNOTATION_PROTOCOL_URL,
    }


def main() -> int:
    args = parse_args()
    pair_path = args.data_dir / PAIR_FILE
    bbox_path = args.data_dir / BBOX_FILE
    pairs = pd.read_parquet(pair_path)
    bbox = pd.read_parquet(bbox_path)

    pair_keys = pairs[list(ROW_KEY)].drop_duplicates()
    bbox_keys = bbox[list(ROW_KEY)].drop_duplicates()
    bbox_join = pair_keys.merge(bbox_keys, on=list(ROW_KEY), how="inner")
    bbox_orphans = bbox_keys.merge(
        pair_keys, on=list(ROW_KEY), how="left", indicator=True
    )
    conflict_profile = target_conflict_profile(pairs)
    raw_patient_multi_source = pairs.groupby("patient_id")["dataset"].nunique().gt(1)
    non_edema_pair_keys = pairs.loc[
        ~pairs["disease_name"].eq("edema"), list(ROW_KEY)
    ].drop_duplicates()
    bbox_vs_non_edema = non_edema_pair_keys.merge(
        bbox_keys, on=list(ROW_KEY), how="outer", indicator=True
    )
    expected_columns = list(ROW_KEY)
    checks = {
        "pair_row_count_matches_card": len(pairs) == 1787,
        "bbox_row_count_matches_card": len(bbox) == 1562,
        "bbox_row_count_matches_non_edema_pairs": len(bbox) == len(non_edema_pair_keys),
        "bbox_rows_exactly_match_non_edema_pairs": bool(
            (bbox_vs_non_edema["_merge"] == "both").all()
        ),
        "pair_columns_exact": list(pairs.columns)
        == expected_columns[1:7] + [expected_columns[7], expected_columns[0]],
        "bbox_has_pair_columns_plus_boxes": set(bbox.columns)
        == set(ROW_KEY) | {"prior_bboxes", "current_bboxes"},
        "pair_required_fields_nonnull": bool(pairs[list(ROW_KEY)].notna().all().all()),
        "bbox_required_fields_nonnull": bool(bbox[list(ROW_KEY)].notna().all().all()),
        "allowed_progression_values_exact": set(pairs["progression"])
        == set(ALLOWED_LABELS),
        "pair_row_key_unique": not bool(pairs.duplicated(list(ROW_KEY)).any()),
        "bbox_row_key_unique": not bool(bbox.duplicated(list(ROW_KEY)).any()),
        "single_progression_target_per_prediction_key": (
            conflict_profile["conflicting_prediction_keys"] == 0
        ),
        "bbox_rows_are_pair_subset": bool((bbox_orphans["_merge"] == "both").all()),
    }
    box_validation = validate_boxes(bbox)
    semantics = bbox_semantics(bbox)
    checks["bbox_schema_valid"] = box_validation["invalid_schema_count"] == 0
    checks["bbox_geometry_valid_without_image_bounds"] = (
        box_validation["invalid_geometry_count"] == 0
    )
    checks["bbox_correspondence_labels_unique_within_side"] = (
        box_validation["duplicate_box_labels_within_side_count"] == 0
    )
    checks["bbox_progression_has_compatible_correspondence_support"] = (
        semantics["progression_support_incompatible_rows"] == 0
    )
    checks["bbox_multi_progression_entity_mapping_identifiable"] = (
        semantics["multi_progression_keys_with_identical_full_box_payloads"] == 0
    )

    nonfatal_checks = {"bbox_row_count_matches_card"}
    fatal_checks_pass = all(
        value for key, value in checks.items() if key not in nonfatal_checks
    )

    profile = {
        "status": "QUALIFIED_WITH_MATERIAL_LIMITATIONS"
        if fatal_checks_pass
        else "FAIL_DATA_QUALITY",
        "evidence_class": "PUBLIC_ANNOTATION_QUALIFICATION",
        "formal_claim_allowed": False,
        "model_evaluation_performed": False,
        "intended_grain": "patient image-pair x finding",
        "files": {
            PAIR_FILE: {
                "bytes": pair_path.stat().st_size,
                "sha256": sha256_file(pair_path),
                "rows": len(pairs),
                "columns": len(pairs.columns),
            },
            BBOX_FILE: {
                "bytes": bbox_path.stat().st_size,
                "sha256": sha256_file(bbox_path),
                "rows": len(bbox),
                "columns": len(bbox.columns),
            },
        },
        "checks": checks,
        "pair_profile": {
            "nulls": null_profile(pairs),
            "exact_duplicate_rows": int(pairs.duplicated().sum()),
            "duplicate_row_keys": int(pairs.duplicated(list(ROW_KEY), False).sum()),
            "target_conflict_audit": conflict_profile,
            "unique_patients_raw": int(pairs["patient_id"].nunique()),
            "unique_dataset_patients": int(
                pairs[["dataset", "patient_id"]].drop_duplicates().shape[0]
            ),
            "raw_patient_ids_in_multiple_sources": int(raw_patient_multi_source.sum()),
            "label_counts": rows_by(("progression",), pairs),
            "dataset_counts": rows_by(("dataset",), pairs),
            "label_dataset_counts": rows_by(("progression", "dataset"), pairs),
            "disease_counts": rows_by(("disease_name",), pairs),
        },
        "bbox_profile": {
            "nulls": null_profile(bbox),
            "duplicate_row_keys": int(bbox.duplicated(list(ROW_KEY), False).sum()),
            "unique_patients_raw": int(bbox["patient_id"].nunique()),
            "matched_pair_rows": int(len(bbox_join)),
            "pair_row_coverage": float(len(bbox_join) / len(pair_keys)),
            "orphan_bbox_rows": int((bbox_orphans["_merge"] != "both").sum()),
            "label_counts": rows_by(("progression",), bbox),
            "dataset_counts": rows_by(("dataset",), bbox),
            "box_validation": box_validation,
            "semantics": semantics,
        },
        "material_findings": [
            {
                "severity": "MEDIUM",
                "finding": (
                    "README declares 1,562 bbox rows, while the pinned parquet has "
                    "1,565 and exactly matches all 1,787 progression rows except the "
                    "222 edema rows that the protocol exempts from boxes."
                ),
                "impact": (
                    "This is a three-row documentation drift, not three unexplained "
                    "or orphan annotations; disclose it and retain the file hash."
                ),
            },
            {
                "severity": "CRITICAL_FOR_SINGLE_LABEL_EVALUATION",
                "finding": (
                    "At the released model-input grain (image pair x finding), 258 "
                    "keys have multiple progression targets across 548 rows."
                ),
                "impact": (
                    "Without a region/entity query or a declared multi-label policy, "
                    "the deterministic single-label accuracy ceiling is "
                    f"{conflict_profile['deterministic_single_label_accuracy_ceiling']:.6f}."
                ),
            },
            {
                "severity": "CRITICAL_FOR_B4",
                "finding": (
                    "All 251 multi-progression bbox keys repeat the same complete box "
                    "arrays on every progression row; box structs omit per-box progression."
                ),
                "impact": (
                    "The release does not identify which correspondence identity owns "
                    "which progression label in multifocal cases."
                ),
            },
            {
                "severity": "HIGH_FOR_B4",
                "finding": (
                    f"{box_validation['rows_with_duplicate_box_labels_within_side']} "
                    "bbox rows repeat a Box label within at least one image side, and "
                    f"{semantics['progression_support_incompatible_rows']} rows lack "
                    "even set-level correspondence support for their progression label."
                ),
                "impact": (
                    "Case-local correspondence cannot be treated as a clean persistent-"
                    "entity oracle without an upstream correction or adjudicated mapping."
                ),
            },
            {
                "severity": "CRITICAL_FOR_B4",
                "finding": (
                    "Bounding-box labels are documented only as case-local correspondence "
                    "identities, not globally persistent lesion/entity IDs."
                ),
                "impact": (
                    "Five-label progression plus boxes does not automatically identify "
                    "the CAPES-CI persistent-entity causal estimand."
                ),
            },
            {
                "severity": "HIGH",
                "finding": "Parent images are not included in the annotation package.",
                "impact": (
                    "Image access, source licenses, patient-level lineage and image hashes "
                    "must qualify separately before any real run."
                ),
            },
            {
                "severity": "HIGH",
                "finding": "The dataset card describes gold as held-out evaluation.",
                "impact": (
                    "No model evaluation was run; a patient-level dev/power-dev/test seal "
                    "must be frozen before using any gold rows for method decisions."
                ),
            },
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(profile, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps({"status": profile["status"], "checks": checks}, sort_keys=True))
    return 0 if profile["status"] != "FAIL_DATA_QUALITY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
