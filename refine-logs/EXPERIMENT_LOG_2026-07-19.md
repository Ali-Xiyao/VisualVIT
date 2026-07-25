# Experiment Log: 2026-07-19

## Goal of this cycle

Move CAPES-CI from component smoke to a reproducible real-data mechanism pilot without opening formal test data. Prove the exact-64 frozen-VLM path, implement honest core baselines/statistics/lineage, find the legal gold-data boundary and calibrate only through registered single-variable experiments.

## Experiment S051: current adapter-contract synthetic refresh

### Purpose

Determine whether the integrated synthetic chain still runs after the Qwen adapter began forcing `use_cache=False` and `logits_to_keep=0`. Expected outcome: two fresh processes pass exactly; otherwise S050 is stale and downstream scaling stops.

### Setting

- Data: 15 balanced five-label synthetic cases plus their 15 mapped time reversals.
- Code change: toy frozen causal LM explicitly accepts and validates no-cache/full-logits arguments.
- Seed/data seed: 17 / 3401.
- Feature/hidden width: 12 / 32.
- Training: 500 AdamW steps, learning rate 0.02, CPU.
- Evidence: `SURVIVAL_SYNTHETIC_NON_CONFIRMATORY`.

### Results

- Two independent Python processes: PASS.
- Original and time-reversed accuracy: 1.00 / 1.00 in both.
- Assignment/null intervention mean absolute score change: 0.1971480995 / 0.0962375551.
- State SHA256 in both: `41ec423af8e348a7a5bfc68f1e1b3ff30fbaec4e3097773042b202713d7b25a3`.
- Reproduction verifier: config, targets, predictions, state and all non-runtime metrics exactly equal.

### Analysis

The current adapter contract does not break the integrated learned-soft path. The issue was an executable-signature regression, not a method change. This result cannot establish real B4/Recovery because the labels and entity identity are synthetic.

### Next Steps

- [x] Preserve both runs and verifier.
- [ ] Run the registered three-seed core calibration only after strict no-null Sinkhorn and statistics implementations pass review.
- [ ] Do not scale to formal data until D010/D020 pass.

## Experiments S060/S070: server and real Qwen survival

### Purpose

Verify the SHA-pinned implementation on CPU/A800 and prove that a real Qwen3-VL consumes exactly 64 relation embeddings without pixels.

### Setting

- Allocation: `4161 / tpami / gpu01`, A800 80GB, retained after child steps.
- Environment: `dsr_stage2_gpu`, torch 2.11.0+cu128, transformers 5.13.1.
- Qwen: local Qwen3-VL-4B-Instruct, BF16, fully frozen.
- Source: versioned focused archives with per-file SHA256 manifests.

### Results

- S060 CPU: 75 pass + one CUDA-only skip; A800: 76/76 pass.
- S070 attempt 1: fail-closed FP32/BF16 projector input mismatch; preserved.
- S070 fixed-source attempt + independent reproduction: PASS, registered-field mismatch count zero.
- Exact placeholders=64, no pixel/image/video path, model trainable parameters=0.
- Relation intervention mean absolute likelihood-score change: 0.0991658196.
- Parent 4161 remained RUNNING; only `4161.batch` remained.

### Analysis

The real frozen-Qwen interface is executable and sensitive to relation-token content. It does not show that the tokens encode correct real longitudinal identity. The failed dtype attempt is an infrastructure failure and was rerun under the same seed after a source-hashed correction.

### Next Steps

- [x] Preserve failed/pass/reproduction artifacts.
- [x] Harden cache/logits/multimodal bypass rejection.
- [ ] Reuse the interface unchanged for S080 after legal data qualification.

## Data qualification diagnostic D010

### Purpose

Identify a legally usable cohort where five-label targets and nontrivial persistent endpoint identity coexist at the same entity unit.

### Setting

- Read-only local/remote inventory.
- No credentials, restricted downloads or test labels exposed.
- Exact official source/version/license/DUA and patient/study/image/hash lineage required.

### Results

- Existing: MIMIC images/reports, official metadata/split/CheXpert/NegBio files, and a MAVL-derived 220,736×51×75 landmark-observation matrix.
- Missing on current disk/server: CheXTemporal, MS-CXR-T and Chest ImaGenome official directories.
- MAVL JSON contains image/text paths and label IDs but no longitudinal pair/entity link/five-label temporal target.

### Analysis

Existing MIMIC/MAVL surfaces can support lineage, visual representation pretraining or weak supervision but cannot alone identify C1/C2. A fine anatomy identifier cannot be both visible to the matcher and used as the oracle identity; the real-data contract now separates coarse compatibility from fine gold identity.

### Next Steps

- [ ] Complete first-party CheXTemporal/MS-CXR-T/Chest ImaGenome/MAVL access and license audit.
- [ ] Run the fail-closed data qualification tool on official metadata.
- [ ] Ask only for authorization state, never credentials, if credentialed sources are still required.

## Experiments S075/S076: registered three-seed synthetic calibration

### Purpose

Test whether identity binding creates a stable five-label downstream effect before spending real-data/GPU budget. The registered gate requires a positive B4 denominator in every seed, mean Delta_bind at least 5 pp, learned Recovery at least 0.60, correct A1/A2 direction, and exact independent-process reproduction.

### Setting

- Seeds `[17,29,43]`; train/inner-development/development data seeds `3401/4401/5401`.
- Five balanced labels; 80 steps; AdamW learning rate 0.02; CPU.
- Strict no-null balanced Sinkhorn with epsilon 0.25 and 2,048 iterations.
- B4a/B4b separately trained from the same initialization; only assignment and its downstream values may differ.
- Exact 64-token, no-pixel, frozen-VLM path; engineering `D=1`, not formal `D>=3`.

### Results

- All technical audits and per-system execution checks: PASS.
- Per-seed Delta_bind: `+8.9524`, `-4.6190`, `+3.5714` pp; mean `+2.6349` pp.
- Mean B4a/B4b/learned-soft macro-F1: `0.1183/0.1446/0.0915`.
- Recovery: undefined for seed29; values `-0.1418/0.4400` for the two positive denominators; qualified-seed mean `0.1491`.
- A1/A2 expected direction was not stable across all seeds.
- S075 verdict: `FAIL_MECHANISM_GATE`.
- Fresh independent-process reproduction: PASS; registered mismatch count zero; canonical SHA256 `a8117be52f57e18b09eacbd6b394575c3a9047b6cb533bacf8ad194779811079`.

### Analysis

This is a deterministic method-signal failure, not an infrastructure failure. The learned-method rescue is ineligible because the B4 denominator is not qualified. Per the registered decision tree, the anchor's support/labels and downstream identifiability must be audited before changing CAPES-CI or launching a wide grid.

### Next Steps

- [x] Preserve main/reproduction summaries and exact verifier.
- [x] Keep formal test sealed and broad scaling locked.
- [ ] Diagnose B4 task identifiability, training dynamics and A1/A2 intervention semantics.
- [ ] Make at most one-factor-at-a-time anchor corrections with new run IDs; never overwrite S075.

## Experiments S078-D1/S078-D2: fixed-decoder and competence ladder

### Purpose

Separate frozen-toy-VLM seed variance from absolute training/readout incompetence without changing S075 or touching the sealed formal test.

### Results

- D1 fixed frozen toy-VLM seed `91001`; all technical checks passed.
- D1 development five-label B4 gap values were `+6.8889/-8.0000/+4.4444` pp (mean `+1.1111` pp), so fixed-decoder initialization did not stabilize the legacy anchor.
- A fresh D1 process reproduced every registered non-runtime field exactly; mismatch count `0`, canonical registered SHA256 `bd9ea37a51f723b5da952f73a9843806f3208de257b62a069a7f81d120e533b5`.
- D2 changed the optimization budget from 80 to 500 steps. Technical execution passed, but B4b train five-label macro-F1 was `0.7333/0.4667/1.0000` across seeds `[17,29,43]`.
- D2 status is `NOT_EVALUABLE_READOUT_INCOMPETENT`; development legacy five-label gap was `-16.6667/-23.3333/+10.0000` pp (mean `-10.0000` pp).
- The registered D3 eligibility rule requires every seed to reach B4b train five-label macro-F1 `>=0.80`. D3 was therefore not run.

### Analysis

Increasing steps does not establish a competent working-oracle readout. The S078 metrics are explicitly legacy five-label diagnostics and are not the persistent-only v2 estimand. A code red-team also found that the query-conditioned module is currently structural only: it lacks a production-path exact-64 runner, equal-budget train/development marginal controls over all visible channels, and complete `(training_seed, derangement_id)` gate aggregation.

### Next Steps

- [x] Stop at D2; do not run D3.
- [ ] Replace the incompetent engineering readout under a separately frozen protocol before any mechanism estimate.
- [ ] Complete and red-team the query-anchor production runner before training it.
- [ ] Preserve S075 and S078 artifacts as negative results.

## D010 pinned CheXTemporal annotation audit

### Results

- Downloaded the public annotation release at commit `81fd9cdd9b1208d8f8bd39d7a914c9b72fed8d79`; both parquet hashes match the preregistered values.
- The progression table has 1,787 rows and the bbox table has 1,565 rows / 4,702 boxes. The 1,565 bbox rows equal all non-edema rows; README's 1,562 count is documentation drift.
- 258 full prediction keys retain multiple progression targets, covering 548/1,787 rows. The deterministic single-label ceiling at that grain is `1497/1787 = 0.8377168439`.
- The released bbox rows repeat the same set-level box payload across conflicting progression rows and do not expose per-box progression, so they cannot identify the registered B4 entity-level oracle.

### Decision

Public annotations and their license/provenance are qualified, but D010 remains `HOLD_SCHEMA`; D020, S080 and formal main/ablation remain locked. No model evaluation was performed on gold rows and the formal test remains sealed.
