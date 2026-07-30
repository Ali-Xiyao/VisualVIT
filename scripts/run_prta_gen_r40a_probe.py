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
import torch.nn.functional as F

from scripts.cache_prta_gen_r40a_tokens import (
    CONFIG_STATUS,
    read_json,
    read_jsonl,
)
from scripts.r37c_common import load_candidate
from visualvit.prta_gen import LinearInformationProbe, exact64_summary_features
from visualvit.qualification import macro_f1


TOKEN_STATUS = "PASS_PRTA_GEN_R40A_TOKEN_CACHE"
RESULT_STATUS = "PASS_PRTA_GEN_R40A_PROBE_SEED"
VARIANTS = ("true_pair", "current_only", "prior_shuffle", "query_only")
TOKEN_KEYS = {
    "true_pair": "true_tokens",
    "current_only": "current_tokens",
    "prior_shuffle": "shuffled_tokens",
}


def validate_args(
    config: dict[str, Any], *, field: str, seed: int
) -> tuple[str, ...]:
    supported = config["supported_probe_classes"]
    if field not in supported:
        raise ValueError(f"unregistered PRTA-Gen probe field: {field}")
    if seed not in config["probe"]["seeds"]:
        raise ValueError("PRTA-Gen probe seed drift")
    classes = tuple(str(value) for value in supported[field])
    if len(classes) < 2 or len(set(classes)) != len(classes):
        raise ValueError("PRTA-Gen supported class registry drift")
    return classes


def load_token_features(
    index_path: Path,
) -> tuple[list[str], list[str], dict[str, Tensor]]:
    index = read_json(index_path)
    if (
        index.get("status") != TOKEN_STATUS
        or index.get("smoke_rows") != 0
        or index.get("labels_in_cache") is not False
        or index.get("sentences_in_cache") is not False
        or index.get("protected_300_dev_read") is not False
        or index.get("revealed_483_test_read") is not False
        or index.get("gold_outcomes_read") is not False
    ):
        raise PermissionError("PRTA-Gen formal token-cache firewall drift")
    example_ids: list[str] = []
    patient_ids: list[str] = []
    features: dict[str, list[Tensor]] = {
        variant: [] for variant in TOKEN_KEYS
    }
    for shard_entry in index["shards"]:
        shard = torch.load(
            shard_entry["path"], map_location="cpu", weights_only=True
        )
        example_ids.extend(str(value) for value in shard["example_ids"])
        patient_ids.extend(str(value) for value in shard["patient_ids"])
        for variant, key in TOKEN_KEYS.items():
            features[variant].append(
                exact64_summary_features(shard[key].float()).to(torch.float16)
            )
    if len(example_ids) != int(index["rows"]):
        raise ValueError("PRTA-Gen token-cache row-count drift")
    if len(set(example_ids)) != len(example_ids):
        raise ValueError("PRTA-Gen token-cache example IDs are not unique")
    return (
        example_ids,
        patient_ids,
        {key: torch.cat(parts) for key, parts in features.items()},
    )


def align_targets(
    example_ids: list[str],
    patient_ids: list[str],
    target_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    targets = {str(row["example_id"]): row for row in target_rows}
    if len(targets) != len(target_rows):
        raise ValueError("PRTA-Gen target example IDs are not unique")
    if set(example_ids) != set(targets):
        raise ValueError("PRTA-Gen token/target example IDs differ")
    aligned = [targets[example_id] for example_id in example_ids]
    if [str(row["patient_id"]) for row in aligned] != patient_ids:
        raise ValueError("PRTA-Gen token/target patient order drift")
    return aligned


def query_only_features(
    rows: list[dict[str, Any]], findings: tuple[str, ...]
) -> Tensor:
    finding_to_index = {finding: index for index, finding in enumerate(findings)}
    unknown = {str(row["finding"]) for row in rows} - set(findings)
    if unknown:
        raise ValueError(f"unregistered findings: {sorted(unknown)}")
    indices = torch.tensor(
        [finding_to_index[str(row["finding"])] for row in rows],
        dtype=torch.long,
    )
    return F.one_hot(indices, num_classes=len(findings)).float()


def select_field_rows(
    rows: list[dict[str, Any]],
    features: dict[str, Tensor],
    *,
    field: str,
    classes: tuple[str, ...],
) -> tuple[list[dict[str, Any]], dict[str, Tensor], Tensor]:
    class_to_index = {label: index for index, label in enumerate(classes)}
    selected_indices = [
        index
        for index, row in enumerate(rows)
        if str(row[field]) in class_to_index
    ]
    if not selected_indices:
        raise ValueError("PRTA-Gen probe has no supported target rows")
    index_tensor = torch.tensor(selected_indices, dtype=torch.long)
    selected_rows = [rows[index] for index in selected_indices]
    selected_features = {
        key: value.index_select(0, index_tensor)
        for key, value in features.items()
    }
    targets = torch.tensor(
        [class_to_index[str(row[field])] for row in selected_rows],
        dtype=torch.long,
    )
    return selected_rows, selected_features, targets


def train_linear_probe(
    training_features: Tensor,
    training_targets: Tensor,
    development_features: Tensor,
    *,
    class_count: int,
    seed: int,
    epochs: int,
    batch_size: int,
    learning_rate: float,
    weight_decay: float,
    device: torch.device,
) -> tuple[list[int], dict[str, Any]]:
    torch.manual_seed(seed)
    if device.type == "cuda":
        torch.cuda.manual_seed_all(seed)
    model = LinearInformationProbe(
        int(training_features.shape[1]), class_count
    ).to(device)
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=learning_rate,
        weight_decay=weight_decay,
    )
    generator = torch.Generator(device="cpu")
    generator.manual_seed(seed)
    model.train()
    last_loss = 0.0
    for _ in range(epochs):
        order = torch.randperm(
            len(training_targets), generator=generator
        )
        for start in range(0, len(order), batch_size):
            indices = order[start : start + batch_size]
            batch_features = training_features.index_select(
                0, indices
            ).to(device=device, dtype=torch.float32)
            batch_targets = training_targets.index_select(0, indices).to(
                device
            )
            optimizer.zero_grad(set_to_none=True)
            loss = F.cross_entropy(model(batch_features), batch_targets)
            loss.backward()
            optimizer.step()
            last_loss = float(loss.detach().cpu().item())
    model.eval()
    predictions: list[int] = []
    with torch.inference_mode():
        for start in range(0, len(development_features), batch_size):
            batch = development_features[start : start + batch_size].to(
                device=device, dtype=torch.float32
            )
            predictions.extend(model(batch).argmax(dim=-1).cpu().tolist())
    return predictions, {
        "epochs": epochs,
        "batch_size": batch_size,
        "last_training_batch_loss": last_loss,
        "trainable_parameters": sum(
            parameter.numel() for parameter in model.parameters()
        ),
    }


def run_probe(
    *,
    config_path: Path,
    field: str,
    seed: int,
    device_name: str,
) -> dict[str, Any]:
    config = read_json(config_path)
    if config.get("status") != CONFIG_STATUS:
        raise PermissionError("PRTA-Gen R40A probe config is not frozen")
    classes = validate_args(config, field=field, seed=seed)
    candidate = load_candidate(WORKSPACE / config["source_candidate"])
    findings = tuple(
        str(value) for value in candidate["frozen_model"]["finding_registry"]
    )
    token_root = Path(config["token_cache_root"])
    frozen_seed = int(config["frozen_prta_seed"])
    partitions: dict[str, Any] = {}
    for scope in ("training", "development"):
        example_ids, patient_ids, token_features = load_token_features(
            token_root
            / scope
            / f"seed_{frozen_seed}"
            / "formal"
            / "index.json"
        )
        target_rows = read_jsonl(
            Path(config["target_root"]) / f"{scope}_targets.jsonl"
        )
        aligned = align_targets(example_ids, patient_ids, target_rows)
        token_features["query_only"] = query_only_features(
            aligned, findings
        )
        selected_rows, selected_features, targets = select_field_rows(
            aligned,
            token_features,
            field=field,
            classes=classes,
        )
        partitions[scope] = {
            "rows": selected_rows,
            "features": selected_features,
            "targets": targets,
        }
    training_patients = {
        str(row["patient_id"]) for row in partitions["training"]["rows"]
    }
    development_patients = {
        str(row["patient_id"]) for row in partitions["development"]["rows"]
    }
    if training_patients & development_patients:
        raise PermissionError("PRTA-Gen probe partitions overlap by patient")

    device = torch.device(device_name)
    if device.type == "cuda":
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA requested but unavailable")
        torch.cuda.set_device(device)
    probe_config = config["probe"]
    predictions: dict[str, list[int]] = {}
    training_audits: dict[str, Any] = {}
    metrics: dict[str, float] = {}
    targets = partitions["development"]["targets"].tolist()
    for variant_index, variant in enumerate(VARIANTS):
        variant_predictions, audit = train_linear_probe(
            partitions["training"]["features"][variant],
            partitions["training"]["targets"],
            partitions["development"]["features"][variant],
            class_count=len(classes),
            seed=seed + 1000 * variant_index,
            epochs=int(probe_config["epochs"]),
            batch_size=int(probe_config["batch_size"]),
            learning_rate=float(probe_config["learning_rate"]),
            weight_decay=float(probe_config["weight_decay"]),
            device=device,
        )
        predictions[variant] = variant_predictions
        training_audits[variant] = audit
        metrics[f"{variant}_macro_f1"] = macro_f1(
            targets, variant_predictions, class_count=len(classes)
        )
    metrics["true_minus_current_pp"] = 100 * (
        metrics["true_pair_macro_f1"] - metrics["current_only_macro_f1"]
    )
    metrics["true_minus_query_pp"] = 100 * (
        metrics["true_pair_macro_f1"] - metrics["query_only_macro_f1"]
    )
    metrics["true_minus_shuffle_pp"] = 100 * (
        metrics["true_pair_macro_f1"] - metrics["prior_shuffle_macro_f1"]
    )

    output_root = (
        Path(config["token_cache_root"]).parent
        / "probes"
        / field
        / f"seed_{seed}"
    )
    if output_root.exists():
        raise FileExistsError(
            f"PRTA-Gen probe output must be fresh: {output_root}"
        )
    output_root.mkdir(parents=True)
    result = {
        "schema": "visualvit.prta-gen.r40a-probe-seed.v1",
        "status": RESULT_STATUS,
        "protocol_id": config["protocol_id"],
        "field": field,
        "classes": classes,
        "seed": seed,
        "training_rows": len(partitions["training"]["rows"]),
        "development_rows": len(partitions["development"]["rows"]),
        "training_patients": len(training_patients),
        "development_patients": len(development_patients),
        "patient_ids": [
            str(row["patient_id"])
            for row in partitions["development"]["rows"]
        ],
        "example_ids": [
            str(row["example_id"])
            for row in partitions["development"]["rows"]
        ],
        "targets": targets,
        "predictions": predictions,
        "metrics": metrics,
        "training_audits": training_audits,
        "field_generation_unlocked": False,
        "requires_three_seed_patient_bootstrap": True,
        "protected_300_dev_read": False,
        "revealed_483_test_read": False,
        "gold_outcomes_read": False,
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
        description="Run one frozen PRTA-Gen R40A information probe"
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument(
        "--field",
        choices=("progression", "laterality", "anatomy", "degree"),
        required=True,
    )
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--device", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = run_probe(
        config_path=args.config,
        field=args.field,
        seed=args.seed,
        device_name=args.device,
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "field": result["field"],
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
