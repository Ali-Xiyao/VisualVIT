from __future__ import annotations

# ruff: noqa: E402

import argparse
import csv
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Iterable, Mapping

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE / "src"))

from visualvit.statistics import (
    DEFAULT_BOOTSTRAP_RNG_SEED,
    PredictionRow,
    evaluate_formal_statistics,
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_serialized_rows(path: Path) -> Iterable[Mapping[str, Any]]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            yield from csv.DictReader(handle)
        return
    if suffix in {".jsonl", ".ndjson"}:
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise ValueError(
                        f"line {line_number} must be a JSON object, got "
                        f"{type(value).__name__}"
                    )
                yield value
        return
    if suffix == ".json":
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, list) or not all(
            isinstance(item, dict) for item in value
        ):
            raise ValueError("JSON input must be an array of row objects")
        yield from value
        return
    raise ValueError("input must use .csv, .json, .jsonl or .ndjson")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the frozen CAPES-CI five-label formal statistics protocol."
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--bootstrap-replicates", type=int, default=10_000)
    parser.add_argument("--patient-only-replicates", type=int)
    parser.add_argument("--rng-seed", type=int, default=DEFAULT_BOOTSTRAP_RNG_SEED)
    parser.add_argument("--b4a-system", default="b4a")
    parser.add_argument("--b4b-system", default="b4b")
    parser.add_argument("--learned-system", default="learned")
    parser.add_argument("--minimum-valid-fraction", type=float, default=0.95)
    parser.add_argument(
        "--minimum-denominator-positive-fraction", type=float, default=0.95
    )
    parser.add_argument("--delta-bind-minimum-effect-pp", type=float, default=5.0)
    parser.add_argument(
        "--allow-nonfrozen-seeds",
        action="store_true",
        help="Disable the frozen ordered seed-bank check (not confirmatory).",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    input_path = args.input.resolve()
    rows = tuple(
        PredictionRow.from_mapping(row) for row in _load_serialized_rows(input_path)
    )
    result = evaluate_formal_statistics(
        rows,
        b4a_system=args.b4a_system,
        b4b_system=args.b4b_system,
        learned_system=args.learned_system,
        bootstrap_replicates=args.bootstrap_replicates,
        patient_only_replicates=args.patient_only_replicates,
        rng_seed=args.rng_seed,
        minimum_valid_fraction=args.minimum_valid_fraction,
        minimum_denominator_positive_fraction=(
            args.minimum_denominator_positive_fraction
        ),
        delta_bind_minimum_effect_pp=args.delta_bind_minimum_effect_pp,
        enforce_seed_bank=not args.allow_nonfrozen_seeds,
    )
    statistics_source = (
        Path(__file__).resolve().parents[1] / "src" / "visualvit" / "statistics.py"
    )
    payload = {
        "schema_version": "capes-ci-formal-statistics-v1",
        "input": {
            "path": str(input_path),
            "sha256": _sha256(input_path),
            "prediction_rows": len(rows),
        },
        "analysis": {
            "statistics_source_sha256": _sha256(statistics_source),
            "runner_source_sha256": _sha256(Path(__file__).resolve()),
            "bootstrap_replicates": args.bootstrap_replicates,
            "patient_only_replicates": (
                args.patient_only_replicates or args.bootstrap_replicates
            ),
            "rng_seed": args.rng_seed,
            "enforce_seed_bank": not args.allow_nonfrozen_seeds,
        },
        "result": asdict(result),
    }
    encoded = json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if args.output is None:
        sys.stdout.write(encoded)
    else:
        output_path = args.output.resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(encoded, encoding="utf-8")
        print(output_path)

    # A low valid-replicate rate suppresses the CIs and is an analysis failure,
    # while a scientifically null C1/C2 result remains a valid completed run.
    return int(
        not result.hierarchical_bootstrap.inference_valid
        or not result.patient_only_bootstrap.inference_valid
    )


if __name__ == "__main__":
    raise SystemExit(main())
