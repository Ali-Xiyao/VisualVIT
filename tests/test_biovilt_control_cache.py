import json
from pathlib import Path

import torch

from scripts.merge_r37_biovilt_pair_cache_parts import merge_parts
from visualvit.biovilt import (
    BIOVILT_CONTROL_MODES,
    BioViLTControlCacheIndex,
)


def _write_part(root: Path, index: int, count: int, pair_id: str) -> None:
    directory = root / f"part_{index:02d}_of_{count:02d}"
    directory.mkdir(parents=True)
    embeddings = {
        mode: torch.full((1, 128), float(mode_index))
        for mode_index, mode in enumerate(BIOVILT_CONTROL_MODES)
    }
    torch.save(
        {
            "pair_ids": (pair_id,),
            "partitions": ("pretrain",),
            "embeddings": embeddings,
        },
        directory / "shard_00000.pt",
    )
    manifest = {
        "status": "PASS_R37_A1_CONTROL_CACHE",
        "part_index": index,
        "part_count": count,
        "part_start": index,
        "part_end": index + 1,
        "formal_inventory_count": count,
        "pair_count": 1,
        "controls": list(BIOVILT_CONTROL_MODES),
        "shards": [{"file": "shard_00000.pt", "count": 1}],
    }
    (directory / "r37_biovilt_pair_cache_manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )


def test_merge_and_random_access_control_cache(tmp_path: Path):
    _write_part(tmp_path, 0, 2, "p0")
    _write_part(tmp_path, 1, 2, "p1")
    merged = merge_parts(tmp_path, 2)
    (
        tmp_path / "r37_biovilt_pair_cache_manifest.json"
    ).write_text(json.dumps(merged), encoding="utf-8")
    cache = BioViLTControlCacheIndex(tmp_path, maximum_loaded_shards=1)
    values = cache.get_many(["p1", "p0"], mode="inverted")
    assert values.shape == (2, 128)
    assert torch.equal(values, torch.full((2, 128), 2.0))
