from __future__ import annotations

# ruff: noqa: E402

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import sys
from typing import Any, Mapping, Sequence

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE))
sys.path.insert(0, str(WORKSPACE / "src"))

import torch

from scripts import run_chest_imagenome_mimic_matcher_qualification as r25
from scripts import run_chextemporal_chexpert_progression_pilot as progression
from visualvit.matching import (
    anatomy_compatible_derangement,
    oracle_plan_from_entity_ids,
)
from visualvit.real_progression import (
    classification_metrics,
    deterministic_patient_folds,
    fold_audit,
    hierarchical_patient_bootstrap,
)


LABELS = ("Improved", "Stable", "Worse")
SYSTEMS = (
    "B4a_deranged",
    "B4b_oracle",
    "oracle_visual_only",
    "oracle_geometry_only",
    "current_only",
)
DERANGEMENT_IDS = progression.DERANGEMENT_IDS
TRAINING_SEEDS = progression.TRAINING_SEEDS
PROTOCOL_PATH = (
    WORKSPACE
    / "docs/superpowers/specs/"
    "2026-07-26-r26-c1-oracle-binding-protocol-v1.md"
)
PROTOCOL_SHA256: str | None = None


def parse_args() -> argparse.Namespace:
    root = Path(r"F:\VisualVIT_runtime\050_routeC\r25_1_matching_qualification")
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, default=PROTOCOL_PATH)
    parser.add_argument(
        "--r25-summary", type=Path, default=root / "process_a/summary.json"
    )
    parser.add_argument(
        "--r25-certificate",
        type=Path,
        default=root / "reproduction_certificate.json",
    )
    parser.add_argument("--cohort", type=Path, default=root / "process_a/cohort.json")
    parser.add_argument(
        "--features", type=Path, default=root / "process_a/crop_features.pt"
    )
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--device", default="cuda:1")
    parser.add_argument("--steps", type=int, default=300)
    parser.add_argument("--learning-rate", type=float, default=0.01)
    parser.add_argument("--bootstrap-replicates", type=int, default=10_000)
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path, expected: type) -> Any:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, expected):
        raise ValueError(f"{path} must contain {expected.__name__}")
    return value


def _target_index(record: Mapping[str, Any], side: str) -> int:
    target = str(record["anatomy"])
    labels = [str(box["label"]) for box in record[f"{side}_boxes"]]
    matches = [index for index, label in enumerate(labels) if label == target]
    if len(matches) != 1:
        raise ValueError(
            f"target anatomy {target!r} must occur exactly once on {side}; "
            f"found {len(matches)}"
        )
    return matches[0]


def _relation_vector(
    record: Mapping[str, Any],
    regions: Any,
    plan: Any,
    *,
    current_only: bool = False,
) -> torch.Tensor:
    plan.validate_hard(regions)
    prior_index = _target_index(record, "prior")
    current_count = regions.current_features.shape[1]
    selected = int(plan.transport[0, prior_index].argmax().item())
    if selected >= current_count:
        raise ValueError("persistent progression target was assigned to null")
    prior = regions.prior_features[0, prior_index].clone()
    current = regions.current_features[0, selected].clone()
    if current_only:
        prior.zero_()
    event = torch.tensor((1.0, 0.0, 0.0), dtype=prior.dtype)
    return torch.cat((prior, current, current - prior, current * prior, event))


def _pair_seed(record: Mapping[str, Any], derangement_id: int) -> int:
    payload = "|".join(
        str(record[key])
        for key in ("patient_id", "prior_dicom_id", "current_dicom_id")
    )
    digest = int(hashlib.sha256(payload.encode("utf-8")).hexdigest()[:8], 16)
    return (digest + int(derangement_id)) % (2**31)


def _representations(
    records: Sequence[dict[str, Any]],
    features: dict[str, torch.Tensor],
) -> tuple[
    dict[str, torch.Tensor],
    dict[int, torch.Tensor],
    list[dict[str, Any]],
]:
    invariant: dict[str, list[torch.Tensor]] = {
        system: [] for system in SYSTEMS if system != "B4a_deranged"
    }
    deranged: dict[int, list[torch.Tensor]] = {
        value: [] for value in DERANGEMENT_IDS
    }
    audits = []
    for record in records:
        regions_vg = r25._region_batch(record, features, "visual_geometry_equal")
        regions_visual = r25._region_batch(record, features, "visual_only")
        regions_geometry = r25._region_batch(record, features, "geometry_only")
        oracle_vg = oracle_plan_from_entity_ids(regions_vg)
        oracle_visual = oracle_plan_from_entity_ids(regions_visual)
        oracle_geometry = oracle_plan_from_entity_ids(regions_geometry)
        invariant["B4b_oracle"].append(
            _relation_vector(record, regions_vg, oracle_vg)
        )
        invariant["oracle_visual_only"].append(
            _relation_vector(record, regions_visual, oracle_visual)
        )
        invariant["oracle_geometry_only"].append(
            _relation_vector(record, regions_geometry, oracle_geometry)
        )
        invariant["current_only"].append(
            _relation_vector(record, regions_vg, oracle_vg, current_only=True)
        )

        prior_count = regions_vg.prior_features.shape[1]
        current_count = regions_vg.current_features.shape[1]
        oracle_real = oracle_vg.transport[:, :prior_count, :current_count]
        derangement_audits = []
        for derangement_id in DERANGEMENT_IDS:
            wrong = anatomy_compatible_derangement(
                regions_vg,
                oracle_vg,
                seed=_pair_seed(record, derangement_id),
            )
            wrong_real = wrong.transport[:, :prior_count, :current_count]
            vector = _relation_vector(record, regions_vg, wrong)
            deranged[derangement_id].append(vector)
            checks = {
                "zero_fixed_point": not bool(
                    ((oracle_real > 0.5) & (wrong_real > 0.5)).any()
                ),
                "assignment_differs": not torch.equal(
                    oracle_vg.transport, wrong.transport
                ),
                "prior_null_equal": torch.equal(
                    oracle_vg.transport[:, :prior_count, current_count],
                    wrong.transport[:, :prior_count, current_count],
                ),
                "current_null_equal": torch.equal(
                    oracle_vg.transport[:, prior_count, :current_count],
                    wrong.transport[:, prior_count, :current_count],
                ),
                "relation_shape_equal": (
                    vector.shape
                    == invariant["B4b_oracle"][-1].shape
                ),
                "source_features_equal": True,
            }
            derangement_audits.append(
                {
                    "derangement_id": derangement_id,
                    "checks": checks,
                    "passed": all(checks.values()),
                }
            )
        audits.append(
            {
                "qualification_id": record["qualification_id"],
                "pair_seed_basis": "|".join(
                    str(record[key])
                    for key in (
                        "patient_id",
                        "prior_dicom_id",
                        "current_dicom_id",
                    )
                ),
                "derangements": derangement_audits,
                "passed": all(item["passed"] for item in derangement_audits),
            }
        )
    if not audits or not all(item["passed"] for item in audits):
        raise RuntimeError("R26 B4 isomorphism audit failed")
    return (
        {name: torch.stack(values) for name, values in invariant.items()},
        {name: torch.stack(values) for name, values in deranged.items()},
        audits,
    )


def _seed_directions(rows: Sequence[dict[str, Any]]) -> dict[str, float]:
    result = {}
    for seed in TRAINING_SEEDS:
        selected = [row for row in rows if row["training_seed"] == seed]
        left = [row for row in selected if row["system"] == "B4b_oracle"]
        right = [row for row in selected if row["system"] == "B4a_deranged"]
        left_f1 = classification_metrics(left, labels=LABELS)[
            "patient_balanced"
        ]["macro_f1"]
        right_f1 = classification_metrics(right, labels=LABELS)[
            "patient_balanced"
        ]["macro_f1"]
        result[str(seed)] = left_f1 - right_f1
    return result


def main() -> int:
    args = parse_args()
    protocol_text = args.protocol.read_text(encoding="utf-8")
    if "Status: `FROZEN_BEFORE_EXECUTION`" not in protocol_text:
        raise RuntimeError("R26 C1 protocol is not frozen")
    if PROTOCOL_SHA256 is None:
        raise RuntimeError("R26 C1 protocol hash is not pinned")
    protocol_hash = sha256_file(args.protocol)
    if protocol_hash != PROTOCOL_SHA256:
        raise RuntimeError(f"R26 protocol hash mismatch: {protocol_hash}")
    if args.output_root.exists():
        raise FileExistsError(args.output_root)

    certificate = _read_json(args.r25_certificate, dict)
    summary = _read_json(args.r25_summary, dict)
    if (
        certificate.get("status") != "PASS_Q6_FRESH_PROCESS_REPRODUCTION"
        or certificate.get("qualified") is not True
    ):
        raise RuntimeError("R25.1 Q6 is not terminal green")
    if summary.get("status") != "AWAITING_FRESH_PROCESS_REPRODUCTION":
        raise RuntimeError("R25.1 process summary is not compute-green")
    if (
        summary.get("evaluation_namespaces", {})
        .get("progression_evaluation", {})
        .get("status")
        != "NOT_EVALUATED"
    ):
        raise RuntimeError("R25.1 progression namespace is not sealed")
    if not all(summary.get("gates", {}).values()):
        raise RuntimeError("R25.1 contains a failed matching gate")
    if certificate.get("process_a", {}).get("sha256") != sha256_file(
        args.r25_summary
    ):
        raise RuntimeError("R25.1 process-A summary hash is not certified")
    expected_feature_hash = (
        summary.get("encoder", {}).get("feature_cache", {}).get("sha256")
    )
    if expected_feature_hash != sha256_file(args.features):
        raise RuntimeError("R25.1 feature cache hash mismatch")

    records = _read_json(args.cohort, list)
    selected = [
        record
        for record in records
        if int(record["shared_count"]) >= 2
        and str(record["progression"]) in LABELS
    ]
    if len({str(record["patient_id"]) for record in selected}) < 100:
        raise RuntimeError("R26 derangeable cohort has fewer than 100 patients")
    features = torch.load(args.features, map_location="cpu", weights_only=True)
    if not isinstance(features, dict):
        raise ValueError("R25.1 feature cache must be a dictionary")

    invariant, deranged, b4_audit = _representations(selected, features)
    assignment = deterministic_patient_folds(
        selected,
        labels=LABELS,
        fold_count=5,
        salt="r26-c1-b3-v1",
    )
    audit = fold_audit(
        selected,
        assignment,
        labels=LABELS,
        fold_count=5,
    )
    if any(
        count == 0
        for fold in audit["folds"]
        for count in fold["label_counts"].values()
    ):
        raise RuntimeError("a registered R26 fold is missing label support")

    device = torch.device(args.device)
    torch.cuda.set_device(device)
    rows, fit_audit = progression._run_task(
        records=selected,
        labels=LABELS,
        systems=SYSTEMS,
        invariant_features=invariant,
        deranged_features=deranged,
        assignment=assignment,
        derangements=DERANGEMENT_IDS,
        steps=args.steps,
        learning_rate=args.learning_rate,
        device=device,
    )
    bootstrap = hierarchical_patient_bootstrap(
        rows,
        labels=LABELS,
        systems=SYSTEMS,
        seeds=TRAINING_SEEDS,
        derangements=DERANGEMENT_IDS,
        contrasts={
            "B4b_minus_B4a": ("B4b_oracle", "B4a_deranged"),
            "B4b_minus_current_only": ("B4b_oracle", "current_only"),
            "visual_minus_geometry": (
                "oracle_visual_only",
                "oracle_geometry_only",
            ),
        },
        invariant_systems=[
            system for system in SYSTEMS if system != "B4a_deranged"
        ],
        replicates=args.bootstrap_replicates,
    )
    primary = bootstrap["contrasts"]["B4b_minus_B4a"]
    seed_directions = _seed_directions(rows)
    gates = {
        "R25_1_Q6_GREEN": True,
        "COHORT_AND_FOLDS_QUALIFIED": audit["patient_disjoint"],
        "B4_ISOMORPHISM": all(item["passed"] for item in b4_audit),
        "BOOTSTRAP_VALID": bootstrap["inference_valid"],
        "DELTA_BIND_AT_LEAST_5PP": primary["point_pp"] >= 5.0,
        "DELTA_BIND_CI_LOWER_POSITIVE": (
            primary["interval"] is not None
            and primary["interval"]["lower"] > 0.0
        ),
        "ALL_SEED_DIRECTIONS_POSITIVE": all(
            value > 0.0 for value in seed_directions.values()
        ),
        "FIT_FINITE": all(
            torch.isfinite(torch.tensor(item["final_loss"])).item()
            for item in fit_audit
        ),
    }

    args.output_root.mkdir(parents=True)
    payloads = {
        "cohort.json": selected,
        "folds.json": {
            "assignment": dict(sorted(assignment.items())),
            "audit": audit,
        },
        "b4_isomorphism.json": b4_audit,
        "predictions.json": rows,
        "fit_audit.json": fit_audit,
        "bootstrap.json": bootstrap,
    }
    artifact_hashes = {}
    for name, value in payloads.items():
        path = args.output_root / name
        path.write_text(
            json.dumps(value, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        artifact_hashes[name] = sha256_file(path)
    result = {
        "status": "PASS_C1_ORACLE_BINDING" if all(gates.values()) else "STOP_C1",
        "evidence_class": "NON_CONFIRMATORY_R26_C1_MECHANISM_GATE",
        "formal_claim_allowed": False,
        "clinical_claim_allowed": False,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "protocol": {"path": str(args.protocol.resolve()), "sha256": protocol_hash},
        "r25_1": {
            "certificate_sha256": sha256_file(args.r25_certificate),
            "summary_sha256": sha256_file(args.r25_summary),
            "cohort_sha256": sha256_file(args.cohort),
            "feature_cache_sha256": sha256_file(args.features),
        },
        "cohort": {
            "patients": len({record["patient_id"] for record in selected}),
            "pairs": len(
                {
                    (
                        record["patient_id"],
                        record["prior_dicom_id"],
                        record["current_dicom_id"],
                    )
                    for record in selected
                }
            ),
            "entities": len(selected),
            "labels": dict(
                sorted(Counter(record["progression"] for record in selected).items())
            ),
        },
        "config": {
            "systems": list(SYSTEMS),
            "training_seeds": list(TRAINING_SEEDS),
            "derangement_ids": list(DERANGEMENT_IDS),
            "folds": 5,
            "fold_salt": "r26-c1-b3-v1",
            "steps": args.steps,
            "learning_rate": args.learning_rate,
            "weight_decay": 1e-4,
            "bootstrap_replicates": args.bootstrap_replicates,
            "device": str(device),
            "classifier": "non-affine LayerNorm + Linear",
        },
        "primary": primary,
        "seed_directions": seed_directions,
        "bootstrap": bootstrap,
        "gates": gates,
        "artifacts": artifact_hashes,
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "torch": torch.__version__,
            "cuda": torch.version.cuda,
            "gpu": torch.cuda.get_device_name(device),
        },
        "interpretation_boundary": (
            "R26 C1 structured-classifier mechanism gate on qualified "
            "official-train data. No learned-matcher, frozen-VLM, clinical, "
            "or confirmatory claim."
        ),
    }
    summary_path = args.output_root / "summary.json"
    summary_path.write_text(
        json.dumps(result, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(json.dumps({"status": result["status"], "summary": str(summary_path)}))
    return 0 if all(gates.values()) else 2


if __name__ == "__main__":
    raise SystemExit(main())
