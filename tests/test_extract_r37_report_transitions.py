from scripts.extract_r37_report_transitions import (
    consistency_verdict,
    extract_report_annotations,
    extract_sentence_annotations,
    report_sections,
)


def test_extracts_finding_scoped_directions():
    report = """
FINDINGS: New mild pulmonary edema with persistent small bilateral pleural
effusions.
IMPRESSION: New mild pulmonary edema. Pleural effusions are unchanged.
"""
    rows = extract_report_annotations(report)
    observed = {(row["finding"], row["label"]) for row in rows}
    assert ("Edema", "New") in observed
    assert ("Pleural Effusion", "Stable") in observed


def test_rejects_no_new_shortcut():
    rows = extract_sentence_annotations(
        "There is no new focal opacity to suggest pneumonia.",
        section="FINDINGS",
    )
    assert not any(row["label"] == "New" for row in rows)


def test_impression_overrides_conflicting_findings():
    report = """
FINDINGS: Pulmonary edema is unchanged.
IMPRESSION: Pulmonary edema has improved.
"""
    rows = extract_report_annotations(report)
    assert [(row["finding"], row["label"]) for row in rows] == [
        ("Edema", "Improved")
    ]


def test_only_findings_and_impression_sections_are_used():
    text = """
INDICATION: Evaluate new pneumonia.
FINDINGS: No focal consolidation.
IMPRESSION: No acute cardiopulmonary process.
"""
    sections = report_sections(text)
    assert {name for name, _ in sections} == {"FINDINGS", "IMPRESSION"}
    assert extract_report_annotations(text) == []


def test_chexpert_consistency_rejects_opposite_binary_change():
    assert consistency_verdict("New", 0, 1) == "pass"
    assert consistency_verdict("New", 1, 0) == "reject"
    assert consistency_verdict("Resolved", 1, 0) == "pass"
    assert consistency_verdict("Improved", 0, 1) == "reject"
    assert consistency_verdict("Worse", 1, 0) == "reject"
    assert consistency_verdict("Stable", 1, 1) == "pass"


def test_scope_rules_reject_neighbor_finding_and_non_assertions():
    assert extract_report_annotations(
        "FINDINGS: Decreased lung volumes but no consolidation."
    ) == []
    assert extract_report_annotations(
        "IMPRESSION: Severe bilateral pneumonia has not improved since prior."
    ) == []
    assert extract_report_annotations(
        "IMPRESSION: Evaluate for worsening pulmonary edema."
    ) == []
    assert extract_report_annotations(
        "FINDINGS: New moderate cardiomegaly without pulmonary edema."
    ) == [
        {
            "finding": "Cardiomegaly",
            "label": "New",
            "section": "FINDINGS",
            "cue": "new",
            "sentence": "New moderate cardiomegaly",
        }
    ]


def test_no_new_and_no_interval_development_are_rejected():
    assert extract_report_annotations(
        "IMPRESSION: No acute change or new consolidation."
    ) == []
    assert extract_report_annotations(
        "FINDINGS: No interval development of pulmonary edema."
    ) == []


def test_partial_resolution_is_improved_not_resolved():
    rows = extract_report_annotations(
        "IMPRESSION: Pulmonary edema has almost resolved."
    )
    assert [(row["finding"], row["label"]) for row in rows] == [
        ("Edema", "Improved")
    ]


def test_missing_space_sentence_boundary_prevents_cue_transfer():
    report = (
        "FINDINGS: No pneumothorax.There are unchanged degenerative changes "
        "of the spine."
    )
    assert extract_report_annotations(report) == []


def test_uncertainty_and_ambiguous_alternatives_are_rejected():
    assert extract_report_annotations(
        "IMPRESSION: There may be worsening opacity at the right base."
    ) == []
    assert extract_report_annotations(
        "IMPRESSION: Potential new consolidation at the right base."
    ) == []
    assert extract_report_annotations(
        "FINDINGS: Stable or increasing layering pleural effusion."
    ) == []
    assert extract_report_annotations(
        "IMPRESSION: A new opacity could represent developing pneumonia."
    ) == []


def test_and_or_boundaries_prevent_neighbor_cue_transfer():
    rows = extract_report_annotations(
        "IMPRESSION: Decreasing pleural effusion and bibasilar atelectasis."
    )
    assert [(row["finding"], row["label"]) for row in rows] == [
        ("Pleural Effusion", "Improved")
    ]
    assert extract_report_annotations(
        "IMPRESSION: The effusion is smaller or resolved."
    ) == []


def test_indented_history_and_technique_artifact_are_excluded():
    report = """
 FINAL REPORT
 HISTORY: Recent pneumonia, new weakness.
 TECHNIQUE: Single portable view.
 FINDINGS: Portable technique creating increased opacity in both lungs.
 IMPRESSION: No acute disease.
"""
    assert extract_report_annotations(report) == []


def test_negated_newly_and_no_new_finding_are_excluded():
    assert extract_report_annotations(
        "FINDINGS: No opacities have newly occurred."
    ) == []
    assert extract_report_annotations(
        "FINDINGS: No new focal consolidation, pleural effusion or "
        "pneumothorax is seen."
    ) == []


def test_suggested_new_source_is_not_a_new_consolidation_label():
    assert extract_report_annotations(
        "FINDINGS: Areas of consolidation are identified to suggest a new "
        "source of infection."
    ) == []


def test_soft_wrap_does_not_separate_no_from_new():
    report = """
FINDINGS: Fibrotic changes are noted. No
 new focal consolidation, pleural effusion or pneumothorax is seen.
"""
    assert extract_report_annotations(report) == []


def test_projectional_increased_opacity_with_uncertainty_is_not_temporal():
    report = """
FINDINGS: Subtle right infrahilar opacity with corresponding increased opacity
 projecting over the heart on lateral view may represent early pneumonia.
"""
    assert extract_report_annotations(report) == []
