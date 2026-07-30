from __future__ import annotations

# ruff: noqa: E402

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE))
sys.path.insert(0, str(WORKSPACE / "src"))

from scripts.build_prta_gen_r40b_smoke_cohort import read_json, write_json
from scripts.build_prta_gen_r41a_roster import CONFIG_STATUS, ROSTER_STATUS
from scripts.run_prta_gen_r41a_progression_sft import (
    ARM_STATUS,
    MODEL_ARMS,
)


PREFLIGHT_STATUS = "PASS_PRTA_GEN_R41A_SEQUENCE_PREFLIGHT"
ENGINEERING_STOP = "STOP_PRTA_GEN_R41A_SEQUENCE_ENGINEERING"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def validate_arm_result(
    config: dict[str, Any],
    *,
    seed: int,
    model_arm: str,
    result: dict[str, Any],
) -> dict[str, Any]:
    if (
        result.get("status") != ARM_STATUS
        or result.get("protocol_id") != config["protocol_id"]
        or int(result.get("seed", -1)) != seed
        or result.get("model_arm") != model_arm
        or result.get("training_rows") != config["roster"]["train_patients"]
        or result.get("development_rows")
        != config["roster"]["development_patients"]
        or result.get("optimizer_updates")
        != config["training"]["expected_optimizer_updates"]
        or result.get("exact64_tokens_used") is not True
        or result.get("free_greedy_generation_evaluated") is not True
        or result.get("pixel_inputs_used") is not False
        or result.get("qwen_free_generation_survival_unlocked") is not False
        or result.get("r42_unlocked") is not False
        or result.get("scientific_claim_allowed") is not False
        or result.get("protected_300_dev_read") is not False
        or result.get("revealed_483_test_read") is not False
        or result.get("gold_outcomes_read") is not False
        or result.get("external_outcomes_read") is not False
    ):
        raise PermissionError(f"R41A Seed {seed}/{model_arm} receipt drift")
    checkpoint = Path(str(result.get("checkpoint", "")))
    if (
        not checkpoint.is_file()
        or checkpoint.stat().st_size != result.get("checkpoint_bytes")
    ):
        raise FileNotFoundError("R41A arm checkpoint receipt drift")
    return {
        "seed": seed,
        "model_arm": model_arm,
        "status": result["status"],
        "true_pair_macro_f1": result["metrics"]["true_pair"]["macro_f1"],
        "true_pair_schema_validity": result["metrics"]["true_pair"][
            "schema_validity"
        ],
        "true_pair_finding_echo_accuracy": result["metrics"]["true_pair"][
            "finding_echo_accuracy"
        ],
        "optimizer_updates": result["optimizer_updates"],
        "checkpoint_bytes": result["checkpoint_bytes"],
        "peak_cuda_allocated_bytes": result["peak_cuda_allocated_bytes"],
    }


def validate_aggregate(
    config: dict[str, Any], result: dict[str, Any]
) -> dict[str, Any]:
    expected = (
        config["result_statuses"]["aggregate_go"]
        if result.get("gate_passed") is True
        else config["result_statuses"]["aggregate_stop"]
    )
    if (
        result.get("status") != expected
        or result.get("protocol_id") != config["protocol_id"]
        or result.get("study_tier") != config["study_tier"]
        or result.get("seeds") != config["training"]["seeds"]
        or result.get("qwen_free_generation_survival_unlocked")
        is not result.get("gate_passed")
        or result.get("r42_unlocked") is not result.get("gate_passed")
        or result.get("r43_unlocked") is not False
        or result.get("scientific_claim_allowed") is not False
        or result.get("protected_300_dev_read") is not False
        or result.get("revealed_483_test_read") is not False
        or result.get("gold_outcomes_read") is not False
        or result.get("external_outcomes_read") is not False
    ):
        raise PermissionError("R41A aggregate receipt drift")
    return {
        "status": result["status"],
        "gate_passed": result["gate_passed"],
        "gate_failure_count": len(result["gate_failures"]),
        "development_patients": result["development_patients"],
        "r42_unlocked": result["r42_unlocked"],
    }


def sequence_preflight(
    *,
    config_path: Path,
    roster_path: Path,
    roster_sha256: str,
    devices: tuple[str, str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    config = read_json(config_path)
    roster = read_json(roster_path)
    if config.get("status") != CONFIG_STATUS:
        raise PermissionError("R41A sequence config is not frozen")
    if config["training"]["seeds"] != [17, 29, 43]:
        raise PermissionError("R41A sequence Seed registry drift")
    if tuple(config["training"]["arms"]) != MODEL_ARMS:
        raise PermissionError("R41A sequence model-arm registry drift")
    if len(set(devices)) != 2 or any(
        not value.startswith("cuda:") for value in devices
    ):
        raise ValueError("R41A sequence requires two distinct CUDA devices")
    if (
        roster.get("status") != ROSTER_STATUS
        or roster.get("protocol_id") != config["protocol_id"]
        or roster.get("patient_sets_disjoint") is not True
        or roster.get("one_row_per_patient") is not True
        or roster.get("excluded_observed_patients_absent") is not True
        or roster.get("development_outcomes_read") is not False
        or roster.get("protected_300_dev_read") is not False
        or roster.get("revealed_483_test_read") is not False
        or roster.get("gold_outcomes_read") is not False
        or roster.get("external_outcomes_read") is not False
    ):
        raise PermissionError("R41A sequence roster receipt drift")
    observed_hash = sha256_file(roster_path)
    if observed_hash != roster_sha256.upper():
        raise PermissionError("R41A sequence roster hash drift")
    if roster_path.resolve() != Path(config["runtime"]["roster"]).resolve():
        raise PermissionError("R41A sequence roster path drift")
    root = Path(config["runtime"]["root"])
    occupied = [
        str(path)
        for path in (
            *(root / f"seed_{seed}" for seed in config["training"]["seeds"]),
            root / "aggregate.json",
            root / "sequence_status.json",
        )
        if path.exists()
    ]
    if occupied:
        raise FileExistsError(
            "R41A sequence outputs must be fresh: " + ", ".join(occupied)
        )
    return config, {
        "schema": "visualvit.prta-gen.r41a-sequence-preflight.v1",
        "status": PREFLIGHT_STATUS,
        "protocol_id": config["protocol_id"],
        "seeds": config["training"]["seeds"],
        "model_arms": list(MODEL_ARMS),
        "devices": list(devices),
        "roster_sha256": observed_hash,
        "training_patients": roster["partitions"]["train"]["patient_count"],
        "development_patients": roster["partitions"]["development"][
            "patient_count"
        ],
        "automatic_continuation_authorized": True,
        "retry_allowed": False,
        "protected_300_dev_read": False,
        "revealed_483_test_read": False,
        "gold_outcomes_read": False,
        "external_outcomes_read": False,
    }


def _launch_pair(
    commands: list[list[str]],
    *,
    stdout_paths: list[Path],
    stderr_paths: list[Path],
) -> list[int]:
    handles = []
    processes = []
    try:
        for command, stdout_path, stderr_path in zip(
            commands, stdout_paths, stderr_paths, strict=True
        ):
            stdout_path.parent.mkdir(parents=True, exist_ok=True)
            stdout_handle = stdout_path.open("w", encoding="utf-8")
            stderr_handle = stderr_path.open("w", encoding="utf-8")
            handles.extend((stdout_handle, stderr_handle))
            processes.append(
                subprocess.Popen(
                    command,
                    cwd=WORKSPACE,
                    stdout=stdout_handle,
                    stderr=stderr_handle,
                )
            )
        while True:
            codes = [process.poll() for process in processes]
            failure = next(
                (code for code in codes if code not in (None, 0)), None
            )
            if failure is not None:
                for process in processes:
                    if process.poll() is None:
                        process.terminate()
                return [process.wait() for process in processes]
            if all(code is not None for code in codes):
                return [int(code) for code in codes]
            time.sleep(1)
    finally:
        for handle in handles:
            handle.close()


def _run_logged(
    command: list[str], *, stdout_path: Path, stderr_path: Path
) -> int:
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    with (
        stdout_path.open("w", encoding="utf-8") as stdout_handle,
        stderr_path.open("w", encoding="utf-8") as stderr_handle,
    ):
        return subprocess.run(
            command,
            cwd=WORKSPACE,
            stdout=stdout_handle,
            stderr=stderr_handle,
            check=False,
        ).returncode


def run_sequence(
    *,
    config_path: Path,
    roster_path: Path,
    roster_sha256: str,
    devices: tuple[str, str],
) -> dict[str, Any]:
    config, preflight = sequence_preflight(
        config_path=config_path,
        roster_path=roster_path,
        roster_sha256=roster_sha256,
        devices=devices,
    )
    root = Path(config["runtime"]["root"])
    logs = root / "sequence_logs"
    status_path = root / "sequence_status.json"
    status: dict[str, Any] = {
        "schema": "visualvit.prta-gen.r41a-sequence-status.v1",
        "status": "RUNNING_PRTA_GEN_R41A_AUTHORIZED_SEQUENCE",
        "protocol_id": config["protocol_id"],
        "started_at_utc": utc_now(),
        "updated_at_utc": utc_now(),
        "roster_sha256": preflight["roster_sha256"],
        "devices": list(devices),
        "registered_seeds": config["training"]["seeds"],
        "registered_model_arms": list(MODEL_ARMS),
        "completed_arm_receipts": [],
        "current_stage": "seed_17_parallel_arms",
        "automatic_continuation_authorized": True,
        "retry_allowed": False,
        "protected_300_dev_read": False,
        "revealed_483_test_read": False,
        "gold_outcomes_read": False,
        "external_outcomes_read": False,
    }
    write_json(status_path, status)
    try:
        for seed in config["training"]["seeds"]:
            status["current_stage"] = f"seed_{seed}_parallel_arms"
            status["updated_at_utc"] = utc_now()
            write_json(status_path, status)
            commands = []
            stdout_paths = []
            stderr_paths = []
            for model_arm, device in zip(MODEL_ARMS, devices, strict=True):
                commands.append(
                    [
                        sys.executable,
                        str(
                            WORKSPACE
                            / "scripts"
                            / "run_prta_gen_r41a_progression_sft.py"
                        ),
                        "--config",
                        str(config_path),
                        "--roster",
                        str(roster_path),
                        "--seed",
                        str(seed),
                        "--model-arm",
                        model_arm,
                        "--device",
                        device,
                    ]
                )
                stdout_paths.append(
                    logs / f"seed_{seed}_{model_arm}.stdout.log"
                )
                stderr_paths.append(
                    logs / f"seed_{seed}_{model_arm}.stderr.log"
                )
            exit_codes = _launch_pair(
                commands,
                stdout_paths=stdout_paths,
                stderr_paths=stderr_paths,
            )
            if exit_codes != [0, 0]:
                raise RuntimeError(
                    f"R41A Seed {seed} arm exit codes: {exit_codes}"
                )
            for model_arm in MODEL_ARMS:
                result = read_json(
                    root
                    / f"seed_{seed}"
                    / model_arm
                    / "result.json"
                )
                status["completed_arm_receipts"].append(
                    validate_arm_result(
                        config,
                        seed=seed,
                        model_arm=model_arm,
                        result=result,
                    )
                )
            status["updated_at_utc"] = utc_now()
            write_json(status_path, status)
        status["current_stage"] = "aggregate"
        status["updated_at_utc"] = utc_now()
        write_json(status_path, status)
        aggregate_exit = _run_logged(
            [
                sys.executable,
                str(
                    WORKSPACE
                    / "scripts"
                    / "aggregate_prta_gen_r41a_progression_sft.py"
                ),
                "--config",
                str(config_path),
                "--roster",
                str(roster_path),
            ],
            stdout_path=logs / "aggregate.stdout.log",
            stderr_path=logs / "aggregate.stderr.log",
        )
        if aggregate_exit not in (0, 2):
            raise RuntimeError(
                f"R41A aggregate exited with code {aggregate_exit}"
            )
        aggregate_receipt = validate_aggregate(
            config, read_json(root / "aggregate.json")
        )
        status["status"] = aggregate_receipt["status"]
        status["current_stage"] = "complete"
        status["aggregate_receipt"] = aggregate_receipt
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
        description="Run the authorized fail-closed two-GPU R41A sequence"
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--roster", type=Path, required=True)
    parser.add_argument("--roster-sha256", required=True)
    parser.add_argument("--devices", nargs=2, default=("cuda:0", "cuda:1"))
    parser.add_argument("--preflight-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    devices = (str(args.devices[0]), str(args.devices[1]))
    if args.preflight_only:
        _, receipt = sequence_preflight(
            config_path=args.config,
            roster_path=args.roster,
            roster_sha256=args.roster_sha256,
            devices=devices,
        )
        print(json.dumps(receipt, indent=2, sort_keys=True))
        return 0
    try:
        result = run_sequence(
            config_path=args.config,
            roster_path=args.roster,
            roster_sha256=args.roster_sha256,
            devices=devices,
        )
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
                "completed_arm_count": len(
                    result["completed_arm_receipts"]
                ),
                "aggregate_receipt": result["aggregate_receipt"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if result["aggregate_receipt"]["gate_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
