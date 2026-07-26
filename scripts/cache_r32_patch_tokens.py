from __future__ import annotations

# ruff: noqa: E402

import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE / "src"))

import torch
from PIL import Image
import timm
from torch.utils.data import DataLoader, Dataset
from torchvision import transforms


COHORT_ROOT = Path(
    r"F:\VisualVIT_runtime\050_routeC\r32_tier_cxr_vlm\cohort_v1"
)
TRAIN_DEV_COHORT = COHORT_ROOT / "train_dev_cohort.json"
MODEL_ROOT = Path(r"H:\Xiyao_Wang\001_models\biomedclip")
WEIGHTS = MODEL_ROOT / "open_clip_pytorch_model.bin"
CONFIG = MODEL_ROOT / "open_clip_config.json"
OUTPUT_ROOT_DEFAULT = Path(
    r"F:\VisualVIT_runtime\050_routeC\r32_tier_cxr_vlm"
    r"\patch_cache_train_dev_v1"
)
CLIP_MEAN = (0.48145466, 0.4578275, 0.40821073)
CLIP_STD = (0.26862954, 0.26130258, 0.27577711)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def image_inventory(records: list[dict[str, Any]]) -> list[dict[str, str]]:
    result: dict[str, str] = {}
    for row in records:
        if row["partition"] not in {"train", "dev"}:
            raise ValueError("patch cache input must contain train/dev only")
        for id_field, path_field in (
            ("prior_dicom_id", "prior_path"),
            ("current_dicom_id", "current_path"),
        ):
            dicom_id = str(row[id_field])
            path = str(row[path_field])
            previous = result.setdefault(dicom_id, path)
            if previous != path:
                raise ValueError(f"dicom ID {dicom_id} maps to two paths")
    return [
        {"dicom_id": dicom_id, "path": result[dicom_id]}
        for dicom_id in sorted(result)
    ]


def visual_state_dict(checkpoint: dict[str, torch.Tensor]) -> dict[str, torch.Tensor]:
    prefix = "visual.trunk."
    state = {
        key[len(prefix) :]: value
        for key, value in checkpoint.items()
        if key.startswith(prefix)
    }
    if len(state) != 150:
        raise RuntimeError(f"expected 150 BiomedCLIP visual keys, got {len(state)}")
    return state


def build_frozen_encoder(device: torch.device) -> torch.nn.Module:
    checkpoint = torch.load(WEIGHTS, map_location="cpu", weights_only=True)
    state = visual_state_dict(checkpoint)
    model = timm.create_model(
        "vit_base_patch16_224", pretrained=False, num_classes=0
    )
    loaded = model.load_state_dict(state, strict=True)
    if loaded.missing_keys or loaded.unexpected_keys:
        raise RuntimeError(
            f"strict encoder load mismatch: {loaded.missing_keys}, "
            f"{loaded.unexpected_keys}"
        )
    model.eval().requires_grad_(False).to(device)
    return model


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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Cache frozen BiomedCLIP train/dev final-layer patch tokens"
    )
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT_DEFAULT)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--shard-size", type=int, default=256)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--max-images", type=int)
    return parser.parse_args()


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True), encoding="utf-8"
    )


def main() -> int:
    args = parse_args()
    if args.output_root.exists():
        raise FileExistsError(f"output root must be fresh: {args.output_root}")
    if args.batch_size <= 0 or args.shard_size <= 0:
        raise ValueError("batch/shard sizes must be positive")
    device = torch.device(args.device)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but unavailable")
    records = json.loads(TRAIN_DEV_COHORT.read_text(encoding="utf-8"))
    inventory = image_inventory(records)
    if args.max_images is not None:
        inventory = inventory[: args.max_images]
    missing = [item["path"] for item in inventory if not Path(item["path"]).is_file()]
    if missing:
        raise FileNotFoundError(f"missing cache images: {len(missing)}")

    args.output_root.mkdir(parents=True, exist_ok=False)
    shards_root = args.output_root / "shards"
    shards_root.mkdir()
    _write_json(args.output_root / "image_inventory.json", inventory)
    encoder = build_frozen_encoder(device)
    frozen = all(not parameter.requires_grad for parameter in encoder.parameters())
    if not frozen or encoder.training:
        raise RuntimeError("BiomedCLIP encoder freeze audit failed")

    dataset = ImageDataset(inventory)
    loader = DataLoader(
        dataset,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=args.workers,
        pin_memory=device.type == "cuda",
        persistent_workers=args.workers > 0,
    )
    if device.type == "cuda":
        torch.cuda.set_device(device)
        torch.cuda.reset_peak_memory_stats(device)
    started = time.perf_counter()
    pending_ids: list[str] = []
    pending_features: list[torch.Tensor] = []
    shard_records = []
    total = 0

    def flush() -> None:
        nonlocal pending_ids, pending_features
        if not pending_ids:
            return
        features = torch.cat(pending_features, dim=0)
        shard_index = len(shard_records)
        path = shards_root / f"patch_tokens_{shard_index:04d}.pt"
        torch.save(
            {
                "schema": "visualvit.r32.biomedclip-patches.v1",
                "dicom_ids": list(pending_ids),
                "features": features,
                "shape": list(features.shape),
                "dtype": str(features.dtype),
            },
            path,
        )
        shard_records.append(
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
            features = encoder.forward_features(images)
            if tuple(features.shape[1:]) != (197, 768):
                raise RuntimeError(
                    f"unexpected BiomedCLIP feature shape: "
                    f"{tuple(features.shape)}"
                )
            if not bool(torch.isfinite(features).all()):
                raise RuntimeError("BiomedCLIP features contain non-finite values")
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
    total_bytes = sum(item["bytes"] for item in shard_records)
    manifest = {
        "schema": "visualvit.r32.patch-cache-manifest.v1",
        "status": "PASS_R32_PATCH_CACHE",
        "scope": "train_dev_only",
        "sealed_test_images_read": False,
        "image_count": total,
        "feature_shape_per_image": [197, 768],
        "feature_dtype": "torch.float16",
        "encoder": {
            "name": "BiomedCLIP ViT-B/16 visual trunk",
            "weights_path": str(WEIGHTS),
            "weights_bytes": WEIGHTS.stat().st_size,
            "config_path": str(CONFIG),
            "config_sha256": sha256_file(CONFIG),
            "strict_visual_key_count": 150,
            "all_frozen": frozen,
        },
        "cache_identifier": canonical_sha256(
            {
                "dicom_ids": [item["dicom_id"] for item in inventory],
                "encoder_weights_bytes": WEIGHTS.stat().st_size,
                "config_sha256": sha256_file(CONFIG),
                "shape": [197, 768],
                "dtype": "float16",
            }
        ),
        "shards": shard_records,
        "shard_count": len(shard_records),
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
        "per_shard_hashes_computed": False,
    }
    _write_json(args.output_root / "cache_manifest.json", manifest)
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
