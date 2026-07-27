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
    CACHE_ROOT,
    FORMAL_CALIBRATION_EXAMPLES,
    FORMAL_SEEDS,
    FORMAL_TRAIN_EXAMPLES,
    OUTPUT_BASE,
    TEXT_CACHE,
    TRANSITION_ROOT,
    balanced_sample,
    batch_indices,
    flatten_partition,
    formal_partition,
)
from visualvit.prta import FrozenBiomedCLIPDifference, PROGRESSION_LABELS
from visualvit.qualification import (
    FindingConditionedLinearProbe,
    macro_f1,
)
from visualvit.r37_cache import Block8CacheIndex


FORMAL_A0_OUTPUT_BASE = Path(
    r"H:\VisualVIT_runtime\050_routeD\r37_prta_cxr"
    r"\r37b_formal\a0_bundle_v1"
)
FORMAL_A0_EPOCHS = 100
FORMAL_A0_BATCH_SIZE = 16
FORMAL_A0_LEARNING_RATE = 1e-2


def validate_formal_args(args: argparse.Namespace) -> None:
    expected = {
        "epochs": FORMAL_A0_EPOCHS,
        "batch_size": FORMAL_A0_BATCH_SIZE,
        "learning_rate": FORMAL_A0_LEARNING_RATE,
        "max_train_examples": 0,
        "max_calibration_examples": 0,
    }
    observed = {name: getattr(args, name) for name in expected}
    if observed != expected:
        raise ValueError(
            f"formal R37 A0 configuration drift: expected {expected}, "
            f"got {observed}"
        )
    if args.seed not in FORMAL_SEEDS:
        raise ValueError(
            f"formal R37 A0 requires one of frozen seeds {FORMAL_SEEDS}"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the engineering-only frozen BiomedCLIP A0 probe"
    )
    parser.add_argument("--transition-root", type=Path, default=TRANSITION_ROOT)
    parser.add_argument("--cache-root", type=Path, default=CACHE_ROOT)
    parser.add_argument("--text-cache", type=Path, default=TEXT_CACHE)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--max-train-examples", type=int, default=100)
    parser.add_argument("--max-calibration-examples", type=int, default=50)
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--learning-rate", type=float, default=1e-2)
    parser.add_argument("--formal", action="store_true")
    return parser.parse_args()


def extract_controls(
    examples: list[dict[str, Any]],
    *,
    cache: Block8CacheIndex,
    model: FrozenBiomedCLIPDifference,
    device: torch.device,
    batch_size: int,
) -> dict[str, dict[str, torch.Tensor]]:
    result = {}
    with torch.inference_mode():
        for start, end in batch_indices(len(examples), batch_size):
            batch = examples[start:end]
            prior = cache.get_many(
                item["prior_dicom_id"] for item in batch
            ).to(device=device, dtype=torch.float32)
            current = cache.get_many(
                item["current_dicom_id"] for item in batch
            ).to(device=device, dtype=torch.float32)
            true_pair = model(prior, current)
            current_only = model(current, current)
            inverted = model(current, prior)
            for index, item in enumerate(batch):
                result[str(item["example_id"])] = {
                    "true_pair": true_pair[index].cpu(),
                    "current_only": current_only[index].cpu(),
                    "inverted": inverted[index].cpu(),
                }
    return result


def make_tensors(
    examples: list[dict[str, Any]],
    features: dict[str, dict[str, torch.Tensor]],
    *,
    mode: str,
    finding_to_index: dict[str, int],
    label_to_index: dict[str, int],
    device: torch.device,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    x = torch.stack(
        [features[str(item["example_id"])][mode] for item in examples]
    ).to(device)
    finding_index = torch.tensor(
        [finding_to_index[str(item["finding"])] for item in examples],
        dtype=torch.long,
        device=device,
    )
    labels = torch.tensor(
        [label_to_index[str(item["label"])] for item in examples],
        dtype=torch.long,
        device=device,
    )
    return x, finding_index, labels


def main() -> int:
    args = parse_args()
    if args.formal:
        validate_formal_args(args)
    output_root = args.output_root
    if output_root is None:
        output_root = (
            FORMAL_A0_OUTPUT_BASE / f"seed_{args.seed}"
            if args.formal
            else OUTPUT_BASE / f"a0_seed{args.seed}_engineering_v1"
        )
    if output_root.exists():
        raise FileExistsError(f"output root must be fresh: {output_root}")
    if args.batch_size <= 0 or args.epochs <= 0:
        raise ValueError("batch size and epochs must be positive")
    if (
        args.max_train_examples > 1000
        or args.max_calibration_examples > 500
        or args.epochs > 300
    ):
        raise ValueError("A0 engineering smoke exceeds its non-formal limit")
    audit = json.loads(
        (args.transition_root / "r37_transition_audit.json").read_text(
            encoding="utf-8"
        )
    )
    if audit["ruleset_version"] != "r37-report-transition-v4.1":
        raise ValueError("transition ruleset drift")
    if args.formal and not audit["formal_training_unlocked"]:
        raise PermissionError(
            "formal A0 remains locked pending independent transition human QA"
        )

    random.seed(args.seed)
    torch.manual_seed(args.seed)
    device = torch.device(args.device)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but unavailable")
    if args.formal:
        train_examples = formal_partition(
            flatten_partition(args.transition_root, "pretrain"),
            expected_count=FORMAL_TRAIN_EXAMPLES,
        )
        calibration_examples = formal_partition(
            flatten_partition(args.transition_root, "internal_calibration"),
            expected_count=FORMAL_CALIBRATION_EXAMPLES,
        )
    else:
        train_examples = balanced_sample(
            flatten_partition(args.transition_root, "pretrain"),
            maximum=args.max_train_examples,
            seed=args.seed,
        )
        calibration_examples = balanced_sample(
            flatten_partition(args.transition_root, "internal_calibration"),
            maximum=args.max_calibration_examples,
            seed=args.seed + 1,
        )
    text_cache = torch.load(
        args.text_cache, map_location="cpu", weights_only=True
    )
    findings = [str(value) for value in text_cache["findings"]]
    labels = [str(value) for value in text_cache["labels"]]
    if tuple(labels) != PROGRESSION_LABELS or len(findings) != 12:
        raise ValueError("R37 finding/label registry drift")
    finding_to_index = {
        finding: index for index, finding in enumerate(findings)
    }
    label_to_index = {label: index for index, label in enumerate(labels)}

    cache = Block8CacheIndex(args.cache_root, maximum_loaded_shards=4)
    encoder = build_frozen_encoder(device)
    frozen = FrozenBiomedCLIPDifference(
        list(encoder.blocks[8:]), final_norm=encoder.norm
    ).to(device)
    del encoder
    selected = train_examples + calibration_examples
    features = extract_controls(
        selected,
        cache=cache,
        model=frozen,
        device=device,
        batch_size=args.batch_size,
    )
    train_x, train_finding, train_y = make_tensors(
        train_examples,
        features,
        mode="true_pair",
        finding_to_index=finding_to_index,
        label_to_index=label_to_index,
        device=device,
    )
    probe = FindingConditionedLinearProbe(
        feature_dim=768,
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

    metrics = {}
    predictions = {}
    targets: list[int] = []
    probe.eval()
    with torch.inference_mode():
        for mode in ("true_pair", "current_only", "inverted"):
            x, finding_index, labels_tensor = make_tensors(
                calibration_examples,
                features,
                mode=mode,
                finding_to_index=finding_to_index,
                label_to_index=label_to_index,
                device=device,
            )
            predicted = probe(x, finding_index).argmax(dim=-1).cpu().tolist()
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
        "schema": (
            "visualvit.r37.a0-formal-probe.v1"
            if args.formal
            else "visualvit.r37.a0-engineering-smoke.v1"
        ),
        "status": (
            "PASS_R37_A0_FORMAL_PROBE"
            if args.formal
            else "PASS_R37_A0_ENGINEERING_PIPELINE"
        ),
        "scientific_claim_allowed": False,
        "scientific_gate_status": (
            "PENDING_THREE_SEED_AGGREGATION"
            if args.formal
            else "NOT_EVALUATED_ENGINEERING_SMOKE"
        ),
        "formal": args.formal,
        "variant": "A0",
        "seed": args.seed,
        "train_examples": len(train_examples),
        "calibration_examples": len(calibration_examples),
        "selection_contract": {
            "train": "all_seed_independent_order"
            if args.formal
            else "balanced_engineering_sample",
            "calibration": "all_seed_independent_order"
            if args.formal
            else "balanced_engineering_sample",
        },
        "train_label_counts": dict(
            Counter(item["label"] for item in train_examples)
        ),
        "calibration_label_counts": dict(
            Counter(item["label"] for item in calibration_examples)
        ),
        "metrics": metrics,
        "predictions": predictions,
        "target_labels": targets,
        "calibration_patient_ids": [
            str(item["patient_id"]) for item in calibration_examples
        ],
        "gradient_audit": {
            "probe_trainable_parameters": sum(
                parameter.numel() for parameter in probe.parameters()
            ),
            "backbone_trainable_parameters": sum(
                parameter.numel()
                for parameter in frozen.parameters()
                if parameter.requires_grad
            ),
        },
        "history": history,
        "protected_outcomes_read": False,
        "sealed_test_read": False,
        "gold_outcomes_read": False,
        "source_hashes_recomputed": False,
        "formal_training_unlocked": bool(
            args.formal and audit["formal_training_unlocked"]
        ),
    }
    output_root.mkdir(parents=True, exist_ok=False)
    result_name = "result.json" if args.formal else "r37_a0_smoke_result.json"
    (output_root / result_name).write_text(
        json.dumps(result, indent=2, sort_keys=True), encoding="utf-8"
    )
    torch.save(
        {"probe_state_dict": probe.state_dict()},
        output_root
        / ("checkpoint.pt" if args.formal else "r37_a0_probe.pt"),
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
