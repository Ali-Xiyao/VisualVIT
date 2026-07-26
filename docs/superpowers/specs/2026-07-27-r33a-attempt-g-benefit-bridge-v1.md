# R33A Attempt G: Benefit-Conditioned Learned Bridge

Date frozen: 2026-07-27

Evidence class: `EXPLORATORY_TRAIN_ONLY_NESTED_OOF`

## Motivation

Attempt F makes robust and rich experts equally competent (P3 0.50720, P4
0.50741) and retains a large case oracle (P7 0.60824), but consensus selection
has essentially zero net correction. The remaining failure is route
identifiability rather than average rich-expert competence.

## Single mutation

Keep Attempt F prebridge, 64-unit trained bottleneck, folds, weights, seeds,
optimizer, and controls unchanged. Replace hard label-consensus routing with
the already implemented Attempt B cross-fitted benefit router:

- obtain robust/rich auxiliary logits with the same learned bridge;
- define rich-help versus rich-harm only on nonzero three-seed training-fold
  benefit;
- use only label-free probability/confidence features at route inference;
- cross-fit every training route and fit the outer route without outer patient
  labels.

No token geometry, finding interactions, threshold tuning, or output stacking
is added.

## Decision

Require the complete original gate set, including +2 pp, CI above zero, all
seed directions, prior-shuffle attenuation, and query/control checks. A failed
Attempt G closes benefit routing on the frozen BiomedCLIP prebridge.
