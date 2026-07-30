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

import torch
from torch import Tensor

from scripts.cache_prta_gen_r40a1_features import (
    CONFIG_STATUSES,
    FEATURE_STATUS,
    ROSTER_STATUSES,
    candidate_spec,
)
from scripts.cache_prta_gen_r40a_tokens import read_json, read_jsonl
from scripts.run_prta_gen_r40a_probe import (
    query_only_features,
    train_linear_probe,
)
from visualvit.qualification import macro_f1


RESULT_STATUS = "PASS_PRTA_GEN_R40A1_PROBE_SEED"
VARIANTS = ("true_pair", "current_only", "query_only", "prior_shuffle")
FEATURE_VARIANTS = ("true_pair", "current_only", "prior_shuffle")


def load_feature_rows(
    index_path: Path, *, candidate_name: str, expected_width: int
) -> tuple[list[str], list[str], list[str], dict[str, Tensor]]:
    index = read_json(index_path)
    if (
        index.get("status") != FEATURE_STATUS
        or index.get("candidate") != candidate_name
        or int(index.get("input_width", -1)) != expected_width
        or index.get("labels_in_cache") is not False
        or index.get("sentences_in_cache") is not False
        or index.get("discovery_outcomes_read") is not False
        or index.get("qualification_outcomes_read") is not False
        or index.get("revealed_483_test_read") is not False
        or index.get("gold_outcomes_read") is not False
    ):
        raise PermissionError("R40A.1 feature-cache firewall drift")
    example_ids: list[str] = []
    patient_ids: list[str] = []
    findings: list[str] = []
    features: dict[str, list[Tensor]] = {
        variant: [] for variant in FEATURE_VARIANTS
    }
    for shard_entry in index["shards"]:
        shard = torch.load(
            shard_entry["path"], map_location="cpu", weights_only=True
        )
        example_ids.extend(str(value) for value in shard["example_ids"])
        patient_ids.extend(str(value) for value in shard["patient_ids"])
        findings.extend(str(value) for value in shard["findings"])
        for variant in FEATURE_VARIANTS:
            tensor = shard[f"{variant}_features"]
            if tensor.ndim != 2 or tensor.shape[1] != expected_width:
                raise ValueError("R40A.1 feature shard width drift")
            features[variant].append(tensor)
    if len(example_ids) != int(index["rows"]):
        raise ValueError("R40A.1 feature-cache row-count drift")
    return (
        example_ids,
        patient_ids,
        findings,
        {key: torch.cat(value) for key, value in features.items()},
    )


def align_target_rows(
    *,
    example_ids: list[str],
    patient_ids: list[str],
    findings: list[str],
    target_path: Path,
) -> list[dict[str, Any]]:
    rows = read_jsonl(target_path)
    by_id = {str(row["example_id"]): row for row in rows}
    if len(by_id) != len(rows) or set(by_id) != set(example_ids):
        raise ValueError("R40A.1 target/feature registry drift")
    aligned = [by_id[example_id] for example_id in example_ids]
    if [str(row["patient_id"]) for row in aligned] != patient_ids:
        raise ValueError("R40A.1 target/feature patient-order drift")
    if [str(row["finding"]) for row in aligned] != findings:
        raise ValueError("R40A.1 target/feature finding-order drift")
    return aligned


def partition_indices(
    rows: list[dict[str, Any]], roster: dict[str, Any]
) -> dict[str, Tensor]:
    patient_to_partition = {
        str(patient_id): partition
        for partition, payload in roster["partitions"].items()
        for patient_id in payload["patient_ids"]
    }
    indices: dict[str, list[int]] = {
        "fit": [],
        "discovery": [],
        "qualification": [],
    }
    excluded = {
        str(value)
        for value in roster.get("excluded_parent_discovery", {}).get(
            "patient_ids", ()
        )
    }
    for index, row in enumerate(rows):
        patient_id = str(row["patient_id"])
        if patient_id not in patient_to_partition:
            if patient_id in excluded:
                continue
            raise ValueError("R40A.1 row patient absent from roster")
        indices[patient_to_partition[patient_id]].append(index)
    tensors = {
        key: torch.tensor(value, dtype=torch.long)
        for key, value in indices.items()
    }
    for partition, expected in roster["partitions"].items():
        if len(tensors[partition]) != int(expected["rows"]):
            raise ValueError("R40A.1 roster row-count drift")
    return tensors


def validate_qualification_selection(
    *,
    selection_path: Path | None,
    candidate_name: str,
    stage_tag: str,
) -> dict[str, Any]:
    if selection_path is None:
        raise PermissionError("qualification requires a selection receipt")
    selection = read_json(selection_path)
    if (
        selection.get("status")
        != f"SELECTED_PRTA_GEN_{stage_tag}_CANDIDATE"
        or selection.get("selected_candidate") != candidate_name
        or selection.get("qualification_unlocked") is not True
        or selection.get("qualification_outcomes_read") is not False
    ):
        raise PermissionError("R40A.1 qualification selection drift")
    return selection


def run_probe(
    *,
    config_path: Path,
    roster_path: Path,
    feature_index_path: Path,
    candidate_name: str,
    scope: str,
    seed: int,
    device_name: str,
    selection_path: Path | None = None,
) -> dict[str, Any]:
    config = read_json(config_path)
    if config.get("status") not in CONFIG_STATUSES:
        raise PermissionError("R40A.1 config is not frozen")
    if seed not in config["probe"]["seeds"]:
        raise ValueError("R40A.1 probe seed drift")
    if scope not in {"discovery", "qualification"}:
        raise ValueError("R40A.1 probe scope must be discovery/qualification")
    spec = candidate_spec(config, candidate_name)
    roster = read_json(roster_path)
    if (
        roster.get("status") not in ROSTER_STATUSES
        or roster.get("patient_sets_disjoint") is not True
        or roster.get("discovery_outcomes_read") is not False
        or roster.get("qualification_outcomes_read") is not False
        or roster.get("revealed_483_test_read") is not False
        or roster.get("gold_outcomes_read") is not False
    ):
        raise PermissionError("R40A.1 roster firewall drift")
    if scope == "qualification":
        validate_qualification_selection(
            selection_path=selection_path,
            candidate_name=candidate_name,
            stage_tag=str(config.get("stage_tag", "R40A1")),
        )

    example_ids, patient_ids, findings, feature_rows = load_feature_rows(
        feature_index_path,
        candidate_name=candidate_name,
        expected_width=int(spec["input_width"]),
    )
    rows = align_target_rows(
        example_ids=example_ids,
        patient_ids=patient_ids,
        findings=findings,
        target_path=Path(config["source"]["target_rows"]),
    )
    indices = partition_indices(rows, roster)
    class_names = tuple(str(value) for value in config["probe"]["classes"])
    class_to_index = {
        class_name: index for index, class_name in enumerate(class_names)
    }
    targets = torch.tensor(
        [class_to_index[str(row["progression"])] for row in rows],
        dtype=torch.long,
    )
    finding_registry = tuple(sorted(set(findings)))
    query_features = query_only_features(rows, finding_registry)
    feature_rows["query_only"] = query_features.to(torch.float16)
    fit_indices = indices["fit"]
    evaluation_indices = indices[scope]
    fit_targets = targets.index_select(0, fit_indices)
    evaluation_targets = targets.index_select(
        0, evaluation_indices
    ).tolist()
    device = torch.device(device_name)
    if device.type == "cuda":
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA requested but unavailable")
        torch.cuda.set_device(device)
    probe = config["probe"]
    predictions: dict[str, list[int]] = {}
    training_audits: dict[str, Any] = {}
    metrics: dict[str, float] = {}
    for variant_index, variant in enumerate(VARIANTS):
        variant_predictions, audit = train_linear_probe(
            feature_rows[variant].index_select(0, fit_indices),
            fit_targets,
            feature_rows[variant].index_select(0, evaluation_indices),
            class_count=len(class_names),
            seed=seed + 1000 * variant_index,
            epochs=int(probe["epochs"]),
            batch_size=int(probe["batch_size"]),
            learning_rate=float(probe["learning_rate"]),
            weight_decay=float(probe["weight_decay"]),
            device=device,
        )
        predictions[variant] = variant_predictions
        training_audits[variant] = audit
        metrics[f"{variant}_macro_f1"] = macro_f1(
            evaluation_targets,
            variant_predictions,
            class_count=len(class_names),
        )
    metrics["true_minus_current_pp"] = 100.0 * (
        metrics["true_pair_macro_f1"]
        - metrics["current_only_macro_f1"]
    )
    metrics["true_minus_query_pp"] = 100.0 * (
        metrics["true_pair_macro_f1"] - metrics["query_only_macro_f1"]
    )
    metrics["true_minus_shuffle_pp"] = 100.0 * (
        metrics["true_pair_macro_f1"]
        - metrics["prior_shuffle_macro_f1"]
    )
    selected_rows = [rows[index] for index in evaluation_indices.tolist()]
    output_root = (
        roster_path.parent
        / "probes"
        / candidate_name
        / scope
        / f"seed_{seed}"
    )
    if output_root.exists():
        raise FileExistsError(
            f"R40A.1 probe output must be fresh: {output_root}"
        )
    output_root.mkdir(parents=True)
    result = {
        "schema": "visualvit.prta-gen.r40a1-probe-seed.v1",
        "status": RESULT_STATUS,
        "protocol_id": config["protocol_id"],
        "candidate": candidate_name,
        "scope": scope,
        "seed": seed,
        "classes": class_names,
        "fit_rows": len(fit_indices),
        "evaluation_rows": len(evaluation_indices),
        "fit_patients": int(roster["partitions"]["fit"]["patients"]),
        "evaluation_patients": int(
            roster["partitions"][scope]["patients"]
        ),
        "patient_ids": [str(row["patient_id"]) for row in selected_rows],
        "example_ids": [str(row["example_id"]) for row in selected_rows],
        "targets": evaluation_targets,
        "predictions": predictions,
        "metrics": metrics,
        "training_audits": training_audits,
        "candidate_selected": False,
        "progression_generation_unlocked": False,
        "qualification_unlocked": False,
        "protected_300_dev_read": False,
        "revealed_483_test_read": False,
        "gold_outcomes_read": False,
        "old_r40a_development_used_for_selection": False,
        "old_r40_component_queue_resumed": False,
        "scientific_claim_allowed": False,
    }
    output_root.joinpath("result.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run one frozen PRTA-Gen R40A.1 probe Seed"
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--roster", type=Path, required=True)
    parser.add_argument("--feature-index", type=Path, required=True)
    parser.add_argument(
        "--candidate",
        choices=(
            "regional_moments_v1",
            "regional_cosine4_v1",
            "semantic_layout_means_v1",
            "semantic_layout_moments_v1",
        ),
        required=True,
    )
    parser.add_argument(
        "--scope", choices=("discovery", "qualification"), required=True
    )
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--device", required=True)
    parser.add_argument("--selection", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = run_probe(
        config_path=args.config,
        roster_path=args.roster,
        feature_index_path=args.feature_index,
        candidate_name=args.candidate,
        scope=args.scope,
        seed=args.seed,
        device_name=args.device,
        selection_path=args.selection,
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "candidate": result["candidate"],
                "scope": result["scope"],
                "seed": result["seed"],
                "metrics": result["metrics"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
