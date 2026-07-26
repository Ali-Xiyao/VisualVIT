from __future__ import annotations

# ruff: noqa: E402

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE))
sys.path.insert(0, str(WORKSPACE / "src"))

from scripts import run_chest_imagenome_mimic_matcher_qualification as runner
from visualvit.real_progression import build_pair_and_entity_manifests


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-root",
        type=Path,
        default=WORKSPACE / "artifacts/r25_1_semantic_repair/manifests",
    )
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _cohort_args() -> SimpleNamespace:
    return SimpleNamespace(
        gold_comparison=runner.CI_ROOT_DEFAULT
        / "gold_dataset/gold_object_comparison_with_coordinates.txt",
        gold_scaling=runner.CI_ROOT_DEFAULT
        / "gold_dataset/gold_bbox_scaling_factors_original_to_224x224.csv",
        metadata=runner.MIMIC_OTHER_DEFAULT / "mimic-cxr-2.0.0-metadata.csv.gz",
        split=runner.MIMIC_OTHER_DEFAULT / "mimic-cxr-2.0.0-split.csv.gz",
        silver_images_to_avoid=runner.CI_ROOT_DEFAULT
        / "silver_dataset/splits/images_to_avoid.csv",
        r24_v3_cohort=WORKSPACE
        / "artifacts/real_qualification/chextemporal_mimic_matcher_v3/"
        "process_a/cohort.json",
        image_root=runner.IMAGE_ROOT_DEFAULT,
    )


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False),
        encoding="utf-8",
    )


def main() -> int:
    args = parse_args()
    if args.output_root.exists():
        raise FileExistsError(args.output_root)

    records, cohort_audit = runner._strict_cohort(_cohort_args())
    pair_manifest, entity_manifest = build_pair_and_entity_manifests(records)
    if len(pair_manifest) != runner.EXPECTED_PAIRS:
        raise RuntimeError(
            f"pair manifest drift: {len(pair_manifest)} != {runner.EXPECTED_PAIRS}"
        )
    if len(entity_manifest) != runner.EXPECTED_ROWS:
        raise RuntimeError(
            f"entity manifest drift: {len(entity_manifest)} != {runner.EXPECTED_ROWS}"
        )

    args.output_root.mkdir(parents=True)
    pair_path = args.output_root / "pair_manifest.json"
    entity_path = args.output_root / "entity_manifest.json"
    audit_path = args.output_root / "cohort_audit.json"
    _write_json(pair_path, pair_manifest)
    _write_json(entity_path, entity_manifest)
    _write_json(audit_path, cohort_audit)

    summary = {
        "status": "PASS_R25_1_MANIFEST_SPLIT",
        "evidence_class": "NON_CONFIRMATORY_MANIFEST_QUALIFICATION",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "counts": {
            "patients": len({item["patient_id"] for item in pair_manifest}),
            "pairs": len(pair_manifest),
            "entities": len(entity_manifest),
            "progression_labels": dict(
                sorted(Counter(item["progression"] for item in entity_manifest).items())
            ),
        },
        "artifacts": {
            pair_path.name: sha256_file(pair_path),
            entity_path.name: sha256_file(entity_path),
            audit_path.name: sha256_file(audit_path),
        },
        "interpretation_boundary": (
            "The pair manifest defines independent matching units; the entity "
            "manifest carries Stable/Improved/Worse targets for a future R26 "
            "classifier. No progression model was executed."
        ),
    }
    summary_path = args.output_root / "manifest_summary.json"
    _write_json(summary_path, summary)
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
