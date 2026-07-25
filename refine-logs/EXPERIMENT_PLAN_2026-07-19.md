# Experiment Plan: CAPES-CI v1

**Date**: 2026-07-19  
**Method**: Causally Identified Persistent Entity Transport Tokenizer  
**Design authority**: `docs/superpowers/specs/2026-07-19-capes-ci-v1.md`  
**Execution target**: retained Slurm allocation `4161 / tpami / gpu01`  
**Current gate**: `GO_IMPLEMENTATION_AND_SURVIVAL_ONLY + NO_GO_FORMAL_TEST_REVEAL + NO_GO_MAIN_CLAIM`

## Claims

| ID | Claim | Primary evidence | Success boundary |
|---|---|---|---|
| C1 | Correct persistent endpoint assignment is an active component under a strictly isomorphic VLM interface | real gold B4b minus B4a | pilot-frozen minimum effect, point estimate currently targeted at >=5 pp and patient-cluster 95% CI lower >0 |
| C2 | Oracle-free two-sided-null transport recovers the assignment effect | learned vs B4a relative to B4b | oracle-gap CI >0; Recovery >=0.60 feasible, >=0.70 strong |
| C3 | The recovered structure changes a frozen VLM rather than only a classifier | exact 64-placeholder relation-token likelihood | preregistered learned-vs-B4a gain with CI lower >0 and intervention sensitivity |
| C4 | The mechanism is not a token-count, transition-only, report-prior or source-boundary artifact | strong baselines, ablations, image-dependence interventions, external transfer | registered ablation directions and uncontaminated replication |

Anti-claims: no clinical causal effect; no first partial OT/dustbin/relational-token claim; no universal optimality of 64 tokens; no formal conclusion from synthetic or report-derived proxy results.

## Data governance

1. Train/dev/test unit is patient; external sources require patient/study/image/hash lineage.
2. MIMIC-CXR-derived datasets are not independent merely because their dataset names differ.
3. Report-derived annotations/features may be used only under a declared weak-supervision protocol and cannot leak target temporal conclusions into image-only evaluation.
4. Formal test labels/outcomes/predictions/metrics remain sealed until code, hyperparameters, seeds, minimum effect, statistics and external identity are signed.
5. Credentialed PhysioNet assets require existing authorized access and DUA compliance; no credential bypass or credential output.
6. Every downloaded asset needs official URL, version/revision, license, byte size and SHA256.

## Survival gates

| Run ID | Gate | Input | Required check | Status |
|---|---|---|---|---|
| S000 | historical regression | current workspace | all 21 legacy tests pass | PASS 2026-07-19 |
| S010 | schema closure | synthetic tensors | backward compatibility, optional metadata validation, no gold-field learned access | PASS 2026-07-19 |
| S020 | soft/null math | enumerated synthetic cases | finite gradients, exact mass, padding/anatomy masks, permutation equivariance | PASS 2026-07-19 |
| S021 | hardening | enumerated micro cases | globally optimal optional assignment, deterministic ties, null when cheaper | PASS 2026-07-19 |
| S030 | allocator | N=0/1/28/29/58/>100 | exact source mass, top27+overflow, deterministic/permutation-stable, B4 shared plan | PASS 2026-07-19 |
| S040 | projector/adapter unit | toy frozen LM | exact 64 replacements, neutral fill, 3-axis positions, label likelihood, no pixels | PASS 2026-07-19 |
| S050 | integrated synthetic | full CAPES-CI chain | five-label overfit, order swap, intervention-logit response, two-process reproduction | PASS 2026-07-19 |
| S060 | server CPU/GPU | focused SHA payload on 4161 | compile/tests, CPU/GPU determinism, no NaN/Inf | PASS 2026-07-19 |
| S070 | Qwen relation-token smoke | Qwen2-VL or qualified Qwen3-VL | no pixel inputs; 64 placeholder replacement; frozen audit; finite label scores | PASS Qwen3-VL-4B 2026-07-19 |
| S080 | real train/dev mechanism pilot | legal gold annotations | stable B4 gap, learned nonzero recovery, no test reveal | LOCKED |

Stop at the first failed gate. One documented rescue per gate is allowed; blind seed/model/data expansion is prohibited.

## Main systems

All applicable systems share encoder features, selected support, token budget, projector, frozen VLM, prompt, label scoring, training steps and tuning budget.

| Family | Systems |
|---|---|
| Input controls | current-only; prior/current equal-budget concat; mean/difference; uniform/random pooling |
| Longitudinal | ProTrans-style directional transition; Med-ST/MLRG/Libra equivalents where official code/data license permits |
| Matching | cosine Hungarian+reject; balanced Sinkhorn; SuperGlue-style dustbin; feasible POT; oracle; anatomy deranged; wrong-anatomy; random |
| Main | CAPES-CI learned soft/null; CAPES-CI hardened inference |
| Token interface | delimiter scaling; independent Q-Former/Perceiver compression; deterministic fixed allocator |
| Negative controls | null-count-preserving shuffle; endpoint permutation; assignment-independent token permutation; same-label patient swap |

Citation-only systems are not presented as reproduced baselines. Any adapted/equivalent implementation is labeled as such.

## Mandatory ablations

| ID | Removal/change | Registered interpretation |
|---|---|---|
| A1 | no persistent identity | tests identity-specific contribution |
| A2 | no birth/death mass | tests two-sided-null contribution |
| A3 | no directional change feature | tests transition representation |
| A4 | no time direction / order encoding | tests directional semantics |
| A5 | no reverse/cycle consistency | tests training constraint |
| A6 | deterministic vs learned allocator | tests allocation complexity without changing support budget |
| A7 | token budget 32/64/96 | 64 is a matched operating point, not a universal optimum |
| A8 | projector linear vs MLP | tests adapter capacity |
| A9 | second encoder | tests vision-backbone transfer |
| A10 | second frozen VLM | tests decoder/interface transfer |

A key ablation is considered established only if its registered direction holds across the preregistered seeds and its patient-cluster interval excludes the no-effect boundary for confirmatory claims.

## B4 isomorphism

B4a is anatomy-compatible zero-fixed-point derangement of persistent endpoints. B4b uses oracle persistent endpoints. Birth/death sets are unchanged.

Before training, an automated audit must show equality of:
- raw feature and observation-metadata hashes;
- selected support and AllocationPlan;
- token layout/type/order/physical attention mask;
- prompt/input IDs/placeholder mask/position IDs;
- parameter initialization, trainable/frozen map and optimizer contract;
- training samples/order/steps and random seeds.

Only assignment hash and its downstream relation values may differ. Null-specific interventions are separate from B4.

## Statistical protocol

- Primary unit: patient; source-content cluster for non-medical external tasks.
- Primary endpoint: patient-balanced macro five-label Change F1 unless the gold dataset only supports three labels, in which case the dataset-specific endpoint is declared secondary and cannot replace the five-label main endpoint.
- Inference: patient-cluster paired bootstrap with 10,000 resamples; training and derangement seeds represented hierarchically.
- Report effect sizes and 95% CIs; no uncorrected OR success rule.
- Learned Recovery is undefined if the oracle denominator CI includes zero.
- Primary claim hierarchy: C1 -> C2 -> C3 -> C4; exploratory families use BH-FDR.
- Scaling-null requires a preregistered equivalence margin and TOST/90% CI; `p>0.05` is not equivalence.
- Pilot uses train/dev only to simulate power and freeze 3–5 training seeds, derangement seeds, sample size, minimum effect and the single rescue rule.

Historical synthetic F1 and invalid MIMIC proxy variation cannot parameterize formal power because they lack the formal data-generating unit and end-to-end VLM path.

## Formal run order

1. Complete S010–S050 locally.
2. Sync and verify focused payload; run S060–S070 as child steps in 4161.
3. Qualify legal annotations/weights and freeze lineage/splits.
4. Run S080 on train/dev; freeze power and protocol.
5. Execute main systems and mandatory ablations on train/dev.
6. Sign configs/checkpoints/manifests, reveal formal test once.
7. Run external replication without adapting to internal test outcomes.
8. Run hierarchical statistics, compute audit and failure analysis.
9. Freeze tables/figures and a submission-grade reproducibility package.

## Evidence requirements

Every run must record run ID, evidence class, git-or-source SHA256 manifest, command, config, seeds, host/job/step, environment, data/checkpoint hashes, stdout/stderr, start/end time, exit status, metrics, VRAM/CPU/RAM, and fail-closed gate result. Failed runs remain in the tracker.

The parent allocation 4161 must remain RUNNING. Only child steps created by this project may be terminated.
