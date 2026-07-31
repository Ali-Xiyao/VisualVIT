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
from scripts.run_prta_gen_r46_cea_discovery import classification_metrics


AGGREGATE_STATUS = "STOP_PRTA_GEN_R46_CEA_DISCOVERY"
SEEDS = (17, 29, 43)


def consensus_prediction(
    *,
    baseline: int,
    true_predictions: list[int],
    current_predictions: list[int],
    minimum_true_votes: int,
    minimum_causal_votes: int,
) -> tuple[int, bool]:
    if (
        len(true_predictions) != len(current_predictions)
        or len(true_predictions) != 3
    ):
        raise ValueError("R46 case-study consensus requires three Seeds")
    counts = Counter(int(value) for value in true_predictions)
    candidate, votes = sorted(
        counts.items(), key=lambda item: (-item[1], item[0])
    )[0]
    causal_votes = sum(
        int(current) != candidate for current in current_predictions
    )
    override = (
        votes >= minimum_true_votes
        and causal_votes >= minimum_causal_votes
        and candidate != int(baseline)
    )
    return (candidate if override else int(baseline)), override


def _rule_metrics(
    *,
    rows: list[dict[str, Any]],
    targets: list[int],
    baseline_predictions: list[int],
    true_by_seed: dict[int, list[int]],
    current_by_seed: dict[int, list[int]],
    minimum_true_votes: int,
    minimum_causal_votes: int,
) -> dict[str, Any]:
    predictions = []
    overrides = []
    for index, baseline in enumerate(baseline_predictions):
        prediction, override = consensus_prediction(
            baseline=int(baseline),
            true_predictions=[
                int(true_by_seed[seed][index]) for seed in SEEDS
            ],
            current_predictions=[
                int(current_by_seed[seed][index]) for seed in SEEDS
            ],
            minimum_true_votes=minimum_true_votes,
            minimum_causal_votes=minimum_causal_votes,
        )
        predictions.append(prediction)
        overrides.append(override)
    recovered = sum(
        override and baseline != target and prediction == target
        for target, baseline, prediction, override in zip(
            targets,
            baseline_predictions,
            predictions,
            overrides,
            strict=True,
        )
    )
    regressed = sum(
        override and baseline == target and prediction != target
        for target, baseline, prediction, override in zip(
            targets,
            baseline_predictions,
            predictions,
            overrides,
            strict=True,
        )
    )
    changed = sum(
        prediction != baseline
        for prediction, baseline in zip(
            predictions, baseline_predictions, strict=True
        )
    )
    return {
        "minimum_true_votes": minimum_true_votes,
        "minimum_causal_votes": minimum_causal_votes,
        "metrics": classification_metrics(rows, predictions),
        "override_count": sum(overrides),
        "override_rate": sum(overrides) / len(overrides),
        "changed_count": changed,
        "recovered_count": recovered,
        "regressed_count": regressed,
        "net_recovery": recovered - regressed,
        "predictions": predictions,
    }


def analyze(
    *,
    config_path: Path,
    aggregate_path: Path,
    output_path: Path,
) -> dict[str, Any]:
    if output_path.exists():
        raise FileExistsError("R46 case-study output must be fresh")
    config = read_json(config_path)
    aggregate = read_json(aggregate_path)
    if (
        aggregate.get("status") != AGGREGATE_STATUS
        or aggregate.get("qualification_unlocked") is not False
        or aggregate.get("confirmation_unlocked") is not False
        or aggregate.get("r45_qualification_outcomes_read") is not False
        or aggregate.get("r45_confirmation_outcomes_read") is not False
    ):
        raise PermissionError("R46 terminal aggregate boundary drift")
    root = Path(config["runtime"]["discovery_root"])
    baseline = read_json(root / "baseline" / "result.json")
    seed_results = {
        seed: read_json(root / f"seed_{seed}" / "result.json")
        for seed in SEEDS
    }
    selected_key = str(aggregate["selected_quantile_key"])
    for result in seed_results.values():
        if (
            result.get("status") != config["result_statuses"]["seed_complete"]
            or result.get("targets") != baseline["targets"]
            or result.get("development_example_ids")
            != baseline["development_example_ids"]
        ):
            raise PermissionError("R46 case-study Seed alignment drift")
    roster = read_json(Path(config["authority"]["roster"]))
    rows = list(roster["partitions"]["development"]["rows"])
    if len(rows) != len(baseline["targets"]):
        raise ValueError("R46 case-study roster/result row-count drift")
    true_by_seed = {
        seed: seed_results[seed]["structured_predictions"]["true_pair"]
        for seed in SEEDS
    }
    current_by_seed = {
        seed: seed_results[seed]["structured_predictions"]["current_only"]
        for seed in SEEDS
    }
    shuffle_by_seed = {
        seed: seed_results[seed]["structured_predictions"]["prior_shuffle"]
        for seed in SEEDS
    }
    selected_cea_by_seed = {
        seed: seed_results[seed]["arbitration_candidates"][selected_key][
            "arms"
        ]["true_pair"]["predictions"]
        for seed in SEEDS
    }
    rule_specs = {
        "majority_true_majority_causal": (2, 2),
        "unanimous_true_majority_causal": (3, 2),
        "unanimous_true_unanimous_causal": (3, 3),
    }
    rules = {
        name: _rule_metrics(
            rows=rows,
            targets=baseline["targets"],
            baseline_predictions=baseline["predictions"]["true_pair"],
            true_by_seed=true_by_seed,
            current_by_seed=current_by_seed,
            minimum_true_votes=spec[0],
            minimum_causal_votes=spec[1],
        )
        for name, spec in rule_specs.items()
    }
    shuffle_rules = {
        name: _rule_metrics(
            rows=rows,
            targets=baseline["targets"],
            baseline_predictions=baseline["predictions"]["prior_shuffle"],
            true_by_seed=shuffle_by_seed,
            current_by_seed=current_by_seed,
            minimum_true_votes=spec[0],
            minimum_causal_votes=spec[1],
        )
        for name, spec in rule_specs.items()
    }
    baseline_predictions = baseline["predictions"]["true_pair"]
    targets = baseline["targets"]
    any_cea_change = [
        any(
            selected_cea_by_seed[seed][index] != baseline_predictions[index]
            for seed in SEEDS
        )
        for index in range(len(targets))
    ]
    unanimous_structured = sum(
        len({true_by_seed[seed][index] for seed in SEEDS}) == 1
        for index in range(len(targets))
    )
    unanimous_cea = sum(
        len({selected_cea_by_seed[seed][index] for seed in SEEDS}) == 1
        for index in range(len(targets))
    )
    result = {
        "schema": "visualvit.prta-gen.r46-cea-failure-case-study.v1",
        "status": "DESCRIPTIVE_PRTA_GEN_R46_CEA_FAILURE_CASE_STUDY",
        "protocol_id": config["protocol_id"],
        "aggregate_path": str(aggregate_path),
        "aggregate_bytes": aggregate_path.stat().st_size,
        "aggregate_sha256": sha256_file(aggregate_path),
        "rows": len(targets),
        "seeds": list(SEEDS),
        "selected_quantile": aggregate["selected_quantile"],
        "baseline_true_macro_f1": baseline["metrics"]["true_pair"]["macro_f1"],
        "unanimous_structured_count": unanimous_structured,
        "unanimous_structured_rate": unanimous_structured / len(targets),
        "unanimous_selected_cea_count": unanimous_cea,
        "unanimous_selected_cea_rate": unanimous_cea / len(targets),
        "any_selected_cea_change_count": sum(any_cea_change),
        "any_selected_cea_change_rate": sum(any_cea_change) / len(targets),
        "rules": {
            name: {
                key: value
                for key, value in payload.items()
                if key != "predictions"
            }
            for name, payload in rules.items()
        },
        "shuffle_rules": {
            name: {
                key: value
                for key, value in payload.items()
                if key != "predictions"
            }
            for name, payload in shuffle_rules.items()
        },
        "identities_written": False,
        "example_ids_written": False,
        "row_level_predictions_written": False,
        "model_training_started": False,
        "threshold_or_gate_changed": False,
        "qualification_unlocked": False,
        "confirmation_unlocked": False,
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run identity-free R46 CEA failure case study"
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--aggregate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = analyze(
        config_path=args.config,
        aggregate_path=args.aggregate,
        output_path=args.output,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
