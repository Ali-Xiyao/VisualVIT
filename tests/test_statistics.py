from dataclasses import replace

import pytest

import visualvit.statistics as statistics_module
from visualvit.statistics import (
    FormalStatisticsError,
    LABEL_ORDER,
    LabelSupportError,
    PairingError,
    PredictionRow,
    PseudoreplicationError,
    evaluate_formal_statistics,
    weighted_macro_f1,
)


SEEDS = (17, 29, 43)
DERANGEMENTS = (101, 103, 107)


def _formal_rows(
    *,
    patients_per_label: int = 10,
    identical_b4: bool = False,
    omitted_label: str | None = None,
) -> list[PredictionRow]:
    rows: list[PredictionRow] = []
    b4a_thresholds = {17: 8, 29: 5, 43: 2}
    learned_thresholds = {17: 4, 29: 3, 43: 1}
    for seed in SEEDS:
        for derangement_index, derangement in enumerate(DERANGEMENTS):
            threshold_shift = 0 if identical_b4 else derangement_index - 1
            for label_index, target in enumerate(LABEL_ORDER):
                if target == omitted_label:
                    continue
                for patient_index in range(patients_per_label):
                    patient_id = f"{target}-{patient_index:03d}"
                    wrong = LABEL_ORDER[(label_index + 1) % len(LABEL_ORDER)]
                    b4a_threshold = max(
                        0,
                        min(
                            patients_per_label,
                            b4a_thresholds[seed] + threshold_shift,
                        ),
                    )
                    learned_threshold = max(
                        0,
                        min(
                            patients_per_label,
                            learned_thresholds[seed],
                        ),
                    )
                    b4a_prediction = wrong if patient_index < b4a_threshold else target
                    predictions = {
                        "b4a": b4a_prediction,
                        "b4b": b4a_prediction if identical_b4 else target,
                        "learned": (
                            wrong if patient_index < learned_threshold else target
                        ),
                    }
                    for system, prediction in predictions.items():
                        rows.append(
                            PredictionRow(
                                patient_id=patient_id,
                                observation_id="entity-0",
                                training_seed=seed,
                                derangement_id=derangement,
                                system=system,
                                target=target,
                                prediction=prediction,
                                weight=1.0,
                            )
                        )
    return rows


def test_weighted_macro_f1_uses_fixed_five_label_endpoint():
    rows = []
    for index, target in enumerate(LABEL_ORDER):
        prediction = "stable" if target == "resolved" else target
        rows.append(
            PredictionRow(
                patient_id=f"p{index}",
                observation_id="q0",
                training_seed=17,
                derangement_id=101,
                system="b4a",
                target=target,
                prediction=prediction,
                weight=1.0,
            )
        )

    result = weighted_macro_f1(rows)

    assert result.per_class_f1["stable"] == pytest.approx(2.0 / 3.0)
    assert result.per_class_f1["resolved"] == 0.0
    assert result.macro_f1 == pytest.approx((2.0 / 3.0 + 3.0) / 5.0)
    assert result.support == {label: 1.0 for label in LABEL_ORDER}


def test_weighted_macro_f1_honors_entity_weights_within_patient():
    rows = [
        PredictionRow(
            patient_id="stable-patient",
            observation_id="q0",
            training_seed=17,
            derangement_id=101,
            system="b4a",
            target="stable",
            prediction="stable",
            weight=0.75,
        ),
        PredictionRow(
            patient_id="stable-patient",
            observation_id="q1",
            training_seed=17,
            derangement_id=101,
            system="b4a",
            target="stable",
            prediction="worse",
            weight=0.25,
        ),
    ]
    for target in LABEL_ORDER[1:]:
        rows.append(
            PredictionRow(
                patient_id=f"{target}-patient",
                observation_id="q0",
                training_seed=17,
                derangement_id=101,
                system="b4a",
                target=target,
                prediction=target,
                weight=1.0,
            )
        )

    result = weighted_macro_f1(rows)

    assert result.support["stable"] == 1.0
    assert result.true_positive["stable"] == 0.75
    assert result.false_negative["stable"] == 0.25
    assert result.false_positive["worse"] == 0.25
    expected = ((1.5 / 1.75) + (2.0 / 2.25) + 3.0) / 5.0
    assert result.macro_f1 == pytest.approx(expected)


def test_single_block_metric_rejects_pooled_repeated_rows():
    rows = _formal_rows(patients_per_label=1)
    two_systems = [row for row in rows if row.system in {"b4a", "b4b"}]
    with pytest.raises(PseudoreplicationError):
        weighted_macro_f1(two_systems)


def test_hierarchical_bootstrap_is_paired_and_identical_effect_is_zero():
    result = evaluate_formal_statistics(
        _formal_rows(identical_b4=True),
        bootstrap_replicates=120,
        rng_seed=77,
    )

    assert result.delta_bind_pp == 0.0
    assert result.hierarchical_bootstrap.delta_bind_pp_interval is not None
    assert result.hierarchical_bootstrap.delta_bind_pp_interval.lower == 0.0
    assert result.hierarchical_bootstrap.delta_bind_pp_interval.upper == 0.0
    assert result.patient_only_bootstrap.delta_bind_pp_interval is not None
    assert result.patient_only_bootstrap.delta_bind_pp_interval.lower == 0.0
    assert result.patient_only_bootstrap.delta_bind_pp_interval.upper == 0.0


def test_derangement_draw_is_crossed_and_shared_across_sampled_seeds(monkeypatch):
    observed_draws: list[tuple[tuple[int, ...], ...]] = []
    original = statistics_module._evaluate_draw

    def recording_evaluate_draw(
        design, patient_counts, seed_indices, derangement_draws
    ):
        if len(seed_indices) > 1:
            observed_draws.append(tuple(tuple(draw) for draw in derangement_draws))
        return original(design, patient_counts, seed_indices, derangement_draws)

    monkeypatch.setattr(statistics_module, "_evaluate_draw", recording_evaluate_draw)
    result = evaluate_formal_statistics(
        _formal_rows(),
        bootstrap_replicates=20,
        patient_only_replicates=10,
        rng_seed=314,
    )

    assert result.hierarchical_bootstrap.resampled_levels == (
        "patient",
        "training_seed",
        "derangement_crossed_across_training_seed",
    )
    assert observed_draws
    assert all(len(set(draws)) == 1 for draws in observed_draws)


def test_seed_variance_and_leave_one_seed_out_are_reported():
    result = evaluate_formal_statistics(
        _formal_rows(),
        bootstrap_replicates=240,
        rng_seed=91,
    )

    assert result.seed_effect_sd_pp > 0.0
    assert tuple(item.training_seed for item in result.seed_effects) == SEEDS
    assert (
        tuple(item.omitted_training_seed for item in result.leave_one_seed_out) == SEEDS
    )
    assert all(
        len(item.retained_training_seeds) == 2 for item in result.leave_one_seed_out
    )
    hierarchical = result.hierarchical_bootstrap.delta_bind_pp_interval
    patient_only = result.patient_only_bootstrap.delta_bind_pp_interval
    assert hierarchical is not None and patient_only is not None
    assert (
        hierarchical.upper - hierarchical.lower
        > patient_only.upper - patient_only.lower
    )


def test_recovery_is_undefined_when_b4_denominator_is_unqualified():
    result = evaluate_formal_statistics(
        _formal_rows(identical_b4=True),
        bootstrap_replicates=120,
        rng_seed=123,
    )

    assert not result.recovery.defined
    assert not result.recovery.denominator_qualified
    assert result.recovery.point_estimate is None
    assert result.recovery.raw_point_ratio is None
    assert result.recovery.undefined_reason == "point_denominator_nonpositive"
    assert result.hierarchical_bootstrap.denominator_positive_fraction == 0.0
    assert result.hierarchical_bootstrap.recovery_invalid_reasons == {
        "denominator_nonpositive": 120
    }


def test_fixed_rng_makes_full_analysis_deterministic():
    rows = _formal_rows()
    first = evaluate_formal_statistics(
        rows,
        bootstrap_replicates=100,
        patient_only_replicates=80,
        rng_seed=2026,
    )
    second = evaluate_formal_statistics(
        rows,
        bootstrap_replicates=100,
        patient_only_replicates=80,
        rng_seed=2026,
    )

    assert first == second


def test_primary_endpoint_fails_closed_when_a_label_has_no_support():
    with pytest.raises(LabelSupportError, match="resolved"):
        evaluate_formal_statistics(
            _formal_rows(omitted_label="resolved"),
            bootstrap_replicates=20,
        )


def test_invalid_bootstrap_replicates_are_counted_and_suppress_ci():
    result = evaluate_formal_statistics(
        _formal_rows(patients_per_label=1),
        bootstrap_replicates=200,
        rng_seed=42,
    )

    summary = result.hierarchical_bootstrap
    assert summary.metric_invalid_replicates > 0
    assert summary.metric_valid_replicates + summary.metric_invalid_replicates == 200
    assert summary.metric_valid_fraction < summary.minimum_valid_fraction
    assert not summary.inference_valid
    assert summary.invalid_reasons
    assert summary.delta_bind_pp_interval is None
    assert not result.delta_bind_gate_pass
    assert not result.recovery.defined


def test_design_rejects_an_unpaired_missing_system_row():
    rows = _formal_rows(patients_per_label=2)
    dropped = next(row for row in rows if row.system == "learned")
    rows.remove(dropped)

    with pytest.raises(PairingError):
        evaluate_formal_statistics(rows, bootstrap_replicates=20)


def test_design_rejects_cross_system_weight_mutation():
    rows = _formal_rows(patients_per_label=2)
    index = next(index for index, row in enumerate(rows) if row.system == "learned")
    rows[index] = replace(rows[index], weight=0.5)

    with pytest.raises(PairingError):
        evaluate_formal_statistics(rows, bootstrap_replicates=20)


@pytest.mark.parametrize("system", ["b4b", "learned"])
def test_pairing_replicas_must_be_prediction_invariant_across_derangements(system):
    rows = _formal_rows(patients_per_label=2)
    index = next(
        index
        for index, row in enumerate(rows)
        if row.system == system and row.derangement_id == DERANGEMENTS[1]
    )
    current = rows[index].prediction
    replacement = next(label for label in LABEL_ORDER if label != current)
    rows[index] = replace(rows[index], prediction=replacement)

    with pytest.raises(PairingError, match="derangement-invariant"):
        evaluate_formal_statistics(rows, bootstrap_replicates=20)


def test_minimum_training_seed_setting_cannot_disable_seed_variance_gate():
    with pytest.raises(FormalStatisticsError, match="at least two"):
        evaluate_formal_statistics(
            _formal_rows(patients_per_label=2),
            bootstrap_replicates=20,
            minimum_training_seeds=1,
        )
