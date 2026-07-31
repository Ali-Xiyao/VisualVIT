from __future__ import annotations

from scripts.cache_prta_gen_r45_cdeb_tokens import receipt_summary


def test_r45_cache_summary_hides_shard_paths() -> None:
    summary = receipt_summary(
        {
            "status": "PASS",
            "shards": [
                {"path": "secret-a", "rows": 3, "bytes": 10},
                {"path": "secret-b", "rows": 2, "bytes": 11},
            ],
        }
    )
    assert summary["shards"] == {"count": 2, "rows": 5, "bytes": 21}
    assert "secret" not in str(summary)
