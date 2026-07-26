# R30 Failure Case Study and R31 Consensus Selection

Date: 2026-07-26

## Formal R30 result

R30 passed every registered development check:

- regularized multiscale minus uniform: +2.30 pp;
- seed deltas: +0.88, +4.61, and +1.42 pp;
- mean train accuracy: 0.5335;
- shuffled-label macro F1: 0.2203.

The one-shot 600-patient test remained directionally consistent but failed the
frozen scientific magnitude and uncertainty gates:

- regularized multiscale: 0.5038 macro F1;
- uniform fusion: 0.4961;
- delta: +0.77 pp;
- 95% CI: [-1.61, +3.18] pp;
- all three seed directions positive;
- verdict: `STOP_R30_TEST_NO_GO`.

The failed first serialization run and the clean recovery run have identical
`dev_predictions.json` SHA-256
`b8013f2dc81aa436320dec93fb2e20452a8b8d59e9da493317440b6762bcb099`.
The recovery changed JSON type handling only.

## Disagreement case study

Regularized-majority and uniform-majority predictions agree on 61.46% of R30
test observations. The complementary errors leave a large selection oracle:
choosing the correct one when either is correct reaches 0.6781 macro F1. The
small direct R30 gain is therefore an aggregation problem, not absence of
complementary evidence.

Five discrete, label-free consensus rules were compared on the now-development
R30 test:

| Rule | Patient-balanced macro F1 |
|---|---:|
| uniform majority | 0.5152 |
| regularized majority | 0.5115 |
| all-six majority | 0.5252 |
| regularized if unanimous, else uniform majority | **0.5276** |
| uniform if unanimous, else regularized majority | 0.5257 |

The selected rule uses regularized multiscale only when its three independent
projection seeds agree; otherwise it falls back to the more stable uniform
expert majority. Ties among three distinct uniform labels use the frozen label
order `Stable`, `Improved`, `Worse`.

Against the original pooled uniform rows, the selected consensus improves by
+3.15 pp with a retrospective patient-bootstrap 95% CI of [+0.91, +5.34] pp
(10,000 valid replicates, RNG seed 20260831).

## R31 decision

R31 independently validates the frozen confidence-consensus rule using only
patients from the untouched R30 sealed reserve. No R31 patient or outcome was
used to choose the rule. R30 thresholds and verdict remain unchanged.
