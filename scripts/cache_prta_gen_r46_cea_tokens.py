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
from scripts.build_prta_gen_r46_cea_roster import (
    preflight as roster_preflight,
    validate_authority as validate_roster_authority,
)
import scripts.cache_prta_gen_r45_cdeb_tokens as r45_cache
from scripts.r37c_common import checkpoint_for, load_candidate


CONFIG_STATUS = "FROZEN_PRTA_GEN_R46_CEA_DISCOVERY"


def validate_config_and_roster(
    config_path: Path,
    *,
    require_token_root_fresh: bool,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    config = read_json(config_path)
    if config.get("status") != CONFIG_STATUS:
        raise PermissionError("R46 CEA cache config is not frozen")
    authority = config["authority"]
    roster_config_path = WORKSPACE / authority["roster_config"]
    if (
        not roster_config_path.is_file()
        or roster_config_path.stat().st_size
        != int(authority["roster_config_bytes"])
        or sha256_file(roster_config_path)
        != authority["roster_config_sha256"]
    ):
        raise PermissionError("R46 roster-config authority drift")
    roster_config = read_json(roster_config_path)
    validate_roster_authority(roster_config)
    roster_path = Path(authority["roster"])
    if (
        not roster_path.is_file()
        or roster_path.stat().st_size != int(authority["roster_bytes"])
        or sha256_file(roster_path) != authority["roster_sha256"]
    ):
        raise PermissionError("R46 roster hash/size drift")
    roster = read_json(roster_path)
    if (
        roster.get("status") != authority["roster_status"]
        or roster.get("protocol_id") != config["protocol_id"]
        or roster.get("all_r45_patients_absent_from_development") is not True
        or roster.get("one_row_per_patient") is not True
        or roster.get("selected_images_complete") is not True
        or roster.get("resplit_allowed") is not False
        or roster.get("r45_development_outcomes_used") is not False
        or roster.get("r45_qualification_outcomes_read") is not False
        or roster.get("r45_confirmation_outcomes_read") is not False
        or roster.get("r45_qualification_tokens_materialized") is not False
        or roster.get("r45_confirmation_tokens_materialized") is not False
        or roster.get("gold_outcomes_read") is not False
        or roster.get("external_outcomes_read") is not False
    ):
        raise PermissionError("R46 roster receipt drift")
    if config["cache"]["partitions"] != ["development"]:
        raise PermissionError("R46 cache partition drift")
    rows = list(roster["partitions"]["development"]["rows"])
    if (
        len(rows) != int(config["cache"]["expected_rows"])
        or len({str(row["patient_id"]) for row in rows}) != len(rows)
    ):
        raise ValueError("R46 development cache row/patient count drift")
    token_root = Path(config["runtime"]["token_root"])
    if require_token_root_fresh and token_root.exists():
        raise FileExistsError("R46 development token root must be fresh")
    return config, roster, rows


def preflight(config_path: Path) -> dict[str, Any]:
    config, _, rows = validate_config_and_roster(
        config_path, require_token_root_fresh=True
    )
    roster_config_path = WORKSPACE / config["authority"]["roster_config"]
    roster_receipt = roster_preflight(roster_config_path)
    cache = config["cache"]
    candidate_path = WORKSPACE / cache["source_candidate"]
    if (
        not candidate_path.is_file()
        or sha256_file(candidate_path)
        != cache["source_candidate_sha256"]
    ):
        raise PermissionError("R46 PRTA candidate authority drift")
    candidate = load_candidate(candidate_path)
    checkpoint = checkpoint_for(
        candidate,
        roster="a6",
        seed=int(cache["frozen_prta_seed"]),
    )
    if not checkpoint.is_file() or not Path(cache["text_cache"]).is_file():
        raise FileNotFoundError("R46 PRTA checkpoint/text cache is absent")
    return {
        "schema": "visualvit.prta-gen.r46-cea-cache-preflight.v1",
        "status": config["result_statuses"]["cache_preflight_pass"],
        "protocol_id": config["protocol_id"],
        "roster_preflight_status": roster_receipt["status"],
        "selected_development_rows": len(rows),
        "cached_partitions": ["development"],
        "source_candidate_sha256": cache["source_candidate_sha256"],
        "prta_checkpoint_present": True,
        "text_cache_present": True,
        "token_root_fresh": True,
        "gpu_cache_started": False,
        "r45_qualification_tokens_materialized": False,
        "r45_confirmation_tokens_materialized": False,
        "r45_qualification_outcomes_read": False,
        "r45_confirmation_outcomes_read": False,
        "gold_outcomes_read": False,
        "external_outcomes_read": False,
        "scientific_claim_allowed": False,
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
            "schema": "visualvit.prta-gen.r46-cea-development-token-cache.v1",
            "status": "PASS_PRTA_GEN_R46_CEA_DEVELOPMENT_TOKEN_CACHE",
            "cached_partitions": ["development"],
            "r45_qualification_tokens_materialized": False,
            "r45_confirmation_tokens_materialized": False,
            "r45_qualification_outcomes_read": False,
            "r45_confirmation_outcomes_read": False,
        }
    )
    write_json(Path(result["shards"][0]["path"]).parents[1] / "index.json", result)
    return result


def receipt_summary(result: dict[str, Any]) -> dict[str, Any]:
    summary = dict(result)
    if "shards" in summary:
        summary["shards"] = {
            "count": len(result["shards"]),
            "rows": sum(int(value["rows"]) for value in result["shards"]),
            "bytes": sum(int(value["bytes"]) for value in result["shards"]),
        }
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Preflight or cache frozen R46 development exact64 tokens"
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--device")
    parser.add_argument("--preflight-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.preflight_only:
        if args.device is not None:
            raise ValueError("R46 cache preflight accepts only --config")
        result = preflight(args.config)
    else:
        if args.device is None:
            raise ValueError("R46 cache execution requires --device")
        result = cache_tokens(
            config_path=args.config,
            device_name=args.device,
        )
    print(json.dumps(receipt_summary(result), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
