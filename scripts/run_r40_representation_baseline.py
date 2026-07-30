from __future__ import annotations

# ruff: noqa: E402

import argparse
from collections import Counter
import json
from pathlib import Path
import random
import sys
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE))
sys.path.insert(0, str(WORKSPACE / "src"))

import torch
import torch.nn.functional as F

from scripts.cache_r37_block8_tokens import build_frozen_encoder
from scripts.run_r37_prta_smoke import (
    R40_CONFIG,
    R40_STATUS,
    batch_indices,
    flatten_partition,
    formal_partition,
    load_r40_config,
)
from visualvit.prta import FrozenBiomedCLIPDifference, PROGRESSION_LABELS
from visualvit.qualification import (
    FindingConditionedLinearProbe,
    macro_f1,
)
from visualvit.r37_cache import Block8CacheIndex


BASELINES = ("B0_frozen_a0", "B2_siamese_signed_abs")
SEEDS = (17, 29, 43)
EPOCHS = 100
BATCH_SIZE = 16
LEARNING_RATE = 1e-2


def validate_args(
    args: argparse.Namespace,
    config: dict[str, Any],
) -> None:
    expected = {
        "epochs": EPOCHS,
        "batch_size": BATCH_SIZE,
        "learning_rate": LEARNING_RATE,
        "max_train_examples": 0,
        "max_development_examples": 0,
    }
    observed = {key: getattr(args, key) for key in expected}
    if observed != expected:
        raise ValueError(
            f"R40 representation baseline drift: expected {expected}, "
            f"got {observed}"
        )
    if args.baseline not in BASELINES:
        raise ValueError(f"unregistered representation baseline: {args.baseline}")
    if args.seed not in SEEDS:
        raise ValueError(f"R40 baseline seed must be one of {SEEDS}")
    registered = config["strong_baselines"]
    if args.baseline not in registered:
        raise ValueError("R40 strong-baseline registry drift")


def validate_roster_audit(
    audit: dict[str, Any],
    config: dict[str, Any],
) -> None:
    required = {
        "status": R40_STATUS,
        "protocol_id": config["protocol_id"],
        "formal_training_unlocked": True,
        "patient_disjoint": True,
        "previous_r37_1_validation_excluded": True,
        "one_shot_development": True,
        "protected_300_dev_read": False,
        "revealed_483_test_read": False,
        "gold_outcomes_read": False,
        "source_hashes_recomputed": False,
        "per_shard_hashes_computed": False,
        "checkpoint_hashes_recomputed": False,
    }
    observed = {key: audit.get(key) for key in required}
    if observed != required:
        raise PermissionError(
            f"R40 representation roster/firewall drift: {observed}"
        )


def siamese_signed_abs_features(
    prior_cls: torch.Tensor,
    current_cls: torch.Tensor,
) -> torch.Tensor:
    if prior_cls.shape != current_cls.shape or prior_cls.ndim != 2:
        raise ValueError("R40 Siamese CLS tensors must have matching [B,D] shape")
    prior = F.normalize(prior_cls, dim=-1)
    current = F.normalize(current_cls, dim=-1)
    signed = current - prior
    absolute = signed.abs()
    return F.normalize(
        torch.cat((prior, current, signed, absolute), dim=-1),
        dim=-1,
    )


def frozen_a0_features(
    prior_cls: torch.Tensor,
    current_cls: torch.Tensor,
) -> torch.Tensor:
    if prior_cls.shape != current_cls.shape or prior_cls.ndim != 2:
        raise ValueError("R40 A0 CLS tensors must have matching [B,D] shape")
    return F.normalize(current_cls - prior_cls, dim=-1)


def extract_features(
    examples: list[dict[str, Any]],
    *,
    baseline: str,
    cache: Block8CacheIndex,
    frozen: FrozenBiomedCLIPDifference,
    device: torch.device,
    batch_size: int,
) -> dict[str, dict[str, torch.Tensor]]:
    result: dict[str, dict[str, torch.Tensor]] = {}
    with torch.inference_mode():
        for start, end in batch_indices(len(examples), batch_size):
            batch = examples[start:end]
            prior = cache.get_many(
                item["prior_dicom_id"] for item in batch
            ).to(device=device, dtype=torch.float32)
            current = cache.get_many(
                item["current_dicom_id"] for item in batch
            ).to(device=device, dtype=torch.float32)
            prior_cls = frozen.encode(prior)[:, 0]
            current_cls = frozen.encode(current)[:, 0]
            if baseline == "B0_frozen_a0":
                modes = {
                    "true_pair": frozen_a0_features(
                        prior_cls, current_cls
                    ),
                    "current_only": frozen_a0_features(
                        current_cls, current_cls
                    ),
                    "inverted": frozen_a0_features(
                        current_cls, prior_cls
                    ),
                }
            else:
                modes = {
                    "true_pair": siamese_signed_abs_features(
                        prior_cls, current_cls
                    ),
                    "current_only": siamese_signed_abs_features(
                        current_cls, current_cls
                    ),
                    "inverted": siamese_signed_abs_features(
                        current_cls, prior_cls
                    ),
                }
            for index, item in enumerate(batch):
                result[str(item["example_id"])] = {
                    mode: values[index].cpu()
                    for mode, values in modes.items()
                }
    return result


def tensors(
    examples: list[dict[str, Any]],
    features: dict[str, dict[str, torch.Tensor]],
    *,
    mode: str,
    finding_to_index: dict[str, int],
    label_to_index: dict[str, int],
    device: torch.device,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    values = torch.stack(
        [features[str(item["example_id"])][mode] for item in examples]
    ).to(device=device, dtype=torch.float32)
    finding_indices = torch.tensor(
        [finding_to_index[str(item["finding"])] for item in examples],
        dtype=torch.long,
        device=device,
    )
    labels = torch.tensor(
        [label_to_index[str(item["label"])] for item in examples],
        dtype=torch.long,
        device=device,
    )
    return values, finding_indices, labels


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run one frozen R40 representation baseline seed"
    )
    parser.add_argument("--config", type=Path, default=R40_CONFIG)
    parser.add_argument("--baseline", choices=BASELINES, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--device", required=True)
    parser.add_argument("--transition-root", type=Path, required=True)
    parser.add_argument("--cache-root", type=Path, required=True)
    parser.add_argument("--text-cache", type=Path, required=True)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--max-train-examples", type=int, default=0)
    parser.add_argument("--max-development-examples", type=int, default=0)
    parser.add_argument("--epochs", type=int, default=EPOCHS)
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    parser.add_argument("--learning-rate", type=float, default=LEARNING_RATE)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_r40_config(args.config)
    validate_args(args, config)
    audit = json.loads(
        (args.transition_root / "r37_transition_audit.json").read_text(
            encoding="utf-8"
        )
    )
    validate_roster_audit(audit, config)
    train_examples = formal_partition(
        flatten_partition(args.transition_root, "pretrain"),
        expected_count=int(audit["training_examples"]),
    )
    development_examples = formal_partition(
        flatten_partition(args.transition_root, "internal_calibration"),
        expected_count=int(audit["development_examples"]),
    )
    output_root = (
        Path(config["strong_baselines"]["output_root"])
        / args.baseline
        / f"seed_{args.seed}"
        if args.output_root is None
        else args.output_root
    )
    if output_root.exists():
        raise FileExistsError(f"R40 baseline output must be fresh: {output_root}")

    random.seed(args.seed)
    torch.manual_seed(args.seed)
    device = torch.device(args.device)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but unavailable")
    text_cache = torch.load(
        args.text_cache, map_location="cpu", weights_only=True
    )
    findings = [str(value) for value in text_cache["findings"]]
    labels = [str(value) for value in text_cache["labels"]]
    if tuple(labels) != PROGRESSION_LABELS or len(findings) != 12:
        raise ValueError("R40 finding/label registry drift")
    finding_to_index = {
        value: index for index, value in enumerate(findings)
    }
    label_to_index = {value: index for index, value in enumerate(labels)}

    cache = Block8CacheIndex(args.cache_root, maximum_loaded_shards=4)
    encoder = build_frozen_encoder(device)
    frozen = FrozenBiomedCLIPDifference(
        list(encoder.blocks[8:]), final_norm=encoder.norm
    ).to(device)
    del encoder
    selected = train_examples + development_examples
    features = extract_features(
        selected,
        baseline=args.baseline,
        cache=cache,
        frozen=frozen,
        device=device,
        batch_size=args.batch_size,
    )
    train_x, train_finding, train_y = tensors(
        train_examples,
        features,
        mode="true_pair",
        finding_to_index=finding_to_index,
        label_to_index=label_to_index,
        device=device,
    )
    feature_dim = int(train_x.shape[-1])
    expected_dim = 768 if args.baseline == "B0_frozen_a0" else 3072
    if feature_dim != expected_dim:
        raise ValueError(
            f"R40 baseline feature width drift: {feature_dim} != {expected_dim}"
        )
    probe = FindingConditionedLinearProbe(
        feature_dim=feature_dim,
        finding_count=len(findings),
        class_count=len(labels),
    ).to(device)
    optimizer = torch.optim.AdamW(
        probe.parameters(), lr=args.learning_rate, weight_decay=0.01
    )
    history = []
    for epoch in range(args.epochs):
        probe.train()
        logits = probe(train_x, train_finding)
        loss = F.cross_entropy(logits, train_y)
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        optimizer.step()
        history.append({"epoch": epoch, "loss": float(loss.detach().cpu())})

    predictions: dict[str, list[int]] = {}
    metrics: dict[str, float] = {}
    targets: list[int] = []
    probe.eval()
    with torch.inference_mode():
        for mode in ("true_pair", "current_only", "inverted"):
            values, finding_index, labels_tensor = tensors(
                development_examples,
                features,
                mode=mode,
                finding_to_index=finding_to_index,
                label_to_index=label_to_index,
                device=device,
            )
            predicted = probe(values, finding_index).argmax(dim=-1).cpu().tolist()
            if not targets:
                targets = labels_tensor.cpu().tolist()
            predictions[mode] = predicted
            metrics[f"{mode}_macro_f1"] = macro_f1(
                targets, predicted, class_count=len(labels)
            )
    metrics["true_minus_current_pp"] = 100 * (
        metrics["true_pair_macro_f1"] - metrics["current_only_macro_f1"]
    )
    metrics["true_minus_inverted_pp"] = 100 * (
        metrics["true_pair_macro_f1"] - metrics["inverted_macro_f1"]
    )
    result = {
        "schema": "visualvit.r40.representation-baseline-seed.v1",
        "status": "PASS_R40_REPRESENTATION_BASELINE_SEED",
        "protocol_id": config["protocol_id"],
        "baseline": args.baseline,
        "seed": args.seed,
        "formal": True,
        "scientific_claim_allowed": False,
        "train_examples": len(train_examples),
        "development_examples": len(development_examples),
        "feature_dim": feature_dim,
        "probe_trainable_parameters": sum(
            parameter.numel() for parameter in probe.parameters()
        ),
        "backbone_trainable_parameters": sum(
            parameter.numel()
            for parameter in frozen.parameters()
            if parameter.requires_grad
        ),
        "train_label_counts": dict(
            Counter(str(item["label"]) for item in train_examples)
        ),
        "development_label_counts": dict(
            Counter(str(item["label"]) for item in development_examples)
        ),
        "metrics": metrics,
        "predictions": predictions,
        "target_labels": targets,
        "development_patient_ids": [
            str(item["patient_id"]) for item in development_examples
        ],
        "history": history,
        "protected_300_dev_read": False,
        "revealed_483_test_read": False,
        "gold_outcomes_read": False,
        "source_hashes_recomputed": False,
        "per_shard_hashes_computed": False,
        "checkpoint_hashes_recomputed": False,
    }
    output_root.mkdir(parents=True, exist_ok=False)
    (output_root / "result.json").write_text(
        json.dumps(result, indent=2, sort_keys=True), encoding="utf-8"
    )
    torch.save(
        {
            "probe_state_dict": probe.state_dict(),
            "baseline": args.baseline,
            "seed": args.seed,
            "protocol_id": config["protocol_id"],
        },
        output_root / "checkpoint.pt",
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "baseline": args.baseline,
                "seed": args.seed,
                "train_examples": len(train_examples),
                "development_examples": len(development_examples),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
