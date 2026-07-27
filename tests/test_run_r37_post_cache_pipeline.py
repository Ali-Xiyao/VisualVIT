import json
from pathlib import Path

from scripts.run_r37_post_cache_pipeline import (
    passed_json,
    read_json,
    write_status,
)


def test_passed_json_requires_exact_status(tmp_path: Path):
    path = tmp_path / "result.json"
    path.write_text(json.dumps({"status": "PASS_EXPECTED"}), encoding="utf-8")
    assert passed_json(path, "PASS_EXPECTED")
    assert not passed_json(path, "PASS_OTHER")


def test_status_write_preserves_firewalls(tmp_path: Path):
    path = tmp_path / "status.json"
    write_status(path, "WAITING", stage="test")
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["status"] == "WAITING"
    assert payload["stage"] == "test"
    assert payload["protected_outcomes_read"] is False
    assert payload["source_hashes_recomputed"] is False


def test_reader_accepts_powershell_utf8_bom(tmp_path: Path):
    path = tmp_path / "powershell-status.json"
    path.write_text(
        json.dumps({"status": "WAITING"}), encoding="utf-8-sig"
    )
    assert read_json(path)["status"] == "WAITING"
