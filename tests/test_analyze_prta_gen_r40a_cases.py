import json

import pytest
import torch

from scripts.analyze_prta_gen_r40a_cases import (
    build_case_study,
    prediction_category,
    token_region_rms,
)
from scripts.run_prta_gen_r40a_probe import RESULT_STATUS, TOKEN_STATUS


def write_fixture(tmp_path, *, protected=False):
    example_ids = ["e0", "e1", "e2", "e3"]
    patient_ids = ["p0", "p1", "p2", "p3"]
    targets = [0, 1, 0, 1]
    target_path = tmp_path / "targets.jsonl"
    target_path.write_text(
        "".join(
            json.dumps(
                {
                    "example_id": example_id,
                    "patient_id": patient_id,
                    "finding": "Edema" if index < 2 else "Atelectasis",
                    "progression": "Stable" if target == 0 else "New",
                    "quality_tier": "A" if index % 2 == 0 else "C",
                }
            )
            + "\n"
            for index, (example_id, patient_id, target) in enumerate(
                zip(example_ids, patient_ids, targets, strict=True)
            )
        ),
        encoding="utf-8",
    )
    result_paths = {}
    for seed in (17, 29, 43):
        payload = {
            "schema": "visualvit.prta-gen.r40a-probe-seed.v1",
            "status": RESULT_STATUS,
            "field": "progression",
            "classes": ["Stable", "New"],
            "seed": seed,
            "field_generation_unlocked": False,
            "protected_300_dev_read": protected,
            "revealed_483_test_read": False,
            "gold_outcomes_read": False,
            "old_r40_component_queue_resumed": False,
            "scientific_claim_allowed": False,
            "example_ids": example_ids,
            "patient_ids": patient_ids,
            "targets": targets,
            "predictions": {
                "true_pair": [0, 0, 0, 0],
                "prior_shuffle": [1, 1, 0, 0],
            },
        }
        path = tmp_path / f"seed-{seed}.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        result_paths[seed] = path
    shard_path = tmp_path / "tokens.pt"
    true_tokens = torch.ones(4, 64, 768, dtype=torch.float16)
    shuffled_tokens = torch.zeros(4, 64, 768, dtype=torch.float16)
    torch.save(
        {
            "example_ids": example_ids,
            "true_tokens": true_tokens,
            "shuffled_tokens": shuffled_tokens,
        },
        shard_path,
    )
    index_path = tmp_path / "index.json"
    index_path.write_text(
        json.dumps(
            {
                "status": TOKEN_STATUS,
                "smoke_rows": 0,
                "labels_in_cache": False,
                "sentences_in_cache": False,
                "protected_300_dev_read": False,
                "revealed_483_test_read": False,
                "gold_outcomes_read": False,
                "shards": [{"path": str(shard_path), "rows": 4}],
            }
        ),
        encoding="utf-8",
    )
    return result_paths, target_path, index_path


def test_prediction_category_covers_four_outcomes():
    assert prediction_category(0, 0, 1) == "true_sensitive"
    assert prediction_category(0, 1, 0) == "shuffle_favored"
    assert prediction_category(0, 0, 0) == "both_correct"
    assert prediction_category(0, 1, 1) == "both_wrong"


def test_token_region_rms_requires_exact64_and_summarizes_regions():
    true_tokens = torch.ones(2, 64, 768)
    shuffled_tokens = torch.zeros(2, 64, 768)
    result = token_region_rms(true_tokens, shuffled_tokens)

    assert result.shape == (2, 4)
    assert torch.allclose(result, torch.ones_like(result))
    with pytest.raises(ValueError, match="exact"):
        token_region_rms(true_tokens[:, :63], shuffled_tokens[:, :63])


def test_case_study_is_descriptive_and_anonymized(tmp_path):
    result_paths, target_path, index_path = write_fixture(tmp_path)
    result = build_case_study(
        result_paths=result_paths,
        target_path=target_path,
        token_index_path=index_path,
        per_pattern=2,
    )

    assert result["status"] == (
        "DESCRIPTIVE_PRTA_GEN_R40A_FAILURE_CASE_STUDY"
    )
    assert result["closed_r40a_result_unchanged"] is True
    assert result["observed_development_reuse_for_selection_allowed"] is False
    assert result["seed_summaries"][0]["category_counts"] == {
        "both_correct": 1,
        "both_wrong": 1,
        "shuffle_favored": 1,
        "true_sensitive": 1,
    }
    assert result["anonymized_cases"]
    assert all(
        "patient_id" not in case and "evidence" not in case
        for case in result["anonymized_cases"]
    )


def test_case_study_rejects_protected_result(tmp_path):
    result_paths, target_path, index_path = write_fixture(
        tmp_path, protected=True
    )
    with pytest.raises(PermissionError, match="protected_300"):
        build_case_study(
            result_paths=result_paths,
            target_path=target_path,
            token_index_path=index_path,
        )
