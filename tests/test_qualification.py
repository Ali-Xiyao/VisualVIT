import pytest
import torch

from visualvit.qualification import (
    FindingConditionedLinearProbe,
    macro_f1,
    patient_bootstrap_difference,
    patient_bootstrap_mean_seed_difference,
    three_seed_survival_gate,
)


def test_generic_finding_conditioned_probe():
    probe = FindingConditionedLinearProbe(
        feature_dim=4, finding_count=3, class_count=2
    )
    logits = probe(torch.zeros(2, 4), torch.tensor([0, 2]))
    assert logits.shape == (2, 2)


def test_macro_f1_checks_lengths():
    with pytest.raises(ValueError, match="lengths differ"):
        macro_f1([0], [0, 1], class_count=2)


def test_patient_bootstrap_is_clustered_and_deterministic():
    kwargs = {
        "patient_ids": ["a", "a", "b", "b"],
        "targets": [0, 1, 0, 1],
        "true_predictions": [0, 1, 0, 1],
        "control_predictions": [1, 0, 1, 0],
        "class_count": 2,
        "replicates": 100,
        "seed": 9,
    }
    first = patient_bootstrap_difference(**kwargs)
    second = patient_bootstrap_difference(**kwargs)
    assert first == second
    assert first["patients"] == 2
    assert first["observed_difference_pp"] == 100
    assert first["ci95_lower_pp"] == 100


def test_three_seed_gate_requires_gain_ci_and_each_seed():
    passed = three_seed_survival_gate(
        [2.1, 2.4, 2.0], pooled_ci_lower_pp=0.1
    )
    failed = three_seed_survival_gate(
        [3.0, -0.1, 3.2], pooled_ci_lower_pp=0.1
    )
    assert passed["passed"]
    assert not failed["passed"]


def test_multi_seed_bootstrap_uses_mean_seed_difference():
    result = patient_bootstrap_mean_seed_difference(
        patient_ids=["a", "a", "b", "b"],
        targets=[0, 1, 0, 1],
        true_predictions_by_seed=[
            [0, 1, 0, 1],
            [0, 1, 0, 1],
            [0, 1, 0, 1],
        ],
        control_predictions_by_seed=[
            [1, 0, 1, 0],
            [1, 0, 1, 0],
            [1, 0, 1, 0],
        ],
        class_count=2,
        replicates=50,
        seed=4,
    )
    assert result["observed_seed_differences_pp"] == [100, 100, 100]
    assert result["ci95_lower_pp"] == 100
