from __future__ import annotations

from scripts.cache_prta_gen_r47_ucc_tokens import receipt_summary


def test_r47_cache_summary_hides_shard_paths() -> None:
    summary = receipt_summary(
        {
            "shards": [
                {"path": "secret", "rows": 500, "bytes": 7},
            ]
        }
    )
    assert summary["shards"] == {"count": 1, "rows": 500, "bytes": 7}
    assert "secret" not in str(summary)
