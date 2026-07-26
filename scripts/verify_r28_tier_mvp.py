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


PROCESS_A_DEFAULT = Path(
    r"F:\VisualVIT_runtime\050_routeC\r28_case_study_tier\tier_mvp_v1"
)
PROCESS_B_DEFAULT = Path(
    r"F:\VisualVIT_runtime\050_routeC\r28_case_study_tier\tier_mvp_v1_repro"
)
CERTIFICATE_DEFAULT = Path(
    r"F:\VisualVIT_runtime\050_routeC\r28_case_study_tier"
    r"\tier_mvp_v1_reproduction_certificate.json"
)
DETERMINISTIC_FILES = (
    "feature_manifest.json",
    "folds.json",
    "sanity_audit.json",
    "predictions.json",
    "router_audit.json",
    "bootstrap.json",
    "attempt_closure.json",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify fresh-process R28 TIER reproduction"
    )
    parser.add_argument("--process-a", type=Path, default=PROCESS_A_DEFAULT)
    parser.add_argument("--process-b", type=Path, default=PROCESS_B_DEFAULT)
    parser.add_argument("--certificate", type=Path, default=CERTIFICATE_DEFAULT)
    return parser.parse_args()


def _normalized_fit(path: Path) -> list[dict[str, Any]]:
    rows = r27.read_json(path, list)
    return [
        {
            key: value
            for key, value in row.items()
            if key != "runtime_seconds"
        }
        for row in rows
    ]


def verify(process_a: Path, process_b: Path) -> dict[str, Any]:
    manifests = {
        "a": r27.read_json(process_a / "artifact_manifest.json", dict),
        "b": r27.read_json(process_b / "artifact_manifest.json", dict),
    }
    checks: dict[str, bool] = {}
    for process, root in (("a", process_a), ("b", process_b)):
        manifest = manifests[process]
        checks[f"{process}:status"] = (
            manifest["status"] == "AWAITING_FRESH_PROCESS_REPRODUCTION"
        )
        checks[f"{process}:engineering"] = (
            manifest["engineering_passed"] is True
        )
        checks[f"{process}:scientific_no_go"] = (
            manifest["scientific_go"] is False
        )
        for name, expected in manifest["outputs"].items():
            checks[f"{process}:hash:{name}"] = (
                r27.sha256_file(root / name) == expected
            )
        checks[f"{process}:report_hash"] = (
            r27.sha256_file(Path(manifest["report"]["path"]))
            == manifest["report"]["sha256"]
        )
        for relative, expected in manifest["source_hashes"].items():
            checks[f"{process}:source:{relative}"] = (
                r27.sha256_file(WORKSPACE / relative) == expected
            )
        payload_hash = str(manifest.pop("manifest_payload_sha256"))
        checks[f"{process}:manifest_self_binding"] = (
            r27.canonical_sha256(manifest) == payload_hash
        )
        manifest["manifest_payload_sha256"] = payload_hash

    for name in DETERMINISTIC_FILES:
        checks[f"exact:{name}"] = (
            (process_a / name).read_bytes() == (process_b / name).read_bytes()
        )
    checks["normalized_fit_audit"] = (
        _normalized_fit(process_a / "fit_audit.json")
        == _normalized_fit(process_b / "fit_audit.json")
    )
    checks["report_content"] = (
        Path(manifests["a"]["report"]["path"]).read_text(encoding="utf-8")
        == Path(manifests["b"]["report"]["path"]).read_text(encoding="utf-8")
    )
    checks["protocol_equal"] = (
        manifests["a"]["protocol"] == manifests["b"]["protocol"]
    )
    checks["feature_cache_equal"] = (
        manifests["a"]["feature_cache"] == manifests["b"]["feature_cache"]
    )
    checks["source_hashes_equal"] = (
        manifests["a"]["source_hashes"] == manifests["b"]["source_hashes"]
    )
    checks["attempts_equal"] = (
        manifests["a"]["attempts"] == manifests["b"]["attempts"]
        == ["tier_a1", "tier_a2"]
    )
    failed = sorted(name for name, value in checks.items() if not value)
    return {
        "status": (
            "PASS_R28_TIER_FRESH_PROCESS_REPRODUCTION"
            if not failed
            else "FAIL_R28_TIER_REPRODUCTION"
        ),
        "qualified": not failed,
        "checks": checks,
        "passed": len(checks) - len(failed),
        "total": len(checks),
        "failed": failed,
        "process_a_manifest_sha256": r27.sha256_file(
            process_a / "artifact_manifest.json"
        ),
        "process_b_manifest_sha256": r27.sha256_file(
            process_b / "artifact_manifest.json"
        ),
        "deterministic_predictions_sha256": r27.sha256_file(
            process_a / "predictions.json"
        ),
        "scientific_go": False,
        "engineering_reproduced": not failed,
    }


def main() -> None:
    args = parse_args()
    result = verify(args.process_a, args.process_b)
    if args.certificate.exists():
        raise FileExistsError(f"certificate already exists: {args.certificate}")
    r27.write_json_exclusive(args.certificate, result)
    print(json.dumps(result, indent=2, sort_keys=True))
    if result["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
