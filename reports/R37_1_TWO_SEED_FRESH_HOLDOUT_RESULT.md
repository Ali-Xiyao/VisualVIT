# R37.1 Two-Seed Fresh-Holdout Result

## Direct conclusion

R37.1 A6 Seeds 17 and 29 both completed successfully on the frozen fresh
patient holdout and passed every pre-registered initial gate:

- temporal-inversion consistency >= 0.90;
- static-state retention >= 0.99;
- true pair minus current-only >= +2 percentage points;
- true pair minus CMCP >= +2 percentage points.

The capacity-matched A0 Seeds 17 and 29 subsequently completed on the same
fresh holdout. The frozen 2,000-replicate patient-cluster bootstrap screen
passed A6 versus current-only, CMCP, and A0.

This is `PASS_R37_1_TWO_SEED_INTERNAL_SCREEN`: a **two-seed descriptive
internal PASS only**. It is not the registered final R37.1 scientific GO
because Seed 43 and the original three-seed gate were deliberately not run.

## Frozen cohort and execution

- Training roster: 10,287 patients, 39,491 finding-level examples.
- Fresh validation roster: 1,815 patients, 6,858 finding-level examples.
- Old R37 calibration patients: excluded before the R37.1 roster was frozen.
- Seeds: 17 and 29.
- A6 epochs/batch/LR/rank: 3 / 2 / 1e-4 / 32.
- A0 epochs/batch/LR: 100 / 16 / 0.01.
- A6 variant: frozen parameter-free Z2-equivariant logit projection.
- Validation was evaluated once on the frozen fresh roster.

The first A6 launch was interrupted by a Windows host reboot before either
seed wrote an output directory. After restart, only the stale zero-byte logs
and status files were archived, both GPUs were confirmed idle, and the
unchanged seed commands were relaunched. No model, loss, threshold, roster,
or seed choice changed.

## A6 descriptive results

| Metric | Frozen gate | Seed 17 | Seed 29 | Two-seed status |
|---|---:|---:|---:|---|
| Inversion consistency | >= 0.90 | 1.0000 | 1.0000 | PASS |
| State retention cosine | >= 0.99 | 0.9934 | 0.9929 | PASS |
| True-pair macro F1 | descriptive | 0.4680 | 0.4529 | — |
| Current-only macro F1 | descriptive | 0.1638 | 0.2007 | — |
| True minus current-only | >= +2 pp | +30.42 pp | +25.22 pp | PASS |
| True-pair CMCP-subset macro F1 | descriptive | 0.3534 | 0.3443 | — |
| CMCP-control macro F1 | descriptive | 0.2258 | 0.2304 | — |
| True minus CMCP | >= +2 pp | +12.76 pp | +11.39 pp | PASS |

The CMCP comparison covers 3,422 fresh-holdout finding rows in each seed.
Both seeds also passed the frozen-base/adapter-gradient engineering audit.

## Capacity-matched A0 and two-seed bootstrap screen

Both A0 probes cover the identical 1,815 patients and 6,858 finding rows.
Seed 17 A0 true-pair macro F1 is 0.3419 and Seed 29 is 0.3404.

| Comparison | Seed 17 | Seed 29 | Two-seed mean | Patient-bootstrap 95% CI | Screen |
|---|---:|---:|---:|---:|---|
| A6 minus current-only | +30.42 pp | +25.22 pp | +27.82 pp | [+25.96, +29.50] pp | PASS |
| A6 minus CMCP | +12.76 pp | +11.39 pp | +12.08 pp | [+10.61, +13.63] pp | PASS |
| A6 minus A0 | +12.62 pp | +11.25 pp | +11.93 pp | [+10.24, +13.66] pp | PASS |

Each screen requires both observed seed effects to be at least +2 pp and the
patient-bootstrap CI lower bound to be above zero. The bootstrap uses 2,000
patient-cluster replicates with frozen seed 37001. The CMCP comparison covers
1,296 patients and 3,422 rows; the other comparisons cover all 1,815 patients
and 6,858 rows.

## Firewall and provenance boundary

All result and launcher artifacts record:

- `protected_outcomes_read=false`;
- `sealed_test_read=false`;
- `gold_outcomes_read=false`;
- `source_hashes_recomputed=false`;
- `scientific_claim_allowed=false`.

No unchanged source or per-shard hash was recomputed. No 300-patient dev,
483-patient sealed test, or gold outcome was revealed.

## What is deliberately not claimed

The current evidence establishes only the reduced two-seed internal screen.
It does not establish the frozen three-seed survival gate. Therefore:

- do not call this final scientific GO;
- do not reveal protected outcomes;
- do not unlock R37C, R38, or R39;
- do not infer Seed 43 or the registered three-seed result from Seeds 17/29.

## Current stopping point

The user selected two seeds as sufficient for this stage. Seed 43, the
original three-seed aggregator, protected 300-dev/483-test/gold evaluation,
R37C, R38, and R39 remain untouched. Resume any of them only after new user
direction and a fresh authority check.
