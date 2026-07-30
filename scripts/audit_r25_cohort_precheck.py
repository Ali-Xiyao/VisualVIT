"""Read-only pre-freeze cohort audit for the R25 Chest ImaGenome protocol.

This script is NON_CONFIRMATORY_PRE_FREEZE_AUDIT. It reads only:
  - Chest ImaGenome gold comparison + attribute files
  - MIMIC-CXR metadata + split (already qualified in R24 v3)
  - R24 v3 cohort summary (for cross-source exclusion estimation)

It writes nothing to artifacts/, loads no model, performs no training, and
accesses no formal test image. Its sole purpose is to produce concrete
patient/pair/row and five-label coverage counts so the five open design
questions in the R25 PRE_FREEZE spec can be resolved before freeze.
"""

from __future__ import annotations

import csv
import gzip
import json
from collections import Counter, defaultdict
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]

CI_ROOT = Path(
    r"F:\VisualVIT_runtime\050_routeC\data\chest_imagenome"
    r"\chest-imagenome-dataset-1.0.0"
)
GOLD_COMPARISON = CI_ROOT / "gold_dataset" / "gold_object_comparison_with_coordinates.txt"
GOLD_ATTRIBUTE = CI_ROOT / "gold_dataset" / "gold_object_attribute_with_coordinates.txt"
GOLD_SCALING = CI_ROOT / "gold_dataset" / "gold_bbox_scaling_factors_original_to_224x224.csv"
ANATOMY_VOCAB = CI_ROOT / "semantics" / "objects_detectable_by_bbox_pipeline_v1.txt"

MIMIC_META = Path(
    r"H:\Xiyao_Wang\000_Public Dataset\mimic_cxr_other"
    r"\mimic-cxr-2.0.0-metadata.csv.gz"
)
MIMIC_SPLIT = Path(
    r"H:\Xiyao_Wang\000_Public Dataset\mimic_cxr_other"
    r"\mimic-cxr-2.0.0-split.csv.gz"
)

R24_V3_SUMMARY = (
    WORKSPACE
    / "artifacts/real_qualification/chextemporal_mimic_matcher_v3/process_a/summary.json"
)


def _read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def _read_gz_csv(path: Path) -> list[dict[str, str]]:
    with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _anatomy_from_object_id(object_id: str) -> str:
    """Chest ImaGenome object_id encodes anatomy after the last '|'."""
    if not object_id:
        return ""
    return object_id.rsplit("|", 1)[-1].strip().lower()


def main() -> None:
    print("=== R25 pre-freeze cohort audit (read-only) ===")
    print(f"Chest ImaGenome root: {CI_ROOT}")
    print(f"  comparison exists: {GOLD_COMPARISON.is_file()}")
    print(f"  attribute exists:  {GOLD_ATTRIBUTE.is_file()}")
    print(f"  scaling exists:    {GOLD_SCALING.is_file()}")
    print(f"MIMIC metadata exists: {MIMIC_META.is_file()}")
    print(f"MIMIC split exists:    {MIMIC_SPLIT.is_file()}")
    print()

    # Closed anatomy vocabulary
    anatomy_vocab = set()
    if ANATOMY_VOCAB.is_file():
        for line in ANATOMY_VOCAB.read_text(encoding="utf-8").splitlines():
            line = line.strip().lower()
            if line:
                anatomy_vocab.add(line)
    print(f"Closed anatomy vocab size: {len(anatomy_vocab)}")

    # ---- Load Chest ImaGenome gold comparison rows ----
    comparison_rows = _read_tsv(GOLD_COMPARISON)
    print(f"Gold comparison rows: {len(comparison_rows)}")
    comp_patients = {r["patient_id"] for r in comparison_rows}
    print(f"  unique patients in comparison file: {len(comp_patients)}")
    comp_images = set()
    for r in comparison_rows:
        comp_images.add(r["current_image_id"])
        comp_images.add(r["previous_image_id"])
    print(f"  unique dicom_ids referenced: {len(comp_images)}")
    comp_comparison_dist = Counter(r["comparison"] for r in comparison_rows)
    print(f"  comparison distribution: {dict(comp_comparison_dist)}")
    print()

    # ---- Load Chest ImaGenome gold attribute rows (per-image entity presence) ----
    attribute_rows = _read_tsv(GOLD_ATTRIBUTE)
    print(f"Gold attribute rows: {len(attribute_rows)}")
    attr_patients = {r["patient_id"] for r in attribute_rows}
    print(f"  unique patients in attribute file: {len(attr_patients)}")
    # Build per-image anatomy presence set.
    # NOTE: attribute file image_id has a '.dcm' suffix (e.g. '...dcm') but the
    # comparison file's current_image_id / previous_image_id do NOT. Normalize by
    # stripping the '.dcm' suffix so the join keys match.
    image_anatomies: dict[str, set[str]] = defaultdict(set)
    image_to_patient: dict[str, str] = {}
    for r in attribute_rows:
        img = r.get("image_id") or r.get("dicom_id") or ""
        if not img:
            continue
        if img.endswith(".dcm"):
            img = img[: -len(".dcm")]
        anatomy = _anatomy_from_object_id(r.get("object_id", ""))
        if anatomy:
            image_anatomies[img].add(anatomy)
            image_to_patient[img] = r["patient_id"]
    print(f"  unique images with anatomy presence: {len(image_anatomies)}")
    print()

    # ---- Load MIMIC metadata ----
    print("Loading MIMIC metadata (this may take a moment)...")
    meta_rows = _read_gz_csv(MIMIC_META)
    print(f"MIMIC metadata rows: {len(meta_rows)}")
    meta_cols = meta_rows[0].keys() if meta_rows else []
    print(f"  columns: {list(meta_cols)}")
    # Build dicom_id -> metadata mapping
    # MIMIC metadata columns: dicom_id, subject_id, study_id, StudyDate, StudyTime, ViewPosition, ...
    dicom_meta: dict[str, dict[str, str]] = {}
    for r in meta_rows:
        did = r.get("dicom_id", "")
        if did:
            dicom_meta[did] = r
    print(f"  unique dicom_ids in metadata: {len(dicom_meta)}")
    print()

    # ---- Load MIMIC split ----
    print("Loading MIMIC split...")
    split_rows = _read_gz_csv(MIMIC_SPLIT)
    print(f"MIMIC split rows: {len(split_rows)}")
    split_cols = split_rows[0].keys() if split_rows else []
    print(f"  columns: {list(split_cols)}")
    dicom_split: dict[str, str] = {}
    for r in split_rows:
        did = r.get("dicom_id", "")
        if did:
            dicom_split[did] = r.get("split", "")
    split_dist = Counter(dicom_split.values())
    print(f"  split distribution: {dict(split_dist)}")
    print()

    # ---- R24 v3 cohort (for cross-source exclusion estimate) ----
    if R24_V3_SUMMARY.is_file():
        r24_summary = json.loads(R24_V3_SUMMARY.read_text(encoding="utf-8"))
        r24_cohort = r24_summary.get("cohort", {})
        print(
            f"R24 v3 cohort: {r24_cohort.get('retained_patients')} patients, "
            f"{r24_cohort.get('retained_pairs')} pairs, "
            f"{r24_cohort.get('retained_rows')} rows"
        )
        # R24 v3 used CheXTemporal patients (different source); the patient_id
        # namespace differs from Chest ImaGenome, so direct overlap is unlikely.
        # We record this as an estimate; the actual cross-source exclusion
        # uses dicom_id overlap, which the runner will check at freeze time.
    print()

    # ---- Apply fail-closed cohort filters ----
    # Conditions from the R25 spec:
    # 1. both images resolve in MIMIC metadata
    # 2. both images in MIMIC train split
    # 3. patient_id / study_id agree (we check patient_id against subject_id)
    # 4. prior time strictly earlier than current (StudyDate then StudyTime)
    # 5. ViewPosition identical and in {AP, PA}
    # 7. unique progression target per (patient, study-pair, anatomy)
    # 9/10. set-level support for labels
    # 11. cross-source leakage exclusion (estimated; full check at freeze)

    print("=== Applying fail-closed cohort filters ===")
    filter_counts = Counter()
    retained_rows: list[dict[str, str]] = []
    pair_keys: set[tuple[str, str, str]] = set()  # (patient, prior_img, current_img)
    pair_anatomy_targets: dict[tuple[str, str, str, str], str] = {}

    for r in comparison_rows:
        filter_counts["total_comparison_rows"] += 1
        pid = r["patient_id"]
        cur_img = r["current_image_id"]
        prv_img = r["previous_image_id"]
        comparison = r["comparison"]
        anatomy = _anatomy_from_object_id(r.get("subject_id", "")) or _anatomy_from_object_id(r.get("object_id", ""))

        # Condition 1: both images in MIMIC metadata
        if cur_img not in dicom_meta or prv_img not in dicom_meta:
            filter_counts["reject_not_in_metadata"] += 1
            continue
        cur_meta = dicom_meta[cur_img]
        prv_meta = dicom_meta[prv_img]

        # Condition 2: both in train split
        if dicom_split.get(cur_img) != "train" or dicom_split.get(prv_img) != "train":
            filter_counts["reject_not_train_split"] += 1
            continue

        # Condition 3: patient_id / study_id agree
        # MIMIC subject_id is the patient; Chest ImaGenome patient_id should match
        cur_subject = cur_meta.get("subject_id", "")
        prv_subject = prv_meta.get("subject_id", "")
        if cur_subject != prv_subject:
            filter_counts["reject_subject_mismatch"] += 1
            continue
        # Chest ImaGenome patient_id is like "patient12345"; MIMIC subject_id is numeric
        # We record the MIMIC subject_id as the authoritative patient key
        mimic_patient = cur_subject

        # Condition 4: chronology
        cur_date = cur_meta.get("StudyDate", "")
        prv_date = prv_meta.get("StudyDate", "")
        cur_time = cur_meta.get("StudyTime", "")
        prv_time = prv_meta.get("StudyTime", "")
        if not cur_date or not prv_date:
            filter_counts["reject_missing_studydate"] += 1
            continue
        if (prv_date, prv_time) >= (cur_date, cur_time):
            filter_counts["reject_not_strictly_chronological"] += 1
            continue

        # Condition 5: ViewPosition identical and in {AP, PA}
        cur_vp = cur_meta.get("ViewPosition", "")
        prv_vp = prv_meta.get("ViewPosition", "")
        if cur_vp != prv_vp or cur_vp not in ("AP", "PA"):
            filter_counts["reject_view_mismatch"] += 1
            continue

        # Condition 7: unique progression target per (patient, pair, anatomy)
        pair_key = (mimic_patient, prv_img, cur_img)
        target_key = (mimic_patient, prv_img, cur_img, anatomy)
        if target_key in pair_anatomy_targets:
            if pair_anatomy_targets[target_key] != comparison:
                filter_counts["reject_target_conflict"] += 1
                continue
            else:
                filter_counts["reject_duplicate_target"] += 1
                continue
        pair_anatomy_targets[target_key] = comparison
        pair_keys.add(pair_key)

        # Map comparison -> persistent label
        label_map = {"no change": "Stable", "improved": "Improved", "worsened": "Worse"}
        persistent_label = label_map.get(comparison, "")
        if not persistent_label:
            filter_counts["reject_unknown_comparison"] += 1
            continue

        retained_rows.append(
            {
                "patient_id": mimic_patient,
                "prior_image": prv_img,
                "current_image": cur_img,
                "anatomy": anatomy,
                "label": persistent_label,
                "comparison": comparison,
            }
        )
        filter_counts["retained_persistent_rows"] += 1

    print(f"Filter counts: {dict(filter_counts)}")
    print()

    # ---- Derive new/resolved from attribute presence/absence ----
    # For each (patient, prior_img, current_img) pair, derive:
    #   new = anatomies in current but not prior
    #   resolved = anatomies in prior but not current
    print("=== Deriving new/resolved labels from attribute presence ===")
    birth_death_rows: list[dict[str, str]] = []
    pairs_with_birth_death = 0
    for pair_key in pair_keys:
        pid, prv_img, cur_img = pair_key
        prv_anat = image_anatomies.get(prv_img, set())
        cur_anat = image_anatomies.get(cur_img, set())
        new_anat = cur_anat - prv_anat
        resolved_anat = prv_anat - cur_anat
        if new_anat or resolved_anat:
            pairs_with_birth_death += 1
        for a in new_anat:
            birth_death_rows.append(
                {
                    "patient_id": pid,
                    "prior_image": prv_img,
                    "current_image": cur_img,
                    "anatomy": a,
                    "label": "New",
                }
            )
        for a in resolved_anat:
            birth_death_rows.append(
                {
                    "patient_id": pid,
                    "prior_image": prv_img,
                    "current_image": cur_img,
                    "anatomy": a,
                    "label": "Resolved",
                }
            )
    print(f"Pairs with birth/death signal: {pairs_with_birth_death} / {len(pair_keys)}")
    print(f"Birth/death rows derived: {len(birth_death_rows)}")
    print()

    # ---- Final cohort counts ----
    all_rows = retained_rows + birth_death_rows
    cohort_patients = {r["patient_id"] for r in all_rows}
    cohort_pairs = {(r["patient_id"], r["prior_image"], r["current_image"]) for r in all_rows}
    label_counts = Counter(r["label"] for r in all_rows)
    label_patients: dict[str, set[str]] = defaultdict(set)
    for r in all_rows:
        label_patients[r["label"]].add(r["patient_id"])

    print("=== R25 cohort pre-audit result ===")
    print(f"Total retained rows (persistent + birth/death): {len(all_rows)}")
    print(f"  persistent rows: {len(retained_rows)}")
    print(f"  birth/death rows: {len(birth_death_rows)}")
    print(f"Unique patients: {len(cohort_patients)}")
    print(f"Unique temporal pairs: {len(cohort_pairs)}")
    print()
    print("Five-label row counts:")
    for label in ("Stable", "Improved", "Worse", "New", "Resolved"):
        print(f"  {label}: {label_counts.get(label, 0)} rows, {len(label_patients.get(label, set()))} patients")
    print()

    # ---- Q7 target check ----
    q7_target = 100
    persistent_patients = {r["patient_id"] for r in retained_rows}
    print(f"Q7 target: >= {q7_target} patients with persistent endpoints")
    print(f"Persistent-endpoint patients: {len(persistent_patients)}")
    if len(persistent_patients) >= q7_target:
        print(f"  -> MEETS Q7 target (margin: +{len(persistent_patients) - q7_target})")
    else:
        print(f"  -> BELOW Q7 target (deficit: -{q7_target - len(persistent_patients)})")
    print()

    # ---- Five-label coverage gate ----
    coverage_min = 10
    labels_meeting = sum(
        1 for label in ("Stable", "Improved", "Worse", "New", "Resolved")
        if len(label_patients.get(label, set())) >= coverage_min
    )
    print(f"Five-label coverage gate: >= {coverage_min} patients per label")
    print(f"  labels meeting gate: {labels_meeting} / 5")
    if labels_meeting == 5:
        print("  -> PRIMARY = five-label endpoint")
    else:
        print("  -> PRIMARY = three-label persistent (fallback); five-label is secondary")
    print()

    # ---- Cross-source exclusion estimate ----
    print("Cross-source exclusion estimate:")
    print("  R24 v3 cohort: 34 patients (CheXTemporal source, different patient namespace)")
    print("  R24 progression pilot: 70 patients (CheXTemporal source)")
    print(f"  Chest ImaGenome gold: {len(cohort_patients)} patients (MIMIC subject_id namespace)")
    print("  Patient_id namespaces differ between CheXTemporal and Chest ImaGenome,")
    print("  so patient-level overlap is unlikely. dicom_id-level overlap is the")
    print("  authoritative check and will be enforced by the runner at freeze time.")
    print()

    print("=== Design question resolution (pre-freeze) ===")
    print("Q1 (anatomy dedup): order by (y1, x1); set-membership; matcher uses anatomy compat.")
    print("Q2 (new/resolved granularity): per-anatomy (set presence/absence) — confirmed")
    print("   feasible; birth/death signal exists in", pairs_with_birth_death, "pairs.")
    print(f"Q3 (fold construction): fresh 5-fold on {len(cohort_patients)} gold patients")
    print("   with seed 20260725; assert no dicom overlap with silver test.csv.")
    print(f"Q4 (cohort ceiling): {len(cohort_patients)} patients pre-exclusion. Q7 needs 100.")
    if len(persistent_patients) >= q7_target:
        print("   -> Q7 is achievable on this cohort.")
    else:
        print("   -> Q7 may be UNDERPOWERED; consider relaxing view/split filters or")
        print("      accept UNDERPOWERED_NO_CLAIM with explicit power limitation.")
    print("Q5 (R25 re-freeze): failure #2 + r16 bundle regen bundled into R25 re-freeze.")


if __name__ == "__main__":
    main()
