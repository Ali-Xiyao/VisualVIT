# R37.1 Two-Seed Fresh-Holdout Result

## Direct conclusion

R37.1 Seeds 17 and 29 both completed successfully on the frozen fresh
patient holdout and passed every pre-registered initial gate:

- temporal-inversion consistency >= 0.90;
- static-state retention >= 0.99;
- true pair minus current-only >= +2 percentage points;
- true pair minus CMCP >= +2 percentage points.

This is a **two-seed descriptive PASS only**. It is not the final R37.1
scientific GO because Seed 43, the capacity-matched A0 baseline, and the
2,000-replicate patient-cluster bootstrap were not run. The user paused all
downstream execution after reviewing this two-seed result.

## Frozen cohort and execution

- Training roster: 10,287 patients, 39,491 finding-level examples.
- Fresh validation roster: 1,815 patients, 6,858 finding-level examples.
- Old R37 calibration patients: excluded before the R37.1 roster was frozen.
- Seeds: 17 and 29.
- Epochs: 3.
- Batch size: 2.
- Learning rate: 1e-4.
- Adapter rank: 32.
- Variant: A6 with the frozen parameter-free Z2-equivariant logit projection.
- Validation was evaluated once on the frozen fresh roster.

The first launch was interrupted by a Windows host reboot before either seed
wrote an output directory. After restart, only the stale zero-byte logs and
status files were archived, both GPUs were confirmed idle, and the unchanged
seed commands were relaunched. No model, loss, threshold, roster, or seed
choice changed.

## Descriptive results

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

## Firewall and provenance boundary

Both result and launcher artifacts record:

- `protected_outcomes_read=false`;
- `sealed_test_read=false`;
- `gold_outcomes_read=false`;
- `source_hashes_recomputed=false`;
- `scientific_claim_allowed=false`.

No unchanged source or per-shard hash was recomputed. No 300-patient dev,
483-patient sealed test, or gold outcome was revealed.

## What is deliberately not claimed

The current evidence does not establish the frozen three-seed survival gate,
patient-bootstrap confidence intervals, or A6-versus-A0 superiority.
Therefore:

- do not call this final scientific GO;
- do not reveal protected outcomes;
- do not unlock R37C, R38, or R39;
- do not infer Seed 43 or bootstrap behavior from Seeds 17 and 29.

## Paused next stage

The code path for explicit R37.1 A0 schemas/roster checks, Seed 43 admission,
and R37.1 aggregation was prepared and passed focused tests, but no downstream
GPU process was started. Resume only after new user direction, beginning with
fresh-output, duplicate-process, GPU-idle, and firewall checks.
