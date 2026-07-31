from __future__ import annotations

# ruff: noqa: E402

import argparse
from collections import Counter
import json
from pathlib import Path
import sys
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE))
sys.path.insert(0, str(WORKSPACE / "src"))

from scripts.audit_prta_gen_r44_independent_support import sha256_file
from scripts.build_prta_gen_r40b_smoke_cohort import read_json, write_json
from scripts.build_prta_gen_r44a_roster import image_id, resolve_image_path
from scripts.build_prta_gen_r45_cdeb_roster import (
    load_image_complete_rows,
    select_rows,
    stable_key,
)
from scripts.build_prta_gen_r46_cea_roster import (
    validate_authority as validate_r46_authority,
)
from visualvit.prta_gen import PROGRESSION_CLASSES


CONFIG_STATUS = "FROZEN_PRTA_GEN_R47_UCC_ROSTER"


def validate_authority(config: dict[str, Any]) -> dict[str, Any]:
    if config.get("status") != CONFIG_STATUS:
        raise PermissionError("R47 roster config is not frozen")
    closed = config["closed_r46"]
    r46_config_path = WORKSPACE / closed["roster_config"]
    if (
        not r46_config_path.is_file()
        or r46_config_path.stat().st_size
        != int(closed["roster_config_bytes"])
        or sha256_file(r46_config_path)
        != closed["roster_config_sha256"]
    ):
        raise PermissionError("R47 R46 roster-config authority drift")
    r46_config = read_json(r46_config_path)
    r46_authority = validate_r46_authority(r46_config)
    r46_roster_path = Path(closed["roster"])
    case_path = Path(closed["case_study"])
    for path, prefix in (
        (r46_roster_path, "roster"),
        (case_path, "case_study"),
    ):
        if (
            not path.is_file()
            or path.stat().st_size != int(closed[f"{prefix}_bytes"])
            or sha256_file(path) != closed[f"{prefix}_sha256"]
        ):
            raise PermissionError(f"R47 R46 {prefix} authority drift")
    r46_roster = read_json(r46_roster_path)
    case_study = read_json(case_path)
    if (
        r46_roster.get("status") != closed["roster_status"]
        or case_study.get("status") != closed["case_study_status"]
        or case_study.get("model_training_started") is not False
        or case_study.get("qualification_unlocked") is not False
        or case_study.get("confirmation_unlocked") is not False
    ):
        raise PermissionError("R47 closed R46 receipt drift")
    r46_patients = {
        str(row["patient_id"])
        for row in r46_roster["partitions"]["development"]["rows"]
    }
    if len(r46_patients) != int(
        closed["required_r46_development_patients"]
    ):
        raise PermissionError("R47 R46 exclusion count drift")
    return {
        **r46_authority,
        "r46_patients": r46_patients,
        "r46_roster": r46_roster,
    }


def selection(
    config: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    authority = validate_authority(config)
    rows, source_inventory, indexed = load_image_complete_rows(
        authority["r45_config"], authority["r45_authority"]
    )
    excluded = authority["r45_patients"] | authority["r46_patients"]
    eligible = [
        row
        for row in rows
        if str(row["patient_id"]) not in excluded
    ]
    counts = {
        "development": {
            str(label): int(count)
            for label, count in config["roster"][
                "development_class_counts"
            ].items()
        }
    }
    selected = select_rows(
        eligible,
        namespace=str(config["roster"]["namespace"]),
        partition_order=["development"],
        class_order=[
            str(value) for value in config["roster"]["class_order"]
        ],
        counts=counts,
    )["development"]
    selected_patients = {str(row["patient_id"]) for row in selected}
    resolved_patients = {
        str(row["patient_id"])
        for row in eligible
        if str(row["progression"]) == "Resolved"
    }
    reserve = len(resolved_patients - selected_patients)
    if reserve < int(
        config["roster"]["minimum_unselected_resolved_patient_reserve"]
    ):
        raise ValueError("R47 Resolved reserve is below frozen minimum")
    inventory = {
        **source_inventory,
        "all_r45_and_r46_excluded_patients": len(excluded),
        "eligible_rows_after_all_exclusions": len(eligible),
        "eligible_patients_after_all_exclusions": len(
            {str(row["patient_id"]) for row in eligible}
        ),
        "eligible_unique_patient_support": {
            label: len(
                {
                    str(row["patient_id"])
                    for row in eligible
                    if str(row["progression"]) == label
                }
            )
            for label in PROGRESSION_CLASSES
        },
    }
    return selected, inventory, {
        **authority,
        "indexed": indexed,
        "excluded": excluded,
        "resolved_patient_reserve": reserve,
    }


def preflight(config_path: Path) -> dict[str, Any]:
    config = read_json(config_path)
    selected, inventory, authority = selection(config)
    return {
        "schema": "visualvit.prta-gen.r47-ucc-roster-preflight.v1",
        "status": config["result_statuses"]["preflight_pass"],
        "protocol_id": config["protocol_id"],
        "inventory": inventory,
        "selected_counts_in_memory_only": dict(
            sorted(Counter(str(row["progression"]) for row in selected).items())
        ),
        "selected_patients_in_memory_only": len(selected),
        "resolved_patient_reserve": authority["resolved_patient_reserve"],
        "real_roster_written": False,
        "gpu_training_started": False,
        "r45_qualification_outcomes_read": False,
        "r45_confirmation_outcomes_read": False,
        "gold_outcomes_read": False,
        "external_outcomes_read": False,
        "scientific_claim_allowed": False,
    }


def build_roster(config_path: Path, output_path: Path) -> dict[str, Any]:
    if output_path.exists():
        raise FileExistsError(f"R47 roster output must be fresh: {output_path}")
    config = read_json(config_path)
    selected, inventory, authority = selection(config)
    root = authority["r45_authority"]["image_root"]
    rows = []
    for row in selected:
        prior_raw = str(row["parent_image_prev"])
        current_raw = str(row["parent_image_curr"])
        rows.append(
            {
                "example_id": stable_key(
                    str(config["roster"]["namespace"]), row
                ),
                "patient_id": str(row["patient_id"]),
                "finding": str(row["finding"]),
                "progression": str(row["progression"]),
                "prior_study_id": str(row["study_id_prev"]),
                "current_study_id": str(row["study_id_curr"]),
                "prior_image_id": image_id(prior_raw),
                "current_image_id": image_id(current_raw),
                "prior_path": str(resolve_image_path(root, prior_raw)),
                "current_path": str(resolve_image_path(root, current_raw)),
            }
        )
    counts = dict(sorted(Counter(row["progression"] for row in rows).items()))
    expected = dict(
        sorted(config["roster"]["development_class_counts"].items())
    )
    if (
        len(rows) != int(config["roster"]["development_patients"])
        or len({row["patient_id"] for row in rows}) != len(rows)
        or counts != expected
        or {row["patient_id"] for row in rows} & authority["excluded"]
    ):
        raise PermissionError("R47 development roster drift")
    result = {
        "schema": "visualvit.prta-gen.r47-ucc-roster.v1",
        "status": config["result_statuses"]["roster_pass"],
        "protocol_id": config["protocol_id"],
        "namespace": config["roster"]["namespace"],
        "partitions": {
            "development": {
                "rows": rows,
                "row_count": len(rows),
                "patient_count": len({row["patient_id"] for row in rows}),
                "progression_class_counts": counts,
            }
        },
        "inventory": inventory,
        "reused_fit_partition": "R45/train",
        "reused_fit_rows": len(authority["fit_rows"]),
        "all_r45_and_r46_excluded_patient_count": len(authority["excluded"]),
        "all_r45_patients_absent_from_development": True,
        "all_r46_patients_absent_from_development": True,
        "all_r45_and_r46_patients_absent_from_development": True,
        "one_row_per_patient": True,
        "selected_images_complete": True,
        "resolved_patient_reserve": authority["resolved_patient_reserve"],
        "resplit_allowed": False,
        "r45_development_outcomes_used": False,
        "r46_outcomes_used_only_for_hypothesis": True,
        "r45_qualification_tokens_materialized": False,
        "r45_confirmation_tokens_materialized": False,
        "r45_qualification_outcomes_read": False,
        "r45_confirmation_outcomes_read": False,
        "gold_outcomes_read": False,
        "external_outcomes_read": False,
        "scientific_claim_allowed": False,
    }
    output_path.parent.mkdir(parents=True, exist_ok=False)
    write_json(output_path, result)
    return result


def receipt_summary(result: dict[str, Any]) -> dict[str, Any]:
    summary = {key: value for key, value in result.items() if key != "partitions"}
    if "partitions" in result:
        summary["partitions"] = {
            name: {key: value for key, value in payload.items() if key != "rows"}
            for name, payload in result["partitions"].items()
        }
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Preflight or build the frozen R47 UCC roster"
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.preflight_only:
        if args.output is not None:
            raise ValueError("R47 preflight must not receive --output")
        result = preflight(args.config)
    else:
        if args.output is None:
            raise ValueError("R47 roster build requires --output")
        result = build_roster(args.config, args.output)
    print(json.dumps(receipt_summary(result), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
