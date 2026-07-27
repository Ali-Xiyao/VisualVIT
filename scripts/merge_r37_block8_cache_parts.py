from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


FORMAL_ROOT = Path(
    r"H:\VisualVIT_runtime\050_routeD\r37_prta_cxr"
    r"\r37_block8_token_cache"
)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Merge disjoint R37 Block-8 cache-part manifests"
    )
    parser.add_argument("--cache-root", type=Path, default=FORMAL_ROOT)
    parser.add_argument("--part-count", type=int, default=2)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output = args.cache_root / "cache_manifest.json"
    if output.exists():
        raise FileExistsError(f"merged manifest must be fresh: {output}")
    manifests = []
    inventories = []
    for index in range(args.part_count):
        part = args.cache_root / f"part_{index:02d}_of_{args.part_count:02d}"
        manifest = read_json(part / "cache_manifest.json")
        inventory = read_json(part / "image_inventory.json")
        expected_slice = manifest["inventory_slice"]
        if expected_slice["part_index"] != index:
            raise ValueError(f"cache part index drift in {part}")
        if expected_slice["part_count"] != args.part_count:
            raise ValueError(f"cache part count drift in {part}")
        if manifest["status"] != "PASS_R37_BLOCK8_FORMAL_CACHE":
            raise ValueError(f"cache part did not pass: {part}")
        if manifest["cached_image_count"] != len(inventory):
            raise ValueError(f"cache inventory count drift in {part}")
        manifests.append(manifest)
        inventories.append(inventory)

    formal_counts = {item["formal_inventory_count"] for item in manifests}
    if len(formal_counts) != 1:
        raise ValueError("formal inventory count differs across cache parts")
    formal_count = formal_counts.pop()
    ordered_ids = [
        item["dicom_id"] for inventory in inventories for item in inventory
    ]
    if len(ordered_ids) != len(set(ordered_ids)):
        raise ValueError("DICOM overlap exists across cache parts")
    if len(ordered_ids) != formal_count:
        raise ValueError(
            f"merged cache coverage {len(ordered_ids)} != {formal_count}"
        )

    merged = {
        "schema": "visualvit.r37.block8-cache-merged-manifest.v1",
        "status": "PASS_R37_BLOCK8_FORMAL_CACHE",
        "cache_root": str(args.cache_root),
        "part_count": args.part_count,
        "formal_inventory_count": formal_count,
        "cached_image_count": len(ordered_ids),
        "feature_shape_per_image": manifests[0]["feature_shape_per_image"],
        "feature_dtype": manifests[0]["feature_dtype"],
        "extraction_boundary": manifests[0]["extraction_boundary"],
        "parts": [
            {
                "manifest_path": str(
                    args.cache_root
                    / f"part_{index:02d}_of_{args.part_count:02d}"
                    / "cache_manifest.json"
                ),
                "cached_image_count": manifest["cached_image_count"],
                "shard_count": manifest["shard_count"],
                "total_bytes": manifest["total_bytes"],
                "elapsed_seconds": manifest["elapsed_seconds"],
                "device": manifest["device"],
                "device_name": manifest["device_name"],
                "reproducibility": manifest["reproducibility"],
            }
            for index, manifest in enumerate(manifests)
        ],
        "shards": [
            shard for manifest in manifests for shard in manifest["shards"]
        ],
        "shard_count": sum(item["shard_count"] for item in manifests),
        "total_bytes": sum(item["total_bytes"] for item in manifests),
        "protected_outcomes_read": False,
        "source_hashes_recomputed": False,
        "per_shard_hashes_computed": False,
    }
    output.write_text(
        json.dumps(merged, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps(merged, indent=2, sort_keys=True))
    print(f"RESULT={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
