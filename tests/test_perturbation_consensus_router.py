import pytest
import torch

from visualvit.hierarchical_temporal_tokens import (
    HierarchicalTemporalTokenBuilder,
)
from visualvit.perturbation_consensus_router import (
    assert_oof_routes,
    fold_assignment,
    hard_consensus_route,
    matched_random_route,
    select_bundle,
)


def test_hard_gate_requires_three_way_unanimity_and_random_matches_coverage():
    logits = torch.tensor(
        [
            [[5.0, 0.0], [5.0, 0.0], [0.0, 5.0]],
            [[4.0, 0.0], [0.0, 4.0], [0.0, 4.0]],
            [[3.0, 0.0], [3.0, 0.0], [0.0, 3.0]],
        ]
    )
    route = hard_consensus_route(logits)
    assert route.tolist() == [True, False, True]
    random = matched_random_route(route, seed=17)
    assert int(random.sum()) == int(route.sum())


def test_selected_bundle_does_not_expose_probe_logits():
    pair = HierarchicalTemporalTokenBuilder(4)(
        torch.randn(2, 6, 4), torch.randn(2, 6, 4), torch.randn(2, 4)
    )
    selected = select_bundle(
        pair.robust, pair.rich, torch.tensor([False, True])
    )
    assert torch.equal(selected.tokens[0], pair.robust.tokens[0])
    assert torch.equal(selected.tokens[1], pair.rich.tokens[1])
    assert selected.tokens.shape == (2, 64, 4)


def test_oof_contract_rejects_in_sample_routes():
    assignment = fold_assignment(["p1", "p2"])
    rows = [
        {
            "patient_id": patient,
            "predicted_fold": fold,
            "trained_folds": [value for value in range(5) if value != fold],
        }
        for patient, fold in assignment.items()
    ]
    assert_oof_routes(rows, assignment)
    rows[0]["trained_folds"] = list(range(5))
    with pytest.raises(ValueError, match="in-sample"):
        assert_oof_routes(rows, assignment)
