from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE / "src"))

import torch
from PIL import Image
import timm
from torchvision import transforms

EVIDENCE_CLASS = "NON_CONFIRMATORY_PROXY"
CLIP_MEAN = (0.48145466, 0.4578275, 0.40821073)
CLIP_STD = (0.26862954, 0.26130258, 0.27577711)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--weights",
        type=Path,
        default=Path(
            r"H:\Xiyao_Wang\021_260129VIVID\pretrained\biomedclip_vit_base.pt"
        ),
    )
    parser.add_argument(
        "--images",
        type=Path,
        nargs="+",
        default=[
            Path(
                r"H:\Xiyao_Wang\000_Public Dataset\CheXpert-v1.0-small\train"
                r"\patient00002\study1\view1_frontal.jpg"
            ),
            Path(
                r"H:\Xiyao_Wang\000_Public Dataset\CheXpert-v1.0-small\train"
                r"\patient00002\study2\view1_frontal.jpg"
            ),
        ],
    )
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path(r"F:\VisualVIT_runtime\050_routeC\runs"),
    )
    parser.add_argument("--run-id", default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    device = torch.device(args.device)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but unavailable")
    if not args.weights.is_file():
        raise FileNotFoundError(args.weights)
    for image_path in args.images:
        if not image_path.is_file():
            raise FileNotFoundError(image_path)

    run_id = args.run_id or (
        "encoder_smoke_" + datetime.now().strftime("%Y%m%dT%H%M%S")
    )
    run_dir = args.output_root / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    weight_hash = sha256_file(args.weights)
    checkpoint = torch.load(args.weights, map_location="cpu", weights_only=True)
    state = checkpoint.get("model", checkpoint)
    model = timm.create_model(
        "vit_base_patch16_224", pretrained=False, num_classes=0
    )
    load_result = model.load_state_dict(state, strict=True)
    if load_result.missing_keys or load_result.unexpected_keys:
        raise RuntimeError(
            f"strict load mismatch: {load_result.missing_keys}, "
            f"{load_result.unexpected_keys}"
        )
    model.eval().to(device)

    preprocessing = transforms.Compose(
        [
            transforms.Resize((224, 224), antialias=True),
            transforms.ToTensor(),
            transforms.Normalize(CLIP_MEAN, CLIP_STD),
        ]
    )
    image_tensors = [
        preprocessing(Image.open(path).convert("RGB")) for path in args.images
    ]
    batch = torch.stack(image_tensors).to(device)

    if device.type == "cuda":
        torch.cuda.reset_peak_memory_stats(device)
        torch.cuda.synchronize(device)
    start = time.perf_counter()
    with torch.inference_mode():
        features_1 = model.forward_features(batch)
        features_2 = model.forward_features(batch)
    if device.type == "cuda":
        torch.cuda.synchronize(device)
    runtime = time.perf_counter() - start
    max_abs_diff = float((features_1 - features_2).abs().max().cpu())
    finite = bool(torch.isfinite(features_1).all())
    expected_shape = [len(args.images), 197, 768]
    actual_shape = list(features_1.shape)
    peak_vram = (
        int(torch.cuda.max_memory_allocated(device)) if device.type == "cuda" else 0
    )

    feature_path = run_dir / "features.pt"
    torch.save(
        {
            "evidence_class": EVIDENCE_CLASS,
            "features": features_1.detach().cpu(),
            "patch_features": features_1[:, 1:].detach().cpu(),
            "image_paths": [str(path) for path in args.images],
        },
        feature_path,
    )
    checks = {
        "strict_weight_load": True,
        "expected_shape": actual_shape == expected_shape,
        "finite": finite,
        "repeat_max_abs_diff_le_1e-6": max_abs_diff <= 1e-6,
        "h_drive_output_forbidden": not str(run_dir).lower().startswith("h:"),
    }
    summary: dict[str, Any] = {
        "evidence_class": EVIDENCE_CLASS,
        "formal_claim_allowed": False,
        "run_id": run_id,
        "status": "PASS" if all(checks.values()) else "FAIL",
        "model": "timm_vit_base_patch16_224_with_vivid_biomedclip_proxy_weights",
        "weights": {
            "path": str(args.weights),
            "sha256": weight_hash,
            "bytes": args.weights.stat().st_size,
            "state_keys": len(state),
            "strict_coverage": 1.0,
        },
        "images": [
            {
                "path": str(path),
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
            }
            for path in args.images
        ],
        "preprocessing": {
            "resize": [224, 224],
            "normalization_mean": CLIP_MEAN,
            "normalization_std": CLIP_STD,
        },
        "feature_shape": actual_shape,
        "patch_feature_shape": list(features_1[:, 1:].shape),
        "finite": finite,
        "repeat_max_abs_diff": max_abs_diff,
        "runtime_seconds_two_passes": runtime,
        "peak_vram_bytes": peak_vram,
        "device": str(device),
        "device_name": (
            torch.cuda.get_device_name(device) if device.type == "cuda" else "CPU"
        ),
        "checks": checks,
        "artifacts": {
            feature_path.name: {
                "sha256": sha256_file(feature_path),
                "bytes": feature_path.stat().st_size,
            }
        },
    }
    summary_path = run_dir / "summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps(summary, sort_keys=True))
    print(f"RESULT_DIR={run_dir}")
    return 0 if summary["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())

