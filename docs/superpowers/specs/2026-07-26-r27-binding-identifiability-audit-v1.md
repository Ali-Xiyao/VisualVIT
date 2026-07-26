# R27 Binding Identifiability Audit Protocol v1

Status: `FROZEN_BEFORE_EXECUTION`

Date: 2026-07-26

Evidence class: `EXPLORATORY_POSTHOC_R27_MECHANISM_AUDIT`

## 1. Question and boundary

R26 C1 terminated at `STOP_C1`. R27 asks whether the small average
oracle-binding effect is associated with pair-level binding identifiability:

> Does B4b oracle minus B4a deranged progression macro F1 increase as the
> probability that a zero-fixed-point identity derangement changes progression
> semantics increases?

R27 is a read-only post-hoc audit. It cannot alter R26, retrain a model,
regenerate predictions, select a new confirmatory endpoint, or unlock R28+.

## 2. Frozen inputs

Runtime root:
`F:\VisualVIT_runtime\050_routeC\r26_c1_oracle_binding\run_v1`

Required SHA-256 pins:

| File | SHA-256 |
|---|---|
| `summary.json` | `2fbb63a5fb97d4be30a6c13daa8c91015cfa2450bd8026c4546540ee1df8e5c0` |
| `predictions.json` | `160f9c66e6009d3e2d45cb4a7b28e06d1e94b037c2112925a9d8af156be40613` |
| `bootstrap.json` | `2d8bf9a2bec80fcfba5cdd9cc02222772b9390d0b6836712cec882d8ae17202a` |
| `b4_isomorphism.json` | `b3390da9779d580f6605469b803863ae31b44f80885941afde3312c45020a139` |
| `folds.json` | `472ecbdaded2e2e980459c42a9cf6e8e7f854595d5e6f017d1d2b9be31b7ef2b` |
| `fit_audit.json` | `785d8a6ca71bb34d581d5b21d17e6a7e972a686a4827d35ca08f6834666c9cc2` |
| `cohort.json` | `71013a070cba1133512408b62d232c13440f343cbafe03aa27be4a7bb8d3fd03` |

Expected R26 terminal state:

- status `STOP_C1`;
- 170 patients / 170 pairs / 774 entities;
- systems `B4a_deranged`, `B4b_oracle`, `current_only`;
- training seeds 17, 29, 43;
- derangement ids 81001, 81002, 81003.

## 3. Assignment provenance

R26's frozen `b4_isomorphism.json` records pair-seed bases and proves
zero-fixed-point assignments, but it does not serialize assignment indices.
R27 therefore reconstructs the deterministic assignment defined by the frozen
R26 implementation:

1. ordered current boxes from frozen `cohort.json`;
2. `sha256(patient_id|prior_dicom_id|current_dicom_id)[:8] + derangement_id`;
3. Torch CPU `randperm` with the resulting seed and the R26 retry/roll rule.

This is labelled `DETERMINISTIC_RECONSTRUCTION`, not a directly serialized
assignment. Execution fails if the R26 runner or matching implementation
differs from frozen commit `8c2ea0b`, if pair-seed bases disagree, or if any
reconstructed assignment has a fixed point.

Frozen source SHA-256 pins:

| Source | SHA-256 |
|---|---|
| `scripts/run_r26_c1_oracle_binding.py` | `951e86bd6c4fc715e159f6a3aece07f8b58aca916a816adb7e5a84e907db28ba` |
| `src/visualvit/matching.py` | `6186fa380093e984430f8170439f447026a52dab9bdf847b2cc1edf2d02b23ec` |
| `src/visualvit/real_progression.py` | `ed9e7dc57d70f33e3eb781540a9036c248ecadc4d5ac038279ff554249b11078` |

No image, feature cache, model, optimizer, or prediction-generation function is
called.

## 4. Pair-level composition and BII

The independent cluster is one patient/pair. For pair \(i\) with \(n_i\)
entities and label counts \(n_{iy}\):

`BII_i = sum_y n_iy * (n_i - n_iy) / (n_i * (n_i - 1))`

This is the expected label-changing fraction over uniformly sampled
zero-fixed-point derangements. Also report natural-log label entropy,
homogeneity, number of distinct labels, and full label counts.

Frozen strata:

- `BII-0`: `BII == 0`
- `BII-Low`: `0 < BII <= 0.33`
- `BII-Mid`: `0.33 < BII <= 0.66`
- `BII-High`: `BII > 0.66`

## 5. Actual semantic-corruption audit

For every qualification entity and registered derangement, reconstruct the
selected current anatomy and compare its frozen progression label with the
target label. Report:

- label-changing rate overall and per patient/derangement;
- all 3×3 target-to-selected-label counts;
- zero-fixed-point count;
- label-preserving and label-changing support;
- per-anatomy counts and corruption rates.

LPD and LCD are audit classifications only:

- LPD: selected anatomy differs and selected label equals the target label;
- LCD: selected anatomy differs and selected label differs from the target.

R27 does not create a new LPD/LCD experimental prediction.

## 6. Stratified effects

Within each frozen BII stratum, compute:

- `B4b_oracle - B4a_deranged`;
- `B4b_oracle - current_only`;
- patient-balanced three-label macro F1 for each system;
- per-seed contrasts;
- per-label and per-anatomy support diagnostics.

The point estimator first computes each seed/derangement block, averages
derangements within seed, then averages seeds.

Uncertainty uses 10,000 patient-cluster bootstrap replicates with RNG seed
20260726. A bootstrap draw resamples patients with replacement and retains all
their entities, systems, seeds, and derangements together. Replicates lacking a
target label are invalid; report the valid fraction and require at least 0.95.

No entity-level IID bootstrap is permitted.

## 7. Support and interpretation gates

Minimum high-BII support for a non-sparse exploratory trend:

- at least 30 patients;
- at least 100 entities;
- all three labels represented by at least 10 patients.

Verdict order:

1. `C_SPARSE_HIGH_BII_SUPPORT` if high-BII support fails, regardless of effect.
2. `B_NO_HIGH_BII_GAIN` if supported high-BII B4b-B4a point estimate is
   non-positive or its 95% lower bound is not positive.
3. `A_MONOTONIC_SUPPORT` only if support passes, stratum point estimates are
   non-decreasing from BII-0 through High, high-BII effect is positive with
   lower bound above zero, and all three seed directions are positive.
4. Otherwise `INCONCLUSIVE_NONMONOTONIC`.

All verdicts retain `exploratory_only=true`, `formal_claim_allowed=false`, and
`r28_unlocked=false`.

## 8. Required outputs

Fresh output root only:

- `pair_label_composition.json`
- `derangement_semantic_audit.json`
- `bii_stratified_effects.json`
- `support_audit.json`
- `artifact_manifest.json`

Repository report:
`reports/R27_BINDING_IDENTIFIABILITY_AUDIT.md`

The manifest binds the protocol, input files, output files, source files,
arguments, environment, counts, gates, and terminal verdict.

## 9. Stop rules

- Any input/source/protocol hash mismatch stops before analysis.
- Any cohort/prediction layout mismatch stops before analysis.
- Any fixed point or missing anatomy label stops before effect analysis.
- Existing output files are never overwritten.
- R27 stops after its exploratory verdict. No R28, R29, TIER, RAD-DINO,
  learned matcher, frozen VLM, DIVE, or scale-up is authorized.
