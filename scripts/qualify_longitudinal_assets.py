from __future__ import annotations

# ruff: noqa: E402

import argparse
import json
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE / "src"))

from visualvit.data_qualification import (
    AUDIT_SCHEMA_VERSION,
    qualify_longitudinal_assets,
    write_audit_json,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fail-closed qualification of longitudinal asset lineage."
    )
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        report = qualify_longitudinal_assets(
            manifest,
            base_dir=args.manifest.parent,
        )
    except (OSError, json.JSONDecodeError) as error:
        report = {
            "audit_schema_version": AUDIT_SCHEMA_VERSION,
            "manifest_schema_version": None,
            "status": "FAIL",
            "qualified": False,
            "formal_use_allowed": False,
            "checks": {},
            "counts": {},
            "sources": [],
            "records": [],
            "duplicates": {
                "cross_split": [],
                "cross_source": [],
                "exact_records": [],
            },
            "sealed_splits": {},
            "sealed_split_hash": None,
            "errors": [
                {
                    "code": "MANIFEST_READ",
                    "message": f"{type(error).__name__}: {error}",
                }
            ],
        }
    write_audit_json(report, args.output)
    print(
        json.dumps(
            {
                "output": str(args.output.resolve()),
                "status": report["status"],
                "errors": len(report["errors"]),
            },
            sort_keys=True,
        )
    )
    return 0 if report["qualified"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
