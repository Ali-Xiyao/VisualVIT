from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "launch_r37_1_a0_seed.ps1"
)


def test_a0_launcher_freezes_roster_hyperparameters_and_firewalls():
    text = SCRIPT.read_text(encoding="utf-8")
    assert "[ValidateSet(17, 29, 43)]" in text
    assert '"--r37-1"' in text
    assert '"--max-train-examples", "0"' in text
    assert '"--max-calibration-examples", "0"' in text
    assert '"--epochs", "100"' in text
    assert '"--batch-size", "16"' in text
    assert '"--learning-rate", "0.01"' in text
    assert "r37_1_transitions_v1" in text
    assert "protected_outcomes_read = $false" in text
    assert "source_hashes_recomputed = $false" in text
    assert "PASS_R37_1_A0_FORMAL_PROBE" in text


def test_a0_launcher_is_duplicate_safe_and_requires_fresh_outputs():
    text = SCRIPT.read_text(encoding="utf-8")
    assert "Duplicate R37.1 A0 seed process detected" in text
    assert "A0 seed output must be fresh" in text
    assert "A0 stdout log must be fresh" in text
    assert "A0 stderr log must be fresh" in text
