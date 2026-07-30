from __future__ import annotations

# ruff: noqa: E402

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import sys
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE))
sys.path.insert(0, str(WORKSPACE / "src"))

import torch
from torch import Tensor

from scripts.cache_prta_gen_r40a_tokens import read_json, read_jsonl
from scripts.run_prta_gen_r40a_probe import RESULT_STATUS, TOKEN_STATUS


CASE_SCHEMA = "visualvit.prta-gen.r40a-failure-case-study.v1"
CASE_STATUS = "DESCRIPTIVE_PRTA_GEN_R40A_FAILURE_CASE_STUDY"
SEEDS = (17, 29, 43)
REGIONS = {
    "state": (0, 20),
    "transition": (20, 40),
    "relation": (40, 60),
    "reserve": (60, 64),
}


def validate_progression_results(
    result_paths: dict[int, Path],
) -> list[dict[str, Any]]:
    if tuple(sorted(result_paths)) != SEEDS:
        raise ValueError("case study requires progression Seeds 17/29/43")
    results = [read_json(result_paths[seed]) for seed in SEEDS]
    reference = results[0]
    for seed, result in zip(SEEDS, results, strict=True):
        checks = {
            "schema": result.get("schema")
            == "visualvit.prta-gen.r40a-probe-seed.v1",
            "status": result.get("status") == RESULT_STATUS,
            "field": result.get("field") == "progression",
            "seed": int(result.get("seed", -1)) == seed,
            "field_locked": result.get("field_generation_unlocked") is False,
            "protected_300": result.get("protected_300_dev_read") is False,
            "revealed_483": result.get("revealed_483_test_read") is False,
            "gold": result.get("gold_outcomes_read") is False,
            "old_r40": result.get("old_r40_component_queue_resumed") is False,
            "claim": result.get("scientific_claim_allowed") is False,
        }
        failed = sorted(name for name, passed in checks.items() if not passed)
        if failed:
            raise PermissionError(
                f"Seed {seed} case-study firewall drift: {failed}"
            )
        if any(
            result[key] != reference[key]
            for key in ("classes", "example_ids", "patient_ids", "targets")
        ):
            raise ValueError("case-study result alignment drift")
    return results


def align_targets(
    example_ids: list[str], target_path: Path
) -> list[dict[str, Any]]:
    rows = read_jsonl(target_path)
    by_id = {str(row["example_id"]): row for row in rows}
    if len(by_id) != len(rows) or set(by_id) != set(example_ids):
        raise ValueError("case-study target/example registry drift")
    return [by_id[example_id] for example_id in example_ids]


def prediction_category(
    target: int, true_prediction: int, shuffled_prediction: int
) -> str:
    true_correct = true_prediction == target
    shuffled_correct = shuffled_prediction == target
    if true_correct and not shuffled_correct:
        return "true_sensitive"
    if shuffled_correct and not true_correct:
        return "shuffle_favored"
    if true_correct:
        return "both_correct"
    return "both_wrong"


def token_region_rms(true_tokens: Tensor, shuffled_tokens: Tensor) -> Tensor:
    if true_tokens.shape != shuffled_tokens.shape:
        raise ValueError("true/shuffled token shapes differ")
    if true_tokens.ndim != 3 or true_tokens.shape[1:] != (64, 768):
        raise ValueError("case study requires exact [rows,64,768] tokens")
    difference = true_tokens.float() - shuffled_tokens.float()
    return torch.stack(
        [
            difference[:, start:end].square().mean(dim=(1, 2)).sqrt()
            for start, end in REGIONS.values()
        ],
        dim=1,
    )


def load_token_distances(
    index_path: Path, expected_example_ids: list[str]
) -> dict[str, dict[str, float]]:
    index = read_json(index_path)
    checks = {
        "status": index.get("status") == TOKEN_STATUS,
        "formal": index.get("smoke_rows") == 0,
        "labels": index.get("labels_in_cache") is False,
        "sentences": index.get("sentences_in_cache") is False,
        "protected_300": index.get("protected_300_dev_read") is False,
        "revealed_483": index.get("revealed_483_test_read") is False,
        "gold": index.get("gold_outcomes_read") is False,
    }
    failed = sorted(name for name, passed in checks.items() if not passed)
    if failed:
        raise PermissionError(f"token-cache case-study drift: {failed}")
    distances: dict[str, dict[str, float]] = {}
    observed_order: list[str] = []
    for shard_entry in index["shards"]:
        shard = torch.load(
            shard_entry["path"], map_location="cpu", weights_only=True
        )
        shard_ids = [str(value) for value in shard["example_ids"]]
        region_rms = token_region_rms(
            shard["true_tokens"], shard["shuffled_tokens"]
        )
        for row_index, example_id in enumerate(shard_ids):
            observed_order.append(example_id)
            distances[example_id] = {
                region: float(region_rms[row_index, region_index].item())
                for region_index, region in enumerate(REGIONS)
            }
    if observed_order != expected_example_ids:
        raise ValueError("case-study token/result row-order drift")
    return distances


def group_summary(
    rows: list[dict[str, Any]], categories: list[str], key: str
) -> dict[str, dict[str, int | float]]:
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    for row, category in zip(rows, categories, strict=True):
        counts[str(row[key])][category] += 1
    result = {}
    for value, counter in sorted(counts.items()):
        total = sum(counter.values())
        result[value] = {
            "rows": total,
            **{
                category: int(counter[category])
                for category in (
                    "true_sensitive",
                    "shuffle_favored",
                    "both_correct",
                    "both_wrong",
                )
            },
            "net_true_sensitive_rate": (
                counter["true_sensitive"] - counter["shuffle_favored"]
            )
            / total,
        }
    return result


def summarize_distances(
    example_ids: list[str],
    categories: list[str],
    distances: dict[str, dict[str, float]],
) -> dict[str, dict[str, float | int]]:
    values: dict[str, dict[str, list[float]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for example_id, category in zip(example_ids, categories, strict=True):
        for region, value in distances[example_id].items():
            values[category][region].append(value)
    return {
        category: {
            "rows": len(next(iter(region_values.values()))),
            **{
                f"{region}_rms_mean": sum(region_numbers)
                / len(region_numbers)
                for region, region_numbers in region_values.items()
            },
        }
        for category, region_values in sorted(values.items())
    }


def select_cases(
    *,
    rows: list[dict[str, Any]],
    results: list[dict[str, Any]],
    distances: dict[str, dict[str, float]],
    per_pattern: int,
) -> list[dict[str, Any]]:
    classes = [str(value) for value in results[0]["classes"]]
    candidates: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for index, row in enumerate(rows):
        target = int(results[0]["targets"][index])
        seed_categories = []
        seed_predictions = {}
        for seed, result in zip(SEEDS, results, strict=True):
            true_prediction = int(
                result["predictions"]["true_pair"][index]
            )
            shuffled_prediction = int(
                result["predictions"]["prior_shuffle"][index]
            )
            seed_categories.append(
                prediction_category(
                    target, true_prediction, shuffled_prediction
                )
            )
            seed_predictions[str(seed)] = {
                "true_pair": classes[true_prediction],
                "prior_shuffle": classes[shuffled_prediction],
            }
        patterns = []
        if all(value == "true_sensitive" for value in seed_categories):
            patterns.append("persistent_true_sensitive")
        if all(value == "shuffle_favored" for value in seed_categories):
            patterns.append("persistent_shuffle_favored")
        if seed_categories[0] == "true_sensitive":
            patterns.append("seed17_true_sensitive")
        if seed_categories[0] == "shuffle_favored":
            patterns.append("seed17_shuffle_favored")
        for pattern in patterns:
            candidates[pattern].append(
                {
                    "example_id": str(row["example_id"]),
                    "finding": str(row["finding"]),
                    "progression": str(row["progression"]),
                    "quality_tier": str(row["quality_tier"]),
                    "seed_predictions": seed_predictions,
                    "token_true_vs_shuffle_rms": distances[
                        str(row["example_id"])
                    ],
                }
            )
    selected = []
    for pattern, items in sorted(candidates.items()):
        reverse = pattern.endswith("true_sensitive")
        items.sort(
            key=lambda item: (
                item["token_true_vs_shuffle_rms"]["transition"],
                item["example_id"],
            ),
            reverse=reverse,
        )
        for item in items[:per_pattern]:
            selected.append({"pattern": pattern, **item})
    return selected


def build_case_study(
    *,
    result_paths: dict[int, Path],
    target_path: Path,
    token_index_path: Path,
    per_pattern: int = 10,
) -> dict[str, Any]:
    results = validate_progression_results(result_paths)
    example_ids = [str(value) for value in results[0]["example_ids"]]
    rows = align_targets(example_ids, target_path)
    if [str(row["patient_id"]) for row in rows] != [
        str(value) for value in results[0]["patient_ids"]
    ]:
        raise ValueError("case-study target patient-order drift")
    distances = load_token_distances(token_index_path, example_ids)
    seed_summaries = []
    seed_categories: dict[int, list[str]] = {}
    for seed, result in zip(SEEDS, results, strict=True):
        categories = [
            prediction_category(
                int(target),
                int(true_prediction),
                int(shuffled_prediction),
            )
            for target, true_prediction, shuffled_prediction in zip(
                result["targets"],
                result["predictions"]["true_pair"],
                result["predictions"]["prior_shuffle"],
                strict=True,
            )
        ]
        seed_categories[seed] = categories
        seed_summaries.append(
            {
                "seed": seed,
                "category_counts": dict(sorted(Counter(categories).items())),
                "by_progression": group_summary(
                    rows, categories, "progression"
                ),
                "by_finding": group_summary(rows, categories, "finding"),
                "by_quality_tier": group_summary(
                    rows, categories, "quality_tier"
                ),
                "token_distance_by_category": summarize_distances(
                    example_ids, categories, distances
                ),
            }
        )
    cross_seed_patterns = Counter()
    for index in range(len(rows)):
        pattern = tuple(seed_categories[seed][index] for seed in SEEDS)
        cross_seed_patterns["|".join(pattern)] += 1
    return {
        "schema": CASE_SCHEMA,
        "status": CASE_STATUS,
        "descriptive_only": True,
        "closed_r40a_result_unchanged": True,
        "observed_development_reuse_for_selection_allowed": False,
        "rows": len(rows),
        "patients": len({str(row["patient_id"]) for row in rows}),
        "seeds": list(SEEDS),
        "seed_summaries": seed_summaries,
        "cross_seed_category_patterns": dict(
            cross_seed_patterns.most_common()
        ),
        "anonymized_cases": select_cases(
            rows=rows,
            results=results,
            distances=distances,
            per_pattern=per_pattern,
        ),
        "protected_300_dev_read": False,
        "revealed_483_test_read": False,
        "gold_outcomes_read": False,
        "source_hashes_recomputed": False,
        "token_hashes_recomputed": False,
        "scientific_claim_allowed": False,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze closed PRTA-Gen R40A progression failures"
    )
    parser.add_argument("--seed-17-result", type=Path, required=True)
    parser.add_argument("--seed-29-result", type=Path, required=True)
    parser.add_argument("--seed-43-result", type=Path, required=True)
    parser.add_argument("--target-path", type=Path, required=True)
    parser.add_argument("--token-index", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--per-pattern", type=int, default=10)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.output.exists():
        raise FileExistsError(
            f"PRTA-Gen case-study output must be fresh: {args.output}"
        )
    payload = build_case_study(
        result_paths={
            17: args.seed_17_result,
            29: args.seed_29_result,
            43: args.seed_43_result,
        },
        target_path=args.target_path,
        token_index_path=args.token_index,
        per_pattern=args.per_pattern,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(args.output)
    print(
        json.dumps(
            {
                "status": payload["status"],
                "rows": payload["rows"],
                "patients": payload["patients"],
                "anonymized_cases": len(payload["anonymized_cases"]),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
