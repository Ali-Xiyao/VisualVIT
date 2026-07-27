import torch

from scripts.run_r37_prta_smoke import (
    balanced_sample,
    macro_f1,
    responsiveness_diagnostics,
)


def test_balanced_smoke_sample_is_deterministic():
    examples = [
        {
            "example_id": f"{label}-{index}",
            "label": label,
        }
        for label in ("Stable", "Improved", "Worse", "New", "Resolved")
        for index in range(5)
    ]
    first = balanced_sample(examples, maximum=10, seed=17)
    second = balanced_sample(examples, maximum=10, seed=17)
    assert first == second
    counts = {}
    for item in first:
        counts[item["label"]] = counts.get(item["label"], 0) + 1
    assert set(counts.values()) == {2}


def test_macro_f1_is_one_for_perfect_five_class_predictions():
    values = [0, 1, 2, 3, 4]
    assert macro_f1(values, values) == 1.0


def test_responsiveness_diagnostics_distinguish_continuous_and_argmax_change():
    reference_embeddings = torch.tensor([[1.0, 0.0], [0.0, 1.0]])
    control_embeddings = torch.tensor([[1.0, 0.0], [1.0, 0.0]])
    reference_logits = torch.tensor([[2.0, 1.0], [1.0, 2.0]])
    control_logits = torch.tensor([[2.0, 1.0], [2.0, 1.0]])

    result = responsiveness_diagnostics(
        reference_embeddings,
        control_embeddings,
        reference_logits,
        control_logits,
    )

    assert result["rows"] == 2
    assert result["embedding_l2_mean"] > 0
    assert result["logit_l2_mean"] > 0
    assert result["prediction_change_count"] == 1
    assert result["prediction_change_rate"] == 0.5
