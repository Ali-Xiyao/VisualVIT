import json

from scripts.build_prta_gen_r40a2_roster import (
    CONFIG_STATUS,
    ROSTER_PASS_V2,
    build_roster,
)


def write_json(path, payload):
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_r40a2_preserves_qualification_and_excludes_observed_discovery(
    tmp_path,
):
    selection = tmp_path / "selection.json"
    write_json(
        selection,
        {
            "status": "STOP_PRTA_GEN_R40A1_DISCOVERY",
            "selected_candidate": None,
            "qualification_unlocked": False,
            "qualification_outcomes_read": False,
            "revealed_483_test_read": False,
            "gold_outcomes_read": False,
        },
    )
    parent = tmp_path / "parent.json"
    write_json(
        parent,
        {
            "status": "PASS_PRTA_GEN_R40A1_ROSTER_SUPPORT",
            "patient_sets_disjoint": True,
            "qualification_outcomes_read": False,
            "revealed_483_test_read": False,
            "gold_outcomes_read": False,
            "partitions": {
                "qualification": {"patient_ids": ["q0", "q1"]},
                "discovery": {"patient_ids": ["d0", "d1"]},
                "fit": {"patient_ids": ["f0", "f1", "f2", "f3"]},
            },
        },
    )
    targets = tmp_path / "targets.jsonl"
    patient_ids = ["q0", "q1", "d0", "d1", "f0", "f1", "f2", "f3"]
    labels = [
        "Stable",
        "Improved",
        "Worse",
        "New",
        "Resolved",
        "Stable",
        "Improved",
        "Worse",
    ]
    targets.write_text(
        "".join(
            json.dumps(
                {
                    "patient_id": patient_id,
                    "example_id": f"e{index}",
                    "progression": label,
                }
            )
            + "\n"
            for index, (patient_id, label) in enumerate(
                zip(patient_ids, labels, strict=True)
            )
        ),
        encoding="utf-8",
    )
    config = tmp_path / "config.json"
    write_json(
        config,
        {
            "status": CONFIG_STATUS,
            "protocol_id": "test",
            "closed_predecessor": {
                "selection": str(selection),
                "required_status": "STOP_PRTA_GEN_R40A1_DISCOVERY",
            },
            "source": {"target_rows": str(targets), "expected_rows": 8},
            "patient_partitions": {
                "parent_roster": str(parent),
                "namespace": "test-r40a2",
                "preserve_parent_qualification_patients": 2,
                "exclude_observed_parent_discovery_patients": 2,
                "discovery_patients": 1,
                "fit_patients": 3,
                "assignment": "test",
                "support_minimums": {
                    "fit_rows_per_progression_class": 0,
                    "discovery_rows_per_progression_class": 0,
                    "qualification_rows_per_progression_class": 0,
                },
            },
        },
    )

    result = build_roster(config)

    assert result["status"] == ROSTER_PASS_V2
    assert result["qualification_matches_parent"] is True
    assert result["partitions"]["qualification"]["patient_ids"] == ["q0", "q1"]
    assert set(result["excluded_parent_discovery"]["patient_ids"]) == {
        "d0",
        "d1",
    }
    assert not (
        set(result["excluded_parent_discovery"]["patient_ids"])
        & {
            patient
            for payload in result["partitions"].values()
            for patient in payload["patient_ids"]
        }
    )
