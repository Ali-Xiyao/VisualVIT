from __future__ import annotations

# ruff: noqa: E402

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Iterable

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE / "src"))

import torch
import torch.nn.functional as F

from visualvit.cmcp import build_cmcp_matches, transition_examples


TRANSITION_ROOT = Path(
    r"H:\VisualVIT_runtime\050_routeD\r37_prta_cxr"
    r"\r37a_transitions_v4_1"
)
CACHE_ROOT = Path(
    r"H:\VisualVIT_runtime\050_routeD\r37_prta_cxr"
    r"\r37_block8_token_cache"
)
OUTPUT = Path(
    r"H:\VisualVIT_runtime\050_routeD\r37_prta_cxr"
    r"\r37_counterfactual_prior_index.json"
)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def load_current_dicom_ids(
    transition_root: Path,
) -> tuple[list[dict[str, Any]], set[str]]:
    rows = []
    for name in (
        "r37_pretrain_manifest.jsonl",
        "r37_internal_calibration_manifest.jsonl",
    ):
        rows.extend(read_jsonl(transition_root / name))
    current_ids = {
        str(row["current_dicom_id"])
        for row in rows
        if row.get("transition_supervision")
    }
    return rows, current_ids


def iter_cache_shards(cache_manifest: dict[str, Any]) -> Iterable[Path]:
    for shard in cache_manifest["shards"]:
        yield Path(shard["path"])


def pooled_current_embeddings(
    cache_root: Path, current_ids: set[str]
) -> dict[str, torch.Tensor]:
    manifest = json.loads(
        (cache_root / "cache_manifest.json").read_text(encoding="utf-8")
    )
    if manifest["status"] != "PASS_R37_BLOCK8_FORMAL_CACHE":
        raise ValueError("formal Block-8 cache has not passed")
    result: dict[str, torch.Tensor] = {}
    for path in iter_cache_shards(manifest):
        shard = torch.load(path, map_location="cpu", weights_only=True)
        ids = [str(value) for value in shard["dicom_ids"]]
        features = shard["features"]
        if tuple(features.shape[1:]) != (197, 768):
            raise ValueError(f"unexpected cache shape in {path}")
        for index, dicom_id in enumerate(ids):
            if dicom_id not in current_ids:
                continue
            pooled = features[index, 1:].to(torch.float32).mean(dim=0)
            result[dicom_id] = F.normalize(pooled, dim=0)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the current-matched counterfactual-prior index"
    )
    parser.add_argument(
        "--transition-root", type=Path, default=TRANSITION_ROOT
    )
    parser.add_argument("--cache-root", type=Path, default=CACHE_ROOT)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--chunk-size", type=int, default=512)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.output.exists():
        raise FileExistsError(f"CMCP output must be fresh: {args.output}")
    rows, current_ids = load_current_dicom_ids(args.transition_root)
    embeddings = pooled_current_embeddings(args.cache_root, current_ids)
    examples = transition_examples(rows)
    matches, matching_audit = build_cmcp_matches(
        examples, embeddings, chunk_size=args.chunk_size
    )
    partition_counts = {}
    for partition in ("pretrain", "internal_calibration"):
        dynamic = sum(
            item["label"] in {"Improved", "Worse", "New", "Resolved"}
            and item["partition"] == partition
            for item in examples
        )
        matched = sum(item["partition"] == partition for item in matches)
        partition_counts[partition] = {
            "dynamic_examples": dynamic,
            "matched_dynamic_examples": matched,
            "coverage": matched / dynamic if dynamic else 0.0,
        }
    coverage_pass = all(
        item["coverage"] >= 0.90 for item in partition_counts.values()
    )
    payload = {
        "schema": "visualvit.r37.cmcp-index.v1",
        "status": (
            "PASS_R37A_CMCP_COVERAGE"
            if coverage_pass
            else "STOP_R37A_CMCP_COVERAGE"
        ),
        "ruleset_version": "r37-report-transition-v4.1",
        "protected_outcomes_read": False,
        "target_outcome_passed_to_model": False,
        "matching_key": [
            "partition",
            "finding",
            "current_view",
            "different_patient",
            "different_transition_label",
        ],
        "ranking": "highest mean-pooled Block-8 current cosine",
        "partition_counts": partition_counts,
        "matching_audit": matching_audit,
        "matches": matches,
    }
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                key: value
                for key, value in payload.items()
                if key != "matches"
            },
            indent=2,
            sort_keys=True,
        )
    )
    print(f"RESULT={args.output}")
    return 0 if coverage_pass else 2


if __name__ == "__main__":
    raise SystemExit(main())
