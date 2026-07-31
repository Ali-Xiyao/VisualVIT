from __future__ import annotations

import pytest
import torch

from scripts.cache_prta_gen_r51_tokens import Exact64ShardWriter
from visualvit.r51_exact64 import (
    B2_PATCH_POSITIONS,
    TILA_PATCH_POSITIONS,
    b2_patch_tokens_to_exact64,
    normalize_exact64_tokens,
    tila_projected_patches_to_exact64,
)


def _assert_exact64(tokens: torch.Tensor) -> None:
    assert tokens.shape[-2:] == (64, 768)
    assert torch.isfinite(tokens).all()
    assert tokens[..., 60:64, :].eq(0).all()
    rms = tokens[..., :60, :].square().mean(dim=-1).sqrt()
    assert torch.allclose(rms, torch.ones_like(rms), atol=1e-5)


def test_r51_tila_translation_is_fixed_exact64() -> None:
    patches = torch.arange(2 * 128 * 14 * 14, dtype=torch.float32).reshape(
        2, 128, 14, 14
    )
    tokens = tila_projected_patches_to_exact64(patches)
    _assert_exact64(tokens)
    assert len(TILA_PATCH_POSITIONS) == 60
    assert TILA_PATCH_POSITIONS[0] == 0
    assert TILA_PATCH_POSITIONS[-1] == 195


def test_r51_b2_translation_has_four_fifteen_token_groups() -> None:
    prior = torch.randn(2, 197, 768)
    current = prior + 0.1 * torch.randn_like(prior)
    tokens = b2_patch_tokens_to_exact64(prior, current)
    _assert_exact64(tokens)
    assert len(B2_PATCH_POSITIONS) == 15
    assert B2_PATCH_POSITIONS[0] == 1
    assert B2_PATCH_POSITIONS[-1] == 196
    assert tokens[:, 45:60].ge(0).all()


def test_r51_common_normalization_rejects_shape_and_nonfinite() -> None:
    with pytest.raises(ValueError, match="64,768"):
        normalize_exact64_tokens(torch.zeros(1, 60, 768))
    invalid = torch.zeros(1, 64, 768)
    invalid[0, 0, 0] = float("nan")
    with pytest.raises(ValueError, match="finite"):
        normalize_exact64_tokens(invalid)


def test_r51_shard_writer_keeps_only_label_free_exact64_payload(tmp_path) -> None:
    writer = Exact64ShardWriter(
        tmp_path / "tokens", shard_size=2, schema="test.r51.shard"
    )
    rows = [
        {"example_id": "e1", "patient_id": "p1", "finding": "Edema"},
        {"example_id": "e2", "patient_id": "p2", "finding": "Edema"},
    ]
    tokens = normalize_exact64_tokens(torch.randn(2, 64, 768))
    writer.add(rows, tokens)
    assert len(writer.shards) == 1
    payload = torch.load(
        writer.shards[0]["path"], map_location="cpu", weights_only=True
    )
    assert payload["exact64_tokens"].shape == (2, 64, 768)
    assert "labels" not in payload
    assert "progression" not in payload
    assert payload["example_ids"] == ["e1", "e2"]
