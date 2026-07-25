from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import tarfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_SINGLE_FILES = (
    "pyproject.toml",
    "docs/superpowers/specs/2026-07-19-capes-ci-v1.md",
    "docs/superpowers/plans/2026-07-19-capes-ci-v1-implementation-plan.md",
    "refine-logs/EXPERIMENT_PLAN.md",
    "refine-logs/EXPERIMENT_TRACKER.md",
    "reports/formal_statistics_protocol_2026-07-19.md",
    "reports/survival_results_2026-07-19.md",
    "scripts/focused_payload.py",
    "scripts/run_capes_ci_synthetic_overfit.py",
    "scripts/run_qwen3vl_relation_token_smoke.py",
    "scripts/verify_capes_ci_synthetic_repro.py",
)
DEFAULT_TREES = ("src", "tests")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def selected_files(root: Path) -> list[Path]:
    files: set[Path] = set()
    for relative in DEFAULT_SINGLE_FILES:
        path = root / relative
        if not path.is_file():
            raise FileNotFoundError(f"required payload file is missing: {relative}")
        files.add(path)
    for relative in DEFAULT_TREES:
        tree = root / relative
        if not tree.is_dir():
            raise FileNotFoundError(f"required payload tree is missing: {relative}")
        files.update(
            path
            for path in tree.rglob("*")
            if path.is_file()
            and "__pycache__" not in path.parts
            and path.suffix != ".pyc"
        )
    return sorted(files, key=lambda path: path.relative_to(root).as_posix())


def manifest_for(root: Path, files: list[Path], label: str) -> dict[str, Any]:
    entries = []
    for path in files:
        entries.append(
            {
                "path": path.relative_to(root).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    return {
        "schema": "visualvit-focused-source-manifest-v1",
        "label": label,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "entry_count": len(entries),
        "entries": entries,
    }


def normalized_tar_info(path: Path, arcname: str) -> tarfile.TarInfo:
    info = tarfile.TarInfo(arcname)
    info.size = path.stat().st_size
    info.mode = 0o644
    info.mtime = 0
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    return info


def build(args: argparse.Namespace) -> int:
    root = args.root.resolve()
    files = selected_files(root)
    manifest = manifest_for(root, files, args.label)
    manifest_bytes = json.dumps(
        manifest, indent=2, sort_keys=True, ensure_ascii=False
    ).encode("utf-8")

    args.archive.parent.mkdir(parents=True, exist_ok=True)
    with args.archive.open("wb") as raw_handle:
        with gzip.GzipFile(fileobj=raw_handle, mode="wb", mtime=0) as gzip_handle:
            with tarfile.open(fileobj=gzip_handle, mode="w") as archive:
                for path in files:
                    arcname = path.relative_to(root).as_posix()
                    info = normalized_tar_info(path, arcname)
                    with path.open("rb") as file_handle:
                        archive.addfile(info, file_handle)
                info = tarfile.TarInfo("SOURCE_MANIFEST.json")
                info.size = len(manifest_bytes)
                info.mode = 0o644
                info.mtime = 0
                info.uid = 0
                info.gid = 0
                archive.addfile(info, io.BytesIO(manifest_bytes))

    envelope = {
        "archive": str(args.archive.resolve()),
        "archive_bytes": args.archive.stat().st_size,
        "archive_sha256": sha256_file(args.archive),
        "source_manifest_sha256": sha256_bytes(manifest_bytes),
        "source_manifest": manifest,
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(
        json.dumps(envelope, indent=2, sort_keys=True, ensure_ascii=False),
        encoding="utf-8",
    )
    print(json.dumps(envelope, indent=2, sort_keys=True, ensure_ascii=False))
    return 0


def verify(args: argparse.Namespace) -> int:
    root = args.root.resolve()
    manifest_path = root / args.manifest
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    failures: list[dict[str, Any]] = []
    for entry in manifest["entries"]:
        path = root / entry["path"]
        if not path.is_file():
            failures.append({"path": entry["path"], "error": "missing"})
            continue
        actual_size = path.stat().st_size
        actual_hash = sha256_file(path)
        if actual_size != entry["bytes"] or actual_hash != entry["sha256"]:
            failures.append(
                {
                    "path": entry["path"],
                    "expected_bytes": entry["bytes"],
                    "actual_bytes": actual_size,
                    "expected_sha256": entry["sha256"],
                    "actual_sha256": actual_hash,
                }
            )
    result = {
        "status": "PASS" if not failures else "FAIL",
        "root": str(root),
        "manifest": str(manifest_path),
        "entry_count": manifest["entry_count"],
        "failure_count": len(failures),
        "failures": failures,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if not failures else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build or verify a focused payload")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_parser = subparsers.add_parser("build")
    build_parser.add_argument("--root", required=True, type=Path)
    build_parser.add_argument("--archive", required=True, type=Path)
    build_parser.add_argument("--manifest", required=True, type=Path)
    build_parser.add_argument("--label", required=True)
    build_parser.set_defaults(handler=build)

    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("--root", required=True, type=Path)
    verify_parser.add_argument(
        "--manifest", default=Path("SOURCE_MANIFEST.json"), type=Path
    )
    verify_parser.set_defaults(handler=verify)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
