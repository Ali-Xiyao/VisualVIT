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

from scripts.aggregate_prta_gen_r41a_progression_sft import (
    paired_patient_bootstrap_with_invalid,
)
from scripts.audit_prta_gen_r44_independent_support import sha256_file
from scripts.build_prta_gen_r40b_smoke_cohort import read_json, write_json
from scripts.run_prta_gen_r41a_progression_sft import (
    PROGRESSION_CLASSES,
    macro_f1,
    per_class_recall,
)


CONFIG_STATUS = "REGISTERED_POST_HOC_PRTA_GEN_R48_FPRR_POOLED_HELDOUT"


def _verify(path: Path, *, expected_bytes: int, expected_sha256: str) -> None:
    if (
        not path.is_file()
        or path.stat().st_size != expected_bytes
        or sha256_file(path) != expected_sha256
    ):
        raise PermissionError(f"pooled input drift: {path}")


def _metrics(
    *,
    targets: list[int],
    predictions: list[int],
    schema_validity: float,
    finding_echo_accuracy: float,
) -> dict[str, Any]:
    recalls = per_class_recall(
        targets, predictions, class_count=len(PROGRESSION_CLASSES)
    )
    return {
        "row_count": len(targets),
        "macro_f1": macro_f1(
            targets, predictions, class_count=len(PROGRESSION_CLASSES)
        ),
        "progression_accuracy": sum(
            target == prediction
            for target, prediction in zip(targets, predictions, strict=True)
        )
        / len(targets),
        "per_class_recall": {
            label: recalls[index]
            for index, label in enumerate(PROGRESSION_CLASSES)
        },
        "schema_validity": schema_validity,
        "finding_echo_accuracy": finding_echo_accuracy,
        "invalid_or_wrong_finding_predictions": sum(
            prediction < 0 for prediction in predictions
        ),
    }


def aggregate(config_path: Path) -> dict[str, Any]:
    config = read_json(config_path)
    if config.get("status") != CONFIG_STATUS:
        raise PermissionError("pooled config is not registered")
    output = Path(config["runtime"]["output"])
    if output.exists():
        raise FileExistsError("pooled aggregate must be fresh")
    baselines = []
    for item in config["inputs"]:
        baseline_path = Path(item["baseline"])
        aggregate_path = Path(item["aggregate"])
        _verify(
            baseline_path,
            expected_bytes=int(item["baseline_bytes"]),
            expected_sha256=str(item["baseline_sha256"]),
        )
        _verify(
            aggregate_path,
            expected_bytes=int(item["aggregate_bytes"]),
            expected_sha256=str(item["aggregate_sha256"]),
        )
        upstream = read_json(aggregate_path)
        if upstream.get("status") != item["aggregate_status"]:
            raise PermissionError("pooled upstream status drift")
        baseline = read_json(baseline_path)
        if len(baseline["development_example_ids"]) != int(item["rows"]):
            raise PermissionError("pooled row-count drift")
        baselines.append(baseline)
    patient_ids = [
        str(value)
        for baseline in baselines
        for value in baseline["development_patient_ids"]
    ]
    example_ids = [
        str(value)
        for baseline in baselines
        for value in baseline["development_example_ids"]
    ]
    targets = [
        int(value)
        for baseline in baselines
        for value in baseline["targets"]
    ]
    if (
        len(patient_ids) != 750
        or len(set(patient_ids)) != len(patient_ids)
        or len(set(example_ids)) != len(example_ids)
    ):
        raise PermissionError("pooled held-out identities are not disjoint")
    metrics = {}
    predictions: dict[str, list[int]] = {}
    for arm in config["arms"]:
        predictions[arm] = [
            int(value)
            for baseline in baselines
            for value in baseline["predictions"][arm]
        ]
        weighted_schema = sum(
            int(item["rows"]) * float(baseline["metrics"][arm]["schema_validity"])
            for item, baseline in zip(config["inputs"], baselines, strict=True)
        ) / len(targets)
        weighted_finding = sum(
            int(item["rows"])
            * float(baseline["metrics"][arm]["finding_echo_accuracy"])
            for item, baseline in zip(config["inputs"], baselines, strict=True)
        ) / len(targets)
        metrics[arm] = _metrics(
            targets=targets,
            predictions=predictions[arm],
            schema_validity=weighted_schema,
            finding_echo_accuracy=weighted_finding,
        )
    replicates = int(
        config["statistics"]["patient_cluster_bootstrap_replicates"]
    )
    seed = int(config["statistics"]["patient_cluster_bootstrap_seed"])
    comparisons = {}
    for offset, arm in enumerate(("prior_shuffle", "current_only")):
        comparisons[f"true_vs_{arm}"] = paired_patient_bootstrap_with_invalid(
            patient_ids=patient_ids,
            targets=targets,
            primary_predictions=predictions["true_pair"],
            control_predictions=predictions[arm],
            class_count=len(PROGRESSION_CLASSES),
            replicates=replicates,
            seed=seed + offset,
        )
    gate = config["original_gate_for_descriptive_reference_only"]
    checks = {
        "true_macro_f1": metrics["true_pair"]["macro_f1"]
        >= float(gate["true_macro_f1_at_least"]),
        "all_class_recall": min(
            metrics["true_pair"]["per_class_recall"].values()
        )
        >= float(gate["all_class_recall_at_least"]),
        "true_minus_prior_shuffle": comparisons[
            "true_vs_prior_shuffle"
        ]["effect_pp"]
        >= float(gate["true_minus_prior_shuffle_at_least_pp"]),
        "true_minus_prior_shuffle_ci95_lower": comparisons[
            "true_vs_prior_shuffle"
        ]["ci95_lower_pp"]
        > float(gate["true_minus_prior_shuffle_ci95_lower_above_pp"]),
        "true_minus_current_only": comparisons[
            "true_vs_current_only"
        ]["effect_pp"]
        >= float(gate["true_minus_current_only_at_least_pp"]),
        "true_minus_current_only_ci95_lower": comparisons[
            "true_vs_current_only"
        ]["ci95_lower_pp"]
        > float(gate["true_minus_current_only_ci95_lower_above_pp"]),
        "true_minus_query_only": 100.0
        * (
            metrics["true_pair"]["macro_f1"]
            - metrics["query_only"]["macro_f1"]
        )
        >= float(gate["true_minus_query_only_at_least_pp"]),
        "schema_validity": metrics["true_pair"]["schema_validity"]
        == float(gate["schema_validity"]),
        "finding_echo_accuracy": metrics["true_pair"]["finding_echo_accuracy"]
        == float(gate["finding_echo_accuracy"]),
    }
    pooled_positive = all(checks.values())
    result = {
        "schema": "visualvit.prta-gen.r48-fprr-pooled-heldout-aggregate.v1",
        "status": config["result_statuses"][
            "positive" if pooled_positive else "negative"
        ],
        "protocol_id": config["protocol_id"],
        "analysis_class": config["analysis_class"],
        "rows": len(targets),
        "patients": len(patient_ids),
        "patient_disjoint": True,
        "metrics": metrics,
        "comparisons": comparisons,
        "original_gate_descriptive_checks": checks,
        "original_gate_descriptive_pass": pooled_positive,
        "pooled_internal_signal_supported": pooled_positive,
        "qualification_status_preserved": config["inputs"][0][
            "aggregate_status"
        ],
        "confirmation_status_preserved": config["inputs"][1][
            "aggregate_status"
        ],
        "independent_confirmation_claim_allowed": False,
        "external_or_gold_claim_allowed": False,
        "scientific_claim_allowed": False,
    }
    write_json(output, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Pool R48 held-out predictions")
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(aggregate(args.config), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
