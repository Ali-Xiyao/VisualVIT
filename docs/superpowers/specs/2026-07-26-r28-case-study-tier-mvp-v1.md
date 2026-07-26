# R28 Case-Study-Driven TIER MVP Protocol v1

Status: `FROZEN_BEFORE_EXECUTION`

Date: 2026-07-26

Evidence class: `NON_CONFIRMATORY_R28_DEVELOPMENT`

## 1. Question

Given frozen BiomedCLIP ROI features, can a label-free router combine current
state, global prior/current transition, and oracle-local transition experts
better than uniform expert fusion under nested patient-disjoint evaluation?

R28 is development evidence. R26/R27 and the R28 case study already used the
same 170 patients, so R28 cannot support a confirmatory or clinical claim.

## 2. Prerequisites

- R26 remains `STOP_C1`.
- R27 remains `C_SPARSE_HIGH_BII_SUPPORT`.
- The frozen R28 case registry is complete.
- Analysis-only case-oracle headroom over the best fixed consensus expert is at
  least `10 pp`, with patient-bootstrap lower bound above zero.
- R25.1 feature cache matches SHA-256
  `2a1df98fb3a3d0ef430698da7846b314a7cbcbe73c9e50f6241bfa57dc623326`.

## 3. Data and units

- Cohort: frozen R26 170 patients / 170 pairs / 774 entities.
- Labels: Improved, Stable, Worse.
- Independent cluster: patient/pair.
- Unit of prediction: qualification entity.
- Encoder: frozen R25.1 BiomedCLIP crop vectors; no image re-encoding.
- Execution: CPU only, to avoid unrelated workloads on both local GPUs.

## 4. Frozen representation construction

Every 768-dimensional crop vector is L2-normalized before composition.
Geometry is `[cx/224, cy/224, width/224, height/224]`.
An anatomy one-hot vocabulary is derived deterministically from the frozen
cohort labels and used by all experts.

To capacity-match the three differently sized raw representations and keep the
CPU experiment bounded, each raw expert input is passed through a deterministic
label-free signed random projection to 128 dimensions. Projection seed is
`20260728 + expert_index`; entries are Rademacher `{-1,+1}/sqrt(128)`.
The projection is generated from the frozen seed, is never fitted, and is
identical across folds and training seeds. All expert heads therefore receive
128 inputs and have identical parameter counts.

### State expert

Input:

`[current_target_visual, current_target_geometry, anatomy_onehot]`

### Global-transition expert

Input:

`[current_target_visual, mean_prior_visual, mean_current_visual,
mean_current-mean_prior, abs(mean_current-mean_prior),
mean_current*mean_prior, mean_prior_geometry, mean_current_geometry,
geometry_delta, anatomy_onehot]`

### Binding expert

Input:

`[prior_target_visual, current_target_visual,
current_target-prior_target, abs(current_target-prior_target),
current_target*prior_target, prior_target_geometry,
current_target_geometry, geometry_delta, anatomy_onehot]`

Each A1 expert is a non-affine LayerNorm plus Linear three-class head, matching
the R26 classifier family after the common 128-dimensional interface. A2
reuses the exact same expert logits.

## 5. Label-free router descriptors

The router may consume only:

- target prior/current cosine and L2 distance;
- global prior/current cosine and L2 distance;
- target-to-global current/prior cosine;
- target prior to all current regions: top-1 cosine and top-1/top-2 margin;
- target center displacement and log area ratio;
- number of regions and AP/PA view indicator;
- each inner-OOF expert's three logits, entropy, maximum probability, and
  top-1/top-2 probability margin.

Forbidden inputs:

- progression label;
- BII or BII stratum;
- case-study archetype;
- LPD/LCD or semantic-corruption flag;
- expert correctness;
- patient, study, DICOM, or qualification identifier.

## 6. Nested patient-OOF design

Outer evaluation:

- five deterministic patient folds;
- salt `r28-tier-outer-v1`;
- every outer test fold contains all three labels.

Within each outer fold and training seed:

1. split outer-training patients into four deterministic inner folds using salt
   `r28-tier-inner-v1-{outer_fold}`;
2. train each expert on inner-train and collect logits on inner-valid;
3. concatenate complete inner-OOF expert logits with label-free descriptors;
4. train the router on outer-training labels using only inner-OOF expert
   outputs;
5. refit each expert on the full outer-training patients;
6. generate expert logits once on the outer-test patients;
7. route outer-test logits without updating any parameter.

No entity from an outer-test patient may appear in expert or router training.

## 7. Registered attempts

Shared:

- training seeds: 17, 29, 43;
- expert steps: 300;
- router steps: 400;
- optimizer: AdamW;
- learning rate: 0.01;
- weight decay: `1e-4`;
- inverse-frequency cross entropy from the relevant training partition;
- deterministic PyTorch algorithms.

### A1 Linear TIER

- Router: non-affine LayerNorm plus Linear to three expert weights.
- Mixture: softmax router weights multiplied by expert logits.

### A2 Nonlinear TIER

May run only after A1 has:

- passed all engineering/leakage gates; and
- failed at least one scientific GO gate; and
- case-oracle headroom remains at least 10 pp.

Router: non-affine LayerNorm, Linear to 32, GELU, Linear to three weights.
Experts, folds, seeds, optimization budget, and evaluation remain unchanged.

## 8. Registered systems

- `state_expert`
- `global_expert`
- `binding_expert`
- `uniform_fusion` (arithmetic mean of the three expert logits)
- `tier_a1`
- conditional `tier_a2`

## 9. Metrics and inference

Primary comparison for each TIER attempt:

`patient-balanced macro F1(TIER) - patient-balanced macro F1(uniform_fusion)`

Report:

- patient-balanced and ordinary macro F1;
- balanced accuracy and per-class F1;
- per-seed direction;
- expert selection/mean router-weight distribution;
- patient-cluster × training-seed bootstrap, 10,000 replicates;
- train/test finite-fit audit;
- fold and leakage audit.

Scientific GO requires all:

- primary delta at least `+2 pp`;
- 95% bootstrap lower bound `> 0`;
- positive direction for all three seeds;
- inference valid;
- no outer/inner patient leakage;
- no forbidden router field;
- no more than `1 pp` degradation versus the strongest single expert.

Engineering success requires:

- complete predictions for 774 entities × 3 seeds;
- all folds nonempty with three-label training support;
- all losses/logits finite;
- deterministic fresh-process reproduction;
- complete hashes and manifest.

## 10. Sanity gates

Before outer OOF execution:

1. representation shapes and finite values;
2. anatomy vocabulary and observation IDs deterministic;
3. toy router separates synthetic expert regimes;
4. tiny train-only slice can overfit;
5. shuffled-label control does not pass the tiny-overfit threshold on held-out
   patients;
6. explicit forbidden-field scan;
7. outer/inner patient-disjoint audits.

## 11. Stop and mutation rules

- If case-oracle headroom prerequisite fails, do not train TIER.
- If A1 engineering fails, repair A1 implementation without opening A2.
- If A1 engineering passes but scientific GO fails, freeze its result before
  running A2.
- If A2 also fails scientific GO, stop structured TIER scale-up.
- A3 report-supervised transition repair requires a separate protocol, legal
  report source, and image-only inference boundary. It is not automatically
  authorized by an A2 failure.
- Do not change thresholds, folds, seeds, labels, or bootstrap after results.
- Do not start frozen VLM, DIVE, RAD-DINO, or scale-up from R28.

## 12. Required outputs

Runtime root:
`F:\VisualVIT_runtime\050_routeC\r28_case_study_tier\tier_mvp_v1`

- `feature_manifest.json`
- `folds.json`
- `sanity_audit.json`
- `predictions.json`
- `fit_audit.json`
- `router_audit.json`
- `bootstrap.json`
- `attempt_closure.json`
- `artifact_manifest.json`

Repository outputs:

- `reports/R28_TIER_MVP_RESULT.md`
- implementation, verifier, and tests listed in `task_plan.md`.
