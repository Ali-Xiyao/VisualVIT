from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Q6 fresh-process verifier for the R25 Chest ImaGenome real-data "
            "qualification.  Compares two process summaries and certifies "
            "independent reproduction only when every deterministic field is "
            "byte-identical."
        )
    )
    parser.add_argument(
        "--process-a",
        type=Path,
        required=True,
        help="Path to process A summary.json",
    )
    parser.add_argument(
        "--process-b",
        type=Path,
        required=True,
        help="Path to process B summary.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Path to write the Q6 reproduction certificate",
    )
    return parser.parse_args()


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} is not a JSON object")
    return value


# Fields that must be byte-identical between the two independent processes.
# Volatile fields (runtime timestamps, PIDs, UUIDs, wall-clock extraction
# seconds, peak VRAM) are excluded and checked separately as invariants.
EXACT_FIELDS = (
    "evidence_class",
    "formal_claim_allowed",
    "status",
    "protocol",
    "inputs",
    "cohort",
    "image_ledger_sha256",
    "feature_ledger_sha256",
    "prediction_sha256",
    "aggregate_sha256",
    "gates",
    "q7_power_estimate",
    "aggregate",
    "mechanics",
    "source",
    "interpretation_boundary",
)


def main() -> int:
    args = parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    first = _read(args.process_a)
    second = _read(args.process_b)

    exact_checks = {
        f"{field}_exact": first.get(field) == second.get(field)
        for field in EXACT_FIELDS
    }
    checks = {
        "process_roles_exact": (
            first.get("process_id") == "a" and second.get("process_id") == "b"
        ),
        "both_completed_evaluation": (
            first.get("status") is not None
            and second.get("status") is not None
            and first.get("status") != "TECHNICAL_FAILURE"
            and second.get("status") != "TECHNICAL_FAILURE"
        ),
        "distinct_process_ids": (
            first.get("runtime", {}).get("pid")
            != second.get("runtime", {}).get("pid")
            and first.get("runtime", {}).get("process_uuid")
            != second.get("runtime", {}).get("process_uuid")
        ),
        "encoder_invariants_exact": (
            first.get("encoder", {}).get("crop_count")
            == second.get("encoder", {}).get("crop_count")
            and first.get("encoder", {}).get("repeat_max_abs_difference")
            == second.get("encoder", {}).get("repeat_max_abs_difference")
            and first.get("encoder", {}).get("feature_cache", {}).get("bytes")
            == second.get("encoder", {}).get("feature_cache", {}).get("bytes")
            and first.get("encoder", {}).get("feature_cache", {}).get("sha256")
            == second.get("encoder", {}).get("feature_cache", {}).get("sha256")
        ),
        "bootstrap_seeds_exact": (
            first.get("runtime", {}).get("bootstrap_seed")
            == second.get("runtime", {}).get("bootstrap_seed")
            and first.get("runtime", {}).get("derangement_seed")
            == second.get("runtime", {}).get("derangement_seed")
            and first.get("runtime", {}).get("bootstrap_replicates")
            == second.get("runtime", {}).get("bootstrap_replicates")
        ),
        "r24_prerequisite_exact": (
            first.get("r24_prerequisite") == second.get("r24_prerequisite")
        ),
        **exact_checks,
    }
    passed = all(checks.values())
    certificate = {
        "status": (
            "PASS_Q6_FRESH_PROCESS_REPRODUCTION"
            if passed
            else "FAIL_Q6_FRESH_PROCESS_REPRODUCTION"
        ),
        "qualified": passed,
        "formal_claim_allowed": False,
        "evidence_class": "NON_CONFIRMATORY_REAL_DATA_QUALIFICATION",
        "checks": checks,
        "process_a": {
            "path": str(args.process_a.resolve()),
            "sha256": sha256_file(args.process_a),
            "pid": first.get("runtime", {}).get("pid"),
            "process_uuid": first.get("runtime", {}).get("process_uuid"),
        },
        "process_b": {
            "path": str(args.process_b.resolve()),
            "sha256": sha256_file(args.process_b),
            "pid": second.get("runtime", {}).get("pid"),
            "process_uuid": second.get("runtime", {}).get("process_uuid"),
        },
        "interpretation_boundary": (
            "Independent reproduction of a non-confirmatory real matcher "
            "qualification on the three-label persistent endpoint "
            "(Stable/Improved/Worse); no per-box progression, clinical, "
            "formal B4, frozen-VLM, or allocation-4161 claim."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(certificate, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps({"status": certificate["status"]}, sort_keys=True))
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
