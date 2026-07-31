from __future__ import annotations

# ruff: noqa: E402

import argparse
import json
from pathlib import Path
import sys

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE))
sys.path.insert(0, str(WORKSPACE / "src"))

from scripts.run_prta_gen_r41a_progression_sft import (
    preflight,
    receipt_summary,
    run_arm,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Preflight or run one frozen R44A Seed/model arm"
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--roster", type=Path)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--model-arm")
    parser.add_argument("--device")
    parser.add_argument("--preflight-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.preflight_only:
        if any(
            value is not None
            for value in (
                args.roster,
                args.seed,
                args.model_arm,
                args.device,
            )
        ):
            raise ValueError("R44A preflight accepts only --config")
        result = preflight(args.config)
    else:
        if (
            args.roster is None
            or args.seed is None
            or args.model_arm is None
            or args.device is None
        ):
            raise ValueError(
                "R44A arm run requires roster, seed, model-arm, and device"
            )
        result = run_arm(
            config_path=args.config,
            roster_path=args.roster,
            seed=args.seed,
            model_arm=args.model_arm,
            device_name=args.device,
        )
    print(json.dumps(receipt_summary(result), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
