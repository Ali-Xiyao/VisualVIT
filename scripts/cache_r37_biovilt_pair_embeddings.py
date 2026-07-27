from __future__ import annotations

# ruff: noqa: E402

import argparse
import json
from pathlib import Path
import sys
import time
from typing import Any, Iterable

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE / "src"))

import torch
from torch.utils.data import DataLoader, Dataset

from visualvit.biovilt import (
    BIOVILT_FEATURE_DIM,
    BIOVILT_HUB_REVISION,
    HI_ML_REVISION,
    canonical_pair_embedding,
    load_biovilt_image,
    load_frozen_biovilt,
)


INPUT_ROOT = Path(
    r"H:\VisualVIT_runtime\050_routeD\r37_prta_cxr\r37a_data_v1"
)
OUTPUT_BASE = Path(
    r"H:\VisualVIT_runtime\050_routeD\r37_prta_cxr"
)
CHECKPOINT = Path(
    r"H:\Xiyao_Wang\001_models\biovilt"
    r"\biovil_t_image_model_proj_size_128.pt"
)
HI_ML_SOURCE = Path(
    r"H:\VisualVIT_runtime\050_routeD\external"
    r"\microsoft_hi_ml_b67c1d27\hi-ml-multimodal\src"
)


def read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def pair_inventory(input_root: Path) -> list[dict[str, str]]:
    rows = []
    seen: set[str] = set()
    for partition, name in (
        ("pretrain", "r37_pretrain_manifest.jsonl"),
        (
            "internal_calibration",
            "r37_internal_calibration_manifest.jsonl",
        ),
    ):
        for row in read_jsonl(input_root / name):
            pair_id = str(row["pair_id"])
            if pair_id in seen:
                raise ValueError(f"duplicate pair_id: {pair_id}")
            seen.add(pair_id)
            rows.append(
                {
                    "pair_id": pair_id,
                    "partition": partition,
                    "prior_path": str(row["prior_path"]),
                    "current_path": str(row["current_path"]),
                }
            )
    return rows


def contiguous_part_bounds(
    length: int, part_index: int, part_count: int
) -> tuple[int, int]:
    if part_count <= 0:
        raise ValueError("part count must be positive")
    if not 0 <= part_index < part_count:
        raise ValueError("part index must be within [0, part_count)")
    return (
        length * part_index // part_count,
        length * (part_index + 1) // part_count,
    )


class PairDataset(Dataset):
    def __init__(self, inventory: list[dict[str, str]]) -> None:
        self.inventory = inventory

    def __len__(self) -> int:
        return len(self.inventory)

    def __getitem__(self, index: int):
        row = self.inventory[index]
        return (
            row["pair_id"],
            row["partition"],
            load_biovilt_image(row["prior_path"]),
            load_biovilt_image(row["current_path"]),
        )


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True), encoding="utf-8"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Cache official frozen BioViL-T pair embeddings for R37 A1"
    )
    parser.add_argument("--input-root", type=Path, default=INPUT_ROOT)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--checkpoint", type=Path, default=CHECKPOINT)
    parser.add_argument("--hi-ml-source", type=Path, default=HI_ML_SOURCE)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--shard-size", type=int, default=1024)
    parser.add_argument("--smoke-pairs", type=int, default=8)
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--part-index", type=int, default=0)
    parser.add_argument("--part-count", type=int, default=1)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.batch_size <= 0 or args.shard_size <= 0:
        raise ValueError("batch and shard sizes must be positive")
    if not args.full and args.smoke_pairs <= 0:
        raise ValueError("smoke pair count must be positive")

    inventory = pair_inventory(args.input_root)
    formal_count = len(inventory)
    if args.full:
        start, end = contiguous_part_bounds(
            formal_count, args.part_index, args.part_count
        )
        inventory = inventory[start:end]
        default_output = (
            OUTPUT_BASE
            / "r37_biovilt_pair_cache"
            / f"part_{args.part_index:02d}_of_{args.part_count:02d}"
        )
    else:
        if args.part_index != 0 or args.part_count != 1:
            raise ValueError("cache parts are supported only with --full")
        start, end = 0, min(args.smoke_pairs, formal_count)
        inventory = inventory[start:end]
        default_output = OUTPUT_BASE / "r37_biovilt_pair_cache_smoke_v1"
    output_root = args.output_root or default_output
    if output_root.exists():
        raise FileExistsError(f"output root must be fresh: {output_root}")
    missing = [
        path
        for row in inventory
        for path in (row["prior_path"], row["current_path"])
        if not Path(path).is_file()
    ]
    if missing:
        raise FileNotFoundError(
            f"{len(missing)} BioViL-T input paths missing; first={missing[0]}"
        )

    device = torch.device(args.device)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but unavailable")
    output_root.mkdir(parents=True)
    model = load_frozen_biovilt(
        args.checkpoint, args.hi_ml_source, device
    )
    loader = DataLoader(
        PairDataset(inventory),
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=args.workers,
        pin_memory=device.type == "cuda",
    )

    started = time.perf_counter()
    shard_ids: list[str] = []
    shard_partitions: list[str] = []
    shard_embeddings: list[torch.Tensor] = []
    shards = []
    processed = 0
    reproducibility_max_abs = None

    def flush() -> None:
        nonlocal shard_ids, shard_partitions, shard_embeddings
        if not shard_ids:
            return
        shard_name = f"shard_{len(shards):05d}.pt"
        tensor = torch.cat(shard_embeddings).to(dtype=torch.float16)
        torch.save(
            {
                "pair_ids": tuple(shard_ids),
                "partitions": tuple(shard_partitions),
                "embeddings": tensor,
            },
            output_root / shard_name,
        )
        shards.append(
            {
                "file": shard_name,
                "count": len(shard_ids),
                "shape": list(tensor.shape),
            }
        )
        shard_ids = []
        shard_partitions = []
        shard_embeddings = []

    for pair_ids, partitions, prior, current in loader:
        prior = prior.to(device, non_blocking=True)
        current = current.to(device, non_blocking=True)
        embeddings = canonical_pair_embedding(
            model, current_image=current, prior_image=prior
        )
        if reproducibility_max_abs is None:
            repeated = canonical_pair_embedding(
                model, current_image=current, prior_image=prior
            )
            reproducibility_max_abs = float(
                (embeddings - repeated).abs().max().item()
            )
        for index, pair_id in enumerate(pair_ids):
            shard_ids.append(str(pair_id))
            shard_partitions.append(str(partitions[index]))
            shard_embeddings.append(embeddings[index : index + 1].cpu())
            processed += 1
            if len(shard_ids) >= args.shard_size:
                flush()
    flush()

    elapsed = time.perf_counter() - started
    manifest = {
        "schema": "visualvit.r37.biovilt-pair-cache.v1",
        "status": "PASS_R37_A1_CACHE",
        "formal": bool(args.full),
        "formal_inventory_count": formal_count,
        "part_index": args.part_index,
        "part_count": args.part_count,
        "part_start": start,
        "part_end": end,
        "pair_count": processed,
        "feature_dim": BIOVILT_FEATURE_DIM,
        "dtype": "float16",
        "hub_revision": BIOVILT_HUB_REVISION,
        "hi_ml_revision": HI_ML_REVISION,
        "checkpoint": str(args.checkpoint),
        "hi_ml_source": str(args.hi_ml_source),
        "elapsed_seconds": elapsed,
        "pairs_per_second": processed / elapsed if elapsed else 0.0,
        "reproducibility_max_abs": reproducibility_max_abs,
        "protected_outcomes_read": False,
        "source_hashes_recomputed": False,
        "shards": shards,
    }
    write_json(output_root / "r37_biovilt_pair_cache_manifest.json", manifest)
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
