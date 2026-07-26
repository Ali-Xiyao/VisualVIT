# R32 TIER-CXR-VLM Authority and Engineering Protocol v1

Date frozen: 2026-07-26

Evidence class: `NON_CONFIRMATORY_R32_AUTHORITY_ENGINEERING`

## Immutable lineage

- Branch starts from R31 closure commit `7c4c51e`.
- R31 remains `PASS_R31_SCIENTIFIC_GO_REPRODUCED` on fresh silver.
- R26 human-gold `STOP_C1` remains unchanged.
- No R24-R31 active patient may enter R32.

## Eligible patients and labels

The only eligible silver patients are the 2,383 `sealed_reserve` patients in
the frozen R31 cohort. Rejoin those patient IDs to the pinned CheXTemporal
silver findings at revision
`81fd9cdd9b1208d8f8bd39d7a914c9b72fed8d79`; retain MIMIC rows with labels
`Stable`, `Improved`, `Worse`, `New`, or `Resolved`.

Before splitting, exclude every source-qualified patient ID in the R32 gold
quarantine. Gold outcome fields are forbidden; only ID/source columns may be
used for quarantine.

## Frozen split

Sort eligible patient IDs by
`SHA256("r32-tier-patient-v1|" + patient_id)` and assign:

- first 1,600 patients: `train`;
- next 300 patients: `dev`;
- final 483 patients: `sealed_vlm_test`.

All eligible finding rows for a patient follow the patient split. No
outcome-dependent balancing or reseeding is allowed. R32 GO requires every
label to have at least 100 patients in train and at least 25 patients in each
of dev and sealed test. These thresholds were frozen before the split audit.

The public R32 cohort artifact contains labels only for train/dev. Sealed-test
labels are written once to a separate local runtime artifact and must not be
read by R33 code.

## R33 boundary

R33 uses only persistent-label (`Stable`, `Improved`, `Worse`) train/dev rows.
Five patient-disjoint folds are assigned by
`SHA256("r33-oof-fold-v1|" + patient_id) mod 5`.
Routes on training rows must be OOF. The 483-patient sealed test remains
unread unless every R33 GO requirement passes.

## Token interface

Every bundle has exactly 64 physical positions:

- 0-3 query/control;
- 4-15 current state;
- 16-31 global transition;
- 32-47 local transition;
- 48-59 relation/context;
- 60-63 reserved neutral.

Robust and rich bundles share token count, order, token types, projector,
prompt, samples, and trainable parameter budget. Probe labels, logits, label
IDs, and label text are forbidden from token content. Every physical
attention value is one; invalid logical slots use the same neutral embedding.

## Models and compute

- Vision encoder: frozen local BiomedCLIP ViT-B/16.
- Primary VLM: frozen local Qwen3-VL-4B-Instruct.
- Seeds: 17, 29, 43.
- Primary GPU: GPU 0 only. GPU 1 is out of scope while occupied by another
  process.

## Lightweight provenance

The pinned source identifiers above are authoritative. Per user instruction,
large unchanged files are not repeatedly hashed. A protocol, cohort, and
feature-cache identifier is computed once when each artifact is first frozen;
ordinary iteration uses schema, count, disjointness, existence, and smoke
checks.

## R32 GO

All of the following are required:

1. exact 1,600/300/483 patient split with zero patient/study/image overlap;
2. five-label support thresholds pass;
3. all referenced images exist;
4. gold quarantine excludes all registered gold IDs and the access log shows
   no outcome or metric access;
5. exact-64 Qwen injection smoke passes with VLM and vision encoder frozen;
6. vectorized five-candidate scoring matches serial scoring within
   `atol=rtol=1e-6`;
7. R32 focused and regression tests pass;
8. no formal test prediction or gold prediction is generated.

Failure stops before R33.
