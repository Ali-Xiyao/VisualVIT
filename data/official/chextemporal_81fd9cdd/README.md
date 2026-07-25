---
license: cc-by-nc-4.0
task_categories:
  - image-classification
  - object-detection
  - text-classification
  - image-text-to-text
language: [en]
tags: [medical, chest-xray, radiology, longitudinal, progression, silver-supervision]
size_categories: [100K<n<1M]
pretty_name: CheXTemporal
configs:
  - config_name: silver_findings
    data_files: silver_findings.parquet
  - config_name: silver_sentences
    data_files: silver_sentences.parquet
  - config_name: silver_studies
    data_files: silver_studies.parquet
  - config_name: gold_progression_pairs
    data_files: gold_progression_pairs.parquet
  - config_name: gold_bboxes
    data_files: gold_bboxes.parquet
extra_gated_prompt: >-
  By accessing CheXTemporal you agree to use it solely for non-commercial
  research, to attribute the dataset and the underlying parent corpora
  (CheXpert, MIMIC-CXR, ReXGradient) in any publication, and to obtain the
  underlying chest-radiograph images yourself under the parent corpora's
  respective access agreements (this dataset does NOT redistribute images).
---

# CheXTemporal

A longitudinal chest-radiograph dataset of paired (current, prior) studies
with disease–progression labels, anatomy-aligned segmentation masks, and
sentence-level static/dynamic annotations, derived from CheXpert, MIMIC-CXR,
and ReXGradient. CheXTemporal pairs an expert-annotated **gold** evaluation
split with a much larger MedGemma-generated **silver** training corpus.

This release contains **annotations only**. Images must be downloaded
separately from each parent corpus under that corpus's license.

## Summary

| | Gold | Silver |
|---|---:|---:|
| Patients | 197 | 34,296 |
| Pair × finding examples | 1,787 | 282,214 |
| Bounding boxes (manual) | 4,702 | — |
| Anatomy masks (automatic) | — | 168,140 |
| Static / dynamic sentences | — | 278,953 / 416,976 |

A "pair × finding" example is one (study, finding) annotation that has a
verified in-corpus prior study and on-disk prior + current image.

## Files

All files live at the repository root.

| File | Contents |
|---|---|
| `README.md` | this file |
| `LICENSE` | CC-BY-NC 4.0 |
| `DATASHEET.md` | Datasheet for Datasets entry |
| `gold_progression_pairs.parquet` | 1,787 expert progression labels |
| `gold_bboxes.parquet` | 1,562 expert bbox annotations |
| `silver_findings.parquet` | 282,214 rows (one per pair × finding) |
| `silver_sentences.parquet` | ~696k rows (one per labeled sentence) |
| `silver_studies.parquet` | 128,071 rows (one per study, with impressions) |
| `silver_masks.zip` | 168,140 anatomy mask JSONs (COCO RLE) |

## Quickstart

```python
from datasets import load_dataset

# Available configs: silver_findings, silver_sentences, silver_studies,
#                    gold_progression_pairs, gold_bboxes
finds = load_dataset("anonaccount107240/CheXTemporal",
                     "silver_findings", split="train")
print(finds[0])
```

Or with pandas (no `datasets` install needed):

```python
import pandas as pd
finds = pd.read_parquet(
    "hf://datasets/anonaccount107240/CheXTemporal/silver_findings.parquet"
)
```

The anatomy masks live in `silver_masks.zip` as one COCO-format JSON
per study; the relative path inside the archive is given by the
`silver_mask_path` column of `silver_findings.parquet`.

## Schemas

### `silver_findings.parquet` (282,214 × 16)

| Column | Type | Description |
|---|---|---|
| `dataset` | str | `chexpert`, `mimic`, or `rexgradient` |
| `patient_id` | str | Patient token (e.g. `patient35117`) |
| `study_id_curr`, `study_id_prev` | str | Current and prior study tokens |
| `finding_token` | str | Snake-case finding ID (e.g. `pleural_effusion`) |
| `finding` | str | Human-readable finding (e.g. `Pleural Effusion`) |
| `progression` | str | One of `Stable`, `New`, `Worse`, `Improved`, `Resolved` |
| `anatomy` | str | MedGemma-extracted anatomy phrase(s) |
| `reasoning` | str | MedGemma's free-text rationale |
| `evidence` | list[str] | Quoted spans from the radiology report |
| `silver_findings_path`, `silver_sentences_path` | str | Original cluster-layout paths (informational; same content lives in this row + `silver_studies.parquet`) |
| `silver_mask_path` | str | Relative path inside `silver_masks.zip` (empty if `has_mask = 0`) |
| `parent_image_curr`, `parent_image_prev` | str | Relative paths under the parent dataset's standard layout |
| `has_mask` | int | 1 if a filtered anatomy mask exists, 0 otherwise (always 0 for ReXGradient) |

### `silver_sentences.parquet` (~696k × 5)

`dataset`, `patient_id`, `study_id`, `sentence`, `label` (`static` or `dynamic`).

### `silver_studies.parquet` (128,071 × 10)

`dataset`, `patient_id`, `study_id`, `current_impression`, `prior_impression`,
`current_findings`, `prior_findings`, `n_sentences`, `n_static`, `n_dynamic`.

> **Note.** Many MIMIC-CXR reports contain only an Impression section,
> not a separate Findings section; in those rows `current_findings` /
> `prior_findings` are empty strings.

### `gold_progression_pairs.parquet` (1,787 × 8)

`patient_id`, `study_id_prev`, `study_id_curr`, `img_path_prev`,
`img_path_curr`, `disease_name`, `progression`, `dataset`. The
`progression` column uses the same five class names as silver:
`Stable`, `New`, `Worse`, `Improved`, `Resolved`.

### `gold_bboxes.parquet` (1,562 × 10)

Same row schema as `gold_progression_pairs`, plus expert bounding boxes
on the prior and current images:

| Column | Type | Description |
|---|---|---|
| `prior_bboxes` | list[struct{x1, y1, x2, y2, label}] | Rectangles drawn on prior image (`[]` if none) |
| `current_bboxes` | list[struct{x1, y1, x2, y2, label}] | Rectangles drawn on current image (`[]` if none) |

```python
gold = pd.read_parquet("gold_bboxes.parquet")
print(gold.iloc[0]["current_bboxes"])
# → [{'x1': 204, 'y1': 118, 'x2': 421, 'y2': 391, 'label': 'Box1'}]
```

### Mask JSONs (inside `silver_masks.zip`)

Each mask is a COCO-format JSON. Decode with
[`pycocotools`](https://github.com/cocodataset/cocoapi):

```python
import json, numpy as np
from pycocotools import mask as cocomask

with open(mask_path) as f:
    d = json.load(f)
H, W = d["annotations"][0]["segmentation"]["size"]
union = np.zeros((H, W), dtype=bool)
for ann in d["annotations"]:
    union |= cocomask.decode(ann["segmentation"]).astype(bool)
```

## Obtaining parent images

Images are not redistributed. Download from each parent corpus and lay
them out under a single root containing `chexpert/`, `mimic/`, and
optionally `rexgradient/` subfolders following each corpus's standard
structure:

| Corpus | Access | Layout |
|---|---|---|
| **CheXpert** | [Stanford ML Group](https://stanfordmlgroup.github.io/competitions/chexpert/) DUA | `chexpert/<split>/<patient>/<study>/<image>.jpg` |
| **MIMIC-CXR** | [PhysioNet](https://physionet.org/content/mimic-cxr/) credentialing | `mimic/p<NN>/p<patient>/s<study>/<dicom_uid>.jpg` |
| **ReXGradient** | Bring your own | `rexgradient/deid_png/<patient>/<study>/.../<image>.png` |

The `parent_image_*` columns and the mask JSONs' embedded `file_name`
fields are relative to that root.

## Statistics

### Per-dataset (pair × finding)

| Dataset | Gold p×f | Silver patients | Silver p×f | Silver sentences | Silver studies | Silver masks |
|---|---:|---:|---:|---:|---:|---:|
| CheXpert | 1,074 | 22,638 | 197,449 | 462,572 | 90,213 | 90,513 |
| MIMIC-CXR | 594 | 8,497 | 79,476 | 208,184 | 34,696 | 77,627 |
| ReXGradient | 119 | 3,161 | 5,289 | 25,173 | 3,162 | 0 |
| **Total** | **1,787** | **34,296** | **282,214** | **695,929** | **128,071** | **168,140** |

### Per-finding (silver only — gold has 7–455 examples per finding)

| Finding | Silver | Finding | Silver |
|---|---:|---|---:|
| Pleural effusion | 69,164 | Pneumothorax | 15,546 |
| Lung opacity | 68,864 | Consolidation | 12,362 |
| Edema | 44,393 | Enlarged cardiomediastinum | 5,900 |
| Atelectasis | 29,691 | Pneumonia | 5,790 |
| Cardiomegaly | 26,079 | Lung lesion | 3,276 |
| | | Pleural other | 1,149 |

### Per-progression-class (pair × finding)

| Class | Gold | Silver |
|---|---:|---:|
| `Stable` | 654 | 145,254 |
| `Worse` | 440 | 64,960 |
| `Improved` | 424 | 36,600 |
| `New` | 154 | 32,272 |
| `Resolved` | 115 | 3,128 |
| **Total** | **1,787** | **282,214** |

## Methodology

1. **Sentence labelling.** Each report's Impression section is
   sentence-split; MedGemma 27B labels each sentence as `static` or
   `dynamic`.
2. **Per-finding extraction.** For each (study, finding) where the
   finding is one of the 11 standard CheXpert categories, MedGemma is
   prompted with the current and matched-prior impressions to extract
   `progression`, `anatomy`, and `evidence` quotes.
3. **Anatomy-aligned masks.** CheXpert/MIMIC frontal images are
   processed by CXAS, then filtered to anatomies relevant to each
   finding (e.g. pleural effusion → costophrenic angles + lower lung).
4. **Pair filtering.** A finding is included only if the patient has a
   verified in-corpus prior study (chronological for CheXpert,
   impression-text-matched for MIMIC and ReXGradient) and both prior
   and current images are on disk.

## Intended uses

- Pre-training / fine-tuning VLMs for chest-X-ray progression
  classification (5-way).
- Supervised heatmap / phrase-grounding learning with anatomy-aligned
  masks (CheXpert + MIMIC-CXR).
- Sentence-level static/dynamic classification.
- Held-out evaluation against the 1,787-row gold split for progression
  and the 4,702 expert bounding boxes for localization.

## Out-of-scope uses

Clinical decision-making for individual patients; re-identification or
attacks; commercial use.

## Limitations

- **Silver labels carry MedGemma's biases**, including class skew toward
  `stable` and `new` and occasional contradictions between
  `progression` and `evidence`.
- **ReXGradient has no anatomy masks** at this release.
- **Findings sections are not always present** in MIMIC-CXR reports
  (Impression-only); `current_findings` / `prior_findings` may be empty.
- **Image availability is cluster-dependent.** A small number of
  manifest-constructible findings were dropped because images were
  absent at assembly time.
- **`evidence` quotes are approximate** — MedGemma's text extraction
  may differ slightly from the report's exact phrasing.

## License

Annotations: **CC-BY-NC 4.0** (see `LICENSE`). Parent image corpora
retain their own licenses (CheXpert DUA, MIMIC-CXR PhysioNet, ReXGradient
per the authors). You must comply with each parent corpus's license
independently.
