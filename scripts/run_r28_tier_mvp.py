from __future__ import annotations

# ruff: noqa: E402

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import platform
import sys
from typing import Any, Mapping, Sequence

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE))
sys.path.insert(0, str(WORKSPACE / "src"))

import torch

from scripts import audit_r26_binding_identifiability as r27
from scripts import run_chest_imagenome_mimic_matcher_qualification as r25
from visualvit.tier import (
    EXPERT_NAMES,
    fit_expert_bundle,
    fit_router,
    signed_random_projection,
    uniform_fusion,
)
from visualvit.real_progression import (
    classification_metrics,
    deterministic_patient_folds,
    fold_audit,
    hierarchical_patient_bootstrap,
)


LABELS = r27.LABELS
TRAINING_SEEDS = r27.TRAINING_SEEDS
OUTER_FOLDS = 5
INNER_FOLDS = 4
EXPERT_STEPS = 300
ROUTER_STEPS = 400
LEARNING_RATE = 0.01
WEIGHT_DECAY = 1e-4
PROJECTION_DIM = 128
PROJECTION_SEED_BASE = 20260728
BOOTSTRAP_REPLICATES = 10_000
SYSTEMS_BASE = (*EXPERT_NAMES, "uniform_fusion")
FORBIDDEN_ROUTER_FIELDS = (
    "progression",
    "target",
    "bii",
    "case_archetype",
    "lpd",
    "lcd",
    "semantic_corruption",
    "expert_correctness",
    "patient_id",
    "study_id",
    "dicom_id",
    "qualification_id",
)
ROUTER_BASE_FIELDS = (
    "target_prior_current_cosine",
    "target_prior_current_l2",
    "global_prior_current_cosine",
    "global_prior_current_l2",
    "target_current_to_global_current_cosine",
    "target_prior_to_global_prior_cosine",
    "match_top1_cosine",
    "match_top1_top2_margin",
    "target_center_displacement",
    "target_log_area_ratio",
    "region_count_scaled",
    "view_ap_indicator",
)

PROTOCOL_PATH = (
    WORKSPACE
    / "docs/superpowers/specs/2026-07-26-r28-case-study-tier-mvp-v1.md"
)
PROTOCOL_SHA256 = (
    "ec5f0b6867607e1b98f7f06cb9fa8ff263c479e5d22dc0f03de8fde487667cce"
)
FEATURE_CACHE = Path(
    r"F:\VisualVIT_runtime\050_routeC\r25_1_matching_qualification"
    r"\process_a\crop_features.pt"
)
FEATURE_CACHE_SHA256 = (
    "2a1df98fb3a3d0ef430698da7846b314a7cbcbe73c9e50f6241bfa57dc623326"
)
CASE_ROOT = Path(
    r"F:\VisualVIT_runtime\050_routeC\r28_case_study_tier\case_study_v1"
)
CASE_MANIFEST_SHA256 = (
    "fa829059f450f8c17a44efb220a66e951e27e2b91c206d3590ad0f6765f9fee0"
)
OUTPUT_ROOT_DEFAULT = Path(
    r"F:\VisualVIT_runtime\050_routeC\r28_case_study_tier\tier_mvp_v1"
)
REPORT_PATH_DEFAULT = WORKSPACE / "reports/R28_TIER_MVP_RESULT.md"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Nested patient-OOF R28 TIER structured MVP"
    )
    parser.add_argument("--cohort", type=Path, default=r27.R26_ROOT_DEFAULT / "cohort.json")
    parser.add_argument("--features", type=Path, default=FEATURE_CACHE)
    parser.add_argument("--case-root", type=Path, default=CASE_ROOT)
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT_DEFAULT)
    parser.add_argument("--report-path", type=Path, default=REPORT_PATH_DEFAULT)
    parser.add_argument("--device", default="cpu")
    return parser.parse_args()


def _l2_normalize(value: torch.Tensor) -> torch.Tensor:
    return value.float() / value.float().norm().clamp_min(1e-8)


def _cosine(left: torch.Tensor, right: torch.Tensor) -> float:
    return float((_l2_normalize(left) * _l2_normalize(right)).sum())


def _geometry(box: Mapping[str, Any]) -> torch.Tensor:
    x1, y1, x2, y2 = (
        float(box[name]) for name in ("x1", "y1", "x2", "y2")
    )
    return torch.tensor(
        (
            (x1 + x2) / 448.0,
            (y1 + y2) / 448.0,
            (x2 - x1) / 224.0,
            (y2 - y1) / 224.0,
        ),
        dtype=torch.float32,
    )


def _target_index(record: Mapping[str, Any], side: str) -> int:
    anatomy = str(record["anatomy"])
    indices = [
        index
        for index, box in enumerate(record[f"{side}_boxes"])
        if str(box["label"]) == anatomy
    ]
    if len(indices) != 1:
        raise ValueError(f"{side} target anatomy must be unique: {anatomy}")
    return indices[0]


def build_representations(
    records: Sequence[Mapping[str, Any]],
    feature_cache: Mapping[str, torch.Tensor],
) -> tuple[
    dict[str, torch.Tensor],
    torch.Tensor,
    torch.Tensor,
    dict[str, Any],
]:
    anatomy_vocab = sorted({str(record["anatomy"]) for record in records})
    anatomy_index = {label: index for index, label in enumerate(anatomy_vocab)}
    raw_values: dict[str, list[torch.Tensor]] = {
        name: [] for name in EXPERT_NAMES
    }
    router_rows = []
    label_index = {label: index for index, label in enumerate(LABELS)}
    targets = []

    for record in records:
        prior_visual = torch.stack(
            [
                _l2_normalize(
                    feature_cache[r25._crop_key(str(record["prior_path"]), box)]
                )
                for box in record["prior_boxes"]
            ]
        )
        current_visual = torch.stack(
            [
                _l2_normalize(
                    feature_cache[r25._crop_key(str(record["current_path"]), box)]
                )
                for box in record["current_boxes"]
            ]
        )
        prior_geometry = torch.stack(
            [_geometry(box) for box in record["prior_boxes"]]
        )
        current_geometry = torch.stack(
            [_geometry(box) for box in record["current_boxes"]]
        )
        prior_index = _target_index(record, "prior")
        current_index = _target_index(record, "current")
        prior_target = prior_visual[prior_index]
        current_target = current_visual[current_index]
        prior_target_geometry = prior_geometry[prior_index]
        current_target_geometry = current_geometry[current_index]
        mean_prior = prior_visual.mean(0)
        mean_current = current_visual.mean(0)
        mean_prior_geometry = prior_geometry.mean(0)
        mean_current_geometry = current_geometry.mean(0)
        anatomy = torch.zeros(len(anatomy_vocab), dtype=torch.float32)
        anatomy[anatomy_index[str(record["anatomy"])]] = 1.0

        raw_values["state_expert"].append(
            torch.cat((current_target, current_target_geometry, anatomy))
        )
        global_delta = mean_current - mean_prior
        raw_values["global_expert"].append(
            torch.cat(
                (
                    current_target,
                    mean_prior,
                    mean_current,
                    global_delta,
                    global_delta.abs(),
                    mean_current * mean_prior,
                    mean_prior_geometry,
                    mean_current_geometry,
                    mean_current_geometry - mean_prior_geometry,
                    anatomy,
                )
            )
        )
        local_delta = current_target - prior_target
        raw_values["binding_expert"].append(
            torch.cat(
                (
                    prior_target,
                    current_target,
                    local_delta,
                    local_delta.abs(),
                    current_target * prior_target,
                    prior_target_geometry,
                    current_target_geometry,
                    current_target_geometry - prior_target_geometry,
                    anatomy,
                )
            )
        )

        similarities = torch.mv(current_visual, prior_target)
        top_values = similarities.topk(k=min(2, len(similarities))).values
        top1 = float(top_values[0])
        margin = (
            float(top_values[0] - top_values[1])
            if len(top_values) > 1
            else 0.0
        )
        center_displacement = float(
            (current_target_geometry[:2] - prior_target_geometry[:2]).norm()
        )
        prior_area = float(
            (prior_target_geometry[2] * prior_target_geometry[3]).clamp_min(1e-8)
        )
        current_area = float(
            (current_target_geometry[2] * current_target_geometry[3]).clamp_min(1e-8)
        )
        router_rows.append(
            torch.tensor(
                (
                    _cosine(prior_target, current_target),
                    float((current_target - prior_target).norm()),
                    _cosine(mean_prior, mean_current),
                    float((mean_current - mean_prior).norm()),
                    _cosine(current_target, mean_current),
                    _cosine(prior_target, mean_prior),
                    top1,
                    margin,
                    center_displacement,
                    math.log(current_area / prior_area),
                    len(current_visual) / 13.0,
                    float(str(record.get("view", "")).upper() == "AP"),
                ),
                dtype=torch.float32,
            )
        )
        targets.append(label_index[str(record["progression"])])

    projected = {}
    projection_hashes = {}
    raw_dims = {}
    for expert_index, name in enumerate(EXPERT_NAMES):
        raw = torch.stack(raw_values[name])
        raw_dims[name] = int(raw.shape[1])
        projected[name], projection_hashes[name] = signed_random_projection(
            raw,
            output_dim=PROJECTION_DIM,
            seed=PROJECTION_SEED_BASE + expert_index,
        )
    router_base = torch.stack(router_rows)
    target_tensor = torch.tensor(targets, dtype=torch.long)
    if not all(torch.isfinite(value).all() for value in projected.values()):
        raise RuntimeError("projected expert features contain non-finite values")
    if not torch.isfinite(router_base).all():
        raise RuntimeError("router descriptors contain non-finite values")
    manifest = {
        "anatomy_vocab": anatomy_vocab,
        "raw_dims": raw_dims,
        "projection_dim": PROJECTION_DIM,
        "projection_seed_base": PROJECTION_SEED_BASE,
        "projection_hashes": projection_hashes,
        "router_base_fields": list(ROUTER_BASE_FIELDS),
        "router_base_dim": int(router_base.shape[1]),
        "forbidden_router_fields": list(FORBIDDEN_ROUTER_FIELDS),
        "entities": len(records),
        "finite": True,
    }
    return projected, router_base, target_tensor, manifest


def _indices(
    records: Sequence[Mapping[str, Any]],
    assignment: Mapping[str, int],
    fold: int,
    *,
    equal: bool,
) -> torch.Tensor:
    return torch.tensor(
        [
            index
            for index, record in enumerate(records)
            if (int(assignment[str(record["patient_id"])]) == fold) == equal
        ],
        dtype=torch.long,
    )


def _prediction_rows(
    records: Sequence[Mapping[str, Any]],
    system: str,
    seed: int,
    predictions: torch.Tensor,
) -> list[dict[str, Any]]:
    patient_sizes = Counter(str(record["patient_id"]) for record in records)
    return [
        {
            "patient_id": str(record["patient_id"]),
            "observation_id": str(record["qualification_id"]),
            "training_seed": seed,
            "derangement_id": 0,
            "system": system,
            "target": str(record["progression"]),
            "prediction": LABELS[int(prediction)],
            "weight": 1.0 / patient_sizes[str(record["patient_id"])],
        }
        for record, prediction in zip(records, predictions.tolist(), strict=True)
    ]


def run_sanity_audit() -> dict[str, Any]:
    generator = torch.Generator(device="cpu")
    generator.manual_seed(20260728)
    prototypes = torch.randn(3, PROJECTION_DIM, generator=generator)
    targets = torch.arange(3).repeat_interleave(8)
    values = prototypes[targets] + 0.01 * torch.randn(
        len(targets), PROJECTION_DIM, generator=generator
    )
    logits, fit = fit_expert_bundle(
        [values, values, values],
        targets,
        [values, values, values],
        seed=20260728,
        class_count=3,
        steps=200,
        learning_rate=LEARNING_RATE,
        device="cpu",
    )
    tiny_overfit = float(
        (logits[:, 0].argmax(-1) == targets).float().mean()
    )

    router_targets = (torch.arange(90) // 3) % 3
    route_ids = torch.arange(90) % 3
    base = torch.nn.functional.one_hot(route_ids, num_classes=3).float()
    expert_logits = torch.full((90, 3, 3), -3.0)
    for index in range(90):
        expert = int(route_ids[index])
        label = int(router_targets[index])
        expert_logits[index, expert, label] = 3.0
    mixed, weights, router_fit = fit_router(
        base[:60],
        expert_logits[:60],
        router_targets[:60],
        base[60:],
        expert_logits[60:],
        kind="linear",
        seed=20260729,
        steps=300,
        learning_rate=LEARNING_RATE,
        device="cpu",
    )
    router_accuracy = float(
        (mixed.argmax(-1) == router_targets[60:]).float().mean()
    )

    shuffled_targets = torch.randperm(60, generator=generator) % 3
    random_values = torch.randn(60, PROJECTION_DIM, generator=generator)
    shuffled_logits, _ = fit_expert_bundle(
        [random_values[:40]] * 3,
        shuffled_targets[:40],
        [random_values[40:]] * 3,
        seed=20260730,
        class_count=3,
        steps=200,
        learning_rate=LEARNING_RATE,
        device="cpu",
    )
    shuffled_accuracy = float(
        (shuffled_logits[:, 0].argmax(-1) == shuffled_targets[40:])
        .float()
        .mean()
    )
    checks = {
        "tiny_train_overfit": tiny_overfit >= 0.95,
        "toy_router_separates_regimes": router_accuracy >= 0.90,
        "shuffled_holdout_below_0_60": shuffled_accuracy < 0.60,
        "fit_finite": fit["finite"] and router_fit["finite"],
        "router_weights_finite": bool(torch.isfinite(weights).all()),
        "forbidden_fields_absent": not (
            set(ROUTER_BASE_FIELDS) & set(FORBIDDEN_ROUTER_FIELDS)
        ),
    }
    return {
        "checks": checks,
        "passed": all(checks.values()),
        "tiny_train_accuracy": tiny_overfit,
        "toy_router_accuracy": router_accuracy,
        "shuffled_holdout_accuracy": shuffled_accuracy,
    }


def prepare_nested_cache(
    records: Sequence[dict[str, Any]],
    features: Mapping[str, torch.Tensor],
    router_base: torch.Tensor,
    targets: torch.Tensor,
    outer_assignment: Mapping[str, int],
    *,
    device: str,
) -> tuple[dict[tuple[int, int], dict[str, Any]], list[dict[str, Any]]]:
    cache = {}
    fit_audit = []
    feature_list = [features[name] for name in EXPERT_NAMES]
    for seed in TRAINING_SEEDS:
        for outer_fold in range(OUTER_FOLDS):
            outer_train = _indices(
                records, outer_assignment, outer_fold, equal=False
            )
            outer_test = _indices(
                records, outer_assignment, outer_fold, equal=True
            )
            train_records = [records[index] for index in outer_train.tolist()]
            inner_assignment = deterministic_patient_folds(
                train_records,
                labels=LABELS,
                fold_count=INNER_FOLDS,
                salt=f"r28-tier-inner-v1-{outer_fold}",
            )
            inner_logits = torch.empty(
                (len(outer_train), len(EXPERT_NAMES), len(LABELS)),
                dtype=torch.float32,
            )
            inner_patient_sets = []
            for inner_fold in range(INNER_FOLDS):
                inner_train_local = _indices(
                    train_records, inner_assignment, inner_fold, equal=False
                )
                inner_valid_local = _indices(
                    train_records, inner_assignment, inner_fold, equal=True
                )
                logits, fit = fit_expert_bundle(
                    [value[outer_train][inner_train_local] for value in feature_list],
                    targets[outer_train][inner_train_local],
                    [value[outer_train][inner_valid_local] for value in feature_list],
                    seed=seed + outer_fold * 100_000 + inner_fold * 1_000,
                    class_count=len(LABELS),
                    steps=EXPERT_STEPS,
                    learning_rate=LEARNING_RATE,
                    weight_decay=WEIGHT_DECAY,
                    device=device,
                )
                inner_logits[inner_valid_local] = logits
                train_patients = {
                    str(train_records[index]["patient_id"])
                    for index in inner_train_local.tolist()
                }
                valid_patients = {
                    str(train_records[index]["patient_id"])
                    for index in inner_valid_local.tolist()
                }
                inner_patient_sets.append(
                    {
                        "fold": inner_fold,
                        "train_patients": len(train_patients),
                        "valid_patients": len(valid_patients),
                        "disjoint": train_patients.isdisjoint(valid_patients),
                    }
                )
                fit_audit.append(
                    {
                        "stage": "inner_expert",
                        "training_seed": seed,
                        "outer_fold": outer_fold,
                        "inner_fold": inner_fold,
                        **fit,
                    }
                )
            outer_logits, fit = fit_expert_bundle(
                [value[outer_train] for value in feature_list],
                targets[outer_train],
                [value[outer_test] for value in feature_list],
                seed=seed + outer_fold * 100_000 + 90_000,
                class_count=len(LABELS),
                steps=EXPERT_STEPS,
                learning_rate=LEARNING_RATE,
                weight_decay=WEIGHT_DECAY,
                device=device,
            )
            fit_audit.append(
                {
                    "stage": "outer_expert",
                    "training_seed": seed,
                    "outer_fold": outer_fold,
                    **fit,
                }
            )
            outer_train_patients = {
                str(records[index]["patient_id"]) for index in outer_train.tolist()
            }
            outer_test_patients = {
                str(records[index]["patient_id"]) for index in outer_test.tolist()
            }
            cache[(seed, outer_fold)] = {
                "outer_train": outer_train,
                "outer_test": outer_test,
                "inner_logits": inner_logits,
                "outer_logits": outer_logits,
                "inner_patient_sets": inner_patient_sets,
                "outer_disjoint": outer_train_patients.isdisjoint(
                    outer_test_patients
                ),
                "train_router_base": router_base[outer_train],
                "test_router_base": router_base[outer_test],
                "train_targets": targets[outer_train],
            }
            print(
                json.dumps(
                    {
                        "stage": "nested_experts",
                        "training_seed": seed,
                        "outer_fold": outer_fold,
                        "complete": True,
                    }
                ),
                flush=True,
            )
    return cache, fit_audit


def run_router_attempt(
    kind: str,
    system_name: str,
    records: Sequence[dict[str, Any]],
    cache: Mapping[tuple[int, int], Mapping[str, Any]],
    targets: torch.Tensor,
    *,
    device: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    predictions_by_seed = {
        seed: torch.empty(len(records), dtype=torch.long)
        for seed in TRAINING_SEEDS
    }
    weights_by_seed = {
        seed: torch.empty((len(records), len(EXPERT_NAMES)))
        for seed in TRAINING_SEEDS
    }
    fit_audit = []
    router_audit = []
    for seed in TRAINING_SEEDS:
        for outer_fold in range(OUTER_FOLDS):
            item = cache[(seed, outer_fold)]
            mixture, route_weights, fit = fit_router(
                item["train_router_base"],
                item["inner_logits"],
                item["train_targets"],
                item["test_router_base"],
                item["outer_logits"],
                kind=kind,
                seed=seed + outer_fold * 100_000 + 70_000,
                steps=ROUTER_STEPS,
                learning_rate=LEARNING_RATE,
                weight_decay=WEIGHT_DECAY,
                device=device,
            )
            test_indices = item["outer_test"]
            predictions_by_seed[seed][test_indices] = mixture.argmax(-1)
            weights_by_seed[seed][test_indices] = route_weights
            fit_audit.append(
                {
                    "stage": f"{system_name}_router",
                    "training_seed": seed,
                    "outer_fold": outer_fold,
                    **fit,
                }
            )
        for index, record in enumerate(records):
            router_audit.append(
                {
                    "system": system_name,
                    "training_seed": seed,
                    "observation_id": str(record["qualification_id"]),
                    "weights": {
                        expert: float(weights_by_seed[seed][index, expert_index])
                        for expert_index, expert in enumerate(EXPERT_NAMES)
                    },
                    "sum": float(weights_by_seed[seed][index].sum()),
                }
            )
        print(
            json.dumps(
                {
                    "stage": system_name,
                    "training_seed": seed,
                    "complete": True,
                }
            ),
            flush=True,
        )
    rows = [
        row
        for seed in TRAINING_SEEDS
        for row in _prediction_rows(
            records, system_name, seed, predictions_by_seed[seed]
        )
    ]
    return rows, fit_audit, router_audit


def base_prediction_rows(
    records: Sequence[dict[str, Any]],
    cache: Mapping[tuple[int, int], Mapping[str, Any]],
) -> list[dict[str, Any]]:
    logits_by_seed = {
        seed: torch.empty(
            (len(records), len(EXPERT_NAMES), len(LABELS)), dtype=torch.float32
        )
        for seed in TRAINING_SEEDS
    }
    for seed in TRAINING_SEEDS:
        for outer_fold in range(OUTER_FOLDS):
            item = cache[(seed, outer_fold)]
            logits_by_seed[seed][item["outer_test"]] = item["outer_logits"]
    rows = []
    for seed in TRAINING_SEEDS:
        logits = logits_by_seed[seed]
        for expert_index, expert in enumerate(EXPERT_NAMES):
            rows.extend(
                _prediction_rows(
                    records, expert, seed, logits[:, expert_index].argmax(-1)
                )
            )
        rows.extend(
            _prediction_rows(
                records,
                "uniform_fusion",
                seed,
                uniform_fusion(logits).argmax(-1),
            )
        )
    return rows


def evaluate_attempt(
    rows: Sequence[dict[str, Any]],
    tier_system: str,
    *,
    all_disjoint: bool,
    all_finite: bool,
) -> dict[str, Any]:
    systems = (*SYSTEMS_BASE, tier_system)
    selected = [row for row in rows if row["system"] in systems]
    bootstrap = hierarchical_patient_bootstrap(
        selected,
        labels=LABELS,
        systems=systems,
        seeds=TRAINING_SEEDS,
        derangements=(0,),
        contrasts={
            "tier_minus_uniform": (tier_system, "uniform_fusion"),
        },
        invariant_systems=systems,
        replicates=BOOTSTRAP_REPLICATES,
        rng_seed=20260728,
    )
    seed_directions = {}
    for seed in TRAINING_SEEDS:
        seed_rows = [
            row for row in selected if int(row["training_seed"]) == seed
        ]
        tier = classification_metrics(
            [row for row in seed_rows if row["system"] == tier_system],
            labels=LABELS,
        )["patient_balanced"]["macro_f1"]
        uniform = classification_metrics(
            [row for row in seed_rows if row["system"] == "uniform_fusion"],
            labels=LABELS,
        )["patient_balanced"]["macro_f1"]
        seed_directions[str(seed)] = float(tier - uniform)
    point = bootstrap["point_system_macro_f1"]
    strongest_single = max(
        EXPERT_NAMES, key=lambda name: float(point[name])
    )
    primary = bootstrap["contrasts"]["tier_minus_uniform"]
    gates = {
        "ENGINEERING_PREDICTIONS_COMPLETE": (
            len([row for row in selected if row["system"] == tier_system])
            == len(TRAINING_SEEDS) * 774
        ),
        "ENGINEERING_PATIENT_DISJOINT": all_disjoint,
        "ENGINEERING_FINITE": all_finite,
        "BOOTSTRAP_VALID": bootstrap["inference_valid"],
        "DELTA_AT_LEAST_2PP": primary["point_pp"] >= 2.0,
        "CI_LOWER_POSITIVE": (
            primary["interval"] is not None
            and primary["interval"]["lower"] > 0
        ),
        "ALL_SEED_DIRECTIONS_POSITIVE": all(
            value > 0 for value in seed_directions.values()
        ),
        "NO_MORE_THAN_1PP_BELOW_STRONGEST_SINGLE": (
            float(point[tier_system]) - float(point[strongest_single]) >= -0.01
        ),
    }
    engineering = all(
        value for name, value in gates.items() if name.startswith("ENGINEERING")
    )
    scientific = engineering and all(
        value for name, value in gates.items() if not name.startswith("ENGINEERING")
    )
    return {
        "system": tier_system,
        "bootstrap": bootstrap,
        "seed_directions": seed_directions,
        "strongest_single_expert": strongest_single,
        "gates": gates,
        "engineering_passed": engineering,
        "scientific_go": scientific,
    }


def render_report(
    attempts: Sequence[Mapping[str, Any]],
    feature_manifest: Mapping[str, Any],
    sanity: Mapping[str, Any],
    reproduction_pending: bool,
) -> str:
    lines = [
        "# R28 TIER MVP Result",
        "",
        "Date: 2026-07-26",
        "",
        "Evidence class: `NON_CONFIRMATORY_R28_DEVELOPMENT`",
        "",
        "## Boundary",
        "",
        "R28 uses the same development cohort already examined in R26/R27 and "
        "cannot be a confirmatory or clinical result. BII, case archetype, labels, "
        "and expert correctness were forbidden router inputs.",
        "",
        "## Representation and sanity",
        "",
        f"- Entities: {feature_manifest['entities']}",
        f"- Projection dimension: {feature_manifest['projection_dim']}",
        f"- Router base descriptors: {feature_manifest['router_base_dim']}",
        f"- Sanity gate: {'PASS' if sanity['passed'] else 'FAIL'}",
        "",
        "## Attempts",
        "",
        "| Attempt | TIER F1 | Uniform F1 | Delta | 95% CI | Engineering | Scientific |",
        "|---|---:|---:|---:|---|---|---|",
    ]
    for attempt in attempts:
        bootstrap = attempt["bootstrap"]
        point = bootstrap["point_system_macro_f1"]
        contrast = bootstrap["contrasts"]["tier_minus_uniform"]
        interval = contrast["interval"]
        ci = (
            "invalid"
            if interval is None
            else f"[{100*interval['lower']:+.2f}, {100*interval['upper']:+.2f}]"
        )
        lines.append(
            f"| {attempt['system']} | {point[attempt['system']]:.4f} | "
            f"{point['uniform_fusion']:.4f} | {contrast['point_pp']:+.2f} pp | "
            f"{ci} pp | {'PASS' if attempt['engineering_passed'] else 'FAIL'} | "
            f"{'GO' if attempt['scientific_go'] else 'NO-GO'} |"
        )
    final = attempts[-1]
    lines.extend(
        [
            "",
            "## Final interpretation",
            "",
            f"- Best admissible attempt: `{final['system']}`",
            f"- Engineering pipeline: "
            f"{'PASS' if final['engineering_passed'] else 'FAIL'}",
            f"- Scientific gate: {'GO' if final['scientific_go'] else 'NO-GO'}",
            f"- Fresh-process reproduction: "
            f"{'PENDING' if reproduction_pending else 'PASS'}",
            "",
            "Engineering completion does not override a scientific NO-GO. If A2 "
            "fails, the next permitted direction is a separately reviewed "
            "report-supervised transition representation; VLM/DIVE/scale-up remain "
            "locked.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    if args.device != "cpu":
        raise ValueError("frozen R28 MVP is CPU-only")
    if args.output_root.exists():
        raise FileExistsError(f"R28 output root must be fresh: {args.output_root}")
    if args.report_path.exists():
        raise FileExistsError(f"R28 report path must be fresh: {args.report_path}")
    if r27.sha256_file(PROTOCOL_PATH) != PROTOCOL_SHA256:
        raise RuntimeError("R28 TIER protocol hash mismatch")
    if r27.sha256_file(args.features) != FEATURE_CACHE_SHA256:
        raise RuntimeError("R25.1 feature cache hash mismatch")
    if (
        r27.sha256_file(args.case_root / "artifact_manifest.json")
        != CASE_MANIFEST_SHA256
    ):
        raise RuntimeError("R28 case-study manifest hash mismatch")
    case_registry = r27.read_json(args.case_root / "case_registry.json", dict)
    headroom = case_registry["case_oracle_headroom"]
    if (
        float(headroom["case_oracle_minus_best_fixed_pp"]) < 10.0
        or headroom["interval"] is None
        or float(headroom["interval"]["lower"]) <= 0
    ):
        raise RuntimeError("case-oracle headroom prerequisite failed")

    cohort = r27.read_json(args.cohort, list)
    features = torch.load(args.features, map_location="cpu", weights_only=True)
    if not isinstance(features, dict):
        raise ValueError("feature cache must be a dictionary")
    projected, router_base, targets, feature_manifest = build_representations(
        cohort, features
    )
    sanity = run_sanity_audit()
    if not sanity["passed"]:
        raise RuntimeError(f"R28 sanity gate failed: {sanity}")

    outer_assignment = deterministic_patient_folds(
        cohort,
        labels=LABELS,
        fold_count=OUTER_FOLDS,
        salt="r28-tier-outer-v1",
    )
    outer_audit = fold_audit(
        cohort,
        outer_assignment,
        labels=LABELS,
        fold_count=OUTER_FOLDS,
    )
    if not outer_audit["patient_disjoint"]:
        raise RuntimeError("outer folds are not patient-disjoint")
    cache, expert_fit = prepare_nested_cache(
        cohort,
        projected,
        router_base,
        targets,
        outer_assignment,
        device=args.device,
    )
    all_disjoint = all(
        item["outer_disjoint"]
        and all(value["disjoint"] for value in item["inner_patient_sets"])
        for item in cache.values()
    )
    base_rows = base_prediction_rows(cohort, cache)
    a1_rows, a1_fit, a1_router = run_router_attempt(
        "linear", "tier_a1", cohort, cache, targets, device=args.device
    )
    all_rows = [*base_rows, *a1_rows]
    all_fit = [*expert_fit, *a1_fit]
    attempts = [
        evaluate_attempt(
            all_rows,
            "tier_a1",
            all_disjoint=all_disjoint,
            all_finite=all(item["finite"] for item in all_fit),
        )
    ]
    router_audit = list(a1_router)

    if attempts[0]["engineering_passed"] and not attempts[0]["scientific_go"]:
        a2_rows, a2_fit, a2_router = run_router_attempt(
            "nonlinear", "tier_a2", cohort, cache, targets, device=args.device
        )
        all_rows.extend(a2_rows)
        all_fit.extend(a2_fit)
        router_audit.extend(a2_router)
        attempts.append(
            evaluate_attempt(
                all_rows,
                "tier_a2",
                all_disjoint=all_disjoint,
                all_finite=all(item["finite"] for item in all_fit),
            )
        )

    final_attempt = attempts[-1]
    status = (
        "AWAITING_FRESH_PROCESS_REPRODUCTION"
        if final_attempt["engineering_passed"]
        else "ENGINEERING_FAILURE"
    )
    args.output_root.mkdir(parents=True, exist_ok=False)
    folds_payload = {
        "outer_assignment": dict(sorted(outer_assignment.items())),
        "outer_audit": outer_audit,
        "nested_disjoint": all_disjoint,
        "inner_audits": {
            f"{seed}:{fold}": cache[(seed, fold)]["inner_patient_sets"]
            for seed in TRAINING_SEEDS
            for fold in range(OUTER_FOLDS)
        },
    }
    closure = {
        "status": status,
        "attempts": attempts,
        "final_system": final_attempt["system"],
        "engineering_passed": final_attempt["engineering_passed"],
        "scientific_go": final_attempt["scientific_go"],
        "formal_claim_allowed": False,
        "clinical_claim_allowed": False,
        "vlm_dive_scaleup_unlocked": False,
    }
    payloads = {
        "feature_manifest.json": feature_manifest,
        "folds.json": folds_payload,
        "sanity_audit.json": sanity,
        "predictions.json": all_rows,
        "fit_audit.json": all_fit,
        "router_audit.json": router_audit,
        "bootstrap.json": {
            attempt["system"]: attempt["bootstrap"] for attempt in attempts
        },
        "attempt_closure.json": closure,
    }
    for name, payload in payloads.items():
        r27.write_json_exclusive(args.output_root / name, payload)
    report = render_report(
        attempts, feature_manifest, sanity, reproduction_pending=True
    )
    args.report_path.write_text(report, encoding="utf-8")
    manifest_base = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "protocol": {
            "path": str(PROTOCOL_PATH),
            "sha256": PROTOCOL_SHA256,
        },
        "feature_cache": {
            "path": str(args.features),
            "sha256": FEATURE_CACHE_SHA256,
        },
        "case_manifest_sha256": CASE_MANIFEST_SHA256,
        "source_hashes": {
            "scripts/run_r28_tier_mvp.py": r27.sha256_file(Path(__file__)),
            "src/visualvit/tier.py": r27.sha256_file(
                WORKSPACE / "src/visualvit/tier.py"
            ),
        },
        "outputs": {
            name: r27.sha256_file(args.output_root / name) for name in payloads
        },
        "report": {
            "path": str(args.report_path),
            "sha256": r27.sha256_file(args.report_path),
        },
        "attempts": [attempt["system"] for attempt in attempts],
        "final_system": final_attempt["system"],
        "engineering_passed": final_attempt["engineering_passed"],
        "scientific_go": final_attempt["scientific_go"],
        "formal_claim_allowed": False,
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "torch": torch.__version__,
            "device": args.device,
        },
    }
    manifest = dict(manifest_base)
    manifest["manifest_payload_sha256"] = r27.canonical_sha256(manifest_base)
    r27.write_json_exclusive(args.output_root / "artifact_manifest.json", manifest)
    print(
        json.dumps(
            {
                "status": status,
                "output_root": str(args.output_root),
                "attempts": [attempt["system"] for attempt in attempts],
                "final_system": final_attempt["system"],
                "engineering_passed": final_attempt["engineering_passed"],
                "scientific_go": final_attempt["scientific_go"],
                "manifest_sha256": r27.sha256_file(
                    args.output_root / "artifact_manifest.json"
                ),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
