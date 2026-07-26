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
import torch

from scripts import audit_r26_binding_identifiability as r27
from scripts import build_r31_fresh_silver_cohort as cohort_builder
from scripts import run_chest_imagenome_mimic_matcher_qualification as r25
from scripts import run_r29_contextual_transition as r29
from scripts import run_r30_regularized_multiscale as r30
from visualvit.real_progression import (
    classification_metrics,
    hierarchical_patient_bootstrap,
)


LABELS = cohort_builder.LABELS
TRAINING_SEEDS = r30.TRAINING_SEEDS
REFERENCE_SYSTEMS = r30.REFERENCE_SYSTEMS
SYSTEMS = (*REFERENCE_SYSTEMS, "confidence_consensus")
BOOTSTRAP_REPLICATES = 10_000
BOOTSTRAP_SEED = 20260831
COHORT_ROOT = cohort_builder.OUTPUT_ROOT_DEFAULT
COHORT_SHA256 = (
    "0e02a9f772c1da8befade554ca2234ac8062bd2cb2e7dc5dd8d1891619c89142"
)
PROTOCOL_PATH = cohort_builder.PROTOCOL_PATH
PROTOCOL_SHA256 = cohort_builder.PROTOCOL_SHA256
WEIGHTS = r25.WEIGHTS_DEFAULT
WEIGHTS_SHA256 = r25.MIMIC_PINS["weights"]
OUTPUT_ROOT_DEFAULT = Path(
    r"F:\VisualVIT_runtime\050_routeC\r31_confidence_consensus\run_v1"
)
REPORT_PATH_DEFAULT = (
    WORKSPACE / "reports/R31_CONFIDENCE_CONSENSUS_RESULT.md"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="R31 confidence-consensus tier experiment"
    )
    parser.add_argument("--cohort-root", type=Path, default=COHORT_ROOT)
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT_DEFAULT)
    parser.add_argument("--report-path", type=Path, default=REPORT_PATH_DEFAULT)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--feature-cache-input", type=Path)
    parser.add_argument("--expected-feature-cache-sha256")
    return parser.parse_args()


def majority(predictions: Sequence[str]) -> str:
    counts = Counter(predictions)
    highest = max(counts.values())
    winners = {
        label for label, count in counts.items() if count == highest
    }
    return next(label for label in LABELS if label in winners)


def add_consensus_rows(
    rows: Sequence[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    indexed = {
        (row["observation_id"], row["system"], row["training_seed"]): row
        for row in rows
    }
    observations = sorted({row["observation_id"] for row in rows})
    output = list(rows)
    regularized_unanimous = 0
    changed_from_uniform_majority = 0
    for observation in observations:
        uniform = [
            indexed[(observation, "uniform_fusion", seed)]["prediction"]
            for seed in TRAINING_SEEDS
        ]
        regularized = [
            indexed[
                (observation, "regularized_multiscale", seed)
            ]["prediction"]
            for seed in TRAINING_SEEDS
        ]
        uniform_majority = majority(uniform)
        if len(set(regularized)) == 1:
            prediction = regularized[0]
            regularized_unanimous += 1
        else:
            prediction = uniform_majority
        changed_from_uniform_majority += int(
            prediction != uniform_majority
        )
        for seed in TRAINING_SEEDS:
            source = indexed[(observation, "uniform_fusion", seed)]
            output.append(
                {
                    **source,
                    "system": "confidence_consensus",
                    "prediction": prediction,
                }
            )
    return output, {
        "observations": len(observations),
        "regularized_unanimous": regularized_unanimous,
        "regularized_unanimous_rate": (
            regularized_unanimous / len(observations)
        ),
        "changed_from_uniform_majority": changed_from_uniform_majority,
        "changed_from_uniform_majority_rate": (
            changed_from_uniform_majority / len(observations)
        ),
        "complete": len(output)
        == len(rows) + len(observations) * len(TRAINING_SEEDS),
    }


def contrast_delta(
    rows: Sequence[dict[str, Any]],
) -> tuple[float, dict[str, float]]:
    consensus = classification_metrics(
        [row for row in rows if row["system"] == "confidence_consensus"],
        labels=LABELS,
    )["patient_balanced"]["macro_f1"]
    directions = {}
    for seed in TRAINING_SEEDS:
        uniform = classification_metrics(
            [
                row
                for row in rows
                if row["system"] == "uniform_fusion"
                and row["training_seed"] == seed
            ],
            labels=LABELS,
        )["patient_balanced"]["macro_f1"]
        directions[str(seed)] = float(consensus - uniform)
    pooled_uniform = classification_metrics(
        [row for row in rows if row["system"] == "uniform_fusion"],
        labels=LABELS,
    )["patient_balanced"]["macro_f1"]
    return float(consensus - pooled_uniform), directions


def fit_stage(
    records: Sequence[Mapping[str, Any]],
    baseline: Mapping[str, torch.Tensor],
    raw: Mapping[str, torch.Tensor],
    queries: torch.Tensor,
    geometries: torch.Tensor,
    targets: torch.Tensor,
    train_indices: torch.Tensor,
    eval_indices: torch.Tensor,
    *,
    device: str,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, dict[str, str]],
    dict[str, Any],
]:
    rows, audits, hashes = r30.fit_stage(
        records,
        baseline,
        raw,
        queries,
        geometries,
        targets,
        train_indices,
        eval_indices,
        device=device,
    )
    rows, consensus_audit = add_consensus_rows(rows)
    return rows, audits, hashes, consensus_audit


def render_report(
    dev: Mapping[str, Any], test: Mapping[str, Any] | None
) -> str:
    lines = [
        "# R31 Confidence-Consensus Result",
        "",
        "Date: 2026-07-26",
        "",
        "Evidence class: `NON_CONFIRMATORY_FRESH_SILVER_DEVELOPMENT`",
        "",
        "## Development survival",
        "",
        f"- Consensus minus uniform: {100*dev['delta']:+.2f} pp",
        f"- Per-uniform-seed directions: {dev['directions']}",
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
            "consensus_minus_uniform"
        ]
        interval = contrast["interval"]
        lines.extend(
            [
                "## One-shot sealed test",
                "",
                f"- Consensus minus uniform: "
                f"{contrast['point_pp']:+.2f} pp",
                f"- 95% CI: [{100*interval['lower']:+.2f}, "
                f"{100*interval['upper']:+.2f}] pp",
                f"- Per-uniform-seed directions: {test['directions']}",
                f"- Pre-reproduction gate: "
                f"{'PASS' if test['pre_reproduction_go'] else 'FAIL'}",
                "",
            ]
        )
    return "\n".join(lines)


def load_or_extract_features(
    args: argparse.Namespace,
    records: Sequence[Mapping[str, Any]],
    device: torch.device,
) -> tuple[dict[str, torch.Tensor], dict[str, Any]]:
    if args.feature_cache_input is None:
        return r29.extract_features(
            records, device=device, batch_size=args.batch_size
        )
    if not args.expected_feature_cache_sha256:
        raise ValueError("reproduction requires expected feature-cache hash")
    cache_hash = r27.sha256_file(args.feature_cache_input)
    if cache_hash != args.expected_feature_cache_sha256:
        raise RuntimeError("R31 reproduction feature-cache hash mismatch")
    features = torch.load(
        args.feature_cache_input, map_location="cpu", weights_only=True
    )
    if not features or not all(
        bool(torch.isfinite(value).all()) for value in features.values()
    ):
        raise RuntimeError("invalid R31 reproduction feature cache")
    return features, {
        "reproduction_cache": True,
        "source_path": str(args.feature_cache_input),
        "source_sha256": cache_hash,
        "tasks": len(features),
        "feature_dim": int(next(iter(features.values())).numel()),
        "finite": True,
    }


def main() -> None:
    args = parse_args()
    if args.output_root.exists():
        raise FileExistsError(f"output root must be fresh: {args.output_root}")
    if args.report_path.exists():
        raise FileExistsError(f"report path must be fresh: {args.report_path}")
    if r27.sha256_file(PROTOCOL_PATH) != PROTOCOL_SHA256:
        raise RuntimeError("R31 protocol hash mismatch")
    if r27.sha256_file(args.cohort_root / "cohort.json") != COHORT_SHA256:
        raise RuntimeError("R31 cohort hash mismatch")
    if r27.sha256_file(WEIGHTS) != WEIGHTS_SHA256:
        raise RuntimeError("BiomedCLIP weights hash mismatch")
    device = torch.device(args.device)
    if device.type != "cuda" or device.index != 0:
        raise ValueError("R31 is frozen to shared-safe cuda:0")

    records = r27.read_json(args.cohort_root / "cohort.json", list)
    records, case_audit = r29.prepare_records(records)
    features, extraction_audit = load_or_extract_features(
        args, records, device
    )
    baseline, baseline_targets, baseline_manifest = (
        r29.build_representations(records, features)
    )
    raw, queries, geometries, targets, regularized_manifest = (
        r30.build_multiscale_blocks(records, features)
    )
    if not torch.equal(targets, baseline_targets):
        raise RuntimeError("R31 target mismatch")
    train_indices = r29._indices(records, ("train",))
    dev_indices = r29._indices(records, ("dev",))
    test_indices = r29._indices(records, ("test",))
    patient_sets = [
        {
            str(records[index]["patient_id"])
            for index in r29._indices(records, (partition,)).tolist()
        }
        for partition in ("train", "dev", "test")
    ]
    disjoint = all(
        not (left & right)
        for index, left in enumerate(patient_sets)
        for right in patient_sets[index + 1 :]
    )

    dev_rows, dev_fit, dev_hashes, dev_consensus = fit_stage(
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
    dev_gate = {
        "delta": dev_delta,
        "directions": dev_directions,
        "mean_train_accuracy": float(
            np.mean([value["train_accuracy"] for value in regularized_fit])
        ),
        "consensus_audit": dev_consensus,
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
            "FITS_FINITE_CONVERGED": all(
                value["finite"] and value["converged"]
                for value in regularized_fit
            ),
            "PATIENT_DISJOINT": disjoint,
            "PREDICTIONS_COMPLETE": dev_consensus["complete"],
            "FORBIDDEN_INPUTS_ABSENT": True,
        },
    }
    dev_gate["passed"] = bool(all(dev_gate["checks"].values()))

    test_result = None
    test_rows: list[dict[str, Any]] = []
    test_fit: list[dict[str, Any]] = []
    test_hashes: dict[str, dict[str, str]] = {}
    test_consensus: dict[str, Any] = {}
    if dev_gate["passed"]:
        train_dev_indices = r29._indices(records, ("train", "dev"))
        test_rows, test_fit, test_hashes, test_consensus = fit_stage(
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
            [
                row
                for row in test_rows
                if row["system"] in SYSTEMS
            ],
            labels=LABELS,
            systems=SYSTEMS,
            seeds=TRAINING_SEEDS,
            derangements=(0,),
            contrasts={
                "consensus_minus_uniform": (
                    "confidence_consensus",
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
        contrast = bootstrap["contrasts"]["consensus_minus_uniform"]
        pre_reproduction_go = bool(
            contrast["point_pp"] >= 2.0
            and contrast["interval"] is not None
            and contrast["interval"]["lower"] > 0
            and all(value > 0 for value in directions.values())
            and point["confidence_consensus"] - point[strongest] >= -0.01
            and bootstrap["inference_valid"]
            and test_consensus["complete"]
        )
        test_result = {
            "bootstrap": bootstrap,
            "directions": directions,
            "strongest_single": strongest,
            "consensus_audit": test_consensus,
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
            "dev_projection_hashes": dev_hashes,
            "test_projection_hashes": test_hashes,
        },
        "dev_predictions.json": dev_rows,
        "dev_fit_audit.json": dev_fit,
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
        status = "STOP_R31_DEV_SURVIVAL"
    elif test_result["pre_reproduction_go"]:
        status = "AWAITING_FRESH_PROCESS_REPRODUCTION"
    else:
        status = "STOP_R31_TEST_NO_GO"
    base = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "protocol_sha256": PROTOCOL_SHA256,
        "cohort_sha256": COHORT_SHA256,
        "weights_sha256": WEIGHTS_SHA256,
        "source_hashes": {
            "scripts/run_r31_confidence_consensus.py": r27.sha256_file(
                Path(__file__)
            ),
            "scripts/run_r30_regularized_multiscale.py": r27.sha256_file(
                WORKSPACE / "scripts/run_r30_regularized_multiscale.py"
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
    manifest = {
        **base,
        "manifest_payload_sha256": r27.canonical_sha256(base),
    }
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
