from __future__ import annotations

# ruff: noqa: E402

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Iterable

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE))
sys.path.insert(0, str(WORKSPACE / "src"))

from scripts.analyze_prta_gen_r41a_failure_cases import (
    classification_metrics,
    confusion_rows,
)


CASE_SCHEMA = "visualvit.prta-gen.r44a-failure-case-study.v1"
CASE_STATUS = "DESCRIPTIVE_PRTA_GEN_R44A_FAILURE_CASE_STUDY"
RESULT_SCHEMA = "visualvit.prta-gen.r44a-arm-result.v1"
RESULT_STATUS = "PASS_PRTA_GEN_R44A_ARM_EVALUATION"
ROSTER_SCHEMA = "visualvit.prta-gen.r44a-roster.v1"
ROSTER_STATUS = "PASS_PRTA_GEN_R44A_ROSTER_SUPPORT"
PROTOCOL_ID = "prta-gen-r44a-cross-source-silver-sft-v1"
STUDY_TIER = "cross_source_silver_progression_only_sft_survival"
SEEDS = (17, 29, 43)
MODEL_ARMS = ("g0_projector_only", "g1_attention_lora")
EVALUATION_ARMS = (
    "true_pair",
    "current_only",
    "query_only",
    "prior_shuffle",
)
EXPECTED_ROWS = 250
EXPECTED_TRAIN_ROWS = 1000
EXPECTED_UPDATES = 94
EXPECTED_CLASSES = ("Stable", "Improved", "Worse", "New", "Resolved")
FORBIDDEN_OUTPUT_KEYS = {
    "example_id",
    "patient_id",
    "development_example_ids",
    "development_patient_ids",
}


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


def _assert_close(observed: float, expected: float, label: str) -> None:
    if abs(observed - expected) > 1e-12:
        raise ValueError(
            f"{label} metric drift: observed={observed}, expected={expected}"
        )


def _prediction_values(
    value: Any, *, classes: list[str], label: str
) -> list[int]:
    _require(
        isinstance(value, list) and len(value) == EXPECTED_ROWS,
        f"{label} must contain {EXPECTED_ROWS} predictions",
    )
    predictions = [int(item) for item in value]
    _require(
        all(0 <= item < len(classes) for item in predictions),
        f"{label} contains an out-of-registry class index",
    )
    return predictions


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
        key: read_json(path)
        for key, path in sorted(
            result_paths.items(), key=lambda item: (item[0][0], item[0][1])
        )
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
            "training_patients": result.get("training_patients")
            == EXPECTED_TRAIN_ROWS,
            "optimizer_updates": result.get("optimizer_updates")
            == EXPECTED_UPDATES,
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
                f"R44A result firewall/schema drift for {seed}/{model_arm}: "
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
        example_ids = [
            str(value)
            for value in result.get("development_example_ids", [])
        ]
        patient_ids = [
            str(value)
            for value in result.get("development_patient_ids", [])
        ]
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
        metrics = result.get("metrics")
        _require(
            isinstance(predictions, dict)
            and set(predictions) == set(EVALUATION_ARMS),
            f"evaluation-arm drift for {seed}/{model_arm}",
        )
        _require(
            isinstance(metrics, dict)
            and set(metrics) == set(EVALUATION_ARMS),
            f"metric-arm drift for {seed}/{model_arm}",
        )
        for evaluation_arm in EVALUATION_ARMS:
            arm_predictions = _prediction_values(
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
    _require(
        sha256_file(roster_path) == expected_sha256.upper(),
        "immutable R44A roster SHA-256 drift",
    )
    roster = read_json(roster_path)
    checks = {
        "schema": roster.get("schema") == ROSTER_SCHEMA,
        "status": roster.get("status") == ROSTER_STATUS,
        "protocol": roster.get("protocol_id") == PROTOCOL_ID,
        "one_row_per_patient": roster.get("one_row_per_patient") is True,
        "disjoint": roster.get("patient_sets_disjoint") is True,
        "images": roster.get("selected_images_complete") is True,
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
        "r41a_selection": roster.get(
            "r41a_outcomes_used_for_roster_selection"
        )
        is False,
        "r41a_reuse": roster.get("r41a_development_reused") is False,
        "scientific_claim": roster.get("scientific_claim_allowed") is False,
    }
    failed = sorted(name for name, passed in checks.items() if not passed)
    if failed:
        raise PermissionError(f"R44A roster firewall/schema drift: {failed}")
    partitions = roster.get("partitions")
    _require(isinstance(partitions, dict), "R44A roster partitions missing")
    train_rows = partitions.get("train", {}).get("rows")
    development_rows = partitions.get("development", {}).get("rows")
    _require(
        isinstance(train_rows, list)
        and len(train_rows) == EXPECTED_TRAIN_ROWS,
        "R44A training roster count drift",
    )
    _require(
        isinstance(development_rows, list)
        and len(development_rows) == EXPECTED_ROWS,
        "R44A development roster count drift",
    )
    _require(
        [str(row["example_id"]) for row in development_rows]
        == [
            str(value)
            for value in reference_result["development_example_ids"]
        ],
        "R44A roster/result example-order drift",
    )
    _require(
        [str(row["patient_id"]) for row in development_rows]
        == [
            str(value)
            for value in reference_result["development_patient_ids"]
        ],
        "R44A roster/result patient-order drift",
    )
    _require(
        [str(row["progression"]) for row in development_rows]
        == [
            reference_result["classes"][int(value)]
            for value in reference_result["targets"]
        ],
        "R44A roster/result target-order drift",
    )
    return development_rows


def _comparison_category(
    target: int, true_prediction: int, control_prediction: int
) -> str:
    true_correct = true_prediction == target
    control_correct = control_prediction == target
    if true_correct and control_correct:
        return "both_correct"
    if true_correct:
        return "true_only_correct"
    if control_correct:
        return "control_only_correct"
    if true_prediction == control_prediction:
        return "both_wrong_same_prediction"
    return "both_wrong_different_prediction"


def _migration_category(
    target: int, g0_prediction: int, g1_prediction: int
) -> str:
    g0_correct = g0_prediction == target
    g1_correct = g1_prediction == target
    if g0_correct and g1_correct:
        return "both_correct"
    if g0_correct:
        return "g0_only_correct_regression"
    if g1_correct:
        return "g1_only_correct_recovery"
    if g0_prediction == g1_prediction:
        return "both_wrong_same_prediction"
    return "both_wrong_different_prediction"


def _group_counts(
    *,
    rows: list[dict[str, Any]],
    targets: list[int],
    classes: list[str],
    categories: list[str],
    key: str,
) -> dict[str, dict[str, int]]:
    counters: dict[str, Counter[str]] = defaultdict(Counter)
    for row, target, category in zip(
        rows, targets, categories, strict=True
    ):
        value = classes[target] if key == "target" else str(row[key])
        counters[value][category] += 1
    return {
        value: {
            "rows": sum(counter.values()),
            **dict(sorted(counter.items())),
        }
        for value, counter in sorted(counters.items())
    }


def comparison_summary(
    *,
    rows: list[dict[str, Any]],
    targets: list[int],
    classes: list[str],
    true_predictions: list[int],
    control_predictions: list[int],
) -> dict[str, Any]:
    categories = [
        _comparison_category(target, true_prediction, control_prediction)
        for target, true_prediction, control_prediction in zip(
            targets, true_predictions, control_predictions, strict=True
        )
    ]
    counts = Counter(categories)
    same_prediction = sum(
        first == second
        for first, second in zip(
            true_predictions, control_predictions, strict=True
        )
    )
    true_only = counts["true_only_correct"]
    control_only = counts["control_only_correct"]
    return {
        "category_counts": dict(sorted(counts.items())),
        "same_prediction_rows": same_prediction,
        "same_prediction_rate": same_prediction / len(targets),
        "changed_prediction_rows": len(targets) - same_prediction,
        "changed_prediction_rate": 1.0 - same_prediction / len(targets),
        "true_only_correct_rows": true_only,
        "control_only_correct_rows": control_only,
        "net_true_sensitive_rows": true_only - control_only,
        "net_true_sensitive_rate": (true_only - control_only) / len(targets),
        "by_target": _group_counts(
            rows=rows,
            targets=targets,
            classes=classes,
            categories=categories,
            key="target",
        ),
        "by_finding": _group_counts(
            rows=rows,
            targets=targets,
            classes=classes,
            categories=categories,
            key="finding",
        ),
    }


def migration_summary(
    *,
    rows: list[dict[str, Any]],
    targets: list[int],
    classes: list[str],
    g0_predictions: list[int],
    g1_predictions: list[int],
) -> dict[str, Any]:
    categories = [
        _migration_category(target, g0_prediction, g1_prediction)
        for target, g0_prediction, g1_prediction in zip(
            targets, g0_predictions, g1_predictions, strict=True
        )
    ]
    counts = Counter(categories)
    recovery = counts["g1_only_correct_recovery"]
    regression = counts["g0_only_correct_regression"]
    return {
        "category_counts": dict(sorted(counts.items())),
        "recovery_rows": recovery,
        "regression_rows": regression,
        "net_g1_rows": recovery - regression,
        "net_g1_rate": (recovery - regression) / len(targets),
        "by_target": _group_counts(
            rows=rows,
            targets=targets,
            classes=classes,
            categories=categories,
            key="target",
        ),
        "by_finding": _group_counts(
            rows=rows,
            targets=targets,
            classes=classes,
            categories=categories,
            key="finding",
        ),
    }


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
    if all(true == shuffle for true, shuffle in zip(
        g1_true, g1_shuffle, strict=True
    )):
        patterns.append("persistent_true_shuffle_invariance")
    if all(
        true == target and shuffle != target
        for true, shuffle in zip(g1_true, g1_shuffle, strict=True)
    ):
        patterns.append("persistent_true_sensitive_success")
    if all(value != target for value in g1_true):
        patterns.append("persistent_g1_true_pair_error")
    if all(
        g0 == target and g1 != target
        for g0, g1 in zip(g0_true, g1_true, strict=True)
    ):
        patterns.append("persistent_g0_correct_g1_regression")
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
    selected = []
    case_number = 0
    for pattern in sorted(candidates):
        for index in candidates[pattern][:per_pattern]:
            case_number += 1
            seed_predictions = {}
            for seed in SEEDS:
                seed_predictions[str(seed)] = {}
                for model_arm in MODEL_ARMS:
                    predictions = results[(seed, model_arm)]["predictions"]
                    seed_predictions[str(seed)][model_arm] = {
                        arm: classes[int(predictions[arm][index])]
                        for arm in EVALUATION_ARMS
                    }
            selected.append(
                {
                    "case_id": f"CASE-{case_number:03d}",
                    "pattern": pattern,
                    "finding": str(rows[index]["finding"]),
                    "target": classes[targets[index]],
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
    rows = validate_roster(
        roster_path=roster_path,
        expected_sha256=roster_sha256,
        reference_result=results[(17, "g0_projector_only")],
    )
    seed_summaries = []
    for seed in SEEDS:
        models = {}
        for model_arm in MODEL_ARMS:
            result = results[(seed, model_arm)]
            evaluations = {}
            for evaluation_arm in EVALUATION_ARMS:
                predictions = [
                    int(value)
                    for value in result["predictions"][evaluation_arm]
                ]
                evaluations[evaluation_arm] = {
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
                }
            models[model_arm] = evaluations
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
        controls = {}
        for control_arm in ("current_only", "query_only", "prior_shuffle"):
            controls[control_arm] = comparison_summary(
                rows=rows,
                targets=targets,
                classes=classes,
                true_predictions=g1_true,
                control_predictions=[
                    int(value)
                    for value in g1_result["predictions"][control_arm]
                ],
            )
        seed_summaries.append(
            {
                "seed": seed,
                "models": models,
                "g0_to_g1_true_pair_migration": migration_summary(
                    rows=rows,
                    targets=targets,
                    classes=classes,
                    g0_predictions=g0_true,
                    g1_predictions=g1_true,
                ),
                "g1_true_pair_vs_controls": controls,
            }
        )
    cross_seed_true = Counter()
    shuffle_sensitivity_counts = Counter()
    for index, target in enumerate(targets):
        true_predictions = [
            int(
                results[(seed, "g1_attention_lora")]["predictions"][
                    "true_pair"
                ][index]
            )
            for seed in SEEDS
        ]
        shuffle_predictions = [
            int(
                results[(seed, "g1_attention_lora")]["predictions"][
                    "prior_shuffle"
                ][index]
            )
            for seed in SEEDS
        ]
        correct = [prediction == target for prediction in true_predictions]
        if all(correct):
            cross_seed_true["unanimous_correct"] += 1
        elif not any(correct) and len(set(true_predictions)) == 1:
            cross_seed_true["unanimous_same_wrong"] += 1
        elif any(correct):
            cross_seed_true["mixed_with_some_correct"] += 1
        else:
            cross_seed_true["mixed_all_wrong"] += 1
        sensitivity_count = sum(
            true != shuffle
            for true, shuffle in zip(
                true_predictions, shuffle_predictions, strict=True
            )
        )
        shuffle_sensitivity_counts[str(sensitivity_count)] += 1
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
        "closed_r44a_result_unchanged": True,
        "observed_development_reuse_for_selection_allowed": False,
        "new_training_started": False,
        "rows": EXPECTED_ROWS,
        "patients": EXPECTED_ROWS,
        "seeds": list(SEEDS),
        "classes": classes,
        "seed_summaries": seed_summaries,
        "cross_seed_g1_true_pair_patterns": dict(
            sorted(cross_seed_true.items())
        ),
        "cross_seed_g1_true_shuffle_changed_seed_count": dict(
            sorted(shuffle_sensitivity_counts.items())
        ),
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
    g1_agreement = []
    g1_true_only = []
    g1_control_only = []
    for summary in payload["seed_summaries"]:
        g1 = summary["g1_true_pair_vs_controls"]["prior_shuffle"]
        g1_agreement.append(g1["same_prediction_rate"])
        g1_true_only.append(g1["true_only_correct_rows"])
        g1_control_only.append(g1["control_only_correct_rows"])
    x = np.arange(len(seeds))
    width = 0.34
    figure, axes = plt.subplots(1, 2, figsize=(13.5, 5.6), dpi=160)
    bars = axes[0].bar(
        x,
        g1_agreement,
        0.55,
        color="#7C3AED",
        edgecolor="#1F2937",
        linewidth=0.6,
    )
    axes[0].set_title(
        "G1 true-vs-shuffle prediction agreement",
        loc="left",
        fontweight="bold",
    )
    axes[0].set_ylim(0.0, 1.0)
    axes[0].set_ylabel("Agreement rate")
    axes[0].bar_label(bars, fmt="%.3f", padding=3)
    first = axes[1].bar(
        x - width / 2,
        g1_true_only,
        width,
        color="#2563EB",
        label="True only correct",
    )
    second = axes[1].bar(
        x + width / 2,
        g1_control_only,
        width,
        color="#EA580C",
        hatch="//",
        label="Shuffle only correct",
    )
    axes[1].set_title(
        "Correctness-changing prior sensitivity",
        loc="left",
        fontweight="bold",
    )
    axes[1].set_ylabel("Patients")
    axes[1].bar_label(first, padding=3)
    axes[1].bar_label(second, padding=3)
    axes[1].legend(frameon=False)
    for axis in axes:
        axis.set_xticks(x, [f"Seed {seed}" for seed in seeds])
        axis.grid(axis="y", color="#D1D5DB", linewidth=0.7, alpha=0.8)
        axis.spines[["top", "right"]].set_visible(False)
    figure.suptitle(
        "R44A correct-prior sensitivity case study",
        x=0.06,
        y=0.99,
        ha="left",
        fontsize=15,
        fontweight="bold",
    )
    figure.text(
        0.06,
        0.93,
        "Frozen 250-patient development cohort; descriptive only",
        color="#4B5563",
    )
    figure.tight_layout(rect=(0.03, 0.03, 0.98, 0.89))
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    figure.savefig(
        temporary, format=output.suffix.lstrip("."), bbox_inches="tight"
    )
    plt.close(figure)
    temporary.replace(output)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze closed PRTA-Gen R44A failures without identities"
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
            f"R44A case-study output must be fresh: {args.output}"
        )
    if args.figure is not None and args.figure.exists():
        raise FileExistsError(
            f"R44A case-study figure must be fresh: {args.figure}"
        )
    result_paths = {}
    for seed in SEEDS:
        for model_arm in MODEL_ARMS:
            argument = f"seed_{seed}_{model_arm}_result"
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
