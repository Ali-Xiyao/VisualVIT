# CAPES-CI Real Train/Dev Pilot Data Contract

Status: `DRAFT_LOCKED_BEFORE_D010`  
Formal test: `SEALED`  
Authority: CAPES-CI v1 method/interface specification and 2026-07-19 statistical protocol

## 1. Unit of analysis

The formal unit is a patient with an ordered prior/current chest-radiograph pair. The prediction unit is an eligible longitudinal entity within that pair. Each entity contributes at most one valid target among:

`stable`, `worse`, `improved`, `new`, `resolved`.

An entity may be an observation-instance anchored to an anatomical region. It is not assumed to be a manually tracked physical lesion unless the source annotation explicitly provides lesion identity.

## 2. Required tables

### `pairs`

- `source_dataset`, `source_version`, `source_revision`
- `pair_id`, `patient_key`
- `prior_study_key`, `current_study_key`
- `prior_image_key`, `current_image_key`
- `prior_time`, `current_time`, `interval_days`
- `split` in `train`, `method_dev`, `power_dev`, `formal_test`, `external_test`
- source-relative image paths and image SHA256 values
- `eligible`, `exclusion_reason`

### `observations`

- `pair_id`, `timepoint`, `observation_key`
- image-space bounding box or patch-support index
- `coarse_anatomy_id` used by the learned support mask
- `fine_anatomy_id` retained only for gold audit when permitted
- source observation/finding concept and annotation provenance
- confidence, validity and `images_to_avoid` state
- crop/feature artifact path, encoder revision and SHA256

### `entity_gold`

- `pair_id`, `gold_entity_key`
- prior/current observation keys, either nullable
- `is_persistent`, `is_birth`, `is_death`
- gold-link provenance and annotator/source confidence
- exact rule or official field that establishes the link

### `progression_labels`

- `pair_id`, `gold_entity_key`
- fixed integer/string label
- validity/uncertainty mask
- label provenance (`gold`, `official_silver`, `weak_report_derived`)
- source comparison relation and deterministic mapping version

### `asset_ledger`

- official URL, version/revision, license and access class
- credential/CITI/project-DUA state without credentials or tokens
- local/remote root, file count, bytes and manifest SHA256
- permitted uses and redistribution boundary

## 3. B4 identifiability requirements

A sample can enter the primary B4 estimand only when all conditions are true:

1. the persistent endpoint link is official gold or produced by a signed deterministic annotation rule independent of model predictions;
2. the learned path never receives `gold_entity_key`, gold cardinality, fine identity or target progression label;
3. the support mask uses a coarser compatibility group than the oracle identity;
4. at least two persistent endpoints are derangeable within a compatibility group, allowing an anatomy-compatible zero-fixed-point permutation;
5. B4a and B4b keep the identical observation multiset, null sets, allocator, token layout, prompt, model and training contract;
6. the target label is defined at the same entity unit as the endpoint assignment.

If exact identity is already deterministically exposed through the learned anatomy input, B4 is trivial and the sample is ineligible. If only one endpoint exists in every compatible group, a zero-fixed-point intervention is impossible and the sample is ineligible. Eligibility is computed before model training and cannot depend on observed effects.

## 4. Operational entity rule

The preferred feasible rule for scene-graph-style data is an observation instance anchored to a fine anatomical region. Persistent identity may be defined by the same normalized finding concept plus the same fine region across time; `new` and `resolved` arise from one-sided presence; `worse`, `improved` and `stable` require an official comparison relation or signed deterministic mapping.

For causal identification, CAPES-CI receives only image-derived features and a preregistered coarse anatomy compatibility group. Fine region/finding identity is oracle/audit-only. Report text, comparison text and target labels cannot enter the image-only learned path or allocator.

This operationalization must be downgraded from “lesion tracking” to “anatomically anchored observation identity” unless the source data explicitly contains lesion-level tracks.

## 5. Split and leakage rules

- split by normalized patient key before pairing or feature extraction;
- hash patient/study/image identities across all MIMIC-derived sources;
- an image or patient appearing in any training-derived source cannot enter internal/external test;
- exact and perceptual image duplicates are excluded across splits;
- `images_to_avoid` is a fail-closed exclusion before any feature cache;
- method-dev selects method/rescue settings; power-dev estimates variance and design; formal-test outcomes remain unreadable until signed freeze;
- silver or report-derived annotations train only under a declared weak-supervision branch and cannot be called gold evidence.

## 6. Feature contract

For each observation, store frozen image-derived region features, box/patch coordinates, confidence, coarse anatomy and stable source IDs. Encoder preprocessing, resize/crop policy, precision and checkpoint SHA256 are fixed. No report embedding, target label, oracle match count or oracle-derived top-K may enter the learned feature tensor or allocator.

## 7. Qualification gates

`D010 PASS` requires a complete asset ledger with legal/access state and zero missing/hash-mismatched required files.

`D020 PASS` requires:

- zero cross-split patient/study/image/hash overlap;
- zero `images_to_avoid` inclusions;
- nonempty five-label support at the primary entity unit;
- nonempty B4-eligible train/method-dev/power-dev cohorts;
- a sealed formal-test manifest hash;
- a written count of excluded non-derangeable cases and each exclusion reason.

If five-label entity targets and nontrivial oracle endpoint identity cannot coexist in one legally usable cohort, the confirmatory CAPES-CI claim is not identified. A three-label image-level benchmark remains secondary and cannot substitute for it.
