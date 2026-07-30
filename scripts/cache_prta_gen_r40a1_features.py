from __future__ import annotations

# ruff: noqa: E402

import argparse
import json
from pathlib import Path
import sys
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE))
sys.path.insert(0, str(WORKSPACE / "src"))

import torch
from torch import Tensor

from scripts.build_prta_gen_r40a1_roster import CONFIG_STATUS, ROSTER_PASS
from scripts.cache_prta_gen_r40a_tokens import read_json
from visualvit.prta_gen import (
    exact64_regional_cosine_features,
    exact64_regional_moment_features,
)


FEATURE_STATUS = "PASS_PRTA_GEN_R40A1_FEATURE_CACHE"
TOKEN_KEYS = {
    "true_pair": "true_tokens",
    "current_only": "current_tokens",
    "prior_shuffle": "shuffled_tokens",
}


def candidate_spec(
    config: dict[str, Any], candidate_name: str
) -> dict[str, Any]:
    matches = [
        item
        for item in config["candidate_order"]
        if item["name"] == candidate_name
    ]
    if len(matches) != 1:
        raise ValueError("unregistered or duplicate R40A.1 candidate")
    return matches[0]


def candidate_features(tokens: Tensor, *, candidate_name: str) -> Tensor:
    if candidate_name == "regional_moments_v1":
        return exact64_regional_moment_features(tokens)
    if candidate_name == "regional_cosine4_v1":
        return exact64_regional_cosine_features(tokens, components=4)
    raise ValueError("unregistered R40A.1 candidate feature function")


def build_feature_cache(
    *,
    config_path: Path,
    roster_path: Path,
    candidate_name: str,
    output_root: Path,
    device_name: str,
) -> dict[str, Any]:
    config = read_json(config_path)
    if config.get("status") != CONFIG_STATUS:
        raise PermissionError("R40A.1 config is not frozen")
    roster = read_json(roster_path)
    if (
        roster.get("status") != ROSTER_PASS
        or roster.get("discovery_outcomes_read") is not False
        or roster.get("qualification_outcomes_read") is not False
        or roster.get("revealed_483_test_read") is not False
        or roster.get("gold_outcomes_read") is not False
    ):
        raise PermissionError("R40A.1 roster firewall drift")
    spec = candidate_spec(config, candidate_name)
    source_index = read_json(Path(config["source"]["token_index"]))
    if (
        source_index.get("status") != "PASS_PRTA_GEN_R40A_TOKEN_CACHE"
        or source_index.get("scope") != "training"
        or source_index.get("labels_in_cache") is not False
        or source_index.get("sentences_in_cache") is not False
        or source_index.get("revealed_483_test_read") is not False
        or source_index.get("gold_outcomes_read") is not False
    ):
        raise PermissionError("R40A.1 source token-cache firewall drift")
    if output_root.exists():
        raise FileExistsError(
            f"R40A.1 feature cache must be fresh: {output_root}"
        )
    device = torch.device(device_name)
    if device.type == "cuda":
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA requested but unavailable")
        torch.cuda.set_device(device)
    shard_root = output_root / "shards"
    shard_root.mkdir(parents=True)
    output_shards = []
    total_rows = 0
    for shard_index, source_entry in enumerate(source_index["shards"]):
        source = torch.load(
            source_entry["path"], map_location="cpu", weights_only=True
        )
        payload: dict[str, Any] = {
            "schema": "visualvit.prta-gen.r40a1-feature-shard.v1",
            "candidate": candidate_name,
            "example_ids": [str(value) for value in source["example_ids"]],
            "patient_ids": [str(value) for value in source["patient_ids"]],
            "findings": [str(value) for value in source["findings"]],
        }
        for variant, token_key in TOKEN_KEYS.items():
            tokens = source[token_key].to(device=device, dtype=torch.float32)
            payload[f"{variant}_features"] = candidate_features(
                tokens, candidate_name=candidate_name
            ).to(device="cpu", dtype=torch.float16)
            del tokens
        rows = len(payload["example_ids"])
        expected_width = int(spec["input_width"])
        for variant in TOKEN_KEYS:
            if tuple(payload[f"{variant}_features"].shape) != (
                rows,
                expected_width,
            ):
                raise ValueError("R40A.1 candidate feature-width drift")
        path = shard_root / f"features_{shard_index:04d}.pt"
        torch.save(payload, path)
        output_shards.append(
            {"path": str(path), "rows": rows, "bytes": path.stat().st_size}
        )
        total_rows += rows
    if (
        total_rows != int(config["source"]["expected_rows"])
        or total_rows != int(source_index["rows"])
    ):
        raise ValueError("R40A.1 feature-cache row-count drift")
    index = {
        "schema": "visualvit.prta-gen.r40a1-feature-cache.v1",
        "status": FEATURE_STATUS,
        "protocol_id": config["protocol_id"],
        "candidate": candidate_name,
        "input_width": int(spec["input_width"]),
        "rows": total_rows,
        "patients": int(source_index["patients"]),
        "shard_count": len(output_shards),
        "shards": output_shards,
        "variants": list(TOKEN_KEYS),
        "dtype": "torch.float16",
        "labels_in_cache": False,
        "sentences_in_cache": False,
        "discovery_outcomes_read": False,
        "qualification_outcomes_read": False,
        "protected_300_dev_read": False,
        "revealed_483_test_read": False,
        "gold_outcomes_read": False,
        "old_r40a_development_used_for_selection": False,
        "source_hashes_recomputed": False,
        "per_shard_hashes_recomputed": False,
        "checkpoint_hashes_recomputed": False,
        "scientific_claim_allowed": False,
    }
    index_path = output_root / "index.json"
    index_path.write_text(
        json.dumps(index, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return index


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Cache one frozen PRTA-Gen R40A.1 candidate"
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--roster", type=Path, required=True)
    parser.add_argument(
        "--candidate",
        choices=("regional_moments_v1", "regional_cosine4_v1"),
        required=True,
    )
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--device", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = build_feature_cache(
        config_path=args.config,
        roster_path=args.roster,
        candidate_name=args.candidate,
        output_root=args.output_root,
        device_name=args.device,
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "candidate": result["candidate"],
                "rows": result["rows"],
                "shards": result["shard_count"],
                "input_width": result["input_width"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
