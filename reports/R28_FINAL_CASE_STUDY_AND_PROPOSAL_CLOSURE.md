# R28 Final Case Study and Proposal Closure

Date: 2026-07-26

Status: `ENGINEERING_REPRODUCED_SCIENTIFIC_NO_GO`

Evidence class: `NON_CONFIRMATORY_DEVELOPMENT`

## Direct verdict

The current proposal has been run through as a deterministic, patient-disjoint,
leak-audited experiment pipeline. It has not passed its scientific gate.

R26's `STOP_C1` remains valid. R28/R28b do not rescue the universal-binding
claim and do not justify VLM, DIVE, RAD-DINO, or scale-up.

## What the case study established

The frozen case registry contains 24 immutable representative cases across
state-sufficient, temporal-helped, binding-helped, binding-harmed, and
all-experts-fail regimes. It exposed five recurring mechanisms:

1. current-state shortcuts solve many progression labels;
2. R26 derangement often preserved label semantics;
3. the nominal anatomy-compatible intervention was not active on the cohort;
4. global acquisition and disease changes can dominate a small local ROI;
5. small edge ROIs can remove the context needed for change direction.

The label-reading case oracle exceeded the best fixed expert by `+25.61 pp`,
95% CI `[+22.87,+28.37]`. This proves expert complementarity exists in
principle, not that a deployable router can identify it.

## Formal attempt ledger

| Attempt | Design change | TIER F1 | Uniform F1 | Delta | 95% CI | Verdict |
|---|---|---:|---:|---:|---|---|
| R28 A1 | linear mixture-loss router | 0.4188 | 0.4368 | -1.80 pp | [-6.07,+2.49] | NO-GO |
| R28 A2 | nonlinear mixture-loss router | 0.4307 | 0.4368 | -0.61 pp | [-4.36,+3.35] | NO-GO |
| R28b B1 | calibrated choice-supervised hard route | 0.4225 | 0.4368 | -1.43 pp | [-5.98,+2.82] | NO-GO |
| R28b B2 | frozen guarded route with global fallback | 0.4281 | 0.4368 | -0.87 pp | [-5.13,+3.20] | NO-GO |

All four attempts passed their engineering checks. None met the frozen
`+2.00 pp`, positive CI lower bound, and all-seed-positive scientific gates.

## Why the new repair still failed

Temperature calibration was active rather than cosmetic: fitted temperatures
ranged from `4.23` to `6.88`. The choice router also fit its training targets
strongly, with mean training choice accuracy `93.50%`.

The failure is therefore not a crashed optimizer. The training target itself
retained a shortcut:

- state choice targets: 51.55%;
- global choice targets: 28.59%;
- binding choice targets: 19.86%.

Because the frozen tie-break selected the cheapest first correct expert, easy
cases were assigned to state even though global was the strongest fixed expert.
At test time the hard router selected state 1,114 times out of 2,322
seed-entity predictions. The guarded router still accepted 86.22% of routes,
so the global fallback was too infrequent to prevent negative transfer.

This diagnosis was recorded after the attempt and must not be used to retune
the same held-out results.

## Reproduction evidence

R28 v1:

- verifier: 43/43 checks passed;
- prediction SHA-256:
  `982591076381cacb5597015a3dfdea399d22c3ef74186e6d25691630fc825135`;
- certificate:
  `F:\VisualVIT_runtime\050_routeC\r28_case_study_tier\tier_mvp_v1_reproduction_certificate.json`;
- certificate SHA-256:
  `abe02618ef9c318bb44f58693126c5c91200dcd10f15078524a606cb0fe1e71c`.

R28b:

- verifier: 42/42 checks passed;
- prediction SHA-256:
  `44bbe466d5199f328a9ffdb9ca9e85b9be3ac9835e9a5678834ae1d2505c565a`;
- certificate:
  `F:\VisualVIT_runtime\050_routeC\r28_case_study_tier\tier_r28b_v1_source_closed_reproduction_certificate.json`;
- certificate SHA-256:
  `c1b126584bc90e61afe9ff3272bf11c8065f982e6b828a89ac47d59a2e5cc2a4`.

Restricted image panels and runtime predictions remain outside Git because
they inherit the MIMIC/Chest ImaGenome data boundary. Protocols, source,
tests, aggregate reports, and manifests/hashes are the publishable handoff.

## Stop boundary and next legitimate experiment

The current reused 170-patient development cohort is exhausted for router
selection. A further threshold, seed, tie-break, or architecture search on it
would be model-selection leakage.

The next legitimate attempt requires a separately frozen protocol and one of:

1. a fresh patient cohort held untouched during R26-R28b;
2. a legally audited report source for report-supervised transition targets;
3. a new transition/ROI-context representation that first passes a
   train-only change-direction survival test, then is evaluated once on fresh
   held-out patients.

Until one of those inputs exists, the scientifically correct terminal result
is `NO_GO_CURRENT_PROPOSAL`; the engineering handoff is complete.
