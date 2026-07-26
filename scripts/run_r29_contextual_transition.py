from __future__ import annotations

# ruff: noqa: E402

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import platform
import sys
import time
from typing import Any, Mapping, Sequence
import zipfile

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE))
sys.path.insert(0, str(WORKSPACE / "src"))

from PIL import Image
import torch
from torchvision import transforms

from scripts import audit_r26_binding_identifiability as r27
from scripts import build_r29_fresh_silver_cohort as cohort_builder
from scripts import run_chest_imagenome_mimic_matcher_qualification as r25
from visualvit.context_transition import (
    BOX_NAMES,
    expand_box,
    fit_transition_head,
    geometry_features,
    map_anatomy,
    pair_interactions,
    union_box,
)
from visualvit.real_progression import (
    classification_metrics,
    hierarchical_patient_bootstrap,
)
from visualvit.tier import signed_random_projection


LABELS = cohort_builder.LABELS
SYSTEMS = (
    "state",
    "global_transition",
    "local_transition",
    "uniform_fusion",
    "context_transition",
)
TRAINING_SEEDS = (17, 29, 43)
PROJECTION_DIM = 256
PROJECTION_SEED_BASE = 20260729
HEAD_STEPS = 350
BOOTSTRAP_REPLICATES = 10_000
COHORT_ROOT = cohort_builder.OUTPUT_ROOT_DEFAULT
COHORT_SHA256 = (
    "0a52d2c84c99c9c3cdc91063b801eb3c0d1304dfa454c16e55c86edbd2197d6e"
)
PROTOCOL_PATH = cohort_builder.PROTOCOL_PATH
PROTOCOL_SHA256 = cohort_builder.PROTOCOL_SHA256
WEIGHTS = r25.WEIGHTS_DEFAULT
WEIGHTS_SHA256 = r25.MIMIC_PINS["weights"]
OUTPUT_ROOT_DEFAULT = Path(
    r"F:\VisualVIT_runtime\050_routeC\r29_contextual_transition\run_v1"
)
REPORT_PATH_DEFAULT = WORKSPACE / "reports/R29_CONTEXTUAL_TRANSITION_RESULT.md"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="R29 fresh-silver contextual transition experiment"
    )
    parser.add_argument("--cohort-root", type=Path, default=COHORT_ROOT)
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT_DEFAULT)
    parser.add_argument("--report-path", type=Path, default=REPORT_PATH_DEFAULT)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--batch-size", type=int, default=64)
    return parser.parse_args()


def _box_dict(box: Sequence[float]) -> dict[str, float]:
    return dict(zip(("x1", "y1", "x2", "y2"), map(float, box), strict=True))


def _feature_key(path: str, box: Sequence[float]) -> str:
    return r27.canonical_sha256(
        {"path": path, "box": [round(float(value), 6) for value in box]}
    )


def prepare_records(
    records: Sequence[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    active = [
        dict(record)
        for record in records
        if record["partition"] != "sealed_reserve"
    ]
    scene_cache: dict[str, dict[str, Any]] = {}
    fallback = 0
    area_ratios = []
    view_changes = 0
    with zipfile.ZipFile(cohort_builder.SCENE_ZIP) as archive:
        for record in active:
            scenes = {}
            for side in ("prior", "current"):
                name = record[f"{side}_scene"]
                if name not in scene_cache:
                    scene_cache[name] = json.loads(archive.read(name))
                scenes[side] = scene_cache[name]
            side_mappings = {}
            for side in ("prior", "current"):
                available = {
                    str(value["bbox_name"]).lower()
                    for value in scenes[side]["objects"]
                }
                side_mappings[side] = map_anatomy(
                    record["anatomy"], available
                )
                record[f"{side}_mapped_anatomy"] = side_mappings[side]
                exact = union_box(
                    scenes[side]["objects"], side_mappings[side]
                )
                context = expand_box(exact, factor=1.5)
                record[f"{side}_exact_box"] = list(exact)
                record[f"{side}_context_box"] = list(context)
            record["mapped_anatomy"] = sorted(
                set(side_mappings["prior"]) | set(side_mappings["current"])
            )
            fallback += int(
                side_mappings["prior"] != side_mappings["current"]
            )
            exact = record["current_exact_box"]
            context = record["current_context_box"]
            exact_area = (exact[2] - exact[0]) * (exact[3] - exact[1])
            context_area = (context[2] - context[0]) * (context[3] - context[1])
            area_ratios.append(exact_area / (224.0 * 224.0))
            record["context_to_exact_area_ratio"] = context_area / max(
                exact_area, 1e-8
            )
            view_changes += int(
                str(record["prior_view"]).upper()
                != str(record["current_view"]).upper()
            )
    sorted_area = sorted(area_ratios)
    audit = {
        "active_records": len(active),
        "scene_graphs_loaded": len(scene_cache),
        "cross_time_anatomy_fallback_records": fallback,
        "cross_time_anatomy_fallback_rate": fallback / len(active),
        "exact_area_ratio_median": sorted_area[len(sorted_area) // 2],
        "exact_area_ratio_p10": sorted_area[len(sorted_area) // 10],
        "view_change_rate": view_changes / len(active),
    }
    return active, audit


def extract_features(
    records: Sequence[Mapping[str, Any]],
    *,
    device: torch.device,
    batch_size: int,
) -> tuple[dict[str, torch.Tensor], dict[str, Any]]:
    tasks: dict[str, tuple[str, tuple[float, float, float, float]]] = {}
    for record in records:
        for side in ("prior", "current"):
            path = str(record[f"{side}_path"])
            for box in (
                (0.0, 0.0, 224.0, 224.0),
                tuple(record[f"{side}_exact_box"]),
                tuple(record[f"{side}_context_box"]),
            ):
                tasks[_feature_key(path, box)] = (path, box)
    ordered = sorted(tasks.items())
    model = r25._load_encoder(WEIGHTS, device)
    preprocessing = transforms.Compose(
        [
            transforms.Resize((224, 224), antialias=True),
            transforms.ToTensor(),
            transforms.Normalize(r25.CLIP_MEAN, r25.CLIP_STD),
        ]
    )
    features = {}
    start = time.perf_counter()
    torch.cuda.reset_peak_memory_stats(device)
    with torch.inference_mode():
        for offset in range(0, len(ordered), batch_size):
            chunk = ordered[offset : offset + batch_size]
            images = []
            for _, (path, box) in chunk:
                bounds = (
                    math.floor(box[0]),
                    math.floor(box[1]),
                    math.ceil(box[2]),
                    math.ceil(box[3]),
                )
                with Image.open(path) as image:
                    images.append(
                        preprocessing(image.convert("RGB").crop(bounds))
                    )
            encoded = model.forward_features(
                torch.stack(images).to(device)
            )[:, 0].cpu()
            if not bool(torch.isfinite(encoded).all()):
                raise RuntimeError("non-finite R29 encoder feature")
            for (key, _), value in zip(chunk, encoded, strict=True):
                features[key] = value
            if offset % (batch_size * 25) == 0:
                print(
                    json.dumps(
                        {
                            "stage": "feature_extraction",
                            "complete": min(offset + len(chunk), len(ordered)),
                            "total": len(ordered),
                        }
                    ),
                    flush=True,
                )
    torch.cuda.synchronize(device)
    audit = {
        "tasks": len(ordered),
        "feature_dim": int(next(iter(features.values())).numel()),
        "runtime_seconds": time.perf_counter() - start,
        "peak_cuda_bytes": int(torch.cuda.max_memory_allocated(device)),
        "finite": True,
    }
    del model
    torch.cuda.empty_cache()
    return features, audit


def build_representations(
    records: Sequence[Mapping[str, Any]],
    features: Mapping[str, torch.Tensor],
) -> tuple[dict[str, torch.Tensor], torch.Tensor, dict[str, Any]]:
    finding_vocab = sorted({str(row["finding_token"]) for row in records})
    finding_index = {value: index for index, value in enumerate(finding_vocab)}
    box_index = {value: index for index, value in enumerate(BOX_NAMES)}
    raw = {
        name: []
        for name in (
            "state",
            "global_transition",
            "local_transition",
            "context_transition",
        )
    }
    targets = []
    label_index = {value: index for index, value in enumerate(LABELS)}
    for record in records:
        query = torch.zeros(
            len(finding_vocab) + len(BOX_NAMES), dtype=torch.float32
        )
        query[finding_index[str(record["finding_token"])]] = 1.0
        for name in record["mapped_anatomy"]:
            if name in box_index:
                query[len(finding_vocab) + box_index[name]] = 1.0

        values = {}
        for side in ("prior", "current"):
            path = str(record[f"{side}_path"])
            values[f"{side}_global"] = features[
                _feature_key(path, (0.0, 0.0, 224.0, 224.0))
            ]
            values[f"{side}_exact"] = features[
                _feature_key(path, record[f"{side}_exact_box"])
            ]
            values[f"{side}_context"] = features[
                _feature_key(path, record[f"{side}_context_box"])
            ]
        raw["state"].append(
            torch.cat((values["current_global"].float(), query))
        )
        global_pair = pair_interactions(
            values["prior_global"], values["current_global"]
        )
        local_pair = pair_interactions(
            values["prior_exact"], values["current_exact"]
        )
        context_pair = pair_interactions(
            values["prior_context"], values["current_context"]
        )
        raw["global_transition"].append(torch.cat((global_pair, query)))
        raw["local_transition"].append(torch.cat((local_pair, query)))
        prior_geometry = geometry_features(
            record["prior_exact_box"],
            record["prior_context_box"],
            record["prior_view"],
            record["current_view"],
        )
        current_geometry = geometry_features(
            record["current_exact_box"],
            record["current_context_box"],
            record["prior_view"],
            record["current_view"],
        )
        raw["context_transition"].append(
            torch.cat(
                (
                    global_pair,
                    local_pair,
                    context_pair,
                    prior_geometry,
                    current_geometry,
                    query,
                )
            )
        )
        targets.append(label_index[str(record["progression"])])
    projected = {}
    projection_hashes = {}
    raw_dims = {}
    for index, name in enumerate(raw):
        values = torch.stack(raw[name])
        raw_dims[name] = int(values.shape[1])
        projected[name], projection_hashes[name] = signed_random_projection(
            values,
            output_dim=PROJECTION_DIM,
            seed=PROJECTION_SEED_BASE + index,
        )
    return (
        projected,
        torch.tensor(targets, dtype=torch.long),
        {
            "finding_vocab": finding_vocab,
            "box_vocab": list(BOX_NAMES),
            "raw_dims": raw_dims,
            "projection_hashes": projection_hashes,
            "projection_dim": PROJECTION_DIM,
        },
    )


def _indices(
    records: Sequence[Mapping[str, Any]], partitions: Sequence[str]
) -> torch.Tensor:
    allowed = set(partitions)
    return torch.tensor(
        [
            index
            for index, record in enumerate(records)
            if record["partition"] in allowed
        ],
        dtype=torch.long,
    )


def _prediction_rows(
    records: Sequence[Mapping[str, Any]],
    indices: torch.Tensor,
    system: str,
    seed: int,
    predictions: torch.Tensor,
) -> list[dict[str, Any]]:
    selected = [records[index] for index in indices.tolist()]
    patient_sizes = Counter(str(row["patient_id"]) for row in selected)
    return [
        {
            "patient_id": str(record["patient_id"]),
            "observation_id": str(record["record_id"]),
            "training_seed": seed,
            "derangement_id": 0,
            "system": system,
            "target": str(record["progression"]),
            "prediction": LABELS[int(prediction)],
            "weight": 1.0 / patient_sizes[str(record["patient_id"])],
        }
        for record, prediction in zip(selected, predictions.tolist(), strict=True)
    ]


def fit_systems(
    records: Sequence[Mapping[str, Any]],
    representations: Mapping[str, torch.Tensor],
    targets: torch.Tensor,
    train_indices: torch.Tensor,
    eval_indices: torch.Tensor,
    *,
    device: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows = []
    audits = []
    expert_names = ("state", "global_transition", "local_transition")
    for seed in TRAINING_SEEDS:
        logits = {}
        for name in (*expert_names, "context_transition"):
            logits[name], fit = fit_transition_head(
                representations[name][train_indices],
                targets[train_indices],
                representations[name][eval_indices],
                seed=seed,
                class_count=len(LABELS),
                steps=HEAD_STEPS,
                device=device,
            )
            audits.append({"system": name, "stage": "head", **fit})
            rows.extend(
                _prediction_rows(
                    records,
                    eval_indices,
                    name,
                    seed,
                    logits[name].argmax(-1),
                )
            )
        uniform = torch.stack([logits[name] for name in expert_names]).mean(0)
        rows.extend(
            _prediction_rows(
                records,
                eval_indices,
                "uniform_fusion",
                seed,
                uniform.argmax(-1),
            )
        )
    return rows, audits


def point_delta(rows: Sequence[dict[str, Any]]) -> tuple[float, dict[str, float]]:
    directions = {}
    for seed in TRAINING_SEEDS:
        selected = [row for row in rows if row["training_seed"] == seed]
        context = classification_metrics(
            [row for row in selected if row["system"] == "context_transition"],
            labels=LABELS,
        )["patient_balanced"]["macro_f1"]
        uniform = classification_metrics(
            [row for row in selected if row["system"] == "uniform_fusion"],
            labels=LABELS,
        )["patient_balanced"]["macro_f1"]
        directions[str(seed)] = float(context - uniform)
    return sum(directions.values()) / len(directions), directions


def render_report(
    dev: Mapping[str, Any], test: Mapping[str, Any] | None
) -> str:
    lines = [
        "# R29 Fresh-Silver Contextual Transition Result",
        "",
        "Date: 2026-07-26",
        "",
        "Evidence class: `NON_CONFIRMATORY_FRESH_SILVER_DEVELOPMENT`",
        "",
        "## Development survival",
        "",
        f"- Context minus uniform: {100*dev['delta']:+.2f} pp",
        f"- Seed directions: {dev['directions']}",
        f"- Shuffled-label macro F1: {dev['shuffled_macro_f1']:.4f}",
        f"- Gate: {'PASS' if dev['passed'] else 'FAIL'}",
        "",
    ]
    if test is None:
        lines.extend(
            [
                "## Test",
                "",
                "Test remained sealed because the development survival gate failed.",
                "",
            ]
        )
    else:
        contrast = test["bootstrap"]["contrasts"]["context_minus_uniform"]
        interval = contrast["interval"]
        lines.extend(
            [
                "## One-shot sealed test",
                "",
                f"- Context minus uniform: {contrast['point_pp']:+.2f} pp",
                f"- 95% CI: [{100*interval['lower']:+.2f}, "
                f"{100*interval['upper']:+.2f}] pp",
                f"- Seed directions: {test['directions']}",
                f"- Scientific verdict: {'GO' if test['scientific_go'] else 'NO-GO'}",
                "",
            ]
        )
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    if args.output_root.exists():
        raise FileExistsError(f"output root must be fresh: {args.output_root}")
    if args.report_path.exists():
        raise FileExistsError(f"report path must be fresh: {args.report_path}")
    if r27.sha256_file(PROTOCOL_PATH) != PROTOCOL_SHA256:
        raise RuntimeError("R29 protocol hash mismatch")
    if r27.sha256_file(args.cohort_root / "cohort.json") != COHORT_SHA256:
        raise RuntimeError("R29 cohort hash mismatch")
    if r27.sha256_file(WEIGHTS) != WEIGHTS_SHA256:
        raise RuntimeError("BiomedCLIP weights hash mismatch")
    device = torch.device(args.device)
    if device.type != "cuda" or device.index != 0:
        raise ValueError("R29 is frozen to shared-safe cuda:0")

    records = r27.read_json(args.cohort_root / "cohort.json", list)
    records, case_audit = prepare_records(records)
    features, extraction_audit = extract_features(
        records, device=device, batch_size=args.batch_size
    )
    representations, targets, representation_manifest = build_representations(
        records, features
    )
    train_indices = _indices(records, ("train",))
    dev_indices = _indices(records, ("dev",))
    test_indices = _indices(records, ("test",))
    if (
        {records[index]["patient_id"] for index in train_indices.tolist()}
        & {records[index]["patient_id"] for index in dev_indices.tolist()}
    ):
        raise RuntimeError("train/dev patient leakage")

    dev_rows, dev_fit = fit_systems(
        records,
        representations,
        targets,
        train_indices,
        dev_indices,
        device=args.device,
    )
    dev_delta, dev_directions = point_delta(dev_rows)
    generator = torch.Generator().manual_seed(20260729)
    shuffled_targets = targets[train_indices][
        torch.randperm(len(train_indices), generator=generator)
    ]
    shuffled_logits, shuffled_fit = fit_transition_head(
        representations["context_transition"][train_indices],
        shuffled_targets,
        representations["context_transition"][dev_indices],
        seed=20260729,
        class_count=len(LABELS),
        steps=HEAD_STEPS,
        device=args.device,
    )
    shuffled_rows = _prediction_rows(
        records,
        dev_indices,
        "context_transition",
        20260729,
        shuffled_logits.argmax(-1),
    )
    shuffled_macro_f1 = classification_metrics(
        shuffled_rows, labels=LABELS
    )["patient_balanced"]["macro_f1"]
    dev_gate = {
        "delta": dev_delta,
        "directions": dev_directions,
        "shuffled_macro_f1": shuffled_macro_f1,
        "checks": {
            "DELTA_AT_LEAST_1PP": dev_delta >= 0.01,
            "TWO_OF_THREE_DIRECTIONS_POSITIVE": (
                sum(value > 0 for value in dev_directions.values()) >= 2
            ),
            "SHUFFLED_BELOW_0_45": shuffled_macro_f1 < 0.45,
            "FITS_FINITE": all(value["finite"] for value in dev_fit)
            and shuffled_fit["finite"],
            "PATIENT_DISJOINT": True,
            "FORBIDDEN_INPUTS_ABSENT": True,
        },
    }
    dev_gate["passed"] = all(dev_gate["checks"].values())

    test_result = None
    test_rows: list[dict[str, Any]] = []
    test_fit: list[dict[str, Any]] = []
    if dev_gate["passed"]:
        train_dev_indices = _indices(records, ("train", "dev"))
        test_rows, test_fit = fit_systems(
            records,
            representations,
            targets,
            train_dev_indices,
            test_indices,
            device=args.device,
        )
        bootstrap = hierarchical_patient_bootstrap(
            test_rows,
            labels=LABELS,
            systems=SYSTEMS,
            seeds=TRAINING_SEEDS,
            derangements=(0,),
            contrasts={
                "context_minus_uniform": (
                    "context_transition",
                    "uniform_fusion",
                )
            },
            invariant_systems=SYSTEMS,
            replicates=BOOTSTRAP_REPLICATES,
            rng_seed=20260729,
        )
        _, directions = point_delta(test_rows)
        point = bootstrap["point_system_macro_f1"]
        strongest = max(
            ("state", "global_transition", "local_transition"),
            key=lambda name: point[name],
        )
        contrast = bootstrap["contrasts"]["context_minus_uniform"]
        scientific = (
            contrast["point_pp"] >= 2.0
            and contrast["interval"] is not None
            and contrast["interval"]["lower"] > 0
            and all(value > 0 for value in directions.values())
            and point["context_transition"] - point[strongest] >= -0.01
            and bootstrap["inference_valid"]
        )
        test_result = {
            "bootstrap": bootstrap,
            "directions": directions,
            "strongest_single": strongest,
            "scientific_go": scientific,
        }

    args.output_root.mkdir(parents=True, exist_ok=False)
    torch.save(features, args.output_root / "feature_cache.pt")
    payloads = {
        "case_audit.json": case_audit,
        "extraction_audit.json": extraction_audit,
        "representation_manifest.json": representation_manifest,
        "dev_predictions.json": dev_rows,
        "dev_fit_audit.json": [*dev_fit, {"system": "shuffled", **shuffled_fit}],
        "dev_gate.json": dev_gate,
        "test_predictions.json": test_rows,
        "test_fit_audit.json": test_fit,
        "test_result.json": test_result,
    }
    for name, payload in payloads.items():
        r27.write_json_exclusive(args.output_root / name, payload)
    report = render_report(dev_gate, test_result)
    args.report_path.write_text(report, encoding="utf-8")
    status = (
        "AWAITING_FRESH_PROCESS_REPRODUCTION"
        if test_result is not None
        else "STOP_R29_DEV_SURVIVAL"
    )
    manifest_base = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "protocol_sha256": PROTOCOL_SHA256,
        "cohort_sha256": COHORT_SHA256,
        "weights_sha256": WEIGHTS_SHA256,
        "source_hashes": {
            "scripts/run_r29_contextual_transition.py": r27.sha256_file(
                Path(__file__)
            ),
            "src/visualvit/context_transition.py": r27.sha256_file(
                WORKSPACE / "src/visualvit/context_transition.py"
            ),
        },
        "outputs": {
            name: r27.sha256_file(args.output_root / name) for name in payloads
        },
        "feature_cache_sha256": r27.sha256_file(
            args.output_root / "feature_cache.pt"
        ),
        "report": {
            "path": str(args.report_path),
            "sha256": r27.sha256_file(args.report_path),
        },
        "dev_passed": dev_gate["passed"],
        "test_revealed": test_result is not None,
        "scientific_go": (
            test_result["scientific_go"] if test_result is not None else False
        ),
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "torch": torch.__version__,
            "device": args.device,
        },
    }
    manifest = dict(manifest_base)
    manifest["manifest_payload_sha256"] = r27.canonical_sha256(manifest_base)
    r27.write_json_exclusive(args.output_root / "artifact_manifest.json", manifest)
    print(json.dumps({"manifest": manifest, "dev": dev_gate, "test": test_result}, indent=2))


if __name__ == "__main__":
    main()
