from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "launch_r40_component_seed.ps1"
)


def test_launcher_freezes_variants_seeds_and_firewalls():
    text = SCRIPT.read_text(encoding="utf-8")
    assert '"A2", "A3", "A4", "A5", "A6_no_state", "A6"' in text
    assert "[ValidateSet(17, 29, 43)]" in text
    assert '[ValidateSet("cuda:0", "cuda:1")]' in text
    assert '"--r40-component"' in text
    assert '"--epochs", "3"' in text
    assert '"--batch-size", "2"' in text
    assert '"--learning-rate", "0.0001"' in text
    assert '"--adapter-rank", "32"' in text
    assert "$Result.revealed_483_test_read -eq $false" in text
    assert "$Result.gold_outcomes_read -eq $false" in text
    assert "$Result.checkpoint_hashes_recomputed -eq $false" in text


def test_launcher_is_duplicate_safe_and_requires_fresh_outputs():
    text = SCRIPT.read_text(encoding="utf-8")
    assert "Get-CimInstance Win32_Process" in text
    assert "Duplicate R40 $Variant Seed $Seed process detected" in text
    assert "R40 component output must be fresh" in text
    assert "R40 component status must be fresh" in text
