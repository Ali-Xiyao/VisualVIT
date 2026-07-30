import torch

from scripts.run_prta_gen_r40c_structured_generalization import (
    load_token_variants,
    padded_query_features,
    per_class_recall,
    train_head_arm,
)


def test_padded_query_features_use_only_registered_finding_slots():
    findings = [f"finding-{index}" for index in range(12)]
    rows = [{"finding": findings[3]}, {"finding": findings[8]}]
    features = padded_query_features(
        rows, findings=findings, input_width=20
    )
    assert features.shape == (2, 20)
    assert features.sum(dim=1).tolist() == [1.0, 1.0]
    assert features[0, 3] == 1
    assert features[1, 8] == 1
    assert not bool(features[:, 12:].any())


def test_per_class_recall_reports_every_registered_class():
    recalls = per_class_recall(
        [0, 0, 1, 1, 2, 2],
        [0, 1, 1, 1, 0, 2],
        class_count=3,
    )
    assert recalls == [0.5, 1.0, 0.5]


def test_load_token_variants_reads_each_selected_example_once(tmp_path):
    shard_path = tmp_path / "shard.pt"
    torch.save(
        {
            "example_ids": ["e1", "e2"],
            "patient_ids": ["p1", "p2"],
            "findings": ["Edema", "Pneumothorax"],
            "true_tokens": torch.ones(2, 64, 768),
            "current_tokens": torch.full((2, 64, 768), 2.0),
            "shuffled_tokens": torch.full((2, 64, 768), 3.0),
        },
        shard_path,
    )
    selected, patients, findings = load_token_variants(
        {"shards": [{"path": str(shard_path)}]},
        example_ids={"e2"},
        token_keys={
            "true_pair": "true_tokens",
            "current_only": "current_tokens",
            "prior_shuffle": "shuffled_tokens",
        },
    )
    assert set(patients) == {"e2"}
    assert patients["e2"] == "p2"
    assert findings["e2"] == "Pneumothorax"
    assert selected["true_pair"]["e2"].mean() == 1
    assert selected["current_only"]["e2"].mean() == 2
    assert selected["prior_shuffle"]["e2"].mean() == 3


def test_train_head_arm_fits_normalization_on_training_only():
    generator = torch.Generator().manual_seed(7)
    training_features = torch.randn(20, 10, generator=generator)
    training_targets = torch.tensor([index % 5 for index in range(20)])
    development_features = (
        torch.randn(10, 10, generator=generator) + 1000.0
    )
    development_targets = torch.tensor([index % 5 for index in range(10)])
    head, mean, _, predictions, audit = train_head_arm(
        training_features=training_features,
        training_targets=training_targets,
        development_features=development_features,
        development_targets=development_targets,
        seed=17,
        hidden_width=8,
        class_count=5,
        epochs=2,
        batch_size=5,
        learning_rate=0.001,
        weight_decay=0.0,
        gradient_clip_norm=1.0,
        device=torch.device("cpu"),
    )
    assert head(torch.zeros(3, 10)).shape == (3, 5)
    assert torch.allclose(mean, training_features.mean(dim=0, keepdim=True))
    assert len(predictions) == 10
    assert audit["updates"] == 8
    assert audit["normalization_fit_on_training_only"] is True
