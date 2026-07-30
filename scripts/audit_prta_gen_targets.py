from __future__ import annotations

# ruff: noqa: E402

import argparse
from collections import Counter
import json
from pathlib import Path
import sys
from typing import Any, Iterable

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE / "src"))

from visualvit.cmcp import stable_hash
from visualvit.prta_gen import (
    ANATOMY_CLASSES,
    DEGREE_CLASSES,
    LATERALITY_CLASSES,
    PROGRESSION_CLASSES,
    ExplicitGenerativeTarget,
    extract_explicit_generative_target,
)


CONFIG_STATUS = "FROZEN_PRTA_GEN_R40_READINESS_V1"
ROSTER_STATUS = "READY_R40_OUTCOME_INDEPENDENT_ROSTER"
PASS_STATUS = "PASS_PRTA_GEN_R40A_TARGET_SUPPORT"
STOP_STATUS = "STOP_PRTA_GEN_R40A_TARGET_SUPPORT"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(
                json.dumps(
                    row,
                    sort_keys=True,
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                + "\n"
            )


def load_config(path: Path) -> dict[str, Any]:
    config = read_json(path)
    if config.get("status") != CONFIG_STATUS:
        raise PermissionError("PRTA-Gen R40 protocol is not frozen")
    firewall = config["firewall"]
    required_false = (
        "revealed_483_test_may_select_any_setting",
        "sealed_gold_or_external_may_be_read",
        "r37_1_observed_validation_may_select_any_setting",
        "source_hashes_recomputed",
        "per_shard_hashes_computed",
        "checkpoint_hashes_recomputed",
        "old_r40_component_queue_resumed",
    )
    drift = [key for key in required_false if firewall.get(key) is not False]
    if drift:
        raise PermissionError(f"PRTA-Gen firewall drift: {drift}")
    label_policy = config["r40a_information_audit"]["label_policy"]
    if (
        label_policy.get("source")
        != "literal current-report comparative sentence only"
        or label_policy.get("infer_from_finding_name") is not False
        or label_policy.get("llm_label_completion") is not False
        or label_policy.get("evidence_may_be_generated_when_source_sentence_missing")
        is not False
        or label_policy.get("unsupported_class_action")
        != "mark_field_unavailable_without_resplitting"
    ):
        raise PermissionError("PRTA-Gen literal-label policy drift")
    return config


def _target_row(
    pair_row: dict[str, Any],
    annotation: dict[str, Any],
    target: ExplicitGenerativeTarget,
) -> dict[str, Any]:
    return {
        "example_id": stable_hash(
            "r37-transition-example-v1",
            pair_row["pair_id"],
            target.finding,
            target.progression,
        ),
        "pair_id": str(pair_row["pair_id"]),
        "patient_id": str(pair_row["patient_id"]),
        "prior_dicom_id": str(pair_row["prior_dicom_id"]),
        "current_dicom_id": str(pair_row["current_dicom_id"]),
        "finding": target.finding,
        "progression": target.progression,
        "laterality": target.laterality,
        "anatomy": target.anatomy,
        "degree": target.degree,
        "evidence": target.evidence,
        "quality_tier": target.quality_tier,
        "literal_laterality": target.literal_laterality,
        "literal_anatomy": target.literal_anatomy,
        "literal_degree": target.literal_degree,
        "source_section": str(annotation.get("section", "")),
        "source_ruleset_version": str(annotation.get("ruleset_version", "")),
    }


def extract_partition_targets(
    rows: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    targets: list[dict[str, Any]] = []
    for pair_row in rows:
        for annotation in pair_row.get("transition_supervision", []):
            target = extract_explicit_generative_target(annotation)
            targets.append(_target_row(pair_row, annotation, target))
    return targets


def _counts(
    rows: list[dict[str, Any]], field: str, registry: tuple[str, ...]
) -> dict[str, int]:
    observed = Counter(str(row[field]) for row in rows)
    unknown = set(observed) - set(registry)
    if unknown:
        raise ValueError(f"unregistered {field} values: {sorted(unknown)}")
    return {label: observed[label] for label in registry}


def _support_decision(
    train_counts: dict[str, int],
    development_counts: dict[str, int],
    *,
    minimum_train: int,
    minimum_development: int,
    unspecified: str | None,
) -> dict[str, Any]:
    labels = [
        label
        for label in train_counts
        if unspecified is None or label != unspecified
    ]
    supported = [
        label
        for label in labels
        if train_counts[label] >= minimum_train
        and development_counts[label] >= minimum_development
    ]
    return {
        "supported_classes": supported,
        "unsupported_classes": [
            label for label in labels if label not in supported
        ],
        "minimum_training_rows_per_class": minimum_train,
        "minimum_development_rows_per_class": minimum_development,
        "probe_available": len(supported) >= 2,
    }


def audit_targets(
    *,
    config_path: Path,
    output_root: Path | None = None,
) -> dict[str, Any]:
    config = load_config(config_path)
    lineage = config["lineage"]
    source_root = Path(lineage["source_roster"])
    target_root = (
        Path(config["runtime"]["target_audit"])
        if output_root is None
        else Path(output_root)
    )
    if target_root.exists():
        raise FileExistsError(
            f"PRTA-Gen target-audit output must be fresh: {target_root}"
        )
    roster_audit = read_json(source_root / "r37_transition_audit.json")
    required_roster = {
        "status": lineage["required_roster_status"],
        "protocol_id": "r40-component-baseline-v1",
        "training_patients": int(lineage["training_patients"]),
        "development_patients": int(lineage["development_patients"]),
        "training_examples": int(lineage["training_examples"]),
        "development_examples": int(lineage["development_examples"]),
        "patient_disjoint": True,
        "previous_r37_1_validation_excluded": True,
        "protected_300_dev_read": False,
        "revealed_483_test_read": False,
        "gold_outcomes_read": False,
        "source_hashes_recomputed": False,
        "per_shard_hashes_computed": False,
        "checkpoint_hashes_recomputed": False,
    }
    observed_roster = {
        key: roster_audit.get(key) for key in required_roster
    }
    if observed_roster != required_roster:
        raise PermissionError(
            "PRTA-Gen source-roster/firewall drift: "
            f"expected {required_roster}, got {observed_roster}"
        )

    training_targets = extract_partition_targets(
        read_jsonl(source_root / "r37_pretrain_manifest.jsonl")
    )
    development_targets = extract_partition_targets(
        read_jsonl(
            source_root / "r37_internal_calibration_manifest.jsonl"
        )
    )
    if len(training_targets) != int(lineage["training_examples"]):
        raise ValueError("PRTA-Gen training example-count drift")
    if len(development_targets) != int(lineage["development_examples"]):
        raise ValueError("PRTA-Gen development example-count drift")
    training_patients = {row["patient_id"] for row in training_targets}
    development_patients = {row["patient_id"] for row in development_targets}
    if training_patients & development_patients:
        raise PermissionError("PRTA-Gen target partitions overlap by patient")

    registries = {
        "progression": PROGRESSION_CLASSES,
        "laterality": LATERALITY_CLASSES,
        "anatomy": ANATOMY_CLASSES,
        "degree": DEGREE_CLASSES,
    }
    counts: dict[str, Any] = {}
    policy = config["r40a_information_audit"]["label_policy"]
    minimum_train = int(policy["minimum_training_rows_per_explicit_class"])
    minimum_development = int(
        policy["minimum_development_rows_per_explicit_class"]
    )
    decisions: dict[str, Any] = {}
    for field, registry in registries.items():
        train_counts = _counts(training_targets, field, registry)
        development_counts = _counts(
            development_targets, field, registry
        )
        counts[field] = {
            "training": train_counts,
            "development": development_counts,
        }
        decisions[field] = _support_decision(
            train_counts,
            development_counts,
            minimum_train=minimum_train,
            minimum_development=minimum_development,
            unspecified=(
                None if field == "progression" else "Unspecified"
            ),
        )

    training_tiers = Counter(
        str(row["quality_tier"]) for row in training_targets
    )
    development_tiers = Counter(
        str(row["quality_tier"]) for row in development_targets
    )
    tier_a_support = (
        training_tiers["A"] >= int(policy["minimum_tier_a_training_rows"])
        and development_tiers["A"]
        >= int(policy["minimum_tier_a_development_rows"])
    )
    progression_ready = (
        not decisions["progression"]["unsupported_classes"]
        and decisions["progression"]["probe_available"]
    )
    status = PASS_STATUS if progression_ready else STOP_STATUS

    target_root.mkdir(parents=True)
    write_jsonl(target_root / "training_targets.jsonl", training_targets)
    write_jsonl(
        target_root / "development_targets.jsonl", development_targets
    )
    audit = {
        "schema": "visualvit.prta-gen.r40a-target-audit.v1",
        "status": status,
        "protocol_id": config["protocol_id"],
        "training_rows": len(training_targets),
        "development_rows": len(development_targets),
        "training_patients": len(training_patients),
        "development_patients": len(development_patients),
        "patient_disjoint": True,
        "counts": counts,
        "field_support": decisions,
        "quality_tier_counts": {
            "training": dict(sorted(training_tiers.items())),
            "development": dict(sorted(development_tiers.items())),
        },
        "tier_a_evidence_retrieval_probe_available": tier_a_support,
        "progression_probe_available": progression_ready,
        "field_generation_unlocked": {
            "progression": False,
            "laterality": False,
            "anatomy": False,
            "degree": False,
            "evidence": False,
        },
        "reason_fields_remain_locked": (
            "target support authorizes probe execution only; "
            "true-pair versus query-only/prior-shuffle results are not run"
        ),
        "protected_300_dev_read": False,
        "revealed_483_test_read": False,
        "gold_outcomes_read": False,
        "source_hashes_recomputed": False,
        "per_shard_hashes_computed": False,
        "checkpoint_hashes_recomputed": False,
        "old_r40_component_queue_resumed": False,
        "scientific_claim_allowed": False,
    }
    write_json(target_root / "audit.json", audit)
    return audit


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit literal PRTA-Gen R40A target support"
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-root", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = audit_targets(
        config_path=args.config,
        output_root=args.output_root,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == PASS_STATUS else 2


if __name__ == "__main__":
    raise SystemExit(main())
