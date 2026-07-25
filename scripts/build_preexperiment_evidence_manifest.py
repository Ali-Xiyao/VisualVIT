from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def record(path: Path, category: str) -> dict[str, Any]:
    return {
        "category": category,
        "path": str(path.resolve()),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path(r"E:\Xiyaowang\050_VisualVIT"),
    )
    parser.add_argument(
        "--runtime",
        type=Path,
        default=Path(r"F:\VisualVIT_runtime\050_routeC"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            r"F:\VisualVIT_runtime\050_routeC\evidence"
            r"\preexperiment_evidence_manifest_20260713.json"
        ),
    )
    parser.add_argument("--include-qwen-shards", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    workspace_files = []
    for pattern in (
        "src/**/*.py",
        "scripts/*.py",
        "tests/*.py",
        "pyproject.toml",
        "docs/superpowers/specs/*.md",
        "docs/superpowers/plans/*.md",
        "refine-logs/*.md",
        "reports/*.md",
        "environment/*.md",
        "task_plan.md",
        "findings.md",
        "progress.md",
    ):
        workspace_files.extend(args.workspace.glob(pattern))
    workspace_files = sorted(
        {
            path.resolve()
            for path in workspace_files
            if "__pycache__" not in path.parts and path.is_file()
        },
        key=lambda value: str(value).lower(),
    )

    runtime_paths = [
        args.runtime
        / "runs"
        / "pilot_synthetic_auditfix_20260713"
        / name
        for name in ("config.json", "environment.json", "per_seed.jsonl", "summary.json", "manifest.json")
    ]
    runtime_paths += [
        args.runtime
        / "runs"
        / "pilot_synthetic_auditfix_rerun_20260713"
        / name
        for name in ("config.json", "environment.json", "per_seed.jsonl", "summary.json", "manifest.json")
    ]
    runtime_paths += [
        args.runtime / "runs" / "encoder_smoke_20260713T122945" / "summary.json",
        args.runtime / "runs" / "qwen2vl_2b_attempt2_20260713" / "summary.json",
        args.runtime / "runs" / "qwen2vl_7b_attempt1_20260713" / "summary.json",
        args.runtime / "runs" / "qwen2vl_2b_adapter_20260713" / "summary.json",
        args.runtime / "runs" / "qwen2vl_7b_adapter_20260713" / "summary.json",
        args.runtime / "data" / "mimic_proxy_manifest_240_20260713" / "proxy_manifest.csv",
        args.runtime / "data" / "mimic_proxy_manifest_240_20260713" / "summary.json",
        args.runtime
        / "runs"
        / "mimic_proxy_biomedclip_convergence_gate_20260713"
        / "per_seed.jsonl",
        args.runtime
        / "runs"
        / "mimic_proxy_biomedclip_convergence_gate_20260713"
        / "summary.json",
        args.runtime
        / "runs"
        / "mimic_proxy_biomedclip_convergence_gate_unitfix_20260713"
        / "per_seed.jsonl",
        args.runtime
        / "runs"
        / "mimic_proxy_biomedclip_convergence_gate_unitfix_20260713"
        / "summary.json",
    ]
    runtime_paths += sorted((args.runtime / "runs").glob("*console_20260713.log"))
    missing_runtime = [str(path) for path in runtime_paths if not path.is_file()]
    runtime_paths = [path for path in runtime_paths if path.is_file()]

    model_paths = [
        Path(
            r"H:\Xiyao_Wang\021_260129VIVID\pretrained"
            r"\biomedclip_vit_base.pt"
        )
    ]
    for model_dir in (
        Path(r"H:\Xiyao_Wang\001_models\Qwen2-VL-2B-Instruct"),
        Path(r"H:\Xiyao_Wang\001_models\Qwen2-VL-7B-Instruct"),
    ):
        model_paths.append(model_dir / "model.safetensors.index.json")
        if args.include_qwen_shards:
            model_paths.extend(sorted(model_dir.glob("model-*.safetensors")))

    files = []
    for path in workspace_files:
        files.append(record(path, "workspace"))
    for path in runtime_paths:
        files.append(record(path, "runtime_evidence"))
    for path in model_paths:
        files.append(record(path, "model_asset"))

    package_names = [
        "torch",
        "torchvision",
        "timm",
        "pandas",
        "Pillow",
        "transformers",
        "accelerate",
        "qwen-vl-utils",
        "pytest",
    ]
    packages = {
        name: importlib.metadata.version(name) for name in package_names
    }
    disks = {}
    for drive in ("E:\\", "F:\\", "H:\\"):
        usage = shutil.disk_usage(drive)
        disks[drive] = {
            "total_bytes": usage.total,
            "used_bytes": usage.used,
            "free_bytes": usage.free,
        }
    gpu_query = subprocess.run(
        [
            "nvidia-smi",
            "--query-gpu=index,name,uuid,driver_version,memory.total,memory.used,"
            "memory.free,utilization.gpu,temperature.gpu,pstate",
            "--format=csv,noheader,nounits",
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip().splitlines()

    manifest = {
        "evidence_class": "NON_CONFIRMATORY_PROXY",
        "formal_claim_allowed": False,
        "created_at": datetime.now().isoformat(),
        "workspace_git_repository": (args.workspace / ".git").exists(),
        "python": sys.version,
        "python_executable": sys.executable,
        "packages": packages,
        "disks": disks,
        "gpus": gpu_query,
        "include_qwen_shards": args.include_qwen_shards,
        "missing_expected_runtime_artifacts": missing_runtime,
        "files": files,
        "verdict": [
            "GO_NONCONFIRMATORY_COMPONENT_SMOKE_ONLY",
            "NO_GO_FORMAL_DATA_LICENSE_ETHICS_ORACLE",
            "NO_GO_END_TO_END_TRANSFER",
            "NO_GO_PHASE_II",
        ],
    }
    args.output.write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps({
        "output": str(args.output),
        "files": len(files),
        "missing": len(missing_runtime),
        "include_qwen_shards": args.include_qwen_shards,
    }, sort_keys=True))
    return 0 if not missing_runtime else 2


if __name__ == "__main__":
    raise SystemExit(main())
