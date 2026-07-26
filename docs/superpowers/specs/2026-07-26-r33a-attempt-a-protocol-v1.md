# R33A Attempt A: Direct Transition Token Bridge

Date frozen: 2026-07-26

Evidence class: `EXPLORATORY_TRAIN_ONLY_NESTED_OOF`

## Motivation

R33 froze a randomly initialized nonlinear token builder and therefore did not
exercise the proposal's allowed trained/competent token bridge. Attempt A
changes the representation, not the endpoint or the patient folds.

## Scope and seal

- Use only the 1,574-patient R32 train partition and its 13,566 persistent
  Stable/Improved/Worse rows.
- Do not compute dev case metrics.
- Do not read the 483-patient sealed-test records/images or gold outcomes.
- Reuse the frozen R32 BiomedCLIP `[197,768]` patch cache without re-encoding
  images or recomputing shard hashes.

## Representation mutation

Use direct outcome-free transition sources:

- query: finding identity only;
- state: current-image CLS;
- global: normalized prior/current CLS interactions;
- robust local: normalized prior/current patch-mean interactions;
- rich local: normalized interactions at spatial positions with the largest
  patch change;
- robust relation: normalized prior/current patch-dispersion interactions;
- rich relation: change-weighted prior/current patch interactions.

Each source is projected by a fixed seed-specific Gaussian projection to
64-dimensional mean and max channels. Robust and rich use the same projection
for corresponding types. The representation remains compatible with the
4/12/16/16/12/4 exact-64 layout; the reserved type is neutral.

P0 is literal query-only: no image-derived value enters token type 0.

## Evaluation

Run the existing true nested five-fold patient OOF evaluator with seeds
17/29/43, the same 774-to-3 linear probe, optimizer, epochs, weighting,
bootstrap, random-route, prior-shuffle, and leakage checks as R33.

Attempt A is exploratory. Passing its train-only gates does not unlock R34.
It permits freezing one candidate for a single 300-patient dev confirmation.
