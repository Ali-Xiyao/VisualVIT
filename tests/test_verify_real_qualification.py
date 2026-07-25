from __future__ import annotations

import json
from pathlib import Path

from scripts import verify_chextemporal_mimic_matcher_reproduction as verifier


def _summary(role: str, pid: int, process_uuid: str) -> dict[str, object]:
    return {
        "process_id": role,
        "status": "AWAITING_FRESH_PROCESS_REPRODUCTION",
        "evidence_class": "NON_CONFIRMATORY_REAL_DATA_QUALIFICATION",
        "formal_claim_allowed": False,
        "protocol": {"sha256": "protocol"},
        "inputs": {"weights": {"sha256": "weights"}},
        "cohort": {"retained_rows": 267},
        "image_ledger_sha256": "images",
        "feature_ledger_sha256": "features",
        "prediction_sha256": "predictions",
        "aggregate_sha256": "aggregate",
        "gates": {"Q0": True},
        "aggregate": {"metric": 1.0},
        "mechanics": {"passed": True},
        "encoder": {"crop_count": 10},
        "source": {"runner_sha256": "runner"},
        "interpretation_boundary": "boundary",
        "runtime": {"pid": pid, "process_uuid": process_uuid},
    }


def test_verifier_requires_distinct_processes_and_exact_outputs(
    tmp_path: Path,
    monkeypatch,
) -> None:
    first = tmp_path / "a.json"
    second = tmp_path / "b.json"
    output = tmp_path / "certificate.json"
    first.write_text(json.dumps(_summary("a", 101, "uuid-a")), encoding="utf-8")
    second.write_text(json.dumps(_summary("b", 202, "uuid-b")), encoding="utf-8")
    monkeypatch.setattr(
        verifier,
        "parse_args",
        lambda: type(
            "Args",
            (),
            {"process_a": first, "process_b": second, "output": output},
        )(),
    )

    assert verifier.main() == 0
    certificate = json.loads(output.read_text(encoding="utf-8"))
    assert certificate["qualified"] is True
    assert certificate["checks"]["distinct_process_ids"] is True


def test_verifier_fails_on_prediction_drift(tmp_path: Path, monkeypatch) -> None:
    first = tmp_path / "a.json"
    second = tmp_path / "b.json"
    output = tmp_path / "certificate.json"
    a = _summary("a", 101, "uuid-a")
    b = _summary("b", 202, "uuid-b")
    b["prediction_sha256"] = "drift"
    first.write_text(json.dumps(a), encoding="utf-8")
    second.write_text(json.dumps(b), encoding="utf-8")
    monkeypatch.setattr(
        verifier,
        "parse_args",
        lambda: type(
            "Args",
            (),
            {"process_a": first, "process_b": second, "output": output},
        )(),
    )

    assert verifier.main() == 2
    certificate = json.loads(output.read_text(encoding="utf-8"))
    assert certificate["qualified"] is False
    assert certificate["checks"]["prediction_sha256_exact"] is False
