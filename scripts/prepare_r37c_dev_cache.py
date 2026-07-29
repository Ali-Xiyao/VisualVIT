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
from scripts.r37c_common import (
    DEFAULT_CANDIDATE,
    load_candidate,
    read_json,
    structural_projection,
    validate_dev_structure,
    write_json,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare the outcome-free R37C dev Block-8 cache"
    )
    parser.add_argument("--candidate", type=Path, default=DEFAULT_CANDIDATE)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--shard-size", type=int, default=256)
    parser.add_argument("--workers", type=int, default=4)
    return parser.parse_args()


def image_inventory(rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    images: dict[str, str] = {}
    for row in rows:
        for id_key, path_key in (
            ("prior_dicom_id", "prior_path"),
            ("current_dicom_id", "current_path"),
        ):
            dicom_id = str(row[id_key])
            path = str(row[path_key])
            previous = images.setdefault(dicom_id, path)
            if previous != path:
                raise ValueError(f"DICOM {dicom_id} maps to two paths")
    return [
        {"dicom_id": dicom_id, "path": images[dicom_id]}
        for dicom_id in sorted(images)
    ]


def main() -> int:
    args = parse_args()
    if args.batch_size <= 0 or args.shard_size <= 0 or args.workers < 0:
        raise ValueError("invalid cache execution settings")
    candidate = load_candidate(args.candidate)
    one_shot = candidate["r37c_one_shot"]
    output_root = Path(one_shot["structural_cache_root"])
    reveal_root = Path(one_shot["protected_reveal_root"])
    if output_root.exists():
        raise FileExistsError(f"cache root must be fresh: {output_root}")
    if reveal_root.exists():
        raise PermissionError(
            "protected reveal root already exists before structural cache"
        )

    # json.load necessarily parses the mixed train/dev container, but only the
    # explicit structural projection below is returned or persisted. No
    # progression field is indexed, summarized, logged, or used at this stage.
    mixed_rows = read_json(Path(one_shot["source"]))
    structure = structural_projection(
        mixed_rows, partition=str(one_shot["partition"])
    )
    del mixed_rows
    validate_dev_structure(structure, candidate)
    inventory = image_inventory(structure)
    missing = [item["path"] for item in inventory if not Path(item["path"]).is_file()]
    if missing:
        raise FileNotFoundError(
            f"{len(missing)} R37C images missing; first={missing[0]}"
        )

    part_root = output_root / "part_00_of_01"
    shards_root = part_root / "shards"
    shards_root.mkdir(parents=True, exist_ok=False)
    write_json(output_root / "dev_structure.json", structure)
    write_json(part_root / "image_inventory.json", inventory)

    device = torch.device(args.device)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but unavailable")
    if device.type == "cuda":
        torch.cuda.set_device(device)
        torch.cuda.reset_peak_memory_stats(device)
    encoder = build_frozen_encoder(device)
    loader = DataLoader(
        ImageDataset(inventory),
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=args.workers,
        pin_memory=device.type == "cuda",
        persistent_workers=args.workers > 0,
    )

    started = time.perf_counter()
    pending_ids: list[str] = []
    pending_features: list[torch.Tensor] = []
    shards: list[dict[str, Any]] = []
    total = 0
    reproducibility: dict[str, Any] | None = None

    def flush() -> None:
        nonlocal pending_ids, pending_features
        if not pending_ids:
            return
        features = torch.cat(pending_features, dim=0)
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
            {
                "path": str(path),
                "images": len(pending_ids),
                "bytes": path.stat().st_size,
                "first_dicom_id": pending_ids[0],
                "last_dicom_id": pending_ids[-1],
            }
        )
        pending_ids = []
        pending_features = []

    with torch.inference_mode():
        for dicom_ids, images in loader:
            images = images.to(device, non_blocking=True)
            features = forward_to_block8(encoder, images)
            if tuple(features.shape[1:]) != TOKEN_SHAPE:
                raise RuntimeError(
                    f"unexpected Block-8 shape: {tuple(features.shape)}"
                )
            if not bool(torch.isfinite(features).all()):
                raise RuntimeError("R37C Block-8 features are non-finite")
            if reproducibility is None:
                repeated = forward_to_block8(encoder, images)
                reproducibility = {
                    "repeated_batch_images": len(dicom_ids),
                    "identical": torch.equal(features, repeated),
                    "maximum_absolute_difference": float(
                        (features - repeated).abs().max().item()
                    ),
                }
                if not reproducibility["identical"]:
                    raise RuntimeError("R37C repeated cache batch differs")
            features = features.to(torch.float16).cpu()
            start = 0
            while start < len(dicom_ids):
                remaining = args.shard_size - len(pending_ids)
                take = min(remaining, len(dicom_ids) - start)
                pending_ids.extend(dicom_ids[start : start + take])
                pending_features.append(features[start : start + take])
                total += take
                start += take
                if len(pending_ids) == args.shard_size:
                    flush()
    flush()
    elapsed = time.perf_counter() - started
    part_manifest = {
        "schema": "visualvit.r37c.block8-cache-part.v1",
        "status": "PASS_R37_BLOCK8_FORMAL_CACHE",
        "scope": "r37c_dev_structural_part_0_of_1",
        "cached_image_count": total,
        "feature_shape_per_image": list(TOKEN_SHAPE),
        "feature_dtype": "torch.float16",
        "extraction_boundary": {
            "completed_blocks": BLOCK_COUNT,
            "next_block_index_zero_based": BLOCK_COUNT,
            "final_encoder_norm_applied": False,
        },
        "encoder": {
            "name": "BiomedCLIP ViT-B/16 visual trunk",
            "weights_path": str(WEIGHTS),
            "weights_bytes": WEIGHTS.stat().st_size,
            "config_path": str(CONFIG),
            "config_bytes": CONFIG.stat().st_size,
            "strict_visual_key_count": EXPECTED_VISUAL_KEYS,
            "all_frozen": True,
        },
        "reproducibility": reproducibility,
        "shards": shards,
        "shard_count": len(shards),
        "total_bytes": sum(item["bytes"] for item in shards),
        "elapsed_seconds": elapsed,
        "images_per_second": total / elapsed,
        "device": str(device),
        "source_hashes_recomputed": False,
        "per_shard_hashes_computed": False,
        "protected_outcomes_read": False,
    }
    part_manifest_path = part_root / "cache_manifest.json"
    write_json(part_manifest_path, part_manifest)
    merged = {
        "schema": "visualvit.r37c.block8-cache-manifest.v1",
        "status": "PASS_R37_BLOCK8_FORMAL_CACHE",
        "candidate_id": candidate["candidate_id"],
        "partition": one_shot["partition"],
        "dev_rows": len(structure),
        "dev_patients": len({str(row["patient_id"]) for row in structure}),
        "cached_image_count": total,
        "parts": [
            {
                "part_index": 0,
                "manifest_path": str(part_manifest_path),
                "cached_image_count": total,
            }
        ],
        "source_container_opened_for_structural_projection": True,
        "progression_field_indexed_or_persisted": False,
        "protected_outcomes_read": False,
        "sealed_483_test_read": False,
        "gold_outcomes_read": False,
        "source_hashes_recomputed": False,
        "per_shard_hashes_computed": False,
    }
    write_json(output_root / "cache_manifest.json", merged)
    print(json.dumps(merged, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
