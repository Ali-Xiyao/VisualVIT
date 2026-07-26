from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
import math
from typing import Any, Iterable, Mapping, Sequence

import numpy as np


def canonical_sha256(value: object) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def deterministic_patient_folds(
    records: Sequence[Mapping[str, Any]],
    *,
    labels: Sequence[str],
    fold_count: int = 5,
    salt: str = "chextemporal-chexpert-v1",
) -> dict[str, int]:
    if fold_count < 2:
        raise ValueError("fold_count must be at least two")
    label_order = tuple(labels)
    label_index = {label: index for index, label in enumerate(label_order)}
    patient_counts: dict[str, np.ndarray] = {}
    for row in records:
        patient = str(row["patient_id"])
        target = str(row["progression"])
        if target not in label_index:
            raise ValueError(f"unsupported fold label: {target!r}")
        counts = patient_counts.setdefault(
            patient, np.zeros(len(label_order), dtype=np.float64)
        )
        counts[label_index[target]] += 1.0
    if len(patient_counts) < fold_count:
        raise ValueError("fewer patients than folds")

    def tie_hash(patient: str) -> str:
        return hashlib.sha256(f"{salt}|{patient}".encode()).hexdigest()

    ordered = sorted(
        patient_counts,
        key=lambda patient: (
            -float(patient_counts[patient].sum()),
            -float(patient_counts[patient].max()),
            tie_hash(patient),
        ),
    )
    total = sum(patient_counts.values(), np.zeros(len(label_order)))
    target_labels = total / fold_count
    target_rows = float(total.sum()) / fold_count
    fold_labels = np.zeros((fold_count, len(label_order)), dtype=np.float64)
    fold_rows = np.zeros(fold_count, dtype=np.float64)
    fold_patients = np.zeros(fold_count, dtype=np.float64)
    assignment: dict[str, int] = {}

    for patient in ordered:
        counts = patient_counts[patient]
        candidates = []
        for fold in range(fold_count):
            next_labels = fold_labels.copy()
            next_rows = fold_rows.copy()
            next_patients = fold_patients.copy()
            next_labels[fold] += counts
            next_rows[fold] += counts.sum()
            next_patients[fold] += 1.0
            label_scale = np.maximum(target_labels, 1.0)
            label_cost = float(
                np.square((next_labels - target_labels) / label_scale).sum()
            )
            row_cost = float(
                np.square((next_rows - target_rows) / max(target_rows, 1.0)).sum()
            )
            patient_cost = float(np.square(next_patients - next_patients.mean()).sum())
            candidates.append(
                (label_cost + 0.20 * row_cost + 0.01 * patient_cost, fold)
            )
        _, chosen = min(candidates)
        assignment[patient] = chosen
        fold_labels[chosen] += counts
        fold_rows[chosen] += counts.sum()
        fold_patients[chosen] += 1.0

    if set(assignment) != set(patient_counts):
        raise RuntimeError("patient fold assignment is incomplete")
    if (fold_patients == 0).any():
        raise RuntimeError("patient fold assignment produced an empty fold")
    return assignment


def fold_audit(
    records: Sequence[Mapping[str, Any]],
    assignment: Mapping[str, int],
    *,
    labels: Sequence[str],
    fold_count: int,
) -> dict[str, Any]:
    folds = []
    seen: set[str] = set()
    for fold in range(fold_count):
        selected = [
            row for row in records if assignment[str(row["patient_id"])] == fold
        ]
        patients = sorted({str(row["patient_id"]) for row in selected})
        if seen.intersection(patients):
            raise RuntimeError("patient appears in more than one fold")
        seen.update(patients)
        counts = Counter(str(row["progression"]) for row in selected)
        folds.append(
            {
                "fold": fold,
                "rows": len(selected),
                "patients": len(patients),
                "label_counts": {label: counts[label] for label in labels},
            }
        )
    return {
        "fold_count": fold_count,
        "patients": len(seen),
        "rows": len(records),
        "folds": folds,
        "assignment_sha256": canonical_sha256(dict(sorted(assignment.items()))),
        "patient_disjoint": sum(item["patients"] for item in folds) == len(seen),
    }


def _confusion(
    targets: Sequence[str],
    predictions: Sequence[str],
    weights: Sequence[float],
    labels: Sequence[str],
) -> np.ndarray:
    if not (len(targets) == len(predictions) == len(weights)):
        raise ValueError("targets, predictions and weights must align")
    index = {label: offset for offset, label in enumerate(labels)}
    result = np.zeros((len(labels), len(labels)), dtype=np.float64)
    for target, prediction, weight in zip(targets, predictions, weights, strict=True):
        if target not in index or prediction not in index:
            raise ValueError("target/prediction lies outside the registered labels")
        if not math.isfinite(weight) or weight < 0:
            raise ValueError("weights must be finite and non-negative")
        result[index[target], index[prediction]] += weight
    return result


def metrics_from_confusion(
    confusion: np.ndarray,
    *,
    labels: Sequence[str],
    require_all_labels: bool = True,
) -> dict[str, Any]:
    confusion = np.asarray(confusion, dtype=np.float64)
    if confusion.shape != (len(labels), len(labels)):
        raise ValueError("confusion matrix has the wrong shape")
    support = confusion.sum(axis=1)
    if require_all_labels and bool((support <= 0).any()):
        missing = [label for label, value in zip(labels, support) if value <= 0]
        raise ValueError("missing label support: " + ",".join(missing))
    true_positive = np.diag(confusion)
    false_positive = confusion.sum(axis=0) - true_positive
    false_negative = support - true_positive
    denominator = 2 * true_positive + false_positive + false_negative
    f1 = np.divide(
        2 * true_positive,
        denominator,
        out=np.zeros_like(true_positive),
        where=denominator > 0,
    )
    recall = np.divide(
        true_positive,
        support,
        out=np.zeros_like(true_positive),
        where=support > 0,
    )
    return {
        "macro_f1": float(f1.mean()),
        "balanced_accuracy": float(recall.mean()),
        "per_class_f1": {
            label: float(value) for label, value in zip(labels, f1, strict=True)
        },
        "support": {
            label: float(value) for label, value in zip(labels, support, strict=True)
        },
    }


def classification_metrics(
    rows: Sequence[Mapping[str, Any]], *, labels: Sequence[str]
) -> dict[str, Any]:
    patient_sizes = Counter(str(row["patient_id"]) for row in rows)
    patient_weights = [1.0 / patient_sizes[str(row["patient_id"])] for row in rows]
    targets = [str(row["target"]) for row in rows]
    predictions = [str(row["prediction"]) for row in rows]
    patient_balanced = metrics_from_confusion(
        _confusion(targets, predictions, patient_weights, labels),
        labels=labels,
    )
    ordinary = metrics_from_confusion(
        _confusion(targets, predictions, [1.0] * len(rows), labels),
        labels=labels,
    )
    return {
        "patient_balanced": patient_balanced,
        "ordinary": ordinary,
        "patients": len(patient_sizes),
        "rows": len(rows),
    }


def progression_rows_from_predictions(
    records: Sequence[Mapping[str, Any]],
    predictions: Mapping[str, str],
    *,
    labels: Sequence[str],
    record_id_key: str = "qualification_id",
) -> list[dict[str, str]]:
    """Bind model predictions to the registered progression targets.

    This is the semantic boundary between a cohort that merely carries
    progression annotations and an evaluation that actually consumes them.
    Prediction ids must match cohort ids exactly; missing, extra, duplicate,
    or out-of-vocabulary values fail closed.
    """

    label_set = set(labels)
    record_ids = [str(record[record_id_key]) for record in records]
    if len(set(record_ids)) != len(record_ids):
        raise ValueError("record ids must be unique")
    prediction_ids = {str(value) for value in predictions}
    if prediction_ids != set(record_ids):
        missing = sorted(set(record_ids) - prediction_ids)
        extra = sorted(prediction_ids - set(record_ids))
        raise ValueError(
            "prediction ids must match record ids exactly; "
            f"missing={missing}, extra={extra}"
        )

    rows = []
    for record, observation_id in zip(records, record_ids, strict=True):
        target = str(record["progression"])
        prediction = str(predictions[observation_id])
        if target not in label_set:
            raise ValueError(f"progression target is outside registered labels: {target!r}")
        if prediction not in label_set:
            raise ValueError(
                f"progression prediction is outside registered labels: {prediction!r}"
            )
        rows.append(
            {
                "patient_id": str(record["patient_id"]),
                "observation_id": observation_id,
                "target": target,
                "prediction": prediction,
            }
        )
    return rows


def build_pair_and_entity_manifests(
    records: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split repeated entity rows from their independent temporal-pair units."""

    required = {
        "qualification_id",
        "patient_id",
        "prior_dicom_id",
        "current_dicom_id",
        "anatomy",
        "label_name",
        "progression",
    }
    groups: dict[tuple[str, str, str], list[Mapping[str, Any]]] = defaultdict(list)
    qualification_ids: set[str] = set()
    for record in records:
        missing = sorted(required - set(record))
        if missing:
            raise ValueError(f"manifest record missing required fields: {missing}")
        qualification_id = str(record["qualification_id"])
        if qualification_id in qualification_ids:
            raise ValueError(f"duplicate qualification_id: {qualification_id}")
        qualification_ids.add(qualification_id)
        key = (
            str(record["patient_id"]),
            str(record["prior_dicom_id"]),
            str(record["current_dicom_id"]),
        )
        groups[key].append(record)

    pair_manifest: list[dict[str, Any]] = []
    entity_manifest: list[dict[str, Any]] = []
    for key in sorted(groups):
        patient_id, prior_dicom_id, current_dicom_id = key
        pair_id = hashlib.sha256("|".join(key).encode("utf-8")).hexdigest()[:20]
        members = sorted(
            groups[key],
            key=lambda item: (
                str(item["anatomy"]),
                str(item["label_name"]),
                str(item["qualification_id"]),
            ),
        )
        pair_manifest.append(
            {
                "pair_id": pair_id,
                "patient_id": patient_id,
                "prior_dicom_id": prior_dicom_id,
                "current_dicom_id": current_dicom_id,
                "entity_count": len(members),
                "anatomies": sorted({str(item["anatomy"]) for item in members}),
                "progression_counts": dict(
                    sorted(Counter(str(item["progression"]) for item in members).items())
                ),
            }
        )
        for item in members:
            entity_manifest.append(
                {
                    "qualification_id": str(item["qualification_id"]),
                    "pair_id": pair_id,
                    "patient_id": patient_id,
                    "prior_dicom_id": prior_dicom_id,
                    "current_dicom_id": current_dicom_id,
                    "anatomy": str(item["anatomy"]),
                    "label_name": str(item["label_name"]),
                    "progression": str(item["progression"]),
                }
            )

    entity_manifest.sort(key=lambda item: item["qualification_id"])
    return pair_manifest, entity_manifest


def hierarchical_patient_bootstrap(
    rows: Iterable[Mapping[str, Any]],
    *,
    labels: Sequence[str],
    systems: Sequence[str],
    seeds: Sequence[int],
    derangements: Sequence[int],
    contrasts: Mapping[str, tuple[str, str]],
    invariant_systems: Sequence[str] = (),
    replicates: int = 10_000,
    rng_seed: int = 20260724,
    minimum_valid_fraction: float = 0.95,
) -> dict[str, Any]:
    materialized = [dict(row) for row in rows]
    if replicates < 2:
        raise ValueError("at least two bootstrap replicates are required")
    patients = sorted({str(row["patient_id"]) for row in materialized})
    system_order = tuple(systems)
    seed_order = tuple(int(value) for value in seeds)
    derangement_order = tuple(int(value) for value in derangements)
    label_order = tuple(labels)
    expected = {
        (system, seed, derangement, patient)
        for system in system_order
        for seed in seed_order
        for derangement in derangement_order
        for patient in patients
    }
    blocks: dict[tuple[str, int, int, str], list[dict[str, Any]]] = defaultdict(list)
    for row in materialized:
        key = (
            str(row["system"]),
            int(row["training_seed"]),
            int(row["derangement_id"]),
            str(row["patient_id"]),
        )
        blocks[key].append(row)
    if set(blocks) != expected:
        raise ValueError("bootstrap design is not fully crossed")

    layouts: dict[str, list[tuple[str, str, float]]] = {}
    for patient in patients:
        reference = blocks[
            (system_order[0], seed_order[0], derangement_order[0], patient)
        ]
        layouts[patient] = sorted(
            (
                str(row["observation_id"]),
                str(row["target"]),
                float(row["weight"]),
            )
            for row in reference
        )
    for key, block in blocks.items():
        patient = key[-1]
        layout = sorted(
            (
                str(row["observation_id"]),
                str(row["target"]),
                float(row["weight"]),
            )
            for row in block
        )
        if layout != layouts[patient]:
            raise ValueError(f"prediction layout mismatch in block {key!r}")
        if not math.isclose(sum(item[2] for item in layout), 1.0, abs_tol=1e-8):
            raise ValueError(f"patient weights do not sum to one in {key!r}")

    for system in invariant_systems:
        for seed in seed_order:
            for patient in patients:
                reference = sorted(
                    (str(row["observation_id"]), str(row["prediction"]))
                    for row in blocks[(system, seed, derangement_order[0], patient)]
                )
                for derangement in derangement_order[1:]:
                    candidate = sorted(
                        (str(row["observation_id"]), str(row["prediction"]))
                        for row in blocks[(system, seed, derangement, patient)]
                    )
                    if candidate != reference:
                        raise ValueError(
                            f"invariant system {system!r} varies by derangement"
                        )

    label_index = {label: index for index, label in enumerate(label_order)}
    confusion = np.zeros(
        (
            len(system_order),
            len(seed_order),
            len(derangement_order),
            len(patients),
            len(label_order),
            len(label_order),
        ),
        dtype=np.float64,
    )
    system_index = {value: index for index, value in enumerate(system_order)}
    seed_index = {value: index for index, value in enumerate(seed_order)}
    derangement_index = {value: index for index, value in enumerate(derangement_order)}
    patient_index = {value: index for index, value in enumerate(patients)}
    for row in materialized:
        confusion[
            system_index[str(row["system"])],
            seed_index[int(row["training_seed"])],
            derangement_index[int(row["derangement_id"])],
            patient_index[str(row["patient_id"])],
            label_index[str(row["target"])],
            label_index[str(row["prediction"])],
        ] += float(row["weight"])

    def evaluate(
        patient_draw: np.ndarray,
        seed_draw: np.ndarray,
        derangement_draw: np.ndarray,
    ) -> dict[str, float]:
        patient_counts = np.bincount(patient_draw, minlength=len(patients))
        values = np.zeros(len(system_order), dtype=np.float64)
        for seed_offset in seed_draw:
            seed_values = np.zeros(len(system_order), dtype=np.float64)
            for derangement_offset in derangement_draw:
                for system_offset in range(len(system_order)):
                    matrix = np.tensordot(
                        patient_counts,
                        confusion[
                            system_offset,
                            seed_offset,
                            derangement_offset,
                        ],
                        axes=(0, 0),
                    )
                    seed_values[system_offset] += metrics_from_confusion(
                        matrix, labels=label_order
                    )["macro_f1"]
            values += seed_values / len(derangement_draw)
        values /= len(seed_draw)
        return {
            system: float(value)
            for system, value in zip(system_order, values, strict=True)
        }

    point = evaluate(
        np.arange(len(patients)),
        np.arange(len(seed_order)),
        np.arange(len(derangement_order)),
    )
    rng = np.random.default_rng(rng_seed)
    system_samples = {system: [] for system in system_order}
    contrast_samples = {name: [] for name in contrasts}
    invalid = Counter()
    for _ in range(replicates):
        try:
            metrics = evaluate(
                rng.integers(0, len(patients), size=len(patients)),
                rng.integers(0, len(seed_order), size=len(seed_order)),
                rng.integers(0, len(derangement_order), size=len(derangement_order)),
            )
        except ValueError as error:
            invalid[str(error)] += 1
            continue
        for system, value in metrics.items():
            system_samples[system].append(value)
        for name, (left, right) in contrasts.items():
            contrast_samples[name].append(metrics[left] - metrics[right])

    valid = len(next(iter(system_samples.values())))
    valid_fraction = valid / replicates
    inference_valid = valid >= 2 and valid_fraction >= minimum_valid_fraction

    def interval(values: Sequence[float]) -> dict[str, float] | None:
        if not inference_valid:
            return None
        lower, upper = np.quantile(values, [0.025, 0.975], method="linear")
        return {"lower": float(lower), "upper": float(upper), "level": 0.95}

    return {
        "point_system_macro_f1": point,
        "system_intervals": {
            system: interval(values) for system, values in system_samples.items()
        },
        "contrasts": {
            name: {
                "left": left,
                "right": right,
                "point": point[left] - point[right],
                "point_pp": 100.0 * (point[left] - point[right]),
                "interval": interval(contrast_samples[name]),
            }
            for name, (left, right) in contrasts.items()
        },
        "requested_replicates": replicates,
        "valid_replicates": valid,
        "invalid_replicates": replicates - valid,
        "valid_fraction": valid_fraction,
        "minimum_valid_fraction": minimum_valid_fraction,
        "inference_valid": inference_valid,
        "invalid_reasons": dict(invalid),
        "rng_seed": rng_seed,
        "resampled_levels": [
            "patient",
            "training_seed",
            "crossed_derangement",
        ],
    }
