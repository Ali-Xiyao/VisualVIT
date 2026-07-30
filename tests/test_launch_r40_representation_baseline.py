from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "launch_r40_representation_baseline.ps1"
)


def test_representation_launcher_freezes_surface():
    text = SCRIPT.read_text(encoding="utf-8")
    assert '"B0_frozen_a0", "B2_siamese_signed_abs"' in text
    assert "[ValidateSet(17, 29, 43)]" in text
    assert '"--epochs", "100"' in text
    assert '"--batch-size", "16"' in text
    assert '"--learning-rate", "0.01"' in text
    assert "$Result.revealed_483_test_read -eq $false" in text
    assert "$Result.gold_outcomes_read -eq $false" in text
    assert "$Result.checkpoint_hashes_recomputed -eq $false" in text


def test_representation_launcher_is_duplicate_safe():
    text = SCRIPT.read_text(encoding="utf-8")
    assert "Get-CimInstance Win32_Process" in text
    assert "Duplicate R40 $Baseline Seed $Seed process detected" in text
    assert "representation baseline path must be fresh" in text
