import json
from pathlib import Path

import pytest

from scripts.build_prta_gen_r40c_roster import (
    build_roster,
    preflight,
    select_partition_rows,
)


CLASSES = ("Stable", "Improved", "Worse", "New", "Resolved")


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value) + "\n", encoding="utf-8")


def test_select_partition_rows_is_deterministic_and_disjoint():
    rows = [
        {
            "example_id": f"{label}-{index}",
            "patient_id": f"{label}-p{index}",
            "finding": "Edema",
            "progression": label,
        }
        for label in CLASSES
        for index in range(5)
    ]
    kwargs = {
        "fit_patients": {str(row["patient_id"]) for row in rows},
        "excluded_patients": set(),
        "namespace": "frozen",
        "class_order": list(reversed(CLASSES)),
        "partition_counts": {
            "train": {label: 1 for label in CLASSES},
            "development": {label: 1 for label in CLASSES},
        },
    }
    selected = select_partition_rows(rows, **kwargs)
    repeated = select_partition_rows(list(reversed(rows)), **kwargs)
    assert selected == repeated
    train_patients = {row["patient_id"] for row in selected["train"]}
    development_patients = {
        row["patient_id"] for row in selected["development"]
    }
    assert len(train_patients) == len(development_patients) == 5
    assert not train_patients & development_patients


def _authority_fixture(tmp_path: Path) -> Path:
    predecessor = tmp_path / "predecessor.json"
    upstream = tmp_path / "upstream.json"
    parent_roster = tmp_path / "parent_roster.json"
    token_index = tmp_path / "token_index.json"
    targets = tmp_path / "targets.jsonl"
    _write_json(
        predecessor,
        {
            "status": "PASS_PRTA_GEN_R40B4_STRUCTURED_HEAD_SMOKE",
            "qwen_free_generation_unlocked": False,
            "scientific_claim_allowed": False,
            "protected_300_dev_read": False,
            "revealed_483_test_read": False,
            "gold_outcomes_read": False,
        },
    )
    _write_json(
        upstream,
        {
            "status": "GO_PRTA_GEN_R40A2_QUALIFICATION",
            "candidate": "semantic_layout_means_v1",
            "progression_generation_unlocked": True,
            "laterality_generation_unlocked": False,
            "anatomy_generation_unlocked": False,
            "degree_generation_unlocked": False,
            "evidence_generation_unlocked": False,
            "protected_300_dev_read": False,
            "revealed_483_test_read": False,
            "gold_outcomes_read": False,
        },
    )
    excluded_patients = [f"excluded-{index}" for index in range(160)]
    available_rows = [
        {
            "example_id": f"{label}-{index}",
            "patient_id": f"{label}-p{index}",
            "finding": "Edema",
            "progression": label,
        }
        for label in CLASSES
        for index in range(3)
    ]
    fit_patients = excluded_patients + [
        str(row["patient_id"]) for row in available_rows
    ]
    _write_json(
        parent_roster,
        {
            "status": "PASS_PRTA_GEN_R40A2_ROSTER_SUPPORT",
            "patient_sets_disjoint": True,
            "partitions": {"fit": {"patient_ids": fit_patients}},
            "protected_300_dev_read": False,
            "revealed_483_test_read": False,
            "gold_outcomes_read": False,
        },
    )
    _write_json(
        token_index,
        {
            "status": "PASS_PRTA_GEN_R40A_TOKEN_CACHE",
            "scope": "training",
            "labels_in_cache": False,
            "sentences_in_cache": False,
            "protected_300_dev_read": False,
            "revealed_483_test_read": False,
            "gold_outcomes_read": False,
        },
    )
    cohort_specs = []
    for cohort_index in range(5):
        path = tmp_path / f"cohort_{cohort_index}.json"
        cohort_rows = [
            {
                "example_id": f"excluded-e-{cohort_index}-{offset}",
                "patient_id": excluded_patients[32 * cohort_index + offset],
            }
            for offset in range(32)
        ]
        status = (
            "PASS_PRTA_GEN_R40B_SMOKE_COHORT"
            if cohort_index == 0
            else f"PASS_PRTA_GEN_R40B{cohort_index}_SMOKE_COHORT"
        )
        _write_json(
            path,
            {
                "status": status,
                "row_count": 32,
                "patient_count": 32,
                "rows": cohort_rows,
                "scientific_claim_allowed": False,
                "protected_300_dev_read": False,
                "revealed_483_test_read": False,
                "gold_outcomes_read": False,
            },
        )
        cohort_specs.append({"path": str(path), "required_status": status})
    targets.write_text(
        "".join(json.dumps(row) + "\n" for row in available_rows),
        encoding="utf-8",
    )
    config = tmp_path / "config.json"
    _write_json(
        config,
        {
            "status": "FROZEN_PRTA_GEN_R40C_STRUCTURED_GENERALIZATION",
            "protocol_id": "test-r40c",
            "closed_predecessor": {
                "result": str(predecessor),
                "required_status": "PASS_PRTA_GEN_R40B4_STRUCTURED_HEAD_SMOKE",
            },
            "upstream": {
                "qualification_aggregate": str(upstream),
                "required_status": "GO_PRTA_GEN_R40A2_QUALIFICATION",
                "required_candidate": "semantic_layout_means_v1",
            },
            "source": {
                "roster": str(parent_roster),
                "required_roster_status": "PASS_PRTA_GEN_R40A2_ROSTER_SUPPORT",
                "partition": "fit",
                "targets": str(targets),
                "token_index": str(token_index),
                "required_token_status": "PASS_PRTA_GEN_R40A_TOKEN_CACHE",
                "exclude_cohorts": cohort_specs,
                "expected_excluded_patient_count": 160,
            },
            "roster": {
                "namespace": "test-r40c",
                "assignment": "stable",
                "class_order": list(reversed(CLASSES)),
                "train_patients": 5,
                "development_patients": 5,
                "train_class_counts": {label: 1 for label in CLASSES},
                "development_class_counts": {
                    label: 1 for label in CLASSES
                },
            },
            "result_statuses": {
                "roster_pass": "PASS_PRTA_GEN_R40C_ROSTER_SUPPORT"
            },
        },
    )
    return config


def test_preflight_selects_in_memory_without_writing_roster(tmp_path):
    config = _authority_fixture(tmp_path)
    result = preflight(config)
    assert result["status"] == "PASS_PRTA_GEN_R40C_PREFLIGHT"
    assert result["selected_counts_in_memory_only"] == {
        "train": 5,
        "development": 5,
    }
    assert result["real_roster_written"] is False
    assert result["gpu_training_started"] is False


def test_build_roster_is_balanced_patient_disjoint_and_excludes_history(
    tmp_path,
):
    config = _authority_fixture(tmp_path)
    output = tmp_path / "roster.json"
    result = build_roster(config, output)
    assert output.exists()
    assert result["status"] == "PASS_PRTA_GEN_R40C_ROSTER_SUPPORT"
    assert result["excluded_observed_patient_count"] == 160
    assert result["excluded_observed_patients_absent"] is True
    assert result["patient_sets_disjoint"] is True
    assert result["one_row_per_patient"] is True
    for partition in ("train", "development"):
        assert result["partitions"][partition]["row_count"] == 5
        assert result["partitions"][partition]["progression_class_counts"] == {
            label: 1 for label in sorted(CLASSES)
        }


def test_preflight_fails_closed_on_protected_parent_roster(tmp_path):
    config_path = _authority_fixture(tmp_path)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    roster_path = Path(config["source"]["roster"])
    roster = json.loads(roster_path.read_text(encoding="utf-8"))
    roster["protected_300_dev_read"] = True
    _write_json(roster_path, roster)
    with pytest.raises(PermissionError, match="parent roster"):
        preflight(config_path)
