# CAPES-CI v1 Method Calibration Protocol

Date: 2026-07-19  
Evidence class: `ENGINEERING_CALIBRATION_NON_CONFIRMATORY`  
Formal test: `SEALED`

## Purpose

Calibrate CAPES-CI by isolating why identity/null transport succeeds or fails before any broad main table. Synthetic calibration may select one preregistered rescue and determine the safe operating envelope; it cannot establish a paper claim or parameterize formal power.

## Fixed comparison contract

Every applicable row shares:

- the same prior/current frozen region features and anatomy support;
- the same assignment-independent selected support and `AllocationPlan`;
- physical `4 global + 28 entity + 28 relation + 4 reserved = 64` tokens;
- the same projector, frozen VLM, prompt, five-label likelihood and label order;
- the same initialization policy, optimizer, steps, samples/order and seed;
- the same parameter and tuning-trial budget where the row is trainable.

Only the matching/fusion operator and the resulting relation-token values may change. Deterministic solvers remain parameter-free. Gold entity IDs/cardinality are forbidden from learned and baseline inputs.

## Core systems

1. `B4a`: anatomy-compatible zero-fixed-point persistent-endpoint derangement; null sets fixed.
2. `B4b`: oracle persistent endpoints; null sets fixed.
3. `CAPES-CI learned`: two-sided-null sub-stochastic transport, no oracle cardinality.
4. `Hungarian+reject`: exact assignment plus one development-frozen reject threshold.
5. `Balanced Sinkhorn`: identical cost/support, uniform balanced marginals, no null mass.
6. `Current-only` and `equal-budget concat`: input/fusion controls.
7. `ProTrans-style transition` and `Libra/TAC-style fusion`: clean-room controlled adaptations, activated only after the core grid is green.

No unlicensed upstream implementation is copied. Full ProTrans/Libra systems are not presented as compute-matched rows.

## One-factor-at-a-time grid

The anchor configuration is frozen before the grid. Change exactly one axis per experiment:

| Axis | Anchor | Diagnostic values | Failure interpretation |
|---|---:|---|---|
| identity signal/noise | medium | strong, medium, weak | matcher lacks identity evidence or overuses state |
| progression magnitude | medium | small, medium, large | relation representation lacks change sensitivity |
| birth/death fraction | 20% | 0%, 10%, 20%, 40% | null calibration or balanced-baseline mismatch |
| anatomy corruption | 0% | 0%, 10%, 25% | anatomy support too brittle or leaks identity |
| entity count | 8 | 1, 8, 28, 29, 58, >100 | allocation/overflow failure |
| padding/missingness | 0% | 0%, 10%, 30% | masked mass or physical/logical-token confusion |
| label prevalence | balanced | balanced, long-tail | macro-F1/calibration instability |
| temporal order | forward | forward, reversed | direction representation failure |

The master training-seed order is `[17, 29, 43, 71, 101, 137, 181, 233]`. Engineering calibration initially uses the first three seeds; bad seeds are never removed. Derangement seeds are independently namespaced and fixed before each registered grid.

## Metrics

- persistent assignment precision/recall/F1;
- birth and death precision/recall/F1;
- row/column feasibility and nonnegative-mass residuals;
- five-label patient/case-balanced macro F1;
- `Delta_bind = 100 * (M_B4b - M_B4a)`;
- `Recovery = (M_learned - M_B4a) / (M_B4b - M_B4a)` only with a qualified positive denominator;
- intervention score change for assignment swap, null deletion and temporal reversal;
- exact token count/mask/position/frozen-parameter audits;
- trainable parameters, steps, wall time and peak CPU/GPU/VRAM.

## Engineering survival criteria

On the anchor configuration across all first three training seeds:

1. all feasibility, finite-value, exact-64, no-pixel and frozen-VLM audits pass;
2. B4 denominator is positive for every seed and aggregate `Delta_bind >= 5 pp`;
3. learned Recovery point estimate is at least 0.60;
4. removing persistent identity reduces assignment F1 and five-label macro F1 with no seed-level sign reversal;
5. removing two-sided null mass reduces birth/death F1 with no seed-level sign reversal;
6. assignment and null interventions change frozen-VLM scores, while assignment-independent token permutation does not create an equivalent effect;
7. independent-process reproduction matches all registered non-runtime fields.

These are survival criteria, not confirmatory significance tests. If any fails, broad baseline/ablation scaling remains locked.

## Diagnostic decision tree

- `B4b` does not outperform `B4a`: the dataset/interface does not identify binding; stop and repair B4 support/labels before changing CAPES-CI.
- `B4` positive but learned Recovery below 0.40: diagnose cost/support/null parameterization; no rescue menu search.
- Recovery 0.40 to below 0.60 with all audits green: run exactly the preregistered single rescue.
- identity ablation has no effect: verify features contain entity information and that relation tokens are actually consumed.
- null ablation has no effect: stratify by true birth/death support and audit null-mass gradients.
- strong synthetic but weak real train/dev: inspect domain shift, annotation mapping, region extraction and prevalence before changing the main method.
- one seed fails: retain it; inspect optimization and data order. Rerun only verified infrastructure failures under the identical seed/config.

## Run order

1. Unit/property tests for baseline, statistics and lineage implementations.
2. Three-seed synthetic anchor with B4a/B4b/learned/core baselines.
3. A1 identity and A2 null ablations only.
4. One-factor stress grid to locate failure boundaries.
5. Freeze one rescue if and only if the grey-zone rule is triggered.
6. Qualify legal gold data and cross-source lineage.
7. Reuse the identical registered systems on real train/dev (S080).
8. Only after S080 and power freeze, unlock full baselines, A1-A10 and formal test.

## Evidence contract

Each run records purpose, expected discriminating outcome, source/config/data/model hashes, seed namespaces, command, host/job/step, logs, checkpoint, raw predictions, metrics, gate decision, failure cases, analysis and next action. Failed attempts are preserved and never overwritten.
