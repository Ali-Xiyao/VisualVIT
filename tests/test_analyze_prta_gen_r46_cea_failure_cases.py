from __future__ import annotations

from scripts.analyze_prta_gen_r46_cea_failure_cases import (
    consensus_prediction,
)


def test_consensus_prediction_overrides_on_majority_causal_support() -> None:
    prediction, override = consensus_prediction(
        baseline=0,
        true_predictions=[2, 2, 1],
        current_predictions=[0, 0, 2],
        minimum_true_votes=2,
        minimum_causal_votes=2,
    )
    assert prediction == 2
    assert override is True


def test_consensus_prediction_preserves_baseline_without_causal_votes() -> None:
    prediction, override = consensus_prediction(
        baseline=0,
        true_predictions=[2, 2, 2],
        current_predictions=[2, 2, 0],
        minimum_true_votes=3,
        minimum_causal_votes=2,
    )
    assert prediction == 0
    assert override is False


def test_consensus_prediction_preserves_matching_baseline() -> None:
    prediction, override = consensus_prediction(
        baseline=2,
        true_predictions=[2, 2, 2],
        current_predictions=[0, 0, 0],
        minimum_true_votes=3,
        minimum_causal_votes=3,
    )
    assert prediction == 2
    assert override is False
