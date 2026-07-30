from __future__ import annotations

# ruff: noqa: E402

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE))
sys.path.insert(0, str(WORKSPACE / "src"))


CONFIG_STATUS = "FROZEN_PRTA_GEN_R40B_OVERFIT_SMOKE"
CONFIG_STATUSES = {
    CONFIG_STATUS,
    "FROZEN_PRTA_GEN_R40B1_CONSTRAINED_SMOKE",
    "FROZEN_PRTA_GEN_R40B2_PROGRESSION_SPAN_SMOKE",
    "FROZEN_PRTA_GEN_R40B3_DIRECT_CLASS_SMOKE",
}
COHORT_STATUS = "PASS_PRTA_GEN_R40B_SMOKE_COHORT"
EXCLUDED_COHORT_STATUSES = {
    COHORT_STATUS,
    "PASS_PRTA_GEN_R40B1_SMOKE_COHORT",
    "PASS_PRTA_GEN_R40B2_SMOKE_COHORT",
}


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise TypeError(f"expected JSON object: {path}")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def stable_key(namespace: str, example_id: str) -> str:
    return hashlib.sha256(
        f"{namespace}|{example_id}".encode("utf-8")
    ).hexdigest()


def compact_target(row: dict[str, Any]) -> str:
    return json.dumps(
        {
            "finding": str(row["finding"]),
            "progression": str(row["progression"]),
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


def read_targets(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    with path.open("r", encoding="utf-8-sig") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                raise TypeError(f"target line {line_number} is not an object")
            required = {"example_id", "patient_id", "finding", "progression"}
            if not required.issubset(row):
                raise ValueError(f"target line {line_number} is incomplete")
            example_id = str(row["example_id"])
            if example_id in seen:
                raise ValueError(f"duplicate target example_id: {example_id}")
            seen.add(example_id)
            rows.append(row)
    return rows


def select_rows(
    rows: list[dict[str, Any]],
    *,
    fit_patient_ids: set[str],
    namespace: str,
    class_counts: dict[str, int],
    excluded_patient_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    excluded = excluded_patient_ids or set()
    selected: list[dict[str, Any]] = []
    used_patients: set[str] = set()
    for progression, count in class_counts.items():
        eligible = sorted(
            (
                row
                for row in rows
                if str(row["progression"]) == progression
                and str(row["patient_id"]) in fit_patient_ids
                and str(row["patient_id"]) not in excluded
            ),
            key=lambda row: stable_key(namespace, str(row["example_id"])),
        )
        class_selected: list[dict[str, Any]] = []
        for row in eligible:
            patient_id = str(row["patient_id"])
            if patient_id in used_patients:
                continue
            class_selected.append(row)
            used_patients.add(patient_id)
            if len(class_selected) == count:
                break
        if len(class_selected) != count:
            raise ValueError(
                f"insufficient unique-patient support for {progression}: "
                f"{len(class_selected)} < {count}"
            )
        selected.extend(class_selected)
    return sorted(
        selected,
        key=lambda row: stable_key(namespace, str(row["example_id"])),
    )


def build_cohort(*, config_path: Path, output_path: Path) -> dict[str, Any]:
    if output_path.exists():
        raise FileExistsError(f"R40B cohort output must be fresh: {output_path}")
    config = read_json(config_path)
    if config.get("status") not in CONFIG_STATUSES:
        raise PermissionError("R40B config is not frozen")
    closed_spec = config.get("closed_predecessor")
    if closed_spec is not None:
        closed = read_json(Path(closed_spec["result"]))
        if closed.get("status") != closed_spec["required_status"]:
            raise PermissionError("R40B.1 predecessor is not formally closed")
    upstream_spec = config["upstream"]
    upstream = read_json(Path(upstream_spec["qualification_aggregate"]))
    if (
        upstream.get("status") != upstream_spec["required_status"]
        or upstream.get("candidate") != upstream_spec["required_candidate"]
        or upstream.get("progression_generation_unlocked") is not True
        or upstream.get("laterality_generation_unlocked") is not False
        or upstream.get("anatomy_generation_unlocked") is not False
        or upstream.get("degree_generation_unlocked") is not False
        or upstream.get("evidence_generation_unlocked") is not False
        or upstream.get("protected_300_dev_read") is not False
        or upstream.get("revealed_483_test_read") is not False
        or upstream.get("gold_outcomes_read") is not False
    ):
        raise PermissionError("R40B qualification unlock drift")
    source = config["source"]
    roster = read_json(Path(source["roster"]))
    if (
        roster.get("status") != source["required_roster_status"]
        or roster.get("protected_300_dev_read") is not False
        or roster.get("revealed_483_test_read") is not False
        or roster.get("gold_outcomes_read") is not False
        or roster.get("patient_sets_disjoint") is not True
    ):
        raise PermissionError("R40B roster firewall drift")
    token_index = read_json(Path(source["token_index"]))
    if (
        token_index.get("status") != source["required_token_status"]
        or token_index.get("scope") != "training"
        or token_index.get("labels_in_cache") is not False
        or token_index.get("sentences_in_cache") is not False
        or token_index.get("revealed_483_test_read") is not False
        or token_index.get("gold_outcomes_read") is not False
    ):
        raise PermissionError("R40B token-cache firewall drift")
    partition = str(source["partition"])
    fit_patients = {
        str(value)
        for value in roster["partitions"][partition]["patient_ids"]
    }
    class_counts = {
        str(key): int(value)
        for key, value in source["progression_class_counts"].items()
    }
    excluded_patients: set[str] = set()
    exclude_cohort_paths = []
    if source.get("exclude_cohort") is not None:
        exclude_cohort_paths.append(source["exclude_cohort"])
    exclude_cohort_paths.extend(source.get("exclude_cohorts", []))
    for exclude_cohort_path in exclude_cohort_paths:
        excluded_cohort = read_json(Path(exclude_cohort_path))
        if excluded_cohort.get("status") not in EXCLUDED_COHORT_STATUSES:
            raise PermissionError("R40B.1 excluded cohort receipt drift")
        excluded_patients.update(
            str(row["patient_id"]) for row in excluded_cohort["rows"]
        )
    if sum(class_counts.values()) != int(source["rows"]):
        raise ValueError("R40B class counts do not sum to frozen row count")
    target_rows = read_targets(Path(source["targets"]))
    selected = select_rows(
        target_rows,
        fit_patient_ids=fit_patients,
        namespace=str(source["namespace"]),
        class_counts=class_counts,
        excluded_patient_ids=excluded_patients,
    )
    rows = [
        {
            "example_id": str(row["example_id"]),
            "patient_id": str(row["patient_id"]),
            "finding": str(row["finding"]),
            "progression": str(row["progression"]),
            "target_text": compact_target(row),
        }
        for row in selected
    ]
    result = {
        "schema": "visualvit.prta-gen.r40b-smoke-cohort.v1",
        "status": (
            COHORT_STATUS
            if str(config.get("stage_tag", "R40B")) == "R40B"
            else f"PASS_PRTA_GEN_{config['stage_tag']}_SMOKE_COHORT"
        ),
        "protocol_id": config["protocol_id"],
        "partition": partition,
        "namespace": source["namespace"],
        "rows": rows,
        "row_count": len(rows),
        "patient_count": len({row["patient_id"] for row in rows}),
        "one_row_per_patient": len({row["patient_id"] for row in rows})
        == len(rows),
        "excluded_parent_patient_count": len(excluded_patients),
        "excluded_parent_patients_absent": not bool(
            excluded_patients.intersection(
                {str(row["patient_id"]) for row in rows}
            )
        ),
        "progression_class_counts": {
            progression: sum(
                row["progression"] == progression for row in rows
            )
            for progression in class_counts
        },
        "target_schema_keys": config["target"]["schema_keys_in_order"],
        "all_other_fields_omitted": True,
        "protected_300_dev_read": False,
        "revealed_483_test_read": False,
        "gold_outcomes_read": False,
        "external_outcomes_read": False,
        "scientific_claim_allowed": False,
    }
    if (
        result["row_count"] != int(source["rows"])
        or result["row_count"] > int(source["maximum_rows"])
        or result["patient_count"] != result["row_count"]
        or result["progression_class_counts"] != class_counts
    ):
        raise ValueError("R40B selected cohort drift")
    write_json(output_path, result)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Freeze the progression-only R40B 32-row smoke cohort"
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = build_cohort(
        config_path=args.config,
        output_path=args.output,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
