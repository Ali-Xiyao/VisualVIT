from __future__ import annotations

# ruff: noqa: E402

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Iterable

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE))
sys.path.insert(0, str(WORKSPACE / "src"))

import torch

from scripts.cache_r37_block8_tokens import build_frozen_encoder
from scripts.r37c_common import checkpoint_for, load_candidate
from scripts.run_r37_prta_smoke import batch_indices
from visualvit.prta import PRTATemporalAdapter, PRTATrainingHeads
from visualvit.r37_cache import Block8CacheIndex
from visualvit.r38_fixed64 import pack_fixed64


CONFIG_STATUS = "FROZEN_PRTA_GEN_R40A_PROBE_AFTER_TARGET_SUPPORT"
TARGET_STATUS = "PASS_PRTA_GEN_R40A_TARGET_SUPPORT"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def stable_order(namespace: str, seed: int, value: str) -> str:
    return hashlib.sha256(
        f"{namespace}|{seed}|{value}".encode("utf-8")
    ).hexdigest()


def prior_shuffle_assignment(
    rows: Iterable[dict[str, Any]],
    *,
    seed: int,
) -> dict[str, str]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row["finding"]), []).append(row)
    assignment: dict[str, str] = {}
    for finding_rows in grouped.values():
        ordered = sorted(
            finding_rows,
            key=lambda row: (
                stable_order(
                    "prta-gen-r40a-prior-shuffle-v1",
                    seed,
                    str(row["example_id"]),
                ),
                str(row["example_id"]),
            ),
        )
        if len({str(row["patient_id"]) for row in ordered}) < 2:
            raise ValueError("prior shuffle requires two patients per finding")
        for index, row in enumerate(ordered):
            for offset in range(1, len(ordered) + 1):
                candidate = ordered[(index + offset) % len(ordered)]
                if str(candidate["patient_id"]) != str(row["patient_id"]):
                    assignment[str(row["example_id"])] = str(
                        candidate["prior_dicom_id"]
                    )
                    break
            else:
                raise RuntimeError("unable to assign cross-patient prior")
    if len(assignment) != sum(len(rows) for rows in grouped.values()):
        raise RuntimeError("prior-shuffle assignment is incomplete")
    return assignment


def load_probe_config(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    config = read_json(path)
    if config.get("status") != CONFIG_STATUS:
        raise PermissionError("PRTA-Gen R40A probe config is not frozen")
    target_audit = read_json(Path(config["upstream_target_audit"]))
    if (
        target_audit.get("status") != config["required_target_status"]
        or target_audit.get("patient_disjoint") is not True
        or target_audit.get("protected_300_dev_read") is not False
        or target_audit.get("revealed_483_test_read") is not False
        or target_audit.get("gold_outcomes_read") is not False
    ):
        raise PermissionError("PRTA-Gen R40A target-audit firewall drift")
    required_false = (
        "protected_300_dev_read",
        "revealed_483_test_read",
        "gold_outcomes_read",
        "source_hashes_recomputed",
        "per_shard_hashes_computed",
        "checkpoint_hashes_recomputed",
        "old_r40_component_queue_resumed",
    )
    drift = [
        key for key in required_false if config["firewall"].get(key) is not False
    ]
    if drift:
        raise PermissionError(f"PRTA-Gen R40A firewall drift: {drift}")
    return config, target_audit


def select_rows(
    rows: list[dict[str, Any]], *, smoke_rows: int
) -> list[dict[str, Any]]:
    if smoke_rows == 0:
        return rows
    if smoke_rows < 0 or smoke_rows > len(rows):
        raise ValueError("invalid smoke row count")
    return sorted(
        rows,
        key=lambda row: (
            stable_order(
                "prta-gen-r40a-token-smoke-v1",
                0,
                str(row["example_id"]),
            ),
            str(row["example_id"]),
        ),
    )[:smoke_rows]


def token_cache_output_root(
    config: dict[str, Any], *, scope: str, smoke_rows: int
) -> Path:
    base = (
        Path(config["token_cache_root"])
        / scope
        / f"seed_{int(config['frozen_prta_seed'])}"
    )
    return base / (f"smoke_{smoke_rows}" if smoke_rows else "formal")


def materialize_required_features(
    cache: Block8CacheIndex,
    dicom_ids: Iterable[str],
) -> dict[str, torch.Tensor]:
    """Clone required rows while reading each source shard only once."""

    unique_ids = sorted({str(value) for value in dicom_ids})
    missing = [value for value in unique_ids if value not in cache.locations]
    if missing:
        raise KeyError(
            f"{len(missing)} required DICOM IDs are absent; first={missing[0]}"
        )
    grouped: dict[Path, list[tuple[str, int]]] = defaultdict(list)
    for dicom_id in unique_ids:
        path, local_index = cache.locations[dicom_id]
        grouped[path].append((dicom_id, local_index))
    compact: dict[str, torch.Tensor] = {}
    for path in sorted(grouped, key=str):
        shard = torch.load(path, map_location="cpu", weights_only=True)
        features = shard["features"]
        if tuple(features.shape[1:]) != (197, 768):
            raise ValueError(f"unexpected Block-8 shard shape: {path}")
        requests = grouped[path]
        indices = torch.tensor(
            [local_index for _, local_index in requests], dtype=torch.long
        )
        selected = features.index_select(0, indices).clone()
        for position, (dicom_id, _) in enumerate(requests):
            compact[dicom_id] = selected[position]
    if len(compact) != len(unique_ids):
        raise RuntimeError("compact Block-8 materialization is incomplete")
    return compact


def compact_get_many(
    compact: dict[str, torch.Tensor], dicom_ids: Iterable[str]
) -> torch.Tensor:
    ids = [str(value) for value in dicom_ids]
    missing = [value for value in ids if value not in compact]
    if missing:
        raise KeyError(f"compact cache is missing DICOM {missing[0]}")
    return torch.stack([compact[value] for value in ids])


def cache_tokens(
    *,
    config_path: Path,
    scope: str,
    device_name: str,
    batch_size: int,
    shard_size: int,
    smoke_rows: int,
) -> dict[str, Any]:
    if scope not in {"training", "development"}:
        raise ValueError("scope must be training or development")
    config, target_audit = load_probe_config(config_path)
    frozen_cache = config["token_cache"]
    if batch_size != int(frozen_cache["batch_size"]):
        raise ValueError("PRTA-Gen token-cache batch-size drift")
    if shard_size != int(frozen_cache["shard_size"]):
        raise ValueError("PRTA-Gen token-cache shard-size drift")
    if smoke_rows not in {0, int(frozen_cache["smoke_rows"])}:
        raise ValueError("PRTA-Gen token-cache smoke-row drift")
    rows = read_jsonl(Path(config["target_root"]) / f"{scope}_targets.jsonl")
    expected_rows = int(frozen_cache["formal_rows"][scope])
    if len(rows) != expected_rows:
        raise ValueError("PRTA-Gen target-row count drift")
    if len({str(row["patient_id"]) for row in rows}) != int(
        target_audit[f"{scope}_patients"]
    ):
        raise ValueError("PRTA-Gen target patient-count drift")
    shuffle = prior_shuffle_assignment(
        rows, seed=int(config["prior_shuffle"]["seed"])
    )
    selected_rows = select_rows(rows, smoke_rows=smoke_rows)

    output_root = token_cache_output_root(
        config,
        scope=scope,
        smoke_rows=smoke_rows,
    )
    if output_root.exists():
        raise FileExistsError(
            f"PRTA-Gen token cache must be fresh: {output_root}"
        )
    output_root.mkdir(parents=True)
    shards_root = output_root / "shards"
    shards_root.mkdir()

    device = torch.device(device_name)
    if device.type != "cuda" or not torch.cuda.is_available():
        raise RuntimeError("PRTA-Gen exact64 caching requires CUDA")
    torch.cuda.set_device(device)
    candidate = load_candidate(WORKSPACE / config["source_candidate"])
    text_cache = torch.load(
        config["text_cache"], map_location="cpu", weights_only=True
    )
    findings = [str(value) for value in text_cache["findings"]]
    finding_to_index = {finding: index for index, finding in enumerate(findings)}
    unknown_findings = {
        str(row["finding"]) for row in selected_rows
    } - set(findings)
    if unknown_findings:
        raise ValueError(
            f"PRTA-Gen target finding registry drift: {sorted(unknown_findings)}"
        )

    cache = Block8CacheIndex(
        Path(config["block8_cache_root"]), maximum_loaded_shards=1
    )
    required_dicom_ids = {
        str(row[key])
        for row in selected_rows
        for key in ("prior_dicom_id", "current_dicom_id")
    }
    required_dicom_ids.update(
        shuffle[str(row["example_id"])] for row in selected_rows
    )
    compact_cache = materialize_required_features(
        cache, required_dicom_ids
    )
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
            seed=int(config["frozen_prta_seed"]),
        ),
        map_location="cpu",
        weights_only=True,
    )
    model.load_state_dict(checkpoint["model"], strict=True)
    heads.load_state_dict(checkpoint["heads"], strict=True)
    model.eval()
    heads.eval()
    finding_text = text_cache["finding_embeddings"].to(device)

    shards: list[dict[str, Any]] = []
    pending: dict[str, list[Any]] = {
        "example_ids": [],
        "patient_ids": [],
        "findings": [],
        "true_tokens": [],
        "current_tokens": [],
        "shuffled_tokens": [],
    }

    def flush() -> None:
        nonlocal pending
        if not pending["example_ids"]:
            return
        path = shards_root / f"fixed64_{len(shards):04d}.pt"
        payload = {
            "schema": "visualvit.prta-gen.r40a-token-shard.v1",
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
        for start, end in batch_indices(len(selected_rows), batch_size):
            batch = selected_rows[start:end]
            prior = compact_get_many(
                compact_cache,
                (row["prior_dicom_id"] for row in batch),
            ).to(device=device, dtype=torch.float32)
            current = compact_get_many(
                compact_cache,
                (row["current_dicom_id"] for row in batch),
            ).to(device=device, dtype=torch.float32)
            shuffled_prior = compact_get_many(
                compact_cache,
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
                    raise RuntimeError("PRTA-Gen exact64 token audit failed")
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
        "schema": "visualvit.prta-gen.r40a-token-cache.v1",
        "status": (
            "PASS_PRTA_GEN_R40A_TOKEN_CACHE_SMOKE"
            if smoke_rows
            else "PASS_PRTA_GEN_R40A_TOKEN_CACHE"
        ),
        "protocol_id": config["protocol_id"],
        "scope": scope,
        "seed": int(config["frozen_prta_seed"]),
        "smoke_rows": smoke_rows,
        "rows": len(selected_rows),
        "patients": len(
            {str(row["patient_id"]) for row in selected_rows}
        ),
        "shards": shards,
        "shard_count": len(shards),
        "token_shape": [64, 768],
        "token_dtype": "torch.float16",
        "cached_variants": frozen_cache["variants"],
        "labels_in_cache": False,
        "sentences_in_cache": False,
        "source_shards_materialized_once": True,
        "compact_required_dicom_count": len(compact_cache),
        "prior_shuffle": config["prior_shuffle"],
        "protected_300_dev_read": False,
        "revealed_483_test_read": False,
        "gold_outcomes_read": False,
        "source_hashes_recomputed": False,
        "per_shard_hashes_computed": False,
        "checkpoint_hashes_recomputed": False,
        "old_r40_component_queue_resumed": False,
        "scientific_claim_allowed": False,
    }
    write_json(output_root / "index.json", index)
    return index


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Cache PRTA-Gen R40A exact64 probe tokens"
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument(
        "--scope", choices=("training", "development"), required=True
    )
    parser.add_argument("--device", required=True)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--shard-size", type=int, default=256)
    parser.add_argument("--smoke-rows", type=int, default=0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = cache_tokens(
        config_path=args.config,
        scope=args.scope,
        device_name=args.device,
        batch_size=args.batch_size,
        shard_size=args.shard_size,
        smoke_rows=args.smoke_rows,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
