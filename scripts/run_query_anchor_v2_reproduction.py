from __future__ import annotations

# ruff: noqa: E402

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any


WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE))

from scripts.run_query_anchor_v2 import (
    REGISTERED_STEPS,
    TRAINABLE_SEEDS,
    _compare_independent_reproduction,
)


PENDING_STATUS = "PASS_GATES_1_TO_6_AWAITING_INDEPENDENT_REPRODUCTION"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run two fresh CAPES-CI query-anchor processes and certify Gate 7 "
            "after registered Gates 1-6."
        )
    )
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--steps", type=int, default=REGISTERED_STEPS)
    parser.add_argument("--seeds", type=int, nargs="+", default=list(TRAINABLE_SEEDS))
    parser.add_argument("--device", choices=("cpu",), default="cpu")
    return parser


def _child_command(args: argparse.Namespace, run_dir: Path) -> list[str]:
    return [
        sys.executable,
        str((WORKSPACE / "scripts" / "run_query_anchor_v2.py").resolve()),
        "--run-dir",
        str(run_dir),
        "--steps",
        str(args.steps),
        "--seeds",
        *(str(seed) for seed in args.seeds),
        "--device",
        args.device,
    ]


def _run_child(
    args: argparse.Namespace, name: str
) -> tuple[subprocess.CompletedProcess[str], dict[str, Any], Path, int]:
    child_dir = args.run_dir / name
    environment = os.environ.copy()
    environment.update(
        {
            "PYTHONHASHSEED": "0",
            "OMP_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
        }
    )
    command = _child_command(args, child_dir)
    process = subprocess.Popen(
        command,
        cwd=WORKSPACE,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    stdout, stderr = process.communicate()
    completed = subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
    (args.run_dir / f"{name}.stdout.log").write_text(completed.stdout, encoding="utf-8")
    (args.run_dir / f"{name}.stderr.log").write_text(completed.stderr, encoding="utf-8")
    summary_path = child_dir / "summary.json"
    if not summary_path.exists():
        summary = {"status": "MISSING_CHILD_SUMMARY"}
    else:
        try:
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            summary = {
                "status": "MALFORMED_CHILD_SUMMARY",
                "error_type": type(error).__name__,
            }
    return completed, summary, summary_path, process.pid


def _raw_file_sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(args: argparse.Namespace) -> dict[str, Any]:
    primary_process, primary, primary_path, primary_pid = _run_child(args, "process_a")
    if primary_process.returncode != 0 or primary.get("status") != PENDING_STATUS:
        return {
            "status": "STOP_PRIMARY_GATES_1_TO_6",
            "formal_claim_allowed": False,
            "primary_process_returncode": primary_process.returncode,
            "primary_status": primary.get("status"),
            "primary_summary_path": str(primary_path.resolve()),
            "primary_summary_raw_sha256": _raw_file_sha256(primary_path),
            "primary_launcher_pid": primary_pid,
            "replica_launched": False,
        }

    replica_process, replica, replica_path, replica_pid = _run_child(args, "process_b")
    gate = _compare_independent_reproduction(
        primary,
        replica,
        primary_returncode=primary_process.returncode,
        replica_returncode=replica_process.returncode,
        primary_expected_pid=primary_pid,
        replica_expected_pid=replica_pid,
    )
    gate.update(
        {
            "primary_summary_path": str(primary_path.resolve()),
            "replica_summary_path": str(replica_path.resolve()),
            "primary_summary_raw_sha256": _raw_file_sha256(primary_path),
            "replica_summary_raw_sha256": _raw_file_sha256(replica_path),
            "launcher_source_sha256": _raw_file_sha256(Path(__file__).resolve()),
        }
    )
    return {
        "status": (
            "PASS_QUERY_ANCHOR" if gate["passed"] else "STOP_INDEPENDENT_REPRODUCTION"
        ),
        "formal_claim_allowed": False,
        "formal_ablation_claim_allowed": False,
        "full_method_claim_allowed": False,
        "independent_process_reproduction_gate": gate,
    }


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    args.run_dir = args.run_dir.resolve()
    args.run_dir.mkdir(parents=True, exist_ok=False)
    certificate = run(args)
    certificate_path = args.run_dir / "reproduction_certificate.json"
    certificate_path.write_text(
        json.dumps(certificate, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps(certificate, sort_keys=True))
    print(f"CERTIFICATE={certificate_path.resolve()}")
    return 0 if certificate["status"] == "PASS_QUERY_ANCHOR" else 3


if __name__ == "__main__":
    raise SystemExit(main())
