from __future__ import annotations

from scripts import verify_r28_tier_mvp as verifier


def test_frozen_processes_pass_r28_reproduction_verifier() -> None:
    result = verifier.verify(
        verifier.PROCESS_A_DEFAULT, verifier.PROCESS_B_DEFAULT
    )
    assert result["status"] == "PASS_R28_TIER_FRESH_PROCESS_REPRODUCTION"
    assert result["qualified"] is True
    assert result["failed"] == []
    assert result["engineering_reproduced"] is True
    assert result["scientific_go"] is False
