from __future__ import annotations

from dataclasses import dataclass
import math
import random
from typing import Any, Mapping, Sequence

import torch
from torch import Tensor

from .schemas import MatchPlan, RegionBatch


EVENT_PERSISTENT = 0
EVENT_DEATH = 1
EVENT_BIRTH = 2
EVENT_COUNT = 3


@dataclass(frozen=True)
class MappedBox:
    label: str
    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def width(self) -> float:
        return self.x2 - self.x1

    @property
    def height(self) -> float:
        return self.y2 - self.y1

    def geometry(self, output_size: int = 224) -> tuple[float, float, float, float]:
        scale = float(output_size)
        return (
            (self.x1 + self.x2) / (2.0 * scale),
            (self.y1 + self.y2) / (2.0 * scale),
            self.width / scale,
            self.height / scale,
        )


def annotation_canvas_size(rows: int, columns: int) -> tuple[float, float]:
    if rows <= 0 or columns <= 0:
        raise ValueError("Rows and Columns must be positive")
    scale = 1024.0 / min(rows, columns)
    return columns * scale, rows * scale


def map_annotation_box(
    box: Mapping[str, Any],
    *,
    rows: int,
    columns: int,
    output_size: int = 224,
    tolerance: float = 1e-6,
) -> MappedBox:
    if output_size <= 0:
        raise ValueError("output_size must be positive")
    label = box.get("label")
    if not isinstance(label, str) or not label.strip():
        raise ValueError("box label must be non-empty")
    try:
        x1, y1, x2, y2 = (float(box[name]) for name in ("x1", "y1", "x2", "y2"))
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("box coordinates must be finite numbers") from error
    if not all(math.isfinite(value) for value in (x1, y1, x2, y2)):
        raise ValueError("box coordinates must be finite numbers")
    if x2 <= x1 or y2 <= y1:
        raise ValueError("box has nonpositive area")

    canvas_width, canvas_height = annotation_canvas_size(rows, columns)
    if not (
        -tolerance <= x1 < x2 <= canvas_width + tolerance
        and -tolerance <= y1 < y2 <= canvas_height + tolerance
    ):
        raise ValueError("box lies outside the annotation canvas")

    scale = float(output_size)
    mapped = MappedBox(
        label=label.strip(),
        x1=min(max(x1 / canvas_width * scale, 0.0), scale),
        y1=min(max(y1 / canvas_height * scale, 0.0), scale),
        x2=min(max(x2 / canvas_width * scale, 0.0), scale),
        y2=min(max(y2 / canvas_height * scale, 0.0), scale),
    )
    if mapped.width <= 0 or mapped.height <= 0:
        raise ValueError("mapped box has nonpositive area")
    return mapped


# Three-label persistent endpoint (R25+).  Chest ImaGenome's ``comparison``
# relation only covers previous-image entities, so the five-label
# New/Resolved derivation is infeasible without per-image attribute presence
# joins.  The closed vocabulary maps the three gold ``comparison`` values to
# the persistent labels used by the R25 real-data qualification.
THREE_LABEL_COMPARISON_MAP: Mapping[str, str] = {
    "no change": "Stable",
    "improved": "Improved",
    "worsened": "Worse",
}
PERSISTENT_LABELS: tuple[str, ...] = ("Stable", "Improved", "Worse")


def three_label_from_comparison(comparison: str) -> str:
    """Map a Chest ImaGenome ``comparison`` value to a persistent label.

    The vocabulary is closed: any value outside {no change, improved,
    worsened} raises ``ValueError`` so that cohort construction fails closed
    rather than silently dropping or defaulting an unknown comparison.
    """
    if not isinstance(comparison, str):
        raise ValueError("comparison must be a string")
    key = comparison.strip()
    if key not in THREE_LABEL_COMPARISON_MAP:
        raise ValueError(f"unsupported comparison value: {comparison!r}")
    return THREE_LABEL_COMPARISON_MAP[key]


def persistent_label_coverage(
    records: Sequence[Mapping[str, Any]],
    *,
    labels: Sequence[str] = PERSISTENT_LABELS,
    label_field: str = "progression",
    patient_field: str = "patient_id",
) -> dict[str, int]:
    """Count distinct patients per persistent label across cohort records.

    Returns a dict keyed by every label in ``labels`` (zero-filled when a
    label has no patients), mirroring the R25 runner's inline coverage gate.
    """
    counts = {label: 0 for label in labels}
    seen: dict[str, set[Any]] = {label: set() for label in labels}
    for record in records:
        label = record.get(label_field)
        if label not in counts:
            continue
        patient = record.get(patient_field)
        if patient is None:
            continue
        seen[label].add(patient)
    for label in labels:
        counts[label] = len(seen[label])
    return counts


def correspondence_support(
    progression: str,
    prior_labels: Sequence[str],
    current_labels: Sequence[str],
) -> dict[str, Any]:
    if len(set(prior_labels)) != len(prior_labels):
        raise ValueError("prior Box labels must be unique within a row")
    if len(set(current_labels)) != len(current_labels):
        raise ValueError("current Box labels must be unique within a row")
    prior = set(prior_labels)
    current = set(current_labels)
    shared = sorted(prior & current)
    deaths = sorted(prior - current)
    births = sorted(current - prior)
    if progression == "New":
        compatible = bool(births)
    elif progression == "Resolved":
        compatible = bool(deaths)
    elif progression in {"Stable", "Worse", "Improved"}:
        compatible = bool(shared)
    else:
        raise ValueError(f"unsupported progression label: {progression!r}")
    return {
        "shared": shared,
        "deaths": deaths,
        "births": births,
        "compatible": compatible,
    }


def entity_ids(
    prior_labels: Sequence[str],
    current_labels: Sequence[str],
) -> tuple[Tensor, Tensor]:
    if len(set(prior_labels)) != len(prior_labels):
        raise ValueError("prior Box labels must be unique")
    if len(set(current_labels)) != len(current_labels):
        raise ValueError("current Box labels must be unique")
    label_to_id = {
        label: index
        for index, label in enumerate(
            sorted(set(prior_labels) | set(current_labels)), start=1
        )
    }
    return (
        torch.tensor([label_to_id[label] for label in prior_labels], dtype=torch.long),
        torch.tensor(
            [label_to_id[label] for label in current_labels], dtype=torch.long
        ),
    )


def greedy_plan_from_utilities(
    regions: RegionBatch,
    edge_utility: Tensor,
    prior_null_utility: Tensor,
    current_null_utility: Tensor,
) -> MatchPlan:
    regions.validate()
    batch_size, prior_count, _ = regions.prior_features.shape
    current_count = regions.current_features.shape[1]
    if tuple(edge_utility.shape) != (batch_size, prior_count, current_count):
        raise ValueError("edge_utility has the wrong shape")
    if tuple(prior_null_utility.shape) != (batch_size, prior_count):
        raise ValueError("prior_null_utility has the wrong shape")
    if tuple(current_null_utility.shape) != (batch_size, current_count):
        raise ValueError("current_null_utility has the wrong shape")
    transport = edge_utility.new_zeros((batch_size, prior_count + 1, current_count + 1))
    for batch_index in range(batch_size):
        candidates = []
        for prior_index in range(prior_count):
            if not bool(regions.prior_valid[batch_index, prior_index]):
                continue
            for current_index in range(current_count):
                if not bool(regions.current_valid[batch_index, current_index]):
                    continue
                if int(regions.prior_anatomy[batch_index, prior_index]) != int(
                    regions.current_anatomy[batch_index, current_index]
                ):
                    continue
                benefit = float(
                    edge_utility[batch_index, prior_index, current_index]
                    - prior_null_utility[batch_index, prior_index]
                    - current_null_utility[batch_index, current_index]
                )
                candidates.append((benefit, prior_index, current_index))
        used_prior: set[int] = set()
        used_current: set[int] = set()
        for benefit, prior_index, current_index in sorted(
            candidates, key=lambda item: (-item[0], item[1], item[2])
        ):
            if benefit <= 0:
                continue
            if prior_index in used_prior or current_index in used_current:
                continue
            transport[batch_index, prior_index, current_index] = 1.0
            used_prior.add(prior_index)
            used_current.add(current_index)
        for prior_index in range(prior_count):
            if (
                bool(regions.prior_valid[batch_index, prior_index])
                and prior_index not in used_prior
            ):
                transport[batch_index, prior_index, current_count] = 1.0
        for current_index in range(current_count):
            if (
                bool(regions.current_valid[batch_index, current_index])
                and current_index not in used_current
            ):
                transport[batch_index, prior_count, current_index] = 1.0
    plan = MatchPlan(transport=transport, mode="greedy_same_utilities")
    plan.validate_hard(regions)
    return plan


def plan_objective(
    plan: MatchPlan,
    regions: RegionBatch,
    edge_utility: Tensor,
    prior_null_utility: Tensor,
    current_null_utility: Tensor,
) -> float:
    plan.validate_hard(regions)
    _, prior_count, _ = regions.prior_features.shape
    current_count = regions.current_features.shape[1]
    real = plan.transport[:, :prior_count, :current_count]
    death = plan.transport[:, :prior_count, current_count]
    birth = plan.transport[:, prior_count, :current_count]
    return float(
        (
            (real * edge_utility).sum()
            + (death * prior_null_utility).sum()
            + (birth * current_null_utility).sum()
        ).item()
    )


def _predicted_events(
    plan: MatchPlan,
    regions: RegionBatch,
    batch_index: int,
) -> tuple[list[int], list[int]]:
    _, prior_count, _ = regions.prior_features.shape
    current_count = regions.current_features.shape[1]
    transport = plan.transport[batch_index]
    prior_events = []
    for prior_index in range(prior_count):
        if not bool(regions.prior_valid[batch_index, prior_index]):
            continue
        target = int(transport[prior_index].argmax().item())
        prior_events.append(
            EVENT_DEATH if target == current_count else EVENT_PERSISTENT
        )
    current_events = []
    for current_index in range(current_count):
        if not bool(regions.current_valid[batch_index, current_index]):
            continue
        source = int(transport[:, current_index].argmax().item())
        current_events.append(
            EVENT_BIRTH if source == prior_count else EVENT_PERSISTENT
        )
    return prior_events, current_events


def match_sufficient_statistics(
    predicted: MatchPlan,
    gold: MatchPlan,
    regions: RegionBatch,
) -> dict[str, Any]:
    predicted.validate_hard(regions)
    gold.validate_hard(regions)
    batch_size, prior_count, _ = regions.prior_features.shape
    current_count = regions.current_features.shape[1]

    edge_tp = edge_fp = edge_fn = exact_rows = 0
    confusion = torch.zeros(EVENT_COUNT, EVENT_COUNT, dtype=torch.long)
    for batch_index in range(batch_size):
        predicted_edges = {
            (prior, current)
            for prior in range(prior_count)
            for current in range(current_count)
            if float(predicted.transport[batch_index, prior, current]) > 0.5
        }
        gold_edges = {
            (prior, current)
            for prior in range(prior_count)
            for current in range(current_count)
            if float(gold.transport[batch_index, prior, current]) > 0.5
        }
        edge_tp += len(predicted_edges & gold_edges)
        edge_fp += len(predicted_edges - gold_edges)
        edge_fn += len(gold_edges - predicted_edges)
        exact_rows += int(
            torch.equal(
                predicted.transport[batch_index],
                gold.transport[batch_index],
            )
        )

        predicted_prior, predicted_current = _predicted_events(
            predicted, regions, batch_index
        )
        gold_prior, gold_current = _predicted_events(gold, regions, batch_index)
        for truth, estimate in zip(
            gold_prior + gold_current,
            predicted_prior + predicted_current,
        ):
            confusion[truth, estimate] += 1

    return {
        "rows": batch_size,
        "edge_tp": edge_tp,
        "edge_fp": edge_fp,
        "edge_fn": edge_fn,
        "exact_rows": exact_rows,
        "event_confusion": confusion.tolist(),
    }


def merge_sufficient_statistics(
    statistics: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    confusion = torch.zeros(EVENT_COUNT, EVENT_COUNT, dtype=torch.long)
    merged = {
        "rows": 0,
        "edge_tp": 0,
        "edge_fp": 0,
        "edge_fn": 0,
        "exact_rows": 0,
    }
    for item in statistics:
        for key in merged:
            merged[key] += int(item[key])
        value = torch.as_tensor(item["event_confusion"], dtype=torch.long)
        if tuple(value.shape) != (EVENT_COUNT, EVENT_COUNT):
            raise ValueError("event_confusion must have shape [3, 3]")
        confusion += value
    merged["event_confusion"] = confusion.tolist()
    return merged


def metrics_from_sufficient_statistics(
    statistics: Mapping[str, Any],
) -> dict[str, float]:
    tp = int(statistics["edge_tp"])
    fp = int(statistics["edge_fp"])
    fn = int(statistics["edge_fn"])
    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    edge_f1 = 2.0 * precision * recall / max(precision + recall, 1e-12)

    confusion = torch.as_tensor(statistics["event_confusion"], dtype=torch.long)
    if tuple(confusion.shape) != (EVENT_COUNT, EVENT_COUNT):
        raise ValueError("event_confusion must have shape [3, 3]")
    event_f1 = []
    for label in range(EVENT_COUNT):
        label_tp = int(confusion[label, label])
        label_fp = int(confusion[:, label].sum()) - label_tp
        label_fn = int(confusion[label].sum()) - label_tp
        denominator = 2 * label_tp + label_fp + label_fn
        event_f1.append(0.0 if denominator == 0 else 2 * label_tp / denominator)
    rows = int(statistics["rows"])
    return {
        "persistent_edge_precision": precision,
        "persistent_edge_recall": recall,
        "persistent_edge_f1": edge_f1,
        "exact_row_recovery": int(statistics["exact_rows"]) / max(rows, 1),
        "three_event_macro_f1": sum(event_f1) / EVENT_COUNT,
    }


def _percentile(values: Sequence[float], probability: float) -> float:
    if not values:
        raise ValueError("cannot compute a percentile of an empty sequence")
    if not 0 <= probability <= 1:
        raise ValueError("probability must be in [0, 1]")
    ordered = sorted(float(value) for value in values)
    position = probability * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def patient_cluster_bootstrap(
    patient_statistics: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    seed: int,
    replicates: int,
    randomized_patient_statistics: (
        Mapping[str, Sequence[Mapping[str, Any]]] | None
    ) = None,
) -> dict[str, Any]:
    patients = sorted(patient_statistics)
    if not patients:
        raise ValueError("patient_statistics must be non-empty")
    if replicates <= 0:
        raise ValueError("replicates must be positive")
    if randomized_patient_statistics is not None and set(
        randomized_patient_statistics
    ) != set(patients):
        raise ValueError("randomized statistics must contain the same patients")

    point = metrics_from_sufficient_statistics(
        merge_sufficient_statistics(
            [
                statistic
                for patient in patients
                for statistic in patient_statistics[patient]
            ]
        )
    )
    randomized_point = None
    if randomized_patient_statistics is not None:
        randomized_point = metrics_from_sufficient_statistics(
            merge_sufficient_statistics(
                [
                    statistic
                    for patient in patients
                    for statistic in randomized_patient_statistics[patient]
                ]
            )
        )

    generator = random.Random(seed)
    replicate_metrics: dict[str, list[float]] = {
        "persistent_edge_f1": [],
        "three_event_macro_f1": [],
    }
    delta_values: list[float] = []
    for _ in range(replicates):
        sample = generator.choices(patients, k=len(patients))
        sampled = merge_sufficient_statistics(
            [
                statistic
                for patient in sample
                for statistic in patient_statistics[patient]
            ]
        )
        metrics = metrics_from_sufficient_statistics(sampled)
        for name in replicate_metrics:
            replicate_metrics[name].append(metrics[name])
        if randomized_patient_statistics is not None:
            randomized_sampled = merge_sufficient_statistics(
                [
                    statistic
                    for patient in sample
                    for statistic in randomized_patient_statistics[patient]
                ]
            )
            randomized_metrics = metrics_from_sufficient_statistics(randomized_sampled)
            delta_values.append(
                metrics["persistent_edge_f1"] - randomized_metrics["persistent_edge_f1"]
            )

    intervals = {
        name: {
            "lower": _percentile(values, 0.025),
            "upper": _percentile(values, 0.975),
        }
        for name, values in replicate_metrics.items()
    }
    result: dict[str, Any] = {
        "seed": seed,
        "replicates": replicates,
        "patient_count": len(patients),
        "point": point,
        "percentile_95_ci": intervals,
    }
    if randomized_point is not None:
        result["randomized_point"] = randomized_point
        result["persistent_edge_f1_delta"] = {
            "point": (
                point["persistent_edge_f1"] - randomized_point["persistent_edge_f1"]
            ),
            "lower": _percentile(delta_values, 0.025),
            "upper": _percentile(delta_values, 0.975),
        }
    return result
