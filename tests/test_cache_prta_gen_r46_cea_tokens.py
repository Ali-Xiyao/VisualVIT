from __future__ import annotations

from scripts.cache_prta_gen_r46_cea_tokens import receipt_summary


def test_r46_cache_summary_hides_shard_paths() -> None:
    summary = receipt_summary(
        {
            "status": "PASS",
            "shards": [
                {"path": "secret-a", "rows": 128, "bytes": 10},
                {"path": "secret-b", "rows": 122, "bytes": 20},
            ],
        }
    )
    assert summary["shards"] == {"count": 2, "rows": 250, "bytes": 30}
    assert "secret" not in str(summary)
