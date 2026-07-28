import json

import pytest

import scripts.build_r37_1_fresh_holdout as builder


def write_source(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    rows = []
    for index in range(6):
        rows.append(
            {
                "pair_id": f"pair-{index}",
                "patient_id": f"patient-{index}",
                "partition": "pretrain",
                "prior_dicom_id": f"prior-{index}",
                "current_dicom_id": f"current-{index}",
                "current_view": "PA",
                "transition_supervision": [
                    {"finding": "Edema", "label": "Stable"}
                ],
            }
        )
    (source / "r37_pretrain_manifest.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )
    (source / "r37_internal_calibration_manifest.jsonl").write_text(
        json.dumps(
            {
                **rows[0],
                "pair_id": "old-calibration-pair",
                "patient_id": "old-calibration-patient",
                "partition": "internal_calibration",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (source / "r37_transition_audit.json").write_text(
        json.dumps(
            {
                "ruleset_version": "r37-report-transition-v4.1",
                "protected_outcomes_read": False,
                "chextemporal_silver_used": False,
            }
        ),
        encoding="utf-8",
    )
    return source


def test_build_holdout_is_patient_disjoint_and_deterministic(
    tmp_path, monkeypatch
):
    source = write_source(tmp_path)
    monkeypatch.setattr(builder, "SOURCE_ELIGIBLE_PATIENTS", 6)
    monkeypatch.setattr(builder, "VALIDATION_PATIENTS", 2)
    output = tmp_path / "output"

    result = builder.build_holdout(
        source_root=source,
        output_root=output,
    )

    assert result["status"] == "READY_R37_1_FRESH_HOLDOUT"
    assert result["training_patients"] == 4
    assert result["validation_patients"] == 2
    assert result["patient_disjoint"]
    assert result["old_calibration_excluded"]
    assert result["protected_outcomes_read"] is False
    roster = json.loads(
        (output / "r37_1_fresh_holdout_roster.json").read_text()
    )
    assert roster["split_seed"] == 37101
    assert len(roster["validation_patient_ids"]) == 2


def test_build_holdout_rejects_existing_output(tmp_path, monkeypatch):
    source = write_source(tmp_path)
    monkeypatch.setattr(builder, "SOURCE_ELIGIBLE_PATIENTS", 6)
    monkeypatch.setattr(builder, "VALIDATION_PATIENTS", 2)
    output = tmp_path / "output"
    output.mkdir()
    with pytest.raises(FileExistsError, match="must be fresh"):
        builder.build_holdout(
            source_root=source,
            output_root=output,
        )


def test_build_holdout_rejects_protected_source(tmp_path, monkeypatch):
    source = write_source(tmp_path)
    monkeypatch.setattr(builder, "SOURCE_ELIGIBLE_PATIENTS", 6)
    audit = json.loads(
        (source / "r37_transition_audit.json").read_text()
    )
    audit["protected_outcomes_read"] = True
    (source / "r37_transition_audit.json").write_text(json.dumps(audit))
    with pytest.raises(PermissionError, match="firewall"):
        builder.build_holdout(
            source_root=source,
            output_root=tmp_path / "output",
        )
