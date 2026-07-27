import json
from pathlib import Path

from scripts.run_r37_post_cache_pipeline import (
    passed_json,
    read_json,
    wait_for_block8,
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


def test_merged_block8_pass_recovers_from_stale_launcher_stop(
    tmp_path: Path,
):
    manifest = tmp_path / "cache_manifest.json"
    launcher = tmp_path / "launcher_status.json"
    status = tmp_path / "pipeline_status.json"
    log = tmp_path / "pipeline.log"
    manifest.write_text(
        json.dumps({"status": "PASS_R37_BLOCK8_FORMAL_CACHE"}),
        encoding="utf-8",
    )
    launcher.write_text(
        json.dumps({"status": "STOP_R37_BLOCK8_CACHE_PART_FAILURE"}),
        encoding="utf-8",
    )

    wait_for_block8(
        manifest=manifest,
        launcher_status=launcher,
        poll_seconds=1,
        status_path=status,
        log_path=log,
    )

    assert "Block-8 merged manifest passed" in log.read_text(
        encoding="utf-8"
    )


def test_powershell_launcher_only_rejects_known_nonzero_exit_codes():
    launcher = (
        Path(__file__).parents[1]
        / "scripts"
        / "launch_r37_block8_cache_when_idle.ps1"
    ).read_text(encoding="utf-8")
    assert (
        "$part0Failed = $null -ne $part0Exit "
        "-and [int]$part0Exit -ne 0"
    ) in launcher
    assert (
        "$part1Failed = $null -ne $part1Exit "
        "-and [int]$part1Exit -ne 0"
    ) in launcher
    assert "merge_r37_block8_cache_parts.py" in launcher
