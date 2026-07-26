from __future__ import annotations

# ruff: noqa: E402

import argparse
import json
import math
from pathlib import Path
import sys
import time

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE / "src"))
sys.path.insert(0, str(WORKSPACE))

import torch
from torch import Tensor
from torch.nn import functional as F

from scripts.prepare_r33_token_features import (
    CACHE_ROOT,
    COHORT,
    LABELS,
    SEEDS,
    build_prior_shuffle,
    load_patch_cache,
)
from scripts.prepare_r33a_anatomy_context_features import (
    anatomy_mask,
    context_mask,
    query_matrix,
    transition_sources,
)


OUTPUT_DEFAULT = Path(
    r"F:\VisualVIT_runtime\050_routeC\r33a_case_study"
    r"\prebridge_features_v1\token_features.pt"
)
PREBRIDGE_WIDTH = 256
TYPE_COUNT = 5
FEATURE_DIM = TYPE_COUNT * PREBRIDGE_WIDTH + 6


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare R33A high-rank outcome-free prebridge features"
    )
    parser.add_argument("--output", type=Path, default=OUTPUT_DEFAULT)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--batch-size", type=int, default=64)
    return parser.parse_args()


def prebridge_projection(
    input_dim: int,
    *,
    seed: int,
    device: torch.device,
) -> Tensor:
    generator = torch.Generator(device="cpu").manual_seed(seed)
    return (
        torch.randn(
            input_dim,
            PREBRIDGE_WIDTH,
            generator=generator,
            dtype=torch.float32,
        )
        .div_(math.sqrt(input_dim))
        .to(device)
    )


def assemble_prebridge(
    query: Tensor,
    state: Tensor,
    global_transition: Tensor,
    local: Tensor,
    relation: Tensor,
    matrices: dict[str, Tensor],
    *,
    rich: bool,
) -> Tensor:
    blocks = []
    for name, source in (
        ("query", query),
        ("state", state),
        ("global", global_transition),
        ("local", local),
        ("relation", relation),
    ):
        blocks.append(
            F.layer_norm(
                source.float() @ matrices[name],
                (PREBRIDGE_WIDTH,),
            )
        )
    fractions = (
        torch.tensor(
            [1.0, 1.0, 1.0, 1.0, 1.0 if rich else 4 / 12, 0.0],
            device=query.device,
        )
        .view(1, -1)
        .expand(query.shape[0], -1)
    )
    output = torch.cat((*blocks, fractions), dim=-1)
    if output.shape[1] != FEATURE_DIM:
        raise RuntimeError("prebridge feature width drift")
    return output


def main() -> int:
    args = parse_args()
    if args.output.exists():
        raise FileExistsError(f"output must be fresh: {args.output}")
    device = torch.device(args.device)
    all_records = json.loads(COHORT.read_text(encoding="utf-8"))
    records = [
        row
        for row in all_records
        if row["partition"] == "train" and row["progression"] in LABELS
    ]
    if len(records) != 13_566:
        raise RuntimeError("R33A train record count drift")
    queries, findings, anatomies = query_matrix(records)
    exact = torch.stack([anatomy_mask(str(row["anatomy"])) for row in records])
    context = torch.stack([context_mask(mask) for mask in exact])
    shuffle = build_prior_shuffle(records)
    patch_index = load_patch_cache()

    widths = {
        "query": queries.shape[1],
        "state": 768,
        "global": 5 * 768,
        "local": 5 * 768,
        "relation": 5 * 768,
    }
    matrices = {
        seed: {
            name: prebridge_projection(
                width,
                seed=20263700 + seed * 100 + offset,
                device=device,
            )
            for offset, (name, width) in enumerate(widths.items())
        }
        for seed in SEEDS
    }
    results = {
        name: {seed: [] for seed in SEEDS}
        for name in (
            "robust",
            "rich",
            "prior_shuffle_robust",
            "prior_shuffle_rich",
        )
    }
    started = time.perf_counter()
    with torch.inference_mode():
        for start in range(0, len(records), args.batch_size):
            end = min(start + args.batch_size, len(records))
            batch = records[start:end]
            prior = torch.stack(
                [patch_index[str(row["prior_dicom_id"])] for row in batch]
            ).to(device)
            current = torch.stack(
                [patch_index[str(row["current_dicom_id"])] for row in batch]
            ).to(device)
            shifted_prior = torch.stack(
                [
                    patch_index[str(records[shuffle[index]]["prior_dicom_id"])]
                    for index in range(start, end)
                ]
            ).to(device)
            exact_batch = exact[start:end].to(device)
            context_batch = context[start:end].to(device)
            original = transition_sources(prior, current, exact_batch, context_batch)
            shifted = transition_sources(
                shifted_prior, current, exact_batch, context_batch
            )
            query = queries[start:end].to(device)
            for seed in SEEDS:
                matrix = matrices[seed]
                for prefix, source in (
                    ("", original),
                    ("prior_shuffle_", shifted),
                ):
                    for rich in (False, True):
                        results[f"{prefix}{'rich' if rich else 'robust'}"][seed].append(
                            assemble_prebridge(
                                query,
                                source["state"],
                                source["global"],
                                source["rich_local" if rich else "robust_local"],
                                source["rich_relation" if rich else "robust_relation"],
                                matrix,
                                rich=rich,
                            )
                            .to(torch.float16)
                            .cpu()
                        )
            if start % (args.batch_size * 25) == 0:
                print(
                    json.dumps(
                        {
                            "stage": "prebridge_features",
                            "complete": end,
                            "total": len(records),
                        }
                    ),
                    flush=True,
                )

    packed = {
        name: {seed: torch.cat(chunks) for seed, chunks in seeded.items()}
        for name, seeded in results.items()
    }
    output = {
        "schema": "visualvit.r33.token-features.v1",
        "status": "PASS_R33_FEATURE_PREPARATION",
        "variant": "r33a_prebridge_256_v1",
        "scope": "train_only",
        "records": [
            {
                "record_id": row["record_id"],
                "patient_id": row["patient_id"],
                "partition": row["partition"],
                "finding_token": row["finding_token"],
                "progression": row["progression"],
            }
            for row in records
        ],
        "features": packed,
        "seeds": SEEDS,
        "labels": LABELS,
        "feature_dim": FEATURE_DIM,
        "feature_type_width": PREBRIDGE_WIDTH,
        "feature_type_count": TYPE_COUNT,
        "learned_bridge_width": 64,
        "token_budget": 64,
        "token_layout": (4, 12, 16, 16, 12, 4),
        "source_cache_identifier": json.loads(
            (CACHE_ROOT / "cache_manifest.json").read_text(encoding="utf-8")
        )["cache_identifier"],
        "biomedclip_text_encoder_frozen": True,
        "builders_frozen": True,
        "prior_shuffle_cross_patient": True,
        "literal_query_only_type": True,
        "finding_query_outcome_free": True,
        "anatomy_masks_outcome_free": True,
        "sealed_test_records_read": False,
        "sealed_test_images_read": False,
        "gold_outcomes_read": False,
        "probe_labels_or_logits_in_tokens": False,
        "dev_case_outcomes_inspected": False,
        "prebridge_outcome_free": True,
        "elapsed_seconds": time.perf_counter() - started,
    }
    args.output.parent.mkdir(parents=True, exist_ok=False)
    torch.save(output, args.output)
    summary = {
        key: value
        for key, value in output.items()
        if key not in {"records", "features"}
    }
    summary.update(
        {
            "record_count": len(records),
            "patient_count": len({str(row["patient_id"]) for row in records}),
            "finding_vocabulary": findings,
            "anatomy_vocabulary_size": len(anatomies),
            "output": str(args.output),
            "output_bytes": args.output.stat().st_size,
        }
    )
    (args.output.parent / "feature_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
