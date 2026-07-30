from __future__ import annotations

# ruff: noqa: E402

import argparse
import json
from pathlib import Path
import sys
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE))
sys.path.insert(0, str(WORKSPACE / "src"))

from scripts.build_prta_gen_r40b_smoke_cohort import read_json, write_json
from scripts.run_prta_gen_r41a_authorized_sequence import (
    _run_logged,
    sequence_preflight as r41a_sequence_preflight,
    utc_now,
)
from scripts.run_prta_gen_r42a_grounding_reversal import (
    preflight as r42a_runner_preflight,
)


CHAIN_STATUS = "RUNNING_PRTA_GEN_R41_R43_AUTHORIZED_CHAIN"
ENGINEERING_STOP = "STOP_PRTA_GEN_R41_R43_CHAIN_ENGINEERING"
TERMINAL_STATUSES = {
    "STOP_PRTA_GEN_R41A_PROGRESSION_SFT_SURVIVAL",
    "STOP_PRTA_GEN_R42A_GROUNDING_REVERSAL_SURVIVAL",
    "STOP_PRTA_GEN_R43_CONFIRMATORY_READINESS",
}


def chain_preflight(
    *,
    r41_config_path: Path,
    r42_config_path: Path,
    r43_config_path: Path,
    roster_path: Path,
    roster_sha256: str,
    devices: tuple[str, str],
) -> dict[str, Any]:
    r41_config, r41_receipt = r41a_sequence_preflight(
        config_path=r41_config_path,
        roster_path=roster_path,
        roster_sha256=roster_sha256,
        devices=devices,
    )
    r42_receipt = r42a_runner_preflight(r42_config_path)
    r43_config = read_json(r43_config_path)
    if (
        r43_config.get("status")
        != "FROZEN_PRTA_GEN_R43_CONFIRMATORY_READINESS"
        or r43_config["firewall"]["outcomes_read"] is not False
        or r43_config["firewall"]["predictions_generated"] is not False
        or r43_config["firewall"]["scientific_claim_allowed"] is not False
    ):
        raise PermissionError("R43 readiness authority drift")
    chain_root = (
        Path(r41_config["runtime"]["root"]).parent
        / "prta_gen_r41_r43_authorized_chain_v1"
    )
    if chain_root.exists():
        raise FileExistsError(
            f"R41-R43 chain output must be fresh: {chain_root}"
        )
    return {
        "schema": "visualvit.prta-gen.r41-r43-chain-preflight.v1",
        "status": "PASS_PRTA_GEN_R41_R43_CHAIN_PREFLIGHT",
        "r41_protocol_id": r41_config["protocol_id"],
        "r42_protocol_id": r42_receipt["protocol_id"],
        "r43_protocol_id": r43_config["protocol_id"],
        "roster_sha256": r41_receipt["roster_sha256"],
        "devices": list(devices),
        "gate_order": ["R41A", "R42A", "R43"],
        "automatic_continuation_authorized": True,
        "stop_at_first_failed_gate": True,
        "retry_allowed": False,
        "protected_300_dev_read": False,
        "revealed_483_test_read": False,
        "gold_outcomes_read": False,
        "external_outcomes_read": False,
    }


def _validate_stage_status(
    stage: str, status: dict[str, Any]
) -> tuple[bool, str]:
    aggregate = status.get("aggregate_receipt", {})
    terminal = str(status.get("status", ""))
    if stage == "R41A":
        if (
            aggregate.get("gate_passed") is True
            and terminal == "GO_PRTA_GEN_R41A_PROGRESSION_SFT_SURVIVAL"
        ):
            return True, terminal
        if (
            aggregate.get("gate_passed") is False
            and terminal == "STOP_PRTA_GEN_R41A_PROGRESSION_SFT_SURVIVAL"
        ):
            return False, terminal
    elif stage == "R42A":
        if (
            aggregate.get("gate_passed") is True
            and terminal == "GO_PRTA_GEN_R42A_GROUNDING_REVERSAL_SURVIVAL"
        ):
            return True, terminal
        if (
            aggregate.get("gate_passed") is False
            and terminal == "STOP_PRTA_GEN_R42A_GROUNDING_REVERSAL_SURVIVAL"
        ):
            return False, terminal
    raise PermissionError(f"{stage} sequence terminal receipt drift")


def run_chain(
    *,
    r41_config_path: Path,
    r42_config_path: Path,
    r43_config_path: Path,
    roster_path: Path,
    roster_sha256: str,
    devices: tuple[str, str],
) -> dict[str, Any]:
    preflight = chain_preflight(
        r41_config_path=r41_config_path,
        r42_config_path=r42_config_path,
        r43_config_path=r43_config_path,
        roster_path=roster_path,
        roster_sha256=roster_sha256,
        devices=devices,
    )
    r41_config = read_json(r41_config_path)
    chain_root = (
        Path(r41_config["runtime"]["root"]).parent
        / "prta_gen_r41_r43_authorized_chain_v1"
    )
    chain_root.mkdir(parents=True, exist_ok=False)
    logs = chain_root / "logs"
    status_path = chain_root / "sequence_status.json"
    status: dict[str, Any] = {
        "schema": "visualvit.prta-gen.r41-r43-chain-status.v1",
        "status": CHAIN_STATUS,
        "started_at_utc": utc_now(),
        "updated_at_utc": utc_now(),
        "current_stage": "R41A",
        "completed_stage_receipts": [],
        "gate_order": preflight["gate_order"],
        "roster_sha256": preflight["roster_sha256"],
        "devices": list(devices),
        "automatic_continuation_authorized": True,
        "stop_at_first_failed_gate": True,
        "retry_allowed": False,
        "protected_300_dev_read": False,
        "revealed_483_test_read": False,
        "gold_outcomes_read": False,
        "external_outcomes_read": False,
    }
    write_json(status_path, status)
    try:
        r41_exit = _run_logged(
            [
                sys.executable,
                str(
                    WORKSPACE
                    / "scripts"
                    / "run_prta_gen_r41a_authorized_sequence.py"
                ),
                "--config",
                str(r41_config_path),
                "--roster",
                str(roster_path),
                "--roster-sha256",
                roster_sha256,
                "--devices",
                *devices,
            ],
            stdout_path=logs / "r41a.stdout.log",
            stderr_path=logs / "r41a.stderr.log",
        )
        if r41_exit not in (0, 2):
            raise RuntimeError(f"R41A sequence exited with code {r41_exit}")
        r41_status = read_json(
            Path(r41_config["runtime"]["root"]) / "sequence_status.json"
        )
        r41_go, r41_terminal = _validate_stage_status("R41A", r41_status)
        status["completed_stage_receipts"].append(
            {
                "stage": "R41A",
                "status": r41_terminal,
                "gate_passed": r41_go,
                "gate_failure_count": r41_status["aggregate_receipt"][
                    "gate_failure_count"
                ],
            }
        )
        if not r41_go:
            status["status"] = r41_terminal
            status["current_stage"] = "complete"
            status["completed_at_utc"] = utc_now()
            status["updated_at_utc"] = status["completed_at_utc"]
            write_json(status_path, status)
            return status
        status["current_stage"] = "R42A"
        status["updated_at_utc"] = utc_now()
        write_json(status_path, status)
        r42_config = read_json(r42_config_path)
        r42_exit = _run_logged(
            [
                sys.executable,
                str(
                    WORKSPACE
                    / "scripts"
                    / "run_prta_gen_r42a_authorized_sequence.py"
                ),
                "--config",
                str(r42_config_path),
                "--roster-sha256",
                roster_sha256,
                "--devices",
                *devices,
            ],
            stdout_path=logs / "r42a.stdout.log",
            stderr_path=logs / "r42a.stderr.log",
        )
        if r42_exit not in (0, 2):
            raise RuntimeError(f"R42A sequence exited with code {r42_exit}")
        r42_status = read_json(
            Path(r42_config["runtime"]["root"]) / "sequence_status.json"
        )
        r42_go, r42_terminal = _validate_stage_status("R42A", r42_status)
        status["completed_stage_receipts"].append(
            {
                "stage": "R42A",
                "status": r42_terminal,
                "gate_passed": r42_go,
                "gate_failure_count": r42_status["aggregate_receipt"][
                    "gate_failure_count"
                ],
            }
        )
        if not r42_go:
            status["status"] = r42_terminal
            status["current_stage"] = "complete"
            status["completed_at_utc"] = utc_now()
            status["updated_at_utc"] = status["completed_at_utc"]
            write_json(status_path, status)
            return status
        status["current_stage"] = "R43"
        status["updated_at_utc"] = utc_now()
        write_json(status_path, status)
        r43_exit = _run_logged(
            [
                sys.executable,
                str(
                    WORKSPACE
                    / "scripts"
                    / "audit_prta_gen_r43_confirmatory_readiness.py"
                ),
                "--config",
                str(r43_config_path),
            ],
            stdout_path=logs / "r43.stdout.log",
            stderr_path=logs / "r43.stderr.log",
        )
        if r43_exit not in (0, 2):
            raise RuntimeError(f"R43 readiness exited with code {r43_exit}")
        r43_config = read_json(r43_config_path)
        r43_result = read_json(Path(r43_config["runtime"]["result"]))
        if (
            r43_result.get("status")
            not in {
                r43_config["result_statuses"]["ready"],
                r43_config["result_statuses"]["stop"],
            }
            or r43_result.get("outcomes_read") is not False
            or r43_result.get("metrics_read") is not False
            or r43_result.get("predictions_generated") is not False
            or r43_result.get("gold_outcomes_read") is not False
            or r43_result.get("external_outcomes_read") is not False
        ):
            raise PermissionError("R43 readiness terminal receipt drift")
        status["completed_stage_receipts"].append(
            {
                "stage": "R43",
                "status": r43_result["status"],
                "gate_passed": r43_result["gate_passed"],
                "gate_failure_count": len(r43_result["gate_failures"]),
                "available_untouched_gold_patients": r43_result[
                    "available_untouched_gold_patients"
                ],
                "predictions_generated": False,
            }
        )
        status["status"] = r43_result["status"]
        status["current_stage"] = "complete"
        status["completed_at_utc"] = utc_now()
        status["updated_at_utc"] = status["completed_at_utc"]
        write_json(status_path, status)
        return status
    except Exception as error:
        status["status"] = ENGINEERING_STOP
        status["failed_stage"] = status["current_stage"]
        status["error_type"] = type(error).__name__
        status["error"] = str(error)
        status["retry_allowed"] = False
        status["updated_at_utc"] = utc_now()
        write_json(status_path, status)
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the frozen automatic R41A -> R42A -> R43 chain"
    )
    parser.add_argument("--r41-config", type=Path, required=True)
    parser.add_argument("--r42-config", type=Path, required=True)
    parser.add_argument("--r43-config", type=Path, required=True)
    parser.add_argument("--roster", type=Path, required=True)
    parser.add_argument("--roster-sha256", required=True)
    parser.add_argument("--devices", nargs=2, default=("cuda:0", "cuda:1"))
    parser.add_argument("--preflight-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    devices = (str(args.devices[0]), str(args.devices[1]))
    kwargs = {
        "r41_config_path": args.r41_config,
        "r42_config_path": args.r42_config,
        "r43_config_path": args.r43_config,
        "roster_path": args.roster,
        "roster_sha256": args.roster_sha256,
        "devices": devices,
    }
    if args.preflight_only:
        print(json.dumps(chain_preflight(**kwargs), indent=2, sort_keys=True))
        return 0
    try:
        result = run_chain(**kwargs)
    except Exception as error:
        print(
            json.dumps(
                {
                    "status": ENGINEERING_STOP,
                    "error_type": type(error).__name__,
                    "error": str(error),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 1
    print(
        json.dumps(
            {
                "status": result["status"],
                "completed_stage_receipts": result[
                    "completed_stage_receipts"
                ],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 2 if result["status"] in TERMINAL_STATUSES else 0


if __name__ == "__main__":
    raise SystemExit(main())
