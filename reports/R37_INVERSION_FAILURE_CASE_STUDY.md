# R37 Inversion-Consistency Failure Case Study

## Verdict

The frozen two-seed R37 run is closed as
`STOP_R37_INVERSION_CONSISTENCY`.

The failure does **not** erase the positive correct-prior result. Seed 17 and
29 improve over current-only by +11.87 and +14.15 macro-F1 points and improve
over CMCP by +7.58 and +7.91 points. However, the registered inversion gate
requires at least 0.90 consistency in every seed, and the two observed seeds
reach only 0.8438 and 0.8735.

Seed 43, A0, bootstrap aggregation, the protected 300-patient development set,
the 483-patient test set, and gold outcomes were not run or read after this
failure.

## Frozen Evidence Boundary

- Calibration rows: 5,242
- Calibration patients: 1,347
- Result seeds: 17 and 29
- Source: firewall-clean formal A6 result artifacts
- Use of these rows: descriptive failure analysis only
- R37.1 model/loss/threshold/checkpoint selection on these rows: forbidden
- Protected, sealed-test, or gold outcomes read: false
- Source or per-shard hashes recomputed: false

The machine-readable summary is stored outside Git at
`H:\VisualVIT_runtime\050_routeD\r37_prta_cxr\r37_inversion_failure_case_study.json`.

## Two-Seed Readout

| Metric | Seed 17 | Seed 29 |
|---|---:|---:|
| True-pair macro F1 | 0.4092 | 0.4105 |
| Current-only macro F1 | 0.2905 | 0.2690 |
| True minus current-only | +11.87 pp | +14.15 pp |
| True minus CMCP | +7.58 pp | +7.91 pp |
| Inversion consistency | 0.8438 | 0.8735 |
| Inconsistent rows | 819 | 663 |
| State-retention cosine | 0.9938 | 0.9936 |

The two seeds share only 324 failed example IDs among 1,158 unique failures
(Jaccard 0.2798). The low overlap argues against one small deterministic set
of corrupt examples and points instead to optimization or head-equivariance
instability.

## Failure Localization

| Target label | Seed 17 consistency | Seed 29 consistency |
|---|---:|---:|
| Stable | 0.9052 | 0.9144 |
| Improved | 0.7914 | 0.8253 |
| Worse | 0.8086 | 0.8526 |
| New | 0.7249 | 0.8166 |
| Resolved | 0.7287 | 0.7926 |

Failures concentrate in Consolidation, Lung Opacity, Pneumonia, Edema,
Atelectasis, and Pleural Effusion. Several other findings have perfect or
near-perfect consistency, but that cannot by itself establish temporal
reasoning: a Stable prediction maps to itself under reversal and can inflate
the consistency metric.

The largest failure modes are expected-Stable becoming Improved,
expected-Worse becoming Stable, and expected-Improved becoming Stable or
Worse. The model therefore responds strongly to the prior while still lacking
an exact, seed-stable action of the temporal reversal operator.

## Root-Cause Hypothesis

R37 uses a detached soft target:

1. compute forward logits;
2. permute those logits with Stable→Stable, Improved↔Worse, and
   New↔Resolved;
3. train reversed logits to match the detached distribution with KL loss.

This regularizes the reversed prediction but does not make the model
equivariant by construction. It can remain approximately consistent, settle
into different local optima across seeds, or obtain high consistency through
an invariant Stable prediction.

## Frozen R37.1 Repair

R37.1 replaces the soft inversion regularizer with a parameter-free
two-element-group projection. Let `z_f` be the raw forward logits, `z_r` the
raw reversed logits, and `P` the fixed label permutation. Define:

```text
L_f = 0.5 * (z_f + P(z_r))
L_r = P(L_f)
```

This guarantees `L_r = P(L_f)` exactly while allowing gradients to flow
through both directions. R37.1 keeps the R37 encoder, Block-8 cache, adapter
rank, epochs, batch size, learning rate, transition alignment, CMCP loss, and
state-preservation loss unchanged. The detached inversion KL term is removed
because the architectural projection supersedes it.

The repair does not guarantee correct classification, correct-prior gain,
CMCP gain, or state retention. Those remain empirical gates on a fresh
patient holdout.

## Fresh Holdout Contract

Before reading any R37.1 validation outcome:

- source population: only the 12,102 transition-eligible patients in the old
  R37 pretraining partition;
- split rule: sort patient IDs, shuffle once with Python RNG seed 37101, and
  hold out the first 1,815 patients (15%);
- R37.1 training: all remaining old-pretraining patients;
- R37.1 validation: all rows belonging to the 1,815 held-out patients;
- old 1,347-patient R37 calibration cohort: excluded from both R37.1 training
  and validation;
- initial seeds: 17 and 29;
- continuation: seed 43, A0, and patient bootstrap only if both initial seeds
  pass every frozen internal gate.

No split revision is permitted after class counts or model outcomes are
observed. If the one-shot roster has inadequate support, R37.1 stops rather
than selecting a more favorable roster.
