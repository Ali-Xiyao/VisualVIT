from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


RUNTIME_ONLY_KEYS = frozenset({"walltime_seconds"})


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare two calibration summaries after removing runtime-only fields."
    )
    parser.add_argument("--run-a", type=Path, required=True)
    parser.add_argument("--run-b", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def strip_runtime_fields(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: strip_runtime_fields(item)
            for key, item in value.items()
            if key not in RUNTIME_ONLY_KEYS
        }
    if isinstance(value, list):
        return [strip_runtime_fields(item) for item in value]
    return value


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def diff_paths(first: Any, second: Any, prefix: str = "$") -> list[str]:
    if type(first) is not type(second):
        return [prefix]
    if isinstance(first, dict):
        paths: list[str] = []
        for key in sorted(set(first) | set(second)):
            path = f"{prefix}.{key}"
            if key not in first or key not in second:
                paths.append(path)
            else:
                paths.extend(diff_paths(first[key], second[key], path))
        return paths
    if isinstance(first, list):
        if len(first) != len(second):
            return [f"{prefix}.length"]
        paths = []
        for index, (left, right) in enumerate(zip(first, second, strict=True)):
            paths.extend(diff_paths(left, right, f"{prefix}[{index}]"))
        return paths
    return [] if first == second else [prefix]


def build_report(first: dict[str, Any], second: dict[str, Any]) -> dict[str, Any]:
    registered_a = strip_runtime_fields(first)
    registered_b = strip_runtime_fields(second)
    mismatches = diff_paths(registered_a, registered_b)
    checks = {
        "both_technically_complete": first.get("status")
        == second.get("status")
        == "COMPLETE",
        "config_sha256_equal": first.get("config_sha256")
        == second.get("config_sha256"),
        "source_manifest_sha256_equal": first.get("source_hashes", {}).get(
            "manifest_sha256"
        )
        == second.get("source_hashes", {}).get("manifest_sha256"),
        "seed_count_equal": len(first.get("seed_results", []))
        == len(second.get("seed_results", [])),
        "mechanism_gate_exact": first.get("mechanism_gate")
        == second.get("mechanism_gate"),
        "all_registered_nonruntime_fields_exact": not mismatches,
    }
    return {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "evidence_class": "ENGINEERING_CALIBRATION_REPRODUCTION",
        "formal_claim_allowed": False,
        "ignored_runtime_only_keys": sorted(RUNTIME_ONLY_KEYS),
        "checks": checks,
        "registered_sha256_a": canonical_sha256(registered_a),
        "registered_sha256_b": canonical_sha256(registered_b),
        "registered_mismatch_count": len(mismatches),
        "registered_mismatch_paths": mismatches[:100],
    }


def main() -> int:
    args = parse_args()
    summary_a = args.run_a / "summary.json"
    summary_b = args.run_b / "summary.json"
    first = json.loads(summary_a.read_text(encoding="utf-8"))
    second = json.loads(summary_b.read_text(encoding="utf-8"))
    report = build_report(first, second)
    report["run_a"] = str(args.run_a.resolve())
    report["run_b"] = str(args.run_b.resolve())
    report["summary_sha256_a"] = hashlib.sha256(summary_a.read_bytes()).hexdigest()
    report["summary_sha256_b"] = hashlib.sha256(summary_b.read_bytes()).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps(report, sort_keys=True))
    return 0 if report["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
