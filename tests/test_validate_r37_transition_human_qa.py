from pathlib import Path

from scripts.validate_r37_transition_human_qa import (
    LABELS,
    PENDING_AUDIT_STATUS,
    REQUIRED_COLUMNS,
    UNLOCKED_AUDIT_STATUS,
    apply_human_qa_unlock,
    validate_review,
    validate_transition_audit,
)


def _rows():
    return [
        {
            "case_id": f"{label}-{index}",
            "label": label,
            "human_direction_correct": "TRUE",
            "human_error_category": "",
            "human_notes": "",
        }
        for label in LABELS
        for index in range(40)
    ]


def _validate(rows):
    source_rows = _rows()
    return validate_review(
        rows,
        REQUIRED_COLUMNS,
        source_rows=source_rows,
        source_columns=REQUIRED_COLUMNS,
        reviewer_name="reviewer-1",
        reviewer_role="radiologist",
        reviewer_experience="5 years chest imaging",
        review_date="2026-07-27",
        independent_review_confirmed=True,
    )


def test_complete_balanced_review_passes():
    result = _validate(_rows())
    assert result["status"] == "PASS_R37_TRANSITION_HUMAN_QA"
    assert result["formal_training_unlocked"] is True
    assert result["overall_accuracy"] == 1.0
    assert set(result["per_label_accuracy"].values()) == {1.0}


def test_incomplete_or_unbalanced_review_stops():
    result = _validate(_rows()[:-1])
    assert result["status"] == "STOP_R37_TRANSITION_HUMAN_QA"
    assert result["formal_training_unlocked"] is False
    assert result["errors"]


def test_false_rows_require_category_and_other_note():
    rows = _rows()
    rows[0]["human_direction_correct"] = "FALSE"
    result = _validate(rows)
    assert result["formal_training_unlocked"] is False
    assert any("error category" in error for error in result["errors"])

    rows[0]["human_error_category"] = "OTHER"
    result = _validate(rows)
    assert result["formal_training_unlocked"] is False
    assert any("OTHER requires" in error for error in result["errors"])


def test_per_class_threshold_is_fail_closed():
    rows = _rows()
    for row in rows[:7]:
        row["human_direction_correct"] = "FALSE"
        row["human_error_category"] = "INSUFFICIENT_EVIDENCE"
    result = _validate(rows)
    assert result["errors"] == []
    assert result["overall_accuracy"] >= 0.90
    assert result["per_label_accuracy"]["Stable"] == 0.825
    assert result["thresholds_pass"] is False
    assert result["formal_training_unlocked"] is False


def test_attestation_is_required():
    result = validate_review(
        _rows(),
        REQUIRED_COLUMNS,
        source_rows=_rows(),
        source_columns=REQUIRED_COLUMNS,
        reviewer_name="",
        reviewer_role="",
        reviewer_experience="",
        review_date="not-a-date",
        independent_review_confirmed=False,
    )
    assert result["formal_training_unlocked"] is False
    assert len(result["errors"]) == 4
    assert result["attestation"]["reviewer_experience"] == "not provided"


def test_non_qa_source_drift_stops():
    source_rows = _rows()
    reviewed_rows = _rows()
    reviewed_rows[0]["label"] = "Worse"
    result = validate_review(
        reviewed_rows,
        REQUIRED_COLUMNS,
        source_rows=source_rows,
        source_columns=REQUIRED_COLUMNS,
        reviewer_name="reviewer-1",
        reviewer_role="radiologist",
        reviewer_experience="5 years chest imaging",
        review_date="2026-07-27",
        independent_review_confirmed=True,
    )
    assert result["formal_training_unlocked"] is False
    assert result["source_integrity"]["non_qa_fields_unchanged"] is False
    assert any("non-QA fields" in error for error in result["errors"])


def _transition_audit():
    return {
        "schema": "visualvit.r37.report-transitions.v1",
        "ruleset_version": "r37-report-transition-v4.1",
        "status": PENDING_AUDIT_STATUS,
        "formal_training_unlocked": False,
        "protected_outcomes_read": False,
    }


def test_transition_audit_unlock_is_explicit_and_preserves_firewall():
    result = _validate(_rows())
    audit = _transition_audit()
    assert validate_transition_audit(audit) == []
    unlocked = apply_human_qa_unlock(
        audit,
        result,
        validation_path=Path("review.json"),
    )
    assert audit["formal_training_unlocked"] is False
    assert unlocked["status"] == UNLOCKED_AUDIT_STATUS
    assert unlocked["formal_training_unlocked"] is True
    assert unlocked["protected_outcomes_read"] is False
    assert unlocked["human_qa_overall_accuracy"] == 1.0


def test_transition_audit_with_dirty_firewall_stops():
    audit = _transition_audit()
    audit["protected_outcomes_read"] = True
    errors = validate_transition_audit(audit)
    assert any("firewall" in error for error in errors)


def test_transition_audit_rejects_status_unlock_inconsistency():
    audit = _transition_audit()
    audit["formal_training_unlocked"] = True
    errors = validate_transition_audit(audit)
    assert any("unexpectedly unlocked" in error for error in errors)
