# R33 TIER-CXR-VLM Token Survival Result

Date: 2026-07-26

Verdict: **STOP_R33_TOKEN_SURVIVAL**

Evidence class: `NON_CONFIRMATORY_TRAIN_DEV_NESTED_OOF`

## Direct result

The registered R33 survival gate failed. Across 15,698 persistent-label rows
from 1,874 train/dev patients, hard-consensus TIER (P6) reached patient-balanced
macro F1 0.4516 versus 0.4583 for robust fixed-64 (P3):

- primary delta: **-0.669 pp**;
- 10,000-patient-cluster bootstrap 95% CI: **[-1.443, +0.109] pp**;
- seed deltas: **+0.405, -0.734, -1.665 pp** for seeds 17, 29, and 43;
- hard-route rich coverage: **46.91%**;
- correction rate: 11.02%; harm rate: 11.66%; net corrected: **-0.643 pp**.

The primary +2 pp, positive-CI, all-seed, prior-shuffle, and query-control
conditions did not pass. The scientific gates therefore did not qualify for a
fresh-process reproduction. R34 remains forbidden and its 483-patient sealed
test remains unread.

## Main nested-OOF metrics

All probes use the same 774-to-3 linear head (2,325 trainable parameters), 20
fixed epochs, AdamW, and patient/class-balanced training weights.

| System | Macro F1 | F1 95% CI | Delta vs P3 (pp) | Delta 95% CI (pp) | Balanced accuracy | NLL | ECE |
|---|---:|---|---:|---|---:|---:|---:|
| P0 query/control proxy | 0.4622 | [0.4498, 0.4748] | +0.385 | [-0.474, +1.224] | 0.4904 | 1.0378 | 0.0269 |
| P1 query/control + state | 0.4601 | [0.4479, 0.4721] | +0.175 | [-0.592, +0.945] | 0.4868 | 1.0447 | 0.0408 |
| P2 query/control + global | 0.4583 | [0.4460, 0.4708] | -0.000 | [-0.754, +0.767] | 0.4840 | 1.0424 | 0.0431 |
| P3 robust fixed-64 | 0.4583 | [0.4461, 0.4703] | 0.000 | [0.000, 0.000] | 0.4817 | 1.0548 | 0.0689 |
| P4 always-rich fixed-64 | 0.4534 | [0.4416, 0.4655] | -0.491 | [-1.261, +0.295] | 0.4776 | 1.0645 | 0.0796 |
| P5 matched-random route | 0.4514 | [0.4396, 0.4633] | -0.688 | [-1.468, +0.116] | 0.4750 | 1.0659 | 0.0771 |
| P6 hard-consensus TIER | 0.4516 | [0.4401, 0.4634] | -0.669 | [-1.443, +0.109] | 0.4739 | 1.0624 | 0.0761 |
| P7 label-reading oracle | 0.5657 | [0.5536, 0.5777] | +10.744 | [+10.209, +11.301] | 0.5908 | 1.0067 | 0.0818 |

P7 is an upper bound only. It reads the endpoint to select between already
produced P3/P4 predictions and is not a deployable or trainable system.

## Seed and control results

| Seed | P3 F1 | P4 F1 | P6 F1 | P6-P3 (pp) | Delta 95% CI (pp) |
|---:|---:|---:|---:|---:|---|
| 17 | 0.4483 | 0.4532 | 0.4524 | +0.405 | [-1.003, +1.841] |
| 29 | 0.4585 | 0.4505 | 0.4512 | -0.734 | [-2.033, +0.589] |
| 43 | 0.4678 | 0.4562 | 0.4512 | -1.665 | [-2.987, -0.379] |

The cross-patient, within-finding prior shuffle produced P3 F1 0.4031 and P6
F1 0.4073, a **+0.422 pp** routed delta. The registered control required this
delta to be at least 0.5 pp below the primary delta (at most -1.169 pp), so the
control failed.

The matched-random route had 47.41% rich coverage and macro F1 0.4514, nearly
identical to hard consensus at 46.91% coverage and 0.4516 F1. This gives no
evidence that the learned hard route is identifying beneficial cases.

## Gate adjudication

| Gate | Registered threshold | Observed | Result |
|---|---|---|---|
| Primary delta | at least +2.0 pp | -0.669 pp | FAIL |
| Primary CI lower | above 0 | -1.443 pp | FAIL |
| Seed direction | all three positive | one of three positive | FAIL |
| Within strongest non-oracle | no worse than -1.0 pp | -1.054 pp vs P0 proxy | FAIL |
| Prior shuffle | routed delta at least 0.5 pp lower | +0.422 pp; not reduced | FAIL |
| Query-only/control | P6 at least +1.0 pp | P6 is -1.054 pp vs P0 proxy | FAIL/INVALID CONTROL |
| Leakage and seal | all pass | all pass | PASS |
| Bootstrap | 10,000 valid | 10,000 valid | PASS |
| Fresh-process reproduction | only after scientific pass | not reached | N/A |

## Query-only implementation audit

The feature summary cannot provide a literal query-only P0. R32 token type 0
contains the finding query plus three global image-derived controls
(prior-global, current-global, and their difference). Consequently P0 is
reported here as a **query/control proxy**, not as a valid query-only shortcut
measurement.

This defect cannot rescue R33: the primary P6-P3 delta, its CI, the seed gate,
and the prior-shuffle control fail independently of P0. As a sensitivity check,
if P0 is excluded, P1 is the strongest remaining non-oracle baseline and P6 is
0.844 pp below it; only the strongest-baseline gate would change, while the
overall STOP remains unchanged. No outcome-conditioned protocol repair or
rerun is warranted.

## Audit and artifact boundary

- Five patient folds: 382 / 370 / 398 / 323 / 401 patients.
- Evaluation routes use models fit on the other four folds.
- Training routes use inner fits on three folds, excluding both outer and
  inner evaluation patients.
- Every row receives exactly one outer prediction.
- Frozen BiomedCLIP representations and three frozen token builders are used.
- No labels or probe logits enter the token features.
- Sealed-test records read: false.
- Sealed-test images read: false.
- Gold outcomes read: false.
- Full result:
  `F:\VisualVIT_runtime\050_routeC\r33_token_survival\nested_oof_v1\r33_token_survival_result.json`.
- OOF predictions:
  `F:\VisualVIT_runtime\050_routeC\r33_token_survival\nested_oof_v1\r33_oof_predictions.pt`.

The R32 one-time identifiers remain the provenance anchors. R33 validation uses
schema, counts, fold disjointness, shape, finite-value, and seal checks rather
than repeated file or shard hashing.
