from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Sequence


WORKSPACE = Path(__file__).resolve().parents[1]
RUNTIME = Path(r"H:\VisualVIT_runtime\050_routeD\r37_prta_cxr")
BLOCK8_ROOT = RUNTIME / "r37_block8_token_cache"
CMCP_INDEX = RUNTIME / "r37_counterfactual_prior_index.json"
A1_CACHE_ROOT = RUNTIME / "r37_biovilt_pair_cache"
SMOKE_ROOT = RUNTIME / "r37b_smokes"
STATUS_PATH = RUNTIME / "r37_post_cache_pipeline_status.json"
LOG_PATH = RUNTIME / "r37_post_cache_pipeline.log"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_status(status_path: Path, status: str, **extra: Any) -> None:
    payload = {
        "schema": "visualvit.r37.post-cache-pipeline.v1",
        "status": status,
        "updated_at": datetime.now().astimezone().isoformat(),
        "protected_outcomes_read": False,
        "source_hashes_recomputed": False,
        **extra,
    }
    temporary = status_path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
    )
    temporary.replace(status_path)


def append_log(log_path: Path, message: str) -> None:
    timestamp = datetime.now().astimezone().isoformat()
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"{timestamp} {message}\n")


def passed_json(path: Path, expected_status: str) -> bool:
    return path.is_file() and read_json(path).get("status") == expected_status


def gpu_memory_used_mib() -> list[int]:
    completed = subprocess.run(
        [
            "nvidia-smi",
            "--query-gpu=memory.used",
            "--format=csv,noheader,nounits",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return [
        int(line.strip())
        for line in completed.stdout.splitlines()
        if line.strip()
    ]


def wait_for_gpu_idle(
    *,
    devices: Sequence[int],
    required_polls: int,
    maximum_used_mib: int,
    poll_seconds: int,
    status_path: Path,
    log_path: Path,
    stage: str,
) -> None:
    idle_polls = 0
    while idle_polls < required_polls:
        usage = gpu_memory_used_mib()
        if max(devices) >= len(usage):
            raise RuntimeError(f"GPU ordinal missing; observed usage={usage}")
        selected = [usage[index] for index in devices]
        if all(value <= maximum_used_mib for value in selected):
            idle_polls += 1
        else:
            idle_polls = 0
        write_status(
            status_path,
            "WAITING_FOR_GPU_IDLE",
            stage=stage,
            devices=list(devices),
            observed_used_mib=selected,
            idle_polls=idle_polls,
            required_idle_polls=required_polls,
        )
        append_log(
            log_path,
            f"{stage} idle={idle_polls}/{required_polls} used_mib={selected}",
        )
        if idle_polls < required_polls:
            time.sleep(poll_seconds)


def run_command(
    command: list[str],
    *,
    workspace: Path,
    log_path: Path,
    stage: str,
) -> None:
    append_log(log_path, f"{stage} command={command}")
    with log_path.open("a", encoding="utf-8") as handle:
        completed = subprocess.run(
            command,
            cwd=workspace,
            stdout=handle,
            stderr=subprocess.STDOUT,
            text=True,
        )
    if completed.returncode != 0:
        raise RuntimeError(f"{stage} failed with exit code {completed.returncode}")


def run_parallel(
    commands: list[list[str]],
    *,
    workspace: Path,
    log_paths: list[Path],
    stage: str,
) -> None:
    handles = [
        path.open("a", encoding="utf-8") for path in log_paths
    ]
    creationflags = (
        subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    )
    try:
        processes = [
            subprocess.Popen(
                command,
                cwd=workspace,
                stdout=handle,
                stderr=subprocess.STDOUT,
                text=True,
                creationflags=creationflags,
            )
            for command, handle in zip(commands, handles)
        ]
        return_codes = [process.wait() for process in processes]
    finally:
        for handle in handles:
            handle.close()
    if any(code != 0 for code in return_codes):
        raise RuntimeError(f"{stage} part exit codes={return_codes}")


def wait_for_block8(
    *,
    manifest: Path,
    launcher_status: Path,
    poll_seconds: int,
    status_path: Path,
    log_path: Path,
) -> None:
    while not passed_json(manifest, "PASS_R37_BLOCK8_FORMAL_CACHE"):
        if launcher_status.is_file():
            launcher = read_json(launcher_status)
            launcher_state = str(launcher.get("status", "UNKNOWN"))
            if launcher_state.startswith("STOP_"):
                raise RuntimeError(
                    f"Block-8 launcher stopped: {launcher_state}"
                )
        else:
            launcher_state = "MISSING"
        write_status(
            status_path,
            "WAITING_FOR_BLOCK8_CACHE",
            stage="block8",
            launcher_status=launcher_state,
        )
        time.sleep(poll_seconds)
    append_log(log_path, "Block-8 merged manifest passed")


def result_passed(root: Path, filename: str, expected: str) -> bool:
    return passed_json(root / filename, expected)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Resume and execute the bounded R37 post-cache pipeline"
    )
    parser.add_argument("--workspace", type=Path, default=WORKSPACE)
    parser.add_argument("--runtime", type=Path, default=RUNTIME)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--poll-seconds", type=int, default=60)
    parser.add_argument("--required-idle-polls", type=int, default=3)
    parser.add_argument("--maximum-used-mib", type=int, default=2000)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.poll_seconds <= 0 or args.required_idle_polls <= 0:
        raise ValueError("poll interval and idle count must be positive")
    runtime = args.runtime
    runtime.mkdir(parents=True, exist_ok=True)
    status_path = runtime / STATUS_PATH.name
    log_path = runtime / LOG_PATH.name
    block8_root = runtime / BLOCK8_ROOT.name
    cmcp_index = runtime / CMCP_INDEX.name
    a1_cache_root = runtime / A1_CACHE_ROOT.name
    smoke_root = runtime / SMOKE_ROOT.name
    launcher_status = runtime / "r37_block8_idle_launcher_status.json"
    python = str(args.python)

    try:
        wait_for_block8(
            manifest=block8_root / "cache_manifest.json",
            launcher_status=launcher_status,
            poll_seconds=args.poll_seconds,
            status_path=status_path,
            log_path=log_path,
        )

        if not passed_json(cmcp_index, "PASS_R37A_CMCP_COVERAGE"):
            if cmcp_index.exists():
                raise RuntimeError("existing CMCP artifact did not pass")
            write_status(status_path, "RUNNING_CMCP", stage="cmcp")
            run_command(
                [
                    python,
                    "scripts/build_r37_cmcp_index.py",
                    "--cache-root",
                    str(block8_root),
                    "--output",
                    str(cmcp_index),
                ],
                workspace=args.workspace,
                log_path=log_path,
                stage="cmcp",
            )
            if not passed_json(cmcp_index, "PASS_R37A_CMCP_COVERAGE"):
                raise RuntimeError("CMCP coverage gate did not pass")

        stages = (
            (
                "a0",
                smoke_root / "a0_seed17_postcache_engineering_v1",
                "r37_a0_smoke_result.json",
                "PASS_R37_A0_ENGINEERING_PIPELINE",
                [
                    python,
                    "scripts/run_r37_a0_frozen_probe.py",
                    "--device",
                    "cuda:0",
                    "--cache-root",
                    str(block8_root),
                    "--output-root",
                    str(smoke_root / "a0_seed17_postcache_engineering_v1"),
                ],
            ),
            (
                "a3",
                smoke_root / "a3_seed17_postcache_engineering_v1",
                "result.json",
                "PASS_R37_PRTA_ENGINEERING_SMOKE",
                [
                    python,
                    "scripts/run_r37_prta_smoke.py",
                    "--variant",
                    "A3",
                    "--device",
                    "cuda:0",
                    "--cache-root",
                    str(block8_root),
                    "--output-root",
                    str(smoke_root / "a3_seed17_postcache_engineering_v1"),
                ],
            ),
            (
                "a6",
                smoke_root / "a6_seed17_postcache_engineering_v1",
                "result.json",
                "PASS_R37_PRTA_ENGINEERING_SMOKE",
                [
                    python,
                    "scripts/run_r37_prta_smoke.py",
                    "--variant",
                    "A6",
                    "--device",
                    "cuda:0",
                    "--cache-root",
                    str(block8_root),
                    "--cmcp-index",
                    str(cmcp_index),
                    "--output-root",
                    str(smoke_root / "a6_seed17_postcache_engineering_v1"),
                ],
            ),
        )
        for stage, root, filename, expected, command in stages:
            if result_passed(root, filename, expected):
                append_log(log_path, f"{stage} already passed; skipping")
                continue
            if root.exists():
                raise RuntimeError(f"existing {stage} output did not pass: {root}")
            wait_for_gpu_idle(
                devices=(0, 1),
                required_polls=args.required_idle_polls,
                maximum_used_mib=args.maximum_used_mib,
                poll_seconds=args.poll_seconds,
                status_path=status_path,
                log_path=log_path,
                stage=stage,
            )
            write_status(status_path, "RUNNING_ENGINEERING_STAGE", stage=stage)
            run_command(
                command,
                workspace=args.workspace,
                log_path=log_path,
                stage=stage,
            )
            if not result_passed(root, filename, expected):
                raise RuntimeError(f"{stage} did not write its PASS result")

        a1_merged = a1_cache_root / "r37_biovilt_pair_cache_manifest.json"
        if not passed_json(
            a1_merged, "PASS_R37_A1_CONTROL_CACHE_MERGED"
        ):
            if a1_merged.exists():
                raise RuntimeError("existing A1 merged manifest did not pass")
            missing_commands = []
            missing_logs = []
            for index in range(2):
                part_root = (
                    a1_cache_root / f"part_{index:02d}_of_02"
                )
                part_manifest = (
                    part_root / "r37_biovilt_pair_cache_manifest.json"
                )
                if passed_json(part_manifest, "PASS_R37_A1_CONTROL_CACHE"):
                    continue
                if part_root.exists():
                    raise RuntimeError(
                        f"existing A1 part did not pass: {part_root}"
                    )
                missing_commands.append(
                    [
                        python,
                        "scripts/cache_r37_biovilt_pair_embeddings.py",
                        "--full",
                        "--part-index",
                        str(index),
                        "--part-count",
                        "2",
                        "--device",
                        f"cuda:{index}",
                        "--batch-size",
                        "16",
                        "--workers",
                        "4",
                        "--shard-size",
                        "1024",
                    ]
                )
                missing_logs.append(
                    runtime / f"r37_a1_cache_part{index}.log"
                )
            if missing_commands:
                wait_for_gpu_idle(
                    devices=(0, 1),
                    required_polls=args.required_idle_polls,
                    maximum_used_mib=args.maximum_used_mib,
                    poll_seconds=args.poll_seconds,
                    status_path=status_path,
                    log_path=log_path,
                    stage="a1_control_cache",
                )
                write_status(
                    status_path,
                    "RUNNING_A1_CONTROL_CACHE",
                    stage="a1_control_cache",
                    parts=len(missing_commands),
                )
                run_parallel(
                    missing_commands,
                    workspace=args.workspace,
                    log_paths=missing_logs,
                    stage="a1_control_cache",
                )
            run_command(
                [
                    python,
                    "scripts/merge_r37_biovilt_pair_cache_parts.py",
                    "--root",
                    str(a1_cache_root),
                    "--part-count",
                    "2",
                ],
                workspace=args.workspace,
                log_path=log_path,
                stage="a1_cache_merge",
            )
            if not passed_json(
                a1_merged, "PASS_R37_A1_CONTROL_CACHE_MERGED"
            ):
                raise RuntimeError("A1 merged cache did not pass")

        a1_result_root = smoke_root / "a1_seed17_cached_engineering_v1"
        if not result_passed(
            a1_result_root,
            "r37_a1_smoke_result.json",
            "PASS_R37_A1_ENGINEERING_PIPELINE",
        ):
            if a1_result_root.exists():
                raise RuntimeError("existing cached A1 result did not pass")
            write_status(status_path, "RUNNING_CACHED_A1_PROBE", stage="a1")
            run_command(
                [
                    python,
                    "scripts/run_r37_biovilt_smoke.py",
                    "--device",
                    "cpu",
                    "--feature-cache",
                    str(a1_cache_root),
                    "--max-train-examples",
                    "100",
                    "--max-calibration-examples",
                    "50",
                    "--output-root",
                    str(a1_result_root),
                ],
                workspace=args.workspace,
                log_path=log_path,
                stage="a1_cached_probe",
            )

        write_status(
            status_path,
            "PASS_R37_POST_CACHE_ENGINEERING_PIPELINE",
            stage="complete",
            block8_manifest=str(block8_root / "cache_manifest.json"),
            cmcp_index=str(cmcp_index),
            a1_cache_manifest=str(a1_merged),
        )
        append_log(log_path, "post-cache engineering pipeline passed")
        return 0
    except Exception as error:
        append_log(log_path, f"STOP error={error!r}")
        write_status(
            status_path,
            "STOP_R37_POST_CACHE_ENGINEERING_PIPELINE",
            stage="error",
            error=repr(error),
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
