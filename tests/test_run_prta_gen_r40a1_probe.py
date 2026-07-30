import json

import pytest
import torch

from scripts.build_prta_gen_r40a1_roster import CONFIG_STATUS, ROSTER_PASS
from scripts.cache_prta_gen_r40a1_features import FEATURE_STATUS
from scripts.run_prta_gen_r40a1_probe import (
    RESULT_STATUS,
    partition_indices,
    run_probe,
)


def write_json(path, payload):
    path.write_text(json.dumps(payload), encoding="utf-8")


def write_fixture(tmp_path):
    example_ids = [f"e{index}" for index in range(10)]
    patient_ids = [f"p{index}" for index in range(10)]
    findings = ["Edema" if index % 2 else "Atelectasis" for index in range(10)]
    labels = ["Stable", "New"] * 5
    feature_shard = tmp_path / "features.pt"
    base = torch.randn(10, 12, dtype=torch.float16)
    torch.save(
        {
            "example_ids": example_ids,
            "patient_ids": patient_ids,
            "findings": findings,
            "true_pair_features": base,
            "current_only_features": base + 0.1,
            "prior_shuffle_features": base - 0.1,
        },
        feature_shard,
    )
    feature_index = tmp_path / "feature-index.json"
    write_json(
        feature_index,
        {
            "status": FEATURE_STATUS,
            "candidate": "regional_moments_v1",
            "input_width": 12,
            "labels_in_cache": False,
            "sentences_in_cache": False,
            "discovery_outcomes_read": False,
            "qualification_outcomes_read": False,
            "revealed_483_test_read": False,
            "gold_outcomes_read": False,
            "rows": 10,
            "shards": [{"path": str(feature_shard), "rows": 10}],
        },
    )
    targets = tmp_path / "targets.jsonl"
    targets.write_text(
        "".join(
            json.dumps(
                {
                    "example_id": example_id,
                    "patient_id": patient_id,
                    "finding": finding,
                    "progression": label,
                }
            )
            + "\n"
            for example_id, patient_id, finding, label in zip(
                example_ids, patient_ids, findings, labels, strict=True
            )
        ),
        encoding="utf-8",
    )
    roster = tmp_path / "roster.json"
    write_json(
        roster,
        {
            "status": ROSTER_PASS,
            "patient_sets_disjoint": True,
            "discovery_outcomes_read": False,
            "qualification_outcomes_read": False,
            "revealed_483_test_read": False,
            "gold_outcomes_read": False,
            "partitions": {
                "fit": {
                    "patients": 6,
                    "rows": 6,
                    "patient_ids": patient_ids[:6],
                },
                "discovery": {
                    "patients": 2,
                    "rows": 2,
                    "patient_ids": patient_ids[6:8],
                },
                "qualification": {
                    "patients": 2,
                    "rows": 2,
                    "patient_ids": patient_ids[8:],
                },
            },
        },
    )
    config = tmp_path / "config.json"
    write_json(
        config,
        {
            "status": CONFIG_STATUS,
            "protocol_id": "test",
            "source": {"target_rows": str(targets)},
            "candidate_order": [
                {"name": "regional_moments_v1", "input_width": 12}
            ],
            "probe": {
                "classes": ["Stable", "New"],
                "seeds": [17, 29, 43],
                "epochs": 1,
                "batch_size": 2,
                "learning_rate": 0.001,
                "weight_decay": 0.0,
            },
        },
    )
    return config, roster, feature_index


def test_partition_indices_are_patient_disjoint():
    rows = [{"patient_id": f"p{index}"} for index in range(3)]
    roster = {
        "partitions": {
            "fit": {"patient_ids": ["p0"], "rows": 1},
            "discovery": {"patient_ids": ["p1"], "rows": 1},
            "qualification": {"patient_ids": ["p2"], "rows": 1},
        }
    }
    result = partition_indices(rows, roster)
    assert result["fit"].tolist() == [0]
    assert result["discovery"].tolist() == [1]
    assert result["qualification"].tolist() == [2]


def test_partition_indices_skip_registered_observed_parent_discovery():
    rows = [{"patient_id": "fit"}, {"patient_id": "old-discovery"}]
    roster = {
        "partitions": {
            "fit": {"patient_ids": ["fit"], "rows": 1},
            "discovery": {"patient_ids": [], "rows": 0},
            "qualification": {"patient_ids": [], "rows": 0},
        },
        "excluded_parent_discovery": {
            "patient_ids": ["old-discovery"]
        },
    }
    result = partition_indices(rows, roster)
    assert result["fit"].tolist() == [0]


def test_discovery_probe_runs_with_generation_locked(tmp_path):
    config, roster, feature_index = write_fixture(tmp_path)
    result = run_probe(
        config_path=config,
        roster_path=roster,
        feature_index_path=feature_index,
        candidate_name="regional_moments_v1",
        scope="discovery",
        seed=17,
        device_name="cpu",
    )

    assert result["status"] == RESULT_STATUS
    assert result["scope"] == "discovery"
    assert result["progression_generation_unlocked"] is False
    assert result["evaluation_rows"] == 2


def test_qualification_requires_selection_receipt(tmp_path):
    config, roster, feature_index = write_fixture(tmp_path)
    with pytest.raises(PermissionError, match="selection"):
        run_probe(
            config_path=config,
            roster_path=roster,
            feature_index_path=feature_index,
            candidate_name="regional_moments_v1",
            scope="qualification",
            seed=17,
            device_name="cpu",
        )
