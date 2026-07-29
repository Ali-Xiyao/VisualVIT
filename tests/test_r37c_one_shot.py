from __future__ import annotations

from copy import deepcopy

import pytest

from scripts.aggregate_r37c_dev import aggregate_payload
from scripts.r37c_common import (
    merge_structure_and_labels,
    structural_projection,
)


def candidate() -> dict:
    return {
        "candidate_id": "r37-1-a6-three-seed-v1",
        "r37c_one_shot": {
            "bootstrap_replicates": 100,
            "bootstrap_seed": 37001,
            "minimum_gain_pp": 2.0,
            "inversion_consistency_minimum": 0.9,
            "state_retention_cosine_minimum": 0.99,
            "cmcp_role": "not_evaluated_no_frozen_dev_counterfactual_roster",
        },
        "protocol_deviation": {"id": "R37C-PD1"},
    }


def payload(seed: int, *, good: bool = True) -> dict:
    targets = [0, 1, 2, 3, 4] * 4
    true = list(targets) if good else [0] * len(targets)
    current = [0] * len(targets)
    a0 = [0] * len(targets)
    return {
        "schema": "visualvit.r37c.one-shot-seed-evaluation.v1",
        "status": "PASS_R37C_ONE_SHOT_SEED_EVALUATION",
        "candidate_id": "r37-1-a6-three-seed-v1",
        "seed": seed,
        "record_ids": [f"r{index}" for index in range(len(targets))],
        "patient_ids": [f"p{index // 2}" for index in range(len(targets))],
        "target_labels": targets,
        "predictions": {
            "a6_true": true,
            "a6_current_only": current,
            "a0_true": a0,
        },
        "qualification_diagnostics": {
            "inversion_consistency_rate": 1.0,
            "state_retention_cosine_mean": 0.995,
        },
        "protected_outcomes_read": True,
        "sealed_483_test_read": False,
        "gold_outcomes_read": False,
        "source_hashes_recomputed": False,
        "per_shard_hashes_computed": False,
        "checkpoint_hashes_recomputed": False,
    }


def test_structural_projection_omits_protected_progression() -> None:
    row = {
        "record_id": "r1",
        "patient_id": "p1",
        "subject_id": "s1",
        "partition": "dev",
        "prior_study_id": "ps",
        "prior_dicom_id": "pd",
        "prior_path": "prior.jpg",
        "prior_view": "PA",
        "current_study_id": "cs",
        "current_dicom_id": "cd",
        "current_path": "current.jpg",
        "current_view": "AP",
        "finding_token": "edema",
        "finding": "Edema",
        "anatomy": "chest",
        "progression": "Worse",
    }
    projected = structural_projection([row], partition="dev")
    assert projected[0]["record_id"] == "r1"
    assert "progression" not in projected[0]


def test_structure_label_merge_is_exact_and_fail_closed() -> None:
    structure = [{"record_id": "r1", "patient_id": "p1"}]
    merged = merge_structure_and_labels(
        structure, [{"record_id": "r1", "progression": "Stable"}]
    )
    assert merged[0]["label"] == "Stable"
    with pytest.raises(ValueError, match="alignment"):
        merge_structure_and_labels(
            structure, [{"record_id": "r2", "progression": "Stable"}]
        )


def test_r37c_aggregate_go_and_scientific_stop() -> None:
    good = [payload(seed) for seed in (17, 29, 43)]
    result = aggregate_payload(good, candidate())
    assert result["status"] == "GO_R37C_ONE_SHOT_DEV"
    assert result["r38_unlocked"] is True

    bad = deepcopy(good)
    bad[1]["qualification_diagnostics"][
        "state_retention_cosine_mean"
    ] = 0.98
    result = aggregate_payload(bad, candidate())
    assert result["status"] == "STOP_R37C_ONE_SHOT_DEV"
    assert result["stop_chain"] is True


def test_r37c_aggregate_rejects_row_order_drift() -> None:
    rows = [payload(seed) for seed in (17, 29, 43)]
    rows[2]["record_ids"] = list(reversed(rows[2]["record_ids"]))
    with pytest.raises(ValueError, match="row order"):
        aggregate_payload(rows, candidate())
