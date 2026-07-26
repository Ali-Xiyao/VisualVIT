from __future__ import annotations

# ruff: noqa: E402

from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE))
sys.path.insert(0, str(WORKSPACE / "src"))

from scripts import audit_r26_binding_identifiability as r27
from scripts import run_r31_confidence_consensus as r31


PRIMARY_ROOT = Path(
    r"F:\VisualVIT_runtime\050_routeC\r31_confidence_consensus\run_v1"
)
REPRO_ROOT = Path(
    r"F:\VisualVIT_runtime\050_routeC\r31_confidence_consensus\run_v1_repro"
)
OUTPUT_ROOT_DEFAULT = Path(
    r"F:\VisualVIT_runtime\050_routeC\r31_confidence_consensus"
    r"\reproduction_verification_v1"
)
REPORT_PATH_DEFAULT = (
    WORKSPACE / "reports/R31_CONFIDENCE_CONSENSUS_FINAL.md"
)
EXACT_OUTPUTS = (
    "case_audit.json",
    "baseline_representation_manifest.json",
    "regularized_representation_manifest.json",
    "dev_predictions.json",
    "dev_gate.json",
    "test_predictions.json",
    "test_result.json",
)


def read(path: Path) -> Any:
    return r27.read_json(path, (dict, list))


def verify(primary: Path, reproduction: Path) -> dict[str, Any]:
    first_manifest = read(primary / "artifact_manifest.json")
    second_manifest = read(reproduction / "artifact_manifest.json")
    checks = {
        "PRIMARY_AWAITING_REPRO": (
            first_manifest["status"]
            == "AWAITING_FRESH_PROCESS_REPRODUCTION"
        ),
        "REPRO_AWAITING_REPRO": (
            second_manifest["status"]
            == "AWAITING_FRESH_PROCESS_REPRODUCTION"
        ),
        "PROTOCOL_MATCH": (
            first_manifest["protocol_sha256"]
            == second_manifest["protocol_sha256"]
            == r31.PROTOCOL_SHA256
        ),
        "COHORT_MATCH": (
            first_manifest["cohort_sha256"]
            == second_manifest["cohort_sha256"]
            == r31.COHORT_SHA256
        ),
        "WEIGHTS_MATCH": (
            first_manifest["weights_sha256"]
            == second_manifest["weights_sha256"]
            == r31.WEIGHTS_SHA256
        ),
        "SOURCE_HASHES_MATCH": (
            first_manifest["source_hashes"]
            == second_manifest["source_hashes"]
        ),
        "FEATURE_CACHE_MATCH": (
            first_manifest["feature_cache_sha256"]
            == second_manifest["feature_cache_sha256"]
        ),
        "REPORT_MATCH": (
            first_manifest["report"]["sha256"]
            == second_manifest["report"]["sha256"]
        ),
    }
    exact_hashes = {}
    for name in EXACT_OUTPUTS:
        first = r27.sha256_file(primary / name)
        second = r27.sha256_file(reproduction / name)
        exact_hashes[name] = {"primary": first, "reproduction": second}
        checks[f"EXACT_{name.upper().replace('.', '_')}"] = first == second
    test = read(primary / "test_result.json")
    dev = read(primary / "dev_gate.json")
    contrast = test["bootstrap"]["contrasts"]["consensus_minus_uniform"]
    checks.update(
        {
            "DEV_PASSED": dev["passed"] is True,
            "TEST_PRE_REPRO_PASSED": test["pre_reproduction_go"] is True,
            "DELTA_AT_LEAST_2PP": contrast["point_pp"] >= 2.0,
            "CI_LOWER_POSITIVE": contrast["interval"]["lower"] > 0,
            "ALL_DIRECTIONS_POSITIVE": all(
                value > 0 for value in test["directions"].values()
            ),
            "BOOTSTRAP_VALID": (
                test["bootstrap"]["inference_valid"]
                and test["bootstrap"]["valid_replicates"] == 10_000
            ),
            "PREDICTIONS_COMPLETE": test["consensus_audit"]["complete"],
        }
    )
    return {
        "status": (
            "PASS_R31_SCIENTIFIC_GO_REPRODUCED"
            if all(checks.values())
            else "FAIL_R31_REPRODUCTION"
        ),
        "scientific_go": bool(all(checks.values())),
        "checks": checks,
        "exact_output_hashes": exact_hashes,
        "primary_manifest_sha256": r27.sha256_file(
            primary / "artifact_manifest.json"
        ),
        "reproduction_manifest_sha256": r27.sha256_file(
            reproduction / "artifact_manifest.json"
        ),
        "effect": {
            "consensus_macro_f1": test["bootstrap"][
                "point_system_macro_f1"
            ]["confidence_consensus"],
            "uniform_macro_f1": test["bootstrap"][
                "point_system_macro_f1"
            ]["uniform_fusion"],
            "delta_pp": contrast["point_pp"],
            "ci_lower_pp": 100 * contrast["interval"]["lower"],
            "ci_upper_pp": 100 * contrast["interval"]["upper"],
            "directions": test["directions"],
        },
        "evidence_class": "NON_CONFIRMATORY_FRESH_SILVER_DEVELOPMENT",
        "r26_human_gold_status": "STOP_C1_UNCHANGED",
    }


def render(result: dict[str, Any]) -> str:
    effect = result["effect"]
    return "\n".join(
        [
            "# R31 Confidence-Consensus Final Closure",
            "",
            "Date: 2026-07-26",
            "",
            f"Status: `{result['status']}`",
            "",
            "## Frozen one-shot result",
            "",
            f"- Consensus macro F1: {effect['consensus_macro_f1']:.4f}",
            f"- Uniform fusion macro F1: {effect['uniform_macro_f1']:.4f}",
            f"- Delta: {effect['delta_pp']:+.2f} pp",
            f"- 95% CI: [{effect['ci_lower_pp']:+.2f}, "
            f"{effect['ci_upper_pp']:+.2f}] pp",
            f"- Per-seed directions: {effect['directions']}",
            "- Bootstrap: 10,000/10,000 valid replicates",
            "",
            "## Reproduction",
            "",
            "- Fresh process: pass",
            "- Protocol/cohort/weights/source hashes: exact match",
            "- Dev/test predictions and scientific result: exact hash match",
            "- Final scientific gate: GO",
            "",
            "## Claim boundary",
            "",
            "This is a fresh-silver, patient-disjoint development GO for the "
            "confidence-consensus tier. It does not reverse the human-gold "
            "R26 `STOP_C1`; external expert-labeled confirmation remains "
            "required.",
            "",
        ]
    )


def main() -> None:
    output_root = OUTPUT_ROOT_DEFAULT
    report_path = REPORT_PATH_DEFAULT
    if output_root.exists():
        raise FileExistsError(f"output root must be fresh: {output_root}")
    if report_path.exists():
        raise FileExistsError(f"report path must be fresh: {report_path}")
    result = verify(PRIMARY_ROOT, REPRO_ROOT)
    if not result["scientific_go"]:
        raise RuntimeError("R31 reproduction verification failed")
    output_root.mkdir(parents=True, exist_ok=False)
    r27.write_json_exclusive(output_root / "verification.json", result)
    report_path.write_text(render(result), encoding="utf-8")
    base = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": result["status"],
        "scientific_go": True,
        "verification_sha256": r27.sha256_file(
            output_root / "verification.json"
        ),
        "report_sha256": r27.sha256_file(report_path),
        "verifier_sha256": r27.sha256_file(Path(__file__)),
    }
    manifest = {
        **base,
        "manifest_payload_sha256": r27.canonical_sha256(base),
    }
    r27.write_json_exclusive(output_root / "manifest.json", manifest)
    print(json.dumps({"manifest": manifest, "result": result}, indent=2))


if __name__ == "__main__":
    main()
