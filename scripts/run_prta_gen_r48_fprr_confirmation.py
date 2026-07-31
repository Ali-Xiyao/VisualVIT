from __future__ import annotations

# ruff: noqa: E402

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Callable

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE))
sys.path.insert(0, str(WORKSPACE / "src"))

from scripts.audit_prta_gen_r44_independent_support import sha256_file
from scripts.build_prta_gen_r40b_smoke_cohort import read_json, write_json
import scripts.run_prta_gen_r46_cea_discovery as r46


CONFIG_STATUS = "FROZEN_PRTA_GEN_R48_FPRR_CONFIRMATION"


def validate_authority(
    config: dict[str, Any],
    *,
    require_development_cache: bool,
) -> dict[str, Any]:
    if config.get("status") != CONFIG_STATUS:
        raise PermissionError("R48 confirmation config is not frozen")
    authority = config["authority"]
    roster_path = Path(authority["roster"])
    qualification_path = Path(authority["qualification_aggregate"])
    roster = read_json(roster_path)
    qualification = read_json(qualification_path)
    for path, prefix in (
        (roster_path, "roster"),
        (qualification_path, "qualification_aggregate"),
    ):
        if (
            path.stat().st_size != int(authority[f"{prefix}_bytes"])
            or sha256_file(path) != authority[f"{prefix}_sha256"]
        ):
            raise PermissionError(f"R48 confirmation {prefix} drift")
    if (
        roster.get("status") != authority["roster_status"]
        or qualification.get("status")
        != authority["qualification_aggregate_status"]
        or qualification.get("confirmation_unlocked") is not True
        or qualification.get("confirmation_tokens_materialized") is not False
        or qualification.get("confirmation_outcomes_read") is not False
    ):
        raise PermissionError("R48 confirmation unlock drift")
    closed = config["closed_r45"]
    train_index = read_json(Path(closed["training_token_index"]))
    for prefix in ("training_token_index", "baseline_projector_checkpoint"):
        path = Path(closed[prefix])
        if (
            path.stat().st_size != int(closed[f"{prefix}_bytes"])
            or sha256_file(path) != closed[f"{prefix}_sha256"]
        ):
            raise PermissionError(f"R48 confirmation {prefix} drift")
    training_rows = list(roster["partitions"]["train"]["rows"])
    development_rows = list(
        roster["partitions"][authority["evaluation_partition"]]["rows"]
    )
    development_index = None
    if require_development_cache:
        source = config["source"]
        if source["development_token_index"] is None:
            raise PermissionError("R48 confirmation token index is not pinned")
        path = Path(source["development_token_index"])
        if (
            path.stat().st_size != int(source["development_token_index_bytes"])
            or sha256_file(path) != source["development_token_index_sha256"]
        ):
            raise PermissionError("R48 confirmation token-index drift")
        development_index = read_json(path)
        if (
            development_index.get("status")
            != source["required_development_token_status"]
            or development_index.get("cached_partitions") != ["confirmation"]
            or development_index.get("rows") != len(development_rows)
        ):
            raise PermissionError("R48 confirmation token receipt drift")
    return {
        "roster": roster,
        "r45_roster": roster,
        "training_rows": training_rows,
        "development_rows": development_rows,
        "training_index": train_index,
        "development_index": development_index,
        "baseline_checkpoint": Path(closed["baseline_projector_checkpoint"]),
    }


def _call(
    function: Callable[..., dict[str, Any]], **kwargs: Any
) -> dict[str, Any]:
    original_status = r46.CONFIG_STATUS
    original_validator = r46.validate_authority
    r46.CONFIG_STATUS = CONFIG_STATUS
    r46.validate_authority = validate_authority
    try:
        return function(**kwargs)
    finally:
        r46.CONFIG_STATUS = original_status
        r46.validate_authority = original_validator


def preflight(config_path: Path) -> dict[str, Any]:
    result = _call(r46.preflight, config_path=config_path)
    result["schema"] = "visualvit.prta-gen.r48-fprr-confirmation-runner-preflight.v1"
    result["status"] = "PASS_PRTA_GEN_R48_FPRR_CONFIRMATION_RUNNER_PREFLIGHT"
    return result


def run(config_path: Path, device_name: str) -> dict[str, Any]:
    result = _call(
        r46.run_baseline,
        config_path=config_path,
        device_name=device_name,
    )
    result["schema"] = "visualvit.prta-gen.r48-fprr-confirmation-baseline.v1"
    result["qualification_outcomes_read"] = True
    result["confirmation_tokens_materialized"] = True
    result["confirmation_outcomes_read"] = True
    config = read_json(config_path)
    write_json(
        Path(config["runtime"]["discovery_root"]) / "baseline" / "result.json",
        result,
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Run frozen R48 confirmation")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--device")
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    result = (
        preflight(args.config)
        if args.preflight_only
        else run(args.config, str(args.device))
    )
    print(json.dumps(r46.receipt_summary(result), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
