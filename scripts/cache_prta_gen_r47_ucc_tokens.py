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
from scripts.build_prta_gen_r47_ucc_roster import (
    preflight as roster_preflight,
    validate_authority as validate_roster_authority,
)
import scripts.cache_prta_gen_r45_cdeb_tokens as r45_cache
from scripts.r37c_common import checkpoint_for, load_candidate


CONFIG_STATUS = "FROZEN_PRTA_GEN_R47_UCC_DISCOVERY"


def validate_config_and_roster(
    config_path: Path,
    *,
    require_token_root_fresh: bool,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    config = read_json(config_path)
    if config.get("status") != CONFIG_STATUS:
        raise PermissionError("R47 cache config is not frozen")
    authority = config["authority"]
    roster_config_path = WORKSPACE / authority["roster_config"]
    if (
        not roster_config_path.is_file()
        or roster_config_path.stat().st_size
        != int(authority["roster_config_bytes"])
        or sha256_file(roster_config_path)
        != authority["roster_config_sha256"]
    ):
        raise PermissionError("R47 roster-config authority drift")
    validate_roster_authority(read_json(roster_config_path))
    roster_path = Path(authority["roster"])
    if (
        not roster_path.is_file()
        or roster_path.stat().st_size != int(authority["roster_bytes"])
        or sha256_file(roster_path) != authority["roster_sha256"]
    ):
        raise PermissionError("R47 roster hash/size drift")
    roster = read_json(roster_path)
    if (
        roster.get("status") != authority["roster_status"]
        or roster.get("all_r45_and_r46_patients_absent_from_development")
        is not True
        or roster.get("selected_images_complete") is not True
        or roster.get("r45_qualification_outcomes_read") is not False
        or roster.get("r45_confirmation_outcomes_read") is not False
        or roster.get("gold_outcomes_read") is not False
        or roster.get("external_outcomes_read") is not False
    ):
        raise PermissionError("R47 roster receipt drift")
    rows = list(roster["partitions"]["development"]["rows"])
    if (
        config["cache"]["partitions"] != ["development"]
        or len(rows) != int(config["cache"]["expected_rows"])
        or len({str(row["patient_id"]) for row in rows}) != len(rows)
    ):
        raise ValueError("R47 cache row registry drift")
    token_root = Path(config["runtime"]["token_root"])
    if require_token_root_fresh and token_root.exists():
        raise FileExistsError("R47 token root must be fresh")
    return config, roster, rows


def preflight(config_path: Path) -> dict[str, Any]:
    config, _, rows = validate_config_and_roster(
        config_path, require_token_root_fresh=True
    )
    roster_receipt = roster_preflight(
        WORKSPACE / config["authority"]["roster_config"]
    )
    cache = config["cache"]
    candidate_path = WORKSPACE / cache["source_candidate"]
    if sha256_file(candidate_path) != cache["source_candidate_sha256"]:
        raise PermissionError("R47 PRTA candidate authority drift")
    candidate = load_candidate(candidate_path)
    if (
        not checkpoint_for(
            candidate,
            roster="a6",
            seed=int(cache["frozen_prta_seed"]),
        ).is_file()
        or not Path(cache["text_cache"]).is_file()
    ):
        raise FileNotFoundError("R47 checkpoint/text cache absent")
    return {
        "schema": "visualvit.prta-gen.r47-ucc-cache-preflight.v1",
        "status": config["result_statuses"]["cache_preflight_pass"],
        "protocol_id": config["protocol_id"],
        "roster_preflight_status": roster_receipt["status"],
        "selected_development_rows": len(rows),
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
            "schema": "visualvit.prta-gen.r47-ucc-development-token-cache.v1",
            "status": "PASS_PRTA_GEN_R47_UCC_DEVELOPMENT_TOKEN_CACHE",
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
        description="Preflight or cache R47 development exact64 tokens"
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--device")
    parser.add_argument("--preflight-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.preflight_only:
        result = preflight(args.config)
    else:
        if args.device is None:
            raise ValueError("R47 cache execution requires --device")
        result = cache_tokens(
            config_path=args.config,
            device_name=args.device,
        )
    print(json.dumps(receipt_summary(result), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
