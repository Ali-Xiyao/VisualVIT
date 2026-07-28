from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
from typing import Any, Callable

from visualvit.cmcp import transition_examples
from visualvit.prta import INVERSION_INDEX, PROGRESSION_LABELS


RESULT_SCHEMA = "visualvit.r37.prta-formal-training.v1"
RESULT_STATUS = "PASS_R37_PRTA_FORMAL_TRAINING"
CASE_STUDY_SCHEMA = "visualvit.r37.inversion-failure-case-study.v1"
CASE_STUDY_STATUS = "STOP_R37_INVERSION_CONSISTENCY"
INVERSION_MINIMUM = 0.90


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def formal_examples(transition_root: Path) -> list[dict[str, Any]]:
    rows = read_jsonl(
        transition_root / "r37_internal_calibration_manifest.jsonl"
    )
    pair_by_id = {str(row["pair_id"]): row for row in rows}
    examples = []
    for example in transition_examples(rows):
        pair = pair_by_id[str(example["pair_id"])]
        examples.append(
            {
                **example,
                "interval_days": int(pair["interval_days"]),
                "prior_view": str(pair["prior_view"]),
                "current_view": str(pair["current_view"]),
            }
        )
    return sorted(
        examples,
        key=lambda item: (
            str(item["patient_id"]),
            str(item["example_id"]),
        ),
    )


def validate_result(
    payload: dict[str, Any],
    *,
    seed: int,
    examples: list[dict[str, Any]],
) -> None:
    checks = {
        "schema": payload.get("schema") == RESULT_SCHEMA,
        "status": payload.get("status") == RESULT_STATUS,
        "formal": payload.get("formal") is True,
        "variant": payload.get("variant") == "A6",
        "seed": payload.get("seed") == seed,
        "protected_outcomes": payload.get("protected_outcomes_read") is False,
        "sealed_test": payload.get("sealed_test_read") is False,
        "gold_outcomes": payload.get("gold_outcomes_read") is False,
        "source_hashes": payload.get("source_hashes_recomputed") is False,
        "scientific_claim": payload.get("scientific_claim_allowed") is False,
    }
    calibration = payload.get("calibration", {})
    expected_patients = [str(item["patient_id"]) for item in examples]
    checks.update(
        {
            "row_count": calibration.get("examples") == len(examples),
            "patient_order": calibration.get("patient_ids")
            == expected_patients,
            "target_count": len(calibration.get("target_labels", ()))
            == len(examples),
            "forward_count": len(
                calibration.get("true_pair_predictions", ())
            )
            == len(examples),
            "inverted_count": len(
                calibration.get("inverted_predictions", ())
            )
            == len(examples),
        }
    )
    failed = sorted(name for name, passed in checks.items() if not passed)
    if failed:
        raise ValueError(
            f"seed {seed} failed case-study validation: {failed}"
        )


def group_consistency(
    *,
    examples: list[dict[str, Any]],
    targets: list[int],
    forward: list[int],
    inverted: list[int],
    key: Callable[[int], str],
) -> dict[str, dict[str, float | int]]:
    inverse = INVERSION_INDEX.tolist()
    counts: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for index in range(len(examples)):
        name = key(index)
        counts[name][1] += 1
        counts[name][0] += int(inverted[index] == inverse[forward[index]])
    return {
        name: {
            "rows": total,
            "consistent_rows": consistent,
            "inconsistent_rows": total - consistent,
            "consistency_rate": consistent / total,
        }
        for name, (consistent, total) in sorted(counts.items())
    }


def summarize_seed(
    payload: dict[str, Any],
    *,
    examples: list[dict[str, Any]],
) -> tuple[dict[str, Any], set[str]]:
    calibration = payload["calibration"]
    targets = [int(value) for value in calibration["target_labels"]]
    forward = [
        int(value) for value in calibration["true_pair_predictions"]
    ]
    inverted = [
        int(value) for value in calibration["inverted_predictions"]
    ]
    inverse = INVERSION_INDEX.tolist()
    consistency = [
        inverted[index] == inverse[forward[index]]
        for index in range(len(examples))
    ]
    failed_ids = {
        str(examples[index]["example_id"])
        for index, passed in enumerate(consistency)
        if not passed
    }
    expected_inverted_targets = [inverse[value] for value in targets]
    failure_transitions = Counter(
        (
            PROGRESSION_LABELS[inverse[forward[index]]],
            PROGRESSION_LABELS[inverted[index]],
        )
        for index, passed in enumerate(consistency)
        if not passed
    )
    groups = {
        "target_label": group_consistency(
            examples=examples,
            targets=targets,
            forward=forward,
            inverted=inverted,
            key=lambda index: PROGRESSION_LABELS[targets[index]],
        ),
        "forward_prediction": group_consistency(
            examples=examples,
            targets=targets,
            forward=forward,
            inverted=inverted,
            key=lambda index: PROGRESSION_LABELS[forward[index]],
        ),
        "finding": group_consistency(
            examples=examples,
            targets=targets,
            forward=forward,
            inverted=inverted,
            key=lambda index: str(examples[index]["finding"]),
        ),
        "view_pair": group_consistency(
            examples=examples,
            targets=targets,
            forward=forward,
            inverted=inverted,
            key=lambda index: (
                f"{examples[index]['prior_view']}"
                f"->{examples[index]['current_view']}"
            ),
        ),
    }
    rows = len(examples)
    summary = {
        "seed": int(payload["seed"]),
        "rows": rows,
        "patients": len({str(item["patient_id"]) for item in examples}),
        "consistent_rows": sum(consistency),
        "inconsistent_rows": len(failed_ids),
        "inversion_consistency_rate": sum(consistency) / rows,
        "forward_accuracy": sum(
            prediction == target
            for prediction, target in zip(forward, targets, strict=True)
        )
        / rows,
        "inverted_target_accuracy": sum(
            prediction == target
            for prediction, target in zip(
                inverted, expected_inverted_targets, strict=True
            )
        )
        / rows,
        "both_directions_correct_rate": sum(
            forward[index] == targets[index]
            and inverted[index] == expected_inverted_targets[index]
            for index in range(rows)
        )
        / rows,
        "groups": groups,
        "top_failure_transitions": [
            {
                "expected_from_forward": expected,
                "observed_inverted": observed,
                "rows": count,
            }
            for (expected, observed), count in failure_transitions.most_common(
                20
            )
        ],
    }
    return summary, failed_ids


def build_case_study(
    *,
    transition_root: Path,
    result_paths: dict[int, Path],
) -> dict[str, Any]:
    examples = formal_examples(transition_root)
    seed_summaries = []
    failed_by_seed = {}
    for seed, result_path in sorted(result_paths.items()):
        payload = read_json(result_path)
        validate_result(payload, seed=seed, examples=examples)
        summary, failed_ids = summarize_seed(payload, examples=examples)
        seed_summaries.append(summary)
        failed_by_seed[seed] = failed_ids
    if len(failed_by_seed) != 2:
        raise ValueError("R37 failure case study requires exactly two seeds")
    first, second = sorted(failed_by_seed)
    intersection = failed_by_seed[first] & failed_by_seed[second]
    union = failed_by_seed[first] | failed_by_seed[second]
    gate_passed = all(
        item["inversion_consistency_rate"] >= INVERSION_MINIMUM
        for item in seed_summaries
    )
    return {
        "schema": CASE_STUDY_SCHEMA,
        "status": (
            "PASS_R37_INVERSION_CONSISTENCY"
            if gate_passed
            else CASE_STUDY_STATUS
        ),
        "descriptive_only": True,
        "scientific_claim_allowed": False,
        "observed_calibration_reuse_allowed": False,
        "protected_outcomes_read": False,
        "sealed_test_read": False,
        "gold_outcomes_read": False,
        "source_hashes_recomputed": False,
        "per_shard_hashes_computed": False,
        "inversion_consistency_minimum": INVERSION_MINIMUM,
        "rows": len(examples),
        "patients": len({str(item["patient_id"]) for item in examples}),
        "seeds": seed_summaries,
        "cross_seed_failure_overlap": {
            "seed_pair": [first, second],
            "intersection_rows": len(intersection),
            "union_rows": len(union),
            "jaccard": len(intersection) / len(union) if union else 1.0,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze the frozen two-seed R37 inversion failure"
    )
    parser.add_argument("--transition-root", type=Path, required=True)
    parser.add_argument("--seed-17-result", type=Path, required=True)
    parser.add_argument("--seed-29-result", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.output.exists():
        raise FileExistsError(f"case-study output must be fresh: {args.output}")
    payload = build_case_study(
        transition_root=args.transition_root,
        result_paths={
            17: args.seed_17_result,
            29: args.seed_29_result,
        },
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(args.output)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["status"] == CASE_STUDY_STATUS else 1


if __name__ == "__main__":
    raise SystemExit(main())
