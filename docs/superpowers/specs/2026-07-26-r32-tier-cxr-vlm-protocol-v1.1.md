# R32 TIER-CXR-VLM Authority and Engineering Protocol v1.1

Date frozen: 2026-07-26

Evidence class: `NON_CONFIRMATORY_R32_AUTHORITY_ENGINEERING`

## Registered authority correction

Protocol v1 attempted the proposal's literal 1,600/300/483 split after gold
quarantine. The pre-model ID-only audit found that 26 of the 2,383 R31 reserve
patients are members of the 500-patient Chest ImaGenome gold registry. No gold
outcome, silver model outcome, sealed-test metric, or prediction was read.

The proposal simultaneously requires all gold patients to be excluded. These
two requirements cannot both hold with 2,383 active patients. Version 1.1
therefore makes the smallest authority-preserving correction:

- retain the complete 2,383-patient R31 reserve as the master authority set;
- mark the 26 Chest ImaGenome gold patients as quarantined and unusable;
- split the remaining 2,357 patients into 1,574 train, 300 dev, and 483 sealed
  VLM test patients.

Dev and sealed-test sizes are unchanged. No outcome-dependent balancing,
replacement patient, or new data source is introduced.

## Immutable lineage

- Branch starts from R31 closure commit `7c4c51e`.
- R31 remains `PASS_R31_SCIENTIFIC_GO_REPRODUCED` on fresh silver.
- R26 human-gold `STOP_C1` remains unchanged.
- No R24-R31 active patient may enter R32.

## Eligible rows

Rejoin the 2,383 reserve IDs to CheXTemporal silver findings revision
`81fd9cdd9b1208d8f8bd39d7a914c9b72fed8d79`; retain MIMIC rows labeled
`Stable`, `Improved`, `Worse`, `New`, or `Resolved`. Exclude the 26
quarantined gold patients before split assignment.

## Frozen split

Sort the remaining 2,357 IDs by
`SHA256("r32-tier-patient-v1|" + patient_id)` and assign:

- first 1,574: `train`;
- next 300: `dev`;
- final 483: `sealed_vlm_test`.

All rows for one patient remain in one split. R32 GO requires every label to
have at least 100 patients in train and at least 25 patients in each of dev
and sealed test. The public artifact carries train/dev labels only; test labels
are written once to a separate local sealed artifact.

## R33 boundary

R33 uses only persistent-label (`Stable`, `Improved`, `Worse`) train/dev rows.
Five patient-disjoint folds are assigned without labels. Every training route
must be OOF. R33 code is forbidden to open either sealed-test artifact.

## Fixed token and model interface

Every robust/rich bundle has the same 64 physical positions: 4 query/control,
12 state, 16 global transition, 16 local transition, 12 relation/context, and
4 reserved neutral. Token type/order, projector, prompt, sample set, trainable
budget, and physical attention are matched. Probe labels/logits and label
names/IDs are forbidden from token content.

The vision encoder is frozen BiomedCLIP ViT-B/16. The VLM is frozen
Qwen3-VL-4B-Instruct. Seeds are 17, 29, and 43. GPU 0 is the only authorized
GPU while GPU 1 is occupied by an unrelated process.

## Lightweight provenance

Large unchanged sources are not repeatedly hashed. A protocol, cohort, and
feature-cache identifier is computed once at freeze. Iteration uses schema,
count, disjointness, path, and smoke checks.

## R32 GO

1. master authority count 2,383; quarantined 26; eligible split exactly
   1,574/300/483;
2. zero cross-split patient/study/image overlap and zero gold overlap;
3. frozen five-label patient-support thresholds pass;
4. all image paths exist and data governance passes;
5. Qwen exact-64 smoke and BiomedCLIP frozen audit pass;
6. vectorized candidate scoring matches serial within `atol=rtol=1e-6`;
7. focused/regression tests pass;
8. no formal test or gold prediction is generated.

Failure stops before R33.
