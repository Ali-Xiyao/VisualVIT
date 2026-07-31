from __future__ import annotations

import pytest
import torch

from visualvit.cea import (
    arbitrate_predictions,
    jensen_shannon_causal_score,
    select_shared_quantile,
)


def test_causal_score_is_zero_for_identical_distributions() -> None:
    probabilities = torch.tensor([[0.7, 0.2, 0.1]])
    score = jensen_shannon_causal_score(probabilities, probabilities)
    assert score.item() == pytest.approx(0.0, abs=1e-8)


def test_causal_score_increases_for_distinct_distribution() -> None:
    source = torch.tensor([[0.8, 0.1, 0.1]])
    near = torch.tensor([[0.7, 0.2, 0.1]])
    far = torch.tensor([[0.1, 0.1, 0.8]])
    near_score = jensen_shannon_causal_score(source, near)
    far_score = jensen_shannon_causal_score(source, far)
    assert far_score.item() > near_score.item() > 0


def test_arbitration_preserves_low_evidence_baseline() -> None:
    result = arbitrate_predictions(
        baseline_predictions=[0, 1, 2],
        structured_predictions=[2, 2, 2],
        scores=torch.tensor([0.1, 0.6, 0.2]),
        threshold=0.5,
    )
    assert result["predictions"] == [0, 2, 2]
    assert result["eligible"] == [False, True, False]
    assert result["actual_override_rate"] == pytest.approx(1 / 3)
    assert result["low_evidence_baseline_agreement"] == 1.0


def test_shared_quantile_ties_by_override_then_higher_quantile() -> None:
    selected = select_shared_quantile(
        {
            "0.2": [{"macro_f1": 0.5, "actual_override_rate": 0.4}],
            "0.8": [{"macro_f1": 0.5, "actual_override_rate": 0.2}],
        }
    )
    assert selected["quantile"] == 0.8
