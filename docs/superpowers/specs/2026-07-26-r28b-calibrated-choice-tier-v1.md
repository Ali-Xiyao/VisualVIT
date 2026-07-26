# R28b Calibrated Choice-Supervised TIER Protocol v1

Date frozen: 2026-07-26

Evidence class: `NON_CONFIRMATORY_R28B_DEVELOPMENT`

## Motivation fixed before execution

R28 A1/A2 ran end to end and reproduced exactly, but both failed the scientific
gate. The global expert was strongest while both mixture-loss routers assigned
the largest mean weight to the weakest state expert. R28b tests one materially
different explanation: expert logits are not calibrated onto a common scale
and the indirect mixture loss does not teach explicit expert selection.

R28b does not modify or replace the R28 v1 record. No R28b outer-test result
has been inspected at the time this protocol is frozen.

## Immutable inheritance

R28b inherits without change:

- the 774-entity frozen cohort and feature-cache hash;
- state, global, and binding expert representations;
- 128-dimensional deterministic signed projections;
- the five outer patient folds and four nested inner patient folds;
- training seeds `17`, `29`, and `43`;
- expert optimizer, steps, learning rate, and weight decay;
- patient-balanced macro F1 and 10,000-replicate patient/seed bootstrap;
- uniform logit fusion as the primary comparator;
- the R28 scientific GO thresholds;
- CPU-only execution and all leakage/provenance checks.

No case archetype, BII, LPD/LCD, correctness summary, patient/study/image ID, or
progression label is available as a router input at inference.

## Training-only calibration

For each training seed and outer fold:

1. Obtain expert logits on every outer-training entity strictly from its nested
   inner held-out fold.
2. Fit one positive scalar temperature per expert by minimizing multiclass
   cross entropy on those inner-OOF logits and outer-training labels.
3. Parameterize temperature as `exp(log_temperature)`, initialize at `1.0`,
   optimize with deterministic Adam for 300 steps at learning rate `0.03`, and
   clamp `log_temperature` to `[-2, 2]` after each step.
4. Apply the fitted temperatures to both inner-OOF training logits and the
   corresponding outer-test logits. No outer-test label enters calibration.

## Choice targets

For each outer-training entity, form a route target using calibrated inner-OOF
predictions:

- if one or more experts predicts the correct class, select the first correct
  expert in the fixed cost order `state -> global -> binding`;
- if no expert is correct, select the expert assigning the highest calibrated
  probability to the true class, with the same cost order resolving ties.

These targets are label-derived training supervision, not router features and
not evaluation subsets. Their use makes R28b a separate development attempt.

## Router and attempt ladder

The router consumes the same 12 label-free R28 base descriptors plus calibrated
expert logits, entropy, maximum probability, and top-two margin.

It is a two-layer router with hidden width 32, GELU activation, deterministic
AdamW, 400 steps, learning rate `0.01`, weight decay `1e-4`, and class-weighted
cross entropy on the expert-choice targets.

Only the following ordered attempts are allowed:

1. `tier_b1_choice_hard`: select the expert with maximum router probability and
   use only that expert's calibrated logits.
2. `tier_b2_choice_guarded`: run only if B1 passes engineering checks but fails
   scientific GO. Select the router expert only when its probability is at
   least `0.60` and the top-two route-probability gap is at least `0.15`;
   otherwise fall back to the global expert. These guard values are frozen
   before any R28b outer-test result.

No threshold search, seed selection, fold change, expert retraining mutation,
or held-out subset selection is permitted.

## Engineering gate

PASS requires:

- all `774 x 3` predictions for each attempted system;
- complete nested inner/outer patient disjointness;
- finite temperatures, fits, route probabilities, and predictions;
- temperatures learned only from inner-OOF outer-training logits;
- a fresh-process reproduction with identical registered metric tables and
  prediction digest.

## Scientific GO gate

For the final allowed attempt, all conditions must hold:

- TIER minus uniform fusion is at least `+2.00 pp`;
- patient-bootstrap 95% CI lower bound is greater than zero;
- all three training-seed directions are positive;
- bootstrap inference is valid;
- TIER is no more than `1.00 pp` below the strongest fixed expert;
- all engineering and leakage gates pass.

The thresholds are not relaxed if R28b fails.

## Stop rule

- Scientific GO unlocks only a fresh-cohort confirmation design, not a formal
  or clinical claim on this reused cohort.
- Engineering PASS with scientific NO-GO closes calibrated choice routing as a
  reproducible negative development result.
- Report-supervised transition repair remains locked unless its source,
  license/DUA boundary, preprocessing, and independent protocol are audited.
- VLM, DIVE, new foundation encoders, and scale-up remain out of scope.
