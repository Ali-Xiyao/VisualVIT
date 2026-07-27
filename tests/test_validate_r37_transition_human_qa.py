from scripts.validate_r37_transition_human_qa import (
    LABELS,
    REQUIRED_COLUMNS,
    validate_review,
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
    return validate_review(
        rows,
        REQUIRED_COLUMNS,
        reviewer_name="reviewer-1",
        reviewer_role="radiologist",
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
        reviewer_name="",
        reviewer_role="",
        review_date="not-a-date",
        independent_review_confirmed=False,
    )
    assert result["formal_training_unlocked"] is False
    assert len(result["errors"]) == 4
