from __future__ import annotations

from collections import defaultdict
import random
from typing import Sequence

import torch
from torch import nn
import torch.nn.functional as F


PATIENT_BOOTSTRAP_REPLICATES = 2000
PATIENT_BOOTSTRAP_SEED = 37001


class FindingConditionedLinearProbe(nn.Module):
    def __init__(
        self,
        *,
        feature_dim: int,
        finding_count: int,
        class_count: int,
    ) -> None:
        super().__init__()
        if feature_dim <= 0 or finding_count <= 0 or class_count <= 1:
            raise ValueError("invalid probe dimensions")
        self.feature_dim = feature_dim
        self.finding_count = finding_count
        self.classifier = nn.Linear(
            feature_dim + finding_count, class_count
        )

    def forward(
        self, features: torch.Tensor, finding_indices: torch.Tensor
    ) -> torch.Tensor:
        if features.ndim != 2 or features.shape[1] != self.feature_dim:
            raise ValueError("unexpected probe feature shape")
        one_hot = F.one_hot(
            finding_indices, num_classes=self.finding_count
        ).to(dtype=features.dtype)
        return self.classifier(torch.cat((features, one_hot), dim=-1))


def macro_f1(
    targets: Sequence[int],
    predictions: Sequence[int],
    *,
    class_count: int,
) -> float:
    if len(targets) != len(predictions):
        raise ValueError("target/prediction lengths differ")
    scores = []
    for label in range(class_count):
        true_positive = sum(
            target == label and prediction == label
            for target, prediction in zip(targets, predictions)
        )
        false_positive = sum(
            target != label and prediction == label
            for target, prediction in zip(targets, predictions)
        )
        false_negative = sum(
            target == label and prediction != label
            for target, prediction in zip(targets, predictions)
        )
        denominator = 2 * true_positive + false_positive + false_negative
        scores.append(
            2 * true_positive / denominator if denominator else 0.0
        )
    return sum(scores) / class_count


def patient_bootstrap_difference(
    *,
    patient_ids: Sequence[str],
    targets: Sequence[int],
    true_predictions: Sequence[int],
    control_predictions: Sequence[int],
    class_count: int,
    replicates: int = PATIENT_BOOTSTRAP_REPLICATES,
    seed: int = PATIENT_BOOTSTRAP_SEED,
) -> dict[str, float | int]:
    lengths = {
        len(patient_ids),
        len(targets),
        len(true_predictions),
        len(control_predictions),
    }
    if len(lengths) != 1 or not patient_ids:
        raise ValueError("bootstrap inputs must have one nonzero length")
    if replicates <= 0:
        raise ValueError("bootstrap replicates must be positive")
    rows_by_patient: dict[str, list[int]] = defaultdict(list)
    for index, patient_id in enumerate(patient_ids):
        rows_by_patient[str(patient_id)].append(index)
    patients = sorted(rows_by_patient)
    rng = random.Random(seed)
    differences = []
    for _ in range(replicates):
        sampled_indices = []
        for _ in patients:
            sampled_patient = patients[rng.randrange(len(patients))]
            sampled_indices.extend(rows_by_patient[sampled_patient])
        sampled_targets = [targets[index] for index in sampled_indices]
        sampled_true = [true_predictions[index] for index in sampled_indices]
        sampled_control = [
            control_predictions[index] for index in sampled_indices
        ]
        differences.append(
            100
            * (
                macro_f1(
                    sampled_targets,
                    sampled_true,
                    class_count=class_count,
                )
                - macro_f1(
                    sampled_targets,
                    sampled_control,
                    class_count=class_count,
                )
            )
        )
    ordered = sorted(differences)
    lower_index = int(0.025 * (replicates - 1))
    upper_index = int(0.975 * (replicates - 1))
    observed = 100 * (
        macro_f1(targets, true_predictions, class_count=class_count)
        - macro_f1(targets, control_predictions, class_count=class_count)
    )
    return {
        "observed_difference_pp": observed,
        "ci95_lower_pp": ordered[lower_index],
        "ci95_upper_pp": ordered[upper_index],
        "patients": len(patients),
        "rows": len(patient_ids),
        "replicates": replicates,
        "seed": seed,
    }


def three_seed_survival_gate(
    seed_differences_pp: Sequence[float],
    *,
    pooled_ci_lower_pp: float,
    minimum_gain_pp: float = 2.0,
) -> dict[str, bool | float | list[float]]:
    if len(seed_differences_pp) != 3:
        raise ValueError("R37 requires exactly three seeds")
    mean_gain = sum(seed_differences_pp) / 3
    all_positive = all(value > 0 for value in seed_differences_pp)
    passed = (
        mean_gain >= minimum_gain_pp
        and pooled_ci_lower_pp > 0
        and all_positive
    )
    return {
        "passed": passed,
        "mean_gain_pp": mean_gain,
        "minimum_gain_pp": minimum_gain_pp,
        "pooled_ci_lower_pp": pooled_ci_lower_pp,
        "all_three_seeds_positive": all_positive,
        "seed_differences_pp": list(seed_differences_pp),
    }


def patient_bootstrap_mean_seed_difference(
    *,
    patient_ids: Sequence[str],
    targets: Sequence[int],
    true_predictions_by_seed: Sequence[Sequence[int]],
    control_predictions_by_seed: Sequence[Sequence[int]],
    class_count: int,
    replicates: int = PATIENT_BOOTSTRAP_REPLICATES,
    seed: int = PATIENT_BOOTSTRAP_SEED,
) -> dict[str, float | int | list[float]]:
    if len(true_predictions_by_seed) != 3:
        raise ValueError("R37 requires true predictions from exactly three seeds")
    if len(control_predictions_by_seed) != 3:
        raise ValueError(
            "R37 requires control predictions from exactly three seeds"
        )
    row_count = len(patient_ids)
    sequences = [
        targets,
        *true_predictions_by_seed,
        *control_predictions_by_seed,
    ]
    if row_count == 0 or any(len(values) != row_count for values in sequences):
        raise ValueError("multi-seed bootstrap row lengths differ")
    rows_by_patient: dict[str, list[int]] = defaultdict(list)
    for index, patient_id in enumerate(patient_ids):
        rows_by_patient[str(patient_id)].append(index)
    patients = sorted(rows_by_patient)
    rng = random.Random(seed)

    def seed_differences(indices: Sequence[int]) -> list[float]:
        selected_targets = [targets[index] for index in indices]
        return [
            100
            * (
                macro_f1(
                    selected_targets,
                    [true_values[index] for index in indices],
                    class_count=class_count,
                )
                - macro_f1(
                    selected_targets,
                    [control_values[index] for index in indices],
                    class_count=class_count,
                )
            )
            for true_values, control_values in zip(
                true_predictions_by_seed, control_predictions_by_seed
            )
        ]

    observed_by_seed = seed_differences(range(row_count))
    bootstrap_means = []
    for _ in range(replicates):
        sampled_indices = []
        for _ in patients:
            sampled_patient = patients[rng.randrange(len(patients))]
            sampled_indices.extend(rows_by_patient[sampled_patient])
        differences = seed_differences(sampled_indices)
        bootstrap_means.append(sum(differences) / 3)
    ordered = sorted(bootstrap_means)
    lower_index = int(0.025 * (replicates - 1))
    upper_index = int(0.975 * (replicates - 1))
    return {
        "observed_seed_differences_pp": observed_by_seed,
        "observed_mean_difference_pp": sum(observed_by_seed) / 3,
        "ci95_lower_pp": ordered[lower_index],
        "ci95_upper_pp": ordered[upper_index],
        "patients": len(patients),
        "rows": row_count,
        "replicates": replicates,
        "seed": seed,
    }
