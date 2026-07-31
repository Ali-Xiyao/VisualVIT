from __future__ import annotations

# ruff: noqa: E402

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import sys
import time
from typing import Any, Iterable

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE))
sys.path.insert(0, str(WORKSPACE / "src"))

import torch
from torch.utils.data import DataLoader

from scripts.audit_prta_gen_r44_independent_support import sha256_file
from scripts.build_prta_gen_r40b_smoke_cohort import read_json, write_json
from scripts.build_prta_gen_r44a_roster import (
    CONFIG_STATUS,
    ROSTER_STATUS,
    preflight as roster_preflight,
    validate_authority,
)
from scripts.cache_r37_block8_tokens import (
    ImageDataset,
    build_frozen_encoder,
    forward_to_block8,
)
from scripts.r37c_common import checkpoint_for, load_candidate
from scripts.run_r37_prta_smoke import batch_indices
from visualvit.prta import PRTATemporalAdapter, PRTATrainingHeads
from visualvit.r38_fixed64 import pack_fixed64


CACHE_STATUS = "PASS_PRTA_GEN_R44A_EXACT64_TOKEN_CACHE"


def stable_order(namespace: str, seed: int, value: str) -> str:
    return hashlib.sha256(
        f"{namespace}|{seed}|{value}".encode()
    ).hexdigest()


def roster_rows(roster: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [
        row
        for partition in ("train", "development")
        for row in roster["partitions"][partition]["rows"]
    ]
    if len(rows) != sum(
        int(roster["partitions"][partition]["row_count"])
        for partition in ("train", "development")
    ):
        raise ValueError("R44A roster row-count drift")
    return rows


def image_inventory(rows: Iterable[dict[str, Any]]) -> list[dict[str, str]]:
    images: dict[str, str] = {}
    for row in rows:
        for id_key, path_key in (
            ("prior_image_id", "prior_path"),
            ("current_image_id", "current_path"),
        ):
            image = str(row[id_key])
            path = str(row[path_key])
            previous = images.setdefault(image, path)
            if previous != path:
                raise ValueError("R44A image ID maps to multiple paths")
    return [
        {"dicom_id": image, "path": images[image]}
        for image in sorted(images)
    ]


def prior_shuffle_assignment(
    rows: Iterable[dict[str, Any]],
    *,
    seed: int,
    namespace: str,
) -> dict[str, str]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["finding"])].append(row)
    assignment: dict[str, str] = {}
    for finding_rows in grouped.values():
        ordered = sorted(
            finding_rows,
            key=lambda row: (
                stable_order(
                    namespace, seed, str(row["example_id"])
                ),
                str(row["example_id"]),
            ),
        )
        if len({str(row["patient_id"]) for row in ordered}) < 2:
            raise ValueError(
                "R44A prior shuffle requires two patients per finding"
            )
        for index, row in enumerate(ordered):
            for offset in range(1, len(ordered) + 1):
                candidate = ordered[(index + offset) % len(ordered)]
                if str(candidate["patient_id"]) != str(row["patient_id"]):
                    assignment[str(row["example_id"])] = str(
                        candidate["prior_image_id"]
                    )
                    break
            else:
                raise RuntimeError("R44A prior-shuffle assignment failed")
    if len(assignment) != sum(len(values) for values in grouped.values()):
        raise RuntimeError("R44A prior-shuffle assignment is incomplete")
    return assignment


def validate_roster(
    config: dict[str, Any],
    roster: dict[str, Any],
    *,
    roster_path: Path,
    roster_sha256: str,
) -> list[dict[str, Any]]:
    if (
        roster.get("status") != ROSTER_STATUS
        or roster.get("protocol_id") != config["protocol_id"]
        or roster.get("patient_sets_disjoint") is not True
        or roster.get("one_row_per_patient") is not True
        or roster.get("selected_images_complete") is not True
        or roster.get("excluded_observed_patients_absent") is not True
        or roster.get("resplit_allowed") is not False
        or roster.get("development_outcomes_read") is not False
        or roster.get("r41a_development_reused") is not False
        or roster.get("r41a_outcomes_used_for_roster_selection") is not False
        or roster.get("protected_300_dev_read") is not False
        or roster.get("revealed_483_test_read") is not False
        or roster.get("gold_outcomes_read") is not False
        or roster.get("external_outcomes_read") is not False
    ):
        raise PermissionError("R44A token-cache roster drift")
    if sha256_file(roster_path) != roster_sha256.upper():
        raise PermissionError("R44A roster hash drift")
    rows = roster_rows(roster)
    expected = int(config["roster"]["train_patients"]) + int(
        config["roster"]["development_patients"]
    )
    if len(rows) != expected:
        raise ValueError("R44A token-cache roster size drift")
    return rows


def compact_get_many(
    compact: dict[str, torch.Tensor], image_ids: Iterable[str]
) -> torch.Tensor:
    values = [str(value) for value in image_ids]
    missing = [value for value in values if value not in compact]
    if missing:
        raise KeyError(f"R44A compact image cache misses {len(missing)} rows")
    return torch.stack([compact[value] for value in values])


def preflight(config_path: Path) -> dict[str, Any]:
    config = read_json(config_path)
    if config.get("status") != CONFIG_STATUS:
        raise PermissionError("R44A cache config is not frozen")
    validate_authority(config)
    roster_receipt = roster_preflight(config_path)
    cache = config["cache"]
    candidate_path = WORKSPACE / cache["source_candidate"]
    if (
        not candidate_path.is_file()
        or sha256_file(candidate_path)
        != cache["source_candidate_sha256"]
    ):
        raise PermissionError("R44A PRTA candidate authority drift")
    candidate = load_candidate(candidate_path)
    checkpoint = checkpoint_for(
        candidate,
        roster="a6",
        seed=int(cache["frozen_prta_seed"]),
    )
    text_cache = Path(cache["text_cache"])
    if not checkpoint.is_file() or not text_cache.is_file():
        raise FileNotFoundError("R44A PRTA checkpoint/text cache is absent")
    token_root = Path(config["runtime"]["token_root"])
    if token_root.exists():
        raise FileExistsError("R44A token-cache output must be fresh")
    return {
        "schema": "visualvit.prta-gen.r44a-token-cache-preflight.v1",
        "status": "PASS_PRTA_GEN_R44A_TOKEN_CACHE_PREFLIGHT",
        "protocol_id": config["protocol_id"],
        "roster_preflight_status": roster_receipt["status"],
        "selected_rows_in_memory_only": sum(
            roster_receipt["selected_counts_in_memory_only"].values()
        ),
        "source_candidate_sha256": cache["source_candidate_sha256"],
        "prta_checkpoint_present": True,
        "text_cache_present": True,
        "token_root_fresh": True,
        "roster_written": False,
        "gpu_cache_started": False,
        "protected_300_dev_read": False,
        "revealed_483_test_read": False,
        "gold_outcomes_read": False,
        "external_outcomes_read": False,
        "scientific_claim_allowed": False,
    }


def cache_tokens(
    *,
    config_path: Path,
    roster_path: Path,
    roster_sha256: str,
    device_name: str,
) -> dict[str, Any]:
    config = read_json(config_path)
    if config.get("status") != CONFIG_STATUS:
        raise PermissionError("R44A cache config is not frozen")
    validate_authority(config)
    roster = read_json(roster_path)
    rows = validate_roster(
        config,
        roster,
        roster_path=roster_path,
        roster_sha256=roster_sha256,
    )
    cache_config = config["cache"]
    token_root = Path(config["runtime"]["token_root"])
    if token_root.exists():
        raise FileExistsError(f"R44A token root must be fresh: {token_root}")
    inventory = image_inventory(rows)
    missing = [
        item["path"] for item in inventory if not Path(item["path"]).is_file()
    ]
    if missing:
        raise FileNotFoundError(
            f"R44A selected images missing at cache time: {len(missing)}"
        )
    shuffle = prior_shuffle_assignment(
        rows,
        seed=int(cache_config["prior_shuffle_seed"]),
        namespace=str(cache_config["prior_shuffle_namespace"]),
    )
    device = torch.device(device_name)
    if device.type != "cuda" or not torch.cuda.is_available():
        raise RuntimeError("R44A exact64 cache requires explicit CUDA")
    torch.cuda.set_device(device)
    torch.cuda.reset_peak_memory_stats(device)
    token_root.mkdir(parents=True, exist_ok=False)
    shards_root = token_root / "shards"
    shards_root.mkdir()
    started = time.perf_counter()

    encoder = build_frozen_encoder(device)
    dataset = ImageDataset(inventory)
    loader = DataLoader(
        dataset,
        batch_size=int(cache_config["batch_size"]),
        shuffle=False,
        num_workers=int(cache_config["workers"]),
        pin_memory=True,
        persistent_workers=int(cache_config["workers"]) > 0,
    )
    compact: dict[str, torch.Tensor] = {}
    reproducibility: dict[str, Any] | None = None
    with torch.inference_mode():
        for image_ids, images in loader:
            images = images.to(device, non_blocking=True)
            features = forward_to_block8(encoder, images)
            if tuple(features.shape[1:]) != (197, 768):
                raise RuntimeError("R44A block-8 feature shape drift")
            if not bool(torch.isfinite(features).all()):
                raise FloatingPointError("R44A block-8 features are non-finite")
            if reproducibility is None:
                repeated = forward_to_block8(encoder, images)
                maximum = float((features - repeated).abs().max().item())
                reproducibility = {
                    "repeated_batch_images": len(image_ids),
                    "identical": torch.equal(features, repeated),
                    "maximum_absolute_difference": maximum,
                }
                if not reproducibility["identical"]:
                    raise RuntimeError("R44A block-8 reproducibility failed")
            for image, tensor in zip(
                image_ids, features.to(torch.float16).cpu(), strict=True
            ):
                compact[str(image)] = tensor
    if len(compact) != len(inventory):
        raise RuntimeError("R44A compact image cache is incomplete")
    del encoder, loader, dataset
    torch.cuda.empty_cache()

    candidate_path = WORKSPACE / cache_config["source_candidate"]
    if sha256_file(candidate_path) != cache_config["source_candidate_sha256"]:
        raise PermissionError("R44A source candidate hash drift")
    candidate = load_candidate(candidate_path)
    text_cache = torch.load(
        cache_config["text_cache"],
        map_location="cpu",
        weights_only=True,
    )
    findings = [str(value) for value in text_cache["findings"]]
    finding_to_index = {
        finding: index for index, finding in enumerate(findings)
    }
    unknown = {str(row["finding"]) for row in rows} - set(findings)
    if unknown:
        raise ValueError(f"R44A unknown finding registry: {sorted(unknown)}")
    encoder_tail = build_frozen_encoder(device)
    model = PRTATemporalAdapter(
        list(encoder_tail.blocks[8:]),
        frozen_final_norm=encoder_tail.norm,
        adapter_rank=int(candidate["frozen_model"]["adapter_rank"]),
    ).to(device)
    heads = PRTATrainingHeads().to(device)
    checkpoint = torch.load(
        checkpoint_for(
            candidate,
            roster="a6",
            seed=int(cache_config["frozen_prta_seed"]),
        ),
        map_location="cpu",
        weights_only=True,
    )
    model.load_state_dict(checkpoint["model"], strict=True)
    heads.load_state_dict(checkpoint["heads"], strict=True)
    model.eval()
    heads.eval()
    finding_text = text_cache["finding_embeddings"].to(device)
    del encoder_tail

    shard_size = int(cache_config["shard_size"])
    pending: dict[str, list[Any]] = {
        "example_ids": [],
        "patient_ids": [],
        "findings": [],
        "true_tokens": [],
        "current_tokens": [],
        "shuffled_tokens": [],
    }
    shards: list[dict[str, Any]] = []

    def flush() -> None:
        nonlocal pending
        if not pending["example_ids"]:
            return
        path = shards_root / f"fixed64_{len(shards):04d}.pt"
        payload = {
            "schema": "visualvit.prta-gen.r44a-token-shard.v1",
            "example_ids": list(pending["example_ids"]),
            "patient_ids": list(pending["patient_ids"]),
            "findings": list(pending["findings"]),
            "true_tokens": torch.cat(pending["true_tokens"]),
            "current_tokens": torch.cat(pending["current_tokens"]),
            "shuffled_tokens": torch.cat(pending["shuffled_tokens"]),
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

    with torch.inference_mode():
        for start, end in batch_indices(
            len(rows), int(cache_config["batch_size"])
        ):
            batch = rows[start:end]
            prior = compact_get_many(
                compact, (row["prior_image_id"] for row in batch)
            ).to(device=device, dtype=torch.float32)
            current = compact_get_many(
                compact, (row["current_image_id"] for row in batch)
            ).to(device=device, dtype=torch.float32)
            shuffled_prior = compact_get_many(
                compact,
                (shuffle[str(row["example_id"])] for row in batch),
            ).to(device=device, dtype=torch.float32)
            finding_index = torch.tensor(
                [finding_to_index[str(row["finding"])] for row in batch],
                dtype=torch.long,
                device=device,
            )
            query = heads.finding_query(finding_text[finding_index])
            outputs = (
                model(prior, current, query),
                model(current, current, query),
                model(shuffled_prior, current, query),
            )
            bundles = [
                pack_fixed64(
                    finding_query=query,
                    state_tokens=output.state_tokens,
                    transition_tokens=output.transition_tokens,
                    aligned_prior_tokens=output.aligned_prior_tokens,
                )
                for output in outputs
            ]
            for bundle in bundles:
                if (
                    tuple(bundle.tokens.shape[1:]) != (64, 768)
                    or not bool(bundle.tokens[:, 60:64].eq(0).all())
                    or not bool(bundle.physical_attention.all())
                ):
                    raise RuntimeError("R44A exact64 token audit failed")
            pending["example_ids"].extend(
                str(row["example_id"]) for row in batch
            )
            pending["patient_ids"].extend(
                str(row["patient_id"]) for row in batch
            )
            pending["findings"].extend(str(row["finding"]) for row in batch)
            pending["true_tokens"].append(
                bundles[0].tokens.to(torch.float16).cpu()
            )
            pending["current_tokens"].append(
                bundles[1].tokens.to(torch.float16).cpu()
            )
            pending["shuffled_tokens"].append(
                bundles[2].tokens.to(torch.float16).cpu()
            )
            if len(pending["example_ids"]) >= shard_size:
                flush()
    flush()
    index = {
        "schema": "visualvit.prta-gen.r44a-token-cache.v1",
        "status": config["result_statuses"]["cache_pass"],
        "protocol_id": config["protocol_id"],
        "roster_sha256": roster_sha256.upper(),
        "rows": len(rows),
        "patients": len({str(row["patient_id"]) for row in rows}),
        "images": len(inventory),
        "shards": shards,
        "shard_count": len(shards),
        "token_shape": cache_config["token_shape"],
        "token_dtype": cache_config["token_dtype"],
        "cached_variants": cache_config["variants"],
        "labels_in_cache": False,
        "sentences_in_cache": False,
        "source_images_materialized_once": True,
        "reproducibility": reproducibility,
        "prior_shuffle": {
            "seed": int(cache_config["prior_shuffle_seed"]),
            "namespace": cache_config["prior_shuffle_namespace"],
            "same_finding_cross_patient": True,
        },
        "pixel_inputs_used_by_qwen": False,
        "protected_300_dev_read": False,
        "revealed_483_test_read": False,
        "gold_outcomes_read": False,
        "external_outcomes_read": False,
        "scientific_claim_allowed": False,
        "peak_cuda_allocated_bytes": torch.cuda.max_memory_allocated(device),
        "elapsed_seconds": time.perf_counter() - started,
    }
    write_json(token_root / "index.json", index)
    return index


def receipt_summary(result: dict[str, Any]) -> dict[str, Any]:
    summary = dict(result)
    if "shards" in summary:
        summary["shards"] = {
            "count": len(result["shards"]),
            "rows": sum(int(value["rows"]) for value in result["shards"]),
            "bytes": sum(int(value["bytes"]) for value in result["shards"]),
        }
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Preflight or cache frozen R44A CheXpert exact64 tokens"
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--roster", type=Path)
    parser.add_argument("--roster-sha256")
    parser.add_argument("--device")
    parser.add_argument("--preflight-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.preflight_only:
        if any(
            value is not None
            for value in (
                args.roster,
                args.roster_sha256,
                args.device,
            )
        ):
            raise ValueError("R44A cache preflight accepts only --config")
        result = preflight(args.config)
    else:
        if (
            args.roster is None
            or args.roster_sha256 is None
            or args.device is None
        ):
            raise ValueError(
                "R44A cache requires roster, roster SHA-256, and device"
            )
        result = cache_tokens(
            config_path=args.config,
            roster_path=args.roster,
            roster_sha256=args.roster_sha256,
            device_name=args.device,
        )
    print(json.dumps(receipt_summary(result), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
