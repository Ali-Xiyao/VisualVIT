from __future__ import annotations

# ruff: noqa: E402

import argparse
import json
import math
from pathlib import Path
import sys
import time
from typing import Any

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


OUTPUT_DEFAULT = Path(
    r"F:\VisualVIT_runtime\050_routeC\r33a_case_study"
    r"\direct_transition_features_v1\token_features.pt"
)
TYPE_COUNT = 6
TYPE_WIDTH = 64
SUMMARY_WIDTH = TYPE_COUNT * TYPE_WIDTH * 2 + TYPE_COUNT


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare R33A direct transition exact-64 summaries"
    )
    parser.add_argument("--output", type=Path, default=OUTPUT_DEFAULT)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--batch-size", type=int, default=128)
    return parser.parse_args()


def pair_interactions(prior: Tensor, current: Tensor) -> Tensor:
    prior = F.normalize(prior.float(), dim=-1)
    current = F.normalize(current.float(), dim=-1)
    delta = current - prior
    return torch.cat((prior, current, delta, delta.abs(), prior * current), -1)


def projection(input_dim: int, seed: int, device: torch.device) -> Tensor:
    generator = torch.Generator(device="cpu").manual_seed(seed)
    value = torch.randn(
        input_dim,
        2 * TYPE_WIDTH,
        generator=generator,
        dtype=torch.float32,
    ) / math.sqrt(input_dim)
    return value.to(device)


def project_summary(value: Tensor, matrix: Tensor) -> tuple[Tensor, Tensor]:
    projected = value.float() @ matrix
    mean, maximum = projected.split(TYPE_WIDTH, dim=-1)
    return F.layer_norm(mean, (TYPE_WIDTH,)), F.layer_norm(maximum, (TYPE_WIDTH,))


def assemble_summary(
    query: Tensor,
    state: Tensor,
    global_transition: Tensor,
    local: Tensor,
    relation: Tensor,
    matrices: dict[str, Tensor],
    *,
    rich: bool,
) -> Tensor:
    sources = {
        "query": query,
        "state": state,
        "global": global_transition,
        "local": local,
        "relation": relation,
    }
    means = []
    maxima = []
    for name in ("query", "state", "global", "local", "relation"):
        mean, maximum = project_summary(sources[name], matrices[name])
        means.append(mean)
        maxima.append(maximum)
    zeros = torch.zeros_like(means[0])
    means.append(zeros)
    maxima.append(zeros)
    fractions = (
        torch.tensor(
            [1.0, 1.0, 1.0, 1.0, 1.0 if rich else 4 / 12, 0.0],
            device=query.device,
        )
        .view(1, -1)
        .expand(query.shape[0], -1)
    )
    output = torch.cat((*means, *maxima, fractions), dim=-1)
    if output.shape[1] != SUMMARY_WIDTH:
        raise RuntimeError("R33A summary width drift")
    return output


def transition_sources(prior: Tensor, current: Tensor) -> dict[str, Tensor]:
    prior = prior.float()
    current = current.float()
    prior_cls = prior[:, 0]
    current_cls = current[:, 0]
    prior_patches = prior[:, 1:]
    current_patches = current[:, 1:]
    prior_mean = prior_patches.mean(dim=1)
    current_mean = current_patches.mean(dim=1)
    prior_std = prior_patches.std(dim=1, unbiased=False)
    current_std = current_patches.std(dim=1, unbiased=False)

    change = (current_patches - prior_patches).float()
    change_score = change.square().mean(dim=-1)
    top = change_score.topk(k=16, dim=-1).indices
    gather = top.unsqueeze(-1).expand(-1, -1, prior_patches.shape[-1])
    prior_top = prior_patches.gather(1, gather).mean(dim=1)
    current_top = current_patches.gather(1, gather).mean(dim=1)

    weights = torch.softmax(
        change_score / change_score.std(dim=1, keepdim=True).clamp_min(1e-6), dim=1
    )
    prior_weighted = torch.einsum("bn,bnd->bd", weights, prior_patches)
    current_weighted = torch.einsum("bn,bnd->bd", weights, current_patches)
    return {
        "state": current_cls,
        "global": pair_interactions(prior_cls, current_cls),
        "robust_local": pair_interactions(prior_mean, current_mean),
        "rich_local": pair_interactions(prior_top, current_top),
        "robust_relation": pair_interactions(prior_std, current_std),
        "rich_relation": pair_interactions(prior_weighted, current_weighted),
    }


def query_matrix(
    records: list[dict[str, Any]],
) -> tuple[Tensor, list[str]]:
    vocabulary = sorted({str(row["finding_token"]) for row in records})
    index = {value: position for position, value in enumerate(vocabulary)}
    output = torch.zeros(len(records), len(vocabulary))
    output[
        torch.arange(len(records)),
        torch.tensor([index[str(row["finding_token"])] for row in records]),
    ] = 1
    return output, vocabulary


def main() -> int:
    args = parse_args()
    if args.output.exists():
        raise FileExistsError(f"output must be fresh: {args.output}")
    device = torch.device(args.device)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but unavailable")
    all_records = json.loads(COHORT.read_text(encoding="utf-8"))
    records = [
        row
        for row in all_records
        if row["partition"] == "train" and row["progression"] in LABELS
    ]
    if len(records) != 13_566:
        raise RuntimeError("R33A train record count drift")
    if len({str(row["patient_id"]) for row in records}) != 1_574:
        raise RuntimeError("R33A train patient count drift")

    queries, finding_vocab = query_matrix(records)
    shuffle = build_prior_shuffle(records)
    patch_index = load_patch_cache()
    results: dict[str, dict[int, list[Tensor]]] = {
        name: {seed: [] for seed in SEEDS}
        for name in (
            "robust",
            "rich",
            "prior_shuffle_robust",
            "prior_shuffle_rich",
        )
    }
    matrices: dict[int, dict[str, Tensor]] = {}
    dims = {
        "query": len(finding_vocab),
        "state": 768,
        "global": 5 * 768,
        "local": 5 * 768,
        "relation": 5 * 768,
    }
    for seed in SEEDS:
        matrices[seed] = {
            name: projection(
                width,
                seed=20263300 + seed * 100 + offset,
                device=device,
            )
            for offset, (name, width) in enumerate(dims.items())
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
            shuffled_prior = torch.stack(
                [
                    patch_index[str(records[shuffle[index]]["prior_dicom_id"])]
                    for index in range(start, end)
                ]
            ).to(device)
            original = transition_sources(prior, current)
            shifted = transition_sources(shuffled_prior, current)
            query = queries[start:end].to(device)
            for seed in SEEDS:
                matrix = matrices[seed]
                for prefix, source in (
                    ("", original),
                    ("prior_shuffle_", shifted),
                ):
                    results[f"{prefix}robust"][seed].append(
                        assemble_summary(
                            query,
                            source["state"],
                            source["global"],
                            source["robust_local"],
                            source["robust_relation"],
                            matrix,
                            rich=False,
                        )
                        .to(torch.float16)
                        .cpu()
                    )
                    results[f"{prefix}rich"][seed].append(
                        assemble_summary(
                            query,
                            source["state"],
                            source["global"],
                            source["rich_local"],
                            source["rich_relation"],
                            matrix,
                            rich=True,
                        )
                        .to(torch.float16)
                        .cpu()
                    )
            if start % (args.batch_size * 25) == 0:
                print(
                    json.dumps(
                        {
                            "complete": end,
                            "total": len(records),
                            "stage": "direct_transition_features",
                        }
                    ),
                    flush=True,
                )

    packed = {
        name: {seed: torch.cat(chunks, dim=0) for seed, chunks in seeded.items()}
        for name, seeded in results.items()
    }
    output = {
        "schema": "visualvit.r33.token-features.v1",
        "status": "PASS_R33_FEATURE_PREPARATION",
        "variant": "r33a_direct_transition_v1",
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
        "feature_dim": SUMMARY_WIDTH,
        "token_budget": 64,
        "token_layout": (4, 12, 16, 16, 12, 4),
        "source_cache_identifier": json.loads(
            (CACHE_ROOT / "cache_manifest.json").read_text(encoding="utf-8")
        )["cache_identifier"],
        "sealed_test_records_read": False,
        "sealed_test_images_read": False,
        "gold_outcomes_read": False,
        "probe_labels_or_logits_in_tokens": False,
        "biomedclip_text_encoder_frozen": True,
        "builders_frozen": True,
        "prior_shuffle_cross_patient": True,
        "literal_query_only_type": True,
        "finding_query_outcome_free": True,
        "dev_case_outcomes_inspected": False,
        "elapsed_seconds": time.perf_counter() - started,
        "finding_vocabulary": finding_vocab,
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
