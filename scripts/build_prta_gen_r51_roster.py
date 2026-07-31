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
    validate_authority as validate_r45_source_authority,
)
from visualvit.prta_gen import PROGRESSION_CLASSES


CONFIG_STATUS = "FROZEN_PRTA_GEN_R51_MATCHED_INTERFACE_ROSTER"


def _verify(path: Path, expected_bytes: int, expected_sha256: str) -> None:
    if (
        not path.is_file()
        or path.stat().st_size != expected_bytes
        or sha256_file(path) != expected_sha256
    ):
        raise PermissionError(f"R51 roster authority drift: {path}")


def selection(
    config_path: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    config = read_json(config_path)
    if config.get("status") != CONFIG_STATUS:
        raise PermissionError("R51 roster config is not frozen")
    authority = config["authority"]
    r45_config_path = WORKSPACE / authority["r45_roster_config"]
    r45_roster_path = Path(authority["r45_roster"])
    _verify(
        r45_config_path,
        int(authority["r45_roster_config_bytes"]),
        str(authority["r45_roster_config_sha256"]),
    )
    _verify(
        r45_roster_path,
        int(authority["r45_roster_bytes"]),
        str(authority["r45_roster_sha256"]),
    )
    r45_config = read_json(r45_config_path)
    r45_roster = read_json(r45_roster_path)
    if r45_roster.get("status") != authority["r45_roster_status"]:
        raise PermissionError("R51 closed R45 roster status drift")
    r45_patients = {
        str(row["patient_id"])
        for payload in r45_roster["partitions"].values()
        for row in payload["rows"]
    }
    if len(r45_patients) != int(authority["required_excluded_r45_patients"]):
        raise PermissionError("R51 R45 exclusion count drift")
    source_authority = validate_r45_source_authority(r45_config)
    rows, source_inventory, indexed = load_image_complete_rows(
        r45_config, source_authority
    )
    unused = [
        row for row in rows if str(row["patient_id"]) not in r45_patients
    ]
    counts = {
        "evaluation": {
            str(label): int(value)
            for label, value in config["roster"][
                "evaluation_class_counts"
            ].items()
        }
    }
    selected = select_rows(
        unused,
        namespace=str(config["roster"]["namespace"]),
        partition_order=["evaluation"],
        class_order=[str(value) for value in config["roster"]["class_order"]],
        counts=counts,
    )["evaluation"]
    selected_patients = {str(row["patient_id"]) for row in selected}
    if (
        len(selected) != int(config["roster"]["evaluation_patients"])
        or len(selected_patients) != len(selected)
        or selected_patients & r45_patients
    ):
        raise PermissionError("R51 fresh evaluation selection drift")
    remaining_resolved = {
        str(row["patient_id"])
        for row in unused
        if str(row["progression"]) == "Resolved"
        and str(row["patient_id"]) not in selected_patients
    }
    if len(remaining_resolved) < int(
        config["roster"]["minimum_remaining_resolved_patient_reserve"]
    ):
        raise ValueError("R51 remaining Resolved reserve is too small")
    inventory = {
        **source_inventory,
        "excluded_r45_patients": len(r45_patients),
        "unused_image_complete_rows": len(unused),
        "unused_image_complete_patients": len(
            {str(row["patient_id"]) for row in unused}
        ),
        "unused_unique_patient_support": {
            label: len(
                {
                    str(row["patient_id"])
                    for row in unused
                    if str(row["progression"]) == label
                }
            )
            for label in PROGRESSION_CLASSES
        },
        "remaining_resolved_patient_reserve": len(remaining_resolved),
    }
    return selected, inventory, {
        "config": config,
        "image_root": source_authority["image_root"],
        "indexed": indexed,
        "r45_patients": r45_patients,
    }


def preflight(config_path: Path) -> dict[str, Any]:
    selected, inventory, authority = selection(config_path)
    config = authority["config"]
    return {
        "schema": "visualvit.prta-gen.r51-roster-preflight.v1",
        "status": config["result_statuses"]["preflight_pass"],
        "protocol_id": config["protocol_id"],
        "evaluation_rows_selected_in_memory_only": len(selected),
        "evaluation_class_counts": dict(
            sorted(Counter(str(row["progression"]) for row in selected).items())
        ),
        "unused_image_complete_patients": inventory[
            "unused_image_complete_patients"
        ],
        "unused_unique_patient_support": inventory[
            "unused_unique_patient_support"
        ],
        "remaining_resolved_patient_reserve": inventory[
            "remaining_resolved_patient_reserve"
        ],
        "all_r45_patients_excluded": True,
        "real_roster_written": False,
        "gpu_work_started": False,
        "evaluation_model_outcomes_read": False,
        "protected_300_dev_read": False,
        "revealed_483_test_read": False,
        "gold_outcomes_read": False,
        "external_outcomes_read": False,
    }


def build_roster(config_path: Path, output_path: Path) -> dict[str, Any]:
    if output_path.exists():
        raise FileExistsError(f"R51 roster output must be fresh: {output_path}")
    selected, inventory, authority = selection(config_path)
    config = authority["config"]
    image_root = authority["image_root"]
    rows: list[dict[str, Any]] = []
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
                "prior_path": str(resolve_image_path(image_root, prior_raw)),
                "current_path": str(resolve_image_path(image_root, current_raw)),
            }
        )
    class_counts = dict(
        sorted(Counter(str(row["progression"]) for row in rows).items())
    )
    expected_counts = dict(
        sorted(
            (str(label), int(value))
            for label, value in config["roster"][
                "evaluation_class_counts"
            ].items()
        )
    )
    if class_counts != expected_counts:
        raise ValueError("R51 evaluation class-count drift")
    result = {
        "schema": "visualvit.prta-gen.r51-fresh-evaluation-roster.v1",
        "status": config["result_statuses"]["roster_pass"],
        "protocol_id": config["protocol_id"],
        "namespace": config["roster"]["namespace"],
        "assignment": config["roster"]["assignment"],
        "partitions": {
            "evaluation": {
                "rows": rows,
                "row_count": len(rows),
                "patient_count": len({str(row["patient_id"]) for row in rows}),
                "progression_class_counts": class_counts,
            }
        },
        "inventory": inventory,
        "excluded_r45_patient_count": len(authority["r45_patients"]),
        "excluded_r45_patients_absent": True,
        "excluded_r44a_patients_absent": True,
        "excluded_gold_patients_absent": True,
        "remaining_resolved_patient_reserve": inventory[
            "remaining_resolved_patient_reserve"
        ],
        "patient_sets_disjoint": True,
        "one_row_per_patient": True,
        "selected_images_complete": True,
        "resplit_allowed": False,
        "silver_labels_used_for_preregistered_balanced_stratification": True,
        "evaluation_model_outcomes_read": False,
        "protected_300_dev_read": False,
        "revealed_483_test_read": False,
        "gold_outcomes_read": False,
        "external_outcomes_read": False,
        "scientific_claim_allowed": False,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Freeze the fresh R51 evaluation roster")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    if args.preflight_only:
        if args.output is not None:
            raise ValueError("R51 roster preflight does not accept --output")
        result = preflight(args.config)
    else:
        if args.output is None:
            raise ValueError("R51 roster build requires --output")
        result = build_roster(args.config, args.output)
    print(json.dumps(receipt_summary(result), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
