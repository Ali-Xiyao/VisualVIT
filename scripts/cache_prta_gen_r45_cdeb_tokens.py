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
from scripts.build_prta_gen_r45_cdeb_roster import (
    preflight as roster_preflight,
    validate_authority as validate_roster_authority,
)
from scripts.cache_prta_gen_r44a_tokens import (
    compact_get_many,
    image_inventory,
    prior_shuffle_assignment,
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


CONFIG_STATUS = "FROZEN_PRTA_GEN_R45_CDEB_DISCOVERY"


def validate_config_and_roster(
    config_path: Path,
    *,
    require_token_root_fresh: bool,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    config = read_json(config_path)
    if config.get("status") != CONFIG_STATUS:
        raise PermissionError("R45 discovery cache config is not frozen")
    authority = config["authority"]
    roster_config_path = WORKSPACE / authority["roster_config"]
    if (
        not roster_config_path.is_file()
        or roster_config_path.stat().st_size
        != int(authority["roster_config_bytes"])
        or sha256_file(roster_config_path)
        != authority["roster_config_sha256"]
    ):
        raise PermissionError("R45 roster-config authority drift")
    roster_config = read_json(roster_config_path)
    validate_roster_authority(roster_config)
    roster_path = Path(authority["roster"])
    if (
        not roster_path.is_file()
        or roster_path.stat().st_size != int(authority["roster_bytes"])
        or sha256_file(roster_path) != authority["roster_sha256"]
    ):
        raise PermissionError("R45 roster hash/size drift")
    roster = read_json(roster_path)
    if (
        roster.get("status") != authority["roster_status"]
        or roster.get("protocol_id") != config["protocol_id"]
        or roster.get("patient_sets_disjoint") is not True
        or roster.get("one_row_per_patient") is not True
        or roster.get("selected_images_complete") is not True
        or roster.get("excluded_r44a_patients_absent") is not True
        or roster.get("excluded_gold_patients_absent") is not True
        or roster.get("resplit_allowed") is not False
        or roster.get("qualification_outcomes_read") is not False
        or roster.get("confirmation_outcomes_read") is not False
        or roster.get("gold_outcomes_read") is not False
        or roster.get("external_outcomes_read") is not False
    ):
        raise PermissionError("R45 discovery roster receipt drift")
    partitions = [str(value) for value in config["cache"]["partitions"]]
    if partitions != ["train", "development"]:
        raise PermissionError("R45 discovery cache partition drift")
    rows = [
        row
        for partition in partitions
        for row in roster["partitions"][partition]["rows"]
    ]
    if (
        len(rows) != int(config["cache"]["expected_rows"])
        or len({str(row["patient_id"]) for row in rows}) != len(rows)
    ):
        raise ValueError("R45 discovery cache row/patient count drift")
    token_root = Path(config["runtime"]["token_root"])
    if require_token_root_fresh and token_root.exists():
        raise FileExistsError("R45 discovery token root must be fresh")
    return config, roster, rows


def preflight(config_path: Path) -> dict[str, Any]:
    config, _, rows = validate_config_and_roster(
        config_path, require_token_root_fresh=True
    )
    roster_config_path = WORKSPACE / config["authority"]["roster_config"]
    roster_receipt = roster_preflight(roster_config_path)
    cache = config["cache"]
    candidate_path = WORKSPACE / cache["source_candidate"]
    if (
        not candidate_path.is_file()
        or sha256_file(candidate_path)
        != cache["source_candidate_sha256"]
    ):
        raise PermissionError("R45 PRTA candidate authority drift")
    candidate = load_candidate(candidate_path)
    checkpoint = checkpoint_for(
        candidate,
        roster="a6",
        seed=int(cache["frozen_prta_seed"]),
    )
    if not checkpoint.is_file() or not Path(cache["text_cache"]).is_file():
        raise FileNotFoundError("R45 PRTA checkpoint/text cache is absent")
    return {
        "schema": "visualvit.prta-gen.r45-cdeb-cache-preflight.v1",
        "status": config["result_statuses"]["cache_preflight_pass"],
        "protocol_id": config["protocol_id"],
        "roster_preflight_status": roster_receipt["status"],
        "selected_discovery_rows_in_memory_only": len(rows),
        "cached_partitions": cache["partitions"],
        "source_candidate_sha256": cache["source_candidate_sha256"],
        "prta_checkpoint_present": True,
        "text_cache_present": True,
        "token_root_fresh": True,
        "gpu_cache_started": False,
        "qualification_tokens_materialized": False,
        "confirmation_tokens_materialized": False,
        "qualification_outcomes_read": False,
        "confirmation_outcomes_read": False,
        "gold_outcomes_read": False,
        "external_outcomes_read": False,
        "scientific_claim_allowed": False,
    }


def cache_tokens(
    *,
    config_path: Path,
    device_name: str,
) -> dict[str, Any]:
    config, _, rows = validate_config_and_roster(
        config_path, require_token_root_fresh=True
    )
    cache = config["cache"]
    inventory = image_inventory(rows)
    missing = [
        item["path"] for item in inventory if not Path(item["path"]).is_file()
    ]
    if missing:
        raise FileNotFoundError(
            f"R45 selected discovery images missing: {len(missing)}"
        )
    shuffle = prior_shuffle_assignment(
        rows,
        seed=int(cache["prior_shuffle_seed"]),
        namespace=str(cache["prior_shuffle_namespace"]),
    )
    device = torch.device(device_name)
    if device.type != "cuda" or not torch.cuda.is_available():
        raise RuntimeError("R45 exact64 cache requires explicit CUDA")
    torch.cuda.set_device(device)
    torch.cuda.reset_peak_memory_stats(device)
    token_root = Path(config["runtime"]["token_root"])
    token_root.mkdir(parents=True, exist_ok=False)
    shards_root = token_root / "shards"
    shards_root.mkdir()
    started = time.perf_counter()

    encoder = build_frozen_encoder(device)
    dataset = ImageDataset(inventory)
    loader = DataLoader(
        dataset,
        batch_size=int(cache["batch_size"]),
        shuffle=False,
        num_workers=int(cache["workers"]),
        pin_memory=True,
        persistent_workers=int(cache["workers"]) > 0,
    )
    compact: dict[str, torch.Tensor] = {}
    reproducibility: dict[str, Any] | None = None
    with torch.inference_mode():
        for image_ids, images in loader:
            images = images.to(device, non_blocking=True)
            features = forward_to_block8(encoder, images)
            if tuple(features.shape[1:]) != (197, 768):
                raise RuntimeError("R45 block-8 feature shape drift")
            if not bool(torch.isfinite(features).all()):
                raise FloatingPointError("R45 block-8 features are non-finite")
            if reproducibility is None:
                repeated = forward_to_block8(encoder, images)
                maximum = float((features - repeated).abs().max().item())
                reproducibility = {
                    "repeated_batch_images": len(image_ids),
                    "identical": torch.equal(features, repeated),
                    "maximum_absolute_difference": maximum,
                }
                if not reproducibility["identical"]:
                    raise RuntimeError("R45 block-8 reproducibility failed")
            for image, tensor in zip(
                image_ids, features.to(torch.float16).cpu(), strict=True
            ):
                compact[str(image)] = tensor
    if len(compact) != len(inventory):
        raise RuntimeError("R45 compact image cache is incomplete")
    del encoder, loader, dataset
    torch.cuda.empty_cache()

    candidate_path = WORKSPACE / cache["source_candidate"]
    if sha256_file(candidate_path) != cache["source_candidate_sha256"]:
        raise PermissionError("R45 source candidate hash drift")
    candidate = load_candidate(candidate_path)
    text_cache = torch.load(
        cache["text_cache"], map_location="cpu", weights_only=True
    )
    findings = [str(value) for value in text_cache["findings"]]
    finding_to_index = {
        finding: index for index, finding in enumerate(findings)
    }
    unknown = {str(row["finding"]) for row in rows} - set(findings)
    if unknown:
        raise ValueError(f"R45 unknown finding registry: {sorted(unknown)}")
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
            seed=int(cache["frozen_prta_seed"]),
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
            "schema": "visualvit.prta-gen.r45-cdeb-token-shard.v1",
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
        for start, end in batch_indices(len(rows), int(cache["batch_size"])):
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
                    raise RuntimeError("R45 exact64 token audit failed")
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
            if len(pending["example_ids"]) >= int(cache["shard_size"]):
                flush()
    flush()
    index = {
        "schema": "visualvit.prta-gen.r45-cdeb-token-cache.v1",
        "status": config["result_statuses"]["cache_pass"],
        "protocol_id": config["protocol_id"],
        "roster_sha256": config["authority"]["roster_sha256"],
        "rows": len(rows),
        "patients": len({str(row["patient_id"]) for row in rows}),
        "cached_partitions": cache["partitions"],
        "images": len(inventory),
        "shards": shards,
        "shard_count": len(shards),
        "token_shape": cache["token_shape"],
        "token_dtype": cache["token_dtype"],
        "cached_variants": cache["variants"],
        "labels_in_cache": False,
        "sentences_in_cache": False,
        "source_images_materialized_once": True,
        "reproducibility": reproducibility,
        "prior_shuffle": {
            "seed": int(cache["prior_shuffle_seed"]),
            "namespace": cache["prior_shuffle_namespace"],
            "same_finding_cross_patient": True,
        },
        "qualification_tokens_materialized": False,
        "confirmation_tokens_materialized": False,
        "qualification_outcomes_read": False,
        "confirmation_outcomes_read": False,
        "pixel_inputs_used_by_qwen": False,
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
        description="Preflight or cache frozen R45 discovery exact64 tokens"
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--device")
    parser.add_argument("--preflight-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.preflight_only:
        if args.device is not None:
            raise ValueError("R45 cache preflight accepts only --config")
        result = preflight(args.config)
    else:
        if args.device is None:
            raise ValueError("R45 cache execution requires --device")
        result = cache_tokens(
            config_path=args.config,
            device_name=args.device,
        )
    print(json.dumps(receipt_summary(result), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
