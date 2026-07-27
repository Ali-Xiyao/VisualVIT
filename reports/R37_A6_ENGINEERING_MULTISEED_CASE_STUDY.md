# R37 A6 Engineering Multiseed Case Study

## Verdict

The frozen A6 mechanism-scale configuration produced positive prior-responsiveness
point estimates for all three prespecified seeds (17, 29, and 43). The weakest
true-pair versus current-only difference was +6.84 macro-F1 points, and the
weakest true-pair versus CMCP counterfactual-prior difference was +5.77 points.

This is positive multiseed engineering evidence, not a scientific GO. Every run
was non-formal, used the same 500-row internal engineering evaluation, and did
not run patient-bootstrap confidence intervals. Protected 300-dev, 483-test,
and gold outcomes remained unread.

## Frozen Configuration

- Variant: A6 full PRTA-CXR
- Seeds: 17, 29, 43
- Train rows: 1,000
- Internal engineering evaluation rows: 500
- Epochs: 3
- Batch size: 2
- Adapter rank: 32
- Learning rate: 1e-4
- Losses, thresholds, architecture, and sampling protocol: unchanged across
  seeds

## Three-Seed Readout

| Seed | True-pair F1 | Current-only F1 | True-current | Inverted F1 | True-inverted | CMCP true F1 | CMCP control F1 | True-CMCP |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 17 | 0.4408 | 0.3724 | +6.84 pp | 0.2917 | +14.91 pp | 0.3425 | 0.2728 | +6.97 pp |
| 29 | 0.4093 | 0.3196 | +8.97 pp | 0.2578 | +15.15 pp | 0.3216 | 0.2331 | +8.85 pp |
| 43 | 0.4228 | 0.3474 | +7.54 pp | 0.2592 | +16.37 pp | 0.3314 | 0.2737 | +5.77 pp |
| Mean | — | — | +7.78 pp | — | +15.48 pp | — | — | +7.20 pp |

All three directional point-estimate checks are positive for every seed. This
replicates the seed-17 mechanism signal without changing settings in response
to outcomes.

## Continuous Responsiveness

| Seed | Current-only prediction-change rate | CMCP prediction-change rate | Inverted prediction-change rate |
|---:|---:|---:|---:|
| 17 | 0.186 | 0.300 | 0.502 |
| 29 | 0.398 | 0.500 | 0.572 |
| 43 | 0.310 | 0.375 | 0.608 |

The nonzero change rates show that the larger case is no longer the
true/current collapse observed in the earlier 50-row tiny smoke. The ordering
is also protocol-consistent: temporal inversion perturbs predictions most,
while current-only and CMCP controls remain materially different from the true
pair.

## Interpretation and Failure Comparison

The earlier bounded A6 case study was too small and undertrained to demonstrate
responsiveness: true/current and true/CMCP predictions were exactly identical.
Scaling only to the pre-existing engineering ceiling (1,000 train rows, 500
evaluation rows, 3 epochs) repaired that diagnostic failure. Replication on two
additional prespecified seeds confirms that seed 17 was not an isolated point
estimate.

This does not establish the proposal's final claim. The formal three-seed
patient-bootstrap gate remains unevaluated, and human QA remains deferred to
the final project stage by user direction. No protected outcome may be opened
from this engineering evidence.

## Runtime Evidence

- Seed 17:
  `H:\VisualVIT_runtime\050_routeD\r37_prta_cxr\r37b_smokes\a6_seed17_mechanism_scale1000x500x3_v1\result.json`
- Seed 29:
  `H:\VisualVIT_runtime\050_routeD\r37_prta_cxr\r37b_smokes\a6_seed29_mechanism_scale1000x500x3_v1\result.json`
- Seed 43:
  `H:\VisualVIT_runtime\050_routeD\r37_prta_cxr\r37b_smokes\a6_seed43_mechanism_scale1000x500x3_v1\result.json`

Each artifact reports `PASS_R37_PRTA_ENGINEERING_SMOKE`,
`scientific_claim_allowed=false`, and no protected-outcome access.
