from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-a", type=Path, required=True)
    parser.add_argument("--run-b", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    first = json.loads((args.run_a / "summary.json").read_text(encoding="utf-8"))
    second = json.loads((args.run_b / "summary.json").read_text(encoding="utf-8"))
    metric_keys = (
        "initial_loss",
        "final_step_loss",
        "final_eval_loss",
        "initial_accuracy",
        "final_accuracy",
        "original_accuracy",
        "order_swapped_accuracy",
        "assignment_intervention_l1",
        "null_intervention_l1",
    )
    checks = {
        "both_pass": first["status"] == second["status"] == "PASS",
        "config_equal": first["config"] == second["config"],
        "state_hash_equal": first["model_state_sha256"] == second["model_state_sha256"],
        "predictions_equal": first["predictions"] == second["predictions"],
        "targets_equal": first["targets"] == second["targets"],
        "metrics_exact_except_time": all(
            first["metrics"][key] == second["metrics"][key] for key in metric_keys
        ),
    }
    report = {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "evidence_class": "SURVIVAL_SYNTHETIC_REPRODUCTION",
        "formal_claim_allowed": False,
        "run_a": str(args.run_a.resolve()),
        "run_b": str(args.run_b.resolve()),
        "checks": checks,
        "state_sha256": first["model_state_sha256"],
        "metrics": {key: first["metrics"][key] for key in metric_keys},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps(report, sort_keys=True))
    return 0 if report["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
