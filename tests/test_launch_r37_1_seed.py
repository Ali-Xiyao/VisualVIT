from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "launch_r37_1_seed.ps1"
)


def test_launcher_freezes_three_seed_scope_and_firewalls():
    text = SCRIPT.read_text(encoding="utf-8")
    assert "[ValidateSet(17, 29, 43)]" in text
    assert '[ValidateSet("cuda:0", "cuda:1")]' in text
    assert '"--r37-1"' in text
    assert '"--max-train-examples", "0"' in text
    assert '"--max-calibration-examples", "0"' in text
    assert '"--epochs", "3"' in text
    assert '"--batch-size", "2"' in text
    assert '"--learning-rate", "0.0001"' in text
    assert '"--adapter-rank", "32"' in text
    assert "protected_outcomes_read = $false" in text
    assert "source_hashes_recomputed = $false" in text
    assert "PASS_R37_1_PRTA_FORMAL_TRAINING" in text
    assert "bootstrap" not in text.lower()
    assert "run_r37_a0" not in text


def test_launcher_is_duplicate_safe_and_requires_fresh_outputs():
    text = SCRIPT.read_text(encoding="utf-8")
    assert "Duplicate R37.1 seed process detected" in text
    assert "seed output must be fresh" in text
    assert "stdout log must be fresh" in text
    assert "stderr log must be fresh" in text
    assert "result_complete" in text
