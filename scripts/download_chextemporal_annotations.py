from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import requests


REPO_ID = "anonaccount107240/CheXTemporal"
REVISION = "81fd9cdd9b1208d8f8bd39d7a914c9b72fed8d79"
FILES = (
    "gold_progression_pairs.parquet",
    "gold_bboxes.parquet",
    "LICENSE",
    "README.md",
    "DATASHEET.md",
)
EXPECTED_SHA256 = {
    "gold_progression_pairs.parquet": (
        "22cda4e85c01c1d67d905fbba0c8a1a9169e2e5b99f754b93782b5c67dfed14b"
    ),
    "gold_bboxes.parquet": (
        "20f114c7f81a66986ed0a697d4056d2b9c4029e7df77c97217db4908726f2064"
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download the SHA-pinned public CheXTemporal annotations."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/official/chextemporal_81fd9cdd"),
    )
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_url(filename: str) -> str:
    return (
        f"https://huggingface.co/datasets/{REPO_ID}/resolve/"
        f"{REVISION}/{filename}?download=true"
    )


def download_file(
    session: requests.Session,
    filename: str,
    output_dir: Path,
    *,
    force: bool,
) -> dict[str, Any]:
    target = output_dir / filename
    expected = EXPECTED_SHA256.get(filename)
    if target.exists() and not force:
        actual = sha256_file(target)
        if expected is None or actual == expected:
            return {
                "filename": filename,
                "bytes": target.stat().st_size,
                "sha256": actual,
                "source_url": resolve_url(filename),
                "status": "REUSED_VERIFIED",
            }
        raise RuntimeError(
            f"existing file hash mismatch for {filename}: {actual} != {expected}"
        )

    part = target.with_name(f"{target.name}.part")
    if part.exists():
        raise RuntimeError(
            f"preserved partial file already exists; inspect before retrying: {part}"
        )
    with session.get(
        resolve_url(filename),
        stream=True,
        timeout=(30, 180),
        allow_redirects=True,
    ) as response:
        response.raise_for_status()
        with part.open("xb") as handle:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    handle.write(chunk)
            handle.flush()
            os.fsync(handle.fileno())

    actual = sha256_file(part)
    if expected is not None and actual != expected:
        raise RuntimeError(
            f"downloaded hash mismatch for {filename}: {actual} != {expected}; "
            f"partial preserved at {part}"
        )
    os.replace(part, target)
    return {
        "filename": filename,
        "bytes": target.stat().st_size,
        "sha256": actual,
        "source_url": resolve_url(filename),
        "status": "DOWNLOADED_VERIFIED",
    }


def main() -> int:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers["User-Agent"] = "VisualVIT-CheXTemporal-audit/1.0"
    records = [
        download_file(session, filename, args.output_dir, force=args.force)
        for filename in FILES
    ]
    report = {
        "status": "PASS",
        "evidence_class": "PUBLIC_ANNOTATION_ACQUISITION",
        "formal_claim_allowed": False,
        "repo_id": REPO_ID,
        "revision": REVISION,
        "contains_images": False,
        "files": records,
    }
    manifest = args.output_dir / "download_manifest.json"
    manifest.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
