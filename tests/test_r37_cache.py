import json

import torch

from visualvit.r37_cache import Block8CacheIndex


def write_json(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")


def build_cache(tmp_path):
    root = tmp_path / "cache"
    part = root / "part_00_of_01"
    shards = part / "shards"
    shards.mkdir(parents=True)
    features0 = torch.zeros(2, 197, 768, dtype=torch.float16)
    features0[1] = 1
    features1 = torch.full((1, 197, 768), 2, dtype=torch.float16)
    path0 = shards / "s0.pt"
    path1 = shards / "s1.pt"
    torch.save({"dicom_ids": ["a", "b"], "features": features0}, path0)
    torch.save({"dicom_ids": ["c"], "features": features1}, path1)
    write_json(
        part / "image_inventory.json",
        [
            {"dicom_id": "a", "path": "a.jpg"},
            {"dicom_id": "b", "path": "b.jpg"},
            {"dicom_id": "c", "path": "c.jpg"},
        ],
    )
    part_manifest = part / "cache_manifest.json"
    write_json(
        part_manifest,
        {
            "shards": [
                {"path": str(path0), "images": 2},
                {"path": str(path1), "images": 1},
            ]
        },
    )
    write_json(
        root / "cache_manifest.json",
        {
            "status": "PASS_R37_BLOCK8_FORMAL_CACHE",
            "cached_image_count": 3,
            "parts": [{"manifest_path": str(part_manifest)}],
        },
    )
    return root


def test_cache_index_retrieves_ordered_tokens_across_shards(tmp_path):
    index = Block8CacheIndex(build_cache(tmp_path), maximum_loaded_shards=1)
    observed = index.get_many(["c", "a", "b"])
    assert observed.shape == (3, 197, 768)
    assert observed[:, 0, 0].tolist() == [2.0, 0.0, 1.0]
    assert len(index) == 3
    assert len(index._loaded) == 1


def test_cache_index_rejects_missing_dicom(tmp_path):
    index = Block8CacheIndex(build_cache(tmp_path))
    try:
        index.get_many(["missing"])
    except KeyError as error:
        assert "first=missing" in str(error)
    else:
        raise AssertionError("missing DICOM should fail")
