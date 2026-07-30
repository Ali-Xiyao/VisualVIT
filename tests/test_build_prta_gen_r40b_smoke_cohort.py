import json
from pathlib import Path

import pytest

from scripts.build_prta_gen_r40b_smoke_cohort import (
    build_cohort,
    compact_target,
    select_rows,
)


def test_select_rows_is_deterministic_balanced_and_patient_unique():
    rows = [
        {
            "example_id": f"{progression}-{index}",
            "patient_id": f"p-{progression}-{index}",
            "finding": "Edema",
            "progression": progression,
        }
        for progression in ("Stable", "New")
        for index in range(5)
    ]
    selected = select_rows(
        rows,
        fit_patient_ids={row["patient_id"] for row in rows},
        namespace="frozen",
        class_counts={"Stable": 2, "New": 2},
    )
    repeated = select_rows(
        list(reversed(rows)),
        fit_patient_ids={row["patient_id"] for row in rows},
        namespace="frozen",
        class_counts={"Stable": 2, "New": 2},
    )
    assert selected == repeated
    assert len({row["patient_id"] for row in selected}) == 4
    assert sum(row["progression"] == "Stable" for row in selected) == 2
    assert sum(row["progression"] == "New" for row in selected) == 2


def test_compact_target_has_exact_two_key_schema():
    text = compact_target({"finding": "Edema", "progression": "Improved"})
    assert text == '{"finding":"Edema","progression":"Improved"}'
    assert list(json.loads(text)) == ["finding", "progression"]


def _write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value) + "\n", encoding="utf-8")


def test_build_cohort_fails_closed_without_qualification_go(tmp_path):
    upstream = tmp_path / "upstream.json"
    roster = tmp_path / "roster.json"
    token_index = tmp_path / "tokens.json"
    targets = tmp_path / "targets.jsonl"
    config = tmp_path / "config.json"
    _write(
        upstream,
        {
            "status": "STOP",
            "candidate": "semantic_layout_means_v1",
            "progression_generation_unlocked": False,
            "laterality_generation_unlocked": False,
            "anatomy_generation_unlocked": False,
            "degree_generation_unlocked": False,
            "evidence_generation_unlocked": False,
            "protected_300_dev_read": False,
            "revealed_483_test_read": False,
            "gold_outcomes_read": False,
        },
    )
    _write(
        roster,
        {
            "status": "PASS_PRTA_GEN_R40A2_ROSTER_SUPPORT",
            "protected_300_dev_read": False,
            "revealed_483_test_read": False,
            "gold_outcomes_read": False,
            "patient_sets_disjoint": True,
            "partitions": {"fit": {"patient_ids": ["p1"]}},
        },
    )
    _write(
        token_index,
        {
            "status": "PASS_PRTA_GEN_R40A_TOKEN_CACHE",
            "scope": "training",
            "labels_in_cache": False,
            "sentences_in_cache": False,
            "revealed_483_test_read": False,
            "gold_outcomes_read": False,
        },
    )
    targets.write_text(
        json.dumps(
            {
                "example_id": "e1",
                "patient_id": "p1",
                "finding": "Edema",
                "progression": "Stable",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    _write(
        config,
        {
            "status": "FROZEN_PRTA_GEN_R40B_OVERFIT_SMOKE",
            "protocol_id": "test",
            "upstream": {
                "qualification_aggregate": str(upstream),
                "required_status": "GO_PRTA_GEN_R40A2_QUALIFICATION",
                "required_candidate": "semantic_layout_means_v1",
            },
            "source": {
                "roster": str(roster),
                "required_roster_status": "PASS_PRTA_GEN_R40A2_ROSTER_SUPPORT",
                "token_index": str(token_index),
                "required_token_status": "PASS_PRTA_GEN_R40A_TOKEN_CACHE",
                "targets": str(targets),
                "partition": "fit",
                "namespace": "test",
                "rows": 1,
                "maximum_rows": 1,
                "progression_class_counts": {"Stable": 1},
            },
            "target": {"schema_keys_in_order": ["finding", "progression"]},
        },
    )
    with pytest.raises(PermissionError, match="qualification unlock"):
        build_cohort(config_path=config, output_path=tmp_path / "out.json")
