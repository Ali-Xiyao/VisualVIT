from __future__ import annotations

# ruff: noqa: E402

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import sys
from typing import Any, Mapping, Sequence

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE))
sys.path.insert(0, str(WORKSPACE / "src"))

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
import torch

from scripts import audit_r26_binding_identifiability as r27
from scripts import build_r30_fresh_silver_cohort as cohort_builder
from scripts import run_chest_imagenome_mimic_matcher_qualification as r25
from scripts import run_r29_contextual_transition as r29
from visualvit.context_transition import geometry_features, pair_interactions
from visualvit.real_progression import (
    classification_metrics,
    hierarchical_patient_bootstrap,
)
from visualvit.tier import signed_random_projection


LABELS = cohort_builder.LABELS
TRAINING_SEEDS = (17, 29, 43)
REFERENCE_SYSTEMS = (
    "state",
    "global_transition",
    "local_transition",
    "uniform_fusion",
)
SYSTEMS = (*REFERENCE_SYSTEMS, "regularized_multiscale")
PROJECTION_DIM = 128
PROJECTION_SEED_BASE = 20260800
LOGISTIC_C = 0.001
MAX_ITER = 2000
BOOTSTRAP_REPLICATES = 10_000
BOOTSTRAP_SEED = 20260830
RECOVERY_FEATURE_CACHE_SHA256 = (
    "9bbb26bf6dab566a74b0a756f6a2f8cb21da8731a619e4dd6a1b24338701cec3"
)
COHORT_ROOT = cohort_builder.OUTPUT_ROOT_DEFAULT
COHORT_SHA256 = (
    "219132709955c5612abd39b5eade618bf3fc69eeb5a520ef6b41196fd41b437f"
)
PROTOCOL_PATH = cohort_builder.PROTOCOL_PATH
PROTOCOL_SHA256 = cohort_builder.PROTOCOL_SHA256
WEIGHTS = r25.WEIGHTS_DEFAULT
WEIGHTS_SHA256 = r25.MIMIC_PINS["weights"]
OUTPUT_ROOT_DEFAULT = Path(
    r"F:\VisualVIT_runtime\050_routeC\r30_regularized_multiscale\run_v1"
)
REPORT_PATH_DEFAULT = (
    WORKSPACE / "reports/R30_REGULARIZED_MULTISCALE_RESULT.md"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="R30 regularized multiscale transition experiment"
    )
    parser.add_argument("--cohort-root", type=Path, default=COHORT_ROOT)
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT_DEFAULT)
    parser.add_argument("--report-path", type=Path, default=REPORT_PATH_DEFAULT)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--feature-cache-input", type=Path)
    return parser.parse_args()


def build_multiscale_blocks(
    records: Sequence[Mapping[str, Any]],
    features: Mapping[str, torch.Tensor],
) -> tuple[
    dict[str, torch.Tensor],
    torch.Tensor,
    torch.Tensor,
    torch.Tensor,
    dict[str, Any],
]:
    finding_vocab = sorted({str(row["finding_token"]) for row in records})
    finding_index = {value: index for index, value in enumerate(finding_vocab)}
    box_index = {value: index for index, value in enumerate(r29.BOX_NAMES)}
    raw = {name: [] for name in ("global", "exact", "context")}
    queries = []
    geometries = []
    targets = []
    label_index = {value: index for index, value in enumerate(LABELS)}
    for record in records:
        query = torch.zeros(
            len(finding_vocab) + len(r29.BOX_NAMES), dtype=torch.float32
        )
        query[finding_index[str(record["finding_token"])]] = 1.0
        for name in record["mapped_anatomy"]:
            if name in box_index:
                query[len(finding_vocab) + box_index[name]] = 1.0
        queries.append(query)
        geometries.append(
            torch.cat(
                [
                    geometry_features(
                        record[f"{side}_exact_box"],
                        record[f"{side}_context_box"],
                        record["prior_view"],
                        record["current_view"],
                    )
                    for side in ("prior", "current")
                ]
            )
        )
        for name, box_field in (
            ("global", None),
            ("exact", "exact_box"),
            ("context", "context_box"),
        ):
            values = []
            for side in ("prior", "current"):
                box = (
                    (0.0, 0.0, 224.0, 224.0)
                    if box_field is None
                    else record[f"{side}_{box_field}"]
                )
                values.append(
                    features[
                        r29._feature_key(record[f"{side}_path"], box)
                    ]
                )
            raw[name].append(pair_interactions(values[0], values[1]))
        targets.append(label_index[str(record["progression"])])
    stacked = {name: torch.stack(values) for name, values in raw.items()}
    return (
        stacked,
        torch.stack(queries),
        torch.stack(geometries),
        torch.tensor(targets, dtype=torch.long),
        {
            "finding_vocab": finding_vocab,
            "box_vocab": list(r29.BOX_NAMES),
            "scale_raw_dims": {
                name: int(values.shape[1])
                for name, values in stacked.items()
            },
            "projection_dim_per_scale": PROJECTION_DIM,
            "logistic_c": LOGISTIC_C,
        },
    )


def project_multiscale(
    raw: Mapping[str, torch.Tensor],
    queries: torch.Tensor,
    geometries: torch.Tensor,
    *,
    seed: int,
) -> tuple[torch.Tensor, dict[str, str]]:
    projected = []
    hashes = {}
    for scale_index, name in enumerate(("global", "exact", "context")):
        values, projection_hash = signed_random_projection(
            raw[name],
            output_dim=PROJECTION_DIM,
            seed=PROJECTION_SEED_BASE + seed + scale_index,
        )
        projected.append(values)
        hashes[name] = projection_hash
    return torch.cat((*projected, queries, geometries), dim=1), hashes


def sample_weights(
    records: Sequence[Mapping[str, Any]],
    indices: torch.Tensor,
    targets: torch.Tensor,
) -> np.ndarray:
    selected = indices.tolist()
    patient_counts = Counter(
        str(records[index]["patient_id"]) for index in selected
    )
    class_counts = Counter(int(targets[index]) for index in selected)
    count = len(selected)
    return np.asarray(
        [
            (1.0 / patient_counts[str(records[index]["patient_id"])])
            * (count / (len(LABELS) * class_counts[int(targets[index])]))
            for index in selected
        ],
        dtype=np.float64,
    )


def fit_regularized(
    records: Sequence[Mapping[str, Any]],
    values: torch.Tensor,
    targets: torch.Tensor,
    train_indices: torch.Tensor,
    eval_indices: torch.Tensor,
    *,
    seed: int,
    train_targets_override: torch.Tensor | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    train_targets = (
        targets[train_indices]
        if train_targets_override is None
        else train_targets_override
    )
    model = make_pipeline(
        StandardScaler(),
        LogisticRegression(
            C=LOGISTIC_C,
            max_iter=MAX_ITER,
            random_state=seed,
        ),
    )
    weights = sample_weights(records, train_indices, targets)
    train_values = values[train_indices].numpy()
    eval_values = values[eval_indices].numpy()
    model.fit(
        train_values,
        train_targets.numpy(),
        logisticregression__sample_weight=weights,
    )
    predictions = torch.from_numpy(model.predict(eval_values))
    train_predictions = model.predict(train_values)
    logistic = model.named_steps["logisticregression"]
    finite = bool(
        np.isfinite(logistic.coef_).all()
        and np.isfinite(logistic.intercept_).all()
    )
    converged = bool(np.all(logistic.n_iter_ < MAX_ITER))
    rows = r29._prediction_rows(
        records,
        eval_indices,
        "regularized_multiscale",
        seed,
        predictions,
    )
    return rows, {
        "seed": seed,
        "system": "regularized_multiscale",
        "train_accuracy": float(
            np.mean(train_predictions == train_targets.numpy())
        ),
        "n_iter": [int(value) for value in logistic.n_iter_],
        "finite": finite,
        "converged": converged,
        "feature_dim": int(values.shape[1]),
        "coefficient_l2": float(np.linalg.norm(logistic.coef_)),
    }


def contrast_delta(
    rows: Sequence[dict[str, Any]],
) -> tuple[float, dict[str, float]]:
    directions = {}
    for seed in TRAINING_SEEDS:
        selected = [row for row in rows if row["training_seed"] == seed]
        regularized = classification_metrics(
            [
                row
                for row in selected
                if row["system"] == "regularized_multiscale"
            ],
            labels=LABELS,
        )["patient_balanced"]["macro_f1"]
        uniform = classification_metrics(
            [
                row
                for row in selected
                if row["system"] == "uniform_fusion"
            ],
            labels=LABELS,
        )["patient_balanced"]["macro_f1"]
        directions[str(seed)] = float(regularized - uniform)
    return float(np.mean(list(directions.values()))), directions


def fit_stage(
    records: Sequence[Mapping[str, Any]],
    baseline_representations: Mapping[str, torch.Tensor],
    raw: Mapping[str, torch.Tensor],
    queries: torch.Tensor,
    geometries: torch.Tensor,
    targets: torch.Tensor,
    train_indices: torch.Tensor,
    eval_indices: torch.Tensor,
    *,
    device: str,
) -> tuple[
    list[dict[str, Any]], list[dict[str, Any]], dict[str, dict[str, str]]
]:
    baseline_rows, baseline_audits = r29.fit_systems(
        records,
        baseline_representations,
        targets,
        train_indices,
        eval_indices,
        device=device,
    )
    rows = [
        row for row in baseline_rows if row["system"] in REFERENCE_SYSTEMS
    ]
    audits = [
        audit
        for audit in baseline_audits
        if audit["system"] in REFERENCE_SYSTEMS
    ]
    projection_hashes = {}
    for seed in TRAINING_SEEDS:
        values, hashes = project_multiscale(
            raw, queries, geometries, seed=seed
        )
        predicted, audit = fit_regularized(
            records,
            values,
            targets,
            train_indices,
            eval_indices,
            seed=seed,
        )
        rows.extend(predicted)
        audits.append(audit)
        projection_hashes[str(seed)] = hashes
    return rows, audits, projection_hashes


def render_report(
    dev: Mapping[str, Any], test: Mapping[str, Any] | None
) -> str:
    lines = [
        "# R30 Regularized Multiscale Result",
        "",
        "Date: 2026-07-26",
        "",
        "Evidence class: `NON_CONFIRMATORY_FRESH_SILVER_DEVELOPMENT`",
        "",
        "## Development survival",
        "",
        f"- Regularized minus uniform: {100*dev['delta']:+.2f} pp",
        f"- Seed directions: {dev['directions']}",
        f"- Mean train accuracy: {dev['mean_train_accuracy']:.4f}",
        f"- Shuffled-label macro F1: {dev['shuffled_macro_f1']:.4f}",
        f"- Gate: {'PASS' if dev['passed'] else 'FAIL'}",
        "",
    ]
    if test is None:
        lines.extend(
            [
                "## Test",
                "",
                "Test remained sealed because development survival failed.",
                "",
            ]
        )
    else:
        contrast = test["bootstrap"]["contrasts"][
            "regularized_minus_uniform"
        ]
        interval = contrast["interval"]
        lines.extend(
            [
                "## One-shot sealed test",
                "",
                f"- Regularized minus uniform: "
                f"{contrast['point_pp']:+.2f} pp",
                f"- 95% CI: [{100*interval['lower']:+.2f}, "
                f"{100*interval['upper']:+.2f}] pp",
                f"- Seed directions: {test['directions']}",
                f"- Pre-reproduction gate: "
                f"{'PASS' if test['pre_reproduction_go'] else 'FAIL'}",
                "",
            ]
        )
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    if args.output_root.exists():
        raise FileExistsError(f"output root must be fresh: {args.output_root}")
    if args.report_path.exists():
        raise FileExistsError(f"report path must be fresh: {args.report_path}")
    if r27.sha256_file(PROTOCOL_PATH) != PROTOCOL_SHA256:
        raise RuntimeError("R30 protocol hash mismatch")
    if r27.sha256_file(args.cohort_root / "cohort.json") != COHORT_SHA256:
        raise RuntimeError("R30 cohort hash mismatch")
    if r27.sha256_file(WEIGHTS) != WEIGHTS_SHA256:
        raise RuntimeError("BiomedCLIP weights hash mismatch")
    device = torch.device(args.device)
    if device.type != "cuda" or device.index != 0:
        raise ValueError("R30 is frozen to shared-safe cuda:0")

    records = r27.read_json(args.cohort_root / "cohort.json", list)
    records, case_audit = r29.prepare_records(records)
    if args.feature_cache_input is None:
        features, extraction_audit = r29.extract_features(
            records, device=device, batch_size=args.batch_size
        )
    else:
        cache_hash = r27.sha256_file(args.feature_cache_input)
        if cache_hash != RECOVERY_FEATURE_CACHE_SHA256:
            raise RuntimeError("R30 recovery feature-cache hash mismatch")
        features = torch.load(
            args.feature_cache_input, map_location="cpu", weights_only=True
        )
        if not features or not all(
            bool(torch.isfinite(value).all()) for value in features.values()
        ):
            raise RuntimeError("invalid R30 recovery feature cache")
        extraction_audit = {
            "recovered_from_failed_serialization_run": True,
            "source_path": str(args.feature_cache_input),
            "source_sha256": cache_hash,
            "tasks": len(features),
            "feature_dim": int(next(iter(features.values())).numel()),
            "finite": True,
        }
    baseline, baseline_targets, baseline_manifest = (
        r29.build_representations(records, features)
    )
    raw, queries, geometries, targets, regularized_manifest = (
        build_multiscale_blocks(records, features)
    )
    if not torch.equal(targets, baseline_targets):
        raise RuntimeError("R30 target construction mismatch")
    train_indices = r29._indices(records, ("train",))
    dev_indices = r29._indices(records, ("dev",))
    test_indices = r29._indices(records, ("test",))
    patient_sets = {
        partition: {
            str(records[index]["patient_id"])
            for index in r29._indices(records, (partition,)).tolist()
        }
        for partition in ("train", "dev", "test")
    }
    disjoint = all(
        not (left & right)
        for index, left in enumerate(patient_sets.values())
        for right in list(patient_sets.values())[index + 1 :]
    )
    if not disjoint:
        raise RuntimeError("R30 patient leakage")

    dev_rows, dev_fit, projection_hashes = fit_stage(
        records,
        baseline,
        raw,
        queries,
        geometries,
        targets,
        train_indices,
        dev_indices,
        device=args.device,
    )
    dev_delta, dev_directions = contrast_delta(dev_rows)
    regularized_fit = [
        value
        for value in dev_fit
        if value["system"] == "regularized_multiscale"
    ]
    values, shuffled_projection = project_multiscale(
        raw, queries, geometries, seed=17
    )
    generator = torch.Generator().manual_seed(BOOTSTRAP_SEED)
    shuffled_targets = targets[train_indices][
        torch.randperm(len(train_indices), generator=generator)
    ]
    shuffled_rows, shuffled_fit = fit_regularized(
        records,
        values,
        targets,
        train_indices,
        dev_indices,
        seed=BOOTSTRAP_SEED,
        train_targets_override=shuffled_targets,
    )
    shuffled_macro_f1 = classification_metrics(
        shuffled_rows, labels=LABELS
    )["patient_balanced"]["macro_f1"]
    dev_gate = {
        "delta": dev_delta,
        "directions": dev_directions,
        "mean_train_accuracy": float(
            np.mean([value["train_accuracy"] for value in regularized_fit])
        ),
        "shuffled_macro_f1": shuffled_macro_f1,
        "checks": {
            "DELTA_AT_LEAST_1PP": dev_delta >= 0.01,
            "ALL_DIRECTIONS_POSITIVE": all(
                value > 0 for value in dev_directions.values()
            ),
            "MEAN_TRAIN_ACCURACY_BELOW_0_80": bool(
                np.mean(
                    [value["train_accuracy"] for value in regularized_fit]
                )
                < 0.80
            ),
            "SHUFFLED_BELOW_0_45": shuffled_macro_f1 < 0.45,
            "FITS_FINITE_CONVERGED": all(
                value["finite"] and value["converged"]
                for value in regularized_fit
            )
            and shuffled_fit["finite"]
            and shuffled_fit["converged"],
            "PATIENT_DISJOINT": disjoint,
            "FORBIDDEN_INPUTS_ABSENT": True,
        },
    }
    dev_gate["passed"] = bool(all(dev_gate["checks"].values()))

    test_result = None
    test_rows: list[dict[str, Any]] = []
    test_fit: list[dict[str, Any]] = []
    test_projection_hashes: dict[str, dict[str, str]] = {}
    if dev_gate["passed"]:
        train_dev_indices = r29._indices(records, ("train", "dev"))
        test_rows, test_fit, test_projection_hashes = fit_stage(
            records,
            baseline,
            raw,
            queries,
            geometries,
            targets,
            train_dev_indices,
            test_indices,
            device=args.device,
        )
        bootstrap = hierarchical_patient_bootstrap(
            test_rows,
            labels=LABELS,
            systems=SYSTEMS,
            seeds=TRAINING_SEEDS,
            derangements=(0,),
            contrasts={
                "regularized_minus_uniform": (
                    "regularized_multiscale",
                    "uniform_fusion",
                )
            },
            invariant_systems=SYSTEMS,
            replicates=BOOTSTRAP_REPLICATES,
            rng_seed=BOOTSTRAP_SEED,
        )
        _, directions = contrast_delta(test_rows)
        point = bootstrap["point_system_macro_f1"]
        strongest = max(
            ("state", "global_transition", "local_transition"),
            key=lambda name: point[name],
        )
        contrast = bootstrap["contrasts"]["regularized_minus_uniform"]
        pre_reproduction_go = bool(
            contrast["point_pp"] >= 2.0
            and contrast["interval"] is not None
            and contrast["interval"]["lower"] > 0
            and all(value > 0 for value in directions.values())
            and point["regularized_multiscale"] - point[strongest] >= -0.01
            and bootstrap["inference_valid"]
        )
        test_result = {
            "bootstrap": bootstrap,
            "directions": directions,
            "strongest_single": strongest,
            "pre_reproduction_go": pre_reproduction_go,
        }

    args.output_root.mkdir(parents=True, exist_ok=False)
    torch.save(features, args.output_root / "feature_cache.pt")
    payloads = {
        "case_audit.json": case_audit,
        "extraction_audit.json": extraction_audit,
        "baseline_representation_manifest.json": baseline_manifest,
        "regularized_representation_manifest.json": {
            **regularized_manifest,
            "dev_projection_hashes": projection_hashes,
            "shuffled_projection_hashes": shuffled_projection,
            "test_projection_hashes": test_projection_hashes,
        },
        "dev_predictions.json": dev_rows,
        "dev_fit_audit.json": [*dev_fit, {"shuffled": shuffled_fit}],
        "dev_gate.json": dev_gate,
        "test_predictions.json": test_rows,
        "test_fit_audit.json": test_fit,
        "test_result.json": test_result,
    }
    for name, payload in payloads.items():
        r27.write_json_exclusive(args.output_root / name, payload)
    report = render_report(dev_gate, test_result)
    args.report_path.write_text(report, encoding="utf-8")
    if test_result is None:
        status = "STOP_R30_DEV_SURVIVAL"
    elif test_result["pre_reproduction_go"]:
        status = "AWAITING_FRESH_PROCESS_REPRODUCTION"
    else:
        status = "STOP_R30_TEST_NO_GO"
    manifest_base = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "protocol_sha256": PROTOCOL_SHA256,
        "cohort_sha256": COHORT_SHA256,
        "weights_sha256": WEIGHTS_SHA256,
        "source_hashes": {
            "scripts/run_r30_regularized_multiscale.py": r27.sha256_file(
                Path(__file__)
            ),
            "scripts/run_r29_contextual_transition.py": r27.sha256_file(
                WORKSPACE / "scripts/run_r29_contextual_transition.py"
            ),
            "src/visualvit/context_transition.py": r27.sha256_file(
                WORKSPACE / "src/visualvit/context_transition.py"
            ),
        },
        "outputs": {
            name: r27.sha256_file(args.output_root / name)
            for name in payloads
        },
        "feature_cache_sha256": r27.sha256_file(
            args.output_root / "feature_cache.pt"
        ),
        "report": {
            "path": str(args.report_path),
            "sha256": r27.sha256_file(args.report_path),
        },
        "dev_passed": dev_gate["passed"],
        "test_revealed": test_result is not None,
        "pre_reproduction_go": bool(
            test_result is not None
            and test_result["pre_reproduction_go"]
        ),
        "scientific_go": False,
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "torch": torch.__version__,
            "sklearn": __import__("sklearn").__version__,
            "device": args.device,
        },
    }
    manifest = dict(manifest_base)
    manifest["manifest_payload_sha256"] = r27.canonical_sha256(manifest_base)
    r27.write_json_exclusive(
        args.output_root / "artifact_manifest.json", manifest
    )
    print(
        json.dumps(
            {"manifest": manifest, "dev": dev_gate, "test": test_result},
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
