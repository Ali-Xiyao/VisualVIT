import json

import pytest
import torch

from scripts.build_prta_gen_r40a1_roster import CONFIG_STATUS, ROSTER_PASS
from scripts.cache_prta_gen_r40a1_features import (
    FEATURE_STATUS,
    build_feature_cache,
    candidate_features,
)


def write_json(path, payload):
    path.write_text(json.dumps(payload), encoding="utf-8")


def write_fixture(tmp_path):
    source_shard = tmp_path / "tokens.pt"
    tokens = torch.randn(3, 64, 4, dtype=torch.float16)
    torch.save(
        {
            "example_ids": ["e0", "e1", "e2"],
            "patient_ids": ["p0", "p1", "p2"],
            "findings": ["Edema", "Edema", "Atelectasis"],
            "true_tokens": tokens,
            "current_tokens": tokens + 1,
            "shuffled_tokens": tokens - 1,
        },
        source_shard,
    )
    source_index = tmp_path / "source-index.json"
    write_json(
        source_index,
        {
            "status": "PASS_PRTA_GEN_R40A_TOKEN_CACHE",
            "scope": "training",
            "labels_in_cache": False,
            "sentences_in_cache": False,
            "revealed_483_test_read": False,
            "gold_outcomes_read": False,
            "rows": 3,
            "patients": 3,
            "shards": [{"path": str(source_shard), "rows": 3}],
        },
    )
    config = tmp_path / "config.json"
    write_json(
        config,
        {
            "status": CONFIG_STATUS,
            "protocol_id": "test",
            "source": {
                "token_index": str(source_index),
                "expected_rows": 3,
            },
            "candidate_order": [
                {
                    "name": "regional_moments_v1",
                    "input_width": 36,
                }
            ],
        },
    )
    roster = tmp_path / "roster.json"
    write_json(
        roster,
        {
            "status": ROSTER_PASS,
            "discovery_outcomes_read": False,
            "qualification_outcomes_read": False,
            "revealed_483_test_read": False,
            "gold_outcomes_read": False,
        },
    )
    return config, roster


def test_candidate_feature_registry_is_fail_closed():
    tokens = torch.zeros(2, 64, 3)
    assert candidate_features(
        tokens, candidate_name="regional_moments_v1"
    ).shape == (2, 27)
    assert candidate_features(
        tokens, candidate_name="regional_cosine4_v1"
    ).shape == (2, 36)
    with pytest.raises(ValueError, match="unregistered"):
        candidate_features(tokens, candidate_name="other")


def test_feature_cache_contains_no_labels_or_sentences(tmp_path):
    config, roster = write_fixture(tmp_path)
    result = build_feature_cache(
        config_path=config,
        roster_path=roster,
        candidate_name="regional_moments_v1",
        output_root=tmp_path / "features",
        device_name="cpu",
    )

    assert result["status"] == FEATURE_STATUS
    assert result["rows"] == 3
    assert result["labels_in_cache"] is False
    shard = torch.load(
        result["shards"][0]["path"], map_location="cpu", weights_only=True
    )
    assert shard["true_pair_features"].shape == (3, 36)
    assert "targets" not in shard and "evidence" not in shard
