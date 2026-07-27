from pathlib import Path

import pytest

from scripts.cache_r37_biovilt_pair_embeddings import (
    contiguous_part_bounds,
    pair_inventory,
)


def test_contiguous_part_bounds_cover_without_overlap():
    assert contiguous_part_bounds(11, 0, 2) == (0, 5)
    assert contiguous_part_bounds(11, 1, 2) == (5, 11)


def test_pair_inventory_preserves_partitions(tmp_path: Path):
    row = (
        '{"pair_id":"p1","prior_path":"a.jpg","current_path":"b.jpg"}\n'
    )
    (tmp_path / "r37_pretrain_manifest.jsonl").write_text(
        row, encoding="utf-8"
    )
    (tmp_path / "r37_internal_calibration_manifest.jsonl").write_text(
        row.replace("p1", "p2"), encoding="utf-8"
    )
    inventory = pair_inventory(tmp_path)
    assert [item["partition"] for item in inventory] == [
        "pretrain",
        "internal_calibration",
    ]


def test_pair_inventory_rejects_duplicate_ids(tmp_path: Path):
    row = (
        '{"pair_id":"p1","prior_path":"a.jpg","current_path":"b.jpg"}\n'
    )
    for name in (
        "r37_pretrain_manifest.jsonl",
        "r37_internal_calibration_manifest.jsonl",
    ):
        (tmp_path / name).write_text(row, encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate pair_id"):
        pair_inventory(tmp_path)
