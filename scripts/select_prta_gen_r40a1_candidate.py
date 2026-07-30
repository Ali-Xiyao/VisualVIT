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

from scripts.cache_prta_gen_r40a1_features import (
    CONFIG_STATUSES,
    ROSTER_STATUSES,
)
from scripts.cache_prta_gen_r40a_tokens import read_json


def select_candidate(
    *, config_path: Path, roster_path: Path
) -> dict[str, Any]:
    config = read_json(config_path)
    roster = read_json(roster_path)
    if config.get("status") not in CONFIG_STATUSES:
        raise PermissionError("R40A.1 config is not frozen")
    if (
        roster.get("status") not in ROSTER_STATUSES
        or roster.get("qualification_outcomes_read") is not False
        or roster.get("revealed_483_test_read") is not False
        or roster.get("gold_outcomes_read") is not False
    ):
        raise PermissionError("R40A.1 roster firewall drift")
    stage_tag = str(config.get("stage_tag", "R40A1"))
    go_status = f"GO_PRTA_GEN_{stage_tag}_DISCOVERY"
    stop_status = f"STOP_PRTA_GEN_{stage_tag}_DISCOVERY"
    selected: str | None = None
    aggregate_paths = []
    for candidate in config["candidate_order"]:
        name = str(candidate["name"])
        path = (
            roster_path.parent
            / "probes"
            / name
            / "discovery"
            / "aggregate.json"
        )
        if not path.exists():
            raise FileNotFoundError(
                f"ordered candidate aggregate not ready: {name}"
            )
        aggregate = read_json(path)
        if (
            aggregate.get("candidate") != name
            or aggregate.get("scope") != "discovery"
            or aggregate.get("progression_generation_unlocked") is not False
            or aggregate.get("qualification_unlocked") is not False
            or aggregate.get("revealed_483_test_read") is not False
            or aggregate.get("gold_outcomes_read") is not False
        ):
            raise PermissionError("R40A.1 discovery aggregate drift")
        aggregate_paths.append(str(path))
        if aggregate.get("status") == go_status:
            selected = name
            break
        if aggregate.get("status") != stop_status:
            raise ValueError("R40A.1 discovery aggregate status drift")
    status = (
        f"SELECTED_PRTA_GEN_{stage_tag}_CANDIDATE"
        if selected is not None
        else stop_status
    )
    return {
        "schema": "visualvit.prta-gen.r40a1-selection.v1",
        "status": status,
        "protocol_id": config["protocol_id"],
        "selection_rule": config["candidate_selection"]["rule"],
        "aggregate_paths_read_in_order": aggregate_paths,
        "selected_candidate": selected,
        "qualification_unlocked": selected is not None,
        "progression_generation_unlocked": False,
        "qualification_outcomes_read": False,
        "protected_300_dev_read": False,
        "revealed_483_test_read": False,
        "gold_outcomes_read": False,
        "old_r40a_development_used_for_selection": False,
        "scientific_claim_allowed": False,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Select the first passing PRTA-Gen R40A.1 candidate"
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--roster", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.output.exists():
        raise FileExistsError(
            f"R40A.1 selection output must be fresh: {args.output}"
        )
    result = select_candidate(
        config_path=args.config, roster_path=args.roster
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["qualification_unlocked"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
