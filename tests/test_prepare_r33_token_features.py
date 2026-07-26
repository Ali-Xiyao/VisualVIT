import torch

from scripts.prepare_r33_token_features import (
    build_prior_shuffle,
    summarize_bundle,
)
from visualvit.schemas import TokenBundle


def test_summary_has_matched_six_type_mean_max_and_validity():
    bundle = TokenBundle(
        tokens=torch.randn(2, 64, 64),
        token_types=torch.tensor(
            [0] * 4 + [1] * 12 + [2] * 16 + [3] * 16 + [4] * 12 + [5] * 4
        ),
        valid_mask=torch.ones(2, 64, dtype=torch.bool),
        assignment=torch.zeros(2, 1, 1),
    )
    assert summarize_bundle(bundle).shape == (2, 774)


def test_prior_shuffle_is_cross_patient_within_finding():
    records = [
        {"record_id": f"r{i}", "patient_id": f"p{i}", "finding_token": "f"}
        for i in range(4)
    ]
    mapping = build_prior_shuffle(records)
    assert sorted(mapping) == list(range(4))
    assert all(
        records[index]["patient_id"] != records[mapping[index]]["patient_id"]
        for index in range(4)
    )
