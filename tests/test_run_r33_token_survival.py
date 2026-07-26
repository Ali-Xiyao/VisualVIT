import torch

from scripts.run_r33_token_survival import (
    benefit_router_features,
    benefit_router_targets,
    bootstrap_systems,
    fit_batched_mlp,
    fit_benefit_router,
    mask_token_types,
    route_behavior,
    training_weights,
    weighted_confusion,
    predict_batched_mlp,
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


def test_benefit_target_and_router_are_label_free_at_evaluation():
    labels = torch.tensor([0, 1, 2, 0])
    robust = torch.tensor(
        [
            [[0.0, 2.0, 0.0], [0.0, 2.0, 0.0], [0.0, 0.0, 2.0], [2.0, 0.0, 0.0]],
            [[0.0, 2.0, 0.0], [0.0, 2.0, 0.0], [0.0, 0.0, 2.0], [2.0, 0.0, 0.0]],
            [[0.0, 2.0, 0.0], [0.0, 2.0, 0.0], [0.0, 0.0, 2.0], [2.0, 0.0, 0.0]],
        ]
    )
    rich = robust.clone()
    rich[:, 0] = torch.tensor([2.0, 0.0, 0.0])
    rich[:, 1] = torch.tensor([2.0, 0.0, 0.0])
    features = benefit_router_features(robust, rich)
    targets, decisive, score = benefit_router_targets(robust, rich, labels)
    assert features.shape[0] == len(labels)
    assert score.tolist() == [3, -3, 0, 0]
    assert decisive.tolist() == [True, True, False, False]
    repeated_features = torch.cat((features[:2], features[:2] + 0.1))
    repeated_targets = torch.tensor([1, 0, 1, 0])
    route, audit = fit_benefit_router(
        repeated_features,
        repeated_targets,
        features,
        seed=7,
    )
    assert route.shape == labels.shape
    assert audit["finite"]


def test_batched_mlp_probe_has_matched_model_axis():
    features = torch.randn(2, 12, 6)
    labels = torch.tensor([0, 1, 2] * 4)
    models = fit_batched_mlp(
        features,
        labels,
        torch.ones(12),
        seed=9,
        device=torch.device("cpu"),
        epochs=1,
        batch_size=6,
        hidden_dim=4,
    )
    logits = predict_batched_mlp(models, features, torch.device("cpu"))
    assert logits.shape == (2, 12, 3)
    assert bool(torch.isfinite(logits).all())
