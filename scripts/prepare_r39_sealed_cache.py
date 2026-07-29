from __future__ import annotations

# ruff: noqa: E402

import argparse
import json
from pathlib import Path
import sys
import time
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE))
sys.path.insert(0, str(WORKSPACE / "src"))

import torch
from torch.utils.data import DataLoader

from scripts.cache_r37_block8_tokens import (
    BLOCK_COUNT,
    CONFIG,
    EXPECTED_VISUAL_KEYS,
    ImageDataset,
    TOKEN_SHAPE,
    WEIGHTS,
    build_frozen_encoder,
    forward_to_block8,
)
from scripts.r37c_common import STRUCTURAL_FIELDS, structural_projection
from scripts.r39_common import DEFAULT_R39_CONFIG, load_r39_config, read_json, write_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the outcome-free R39 sealed Block-8 cache"
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_R39_CONFIG)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--shard-size", type=int, default=256)
    parser.add_argument("--workers", type=int, default=4)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_r39_config(args.config)
    sealed = config["sealed_test"]
    output_root = Path(sealed["block8_cache_root"])
    if output_root.exists():
        raise FileExistsError(f"sealed cache root must be fresh: {output_root}")
    rows = structural_projection(
        read_json(Path(sealed["structural_manifest"])),
        partition="sealed_vlm_test",
    )
    if (
        len(rows) != int(sealed["expected_rows"])
        or len({str(row["patient_id"]) for row in rows})
        != int(sealed["expected_patients"])
        or any(key not in STRUCTURAL_FIELDS for row in rows for key in row)
    ):
        raise ValueError("R39 sealed structural roster drift")
    images: dict[str, str] = {}
    for row in rows:
        for id_key, path_key in (
            ("prior_dicom_id", "prior_path"),
            ("current_dicom_id", "current_path"),
        ):
            dicom_id, path = str(row[id_key]), str(row[path_key])
            previous = images.setdefault(dicom_id, path)
            if previous != path:
                raise ValueError(f"DICOM {dicom_id} maps to two paths")
    inventory = [
        {"dicom_id": key, "path": images[key]} for key in sorted(images)
    ]
    missing = [item["path"] for item in inventory if not Path(item["path"]).is_file()]
    if missing:
        raise FileNotFoundError(f"sealed cache image missing: {missing[0]}")

    part_root = output_root / "part_00_of_01"
    shards_root = part_root / "shards"
    shards_root.mkdir(parents=True, exist_ok=False)
    write_json(output_root / "sealed_structure.json", rows)
    write_json(part_root / "image_inventory.json", inventory)
    device = torch.device(args.device)
    torch.cuda.set_device(device)
    torch.cuda.reset_peak_memory_stats(device)
    encoder = build_frozen_encoder(device)
    loader = DataLoader(
        ImageDataset(inventory),
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=args.workers,
        pin_memory=True,
        persistent_workers=args.workers > 0,
    )
    started = time.perf_counter()
    pending_ids: list[str] = []
    pending_features: list[torch.Tensor] = []
    shards: list[dict[str, Any]] = []
    total = 0

    def flush() -> None:
        nonlocal pending_ids, pending_features
        if not pending_ids:
            return
        features = torch.cat(pending_features)
        path = shards_root / f"block8_tokens_{len(shards):04d}.pt"
        torch.save(
            {
                "schema": "visualvit.r37.biomedclip-block8.v1",
                "dicom_ids": list(pending_ids),
                "features": features,
                "shape": list(features.shape),
                "dtype": str(features.dtype),
                "completed_blocks": BLOCK_COUNT,
                "final_encoder_norm_applied": False,
            },
            path,
        )
        shards.append(
            {"path": str(path), "images": len(pending_ids), "bytes": path.stat().st_size}
        )
        pending_ids, pending_features = [], []

    with torch.inference_mode():
        for dicom_ids, images_tensor in loader:
            features = forward_to_block8(
                encoder, images_tensor.to(device, non_blocking=True)
            )
            if tuple(features.shape[1:]) != TOKEN_SHAPE:
                raise RuntimeError("sealed Block-8 shape drift")
            features = features.to(torch.float16).cpu()
            start = 0
            while start < len(dicom_ids):
                take = min(args.shard_size - len(pending_ids), len(dicom_ids) - start)
                pending_ids.extend(dicom_ids[start : start + take])
                pending_features.append(features[start : start + take])
                start += take
                total += take
                if len(pending_ids) == args.shard_size:
                    flush()
    flush()
    elapsed = time.perf_counter() - started
    part_manifest = {
        "schema": "visualvit.r39.sealed-block8-part.v1",
        "status": "PASS_R37_BLOCK8_FORMAL_CACHE",
        "cached_image_count": total,
        "shards": shards,
        "encoder": {
            "weights_path": str(WEIGHTS),
            "weights_bytes": WEIGHTS.stat().st_size,
            "config_path": str(CONFIG),
            "config_bytes": CONFIG.stat().st_size,
            "strict_visual_key_count": EXPECTED_VISUAL_KEYS,
        },
        "elapsed_seconds": elapsed,
        "source_hashes_recomputed": False,
        "per_shard_hashes_computed": False,
        "sealed_483_test_labels_read": False,
        "gold_outcomes_read": False,
    }
    part_path = part_root / "cache_manifest.json"
    write_json(part_path, part_manifest)
    merged = {
        "schema": "visualvit.r39.sealed-block8-cache.v1",
        "status": "PASS_R37_BLOCK8_FORMAL_CACHE",
        "cached_image_count": total,
        "rows": len(rows),
        "patients": len({str(row["patient_id"]) for row in rows}),
        "parts": [{"part_index": 0, "manifest_path": str(part_path)}],
        "source_hashes_recomputed": False,
        "per_shard_hashes_computed": False,
        "sealed_483_test_labels_read": False,
        "gold_outcomes_read": False,
    }
    write_json(output_root / "cache_manifest.json", merged)
    print(json.dumps(merged, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
