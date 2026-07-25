# CheXTemporal-CheXpert Progression Pilot v1

**Frozen intent:** paper-grade secondary real-data experiment  
**Evidence class:** `NON_CONFIRMATORY_REAL_DATA_SECONDARY`  
**Date:** 2026-07-24

## Question and interpretation boundary

This experiment asks whether the frozen-image CAPES relation interface carries
useful real longitudinal progression signal, and whether correct cross-time
assignment changes three-class persistent progression performance under an
isomorphic B4 intervention.

It is not the confirmatory CAPES entity-level five-label experiment.
CheXTemporal supplies one progression label and two sets of labeled boxes per
finding row, but does not assign a separate progression owner to every box in a
multifocal row. Results may support engineering feasibility, a secondary
image-level table, and the design of the eventual formal experiment. They may
not be described as lesion tracking, a clinical effect, or `GO_FORMAL_E1`.

## Frozen sources

- CheXTemporal `gold_bboxes.parquet`: 91,676 bytes, SHA-256
  `20f114c7f81a66986ed0a697d4056d2b9c4029e7df77c97217db4908726f2064`.
- CheXpert-v1.0-small parent images under
  `H:\Xiyao_Wang\000_Public Dataset\CheXpert-v1.0-small`.
- Frozen BiomedCLIP ViT-B/16 checkpoint: 343,241,699 bytes, SHA-256
  `3be6f957b2fc8b8324cc6ed6faebdcb218511b41fc0f542312e21850424a2590`.
- The CheXTemporal and CheXpert source licenses remain controlling. Raw images
  are not copied into the repository or result bundle.

## Cohort

Only `dataset == chexpert` rows enter. Both parent images must exist under the
official CheXpert `train` tree. Boxes are mapped from the CheXTemporal
short-side-1024 annotation canvas to the derivative image aspect ratio and then
to the registered 224-by-224 encoder input. A row is excluded when:

1. a parent image is missing or lies outside the official train tree;
2. a Box label is duplicated within either timepoint;
3. coordinates are non-finite, non-positive, outside the annotation canvas, or
   map below two pixels in width or height;
4. the row progression is incompatible with set-level support: `New` requires
   a current-only endpoint, `Resolved` requires a prior-only endpoint, and a
   persistent label requires a shared endpoint.

Rows with conflicting progression targets for the same
patient/pair/image/finding key are also excluded before feature extraction.
The complete preregistration audit produced 601 retained rows, 70 patients, 357
temporal pairs, and 475 unique retained parent images. Label counts are Improved
127, New 58, Resolved 29, Stable 251, and Worse 136. Exactly 90 rows from 22
patients have at least two shared endpoints and a persistent label; their counts
are Improved 24, Stable 38, and Worse 28. Runtime counts must match exactly or
stop.

## Frozen representation

The encoder is inference-only and uses the same CLIP normalization as the
successful MIMIC v3 qualification. Every unique whole image and exact bbox crop
is encoded once. The crop rectangle is exact; no label-dependent expansion is
allowed. Repeating the first registered batch with identical order and shape
must give maximum absolute difference zero.

Each region feature is `[zero_state, zero_query, cx, cy, width, height,
BiomedCLIP_CLS]`. A relation is
`[prior, current, current-prior, prior*current, event_onehot]`. Variable relation
sets are reduced by the valid-slot mean. The classifier is fixed to a
non-affine LayerNorm followed by one linear layer. The vision encoder is frozen.

## Tasks and systems

### F5: full five-label secondary task

All 876 rows enter. Systems:

- `current_only_global`: current whole-image CLS only;
- `paired_global`: prior/current whole-image CLS relation;
- `oracle_region`: relation mean under equal Box-label assignment;
- `learned_region`: frozen visual-plus-geometry global Hungarian matcher;
- `oracle_no_interaction`: oracle relation with delta and multiplicative
  interaction channels zeroed.

### B3: persistent three-label B4 task

Only the 90 B4-eligible rows enter. Systems:

- `B4a_deranged`: anatomy-compatible, zero-fixed-point permutation of persistent
  endpoints, preserving observation multisets and birth/death sets;
- `B4b_oracle`: equal Box-label assignment;
- `learned_region`: frozen visual-plus-geometry global Hungarian assignment;
- `paired_global`;
- `current_only_global`;
- `oracle_no_interaction`.

Derangement IDs are `[81001, 81002, 81003]`. Non-deranged systems are computed
once and copied identically across IDs solely to preserve the paired design.

## Splits and training

- Deterministic patient-stratified five-fold out-of-fold evaluation, separately
  for F5 and B3. No patient may cross folds.
- Fold construction uses only patient label-count vectors and deterministic
  tie-breaking. The emitted fold manifest and SHA-256 are evidence.
- Training seeds: `[17, 29, 43]`.
- Full-batch AdamW, 300 fixed steps, learning rate `0.01`, weight decay `1e-4`.
- Training-fold inverse-frequency class weights; no early stopping, checkpoint
  selection, threshold selection, rescue, or fold deletion.
- Every system uses the same task rows, folds, seed, optimizer, step count, and
  classifier architecture. B4a and B4b differ only in assignment.

## Metrics and inference

Primary metric is patient-balanced macro F1: valid rows within each patient sum
to weight one before classwise F1 is computed. Also report ordinary macro F1,
balanced accuracy, per-class F1, training fit, runtime, peak VRAM, and parameter
count.

Ten thousand paired hierarchical bootstrap replicates resample patients and
training seeds; B3 additionally samples the crossed derangement bank. Report
95% percentile intervals for every system and:

- `B4b_oracle - B4a_deranged`;
- `learned_region - B4a_deranged`;
- `B4b_oracle - paired_global`;
- `B4b_oracle - oracle_no_interaction`.

At least 95% of replicates must contain all registered labels. A directional
engineering signal requires a point difference of at least 5 percentage points
and a 95% lower bound above zero. This threshold does not convert the experiment
into a confirmatory entity-level claim.

## Stop order

Stop before metrics on any source/model/protocol hash mismatch, count drift,
patient overlap, coordinate failure, non-finite feature, nonzero repeat
difference, B4 isomorphism failure, fixed point, null-set change, prediction
layout mismatch, or insufficient bootstrap validity. No retry may change the
cohort, seed bank, fold algorithm, systems, thresholds, or optimization
contract.

## Required artifacts

- protocol/source/model/image/feature ledgers and hashes;
- retained cohort and exclusions;
- patient fold manifests for F5 and B3;
- feature cache;
- per-row OOF predictions for every system/seed/derangement;
- per-block and aggregate metrics;
- B4 isomorphism audit;
- hierarchical bootstrap samples summary and intervals;
- environment, runtime, peak VRAM, command, and terminal verdict.
