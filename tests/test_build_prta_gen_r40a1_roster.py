import hashlib
import json

import pytest

from scripts.build_prta_gen_r40a1_roster import (
    CONFIG_STATUS,
    ROSTER_PASS,
    build_roster,
    patient_order,
)


def write_json(path, payload):
    path.write_text(json.dumps(payload), encoding="utf-8")


def write_fixture(tmp_path, *, predecessor_status=None):
    predecessor = tmp_path / "aggregate.json"
    write_json(
        predecessor,
        {
            "status": predecessor_status
            or "STOP_PRTA_GEN_R40A_FIELD_INFORMATION",
            "field": "progression",
            "field_generation_unlocked": False,
            "revealed_483_test_read": False,
            "gold_outcomes_read": False,
        },
    )
    case_study = tmp_path / "case.json"
    write_json(
        case_study,
        {
            "status": "DESCRIPTIVE_PRTA_GEN_R40A_FAILURE_CASE_STUDY",
            "observed_development_reuse_for_selection_allowed": False,
            "closed_r40a_result_unchanged": True,
        },
    )
    token_index = tmp_path / "index.json"
    write_json(
        token_index,
        {
            "status": "PASS_PRTA_GEN_R40A_TOKEN_CACHE",
            "scope": "training",
            "smoke_rows": 0,
            "labels_in_cache": False,
            "sentences_in_cache": False,
            "protected_300_dev_read": False,
            "revealed_483_test_read": False,
            "gold_outcomes_read": False,
            "rows": 10,
            "patients": 10,
        },
    )
    targets = tmp_path / "targets.jsonl"
    labels = ["Stable", "Improved", "Worse", "New", "Resolved"] * 2
    targets.write_text(
        "".join(
            json.dumps(
                {
                    "patient_id": f"p{index}",
                    "example_id": f"e{index}",
                    "progression": label,
                }
            )
            + "\n"
            for index, label in enumerate(labels)
        ),
        encoding="utf-8",
    )
    output = tmp_path / "roster.json"
    config = tmp_path / "config.json"
    write_json(
        config,
        {
            "status": CONFIG_STATUS,
            "protocol_id": "test",
            "closed_predecessor": {"aggregate": str(predecessor)},
            "case_study": {"path": str(case_study)},
            "source": {
                "token_index": str(token_index),
                "target_rows": str(targets),
                "expected_rows": 10,
                "expected_patients": 10,
            },
            "patient_partitions": {
                "namespace": "test-split",
                "qualification_patients": 2,
                "discovery_patients": 2,
                "fit_patients": 6,
                "assignment": "test",
                "roster_output": str(output),
                "support_minimums": {
                    "fit_rows_per_progression_class": 0,
                    "discovery_rows_per_progression_class": 0,
                    "qualification_rows_per_progression_class": 0,
                },
            },
        },
    )
    return config


def test_patient_order_is_hash_deterministic():
    observed = patient_order({"p1", "p2", "p3"}, namespace="n")
    expected = sorted(
        ("p1", "p2", "p3"),
        key=lambda patient_id: (
            hashlib.sha256(f"n|{patient_id}".encode()).hexdigest(),
            patient_id,
        ),
    )
    assert observed == expected


def test_roster_is_disjoint_and_preserves_frozen_counts(tmp_path):
    result = build_roster(write_fixture(tmp_path))

    assert result["status"] == ROSTER_PASS
    assert result["patient_sets_disjoint"] is True
    assert result["partitions"]["fit"]["patients"] == 6
    assert result["partitions"]["discovery"]["patients"] == 2
    assert result["partitions"]["qualification"]["patients"] == 2
    all_patients = [
        patient
        for partition in result["partitions"].values()
        for patient in partition["patient_ids"]
    ]
    assert len(all_patients) == len(set(all_patients)) == 10


def test_roster_rejects_nonstop_predecessor(tmp_path):
    config = write_fixture(
        tmp_path,
        predecessor_status="GO_PRTA_GEN_R40A_FIELD_INFORMATION",
    )
    with pytest.raises(PermissionError, match="predecessor"):
        build_roster(config)
