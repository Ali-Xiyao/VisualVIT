# R31 Confidence-Consensus Tier Protocol v1

Date frozen: 2026-07-26

Evidence class: `NON_CONFIRMATORY_FRESH_SILVER_DEVELOPMENT`

## Motivation and selection disclosure

R30 passed development but stopped on its sealed test because its consistent
+0.77 pp improvement did not meet the frozen +2 pp and positive-CI gates.
The revealed R30 test was then used only as disclosed R31 development evidence.
Five label-free discrete aggregation rules were evaluated and frozen in
`reports/R30_FAILURE_CASE_STUDY.md`.

R31 independently validates the selected confidence-consensus rule. No R31
patient or outcome was used for rule selection.

## Cohort authority

- Eligible patients are only the `sealed_reserve` of R30 cohort SHA-256
  `219132709955c5612abd39b5eade618bf3fc69eeb5a520ef6b41196fd41b437f`.
- Sort patients by `SHA256("r31-patient-v1|" + patient_id)`.
- Assign the first 1,200 to train, next 300 to dev, next 500 to sealed test,
  and all remaining patients to sealed reserve.
- Within active patients, sort by
  `SHA256("r31-row-v1|" + record_id)` and retain at most 12 rows.
- Every R24-R30 active patient is forbidden.
- Image binding, labels, allowed input fields, encoder, crops, and anatomy
  fallbacks are exactly R30.

## Frozen base systems

Fit the R30 systems without modification:

- R29 `state`, `global_transition`, `local_transition`, and `uniform_fusion`
  MLP references;
- R30 `regularized_multiscale` with separate 128-dimensional scale
  projections, `C=0.001`, patient/class weighting, and seeds 17, 29, 43.

## Confidence-consensus tier

For each observation:

1. collect the three `regularized_multiscale` class predictions;
2. if all three agree, output that unanimous class;
3. otherwise output the majority of the three `uniform_fusion` predictions;
4. if the three uniform predictions are all different, select the first class
   in the frozen order `Stable`, `Improved`, `Worse`.

The resulting deterministic consensus prediction is replicated across the
three registered seed rows only so paired seed/bootstrap contracts remain
identical to prior rounds. It contains no label, metric, anatomy subgroup, or
test-dependent decision.

## Development survival

Before any R31 test prediction:

- consensus minus pooled uniform dev macro F1 >= +1 pp;
- consensus minus each uniform seed macro F1 is positive;
- base fits finite/converged and regularized mean train accuracy < 0.80;
- patient partitions disjoint and all prior active patients absent;
- prediction coverage complete and forbidden inputs absent.

Failure closes R31 with test sealed.

## One-shot test scientific GO

After a dev pass, refit base systems on train+dev and reveal test once. GO
requires:

- consensus minus pooled uniform >= +2 pp;
- hierarchical patient-bootstrap 95% CI lower bound > 0;
- consensus minus each uniform seed is positive;
- consensus no more than 1 pp below the strongest single reference expert;
- 10,000 valid bootstrap replicates, RNG seed 20260831;
- complete finite predictions, zero patient overlap, and fresh-process
  reproduction.

A successful reproduction yields only a fresh-silver development GO. R26
`STOP_C1` remains the human-gold formal conclusion until new external labels
are acquired.

## Stop and continuation

Any R31 dev/test failure is immutable. R32, if required, must use the remaining
R31 reserve and a new pre-outcome protocol; no threshold, seed, tie-order,
case, or subgroup changes are allowed.
