from __future__ import annotations

# ruff: noqa: E402

import argparse
import importlib.util
import json
from pathlib import Path
import random
import sys
import time
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE))
sys.path.insert(0, str(WORKSPACE / "src"))

import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader

from scripts.cache_r37_block8_tokens import (
    ImageDataset,
    build_frozen_encoder,
    forward_to_block8,
)
from scripts.r50_common import validate_authority
from visualvit.prta import FrozenBiomedCLIPDifference
from visualvit.r50_method_baselines import siamese_signed_abs_features


DEFAULT_CONFIG = (
    WORKSPACE / "configs" / "prta_gen" / "prta_gen_r50_method_benchmark_v1.json"
)


def _device(name: str) -> torch.device:
    device = torch.device(name)
    if device.type != "cuda" or not torch.cuda.is_available():
        raise RuntimeError("R50 feature caching requires explicit CUDA")
    torch.cuda.set_device(device)
    torch.empty(1, device=device)
    torch.cuda.reset_peak_memory_stats(device)
    return device


def _all_rows(
    training_rows: list[dict[str, Any]],
    evaluation_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return training_rows + evaluation_rows


def _cache_payload(
    *,
    config: dict[str, Any],
    rows: list[dict[str, Any]],
    forward: torch.Tensor,
    reversed_: torch.Tensor,
    status: str,
    representation: str,
    elapsed_seconds: float,
    peak_cuda_allocated_bytes: int,
) -> dict[str, Any]:
    if forward.shape != reversed_.shape or forward.shape[0] != len(rows):
        raise RuntimeError("R50 feature-cache tensor shape drift")
    return {
        "schema": "visualvit.prta-gen.r50-feature-cache.v1",
        "status": status,
        "protocol_id": config["protocol_id"],
        "representation": representation,
        "example_ids": [str(row["example_id"]) for row in rows],
        "patient_ids": [str(row["patient_id"]) for row in rows],
        "findings": [str(row["finding"]) for row in rows],
        "forward_features": forward,
        "reversed_features": reversed_,
        "labels_in_cache": False,
        "protected_483_test_read": False,
        "gold_outcomes_read": False,
        "external_outcomes_read": False,
        "elapsed_seconds": elapsed_seconds,
        "peak_cuda_allocated_bytes": peak_cuda_allocated_bytes,
    }


def _load_official_tila_image_encoder(
    config: dict[str, Any], device: torch.device
) -> tuple[torch.nn.Module, Any]:
    spec = config["external_methods"]["tila"]
    model_root = Path(spec["local_model_root"])
    required = [
        model_root / "model.py",
        model_root / "processor.py",
        model_root / "preprocess.py",
        model_root / spec["weights_filename"],
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"R50 TILA model files missing: {missing}")
    if str(model_root) not in sys.path:
        sys.path.insert(0, str(model_root))

    model_spec = importlib.util.spec_from_file_location(
        "r50_official_tila_model", model_root / "model.py"
    )
    processor_spec = importlib.util.spec_from_file_location(
        "r50_official_tila_processor", model_root / "processor.py"
    )
    if (
        model_spec is None
        or model_spec.loader is None
        or processor_spec is None
        or processor_spec.loader is None
    ):
        raise ImportError("R50 could not load official TILA modules")
    model_module = importlib.util.module_from_spec(model_spec)
    sys.modules[model_spec.name] = model_module
    model_spec.loader.exec_module(model_module)
    processor_module = importlib.util.module_from_spec(processor_spec)
    sys.modules[processor_spec.name] = processor_module
    processor_spec.loader.exec_module(processor_module)

    encoder = model_module.TILAImageEncoder()
    from safetensors.torch import load_file

    state = load_file(str(model_root / spec["weights_filename"]), device="cpu")
    prefix = "image_encoder."
    image_state = {
        key[len(prefix) :]: value
        for key, value in state.items()
        if key.startswith(prefix)
    }
    if not image_state:
        raise RuntimeError("R50 TILA checkpoint lacks image_encoder weights")
    loaded = encoder.load_state_dict(image_state, strict=True)
    if loaded.missing_keys or loaded.unexpected_keys:
        raise RuntimeError("R50 TILA strict image-encoder load failed")
    encoder.eval().requires_grad_(False)
    encoder.to(device=device, dtype=torch.bfloat16)
    processor = processor_module.TILAProcessor(
        raw_preprocess=bool(spec["processor"]["raw_preprocess"]),
        max_size=int(spec["processor"]["max_size"]),
        crop_size=int(spec["processor"]["crop_size"]),
        dtype=torch.bfloat16,
        device="cpu",
    )
    return encoder, processor


def cache_tila(config_path: Path, device_name: str) -> dict[str, Any]:
    config, _, training_rows, evaluation_rows = validate_authority(config_path)
    rows = _all_rows(training_rows, evaluation_rows)
    output = Path(config["runtime"]["tila_cache"])
    if output.exists():
        raise FileExistsError(f"R50 TILA cache must be fresh: {output}")
    device = _device(device_name)
    encoder, processor = _load_official_tila_image_encoder(config, device)
    started = time.perf_counter()
    forward: list[torch.Tensor] = []
    reversed_: list[torch.Tensor] = []
    batch_size = int(config["cache"]["tila_batch_size"])
    with torch.inference_mode():
        for start in range(0, len(rows), batch_size):
            batch = rows[start : start + batch_size]
            prior = torch.cat(
                [processor(str(row["prior_path"])) for row in batch]
            ).to(device, non_blocking=True)
            current = torch.cat(
                [processor(str(row["current_path"])) for row in batch]
            ).to(device, non_blocking=True)
            forward_output = encoder(current, prior).projected_global_embedding
            reversed_output = encoder(prior, current).projected_global_embedding
            forward.append(F.normalize(forward_output.float(), dim=-1).half().cpu())
            reversed_.append(
                F.normalize(reversed_output.float(), dim=-1).half().cpu()
            )
    forward_tensor = torch.cat(forward)
    reversed_tensor = torch.cat(reversed_)
    expected = tuple(config["cache"]["tila_cache_shape"])
    observed = (len(rows), 2, int(forward_tensor.shape[-1]))
    if observed != expected or not torch.isfinite(forward_tensor).all():
        raise RuntimeError(f"R50 TILA cache shape/finite drift: {observed}")
    payload = _cache_payload(
        config=config,
        rows=rows,
        forward=forward_tensor,
        reversed_=reversed_tensor,
        status=config["result_statuses"]["tila_cache_pass"],
        representation="official_TILA_128d_pair_embedding",
        elapsed_seconds=time.perf_counter() - started,
        peak_cuda_allocated_bytes=torch.cuda.max_memory_allocated(device),
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    torch.save(payload, output)
    return payload


def cache_b2(config_path: Path, device_name: str) -> dict[str, Any]:
    config, _, training_rows, evaluation_rows = validate_authority(config_path)
    rows = _all_rows(training_rows, evaluation_rows)
    output = Path(config["runtime"]["b2_cache"])
    if output.exists():
        raise FileExistsError(f"R50 B2 cache must be fresh: {output}")
    device = _device(device_name)
    encoder = build_frozen_encoder(device)
    frozen = FrozenBiomedCLIPDifference(
        list(encoder.blocks[8:]), final_norm=encoder.norm
    ).to(device)
    started = time.perf_counter()
    images: dict[str, str] = {}
    for row in rows:
        for id_key, path_key in (
            ("prior_image_id", "prior_path"),
            ("current_image_id", "current_path"),
        ):
            image_id = str(row[id_key])
            path = str(row[path_key])
            previous = images.setdefault(image_id, path)
            if previous != path:
                raise PermissionError("R50 image ID maps to multiple paths")
    inventory = [
        {"dicom_id": image_id, "path": path}
        for image_id, path in sorted(images.items())
    ]
    loader = DataLoader(
        ImageDataset(inventory),
        batch_size=int(config["cache"]["b2_batch_size"]),
        shuffle=False,
        num_workers=int(config["cache"]["b2_workers"]),
        pin_memory=True,
        persistent_workers=int(config["cache"]["b2_workers"]) > 0,
    )
    compact: dict[str, torch.Tensor] = {}
    batch_size = int(config["cache"]["b2_batch_size"])
    with torch.inference_mode():
        for image_ids, image_tensor in loader:
            image_tensor = image_tensor.to(device, non_blocking=True)
            block8 = forward_to_block8(encoder, image_tensor)
            cls = frozen.encode(block8)[:, 0].half().cpu()
            for image_id, value in zip(image_ids, cls, strict=True):
                compact[str(image_id)] = value
    if len(compact) != len(inventory):
        raise RuntimeError("R50 B2 image encoding is incomplete")
    forward_values: list[torch.Tensor] = []
    reversed_values: list[torch.Tensor] = []
    for start in range(0, len(rows), batch_size):
        batch = rows[start : start + batch_size]
        prior_cls = torch.stack(
            [compact[str(row["prior_image_id"])] for row in batch]
        )
        current_cls = torch.stack(
            [compact[str(row["current_image_id"])] for row in batch]
        )
        forward_values.append(
            siamese_signed_abs_features(prior_cls, current_cls).half()
        )
        reversed_values.append(
            siamese_signed_abs_features(current_cls, prior_cls).half()
        )
    forward_tensor = torch.cat(forward_values)
    reversed_tensor = torch.cat(reversed_values)
    expected = tuple(config["cache"]["b2_cache_shape"])
    observed = (len(rows), 2, int(forward_tensor.shape[-1]))
    if observed != expected or not torch.isfinite(forward_tensor).all():
        raise RuntimeError(f"R50 B2 cache shape/finite drift: {observed}")
    payload = _cache_payload(
        config=config,
        rows=rows,
        forward=forward_tensor,
        reversed_=reversed_tensor,
        status=config["result_statuses"]["b2_cache_pass"],
        representation="BiomedCLIP_siamese_signed_abs_3072d",
        elapsed_seconds=time.perf_counter() - started,
        peak_cuda_allocated_bytes=torch.cuda.max_memory_allocated(device),
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    torch.save(payload, output)
    return payload


def preflight(config_path: Path) -> dict[str, Any]:
    config, _, training_rows, evaluation_rows = validate_authority(config_path)
    rows = _all_rows(training_rows, evaluation_rows)
    missing_images = [
        str(row[key])
        for row in rows
        for key in ("prior_path", "current_path")
        if not Path(row[key]).is_file()
    ]
    if missing_images:
        raise FileNotFoundError(f"R50 images missing: {len(missing_images)}")
    model = config["external_methods"]["tila"]
    weights = Path(model["local_model_root"]) / model["weights_filename"]
    from scripts.r50_common import verify_file

    verify_file(weights, model["weights_bytes"], model["weights_sha256"])
    runtime = Path(config["runtime"]["root"])
    if runtime.exists():
        raise FileExistsError(f"R50 runtime must be fresh: {runtime}")
    if torch.cuda.device_count() < 2:
        raise RuntimeError("R50 requires two visible CUDA devices")
    return {
        "schema": "visualvit.prta-gen.r50-preflight.v1",
        "status": config["result_statuses"]["preflight_pass"],
        "protocol_id": config["protocol_id"],
        "training_rows": len(training_rows),
        "evaluation_rows": len(evaluation_rows),
        "all_images_present": True,
        "tila_weights_verified": True,
        "runtime_fresh": True,
        "cuda_devices": torch.cuda.device_count(),
        "gpu_work_started": False,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Cache R50 method features")
    parser.add_argument(
        "command", choices=("preflight", "tila", "b2")
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--device", default="cuda:0")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    random.seed(0)
    torch.manual_seed(0)
    if args.command == "preflight":
        result = preflight(args.config)
    elif args.command == "tila":
        result = cache_tila(args.config, args.device)
    else:
        result = cache_b2(args.config, args.device)
    printable = {
        key: value
        for key, value in result.items()
        if not isinstance(value, torch.Tensor)
        and not isinstance(value, list)
    }
    print(json.dumps(printable, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
