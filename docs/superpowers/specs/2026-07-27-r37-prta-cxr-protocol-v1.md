# R37 PRTA-CXR Protocol v1

Date frozen: 2026-07-27

Branch: `codex/r37-prior-responsive-temporal-adapter`

Parent commit: `85f3951`

## 1. Scientific status

R31 is retained as a valid but non-transferable discovery result. R33 and
R33A falsify the frozen-final-layer-cache token-routing premise. No further
route, threshold, bridge-width, projection-seed, expert-vote, coverage, or
64-token-allocation search is allowed on the R33A cohort.

R37 tests a distinct premise:

> Intermediate BiomedCLIP patch representations can be adapted to encode
> directional, correct-prior-responsive change while preserving current-image
> medical state.

R37 representation qualification precedes any fixed-64-token survival test or
frozen-VLM transfer.

## 2. Protected outcome firewall

The following outcomes remain unavailable:

- the 300-patient R32 development partition;
- the 483-patient R32 sealed VLM test partition;
- every CheXTemporal and Chest ImaGenome gold outcome;
- every downstream R38/R39 outcome until its preceding gate passes.

R37A may read only structural identifiers needed for exclusion. It must not
open `sealed_vlm_test_labels.json`. The mixed R32 train/dev artifact may be
projected to `patient_id` and `partition` only; progression fields must never be
returned, logged, summarized, or used by R37.

For a conservative independence boundary, the R37 source pool excludes all R32
train, dev, and sealed-test patients, plus every frozen gold-quarantine patient.
Thus none of the old 1,574 R33A training patients can re-enter under
report-derived supervision.

## 3. Authorized source assets

R37A uses locally authorized MIMIC-CXR assets:

- official MIMIC-CXR-JPG metadata and split tables;
- official MIMIC-CXR reports;
- official MIMIC-CXR-JPG frontal images;
- MIMIC-CXR-JPG CheXpert study labels as a consistency signal;
- Chest ImaGenome relations only where the existing DUA and patient firewall
  permit their use.

CheXTemporal silver is evaluation-only for this route and must not be used for
R37 training or calibration.

No source dataset is rehashed during iteration. Source paths, sizes, schemas,
row counts, frozen identifier projections, and targeted existence checks are
the active provenance boundary. New R37 artifacts receive one identifier when
they are frozen; cache shards are not individually hashed.

## 4. R37A cohort construction

### 4.1 Study selection

1. Use only patients assigned to the official MIMIC `train` split.
2. Exclude the complete forbidden-patient registry before reading reports or
   deriving transition supervision.
3. Retain frontal `PA` or `AP` images.
4. Select exactly one image per study, preferring `PA` over `AP`, then the
   lexicographically smallest DICOM ID.
5. Require the selected image and the study report to exist.
6. Sort studies by patient, study date, study time, study ID, and DICOM ID.
7. Pair consecutive eligible studies only.
8. Exclude same-date pairs and non-positive temporal intervals.
9. A pair may cross AP/PA view, but view is recorded and CMCP must match the
   current view.

### 4.2 Patient-disjoint internal split

Patients are assigned by the stable key
`sha256("r37-patient-split-v1|<subject_id>")`.

- hash integer modulo 10 equals zero: `internal_calibration`;
- remaining nine deciles: `pretrain`.

No patient, study, or image may occur across the two partitions.

### 4.3 Manifest schema

Each JSONL row contains:

- `pair_id`, `subject_id`, and `partition`;
- prior/current study, DICOM, date/time, view, image path, and report path;
- `interval_days`;
- source revision and official split;
- transition supervision records after Section 5 qualification.

The pretraining and internal-calibration manifests are written separately.
They contain no R32, sealed-test, or gold outcome.

## 5. Report-derived transition supervision

Reports supervise visual pretraining only and are never model inputs at
evaluation.

### 5.1 Five-class vocabulary

The frozen directional vocabulary is:

- `Stable`
- `Improved`
- `Worse`
- `New`
- `Resolved`

Finding aliases are frozen before the first adapter run. A transition sentence
is eligible only when the current report contains both a recognized finding
alias and an unambiguous temporal phrase in the same sentence or clause.

- `New`: new, newly developed, interval development, or newly seen.
- `Resolved`: resolved, resolution, no longer seen, cleared, or disappeared.
- `Improved`: improved, improving, decreased, decreasing, less, smaller, or
  resolving.
- `Worse`: worsened, worsening, increased, increasing, progressed, larger, or
  more prominent.
- `Stable`: unchanged, stable, similar, or no significant interval change.

Generic `persistent` or `remains` wording is not sufficient for a finding-level
Stable label because it frequently scopes to a neighboring device or finding.
Negated, question, indication, lateral size-comparison, or uncertainty-scoped
matches are rejected. Conflicting labels for the same finding in one current
report are rejected. New/Resolved examples are
cross-checked against available CheXpert prior/current state changes when the
finding maps to a CheXpert observation. Improved/Worse require an explicit
directional phrase and are not inferred from binary labels.

Before formal training, a deterministic stratified case-study sheet must
sample at least 40 rows per class (200 total) for human error categorization.
The extractor freezes only if at least 90% are directionally correct overall
and at least 85% are correct in each class. Otherwise R37 stops for extractor
revision; the adapter is not used to hide label noise.

### 5.2 Directional-support gate

R37A requires:

- at least 30,000 eligible longitudinal image pairs;
- all five classes present;
- at least 500 unique pretraining patients per dynamic class;
- at least 50 unique internal-calibration patients per dynamic class.

Failure is `STOP_R37A_DATA_SUPPORT`, not permission to reveal R32 outcomes.

## 6. Block-8 cache

The local BiomedCLIP ViT-B/16 visual trunk is loaded strictly from the frozen
150-key visual state dictionary.

- patch embedding, position embedding, and Blocks 1-8 are run in evaluation
  mode with gradients disabled;
- the cached tensor is the normalized input to Block 9 immediately after
  completing Block 8;
- expected per-image shape is `[197, 768]`;
- storage dtype is FP16;
- images are deduplicated by DICOM ID;
- a DICOM ID mapping to more than one path is fatal;
- non-finite tensors are fatal;
- the formal cache starts only after a fresh small smoke reproduces identical
  IDs and numerically equal tensors for a repeated batch.

The default formal cache root is
`H:\VisualVIT_runtime\050_routeD\r37_prta_cxr\r37_block8_token_cache`.

## 7. Current-Matched Counterfactual Prior

CMCP is constructed only after the Block-8 cache exists.

For every dynamic pair-finding row, candidates must:

- come from a different patient;
- have the same finding;
- have the same current view;
- have a different transition class;
- belong to the same R37 partition;
- never use a protected patient.

Candidate current images are ranked by cosine similarity between mean-pooled
Block-8 patch tokens after L2 normalization. The highest-similarity eligible
candidate is selected, with `pair_id` as the deterministic tie-breaker. The
selected counterfactual uses that candidate's prior with the target row's
current image.

The offline index may use the training transition label to ensure a
counterfactual direction, but the label and selection metadata are never model
inputs. R37A requires valid CMCP matches for at least 90% of dynamic rows in
both pretrain and internal-calibration partitions.

## 8. R37B model and ablations

Blocks 1-8 remain frozen. Base parameters in Blocks 9-12 remain frozen.
Trainable parameters are limited to low-rank adapters, query-conditioned
cross-time attention, state/transition readouts, and registered projection
heads.

The frozen comparison matrix is:

| ID | System |
|---|---|
| A0 | Frozen BiomedCLIP difference tokens |
| A1 | Frozen BioViL-T, only if an authorized compatible checkpoint is available |
| A2 | Naive temporal adapter |
| A3 | A2 plus transition text alignment |
| A4 | A3 plus temporal inversion |
| A5 | A3 plus CMCP |
| A6 | Full PRTA: CMCP, inversion, and static-state preservation |
| A7 | ProTrans, only if an authorized compatible weight or faithful reproduction is available |

A1/A7 unavailability must be reported as an availability boundary, not silently
replaced by a weaker model.

The A0 frozen difference feature is also fixed before evaluation: pass cached
Block-8 tokens through the unmodified frozen BiomedCLIP Blocks 9-12 and final
norm, subtract prior CLS from current CLS, and L2-normalize the 768-D delta.
The capacity-matched probe is a linear five-class classifier conditioned by the
same fixed 12-finding one-hot vector used by A1. Current-only replaces the prior
with the current image, and inversion swaps the pair order. No patch pooling,
adapter, or prompt-derived feature may be substituted after results are seen.

The now-available A1 implementation is frozen before outcome evaluation:

- official `microsoft/BiomedVLP-BioViL-T` image weights at Hub revision
  `692f09e9be1bfe5fdd5f3efdd0e1eca7d2c10b23`;
- official archived Microsoft HI-ML source at
  `b67c1d27c6b17d8e8ff01f8c507f3cabdb307388`;
- official grayscale resize-512/center-crop-448 preprocessing;
- current image passed as `current_image` and prior image as
  `previous_image`;
- the canonical normalized 128-D `projected_global_embedding`, not an
  invented reconstruction of BioViL-T tokens;
- a frozen-backbone linear five-class probe conditioned only by the same
  12-finding one-hot query used to enumerate the R37 transition rows.

The A1 feature cache is built once per transition-supervised pair and reused
across findings and seeds. It stores true-pair, current-only, and inverted
canonical embeddings so none of the three controls is re-encoded per seed. No
protected outcome is used to choose the representation or probe.

The full loss is:

`L_transition + lambda_c L_CMCP + lambda_i L_inversion + lambda_s L_state`.

Grounding is optional and cannot be introduced after R37B begins unless a new
protocol version is frozen before any protected outcome is read.

## 9. Internal qualification and unlocks

All thresholds, seeds, loss weights, probe capacity, and baseline code freeze
on R37 internal calibration only.

Patient-bootstrap intervals use 2,000 deterministic percentile replicates.
Patients, not individual finding rows, are sampled with replacement; every row
from a sampled patient is retained, including repeated copies when that patient
is drawn more than once. Training seeds are 17, 29, and 43. The frozen
bootstrap seed is 37001. The reported interval is the distribution of the mean
true-minus-control macro-F1 difference across the three seeds under the same
sampled patient clusters.

Internal GO requires:

1. true pair minus current-only macro F1 at least +2.0 pp, patient-bootstrap
   95% CI lower bound above zero, all three seeds positive;
2. true pair minus CMCP-prior macro F1 at least +2.0 pp with CI lower above
   zero;
3. temporal inversion consistency is measured as the fraction of reversed-pair
   predictions equal to the fixed inverse mapping
   `Stable->Stable`, `Improved<->Worse`, and `New<->Resolved`; every seed must
   reach at least 0.90;
4. current-state retention is the mean cosine similarity between the adapted
   state embedding and the frozen current-image embedding used by the
   preregistered state-preservation loss. Frozen BiomedCLIP defines 1.0, so
   "no more than 1.0 pp below" requires at least 0.99 in every seed;
5. a capacity-matched probe on PRTA transition tokens beats frozen BiomedCLIP
   difference tokens by at least +2.0 pp.

Only then may one frozen A0-A7 bundle reveal the 300-patient dev once in R37C.
R38 fixed-64 survival remains locked until R37C GO. R39 frozen-VLM transfer,
483 sealed test, and gold remain locked until their preceding gates pass.

## 10. Required R37A artifacts

- `r37_forbidden_patient_registry.json`
- `r37_pretrain_manifest.jsonl`
- `r37_internal_calibration_manifest.jsonl`
- `r37_transition_case_study.csv`
- `r37_counterfactual_prior_index.json`
- `r37_block8_token_cache/`
- `r37_data_audit.json`

R37A final status is one of:

- `GO_R37A_DATA_AND_CACHE`
- `STOP_R37A_DATA_SUPPORT`
- `STOP_R37A_TRANSITION_QUALITY`
- `STOP_R37A_CMCP_COVERAGE`
- `STOP_R37A_CACHE_REPRODUCIBILITY`
