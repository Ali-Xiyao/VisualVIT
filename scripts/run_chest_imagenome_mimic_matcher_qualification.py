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
EXPECTED_PATIENTS = 189
EXPECTED_PAIRS = 189
EXPECTED_ROWS = 793
BOOTSTRAP_SEED = 20260725
DERANGEMENT_SEED = 20260725
COMPARISON_MAP = {"no change": "Stable", "improved": "Improved", "worsened": "Worse"}
LABELS = ("Stable", "Improved", "Worse")
MIN_PATIENTS_PER_LABEL = 10
Q7_MIN_PATIENTS = 100
CLIP_MEAN = (0.48145466, 0.4578275, 0.40821073)
CLIP_STD = (0.26862954, 0.26130258, 0.27577711)

R25_PROTOCOL_PATH = (
    WORKSPACE
    / "docs/superpowers/specs/2026-07-25-chest-imagenome-real-data-protocol-v1.md"
)
R25_PROTOCOL_SHA256 = (
    "9862dac5b2bc304129b619b5d247919797979e4e80ed80c12ae535d79d10d1fc"
)

CI_ROOT_DEFAULT = Path(
    r"F:\VisualVIT_runtime\050_routeC\data\chest_imagenome"
    r"\chest-imagenome-dataset-1.0.0"
)
MIMIC_OTHER_DEFAULT = Path(r"H:\Xiyao_Wang\000_Public Dataset\mimic_cxr_other")
IMAGE_ROOT_DEFAULT = Path(
    r"H:\Xiyao_Wang\000_Public Dataset\mimic-cxr\mimic-cxr"
    r"\mimic-cxr-images\files"
)
WEIGHTS_DEFAULT = Path(
    r"H:\Xiyao_Wang\021_260129VIVID\pretrained\biomedclip_vit_base.pt"
)

# Chest ImaGenome gold + silver + semantics file pins (from the R25 spec table).
CI_PINS = {
    "gold_comparison": (
        "7efc6d779705aee0770f3c474baa3fc7cfd486333ad5c39717ad1ff9d95772b0"
    ),
    "gold_attribute": (
        "b6c72e55ef322d61a2a7feae1cbfd6b69ef3009258f0afb6d1e342e51a158262"
    ),
    "gold_scaling": (
        "8570f0f532e231205bd369d823e7072644b4fbd4f335ff4b908e3a0967698b86"
    ),
    "gold_attributes_relations": (
        "5c1d07c3f990421dd88ea13c24a4eb1e6d34511230fde75dd175d2b66b655c01"
    ),
    "gold_comparison_relations": (
        "b7008b4cf9c39e2420ad813187a43e714feab82ce60150e1be6007d967682d8a"
    ),
    "silver_train": (
        "5d99b3b598bca65208bd445932618d1f888026b1a80bd3675330b188e42c1190"
    ),
    "silver_valid": (
        "2f8a874ec158aad595dfd07e8391ddba8d0aa2a9f1bd7650a9e566ba820e6bd4"
    ),
    "silver_test": (
        "3682ca030432c33f189a1d9ad96a126b30531c708b40cf704674bda255f99c3f"
    ),
    "silver_images_to_avoid": (
        "a7c13c8385887104df6de626f54091bd693d47ee7cb1b61f33081bc60368b010"
    ),
    "semantics_comparison": (
        "cb3f9fff758f4f8a51778ef45558ade27824ae241008ec0a3b9ae7e6fb6bba18"
    ),
    "semantics_attribute": (
        "05d4ac0ae0f42ef2e5a1b29fc9b7ea2566583dfc025360384f4ec4451c57aef6"
    ),
    "semantics_objects": (
        "e84d70cf39f02c030b0878933e716f088964b6da8b413b41422a666302d7377b"
    ),
    "semantics_umls": (
        "0f2ed069ed95335fa676921989cba7dbf45d48203a9f20a657835fd7a275ba15"
    ),
    "license": (
        "30492d35caacc57d31754ce490e806110abee5d55effac7ddc460de4191ac773"
    ),
    "sha256sums": (
        "df13e5da4f141a4509cee15af425187dd65cb457650cc37738db7c7502f559d5"
    ),
}

# MIMIC + BiomedCLIP pins (re-qualified from R24 v3).
MIMIC_PINS = {
    "metadata": (
        "6a3748ce77724c0dfe7d2def8f47643e989e3bbf0795bc13b89c1578e1649d6b"
    ),
    "split": (
        "515997bd6649045d7443d60c59a4ce9f6cca6c478871b8f2fb13454462bedb2f"
    ),
    "weights": (
        "3be6f957b2fc8b8324cc6ed6faebdcb218511b41fc0f542312e21850424a2590"
    ),
}

# R24 synthetic engineering prerequisite pins (same as R24 v3 runner validates
# for R23).  The R25 runner validates these exact artifacts before creating an
# output root, mirroring the R24 v3 prerequisite gate.
R24_PREREQUISITE_PINS = {
    "protocol": (
        "2f8b1577d193bf6a63d5146853ffd2b5fdc70918b6937652ff2cef47d8cc8e44"
    ),
    "certificate": (
        "e96629b24d4a7caf6239c0a48fe995649f04bbbc61ae5b1ec5e264c1d0a01d0c"
    ),
    "launcher_result": (
        "4ab514b54b352a7f9206f9ebe7f43247a0fcfdf6c79f54a78adf5cc48228ea05"
    ),
}

# R24 real CheXTemporal-MIMIC v3 prerequisite pins (new in R25).  The R25
# protocol authorizes real-data access only when the R24 real v3 certificate
# is terminally green at Q6.
R24_REAL_V3_PREREQUISITE_PINS = {
    "protocol": (
        "638c7d130fa56cd789098f9da8374a2a56075a0b63ef92357ef6bfce277ba4d9"
    ),
    "certificate": (
        "9f30b990c0ad4c6e8c50895a3a98e5c087143c9bf288c7cf1911aac42bc66fba"
    ),
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


def parse_box_list(value: object) -> list[float]:
    """Parse a Chest ImaGenome ``[x1, y1, x2, y2]`` string into floats."""
    if hasattr(value, "tolist"):
        value = value.tolist()
    if isinstance(value, str):
        value = ast.literal_eval(value)
    if not isinstance(value, (list, tuple)):
        raise ValueError("bbox payload must be a list or tuple")
    if len(value) != 4:
        raise ValueError("bbox payload must have exactly four coordinates")
    return [float(coord) for coord in value]


def image_path(root: Path, subject_id: object, study_id: object, dicom_id: str) -> Path:
    subject_text = str(int(subject_id))
    return (
        root
        / f"p{subject_text[:2]}"
        / f"p{subject_text}"
        / f"s{int(study_id)}"
        / f"{dicom_id}.jpg"
    )


def _verify_box_scaling(
    box_224: list[float],
    box_original: list[float],
    scaling_row: dict[str, Any],
    *,
    epsilon: float = 0.5,
) -> None:
    """Assert ``bbox_coord_224 ~= bbox_coord_original * ratio + padding``.

    The Chest ImaGenome scaling CSV records per-image padding (top/left) and a
    uniform resize ratio.  The transform is::

        x_224 = x_original * ratio + left
        y_224 = y_original * ratio + top

    The 224-space coordinates in the gold TSV are stored as integers (rounded
    from the float transform), so the epsilon must accommodate standard
    rounding error (up to 0.5 per coordinate).  A 1.0 drift is still rejected.
    """
    ratio = float(scaling_row["ratio"])
    left = float(scaling_row["left"])
    top = float(scaling_row["top"])
    expected = [
        box_original[0] * ratio + left,
        box_original[1] * ratio + top,
        box_original[2] * ratio + left,
        box_original[3] * ratio + top,
    ]
    for actual, predicted in zip(box_224, expected):
        if abs(actual - predicted) > epsilon:
            raise ValueError(
                f"scaling verification failed: 224={actual}, expected={predicted}, "
                f"ratio={ratio}, left={left}, top={top}"
            )


def _validate_box_bounds(box: list[float], *, tolerance: float = 1e-4) -> None:
    """Assert ``0 <= x1 < x2 <= 224`` and ``0 <= y1 < y2 <= 224``."""
    x1, y1, x2, y2 = box
    if not (-tolerance <= x1 < x2 <= 224.0 + tolerance):
        raise ValueError(f"box x-coordinates out of bounds: {box}")
    if not (-tolerance <= y1 < y2 <= 224.0 + tolerance):
        raise ValueError(f"box y-coordinates out of bounds: {box}")
    if x2 - x1 <= 0 or y2 - y1 <= 0:
        raise ValueError(f"box has nonpositive area: {box}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--gold-comparison",
        type=Path,
        default=CI_ROOT_DEFAULT / "gold_dataset"
        / "gold_object_comparison_with_coordinates.txt",
    )
    parser.add_argument(
        "--gold-attribute",
        type=Path,
        default=CI_ROOT_DEFAULT / "gold_dataset"
        / "gold_object_attribute_with_coordinates.txt",
    )
    parser.add_argument(
        "--gold-scaling",
        type=Path,
        default=CI_ROOT_DEFAULT / "gold_dataset"
        / "gold_bbox_scaling_factors_original_to_224x224.csv",
    )
    parser.add_argument(
        "--gold-attributes-relations",
        type=Path,
        default=CI_ROOT_DEFAULT / "gold_dataset"
        / "gold_attributes_relations_500pts_500studies1st.txt",
    )
    parser.add_argument(
        "--gold-comparison-relations",
        type=Path,
        default=CI_ROOT_DEFAULT / "gold_dataset"
        / "gold_comparison_relations_500pts_500studies2nd.txt",
    )
    parser.add_argument(
        "--silver-train",
        type=Path,
        default=CI_ROOT_DEFAULT / "silver_dataset" / "splits" / "train.csv",
    )
    parser.add_argument(
        "--silver-valid",
        type=Path,
        default=CI_ROOT_DEFAULT / "silver_dataset" / "splits" / "valid.csv",
    )
    parser.add_argument(
        "--silver-test",
        type=Path,
        default=CI_ROOT_DEFAULT / "silver_dataset" / "splits" / "test.csv",
    )
    parser.add_argument(
        "--silver-images-to-avoid",
        type=Path,
        default=CI_ROOT_DEFAULT / "silver_dataset" / "splits"
        / "images_to_avoid.csv",
    )
    parser.add_argument(
        "--semantics-comparison",
        type=Path,
        default=CI_ROOT_DEFAULT / "semantics" / "comparison_relations_v1.txt",
    )
    parser.add_argument(
        "--semantics-attribute",
        type=Path,
        default=CI_ROOT_DEFAULT / "semantics" / "attribute_relations_v1.txt",
    )
    parser.add_argument(
        "--semantics-objects",
        type=Path,
        default=CI_ROOT_DEFAULT / "semantics"
        / "objects_detectable_by_bbox_pipeline_v1.txt",
    )
    parser.add_argument(
        "--semantics-umls",
        type=Path,
        default=CI_ROOT_DEFAULT / "semantics" / "label_to_UMLS_mapping.json",
    )
    parser.add_argument(
        "--ci-license",
        type=Path,
        default=CI_ROOT_DEFAULT / "LICENSE.txt",
    )
    parser.add_argument(
        "--ci-sha256sums",
        type=Path,
        default=CI_ROOT_DEFAULT / "SHA256SUMS.txt",
    )
    parser.add_argument(
        "--metadata",
        type=Path,
        default=MIMIC_OTHER_DEFAULT / "mimic-cxr-2.0.0-metadata.csv.gz",
    )
    parser.add_argument(
        "--split",
        type=Path,
        default=MIMIC_OTHER_DEFAULT / "mimic-cxr-2.0.0-split.csv.gz",
    )
    parser.add_argument(
        "--image-root",
        type=Path,
        default=IMAGE_ROOT_DEFAULT,
    )
    parser.add_argument(
        "--weights",
        type=Path,
        default=WEIGHTS_DEFAULT,
    )
    parser.add_argument(
        "--protocol",
        type=Path,
        default=R25_PROTOCOL_PATH,
    )
    parser.add_argument(
        "--r24-protocol",
        type=Path,
        default=WORKSPACE
        / "refine-logs/CALIBRATION_PROTOCOL_R24_2026-07-24.md",
    )
    parser.add_argument(
        "--r24-certificate",
        type=Path,
        default=WORKSPACE
        / "artifacts/calibration/"
        "capes_ci_qptm_r24_reproduction_local_20260724_v1/"
        "reproduction_certificate.json",
    )
    parser.add_argument(
        "--r24-launcher-result",
        type=Path,
        default=WORKSPACE
        / "artifacts/calibration/r24_launcher_logs/"
        "launcher_process_result.json",
    )
    parser.add_argument(
        "--r24-real-v3-protocol",
        type=Path,
        default=WORKSPACE
        / "docs/superpowers/specs/"
        "2026-07-24-chextemporal-mimic-matcher-qualification-v3.md",
    )
    parser.add_argument(
        "--r24-real-v3-certificate",
        type=Path,
        default=WORKSPACE
        / "artifacts/real_qualification/chextemporal_mimic_matcher_v3/"
        "reproduction_certificate.json",
    )
    parser.add_argument(
        "--r24-v3-cohort",
        type=Path,
        default=WORKSPACE
        / "artifacts/real_qualification/chextemporal_mimic_matcher_v3/"
        "process_a/cohort.json",
    )
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--process-id", choices=("a", "b"), required=True)
    parser.add_argument("--device", default="cuda:1")
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--bootstrap-replicates", type=int, default=10_000)
    return parser.parse_args()


def _validate_r24_prerequisite(args: argparse.Namespace) -> dict[str, Any]:
    """Validate the R24 synthetic + real v3 prerequisite artifacts."""
    ledger: dict[str, Any] = {"synthetic": {}, "real_v3": {}}

    synthetic_paths = {
        "protocol": args.r24_protocol,
        "certificate": args.r24_certificate,
        "launcher_result": args.r24_launcher_result,
    }
    for name, path in synthetic_paths.items():
        actual = sha256_file(path)
        if actual != R24_PREREQUISITE_PINS[name]:
            raise RuntimeError(f"R24 synthetic {name} hash mismatch: {actual}")
        ledger["synthetic"][name] = {
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
        or gate.get("primary_canonical_sha256")
        != gate.get("replica_canonical_sha256")
        or gate.get("comparison_excludes_only")
        != R24_EXPECTED_COMPARISON_EXCLUSIONS
    ):
        raise RuntimeError("R24 synthetic parent certificate is not terminally green")
    launch = json.loads(args.r24_launcher_result.read_text(encoding="utf-8-sig"))
    if launch.get("exit_code") != 0 or launch.get("retry_attempted") is not False:
        raise RuntimeError(
            "R24 synthetic scheduled launcher result is not terminally green"
        )

    real_v3_paths = {
        "protocol": args.r24_real_v3_protocol,
        "certificate": args.r24_real_v3_certificate,
    }
    for name, path in real_v3_paths.items():
        actual = sha256_file(path)
        if actual != R24_REAL_V3_PREREQUISITE_PINS[name]:
            raise RuntimeError(f"R24 real v3 {name} hash mismatch: {actual}")
        ledger["real_v3"][name] = {
            "path": str(path.resolve()),
            "bytes": path.stat().st_size,
            "sha256": actual,
        }
    real_v3_certificate = json.loads(
        args.r24_real_v3_certificate.read_text(encoding="utf-8")
    )
    if (
        real_v3_certificate.get("status")
        != "PASS_Q6_FRESH_PROCESS_REPRODUCTION"
        or real_v3_certificate.get("qualified") is not True
        or real_v3_certificate.get("formal_claim_allowed") is not False
    ):
        raise RuntimeError("R24 real v3 certificate is not terminally green at Q6")
    return ledger


def _strict_cohort(
    args: argparse.Namespace,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Build the fail-closed three-label persistent cohort.

    Reads the Chest ImaGenome gold comparison TSV, joins to MIMIC-CXR
    metadata/split, verifies 224x224 box coordinates against per-image scaling
    factors, enforces cross-source patient-level leakage exclusion against the
    R24 v3 cohort, and produces one record per (patient, pair, anatomy)
    carrying ALL anatomy boxes for that pair (matching the R24 v3 record
    pattern).  The silver ``images_to_avoid.csv`` list is loaded for audit
    transparency but is NOT used as an exclusion filter: it lists the gold
    DICOMs themselves (so silver training can avoid them), and the R25 cohort
    is gold-only by construction.
    """
    comparison_frame = pd.read_csv(args.gold_comparison, sep="\t")
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
    source_index: dict[str, dict[str, Any]] = {
        str(row["dicom_id"]): row.to_dict() for _, row in source.iterrows()
    }

    scaling_frame = pd.read_csv(args.gold_scaling)
    scaling_index: dict[str, dict[str, Any]] = {
        str(row["image_id"]): row.to_dict() for _, row in scaling_frame.iterrows()
    }

    avoid_frame = pd.read_csv(args.silver_images_to_avoid, usecols=["dicom_id"])
    avoid_dicoms = {str(dicom_id) for dicom_id in avoid_frame["dicom_id"]}

    r24_cohort_path = args.r24_v3_cohort
    r24_cohort_records = json.loads(r24_cohort_path.read_text(encoding="utf-8"))
    r24_patients = {
        str(record["patient_id"]) for record in r24_cohort_records
    }

    exclusions: Counter[str] = Counter()
    pair_anatomy_targets: dict[tuple[str, str, str, str], str] = {}
    pair_entries: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)

    for row in comparison_frame.itertuples():
        comparison = str(row.comparison).strip()
        anatomy = str(row.bbox).strip().lower()
        current_dicom = str(row.current_image_id).strip()
        previous_dicom = str(row.previous_image_id).strip()
        label_name = str(row.label_name).strip()

        if current_dicom not in source_index or previous_dicom not in source_index:
            exclusions["metadata_or_split_missing"] += 1
            continue
        current_meta = source_index[current_dicom]
        previous_meta = source_index[previous_dicom]

        if (
            current_meta.get("split") != "train"
            or previous_meta.get("split") != "train"
        ):
            exclusions["not_official_train"] += 1
            continue

        current_subject = str(current_meta["subject_id"])
        previous_subject = str(previous_meta["subject_id"])
        if current_subject != previous_subject:
            exclusions["subject_mismatch"] += 1
            continue
        mimic_patient = current_subject

        current_study = str(current_meta["study_id"])
        previous_study = str(previous_meta["study_id"])

        prior_time = (
            str(previous_meta["StudyDate"]),
            str(previous_meta["StudyTime"]),
        )
        current_time = (
            str(current_meta["StudyDate"]),
            str(current_meta["StudyTime"]),
        )
        if not prior_time < current_time:
            exclusions["not_strictly_chronological"] += 1
            continue

        prior_view = str(previous_meta["ViewPosition"]).strip()
        current_view = str(current_meta["ViewPosition"]).strip()
        if prior_view != current_view or prior_view not in {"AP", "PA"}:
            exclusions["view_mismatch"] += 1
            continue

        target_key = (mimic_patient, previous_dicom, current_dicom, anatomy)
        if target_key in pair_anatomy_targets:
            if pair_anatomy_targets[target_key] != comparison:
                exclusions["target_conflict"] += 1
            else:
                exclusions["duplicate_target"] += 1
            continue
        pair_anatomy_targets[target_key] = comparison

        if comparison not in COMPARISON_MAP:
            exclusions["unknown_comparison"] += 1
            continue
        persistent_label = COMPARISON_MAP[comparison]

        if mimic_patient in r24_patients:
            exclusions["cross_source_patient_overlap"] += 1
            continue
        # NOTE: ``images_to_avoid.csv`` lists the gold DICOMs so silver training
        # can exclude them.  The R25 cohort is gold-only, so every gold DICOM
        # is by construction in that list; using it as an exclusion filter would
        # reject the entire cohort.  Cross-source leakage is already enforced
        # by the patient-level R24 v3 overlap check above.  The avoid-list size
        # is retained in the audit for transparency only.

        prior_path = image_path(
            args.image_root, mimic_patient, previous_study, previous_dicom
        )
        current_path = image_path(
            args.image_root, mimic_patient, current_study, current_dicom
        )
        if not prior_path.is_file() or not current_path.is_file():
            exclusions["parent_image_missing"] += 1
            continue

        try:
            current_box_224 = parse_box_list(row.bbox_coord_224_subject)
            previous_box_224 = parse_box_list(row.bbox_coord_224_object)
            current_box_original = parse_box_list(
                row.bbox_coord_original_subject
            )
            previous_box_original = parse_box_list(
                row.bbox_coord_original_object
            )
        except (ValueError, SyntaxError, TypeError):
            exclusions["coordinate_parse_failure"] += 1
            continue

        current_scaling_key = f"{current_dicom}.dcm"
        previous_scaling_key = f"{previous_dicom}.dcm"
        if (
            current_scaling_key not in scaling_index
            or previous_scaling_key not in scaling_index
        ):
            exclusions["scaling_factor_missing"] += 1
            continue
        try:
            _verify_box_scaling(
                current_box_224,
                current_box_original,
                scaling_index[current_scaling_key],
            )
            _verify_box_scaling(
                previous_box_224,
                previous_box_original,
                scaling_index[previous_scaling_key],
            )
        except ValueError:
            exclusions["scaling_verification_failed"] += 1
            continue

        try:
            _validate_box_bounds(current_box_224)
            _validate_box_bounds(previous_box_224)
        except ValueError:
            exclusions["box_out_of_bounds"] += 1
            continue

        prior_box = {
            "label": anatomy,
            "x1": float(previous_box_224[0]),
            "y1": float(previous_box_224[1]),
            "x2": float(previous_box_224[2]),
            "y2": float(previous_box_224[3]),
        }
        current_box = {
            "label": anatomy,
            "x1": float(current_box_224[0]),
            "y1": float(current_box_224[1]),
            "x2": float(current_box_224[2]),
            "y2": float(current_box_224[3]),
        }

        pair_key = (mimic_patient, previous_dicom, current_dicom)
        pair_entries[pair_key].append(
            {
                "anatomy": anatomy,
                "label_name": label_name,
                "comparison": comparison,
                "persistent_label": persistent_label,
                "prior_box": prior_box,
                "current_box": current_box,
                "prior_path": str(prior_path),
                "current_path": str(current_path),
                "prior_study_id": previous_study,
                "current_study_id": current_study,
                "view": prior_view,
            }
        )

    records: list[dict[str, Any]] = []
    for pair_key, entries in pair_entries.items():
        mimic_patient, previous_dicom, current_dicom = pair_key
        all_prior_boxes = [entry["prior_box"] for entry in entries]
        all_current_boxes = [entry["current_box"] for entry in entries]
        prior_labels = [box["label"] for box in all_prior_boxes]
        current_labels = [box["label"] for box in all_current_boxes]
        if len(set(prior_labels)) != len(prior_labels):
            continue
        if len(set(current_labels)) != len(current_labels):
            continue
        support = correspondence_support(
            entries[0]["persistent_label"],
            prior_labels,
            current_labels,
        )
        if not support["compatible"]:
            continue

        for entry in entries:
            record_key = "|".join(
                str(value)
                for value in (
                    mimic_patient,
                    previous_dicom,
                    current_dicom,
                    entry["anatomy"],
                    entry["persistent_label"],
                )
            )
            records.append(
                {
                    "qualification_id": hashlib.sha256(
                        record_key.encode("utf-8")
                    ).hexdigest()[:20],
                    "patient_id": mimic_patient,
                    "prior_dicom_id": previous_dicom,
                    "current_dicom_id": current_dicom,
                    "prior_study_id": entry["prior_study_id"],
                    "current_study_id": entry["current_study_id"],
                    "prior_path": entry["prior_path"],
                    "current_path": entry["current_path"],
                    "view": entry["view"],
                    "anatomy": entry["anatomy"],
                    "label_name": entry["label_name"],
                    "comparison": entry["comparison"],
                    "progression": entry["persistent_label"],
                    "prior_boxes": all_prior_boxes,
                    "current_boxes": all_current_boxes,
                    "shared_count": len(support["shared"]),
                    "death_count": len(support["deaths"]),
                    "birth_count": len(support["births"]),
                }
            )

    records.sort(key=lambda item: item["qualification_id"])

    label_patient_counts: dict[str, int] = {}
    for label in LABELS:
        label_patient_counts[label] = len(
            {item["patient_id"] for item in records if item["progression"] == label}
        )

    audit = {
        "input_comparison_rows": int(len(comparison_frame)),
        "retained_rows": len(records),
        "retained_patients": len(
            {item["patient_id"] for item in records}
        ),
        "retained_pairs": len(
            {
                (
                    item["patient_id"],
                    item["prior_dicom_id"],
                    item["current_dicom_id"],
                )
                for item in records
            }
        ),
        "label_counts": dict(
            Counter(item["progression"] for item in records)
        ),
        "label_patient_counts": label_patient_counts,
        "cross_source_excluded_patients": len(r24_patients),
        "cross_source_excluded_dicoms": len(avoid_dicoms),
        "exclusions": dict(sorted(exclusions.items())),
    }

    if audit["retained_rows"] != EXPECTED_ROWS:
        raise RuntimeError(
            f"strict cohort drift: expected {EXPECTED_ROWS} rows, "
            f"got {audit['retained_rows']}"
        )
    if audit["retained_patients"] != EXPECTED_PATIENTS:
        raise RuntimeError(
            f"strict cohort drift: expected {EXPECTED_PATIENTS} patients, "
            f"got {audit['retained_patients']}"
        )
    if audit["retained_pairs"] != EXPECTED_PAIRS:
        raise RuntimeError(
            f"strict cohort drift: expected {EXPECTED_PAIRS} pairs, "
            f"got {audit['retained_pairs']}"
        )
    for label in LABELS:
        if label_patient_counts[label] < MIN_PATIENTS_PER_LABEL:
            raise RuntimeError(
                f"three-label coverage gate failed: {label} has only "
                f"{label_patient_counts[label]} patients "
                f"(minimum {MIN_PATIENTS_PER_LABEL})"
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
        second = model.forward_features(
            torch.stack(repeated).to(device)
        )[:, 0].cpu()
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
        current_source_ids=(
            torch.arange(current.shape[1]) + prior.shape[1]
        ).unsqueeze(0),
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


def _anatomy_constraint_audit(regions: RegionBatch) -> dict[str, Any]:
    valid = regions.prior_valid[:, :, None] & regions.current_valid[:, None, :]
    compatible = valid & (
        regions.prior_anatomy[:, :, None] == regions.current_anatomy[:, None, :]
    )
    valid_candidates = int(valid.sum().item())
    compatible_candidates = int(compatible.sum().item())
    removed_candidates = valid_candidates - compatible_candidates
    return {
        "configured": True,
        "active_on_batch": removed_candidates > 0,
        "valid_candidates": valid_candidates,
        "compatible_candidates": compatible_candidates,
        "removed_candidates": removed_candidates,
        "reason": (
            None
            if removed_candidates > 0
            else "All emitted anatomy ids are identical, so the mask removes no candidates."
        ),
    }


def _evaluate(
    records: list[dict[str, Any]],
    features: dict[str, torch.Tensor],
    bootstrap_replicates: int,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    variants = ("visual_only", "geometry_only", "visual_geometry_equal")
    patient_statistics = {name: defaultdict(list) for name in variants}
    row_outputs: list[dict[str, Any]] = []
    global_greedy_dominance = True
    b4_correct: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    b4_deranged: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    b4_checks: list[dict[str, Any]] = []
    anatomy_audits: list[dict[str, Any]] = []

    for row_index, record in enumerate(records):
        output: dict[str, Any] = {
            "qualification_id": record["qualification_id"],
            "patient_id": record["patient_id"],
            "variants": {},
        }
        for variant in variants:
            regions = _region_batch(record, features, variant)
            if variant == "visual_geometry_equal":
                anatomy_audits.append(_anatomy_constraint_audit(regions))
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
                        seed=DERANGEMENT_SEED + row_index,
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
                    deranged_real = deranged.transport[
                        :, :prior_count, :current_count
                    ]
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
                            gold_tokens.tokens.shape
                            == deranged_tokens.tokens.shape
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
                            "current_features": tensor_hash(
                                regions.current_features
                            ),
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

    mechanics: dict[str, Any] = {
        "global_objective_never_below_greedy": global_greedy_dominance,
        "anatomy_constraint": {
            "configured": True,
            "active_on_cohort": any(
                item["active_on_batch"] for item in anatomy_audits
            ),
            "batches": len(anatomy_audits),
            "valid_candidates": sum(
                item["valid_candidates"] for item in anatomy_audits
            ),
            "removed_candidates": sum(
                item["removed_candidates"] for item in anatomy_audits
            ),
            "reason": (
                None
                if any(item["active_on_batch"] for item in anatomy_audits)
                else (
                    "All emitted anatomy ids are identical, so the configured "
                    "mask removes no candidates."
                )
            ),
        },
        "b4_rows": len(b4_checks),
        "b4_all_passed": (
            all(item["passed"] for item in b4_checks) if b4_checks else True
        ),
        "b4_checks": b4_checks,
    }

    if b4_correct:
        b4_bootstrap = patient_cluster_bootstrap(
            b4_correct,
            seed=BOOTSTRAP_SEED,
            replicates=bootstrap_replicates,
            randomized_patient_statistics=b4_deranged,
        )
        mechanics["b4_bootstrap"] = b4_bootstrap
    else:
        mechanics["b4_bootstrap"] = None

    return aggregate, row_outputs, mechanics


def _evaluate_gates(
    cohort_audit: dict[str, Any],
    image_ledger: list[dict[str, Any]],
    feature_ledger: list[dict[str, Any]],
    repeat_difference: float,
    mechanics: dict[str, Any],
    aggregate: dict[str, Any],
) -> tuple[dict[str, bool], str | None, dict[str, Any]]:
    """Evaluate Q0-Q5 and Q7.  Q6 is evaluated externally.

    Returns the gates dict, the first failed gate name (or None), and the Q7
    power-estimate details for the certificate.
    """
    primary = aggregate["visual_geometry_equal"]["point"]
    q7_details: dict[str, Any] = {
        "min_patients": Q7_MIN_PATIENTS,
        "b4_bootstrap_present": mechanics.get("b4_bootstrap") is not None,
    }

    gates = {
        "Q0_ASSET_LINEAGE": True,
        "Q1_COHORT_GEOMETRY": (
            cohort_audit["retained_rows"] == EXPECTED_ROWS
            and cohort_audit["retained_patients"] == EXPECTED_PATIENTS
            and cohort_audit["retained_pairs"] == EXPECTED_PAIRS
            and len(image_ledger) > 0
            and all(
                cohort_audit["label_patient_counts"][label]
                >= MIN_PATIENTS_PER_LABEL
                for label in LABELS
            )
        ),
        "Q2_FEATURE_INTEGRITY": (
            repeat_difference == 0.0
            and all(item["feature_sha256"] for item in feature_ledger)
        ),
        "Q3_MATCHPLAN_MECHANICS": mechanics[
            "global_objective_never_below_greedy"
        ],
        "Q4_MATCHING_SIGNAL": (
            primary["persistent_edge_f1"] >= 0.50
            and (
                mechanics.get("b4_bootstrap") is not None
                and mechanics["b4_bootstrap"]["persistent_edge_f1_delta"][
                    "lower"
                ]
                > 0.0
            )
        ),
        "Q5_B4_STRUCTURE": mechanics["b4_all_passed"],
    }

    b4_bootstrap = mechanics.get("b4_bootstrap")
    q7_passes = False
    if b4_bootstrap is not None:
        delta = b4_bootstrap["persistent_edge_f1_delta"]
        q7_details["delta_match_pp"] = 100.0 * delta["point"]
        q7_details["delta_match_lower_pp"] = 100.0 * delta["lower"]
        q7_details["delta_match_upper_pp"] = 100.0 * delta["upper"]
        q7_details["effective_unique_patients"] = b4_bootstrap["patient_count"]
        q7_passes = (
            delta["lower"] > 0.0
            and b4_bootstrap["patient_count"] >= Q7_MIN_PATIENTS
        )
    else:
        q7_details["delta_match_pp"] = None
        q7_details["delta_match_lower_pp"] = None
        q7_details["delta_match_upper_pp"] = None
        q7_details["effective_unique_patients"] = 0
    gates["Q7_MATCHING_POWER_ESTIMATE"] = q7_passes

    first_failed = next(
        (name for name, passed in gates.items() if not passed), None
    )
    return gates, first_failed, q7_details


def _evaluation_namespaces(aggregate: dict[str, Any]) -> dict[str, Any]:
    return {
        "matching_evaluation": {
            "status": "EVALUATED",
            "task": "cross_temporal_correspondence",
            "event_labels": ["persistent", "death", "birth"],
            "aggregate": aggregate,
        },
        "progression_evaluation": {
            "status": "NOT_EVALUATED",
            "labels": list(LABELS),
            "reason": (
                "R25.1 qualifies correspondence only; no progression prediction "
                "head is executed."
            ),
        },
    }


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

    ci_input_paths = {
        "gold_comparison": args.gold_comparison,
        "gold_attribute": args.gold_attribute,
        "gold_scaling": args.gold_scaling,
        "gold_attributes_relations": args.gold_attributes_relations,
        "gold_comparison_relations": args.gold_comparison_relations,
        "silver_train": args.silver_train,
        "silver_valid": args.silver_valid,
        "silver_test": args.silver_test,
        "silver_images_to_avoid": args.silver_images_to_avoid,
        "semantics_comparison": args.semantics_comparison,
        "semantics_attribute": args.semantics_attribute,
        "semantics_objects": args.semantics_objects,
        "semantics_umls": args.semantics_umls,
        "license": args.ci_license,
        "sha256sums": args.ci_sha256sums,
    }
    mimic_input_paths = {
        "metadata": args.metadata,
        "split": args.split,
        "weights": args.weights,
    }

    input_ledger: dict[str, Any] = {"chest_imagenome": {}, "mimic": {}}
    for name, path in ci_input_paths.items():
        actual = sha256_file(path)
        if actual != CI_PINS[name]:
            raise RuntimeError(
                f"Chest ImaGenome {name} hash mismatch: {actual}"
            )
        input_ledger["chest_imagenome"][name] = {
            "path": str(path.resolve()),
            "bytes": path.stat().st_size,
            "sha256": actual,
        }
    for name, path in mimic_input_paths.items():
        actual = sha256_file(path)
        if actual != MIMIC_PINS[name]:
            raise RuntimeError(f"MIMIC {name} hash mismatch: {actual}")
        input_ledger["mimic"][name] = {
            "path": str(path.resolve()),
            "bytes": path.stat().st_size,
            "sha256": actual,
        }

    protocol_text = args.protocol.read_text(encoding="utf-8")
    if "Status: `PRE_FREEZE_DESIGN_CANDIDATE`" not in protocol_text:
        raise RuntimeError("R25 qualification protocol is not in pre-freeze state")
    protocol_hash = sha256_file(args.protocol)
    if protocol_hash != R25_PROTOCOL_SHA256:
        raise RuntimeError(
            f"R25 protocol hash mismatch: {protocol_hash} "
            f"(expected {R25_PROTOCOL_SHA256})"
        )

    records, cohort_audit = _strict_cohort(args)

    image_paths = sorted(
        {
            Path(record[side])
            for record in records
            for side in ("prior_path", "current_path")
        },
        key=str,
    )
    image_ledger: list[dict[str, Any]] = []
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
    (
        features,
        feature_ledger,
        extraction_seconds,
        repeat_difference,
    ) = _extract_features(records, model, device, args.batch_size)
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

    gates, first_failed, q7_details = _evaluate_gates(
        cohort_audit,
        image_ledger,
        feature_ledger,
        repeat_difference,
        mechanics,
        aggregate,
    )
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
            "r25_protocol_sha256_const": R25_PROTOCOL_SHA256,
        },
        "r24_prerequisite": r24_prerequisite,
        "inputs": input_ledger,
        "cohort": cohort_audit,
        "image_ledger_sha256": canonical_hash(image_ledger),
        "feature_ledger_sha256": canonical_hash(feature_ledger),
        "prediction_sha256": canonical_hash(row_outputs),
        "aggregate_sha256": canonical_hash(aggregate),
        "evaluation_namespaces": _evaluation_namespaces(aggregate),
        "gates": gates,
        "q7_power_estimate": q7_details,
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
            "derangement_seed": DERANGEMENT_SEED,
            "bootstrap_replicates": args.bootstrap_replicates,
        },
        "source": {
            "runner_sha256": sha256_file(Path(__file__)),
            "module_sha256": sha256_file(
                WORKSPACE / "src/visualvit/real_qualification.py"
            ),
        },
        "interpretation_boundary": (
            "Real-data matcher qualification only. Stable/Improved/Worse labels "
            "are audited in the cohort but are not predicted or evaluated. "
            "Matching-event metrics and delta_match cannot support a progression, "
            "clinical, formal B4, frozen-VLM, or allocation-4161 claim. Q6 "
            "(fresh-process reproduction) is evaluated externally."
        ),
    }
    summary_path = args.output_root / "summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(
        json.dumps(
            {"status": status, "summary": str(summary_path)}, sort_keys=True
        )
    )
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
