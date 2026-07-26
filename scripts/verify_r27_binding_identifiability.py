from __future__ import annotations

# ruff: noqa: E402

import argparse
import json
from pathlib import Path
import sys
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE))

from scripts import audit_r26_binding_identifiability as r27


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Independently verify the frozen R27 exploratory package"
    )
    parser.add_argument(
        "--r27-root", type=Path, default=r27.OUTPUT_ROOT_DEFAULT
    )
    return parser.parse_args()


def verify(root: Path) -> dict[str, Any]:
    manifest_path = root / "artifact_manifest.json"
    manifest = r27.read_json(manifest_path, dict)
    checks: dict[str, bool] = {}

    checks["terminal_status"] = (
        manifest.get("status") == "C_SPARSE_HIGH_BII_SUPPORT"
    )
    checks["exploratory_only"] = manifest.get("exploratory_only") is True
    checks["formal_claim_blocked"] = (
        manifest.get("formal_claim_allowed") is False
    )
    checks["r28_locked"] = manifest.get("r28_unlocked") is False
    checks["assignment_provenance_explicit"] = (
        manifest.get("assignment_source") == "DETERMINISTIC_RECONSTRUCTION"
        and manifest.get("assignment_indices_serialized_by_r26") is False
    )
    checks["protocol_hash"] = (
        r27.sha256_file(r27.PROTOCOL_PATH) == manifest["protocol"]["sha256"]
        == r27.PROTOCOL_SHA256
    )

    for name, expected in manifest["r26_input_hashes"].items():
        checks[f"r26_input:{name}"] = (
            r27.sha256_file(Path(manifest["r26_root"]) / name) == expected
            == r27.R26_INPUT_HASHES[name]
        )
    for relative, expected in manifest["frozen_source_hashes"].items():
        checks[f"frozen_source:{relative}"] = (
            r27.sha256_file(WORKSPACE / relative) == expected
            == r27.FROZEN_SOURCE_HASHES[relative]
        )
    for name, expected in manifest["outputs"].items():
        checks[f"r27_output:{name}"] = r27.sha256_file(root / name) == expected
    for relative, expected in manifest["r27_source_hashes"].items():
        checks[f"r27_source:{relative}"] = (
            r27.sha256_file(WORKSPACE / relative) == expected
        )
    report_path = Path(manifest["report"]["path"])
    checks["report_hash"] = (
        r27.sha256_file(report_path) == manifest["report"]["sha256"]
    )

    payload_hash = str(manifest.pop("manifest_payload_sha256"))
    checks["manifest_payload_self_binding"] = (
        r27.canonical_sha256(manifest) == payload_hash
    )
    manifest["manifest_payload_sha256"] = payload_hash

    composition = r27.read_json(root / "pair_label_composition.json", dict)
    semantic = r27.read_json(root / "derangement_semantic_audit.json", dict)
    stratified = r27.read_json(root / "bii_stratified_effects.json", dict)
    support = r27.read_json(root / "support_audit.json", dict)
    checks["pair_count"] = len(composition["pairs"]) == 170
    checks["semantic_assignment_count"] = (
        len(semantic["records"]) == 774 * len(r27.DERANGEMENT_IDS)
    )
    checks["zero_fixed_points"] = (
        semantic["overall"]["zero_fixed_points"] == 0
        and all(item["zero_fixed_point"] for item in semantic["records"])
    )
    checks["cohort_conservation"] = (
        support["cohort_conservation"]["passed"] is True
        and support["cohort_conservation"]["patients"] == 170
        and support["cohort_conservation"]["entities"] == 774
    )
    checks["strata_complete"] = (
        set(stratified["strata"]) == set(r27.STRATUM_ORDER)
    )
    checks["patient_only_bootstrap"] = all(
        value["bootstrap"]["resampled_levels"] == ["patient"]
        and value["bootstrap"]["fixed_levels"]
        == ["training_seed", "derangement_id"]
        for value in stratified["strata"].values()
    )
    checks["report_boundary"] = (
        "`exploratory_only=true`" in report_path.read_text(encoding="utf-8")
        and "`r28_unlocked=false`" in report_path.read_text(encoding="utf-8")
    )

    failed = sorted(name for name, passed in checks.items() if not passed)
    return {
        "status": "PASS_R27_INDEPENDENT_VERIFICATION" if not failed else "FAIL",
        "checks": checks,
        "passed": len(checks) - len(failed),
        "total": len(checks),
        "failed": failed,
        "manifest_sha256": r27.sha256_file(manifest_path),
    }


def main() -> None:
    result = verify(parse_args().r27_root)
    print(json.dumps(result, indent=2, sort_keys=True))
    if result["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
