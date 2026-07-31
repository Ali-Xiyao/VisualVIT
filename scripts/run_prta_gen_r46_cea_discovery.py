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

from scripts.audit_prta_gen_r44_independent_support import sha256_file
from scripts.build_prta_gen_r40b_smoke_cohort import read_json, write_json
from scripts.r39_common import token_bundle
from scripts.run_prta_gen_r40b_overfit_smoke import build_prompt_ids
from scripts.run_prta_gen_r40c_structured_generalization import (
    load_token_variants,
    train_head_arm,
)
from scripts.run_prta_gen_r45_cdeb_discovery import (
    _metrics as classification_metrics,
    evaluate as evaluate_generator,
)
from visualvit.cea import (
    arbitrate_predictions,
    jensen_shannon_causal_score,
)
from visualvit.prta_gen import (
    PROGRESSION_CLASSES,
    exact64_semantic_mean_features,
)
from visualvit.qwen_adapter import GenerativeVLMAdapter
from visualvit.tier_token_projector import TierTokenProjector


CONFIG_STATUS = "FROZEN_PRTA_GEN_R46_CEA_DISCOVERY"
ARMS = ("true_pair", "current_only", "query_only", "prior_shuffle")
HEAD_ARMS = ("true_pair", "current_only", "prior_shuffle")


def _validate_file(
    spec: dict[str, Any],
    prefix: str,
    *,
    expected_status: str | None = None,
) -> tuple[Path, dict[str, Any] | None]:
    path = Path(spec[prefix])
    if (
        not path.is_file()
        or path.stat().st_size != int(spec[f"{prefix}_bytes"])
        or sha256_file(path) != spec[f"{prefix}_sha256"]
    ):
        raise PermissionError(f"R46 {prefix} authority drift")
    payload = (
        read_json(path)
        if path.suffix.lower() == ".json"
        else None
    )
    if expected_status is not None and (
        payload is None or payload.get("status") != expected_status
    ):
        raise PermissionError(f"R46 {prefix} status drift")
    return path, payload


def validate_authority(
    config: dict[str, Any],
    *,
    require_development_cache: bool,
) -> dict[str, Any]:
    if config.get("status") != CONFIG_STATUS:
        raise PermissionError("R46 discovery config is not frozen")
    authority = config["authority"]
    _, roster = _validate_file(
        authority,
        "roster",
        expected_status=authority["roster_status"],
    )
    assert roster is not None
    if (
        roster.get("all_r45_patients_absent_from_development") is not True
        or roster.get("r45_development_outcomes_used") is not False
        or roster.get("r45_qualification_outcomes_read") is not False
        or roster.get("r45_confirmation_outcomes_read") is not False
    ):
        raise PermissionError("R46 development roster firewall drift")
    closed = config["closed_r45"]
    _, r45_roster = _validate_file(
        closed,
        "roster",
        expected_status=closed["roster_status"],
    )
    _, r45_aggregate = _validate_file(
        closed,
        "aggregate",
        expected_status=closed["aggregate_status"],
    )
    _, train_index = _validate_file(
        closed,
        "training_token_index",
        expected_status=closed["training_token_status"],
    )
    checkpoint_path, _ = _validate_file(
        closed, "baseline_projector_checkpoint"
    )
    assert (
        r45_roster is not None
        and r45_aggregate is not None
        and train_index is not None
    )
    if (
        r45_aggregate.get("qualification_unlocked") is not False
        or r45_aggregate.get("confirmation_unlocked") is not False
        or r45_aggregate.get("qualification_tokens_materialized") is not False
        or r45_aggregate.get("confirmation_tokens_materialized") is not False
        or r45_aggregate.get("qualification_outcomes_read") is not False
        or r45_aggregate.get("confirmation_outcomes_read") is not False
    ):
        raise PermissionError("R46 closed R45 firewall drift")
    training_rows = list(
        r45_roster["partitions"][closed["fit_partition"]]["rows"]
    )
    development_rows = list(roster["partitions"]["development"]["rows"])
    if (
        len(training_rows) != int(closed["fit_rows"])
        or len({str(row["patient_id"]) for row in training_rows})
        != int(closed["fit_patients"])
        or len(development_rows) != int(config["cache"]["expected_rows"])
    ):
        raise ValueError("R46 train/development row-count drift")
    train_patients = {str(row["patient_id"]) for row in training_rows}
    dev_patients = {str(row["patient_id"]) for row in development_rows}
    if train_patients & dev_patients:
        raise PermissionError("R46 train/development patient overlap")
    development_index = None
    if require_development_cache:
        source = config["source"]
        if any(
            source.get(key) is None
            for key in (
                "development_token_index",
                "development_token_index_bytes",
                "development_token_index_sha256",
            )
        ):
            raise PermissionError("R46 development token index is not pinned")
        _, development_index = _validate_file(
            source,
            "development_token_index",
            expected_status=source["required_development_token_status"],
        )
        assert development_index is not None
        if (
            development_index.get("rows") != len(development_rows)
            or development_index.get("cached_partitions") != ["development"]
            or development_index.get("labels_in_cache") is not False
            or development_index.get("sentences_in_cache") is not False
            or development_index.get("r45_qualification_tokens_materialized")
            is not False
            or development_index.get("r45_confirmation_tokens_materialized")
            is not False
        ):
            raise PermissionError("R46 development token receipt drift")
    return {
        "roster": roster,
        "r45_roster": r45_roster,
        "training_rows": training_rows,
        "development_rows": development_rows,
        "training_index": train_index,
        "development_index": development_index,
        "baseline_checkpoint": checkpoint_path,
    }


def _load_tokens(
    config: dict[str, Any], authority: dict[str, Any]
) -> dict[str, dict[str, Tensor]]:
    token_keys = {
        str(arm): str(key)
        for arm, key in config["source"]["token_variants"].items()
    }
    loaded: dict[str, dict[str, Tensor]] = {
        arm: {} for arm in token_keys
    }
    for rows_key, index_key in (
        ("training_rows", "training_index"),
        ("development_rows", "development_index"),
    ):
        rows = authority[rows_key]
        index = authority[index_key]
        assert index is not None
        subset, patients, findings = load_token_variants(
            index,
            example_ids={str(row["example_id"]) for row in rows},
            token_keys=token_keys,
        )
        for row in rows:
            example_id = str(row["example_id"])
            if (
                patients[example_id] != str(row["patient_id"])
                or findings[example_id] != str(row["finding"])
            ):
                raise ValueError("R46 roster/token alignment drift")
        for arm in token_keys:
            if set(loaded[arm]) & set(subset[arm]):
                raise ValueError("R46 duplicate token example across indices")
            loaded[arm].update(subset[arm])
    return loaded


def preflight(config_path: Path) -> dict[str, Any]:
    config = read_json(config_path)
    authority = validate_authority(
        config, require_development_cache=True
    )
    development_index = authority["development_index"]
    assert development_index is not None
    sampled = torch.load(
        development_index["shards"][0]["path"],
        map_location="cpu",
        weights_only=True,
    )
    sampled_rows = len(sampled["example_ids"])
    if (
        sampled_rows == 0
        or any(
            tuple(sampled[key].shape) != (sampled_rows, 64, 768)
            for key in (
                "true_tokens",
                "current_tokens",
                "shuffled_tokens",
            )
        )
    ):
        raise ValueError("R46 sampled development shard drift")
    checkpoint = torch.load(
        authority["baseline_checkpoint"],
        map_location="cpu",
        weights_only=True,
    )
    if (
        checkpoint.get("schema")
        != "visualvit.prta-gen.r45-cdeb-checkpoint.v1"
        or checkpoint.get("seed") != 17
        or checkpoint.get("method") != "baseline_projector"
        or len(checkpoint.get("projector", {})) != 12
    ):
        raise PermissionError("R46 inherited baseline checkpoint drift")
    baseline_root = Path(config["runtime"]["discovery_root"]) / "baseline"
    seeds = [int(value) for value in config["training"]["seeds"]]
    seed_roots = [
        Path(config["runtime"]["discovery_root"]) / f"seed_{seed}"
        for seed in seeds
    ]
    if baseline_root.exists() or any(path.exists() for path in seed_roots):
        raise FileExistsError("R46 discovery output must be fresh")
    model_path = Path(config["model"]["path"])
    if not model_path.is_dir():
        raise FileNotFoundError("R46 local Qwen model is absent")
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(
        model_path,
        local_files_only=True,
        trust_remote_code=False,
    )
    placeholder_id = int(
        tokenizer.convert_tokens_to_ids(config["model"]["sentinel_token"])
    )
    if placeholder_id != int(config["model"]["placeholder_token_id"]):
        raise ValueError("R46 sentinel token drift")
    return {
        "schema": "visualvit.prta-gen.r46-cea-runner-preflight.v1",
        "status": "PASS_PRTA_GEN_R46_CEA_RUNNER_PREFLIGHT",
        "protocol_id": config["protocol_id"],
        "training_rows": len(authority["training_rows"]),
        "development_rows": len(authority["development_rows"]),
        "seeds": seeds,
        "development_token_shards": development_index["shard_count"],
        "sampled_development_shard_rows": sampled_rows,
        "inherited_projector_tensors": len(checkpoint["projector"]),
        "local_qwen_present": True,
        "placeholder_token_id": placeholder_id,
        "all_outputs_fresh": True,
        "gpu_work_started": False,
        "r45_qualification_tokens_materialized": False,
        "r45_confirmation_tokens_materialized": False,
        "r45_qualification_outcomes_read": False,
        "r45_confirmation_outcomes_read": False,
        "gold_outcomes_read": False,
        "external_outcomes_read": False,
        "scientific_claim_allowed": False,
    }


def run_baseline(
    *, config_path: Path, device_name: str
) -> dict[str, Any]:
    config = read_json(config_path)
    authority = validate_authority(
        config, require_development_cache=True
    )
    output_root = Path(config["runtime"]["discovery_root"]) / "baseline"
    if output_root.exists():
        raise FileExistsError("R46 baseline output must be fresh")
    development_rows = authority["development_rows"]
    loaded = _load_tokens(config, authority)
    device = torch.device(device_name)
    if device.type != "cuda" or not torch.cuda.is_available():
        raise RuntimeError("R46 baseline requires explicit CUDA")
    torch.cuda.set_device(device)
    torch.cuda.reset_peak_memory_stats(device)
    from transformers import AutoTokenizer, Qwen3VLForConditionalGeneration

    tokenizer = AutoTokenizer.from_pretrained(
        config["model"]["path"],
        local_files_only=True,
        trust_remote_code=False,
    )
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token_id = tokenizer.eos_token_id
    placeholder_id = int(
        tokenizer.convert_tokens_to_ids(config["model"]["sentinel_token"])
    )
    model = Qwen3VLForConditionalGeneration.from_pretrained(
        config["model"]["path"],
        dtype=torch.bfloat16,
        attn_implementation=config["model"]["attention_implementation"],
        local_files_only=True,
        trust_remote_code=False,
        low_cpu_mem_usage=True,
    ).to(device)
    model.requires_grad_(False)
    model.config.use_cache = True
    projector = TierTokenProjector(
        input_dim=int(config["model"]["input_width"]),
        hidden_size=int(config["model"]["hidden_size"]),
    ).to(device)
    checkpoint = torch.load(
        authority["baseline_checkpoint"],
        map_location="cpu",
        weights_only=True,
    )
    projector.load_state_dict(checkpoint["projector"], strict=True)
    projector.requires_grad_(False)
    adapter = GenerativeVLMAdapter(
        model,
        placeholder_id,
        tokenizer=tokenizer,
        token_budget=int(config["model"]["token_budget"]),
    ).to(device)
    model_audit = adapter.trainable_parameter_audit()
    if int(model_audit["trainable_parameter_count"]) != 0:
        raise PermissionError("R46 inherited Qwen baseline is not frozen")
    first = development_rows[0]
    first_tokens = loaded["true_pair"][str(first["example_id"])]
    projected = projector(
        token_bundle(
            first_tokens.unsqueeze(0).to(device=device, dtype=torch.float32)
        )
    )
    prompt = build_prompt_ids(
        tokenizer, config, finding=str(first["finding"])
    ).to(device)
    cache_audit = adapter.audit_first_step_cache_equivalence(
        prompt, projected
    )
    if cache_audit["passed"] is not True:
        raise PermissionError("R46 baseline cache-equivalence drift")
    metrics, predictions, auxiliary = evaluate_generator(
        adapter=adapter,
        projector=projector,
        cdeb=None,
        bridge_enabled=False,
        tokenizer=tokenizer,
        config=config,
        rows=development_rows,
        loaded=loaded,
        device=device,
    )
    if auxiliary:
        raise PermissionError("R46 baseline produced unexpected auxiliary output")
    class_to_index = {
        label: index for index, label in enumerate(PROGRESSION_CLASSES)
    }
    result = {
        "schema": "visualvit.prta-gen.r46-cea-baseline.v1",
        "status": config["result_statuses"]["baseline_complete"],
        "protocol_id": config["protocol_id"],
        "study_tier": config["study_tier"],
        "classes": list(PROGRESSION_CLASSES),
        "development_patient_ids": [
            str(row["patient_id"]) for row in development_rows
        ],
        "development_example_ids": [
            str(row["example_id"]) for row in development_rows
        ],
        "targets": [
            class_to_index[str(row["progression"])]
            for row in development_rows
        ],
        "metrics": metrics,
        "predictions": predictions,
        "cache_equivalence_audit": cache_audit,
        "qwen_trainable_parameters": 0,
        "projector_trainable_parameters": 0,
        "inherited_projector_checkpoint_sha256": config["closed_r45"][
            "baseline_projector_checkpoint_sha256"
        ],
        "exact64_tokens_used": True,
        "free_greedy_generation_evaluated": True,
        "pixel_inputs_used": False,
        "r45_qualification_tokens_materialized": False,
        "r45_confirmation_tokens_materialized": False,
        "r45_qualification_outcomes_read": False,
        "r45_confirmation_outcomes_read": False,
        "gold_outcomes_read": False,
        "external_outcomes_read": False,
        "scientific_claim_allowed": False,
        "peak_cuda_allocated_bytes": torch.cuda.max_memory_allocated(device),
    }
    output_root.mkdir(parents=True, exist_ok=False)
    write_json(output_root / "result.json", result)
    return result


def _probabilities(
    head: torch.nn.Module,
    features: Tensor,
    mean: Tensor,
    std: Tensor,
    device: torch.device,
) -> Tensor:
    with torch.no_grad():
        normalized = (features - mean) / std
        return torch.softmax(head(normalized.to(device)), dim=-1).cpu()


def run_seed(
    *, config_path: Path, seed: int, device_name: str
) -> dict[str, Any]:
    config = read_json(config_path)
    seeds = [int(value) for value in config["training"]["seeds"]]
    if seed not in seeds:
        raise ValueError("R46 Seed is not registered")
    authority = validate_authority(
        config, require_development_cache=True
    )
    baseline_path = (
        Path(config["runtime"]["discovery_root"])
        / "baseline"
        / "result.json"
    )
    if not baseline_path.is_file():
        raise FileNotFoundError("R46 baseline must complete before head Seeds")
    baseline = read_json(baseline_path)
    if baseline.get("status") != config["result_statuses"]["baseline_complete"]:
        raise PermissionError("R46 baseline receipt drift")
    output_root = (
        Path(config["runtime"]["discovery_root"]) / f"seed_{seed}"
    )
    if output_root.exists():
        raise FileExistsError(f"R46 Seed output must be fresh: {output_root}")
    training_rows = authority["training_rows"]
    development_rows = authority["development_rows"]
    loaded = _load_tokens(config, authority)
    all_rows = training_rows + development_rows
    features = {
        arm: exact64_semantic_mean_features(
            torch.stack(
                [loaded[arm][str(row["example_id"])] for row in all_rows]
            )
        )
        for arm in HEAD_ARMS
    }
    class_to_index = {
        label: index for index, label in enumerate(PROGRESSION_CLASSES)
    }
    targets = torch.tensor(
        [class_to_index[str(row["progression"])] for row in all_rows],
        dtype=torch.long,
    )
    training_count = len(training_rows)
    device = torch.device(device_name)
    if device.type != "cuda" or not torch.cuda.is_available():
        raise RuntimeError("R46 structured head requires explicit CUDA")
    torch.cuda.set_device(device)
    torch.cuda.reset_peak_memory_stats(device)
    spec = config["training"]
    head, mean, std, true_predictions, audit = train_head_arm(
        training_features=features["true_pair"][:training_count],
        training_targets=targets[:training_count],
        development_features=features["true_pair"][training_count:],
        development_targets=targets[training_count:],
        seed=seed,
        hidden_width=int(config["head"]["hidden_width"]),
        class_count=int(config["head"]["class_count"]),
        epochs=int(spec["epochs"]),
        batch_size=int(spec["batch_size"]),
        learning_rate=float(spec["learning_rate"]),
        weight_decay=float(spec["weight_decay"]),
        gradient_clip_norm=float(spec["gradient_clip_norm"]),
        device=device,
    )
    if audit["updates"] != int(spec["expected_updates_per_seed"]):
        raise ValueError("R46 head update-count drift")
    train_probabilities = {
        arm: _probabilities(
            head,
            features[arm][:training_count],
            mean,
            std,
            device,
        )
        for arm in ("true_pair", "current_only")
    }
    development_probabilities = {
        arm: _probabilities(
            head,
            features[arm][training_count:],
            mean,
            std,
            device,
        )
        for arm in HEAD_ARMS
    }
    structured_predictions = {
        arm: [
            int(value)
            for value in probabilities.argmax(dim=-1).tolist()
        ]
        for arm, probabilities in development_probabilities.items()
    }
    if structured_predictions["true_pair"] != true_predictions:
        raise RuntimeError("R46 structured prediction reproducibility drift")
    train_scores = jensen_shannon_causal_score(
        train_probabilities["true_pair"],
        train_probabilities["current_only"],
    )
    development_scores = {
        arm: jensen_shannon_causal_score(
            probabilities,
            development_probabilities["current_only"],
        )
        for arm, probabilities in development_probabilities.items()
    }
    target_list = [int(value) for value in targets[training_count:].tolist()]
    structured_metrics = {
        arm: classification_metrics(
            development_rows, structured_predictions[arm]
        )
        for arm in HEAD_ARMS
    }
    candidates: dict[str, Any] = {}
    for raw_quantile in config["arbitration"][
        "candidate_override_coverage_quantiles"
    ]:
        quantile = float(raw_quantile)
        key = f"{quantile:.2f}"
        threshold = float(torch.quantile(train_scores, quantile).item())
        arms: dict[str, Any] = {}
        for arm in HEAD_ARMS:
            arbitration = arbitrate_predictions(
                baseline_predictions=[
                    int(value) for value in baseline["predictions"][arm]
                ],
                structured_predictions=structured_predictions[arm],
                scores=development_scores[arm],
                threshold=threshold,
            )
            arbitration["metrics"] = classification_metrics(
                development_rows, arbitration["predictions"]
            )
            arms[arm] = arbitration
        arms["query_only"] = {
            "predictions": [
                int(value)
                for value in baseline["predictions"]["query_only"]
            ],
            "eligible": [False] * len(development_rows),
            "changed": [False] * len(development_rows),
            "eligible_coverage": 0.0,
            "actual_override_rate": 0.0,
            "low_evidence_baseline_agreement": 1.0,
            "metrics": baseline["metrics"]["query_only"],
        }
        candidates[key] = {
            "quantile": quantile,
            "threshold": threshold,
            "arms": arms,
        }
    output_root.mkdir(parents=True, exist_ok=False)
    checkpoint_path = output_root / "structured_head_checkpoint.pt"
    torch.save(
        {
            "schema": "visualvit.prta-gen.r46-cea-head-checkpoint.v1",
            "seed": seed,
            "head": head.state_dict(),
            "feature_mean": mean,
            "feature_std": std,
            "classes": list(PROGRESSION_CLASSES),
        },
        checkpoint_path,
    )
    result = {
        "schema": "visualvit.prta-gen.r46-cea-seed.v1",
        "status": config["result_statuses"]["seed_complete"],
        "protocol_id": config["protocol_id"],
        "study_tier": config["study_tier"],
        "seed": seed,
        "classes": list(PROGRESSION_CLASSES),
        "training_rows": len(training_rows),
        "training_patients": len(
            {str(row["patient_id"]) for row in training_rows}
        ),
        "development_rows": len(development_rows),
        "development_patients": len(
            {str(row["patient_id"]) for row in development_rows}
        ),
        "development_patient_ids": baseline["development_patient_ids"],
        "development_example_ids": baseline["development_example_ids"],
        "targets": target_list,
        "structured_predictions": structured_predictions,
        "structured_metrics": structured_metrics,
        "arbitration_candidates": candidates,
        "training_audit": audit,
        "parameter_count": sum(
            parameter.numel() for parameter in head.parameters()
        ),
        "checkpoint": str(checkpoint_path),
        "checkpoint_bytes": checkpoint_path.stat().st_size,
        "exact64_tokens_used": True,
        "qwen_loaded": False,
        "qwen_trainable_parameters": 0,
        "schema_validity": 1.0,
        "finding_echo_accuracy": 1.0,
        "r45_qualification_tokens_materialized": False,
        "r45_confirmation_tokens_materialized": False,
        "r45_qualification_outcomes_read": False,
        "r45_confirmation_outcomes_read": False,
        "gold_outcomes_read": False,
        "external_outcomes_read": False,
        "scientific_claim_allowed": False,
        "peak_cuda_allocated_bytes": torch.cuda.max_memory_allocated(device),
    }
    write_json(output_root / "result.json", result)
    return result


def receipt_summary(result: dict[str, Any]) -> dict[str, Any]:
    excluded = {
        "development_patient_ids",
        "development_example_ids",
        "targets",
        "predictions",
        "structured_predictions",
        "arbitration_candidates",
    }
    return {key: value for key, value in result.items() if key not in excluded}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run frozen R46 CEA baseline or structured-head Seed"
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
        if any(value is not None for value in (args.stage, args.seed, args.device)):
            raise ValueError("R46 preflight accepts only --config")
        result = preflight(args.config)
    elif args.stage == "baseline":
        if args.device is None or args.seed is not None:
            raise ValueError("R46 baseline requires --device and no --seed")
        result = run_baseline(
            config_path=args.config,
            device_name=args.device,
        )
    elif args.stage == "seed":
        if args.device is None or args.seed is None:
            raise ValueError("R46 Seed requires --device and --seed")
        result = run_seed(
            config_path=args.config,
            seed=args.seed,
            device_name=args.device,
        )
    else:
        raise ValueError("R46 requires --preflight-only or --stage")
    print(json.dumps(receipt_summary(result), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
