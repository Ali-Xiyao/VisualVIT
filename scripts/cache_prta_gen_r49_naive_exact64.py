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

from scripts.audit_prta_gen_r44_independent_support import sha256_file
from scripts.build_prta_gen_r40b_smoke_cohort import read_json, write_json
from scripts.cache_r37_block8_tokens import (
    ImageDataset,
    build_frozen_encoder,
    forward_to_block8,
)


CONFIG_STATUS = "FROZEN_PRTA_GEN_R49_UNIFIED_THREE_WAY"


def _verify(path: Path, expected_bytes: int, expected_sha256: str) -> None:
    if (
        not path.is_file()
        or path.stat().st_size != expected_bytes
        or sha256_file(path) != expected_sha256
    ):
        raise PermissionError(f"R49 authority drift: {path}")


def validate_authority(
    config_path: Path, *, require_fresh: bool
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    config = read_json(config_path)
    if config.get("status") != CONFIG_STATUS:
        raise PermissionError("R49 config is not frozen")
    authority = config["authority"]
    for prefix in ("r40_component_config", "r45_training_config"):
        _verify(
            WORKSPACE / authority[prefix],
            int(authority[f"{prefix}_bytes"]),
            str(authority[f"{prefix}_sha256"]),
        )
    roster_path = Path(authority["roster"])
    _verify(
        roster_path,
        int(authority["roster_bytes"]),
        str(authority["roster_sha256"]),
    )
    roster = read_json(roster_path)
    if (
        roster.get("status") != authority["roster_status"]
        or roster.get("one_row_per_patient") is not True
        or roster.get("patient_sets_disjoint") is not True
        or roster.get("selected_images_complete") is not True
        or authority.get("resplit_allowed") is not False
    ):
        raise PermissionError("R49 roster contract drift")
    partitions = list(config["naive_exact64"]["cache_partitions"])
    rows = [
        row
        for partition in partitions
        for row in roster["partitions"][partition]["rows"]
    ]
    if (
        len(rows) != int(config["naive_exact64"]["cache_rows"])
        or len({str(row["patient_id"]) for row in rows}) != len(rows)
    ):
        raise ValueError("R49 naive cache roster drift")
    patch_positions = [
        int(value) for value in config["naive_exact64"]["patch_positions"]
    ]
    expected_positions = [1 + round(index * 195 / 29) for index in range(30)]
    if (
        patch_positions != expected_positions
        or len(set(patch_positions)) != 30
        or min(patch_positions) < 1
        or max(patch_positions) > 196
    ):
        raise PermissionError("R49 naive patch-selection drift")
    token_root = Path(config["runtime"]["naive_token_root"])
    if require_fresh and token_root.exists():
        raise FileExistsError("R49 naive token root must be fresh")
    return config, rows


def _inventory(rows: list[dict[str, Any]]) -> list[dict[str, str]]:
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
                raise ValueError("R49 image identifier maps to two paths")
    return [
        {"dicom_id": image_id, "path": images[image_id]}
        for image_id in sorted(images)
    ]


def preflight(config_path: Path) -> dict[str, Any]:
    config, rows = validate_authority(config_path, require_fresh=True)
    inventory = _inventory(rows)
    missing = sum(not Path(item["path"]).is_file() for item in inventory)
    if missing:
        raise FileNotFoundError(f"R49 selected images missing: {missing}")
    return {
        "schema": "visualvit.prta-gen.r49-naive-cache-preflight.v1",
        "status": config["result_statuses"]["cache_preflight_pass"],
        "protocol_id": config["protocol_id"],
        "rows": len(rows),
        "patients": len({str(row["patient_id"]) for row in rows}),
        "images": len(inventory),
        "patch_positions": config["naive_exact64"]["patch_positions"],
        "token_layout": config["naive_exact64"]["layout"],
        "all_images_present": True,
        "token_root_fresh": True,
        "gpu_cache_started": False,
    }


def cache_tokens(config_path: Path, device_name: str) -> dict[str, Any]:
    config, rows = validate_authority(config_path, require_fresh=True)
    spec = config["naive_exact64"]
    inventory = _inventory(rows)
    missing = [item["path"] for item in inventory if not Path(item["path"]).is_file()]
    if missing:
        raise FileNotFoundError(f"R49 selected images missing: {len(missing)}")
    device = torch.device(device_name)
    if device.type != "cuda" or not torch.cuda.is_available():
        raise RuntimeError("R49 naive cache requires explicit CUDA")
    torch.cuda.set_device(device)
    torch.cuda.reset_peak_memory_stats(device)
    root = Path(config["runtime"]["naive_token_root"])
    root.mkdir(parents=True, exist_ok=False)
    shards_root = root / "shards"
    shards_root.mkdir()
    started = time.perf_counter()

    encoder = build_frozen_encoder(device)
    loader = DataLoader(
        ImageDataset(inventory),
        batch_size=int(spec["batch_size"]),
        shuffle=False,
        num_workers=int(spec["workers"]),
        pin_memory=True,
        persistent_workers=int(spec["workers"]) > 0,
    )
    compact: dict[str, torch.Tensor] = {}
    reproducibility: dict[str, Any] | None = None
    with torch.inference_mode():
        for image_ids, images in loader:
            images = images.to(device, non_blocking=True)
            features = forward_to_block8(encoder, images)
            if tuple(features.shape[1:]) != (197, 768):
                raise RuntimeError("R49 Block-8 feature shape drift")
            if reproducibility is None:
                repeated = forward_to_block8(encoder, images)
                reproducibility = {
                    "images": len(image_ids),
                    "identical": torch.equal(features, repeated),
                    "maximum_absolute_difference": float(
                        (features - repeated).abs().max().item()
                    ),
                }
                if reproducibility["identical"] is not True:
                    raise RuntimeError("R49 Block-8 reproducibility failed")
            for image_id, tensor in zip(
                image_ids, features.to(torch.float16).cpu(), strict=True
            ):
                compact[str(image_id)] = tensor
    if len(compact) != len(inventory):
        raise RuntimeError("R49 compact feature cache incomplete")
    del encoder, loader
    torch.cuda.empty_cache()

    positions = torch.tensor(spec["patch_positions"], dtype=torch.long)
    pending: dict[str, list[Any]] = {
        "example_ids": [],
        "patient_ids": [],
        "findings": [],
        "naive_tokens": [],
    }
    shards: list[dict[str, Any]] = []

    def flush() -> None:
        nonlocal pending
        if not pending["example_ids"]:
            return
        path = shards_root / f"fixed64_{len(shards):04d}.pt"
        payload = {
            "schema": "visualvit.prta-gen.r49-naive-token-shard.v1",
            "example_ids": list(pending["example_ids"]),
            "patient_ids": list(pending["patient_ids"]),
            "findings": list(pending["findings"]),
            "naive_tokens": torch.cat(pending["naive_tokens"]),
        }
        torch.save(payload, path)
        shards.append(
            {
                "path": str(path),
                "rows": len(payload["example_ids"]),
                "bytes": path.stat().st_size,
            }
        )
        pending = {key: [] for key in pending}

    zeros = torch.zeros((4, 768), dtype=torch.float16)
    for row in rows:
        prior = compact[str(row["prior_image_id"])].index_select(0, positions)
        current = compact[str(row["current_image_id"])].index_select(0, positions)
        tokens = torch.cat((prior, current, zeros), dim=0)
        if tuple(tokens.shape) != (64, 768) or not bool(tokens[60:64].eq(0).all()):
            raise RuntimeError("R49 naive exact64 layout audit failed")
        pending["example_ids"].append(str(row["example_id"]))
        pending["patient_ids"].append(str(row["patient_id"]))
        pending["findings"].append(str(row["finding"]))
        pending["naive_tokens"].append(tokens.unsqueeze(0))
        if len(pending["example_ids"]) >= int(spec["shard_size"]):
            flush()
    flush()
    del compact
    index = {
        "schema": "visualvit.prta-gen.r49-naive-token-cache.v1",
        "status": config["result_statuses"]["cache_pass"],
        "protocol_id": config["protocol_id"],
        "roster_sha256": config["authority"]["roster_sha256"],
        "rows": len(rows),
        "patients": len({str(row["patient_id"]) for row in rows}),
        "cached_partitions": spec["cache_partitions"],
        "images": len(inventory),
        "shards": shards,
        "shard_count": len(shards),
        "token_shape": spec["token_shape"],
        "token_dtype": spec["token_dtype"],
        "token_key": spec["token_key"],
        "patch_positions": spec["patch_positions"],
        "layout": spec["layout"],
        "reserved_positions_exact_zero": True,
        "labels_in_cache": False,
        "sentences_in_cache": False,
        "reproducibility": reproducibility,
        "peak_cuda_allocated_bytes": int(torch.cuda.max_memory_allocated(device)),
        "elapsed_seconds": time.perf_counter() - started,
        "gold_outcomes_read": False,
        "external_outcomes_read": False,
    }
    write_json(root / "index.json", index)
    return index


def receipt_summary(result: dict[str, Any]) -> dict[str, Any]:
    summary = dict(result)
    if isinstance(summary.get("shards"), list):
        summary["shards"] = {"count": len(summary["shards"])}
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Cache R49 naive exact-64 tokens")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--device")
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    if args.preflight_only:
        result = preflight(args.config)
    else:
        if args.device is None:
            raise ValueError("R49 cache requires --device")
        result = cache_tokens(args.config, str(args.device))
    print(json.dumps(receipt_summary(result), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
