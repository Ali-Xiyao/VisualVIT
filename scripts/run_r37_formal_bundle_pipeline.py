from __future__ import annotations

# ruff: noqa: E402

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from typing import Any, Sequence

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE))

from scripts.preflight_r37_formal_bundle import (
    inspect_bundle,
    seed_output_state,
)


DEFAULT_SPEC = WORKSPACE / "configs" / "r37" / "prta_a6_formal_bundle_v1.json"
DEFAULT_RUNTIME = Path(r"H:\VisualVIT_runtime\050_routeD\r37_prta_cxr")


@dataclass(frozen=True)
class FormalTask:
    key: str
    variant: str
    seed: int
    device: int
    bundle_root: Path
    command: tuple[str, ...]
    result_schema: str
    result_status: str

    @property
    def output_root(self) -> Path:
        return self.bundle_root / f"seed_{self.seed}"


def now_iso() -> str:
    return datetime.now().astimezone().isoformat()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    temporary.replace(path)


def append_log(path: Path, message: str) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"{now_iso()} {message}\n")


def process_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if sys.platform == "win32":
        completed = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
            check=False,
            capture_output=True,
            text=True,
        )
        for row in csv.reader(completed.stdout.splitlines()):
            if len(row) >= 2 and row[1].isdigit() and int(row[1]) == pid:
                return True
        return False
    try:
        os.kill(pid, 0)
    except (OSError, ProcessLookupError):
        return False
    return True


def acquire_single_instance(lock_path: Path) -> int:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    while True:
        try:
            descriptor = os.open(
                lock_path,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
            )
        except FileExistsError:
            try:
                existing = read_json(lock_path)
                existing_pid = int(existing.get("pid", -1))
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                existing_pid = -1
            if process_alive(existing_pid):
                raise RuntimeError(
                    f"formal pipeline already active as PID {existing_pid}"
                )
            lock_path.unlink()
            continue
        payload = json.dumps({"pid": os.getpid(), "created_at": now_iso()})
        os.write(descriptor, payload.encode("utf-8"))
        return descriptor


def release_single_instance(lock_path: Path, descriptor: int) -> None:
    os.close(descriptor)
    if lock_path.is_file():
        lock_path.unlink()


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


def task_output_state(task: FormalTask) -> str:
    state = seed_output_state(
        task.bundle_root,
        task.seed,
        schema=task.result_schema,
        status=task.result_status,
        variant=task.variant,
    )
    return str(state["state"])


def build_tasks(
    spec: dict[str, Any],
    *,
    python: str,
) -> dict[int, list[FormalTask]]:
    artifacts = spec["artifacts"]
    training = spec["training"]
    baseline = spec["baseline_a0"]
    a6_root = Path(artifacts["formal_output_root"])
    a0_root = Path(baseline["formal_output_root"])

    def a6(seed: int, device: int) -> FormalTask:
        output_root = a6_root / f"seed_{seed}"
        command = (
            python,
            "scripts/run_r37_prta_smoke.py",
            "--formal",
            "--variant",
            "A6",
            "--seed",
            str(seed),
            "--device",
            f"cuda:{device}",
            "--max-train-examples",
            "0",
            "--max-calibration-examples",
            "0",
            "--epochs",
            str(training["epochs"]),
            "--batch-size",
            str(training["batch_size"]),
            "--learning-rate",
            str(training["learning_rate"]),
            "--adapter-rank",
            str(training["adapter_rank"]),
            "--transition-root",
            artifacts["transition_root"],
            "--cache-root",
            artifacts["block8_cache_root"],
            "--text-cache",
            artifacts["text_cache"],
            "--cmcp-index",
            artifacts["cmcp_index"],
            "--output-root",
            str(output_root),
        )
        return FormalTask(
            key=f"a6_seed_{seed}",
            variant="A6",
            seed=seed,
            device=device,
            bundle_root=a6_root,
            command=command,
            result_schema="visualvit.r37.prta-formal-training.v1",
            result_status="PASS_R37_PRTA_FORMAL_TRAINING",
        )

    def a0(seed: int, device: int) -> FormalTask:
        output_root = a0_root / f"seed_{seed}"
        command = (
            python,
            "scripts/run_r37_a0_frozen_probe.py",
            "--formal",
            "--seed",
            str(seed),
            "--device",
            f"cuda:{device}",
            "--max-train-examples",
            "0",
            "--max-calibration-examples",
            "0",
            "--epochs",
            str(baseline["epochs"]),
            "--batch-size",
            str(baseline["batch_size"]),
            "--learning-rate",
            str(baseline["learning_rate"]),
            "--transition-root",
            artifacts["transition_root"],
            "--cache-root",
            artifacts["block8_cache_root"],
            "--text-cache",
            artifacts["text_cache"],
            "--output-root",
            str(output_root),
        )
        return FormalTask(
            key=f"a0_seed_{seed}",
            variant="A0",
            seed=seed,
            device=device,
            bundle_root=a0_root,
            command=command,
            result_schema="visualvit.r37.a0-formal-probe.v1",
            result_status="PASS_R37_A0_FORMAL_PROBE",
        )

    return {
        0: [a6(17, 0), a6(43, 0), a0(17, 0), a0(43, 0)],
        1: [a6(29, 1), a0(29, 1)],
    }


class PipelineStatus:
    def __init__(self, path: Path, tasks: Sequence[FormalTask]) -> None:
        self.path = path
        self.lock = threading.Lock()
        self.payload: dict[str, Any] = {
            "schema": "visualvit.r37.formal-bundle-pipeline.v1",
            "status": "RUNNING_R37_FORMAL_BUNDLE",
            "launcher_pid": os.getpid(),
            "started_at": now_iso(),
            "updated_at": now_iso(),
            "tasks": {
                task.key: {
                    "variant": task.variant,
                    "seed": task.seed,
                    "device": task.device,
                    "state": "queued",
                    "pid": None,
                    "output_root": str(task.output_root),
                }
                for task in tasks
            },
            "protected_outcomes_read": False,
            "sealed_test_read": False,
            "gold_outcomes_read": False,
            "source_hashes_recomputed": False,
            "per_shard_hashes_computed": False,
            "scientific_claim_allowed": False,
        }
        write_json_atomic(self.path, self.payload)

    def update(self, status: str | None = None, **extra: Any) -> None:
        with self.lock:
            if status:
                self.payload["status"] = status
            self.payload.update(extra)
            self.payload["updated_at"] = now_iso()
            write_json_atomic(self.path, self.payload)

    def update_task(self, key: str, **values: Any) -> None:
        with self.lock:
            self.payload["tasks"][key].update(values)
            self.payload["updated_at"] = now_iso()
            write_json_atomic(self.path, self.payload)


def wait_for_device_idle(
    task: FormalTask,
    *,
    status: PipelineStatus,
    required_polls: int,
    maximum_used_mib: int,
    poll_seconds: int,
    log_path: Path,
) -> None:
    idle_polls = 0
    while idle_polls < required_polls:
        usage = gpu_memory_used_mib()
        if task.device >= len(usage):
            raise RuntimeError(f"GPU {task.device} missing; usage={usage}")
        used = usage[task.device]
        idle_polls = idle_polls + 1 if used <= maximum_used_mib else 0
        status.update_task(
            task.key,
            state="waiting_for_gpu_idle",
            observed_used_mib=used,
            idle_polls=idle_polls,
            required_idle_polls=required_polls,
        )
        status.update(active_task=task.key)
        append_log(
            log_path,
            f"{task.key} idle={idle_polls}/{required_polls} used_mib={used}",
        )
        if idle_polls < required_polls:
            time.sleep(poll_seconds)


def run_task(
    task: FormalTask,
    *,
    workspace: Path,
    status: PipelineStatus,
    runtime: Path,
    required_idle_polls: int,
    maximum_used_mib: int,
    poll_seconds: int,
    pipeline_log: Path,
) -> None:
    state = task_output_state(task)
    if state == "complete":
        status.update_task(task.key, state="complete_reused")
        append_log(pipeline_log, f"{task.key} already complete; reused")
        return
    if state != "fresh":
        raise RuntimeError(f"{task.key} output state is {state}, not resumable")

    wait_for_device_idle(
        task,
        status=status,
        required_polls=required_idle_polls,
        maximum_used_mib=maximum_used_mib,
        poll_seconds=poll_seconds,
        log_path=pipeline_log,
    )
    if task_output_state(task) != "fresh":
        raise RuntimeError(f"{task.key} changed before launch")

    task_log = runtime / f"r37_formal_{task.key}.log"
    creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    with task_log.open("a", encoding="utf-8") as handle:
        process = subprocess.Popen(
            list(task.command),
            cwd=workspace,
            stdout=handle,
            stderr=subprocess.STDOUT,
            text=True,
            creationflags=creationflags,
        )
        status.update_task(
            task.key,
            state="running",
            pid=process.pid,
            started_at=now_iso(),
            log_path=str(task_log),
        )
        status.update(
            "RUNNING_R37_FORMAL_BUNDLE",
            active_task=task.key,
        )
        append_log(
            pipeline_log,
            f"{task.key} started pid={process.pid} device={task.device}",
        )
        return_code = process.wait()

    if return_code != 0:
        raise RuntimeError(f"{task.key} exited with code {return_code}")
    final_state = task_output_state(task)
    if final_state != "complete":
        raise RuntimeError(f"{task.key} ended with output state {final_state}")
    status.update_task(
        task.key,
        state="complete",
        pid=None,
        completed_at=now_iso(),
    )
    append_log(pipeline_log, f"{task.key} completed")


def run_lane(
    tasks: Sequence[FormalTask],
    **kwargs: Any,
) -> None:
    for task in tasks:
        run_task(task, **kwargs)


def run_aggregation(
    *,
    control: str,
    a6_root: Path,
    a0_root: Path,
    output: Path,
    python: str,
    workspace: Path,
    log_path: Path,
) -> dict[str, Any]:
    if output.is_file():
        payload = read_json(output)
        if not str(payload.get("status", "")).startswith(("PASS_", "STOP_")):
            raise RuntimeError(f"invalid existing aggregation: {output}")
        return payload
    command = [
        python,
        "scripts/aggregate_r37_internal_qualification.py",
    ]
    for seed in (17, 29, 43):
        command.extend(["--result", str(a6_root / f"seed_{seed}" / "result.json")])
    command.extend(["--control", control])
    if control == "a0":
        for seed in (17, 29, 43):
            command.extend(
                [
                    "--baseline-result",
                    str(a0_root / f"seed_{seed}" / "result.json"),
                ]
            )
    command.extend(["--output", str(output)])
    with log_path.open("a", encoding="utf-8") as handle:
        completed = subprocess.run(
            command,
            cwd=workspace,
            stdout=handle,
            stderr=subprocess.STDOUT,
            text=True,
        )
    if completed.returncode not in {0, 2} or not output.is_file():
        raise RuntimeError(
            f"{control} aggregation failed with code {completed.returncode}"
        )
    payload = read_json(output)
    if not str(payload.get("status", "")).startswith(("PASS_", "STOP_")):
        raise RuntimeError(f"{control} aggregation wrote invalid status")
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the frozen two-GPU R37 A6/A0 formal bundle"
    )
    parser.add_argument("--workspace", type=Path, default=WORKSPACE)
    parser.add_argument("--spec", type=Path, default=DEFAULT_SPEC)
    parser.add_argument("--runtime", type=Path, default=DEFAULT_RUNTIME)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--poll-seconds", type=int, default=30)
    parser.add_argument("--required-idle-polls", type=int, default=3)
    parser.add_argument("--maximum-used-mib", type=int, default=2000)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.poll_seconds <= 0 or args.required_idle_polls <= 0:
        raise ValueError("poll interval and idle count must be positive")
    args.runtime.mkdir(parents=True, exist_ok=True)
    status_path = args.runtime / "r37_formal_bundle_pipeline_status.json"
    pipeline_log = args.runtime / "r37_formal_bundle_pipeline.log"
    lock_path = args.runtime / "r37_formal_bundle_pipeline.lock"
    descriptor = acquire_single_instance(lock_path)
    status: PipelineStatus | None = None
    try:
        spec = read_json(args.spec)
        preflight = inspect_bundle(spec)
        if (
            preflight.get("status") != "READY_R37_FORMAL_BUNDLE"
            or preflight.get("formal_execution_allowed") is not True
        ):
            raise PermissionError(
                f"formal preflight not ready: {preflight.get('status')}"
            )
        tasks_by_device = build_tasks(spec, python=str(args.python))
        tasks = [
            task
            for device in sorted(tasks_by_device)
            for task in tasks_by_device[device]
        ]
        status = PipelineStatus(status_path, tasks)
        append_log(pipeline_log, f"launcher pid={os.getpid()} preflight ready")

        errors: list[str] = []
        threads = []

        def lane_target(device: int) -> None:
            try:
                run_lane(
                    tasks_by_device[device],
                    workspace=args.workspace,
                    status=status,
                    runtime=args.runtime,
                    required_idle_polls=args.required_idle_polls,
                    maximum_used_mib=args.maximum_used_mib,
                    poll_seconds=args.poll_seconds,
                    pipeline_log=pipeline_log,
                )
            except Exception as error:
                errors.append(f"device {device}: {error!r}")
                append_log(pipeline_log, errors[-1])

        for device in sorted(tasks_by_device):
            thread = threading.Thread(
                target=lane_target,
                args=(device,),
                name=f"r37-formal-cuda-{device}",
            )
            thread.start()
            threads.append(thread)
        for thread in threads:
            thread.join()

        if errors:
            status.update(
                "STOP_R37_FORMAL_BUNDLE_PIPELINE",
                errors=errors,
                scientific_claim_allowed=False,
            )
            return 2

        final_preflight = inspect_bundle(spec)
        all_complete = all(
            item["state"] == "complete"
            for item in [
                *final_preflight["seed_output_states"],
                *final_preflight["a0_seed_output_states"],
            ]
        )
        if not all_complete:
            raise RuntimeError("formal jobs ended without six complete outputs")

        status.update("RUNNING_R37_INTERNAL_AGGREGATION")
        qualification_root = (
            Path(spec["artifacts"]["formal_output_root"]).parent
            / "qualification_v1"
        )
        a6_root = Path(spec["artifacts"]["formal_output_root"])
        a0_root = Path(spec["baseline_a0"]["formal_output_root"])
        qualification_log = args.runtime / "r37_formal_qualification.log"
        aggregation = {
            control: run_aggregation(
                control=control,
                a6_root=a6_root,
                a0_root=a0_root,
                output=qualification_root / f"{control}.json",
                python=str(args.python),
                workspace=args.workspace,
                log_path=qualification_log,
            )
            for control in ("current_only", "cmcp", "a0")
        }
        passed = all(
            str(payload["status"]).startswith("PASS_")
            for payload in aggregation.values()
        )
        status.update(
            (
                "PASS_R37_INTERNAL_QUALIFICATION"
                if passed
                else "STOP_R37_INTERNAL_QUALIFICATION"
            ),
            qualification={
                control: {
                    "status": payload["status"],
                    "output": str(qualification_root / f"{control}.json"),
                }
                for control, payload in aggregation.items()
            },
            scientific_claim_allowed=passed,
            completed_at=now_iso(),
        )
        return 0 if passed else 2
    except Exception as error:
        append_log(pipeline_log, f"STOP error={error!r}")
        if status is None:
            write_json_atomic(
                status_path,
                {
                    "schema": "visualvit.r37.formal-bundle-pipeline.v1",
                    "status": "STOP_R37_FORMAL_BUNDLE_PIPELINE",
                    "launcher_pid": os.getpid(),
                    "updated_at": now_iso(),
                    "errors": [repr(error)],
                    "protected_outcomes_read": False,
                    "sealed_test_read": False,
                    "gold_outcomes_read": False,
                    "source_hashes_recomputed": False,
                    "per_shard_hashes_computed": False,
                    "scientific_claim_allowed": False,
                },
            )
        else:
            status.update(
                "STOP_R37_FORMAL_BUNDLE_PIPELINE",
                errors=[repr(error)],
                scientific_claim_allowed=False,
            )
        return 2
    finally:
        release_single_instance(lock_path, descriptor)


if __name__ == "__main__":
    raise SystemExit(main())
