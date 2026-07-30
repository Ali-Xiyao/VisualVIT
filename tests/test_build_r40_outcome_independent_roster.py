import json

import pytest

from scripts.build_r40_outcome_independent_roster import (
    STATUS,
    build_roster,
    roster_order,
)
from visualvit.cmcp import stable_hash


LABELS = ("Stable", "Improved", "Worse", "New", "Resolved")


def write_fixture(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    rows = []
    matches = []
    for patient_index in range(10):
        supervision = []
        for label_index, label in enumerate(LABELS):
            supervision.append(
                {"finding": f"Finding-{label_index}", "label": label}
            )
            if label != "Stable":
                matches.append(
                    {
                        "target_example_id": (
                            stable_hash(
                                "r37-transition-example-v1",
                                f"pair-{patient_index}",
                                f"Finding-{label_index}",
                                label,
                            )
                        )
                    }
                )
        rows.append(
            {
                "pair_id": f"pair-{patient_index}",
                "patient_id": f"patient-{patient_index}",
                "partition": "pretrain",
                "prior_dicom_id": f"prior-{patient_index}",
                "current_dicom_id": f"current-{patient_index}",
                "current_view": "PA",
                "transition_supervision": supervision,
            }
        )
    (source / "r37_pretrain_manifest.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )
    (source / "r37_transition_audit.json").write_text(
        json.dumps(
            {
                "status": "READY_R37_1_FRESH_HOLDOUT",
                "ruleset_version": "r37-report-transition-v4.1",
                "patient_disjoint": True,
                "old_calibration_excluded": True,
                "one_shot_validation": True,
                "protected_outcomes_read": False,
                "sealed_test_read": False,
                "gold_outcomes_read": False,
                "source_hashes_recomputed": False,
                "per_shard_hashes_computed": False,
            }
        ),
        encoding="utf-8",
    )
    cmcp = tmp_path / "cmcp.json"
    cmcp.write_text(
        json.dumps(
            {
                "status": "PASS_R37A_CMCP_COVERAGE",
                "matches": matches,
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "output"
    config = tmp_path / "config.json"
    config.write_text(
        json.dumps(
            {
                "status": "FROZEN_R40_OUTCOME_INDEPENDENT_PROTOCOL",
                "protocol_id": "fixture",
                "roster": {
                    "source_root": str(source),
                    "source_status": "READY_R37_1_FRESH_HOLDOUT",
                    "source_training_patients": 10,
                    "development_patients": 2,
                    "selection_namespace": "fixture",
                    "selection_seed": 40701,
                    "selection_rule": "fixture deterministic split",
                    "output_root": str(output),
                    "minimum_train_examples_per_label": 1,
                    "minimum_development_examples_per_label": 1,
                },
                "shared_artifacts": {"cmcp_index": str(cmcp)},
            }
        ),
        encoding="utf-8",
    )
    return config, output


def test_roster_order_is_deterministic():
    assert roster_order("r40", 40701, "patient-1") == roster_order(
        "r40", 40701, "patient-1"
    )
    assert roster_order("r40", 40701, "patient-1") != roster_order(
        "r40", 40701, "patient-2"
    )


def test_build_roster_is_patient_disjoint_and_fail_closed(tmp_path):
    config, output = write_fixture(tmp_path)
    result = build_roster(config_path=config)

    assert result["status"] == STATUS
    assert result["training_patients"] == 8
    assert result["development_patients"] == 2
    assert result["patient_disjoint"]
    assert result["previous_r37_1_validation_excluded"]
    assert result["label_support_pass"]
    assert result["cmcp_coverage_pass"]
    assert result["revealed_483_test_read"] is False
    assert len(
        json.loads((output / "r40_roster.json").read_text())[
            "development_patient_ids"
        ]
    ) == 2


def test_build_roster_rejects_existing_output(tmp_path):
    config, output = write_fixture(tmp_path)
    output.mkdir()
    with pytest.raises(FileExistsError, match="must be fresh"):
        build_roster(config_path=config)


def test_build_roster_rejects_source_firewall_drift(tmp_path):
    config, _ = write_fixture(tmp_path)
    source_audit_path = (
        config.parent / "source" / "r37_transition_audit.json"
    )
    source_audit = json.loads(source_audit_path.read_text())
    source_audit["sealed_test_read"] = True
    source_audit_path.write_text(json.dumps(source_audit))
    with pytest.raises(PermissionError, match="firewall drift"):
        build_roster(config_path=config)


def test_build_roster_stops_without_resplitting_on_missing_cmcp(tmp_path):
    config, _ = write_fixture(tmp_path)
    payload = json.loads(config.read_text())
    cmcp_path = config.parent / "cmcp.json"
    assert str(cmcp_path) == payload["shared_artifacts"]["cmcp_index"]
    cmcp = json.loads(cmcp_path.read_text(encoding="utf-8"))
    cmcp["matches"].pop()
    cmcp_path.write_text(json.dumps(cmcp), encoding="utf-8")

    result = build_roster(config_path=config)

    assert result["status"] == "STOP_R40_ROSTER_SUPPORT"
    assert result["cmcp_coverage_pass"] is False
