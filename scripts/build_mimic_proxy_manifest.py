from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

EVIDENCE_CLASS = "NON_CONFIRMATORY_PROXY"
LABEL_ORDER = ("new", "resolved", "stable_positive")
LABEL_ID = {"new": 0, "resolved": 1, "stable_positive": 2}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_score(seed: int, *values: object) -> str:
    payload = ":".join((str(seed), *(str(value) for value in values)))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def image_path(root: Path, subject_id: int, study_id: int, dicom_id: str) -> Path:
    subject = str(int(subject_id))
    study = str(int(study_id))
    return root / f"p{subject[:2]}" / f"p{subject}" / f"s{study}" / f"{dicom_id}.jpg"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    base = Path(r"H:\Xiyao_Wang\000_Public Dataset\mimic_cxr_other")
    parser.add_argument(
        "--metadata",
        type=Path,
        default=base / "mimic-cxr-2.0.0-metadata.csv.gz",
    )
    parser.add_argument(
        "--official-split",
        type=Path,
        default=base / "mimic-cxr-2.0.0-split.csv.gz",
    )
    parser.add_argument(
        "--labels",
        type=Path,
        default=base / "mimic-cxr-2.0.0-chexpert.csv.gz",
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
        "--output-root",
        type=Path,
        default=Path(r"F:\VisualVIT_runtime\050_routeC\data"),
    )
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--per-class", type=int, default=80)
    parser.add_argument("--train-per-class", type=int, default=60)
    parser.add_argument("--seed", type=int, default=20260713)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    for path in (args.metadata, args.official_split, args.labels):
        if not path.is_file():
            raise FileNotFoundError(path)
    if not args.image_root.is_dir():
        raise FileNotFoundError(args.image_root)
    if args.train_per_class >= args.per_class:
        raise ValueError("train_per_class must be smaller than per_class")

    run_id = args.run_id or (
        "mimic_proxy_manifest_" + datetime.now().strftime("%Y%m%dT%H%M%S")
    )
    run_dir = args.output_root / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    metadata = pd.read_csv(
        args.metadata,
        usecols=[
            "dicom_id",
            "subject_id",
            "study_id",
            "ViewPosition",
            "StudyDate",
            "StudyTime",
        ],
    )
    official_split = pd.read_csv(args.official_split)
    labels = pd.read_csv(
        args.labels,
        usecols=["subject_id", "study_id", "Pleural Effusion"],
    )
    merged = metadata.merge(
        official_split,
        on=["dicom_id", "study_id", "subject_id"],
        how="inner",
        validate="one_to_one",
    )
    if int(merged.groupby("subject_id")["split"].nunique().max()) != 1:
        raise ValueError("official split leaks patients across partitions")

    merged["ViewPosition"] = merged["ViewPosition"].astype(str).str.upper()
    frontal = merged[merged["ViewPosition"].isin(["PA", "AP"])].copy()
    frontal["view_rank"] = frontal["ViewPosition"].map({"PA": 0, "AP": 1})
    frontal = (
        frontal.sort_values(
            ["subject_id", "study_id", "view_rank", "dicom_id"]
        )
        .drop_duplicates(["subject_id", "study_id"])
        .merge(
            labels,
            on=["subject_id", "study_id"],
            how="left",
            validate="many_to_one",
        )
        .sort_values(
            ["subject_id", "StudyDate", "StudyTime", "study_id", "dicom_id"]
        )
    )

    records: list[dict[str, Any]] = []
    for subject_id, group in frontal.groupby("subject_id", sort=False):
        rows = group.to_dict("records")
        for prior, current in zip(rows[:-1], rows[1:]):
            if prior["split"] != "train" or current["split"] != "train":
                continue
            if int(prior["StudyDate"]) == int(current["StudyDate"]):
                continue
            if prior["ViewPosition"] != current["ViewPosition"]:
                continue
            prior_label = prior["Pleural Effusion"]
            current_label = current["Pleural Effusion"]
            if pd.isna(prior_label) or pd.isna(current_label):
                continue
            if prior_label not in (0.0, 1.0) or current_label not in (0.0, 1.0):
                continue
            if prior_label == 0.0 and current_label == 1.0:
                proxy_label = "new"
            elif prior_label == 1.0 and current_label == 0.0:
                proxy_label = "resolved"
            elif prior_label == 1.0 and current_label == 1.0:
                proxy_label = "stable_positive"
            else:
                continue
            records.append(
                {
                    "subject_id": int(subject_id),
                    "proxy_label": proxy_label,
                    "label_id": LABEL_ID[proxy_label],
                    "view": prior["ViewPosition"],
                    "prior_study_id": int(prior["study_id"]),
                    "current_study_id": int(current["study_id"]),
                    "prior_dicom_id": prior["dicom_id"],
                    "current_dicom_id": current["dicom_id"],
                    "prior_date": int(prior["StudyDate"]),
                    "current_date": int(current["StudyDate"]),
                    "prior_path": str(
                        image_path(
                            args.image_root,
                            int(subject_id),
                            int(prior["study_id"]),
                            prior["dicom_id"],
                        )
                    ),
                    "current_path": str(
                        image_path(
                            args.image_root,
                            int(subject_id),
                            int(current["study_id"]),
                            current["dicom_id"],
                        )
                    ),
                }
            )

    candidates = pd.DataFrame.from_records(records)
    candidate_counts = candidates.groupby("proxy_label").size().to_dict()
    selected_groups = []
    used_subjects: set[int] = set()
    for label in LABEL_ORDER:
        group = candidates[candidates["proxy_label"] == label].copy()
        group["selection_score"] = [
            stable_score(
                args.seed,
                row.subject_id,
                row.prior_study_id,
                row.current_study_id,
            )
            for row in group.itertuples()
        ]
        group = (
            group.sort_values("selection_score")
            .drop_duplicates("subject_id")
        )
        group = group[~group["subject_id"].isin(used_subjects)].head(args.per_class)
        if len(group) != args.per_class:
            raise ValueError(f"not enough unique patients for {label}: {len(group)}")
        used_subjects.update(int(value) for value in group["subject_id"])
        group["split_score"] = [
            stable_score(args.seed + 1, value) for value in group["subject_id"]
        ]
        group = group.sort_values("split_score").reset_index(drop=True)
        group["proxy_split"] = "dev"
        group.loc[: args.train_per_class - 1, "proxy_split"] = "train"
        selected_groups.append(group)

    selected = pd.concat(selected_groups, ignore_index=True)
    selected = selected.sort_values(
        ["proxy_split", "proxy_label", "subject_id"]
    ).reset_index(drop=True)
    selected.insert(
        0,
        "proxy_id",
        [f"mimic_proxy_{index:04d}" for index in range(len(selected))],
    )
    selected["evidence_class"] = EVIDENCE_CLASS
    selected["official_split"] = "train"
    selected = selected.drop(columns=["selection_score", "split_score"])

    if selected["subject_id"].nunique() != len(selected):
        raise ValueError("patient uniqueness failed")
    if set(selected["official_split"]) != {"train"}:
        raise ValueError("non-train official partition entered proxy manifest")
    if (selected["prior_date"] == selected["current_date"]).any():
        raise ValueError("same-day pair entered proxy manifest")
    missing = []
    for row in selected.itertuples():
        for path_value in (row.prior_path, row.current_path):
            if not Path(path_value).is_file():
                missing.append(path_value)
    if missing:
        raise FileNotFoundError(f"{len(missing)} proxy images missing; first={missing[0]}")

    manifest_path = run_dir / "proxy_manifest.csv"
    selected.to_csv(manifest_path, index=False)
    source_files = {}
    for path in (args.metadata, args.official_split, args.labels):
        source_files[path.name] = {
            "path": str(path),
            "sha256": sha256_file(path),
            "bytes": path.stat().st_size,
        }

    split_counts = (
        selected.groupby(["proxy_split", "proxy_label"])
        .size()
        .unstack(fill_value=0)
        .to_dict(orient="index")
    )
    summary = {
        "evidence_class": EVIDENCE_CLASS,
        "formal_claim_allowed": False,
        "run_id": run_id,
        "status": "PASS",
        "source_files": source_files,
        "image_root": str(args.image_root),
        "candidate_counts": {key: int(value) for key, value in candidate_counts.items()},
        "selected_pairs": len(selected),
        "unique_patients": int(selected["subject_id"].nunique()),
        "split_counts": split_counts,
        "checks": {
            "official_train_only": True,
            "patient_unique_across_proxy_splits": True,
            "same_view_within_pair": bool(
                (selected["view"].isin(["AP", "PA"])).all()
            ),
            "different_study_date": True,
            "all_images_exist": True,
            "uncertain_and_missing_labels_masked": True,
            "reports_not_model_input": True,
        },
        "limitations": [
            "Pleural Effusion labels are report-derived study labels.",
            "No region/entity/bbox/null oracle is present.",
            "This manifest cannot support a formal CAPES B4 or clinical claim.",
        ],
        "artifacts": {
            manifest_path.name: {
                "sha256": sha256_file(manifest_path),
                "bytes": manifest_path.stat().st_size,
            }
        },
    }
    summary_path = run_dir / "summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps(summary, sort_keys=True))
    print(f"RESULT_DIR={run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

