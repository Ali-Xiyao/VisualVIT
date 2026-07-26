from __future__ import annotations

# ruff: noqa: E402

import argparse
import json
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
from scripts.prepare_r33a_direct_transition_features import (
    SUMMARY_WIDTH,
    assemble_summary,
    pair_interactions,
    projection,
)


OUTPUT_DEFAULT = Path(
    r"F:\VisualVIT_runtime\050_routeC\r33a_case_study"
    r"\anatomy_context_features_v1\token_features.pt"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare R33A anatomy-aware contextual token summaries"
    )
    parser.add_argument("--output", type=Path, default=OUTPUT_DEFAULT)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--batch-size", type=int, default=128)
    return parser.parse_args()


def _single_anatomy_mask(text: str, grid: int = 14) -> Tensor:
    value = text.lower()
    y, x = torch.meshgrid(
        torch.linspace(0, 1, grid),
        torch.linspace(0, 1, grid),
        indexing="ij",
    )
    if "costophrenic" in value:
        mask = y.ge(0.65)
    elif "cardiac" in value:
        mask = y.ge(0.32) & y.le(0.88) & x.ge(0.25) & x.le(0.72)
    elif "mediast" in value:
        mask = y.ge(0.08) & y.le(0.82) & x.ge(0.34) & x.le(0.66)
    elif "hilar" in value:
        mask = y.ge(0.28) & y.le(0.68) & x.ge(0.22) & x.le(0.78)
    else:
        mask = y.ge(0.10) & y.le(0.92) & (x.le(0.46) | x.ge(0.54))

    # Patient right is displayed on the image's left.
    has_left = "left" in value
    has_right = "right" in value
    if has_left and not has_right:
        mask &= x.ge(0.46)
    elif has_right and not has_left:
        mask &= x.le(0.54)
    if "upper" in value:
        mask &= y.le(0.56)
    elif "lower" in value:
        mask &= y.ge(0.44)
    elif "mid" in value:
        mask &= y.ge(0.28) & y.le(0.75)
    return mask.flatten()


def anatomy_mask(text: str, grid: int = 14) -> Tensor:
    """Return the union of registered anatomy regions on the patch grid."""

    parts = [part.strip() for part in text.split(",") if part.strip()]
    if not parts:
        raise ValueError("anatomy text must not be empty")
    masks = [_single_anatomy_mask(part, grid) for part in parts]
    output = torch.stack(masks).any(dim=0)
    if not bool(output.any()):
        raise RuntimeError(f"empty anatomy mask for {text!r}")
    return output


def context_mask(mask: Tensor, grid: int = 14) -> Tensor:
    value = mask.float().view(1, 1, grid, grid)
    return F.max_pool2d(value, kernel_size=5, stride=1, padding=2).bool().flatten()


def pool_masked(patches: Tensor, mask: Tensor) -> Tensor:
    weights = mask.to(patches.device, dtype=patches.dtype)
    return torch.einsum("bn,bnd->bd", weights, patches) / weights.sum(
        dim=1, keepdim=True
    ).clamp_min(1)


def transition_sources(
    prior: Tensor,
    current: Tensor,
    exact_masks: Tensor,
    context_masks: Tensor,
) -> dict[str, Tensor]:
    prior = prior.float()
    current = current.float()
    prior_patches = prior[:, 1:]
    current_patches = current[:, 1:]
    prior_global = prior_patches.mean(dim=1)
    current_global = current_patches.mean(dim=1)
    prior_exact = pool_masked(prior_patches, exact_masks)
    current_exact = pool_masked(current_patches, exact_masks)
    prior_context = pool_masked(prior_patches, context_masks)
    current_context = pool_masked(current_patches, context_masks)
    coarse = pair_interactions(prior_global, current_global)
    return {
        "state": current_exact,
        "global": pair_interactions(prior[:, 0], current[:, 0]),
        "robust_local": coarse,
        "rich_local": pair_interactions(prior_exact, current_exact),
        "robust_relation": coarse,
        "rich_relation": pair_interactions(prior_context, current_context),
    }


def query_matrix(
    records: list[dict[str, Any]],
) -> tuple[Tensor, list[str], list[str]]:
    findings = sorted({str(row["finding_token"]) for row in records})
    anatomies = sorted({str(row["anatomy"]).lower() for row in records})
    finding_index = {value: index for index, value in enumerate(findings)}
    anatomy_index = {
        value: len(findings) + index for index, value in enumerate(anatomies)
    }
    output = torch.zeros(len(records), len(findings) + len(anatomies))
    for row_index, row in enumerate(records):
        output[row_index, finding_index[str(row["finding_token"])]] = 1
        output[row_index, anatomy_index[str(row["anatomy"]).lower()]] = 1
    return output, findings, anatomies


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
    if bool((context.sum(1) < exact.sum(1)).any()):
        raise RuntimeError("context mask must contain exact mask")
    shuffle = build_prior_shuffle(records)
    patch_index = load_patch_cache()

    dims = {
        "query": queries.shape[1],
        "state": 768,
        "global": 5 * 768,
        "local": 5 * 768,
        "relation": 5 * 768,
    }
    matrices = {
        seed: {
            name: projection(
                width,
                seed=20263400 + seed * 100 + offset,
                device=device,
            )
            for offset, (name, width) in enumerate(dims.items())
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
                            assemble_summary(
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
                            "stage": "anatomy_context_features",
                            "complete": end,
                            "total": len(records),
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
        "variant": "r33a_anatomy_context_v1",
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
        "anatomy_masks_outcome_free": True,
        "finding_vocabulary": findings,
        "anatomy_vocabulary": anatomies,
        "elapsed_seconds": time.perf_counter() - started,
    }
    args.output.parent.mkdir(parents=True, exist_ok=False)
    torch.save(output, args.output)
    summary = {
        key: value
        for key, value in output.items()
        if key not in {"records", "features", "anatomy_vocabulary"}
    }
    summary.update(
        {
            "anatomy_vocabulary_size": len(anatomies),
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
