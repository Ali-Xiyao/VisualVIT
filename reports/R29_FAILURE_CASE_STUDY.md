# R29 Failure Case Study and R30 Repair Selection

Date: 2026-07-26

Evidence boundary: R29 train/dev only. The 300-patient R29 test partition was
never predicted or evaluated.

## Formal R29 result

R29 stopped at the registered development survival gate:

- contextual minus uniform: -1.80 pp;
- seed deltas: +1.66, -3.79, and -3.26 pp;
- shuffled-label macro F1: 0.2997;
- finite fits, patient disjointness, and forbidden-input checks: pass;
- test revealed: no.

## Failure pattern

The original expert heads memorized the training cohort:

- global-transition train accuracy: 0.9821 to 1.0000;
- local-transition train accuracy: 0.9950 to 1.0000;
- their pooled development macro F1: 0.4532 and 0.4217;
- contextual train accuracy: 0.8469 to 0.8851;
- contextual pooled development macro F1: 0.4514;
- uniform pooled development macro F1: 0.4695.

The 11,570-dimensional contextual raw block was compressed to one
256-dimensional random projection. This mixed global, local, context,
geometry, finding, and anatomy fields before learning. Adding more evidence
therefore increased capacity without preserving scale identity.

Finding-level review was heterogeneous. Context helped atelectasis by about
+5.08 pp but hurt cardiomegaly by about -2.61 pp and enlarged
cardiomediastinum by about -3.29 pp. This is consistent with an unstable
high-capacity representation rather than a universally useful context signal.

## Disclosed R29 train/dev repair audit

Four representation variants were first tested with the original MLP head:

- preserved query: 0.4469 mean macro F1;
- separate 128-dimensional scale projections: 0.4602;
- structured scalar deltas: 0.4136;
- hybrid scale/scalar representation: 0.4359.

None survived. A capacity audit then replaced the MLP with a patient- and
class-weighted standardized logistic head. The regularization grid was frozen
to `C in {0.001, 0.01, 0.1, 1.0}` for this retrospective audit. `C=0.001`
was strongest and was selected before any R30 patient was assigned.

With independent scale projections for seeds 17, 29, and 43, the selected
multiscale head achieved:

| Seed | Development macro F1 | Train accuracy |
|---:|---:|---:|
| 17 | 0.5331 | 0.5328 |
| 29 | 0.5210 | 0.5275 |
| 43 | 0.5283 | 0.5306 |

All three exceed the corresponding R29 uniform scores (0.4559, 0.5003, and
0.4504). The repair removes the near-perfect training fit while retaining
global, exact-ROI, expanded-context, query, and geometry evidence.

## R30 decision

Freeze a low-capacity regularized multiscale transition head. R30 must use
only patients from the untouched R29 sealed reserve, create a new
patient-disjoint train/dev/test split, repeat the development survival gate,
and reveal its test once only if the gate passes. No further `C`, projection
dimension, seed, crop, threshold, or subset search is allowed.
