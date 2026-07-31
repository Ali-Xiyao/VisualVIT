from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


CASE_SCHEMA = "visualvit.prta-gen.r41a-failure-case-study.v1"
CASE_STATUS = "DESCRIPTIVE_PRTA_GEN_R41A_FAILURE_CASE_STUDY"
RESULT_SCHEMA = "visualvit.prta-gen.r41a-arm-result.v1"
RESULT_STATUS = "PASS_PRTA_GEN_R41A_ARM_EVALUATION"
ROSTER_SCHEMA = "visualvit.prta-gen.r41a-roster.v1"
ROSTER_STATUS = "PASS_PRTA_GEN_R41A_ROSTER_SUPPORT"
PROTOCOL_ID = "prta-gen-r41a-progression-sft-v1"
STUDY_TIER = "bounded_internal_progression_only_sft_survival"
SEEDS = (17, 29, 43)
MODEL_ARMS = ("g0_projector_only", "g1_attention_lora")
EVALUATION_ARMS = (
    "true_pair",
    "current_only",
    "query_only",
    "prior_shuffle",
)
EXPECTED_ROWS = 125
EXPECTED_TRAIN_ROWS = 375
EXPECTED_CLASSES = ("Stable", "Improved", "Worse", "New", "Resolved")
FORBIDDEN_OUTPUT_KEYS = {"example_id", "patient_id"}


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected a JSON object: {path}")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _validate_prediction(
    predictions: Any, *, classes: list[str], label: str
) -> list[int]:
    _require(
        isinstance(predictions, list) and len(predictions) == EXPECTED_ROWS,
        f"{label} must contain {EXPECTED_ROWS} predictions",
    )
    normalized = [int(value) for value in predictions]
    _require(
        all(0 <= value < len(classes) for value in normalized),
        f"{label} contains an out-of-registry class index",
    )
    return normalized


def classification_metrics(
    targets: list[int], predictions: list[int], classes: list[str]
) -> dict[str, Any]:
    _require(len(targets) == len(predictions), "metric length mismatch")
    recalls: dict[str, float] = {}
    f1_values: list[float] = []
    for class_index, class_name in enumerate(classes):
        true_positive = sum(
            target == class_index and prediction == class_index
            for target, prediction in zip(targets, predictions, strict=True)
        )
        false_negative = sum(
            target == class_index and prediction != class_index
            for target, prediction in zip(targets, predictions, strict=True)
        )
        false_positive = sum(
            target != class_index and prediction == class_index
            for target, prediction in zip(targets, predictions, strict=True)
        )
        support = true_positive + false_negative
        recall = true_positive / support if support else 0.0
        precision_denominator = true_positive + false_positive
        precision = (
            true_positive / precision_denominator
            if precision_denominator
            else 0.0
        )
        f1 = (
            2.0 * precision * recall / (precision + recall)
            if precision + recall
            else 0.0
        )
        recalls[class_name] = recall
        f1_values.append(f1)
    return {
        "progression_accuracy": sum(
            target == prediction
            for target, prediction in zip(targets, predictions, strict=True)
        )
        / len(targets),
        "macro_f1": sum(f1_values) / len(f1_values),
        "per_class_recall": recalls,
    }


def _assert_close(observed: float, expected: float, label: str) -> None:
    if abs(observed - expected) > 1e-12:
        raise ValueError(
            f"{label} metric drift: observed={observed}, expected={expected}"
        )


def validate_results(
    result_paths: dict[tuple[int, str], Path],
) -> tuple[dict[tuple[int, str], dict[str, Any]], list[str], list[int]]:
    expected = {
        (seed, model_arm) for seed in SEEDS for model_arm in MODEL_ARMS
    }
    _require(
        set(result_paths) == expected,
        "case study requires exactly Seeds 17/29/43 x G0/G1",
    )
    results = {
        key: read_json(result_paths[key])
        for key in sorted(result_paths, key=lambda value: (value[0], value[1]))
    }
    reference: dict[str, Any] | None = None
    for (seed, model_arm), result in results.items():
        checks = {
            "schema": result.get("schema") == RESULT_SCHEMA,
            "status": result.get("status") == RESULT_STATUS,
            "protocol": result.get("protocol_id") == PROTOCOL_ID,
            "study_tier": result.get("study_tier") == STUDY_TIER,
            "seed": int(result.get("seed", -1)) == seed,
            "model_arm": result.get("model_arm") == model_arm,
            "development_rows": result.get("development_rows")
            == EXPECTED_ROWS,
            "development_patients": result.get("development_patients")
            == EXPECTED_ROWS,
            "training_rows": result.get("training_rows")
            == EXPECTED_TRAIN_ROWS,
            "optimizer_updates": result.get("optimizer_updates") == 36,
            "exact64": result.get("exact64_tokens_used") is True,
            "pixels": result.get("pixel_inputs_used") is False,
            "protected_300": result.get("protected_300_dev_read") is False,
            "revealed_483": result.get("revealed_483_test_read") is False,
            "gold": result.get("gold_outcomes_read") is False,
            "external": result.get("external_outcomes_read") is False,
            "r42": result.get("r42_unlocked") is False,
            "qwen_survival": result.get(
                "qwen_free_generation_survival_unlocked"
            )
            is False,
            "scientific_claim": result.get("scientific_claim_allowed")
            is False,
        }
        failed = sorted(name for name, passed in checks.items() if not passed)
        if failed:
            raise PermissionError(
                f"R41A result firewall/schema drift for {seed}/{model_arm}: "
                f"{failed}"
            )
        classes = [str(value) for value in result.get("classes", [])]
        _require(
            tuple(classes) == EXPECTED_CLASSES,
            f"class registry drift for {seed}/{model_arm}",
        )
        targets = [int(value) for value in result.get("targets", [])]
        _require(
            len(targets) == EXPECTED_ROWS
            and all(0 <= value < len(classes) for value in targets),
            f"target registry drift for {seed}/{model_arm}",
        )
        example_ids = [str(value) for value in result.get(
            "development_example_ids", []
        )]
        patient_ids = [str(value) for value in result.get(
            "development_patient_ids", []
        )]
        _require(
            len(example_ids) == EXPECTED_ROWS
            and len(set(example_ids)) == EXPECTED_ROWS,
            f"development example registry drift for {seed}/{model_arm}",
        )
        _require(
            len(patient_ids) == EXPECTED_ROWS
            and len(set(patient_ids)) == EXPECTED_ROWS,
            f"development patient registry drift for {seed}/{model_arm}",
        )
        if reference is None:
            reference = result
        else:
            for field in (
                "classes",
                "targets",
                "development_example_ids",
                "development_patient_ids",
            ):
                _require(
                    result[field] == reference[field],
                    f"cross-result alignment drift in {field}",
                )
        predictions = result.get("predictions")
        _require(
            isinstance(predictions, dict)
            and set(predictions) == set(EVALUATION_ARMS),
            f"evaluation-arm drift for {seed}/{model_arm}",
        )
        metrics = result.get("metrics")
        _require(
            isinstance(metrics, dict)
            and set(metrics) == set(EVALUATION_ARMS),
            f"metric-arm drift for {seed}/{model_arm}",
        )
        for evaluation_arm in EVALUATION_ARMS:
            arm_predictions = _validate_prediction(
                predictions[evaluation_arm],
                classes=classes,
                label=f"{seed}/{model_arm}/{evaluation_arm}",
            )
            recomputed = classification_metrics(
                targets, arm_predictions, classes
            )
            recorded = metrics[evaluation_arm]
            _require(
                recorded.get("row_count") == EXPECTED_ROWS,
                f"row-count metric drift for {seed}/{model_arm}/"
                f"{evaluation_arm}",
            )
            _require(
                recorded.get("schema_validity") == 1.0
                and recorded.get("finding_echo_accuracy") == 1.0
                and recorded.get("invalid_or_wrong_finding_predictions") == 0,
                f"schema/finding metric drift for {seed}/{model_arm}/"
                f"{evaluation_arm}",
            )
            for metric_name in ("progression_accuracy", "macro_f1"):
                _assert_close(
                    float(recorded[metric_name]),
                    float(recomputed[metric_name]),
                    f"{seed}/{model_arm}/{evaluation_arm}/{metric_name}",
                )
            for class_name in classes:
                _assert_close(
                    float(recorded["per_class_recall"][class_name]),
                    float(recomputed["per_class_recall"][class_name]),
                    f"{seed}/{model_arm}/{evaluation_arm}/recall/"
                    f"{class_name}",
                )
    assert reference is not None
    return (
        results,
        [str(value) for value in reference["classes"]],
        [int(value) for value in reference["targets"]],
    )


def validate_roster(
    *,
    roster_path: Path,
    expected_sha256: str,
    reference_result: dict[str, Any],
) -> list[dict[str, Any]]:
    actual_sha256 = sha256_file(roster_path)
    _require(
        actual_sha256 == expected_sha256.upper(),
        "immutable R41A roster SHA-256 drift",
    )
    roster = read_json(roster_path)
    checks = {
        "schema": roster.get("schema") == ROSTER_SCHEMA,
        "status": roster.get("status") == ROSTER_STATUS,
        "protocol": roster.get("protocol_id") == PROTOCOL_ID,
        "one_row_per_patient": roster.get("one_row_per_patient") is True,
        "disjoint": roster.get("patient_sets_disjoint") is True,
        "resplit": roster.get("resplit_allowed") is False,
        "development_outcomes": roster.get("development_outcomes_read")
        is False,
        "protected_300": roster.get("protected_300_dev_read") is False,
        "revealed_483": roster.get("revealed_483_test_read") is False,
        "gold": roster.get("gold_outcomes_read") is False,
        "external": roster.get("external_outcomes_read") is False,
        "r40c_selection": roster.get(
            "r40c_outcomes_used_for_roster_selection"
        )
        is False,
        "scientific_claim": roster.get("scientific_claim_allowed") is False,
    }
    failed = sorted(name for name, passed in checks.items() if not passed)
    if failed:
        raise PermissionError(f"R41A roster firewall/schema drift: {failed}")
    partitions = roster.get("partitions")
    _require(isinstance(partitions, dict), "R41A roster partitions missing")
    train_rows = partitions.get("train", {}).get("rows")
    development_rows = partitions.get("development", {}).get("rows")
    _require(
        isinstance(train_rows, list)
        and len(train_rows) == EXPECTED_TRAIN_ROWS,
        "R41A training roster count drift",
    )
    _require(
        isinstance(development_rows, list)
        and len(development_rows) == EXPECTED_ROWS,
        "R41A development roster count drift",
    )
    _require(
        [str(row["example_id"]) for row in development_rows]
        == [
            str(value)
            for value in reference_result["development_example_ids"]
        ],
        "R41A roster/result example-order drift",
    )
    _require(
        [str(row["patient_id"]) for row in development_rows]
        == [
            str(value)
            for value in reference_result["development_patient_ids"]
        ],
        "R41A roster/result patient-order drift",
    )
    _require(
        [str(row["progression"]) for row in development_rows]
        == [
            reference_result["classes"][int(value)]
            for value in reference_result["targets"]
        ],
        "R41A roster/result target-order drift",
    )
    return development_rows


def confusion_rows(
    targets: list[int], predictions: list[int], classes: list[str]
) -> list[dict[str, Any]]:
    counts: Counter[tuple[str, str]] = Counter(
        (classes[target], classes[prediction])
        for target, prediction in zip(targets, predictions, strict=True)
    )
    return [
        {
            "target": target_name,
            "prediction": prediction_name,
            "count": counts[(target_name, prediction_name)],
        }
        for target_name in classes
        for prediction_name in classes
    ]


def correctness_category(
    target: int, first_prediction: int, second_prediction: int
) -> str:
    first_correct = first_prediction == target
    second_correct = second_prediction == target
    if first_correct and second_correct:
        return "both_correct"
    if first_correct:
        return "first_only_correct"
    if second_correct:
        return "second_only_correct"
    return "both_wrong"


def grouped_category_counts(
    rows: list[dict[str, Any]],
    categories: list[str],
    key: str,
) -> dict[str, dict[str, int]]:
    grouped: dict[str, Counter[str]] = defaultdict(Counter)
    for row, category in zip(rows, categories, strict=True):
        grouped[str(row[key])][category] += 1
    return {
        value: {
            "rows": sum(counter.values()),
            **dict(sorted(counter.items())),
        }
        for value, counter in sorted(grouped.items())
    }


def accuracy_by_group(
    *,
    rows: list[dict[str, Any]],
    targets: list[int],
    predictions: list[int],
    key: str,
) -> dict[str, dict[str, float | int]]:
    totals: Counter[str] = Counter()
    correct: Counter[str] = Counter()
    for row, target, prediction in zip(
        rows, targets, predictions, strict=True
    ):
        value = str(row[key])
        totals[value] += 1
        correct[value] += target == prediction
    return {
        value: {
            "rows": totals[value],
            "correct": correct[value],
            "accuracy": correct[value] / totals[value],
        }
        for value in sorted(totals)
    }


def control_category(
    target: int, true_prediction: int, control_prediction: int
) -> str:
    true_correct = true_prediction == target
    control_correct = control_prediction == target
    if true_correct and not control_correct:
        return "true_sensitive"
    if control_correct and not true_correct:
        return "control_favored"
    if true_correct:
        return "both_correct"
    return "both_wrong"


def _case_patterns(
    *,
    index: int,
    target: int,
    results: dict[tuple[int, str], dict[str, Any]],
) -> list[str]:
    g0_true = [
        int(results[(seed, "g0_projector_only")]["predictions"]["true_pair"][
            index
        ])
        for seed in SEEDS
    ]
    g1_true = [
        int(results[(seed, "g1_attention_lora")]["predictions"]["true_pair"][
            index
        ])
        for seed in SEEDS
    ]
    g1_shuffle = [
        int(
            results[(seed, "g1_attention_lora")]["predictions"][
                "prior_shuffle"
            ][index]
        )
        for seed in SEEDS
    ]
    patterns = []
    if all(value != target for value in g1_true):
        patterns.append("persistent_g1_true_pair_error")
    if all(
        g0_prediction == target and g1_prediction != target
        for g0_prediction, g1_prediction in zip(
            g0_true, g1_true, strict=True
        )
    ):
        patterns.append("persistent_g0_correct_g1_wrong")
    if all(
        g0_prediction != target and g1_prediction == target
        for g0_prediction, g1_prediction in zip(
            g0_true, g1_true, strict=True
        )
    ):
        patterns.append("persistent_g1_recovers_over_g0")
    if all(
        true_prediction == target and shuffle_prediction != target
        for true_prediction, shuffle_prediction in zip(
            g1_true, g1_shuffle, strict=True
        )
    ):
        patterns.append("persistent_g1_true_sensitive_vs_shuffle")
    if target == EXPECTED_CLASSES.index("Worse") and all(
        value != target for value in g1_true
    ):
        patterns.append("persistent_worse_g1_error")
    return patterns


def select_anonymized_cases(
    *,
    rows: list[dict[str, Any]],
    targets: list[int],
    classes: list[str],
    results: dict[tuple[int, str], dict[str, Any]],
    per_pattern: int,
) -> list[dict[str, Any]]:
    candidates: dict[str, list[int]] = defaultdict(list)
    for index, target in enumerate(targets):
        for pattern in _case_patterns(
            index=index, target=target, results=results
        ):
            candidates[pattern].append(index)
    selected: list[dict[str, Any]] = []
    case_number = 0
    for pattern in sorted(candidates):
        for index in candidates[pattern][:per_pattern]:
            case_number += 1
            target = targets[index]
            seed_predictions = {}
            for seed in SEEDS:
                seed_predictions[str(seed)] = {}
                for model_arm in MODEL_ARMS:
                    predictions = results[(seed, model_arm)]["predictions"]
                    seed_predictions[str(seed)][model_arm] = {
                        evaluation_arm: classes[
                            int(predictions[evaluation_arm][index])
                        ]
                        for evaluation_arm in EVALUATION_ARMS
                    }
            selected.append(
                {
                    "case_id": f"CASE-{case_number:03d}",
                    "pattern": pattern,
                    "finding": str(rows[index]["finding"]),
                    "target": classes[target],
                    "seed_predictions": seed_predictions,
                    "descriptive_only": True,
                    "reuse_for_selection_allowed": False,
                }
            )
    return selected


def _iter_keys(value: Any) -> Iterable[str]:
    if isinstance(value, dict):
        for key, item in value.items():
            yield str(key)
            yield from _iter_keys(item)
    elif isinstance(value, list):
        for item in value:
            yield from _iter_keys(item)


def build_case_study(
    *,
    result_paths: dict[tuple[int, str], Path],
    roster_path: Path,
    roster_sha256: str,
    per_pattern: int = 4,
) -> dict[str, Any]:
    _require(per_pattern > 0, "per_pattern must be positive")
    results, classes, targets = validate_results(result_paths)
    reference = results[(17, "g0_projector_only")]
    rows = validate_roster(
        roster_path=roster_path,
        expected_sha256=roster_sha256,
        reference_result=reference,
    )
    seed_summaries = []
    for seed in SEEDS:
        model_summaries = {}
        for model_arm in MODEL_ARMS:
            result = results[(seed, model_arm)]
            evaluation_summaries = {}
            for evaluation_arm in EVALUATION_ARMS:
                predictions = [
                    int(value)
                    for value in result["predictions"][evaluation_arm]
                ]
                evaluation_summaries[evaluation_arm] = {
                    "metrics": result["metrics"][evaluation_arm],
                    "prediction_distribution": dict(
                        sorted(
                            Counter(
                                classes[prediction]
                                for prediction in predictions
                            ).items()
                        )
                    ),
                    "confusion": confusion_rows(
                        targets, predictions, classes
                    ),
                    "accuracy_by_finding": accuracy_by_group(
                        rows=rows,
                        targets=targets,
                        predictions=predictions,
                        key="finding",
                    ),
                }
            model_summaries[model_arm] = evaluation_summaries
        g0_true = [
            int(value)
            for value in results[(seed, "g0_projector_only")][
                "predictions"
            ]["true_pair"]
        ]
        g1_result = results[(seed, "g1_attention_lora")]
        g1_true = [
            int(value) for value in g1_result["predictions"]["true_pair"]
        ]
        migration_categories = [
            correctness_category(target, g0_prediction, g1_prediction)
            for target, g0_prediction, g1_prediction in zip(
                targets, g0_true, g1_true, strict=True
            )
        ]
        controls = {}
        for control_arm in ("current_only", "query_only", "prior_shuffle"):
            categories = [
                control_category(target, true_prediction, control_prediction)
                for target, true_prediction, control_prediction in zip(
                    targets,
                    g1_true,
                    g1_result["predictions"][control_arm],
                    strict=True,
                )
            ]
            controls[control_arm] = {
                "category_counts": dict(
                    sorted(Counter(categories).items())
                ),
                "by_target": grouped_category_counts(
                    [
                        {**row, "target": classes[target]}
                        for row, target in zip(rows, targets, strict=True)
                    ],
                    categories,
                    "target",
                ),
                "by_finding": grouped_category_counts(
                    rows, categories, "finding"
                ),
            }
        seed_summaries.append(
            {
                "seed": seed,
                "models": model_summaries,
                "g0_to_g1_true_pair_migration": {
                    "category_counts": dict(
                        sorted(Counter(migration_categories).items())
                    ),
                    "by_target": grouped_category_counts(
                        [
                            {**row, "target": classes[target]}
                            for row, target in zip(rows, targets, strict=True)
                        ],
                        migration_categories,
                        "target",
                    ),
                    "by_finding": grouped_category_counts(
                        rows, migration_categories, "finding"
                    ),
                },
                "g1_true_pair_vs_controls": controls,
            }
        )
    cross_seed = Counter()
    for index, target in enumerate(targets):
        predictions = [
            int(
                results[(seed, "g1_attention_lora")]["predictions"][
                    "true_pair"
                ][index]
            )
            for seed in SEEDS
        ]
        correct = [prediction == target for prediction in predictions]
        if all(correct):
            cross_seed["unanimous_correct"] += 1
        elif not any(correct) and len(set(predictions)) == 1:
            cross_seed["unanimous_same_wrong"] += 1
        elif any(correct):
            cross_seed["mixed_with_some_correct"] += 1
        else:
            cross_seed["mixed_all_wrong"] += 1
    source_hashes = {
        f"seed_{seed}_{model_arm}_result_sha256": sha256_file(
            result_paths[(seed, model_arm)]
        )
        for seed in SEEDS
        for model_arm in MODEL_ARMS
    }
    payload = {
        "schema": CASE_SCHEMA,
        "status": CASE_STATUS,
        "protocol_id": PROTOCOL_ID,
        "study_tier": STUDY_TIER,
        "descriptive_only": True,
        "closed_r41a_result_unchanged": True,
        "observed_development_reuse_for_selection_allowed": False,
        "new_training_started": False,
        "rows": EXPECTED_ROWS,
        "patients": EXPECTED_ROWS,
        "seeds": list(SEEDS),
        "classes": classes,
        "seed_summaries": seed_summaries,
        "cross_seed_g1_true_pair_patterns": dict(sorted(cross_seed.items())),
        "anonymized_cases": select_anonymized_cases(
            rows=rows,
            targets=targets,
            classes=classes,
            results=results,
            per_pattern=per_pattern,
        ),
        "source_hashes": {
            "roster_sha256": sha256_file(roster_path),
            **source_hashes,
        },
        "protected_300_dev_read": False,
        "revealed_483_test_read": False,
        "gold_outcomes_read": False,
        "external_outcomes_read": False,
        "r42_started": False,
        "r43_started": False,
        "source_hashes_recomputed": True,
        "scientific_claim_allowed": False,
    }
    leaked_keys = FORBIDDEN_OUTPUT_KEYS.intersection(_iter_keys(payload))
    if leaked_keys:
        raise AssertionError(
            f"identity-bearing keys escaped case study: {sorted(leaked_keys)}"
        )
    return payload


def render_summary_figure(payload: dict[str, Any], output: Path) -> None:
    import matplotlib.pyplot as plt
    import numpy as np

    seeds = [summary["seed"] for summary in payload["seed_summaries"]]
    g0_macro = [
        summary["models"]["g0_projector_only"]["true_pair"]["metrics"][
            "macro_f1"
        ]
        for summary in payload["seed_summaries"]
    ]
    g1_macro = [
        summary["models"]["g1_attention_lora"]["true_pair"]["metrics"][
            "macro_f1"
        ]
        for summary in payload["seed_summaries"]
    ]
    g0_worse = [
        summary["models"]["g0_projector_only"]["true_pair"]["metrics"][
            "per_class_recall"
        ]["Worse"]
        for summary in payload["seed_summaries"]
    ]
    g1_worse = [
        summary["models"]["g1_attention_lora"]["true_pair"]["metrics"][
            "per_class_recall"
        ]["Worse"]
        for summary in payload["seed_summaries"]
    ]
    x = np.arange(len(seeds))
    width = 0.34
    colors = ("#2563EB", "#EA580C")
    figure, axes = plt.subplots(1, 2, figsize=(13.5, 5.8), dpi=160)
    for axis, first, second, title in (
        (axes[0], g0_macro, g1_macro, "True-pair macro-F1"),
        (axes[1], g0_worse, g1_worse, "True-pair Worse recall"),
    ):
        first_bars = axis.bar(
            x - width / 2,
            first,
            width,
            color=colors[0],
            edgecolor="#1F2937",
            linewidth=0.6,
            label="G0 projector only",
        )
        second_bars = axis.bar(
            x + width / 2,
            second,
            width,
            color=colors[1],
            edgecolor="#1F2937",
            linewidth=0.6,
            hatch="//",
            label="G1 attention LoRA",
        )
        axis.set_title(title, loc="left", fontsize=12, fontweight="bold")
        axis.set_xticks(x, [f"Seed {seed}" for seed in seeds])
        axis.set_ylim(0.0, 0.8)
        axis.set_ylabel("Score")
        axis.grid(axis="y", color="#D1D5DB", linewidth=0.7, alpha=0.8)
        axis.spines[["top", "right"]].set_visible(False)
        axis.bar_label(first_bars, fmt="%.3f", padding=3, fontsize=9)
        axis.bar_label(second_bars, fmt="%.3f", padding=3, fontsize=9)
    axes[0].legend(frameon=False, loc="upper left")
    figure.suptitle(
        "R41A true-pair development performance by Seed",
        x=0.08,
        y=0.99,
        ha="left",
        fontsize=15,
        fontweight="bold",
    )
    figure.text(
        0.08,
        0.935,
        "Frozen 125-patient development cohort; descriptive only",
        fontsize=10,
        color="#4B5563",
    )
    figure.tight_layout(rect=(0.04, 0.03, 0.98, 0.90))
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    figure.savefig(temporary, format=output.suffix.lstrip("."), bbox_inches="tight")
    plt.close(figure)
    temporary.replace(output)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze closed PRTA-Gen R41A failures without identities"
    )
    for seed in SEEDS:
        for model_arm in MODEL_ARMS:
            parser.add_argument(
                f"--seed-{seed}-{model_arm.replace('_', '-')}-result",
                type=Path,
                required=True,
            )
    parser.add_argument("--roster", type=Path, required=True)
    parser.add_argument("--roster-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--figure", type=Path)
    parser.add_argument("--per-pattern", type=int, default=4)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.output.exists():
        raise FileExistsError(
            f"R41A case-study output must be fresh: {args.output}"
        )
    if args.figure is not None and args.figure.exists():
        raise FileExistsError(
            f"R41A case-study figure must be fresh: {args.figure}"
        )
    result_paths = {}
    for seed in SEEDS:
        for model_arm in MODEL_ARMS:
            argument = (
                f"seed_{seed}_{model_arm.replace('-', '_')}_result"
            )
            result_paths[(seed, model_arm)] = getattr(args, argument)
    payload = build_case_study(
        result_paths=result_paths,
        roster_path=args.roster,
        roster_sha256=args.roster_sha256,
        per_pattern=args.per_pattern,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(args.output)
    if args.figure is not None:
        render_summary_figure(payload, args.figure)
    print(
        json.dumps(
            {
                "status": payload["status"],
                "rows": payload["rows"],
                "patients": payload["patients"],
                "anonymized_cases": len(payload["anonymized_cases"]),
                "identity_fields_emitted": False,
                "new_training_started": False,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
