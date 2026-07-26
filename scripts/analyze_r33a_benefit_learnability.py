from __future__ import annotations

# ruff: noqa: E402

import argparse
import json
from pathlib import Path
import sys
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE))
sys.path.insert(0, str(WORKSPACE / "src"))

import torch
from torch import Tensor
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from scripts.run_r33_token_survival import (
    SEEDS,
    benefit_router_features,
    benefit_router_targets,
    fit_benefit_router,
    weighted_confusion,
)


FEATURES_DEFAULT = Path(
    r"F:\VisualVIT_runtime\050_routeC\r33a_case_study"
    r"\anatomy_context_features_v1\token_features.pt"
)
PREDICTIONS_DEFAULT = Path(
    r"F:\VisualVIT_runtime\050_routeC\r33a_case_study"
    r"\attempt_d_anatomy_context_v1\r33_oof_predictions.pt"
)
OUTPUT_DEFAULT = Path(
    r"F:\VisualVIT_runtime\050_routeC\r33a_case_study"
    r"\benefit_learnability_v3\result.json"
)
THRESHOLDS = (0.50, 0.55, 0.60, 0.65, 0.70, 0.75)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Cross-fold audit of R33A rich-benefit learnability"
    )
    parser.add_argument("--features", type=Path, default=FEATURES_DEFAULT)
    parser.add_argument("--predictions", type=Path, default=PREDICTIONS_DEFAULT)
    parser.add_argument("--output", type=Path, default=OUTPUT_DEFAULT)
    return parser.parse_args()


def token_geometry_features(
    robust: dict[int, Tensor], rich: dict[int, Tensor]
) -> Tensor:
    rows = next(iter(robust.values())).shape[0]
    output = []
    for seed in SEEDS:
        left = robust[seed].float()
        right = rich[seed].float()
        if left.shape != right.shape or left.shape != (rows, 774):
            raise ValueError("token feature shape drift")
        for token_type in range(6):
            start = token_type * 64
            max_start = 384 + token_type * 64
            left_type = torch.cat(
                (
                    left[:, start : start + 64],
                    left[:, max_start : max_start + 64],
                ),
                dim=1,
            )
            right_type = torch.cat(
                (
                    right[:, start : start + 64],
                    right[:, max_start : max_start + 64],
                ),
                dim=1,
            )
            difference = right_type - left_type
            output.extend(
                (
                    left_type.norm(dim=1, keepdim=True),
                    right_type.norm(dim=1, keepdim=True),
                    difference.norm(dim=1, keepdim=True),
                    torch.nn.functional.cosine_similarity(
                        left_type, right_type, dim=1
                    ).unsqueeze(1),
                    difference.abs().mean(dim=1, keepdim=True),
                )
            )
        # Preserve outcome-free query/anatomy identity at useful resolution.
        output.append(left[:, :64])
        output.append(left[:, 384:448])
    return torch.cat(output, dim=1)


def finding_interaction_features(base: Tensor, findings: list[str]) -> Tensor:
    if base.shape[0] != len(findings):
        raise ValueError("finding features must align with rows")
    vocabulary = sorted(set(findings))
    index = {value: position for position, value in enumerate(vocabulary)}
    one_hot = torch.zeros(len(findings), len(vocabulary))
    one_hot[
        torch.arange(len(findings)),
        torch.tensor([index[value] for value in findings]),
    ] = 1
    interactions = (one_hot[:, :, None] * base[:, None, :]).reshape(len(findings), -1)
    return torch.cat((base, one_hot, interactions), dim=1)


def route_metrics(
    labels: Tensor,
    robust: Tensor,
    rich: Tensor,
    route: Tensor,
    patient_ids: list[str],
) -> dict[str, float]:
    selected = torch.where(route[None], rich, robust)
    robust_correct = robust.eq(labels[None])
    rich_correct = rich.eq(labels[None])
    helped = (~robust_correct) & rich_correct
    harmed = robust_correct & (~rich_correct)
    chosen = route[None].expand_as(helped)
    return {
        "macro_f1": float(
            weighted_confusion(labels, selected, patient_ids)["macro_f1"]
        ),
        "rich_coverage": float(route.float().mean()),
        "selected_help_units": int((chosen & helped).sum()),
        "selected_harm_units": int((chosen & harmed).sum()),
        "net_selected_help_minus_harm": int(
            (chosen & helped).sum() - (chosen & harmed).sum()
        ),
    }


def fit_router_probabilities(
    train_features: Tensor,
    train_targets: Tensor,
    eval_features: Tensor,
    *,
    seed: int,
) -> Tensor:
    model = make_pipeline(
        StandardScaler(),
        LogisticRegression(
            C=0.1,
            class_weight="balanced",
            max_iter=1_000,
            random_state=seed,
        ),
    )
    model.fit(train_features.numpy(), train_targets.numpy())
    return torch.from_numpy(model.predict_proba(eval_features.numpy())[:, 1]).float()


def main() -> int:
    args = parse_args()
    if args.output.exists():
        raise FileExistsError(f"output must be fresh: {args.output}")
    feature_payload = torch.load(args.features, map_location="cpu", weights_only=False)
    prediction_payload = torch.load(
        args.predictions, map_location="cpu", weights_only=False
    )
    records = feature_payload["records"]
    labels = prediction_payload["labels"]
    folds = prediction_payload["folds"]
    patient_ids = [str(row["patient_id"]) for row in records]
    robust_predictions = prediction_payload["predictions"]["P3"]
    rich_predictions = prediction_payload["predictions"]["P4"]
    robust_logits = prediction_payload["probabilities"]["P3"].clamp_min(1e-8).log()
    rich_logits = prediction_payload["probabilities"]["P4"].clamp_min(1e-8).log()
    targets, decisive, score = benefit_router_targets(
        robust_logits, rich_logits, labels
    )
    logits_only = benefit_router_features(robust_logits, rich_logits)
    logits_finding = finding_interaction_features(
        logits_only, [str(row["finding_token"]) for row in records]
    )
    geometry = token_geometry_features(
        {
            int(seed): value
            for seed, value in feature_payload["features"]["robust"].items()
        },
        {
            int(seed): value
            for seed, value in feature_payload["features"]["rich"].items()
        },
    )
    systems = {
        "logits_only": logits_only,
        "logits_plus_finding_interactions": logits_finding,
        "logits_plus_token_geometry": torch.cat((logits_only, geometry), dim=1),
    }
    results: dict[str, Any] = {}
    for system, values in systems.items():
        route = torch.empty(len(records), dtype=torch.bool)
        route_probability = torch.empty(len(records), dtype=torch.float32)
        fold_audits = []
        for fold in range(5):
            evaluation = folds.eq(fold)
            fitting = (~evaluation) & decisive
            route[evaluation], audit = fit_benefit_router(
                values[fitting],
                targets[fitting],
                values[evaluation],
                seed=20263500 + fold,
            )
            route_probability[evaluation] = fit_router_probabilities(
                values[fitting],
                targets[fitting],
                values[evaluation],
                seed=20263500 + fold,
            )
            fold_audits.append(
                {
                    "fold": fold,
                    "decisive_eval_rows": int((evaluation & decisive).sum()),
                    "decisive_eval_accuracy": float(
                        route[evaluation & decisive]
                        .eq(targets[evaluation & decisive].bool())
                        .float()
                        .mean()
                    ),
                    **audit,
                }
            )
        results[system] = {
            "route": route_metrics(
                labels,
                robust_predictions,
                rich_predictions,
                route,
                patient_ids,
            ),
            "fold_audits": fold_audits,
            "mean_decisive_eval_accuracy": sum(
                row["decisive_eval_accuracy"] for row in fold_audits
            )
            / len(fold_audits),
            "threshold_curve": {
                f"{threshold:.2f}": route_metrics(
                    labels,
                    robust_predictions,
                    rich_predictions,
                    route_probability.ge(threshold),
                    patient_ids,
                )
                for threshold in THRESHOLDS
            },
        }
    robust_f1 = weighted_confusion(labels, robust_predictions, patient_ids)["macro_f1"]
    result = {
        "schema": "visualvit.r33a.benefit-learnability.v1",
        "status": "PASS_R33A_BENEFIT_LEARNABILITY_AUDIT",
        "scope": "train_only_cross_fold_case_study",
        "records": len(records),
        "patients": len(set(patient_ids)),
        "decisive_rows": int(decisive.sum()),
        "positive_benefit_rows": int(score.gt(0).sum()),
        "negative_benefit_rows": int(score.lt(0).sum()),
        "robust_macro_f1": robust_f1,
        "systems": results,
        "dev_case_outcomes_inspected": False,
        "sealed_test_records_read": False,
        "sealed_test_images_read": False,
        "gold_outcomes_read": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=False)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
