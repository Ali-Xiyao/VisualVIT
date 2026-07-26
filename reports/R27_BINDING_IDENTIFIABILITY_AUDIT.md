# R27 Binding Identifiability Audit

Date: 2026-07-26

Terminal verdict: `C_SPARSE_HIGH_BII_SUPPORT`

Evidence class: `EXPLORATORY_POSTHOC_R27_MECHANISM_AUDIT`

`exploratory_only=true`; `formal_claim_allowed=false`; `r28_unlocked=false`.

## Formal boundary

R26 remains `STOP_C1`. R27 read the frozen R26 cohort and predictions, did not train a model, and did not regenerate predictions. R26 did not serialize assignment indices; semantic assignments were deterministically reconstructed from the frozen cohort order, registered derangement ids, pair-seed basis, and frozen R26 algorithm.

## Pair composition

| Stratum | Patients | Entities |
|---|---:|---:|
| BII-0 | 122 | 467 |
| BII-Low | 5 | 40 |
| BII-Mid | 35 | 240 |
| BII-High | 8 | 27 |

Cohort conservation: 170/170 patients and 774/774 entities.

## Actual R26 derangement semantics

- Assignments audited: 2322
- Label-preserving (LPD-class): 1846
- Label-changing (LCD-class): 476
- Semantic corruption rate: 20.50%
- Reconstructed fixed points: 0

## BII-stratified frozen-prediction effects

| Stratum | B4b − B4a | B4b − Current | Bootstrap valid |
|---|---|---|---:|
| BII-0 | +2.36 pp; 95% CI [-2.23, +6.97] pp | +1.76 pp; 95% CI [-4.67, +8.23] pp | 100.00% |
| BII-Low | +4.92 pp; CI invalid (bootstrap valid fraction below 0.95) | -4.31 pp; CI invalid (bootstrap valid fraction below 0.95) | 91.28% |
| BII-Mid | -1.50 pp; 95% CI [-9.11, +5.56] pp | +1.42 pp; 95% CI [-6.57, +9.03] pp | 100.00% |
| BII-High | -6.24 pp; 95% CI [-19.10, +7.75] pp | +23.42 pp; 95% CI [+9.17, +37.50] pp | 97.70% |

## Verdict

High-BII support is 8 patients / 27 entities. The registered support gate requires at least 30 patients, 100 entities, and at least 10 patients for each label, so the terminal classification is `C_SPARSE_HIGH_BII_SUPPORT` before any positive subgroup pattern can be elevated.

Verdict checks:

- `high_bii_support`: FAIL
- `nondecreasing_stratum_points`: FAIL
- `high_bii_point_positive`: FAIL
- `high_bii_ci_lower_positive`: FAIL
- `all_high_bii_seed_directions_positive`: FAIL

This result may generate an independently preregistered R28/R29 hypothesis, but it is not a confirmatory rescue of R26. R28, R29, TIER, learned matcher, RAD-DINO, frozen VLM, DIVE, and scale-up remain locked.

## Provenance

- Pairs audited: 170
- Protocol SHA-256: `08d235a5d645225e908bde03d635b795cf15743914c3cc3ae643a1368720f887`
- Frozen R26 commit: `8c2ea0b`
- Bootstrap: 10000 patient-only replicates, seed 20260726
