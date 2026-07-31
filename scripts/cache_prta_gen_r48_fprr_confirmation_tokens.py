from __future__ import annotations

# ruff: noqa: E402

import argparse
import json
from pathlib import Path
import sys
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE))
sys.path.insert(0, str(WORKSPACE / "src"))

from scripts.audit_prta_gen_r44_independent_support import sha256_file
from scripts.build_prta_gen_r40b_smoke_cohort import read_json, write_json
import scripts.cache_prta_gen_r45_cdeb_tokens as r45_cache
from scripts.cache_prta_gen_r48_fprr_tokens import receipt_summary


CONFIG_STATUS = "FROZEN_PRTA_GEN_R48_FPRR_CONFIRMATION"


def validate_config_and_roster(
    config_path: Path,
    *,
    require_token_root_fresh: bool,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    config = read_json(config_path)
    if config.get("status") != CONFIG_STATUS:
        raise PermissionError("R48 confirmation config is not frozen")
    authority = config["authority"]
    receipts = (
        ("roster", authority["roster_status"]),
        ("closed_aggregate", authority["closed_aggregate_status"]),
        ("qualification_aggregate", authority["qualification_aggregate_status"]),
    )
    loaded: dict[str, dict[str, Any]] = {}
    for prefix, expected_status in receipts:
        path = Path(authority[prefix])
        if (
            not path.is_file()
            or path.stat().st_size != int(authority[f"{prefix}_bytes"])
            or sha256_file(path) != authority[f"{prefix}_sha256"]
        ):
            raise PermissionError(f"R48 confirmation {prefix} authority drift")
        loaded[prefix] = read_json(path)
        if loaded[prefix].get("status") != expected_status:
            raise PermissionError(
                f"R48 confirmation {prefix} status drift"
            )
    qualification = loaded["qualification_aggregate"]
    if (
        qualification.get("gate_passed") is not True
        or qualification.get("confirmation_unlocked") is not True
        or qualification.get("confirmation_tokens_materialized") is not False
        or qualification.get("confirmation_outcomes_read") is not False
    ):
        raise PermissionError("R48 confirmation is not cleanly unlocked")
    partition = authority["evaluation_partition"]
    if config["cache"]["partitions"] != [partition]:
        raise PermissionError("R48 confirmation cache partition drift")
    roster = loaded["roster"]
    rows = list(roster["partitions"][partition]["rows"])
    if (
        len(rows) != int(authority["expected_rows"])
        or len({str(row["patient_id"]) for row in rows}) != len(rows)
    ):
        raise ValueError("R48 confirmation row-count drift")
    token_root = Path(config["runtime"]["token_root"])
    if require_token_root_fresh and token_root.exists():
        raise FileExistsError("R48 confirmation token root must be fresh")
    return config, roster, rows


def preflight(config_path: Path) -> dict[str, Any]:
    config, _, rows = validate_config_and_roster(
        config_path, require_token_root_fresh=True
    )
    return {
        "schema": "visualvit.prta-gen.r48-fprr-confirmation-cache-preflight.v1",
        "status": config["result_statuses"]["cache_preflight_pass"],
        "protocol_id": config["protocol_id"],
        "confirmation_rows": len(rows),
        "token_root_fresh": True,
        "training_started": False,
        "qualification_outcomes_read": True,
        "confirmation_tokens_materialized": False,
        "confirmation_outcomes_read": False,
    }


def cache_tokens(*, config_path: Path, device_name: str) -> dict[str, Any]:
    original = r45_cache.validate_config_and_roster
    r45_cache.validate_config_and_roster = validate_config_and_roster
    try:
        result = r45_cache.cache_tokens(
            config_path=config_path,
            device_name=device_name,
        )
    finally:
        r45_cache.validate_config_and_roster = original
    result.update(
        {
            "schema": "visualvit.prta-gen.r48-fprr-confirmation-token-cache.v1",
            "status": "PASS_PRTA_GEN_R48_FPRR_CONFIRMATION_TOKEN_CACHE",
            "cached_partitions": ["confirmation"],
            "qualification_outcomes_read": True,
            "confirmation_tokens_materialized": True,
            "confirmation_outcomes_read": False,
        }
    )
    write_json(Path(result["shards"][0]["path"]).parents[1] / "index.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Cache R48 confirmation tokens")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--device")
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    result = (
        preflight(args.config)
        if args.preflight_only
        else cache_tokens(config_path=args.config, device_name=str(args.device))
    )
    print(json.dumps(receipt_summary(result), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
