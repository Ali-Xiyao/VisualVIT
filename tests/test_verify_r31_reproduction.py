from __future__ import annotations

from scripts import verify_r31_reproduction as verifier


def test_final_report_keeps_human_gold_boundary() -> None:
    result = {
        "status": "PASS_R31_SCIENTIFIC_GO_REPRODUCED",
        "effect": {
            "consensus_macro_f1": 0.51,
            "uniform_macro_f1": 0.47,
            "delta_pp": 4.0,
            "ci_lower_pp": 1.0,
            "ci_upper_pp": 7.0,
            "directions": {"17": 0.03, "29": 0.04, "43": 0.05},
        },
    }
    report = verifier.render(result)
    assert "Final scientific gate: GO" in report
    assert "does not reverse the human-gold R26 `STOP_C1`" in report
