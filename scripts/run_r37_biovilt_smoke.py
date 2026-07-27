from __future__ import annotations

# ruff: noqa: E402

import argparse
from collections import Counter
import json
from pathlib import Path
import random
import sys
from typing import Any, Iterable

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE))
sys.path.insert(0, str(WORKSPACE / "src"))

import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader, Dataset

from scripts.cache_r37_biovilt_pair_embeddings import (
    CHECKPOINT,
    HI_ML_SOURCE,
)
from visualvit.biovilt import (
    BIOVILT_CONTROL_MODES,
    BioViLTControlCacheIndex,
    FindingConditionedLinearProbe,
    canonical_pair_embedding,
    load_biovilt_image,
    load_frozen_biovilt,
)
from visualvit.cmcp import stable_hash, transition_examples
from visualvit.prta import PROGRESSION_LABELS


TRANSITION_ROOT = Path(
    r"H:\VisualVIT_runtime\050_routeD\r37_prta_cxr"
    r"\r37a_transitions_v4_1"
)
TEXT_CACHE = Path(
    r"H:\VisualVIT_runtime\050_routeD\r37_prta_cxr"
    r"\r37_biomedclip_text_embeddings.pt"
)
OUTPUT_BASE = Path(
    r"H:\VisualVIT_runtime\050_routeD\r37_prta_cxr\r37b_smokes"
)
FEATURE_CACHE = Path(
    r"H:\VisualVIT_runtime\050_routeD\r37_prta_cxr"
    r"\r37_biovilt_pair_cache"
)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def flatten_partition(
    transition_root: Path, partition: str
) -> list[dict[str, Any]]:
    name = (
        "r37_pretrain_manifest.jsonl"
        if partition == "pretrain"
        else "r37_internal_calibration_manifest.jsonl"
    )
    rows = read_jsonl(transition_root / name)
    pair_by_id = {str(row["pair_id"]): row for row in rows}
    result = []
    for example in transition_examples(rows):
        pair = pair_by_id[str(example["pair_id"])]
        result.append(
            {
                **example,
                "patient_id": str(pair["patient_id"]),
                "prior_path": str(pair["prior_path"]),
                "current_path": str(pair["current_path"]),
            }
        )
    return result


def balanced_sample(
    examples: Iterable[dict[str, Any]], *, maximum: int, seed: int
) -> list[dict[str, Any]]:
    if maximum < len(PROGRESSION_LABELS):
        raise ValueError("maximum must permit at least one row per label")
    groups = {label: [] for label in PROGRESSION_LABELS}
    for example in examples:
        groups[str(example["label"])].append(example)
    per_label = maximum // len(PROGRESSION_LABELS)
    selected = []
    for label in PROGRESSION_LABELS:
        ordered = sorted(
            groups[label],
            key=lambda item: stable_hash(
                "r37-a1-smoke-sample-v1", seed, item["example_id"]
            ),
        )
        selected.extend(ordered[:per_label])
    return sorted(
        selected,
        key=lambda item: stable_hash(
            "r37-a1-smoke-order-v1", seed, item["example_id"]
        ),
    )


class PairDataset(Dataset):
    def __init__(self, examples: list[dict[str, Any]]) -> None:
        self.examples = examples

    def __len__(self) -> int:
        return len(self.examples)

    def __getitem__(self, index: int):
        item = self.examples[index]
        return (
            str(item["pair_id"]),
            load_biovilt_image(item["prior_path"]),
            load_biovilt_image(item["current_path"]),
        )


def unique_pairs(
    *groups: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for examples in groups:
        for example in examples:
            pair_id = str(example["pair_id"])
            previous = by_id.setdefault(pair_id, example)
            if (
                previous["prior_path"] != example["prior_path"]
                or previous["current_path"] != example["current_path"]
            ):
                raise ValueError(f"pair path drift: {pair_id}")
    return [by_id[pair_id] for pair_id in sorted(by_id)]


@torch.no_grad()
def extract_controls(
    model: torch.nn.Module,
    pairs: list[dict[str, Any]],
    *,
    device: torch.device,
    batch_size: int,
    workers: int,
) -> dict[str, dict[str, torch.Tensor]]:
    result: dict[str, dict[str, torch.Tensor]] = {}
    loader = DataLoader(
        PairDataset(pairs),
        batch_size=batch_size,
        shuffle=False,
        num_workers=workers,
        pin_memory=device.type == "cuda",
    )
    for pair_ids, prior, current in loader:
        prior = prior.to(device, non_blocking=True)
        current = current.to(device, non_blocking=True)
        true_pair = canonical_pair_embedding(
            model, current_image=current, prior_image=prior
        )
        current_only = canonical_pair_embedding(
            model, current_image=current, prior_image=None
        )
        inverted = canonical_pair_embedding(
            model, current_image=prior, prior_image=current
        )
        for index, pair_id in enumerate(pair_ids):
            result[str(pair_id)] = {
                "true_pair": true_pair[index].cpu(),
                "current_only": current_only[index].cpu(),
                "inverted": inverted[index].cpu(),
            }
    return result


def extract_cached_controls(
    cache: BioViLTControlCacheIndex,
    pairs: list[dict[str, Any]],
) -> dict[str, dict[str, torch.Tensor]]:
    pair_ids = [str(item["pair_id"]) for item in pairs]
    batched = {
        mode: cache.get_many(pair_ids, mode=mode)
        for mode in BIOVILT_CONTROL_MODES
    }
    return {
        pair_id: {
            mode: batched[mode][index]
            for mode in BIOVILT_CONTROL_MODES
        }
        for index, pair_id in enumerate(pair_ids)
    }


def tensors(
    examples: list[dict[str, Any]],
    features: dict[str, dict[str, torch.Tensor]],
    *,
    mode: str,
    finding_to_index: dict[str, int],
    label_to_index: dict[str, int],
    device: torch.device,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    embeddings = torch.stack(
        [features[str(item["pair_id"])][mode] for item in examples]
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
    return embeddings, finding_indices, labels


def macro_f1(targets: list[int], predictions: list[int]) -> float:
    scores = []
    for label in range(len(PROGRESSION_LABELS)):
        tp = sum(
            target == label and prediction == label
            for target, prediction in zip(targets, predictions)
        )
        fp = sum(
            target != label and prediction == label
            for target, prediction in zip(targets, predictions)
        )
        fn = sum(
            target == label and prediction != label
            for target, prediction in zip(targets, predictions)
        )
        denominator = 2 * tp + fp + fn
        scores.append(2 * tp / denominator if denominator else 0.0)
    return sum(scores) / len(scores)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run an engineering-only frozen BioViL-T A1 probe smoke"
    )
    parser.add_argument("--transition-root", type=Path, default=TRANSITION_ROOT)
    parser.add_argument("--text-cache", type=Path, default=TEXT_CACHE)
    parser.add_argument("--checkpoint", type=Path, default=CHECKPOINT)
    parser.add_argument("--hi-ml-source", type=Path, default=HI_ML_SOURCE)
    parser.add_argument("--feature-cache", type=Path, default=FEATURE_CACHE)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--max-train-examples", type=int, default=25)
    parser.add_argument("--max-calibration-examples", type=int, default=10)
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--learning-rate", type=float, default=1e-2)
    parser.add_argument("--formal", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_root = args.output_root or (
        OUTPUT_BASE / f"a1_seed{args.seed}_engineering_v1"
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
        raise ValueError("A1 engineering smoke exceeds its non-formal limit")

    audit = json.loads(
        (args.transition_root / "r37_transition_audit.json").read_text(
            encoding="utf-8"
        )
    )
    if audit["ruleset_version"] != "r37-report-transition-v4.1":
        raise ValueError("transition ruleset drift")
    if args.formal and not audit["formal_training_unlocked"]:
        raise PermissionError(
            "formal A1 remains locked pending independent transition human QA"
        )
    random.seed(args.seed)
    torch.manual_seed(args.seed)
    device = torch.device(args.device)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but unavailable")

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

    selected_pairs = unique_pairs(train_examples, calibration_examples)
    cache_manifest = (
        args.feature_cache / "r37_biovilt_pair_cache_manifest.json"
    )
    if cache_manifest.is_file():
        features = extract_cached_controls(
            BioViLTControlCacheIndex(args.feature_cache),
            selected_pairs,
        )
        feature_source = "frozen_control_cache"
    else:
        if args.formal:
            raise FileNotFoundError(
                "formal A1 requires the merged one-time control cache"
            )
        model = load_frozen_biovilt(
            args.checkpoint, args.hi_ml_source, device
        )
        features = extract_controls(
            model,
            selected_pairs,
            device=device,
            batch_size=args.batch_size,
            workers=args.workers,
        )
        del model
        feature_source = "direct_engineering_inference"

    train_x, train_finding, train_y = tensors(
        train_examples,
        features,
        mode="true_pair",
        finding_to_index=finding_to_index,
        label_to_index=label_to_index,
        device=device,
    )
    probe = FindingConditionedLinearProbe(
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

    probe.eval()
    metrics = {}
    predictions = {}
    with torch.no_grad():
        for mode in ("true_pair", "current_only", "inverted"):
            x, finding_index, target = tensors(
                calibration_examples,
                features,
                mode=mode,
                finding_to_index=finding_to_index,
                label_to_index=label_to_index,
                device=device,
            )
            prediction = probe(x, finding_index).argmax(dim=-1)
            targets = target.cpu().tolist()
            predicted = prediction.cpu().tolist()
            metrics[f"{mode}_macro_f1"] = macro_f1(targets, predicted)
            predictions[mode] = predicted
    metrics["true_minus_current_pp"] = 100 * (
        metrics["true_pair_macro_f1"] - metrics["current_only_macro_f1"]
    )
    metrics["true_minus_inverted_pp"] = 100 * (
        metrics["true_pair_macro_f1"] - metrics["inverted_macro_f1"]
    )

    gradient_audit = {
        "probe_trainable_parameters": sum(
            parameter.numel() for parameter in probe.parameters()
        ),
        "backbone_trainable_parameters": 0,
    }
    result = {
        "schema": "visualvit.r37.a1-engineering-smoke.v1",
        "status": "PASS_R37_A1_ENGINEERING_PIPELINE",
        "scientific_gate_status": (
            "PENDING_THREE_SEED_AGGREGATION"
            if args.formal
            else "NOT_EVALUATED_TINY_SMOKE"
        ),
        "formal": args.formal,
        "variant": "A1",
        "seed": args.seed,
        "train_examples": len(train_examples),
        "calibration_examples": len(calibration_examples),
        "unique_pairs": len(features),
        "feature_source": feature_source,
        "train_label_counts": dict(
            Counter(item["label"] for item in train_examples)
        ),
        "calibration_label_counts": dict(
            Counter(item["label"] for item in calibration_examples)
        ),
        "metrics": metrics,
        "gradient_audit": gradient_audit,
        "predictions": predictions,
        "target_labels": [
            label_to_index[str(item["label"])]
            for item in calibration_examples
        ],
        "calibration_patient_ids": [
            str(item["patient_id"]) for item in calibration_examples
        ],
        "protected_outcomes_read": False,
        "source_hashes_recomputed": False,
        "formal_training_unlocked": bool(
            args.formal and audit["formal_training_unlocked"]
        ),
        "history": history,
    }
    output_root.mkdir(parents=True)
    (output_root / "r37_a1_smoke_result.json").write_text(
        json.dumps(result, indent=2, sort_keys=True), encoding="utf-8"
    )
    torch.save(
        {"probe_state_dict": probe.state_dict()},
        output_root / "r37_a1_probe.pt",
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
