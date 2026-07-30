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
from scripts.cache_prta_gen_r42a_reverse_tokens import REVERSE_CACHE_STATUS
from scripts.run_prta_gen_r41a_authorized_sequence import (
    _launch_pair,
    _run_logged,
    sha256_file,
    utc_now,
)
from scripts.run_prta_gen_r42a_grounding_reversal import (
    ARM_STATUS,
    CONFIG_STATUS,
    TRAINING_ARMS,
)


PREFLIGHT_STATUS = "PASS_PRTA_GEN_R42A_SEQUENCE_PREFLIGHT"
ENGINEERING_STOP = "STOP_PRTA_GEN_R42A_SEQUENCE_ENGINEERING"


def validate_arm_result(
    config: dict[str, Any],
    *,
    seed: int,
    training_arm: str,
    result: dict[str, Any],
) -> dict[str, Any]:
    if (
        result.get("status") != ARM_STATUS
        or result.get("protocol_id") != config["protocol_id"]
        or int(result.get("seed", -1)) != seed
        or result.get("training_arm") != training_arm
        or result.get("training_rows") != 375
        or result.get("development_rows") != 125
        or result.get("optimizer_updates")
        != config["training"]["expected_optimizer_updates"]
        or result.get("reverse_tokens_recomputed_by_input_swap") is not True
        or result.get("heuristic_token_permutation_used") is not False
        or result.get("pixel_inputs_used") is not False
        or result.get("r43_unlocked") is not False
        or result.get("scientific_claim_allowed") is not False
        or result.get("protected_300_dev_read") is not False
        or result.get("revealed_483_test_read") is not False
        or result.get("gold_outcomes_read") is not False
        or result.get("external_outcomes_read") is not False
    ):
        raise PermissionError(
            f"R42A Seed {seed}/{training_arm} receipt drift"
        )
    checkpoint = Path(str(result.get("checkpoint", "")))
    if (
        not checkpoint.is_file()
        or checkpoint.stat().st_size != result.get("checkpoint_bytes")
    ):
        raise FileNotFoundError("R42A checkpoint receipt drift")
    return {
        "seed": seed,
        "training_arm": training_arm,
        "status": result["status"],
        "true_pair_macro_f1": result["metrics"]["true_pair"]["macro_f1"],
        "reversal_mapped_accuracy": result["metrics"]["time_reversed"][
            "progression_accuracy"
        ],
        "correct_prior_preference": result["correct_prior_preference"][
            "correct_prior_preference"
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
        or result.get("r43_readiness_unlocked") is not result.get("gate_passed")
        or result.get("scientific_claim_allowed") is not False
        or result.get("protected_300_dev_read") is not False
        or result.get("revealed_483_test_read") is not False
        or result.get("gold_outcomes_read") is not False
        or result.get("external_outcomes_read") is not False
    ):
        raise PermissionError("R42A aggregate receipt drift")
    return {
        "status": result["status"],
        "gate_passed": result["gate_passed"],
        "gate_failure_count": len(result["gate_failures"]),
        "development_patients": result["development_patients"],
        "r43_readiness_unlocked": result["r43_readiness_unlocked"],
    }


def sequence_preflight(
    *,
    config_path: Path,
    roster_sha256: str,
    devices: tuple[str, str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    config = read_json(config_path)
    if config.get("status") != CONFIG_STATUS:
        raise PermissionError("R42A sequence config is not frozen")
    predecessor = read_json(Path(config["closed_predecessor"]["aggregate"]))
    if (
        predecessor.get("status")
        != config["closed_predecessor"]["required_status"]
        or predecessor.get("gate_passed") is not True
        or predecessor.get("r42_unlocked") is not True
    ):
        raise PermissionError("R42A sequence predecessor drift")
    roster_path = Path(config["source"]["roster"])
    roster = read_json(roster_path)
    if (
        sha256_file(roster_path) != roster_sha256.upper()
        or roster.get("status") != config["source"]["required_roster_status"]
        or roster.get("patient_sets_disjoint") is not True
        or roster.get("protected_300_dev_read") is not False
        or roster.get("gold_outcomes_read") is not False
    ):
        raise PermissionError("R42A sequence roster/hash drift")
    if tuple(config["training"]["arms"]) != TRAINING_ARMS:
        raise PermissionError("R42A sequence arm registry drift")
    if len(set(devices)) != 2 or any(
        not value.startswith("cuda:") for value in devices
    ):
        raise ValueError("R42A sequence requires two distinct CUDA devices")
    root = Path(config["runtime"]["root"])
    occupied = [
        str(path)
        for path in (
            Path(config["runtime"]["reverse_tokens"]),
            *(root / f"seed_{seed}" for seed in config["training"]["seeds"]),
            root / "aggregate.json",
            root / "sequence_status.json",
        )
        if path.exists()
    ]
    if occupied:
        raise FileExistsError(
            "R42A sequence outputs must be fresh: " + ", ".join(occupied)
        )
    return config, {
        "schema": "visualvit.prta-gen.r42a-sequence-preflight.v1",
        "status": PREFLIGHT_STATUS,
        "protocol_id": config["protocol_id"],
        "seeds": config["training"]["seeds"],
        "training_arms": list(TRAINING_ARMS),
        "devices": list(devices),
        "roster_sha256": roster_sha256.upper(),
        "reverse_cache_rows": config["reverse_cache"]["expected_rows"],
        "automatic_continuation_authorized": True,
        "retry_allowed": False,
        "protected_300_dev_read": False,
        "revealed_483_test_read": False,
        "gold_outcomes_read": False,
        "external_outcomes_read": False,
    }


def run_sequence(
    *,
    config_path: Path,
    roster_sha256: str,
    devices: tuple[str, str],
) -> dict[str, Any]:
    config, preflight = sequence_preflight(
        config_path=config_path,
        roster_sha256=roster_sha256,
        devices=devices,
    )
    root = Path(config["runtime"]["root"])
    logs = root / "sequence_logs"
    status_path = root / "sequence_status.json"
    status: dict[str, Any] = {
        "schema": "visualvit.prta-gen.r42a-sequence-status.v1",
        "status": "RUNNING_PRTA_GEN_R42A_AUTHORIZED_SEQUENCE",
        "protocol_id": config["protocol_id"],
        "started_at_utc": utc_now(),
        "updated_at_utc": utc_now(),
        "roster_sha256": preflight["roster_sha256"],
        "devices": list(devices),
        "completed_arm_receipts": [],
        "current_stage": "reverse_token_cache",
        "automatic_continuation_authorized": True,
        "retry_allowed": False,
        "protected_300_dev_read": False,
        "revealed_483_test_read": False,
        "gold_outcomes_read": False,
        "external_outcomes_read": False,
    }
    write_json(status_path, status)
    try:
        cache_exit = _run_logged(
            [
                sys.executable,
                str(
                    WORKSPACE
                    / "scripts"
                    / "cache_prta_gen_r42a_reverse_tokens.py"
                ),
                "--config",
                str(config_path),
                "--device",
                devices[0],
            ],
            stdout_path=logs / "reverse_cache.stdout.log",
            stderr_path=logs / "reverse_cache.stderr.log",
        )
        if cache_exit != 0:
            raise RuntimeError(
                f"R42A reverse cache exited with code {cache_exit}"
            )
        reverse_index = read_json(Path(config["source"]["reverse_token_index"]))
        if (
            reverse_index.get("status") != REVERSE_CACHE_STATUS
            or reverse_index.get("rows")
            != config["reverse_cache"]["expected_rows"]
            or reverse_index.get("heuristic_token_permutation_used") is not False
        ):
            raise PermissionError("R42A reverse-cache receipt drift")
        status["reverse_cache_receipt"] = {
            "status": reverse_index["status"],
            "rows": reverse_index["rows"],
            "patients": reverse_index["patients"],
            "shard_count": reverse_index["shard_count"],
            "heuristic_token_permutation_used": False,
        }
        for seed in config["training"]["seeds"]:
            status["current_stage"] = f"seed_{seed}_parallel_arms"
            status["updated_at_utc"] = utc_now()
            write_json(status_path, status)
            commands = []
            stdout_paths = []
            stderr_paths = []
            for training_arm, device in zip(
                TRAINING_ARMS, devices, strict=True
            ):
                commands.append(
                    [
                        sys.executable,
                        str(
                            WORKSPACE
                            / "scripts"
                            / "run_prta_gen_r42a_grounding_reversal.py"
                        ),
                        "--config",
                        str(config_path),
                        "--seed",
                        str(seed),
                        "--training-arm",
                        training_arm,
                        "--device",
                        device,
                    ]
                )
                stdout_paths.append(
                    logs / f"seed_{seed}_{training_arm}.stdout.log"
                )
                stderr_paths.append(
                    logs / f"seed_{seed}_{training_arm}.stderr.log"
                )
            exit_codes = _launch_pair(
                commands,
                stdout_paths=stdout_paths,
                stderr_paths=stderr_paths,
            )
            if exit_codes != [0, 0]:
                raise RuntimeError(
                    f"R42A Seed {seed} arm exit codes: {exit_codes}"
                )
            for training_arm in TRAINING_ARMS:
                result = read_json(
                    root
                    / f"seed_{seed}"
                    / training_arm
                    / "result.json"
                )
                status["completed_arm_receipts"].append(
                    validate_arm_result(
                        config,
                        seed=seed,
                        training_arm=training_arm,
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
                    / "aggregate_prta_gen_r42a_grounding_reversal.py"
                ),
                "--config",
                str(config_path),
            ],
            stdout_path=logs / "aggregate.stdout.log",
            stderr_path=logs / "aggregate.stderr.log",
        )
        if aggregate_exit not in (0, 2):
            raise RuntimeError(
                f"R42A aggregate exited with code {aggregate_exit}"
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
        description="Run the authorized fail-closed two-GPU R42A sequence"
    )
    parser.add_argument("--config", type=Path, required=True)
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
            roster_sha256=args.roster_sha256,
            devices=devices,
        )
        print(json.dumps(receipt, indent=2, sort_keys=True))
        return 0
    try:
        result = run_sequence(
            config_path=args.config,
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
