# R30 Regularized Multiscale Transition Protocol v1

Date frozen: 2026-07-26

Evidence class: `NON_CONFIRMATORY_FRESH_SILVER_DEVELOPMENT`

## Motivation and selection disclosure

R29 stopped at its development gate without revealing its test. Its large MLP
heads memorized training rows, while a disclosed R29 train/dev capacity audit
showed that standardized, strongly regularized linear multiscale heads retained
signal without memorization. Full selection evidence is frozen in
`reports/R29_FAILURE_CASE_STUDY.md`.

R30 is an independent validation of that selected repair. No R29 test patient
and no R30 patient was used to select the representation, regularization,
projection dimension, seeds, crops, or gates.

## Data authority and cohort

- Parent source and input pins are inherited from R29 protocol v1.1.
- Eligible patients are only those assigned `sealed_reserve` by the frozen R29
  cohort SHA-256
  `0a52d2c84c99c9c3cdc91063b801eb3c0d1304dfa454c16e55c86edbd2197d6e`.
- Sort eligible patients by
  `SHA256("r30-patient-v1|" + patient_id)`.
- Assign the first 1,500 patients to train, next 400 to dev, next 600 to sealed
  test, and all others to sealed reserve.
- For active patients, sort records by
  `SHA256("r30-row-v1|" + record_id)` and retain at most 12.
- R29 train/dev/test patients, R24-MIMIC, R25, and R26 patients are forbidden.
- Labels remain `Stable`, `Improved`, and `Worse`.

## Image binding

Use the frozen R29 v1.1 per-image anatomy resolver:

- full-image global crop;
- exact anatomy union crop;
- exact crop expanded by 1.5 and clipped to 224-space;
- same-side pulmonary parent/landmark fallback when a fine box is absent;
- fallback and cross-time mapping differences audited.

Only image pixels and finding/anatomy query fields are allowed. Report
evidence, reasoning, scene-graph attributes, relationships, progression labels,
and test outcomes are forbidden model inputs.

## Systems and selected repair

The reference systems are the frozen R29 `state`, `global_transition`,
`local_transition`, and `uniform_fusion` heads with seeds 17, 29, and 43.

For `regularized_multiscale`:

1. L2-normalize prior/current frozen BiomedCLIP ViT-B features separately at
   global, exact, and expanded-context scale.
2. At each scale concatenate prior, current, signed delta, absolute delta, and
   elementwise product.
3. Project each scale independently to 128 dimensions using a signed random
   projection with seed `20260800 + training_seed + scale_index`, where scale
   indices are 0, 1, and 2.
4. Concatenate the three projected scale blocks, the unprojected
   finding/anatomy one-hot query, and the 18 frozen geometry/view fields.
5. Fit `StandardScaler` on training rows only.
6. Fit multinomial `LogisticRegression(C=0.001, max_iter=2000)` with inverse
   patient-frequency and inverse class-frequency sample weights.

No regularization grid, feature deletion, seed replacement, threshold change,
or subset selection is allowed on R30.

## Development survival gate

Before any R30 test prediction:

- regularized multiscale minus uniform dev patient-balanced macro F1 >= +1 pp;
- all three seed-specific directions positive;
- mean train accuracy < 0.80;
- shuffled-label regularized multiscale dev macro F1 < 0.45;
- all fits finite and converged;
- train/dev/test patients disjoint and all prior cohorts absent;
- no forbidden input field.

If any condition fails, test remains sealed and R30 stops.

## One-shot test scientific GO

After a development pass, refit each system on train+dev and reveal test once.
GO requires:

- regularized multiscale minus uniform >= +2 pp;
- hierarchical patient-bootstrap 95% CI lower bound > 0;
- all three seed-specific directions positive;
- regularized multiscale no more than 1 pp below the strongest reference
  single expert;
- inference valid, complete finite predictions, and zero patient overlap;
- fresh-process reproduction.

Bootstrap uses 10,000 replicates and RNG seed 20260830. A GO supports only the
fresh-silver development claim and does not reverse R26 `STOP_C1` without new
human-gold confirmation.

## Stop and continuation

A dev or test NO-GO closes R30. Any R31 must use the remaining R30 sealed
reserve, a new frozen protocol, and a materially different representation or
training strategy. Threshold, seed, case, and subset retuning is forbidden.
