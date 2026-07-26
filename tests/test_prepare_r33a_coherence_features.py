import torch

from scripts.prepare_r33a_coherence_features import (
    ADAPTER_INPUT,
    ADAPTER_SCALE,
    ADAPTER_WIDTH,
    CoherenceAdapter,
    build_contrastive_negatives,
    projection_matrices,
    relation_with_coherence,
)
from scripts.prepare_r33a_direct_transition_features import projection


def test_contrastive_negative_is_finding_matched_cross_patient():
    records = [
        {
            "record_id": f"r{index}",
            "patient_id": f"p{index}",
            "finding_token": "edema",
        }
        for index in range(6)
    ]
    mapping = build_contrastive_negatives(records)
    assert sorted(mapping) == list(range(6))
    assert all(
        records[source]["finding_token"] == records[target]["finding_token"]
        and records[source]["patient_id"] != records[target]["patient_id"]
        for source, target in enumerate(mapping)
    )


def test_coherence_adapter_and_equal_width_relation_blocks():
    adapter = CoherenceAdapter()
    base = torch.randn(3, ADAPTER_INPUT)
    embedding = adapter.encode(base)
    assert embedding.shape == (3, ADAPTER_WIDTH)
    assert adapter(base).shape == (3,)
    robust = relation_with_coherence(base, None)
    rich = relation_with_coherence(base, embedding)
    assert robust.shape == rich.shape == (3, ADAPTER_INPUT + ADAPTER_WIDTH)
    assert torch.equal(robust[:, -ADAPTER_WIDTH:], torch.zeros(3, ADAPTER_WIDTH))
    assert torch.allclose(
        rich[:, -ADAPTER_WIDTH:], embedding * ADAPTER_SCALE
    )


def test_projection_matrices_preserve_attempt_d_rows():
    matrices = projection_matrices(11, seed=17, device=torch.device("cpu"))
    expected_query = projection(
        11, seed=20263400 + 17 * 100, device=torch.device("cpu")
    )
    expected_relation = projection(
        ADAPTER_INPUT,
        seed=20263400 + 17 * 100 + 4,
        device=torch.device("cpu"),
    )
    assert torch.equal(matrices["query"], expected_query)
    assert torch.equal(matrices["relation"][:ADAPTER_INPUT], expected_relation)
    assert matrices["relation"].shape == (
        ADAPTER_INPUT + ADAPTER_WIDTH,
        2 * ADAPTER_WIDTH,
    )
