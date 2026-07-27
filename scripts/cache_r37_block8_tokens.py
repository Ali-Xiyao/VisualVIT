from __future__ import annotations

# ruff: noqa: E402

import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
from typing import Any, Iterable

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE / "src"))

import torch
from PIL import Image
import timm
from torch.utils.data import DataLoader, Dataset
from torchvision import transforms


MODEL_ROOT = Path(r"H:\Xiyao_Wang\001_models\biomedclip")
WEIGHTS = MODEL_ROOT / "open_clip_pytorch_model.bin"
CONFIG = MODEL_ROOT / "open_clip_config.json"
INPUT_ROOT = Path(
    r"H:\VisualVIT_runtime\050_routeD\r37_prta_cxr\r37a_data_v1"
)
RUNTIME_ROOT = Path(r"H:\VisualVIT_runtime\050_routeD\r37_prta_cxr")
SMOKE_ROOT = RUNTIME_ROOT / "r37_block8_token_cache_smoke_v1"
FORMAL_ROOT = RUNTIME_ROOT / "r37_block8_token_cache"
CLIP_MEAN = (0.48145466, 0.4578275, 0.40821073)
CLIP_STD = (0.26862954, 0.26130258, 0.27577711)
EXPECTED_VISUAL_KEYS = 150
BLOCK_COUNT = 8
TOKEN_SHAPE = (197, 768)


def stable_hash(*parts: object) -> str:
    return hashlib.sha256(
        "|".join(str(part) for part in parts).encode("utf-8")
    ).hexdigest()


def read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def image_inventory(input_root: Path) -> list[dict[str, str]]:
    images: dict[str, str] = {}
    for name in (
        "r37_pretrain_manifest.jsonl",
        "r37_internal_calibration_manifest.jsonl",
    ):
        for row in read_jsonl(input_root / name):
            for id_field, path_field in (
                ("prior_dicom_id", "prior_path"),
                ("current_dicom_id", "current_path"),
            ):
                dicom_id = str(row[id_field])
                path = str(row[path_field])
                previous = images.setdefault(dicom_id, path)
                if previous != path:
                    raise ValueError(f"DICOM {dicom_id} maps to two paths")
    return [
        {"dicom_id": dicom_id, "path": images[dicom_id]}
        for dicom_id in sorted(images)
    ]


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


def visual_state_dict(
    checkpoint: dict[str, torch.Tensor],
) -> dict[str, torch.Tensor]:
    prefix = "visual.trunk."
    state = {
        key[len(prefix) :]: value
        for key, value in checkpoint.items()
        if key.startswith(prefix)
    }
    if len(state) != EXPECTED_VISUAL_KEYS:
        raise RuntimeError(
            f"expected {EXPECTED_VISUAL_KEYS} BiomedCLIP visual keys, "
            f"got {len(state)}"
        )
    return state


def build_frozen_encoder(device: torch.device) -> torch.nn.Module:
    checkpoint = torch.load(WEIGHTS, map_location="cpu", weights_only=True)
    model = timm.create_model(
        "vit_base_patch16_224", pretrained=False, num_classes=0
    )
    loaded = model.load_state_dict(visual_state_dict(checkpoint), strict=True)
    if loaded.missing_keys or loaded.unexpected_keys:
        raise RuntimeError(
            f"strict encoder load mismatch: {loaded.missing_keys}, "
            f"{loaded.unexpected_keys}"
        )
    model.eval().requires_grad_(False).to(device)
    if model.training or any(
        parameter.requires_grad for parameter in model.parameters()
    ):
        raise RuntimeError("BiomedCLIP encoder freeze audit failed")
    if len(model.blocks) != 12:
        raise RuntimeError(f"expected 12 ViT blocks, got {len(model.blocks)}")
    return model


def forward_to_block8(
    encoder: torch.nn.Module, images: torch.Tensor
) -> torch.Tensor:
    tokens = encoder.patch_embed(images)
    tokens = encoder._pos_embed(tokens)
    tokens = encoder.patch_drop(tokens)
    tokens = encoder.norm_pre(tokens)
    for block in encoder.blocks[:BLOCK_COUNT]:
        tokens = block(tokens)
    return tokens


class ImageDataset(Dataset):
    def __init__(self, inventory: list[dict[str, str]]) -> None:
        self.inventory = inventory
        self.preprocess = transforms.Compose(
            (
                transforms.Resize((224, 224), antialias=True),
                transforms.ToTensor(),
                transforms.Normalize(CLIP_MEAN, CLIP_STD),
            )
        )

    def __len__(self) -> int:
        return len(self.inventory)

    def __getitem__(self, index: int):
        item = self.inventory[index]
        with Image.open(item["path"]) as image:
            tensor = self.preprocess(image.convert("RGB"))
        return item["dicom_id"], tensor


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True), encoding="utf-8"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Cache frozen BiomedCLIP Block-8 patch tokens for R37"
    )
    parser.add_argument("--input-root", type=Path, default=INPUT_ROOT)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--device", default="cuda:1")
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--shard-size", type=int, default=256)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument(
        "--full",
        action="store_true",
        help="cache the complete inventory; default is a 64-image smoke",
    )
    parser.add_argument("--smoke-images", type=int, default=64)
    parser.add_argument("--part-index", type=int, default=0)
    parser.add_argument("--part-count", type=int, default=1)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.full and args.part_count > 1:
        default_output = (
            FORMAL_ROOT
            / f"part_{args.part_index:02d}_of_{args.part_count:02d}"
        )
    else:
        default_output = FORMAL_ROOT if args.full else SMOKE_ROOT
    output_root = args.output_root or default_output
    if output_root.exists():
        raise FileExistsError(f"output root must be fresh: {output_root}")
    if args.batch_size <= 0 or args.shard_size <= 0:
        raise ValueError("batch and shard sizes must be positive")
    if not args.full and args.smoke_images <= 0:
        raise ValueError("smoke image count must be positive")

    inventory = image_inventory(args.input_root)
    formal_inventory_count = len(inventory)
    if args.full:
        part_start, part_end = contiguous_part_bounds(
            formal_inventory_count, args.part_index, args.part_count
        )
        inventory = inventory[part_start:part_end]
    else:
        if args.part_index != 0 or args.part_count != 1:
            raise ValueError("cache parts are supported only with --full")
        part_start, part_end = 0, min(args.smoke_images, len(inventory))
        inventory = inventory[: args.smoke_images]
    missing = [item["path"] for item in inventory if not Path(item["path"]).is_file()]
    if missing:
        raise FileNotFoundError(
            f"{len(missing)} cache images are missing; first={missing[0]}"
        )

    device = torch.device(args.device)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but unavailable")
    encoder = build_frozen_encoder(device)
    dataset = ImageDataset(inventory)
    loader = DataLoader(
        dataset,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=args.workers,
        pin_memory=device.type == "cuda",
        persistent_workers=args.workers > 0,
    )

    output_root.mkdir(parents=True, exist_ok=False)
    shards_root = output_root / "shards"
    shards_root.mkdir()
    write_json(output_root / "image_inventory.json", inventory)
    if device.type == "cuda":
        torch.cuda.set_device(device)
        torch.cuda.reset_peak_memory_stats(device)

    started = time.perf_counter()
    pending_ids: list[str] = []
    pending_features: list[torch.Tensor] = []
    shards = []
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
                raise RuntimeError("Block-8 features contain non-finite values")
            if reproducibility is None:
                repeated = forward_to_block8(encoder, images)
                identical = torch.equal(features, repeated)
                maximum_difference = float(
                    (features - repeated).abs().max().item()
                )
                reproducibility = {
                    "repeated_batch_images": len(dicom_ids),
                    "identical": identical,
                    "maximum_absolute_difference": maximum_difference,
                }
                if not identical:
                    raise RuntimeError(
                        "Block-8 repeated-batch reproducibility failed: "
                        f"max diff={maximum_difference}"
                    )
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
    total_bytes = sum(item["bytes"] for item in shards)
    manifest = {
        "schema": "visualvit.r37.block8-cache-manifest.v1",
        "status": (
            "PASS_R37_BLOCK8_FORMAL_CACHE"
            if args.full
            else "PASS_R37_BLOCK8_SMOKE"
        ),
        "scope": (
            f"formal_part_{args.part_index}_of_{args.part_count}"
            if args.full
            else f"smoke_first_{len(inventory)}"
        ),
        "input_root": str(args.input_root),
        "output_root": str(output_root),
        "formal_inventory_count": formal_inventory_count,
        "cached_image_count": total,
        "inventory_slice": {
            "part_index": args.part_index,
            "part_count": args.part_count,
            "start_inclusive": part_start,
            "end_exclusive": part_end,
        },
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
        "cache_identifier": stable_hash(
            "r37-block8-cache-v1",
            *(item["dicom_id"] for item in inventory),
            WEIGHTS.stat().st_size,
            CONFIG.stat().st_size,
            BLOCK_COUNT,
            TOKEN_SHAPE,
            "float16",
        ),
        "shards": shards,
        "shard_count": len(shards),
        "total_bytes": total_bytes,
        "elapsed_seconds": elapsed,
        "images_per_second": total / elapsed,
        "device": str(device),
        "device_name": (
            torch.cuda.get_device_name(device) if device.type == "cuda" else "CPU"
        ),
        "peak_cuda_allocated_bytes": (
            torch.cuda.max_memory_allocated(device)
            if device.type == "cuda"
            else 0
        ),
        "lightweight_provenance": True,
        "source_hashes_recomputed": False,
        "per_shard_hashes_computed": False,
        "protected_outcomes_read": False,
    }
    write_json(output_root / "cache_manifest.json", manifest)
    print(json.dumps(manifest, indent=2, sort_keys=True))
    print(f"RESULT_DIR={output_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
