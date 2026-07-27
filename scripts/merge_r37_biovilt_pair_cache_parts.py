from __future__ import annotations

# ruff: noqa: E402

import argparse
import json
from pathlib import Path
import sys
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE / "src"))

import torch

from visualvit.biovilt import (
    BIOVILT_CONTROL_MODES,
    BIOVILT_HUB_REVISION,
    HI_ML_REVISION,
)


ROOT = Path(
    r"H:\VisualVIT_runtime\050_routeD\r37_prta_cxr"
    r"\r37_biovilt_pair_cache"
)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def merge_parts(root: Path, part_count: int) -> dict[str, Any]:
    if part_count <= 0:
        raise ValueError("part count must be positive")
    manifests = []
    pair_ids: set[str] = set()
    expected_start = 0
    formal_count = None
    parts = []
    for index in range(part_count):
        directory = f"part_{index:02d}_of_{part_count:02d}"
        part_root = root / directory
        manifest = read_json(
            part_root / "r37_biovilt_pair_cache_manifest.json"
        )
        manifests.append(manifest)
        if manifest["status"] != "PASS_R37_A1_CONTROL_CACHE":
            raise ValueError(f"A1 part gate failed: {directory}")
        if int(manifest["part_index"]) != index:
            raise ValueError(f"A1 part index drift: {directory}")
        if int(manifest["part_count"]) != part_count:
            raise ValueError(f"A1 part count drift: {directory}")
        if int(manifest["part_start"]) != expected_start:
            raise ValueError(f"A1 part range gap: {directory}")
        expected_start = int(manifest["part_end"])
        if formal_count is None:
            formal_count = int(manifest["formal_inventory_count"])
        elif formal_count != int(manifest["formal_inventory_count"]):
            raise ValueError("A1 formal inventory count drift")
        if tuple(manifest["controls"]) != BIOVILT_CONTROL_MODES:
            raise ValueError("A1 control registry drift")
        part_ids = []
        for shard in manifest["shards"]:
            payload = torch.load(
                part_root / str(shard["file"]),
                map_location="cpu",
                weights_only=True,
            )
            ids = [str(value) for value in payload["pair_ids"]]
            if len(ids) != int(shard["count"]):
                raise ValueError("A1 shard count drift")
            part_ids.extend(ids)
        if len(part_ids) != int(manifest["pair_count"]):
            raise ValueError(f"A1 part pair count drift: {directory}")
        overlap = pair_ids.intersection(part_ids)
        if overlap:
            raise ValueError(f"A1 cross-part overlap: {next(iter(overlap))}")
        pair_ids.update(part_ids)
        parts.append(
            {
                "directory": directory,
                "pair_count": len(part_ids),
                "part_start": int(manifest["part_start"]),
                "part_end": int(manifest["part_end"]),
            }
        )
    if formal_count is None or expected_start != formal_count:
        raise ValueError("A1 parts do not cover the formal inventory")
    if len(pair_ids) != formal_count:
        raise ValueError("A1 unique pair coverage drift")
    return {
        "schema": "visualvit.r37.biovilt-pair-control-cache-merged.v2",
        "status": "PASS_R37_A1_CONTROL_CACHE_MERGED",
        "pair_count": formal_count,
        "part_count": part_count,
        "feature_dim": 128,
        "controls": list(BIOVILT_CONTROL_MODES),
        "hub_revision": BIOVILT_HUB_REVISION,
        "hi_ml_revision": HI_ML_REVISION,
        "protected_outcomes_read": False,
        "source_hashes_recomputed": False,
        "parts": parts,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Merge and audit R37 A1 BioViL-T control-cache parts"
    )
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--part-count", type=int, default=2)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output = args.root / "r37_biovilt_pair_cache_manifest.json"
    if output.exists():
        raise FileExistsError(f"merged A1 manifest must be fresh: {output}")
    payload = merge_parts(args.root, args.part_count)
    output.write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
