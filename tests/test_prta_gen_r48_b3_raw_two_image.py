from __future__ import annotations

import pytest

from scripts.run_prta_gen_r48_b3_raw_two_image import (
    _metrics,
    receipt_summary,
    select_shard,
)


def test_select_shard_is_disjoint_and_complete() -> None:
    rows = [{"value": index} for index in range(7)]
    left = select_shard(rows, 0, 2)
    right = select_shard(rows, 1, 2)
    indices = sorted(index for index, _ in left + right)
    assert indices == list(range(7))
    assert not ({index for index, _ in left} & {index for index, _ in right})


def test_select_shard_rejects_invalid_index() -> None:
    with pytest.raises(ValueError):
        select_shard([], 2, 2)


def test_metrics_counts_invalid_prediction() -> None:
    metrics = _metrics([0, 1, 2, 3, 4], [0, 1, -1, 3, 4])
    assert metrics["invalid_or_wrong_finding_predictions"] == 1
    assert metrics["row_count"] == 5


def test_receipt_summary_preserves_preflight_row_count() -> None:
    assert receipt_summary({"rows": 500})["rows"] == 500
