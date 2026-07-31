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

from scripts.build_prta_gen_r40b_smoke_cohort import read_json, write_json
import scripts.run_prta_gen_r46_cea_discovery as r46


CONFIG_STATUS = "FROZEN_PRTA_GEN_R47_UCC_DISCOVERY"


def _with_r47_status(function: Callable[..., dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
    original = r46.CONFIG_STATUS
    r46.CONFIG_STATUS = CONFIG_STATUS
    try:
        return function(**kwargs)
    finally:
        r46.CONFIG_STATUS = original


def preflight(config_path: Path) -> dict[str, Any]:
    result = _with_r47_status(r46.preflight, config_path=config_path)
    result["schema"] = "visualvit.prta-gen.r47-ucc-runner-preflight.v1"
    result["status"] = "PASS_PRTA_GEN_R47_UCC_RUNNER_PREFLIGHT"
    return result


def run_baseline(
    *, config_path: Path, device_name: str
) -> dict[str, Any]:
    result = _with_r47_status(
        r46.run_baseline,
        config_path=config_path,
        device_name=device_name,
    )
    result["schema"] = "visualvit.prta-gen.r47-ucc-baseline.v1"
    config = read_json(config_path)
    output = Path(config["runtime"]["discovery_root"]) / "baseline" / "result.json"
    write_json(output, result)
    return result


def run_seed(
    *, config_path: Path, seed: int, device_name: str
) -> dict[str, Any]:
    result = _with_r47_status(
        r46.run_seed,
        config_path=config_path,
        seed=seed,
        device_name=device_name,
    )
    result["schema"] = "visualvit.prta-gen.r47-ucc-seed.v1"
    config = read_json(config_path)
    output = (
        Path(config["runtime"]["discovery_root"])
        / f"seed_{seed}"
        / "result.json"
    )
    write_json(output, result)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run frozen R47 UCC baseline or structured-head Seed"
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--stage", choices=("baseline", "seed"))
    parser.add_argument("--seed", type=int)
    parser.add_argument("--device")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.preflight_only:
        result = preflight(args.config)
    elif args.stage == "baseline":
        if args.device is None:
            raise ValueError("R47 baseline requires --device")
        result = run_baseline(
            config_path=args.config,
            device_name=args.device,
        )
    elif args.stage == "seed":
        if args.device is None or args.seed is None:
            raise ValueError("R47 Seed requires --device and --seed")
        result = run_seed(
            config_path=args.config,
            seed=args.seed,
            device_name=args.device,
        )
    else:
        raise ValueError("R47 requires --preflight-only or --stage")
    print(json.dumps(r46.receipt_summary(result), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
