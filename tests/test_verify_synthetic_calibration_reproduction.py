from __future__ import annotations

# ruff: noqa: E402

from pathlib import Path
import sys

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE))

from scripts.verify_synthetic_calibration_reproduction import (
    build_report,
    canonical_sha256,
    strip_runtime_fields,
)


def _summary(metric: float, walltime: float) -> dict[str, object]:
    return {
        "status": "COMPLETE",
        "config_sha256": "config",
        "source_hashes": {"manifest_sha256": "source"},
        "seed_results": [{"metric": metric, "walltime_seconds": walltime}],
        "mechanism_gate": {"pass": False},
        "walltime_seconds": walltime,
    }


def test_runtime_only_fields_do_not_change_registered_hash() -> None:
    first = _summary(metric=0.25, walltime=1.0)
    second = _summary(metric=0.25, walltime=99.0)
    assert strip_runtime_fields(first) == strip_runtime_fields(second)
    assert canonical_sha256(strip_runtime_fields(first)) == canonical_sha256(
        strip_runtime_fields(second)
    )
    report = build_report(first, second)
    assert report["status"] == "PASS"
    assert report["registered_mismatch_count"] == 0


def test_registered_metric_difference_fails_closed() -> None:
    report = build_report(
        _summary(metric=0.25, walltime=1.0),
        _summary(metric=0.30, walltime=1.0),
    )
    assert report["status"] == "FAIL"
    assert report["checks"]["all_registered_nonruntime_fields_exact"] is False
    assert report["registered_mismatch_paths"] == ["$.seed_results[0].metric"]
