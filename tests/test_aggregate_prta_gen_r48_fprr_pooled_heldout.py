from __future__ import annotations

from scripts.aggregate_prta_gen_r48_fprr_pooled_heldout import aggregate


def test_pooled_aggregate_is_importable() -> None:
    assert callable(aggregate)
