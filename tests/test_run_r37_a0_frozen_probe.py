import torch

from scripts.run_r37_a0_frozen_probe import make_tensors


def test_a0_make_tensors_preserves_example_order():
    examples = [
        {"example_id": "b", "finding": "f1", "label": "Stable"},
        {"example_id": "a", "finding": "f0", "label": "New"},
    ]
    features = {
        "a": {"true_pair": torch.ones(3)},
        "b": {"true_pair": torch.zeros(3)},
    }
    x, findings, labels = make_tensors(
        examples,
        features,
        mode="true_pair",
        finding_to_index={"f0": 0, "f1": 1},
        label_to_index={"Stable": 0, "New": 1},
        device=torch.device("cpu"),
    )
    assert torch.equal(
        x, torch.tensor([[0.0, 0.0, 0.0], [1.0, 1.0, 1.0]])
    )
    assert findings.tolist() == [1, 0]
    assert labels.tolist() == [0, 1]
