# CAPES-CI Three-Seed Engineering Calibration Results

Date: 2026-07-19  
Evidence class: `ENGINEERING_CALIBRATION_NONCONFIRMATORY`  
Formal claim allowed: **No**  
Formal test: **SEALED**

## Outcome

The registered synthetic anchor executed correctly and reproduced exactly, but the mechanism gate **failed**. The current anchor therefore does not justify a real-data main-table launch or formal ablation scaling.

All technical safeguards passed: every system completed, the B4a/B4b comparison preserved the same initialization/input/allocation/prompt/optimizer/steps/seed while changing only assignment and its downstream values, the exact-64/no-pixel/frozen-VLM audit passed, strict balanced Sinkhorn was feasible for every case, and no oracle cardinality argument entered learned or baseline APIs.

## Locked setting

- Training seeds: `[17, 29, 43]`.
- Data seeds: train `3401`, inner-development `4401`, development `5401`.
- Five balanced progression labels; 10 train, 5 inner-development and 10 development cases.
- Feature/hidden width: 12/16.
- Training: 80 AdamW steps, learning rate 0.02, fixed full-batch order.
- Balanced Sinkhorn: epsilon 0.25, 2,048 iterations, strict `1e-6` feasibility semantics.
- B4 engineering derangements: `D=1`; formal protocol still requires `D>=3`.
- Physical token contract: `4 + 28 + 28 + 4 = 64`; no pixels; frozen toy VLM likelihood path.
- Config SHA256: `0594e2cef993190eb2a9c249580c7db19c30225e2e994b24236c5a51324478f6`.
- Source-manifest SHA256: `7a3c6cdc52adf2f1ca13a5793316dcf70127f32918fcd7e5c75d7d41268e005f`.

## Primary mechanism results

| Seed | B4a deranged macro-F1 | B4b oracle macro-F1 | Learned-soft macro-F1 | Delta_bind (pp) | Recovery |
|---:|---:|---:|---:|---:|---:|
| 17 | 0.0571 | 0.1467 | 0.0444 | +8.9524 | -0.1418 |
| 29 | 0.1833 | 0.1371 | 0.1000 | -4.6190 | undefined; denominator nonpositive |
| 43 | 0.1143 | 0.1500 | 0.1300 | +3.5714 | 0.4400 |
| Mean | 0.1183 | 0.1446 | 0.0915 | **+2.6349** | 0.1491 over two positive denominators |

Gate failures:

- Delta_bind was not positive for every seed.
- Mean Delta_bind was below the registered 5 pp threshold.
- Recovery was not qualified for every seed and its qualified-seed mean was below 0.60.
- A1 identity masking and A2 null deletion did not have the expected direction in every seed.

The deterministic baseline means were 0.1446 for Hungarian+development-frozen reject and 0.1578 for strict balanced Sinkhorn. Learned-hard mean macro-F1 was 0.1019. These are engineering diagnostics, not formal baseline results.

## Intervention diagnostics

| Seed | A1 identity-masking macro-F1 change | A2 null-deletion macro-F1 change |
|---:|---:|---:|
| 17 | +0.0222 | -0.0133 |
| 29 | -0.0333 | -0.0571 |
| 43 | +0.2922 | 0.0000 |

A1/A2 are explicitly classified as input/engineering interventions in this anchor. They are excluded from Delta_bind and Recovery and cannot be cited as formal ablations.

## Independent-process reproduction

The complete three-seed run was repeated in a fresh Python process under the identical configuration. A dedicated verifier recursively removed only the registered runtime-only key `walltime_seconds` and compared every remaining field.

- Reproduction status: **PASS**.
- Registered mismatch count: `0`.
- Registered canonical SHA256 for both runs: `a8117be52f57e18b09eacbd6b394575c3a9047b6cb533bacf8ad194779811079`.
- First summary SHA256: `6a465a2d92c4d9b5061983b6fa12b0610a614f915dfdb022d9d2d09a977780b4`.
- Second summary SHA256: `80c43d64c42de68d4b396c65a3ca1c08785eda5f67cf700673279d895e6fb6eb`.

The raw summary hashes differ only because wall times are recorded; all registered non-runtime data, predictions, metrics, states, source hashes and gate decisions are exact.

## Decision

Per `refine-logs/CALIBRATION_PROTOCOL_2026-07-19.md`, this is a fail-closed mechanism result rather than an infrastructure failure. Broad baselines, formal ablations, real main experiments and sealed test remain locked. The next admissible action is to diagnose whether the anchor labels/interface genuinely require persistent identity binding and whether the low downstream five-label performance is caused by task identifiability or optimization. The learned-method single rescue is **not eligible** because the B4 denominator itself is not qualified.

## Post-failure diagnosis

Three independent read-only audits converged on the following explanation:

1. **Assignment-independent bypass:** the v1 label state changes enter the 4 global and 28 entity token payloads directly. B4a can therefore infer single-timepoint state marginals without using the corrupted persistent relation. Correct B4b/Hungarian assignment F1 was 1.0, but B4b five-label macro-F1 stayed near chance, so the anchor never established a working downstream oracle.
2. **Frozen-decoder seed confound:** training seed 17/29/43 also initialized a different random frozen toy VLM. Real frozen checkpoints do not change across training seeds; v1 therefore mixed trainable initialization variance with decoder variance.
3. **Underpowered/undertrained readout:** only 10 training and 10 development cases with 80 full-batch steps left final CE high. More steps alone cannot repair the information bypass, but competence must be established before estimating a mechanism.
4. **Manipulation mismatch:** `A1_identity_masking` changes matcher real-edge evidence, null heads, entity/relation content and downstream nuisance features together. `A2_null_deletion` is an oracle inference-time collapse. Neither is a matched trained ablation, and the implemented gate checked overall label macro-F1 direction rather than the protocol's component-local manipulation checks.

Accordingly, S075 remains failed and non-evaluable as evidence about the full method. A new frozen v2 protocol (`refine-logs/CALIBRATION_PROTOCOL_V2_2026-07-19.md`) separates three one-factor diagnostics, fixes the decoder seed, requires a competent B4b oracle, decomposes persistent/null metrics, and defines a query-gated relation-mediator anchor with hidden-ID invariance and crossed `D=3`. Passing that controlled anchor will still require a separate full-token train/dev bridge before a CAPES-CI main-method claim.

## Evidence

- `artifacts/calibration/capes_ci_anchor_20260719T1407_main/summary.json`
- `artifacts/calibration/capes_ci_anchor_20260719T1410_repro/summary.json`
- `artifacts/calibration/capes_ci_anchor_20260719_reproduction.json`
- `scripts/run_synthetic_calibration_grid.py`
- `scripts/verify_synthetic_calibration_reproduction.py`
