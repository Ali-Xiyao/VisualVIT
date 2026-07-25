from __future__ import annotations

from torch import Tensor


def macro_f1(predictions: Tensor, targets: Tensor, num_classes: int) -> float:
    values: list[float] = []
    for class_index in range(num_classes):
        pred_positive = predictions == class_index
        true_positive = targets == class_index
        tp = int((pred_positive & true_positive).sum().item())
        fp = int((pred_positive & ~true_positive).sum().item())
        fn = int((~pred_positive & true_positive).sum().item())
        denominator = 2 * tp + fp + fn
        values.append(0.0 if denominator == 0 else (2.0 * tp) / denominator)
    return sum(values) / len(values)
