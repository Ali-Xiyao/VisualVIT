from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable, Mapping


EXPECTED_LABELS = {
    "Improved": 127,
    "New": 58,
    "Resolved": 29,
    "Stable": 251,
    "Worse": 136,
}
FULL_SYSTEMS = {
    "current_only_global",
    "paired_global",
    "oracle_region",
    "learned_region",
    "oracle_no_interaction",
}
B4_SYSTEMS = {
    "B4a_deranged",
    "B4b_oracle",
    "learned_region",
    "paired_global",
    "current_only_global",
    "oracle_no_interaction",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read(path: Path, expected_type: type) -> Any:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, expected_type):
        raise ValueError(f"{path} must contain {expected_type.__name__}")
    return value


def non_deranged_predictions_invariant(
    predictions: Iterable[Mapping[str, Any]],
) -> bool:
    grouped: dict[tuple[str, str, int], set[str]] = defaultdict(set)
    for row in predictions:
        if row["system"] == "B4a_deranged":
            continue
        key = (row["observation_id"], row["system"], row["training_seed"])
        grouped[key].add(row["prediction"])
    return len(grouped) == 90 * 5 * 3 and all(
        len(values) == 1 for values in grouped.values()
    )


def verify_result(result_root: Path) -> dict[str, Any]:
    summary_path = result_root / "summary.json"
    summary = _read(summary_path, dict)
    cohort = _read(result_root / "cohort.json", list)
    folds = _read(result_root / "folds.json", dict)
    predictions = _read(result_root / "predictions.json", dict)
    fit_audit = _read(result_root / "fit_audit.json", dict)
    b4_audit = _read(result_root / "b4_isomorphism.json", list)

    checks: dict[str, bool] = {
        "status_exact": (
            summary.get("status") == "PASS_NONCONFIRMATORY_REAL_DATA_SECONDARY"
        ),
        "evidence_class_exact": (
            summary.get("evidence_class") == "NON_CONFIRMATORY_REAL_DATA_SECONDARY"
        ),
        "formal_claim_locked": summary.get("formal_entity_claim_allowed") is False,
        "clinical_claim_locked": summary.get("clinical_claim_allowed") is False,
        "all_declared_gates": all(summary.get("gates", {}).values()),
    }
    artifacts = summary.get("artifacts", {})
    for name, expected_hash in artifacts.items():
        path = result_root / name
        checks[f"artifact_hash:{name}"] = (
            path.is_file() and sha256_file(path) == expected_hash
        )

    checks.update(
        {
            "cohort_rows_exact": len(cohort) == 601,
            "cohort_patients_exact": (len({row["patient_id"] for row in cohort}) == 70),
            "cohort_labels_exact": (
                Counter(row["progression"] for row in cohort)
                == Counter(EXPECTED_LABELS)
            ),
            "fold_patient_counts_exact": (
                len(folds["full_assignment"]) == 70
                and len(folds["b4_assignment"]) == 22
            ),
            "fold_ranges_exact": (
                set(folds["full_assignment"].values()) == set(range(5))
                and set(folds["b4_assignment"].values()) == set(range(5))
            ),
            "full_prediction_count_exact": (
                len(predictions["full"]) == 601 * len(FULL_SYSTEMS) * 3
            ),
            "b4_prediction_count_exact": (
                len(predictions["b4"]) == 90 * len(B4_SYSTEMS) * 3 * 3
            ),
            "fit_audit_counts_exact": (
                len(fit_audit["full"]) == 75 and len(fit_audit["b4"]) == 120
            ),
            "fit_audit_finite": all(
                math.isfinite(row["final_loss"]) and 0.0 <= row["train_accuracy"] <= 1.0
                for partition in fit_audit.values()
                for row in partition
            ),
            "b4_isomorphism_rows_exact": len(b4_audit) == 90,
            "b4_isomorphism_all_pass": all(
                row["passed"]
                and len(row["derangements"]) == 3
                and all(
                    derangement["passed"] and all(derangement["checks"].values())
                    for derangement in row["derangements"]
                )
                for row in b4_audit
            ),
            "b4_non_deranged_predictions_invariant": (
                non_deranged_predictions_invariant(predictions["b4"])
            ),
            "full_prediction_patients_known": all(
                row["patient_id"] in folds["full_assignment"]
                for row in predictions["full"]
            ),
            "b4_prediction_patients_known": all(
                row["patient_id"] in folds["b4_assignment"] for row in predictions["b4"]
            ),
        }
    )

    full_contrast = summary["metrics"]["full_bootstrap"]["contrasts"][
        "oracle_minus_paired_global"
    ]
    b4_contrast = summary["metrics"]["b4_bootstrap"]["contrasts"]["B4b_minus_B4a"]
    checks["full_region_contrast_positive"] = full_contrast["interval"]["lower"] > 0.0
    checks["b4_identity_interval_contains_zero"] = (
        b4_contrast["interval"]["lower"] <= 0.0 <= b4_contrast["interval"]["upper"]
    )

    failed = sorted(name for name, passed in checks.items() if not passed)
    return {
        "status": (
            "PASS_INDEPENDENT_RESULT_AUDIT"
            if not failed
            else "FAIL_INDEPENDENT_RESULT_AUDIT"
        ),
        "passed": not failed,
        "checks": checks,
        "failed_checks": failed,
        "summary": {
            "path": str(summary_path.resolve()),
            "sha256": sha256_file(summary_path),
        },
        "counts": {
            "cohort_rows": len(cohort),
            "full_predictions": len(predictions["full"]),
            "b4_predictions": len(predictions["b4"]),
            "full_fits": len(fit_audit["full"]),
            "b4_fits": len(fit_audit["b4"]),
        },
        "registered_inference": {
            "full_oracle_minus_paired_global": full_contrast,
            "b4b_minus_b4a": b4_contrast,
        },
        "interpretation_boundary": (
            "The full five-label result is a set-level structural upper bound. "
            "The strict B4 identity contrast is not established because its "
            "registered 95% interval contains zero. No formal entity-level or "
            "clinical claim is unlocked."
        ),
    }


def main() -> int:
    args = parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    certificate = verify_result(args.result_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(certificate, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "failed_checks": certificate["failed_checks"],
                "status": certificate["status"],
            },
            sort_keys=True,
        )
    )
    return 0 if certificate["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
