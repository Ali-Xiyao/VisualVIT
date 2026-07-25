from __future__ import annotations

# ruff: noqa: E402

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
import time
from typing import Any, Mapping, Sequence

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE / "src"))
sys.path.insert(0, str(WORKSPACE / "scripts"))

import pandas as pd
from PIL import Image
import torch
from torch import nn
from torchvision import transforms

from run_chextemporal_mimic_matcher_qualification import (
    CLIP_MEAN,
    CLIP_STD,
    _extract_features,
    _load_encoder,
    _matcher,
    _region_batch,
    parse_boxes,
    sha256_file,
    tensor_hash,
)
from visualvit.allocator import DeterministicGlobalAllocator
from visualvit.matching import (
    anatomy_compatible_derangement,
    oracle_plan_from_entity_ids,
)
from visualvit.real_progression import (
    canonical_sha256,
    classification_metrics,
    deterministic_patient_folds,
    fold_audit,
    hierarchical_patient_bootstrap,
)
from visualvit.real_qualification import (
    correspondence_support,
    map_annotation_box,
)
from visualvit.tokenizer import (
    assemble_capes_ci_tokens,
    build_soft_relation_candidates,
)


EVIDENCE_CLASS = "NON_CONFIRMATORY_REAL_DATA_SECONDARY"
PROTOCOL_SHA256 = "1e500fef7424a8c764cf1f55611b5fa3d164fd95a9f2be497d7f46b9284a2cb6"
BBOX_SHA256 = "20f114c7f81a66986ed0a697d4056d2b9c4029e7df77c97217db4908726f2064"
MODEL_SHA256 = "3be6f957b2fc8b8324cc6ed6faebdcb218511b41fc0f542312e21850424a2590"
EXPECTED = {
    "rows": 601,
    "patients": 70,
    "pairs": 357,
    "images": 475,
    "labels": {
        "Improved": 127,
        "New": 58,
        "Resolved": 29,
        "Stable": 251,
        "Worse": 136,
    },
    "b4_rows": 90,
    "b4_patients": 22,
    "b4_labels": {"Improved": 24, "Stable": 38, "Worse": 28},
}
FULL_LABELS = ("Improved", "New", "Resolved", "Stable", "Worse")
B4_LABELS = ("Improved", "Stable", "Worse")
TRAINING_SEEDS = (17, 29, 43)
DERANGEMENT_IDS = (81001, 81002, 81003)
FULL_SYSTEMS = (
    "current_only_global",
    "paired_global",
    "oracle_region",
    "learned_region",
    "oracle_no_interaction",
)
B4_SYSTEMS = (
    "B4a_deranged",
    "B4b_oracle",
    "learned_region",
    "paired_global",
    "current_only_global",
    "oracle_no_interaction",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--bbox",
        type=Path,
        default=WORKSPACE / "data/official/chextemporal_81fd9cdd/gold_bboxes.parquet",
    )
    parser.add_argument(
        "--image-root",
        type=Path,
        default=Path(r"H:\Xiyao_Wang\000_Public Dataset\CheXpert-v1.0-small"),
    )
    parser.add_argument(
        "--weights",
        type=Path,
        default=Path(
            r"H:\Xiyao_Wang\021_260129VIVID\pretrained\biomedclip_vit_base.pt"
        ),
    )
    parser.add_argument(
        "--protocol",
        type=Path,
        default=WORKSPACE / "docs/superpowers/specs/"
        "2026-07-24-chextemporal-chexpert-progression-pilot-v1.md",
    )
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--device", default="cuda:1")
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--steps", type=int, default=300)
    parser.add_argument("--learning-rate", type=float, default=0.01)
    parser.add_argument("--bootstrap-replicates", type=int, default=10_000)
    return parser.parse_args()


def _path_for(root: Path, raw: object) -> tuple[Path, str]:
    relative = Path(str(raw))
    train = root / "train" / relative
    if train.is_file():
        return train, "train"
    valid = root / "valid" / relative
    if valid.is_file():
        return valid, "valid"
    return train, "missing"


def _mapped_boxes(
    raw: object, *, path: Path
) -> tuple[list[dict[str, Any]], tuple[int, int]]:
    boxes = parse_boxes(raw)
    with Image.open(path) as image:
        width, height = image.size
    mapped = [map_annotation_box(box, rows=height, columns=width) for box in boxes]
    if any(box.width < 2.0 or box.height < 2.0 for box in mapped):
        raise ValueError("mapped box is below the two-pixel minimum")
    return [box.__dict__ for box in mapped], (width, height)


def build_cohort(
    args: argparse.Namespace,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    frame = pd.read_parquet(args.bbox)
    frame = frame[frame["dataset"].str.casefold() == "chexpert"].copy()
    key = [
        "patient_id",
        "study_id_prev",
        "study_id_curr",
        "img_path_prev",
        "img_path_curr",
        "disease_name",
    ]
    targets = frame.groupby(key, dropna=False)["progression"].nunique()
    frame = frame.merge(targets.rename("target_count").reset_index(), on=key)

    records = []
    exclusions: Counter[str] = Counter()
    image_sizes: dict[str, tuple[int, int]] = {}
    for row in frame.itertuples():
        reasons = []
        prior_path, prior_partition = _path_for(args.image_root, row.img_path_prev)
        current_path, current_partition = _path_for(args.image_root, row.img_path_curr)
        if prior_partition != "train" or current_partition != "train":
            reasons.append("parent_not_official_train")
        if int(row.target_count) != 1:
            reasons.append("target_conflict")
        prior_raw = parse_boxes(row.prior_bboxes)
        current_raw = parse_boxes(row.current_bboxes)
        try:
            support = correspondence_support(
                str(row.progression),
                [str(box["label"]) for box in prior_raw],
                [str(box["label"]) for box in current_raw],
            )
        except ValueError:
            support = {
                "compatible": False,
                "shared": [],
                "deaths": [],
                "births": [],
            }
            reasons.append("duplicate_box_label")
        if not support["compatible"]:
            reasons.append("progression_support_incompatible")
        try:
            prior_boxes, prior_size = _mapped_boxes(row.prior_bboxes, path=prior_path)
            current_boxes, current_size = _mapped_boxes(
                row.current_bboxes, path=current_path
            )
            image_sizes[str(prior_path)] = prior_size
            image_sizes[str(current_path)] = current_size
        except (OSError, TypeError, ValueError):
            prior_boxes, current_boxes = [], []
            reasons.append("coordinate_or_image_invalid")
        if reasons:
            exclusions.update(set(reasons))
            continue

        record_key = "|".join(
            str(value)
            for value in (
                row.patient_id,
                row.study_id_prev,
                row.study_id_curr,
                row.disease_name,
                row.progression,
            )
        )
        records.append(
            {
                "qualification_id": hashlib.sha256(record_key.encode()).hexdigest()[
                    :20
                ],
                "patient_id": str(row.patient_id),
                "prior_study_id": str(row.study_id_prev),
                "current_study_id": str(row.study_id_curr),
                "prior_path": str(prior_path),
                "current_path": str(current_path),
                "view": "frontal",
                "disease_name": str(row.disease_name),
                "progression": str(row.progression),
                "prior_boxes": prior_boxes,
                "current_boxes": current_boxes,
                "shared_count": len(support["shared"]),
                "death_count": len(support["deaths"]),
                "birth_count": len(support["births"]),
            }
        )
    records.sort(key=lambda row: row["qualification_id"])
    retained_paths = {row["prior_path"] for row in records} | {
        row["current_path"] for row in records
    }
    retained_sizes = {path: image_sizes[path] for path in retained_paths}
    audit = {
        "input_rows": len(frame),
        "retained_rows": len(records),
        "retained_patients": len({row["patient_id"] for row in records}),
        "retained_pairs": len(
            {
                (
                    row["patient_id"],
                    row["prior_study_id"],
                    row["current_study_id"],
                )
                for row in records
            }
        ),
        "unique_images": len(retained_sizes),
        "label_counts": dict(Counter(row["progression"] for row in records)),
        "exclusions": dict(sorted(exclusions.items())),
        "image_size_counts": {
            f"{width}x{height}": count
            for (width, height), count in sorted(
                Counter(retained_sizes.values()).items()
            )
        },
    }
    b4 = [
        row
        for row in records
        if row["shared_count"] >= 2 and row["progression"] in B4_LABELS
    ]
    audit["b4_rows"] = len(b4)
    audit["b4_patients"] = len({row["patient_id"] for row in b4})
    audit["b4_label_counts"] = dict(Counter(row["progression"] for row in b4))
    actual = {
        "rows": audit["retained_rows"],
        "patients": audit["retained_patients"],
        "pairs": audit["retained_pairs"],
        "images": audit["unique_images"],
        "labels": audit["label_counts"],
        "b4_rows": audit["b4_rows"],
        "b4_patients": audit["b4_patients"],
        "b4_labels": audit["b4_label_counts"],
    }
    if actual != EXPECTED:
        raise RuntimeError(f"registered cohort drift: {actual!r}")
    return records, audit


def _image_ledger(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    paths = sorted(
        {str(row["prior_path"]) for row in records}
        | {str(row["current_path"]) for row in records}
    )
    return [
        {
            "path": path,
            "bytes": Path(path).stat().st_size,
            "sha256": sha256_file(Path(path)),
        }
        for path in paths
    ]


def _extract_global_features(
    paths: Sequence[str],
    model: nn.Module,
    device: torch.device,
    batch_size: int,
) -> tuple[dict[str, torch.Tensor], list[dict[str, Any]], float, float]:
    preprocessing = transforms.Compose(
        [
            transforms.Resize((224, 224), antialias=True),
            transforms.ToTensor(),
            transforms.Normalize(CLIP_MEAN, CLIP_STD),
        ]
    )
    ordered = sorted(paths)
    features: dict[str, torch.Tensor] = {}
    start = time.perf_counter()
    with torch.inference_mode():
        for offset in range(0, len(ordered), batch_size):
            chunk = ordered[offset : offset + batch_size]
            batch = torch.stack(
                [preprocessing(Image.open(path).convert("RGB")) for path in chunk]
            ).to(device)
            encoded = model.forward_features(batch)[:, 0].detach().cpu()
            if not torch.isfinite(encoded).all():
                raise RuntimeError("non-finite global image feature")
            for path, feature in zip(chunk, encoded, strict=True):
                features[path] = feature
    repeat_paths = ordered[: min(batch_size, len(ordered))]
    with torch.inference_mode():
        repeated = torch.stack(
            [preprocessing(Image.open(path).convert("RGB")) for path in repeat_paths]
        ).to(device)
        second = model.forward_features(repeated)[:, 0].detach().cpu()
    first = torch.stack([features[path] for path in repeat_paths])
    repeat_difference = float((first - second).abs().max())
    ledger = [
        {
            "path": path,
            "feature_sha256": tensor_hash(features[path]),
        }
        for path in ordered
    ]
    return features, ledger, time.perf_counter() - start, repeat_difference


def _relation_mean(
    regions: Any,
    plan: Any,
    *,
    no_interaction: bool = False,
) -> torch.Tensor:
    candidates = build_soft_relation_candidates(regions, plan)
    allocation = DeterministicGlobalAllocator()(candidates)
    bundle = assemble_capes_ci_tokens(regions, plan, allocation)
    relation = bundle.tokens[0, 32:60].clone()
    valid = bundle.valid_mask[0, 32:60]
    if not bool(valid.any()):
        raise RuntimeError("relation representation has no valid token")
    result = relation[valid].mean(dim=0)
    if no_interaction:
        feature_dim = (result.numel() - 3) // 4
        result[2 * feature_dim : 4 * feature_dim] = 0.0
    return result


def _global_relation(
    prior: torch.Tensor,
    current: torch.Tensor,
    *,
    current_only: bool,
) -> torch.Tensor:
    feature_dim = 774
    prior_padded = torch.zeros(feature_dim)
    current_padded = torch.zeros(feature_dim)
    if not current_only:
        prior_padded[-prior.numel() :] = prior
    current_padded[-current.numel() :] = current
    event = torch.tensor([1.0, 0.0, 0.0])
    return torch.cat(
        (
            prior_padded,
            current_padded,
            current_padded - prior_padded,
            current_padded * prior_padded,
            event,
        )
    )


def _representations(
    records: Sequence[dict[str, Any]],
    crop_features: dict[str, torch.Tensor],
    global_features: dict[str, torch.Tensor],
) -> tuple[
    dict[str, torch.Tensor],
    dict[int, torch.Tensor],
    list[dict[str, Any]],
]:
    invariant: dict[str, list[torch.Tensor]] = defaultdict(list)
    deranged: dict[int, list[torch.Tensor]] = {value: [] for value in DERANGEMENT_IDS}
    b4_audits = []
    for record in records:
        regions = _region_batch(record, crop_features, "visual_geometry_equal")
        oracle = oracle_plan_from_entity_ids(regions)
        matcher = _matcher(regions, "visual_geometry_equal")
        edge, prior_null, current_null = matcher.compute_utilities(regions)
        learned = matcher.plan_from_utilities(
            regions, edge, prior_null, current_null, hard=True
        )
        invariant["oracle_region"].append(_relation_mean(regions, oracle))
        invariant["B4b_oracle"].append(_relation_mean(regions, oracle))
        invariant["learned_region"].append(_relation_mean(regions, learned))
        invariant["oracle_no_interaction"].append(
            _relation_mean(regions, oracle, no_interaction=True)
        )
        prior_global = global_features[record["prior_path"]]
        current_global = global_features[record["current_path"]]
        invariant["paired_global"].append(
            _global_relation(prior_global, current_global, current_only=False)
        )
        invariant["current_only_global"].append(
            _global_relation(prior_global, current_global, current_only=True)
        )

        if record["shared_count"] >= 2 and record["progression"] in B4_LABELS:
            per_row_checks = []
            for derangement_id in DERANGEMENT_IDS:
                stable_seed = (
                    derangement_id + int(record["qualification_id"][:8], 16)
                ) % (2**31)
                wrong = anatomy_compatible_derangement(
                    regions, oracle, seed=stable_seed
                )
                deranged[derangement_id].append(_relation_mean(regions, wrong))
                prior_count = regions.prior_features.shape[1]
                current_count = regions.current_features.shape[1]
                oracle_real = oracle.transport[:, :prior_count, :current_count]
                wrong_real = wrong.transport[:, :prior_count, :current_count]
                checks = {
                    "zero_fixed_point": not bool(
                        ((oracle_real > 0.5) & (wrong_real > 0.5)).any()
                    ),
                    "assignment_differs": not torch.equal(
                        oracle.transport, wrong.transport
                    ),
                    "prior_null_equal": torch.equal(
                        oracle.transport[:, :prior_count, current_count],
                        wrong.transport[:, :prior_count, current_count],
                    ),
                    "current_null_equal": torch.equal(
                        oracle.transport[:, prior_count, :current_count],
                        wrong.transport[:, prior_count, :current_count],
                    ),
                    "prior_feature_equal": True,
                    "current_feature_equal": True,
                }
                per_row_checks.append(
                    {
                        "derangement_id": derangement_id,
                        "checks": checks,
                        "passed": all(checks.values()),
                    }
                )
            b4_audits.append(
                {
                    "qualification_id": record["qualification_id"],
                    "derangements": per_row_checks,
                    "passed": all(item["passed"] for item in per_row_checks),
                }
            )
    if not all(item["passed"] for item in b4_audits):
        raise RuntimeError("B4 isomorphism audit failed")
    return (
        {name: torch.stack(values) for name, values in invariant.items()},
        {name: torch.stack(values) for name, values in deranged.items()},
        b4_audits,
    )


class FrozenShapeLinear(nn.Module):
    def __init__(self, input_dim: int, class_count: int) -> None:
        super().__init__()
        self.norm = nn.LayerNorm(input_dim, elementwise_affine=False)
        self.linear = nn.Linear(input_dim, class_count)

    def forward(self, value: torch.Tensor) -> torch.Tensor:
        return self.linear(self.norm(value))


def _set_determinism(seed: int) -> None:
    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.use_deterministic_algorithms(True)


def _fit_predict(
    x_train: torch.Tensor,
    y_train: torch.Tensor,
    x_test: torch.Tensor,
    *,
    seed: int,
    class_count: int,
    steps: int,
    learning_rate: float,
    device: torch.device,
) -> tuple[torch.Tensor, dict[str, Any]]:
    _set_determinism(seed)
    model = FrozenShapeLinear(x_train.shape[1], class_count).to(device)
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=learning_rate, weight_decay=1e-4
    )
    counts = torch.bincount(y_train, minlength=class_count).float()
    if bool((counts == 0).any()):
        raise RuntimeError("training fold is missing a registered label")
    class_weights = (counts.sum() / (class_count * counts)).to(device)
    x_train = x_train.to(device)
    y_train = y_train.to(device)
    x_test = x_test.to(device)
    start = time.perf_counter()
    final_loss = float("nan")
    for _ in range(steps):
        optimizer.zero_grad(set_to_none=True)
        logits = model(x_train)
        loss = nn.functional.cross_entropy(logits, y_train, weight=class_weights)
        loss.backward()
        optimizer.step()
        final_loss = float(loss.detach().cpu())
    with torch.inference_mode():
        train_prediction = model(x_train).argmax(-1).cpu()
        test_prediction = model(x_test).argmax(-1).cpu()
    return test_prediction, {
        "final_loss": final_loss,
        "train_accuracy": float((train_prediction == y_train.cpu()).float().mean()),
        "runtime_seconds": time.perf_counter() - start,
        "parameter_count": sum(parameter.numel() for parameter in model.parameters()),
    }


def _run_task(
    *,
    records: Sequence[dict[str, Any]],
    labels: Sequence[str],
    systems: Sequence[str],
    invariant_features: Mapping[str, torch.Tensor],
    deranged_features: Mapping[int, torch.Tensor],
    assignment: Mapping[str, int],
    derangements: Sequence[int],
    steps: int,
    learning_rate: float,
    device: torch.device,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    label_index = {label: index for index, label in enumerate(labels)}
    targets = torch.tensor(
        [label_index[row["progression"]] for row in records], dtype=torch.long
    )
    patient_sizes = Counter(row["patient_id"] for row in records)
    output_rows = []
    fit_audit = []
    invariant_systems = [system for system in systems if system != "B4a_deranged"]
    for training_seed in TRAINING_SEEDS:
        system_predictions: dict[tuple[str, int], list[str | None]] = {}
        for system in invariant_systems:
            system_predictions[(system, derangements[0])] = [None] * len(records)
        if "B4a_deranged" in systems:
            for derangement in derangements:
                system_predictions[("B4a_deranged", derangement)] = [None] * len(
                    records
                )

        for fold in range(5):
            train_indices = torch.tensor(
                [
                    index
                    for index, row in enumerate(records)
                    if assignment[row["patient_id"]] != fold
                ],
                dtype=torch.long,
            )
            test_indices = torch.tensor(
                [
                    index
                    for index, row in enumerate(records)
                    if assignment[row["patient_id"]] == fold
                ],
                dtype=torch.long,
            )
            if len(train_indices) == 0 or len(test_indices) == 0:
                raise RuntimeError("empty train/test fold")
            model_seed = training_seed + 100_000 * fold
            for system in invariant_systems:
                test_prediction, fit = _fit_predict(
                    invariant_features[system][train_indices],
                    targets[train_indices],
                    invariant_features[system][test_indices],
                    seed=model_seed,
                    class_count=len(labels),
                    steps=steps,
                    learning_rate=learning_rate,
                    device=device,
                )
                for index, prediction in zip(
                    test_indices.tolist(), test_prediction.tolist(), strict=True
                ):
                    system_predictions[(system, derangements[0])][index] = labels[
                        prediction
                    ]
                fit_audit.append(
                    {
                        "system": system,
                        "training_seed": training_seed,
                        "derangement_id": derangements[0],
                        "fold": fold,
                        **fit,
                    }
                )
            if "B4a_deranged" in systems:
                for derangement in derangements:
                    feature = deranged_features[derangement]
                    test_prediction, fit = _fit_predict(
                        feature[train_indices],
                        targets[train_indices],
                        feature[test_indices],
                        seed=model_seed,
                        class_count=len(labels),
                        steps=steps,
                        learning_rate=learning_rate,
                        device=device,
                    )
                    for index, prediction in zip(
                        test_indices.tolist(),
                        test_prediction.tolist(),
                        strict=True,
                    ):
                        system_predictions[("B4a_deranged", derangement)][index] = (
                            labels[prediction]
                        )
                    fit_audit.append(
                        {
                            "system": "B4a_deranged",
                            "training_seed": training_seed,
                            "derangement_id": derangement,
                            "fold": fold,
                            **fit,
                        }
                    )

        for system in invariant_systems:
            reference = system_predictions[(system, derangements[0])]
            if any(value is None for value in reference):
                raise RuntimeError("incomplete OOF predictions")
            for derangement in derangements:
                for index, prediction in enumerate(reference):
                    row = records[index]
                    output_rows.append(
                        {
                            "patient_id": row["patient_id"],
                            "observation_id": row["qualification_id"],
                            "training_seed": training_seed,
                            "derangement_id": derangement,
                            "system": system,
                            "target": row["progression"],
                            "prediction": prediction,
                            "weight": 1.0 / patient_sizes[row["patient_id"]],
                        }
                    )
        if "B4a_deranged" in systems:
            for derangement in derangements:
                predictions = system_predictions[("B4a_deranged", derangement)]
                if any(value is None for value in predictions):
                    raise RuntimeError("incomplete B4a OOF predictions")
                for index, prediction in enumerate(predictions):
                    row = records[index]
                    output_rows.append(
                        {
                            "patient_id": row["patient_id"],
                            "observation_id": row["qualification_id"],
                            "training_seed": training_seed,
                            "derangement_id": derangement,
                            "system": "B4a_deranged",
                            "target": row["progression"],
                            "prediction": prediction,
                            "weight": 1.0 / patient_sizes[row["patient_id"]],
                        }
                    )
    return output_rows, fit_audit


def _block_metrics(
    rows: Sequence[dict[str, Any]], labels: Sequence[str]
) -> list[dict[str, Any]]:
    groups: dict[tuple[str, int, int], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[
            (
                row["system"],
                row["training_seed"],
                row["derangement_id"],
            )
        ].append(row)
    return [
        {
            "system": key[0],
            "training_seed": key[1],
            "derangement_id": key[2],
            "metrics": classification_metrics(block, labels=labels),
        }
        for key, block in sorted(groups.items())
    ]


def main() -> int:
    args = parse_args()
    pins = {
        "protocol": (args.protocol, PROTOCOL_SHA256),
        "bbox": (args.bbox, BBOX_SHA256),
        "weights": (args.weights, MODEL_SHA256),
    }
    pin_ledger = {}
    for name, (path, expected) in pins.items():
        actual = sha256_file(path)
        if actual != expected:
            raise RuntimeError(f"{name} hash mismatch: {actual}")
        pin_ledger[name] = {
            "path": str(path.resolve()),
            "bytes": path.stat().st_size,
            "sha256": actual,
        }
    records, cohort_audit = build_cohort(args)
    if args.output_root.exists():
        raise FileExistsError(args.output_root)
    args.output_root.mkdir(parents=True)

    (args.output_root / "cohort.json").write_text(
        json.dumps(records, indent=2, sort_keys=True), encoding="utf-8"
    )
    image_ledger = _image_ledger(records)
    (args.output_root / "image_ledger.json").write_text(
        json.dumps(image_ledger, indent=2, sort_keys=True), encoding="utf-8"
    )

    device = torch.device(args.device)
    torch.cuda.set_device(device)
    model = _load_encoder(args.weights, device)
    torch.cuda.reset_peak_memory_stats(device)
    crop_features, crop_ledger, crop_seconds, crop_repeat = _extract_features(
        records, model, device, args.batch_size
    )
    image_paths = sorted(
        {row["prior_path"] for row in records}
        | {row["current_path"] for row in records}
    )
    global_features, global_ledger, global_seconds, global_repeat = (
        _extract_global_features(image_paths, model, device, args.batch_size)
    )
    peak_vram = int(torch.cuda.max_memory_allocated(device))
    if crop_repeat != 0.0 or global_repeat != 0.0:
        raise RuntimeError(
            f"feature repeat mismatch: crop={crop_repeat}, global={global_repeat}"
        )
    del model
    torch.cuda.empty_cache()
    cache_path = args.output_root / "features.pt"
    torch.save(
        {"crop_features": crop_features, "global_features": global_features},
        cache_path,
    )
    (args.output_root / "feature_ledger.json").write_text(
        json.dumps(
            {"crop": crop_ledger, "global": global_ledger},
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    invariant_full, deranged_b4, b4_audits = _representations(
        records, crop_features, global_features
    )
    b4_indices = [
        index
        for index, row in enumerate(records)
        if row["shared_count"] >= 2 and row["progression"] in B4_LABELS
    ]
    b4_records = [records[index] for index in b4_indices]
    invariant_b4 = {
        "B4b_oracle": invariant_full["B4b_oracle"][b4_indices],
        "learned_region": invariant_full["learned_region"][b4_indices],
        "paired_global": invariant_full["paired_global"][b4_indices],
        "current_only_global": invariant_full["current_only_global"][b4_indices],
        "oracle_no_interaction": invariant_full["oracle_no_interaction"][b4_indices],
    }
    if any(len(value) != len(b4_records) for value in deranged_b4.values()):
        raise RuntimeError("B4 feature count mismatch")
    (args.output_root / "b4_isomorphism.json").write_text(
        json.dumps(b4_audits, indent=2, sort_keys=True), encoding="utf-8"
    )

    full_assignment = deterministic_patient_folds(
        records, labels=FULL_LABELS, fold_count=5, salt="f5-v1"
    )
    b4_assignment = deterministic_patient_folds(
        b4_records, labels=B4_LABELS, fold_count=5, salt="b3-v1"
    )
    full_fold_audit = fold_audit(
        records,
        full_assignment,
        labels=FULL_LABELS,
        fold_count=5,
    )
    b4_fold_audit = fold_audit(
        b4_records,
        b4_assignment,
        labels=B4_LABELS,
        fold_count=5,
    )
    if any(
        count == 0
        for audit in (full_fold_audit, b4_fold_audit)
        for fold in audit["folds"]
        for count in fold["label_counts"].values()
    ):
        raise RuntimeError("a registered test fold is missing label support")
    fold_payload = {
        "full_assignment": dict(sorted(full_assignment.items())),
        "b4_assignment": dict(sorted(b4_assignment.items())),
        "full_audit": full_fold_audit,
        "b4_audit": b4_fold_audit,
    }
    (args.output_root / "folds.json").write_text(
        json.dumps(fold_payload, indent=2, sort_keys=True), encoding="utf-8"
    )

    full_rows, full_fit = _run_task(
        records=records,
        labels=FULL_LABELS,
        systems=FULL_SYSTEMS,
        invariant_features=invariant_full,
        deranged_features={},
        assignment=full_assignment,
        derangements=(0,),
        steps=args.steps,
        learning_rate=args.learning_rate,
        device=device,
    )
    b4_rows, b4_fit = _run_task(
        records=b4_records,
        labels=B4_LABELS,
        systems=B4_SYSTEMS,
        invariant_features=invariant_b4,
        deranged_features=deranged_b4,
        assignment=b4_assignment,
        derangements=DERANGEMENT_IDS,
        steps=args.steps,
        learning_rate=args.learning_rate,
        device=device,
    )
    predictions = {"full": full_rows, "b4": b4_rows}
    prediction_path = args.output_root / "predictions.json"
    prediction_path.write_text(
        json.dumps(predictions, indent=2, sort_keys=True), encoding="utf-8"
    )
    fit_path = args.output_root / "fit_audit.json"
    fit_path.write_text(
        json.dumps({"full": full_fit, "b4": b4_fit}, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    full_bootstrap = hierarchical_patient_bootstrap(
        full_rows,
        labels=FULL_LABELS,
        systems=FULL_SYSTEMS,
        seeds=TRAINING_SEEDS,
        derangements=(0,),
        contrasts={
            "oracle_minus_paired_global": ("oracle_region", "paired_global"),
            "learned_minus_paired_global": ("learned_region", "paired_global"),
            "oracle_minus_no_interaction": (
                "oracle_region",
                "oracle_no_interaction",
            ),
        },
        invariant_systems=FULL_SYSTEMS,
        replicates=args.bootstrap_replicates,
    )
    b4_bootstrap = hierarchical_patient_bootstrap(
        b4_rows,
        labels=B4_LABELS,
        systems=B4_SYSTEMS,
        seeds=TRAINING_SEEDS,
        derangements=DERANGEMENT_IDS,
        contrasts={
            "B4b_minus_B4a": ("B4b_oracle", "B4a_deranged"),
            "learned_minus_B4a": ("learned_region", "B4a_deranged"),
            "B4b_minus_paired_global": ("B4b_oracle", "paired_global"),
            "B4b_minus_no_interaction": (
                "B4b_oracle",
                "oracle_no_interaction",
            ),
        },
        invariant_systems=[system for system in B4_SYSTEMS if system != "B4a_deranged"],
        replicates=args.bootstrap_replicates,
    )
    gates = {
        "source_and_model_pins": True,
        "cohort_exact": True,
        "image_ledger_complete": len(image_ledger) == EXPECTED["images"],
        "feature_repeat_exact_zero": crop_repeat == 0.0 and global_repeat == 0.0,
        "features_finite": all(
            torch.isfinite(value).all()
            for value in list(crop_features.values()) + list(global_features.values())
        ),
        "b4_isomorphism": all(item["passed"] for item in b4_audits),
        "patient_folds_disjoint": full_fold_audit["patient_disjoint"]
        and b4_fold_audit["patient_disjoint"],
        "full_bootstrap_valid": full_bootstrap["inference_valid"],
        "b4_bootstrap_valid": b4_bootstrap["inference_valid"],
    }
    summary = {
        "status": (
            "PASS_NONCONFIRMATORY_REAL_DATA_SECONDARY"
            if all(gates.values())
            else "STOP_REAL_DATA_SECONDARY"
        ),
        "evidence_class": EVIDENCE_CLASS,
        "formal_entity_claim_allowed": False,
        "clinical_claim_allowed": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "pins": pin_ledger,
        "cohort": cohort_audit,
        "folds": {
            "full": full_fold_audit,
            "b4": b4_fold_audit,
        },
        "features": {
            "crop_count": len(crop_features),
            "global_count": len(global_features),
            "crop_seconds": crop_seconds,
            "global_seconds": global_seconds,
            "crop_repeat_max_abs_difference": crop_repeat,
            "global_repeat_max_abs_difference": global_repeat,
            "peak_vram_bytes": peak_vram,
            "cache_sha256": sha256_file(cache_path),
            "crop_ledger_sha256": canonical_sha256(crop_ledger),
            "global_ledger_sha256": canonical_sha256(global_ledger),
        },
        "metrics": {
            "full_blocks": _block_metrics(full_rows, FULL_LABELS),
            "b4_blocks": _block_metrics(b4_rows, B4_LABELS),
            "full_bootstrap": full_bootstrap,
            "b4_bootstrap": b4_bootstrap,
        },
        "gates": gates,
        "config": {
            "training_seeds": list(TRAINING_SEEDS),
            "derangement_ids": list(DERANGEMENT_IDS),
            "folds": 5,
            "steps": args.steps,
            "learning_rate": args.learning_rate,
            "weight_decay": 1e-4,
            "bootstrap_replicates": args.bootstrap_replicates,
            "device": str(device),
            "batch_size": args.batch_size,
            "classifier": "non-affine LayerNorm + Linear",
        },
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "torch": torch.__version__,
            "cuda": torch.version.cuda,
            "gpu": torch.cuda.get_device_name(device),
        },
        "artifacts": {
            "cohort.json": sha256_file(args.output_root / "cohort.json"),
            "image_ledger.json": sha256_file(args.output_root / "image_ledger.json"),
            "feature_ledger.json": sha256_file(
                args.output_root / "feature_ledger.json"
            ),
            "features.pt": sha256_file(cache_path),
            "folds.json": sha256_file(args.output_root / "folds.json"),
            "b4_isomorphism.json": sha256_file(
                args.output_root / "b4_isomorphism.json"
            ),
            "predictions.json": sha256_file(prediction_path),
            "fit_audit.json": sha256_file(fit_path),
        },
        "interpretation_boundary": (
            "Secondary real-data engineering evidence only. CheXTemporal does "
            "not assign a distinct progression owner to every box in a "
            "multifocal row; no formal entity-level or clinical claim."
        ),
    }
    summary_path = args.output_root / "summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps(summary, sort_keys=True))
    print(f"RESULT_DIR={args.output_root}")
    return 0 if all(gates.values()) else 2


if __name__ == "__main__":
    raise SystemExit(main())
