import json

import pytest

from scripts.audit_prta_gen_targets import (
    PASS_STATUS,
    audit_targets,
)


LABELS = ("Stable", "Improved", "Worse", "New", "Resolved")


def _pair(patient, label, sentence):
    return {
        "pair_id": f"pair-{patient}-{label}",
        "patient_id": patient,
        "prior_dicom_id": f"prior-{patient}",
        "current_dicom_id": f"current-{patient}",
        "transition_supervision": [
            {
                "finding": "Pneumothorax",
                "label": label,
                "sentence": sentence,
                "section": "IMPRESSION",
                "ruleset_version": "r37-report-transition-v4.1",
            }
        ],
    }


def _write_jsonl(path, rows):
    path.write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )


def fixture(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    training = []
    development = []
    sentences = {
        "Stable": "The left apical pneumothorax is unchanged.",
        "Improved": "The right apical pneumothorax has mildly improved.",
        "Worse": "The left apical pneumothorax has moderately worsened.",
        "New": "A new right apical pneumothorax is present.",
        "Resolved": "The left apical pneumothorax has resolved.",
    }
    for index, label in enumerate(LABELS):
        training.append(_pair(f"train-{index}", label, sentences[label]))
        development.append(_pair(f"dev-{index}", label, sentences[label]))
    _write_jsonl(source / "r37_pretrain_manifest.jsonl", training)
    _write_jsonl(
        source / "r37_internal_calibration_manifest.jsonl", development
    )
    (source / "r37_transition_audit.json").write_text(
        json.dumps(
            {
                "status": "READY_R40_OUTCOME_INDEPENDENT_ROSTER",
                "protocol_id": "r40-component-baseline-v1",
                "training_patients": 5,
                "development_patients": 5,
                "training_examples": 5,
                "development_examples": 5,
                "patient_disjoint": True,
                "previous_r37_1_validation_excluded": True,
                "protected_300_dev_read": False,
                "revealed_483_test_read": False,
                "gold_outcomes_read": False,
                "source_hashes_recomputed": False,
                "per_shard_hashes_computed": False,
                "checkpoint_hashes_recomputed": False,
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "output"
    config = tmp_path / "config.json"
    config.write_text(
        json.dumps(
            {
                "status": "FROZEN_PRTA_GEN_R40_READINESS_V1",
                "protocol_id": "fixture",
                "lineage": {
                    "source_roster": str(source),
                    "required_roster_status": (
                        "READY_R40_OUTCOME_INDEPENDENT_ROSTER"
                    ),
                    "training_patients": 5,
                    "development_patients": 5,
                    "training_examples": 5,
                    "development_examples": 5,
                },
                "r40a_information_audit": {
                    "label_policy": {
                        "source": (
                            "literal current-report comparative sentence only"
                        ),
                        "infer_from_finding_name": False,
                        "llm_label_completion": False,
                        "evidence_may_be_generated_when_source_sentence_missing": False,
                        "minimum_training_rows_per_explicit_class": 1,
                        "minimum_development_rows_per_explicit_class": 1,
                        "minimum_tier_a_training_rows": 1,
                        "minimum_tier_a_development_rows": 1,
                        "unsupported_class_action": (
                            "mark_field_unavailable_without_resplitting"
                        ),
                    }
                },
                "runtime": {"target_audit": str(output)},
                "firewall": {
                    "revealed_483_test_may_select_any_setting": False,
                    "sealed_gold_or_external_may_be_read": False,
                    "r37_1_observed_validation_may_select_any_setting": False,
                    "source_hashes_recomputed": False,
                    "per_shard_hashes_computed": False,
                    "checkpoint_hashes_recomputed": False,
                    "old_r40_component_queue_resumed": False,
                },
            }
        ),
        encoding="utf-8",
    )
    return config, source, output


def test_target_audit_is_patient_disjoint_and_keeps_generation_locked(tmp_path):
    config, _, output = fixture(tmp_path)

    result = audit_targets(config_path=config)

    assert result["status"] == PASS_STATUS
    assert result["patient_disjoint"]
    assert result["progression_probe_available"]
    assert result["field_support"]["laterality"]["probe_available"]
    assert result["field_support"]["anatomy"]["probe_available"] is False
    assert not any(result["field_generation_unlocked"].values())
    assert result["revealed_483_test_read"] is False
    assert (output / "training_targets.jsonl").is_file()


def test_target_audit_rejects_protected_roster_drift(tmp_path):
    config, source, _ = fixture(tmp_path)
    audit_path = source / "r37_transition_audit.json"
    audit = json.loads(audit_path.read_text())
    audit["gold_outcomes_read"] = True
    audit_path.write_text(json.dumps(audit))

    with pytest.raises(PermissionError, match="roster/firewall drift"):
        audit_targets(config_path=config)


def test_target_audit_requires_fresh_output(tmp_path):
    config, _, output = fixture(tmp_path)
    output.mkdir()

    with pytest.raises(FileExistsError, match="must be fresh"):
        audit_targets(config_path=config)
