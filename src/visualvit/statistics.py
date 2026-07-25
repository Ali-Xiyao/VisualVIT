from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import math
from statistics import stdev
from typing import Any, Iterable, Mapping, Sequence

import numpy as np


LABEL_ORDER = ("stable", "worse", "improved", "new", "resolved")
DEFAULT_TRAINING_SEED_BANK = (17, 29, 43, 71, 101, 137, 181, 233)
DEFAULT_BOOTSTRAP_RNG_SEED = 20260719


class FormalStatisticsError(ValueError):
    """Base class for fail-closed formal-statistics validation errors."""


class LabelSupportError(FormalStatisticsError):
    """Raised when one or more frozen endpoint labels have no target support."""

    def __init__(self, missing_labels: Sequence[str]) -> None:
        self.missing_labels = tuple(missing_labels)
        super().__init__(
            "primary five-label endpoint is not computable; missing support for: "
            + ", ".join(self.missing_labels)
        )


class PairingError(FormalStatisticsError):
    """Raised when systems do not share the exact confirmatory evaluation units."""


class PseudoreplicationError(PairingError):
    """Raised when repeated systems/seeds/derangements would be pooled as rows."""


@dataclass(frozen=True, slots=True)
class PredictionRow:
    """One entity/query prediction in a fully identified evaluation block.

    A formal block is identified by ``system``, ``training_seed`` and
    ``derangement_id``. ``observation_id`` identifies the paired entity/query
    within a patient. Invalid or uncertain observations must have ``valid=False``
    and zero weight; they are never converted into a negative target.
    """

    patient_id: str
    observation_id: str
    training_seed: int
    derangement_id: int
    system: str
    target: str | None
    prediction: str | None
    weight: float
    valid: bool = True

    @classmethod
    def from_mapping(cls, row: Mapping[str, Any]) -> PredictionRow:
        valid = row.get("valid", True)
        if isinstance(valid, str):
            normalized = valid.strip().lower()
            if normalized in {"true", "1", "yes", "y"}:
                valid = True
            elif normalized in {"false", "0", "no", "n"}:
                valid = False
            else:
                raise FormalStatisticsError(f"invalid boolean value: {valid!r}")
        target = row.get("target")
        prediction = row.get("prediction")
        return cls(
            patient_id=str(row["patient_id"]),
            observation_id=str(row["observation_id"]),
            training_seed=int(row["training_seed"]),
            derangement_id=int(row["derangement_id"]),
            system=str(row["system"]),
            target=None if target in (None, "") else str(target),
            prediction=None if prediction in (None, "") else str(prediction),
            weight=float(row["weight"]),
            valid=bool(valid),
        )


@dataclass(frozen=True, slots=True)
class WeightedMacroF1Result:
    macro_f1: float
    per_class_f1: Mapping[str, float]
    support: Mapping[str, float]
    true_positive: Mapping[str, float]
    false_positive: Mapping[str, float]
    false_negative: Mapping[str, float]


@dataclass(frozen=True, slots=True)
class PercentileInterval:
    lower: float
    upper: float
    level: float
    method: str = "percentile-linear"


@dataclass(frozen=True, slots=True)
class BootstrapSummary:
    requested_replicates: int
    metric_valid_replicates: int
    metric_invalid_replicates: int
    metric_valid_fraction: float
    inference_valid: bool
    minimum_valid_fraction: float
    invalid_reasons: Mapping[str, int]
    system_intervals: Mapping[str, PercentileInterval] | None
    gap_interval: PercentileInterval | None
    delta_bind_pp_interval: PercentileInterval | None
    recovery_interval: PercentileInterval | None
    denominator_positive_replicates: int
    denominator_positive_fraction: float
    recovery_invalid_reasons: Mapping[str, int]
    rng_seed: int
    rng_algorithm: str
    resampled_levels: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SeedEffectSummary:
    training_seed: int
    system_metrics: Mapping[str, float]
    gap: float
    delta_bind_pp: float
    learned_numerator: float
    raw_recovery: float | None


@dataclass(frozen=True, slots=True)
class LeaveOneSeedOutSummary:
    omitted_training_seed: int
    retained_training_seeds: tuple[int, ...]
    system_metrics: Mapping[str, float]
    gap: float
    delta_bind_pp: float
    learned_numerator: float
    raw_recovery: float | None


@dataclass(frozen=True, slots=True)
class RecoverySummary:
    defined: bool
    point_estimate: float | None
    raw_point_ratio: float | None
    numerator: float
    denominator_gap: float
    denominator_qualified: bool
    denominator_positive_fraction: float
    confidence_interval: PercentileInterval | None
    undefined_reason: str | None


@dataclass(frozen=True, slots=True)
class FormalStatisticsResult:
    labels: tuple[str, ...]
    patients: int
    training_seeds: tuple[int, ...]
    derangement_ids: tuple[int, ...]
    system_metrics: Mapping[str, float]
    delta_bind_pp: float
    delta_bind_minimum_effect_pp: float
    delta_bind_gate_pass: bool
    recovery: RecoverySummary
    hierarchical_bootstrap: BootstrapSummary
    patient_only_bootstrap: BootstrapSummary
    seed_effects: tuple[SeedEffectSummary, ...]
    seed_effect_sd_pp: float
    leave_one_seed_out: tuple[LeaveOneSeedOutSummary, ...]


@dataclass(frozen=True, slots=True)
class _ValidatedDesign:
    systems: tuple[str, ...]
    seeds: tuple[int, ...]
    derangements: tuple[int, ...]
    patients: tuple[str, ...]
    # [system, seed, derangement, patient, target, prediction]
    confusion: np.ndarray


def _validate_static_row(row: PredictionRow) -> None:
    if not isinstance(row, PredictionRow):
        raise TypeError(
            "formal inference accepts PredictionRow objects; use "
            "PredictionRow.from_mapping for serialized data"
        )
    if not row.patient_id or not row.observation_id or not row.system:
        raise FormalStatisticsError(
            "patient_id, observation_id and system must be non-empty"
        )
    if not math.isfinite(row.weight) or row.weight < 0.0:
        raise FormalStatisticsError("weights must be finite and non-negative")
    if row.valid:
        if row.target not in LABEL_ORDER:
            raise FormalStatisticsError(f"invalid target label: {row.target!r}")
        if row.prediction not in LABEL_ORDER:
            raise FormalStatisticsError(f"invalid prediction label: {row.prediction!r}")
    else:
        if not math.isclose(row.weight, 0.0, abs_tol=1e-12):
            raise FormalStatisticsError("masked/uncertain rows must have zero weight")
        if row.target is not None and row.target not in LABEL_ORDER:
            raise FormalStatisticsError(f"invalid masked target: {row.target!r}")
        if row.prediction is not None and row.prediction not in LABEL_ORDER:
            raise FormalStatisticsError(
                f"invalid masked prediction: {row.prediction!r}"
            )


def _metric_from_confusion(
    confusion: np.ndarray, *, require_all_labels: bool = True
) -> WeightedMacroF1Result:
    if confusion.shape != (len(LABEL_ORDER), len(LABEL_ORDER)):
        raise FormalStatisticsError(
            f"expected a {len(LABEL_ORDER)}x{len(LABEL_ORDER)} confusion matrix"
        )
    if not np.isfinite(confusion).all() or (confusion < 0).any():
        raise FormalStatisticsError("confusion weights must be finite and non-negative")

    support_values = confusion.sum(axis=1)
    missing = [
        label
        for label, support in zip(LABEL_ORDER, support_values, strict=True)
        if support <= 0.0
    ]
    if missing and require_all_labels:
        raise LabelSupportError(missing)

    diagonal = np.diag(confusion)
    fp_values = confusion.sum(axis=0) - diagonal
    fn_values = support_values - diagonal
    denominators = 2.0 * diagonal + fp_values + fn_values
    f1_values = np.divide(
        2.0 * diagonal,
        denominators,
        out=np.zeros_like(diagonal),
        where=denominators > 0.0,
    )
    return WeightedMacroF1Result(
        macro_f1=float(f1_values.mean()),
        per_class_f1={
            label: float(value)
            for label, value in zip(LABEL_ORDER, f1_values, strict=True)
        },
        support={
            label: float(value)
            for label, value in zip(LABEL_ORDER, support_values, strict=True)
        },
        true_positive={
            label: float(value)
            for label, value in zip(LABEL_ORDER, diagonal, strict=True)
        },
        false_positive={
            label: float(value)
            for label, value in zip(LABEL_ORDER, fp_values, strict=True)
        },
        false_negative={
            label: float(value)
            for label, value in zip(LABEL_ORDER, fn_values, strict=True)
        },
    )


def weighted_macro_f1(rows: Iterable[PredictionRow]) -> WeightedMacroF1Result:
    """Compute the patient-balanced frozen five-label macro F1 for one block.

    This public primitive deliberately rejects multiple systems, training seeds
    or derangements. Pooling those repeated rows would be pseudo-replication;
    use :func:`evaluate_formal_statistics` for the hierarchical estimator.
    """

    materialized = tuple(rows)
    if not materialized:
        raise FormalStatisticsError("at least one prediction row is required")
    for row in materialized:
        _validate_static_row(row)

    block_ids = {
        (row.system, row.training_seed, row.derangement_id) for row in materialized
    }
    if len(block_ids) != 1:
        raise PseudoreplicationError(
            "weighted_macro_f1 accepts exactly one system/seed/derangement block"
        )

    seen: set[tuple[str, str]] = set()
    patient_weights: Counter[str] = Counter()
    confusion = np.zeros((len(LABEL_ORDER), len(LABEL_ORDER)), dtype=np.float64)
    label_index = {label: index for index, label in enumerate(LABEL_ORDER)}
    for row in materialized:
        key = (row.patient_id, row.observation_id)
        if key in seen:
            raise PseudoreplicationError(f"duplicate evaluation unit: {key!r}")
        seen.add(key)
        if not row.valid:
            continue
        patient_weights[row.patient_id] += row.weight
        confusion[label_index[row.target], label_index[row.prediction]] += row.weight

    all_patients = {row.patient_id for row in materialized}
    for patient in all_patients:
        if not math.isclose(patient_weights[patient], 1.0, rel_tol=1e-8, abs_tol=1e-8):
            raise FormalStatisticsError(
                f"valid weights for patient {patient!r} must sum to one; got "
                f"{patient_weights[patient]:.12g}"
            )
    return _metric_from_confusion(confusion)


def percentile_interval(
    values: Iterable[float], *, level: float = 0.95
) -> PercentileInterval:
    """Return a two-sided linear-interpolation percentile interval."""

    if not 0.0 < level < 1.0:
        raise FormalStatisticsError("confidence level must lie strictly within (0, 1)")
    array = np.asarray(tuple(values), dtype=np.float64)
    if array.ndim != 1 or array.size == 0:
        raise FormalStatisticsError("percentile interval requires non-empty 1-D data")
    if not np.isfinite(array).all():
        raise FormalStatisticsError("percentile interval values must all be finite")
    tail = (1.0 - level) / 2.0
    lower, upper = np.quantile(array, [tail, 1.0 - tail], method="linear")
    return PercentileInterval(lower=float(lower), upper=float(upper), level=level)


def _validate_design(
    rows: Sequence[PredictionRow],
    *,
    required_systems: Sequence[str],
    derangement_invariant_systems: Sequence[str],
    enforce_seed_bank: bool,
    minimum_training_seeds: int,
    minimum_derangements: int,
) -> _ValidatedDesign:
    if not rows:
        raise FormalStatisticsError("at least one prediction row is required")
    for row in rows:
        _validate_static_row(row)

    systems = tuple(sorted({row.system for row in rows}))
    missing_systems = sorted(set(required_systems) - set(systems))
    if missing_systems:
        raise PairingError("missing required systems: " + ", ".join(missing_systems))
    seeds = tuple(sorted({row.training_seed for row in rows}))
    if len(seeds) < minimum_training_seeds:
        raise PairingError(
            f"at least {minimum_training_seeds} training seeds are required; "
            f"found {len(seeds)}"
        )
    if enforce_seed_bank:
        expected = DEFAULT_TRAINING_SEED_BANK[: len(seeds)]
        if seeds != expected:
            raise PairingError(
                f"training seeds must be the frozen bank prefix {expected}; got {seeds}"
            )
    derangements = tuple(sorted({row.derangement_id for row in rows}))
    if len(derangements) < minimum_derangements:
        raise PairingError(
            f"at least {minimum_derangements} derangement blocks are required; "
            f"found {len(derangements)}"
        )
    patients = tuple(sorted({row.patient_id for row in rows}))

    blocks: dict[tuple[str, int, int, str], dict[str, PredictionRow]] = {}
    for row in rows:
        block_key = (
            row.system,
            row.training_seed,
            row.derangement_id,
            row.patient_id,
        )
        block = blocks.setdefault(block_key, {})
        if row.observation_id in block:
            raise PseudoreplicationError(
                "duplicate row for system/seed/derangement/patient/observation: "
                f"{block_key + (row.observation_id,)!r}"
            )
        block[row.observation_id] = row

    expected_block_keys = {
        (system, seed, derangement, patient)
        for system in systems
        for seed in seeds
        for derangement in derangements
        for patient in patients
    }
    missing_blocks = expected_block_keys - set(blocks)
    extra_blocks = set(blocks) - expected_block_keys
    if missing_blocks or extra_blocks:
        example = next(iter(missing_blocks or extra_blocks))
        raise PairingError(
            "the design must be fully crossed over system, seed, derangement and "
            f"patient; offending block example: {example!r}"
        )

    reference_layouts: dict[str, dict[str, tuple[bool, str | None, float]]] = {}
    for patient in patients:
        reference_key = (systems[0], seeds[0], derangements[0], patient)
        reference_layouts[patient] = {
            observation_id: (row.valid, row.target, row.weight)
            for observation_id, row in blocks[reference_key].items()
        }

    for block_key, block in blocks.items():
        patient = block_key[-1]
        layout = {
            observation_id: (row.valid, row.target, row.weight)
            for observation_id, row in block.items()
        }
        if layout != reference_layouts[patient]:
            raise PairingError(
                "all systems/seeds/derangements must share identical observation "
                f"IDs, masks, targets and weights; mismatch in {block_key!r}"
            )
        weight_sum = sum(row.weight for row in block.values() if row.valid)
        if not math.isclose(weight_sum, 1.0, rel_tol=1e-8, abs_tol=1e-8):
            raise PairingError(
                f"valid patient weights must sum to one in {block_key!r}; "
                f"got {weight_sum:.12g}"
            )

    # B4b and learned predictions are duplicated over derangement IDs only to
    # preserve pairing with B4a. They may not acquire derangement variation.
    for system in derangement_invariant_systems:
        for seed in seeds:
            for patient in patients:
                reference = blocks[(system, seed, derangements[0], patient)]
                reference_values = {
                    observation_id: (
                        row.prediction,
                        row.target,
                        row.valid,
                        row.weight,
                    )
                    for observation_id, row in reference.items()
                }
                for derangement in derangements[1:]:
                    candidate = blocks[(system, seed, derangement, patient)]
                    candidate_values = {
                        observation_id: (
                            row.prediction,
                            row.target,
                            row.valid,
                            row.weight,
                        )
                        for observation_id, row in candidate.items()
                    }
                    if candidate_values != reference_values:
                        raise PairingError(
                            f"system {system!r} must be derangement-invariant; "
                            "B4b/learned rows are pairing replicas, not "
                            f"derangement-dependent observations (seed={seed}, "
                            f"patient={patient!r}, derangement={derangement})"
                        )

    system_index = {value: index for index, value in enumerate(systems)}
    seed_index = {value: index for index, value in enumerate(seeds)}
    derangement_index = {value: index for index, value in enumerate(derangements)}
    patient_index = {value: index for index, value in enumerate(patients)}
    label_index = {value: index for index, value in enumerate(LABEL_ORDER)}
    confusion = np.zeros(
        (
            len(systems),
            len(seeds),
            len(derangements),
            len(patients),
            len(LABEL_ORDER),
            len(LABEL_ORDER),
        ),
        dtype=np.float64,
    )
    for row in rows:
        if not row.valid:
            continue
        confusion[
            system_index[row.system],
            seed_index[row.training_seed],
            derangement_index[row.derangement_id],
            patient_index[row.patient_id],
            label_index[row.target],
            label_index[row.prediction],
        ] += row.weight

    # The original (unresampled) endpoint must itself have all five labels.
    reference_confusion = confusion[0, 0, 0].sum(axis=0)
    _metric_from_confusion(reference_confusion)
    return _ValidatedDesign(
        systems=systems,
        seeds=seeds,
        derangements=derangements,
        patients=patients,
        confusion=confusion,
    )


def _evaluate_draw(
    design: _ValidatedDesign,
    patient_counts: np.ndarray,
    seed_indices: Sequence[int],
    derangement_draws: Sequence[Sequence[int]],
) -> dict[str, float]:
    if len(seed_indices) != len(derangement_draws):
        raise RuntimeError("one derangement draw is required per sampled seed block")
    totals = np.zeros(len(design.systems), dtype=np.float64)
    for seed_index, sampled_derangements in zip(
        seed_indices, derangement_draws, strict=True
    ):
        if not sampled_derangements:
            raise RuntimeError("a sampled seed block cannot have zero derangements")
        seed_values = np.zeros(len(design.systems), dtype=np.float64)
        for derangement_index in sampled_derangements:
            for system_index in range(len(design.systems)):
                confusion = np.tensordot(
                    patient_counts,
                    design.confusion[system_index, seed_index, derangement_index],
                    axes=(0, 0),
                )
                seed_values[system_index] += _metric_from_confusion(confusion).macro_f1
        totals += seed_values / len(sampled_derangements)
    totals /= len(seed_indices)
    return {
        system: float(value)
        for system, value in zip(design.systems, totals, strict=True)
    }


def _point_metrics(
    design: _ValidatedDesign, seed_indices: Sequence[int]
) -> dict[str, float]:
    patient_counts = np.ones(len(design.patients), dtype=np.float64)
    derangement_draws = tuple(
        tuple(range(len(design.derangements))) for _ in seed_indices
    )
    return _evaluate_draw(
        design, patient_counts, tuple(seed_indices), derangement_draws
    )


def _bootstrap(
    design: _ValidatedDesign,
    *,
    b4a_system: str,
    b4b_system: str,
    learned_system: str,
    replicates: int,
    rng: np.random.Generator,
    rng_seed: int,
    resample_seed_blocks: bool,
    confidence_level: float,
    minimum_valid_fraction: float,
    minimum_positive_fraction: float,
) -> BootstrapSummary:
    system_samples: dict[str, list[float]] = {system: [] for system in design.systems}
    gap_samples: list[float] = []
    delta_samples: list[float] = []
    recovery_samples: list[float] = []
    invalid_reasons: Counter[str] = Counter()
    recovery_invalid_reasons: Counter[str] = Counter()

    patient_count = len(design.patients)
    seed_count = len(design.seeds)
    derangement_count = len(design.derangements)
    fixed_seeds = tuple(range(seed_count))
    fixed_derangements = tuple(range(derangement_count))

    for _ in range(replicates):
        patient_indices = rng.integers(0, patient_count, size=patient_count)
        patient_counts = np.bincount(patient_indices, minlength=patient_count).astype(
            np.float64
        )
        if resample_seed_blocks:
            seed_indices = tuple(
                int(value) for value in rng.integers(0, seed_count, size=seed_count)
            )
            # derangement_id identifies a patient-hash map shared across all
            # training seeds, so it is a crossed—not nested—factor. One draw is
            # reused for every sampled seed block in this replicate.
            crossed_derangement_draw = tuple(
                int(value)
                for value in rng.integers(0, derangement_count, size=derangement_count)
            )
            derangement_draws = tuple(crossed_derangement_draw for _ in seed_indices)
        else:
            seed_indices = fixed_seeds
            derangement_draws = tuple(fixed_derangements for _ in seed_indices)

        try:
            metrics = _evaluate_draw(
                design, patient_counts, seed_indices, derangement_draws
            )
        except LabelSupportError as error:
            key = "missing_label_support:" + ",".join(error.missing_labels)
            invalid_reasons[key] += 1
            continue

        for system, value in metrics.items():
            system_samples[system].append(value)
        gap = metrics[b4b_system] - metrics[b4a_system]
        numerator = metrics[learned_system] - metrics[b4a_system]
        gap_samples.append(gap)
        delta_samples.append(100.0 * gap)
        if gap > 0.0:
            recovery_samples.append(numerator / gap)
        else:
            recovery_invalid_reasons["denominator_nonpositive"] += 1

    metric_valid = len(gap_samples)
    metric_invalid = replicates - metric_valid
    valid_fraction = metric_valid / replicates
    inference_valid = metric_valid >= 2 and valid_fraction >= minimum_valid_fraction
    positive_count = len(recovery_samples)
    positive_fraction = positive_count / metric_valid if metric_valid else 0.0

    if inference_valid:
        system_intervals: Mapping[str, PercentileInterval] | None = {
            system: percentile_interval(values, level=confidence_level)
            for system, values in system_samples.items()
        }
        gap_interval = percentile_interval(gap_samples, level=confidence_level)
        delta_interval = percentile_interval(delta_samples, level=confidence_level)
    else:
        system_intervals = None
        gap_interval = None
        delta_interval = None

    if (
        inference_valid
        and positive_fraction >= minimum_positive_fraction
        and len(recovery_samples) >= 2
    ):
        recovery_interval = percentile_interval(
            recovery_samples, level=confidence_level
        )
    else:
        recovery_interval = None

    return BootstrapSummary(
        requested_replicates=replicates,
        metric_valid_replicates=metric_valid,
        metric_invalid_replicates=metric_invalid,
        metric_valid_fraction=valid_fraction,
        inference_valid=inference_valid,
        minimum_valid_fraction=minimum_valid_fraction,
        invalid_reasons=dict(sorted(invalid_reasons.items())),
        system_intervals=system_intervals,
        gap_interval=gap_interval,
        delta_bind_pp_interval=delta_interval,
        recovery_interval=recovery_interval,
        denominator_positive_replicates=positive_count,
        denominator_positive_fraction=positive_fraction,
        recovery_invalid_reasons=dict(sorted(recovery_invalid_reasons.items())),
        rng_seed=rng_seed,
        rng_algorithm="NumPy-PCG64-SeedSequence",
        resampled_levels=(
            ("patient", "training_seed", "derangement_crossed_across_training_seed")
            if resample_seed_blocks
            else ("patient",)
        ),
    )


def evaluate_formal_statistics(
    rows: Iterable[PredictionRow],
    *,
    b4a_system: str = "b4a",
    b4b_system: str = "b4b",
    learned_system: str = "learned",
    bootstrap_replicates: int = 10_000,
    patient_only_replicates: int | None = None,
    rng_seed: int = DEFAULT_BOOTSTRAP_RNG_SEED,
    confidence_level: float = 0.95,
    minimum_valid_fraction: float = 0.95,
    minimum_denominator_positive_fraction: float = 0.95,
    delta_bind_minimum_effect_pp: float = 5.0,
    enforce_seed_bank: bool = True,
    minimum_training_seeds: int = 3,
    minimum_derangements: int = 3,
) -> FormalStatisticsResult:
    """Run the preregisterable C1/C2 paired hierarchical analysis.

    The patient draw is shared across every system, sampled training-seed block
    and sampled derangement block. Metrics are first computed separately for
    each seed/derangement, averaged within seed, and then averaged across seed
    blocks. Repeated prediction rows are therefore never treated as independent
    observations.
    """

    if bootstrap_replicates < 2:
        raise FormalStatisticsError("at least two bootstrap replicates are required")
    if patient_only_replicates is None:
        patient_only_replicates = bootstrap_replicates
    if patient_only_replicates < 2:
        raise FormalStatisticsError(
            "at least two patient-only bootstrap replicates are required"
        )
    if minimum_training_seeds < 2:
        raise FormalStatisticsError(
            "minimum_training_seeds must be at least two so seed variance and "
            "leave-one-seed-out sensitivity are defined"
        )
    if not 0.0 < minimum_valid_fraction <= 1.0:
        raise FormalStatisticsError("minimum_valid_fraction must lie in (0, 1]")
    if not 0.0 < minimum_denominator_positive_fraction <= 1.0:
        raise FormalStatisticsError(
            "minimum_denominator_positive_fraction must lie in (0, 1]"
        )

    materialized = tuple(rows)
    required_systems = (b4a_system, b4b_system, learned_system)
    if len(set(required_systems)) != 3:
        raise FormalStatisticsError("B4a, B4b and learned system names must differ")
    design = _validate_design(
        materialized,
        required_systems=required_systems,
        derangement_invariant_systems=(b4b_system, learned_system),
        enforce_seed_bank=enforce_seed_bank,
        minimum_training_seeds=minimum_training_seeds,
        minimum_derangements=minimum_derangements,
    )

    all_seed_indices = tuple(range(len(design.seeds)))
    point = _point_metrics(design, all_seed_indices)
    gap = point[b4b_system] - point[b4a_system]
    numerator = point[learned_system] - point[b4a_system]
    raw_recovery = numerator / gap if gap > 0.0 else None
    delta_bind_pp = 100.0 * gap

    seed_sequence = np.random.SeedSequence(rng_seed)
    hierarchical_sequence, patient_only_sequence = seed_sequence.spawn(2)
    hierarchical = _bootstrap(
        design,
        b4a_system=b4a_system,
        b4b_system=b4b_system,
        learned_system=learned_system,
        replicates=bootstrap_replicates,
        rng=np.random.Generator(np.random.PCG64(hierarchical_sequence)),
        rng_seed=rng_seed,
        resample_seed_blocks=True,
        confidence_level=confidence_level,
        minimum_valid_fraction=minimum_valid_fraction,
        minimum_positive_fraction=minimum_denominator_positive_fraction,
    )
    patient_only = _bootstrap(
        design,
        b4a_system=b4a_system,
        b4b_system=b4b_system,
        learned_system=learned_system,
        replicates=patient_only_replicates,
        rng=np.random.Generator(np.random.PCG64(patient_only_sequence)),
        rng_seed=rng_seed,
        resample_seed_blocks=False,
        confidence_level=confidence_level,
        minimum_valid_fraction=minimum_valid_fraction,
        minimum_positive_fraction=minimum_denominator_positive_fraction,
    )

    gap_interval = hierarchical.gap_interval
    if not hierarchical.inference_valid or gap_interval is None:
        denominator_qualified = False
        undefined_reason = "hierarchical_bootstrap_invalid"
    elif gap <= 0.0:
        denominator_qualified = False
        undefined_reason = "point_denominator_nonpositive"
    elif gap_interval.lower <= 0.0:
        denominator_qualified = False
        undefined_reason = "denominator_ci_not_wholly_positive"
    elif (
        hierarchical.denominator_positive_fraction
        < minimum_denominator_positive_fraction
    ):
        denominator_qualified = False
        undefined_reason = "insufficient_positive_denominator_replicates"
    elif hierarchical.recovery_interval is None:
        denominator_qualified = False
        undefined_reason = "recovery_bootstrap_invalid"
    else:
        denominator_qualified = True
        undefined_reason = None

    recovery = RecoverySummary(
        defined=denominator_qualified,
        point_estimate=raw_recovery if denominator_qualified else None,
        raw_point_ratio=raw_recovery,
        numerator=numerator,
        denominator_gap=gap,
        denominator_qualified=denominator_qualified,
        denominator_positive_fraction=hierarchical.denominator_positive_fraction,
        confidence_interval=(
            hierarchical.recovery_interval if denominator_qualified else None
        ),
        undefined_reason=undefined_reason,
    )

    seed_effects: list[SeedEffectSummary] = []
    for seed_index, seed in enumerate(design.seeds):
        metrics = _point_metrics(design, (seed_index,))
        seed_gap = metrics[b4b_system] - metrics[b4a_system]
        seed_numerator = metrics[learned_system] - metrics[b4a_system]
        seed_effects.append(
            SeedEffectSummary(
                training_seed=seed,
                system_metrics=metrics,
                gap=seed_gap,
                delta_bind_pp=100.0 * seed_gap,
                learned_numerator=seed_numerator,
                raw_recovery=(seed_numerator / seed_gap if seed_gap > 0.0 else None),
            )
        )
    seed_effect_sd_pp = stdev(effect.delta_bind_pp for effect in seed_effects)

    leave_one_out: list[LeaveOneSeedOutSummary] = []
    for omitted_index, omitted_seed in enumerate(design.seeds):
        retained_indices = tuple(
            index for index in all_seed_indices if index != omitted_index
        )
        metrics = _point_metrics(design, retained_indices)
        loo_gap = metrics[b4b_system] - metrics[b4a_system]
        loo_numerator = metrics[learned_system] - metrics[b4a_system]
        leave_one_out.append(
            LeaveOneSeedOutSummary(
                omitted_training_seed=omitted_seed,
                retained_training_seeds=tuple(
                    design.seeds[index] for index in retained_indices
                ),
                system_metrics=metrics,
                gap=loo_gap,
                delta_bind_pp=100.0 * loo_gap,
                learned_numerator=loo_numerator,
                raw_recovery=(loo_numerator / loo_gap if loo_gap > 0.0 else None),
            )
        )

    delta_interval = hierarchical.delta_bind_pp_interval
    delta_gate = bool(
        delta_interval is not None
        and delta_bind_pp >= delta_bind_minimum_effect_pp
        and delta_interval.lower > 0.0
    )
    return FormalStatisticsResult(
        labels=LABEL_ORDER,
        patients=len(design.patients),
        training_seeds=design.seeds,
        derangement_ids=design.derangements,
        system_metrics=point,
        delta_bind_pp=delta_bind_pp,
        delta_bind_minimum_effect_pp=delta_bind_minimum_effect_pp,
        delta_bind_gate_pass=delta_gate,
        recovery=recovery,
        hierarchical_bootstrap=hierarchical,
        patient_only_bootstrap=patient_only,
        seed_effects=tuple(seed_effects),
        seed_effect_sd_pp=seed_effect_sd_pp,
        leave_one_seed_out=tuple(leave_one_out),
    )
