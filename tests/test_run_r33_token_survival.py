import torch

from scripts.run_r33_token_survival import (
    bootstrap_systems,
    mask_token_types,
    route_behavior,
    training_weights,
    weighted_confusion,
)


def test_type_mask_preserves_only_requested_mean_max_fraction():
    features = torch.arange(774, dtype=torch.float32).view(1, -1) + 1
    masked = mask_token_types(features, (0, 2))
    assert masked[0, :64].ne(0).all()
    assert masked[0, 64:128].eq(0).all()
    assert masked[0, 128:192].ne(0).all()
    assert masked[0, 384:448].ne(0).all()
    assert masked[0, 448:512].eq(0).all()
    assert masked[0, 512:576].ne(0).all()
    assert masked[0, 768].ne(0)
    assert masked[0, 769].eq(0)
    assert masked[0, 770].ne(0)


def test_training_weights_balance_class_and_patient_rows():
    labels = torch.tensor([0, 0, 1, 1, 1, 2])
    patients = ["a", "a", "b", "c", "c", "d"]
    weights = training_weights(labels, patients)
    assert torch.isclose(weights.mean(), torch.tensor(1.0))
    assert bool(torch.isfinite(weights).all())
    assert bool(weights.gt(0).all())


def test_patient_balanced_metric_and_bootstrap_are_valid():
    labels = torch.tensor([0, 1, 2, 0, 1, 2])
    patients = ["a", "a", "b", "b", "c", "c"]
    robust = torch.tensor([[0, 1, 2, 1, 1, 0]])
    tier = torch.tensor([[0, 1, 2, 0, 1, 2]])
    metrics = weighted_confusion(labels, tier, patients)
    assert metrics["macro_f1"] == 1.0
    bootstrap = bootstrap_systems(
        labels, {"P3": robust, "P6": tier}, patients, 100, seed=7
    )
    assert bootstrap["replicates_valid"] == 100
    assert bootstrap["systems"]["P6"]["delta_vs_p3_ci95"][0] >= 0


def test_route_behavior_reports_correction_without_harm():
    labels = torch.tensor([0, 1, 2])
    robust = torch.tensor([[1, 1, 2]])
    routed = torch.tensor([[0, 1, 2]])
    behavior = route_behavior(
        labels,
        robust,
        routed,
        torch.tensor([True, False, False]),
        ["a", "b", "c"],
    )
    assert behavior["correction_rate"] > 0
    assert behavior["harm_rate"] == 0
    assert behavior["net_corrected"] > 0
