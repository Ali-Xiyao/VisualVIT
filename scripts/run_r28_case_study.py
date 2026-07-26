from __future__ import annotations

# ruff: noqa: E402

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import sys
from typing import Any, Iterable, Mapping, Sequence

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE))
sys.path.insert(0, str(WORKSPACE / "src"))

import numpy as np
from PIL import Image, ImageDraw

from scripts import audit_r26_binding_identifiability as r27
from visualvit.real_progression import classification_metrics


LABELS = r27.LABELS
ARCHETYPE_ORDER = (
    "STATE_SUFFICIENT",
    "TEMPORAL_HELPED",
    "BINDING_HELPED",
    "BINDING_HARMED",
    "ALL_EXPERTS_FAIL",
)
SYSTEM_ORDER = ("current_only", "B4b_oracle", "B4a_deranged")
REGISTRY_PROTOCOL = (
    WORKSPACE
    / "docs/superpowers/specs/2026-07-26-r28-case-study-registry-v1.md"
)
REGISTRY_PROTOCOL_SHA256 = (
    "eba70adf492ababebc5005d38eafa51bb8799da910a478f6627a4df553b462ce"
)
R26_ROOT_DEFAULT = r27.R26_ROOT_DEFAULT
R27_ROOT_DEFAULT = r27.OUTPUT_ROOT_DEFAULT
OUTPUT_ROOT_DEFAULT = Path(
    r"F:\VisualVIT_runtime\050_routeC\r28_case_study_tier\case_study_v1"
)
REPORT_PATH_DEFAULT = WORKSPACE / "reports/R28_CASE_STUDY_AND_FAILURE_ANALYSIS.md"
BOOTSTRAP_REPLICATES = 10_000
BOOTSTRAP_SEED = 20260728


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Frozen R28 case registry and routing-headroom study"
    )
    parser.add_argument("--r26-root", type=Path, default=R26_ROOT_DEFAULT)
    parser.add_argument("--r27-root", type=Path, default=R27_ROOT_DEFAULT)
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT_DEFAULT)
    parser.add_argument("--report-path", type=Path, default=REPORT_PATH_DEFAULT)
    return parser.parse_args()


def majority_label(values: Iterable[str]) -> str:
    counts = Counter(str(value) for value in values)
    if not counts:
        raise ValueError("majority vote requires at least one label")
    best = max(counts.values())
    return next(label for label in LABELS if counts[label] == best)


def system_rows_for_accuracy(
    rows: Sequence[Mapping[str, Any]], system: str
) -> list[dict[str, Any]]:
    selected = [dict(row) for row in rows if str(row["system"]) == system]
    if system in {"current_only", "B4b_oracle"}:
        selected = [
            row
            for row in selected
            if int(row["derangement_id"]) == r27.DERANGEMENT_IDS[0]
        ]
    return selected


def summarize_entities(
    cohort: Sequence[Mapping[str, Any]],
    predictions: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    cohort_by_qid = {
        str(record["qualification_id"]): dict(record) for record in cohort
    }
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in predictions:
        grouped[str(row["observation_id"])].append(dict(row))
    if set(grouped) != set(cohort_by_qid):
        raise ValueError("prediction/cohort observation ids do not match")

    summaries = []
    for qid in sorted(cohort_by_qid):
        record = cohort_by_qid[qid]
        rows = grouped[qid]
        accuracies = {}
        consensus = {}
        for system in SYSTEM_ORDER:
            system_rows = system_rows_for_accuracy(rows, system)
            accuracies[system] = sum(
                str(row["prediction"]) == str(row["target"])
                for row in system_rows
            ) / len(system_rows)
            consensus[system] = majority_label(
                str(row["prediction"]) for row in system_rows
            )
        summaries.append(
            {
                "qualification_id": qid,
                "patient_id": str(record["patient_id"]),
                "prior_dicom_id": str(record["prior_dicom_id"]),
                "current_dicom_id": str(record["current_dicom_id"]),
                "anatomy": str(record["anatomy"]),
                "target": str(record["progression"]),
                "current_accuracy": accuracies["current_only"],
                "oracle_accuracy": accuracies["B4b_oracle"],
                "deranged_accuracy": accuracies["B4a_deranged"],
                "consensus_prediction": consensus,
            }
        )
    return summaries


def archetype_memberships(item: Mapping[str, Any]) -> dict[str, float]:
    current = float(item["current_accuracy"])
    oracle = float(item["oracle_accuracy"])
    deranged = float(item["deranged_accuracy"])
    memberships = {}
    if current >= 2 / 3 and oracle - current <= 1 / 3:
        memberships["STATE_SUFFICIENT"] = current
    if oracle - current >= 2 / 3:
        memberships["TEMPORAL_HELPED"] = oracle - current
    if oracle - deranged >= 4 / 9:
        memberships["BINDING_HELPED"] = oracle - deranged
    if deranged - oracle >= 4 / 9:
        memberships["BINDING_HARMED"] = deranged - oracle
    if current == 0 and oracle == 0 and deranged == 0:
        memberships["ALL_EXPERTS_FAIL"] = 0.0
    return memberships


def select_registry(
    summaries: Sequence[Mapping[str, Any]], limit: int = 5
) -> tuple[dict[str, list[str]], dict[str, int]]:
    candidates: dict[str, list[tuple[float, str]]] = defaultdict(list)
    for item in summaries:
        qid = str(item["qualification_id"])
        for archetype, margin in archetype_memberships(item).items():
            candidates[archetype].append((float(margin), qid))
    selected = {}
    support = {}
    for archetype in ARCHETYPE_ORDER:
        ordered = sorted(
            candidates[archetype], key=lambda value: (-value[0], value[1])
        )
        support[archetype] = len(ordered)
        selected[archetype] = [qid for _, qid in ordered[:limit]]
    return selected, support


def case_oracle_headroom(
    summaries: Sequence[Mapping[str, Any]],
    *,
    replicates: int = BOOTSTRAP_REPLICATES,
    rng_seed: int = BOOTSTRAP_SEED,
) -> dict[str, Any]:
    rows_by_system: dict[str, list[dict[str, str]]] = defaultdict(list)
    for item in summaries:
        target = str(item["target"])
        base = {
            "patient_id": str(item["patient_id"]),
            "observation_id": str(item["qualification_id"]),
            "target": target,
        }
        predictions = {
            system: str(item["consensus_prediction"][system])
            for system in SYSTEM_ORDER
        }
        oracle_prediction = predictions["current_only"]
        selected_expert = "current_only"
        for system in SYSTEM_ORDER:
            if predictions[system] == target:
                oracle_prediction = target
                selected_expert = system
                break
        for system, prediction in predictions.items():
            rows_by_system[system].append({**base, "prediction": prediction})
        rows_by_system["case_oracle"].append(
            {
                **base,
                "prediction": oracle_prediction,
                "selected_expert": selected_expert,
            }
        )

    systems = (*SYSTEM_ORDER, "case_oracle")
    point = {
        system: classification_metrics(rows_by_system[system], labels=LABELS)[
            "patient_balanced"
        ]
        for system in systems
    }
    best_fixed = max(
        SYSTEM_ORDER, key=lambda name: float(point[name]["macro_f1"])
    )
    contrast = (
        float(point["case_oracle"]["macro_f1"])
        - float(point[best_fixed]["macro_f1"])
    )

    patient_ids = sorted(
        {str(item["patient_id"]) for item in summaries}
    )
    indices_by_patient: dict[str, list[int]] = defaultdict(list)
    for index, item in enumerate(summaries):
        indices_by_patient[str(item["patient_id"])].append(index)
    rng = np.random.default_rng(rng_seed)
    samples = []
    invalid = Counter()
    for _ in range(replicates):
        draw = rng.choice(patient_ids, size=len(patient_ids), replace=True)
        sampled_indices = [
            index for patient in draw for index in indices_by_patient[patient]
        ]
        try:
            oracle_metric = classification_metrics(
                [rows_by_system["case_oracle"][index] for index in sampled_indices],
                labels=LABELS,
            )["patient_balanced"]["macro_f1"]
            fixed_metric = classification_metrics(
                [rows_by_system[best_fixed][index] for index in sampled_indices],
                labels=LABELS,
            )["patient_balanced"]["macro_f1"]
        except ValueError as error:
            invalid[str(error)] += 1
            continue
        samples.append(float(oracle_metric) - float(fixed_metric))
    valid_fraction = len(samples) / replicates
    if len(samples) < 2 or valid_fraction < 0.95:
        interval = None
    else:
        lower, upper = np.quantile(samples, [0.025, 0.975], method="linear")
        interval = {
            "lower": float(lower),
            "upper": float(upper),
            "lower_pp": 100.0 * float(lower),
            "upper_pp": 100.0 * float(upper),
            "level": 0.95,
        }
    selected_counts = Counter(
        str(row["selected_expert"]) for row in rows_by_system["case_oracle"]
    )
    return {
        "analysis_only": True,
        "label_derived_router": True,
        "point_system_metrics": point,
        "best_fixed_system": best_fixed,
        "case_oracle_minus_best_fixed": contrast,
        "case_oracle_minus_best_fixed_pp": 100.0 * contrast,
        "interval": interval,
        "oracle_selected_expert_counts": dict(sorted(selected_counts.items())),
        "bootstrap": {
            "unit": "patient",
            "replicates": replicates,
            "rng_seed": rng_seed,
            "valid_replicates": len(samples),
            "valid_fraction": valid_fraction,
            "invalid_reasons": dict(invalid),
        },
    }


def _box_for_anatomy(record: Mapping[str, Any], side: str) -> dict[str, Any]:
    anatomy = str(record["anatomy"])
    matches = [
        dict(box)
        for box in record[f"{side}_boxes"]
        if str(box["label"]) == anatomy
    ]
    if len(matches) != 1:
        raise ValueError(f"{side} target box must be unique for {anatomy}")
    return matches[0]


def _normalize_pair(images: Sequence[Image.Image]) -> list[Image.Image]:
    arrays = [np.asarray(image.convert("L"), dtype=np.float32) for image in images]
    minimum = min(float(array.min()) for array in arrays)
    maximum = max(float(array.max()) for array in arrays)
    scale = max(maximum - minimum, 1.0)
    return [
        Image.fromarray(
            np.clip((array - minimum) * (255.0 / scale), 0, 255).astype(np.uint8),
            mode="L",
        )
        for array in arrays
    ]


def _letterbox(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    canvas = Image.new("L", size, color=0)
    copy = image.copy()
    copy.thumbnail(size, Image.Resampling.BILINEAR)
    x = (size[0] - copy.width) // 2
    y = (size[1] - copy.height) // 2
    canvas.paste(copy, (x, y))
    return canvas


def render_case_panel(record: Mapping[str, Any], path: Path) -> None:
    prior = Image.open(str(record["prior_path"])).convert("L")
    current = Image.open(str(record["current_path"])).convert("L")
    prior_box = _box_for_anatomy(record, "prior")
    current_box = _box_for_anatomy(record, "current")

    def crop(image: Image.Image, box: Mapping[str, Any]) -> Image.Image:
        coords = tuple(
            int(round(float(box[name]))) for name in ("x1", "y1", "x2", "y2")
        )
        return image.crop(coords)

    prior_display, current_display = _normalize_pair((prior, current))
    prior_crop, current_crop = _normalize_pair(
        (crop(prior, prior_box), crop(current, current_box))
    )
    full_size = (300, 300)
    crop_size = (300, 180)
    canvas = Image.new("RGB", (620, 540), color="white")
    draw = ImageDraw.Draw(canvas)
    full_images = []
    for image, box in (
        (prior_display, prior_box),
        (current_display, current_box),
    ):
        rgb = image.convert("RGB").resize(full_size, Image.Resampling.BILINEAR)
        scale_x = full_size[0] / image.width
        scale_y = full_size[1] / image.height
        coords = (
            int(float(box["x1"]) * scale_x),
            int(float(box["y1"]) * scale_y),
            int(float(box["x2"]) * scale_x),
            int(float(box["y2"]) * scale_y),
        )
        ImageDraw.Draw(rgb).rectangle(coords, outline=(255, 0, 0), width=3)
        full_images.append(rgb)
    canvas.paste(full_images[0], (5, 35))
    canvas.paste(full_images[1], (315, 35))
    canvas.paste(_letterbox(prior_crop, crop_size).convert("RGB"), (5, 355))
    canvas.paste(_letterbox(current_crop, crop_size).convert("RGB"), (315, 355))
    draw.text((5, 8), "PRIOR", fill="black")
    draw.text((315, 8), "CURRENT", fill="black")
    draw.text(
        (5, 338),
        f"ROI: {record['anatomy']} | target: {record['progression']}",
        fill="black",
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(path)


def bind_r27_context(
    summaries: list[dict[str, Any]],
    composition_payload: Mapping[str, Any],
    semantic_payload: Mapping[str, Any],
) -> None:
    pair_context = {
        str(item["pair_id"]): dict(item)
        for item in composition_payload["pairs"]
    }
    semantic_by_qid: dict[str, list[bool]] = defaultdict(list)
    for item in semantic_payload["records"]:
        semantic_by_qid[str(item["qualification_id"])].append(
            bool(item["label_changed"])
        )
    for item in summaries:
        key = (
            str(item["patient_id"]),
            str(item["prior_dicom_id"]),
            str(item["current_dicom_id"]),
        )
        pid = r27.pair_id_from_key(key)
        context = pair_context[pid]
        item["pair_id"] = pid
        item["bii"] = float(context["bii"])
        item["bii_stratum"] = str(context["bii_stratum"])
        item["pair_label_counts"] = dict(context["label_counts"])
        values = semantic_by_qid[str(item["qualification_id"])]
        item["actual_semantic_corruption_rate"] = sum(values) / len(values)


def render_report(
    *,
    summaries: Sequence[Mapping[str, Any]],
    selected: Mapping[str, Sequence[str]],
    support: Mapping[str, int],
    headroom: Mapping[str, Any],
    panel_paths: Mapping[str, str],
) -> str:
    by_qid = {str(item["qualification_id"]): item for item in summaries}
    interval = headroom["interval"]
    ci = (
        "invalid"
        if interval is None
        else f"[{interval['lower_pp']:+.2f}, {interval['upper_pp']:+.2f}] pp"
    )
    lines = [
        "# R28 Case Study and Prior-Failure Analysis",
        "",
        "Date: 2026-07-26",
        "",
        "Evidence class: `EXPLORATORY_CASE_STUDY`",
        "",
        "## Executive finding",
        "",
        "R26/R27 did not fail because correspondence could not be computed. They "
        "failed because correct binding produced little average progression gain, "
        "the derangement often preserved label semantics, and the high-BII subset "
        "did not show a positive binding effect. The case-study route therefore "
        "tests routing headroom before training TIER.",
        "",
        "## Failure taxonomy",
        "",
        "| Failure mode | Evidence | Consequence for the new attempt |",
        "|---|---|---|",
        "| Endpoint shortcut | Current-only was close to oracle on average | Keep a state expert |",
        "| Weak semantic intervention | Only 20.50% of R26 assignments changed the target label | Do not use BII as a router target |",
        "| Inactive anatomy constraint | R25.1 emitted all-zero anatomy IDs | Treat prior B4a corruption as cross-pair derangement, not a clean anatomy-local intervention |",
        "| Representation bottleneck | Frozen ROI heads weakly separated change direction | Add a global transition expert before a larger binding module |",
        "| Estimator adaptation | B4a and B4b heads trained separately | Evaluate fixed-expert routing and end-to-end utility separately |",
        "| Sparse support | High-BII had only 8 patients | Do not claim a binding-critical subgroup |",
        "| Reuse/model-selection risk | Same 170 patients informed R26/R27 | R28 remains development evidence; use nested patient folds |",
        "",
        "## Registry support",
        "",
        "| Archetype | Eligible | Selected |",
        "|---|---:|---:|",
    ]
    for archetype in ARCHETYPE_ORDER:
        lines.append(
            f"| {archetype} | {support[archetype]} | {len(selected[archetype])} |"
        )
    lines.extend(
        [
            "",
            "## Analysis-only routing headroom",
            "",
            f"- Best fixed consensus expert: `{headroom['best_fixed_system']}`",
            "- Case-oracle minus best fixed: "
            f"{headroom['case_oracle_minus_best_fixed_pp']:+.2f} pp; "
            f"95% patient-bootstrap CI {ci}",
            "- Oracle expert selections: "
            + ", ".join(
                f"{key}={value}"
                for key, value in headroom[
                    "oracle_selected_expert_counts"
                ].items()
            ),
            "",
            "This oracle reads the target label and is not a usable model. It only "
            "tests whether expert diversity leaves enough theoretical headroom for "
            "a label-free router.",
            "",
            "## Registered cases",
            "",
        ]
    )
    for archetype in ARCHETYPE_ORDER:
        lines.extend(
            [
                f"### {archetype}",
                "",
                "| Case | Anatomy | Target | Current | Oracle | Deranged | BII |",
                "|---|---|---|---:|---:|---:|---:|",
            ]
        )
        for qid in selected[archetype]:
            item = by_qid[qid]
            lines.append(
                f"| `{qid}` | {item['anatomy']} | {item['target']} | "
                f"{item['current_accuracy']:.2f} | {item['oracle_accuracy']:.2f} | "
                f"{item['deranged_accuracy']:.2f} | {item['bii']:.2f} |"
            )
        lines.append("")
    lines.extend(
        [
            "## Local panel boundary",
            "",
            "The generated image panels remain under the restricted runtime root "
            "and are not committed to Git. Their manifest paths are recorded in "
            "`case_panel_manifest.json`. No selected case was removed after image "
            "inspection.",
            "",
            f"Unique local panels generated: {len(panel_paths)}.",
            "",
            "## Implication for TIER",
            "",
            "Proceed only if the case oracle shows material headroom. The first "
            "admissible attempt must use label-free features, a state expert, a "
            "global prior/current transition expert, and a local binding expert "
            "under nested patient-disjoint evaluation. BII, case archetype, target "
            "label, and expert correctness are forbidden router inputs.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    if args.output_root.exists():
        raise FileExistsError(f"case-study output root must be fresh: {args.output_root}")
    if args.report_path.exists():
        raise FileExistsError(f"case-study report must be fresh: {args.report_path}")
    if r27.sha256_file(REGISTRY_PROTOCOL) != REGISTRY_PROTOCOL_SHA256:
        raise RuntimeError("R28 case registry protocol hash mismatch")

    for name, expected in r27.R26_INPUT_HASHES.items():
        observed = r27.sha256_file(args.r26_root / name)
        if observed != expected:
            raise RuntimeError(f"R26 input hash mismatch: {name}")
    r27_manifest = r27.read_json(args.r27_root / "artifact_manifest.json", dict)
    for name, expected in r27_manifest["outputs"].items():
        if r27.sha256_file(args.r27_root / name) != expected:
            raise RuntimeError(f"R27 output hash mismatch: {name}")

    cohort = r27.read_json(args.r26_root / "cohort.json", list)
    predictions = r27.read_json(args.r26_root / "predictions.json", list)
    r27.validate_predictions(predictions, cohort)
    composition = r27.read_json(
        args.r27_root / "pair_label_composition.json", dict
    )
    semantic = r27.read_json(
        args.r27_root / "derangement_semantic_audit.json", dict
    )
    summaries = summarize_entities(cohort, predictions)
    bind_r27_context(summaries, composition, semantic)
    selected, support = select_registry(summaries)
    headroom = case_oracle_headroom(summaries)

    selected_qids = sorted({qid for values in selected.values() for qid in values})
    cohort_by_qid = {
        str(record["qualification_id"]): dict(record) for record in cohort
    }
    panel_paths = {}
    panel_root = args.output_root / "case_panels"
    args.output_root.mkdir(parents=True, exist_ok=False)
    for qid in selected_qids:
        path = panel_root / f"{qid}.png"
        render_case_panel(cohort_by_qid[qid], path)
        panel_paths[qid] = str(path)

    selected_details = {
        qid: [
            dict(row)
            for row in predictions
            if str(row["observation_id"]) == qid
            and str(row["system"]) in SYSTEM_ORDER
        ]
        for qid in selected_qids
    }
    registry_payload = {
        "evidence_class": "EXPLORATORY_CASE_STUDY",
        "protocol_sha256": REGISTRY_PROTOCOL_SHA256,
        "archetype_support": support,
        "selected": selected,
        "unique_selected_cases": len(selected_qids),
        "overlap": {
            qid: [
                archetype
                for archetype, values in selected.items()
                if qid in values
            ]
            for qid in selected_qids
            if sum(qid in values for values in selected.values()) > 1
        },
        "case_oracle_headroom": headroom,
    }
    predictions_payload = {
        "entity_summaries": summaries,
        "selected_case_prediction_rows": selected_details,
    }
    panel_payload = {
        "restricted_data": True,
        "committed_to_git": False,
        "panels": {
            qid: {
                "path": path,
                "sha256": r27.sha256_file(Path(path)),
            }
            for qid, path in panel_paths.items()
        },
    }
    outputs = {
        "case_registry.json": registry_payload,
        "case_level_predictions.json": predictions_payload,
        "case_panel_manifest.json": panel_payload,
    }
    for name, payload in outputs.items():
        r27.write_json_exclusive(args.output_root / name, payload)

    report = render_report(
        summaries=summaries,
        selected=selected,
        support=support,
        headroom=headroom,
        panel_paths=panel_paths,
    )
    args.report_path.write_text(report, encoding="utf-8")
    manifest_base = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": "CASE_STUDY_COMPLETE",
        "evidence_class": "EXPLORATORY_CASE_STUDY",
        "protocol": {
            "path": str(REGISTRY_PROTOCOL),
            "sha256": REGISTRY_PROTOCOL_SHA256,
        },
        "r26_input_hashes": dict(r27.R26_INPUT_HASHES),
        "r27_manifest_sha256": r27.sha256_file(
            args.r27_root / "artifact_manifest.json"
        ),
        "outputs": {
            name: r27.sha256_file(args.output_root / name) for name in outputs
        },
        "report": {
            "path": str(args.report_path),
            "sha256": r27.sha256_file(args.report_path),
        },
        "panel_count": len(panel_paths),
        "case_oracle_headroom_pp": headroom[
            "case_oracle_minus_best_fixed_pp"
        ],
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "numpy": np.__version__,
            "gpu_used": False,
        },
    }
    manifest = dict(manifest_base)
    manifest["manifest_payload_sha256"] = r27.canonical_sha256(manifest_base)
    r27.write_json_exclusive(args.output_root / "artifact_manifest.json", manifest)
    print(
        json.dumps(
            {
                "status": "CASE_STUDY_COMPLETE",
                "output_root": str(args.output_root),
                "report": str(args.report_path),
                "unique_selected_cases": len(selected_qids),
                "archetype_support": support,
                "case_oracle_headroom_pp": headroom[
                    "case_oracle_minus_best_fixed_pp"
                ],
                "manifest_sha256": r27.sha256_file(
                    args.output_root / "artifact_manifest.json"
                ),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
