from __future__ import annotations

from collections import OrderedDict, defaultdict
import json
from pathlib import Path
from typing import Any, Iterable

import torch


class Block8CacheIndex:
    def __init__(self, cache_root: Path, *, maximum_loaded_shards: int = 4):
        if maximum_loaded_shards <= 0:
            raise ValueError("maximum loaded shards must be positive")
        self.cache_root = Path(cache_root)
        self.maximum_loaded_shards = maximum_loaded_shards
        self.locations: dict[str, tuple[Path, int]] = {}
        self._loaded: OrderedDict[Path, dict[str, Any]] = OrderedDict()
        self._build_index()

    def _build_index(self) -> None:
        merged = json.loads(
            (self.cache_root / "cache_manifest.json").read_text(
                encoding="utf-8"
            )
        )
        if merged["status"] != "PASS_R37_BLOCK8_FORMAL_CACHE":
            raise ValueError("R37 Block-8 cache is not a PASS artifact")
        for part_entry in merged["parts"]:
            part_manifest_path = Path(part_entry["manifest_path"])
            part_manifest = json.loads(
                part_manifest_path.read_text(encoding="utf-8")
            )
            inventory = json.loads(
                (part_manifest_path.parent / "image_inventory.json").read_text(
                    encoding="utf-8"
                )
            )
            offset = 0
            for shard_entry in part_manifest["shards"]:
                count = int(shard_entry["images"])
                current = inventory[offset : offset + count]
                if len(current) != count:
                    raise ValueError("cache shard exceeds part inventory")
                path = Path(shard_entry["path"])
                for local_index, item in enumerate(current):
                    dicom_id = str(item["dicom_id"])
                    if dicom_id in self.locations:
                        raise ValueError(f"duplicate cached DICOM: {dicom_id}")
                    self.locations[dicom_id] = (path, local_index)
                offset += count
            if offset != len(inventory):
                raise ValueError("cache part did not consume its inventory")
        if len(self.locations) != int(merged["cached_image_count"]):
            raise ValueError("merged cache count differs from indexed DICOMs")

    def __len__(self) -> int:
        return len(self.locations)

    def _load_shard(self, path: Path) -> dict[str, Any]:
        if path in self._loaded:
            value = self._loaded.pop(path)
            self._loaded[path] = value
            return value
        value = torch.load(path, map_location="cpu", weights_only=True)
        if tuple(value["features"].shape[1:]) != (197, 768):
            raise ValueError(f"unexpected Block-8 shard shape: {path}")
        self._loaded[path] = value
        while len(self._loaded) > self.maximum_loaded_shards:
            self._loaded.popitem(last=False)
        return value

    def get_many(self, dicom_ids: Iterable[str]) -> torch.Tensor:
        ids = [str(value) for value in dicom_ids]
        missing = [value for value in ids if value not in self.locations]
        if missing:
            raise KeyError(f"{len(missing)} DICOM IDs are absent; first={missing[0]}")
        grouped: dict[Path, list[tuple[int, int]]] = defaultdict(list)
        for output_index, dicom_id in enumerate(ids):
            path, local_index = self.locations[dicom_id]
            grouped[path].append((output_index, local_index))
        output: list[torch.Tensor | None] = [None] * len(ids)
        for path, requests in grouped.items():
            shard = self._load_shard(path)
            features = shard["features"]
            for output_index, local_index in requests:
                output[output_index] = features[local_index]
        if any(value is None for value in output):
            raise RuntimeError("cache retrieval left an unfilled output")
        return torch.stack([value for value in output if value is not None])
