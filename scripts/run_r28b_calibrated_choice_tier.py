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

import torch

from scripts import audit_r26_binding_identifiability as r27
from scripts import run_r28_tier_mvp as r28
from visualvit.real_progression import deterministic_patient_folds, fold_audit
from visualvit.tier import EXPERT_NAMES
from visualvit.tier_choice import (
    apply_temperatures,
    fit_choice_router,
    fit_scalar_temperatures,
    select_routed_logits,
)


PROTOCOL_PATH = (
    WORKSPACE
    / "docs/superpowers/specs/2026-07-26-r28b-calibrated-choice-tier-v1.md"
)
PROTOCOL_SHA256 = (
    "9f5fe2779662f1b976dbf2df5f3dab88d48d5e596e8290b4e784e9f233207034"
)
OUTPUT_ROOT_DEFAULT = Path(
    r"F:\VisualVIT_runtime\050_routeC\r28_case_study_tier\tier_r28b_v1"
)
REPORT_PATH_DEFAULT = WORKSPACE / "reports/R28B_CALIBRATED_CHOICE_TIER_RESULT.md"
TEMPERATURE_STEPS = 300
TEMPERATURE_LEARNING_RATE = 0.03
GUARD_MINIMUM_PROBABILITY = 0.60
GUARD_MINIMUM_MARGIN = 0.15
SYSTEM_B1 = "tier_b1_choice_hard"
SYSTEM_B2 = "tier_b2_choice_guarded"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="R28b calibrated choice-supervised TIER"
    )
    parser.add_argument(
        "--cohort", type=Path, default=r27.R26_ROOT_DEFAULT / "cohort.json"
    )
    parser.add_argument("--features", type=Path, default=r28.FEATURE_CACHE)
    parser.add_argument("--case-root", type=Path, default=r28.CASE_ROOT)
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT_DEFAULT)
    parser.add_argument("--report-path", type=Path, default=REPORT_PATH_DEFAULT)
    parser.add_argument("--device", default="cpu")
    return parser.parse_args()


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
            "prediction": r28.LABELS[int(prediction)],
            "weight": 1.0 / patient_sizes[str(record["patient_id"])],
        }
        for record, prediction in zip(records, predictions.tolist(), strict=True)
    ]


def run_choice_attempts(
    records: Sequence[dict[str, Any]],
    cache: Mapping[tuple[int, int], Mapping[str, Any]],
    *,
    device: str,
) -> tuple[
    dict[str, list[dict[str, Any]]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    predictions = {
        system: {
            seed: torch.empty(len(records), dtype=torch.long)
            for seed in r28.TRAINING_SEEDS
        }
        for system in (SYSTEM_B1, SYSTEM_B2)
    }
    fit_audit = []
    route_audit = []
    for seed in r28.TRAINING_SEEDS:
        for outer_fold in range(r28.OUTER_FOLDS):
            item = cache[(seed, outer_fold)]
            temperatures, temperature_fit = fit_scalar_temperatures(
                item["inner_logits"],
                item["train_targets"],
                steps=TEMPERATURE_STEPS,
                learning_rate=TEMPERATURE_LEARNING_RATE,
                device=device,
            )
            train_logits = apply_temperatures(
                item["inner_logits"], temperatures
            )
            test_logits = apply_temperatures(
                item["outer_logits"], temperatures
            )
            route_probabilities, route_fit = fit_choice_router(
                item["train_router_base"],
                train_logits,
                item["train_targets"],
                item["test_router_base"],
                test_logits,
                seed=seed + outer_fold * 100_000 + 80_000,
                steps=r28.ROUTER_STEPS,
                learning_rate=r28.LEARNING_RATE,
                weight_decay=r28.WEIGHT_DECAY,
                device=device,
            )
            hard_logits, hard_choices, hard_accepted = select_routed_logits(
                test_logits, route_probabilities, mode="hard"
            )
            guarded_logits, guarded_choices, guarded_accepted = (
                select_routed_logits(
                    test_logits,
                    route_probabilities,
                    mode="guarded",
                    fallback_expert=1,
                    minimum_probability=GUARD_MINIMUM_PROBABILITY,
                    minimum_margin=GUARD_MINIMUM_MARGIN,
                )
            )
            test_indices = item["outer_test"]
            predictions[SYSTEM_B1][seed][test_indices] = hard_logits.argmax(-1)
            predictions[SYSTEM_B2][seed][test_indices] = (
                guarded_logits.argmax(-1)
            )
            fit_audit.extend(
                (
                    {
                        "stage": "temperature_calibration",
                        "training_seed": seed,
                        "outer_fold": outer_fold,
                        **temperature_fit,
                    },
                    {
                        "stage": "choice_router",
                        "training_seed": seed,
                        "outer_fold": outer_fold,
                        **route_fit,
                    },
                )
            )
            for local_index, global_index in enumerate(test_indices.tolist()):
                record = records[global_index]
                route_audit.append(
                    {
                        "training_seed": seed,
                        "outer_fold": outer_fold,
                        "observation_id": str(record["qualification_id"]),
                        "probabilities": {
                            expert: float(
                                route_probabilities[
                                    local_index, expert_index
                                ]
                            )
                            for expert_index, expert in enumerate(EXPERT_NAMES)
                        },
                        "hard_choice": EXPERT_NAMES[int(hard_choices[local_index])],
                        "hard_accepted": bool(hard_accepted[local_index]),
                        "guarded_choice": EXPERT_NAMES[
                            int(guarded_choices[local_index])
                        ],
                        "guarded_accepted": bool(
                            guarded_accepted[local_index]
                        ),
                    }
                )
            print(
                json.dumps(
                    {
                        "stage": "r28b_outer_fold",
                        "training_seed": seed,
                        "outer_fold": outer_fold,
                        "temperatures": temperature_fit["temperatures"],
                        "guarded_acceptance": float(
                            guarded_accepted.float().mean()
                        ),
                    }
                ),
                flush=True,
            )
    rows = {
        system: [
            row
            for seed in r28.TRAINING_SEEDS
            for row in _prediction_rows(
                records, system, seed, predictions[system][seed]
            )
        ]
        for system in (SYSTEM_B1, SYSTEM_B2)
    }
    return rows, fit_audit, route_audit


def render_report(
    attempts: Sequence[Mapping[str, Any]],
    *,
    guarded_acceptance: float,
) -> str:
    lines = [
        "# R28b Calibrated Choice-Supervised TIER Result",
        "",
        "Date: 2026-07-26",
        "",
        "Evidence class: `NON_CONFIRMATORY_R28B_DEVELOPMENT`",
        "",
        "## Boundary",
        "",
        "R28b is a separate failure-derived attempt. Temperatures and route "
        "targets use only nested inner-OOF logits and outer-training labels; "
        "outer-test inference remains label-free. R28 A1/A2 are unchanged.",
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
            "## Registered diagnostics",
            "",
            f"- Guarded-route acceptance: {100 * guarded_acceptance:.2f}%",
            f"- Final engineering gate: "
            f"{'PASS' if final['engineering_passed'] else 'FAIL'}",
            f"- Final scientific gate: "
            f"{'GO' if final['scientific_go'] else 'NO-GO'}",
            "- Fresh-process reproduction: PENDING",
            "",
            "A scientific NO-GO is retained even when the software pipeline "
            "passes. The registered thresholds, folds, seeds, and cases are not "
            "changed after this result.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    if args.device != "cpu":
        raise ValueError("frozen R28b protocol is CPU-only")
    if args.output_root.exists():
        raise FileExistsError(f"R28b output root must be fresh: {args.output_root}")
    if args.report_path.exists():
        raise FileExistsError(f"R28b report path must be fresh: {args.report_path}")
    if r27.sha256_file(PROTOCOL_PATH) != PROTOCOL_SHA256:
        raise RuntimeError("R28b protocol hash mismatch")
    if r27.sha256_file(args.features) != r28.FEATURE_CACHE_SHA256:
        raise RuntimeError("R25.1 feature cache hash mismatch")
    if (
        r27.sha256_file(args.case_root / "artifact_manifest.json")
        != r28.CASE_MANIFEST_SHA256
    ):
        raise RuntimeError("R28 case-study manifest hash mismatch")

    cohort = r27.read_json(args.cohort, list)
    features = torch.load(args.features, map_location="cpu", weights_only=True)
    if not isinstance(features, dict):
        raise ValueError("feature cache must be a dictionary")
    projected, router_base, targets, feature_manifest = r28.build_representations(
        cohort, features
    )
    outer_assignment = deterministic_patient_folds(
        cohort,
        labels=r28.LABELS,
        fold_count=r28.OUTER_FOLDS,
        salt="r28-tier-outer-v1",
    )
    outer_audit = fold_audit(
        cohort,
        outer_assignment,
        labels=r28.LABELS,
        fold_count=r28.OUTER_FOLDS,
    )
    cache, expert_fit = r28.prepare_nested_cache(
        cohort,
        projected,
        router_base,
        targets,
        outer_assignment,
        device=args.device,
    )
    all_disjoint = outer_audit["patient_disjoint"] and all(
        item["outer_disjoint"]
        and all(value["disjoint"] for value in item["inner_patient_sets"])
        for item in cache.values()
    )
    base_rows = r28.base_prediction_rows(cohort, cache)
    rows_by_system, r28b_fit, route_audit = run_choice_attempts(
        cohort, cache, device=args.device
    )
    all_fit = [*expert_fit, *r28b_fit]
    all_finite = all(item["finite"] for item in all_fit)
    all_rows = [*base_rows, *rows_by_system[SYSTEM_B1]]
    attempts = [
        r28.evaluate_attempt(
            all_rows,
            SYSTEM_B1,
            all_disjoint=all_disjoint,
            all_finite=all_finite,
        )
    ]
    if attempts[0]["engineering_passed"] and not attempts[0]["scientific_go"]:
        all_rows.extend(rows_by_system[SYSTEM_B2])
        attempts.append(
            r28.evaluate_attempt(
                all_rows,
                SYSTEM_B2,
                all_disjoint=all_disjoint,
                all_finite=all_finite,
            )
        )
    final = attempts[-1]
    guarded_rows = [
        row for row in route_audit if row["guarded_accepted"]
    ]
    guarded_acceptance = len(guarded_rows) / len(route_audit)
    status = (
        "AWAITING_FRESH_PROCESS_REPRODUCTION"
        if final["engineering_passed"]
        else "ENGINEERING_FAILURE"
    )

    args.output_root.mkdir(parents=True, exist_ok=False)
    payloads = {
        "feature_manifest.json": feature_manifest,
        "folds.json": {
            "outer_assignment": dict(sorted(outer_assignment.items())),
            "outer_audit": outer_audit,
            "nested_disjoint": all_disjoint,
            "inner_audits": {
                f"{seed}:{fold}": cache[(seed, fold)]["inner_patient_sets"]
                for seed in r28.TRAINING_SEEDS
                for fold in range(r28.OUTER_FOLDS)
            },
        },
        "predictions.json": all_rows,
        "fit_audit.json": all_fit,
        "route_audit.json": route_audit,
        "bootstrap.json": {
            attempt["system"]: attempt["bootstrap"] for attempt in attempts
        },
        "attempt_closure.json": {
            "status": status,
            "attempts": attempts,
            "final_system": final["system"],
            "engineering_passed": final["engineering_passed"],
            "scientific_go": final["scientific_go"],
            "formal_claim_allowed": False,
            "clinical_claim_allowed": False,
            "fresh_confirmation_unlocked": final["scientific_go"],
            "vlm_dive_scaleup_unlocked": False,
        },
    }
    for name, payload in payloads.items():
        r27.write_json_exclusive(args.output_root / name, payload)
    report = render_report(attempts, guarded_acceptance=guarded_acceptance)
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
            "sha256": r28.FEATURE_CACHE_SHA256,
        },
        "case_manifest_sha256": r28.CASE_MANIFEST_SHA256,
        "source_hashes": {
            "scripts/run_r28b_calibrated_choice_tier.py": r27.sha256_file(
                Path(__file__)
            ),
            "src/visualvit/tier.py": r27.sha256_file(
                WORKSPACE / "src/visualvit/tier.py"
            ),
            "src/visualvit/tier_choice.py": r27.sha256_file(
                WORKSPACE / "src/visualvit/tier_choice.py"
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
        "final_system": final["system"],
        "engineering_passed": final["engineering_passed"],
        "scientific_go": final["scientific_go"],
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
                "final_system": final["system"],
                "engineering_passed": final["engineering_passed"],
                "scientific_go": final["scientific_go"],
                "guarded_acceptance": guarded_acceptance,
                "manifest_sha256": r27.sha256_file(
                    args.output_root / "artifact_manifest.json"
                ),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
