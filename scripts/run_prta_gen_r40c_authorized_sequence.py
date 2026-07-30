from __future__ import annotations

# ruff: noqa: E402

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE))
sys.path.insert(0, str(WORKSPACE / "src"))

from scripts.build_prta_gen_r40b_smoke_cohort import read_json, write_json


CONFIG_STATUS = "FROZEN_PRTA_GEN_R40C_STRUCTURED_GENERALIZATION"
ROSTER_STATUS = "PASS_PRTA_GEN_R40C_ROSTER_SUPPORT"
SEED_STATUS = "PASS_PRTA_GEN_R40C_SEED_EVALUATION"
PREFLIGHT_STATUS = "PASS_PRTA_GEN_R40C_SEQUENCE_PREFLIGHT"
ENGINEERING_STOP = "STOP_PRTA_GEN_R40C_SEQUENCE_ENGINEERING"
ARMS = ("true_pair", "current_only", "query_only", "prior_shuffle")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def validate_seed_result(
    config: dict[str, Any],
    *,
    seed: int,
    result: dict[str, Any],
) -> dict[str, Any]:
    if (
        result.get("status") != SEED_STATUS
        or result.get("protocol_id") != config["protocol_id"]
        or int(result.get("seed", -1)) != seed
        or result.get("training_rows") != config["roster"]["train_patients"]
        or result.get("training_patients")
        != config["roster"]["train_patients"]
        or result.get("development_rows")
        != config["roster"]["development_patients"]
        or result.get("development_patients")
        != config["roster"]["development_patients"]
        or result.get("parameter_count") != config["head"]["parameter_count"]
        or result.get("normalization_fit_on_training_only") is not True
        or result.get("exact64_tokens_used") is not True
        or result.get("pixel_inputs_used") is not False
        or result.get("qwen_free_generation_unlocked") is not False
        or result.get("r41_qwen_sft_unlocked") is not False
        or result.get("scientific_claim_allowed") is not False
        or result.get("protected_300_dev_read") is not False
        or result.get("revealed_483_test_read") is not False
        or result.get("gold_outcomes_read") is not False
        or result.get("external_outcomes_read") is not False
    ):
        raise PermissionError(f"R40C Seed {seed} receipt drift")
    structured = result.get("structured", {})
    if (
        structured.get("schema_validity")
        != config["gate"]["structured_schema_validity"]
        or structured.get("finding_echo_accuracy")
        != config["gate"]["structured_finding_echo_accuracy"]
    ):
        raise PermissionError(f"R40C Seed {seed} structured receipt drift")
    audits = result.get("training_audits", {})
    if set(audits) != set(ARMS) or any(
        audit.get("updates") != config["training"]["expected_updates_per_arm"]
        or audit.get("normalization_fit_on_training_only") is not True
        for audit in audits.values()
    ):
        raise PermissionError(f"R40C Seed {seed} training audit drift")
    checkpoint = Path(str(result.get("checkpoint", "")))
    if (
        not checkpoint.is_file()
        or checkpoint.stat().st_size != result.get("checkpoint_bytes")
    ):
        raise FileNotFoundError(f"R40C Seed {seed} checkpoint receipt drift")
    return {
        "seed": seed,
        "status": result["status"],
        "true_pair_macro_f1": result["metrics"]["true_pair"]["macro_f1"],
        "effects_pp": result["metrics"]["effects_pp"],
        "schema_validity": structured["schema_validity"],
        "finding_echo_accuracy": structured["finding_echo_accuracy"],
        "checkpoint_bytes": result["checkpoint_bytes"],
        "peak_cuda_allocated_bytes": result["peak_cuda_allocated_bytes"],
    }


def validate_aggregate(
    config: dict[str, Any], result: dict[str, Any]
) -> dict[str, Any]:
    expected_status = (
        config["result_statuses"]["aggregate_go"]
        if result.get("gate_passed") is True
        else config["result_statuses"]["aggregate_stop"]
    )
    if (
        result.get("status") != expected_status
        or result.get("protocol_id") != config["protocol_id"]
        or result.get("study_tier") != config["study_tier"]
        or result.get("seeds") != config["training"]["seeds"]
        or result.get("qwen_free_generation_unlocked") is not False
        or result.get("r41_qwen_sft_unlocked") is not False
        or result.get("scientific_claim_allowed") is not False
        or result.get("protected_300_dev_read") is not False
        or result.get("revealed_483_test_read") is not False
        or result.get("gold_outcomes_read") is not False
        or result.get("external_outcomes_read") is not False
    ):
        raise PermissionError("R40C aggregate receipt drift")
    return {
        "status": result["status"],
        "gate_passed": result["gate_passed"],
        "gate_failure_count": len(result.get("gate_failures", [])),
        "development_patients": result["development_patients"],
    }


def sequence_preflight(
    *,
    config_path: Path,
    roster_path: Path,
    roster_sha256: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    config = read_json(config_path)
    roster = read_json(roster_path)
    if config.get("status") != CONFIG_STATUS:
        raise PermissionError("R40C sequence config is not frozen")
    if config["training"]["seeds"] != [17, 29, 43]:
        raise PermissionError("R40C sequence Seed registry drift")
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
        raise PermissionError("R40C sequence roster receipt drift")
    observed_hash = sha256_file(roster_path)
    if observed_hash != roster_sha256.upper():
        raise PermissionError("R40C sequence roster hash drift")
    root = Path(config["runtime"]["root"])
    expected_roster = Path(config["runtime"]["roster"]).resolve()
    if roster_path.resolve() != expected_roster:
        raise PermissionError("R40C sequence roster path drift")
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
            "R40C sequence outputs must be fresh: " + ", ".join(occupied)
        )
    return config, {
        "status": PREFLIGHT_STATUS,
        "protocol_id": config["protocol_id"],
        "seeds": config["training"]["seeds"],
        "roster_sha256": observed_hash,
        "training_patients": roster["partitions"]["train"]["patient_count"],
        "development_patients": roster["partitions"]["development"][
            "patient_count"
        ],
        "protected_300_dev_read": False,
        "revealed_483_test_read": False,
        "gold_outcomes_read": False,
        "external_outcomes_read": False,
    }


def run_logged(command: list[str], *, stdout_path: Path, stderr_path: Path) -> int:
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    with (
        stdout_path.open("w", encoding="utf-8") as stdout_handle,
        stderr_path.open("w", encoding="utf-8") as stderr_handle,
    ):
        completed = subprocess.run(
            command,
            cwd=WORKSPACE,
            stdout=stdout_handle,
            stderr=stderr_handle,
            check=False,
        )
    return completed.returncode


def run_sequence(
    *,
    config_path: Path,
    roster_path: Path,
    roster_sha256: str,
    device: str,
) -> dict[str, Any]:
    config, preflight_receipt = sequence_preflight(
        config_path=config_path,
        roster_path=roster_path,
        roster_sha256=roster_sha256,
    )
    root = Path(config["runtime"]["root"])
    logs = root / "sequence_logs"
    status_path = root / "sequence_status.json"
    status: dict[str, Any] = {
        "schema": "visualvit.prta-gen.r40c-sequence-status.v1",
        "status": "RUNNING_PRTA_GEN_R40C_AUTHORIZED_SEQUENCE",
        "protocol_id": config["protocol_id"],
        "started_at_utc": utc_now(),
        "updated_at_utc": utc_now(),
        "roster_sha256": preflight_receipt["roster_sha256"],
        "device": device,
        "registered_seeds": config["training"]["seeds"],
        "completed_seed_receipts": [],
        "current_stage": "seed_17",
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
            status["current_stage"] = f"seed_{seed}"
            status["updated_at_utc"] = utc_now()
            write_json(status_path, status)
            command = [
                sys.executable,
                str(
                    WORKSPACE
                    / "scripts"
                    / "run_prta_gen_r40c_structured_generalization.py"
                ),
                "--config",
                str(config_path),
                "--roster",
                str(roster_path),
                "--seed",
                str(seed),
                "--device",
                device,
            ]
            exit_code = run_logged(
                command,
                stdout_path=logs / f"seed_{seed}.stdout.log",
                stderr_path=logs / f"seed_{seed}.stderr.log",
            )
            if exit_code != 0:
                raise RuntimeError(
                    f"R40C Seed {seed} exited with code {exit_code}"
                )
            result_path = root / f"seed_{seed}" / "result.json"
            receipt = validate_seed_result(
                config, seed=seed, result=read_json(result_path)
            )
            status["completed_seed_receipts"].append(receipt)
            status["updated_at_utc"] = utc_now()
            write_json(status_path, status)
        status["current_stage"] = "aggregate"
        status["updated_at_utc"] = utc_now()
        write_json(status_path, status)
        aggregate_command = [
            sys.executable,
            str(
                WORKSPACE
                / "scripts"
                / "aggregate_prta_gen_r40c_generalization.py"
            ),
            "--config",
            str(config_path),
            "--roster",
            str(roster_path),
        ]
        aggregate_exit = run_logged(
            aggregate_command,
            stdout_path=logs / "aggregate.stdout.log",
            stderr_path=logs / "aggregate.stderr.log",
        )
        if aggregate_exit not in (0, 2):
            raise RuntimeError(
                f"R40C aggregate exited with code {aggregate_exit}"
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
        description="Run the authorized fail-closed R40C Seed sequence"
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--roster", type=Path, required=True)
    parser.add_argument("--roster-sha256", required=True)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--preflight-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.preflight_only:
        _, receipt = sequence_preflight(
            config_path=args.config,
            roster_path=args.roster,
            roster_sha256=args.roster_sha256,
        )
        print(json.dumps(receipt, indent=2, sort_keys=True))
        return 0
    try:
        result = run_sequence(
            config_path=args.config,
            roster_path=args.roster,
            roster_sha256=args.roster_sha256,
            device=args.device,
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
                "completed_seed_count": len(
                    result["completed_seed_receipts"]
                ),
                "aggregate_receipt": result["aggregate_receipt"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
