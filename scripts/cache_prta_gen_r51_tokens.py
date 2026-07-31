from __future__ import annotations

# ruff: noqa: E402

import argparse
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
from torch.utils.data import DataLoader

from scripts.build_prta_gen_r40b_smoke_cohort import write_json
from scripts.cache_r37_block8_tokens import (
    ImageDataset,
    build_frozen_encoder,
    forward_to_block8,
)
import scripts.cache_prta_gen_r45_cdeb_tokens as r45_cache
from scripts.cache_prta_gen_r50_features import _load_official_tila_image_encoder
from scripts.r51_common import validate_authority
from visualvit.prta import FrozenBiomedCLIPDifference
from visualvit.r51_exact64 import (
    B2_PATCH_POSITIONS,
    TILA_PATCH_POSITIONS,
    b2_patch_tokens_to_exact64,
    tila_projected_patches_to_exact64,
)


DEFAULT_CONFIG = (
    WORKSPACE / "configs" / "prta_gen" / "prta_gen_r51_matched_interface_v1.json"
)


class Exact64ShardWriter:
    def __init__(
        self,
        root: Path,
        *,
        shard_size: int,
        schema: str,
    ) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=False)
        self.shards_root = root / "shards"
        self.shards_root.mkdir()
        self.shard_size = shard_size
        self.schema = schema
        self.pending: dict[str, list[Any]] = {
            "example_ids": [],
            "patient_ids": [],
            "findings": [],
            "exact64_tokens": [],
        }
        self.shards: list[dict[str, Any]] = []

    def add(self, rows: list[dict[str, Any]], tokens: torch.Tensor) -> None:
        if tuple(tokens.shape) != (len(rows), 64, 768):
            raise ValueError("R51 shard batch shape drift")
        self.pending["example_ids"].extend(str(row["example_id"]) for row in rows)
        self.pending["patient_ids"].extend(str(row["patient_id"]) for row in rows)
        self.pending["findings"].extend(str(row["finding"]) for row in rows)
        self.pending["exact64_tokens"].append(tokens.to(torch.float16).cpu())
        if len(self.pending["example_ids"]) >= self.shard_size:
            self.flush()

    def flush(self) -> None:
        if not self.pending["example_ids"]:
            return
        path = self.shards_root / f"exact64_{len(self.shards):04d}.pt"
        payload = {
            "schema": self.schema,
            "example_ids": list(self.pending["example_ids"]),
            "patient_ids": list(self.pending["patient_ids"]),
            "findings": list(self.pending["findings"]),
            "exact64_tokens": torch.cat(self.pending["exact64_tokens"]),
        }
        torch.save(payload, path)
        self.shards.append(
            {
                "path": str(path),
                "rows": len(payload["example_ids"]),
                "bytes": path.stat().st_size,
            }
        )
        self.pending = {key: [] for key in self.pending}


def _device(name: str) -> torch.device:
    device = torch.device(name)
    if device.type != "cuda" or not torch.cuda.is_available():
        raise RuntimeError("R51 token caching requires explicit CUDA")
    torch.cuda.set_device(device)
    torch.empty(1, device=device)
    torch.cuda.reset_peak_memory_stats(device)
    return device


def _all_rows(
    training_rows: list[dict[str, Any]], evaluation_rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    return training_rows + evaluation_rows


def _validate_tokens(tokens: torch.Tensor) -> None:
    if (
        tuple(tokens.shape[-2:]) != (64, 768)
        or not bool(torch.isfinite(tokens).all())
        or not bool(tokens[..., 60:64, :].eq(0).all())
    ):
        raise RuntimeError("R51 exact64 token audit failed")


def validate_prta_cache_config(
    config_path: Path, *, require_token_root_fresh: bool
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    config, _, evaluation_rows = validate_authority(
        config_path, require_pinned_caches=False
    )
    root = Path(config["runtime"]["prta_evaluation_token_root"])
    if require_token_root_fresh and root.exists():
        raise FileExistsError("R51 PRTA evaluation token root must be fresh")
    return config, {}, evaluation_rows


def cache_prta(config_path: Path, device_name: str) -> dict[str, Any]:
    original = r45_cache.validate_config_and_roster
    r45_cache.validate_config_and_roster = validate_prta_cache_config
    try:
        result = r45_cache.cache_tokens(
            config_path=config_path, device_name=device_name
        )
    finally:
        r45_cache.validate_config_and_roster = original
    result.update(
        {
            "schema": "visualvit.prta-gen.r51-prta-evaluation-token-cache.v1",
            "status": result["status"],
            "protocol_id": "prta-gen-r51-matched-interface-v1",
            "cached_partitions": ["evaluation"],
            "evaluation_model_outcomes_read": False,
            "protected_300_dev_read": False,
            "revealed_483_test_read": False,
        }
    )
    path = Path(result["shards"][0]["path"]).parents[1] / "index.json"
    write_json(path, result)
    return result


def _write_index(
    *,
    config: dict[str, Any],
    rows: list[dict[str, Any]],
    writer: Exact64ShardWriter,
    status: str,
    representation: str,
    started: float,
    device: torch.device,
) -> dict[str, Any]:
    writer.flush()
    index = {
        "schema": "visualvit.prta-gen.r51-exact64-token-cache.v1",
        "status": status,
        "protocol_id": config["protocol_id"],
        "representation": representation,
        "training_roster_sha256": config["authority"]["training_roster_sha256"],
        "evaluation_roster_sha256": config["authority"]["evaluation_roster_sha256"],
        "rows": len(rows),
        "patients": len({str(row["patient_id"]) for row in rows}),
        "cached_partitions": ["train", "evaluation"],
        "shards": writer.shards,
        "shard_count": len(writer.shards),
        "token_shape": [64, 768],
        "token_dtype": "torch.float16",
        "token_key": "exact64_tokens",
        "common_normalization": config["translation"]["common_normalization"],
        "reserved_positions_exact_zero": True,
        "labels_in_cache": False,
        "sentences_in_cache": False,
        "translation_trainable_parameters": 0,
        "evaluation_model_outcomes_read": False,
        "protected_300_dev_read": False,
        "revealed_483_test_read": False,
        "gold_outcomes_read": False,
        "external_outcomes_read": False,
        "peak_cuda_allocated_bytes": int(torch.cuda.max_memory_allocated(device)),
        "elapsed_seconds": time.perf_counter() - started,
    }
    write_json(writer.root / "index.json", index)
    return index


def cache_tila(config_path: Path, device_name: str) -> dict[str, Any]:
    config, training_rows, evaluation_rows = validate_authority(
        config_path, require_pinned_caches=False
    )
    rows = _all_rows(training_rows, evaluation_rows)
    root = Path(config["runtime"]["tila_token_root"])
    if root.exists():
        raise FileExistsError("R51 TILA token root must be fresh")
    device = _device(device_name)
    encoder, processor = _load_official_tila_image_encoder(config, device)
    writer = Exact64ShardWriter(
        root,
        shard_size=int(config["cache"]["shard_size"]),
        schema="visualvit.prta-gen.r51-tila-exact64-token-shard.v1",
    )
    started = time.perf_counter()
    batch_size = int(config["cache"]["tila_batch_size"])
    with torch.inference_mode():
        for start in range(0, len(rows), batch_size):
            batch = rows[start : start + batch_size]
            prior = torch.cat([processor(str(row["prior_path"])) for row in batch]).to(
                device, non_blocking=True
            )
            current = torch.cat(
                [processor(str(row["current_path"])) for row in batch]
            ).to(device, non_blocking=True)
            projected = encoder(current, prior).projected_patch_embeddings
            tokens = tila_projected_patches_to_exact64(projected)
            _validate_tokens(tokens)
            writer.add(batch, tokens)
    index = _write_index(
        config=config,
        rows=rows,
        writer=writer,
        status=config["result_statuses"]["tila_cache_pass"],
        representation="official_TILA_temporal_projected_patches_exact64_adaptation",
        started=started,
        device=device,
    )
    index["patch_positions"] = list(TILA_PATCH_POSITIONS)
    index["width_expansion"] = config["translation"]["tila_width_expansion"]
    write_json(root / "index.json", index)
    return index


def cache_b2(config_path: Path, device_name: str) -> dict[str, Any]:
    config, training_rows, evaluation_rows = validate_authority(
        config_path, require_pinned_caches=False
    )
    rows = _all_rows(training_rows, evaluation_rows)
    root = Path(config["runtime"]["b2_token_root"])
    if root.exists():
        raise FileExistsError("R51 B2 token root must be fresh")
    device = _device(device_name)
    encoder = build_frozen_encoder(device)
    frozen = FrozenBiomedCLIPDifference(
        list(encoder.blocks[8:]), final_norm=encoder.norm
    ).to(device)
    prior_inventory = [
        {"dicom_id": str(row["example_id"]), "path": str(row["prior_path"])}
        for row in rows
    ]
    current_inventory = [
        {"dicom_id": str(row["example_id"]), "path": str(row["current_path"])}
        for row in rows
    ]
    loader_kwargs = {
        "batch_size": int(config["cache"]["b2_batch_size"]),
        "shuffle": False,
        "num_workers": int(config["cache"]["b2_workers"]),
        "pin_memory": True,
        "persistent_workers": int(config["cache"]["b2_workers"]) > 0,
    }
    prior_loader = DataLoader(ImageDataset(prior_inventory), **loader_kwargs)
    current_loader = DataLoader(ImageDataset(current_inventory), **loader_kwargs)
    writer = Exact64ShardWriter(
        root,
        shard_size=int(config["cache"]["shard_size"]),
        schema="visualvit.prta-gen.r51-b2-exact64-token-shard.v1",
    )
    started = time.perf_counter()
    offset = 0
    with torch.inference_mode():
        for (prior_ids, prior_images), (current_ids, current_images) in zip(
            prior_loader, current_loader, strict=True
        ):
            if list(prior_ids) != list(current_ids):
                raise PermissionError("R51 B2 pair loader order drift")
            count = len(prior_ids)
            images = torch.cat((prior_images, current_images)).to(
                device, non_blocking=True
            )
            block8 = forward_to_block8(encoder, images)
            encoded = frozen.encode(block8)
            prior_tokens, current_tokens = encoded[:count], encoded[count:]
            tokens = b2_patch_tokens_to_exact64(prior_tokens, current_tokens)
            _validate_tokens(tokens)
            writer.add(rows[offset : offset + count], tokens)
            offset += count
    if offset != len(rows):
        raise RuntimeError("R51 B2 cache row count drift")
    index = _write_index(
        config=config,
        rows=rows,
        writer=writer,
        status=config["result_statuses"]["b2_cache_pass"],
        representation="BiomedCLIP_patchwise_prior_current_signed_absolute_exact64",
        started=started,
        device=device,
    )
    index["patch_positions"] = list(B2_PATCH_POSITIONS)
    index["component_order"] = config["translation"]["b2_component_order"]
    write_json(root / "index.json", index)
    return index


def preflight(config_path: Path) -> dict[str, Any]:
    config, training_rows, evaluation_rows = validate_authority(
        config_path, require_pinned_caches=False
    )
    rows = _all_rows(training_rows, evaluation_rows)
    missing = [
        str(row[key])
        for row in rows
        for key in ("prior_path", "current_path")
        if not Path(row[key]).is_file()
    ]
    if missing:
        raise FileNotFoundError(f"R51 selected images missing: {len(missing)}")
    roots = [
        Path(config["runtime"]["prta_evaluation_token_root"]),
        Path(config["runtime"]["tila_token_root"]),
        Path(config["runtime"]["b2_token_root"]),
    ]
    existing = [str(path) for path in roots if path.exists()]
    if existing:
        raise FileExistsError(f"R51 token roots are not fresh: {existing}")
    if torch.cuda.device_count() < 2:
        raise RuntimeError("R51 requires two CUDA devices")
    return {
        "schema": "visualvit.prta-gen.r51-precache-preflight.v1",
        "status": config["result_statuses"]["preflight_pass"],
        "protocol_id": config["protocol_id"],
        "training_rows": len(training_rows),
        "evaluation_rows": len(evaluation_rows),
        "images_verified": len(rows) * 2,
        "all_token_roots_fresh": True,
        "translation_trainable_parameters": 0,
        "cuda_devices": torch.cuda.device_count(),
        "qwen_loaded": False,
        "gpu_cache_started": False,
        "evaluation_model_outcomes_read": False,
        "protected_300_dev_read": False,
        "revealed_483_test_read": False,
        "gold_outcomes_read": False,
        "external_outcomes_read": False,
    }


def receipt_summary(result: dict[str, Any]) -> dict[str, Any]:
    summary = dict(result)
    if "shards" in summary:
        summary["shards"] = {
            "count": len(result["shards"]),
            "rows": sum(int(value["rows"]) for value in result["shards"]),
        }
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Cache frozen R51 exact64 tokens")
    parser.add_argument("command", choices=("preflight", "prta", "tila", "b2"))
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--device", default="cuda:0")
    args = parser.parse_args()
    random.seed(0)
    torch.manual_seed(0)
    if args.command == "preflight":
        result = preflight(args.config)
    elif args.command == "prta":
        result = cache_prta(args.config, str(args.device))
    elif args.command == "tila":
        result = cache_tila(args.config, str(args.device))
    else:
        result = cache_b2(args.config, str(args.device))
    print(json.dumps(receipt_summary(result), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
