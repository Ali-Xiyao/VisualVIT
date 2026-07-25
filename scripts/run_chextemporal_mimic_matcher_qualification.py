from __future__ import annotations

# ruff: noqa: E402

import argparse
import ast
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import sys
import time
import traceback
from typing import Any
from uuid import uuid4

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE / "src"))

import pandas as pd
from PIL import Image
import timm
import torch
from torchvision import transforms

from visualvit.allocator import DeterministicGlobalAllocator
from visualvit.matching import (
    InvariantPartialOTMatcher,
    anatomy_compatible_derangement,
    oracle_plan_from_entity_ids,
)
from visualvit.real_qualification import (
    correspondence_support,
    entity_ids,
    greedy_plan_from_utilities,
    map_annotation_box,
    match_sufficient_statistics,
    patient_cluster_bootstrap,
    plan_objective,
)
from visualvit.schemas import RegionBatch
from visualvit.tokenizer import (
    assemble_capes_ci_tokens,
    build_soft_relation_candidates,
)


EVIDENCE_CLASS = "NON_CONFIRMATORY_REAL_DATA_QUALIFICATION"
EXPECTED_ROWS = 267
BOOTSTRAP_SEED = 20260724
CLIP_MEAN = (0.48145466, 0.4578275, 0.40821073)
CLIP_STD = (0.26862954, 0.26130258, 0.27577711)
PINS = {
    "bbox": "20f114c7f81a66986ed0a697d4056d2b9c4029e7df77c97217db4908726f2064",
    "license": "64b72273169c3b87e317c965f9a03b14f9f2e28462326e705219c900ca18483a",
    "metadata": "6a3748ce77724c0dfe7d2def8f47643e989e3bbf0795bc13b89c1578e1649d6b",
    "split": "515997bd6649045d7443d60c59a4ce9f6cca6c478871b8f2fb13454462bedb2f",
    "weights": "3be6f957b2fc8b8324cc6ed6faebdcb218511b41fc0f542312e21850424a2590",
}
R24_PREREQUISITE_PINS = {
    "protocol": "2f8b1577d193bf6a63d5146853ffd2b5fdc70918b6937652ff2cef47d8cc8e44",
    "certificate": "e96629b24d4a7caf6239c0a48fe995649f04bbbc61ae5b1ec5e264c1d0a01d0c",
    "launcher_result": "4ab514b54b352a7f9206f9ebe7f43247a0fcfdf6c79f54a78adf5cc48228ea05",
}
R24_EXPECTED_COMPARISON_EXCLUSIONS = [
    "/provenance/start_utc",
    "/provenance/end_utc",
    "/provenance/monotonic_elapsed_seconds",
    "/provenance/pid",
    "/provenance/process_uuid",
    "/provenance/output_root_absolute",
    "/provenance/raw_argv",
    "/provenance/output_root_entry_evidence/output_root_contract/expected_leaf",
    "/phase_authorization",
    "/source_manifest/observed_workspace_imports",
]
OWNED_OUTPUT_ROOT: Path | None = None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_hash(value: object) -> str:
    payload = json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def tensor_hash(value: torch.Tensor) -> str:
    tensor = value.detach().cpu().contiguous()
    return hashlib.sha256(tensor.numpy().tobytes()).hexdigest()


def parse_boxes(value: object) -> list[dict[str, Any]]:
    if hasattr(value, "tolist"):
        value = value.tolist()
    if isinstance(value, str):
        value = ast.literal_eval(value)
    if not isinstance(value, list):
        raise ValueError("bbox payload must be a list")
    return [dict(item) for item in value]


def image_path(root: Path, patient: object, study: object, raw: object) -> Path:
    patient_text = str(int(patient))
    return (
        root
        / f"p{patient_text[:2]}"
        / f"p{patient_text}"
        / f"s{int(study)}"
        / Path(str(raw)).name
    )


def parse_args() -> argparse.Namespace:
    base = Path(r"H:\Xiyao_Wang\000_Public Dataset\mimic_cxr_other")
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--bbox",
        type=Path,
        default=WORKSPACE / "data/official/chextemporal_81fd9cdd/gold_bboxes.parquet",
    )
    parser.add_argument(
        "--metadata",
        type=Path,
        default=base / "mimic-cxr-2.0.0-metadata.csv.gz",
    )
    parser.add_argument(
        "--license",
        type=Path,
        default=WORKSPACE / "data/official/chextemporal_81fd9cdd/LICENSE",
    )
    parser.add_argument(
        "--split",
        type=Path,
        default=base / "mimic-cxr-2.0.0-split.csv.gz",
    )
    parser.add_argument(
        "--image-root",
        type=Path,
        default=Path(
            r"H:\Xiyao_Wang\000_Public Dataset\mimic-cxr\mimic-cxr"
            r"\mimic-cxr-images\files"
        ),
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
        "2026-07-24-chextemporal-mimic-matcher-qualification-v3.md",
    )
    parser.add_argument(
        "--r24-protocol",
        type=Path,
        default=WORKSPACE / "refine-logs/CALIBRATION_PROTOCOL_R24_2026-07-24.md",
    )
    parser.add_argument(
        "--r24-certificate",
        type=Path,
        default=WORKSPACE / "artifacts/calibration/"
        "capes_ci_qptm_r24_reproduction_local_20260724_v1/"
        "reproduction_certificate.json",
    )
    parser.add_argument(
        "--r24-launcher-result",
        type=Path,
        default=WORKSPACE
        / "artifacts/calibration/r24_launcher_logs/launcher_process_result.json",
    )
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--process-id", choices=("a", "b"), required=True)
    parser.add_argument("--device", default="cuda:1")
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--bootstrap-replicates", type=int, default=10_000)
    return parser.parse_args()


def _validate_r24_prerequisite(args: argparse.Namespace) -> dict[str, Any]:
    paths = {
        "protocol": args.r24_protocol,
        "certificate": args.r24_certificate,
        "launcher_result": args.r24_launcher_result,
    }
    ledger = {}
    for name, path in paths.items():
        actual = sha256_file(path)
        if actual != R24_PREREQUISITE_PINS[name]:
            raise RuntimeError(f"R24 {name} hash mismatch: {actual}")
        ledger[name] = {
            "path": str(path.resolve()),
            "bytes": path.stat().st_size,
            "sha256": actual,
        }
    certificate = json.loads(args.r24_certificate.read_text(encoding="utf-8"))
    gate = certificate.get("independent_reproduction_gate", {})
    checks = gate.get("checks", {})
    if (
        certificate.get("status") != "PASS_R24_SYNTHETIC_ENGINEERING"
        or gate.get("passed") is not True
        or not isinstance(checks, dict)
        or len(checks) != 11
        or not all(value is True for value in checks.values())
        or gate.get("mismatch_count") != 0
        or gate.get("mismatch_paths") != []
        or gate.get("primary_canonical_sha256") != gate.get("replica_canonical_sha256")
        or gate.get("comparison_excludes_only") != R24_EXPECTED_COMPARISON_EXCLUSIONS
    ):
        raise RuntimeError("R24 parent certificate is not terminally green")
    launch = json.loads(args.r24_launcher_result.read_text(encoding="utf-8-sig"))
    if launch.get("exit_code") != 0 or launch.get("retry_attempted") is not False:
        raise RuntimeError("R24 scheduled launcher result is not terminally green")
    return ledger


def _strict_cohort(
    args: argparse.Namespace,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    frame = pd.read_parquet(args.bbox)
    frame = frame[frame["dataset"].str.casefold() == "mimic"].copy()
    frame["patient_num"] = pd.to_numeric(frame["patient_id"])
    frame["prior_study_num"] = pd.to_numeric(frame["study_id_prev"])
    frame["current_study_num"] = pd.to_numeric(frame["study_id_curr"])
    frame["prior_dicom"] = frame["img_path_prev"].map(lambda value: Path(value).stem)
    frame["current_dicom"] = frame["img_path_curr"].map(lambda value: Path(value).stem)
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

    metadata = pd.read_csv(
        args.metadata,
        usecols=[
            "dicom_id",
            "subject_id",
            "study_id",
            "Rows",
            "Columns",
            "StudyDate",
            "StudyTime",
            "ViewPosition",
        ],
    )
    split = pd.read_csv(
        args.split,
        usecols=["dicom_id", "subject_id", "study_id", "split"],
    )
    source = metadata.merge(
        split,
        on=["dicom_id", "subject_id", "study_id"],
        validate="one_to_one",
    )
    frame = frame.merge(
        source.add_prefix("prior_"),
        left_on=["prior_dicom", "patient_num", "prior_study_num"],
        right_on=["prior_dicom_id", "prior_subject_id", "prior_study_id"],
        how="left",
        validate="many_to_one",
    )
    frame = frame.merge(
        source.add_prefix("current_"),
        left_on=["current_dicom", "patient_num", "current_study_num"],
        right_on=["current_dicom_id", "current_subject_id", "current_study_id"],
        how="left",
        validate="many_to_one",
    )

    records = []
    exclusions: Counter[str] = Counter()
    for row in frame.itertuples():
        reasons = []
        if pd.isna(row.prior_split) or pd.isna(row.current_split):
            reasons.append("metadata_or_split_missing")
        elif row.prior_split != "train" or row.current_split != "train":
            reasons.append("not_official_train")
        prior_time = (float(row.prior_StudyDate), float(row.prior_StudyTime))
        current_time = (float(row.current_StudyDate), float(row.current_StudyTime))
        if not prior_time < current_time:
            reasons.append("not_strictly_chronological")
        if (
            row.prior_ViewPosition not in {"AP", "PA"}
            or row.current_ViewPosition != row.prior_ViewPosition
        ):
            reasons.append("view_mismatch")
        if int(row.target_count) != 1:
            reasons.append("target_conflict")

        prior_raw = parse_boxes(row.prior_bboxes)
        current_raw = parse_boxes(row.current_bboxes)
        prior_labels = [str(box["label"]) for box in prior_raw]
        current_labels = [str(box["label"]) for box in current_raw]
        try:
            support = correspondence_support(
                row.progression, prior_labels, current_labels
            )
        except ValueError:
            support = {"compatible": False, "shared": [], "deaths": [], "births": []}
            reasons.append("duplicate_box_label")
        if not support["compatible"]:
            reasons.append("progression_support_incompatible")

        prior_path = image_path(
            args.image_root,
            row.patient_id,
            row.study_id_prev,
            row.img_path_prev,
        )
        current_path = image_path(
            args.image_root,
            row.patient_id,
            row.study_id_curr,
            row.img_path_curr,
        )
        if not prior_path.is_file() or not current_path.is_file():
            reasons.append("parent_image_missing")
        try:
            prior_boxes = [
                map_annotation_box(
                    box,
                    rows=int(row.prior_Rows),
                    columns=int(row.prior_Columns),
                )
                for box in prior_raw
            ]
            current_boxes = [
                map_annotation_box(
                    box,
                    rows=int(row.current_Rows),
                    columns=int(row.current_Columns),
                )
                for box in current_raw
            ]
        except (TypeError, ValueError):
            prior_boxes = []
            current_boxes = []
            reasons.append("coordinate_invalid")
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
                "qualification_id": hashlib.sha256(
                    record_key.encode("utf-8")
                ).hexdigest()[:20],
                "patient_id": str(row.patient_id),
                "prior_study_id": str(row.study_id_prev),
                "current_study_id": str(row.study_id_curr),
                "prior_dicom_id": row.prior_dicom,
                "current_dicom_id": row.current_dicom,
                "prior_path": str(prior_path),
                "current_path": str(current_path),
                "view": row.prior_ViewPosition,
                "disease_name": row.disease_name,
                "progression": row.progression,
                "prior_boxes": [box.__dict__ for box in prior_boxes],
                "current_boxes": [box.__dict__ for box in current_boxes],
                "shared_count": len(support["shared"]),
                "death_count": len(support["deaths"]),
                "birth_count": len(support["births"]),
            }
        )
    records.sort(key=lambda item: item["qualification_id"])
    audit = {
        "input_mimic_rows": len(frame),
        "retained_rows": len(records),
        "retained_patients": len({item["patient_id"] for item in records}),
        "retained_pairs": len(
            {
                (
                    item["patient_id"],
                    item["prior_study_id"],
                    item["current_study_id"],
                )
                for item in records
            }
        ),
        "label_counts": dict(Counter(item["progression"] for item in records)),
        "exclusions": dict(sorted(exclusions.items())),
    }
    if len(records) != EXPECTED_ROWS:
        raise RuntimeError(
            f"strict cohort drift: expected {EXPECTED_ROWS}, got {len(records)}"
        )
    return records, audit


def _load_encoder(weights: Path, device: torch.device) -> torch.nn.Module:
    checkpoint = torch.load(weights, map_location="cpu", weights_only=True)
    model = timm.create_model("vit_base_patch16_224", pretrained=False, num_classes=0)
    result = model.load_state_dict(checkpoint.get("model", checkpoint), strict=True)
    if result.missing_keys or result.unexpected_keys:
        raise RuntimeError("strict encoder load failed")
    return model.eval().to(device)


def _crop_key(path: str, box: dict[str, Any]) -> str:
    return canonical_hash({"path": path, "box": box})


def _extract_features(
    records: list[dict[str, Any]],
    model: torch.nn.Module,
    device: torch.device,
    batch_size: int,
) -> tuple[dict[str, torch.Tensor], list[dict[str, Any]], float, float]:
    tasks: dict[str, tuple[str, dict[str, Any]]] = {}
    for record in records:
        for side in ("prior", "current"):
            path = record[f"{side}_path"]
            for box in record[f"{side}_boxes"]:
                tasks[_crop_key(path, box)] = (path, box)
    ordered = sorted(tasks.items())
    preprocessing = transforms.Compose(
        [
            transforms.Resize((224, 224), antialias=True),
            transforms.ToTensor(),
            transforms.Normalize(CLIP_MEAN, CLIP_STD),
        ]
    )
    features: dict[str, torch.Tensor] = {}
    start = time.perf_counter()
    torch.cuda.reset_peak_memory_stats(device)
    with torch.inference_mode():
        for batch_start in range(0, len(ordered), batch_size):
            chunk = ordered[batch_start : batch_start + batch_size]
            images = []
            for _, (path, box) in chunk:
                bounds = (
                    math.floor(box["x1"]),
                    math.floor(box["y1"]),
                    math.ceil(box["x2"]),
                    math.ceil(box["y2"]),
                )
                with Image.open(path) as image:
                    crop = image.convert("RGB").crop(bounds)
                    images.append(preprocessing(crop))
            batch = torch.stack(images).to(device)
            encoded = model.forward_features(batch)[:, 0].detach().cpu()
            if not bool(torch.isfinite(encoded).all()):
                raise RuntimeError("non-finite crop feature")
            for (key, _), feature in zip(chunk, encoded):
                features[key] = feature
    torch.cuda.synchronize(device)
    elapsed = time.perf_counter() - start

    sample = ordered[: min(batch_size, len(ordered))]
    repeated = []
    with torch.inference_mode():
        for _, (path, box) in sample:
            bounds = (
                math.floor(box["x1"]),
                math.floor(box["y1"]),
                math.ceil(box["x2"]),
                math.ceil(box["y2"]),
            )
            with Image.open(path) as image:
                repeated.append(preprocessing(image.convert("RGB").crop(bounds)))
        second = model.forward_features(torch.stack(repeated).to(device))[:, 0].cpu()
    first = torch.stack([features[key] for key, _ in sample])
    max_repeat_difference = float((first - second).abs().max())
    ledger = [
        {
            "crop_key": key,
            "path": value[0],
            "box": value[1],
            "feature_sha256": tensor_hash(features[key]),
        }
        for key, value in ordered
    ]
    return features, ledger, elapsed, max_repeat_difference


def _region_batch(
    record: dict[str, Any],
    features: dict[str, torch.Tensor],
    variant: str,
) -> RegionBatch:
    prior_labels = [box["label"] for box in record["prior_boxes"]]
    current_labels = [box["label"] for box in record["current_boxes"]]
    prior_ids, current_ids = entity_ids(prior_labels, current_labels)
    visual_dim = next(iter(features.values())).numel()

    def side_features(side: str) -> torch.Tensor:
        rows = []
        path = record[f"{side}_path"]
        for box in record[f"{side}_boxes"]:
            visual = features[_crop_key(path, box)]
            geometry = torch.tensor(
                (
                    (box["x1"] + box["x2"]) / 448.0,
                    (box["y1"] + box["y2"]) / 448.0,
                    (box["x2"] - box["x1"]) / 224.0,
                    (box["y2"] - box["y1"]) / 224.0,
                ),
                dtype=visual.dtype,
            )
            if variant == "visual_only":
                identity = visual
            elif variant == "geometry_only":
                identity = geometry
            elif variant == "visual_geometry_equal":
                identity = torch.cat((geometry, visual))
            else:
                raise ValueError(f"unknown variant {variant}")
            rows.append(torch.cat((torch.zeros(2, dtype=visual.dtype), identity)))
        if not rows:
            identity_dim = {
                "visual_only": visual_dim,
                "geometry_only": 4,
                "visual_geometry_equal": visual_dim + 4,
            }.get(variant)
            if identity_dim is None:
                raise ValueError(f"unknown variant {variant}")
            return torch.empty((1, 0, identity_dim + 2))
        return torch.stack(rows).unsqueeze(0)

    prior = side_features("prior")
    current = side_features("current")
    return RegionBatch(
        prior_features=prior,
        current_features=current,
        prior_valid=torch.ones(1, prior.shape[1], dtype=torch.bool),
        current_valid=torch.ones(1, current.shape[1], dtype=torch.bool),
        prior_anatomy=torch.zeros(1, prior.shape[1], dtype=torch.long),
        current_anatomy=torch.zeros(1, current.shape[1], dtype=torch.long),
        prior_entity_ids=prior_ids.unsqueeze(0),
        current_entity_ids=current_ids.unsqueeze(0),
        prior_boxes=torch.tensor(
            [
                [
                    [box[name] for name in ("x1", "y1", "x2", "y2")]
                    for box in record["prior_boxes"]
                ]
            ]
        ).reshape(1, -1, 4),
        current_boxes=torch.tensor(
            [
                [
                    [box[name] for name in ("x1", "y1", "x2", "y2")]
                    for box in record["current_boxes"]
                ]
            ]
        ).reshape(1, -1, 4),
        prior_source_ids=torch.arange(prior.shape[1]).unsqueeze(0),
        current_source_ids=(torch.arange(current.shape[1]) + prior.shape[1]).unsqueeze(
            0
        ),
    )


def _matcher(regions: RegionBatch, variant: str) -> InvariantPartialOTMatcher:
    feature_dim = regions.prior_features.shape[-1]
    if variant == "visual_geometry_equal":
        identity_views = ((2, 6), (6, feature_dim))
    else:
        identity_views = ((2, feature_dim),)
    return InvariantPartialOTMatcher(
        feature_dim,
        identity_views=identity_views,
        anatomy_constrained=True,
    ).eval()


def _evaluate(
    records: list[dict[str, Any]],
    features: dict[str, torch.Tensor],
    bootstrap_replicates: int,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    variants = ("visual_only", "geometry_only", "visual_geometry_equal")
    patient_statistics = {name: defaultdict(list) for name in variants}
    row_outputs = []
    global_greedy_dominance = True
    b4_correct: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    b4_deranged: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    b4_checks = []

    for row_index, record in enumerate(records):
        output = {
            "qualification_id": record["qualification_id"],
            "patient_id": record["patient_id"],
            "variants": {},
        }
        for variant in variants:
            regions = _region_batch(record, features, variant)
            gold = oracle_plan_from_entity_ids(regions)
            matcher = _matcher(regions, variant)
            edge, prior_null, current_null = matcher.compute_utilities(regions)
            predicted = matcher.plan_from_utilities(
                regions, edge, prior_null, current_null, hard=True
            )
            statistics = match_sufficient_statistics(predicted, gold, regions)
            patient_statistics[variant][record["patient_id"]].append(statistics)
            output["variants"][variant] = {
                "statistics": statistics,
                "plan_sha256": tensor_hash(predicted.transport),
            }
            if variant == "visual_geometry_equal":
                greedy = greedy_plan_from_utilities(
                    regions, edge, prior_null, current_null
                )
                global_objective = plan_objective(
                    predicted, regions, edge, prior_null, current_null
                )
                greedy_objective = plan_objective(
                    greedy, regions, edge, prior_null, current_null
                )
                dominates = global_objective + 1e-7 >= greedy_objective
                global_greedy_dominance = global_greedy_dominance and dominates
                output["global_objective"] = global_objective
                output["greedy_objective"] = greedy_objective

                if record["shared_count"] >= 2:
                    deranged = anatomy_compatible_derangement(
                        regions,
                        gold,
                        seed=BOOTSTRAP_SEED + row_index,
                    )
                    correct_stats = match_sufficient_statistics(
                        predicted, gold, regions
                    )
                    deranged_stats = match_sufficient_statistics(
                        predicted, deranged, regions
                    )
                    b4_correct[record["patient_id"]].append(correct_stats)
                    b4_deranged[record["patient_id"]].append(deranged_stats)
                    candidates = build_soft_relation_candidates(regions, gold)
                    allocation = DeterministicGlobalAllocator()(candidates)
                    gold_tokens = assemble_capes_ci_tokens(regions, gold, allocation)
                    deranged_tokens = assemble_capes_ci_tokens(
                        regions, deranged, allocation
                    )
                    prior_count = regions.prior_features.shape[1]
                    current_count = regions.current_features.shape[1]
                    null_equal = torch.equal(
                        gold.transport[:, :prior_count, current_count],
                        deranged.transport[:, :prior_count, current_count],
                    ) and torch.equal(
                        gold.transport[:, prior_count, :current_count],
                        deranged.transport[:, prior_count, :current_count],
                    )
                    oracle_real = gold.transport[:, :prior_count, :current_count]
                    deranged_real = deranged.transport[:, :prior_count, :current_count]
                    zero_fixed = not bool(
                        ((oracle_real > 0.5) & (deranged_real > 0.5)).any()
                    )
                    structural_checks = {
                        "null_sets_equal": null_equal,
                        "zero_fixed_persistent_edges": zero_fixed,
                        "assignments_differ": not torch.equal(
                            gold.transport, deranged.transport
                        ),
                        "token_shape_equal": (
                            gold_tokens.tokens.shape == deranged_tokens.tokens.shape
                        ),
                        "token_budget_exact64": (
                            gold_tokens.tokens.shape[1] == 64
                            and deranged_tokens.tokens.shape[1] == 64
                        ),
                        "token_types_equal": torch.equal(
                            gold_tokens.token_types, deranged_tokens.token_types
                        ),
                        "token_valid_mask_equal": torch.equal(
                            gold_tokens.valid_mask, deranged_tokens.valid_mask
                        ),
                        "entity_tokens_equal": torch.equal(
                            gold_tokens.tokens[:, 4:32],
                            deranged_tokens.tokens[:, 4:32],
                        ),
                        "relation_tokens_differ": not torch.equal(
                            gold_tokens.tokens[:, 32:60],
                            deranged_tokens.tokens[:, 32:60],
                        ),
                        "optimizer_contract_both_none": True,
                    }
                    structural = {
                        "qualification_id": record["qualification_id"],
                        "checks": structural_checks,
                        "hashes": {
                            "prior_features": tensor_hash(regions.prior_features),
                            "current_features": tensor_hash(regions.current_features),
                            "allocation_weights": tensor_hash(allocation.weights),
                            "gold_assignment": tensor_hash(gold.transport),
                            "deranged_assignment": tensor_hash(deranged.transport),
                        },
                        "passed": all(structural_checks.values()),
                    }
                    b4_checks.append(structural)
        row_outputs.append(output)

    aggregate = {
        variant: patient_cluster_bootstrap(
            patient_statistics[variant],
            seed=BOOTSTRAP_SEED,
            replicates=bootstrap_replicates,
        )
        for variant in variants
    }
    b4_bootstrap = patient_cluster_bootstrap(
        b4_correct,
        seed=BOOTSTRAP_SEED,
        replicates=bootstrap_replicates,
        randomized_patient_statistics=b4_deranged,
    )
    mechanics = {
        "global_objective_never_below_greedy": global_greedy_dominance,
        "b4_rows": len(b4_checks),
        "b4_all_passed": all(item["passed"] for item in b4_checks),
        "b4_checks": b4_checks,
        "b4_bootstrap": b4_bootstrap,
    }
    return aggregate, row_outputs, mechanics


def main() -> int:
    global OWNED_OUTPUT_ROOT
    args = parse_args()
    start_utc = datetime.now(timezone.utc).isoformat()
    process_uuid = str(uuid4())
    r24_prerequisite = _validate_r24_prerequisite(args)
    if args.output_root.exists():
        raise FileExistsError(args.output_root)
    args.output_root.mkdir(parents=True)
    OWNED_OUTPUT_ROOT = args.output_root
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required for the frozen encoder")
    device = torch.device(args.device)
    torch.cuda.set_device(device)
    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    torch.manual_seed(BOOTSTRAP_SEED)
    torch.cuda.manual_seed_all(BOOTSTRAP_SEED)
    torch.use_deterministic_algorithms(True)

    input_paths = {
        "bbox": args.bbox,
        "license": args.license,
        "metadata": args.metadata,
        "split": args.split,
        "weights": args.weights,
    }
    input_ledger = {}
    for name, path in input_paths.items():
        actual = sha256_file(path)
        if actual != PINS[name]:
            raise RuntimeError(f"{name} hash mismatch: {actual}")
        input_ledger[name] = {
            "path": str(path.resolve()),
            "bytes": path.stat().st_size,
            "sha256": actual,
        }
    protocol_text = args.protocol.read_text(encoding="utf-8")
    if "Status: `FROZEN_BEFORE_MODEL_ACCESS`" not in protocol_text:
        raise RuntimeError("qualification protocol is not frozen")
    protocol_hash = sha256_file(args.protocol)
    records, cohort_audit = _strict_cohort(args)
    image_paths = sorted(
        {
            Path(record[side])
            for record in records
            for side in ("prior_path", "current_path")
        },
        key=str,
    )
    image_ledger = []
    for path in image_paths:
        with Image.open(path) as image:
            width, height = image.size
        if (width, height) != (224, 224):
            raise RuntimeError(
                f"unexpected derivative image size: {path}={width}x{height}"
            )
        image_ledger.append(
            {
                "path": str(path),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
                "width": width,
                "height": height,
            }
        )
    (args.output_root / "cohort.json").write_text(
        json.dumps(records, indent=2, sort_keys=True), encoding="utf-8"
    )
    (args.output_root / "image_ledger.json").write_text(
        json.dumps(image_ledger, indent=2, sort_keys=True), encoding="utf-8"
    )

    model = _load_encoder(args.weights, device)
    features, feature_ledger, extraction_seconds, repeat_difference = _extract_features(
        records, model, device, args.batch_size
    )
    peak_vram = int(torch.cuda.max_memory_allocated(device))
    del model
    torch.cuda.empty_cache()
    feature_path = args.output_root / "crop_features.pt"
    torch.save(features, feature_path)
    (args.output_root / "feature_ledger.json").write_text(
        json.dumps(feature_ledger, indent=2, sort_keys=True), encoding="utf-8"
    )

    aggregate, row_outputs, mechanics = _evaluate(
        records, features, args.bootstrap_replicates
    )
    (args.output_root / "per_row.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in row_outputs),
        encoding="utf-8",
    )
    primary = aggregate["visual_geometry_equal"]["point"]
    delta = mechanics["b4_bootstrap"]["persistent_edge_f1_delta"]
    gates = {
        "Q0_ASSET_LINEAGE": True,
        "Q1_COHORT_GEOMETRY": (
            cohort_audit["retained_rows"] == EXPECTED_ROWS and len(image_ledger) > 0
        ),
        "Q2_FEATURE_INTEGRITY": (
            repeat_difference == 0.0
            and all(item["feature_sha256"] for item in feature_ledger)
        ),
        "Q3_MATCHPLAN_MECHANICS": mechanics["global_objective_never_below_greedy"],
        "Q4_REAL_SIGNAL": (
            primary["persistent_edge_f1"] >= 0.50
            and primary["three_event_macro_f1"] >= 0.50
            and delta["lower"] > 0.0
        ),
        "Q5_B4_STRUCTURE": mechanics["b4_all_passed"],
    }
    first_failed = next((name for name, passed in gates.items() if not passed), None)
    status = (
        "AWAITING_FRESH_PROCESS_REPRODUCTION"
        if first_failed is None
        else f"FAIL_{first_failed}"
    )
    summary = {
        "evidence_class": EVIDENCE_CLASS,
        "formal_claim_allowed": False,
        "status": status,
        "first_failed_gate": first_failed,
        "process_id": args.process_id,
        "protocol": {
            "path": str(args.protocol.resolve()),
            "sha256": protocol_hash,
        },
        "r24_prerequisite": r24_prerequisite,
        "inputs": input_ledger,
        "cohort": cohort_audit,
        "image_ledger_sha256": canonical_hash(image_ledger),
        "feature_ledger_sha256": canonical_hash(feature_ledger),
        "prediction_sha256": canonical_hash(row_outputs),
        "aggregate_sha256": canonical_hash(aggregate),
        "gates": gates,
        "aggregate": aggregate,
        "mechanics": mechanics,
        "encoder": {
            "crop_count": len(feature_ledger),
            "extraction_seconds": extraction_seconds,
            "repeat_max_abs_difference": repeat_difference,
            "peak_vram_bytes": peak_vram,
            "feature_cache": {
                "path": feature_path.name,
                "bytes": feature_path.stat().st_size,
                "sha256": sha256_file(feature_path),
            },
        },
        "runtime": {
            "argv": sys.argv,
            "cwd": str(Path.cwd()),
            "start_utc": start_utc,
            "end_utc": datetime.now(timezone.utc).isoformat(),
            "pid": os.getpid(),
            "process_uuid": process_uuid,
            "python": sys.version,
            "platform": platform.platform(),
            "torch": torch.__version__,
            "timm": timm.__version__,
            "device": str(device),
            "gpu": torch.cuda.get_device_name(device),
            "bootstrap_seed": BOOTSTRAP_SEED,
            "bootstrap_replicates": args.bootstrap_replicates,
        },
        "source": {
            "runner_sha256": sha256_file(Path(__file__)),
            "module_sha256": sha256_file(
                WORKSPACE / "src/visualvit/real_qualification.py"
            ),
        },
        "interpretation_boundary": (
            "Real-data matcher qualification only; no per-box progression, "
            "clinical, formal B4, or frozen-VLM claim."
        ),
    }
    summary_path = args.output_root / "summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps({"status": status, "summary": str(summary_path)}, sort_keys=True))
    return 0 if first_failed is None else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as error:
        if OWNED_OUTPUT_ROOT is not None:
            failure = {
                "status": "TECHNICAL_FAILURE",
                "formal_claim_allowed": False,
                "error_type": type(error).__name__,
                "error": str(error),
                "traceback": traceback.format_exc(),
                "argv": sys.argv,
            }
            (OWNED_OUTPUT_ROOT / "failure.json").write_text(
                json.dumps(failure, indent=2, sort_keys=True), encoding="utf-8"
            )
        raise
