from __future__ import annotations

# ruff: noqa: E402

import argparse
from collections import defaultdict
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
from sklearn.metrics import roc_auc_score
from torch import Tensor, nn
from torch.nn import functional as F

from scripts.prepare_r33_token_features import (
    CACHE_ROOT,
    COHORT,
    LABELS,
    SEEDS,
    build_prior_shuffle,
    load_patch_cache,
    stable_hash,
)
from scripts.prepare_r33a_anatomy_context_features import (
    anatomy_mask,
    context_mask,
    query_matrix,
    transition_sources,
)
from scripts.prepare_r33a_direct_transition_features import (
    SUMMARY_WIDTH,
    assemble_summary,
    projection,
)


OUTPUT_DEFAULT = Path(
    r"F:\VisualVIT_runtime\050_routeC\r33a_case_study"
    r"\coherence_features_v3_projection_matched\token_features.pt"
)
ADAPTER_INPUT = 5 * 768
ADAPTER_WIDTH = 64
ADAPTER_SEED = 20263350
ADAPTER_SCALE = math.sqrt(ADAPTER_INPUT / ADAPTER_WIDTH)


class CoherenceAdapter(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.input = nn.Linear(ADAPTER_INPUT, ADAPTER_WIDTH)
        self.output = nn.Linear(ADAPTER_WIDTH, 1)

    def encode(self, value: Tensor) -> Tensor:
        hidden = F.gelu(self.input(value.float()))
        return F.layer_norm(hidden, (ADAPTER_WIDTH,))

    def forward(self, value: Tensor) -> Tensor:
        return self.output(self.encode(value)).squeeze(-1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare R33A outcome-free coherence token summaries"
    )
    parser.add_argument("--output", type=Path, default=OUTPUT_DEFAULT)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--adapter-batch-size", type=int, default=256)
    parser.add_argument("--adapter-epochs", type=int, default=12)
    return parser.parse_args()


def build_contrastive_negatives(records: list[dict[str, Any]]) -> list[int]:
    """Create finding-matched cross-patient negatives distinct from the control."""

    groups: dict[str, list[int]] = defaultdict(list)
    for index, row in enumerate(records):
        groups[str(row["finding_token"])].append(index)
    mapping = list(range(len(records)))
    for finding, indices in groups.items():
        ordered = sorted(
            indices,
            key=lambda index: stable_hash(
                "r33a-coherence-negative-v1",
                finding,
                records[index]["record_id"],
            ),
        )
        for position, index in enumerate(ordered):
            replacement = None
            # Start away from the adjacent rotation used by the formal control.
            start = max(1, len(ordered) // 3)
            for offset in range(start, start + len(ordered)):
                candidate = ordered[(position + offset) % len(ordered)]
                if records[candidate]["patient_id"] != records[index]["patient_id"]:
                    replacement = candidate
                    break
            if replacement is None:
                raise RuntimeError(
                    f"finding {finding!r} lacks a cross-patient negative"
                )
            mapping[index] = replacement
    return mapping


def relation_with_coherence(
    base: Tensor,
    embedding: Tensor | None,
) -> Tensor:
    if base.ndim != 2 or base.shape[1] != ADAPTER_INPUT:
        raise ValueError("base relation must have shape [N, 3840]")
    if embedding is None:
        extra = torch.zeros(
            base.shape[0],
            ADAPTER_WIDTH,
            device=base.device,
            dtype=base.dtype,
        )
    else:
        if embedding.shape != (base.shape[0], ADAPTER_WIDTH):
            raise ValueError("coherence embedding must have shape [N, 64]")
        extra = embedding.to(base.dtype) * ADAPTER_SCALE
    return torch.cat((base, extra), dim=-1)


def projection_matrices(
    query_width: int,
    seed: int,
    device: torch.device,
) -> dict[str, Tensor]:
    """Preserve every Attempt D row and append only coherence projection rows."""

    widths = {
        "query": query_width,
        "state": 768,
        "global": ADAPTER_INPUT,
        "local": ADAPTER_INPUT,
    }
    matrices = {
        name: projection(
            width,
            seed=20263400 + seed * 100 + offset,
            device=device,
        )
        for offset, (name, width) in enumerate(widths.items())
    }
    base_relation = projection(
        ADAPTER_INPUT,
        seed=20263400 + seed * 100 + 4,
        device=device,
    )
    added_relation = (
        projection(
            ADAPTER_WIDTH,
            seed=20263600 + seed * 100 + 4,
            device=device,
        )
        / ADAPTER_SCALE
    )
    matrices["relation"] = torch.cat((base_relation, added_relation), dim=0)
    return matrices


def _pair_inputs(
    records: list[dict[str, Any]],
    mapping: list[int],
    patch_index: dict[str, Tensor],
    context_masks: Tensor,
    *,
    device: torch.device,
    batch_size: int,
) -> Tensor:
    chunks = []
    with torch.inference_mode():
        for start in range(0, len(records), batch_size):
            end = min(start + batch_size, len(records))
            current = torch.stack(
                [
                    patch_index[str(records[index]["current_dicom_id"])]
                    for index in range(start, end)
                ]
            ).to(device)
            prior = torch.stack(
                [
                    patch_index[
                        str(records[mapping[index]]["prior_dicom_id"])
                    ]
                    for index in range(start, end)
                ]
            ).to(device)
            exact = torch.zeros_like(context_masks[start:end]).to(device)
            source = transition_sources(
                prior,
                current,
                exact,
                context_masks[start:end].to(device),
            )
            chunks.append(source["rich_relation"].to(torch.float16).cpu())
    return torch.cat(chunks)


def fit_adapter(
    positive: Tensor,
    negative: Tensor,
    heldout_negative: Tensor,
    *,
    device: torch.device,
    epochs: int,
    batch_size: int,
) -> tuple[CoherenceAdapter, dict[str, Any]]:
    if positive.shape != negative.shape or positive.shape != heldout_negative.shape:
        raise ValueError("coherence pair matrices must align")
    torch.manual_seed(ADAPTER_SEED)
    model = CoherenceAdapter().to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=3e-4, weight_decay=1e-2)
    values = torch.cat((positive, negative)).float()
    targets = torch.cat(
        (torch.ones(positive.shape[0]), torch.zeros(negative.shape[0]))
    )
    generator = torch.Generator(device="cpu").manual_seed(ADAPTER_SEED)
    model.train()
    for _ in range(epochs):
        permutation = torch.randperm(values.shape[0], generator=generator)
        for start in range(0, values.shape[0], batch_size):
            index = permutation[start : start + batch_size]
            logits = model(values[index].to(device))
            loss = F.binary_cross_entropy_with_logits(
                logits, targets[index].to(device)
            )
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            optimizer.step()
    model.eval()
    with torch.inference_mode():
        positive_logits = []
        heldout_logits = []
        for start in range(0, positive.shape[0], batch_size):
            end = min(start + batch_size, positive.shape[0])
            positive_logits.append(model(positive[start:end].to(device)).cpu())
            heldout_logits.append(
                model(heldout_negative[start:end].to(device)).cpu()
            )
        positive_logits = torch.cat(positive_logits)
        heldout_logits = torch.cat(heldout_logits)
    audit_targets = torch.cat(
        (torch.ones_like(positive_logits), torch.zeros_like(heldout_logits))
    )
    audit_logits = torch.cat((positive_logits, heldout_logits))
    return model, {
        "adapter_seed": ADAPTER_SEED,
        "adapter_epochs": epochs,
        "adapter_batch_size": batch_size,
        "train_positive_rows": int(positive.shape[0]),
        "train_negative_rows": int(negative.shape[0]),
        "heldout_control_negative_rows": int(heldout_negative.shape[0]),
        "heldout_control_accuracy": float(
            audit_logits.ge(0).eq(audit_targets.bool()).float().mean()
        ),
        "heldout_control_auc": float(
            roc_auc_score(audit_targets.numpy(), audit_logits.numpy())
        ),
        "positive_logit_mean": float(positive_logits.mean()),
        "heldout_negative_logit_mean": float(heldout_logits.mean()),
    }


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

    queries, findings, anatomies = query_matrix(records)
    exact = torch.stack([anatomy_mask(str(row["anatomy"])) for row in records])
    context = torch.stack([context_mask(mask) for mask in exact])
    formal_shuffle = build_prior_shuffle(records)
    contrastive_shuffle = build_contrastive_negatives(records)
    if formal_shuffle == contrastive_shuffle:
        raise RuntimeError("contrastive negatives must differ from formal control")
    if any(
        records[contrastive_shuffle[index]]["patient_id"] == row["patient_id"]
        for index, row in enumerate(records)
    ):
        raise RuntimeError("contrastive negative contains a same-patient prior")
    patch_index = load_patch_cache()

    identity = list(range(len(records)))
    started = time.perf_counter()
    positive_inputs = _pair_inputs(
        records,
        identity,
        patch_index,
        context,
        device=device,
        batch_size=args.batch_size,
    )
    negative_inputs = _pair_inputs(
        records,
        contrastive_shuffle,
        patch_index,
        context,
        device=device,
        batch_size=args.batch_size,
    )
    formal_control_inputs = _pair_inputs(
        records,
        formal_shuffle,
        patch_index,
        context,
        device=device,
        batch_size=args.batch_size,
    )
    adapter, adapter_audit = fit_adapter(
        positive_inputs,
        negative_inputs,
        formal_control_inputs,
        device=device,
        epochs=args.adapter_epochs,
        batch_size=args.adapter_batch_size,
    )

    matrices = {
        seed: projection_matrices(queries.shape[1], seed, device)
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
                    patch_index[
                        str(records[formal_shuffle[index]]["prior_dicom_id"])
                    ]
                    for index in range(start, end)
                ]
            ).to(device)
            exact_batch = exact[start:end].to(device)
            context_batch = context[start:end].to(device)
            original = transition_sources(prior, current, exact_batch, context_batch)
            shifted = transition_sources(
                shifted_prior, current, exact_batch, context_batch
            )
            original_embedding = adapter.encode(original["rich_relation"])
            shifted_embedding = adapter.encode(shifted["rich_relation"])
            for source, embedding in (
                (original, original_embedding),
                (shifted, shifted_embedding),
            ):
                source["robust_relation"] = relation_with_coherence(
                    source["robust_relation"], None
                )
                source["rich_relation"] = relation_with_coherence(
                    source["rich_relation"], embedding
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
                            "stage": "coherence_features",
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
        "variant": "r33a_coherence_adapter_v3_projection_matched",
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
        "adapter_audit": adapter_audit,
        "adapter_outcome_free": True,
        "contrastive_negative_distinct_from_formal_control": True,
        "attempt_d_projection_rows_preserved": True,
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
            "anatomy_vocabulary_size": len(anatomies),
            "finding_vocabulary": findings,
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
