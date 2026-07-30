from __future__ import annotations

# ruff: noqa: E402

import argparse
from collections import defaultdict
import json
from pathlib import Path
import sys
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE))
sys.path.insert(0, str(WORKSPACE / "src"))

import numpy as np

from scripts.cache_prta_gen_r40a_tokens import CONFIG_STATUS, read_json
from scripts.run_prta_gen_r40a_probe import RESULT_STATUS


CONTROLS = ("current_only", "query_only", "prior_shuffle")


def confusion_by_patient(
    patient_ids: list[str],
    targets: list[int],
    predictions: list[int],
    *,
    class_count: int,
) -> tuple[list[str], np.ndarray]:
    if not (len(patient_ids) == len(targets) == len(predictions)):
        raise ValueError("patient, target, and prediction lengths differ")
    patients = sorted(set(patient_ids))
    patient_to_index = {patient: index for index, patient in enumerate(patients)}
    matrices = np.zeros(
        (len(patients), class_count, class_count), dtype=np.int64
    )
    for patient, target, prediction in zip(
        patient_ids, targets, predictions
    ):
        if not 0 <= target < class_count or not 0 <= prediction < class_count:
            raise ValueError("target or prediction exceeds class registry")
        matrices[patient_to_index[patient], target, prediction] += 1
    return patients, matrices


def macro_f1_from_confusion(confusion: np.ndarray) -> float:
    scores = []
    for label in range(confusion.shape[0]):
        true_positive = float(confusion[label, label])
        false_positive = float(confusion[:, label].sum() - true_positive)
        false_negative = float(confusion[label, :].sum() - true_positive)
        denominator = (
            2.0 * true_positive + false_positive + false_negative
        )
        scores.append(
            0.0 if denominator == 0.0 else 2.0 * true_positive / denominator
        )
    return float(np.mean(scores))


def paired_patient_bootstrap(
    *,
    patient_ids: list[str],
    targets: list[int],
    true_predictions: list[int],
    control_predictions: list[int],
    class_count: int,
    replicates: int,
    seed: int,
) -> dict[str, Any]:
    patients, true_confusions = confusion_by_patient(
        patient_ids,
        targets,
        true_predictions,
        class_count=class_count,
    )
    control_patients, control_confusions = confusion_by_patient(
        patient_ids,
        targets,
        control_predictions,
        class_count=class_count,
    )
    if patients != control_patients:
        raise ValueError("paired bootstrap patient registries differ")
    rng = np.random.default_rng(seed)
    samples = rng.integers(
        0, len(patients), size=(replicates, len(patients))
    )
    effects = np.empty(replicates, dtype=np.float64)
    for index, sampled_patients in enumerate(samples):
        true_confusion = true_confusions[sampled_patients].sum(axis=0)
        control_confusion = control_confusions[sampled_patients].sum(axis=0)
        effects[index] = (
            macro_f1_from_confusion(true_confusion)
            - macro_f1_from_confusion(control_confusion)
        )
    point_effect = (
        macro_f1_from_confusion(true_confusions.sum(axis=0))
        - macro_f1_from_confusion(control_confusions.sum(axis=0))
    )
    lower, upper = np.quantile(effects, [0.025, 0.975])
    return {
        "effect_pp": 100.0 * point_effect,
        "ci95_lower_pp": 100.0 * float(lower),
        "ci95_upper_pp": 100.0 * float(upper),
        "replicates": replicates,
        "seed": seed,
        "unit": "patient_cluster",
        "patients": len(patients),
    }


def aggregate_field(
    *, config_path: Path, field: str
) -> dict[str, Any]:
    config = read_json(config_path)
    if config.get("status") != CONFIG_STATUS:
        raise PermissionError("PRTA-Gen R40A probe config is not frozen")
    if field not in config["supported_probe_classes"]:
        raise ValueError("unregistered PRTA-Gen field")
    seeds = [int(value) for value in config["probe"]["seeds"]]
    result_root = Path(config["token_cache_root"]).parent / "probes" / field
    seed_results = [
        read_json(result_root / f"seed_{seed}" / "result.json")
        for seed in seeds
    ]
    for seed, result in zip(seeds, seed_results):
        if (
            result.get("status") != RESULT_STATUS
            or result.get("field") != field
            or int(result.get("seed", -1)) != seed
            or result.get("field_generation_unlocked") is not False
            or result.get("revealed_483_test_read") is not False
            or result.get("gold_outcomes_read") is not False
        ):
            raise PermissionError("PRTA-Gen seed-result firewall drift")
    reference = seed_results[0]
    alignment_keys = ("patient_ids", "example_ids", "targets", "classes")
    for result in seed_results[1:]:
        if any(result[key] != reference[key] for key in alignment_keys):
            raise ValueError("PRTA-Gen seed result alignment drift")

    bootstrap_replicates = int(
        config["probe"]["patient_bootstrap_replicates"]
    )
    bootstrap_seed = int(config["probe"]["patient_bootstrap_seed"])
    comparisons: dict[str, Any] = defaultdict(dict)
    for result in seed_results:
        seed = str(result["seed"])
        for control in CONTROLS:
            comparisons[control][seed] = paired_patient_bootstrap(
                patient_ids=result["patient_ids"],
                targets=result["targets"],
                true_predictions=result["predictions"]["true_pair"],
                control_predictions=result["predictions"][control],
                class_count=len(result["classes"]),
                replicates=bootstrap_replicates,
                seed=bootstrap_seed,
            )
    required_controls = ("query_only", "prior_shuffle")
    passed = all(
        comparisons[control][str(seed)]["effect_pp"] > 0.0
        and comparisons[control][str(seed)]["ci95_lower_pp"] > 0.0
        for control in required_controls
        for seed in seeds
    )
    status = (
        "GO_PRTA_GEN_R40A_FIELD_INFORMATION"
        if passed
        else "STOP_PRTA_GEN_R40A_FIELD_INFORMATION"
    )
    output_path = result_root / "aggregate.json"
    if output_path.exists():
        raise FileExistsError(
            f"PRTA-Gen field aggregate must be fresh: {output_path}"
        )
    aggregate = {
        "schema": "visualvit.prta-gen.r40a-field-aggregate.v1",
        "status": status,
        "protocol_id": config["protocol_id"],
        "field": field,
        "classes": reference["classes"],
        "seeds": seeds,
        "comparisons": dict(comparisons),
        "required_controls": required_controls,
        "all_three_seeds_positive_and_ci_lower_above_zero": passed,
        "field_generation_unlocked": passed,
        "evidence_generation_unlocked": False,
        "protected_300_dev_read": False,
        "revealed_483_test_read": False,
        "gold_outcomes_read": False,
        "scientific_claim_allowed": False,
    }
    output_path.write_text(
        json.dumps(aggregate, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return aggregate


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Aggregate one PRTA-Gen R40A field"
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument(
        "--field",
        choices=("progression", "laterality", "anatomy", "degree"),
        required=True,
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = aggregate_field(config_path=args.config, field=args.field)
    print(json.dumps(result, indent=2, sort_keys=True))
    return (
        0
        if result["status"] == "GO_PRTA_GEN_R40A_FIELD_INFORMATION"
        else 2
    )


if __name__ == "__main__":
    raise SystemExit(main())
