from __future__ import annotations

# ruff: noqa: E402

import argparse
from collections import defaultdict
import gc
import hashlib
import json
from pathlib import Path
import sys
import time
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE / "src"))

import torch
from torch import Tensor

from visualvit.hierarchical_temporal_tokens import (
    HierarchicalTemporalTokenBuilder,
)
from visualvit.schemas import TokenBundle


LABELS = ("Stable", "Improved", "Worse")
SEEDS = (17, 29, 43)
COHORT = Path(
    r"F:\VisualVIT_runtime\050_routeC\r32_tier_cxr_vlm"
    r"\cohort_v1\train_dev_cohort.json"
)
CACHE_ROOT = Path(
    r"F:\VisualVIT_runtime\050_routeC\r32_tier_cxr_vlm"
    r"\patch_cache_train_dev_v1"
)
BIOMEDCLIP_ROOT = Path(r"H:\Xiyao_Wang\001_models\biomedclip")
OUTPUT_DEFAULT = Path(
    r"F:\VisualVIT_runtime\050_routeC\r33_token_survival"
    r"\features_v1\token_features.pt"
)


def stable_hash(*parts: object) -> str:
    return hashlib.sha256(
        "|".join(str(part) for part in parts).encode("utf-8")
    ).hexdigest()


def fixed_projection(
    input_dim: int, output_dim: int, seed: int, device: torch.device
) -> Tensor:
    generator = torch.Generator(device="cpu").manual_seed(seed)
    matrix = torch.randn(
        input_dim, output_dim, generator=generator, dtype=torch.float32
    )
    matrix = torch.linalg.qr(matrix, mode="reduced").Q
    return matrix.to(device)


def load_patch_cache() -> dict[str, Tensor]:
    manifest = json.loads(
        (CACHE_ROOT / "cache_manifest.json").read_text(encoding="utf-8")
    )
    if manifest["status"] != "PASS_R32_PATCH_CACHE":
        raise RuntimeError("R32 patch cache is not a PASS artifact")
    if manifest["scope"] != "train_dev_only":
        raise RuntimeError("R33 forbids a cache that includes sealed images")
    index: dict[str, Tensor] = {}
    for shard_entry in manifest["shards"]:
        shard = torch.load(
            shard_entry["path"], map_location="cpu", weights_only=True
        )
        features = shard["features"]
        if tuple(features.shape[1:]) != (197, 768):
            raise RuntimeError("patch cache shape drift")
        for row, dicom_id in enumerate(shard["dicom_ids"]):
            if dicom_id in index:
                raise RuntimeError(f"duplicate cached image: {dicom_id}")
            index[str(dicom_id)] = features[row]
    if len(index) != int(manifest["image_count"]):
        raise RuntimeError("patch cache inventory count mismatch")
    return index


def biomedclip_text_embeddings(findings: list[str]) -> dict[str, Tensor]:
    from open_clip.model import (
        CLIPTextCfg,
        CLIPVisionCfg,
        CustomTextCLIP,
    )
    from transformers import AutoTokenizer

    config = json.loads(
        (BIOMEDCLIP_ROOT / "open_clip_config.json").read_text(encoding="utf-8")
    )["model_cfg"]
    text_config = dict(config["text_cfg"])
    text_config["hf_model_pretrained"] = False
    model = CustomTextCLIP(
        embed_dim=int(config["embed_dim"]),
        vision_cfg=CLIPVisionCfg(**config["vision_cfg"]),
        text_cfg=CLIPTextCfg(**text_config),
    )
    state = torch.load(
        BIOMEDCLIP_ROOT / "open_clip_pytorch_model.bin",
        map_location="cpu",
        weights_only=True,
    )
    # Older Transformers persisted this deterministic buffer; current versions
    # recreate it and no longer register it in the state dict.
    state.pop("text.transformer.embeddings.position_ids", None)
    loaded = model.load_state_dict(state, strict=True)
    if loaded.missing_keys or loaded.unexpected_keys:
        raise RuntimeError("BiomedCLIP text tower strict load failed")
    model.eval().requires_grad_(False)
    tokenizer = AutoTokenizer.from_pretrained(
        BIOMEDCLIP_ROOT, local_files_only=True
    )
    encoded = tokenizer(
        findings,
        padding="max_length",
        truncation=True,
        max_length=256,
        return_tensors="pt",
    )["input_ids"]
    with torch.inference_mode():
        embeddings = model.encode_text(encoded, normalize=True).cpu()
    if tuple(embeddings.shape) != (len(findings), 512):
        raise RuntimeError("unexpected BiomedCLIP text embedding shape")
    return {
        finding: embeddings[index]
        for index, finding in enumerate(findings)
    }


def summarize_bundle(bundle: TokenBundle) -> Tensor:
    """Pool every token type with matched mean/max capacity."""

    bundle.validate()
    token_types = bundle.token_types
    if token_types.ndim == 2:
        token_types = token_types[0]
    means = []
    maxima = []
    fractions = []
    for token_type in range(6):
        type_mask = token_types.eq(token_type).view(1, -1)
        valid = bundle.valid_mask & type_mask
        denominator = valid.sum(dim=1, keepdim=True).clamp_min(1)
        means.append(
            (bundle.tokens * valid.unsqueeze(-1)).sum(dim=1) / denominator
        )
        masked = bundle.tokens.masked_fill(~valid.unsqueeze(-1), -torch.inf)
        maximum = masked.max(dim=1).values
        maximum = torch.where(
            torch.isfinite(maximum), maximum, torch.zeros_like(maximum)
        )
        maxima.append(maximum)
        fractions.append(
            valid.sum(dim=1, keepdim=True).to(bundle.tokens.dtype)
            / int(type_mask.sum())
        )
    return torch.cat((*means, *maxima, *fractions), dim=-1)


def build_prior_shuffle(records: list[dict[str, Any]]) -> list[int]:
    groups: dict[str, list[int]] = defaultdict(list)
    for index, row in enumerate(records):
        groups[str(row["finding_token"])].append(index)
    mapping = list(range(len(records)))
    for finding, indices in groups.items():
        ordered = sorted(
            indices,
            key=lambda index: stable_hash(
                "r33-prior-shuffle-v1",
                finding,
                records[index]["record_id"],
            ),
        )
        for position, index in enumerate(ordered):
            replacement = None
            for offset in range(1, len(ordered) + 1):
                candidate = ordered[(position + offset) % len(ordered)]
                if (
                    records[candidate]["patient_id"]
                    != records[index]["patient_id"]
                ):
                    replacement = candidate
                    break
            if replacement is None:
                raise RuntimeError(
                    f"finding {finding!r} lacks a cross-patient prior shuffle"
                )
            mapping[index] = replacement
    return mapping


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare R33 exact-64 train/dev token summaries"
    )
    parser.add_argument("--output", type=Path, default=OUTPUT_DEFAULT)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--batch-size", type=int, default=128)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.output.exists():
        raise FileExistsError(f"output must be fresh: {args.output}")
    device = torch.device(args.device)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but unavailable")
    all_records = json.loads(COHORT.read_text(encoding="utf-8"))
    records = [
        row for row in all_records if row["progression"] in LABELS
    ]
    if any(row["partition"] not in {"train", "dev"} for row in records):
        raise RuntimeError("R33 features contain a forbidden partition")
    if len({row["patient_id"] for row in records}) != 1874:
        raise RuntimeError("R33 persistent train+dev patient count drift")

    findings = sorted({str(row["finding_token"]) for row in records})
    text_embeddings = biomedclip_text_embeddings(findings)
    text_matrix = torch.stack(
        [text_embeddings[str(row["finding_token"])] for row in records]
    )
    del text_embeddings
    gc.collect()

    patch_index = load_patch_cache()
    missing = {
        str(row[field])
        for row in records
        for field in ("prior_dicom_id", "current_dicom_id")
        if str(row[field]) not in patch_index
    }
    if missing:
        raise RuntimeError(f"R33 patch cache misses {len(missing)} images")
    shuffle = build_prior_shuffle(records)
    image_projection = fixed_projection(768, 64, 20263301, device)
    query_projection = fixed_projection(512, 64, 20263302, device)
    builders = {}
    for seed in SEEDS:
        torch.manual_seed(seed)
        builder = HierarchicalTemporalTokenBuilder(64, 64)
        builder.eval().requires_grad_(False).to(device)
        builders[seed] = builder

    result: dict[str, dict[int, list[Tensor]]] = {
        "robust": {seed: [] for seed in SEEDS},
        "rich": {seed: [] for seed in SEEDS},
        "prior_shuffle_robust": {seed: [] for seed in SEEDS},
        "prior_shuffle_rich": {seed: [] for seed in SEEDS},
    }
    started = time.perf_counter()
    with torch.inference_mode():
        for start in range(0, len(records), args.batch_size):
            end = min(start + args.batch_size, len(records))
            batch = records[start:end]
            prior = torch.stack(
                [patch_index[str(row["prior_dicom_id"])] for row in batch]
            ).to(device=device, dtype=torch.float32)
            current = torch.stack(
                [patch_index[str(row["current_dicom_id"])] for row in batch]
            ).to(device=device, dtype=torch.float32)
            shuffled_prior = torch.stack(
                [
                    patch_index[
                        str(records[shuffle[index]]["prior_dicom_id"])
                    ]
                    for index in range(start, end)
                ]
            ).to(device=device, dtype=torch.float32)
            # Preserve CLS and pool 14x14 patches to a 7x7 grid.
            def reduce_images(features: Tensor) -> Tensor:
                cls = features[:, :1]
                patches = features[:, 1:].view(
                    features.shape[0], 14, 14, 768
                )
                patches = patches.view(
                    features.shape[0], 7, 2, 7, 2, 768
                ).mean(dim=(2, 4))
                reduced = torch.cat(
                    (cls, patches.reshape(features.shape[0], 49, 768)),
                    dim=1,
                )
                return reduced @ image_projection

            prior = reduce_images(prior)
            current = reduce_images(current)
            shuffled_prior = reduce_images(shuffled_prior)
            query = text_matrix[start:end].to(device) @ query_projection
            for seed, builder in builders.items():
                original = builder(prior, current, query)
                shifted = builder(shuffled_prior, current, query)
                result["robust"][seed].append(
                    summarize_bundle(original.robust).to(torch.float16).cpu()
                )
                result["rich"][seed].append(
                    summarize_bundle(original.rich).to(torch.float16).cpu()
                )
                result["prior_shuffle_robust"][seed].append(
                    summarize_bundle(shifted.robust).to(torch.float16).cpu()
                )
                result["prior_shuffle_rich"][seed].append(
                    summarize_bundle(shifted.rich).to(torch.float16).cpu()
                )

    packed = {
        name: {
            seed: torch.cat(chunks, dim=0)
            for seed, chunks in seeded.items()
        }
        for name, seeded in result.items()
    }
    feature_dim = next(iter(packed["robust"].values())).shape[1]
    if feature_dim != 774:
        raise RuntimeError(f"unexpected R33 summary width: {feature_dim}")
    output = {
        "schema": "visualvit.r33.token-features.v1",
        "status": "PASS_R33_FEATURE_PREPARATION",
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
        "feature_dim": feature_dim,
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
        "elapsed_seconds": time.perf_counter() - started,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    torch.save(output, args.output)
    summary = {
        key: value
        for key, value in output.items()
        if key not in {"records", "features"}
    }
    summary["record_count"] = len(records)
    summary["patient_count"] = len({row["patient_id"] for row in records})
    summary["output"] = str(args.output)
    summary["output_bytes"] = args.output.stat().st_size
    (args.output.parent / "feature_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
