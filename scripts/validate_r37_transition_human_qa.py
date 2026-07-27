from __future__ import annotations

import argparse
import csv
from datetime import date
import json
from pathlib import Path
from typing import Any, Iterable


LABELS = ("Stable", "Improved", "Worse", "New", "Resolved")
EXPECTED_ROWS = 200
EXPECTED_ROWS_PER_LABEL = 40
OVERALL_MINIMUM = 0.90
PER_LABEL_MINIMUM = 0.85
ERROR_CATEGORIES = frozenset(
    {
        "NEGATION_SCOPE",
        "UNCERTAINTY",
        "HISTORY_OR_INDICATION",
        "TECHNIQUE_OR_ARTIFACT",
        "FINDING_SCOPE",
        "TEMPORAL_DIRECTION",
        "ALTERNATIVE_OR_DIFFERENTIAL",
        "INSUFFICIENT_EVIDENCE",
        "OTHER",
    }
)
REQUIRED_COLUMNS = frozenset(
    {
        "case_id",
        "label",
        "human_direction_correct",
        "human_error_category",
        "human_notes",
    }
)


def read_rows(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = reader.fieldnames or []
        rows = [
            {key: str(value or "").strip() for key, value in row.items()}
            for row in reader
        ]
    return rows, columns


def validate_review(
    rows: Iterable[dict[str, str]],
    columns: Iterable[str],
    *,
    reviewer_name: str,
    reviewer_role: str,
    review_date: str,
    independent_review_confirmed: bool,
) -> dict[str, Any]:
    rows = list(rows)
    columns = list(columns)
    errors: list[str] = []
    missing_columns = sorted(REQUIRED_COLUMNS.difference(columns))
    if missing_columns:
        errors.append(f"missing columns: {missing_columns}")
    if len(rows) != EXPECTED_ROWS:
        errors.append(
            f"expected {EXPECTED_ROWS} rows, got {len(rows)}"
        )
    case_ids = [row.get("case_id", "") for row in rows]
    if any(not value for value in case_ids):
        errors.append("case_id contains blanks")
    if len(set(case_ids)) != len(case_ids):
        errors.append("case_id values are not unique")

    counts = {label: 0 for label in LABELS}
    correct = {label: 0 for label in LABELS}
    completed = 0
    for index, row in enumerate(rows, start=2):
        label = row.get("label", "")
        if label not in counts:
            errors.append(f"row {index}: invalid label {label!r}")
            continue
        counts[label] += 1
        judgment = row.get("human_direction_correct", "").upper()
        category = row.get("human_error_category", "").upper()
        notes = row.get("human_notes", "")
        if judgment not in {"TRUE", "FALSE"}:
            errors.append(
                f"row {index}: human_direction_correct must be TRUE or FALSE"
            )
            continue
        completed += 1
        if judgment == "TRUE":
            correct[label] += 1
            if category:
                errors.append(
                    f"row {index}: TRUE judgment must have blank error category"
                )
        else:
            if category not in ERROR_CATEGORIES:
                errors.append(
                    f"row {index}: invalid or blank error category {category!r}"
                )
            if category == "OTHER" and not notes:
                errors.append(f"row {index}: OTHER requires human_notes")

    for label in LABELS:
        if counts[label] != EXPECTED_ROWS_PER_LABEL:
            errors.append(
                f"{label}: expected {EXPECTED_ROWS_PER_LABEL} rows, "
                f"got {counts[label]}"
            )

    attestation = {
        "reviewer_name": reviewer_name.strip(),
        "reviewer_role": reviewer_role.strip(),
        "review_date": review_date.strip(),
        "independent_review_confirmed": independent_review_confirmed,
    }
    if not attestation["reviewer_name"]:
        errors.append("reviewer name or institutional ID is required")
    if not attestation["reviewer_role"]:
        errors.append("reviewer professional role is required")
    try:
        date.fromisoformat(attestation["review_date"])
    except ValueError:
        errors.append("review date must use YYYY-MM-DD")
    if not independent_review_confirmed:
        errors.append("independent review confirmation is required")

    overall_accuracy = (
        sum(correct.values()) / len(rows) if rows else 0.0
    )
    per_label_accuracy = {
        label: correct[label] / counts[label] if counts[label] else 0.0
        for label in LABELS
    }
    thresholds_pass = (
        completed == EXPECTED_ROWS
        and overall_accuracy >= OVERALL_MINIMUM
        and all(
            value >= PER_LABEL_MINIMUM
            for value in per_label_accuracy.values()
        )
    )
    passed = not errors and thresholds_pass
    return {
        "schema": "visualvit.r37.transition-human-qa.v1",
        "status": (
            "PASS_R37_TRANSITION_HUMAN_QA"
            if passed
            else "STOP_R37_TRANSITION_HUMAN_QA"
        ),
        "formal_training_unlocked": passed,
        "rows": len(rows),
        "completed_rows": completed,
        "label_counts": counts,
        "correct_counts": correct,
        "overall_accuracy": overall_accuracy,
        "per_label_accuracy": per_label_accuracy,
        "thresholds": {
            "overall_minimum": OVERALL_MINIMUM,
            "per_label_minimum": PER_LABEL_MINIMUM,
            "all_rows_required": True,
        },
        "thresholds_pass": thresholds_pass,
        "attestation": attestation,
        "errors": errors,
        "protected_outcomes_read": False,
        "sealed_test_read": False,
        "gold_outcomes_read": False,
        "source_hashes_recomputed": False,
        "scientific_claim_allowed": False,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate the frozen independent R37 transition QA sheet"
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reviewer-name", required=True)
    parser.add_argument("--reviewer-role", required=True)
    parser.add_argument("--review-date", required=True)
    parser.add_argument(
        "--independent-review-confirmed",
        action="store_true",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rows, columns = read_rows(args.input)
    result = validate_review(
        rows,
        columns,
        reviewer_name=args.reviewer_name,
        reviewer_role=args.reviewer_role,
        review_date=args.review_date,
        independent_review_confirmed=args.independent_review_confirmed,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["formal_training_unlocked"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
