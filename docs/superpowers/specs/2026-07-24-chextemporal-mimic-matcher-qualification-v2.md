# CheXTemporal-MIMIC Matcher Qualification v2

Status: `FROZEN_BEFORE_MODEL_ACCESS`  
Evidence class: `NON_CONFIRMATORY_REAL_DATA_QUALIFICATION`  
Formal claim allowed: `false`  
Training: `none`

## Direct base and v1 terminal evidence

The direct base is the frozen v1 protocol snapshot at SHA-256
`981d9ba67fc0f2c8cd5a870e132c4effee66d8922d47b8549bbd86b873069c6b`.
Its one no-retry process-A run is immutable technical-negative evidence:

- failure SHA-256:
  `7a090fdcc26d7fbe234807c5e7fa5fb9f8392bb733a9dbf30dc779b7d37f6860`;
- launcher result SHA-256:
  `a387d03cb89faa72193b7a3eca4bdc27fdb193f0d22aedc773746e94bcacb802`;
- failure:
  `valid source IDs must be unique within each batch item`;
- B was never started and no Q6 certificate was issued.

The failure occurred after frozen real image features were extracted and before
Q5 structural token allocation completed. It is not a scientific Q4 result.
The sole v2 behavioral correction offsets current-side observation source IDs
by the number of prior-side observations, so the joint source universe is
`0..(R_prior + R_current - 1)`. Gold entity IDs, Box labels, progression labels,
matcher scores, transport, cohort, crops, encoder, thresholds, bootstrap, and
gate order do not enter this ID construction and remain unchanged.

## Prerequisite authority

Model access is authorized only by the completed no-retry R24 double-CPU
transaction:

- frozen R24 protocol SHA-256:
  `2f8b1577d193bf6a63d5146853ffd2b5fdc70918b6937652ff2cef47d8cc8e44`;
- R24 parent certificate SHA-256:
  `e96629b24d4a7caf6239c0a48fe995649f04bbbc61ae5b1ec5e264c1d0a01d0c`;
- R24 scheduled launcher result SHA-256:
  `4ab514b54b352a7f9206f9ebe7f43247a0fcfdf6c79f54a78adf5cc48228ea05`;
- parent status `PASS_R24_SYNTHETIC_ENGINEERING`, all 11 comparison checks
  true, zero mismatch paths, equal canonical SHA-256, launcher exit code zero,
  and `retry_attempted=false`.

The qualification runner validates those three exact artifacts before creating
an output root. Any drift or non-green field relocks model access.

## Purpose

This gate asks one narrow question before any real progression training or
retained-allocation GPU experiment: can the frozen CAPES-CI partial-assignment
implementation consume real longitudinal box crops, represent persistent,
birth, and death endpoints, and recover case-local expert correspondence above
a within-pair randomized control?

It does not test per-box progression, clinical benefit, a formal B4 effect, or
frozen-VLM transfer. CheXTemporal's released parquet does not identify per-box
progression ownership in multifocal cases, so no entity-level progression claim
may be made from this run.

## Frozen inputs

- CheXTemporal revision:
  `81fd9cdd9b1208d8f8bd39d7a914c9b72fed8d79`
- `gold_bboxes.parquet`: 91,676 bytes, SHA-256
  `20f114c7f81a66986ed0a697d4056d2b9c4029e7df77c97217db4908726f2064`
- MIMIC metadata: 16,546,905 bytes, SHA-256
  `6a3748ce77724c0dfe7d2def8f47643e989e3bbf0795bc13b89c1578e1649d6b`
- MIMIC split: 12,198,758 bytes, SHA-256
  `515997bd6649045d7443d60c59a4ce9f6cca6c478871b8f2fb13454462bedb2f`
- BiomedCLIP ViT-B/16 checkpoint: 343,241,699 bytes, SHA-256
  `3be6f957b2fc8b8324cc6ed6faebdcb218511b41fc0f542312e21850424a2590`
- Annotation license: pinned package `CC BY-NC 4.0`.
- Parent-image use remains local/internal under the user's existing MIMIC
  access. This document does not certify CITI, a PhysioNet project DUA, or
  redistribution rights.

The exact selected-image SHA-256 ledger is materialized before feature
extraction. Any declared input hash drift is terminal.

## Frozen implementation

- qualification runner SHA-256:
  `4090a413cd00b52e2ae7fe36509c120cf03928a23d1b0ab0f7f9ceb9b06fee4c`;
- real-qualification module SHA-256:
  `6c3f2fe0bdb6721a8da60b1aa77927e7c6094cd0440bac30fc69c4218ac6e7a9`;
- independent verifier SHA-256:
  `6f7284372e10ed70a8a8cf1f07934e80635694c5546bad06f212011308644654`;
- focused test hashes:
  `07782b54cd801b81a976940aebfeb9bfb49cfc01aa22d5e36dc9e451be0a8c45`,
  `1dfeb9c5cf67736db342b271b4605e506fa19ae6f5f2aa130627789e6e678e4c`,
  and
  `cb1369b8fc84bcf4dacae693937f7bb147023cf76051a42c7d9c20d750179915`.

The frozen focused suite passes `15/15`; Ruff, format, and py_compile checks
pass. Source changes require a new protocol version and output namespace.

## Pre-freeze real-feature replay

Before freezing v2, the exact 267-row v1 cohort and its already persisted
BiomedCLIP feature cache were replayed through the corrected CPU matcher,
allocator, token, metric, and 10,000-replicate patient-bootstrap path. This
replay did not extract new features or overwrite v1:

- all 267 rows completed;
- global objective dominance passed;
- all 67 nontrivial B4 structural rows passed;
- primary persistent-edge F1 `0.993920972644377`;
- primary three-event macro F1 `1.0`;
- primary-minus-randomized persistent-edge F1 `0.9795918367346939`,
  patient-bootstrap 95% CI `[0.9620253164556962, 1.0]`;
- prediction SHA-256
  `01463ff0dff195b903af2e734d2e9291b788f61b20064fe39675653748cfbf94`;
- aggregate SHA-256
  `d8c32c216548def33f9c062b5f6c3016452c93bac22dd5af8c9b311bbe5c4298`.

These are pre-freeze qualification diagnostics, not the registered v2 result.
The registered v2 processes must independently reproduce them from images.

## Fail-closed cohort

Use only `dataset == "mimic"` rows satisfying all conditions:

1. both image IDs resolve in official MIMIC metadata and split;
2. both images belong to official `train`, to prevent accidental access to an
   official validation/test image;
3. patient ID and study IDs agree with metadata;
4. prior time is strictly earlier than current time;
5. prior and current `ViewPosition` are identical and in `{AP, PA}`;
6. both local derivative images exist;
7. the full patient/pair/finding key has exactly one progression target;
8. Box labels are unique within each image side;
9. persistent labels occur on both sides, prior-only labels define death, and
   current-only labels define birth;
10. the row's progression has compatible set-level support: a current-only
    endpoint for `New`, a prior-only endpoint for `Resolved`, and at least one
    shared endpoint for persistent labels.

The pre-code read-only audit expects 267 rows, 148 study pairs, and 34 patients.
Count drift is terminal until explained without reading model outputs.

## Coordinate contract

CheXTemporal annotations were drawn after scaling the shorter original image
side to 1024 while preserving aspect ratio. For original metadata
`Rows=H, Columns=W`, define:

```text
s = 1024 / min(H, W)
annotation_width  = W * s
annotation_height = H * s
x_224 = x_annotation / annotation_width  * 224
y_224 = y_annotation / annotation_height * 224
```

Coordinates are clipped only for floating-point epsilon at the closed upper
edge. Any nonpositive or out-of-frame box before or after mapping is terminal;
silent clipping, fixed `224/1024` scaling, and aspect-ratio guesses are
forbidden. Crop bounds use deterministic outward rounding (`floor` lower
coordinates, `ceil` upper coordinates) after validation. A fixture with unequal
Rows/Columns must test this transform.

## Frozen feature and matcher variants

All image crops use the same frozen BiomedCLIP preprocessing and checkpoint.
The crop rectangle is exact, with no label-dependent expansion. Features are
finite float32 vectors.

The CAPES-CI matcher receives two leading zero state/query channels followed by
declared identity views:

- `visual_only`: normalized crop embedding;
- `geometry_only`: normalized `(cx, cy, width, height)` in the 224 frame;
- `visual_geometry_equal`: the two disjoint identity views with fixed equal
  simplex weights.

The primary variant is `visual_geometry_equal`. Residual coefficient and both
null utilities stay at their transparent zero initialization. No annotation,
Box label, progression label, match count, or oracle cardinality enters the
matcher. Hard inference uses the registered global Hungarian solver. Greedy
combined-utility, geometry-only, and visual-only results are descriptive
comparators, not rescue variants.

## Gold and metrics

Within a row, equal expert Box labels define a persistent edge. Prior-only Box
labels define deaths; current-only labels define births. The labels are
case-local and are never treated as globally persistent lesion IDs.

Persist row-level sufficient statistics and aggregate:

- persistent edge precision, recall, F1, and exact row recovery;
- three-event macro F1 over persistent, death, and birth endpoints;
- global assignment objective and hard-plan feasibility;
- prediction determinism under a second fresh process;
- global-vs-greedy objective dominance;
- primary-minus-within-row-randomized differences.

The randomized comparison is evaluated only on rows with at least two shared
endpoints. It uses the registered `anatomy_compatible_derangement` with seed
`20260724`, requires zero fixed persistent edges, and preserves the exact
birth/death sets. Absolute primary metrics use the full qualified cohort.

Uncertainty uses a patient-cluster nonparametric bootstrap with seed `20260724`
and 10,000 replicates. Each replicate samples patients with replacement and
includes all their rows. Report percentile 95% confidence intervals and the
effective unique-patient count. No row-level iid interval may be called the
primary interval.

## Qualification gates

Evaluate in this order and stop at the first failure:

1. `Q0_ASSET_LINEAGE`: all frozen hashes, image paths, IDs, official splits,
   and license/access boundaries are recorded.
2. `Q1_COHORT_GEOMETRY`: exact cohort counts are reproduced; every annotation
   and mapped box is valid; no same-time or cross-view row survives.
3. `Q2_FEATURE_INTEGRITY`: all crop features are finite, checkpoint-frozen, and
   reproducible on a registered sample.
4. `Q3_MATCHPLAN_MECHANICS`: every hard plan passes exact mass accounting,
   anatomy/support masks, binary transport, and zero dustbin-to-dustbin mass;
   global objective is never below greedy on the same utilities.
5. `Q4_REAL_SIGNAL`: primary persistent-edge F1 is at least `0.50`, three-event
   macro F1 is at least `0.50`, and the patient-bootstrap 95% lower bound for
   primary-minus-randomized persistent-edge F1 is greater than `0`.
6. `Q5_B4_STRUCTURE`: on every retained persistent row with at least two shared
   endpoints, a seeded zero-fixed-point derangement exists; input tensors,
   null sets, source multiset, allocation, token count/order, initialization,
   and optimizer contract are identical, while only persistent assignment and
   downstream relation values differ.
7. `Q6_FRESH_PROCESS_REPRODUCTION`: a second fresh process produces identical
   cohort, feature-ledger, prediction, sufficient-statistic, and verdict hashes.

`Q5` is a structural check only. It must not report a progression effect.

## Registered rescue

Exactly one rescue is allowed only when Q0-Q3 pass and Q4 fails due to inadequate
visual signal. The rescue replaces BiomedCLIP with a SHA-pinned RAD-DINO frozen
encoder while keeping the cohort, coordinate transform, identity geometry,
matcher/null settings, metrics, bootstrap seed, thresholds, and gate order
unchanged. The rescue must be declared before downloading weights. No seed,
threshold, crop, or cohort search is allowed.

## Output contract

Write to one fresh root under
`artifacts/real_qualification/chextemporal_mimic_matcher_v2/`:

- immutable protocol snapshot and SHA-256;
- command, argv, environment, GPU, package, source, and checkpoint hashes;
- selected-row and selected-image ledgers;
- coordinate audit and crop-feature ledger;
- per-row predictions/sufficient statistics;
- bootstrap replicate summary;
- gate-by-gate result with first-stop semantics;
- fresh-process comparison and final certificate.

The formal test remains sealed, formal claims remain false, and allocation 4161
is not used until this qualification is terminally green.
