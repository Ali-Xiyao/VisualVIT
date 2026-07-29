from __future__ import annotations

# ruff: noqa: E402

import argparse
import json
from pathlib import Path
import sys

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE))
sys.path.insert(0, str(WORKSPACE / "src"))

import torch
import torch.nn.functional as F

from scripts.cache_r37_block8_tokens import build_frozen_encoder
from scripts.r37c_common import (
    canonical_registry_value,
    checkpoint_for,
    load_candidate,
    read_json,
)
from scripts.r38_common import DEFAULT_R38_CONFIG
from scripts.r39_common import (
    DEFAULT_R39_CONFIG,
    load_r39_config,
    prior_shuffle_assignment,
    write_json,
)
from scripts.run_r37_prta_smoke import TEXT_CACHE, batch_indices
from visualvit.prta import PRTATemporalAdapter, PRTATrainingHeads
from visualvit.r37_cache import Block8CacheIndex
from visualvit.r38_fixed64 import pack_fixed64


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Cache outcome-free R39 fixed-64 tokens"
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_R39_CONFIG)
    parser.add_argument("--scope", choices=("dev", "sealed"), required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--device", required=True)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--shard-size", type=int, default=128)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_r39_config(args.config)
    if args.seed not in config["training"]["seeds"]:
        raise ValueError("R39 token-cache seed drift")
    candidate = load_candidate(WORKSPACE / config["source_r37_candidate"])
    if args.scope == "dev":
        cache_root = Path(candidate["r37c_one_shot"]["structural_cache_root"])
        structure_path = cache_root / "dev_structure.json"
        expected_rows, expected_patients = 2453, 300
    else:
        cache_root = Path(config["sealed_test"]["block8_cache_root"])
        structure_path = cache_root / "sealed_structure.json"
        expected_rows, expected_patients = 4821, 483
    rows = read_json(structure_path)
    if (
        len(rows) != expected_rows
        or len({str(row["patient_id"]) for row in rows}) != expected_patients
    ):
        raise ValueError("R39 token-cache structural roster drift")
    text_cache = torch.load(TEXT_CACHE, map_location="cpu", weights_only=True)
    findings = [str(value) for value in text_cache["findings"]]
    finding_to_index = {value: index for index, value in enumerate(findings)}
    for row in rows:
        row["finding"] = canonical_registry_value(row["finding"], findings)
    shuffled_prior = prior_shuffle_assignment(
        rows, seed=int(config["final_gate"]["prior_shuffle_seed"])
    )
    output_root = (
        Path(config["runtime"][f"{args.scope}_token_cache"])
        / f"seed_{args.seed}"
    )
    if output_root.exists():
        raise FileExistsError(f"R39 token cache must be fresh: {output_root}")
    output_root.mkdir(parents=True, exist_ok=False)
    shards_root = output_root / "shards"
    shards_root.mkdir()

    device = torch.device(args.device)
    torch.cuda.set_device(device)
    cache = Block8CacheIndex(cache_root, maximum_loaded_shards=4)
    encoder = build_frozen_encoder(device)
    model = PRTATemporalAdapter(
        list(encoder.blocks[8:]),
        frozen_final_norm=encoder.norm,
        adapter_rank=int(candidate["frozen_model"]["adapter_rank"]),
    ).to(device)
    heads = PRTATrainingHeads().to(device)
    del encoder
    checkpoint = torch.load(
        checkpoint_for(candidate, roster="a6", seed=args.seed),
        map_location="cpu",
        weights_only=True,
    )
    model.load_state_dict(checkpoint["model"], strict=True)
    heads.load_state_dict(checkpoint["heads"], strict=True)
    model.eval()
    heads.eval()
    finding_text = text_cache["finding_embeddings"].to(device)
    shards = []
    pending: dict[str, list] = {
        "record_ids": [],
        "patient_ids": [],
        "findings": [],
        "true_tokens": [],
        "current_tokens": [],
        "a0_tokens": [],
        "shuffled_tokens": [],
    }

    def flush() -> None:
        nonlocal pending
        if not pending["record_ids"]:
            return
        path = shards_root / f"fixed64_{len(shards):04d}.pt"
        payload = {
            "schema": "visualvit.r39.fixed64-token-shard.v1",
            "record_ids": list(pending["record_ids"]),
            "patient_ids": list(pending["patient_ids"]),
            "findings": list(pending["findings"]),
            "true_tokens": torch.cat(pending["true_tokens"]),
            "current_tokens": torch.cat(pending["current_tokens"]),
            "a0_tokens": torch.cat(pending["a0_tokens"]),
            "shuffled_tokens": torch.cat(pending["shuffled_tokens"]),
        }
        torch.save(payload, path)
        shards.append(
            {
                "path": str(path),
                "rows": len(payload["record_ids"]),
                "bytes": path.stat().st_size,
            }
        )
        pending = {key: [] for key in pending}

    with torch.inference_mode():
        for start, end in batch_indices(len(rows), args.batch_size):
            batch = rows[start:end]
            prior = cache.get_many(
                item["prior_dicom_id"] for item in batch
            ).to(device=device, dtype=torch.float32)
            current = cache.get_many(
                item["current_dicom_id"] for item in batch
            ).to(device=device, dtype=torch.float32)
            shuffled = cache.get_many(
                shuffled_prior[str(item["record_id"])] for item in batch
            ).to(device=device, dtype=torch.float32)
            finding_index = torch.tensor(
                [finding_to_index[item["finding"]] for item in batch],
                dtype=torch.long,
                device=device,
            )
            query = heads.finding_query(finding_text[finding_index])
            true_output = model(prior, current, query)
            current_output = model(current, current, query)
            shuffled_output = model(shuffled, current, query)
            frozen_prior_cls = model.tail.forward_frozen(prior)[:, 0]
            frozen_current_cls = model.tail.forward_frozen(current)[:, 0]
            a0_delta = F.normalize(
                frozen_current_cls - frozen_prior_cls, dim=-1
            )
            true_bundle = pack_fixed64(
                finding_query=query,
                state_tokens=true_output.state_tokens,
                transition_tokens=true_output.transition_tokens,
                aligned_prior_tokens=true_output.aligned_prior_tokens,
            )
            current_bundle = pack_fixed64(
                finding_query=query,
                state_tokens=current_output.state_tokens,
                transition_tokens=current_output.transition_tokens,
                aligned_prior_tokens=current_output.aligned_prior_tokens,
            )
            shuffled_bundle = pack_fixed64(
                finding_query=query,
                state_tokens=shuffled_output.state_tokens,
                transition_tokens=shuffled_output.transition_tokens,
                aligned_prior_tokens=shuffled_output.aligned_prior_tokens,
            )
            a0_tokens = torch.cat(
                (
                    a0_delta[:, None, :].expand(-1, 60, -1),
                    torch.zeros(
                        len(batch),
                        4,
                        a0_delta.shape[-1],
                        device=device,
                        dtype=a0_delta.dtype,
                    ),
                ),
                dim=1,
            )
            pending["record_ids"].extend(str(item["record_id"]) for item in batch)
            pending["patient_ids"].extend(str(item["patient_id"]) for item in batch)
            pending["findings"].extend(str(item["finding"]) for item in batch)
            pending["true_tokens"].append(true_bundle.tokens.to(torch.float16).cpu())
            pending["current_tokens"].append(
                current_bundle.tokens.to(torch.float16).cpu()
            )
            pending["a0_tokens"].append(
                a0_tokens.to(torch.float16).cpu()
            )
            pending["shuffled_tokens"].append(
                shuffled_bundle.tokens.to(torch.float16).cpu()
            )
            if len(pending["record_ids"]) >= args.shard_size:
                flush()
    flush()
    index = {
        "schema": "visualvit.r39.fixed64-token-cache.v1",
        "status": "PASS_R39_FIXED64_TOKEN_CACHE",
        "scope": args.scope,
        "seed": args.seed,
        "rows": len(rows),
        "patients": len({str(row["patient_id"]) for row in rows}),
        "shards": shards,
        "shard_count": len(shards),
        "token_shape": [64, 768],
        "token_dtype": "torch.float16",
        "labels_in_cache": False,
        "probe_logits_in_cache": False,
        "cached_variants": [
            "a6_true_pair",
            "a6_current_only",
            "a0_frozen_difference",
            "a6_prior_shuffle",
        ],
        "a0_representation": (
            "frozen BiomedCLIP normalized current-minus-prior CLS repeated "
            "over 60 active positions plus four shared zero reserved positions"
        ),
        "prior_shuffle": {
            "seed": config["final_gate"]["prior_shuffle_seed"],
            "within_finding": True,
            "cross_patient": True,
            "outcome_used": False,
        },
        "sample_level_routing": False,
        "sealed_483_test_labels_read": False,
        "gold_outcomes_read": False,
        "source_hashes_recomputed": False,
        "per_shard_hashes_computed": False,
        "checkpoint_hashes_recomputed": False,
        "r38_config_reference": str(DEFAULT_R38_CONFIG),
    }
    write_json(output_root / "index.json", index)
    print(json.dumps(index, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
