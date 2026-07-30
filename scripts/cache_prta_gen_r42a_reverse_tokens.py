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

from scripts.build_prta_gen_r40b_smoke_cohort import (
    read_json,
    read_targets,
    write_json,
)
from scripts.build_prta_gen_r41a_roster import ROSTER_STATUS
from scripts.cache_prta_gen_r40a_tokens import (
    compact_get_many,
    materialize_required_features,
)
from scripts.cache_r37_block8_tokens import build_frozen_encoder
from scripts.r37c_common import checkpoint_for, load_candidate
from scripts.run_r37_prta_smoke import batch_indices
from visualvit.prta import PRTATemporalAdapter, PRTATrainingHeads
from visualvit.r37_cache import Block8CacheIndex
from visualvit.r38_fixed64 import pack_fixed64


CONFIG_STATUS = "FROZEN_PRTA_GEN_R42A_GROUNDING_REVERSAL"
REVERSE_CACHE_STATUS = "PASS_PRTA_GEN_R42A_REVERSE_TOKEN_CACHE"


def _selected_source_rows(
    config: dict[str, Any], roster: dict[str, Any]
) -> list[dict[str, Any]]:
    selected = {
        str(row["example_id"]): row
        for partition in ("train", "development")
        for row in roster["partitions"][partition]["rows"]
    }
    source = {
        str(row["example_id"]): row
        for row in read_targets(Path(config["source"]["targets"]))
        if str(row["example_id"]) in selected
    }
    if set(source) != set(selected):
        raise ValueError("R42A reverse cache source rows are incomplete")
    rows = []
    for partition in ("train", "development"):
        for roster_row in roster["partitions"][partition]["rows"]:
            row = source[str(roster_row["example_id"])]
            if (
                str(row["patient_id"]) != str(roster_row["patient_id"])
                or str(row["finding"]) != str(roster_row["finding"])
                or str(row["progression"]) != str(roster_row["progression"])
            ):
                raise ValueError("R42A reverse cache roster/source drift")
            rows.append(row)
    return rows


def preflight(config_path: Path) -> dict[str, Any]:
    config = read_json(config_path)
    if config.get("status") != CONFIG_STATUS:
        raise PermissionError("R42A config is not frozen")
    roster = read_json(Path(config["source"]["roster"]))
    if (
        roster.get("status") != ROSTER_STATUS
        or roster.get("patient_sets_disjoint") is not True
        or roster.get("protected_300_dev_read") is not False
        or roster.get("revealed_483_test_read") is not False
        or roster.get("gold_outcomes_read") is not False
        or roster.get("external_outcomes_read") is not False
    ):
        raise PermissionError("R42A reverse cache roster drift")
    rows = _selected_source_rows(config, roster)
    expected_rows = int(config["reverse_cache"]["expected_rows"])
    expected_patients = int(config["reverse_cache"]["expected_patients"])
    if (
        len(rows) != expected_rows
        or len({str(row["patient_id"]) for row in rows}) != expected_patients
    ):
        raise ValueError("R42A reverse cache row/patient count drift")
    r40a_config = read_json(WORKSPACE / config["source"]["r40a_cache_config"])
    cache = Block8CacheIndex(Path(r40a_config["block8_cache_root"]))
    required = {
        str(row[key])
        for row in rows
        for key in ("prior_dicom_id", "current_dicom_id")
    }
    missing = sum(value not in cache.locations for value in required)
    if missing:
        raise FileNotFoundError(
            f"R42A reverse cache misses {missing} Block-8 DICOM features"
        )
    output_root = Path(config["runtime"]["reverse_tokens"])
    if output_root.exists():
        raise FileExistsError(
            f"R42A reverse token output must be fresh: {output_root}"
        )
    return {
        "schema": "visualvit.prta-gen.r42a-reverse-cache-preflight.v1",
        "status": "PASS_PRTA_GEN_R42A_REVERSE_CACHE_PREFLIGHT",
        "protocol_id": config["protocol_id"],
        "rows": len(rows),
        "patients": len({str(row["patient_id"]) for row in rows}),
        "required_dicom_features": len(required),
        "missing_dicom_features": missing,
        "reverse_definition": config["source"]["reverse_definition"],
        "heuristic_token_permutation_used": False,
        "gpu_caching_started": False,
        "protected_300_dev_read": False,
        "revealed_483_test_read": False,
        "gold_outcomes_read": False,
        "external_outcomes_read": False,
    }


def cache_reverse_tokens(
    *,
    config_path: Path,
    device_name: str,
) -> dict[str, Any]:
    preflight(config_path)
    config = read_json(config_path)
    roster = read_json(Path(config["source"]["roster"]))
    rows = _selected_source_rows(config, roster)
    r40a_config = read_json(WORKSPACE / config["source"]["r40a_cache_config"])
    output_root = Path(config["runtime"]["reverse_tokens"])
    output_root.mkdir(parents=True, exist_ok=False)
    shards_root = output_root / "shards"
    shards_root.mkdir()
    cache = Block8CacheIndex(Path(r40a_config["block8_cache_root"]))
    required = {
        str(row[key])
        for row in rows
        for key in ("prior_dicom_id", "current_dicom_id")
    }
    compact = materialize_required_features(cache, required)
    device = torch.device(device_name)
    if device.type != "cuda" or not torch.cuda.is_available():
        raise RuntimeError("R42A reverse token caching requires CUDA")
    torch.cuda.set_device(device)
    candidate = load_candidate(WORKSPACE / r40a_config["source_candidate"])
    encoder = build_frozen_encoder(device)
    model = PRTATemporalAdapter(
        list(encoder.blocks[8:]),
        frozen_final_norm=encoder.norm,
        adapter_rank=int(candidate["frozen_model"]["adapter_rank"]),
    ).to(device)
    heads = PRTATrainingHeads().to(device)
    del encoder
    checkpoint = torch.load(
        checkpoint_for(
            candidate,
            roster="a6",
            seed=int(r40a_config["frozen_prta_seed"]),
        ),
        map_location="cpu",
        weights_only=True,
    )
    model.load_state_dict(checkpoint["model"], strict=True)
    heads.load_state_dict(checkpoint["heads"], strict=True)
    model.eval()
    heads.eval()
    text_cache = torch.load(
        r40a_config["text_cache"], map_location="cpu", weights_only=True
    )
    findings = [str(value) for value in text_cache["findings"]]
    finding_to_index = {
        finding: index for index, finding in enumerate(findings)
    }
    finding_text = text_cache["finding_embeddings"].to(device)
    shard_size = int(config["reverse_cache"]["shard_size"])
    batch_size = int(config["reverse_cache"]["batch_size"])
    shards = []
    pending: dict[str, list[Any]] = {
        "example_ids": [],
        "patient_ids": [],
        "findings": [],
        "reversed_tokens": [],
    }

    def flush() -> None:
        nonlocal pending
        if not pending["example_ids"]:
            return
        path = shards_root / f"fixed64_reverse_{len(shards):04d}.pt"
        payload = {
            "schema": "visualvit.prta-gen.r42a-reverse-token-shard.v1",
            "example_ids": list(pending["example_ids"]),
            "patient_ids": list(pending["patient_ids"]),
            "findings": list(pending["findings"]),
            "reversed_tokens": torch.cat(pending["reversed_tokens"]),
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
        for start, end in batch_indices(len(rows), batch_size):
            batch = rows[start:end]
            original_current = compact_get_many(
                compact, (row["current_dicom_id"] for row in batch)
            ).to(device=device, dtype=torch.float32)
            original_prior = compact_get_many(
                compact, (row["prior_dicom_id"] for row in batch)
            ).to(device=device, dtype=torch.float32)
            finding_index = torch.tensor(
                [finding_to_index[str(row["finding"])] for row in batch],
                dtype=torch.long,
                device=device,
            )
            query = heads.finding_query(finding_text[finding_index])
            output = model(original_current, original_prior, query)
            bundle = pack_fixed64(
                finding_query=query,
                state_tokens=output.state_tokens,
                transition_tokens=output.transition_tokens,
                aligned_prior_tokens=output.aligned_prior_tokens,
            )
            if (
                tuple(bundle.tokens.shape[1:]) != (64, 768)
                or not bool(bundle.tokens[:, 60:64].eq(0).all())
                or not bool(bundle.physical_attention.all())
            ):
                raise RuntimeError("R42A reversed exact64 token audit failed")
            pending["example_ids"].extend(
                str(row["example_id"]) for row in batch
            )
            pending["patient_ids"].extend(
                str(row["patient_id"]) for row in batch
            )
            pending["findings"].extend(str(row["finding"]) for row in batch)
            pending["reversed_tokens"].append(
                bundle.tokens.to(torch.float16).cpu()
            )
            if len(pending["example_ids"]) >= shard_size:
                flush()
    flush()
    index = {
        "schema": "visualvit.prta-gen.r42a-reverse-token-cache.v1",
        "status": config["result_statuses"]["reverse_cache_pass"],
        "protocol_id": config["protocol_id"],
        "rows": len(rows),
        "patients": len({str(row["patient_id"]) for row in rows}),
        "shards": shards,
        "shard_count": len(shards),
        "token_shape": [64, 768],
        "token_dtype": "torch.float16",
        "reverse_definition": config["source"]["reverse_definition"],
        "heuristic_token_permutation_used": False,
        "labels_in_cache": False,
        "sentences_in_cache": False,
        "pixel_inputs_used": False,
        "protected_300_dev_read": False,
        "revealed_483_test_read": False,
        "gold_outcomes_read": False,
        "external_outcomes_read": False,
        "scientific_claim_allowed": False,
    }
    write_json(output_root / "index.json", index)
    return index


def receipt_summary(result: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in result.items()
        if key not in {"shards"}
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Preflight or cache frozen R42A reversed exact64 tokens"
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--device")
    parser.add_argument("--preflight-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.preflight_only:
        if args.device is not None:
            raise ValueError("R42A reverse-cache preflight accepts no device")
        result = preflight(args.config)
    else:
        if args.device is None:
            raise ValueError("R42A reverse caching requires --device")
        result = cache_reverse_tokens(
            config_path=args.config, device_name=args.device
        )
    print(json.dumps(receipt_summary(result), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
