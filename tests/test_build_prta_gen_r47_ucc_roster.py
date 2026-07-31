from __future__ import annotations

from scripts.build_prta_gen_r47_ucc_roster import receipt_summary


def test_r47_receipt_summary_hides_rows() -> None:
    summary = receipt_summary(
        {
            "status": "PASS",
            "partitions": {
                "development": {
                    "rows": [{"patient_id": "secret"}],
                    "row_count": 1,
                }
            },
        }
    )
    assert summary["partitions"]["development"] == {"row_count": 1}
    assert "secret" not in str(summary)
