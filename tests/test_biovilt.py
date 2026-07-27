from __future__ import annotations

from pathlib import Path

from PIL import Image
import pytest
import torch
from torch import nn

from visualvit.biovilt import (
    BIOVILT_CROP,
    BIOVILT_FEATURE_DIM,
    FindingConditionedLinearProbe,
    canonical_pair_embedding,
    load_biovilt_image,
    load_frozen_biovilt,
)


class _Output:
    def __init__(self, value: torch.Tensor) -> None:
        self.projected_global_embedding = value


class _PairModel(nn.Module):
    def forward(
        self, *, current_image: torch.Tensor, previous_image: torch.Tensor
    ) -> _Output:
        value = current_image[:, :BIOVILT_FEATURE_DIM]
        return _Output(value + previous_image[:, :BIOVILT_FEATURE_DIM])


def test_official_preprocess_is_grayscale_three_channel_448(tmp_path: Path):
    path = tmp_path / "image.png"
    Image.new("L", (600, 700), color=128).save(path)
    tensor = load_biovilt_image(path)
    assert tensor.shape == (3, BIOVILT_CROP, BIOVILT_CROP)
    assert torch.equal(tensor[0], tensor[1])
    assert torch.equal(tensor[1], tensor[2])


def test_canonical_pair_embedding_is_normalized_and_ordered():
    current = torch.zeros(2, BIOVILT_FEATURE_DIM)
    prior = torch.zeros_like(current)
    current[:, 0] = 2
    prior[:, 1] = 1
    result = canonical_pair_embedding(
        _PairModel(), current_image=current, prior_image=prior
    )
    assert result.shape == (2, BIOVILT_FEATURE_DIM)
    assert torch.allclose(result.norm(dim=-1), torch.ones(2))
    assert result[0, 0] > result[0, 1]


def test_loader_fails_closed_without_pinned_source(tmp_path: Path):
    checkpoint = tmp_path / "weights.pt"
    torch.save({}, checkpoint)
    with pytest.raises(FileNotFoundError, match="HI-ML source root"):
        load_frozen_biovilt(
            checkpoint,
            tmp_path / "missing-source",
            torch.device("cpu"),
        )


def test_finding_conditioned_probe_shape_and_query_effect():
    probe = FindingConditionedLinearProbe(finding_count=12, class_count=5)
    embeddings = torch.zeros(2, BIOVILT_FEATURE_DIM)
    findings = torch.tensor([0, 1])
    logits = probe(embeddings, findings)
    assert logits.shape == (2, 5)
    assert not torch.equal(logits[0], logits[1])
