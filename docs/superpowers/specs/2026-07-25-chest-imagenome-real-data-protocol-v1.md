# Chest ImaGenome–MIMIC Real-Data Matcher Qualification v1 (R25+)

Status: `PRE_FREEZE_DESIGN_CANDIDATE`
Evidence class: `NON_CONFIRMATORY_REAL_DATA_QUALIFICATION`
Formal claim allowed: `false`
Training: `none`
Direct base: R24 frozen synthetic engineering + CheXTemporal-MIMIC matcher qualification v3.

## Purpose and scope

This protocol asks one narrow question before any real progression training,
formal B4 claim, or retained-allocation GPU experiment: can the frozen CAPES-CI
partial-assignment implementation consume Chest ImaGenome gold per-bbox
longitudinal annotations joined to local MIMIC-CXR-JPG metadata, derive a
**three-label persistent progression oracle** (stable / improved / worse), and
recover case-local expert correspondence above a within-pair randomized control
on a cohort materially larger than the R24 v3 34-patient / 148-pair cohort?

The read-only cohort pre-audit (`scripts/audit_r25_cohort_precheck.py`,
2026-07-25 session 3) confirmed that the five-label endpoint (with `new` /
`resolved` birth/death labels) is **infeasible** on Chest ImaGenome: all
attribute-like files cover only the 284 *previous* (1st-study) images and zero
cover the 284 *current* (2nd-study) images, so per-image attribute
presence/absence cannot derive birth/death. The three-label persistent endpoint
is therefore the **primary** endpoint (not a fallback), matching R24 v3.

It does **not** test clinical benefit, a formal entity-level B4 causal claim,
frozen-VLM transfer, or any Phase II outcome. The R24 v3 strict persistent B4
contrast on 22 patients gave `+7.25 pp`, 95% CI `[-0.47, +16.92]` —
underpowered and crossing zero. R25+ targets a larger identifiable
persistent-entity cohort so that the same `Delta_bind` estimand can be
re-estimated with a tighter patient-cluster bootstrap interval. A positive
result here unlocks only the next survival gate (frozen-VLM transfer on
retained allocation `4161`); it does not unseal the formal test, does not
authorize a clinical claim, and does not by itself establish the formal CAPES
identity-binding causal estimand.

## Prerequisite authority

Real-data access under this protocol is authorized only by the completed
no-retry R24 double-CPU transaction and the terminally green R24 real
CheXTemporal-MIMIC matcher v3 certificate. The runner must validate these
exact artifacts before creating an output root:

- frozen R24 protocol SHA-256:
  `2f8b1577d193bf6a63d5146853ffd2b5fdc70918b6937652ff2cef47d8cc8e44`;
- R24 parent certificate SHA-256:
  `e96629b24d4a7caf6239c0a48fe995649f04bbbc61ae5b1ec5e264c1d0a01d0c`;
- R24 scheduled launcher result SHA-256:
  `4ab514b54b352a7f9206f9ebe7f43247a0fcfdf6c79f54a78adf5cc48228ea05`;
- R24 real CheXTemporal-MIMIC v3 protocol SHA-256:
  `638c7d130fa56cd789098f9da8374a2a56075a0b63ef92357ef6bfce277ba4d9`;
- R24 real v3 Q6 certificate SHA-256:
  `9f30b990c0ad4c6e8c50895a3a98e5c087143c9bf288c7cf1911aac42bc66fba`.

Any drift or non-green field relocks model access. R24 must not be retrofitted;
R25+ uses a fresh output namespace and fresh credential/claim paths.

## Frozen inputs

### Chest ImaGenome v1.0.0 (PhysioNet Credentialed Health Data License 1.5.0)

Extracted root:
`F:\VisualVIT_runtime\050_routeC\data\chest_imagenome\chest-imagenome-dataset-1.0.0\`.

Source zip SHA-256:
`D5D292379D9C5B1C9061F5373821CEEC7B769FB00931877509879EEA0E3BB033`
(1,553,519,249 bytes; integrity 57/57 OK against in-package `SHA256SUMS.txt`).

License: **PhysioNet Credentialed Health Data License 1.5.0** (NOT CC BY 4.0).
Annotations and metadata only — no parent images. Licensee must not re-identify,
must not share access, must keep HIPAA / human-subject training current, and
obligations survive termination. Parent MIMIC-CXR-JPG images require separate
PhysioNet credentialed access under the user's existing credentialed account.
This document does not certify CITI, a PhysioNet project DUA, or redistribution
rights beyond the user's existing credentialed access.

Pinned gold inputs (per-bbox longitudinal annotations):

| File | Bytes | SHA-256 |
|---|---:|---|
| `gold_dataset/gold_object_comparison_with_coordinates.txt` | 2,110,008 | `7efc6d779705aee0770f3c474baa3fc7cfd486333ad5c39717ad1ff9d95772b0` |
| `gold_dataset/gold_object_attribute_with_coordinates.txt` | 7,424,398 | `b6c72e55ef322d61a2a7feae1cbfd6b69ef3009258f0afb6d1e342e51a158262` |
| `gold_dataset/gold_bbox_scaling_factors_original_to_224x224.csv` | 78,860 | `8570f0f532e231205bd369d823e7072644b4fbd4f335ff4b908e3a0967698b86` |
| `gold_dataset/gold_attributes_relations_500pts_500studies1st.txt` | 8,735,969 | `5c1d07c3f990421dd88ea13c24a4eb1e6d34511230fde75dd175d2b66b655c01` |
| `gold_dataset/gold_comparison_relations_500pts_500studies2nd.txt` | 2,945,320 | `b7008b4cf9c39e2420ad813187a43e714feab82ce60150e1be6007d967682d8a` |

Pinned silver splits (patient-disjoint MIMIC-CXR partitioning; used for
cross-source leakage control and patient-disjoint fold construction, NOT as
training data):

| File | Bytes | SHA-256 |
|---|---:|---|
| `silver_dataset/splits/train.csv` | 25,200,130 | `5d99b3b598bca65208bd445932618d1f888026b1a80bd3675330b188e42c1190` |
| `silver_dataset/splits/valid.csv` | 3,605,841 | `2f8a874ec158aad595dfd07e8391ddba8d0aa2a9f1bd7650a9e566ba820e6bd4` |
| `silver_dataset/splits/test.csv` | 7,145,281 | `3682ca030432c33f189a1d9ad96a126b30531c708b40cf704674bda255f99c3f` |
| `silver_dataset/splits/images_to_avoid.csv` | 558,127 | `a7c13c8385887104df6de626f54091bd693d47ee7cb1b61f33081bc60368b010` |

Pinned semantics (closed vocabularies for label/entity alignment):

| File | Bytes | SHA-256 |
|---|---:|---|
| `semantics/comparison_relations_v1.txt` | 74 | `cb3f9fff758f4f8a51778ef45558ade27824ae241008ec0a3b9ae7e6fb6bba18` |
| `semantics/attribute_relations_v1.txt` | 3,233 | `05d4ac0ae0f42ef2e5a1b29fc9b7ea2566583dfc025360384f4ec4451c57aef6` |
| `semantics/objects_detectable_by_bbox_pipeline_v1.txt` | 660 | `e84d70cf39f02c030b0878933e716f088964b6da8b413b41422a666302d7377b` |
| `semantics/label_to_UMLS_mapping.json` | 165,547 | `0f2ed069ed95335fa676921989cba7dbf45d48203a9f20a657835fd7a275ba15` |
| `LICENSE.txt` | 2,518 | `30492d35caacc57d31754ce490e806110abee5d55effac7ddc460de4191ac773` |
| `SHA256SUMS.txt` | 7,028 | `df13e5da4f141a4509cee15af425187dd65cb457650cc37738db7c7502f559d5` |

### MIMIC-CXR metadata (re-qualified from R24 v3)

- MIMIC metadata: 16,546,905 bytes, SHA-256
  `6a3748ce77724c0dfe7d2def8f47643e989e3bbf0795bc13b89c1578e1649d6b`.
- MIMIC split: 12,198,758 bytes, SHA-256
  `515997bd6649045d7443d60c59a4ce9f6cca6c478871b8f2fb13454462bedb2f`.
- BiomedCLIP ViT-B/16 checkpoint: 343,241,699 bytes, SHA-256
  `3be6f957b2fc8b8324cc6ed6faebdcb218511b41fc0f542312e21850424a2590`
  (byte-identical on local and server).

The exact selected-image SHA-256 ledger is materialized before feature
extraction. Any declared input hash drift is terminal.

## Chest ImaGenome gold schema (verified)

`gold_object_comparison_with_coordinates.txt` (3,921 rows, tab-separated):
`patient_id`, `relationship_id`, `subject_id`, `object_id`, `bbox`,
`comparison`, `attribute`, `sentence`, `bbox_coord_224_subject`,
`bbox_coord_224_object`, `bbox_coord_original_subject`,
`bbox_coord_original_object`, `label_name`, `current_image_id`,
`previous_image_id`.

- `current_image_id` / `previous_image_id` are MIMIC `dicom_id` values →
  direct join key to MIMIC-CXR metadata.
- `comparison` ∈ {`no change`, `improved`, `worsened`} (closed per
  `comparison_relations_v1.txt`) → maps to {`stable`, `improved`, `worse`}.
- `subject_id` / `object_id` encode anatomy (e.g. `..._aortic arch`) →
  entity identity. The anatomy suffix is the coarse compatibility key used by
  the learned matcher; the full `label_name` is oracle-only.
- `bbox_coord_224_*` columns already provide 224×224-normalized boxes. The
  `gold_bbox_scaling_factors_original_to_224x224.csv` file provides the
  per-image ratio for integrity verification, not for runtime transform.

`gold_object_attribute_with_coordinates.txt` (15,688 rows) provides per-image
entity presence. The pre-audit confirmed that these attribute annotations cover
**only the 284 previous (1st-study) images** — zero current (2nd-study) images
have attribute rows. Therefore `new` / `resolved` (birth / death) labels cannot
be derived from set-level presence/absence across the pair: one side of every
pair is missing attribute coverage. The five-label endpoint is infeasible on
this data source; R25 uses the three-label persistent endpoint exclusively.

## Three-label persistent oracle derivation (pre-audit refined)

### Pre-audit finding: five-label endpoint is INFEASIBLE on Chest ImaGenome

The read-only cohort pre-audit (`scripts/audit_r25_cohort_precheck.py`,
2026-07-25 session 3) confirmed that all three Chest ImaGenome attribute-like
files cover only the 284 **previous** (1st-study) images. **ZERO** cover the
284 **current** (2nd-study) images. Chest ImaGenome annotates one study per
patient with object-attribute relations; the comparison is to a follow-up study
with **no attribute annotations**. Therefore `new` / `resolved` (birth / death)
cannot be derived from per-image attribute presence/absence — one side of every
pair is missing. The five-label endpoint is dropped (infeasible on this data
source, not a "fallback"). A five-label endpoint would require MS-CXR-T
(blocked by DUA) or CheXTemporal (R24 v3 already used at 22 patients).

### Three-label persistent derivation (from `gold_object_comparison_with_coordinates.txt`)

Map Chest ImaGenome comparison relations to the project's three-label
persistent progression target (Stable / Improved / Worse) at the per-bbox
entity unit:

1. `comparison == "no change"` → `Stable`
2. `comparison == "improved"` → `Improved`
3. `comparison == "worsened"` → `Worse`

The entity is present on both sides (same anatomy + `label_name`). The
`comparison` vocabulary is closed per `comparison_relations_v1.txt`
({`no change`, `improved`, `worsened`}).

### Entity unit and ordering

- **Entity unit**: `anatomy` (one of the 29 closed
  `objects_detectable_by_bbox_pipeline_v1.txt` zones) is the operational
  identity. When multiple bboxes of the same anatomy exist in one image,
  they are ordered by a deterministic key `(y1, x1)` (top→bottom, left→right)
  and matched by set membership; the learned matcher never sees the ordering.
- **No lesion-level claim**: Chest ImaGenome provides anatomically anchored
  observation instances, not lesion tracks. The protocol's operational entity
  is "anatomically anchored observation instance", matching the R24 v3
  boundary. A lesion-level claim requires an explicit track ID that Chest
  ImaGenome does not provide.
- The learned matcher sees only **coarse anatomy compatibility** (one of the
  36 zones), never the fine `label_name` (e.g. "tortuous aorta"). Fine entity
  identity is oracle-only and audit-only. This is the R24 identifiability
  lesson: the learned support must not leak fine entity IDs.

## Coordinate contract

Chest ImaGenome gold files already contain both `bbox_coord_224_*` and
`bbox_coord_original_*`. R25 uses the pre-computed 224×224 coordinates
directly, but verifies each box against the per-image scaling factor:

1. For each `current_image_id` / `previous_image_id`, look up
   `image_id` (with `.dcm` suffix) in
   `gold_bbox_scaling_factors_original_to_224x224.csv` to recover `ratio`.
2. Assert `bbox_coord_224 ≈ bbox_coord_original * ratio` within a
   floating-point epsilon (`1e-4`). Any box failing this check is terminal.
3. Mapped boxes must satisfy `0 <= x1 < x2 <= 224` and `0 <= y1 < y2 <= 224`
   after epsilon tolerance at the closed upper edge. Any nonpositive or
   out-of-frame box is terminal; silent clipping is forbidden.
4. Crop bounds use deterministic outward rounding (`floor` lower coordinates,
   `ceil` upper coordinates) after validation.

This differs from the R24 v3 CheXTemporal transform (short-side-1024 canvas).
The two transforms must not be mixed. A fixture with a known Chest ImaGenome
box must test this verification path.

## Fail-closed cohort

Use only Chest ImaGenome gold rows satisfying all conditions:

1. both `current_image_id` and `previous_image_id` resolve in official MIMIC
   metadata and split;
2. both images belong to official MIMIC `train`, to prevent accidental access
   to an official validation/test image;
3. `patient_id` and `study_id` agree with MIMIC metadata for both images;
4. prior time is strictly earlier than current time (MIMIC `StudyDate` then
   `StudyTime`);
5. prior and current `ViewPosition` are identical and in `{AP, PA}`;
6. both local derivative images exist (224×224 MIMIC-CXR-JPG derivatives
   already qualified in R24 v3);
7. the full `patient_id / study-pair / anatomy` key has exactly one
   progression target — conflicting comparison rows for the same anatomy in
   the same pair are excluded;
8. Box labels (anatomy) are unique within each image side, or the row is
   reduced to the deterministic ordered set;
9. the entity (anatomy + `label_name`) is present on both sides (persistent
   endpoint only — birth/death endpoints are infeasible on this data source
   and are not derived);
10. the row's `comparison` value is in the closed vocabulary {`no change`,
    `improved`, `worsened`} and maps to exactly one of {`Stable`, `Improved`,
    `Worse`};
11. **cross-source leakage exclusion**: the `patient_id` is not present in the
    R24 CheXTemporal-MIMIC v3 cohort (34 patients) or the R24 real progression
    pilot cohort (70 patients), and the `dicom_id` is not in Chest ImaGenome
    `silver_dataset/splits/images_to_avoid.csv`. This prevents any
    train/evaluation contamination between R24 and R25;
12. **three-label coverage gate**: the retained cohort must represent all three
    persistent labels (`Stable` / `Improved` / `Worse`) with at least a
    pre-registered minimum count per label (default `>= 10` patients per
    label). The pre-audit confirmed this gate is met: Stable=122 patients,
    Improved=45, Worse=72 (all exceed the 10-patient minimum). If any label
    were underrepresented, the protocol would declare the cohort underpowered
    and record a pre-registered stop, not a post-hoc decision.

### Pre-audit cohort counts (read-only, 2026-07-25 session 3)

The pre-audit (`scripts/audit_r25_cohort_precheck.py`) on the actual Chest
ImaGenome gold files + MIMIC metadata produced:

- **189 patients, 189 temporal pairs, 795 persistent rows** — exceeds the Q7
  target of 100 patients (margin +89).
- Persistent label coverage: Stable=371 rows/122 patients, Improved=162/45,
  Worse=262/72. All three persistent labels meet the `>= 10`-patient gate.
- Filter rejections: view_mismatch=1065, duplicate_target=1577,
  target_conflict=223, not_train_split=68, not_chronological=187,
  unknown_comparison=5 (multi-label `no change;;worsened` rows).

Count drift is terminal until explained without reading model outputs.

## Frozen feature and matcher variants

All image crops use the same frozen BiomedCLIP preprocessing and checkpoint
as R24 v3. The crop rectangle is exact, with no label-dependent expansion.
Features are finite float32 vectors.

The CAPES-CI matcher receives two leading zero state/query channels followed
by declared identity views, identical to R24 v3:

- `visual_only`: normalized crop embedding;
- `geometry_only`: normalized `(cx, cy, width, height)` in the 224 frame;
- `visual_geometry_equal`: the two disjoint identity views with fixed equal
  simplex weights (primary variant).

No annotation, Box label, progression label, match count, or oracle
cardinality enters the matcher. Hard inference uses the registered global
Hungarian solver. The learned matcher sees only **coarse anatomy
compatibility** (one of the 29 `objects_detectable_by_bbox_pipeline_v1.txt`
zones), never the fine `label_name` (e.g. "tortuous aorta"). Fine entity
identity is oracle-only and audit-only. This is the R24 identifiability
lesson: the learned support must not leak fine entity IDs.

## Gold and metrics

Within a row, equal expert anatomy labels on both sides define a persistent
edge. The labels are case-local and are never treated as globally persistent
lesion IDs. Birth/death endpoints are not derived (infeasible on this data
source).

Persist row-level sufficient statistics and aggregate:

- persistent edge precision, recall, F1, and exact row recovery;
- **three-label persistent macro F1** over {`Stable`, `Improved`, `Worse`};
- global assignment objective and hard-plan feasibility;
- prediction determinism under a second fresh process;
- global-vs-greedy objective dominance;
- primary-minus-within-row-randomized differences.

The randomized comparison is evaluated only on rows with at least two shared
endpoints. It uses the registered `anatomy_compatible_derangement` with seed
`20260725`, requires zero fixed persistent edges, and preserves the exact
persistent label sets. Absolute primary metrics use the full qualified cohort.

Uncertainty uses a patient-cluster nonparametric bootstrap with seed `20260725`
and 10,000 replicates. Each replicate samples patients with replacement and
includes all their rows. Report percentile 95% confidence intervals and the
effective unique-patient count. No row-level iid interval may be called the
primary interval.

## Qualification gates

Evaluate in this order and stop at the first failure:

1. `Q0_ASSET_LINEAGE`: all frozen Chest ImaGenome / MIMIC / BiomedCLIP hashes,
   image paths, IDs, official splits, license/access boundaries, and the R24
   prerequisite hashes are recorded and match.
2. `Q1_COHORT_GEOMETRY`: exact cohort counts are reproduced (target: 189
   patients / 189 pairs / 795 persistent rows per pre-audit); every annotation
   and mapped box passes the scaling-factor verification; no same-time,
   cross-view, or cross-source-contaminated row survives; the three-label
   coverage gate is confirmed (Stable ≥ 10, Improved ≥ 10, Worse ≥ 10
   patients).
3. `Q2_FEATURE_INTEGRITY`: all crop features are finite, checkpoint-frozen,
   and reproducible on a registered sample (exact-zero repeat difference at
   the registered extraction batch size, matching the R24 v3 lesson).
4. `Q3_MATCHPLAN_MECHANICS`: every hard plan passes exact mass accounting,
   anatomy/support masks, binary transport, and zero dustbin-to-dustbin mass;
   global objective is never below greedy on the same utilities.
5. `Q4_REAL_SIGNAL`: primary persistent-edge F1 is at least `0.50`,
   three-label persistent macro F1 is at least `0.50`, and the
   patient-bootstrap 95% lower bound for primary-minus-randomized
   persistent-edge F1 is greater than `0`.
6. `Q5_B4_STRUCTURE`: on every retained persistent row with at least two
   shared endpoints, a seeded zero-fixed-point derangement exists; input
   tensors, null sets, source multiset, allocation, token count/order,
   initialization, and optimizer contract are identical, while only persistent
   assignment and downstream relation values differ. `Q5` is a structural
   check only and must not report a progression effect.
7. `Q6_FRESH_PROCESS_REPRODUCTION`: a second fresh process produces identical
   cohort, feature-ledger, prediction, sufficient-statistic, and verdict
   hashes.
8. `Q7_B4_POWER_ESTIMATE` (new vs R24 v3): on the strict persistent B4
   endpoint, report `Delta_bind = 100 * (F_B4b - F_B4a)` with patient-cluster
   bootstrap 95% CI. The gate passes if the CI lower bound is greater than
   `0` **and** the effective unique-patient count is at least `100`. If the
   cohort is smaller than 100 patients, the gate is recorded as
   `UNDERPOWERED_NO_CLAIM` and the formal CAPES identity-binding claim remains
   locked; the result is still publishable as a non-confirmatory upper bound
   with an explicit power limitation statement.

`Q7` is the gate that R24 v3 could not pass (22 patients, CI crossed zero).
R25+ targets passing `Q7` by enlarging the cohort via Chest ImaGenome gold
(pre-audit: 189 patients, margin +89 over the 100-patient threshold). If
`Q7` still fails, the protocol honestly reports the negative result and does
not scale the same endpoint to a larger VLM merely to obtain more compute.

## Registered rescue

Exactly one rescue is allowed only when Q0-Q3 pass and Q4 fails due to
inadequate visual signal. The rescue replaces BiomedCLIP with a SHA-pinned
RAD-DINO frozen encoder while keeping the cohort, coordinate verification,
identity geometry, matcher/null settings, metrics, bootstrap seed, thresholds,
and gate order unchanged. The rescue must be declared before downloading
weights. No seed, threshold, crop, or cohort search is allowed.

## Output contract

Write to one fresh root under
`artifacts/real_qualification/chest_imagenome_mimic_matcher_v1/`:

- immutable protocol snapshot and SHA-256;
- command, argv, environment, GPU, package, source, and checkpoint hashes;
- selected-row and selected-image ledgers (with cross-source exclusion audit);
- coordinate verification audit and crop-feature ledger;
- three-label persistent derivation audit (per-row `comparison` →
  {`Stable`,`Improved`,`Worse`} mapping + anatomy presence on both sides);
- per-row predictions / sufficient statistics;
- bootstrap replicate summary;
- gate-by-gate result with first-stop semantics;
- fresh-process comparison and final certificate.

The formal test remains sealed, formal claims remain false, and allocation
`4161` is not used until this qualification is terminally green and `Q7`
passes.

## Boundary and non-actions

- R24 frozen artifacts and protocol markdown are not modified.
- R24 real CheXTemporal-MIMIC v3 cohort is not reused; the R25 cohort is
  constructed fresh from Chest ImaGenome gold with cross-source exclusion.
- Formal test reveal, formal entity-level B4 causal claim, Phase II transfer,
  and allocation `4161` GPU execution remain locked until `Q7` passes.
- No model or dataset download is authorized beyond the already-ingested Chest
  ImaGenome v1.0.0 and the local BiomedCLIP checkpoint; the RAD-DINO rescue
  download is conditional on Q4 failure and must be declared first.
- Silver dataset `study_level_attribute_rdfgraphs.json` (4.6 GB) and
  `scene_graph.zip` (1.0 GB) are NOT used in this protocol; only the gold
  per-bbox annotations and the silver patient-disjoint splits are consumed.

## Resolved design questions (pre-audit, 2026-07-25 session 3)

The five open design questions have been resolved by the read-only cohort
pre-audit (`scripts/audit_r25_cohort_precheck.py`). They are recorded here as
frozen decisions, not open questions:

1. **Anatomy deduplication** — RESOLVED: order by `(y1, x1)` and treat as a
   set; the learned matcher matches by coarse anatomy compatibility, not by
   slot index. Confirmed feasible; anatomy vocabulary = 36 zones in the gold
   data (29 in the closed `objects_detectable_by_bbox_pipeline_v1.txt`).
2. **New/resolved derivation granularity** — MOOT: Chest ImaGenome's annotation
   structure (attribute files cover only previous images, zero current images)
   makes `new`/`resolved` infeasible regardless of granularity. The
   three-label persistent endpoint is the primary endpoint; five-label is
   dropped, not fallback.
3. **Patient-disjoint fold construction** — RESOLVED: fresh 5-fold on the 189
   gold patients with seed `20260725`; assert no `dicom_id` overlap with
   silver `test.csv` to keep the formal test sealed.
4. **Cohort size ceiling** — RESOLVED: 189 patients after fail-closed
   filtering (pre-audit). Q7 (≥ 100 patients) is achievable with margin +89.
   No further power analysis is needed before freeze; the pre-audit counts are
   the frozen cohort targets.
5. **R25 re-freeze of `test_query_anchor_r4_runner.py:274`** — RESOLVED:
   failure #2 (`dry_run_authorized` truthy-vs-`is False` mismatch) and
   failure #1 (r16 frozen-validator bundle regeneration) are bundled into R25
   re-freeze. The test edit (`dry_run_authorized is False`) and the r16 bundle
   regeneration must be recorded as a separate
   `freeze_record_runner_tests_sha256_exact` bump and a fresh
   `frozen_validator_dependency_bundle` directory, not silent changes.

## Next step

The PRE_FREEZE design review is complete: the five open design questions are
resolved by the pre-audit, and the three-label persistent endpoint is frozen
as the primary endpoint. The next actions are:

1. Implement the R25 qualification runner, real-qualification module
   extension, independent verifier, and focused tests as a new namespace
   (not modifying R24 frozen source). The runner must validate the R24
   prerequisite hashes and the pre-audit cohort counts (189 patients / 189
   pairs / 795 persistent rows) before creating an output root.
2. Align the two R25-bound pytest failures alongside the R25 implementation:
   - `test_query_anchor_r4_runner.py:274`: change `dry_run_authorized`
     (truthy) to `dry_run_authorized is False` (matching production semantics
     for post-dry-run frozen state);
   - regenerate `.tmp/r16_frozen_r14_validation_bundle.py` +
     `.tmp/r16_frozen_r14_validator_bundle_v5/` via the R16 finalizer under
     R25 authority (the R14-era source bytes are unrecoverable without a
     fresh finalizer run; copying current R24 source would be inauthentic).
3. Freeze R25 protocol/registry, pass focused + relevant suite (target:
   444/444 with the two R25-bound fixes), run three independent Gate-0
   processes.
4. Only after Gate-0 is green, execute the no-retry sequential R25
   qualification transaction (process A → Q6 fresh-process reproduction →
   Q7 power estimate).

Until then, no R25 output root, training, formal-data access beyond the
already-ingested annotations, model download, GPU/Slurm step, or allocation
`4161` use is authorized.
