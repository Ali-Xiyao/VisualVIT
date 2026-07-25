# CAPES-CI Formal Statistical Protocol

Status: **preregisterable draft; formal test remains sealed**  
Authority date: 2026-07-19  
Applies to: CAPES-CI v1 five-label region/entity progression experiments

## 1. Mandatory design correction

The mechanism pilot must use at least three training seeds. A one-training-seed pilot cannot estimate between-seed variance because resampling a singleton always yields zero seed variance. The ordered seed bank is:

`[17, 29, 43, 71, 101, 137, 181, 233]`

Use the first three seeds initially. Expand to the first five only when the preregistered power rule requires it. A low-performing seed cannot be removed or replaced. Use at least three independently namespaced derangement seeds and freeze their exact values and generation algorithm.

## 2. Primary endpoint

The fixed label order is:

`stable`, `worse`, `improved`, `new`, `resolved`.

Missing or uncertain labels are masked, never converted to negatives. Within each patient, valid entity/query weights sum to one. Compute weighted TP, FP and FN for each class, then macro-average the five class F1 values:

`M = (1/5) sum_c F1_c`.

If a formal-test class has no valid support, the primary endpoint is not computable. Classes cannot be merged after test reveal. A three-label dataset is secondary and cannot substitute for this endpoint.

Compute each training-seed/derangement metric separately and average seed-level metrics. Do not pool patient x training-seed x derangement rows as independent observations.

## 3. Confirmatory estimands and gates

### C1: assignment effect

`Delta_bind = 100 * (M_B4b - M_B4a)` percentage points.

C1 passes only when both conditions hold:

1. point estimate is at least the signed minimum relevant effect, currently a 5.0 pp candidate;
2. paired hierarchical-bootstrap 95% CI lower bound is greater than zero.

The final minimum effect must be signed before formal test and cannot be lowered after pilot results are known.

### C2: learned Recovery

`G = M_B4b - M_B4a`  
`N_R = M_learned - M_B4a`  
`Recovery = N_R / G`

Recovery is not clipped. It is defined only if the 95% CI for `G` is wholly above zero and at least 95% of bootstrap replicates have `G > 0`. Otherwise C2 is untestable, not zero.

- Strong success: point estimate and 95% lower bound are both at least 0.70.
- Feasible success: point estimate and 95% lower bound are both at least 0.60.
- Pilot grey zone: point estimate 0.40 to below 0.60, eligible for the single preregistered rescue.
- Below 0.40, or an unqualified denominator: downgrade C2 without rescue.
- No rescue is permitted after formal-test reveal.

### C3: frozen-VLM transfer

The learned-versus-B4a effect is confirmatory only under the exact 64-placeholder, no-pixel, frozen-VLM path. The 95% CI lower bound must be greater than zero and the preregistered intervention-sensitivity checks must pass.

### C4: scaling-null equivalence

Use exact checkpoints from one VLM family and hold encoder, inputs, token budget, prompt, scoring, patients, seeds and derangements fixed.

For smallest and largest preregistered models:

`G_s = 100 * (M_B4b,s - M_B4a,s)`  
`S_close = G_small - G_large`

Equivalence passes only when the paired hierarchical-bootstrap 90% CI for `S_close` lies wholly inside the signed equivalence margin. A candidate margin is +/-2 pp, but the exact margin and checkpoints must be frozen before test. `p > 0.05` or a visually flat curve is not evidence of equivalence.

## 4. Hierarchical inference

Use 10,000 paired hierarchical-bootstrap replicates with a fixed RNG:

1. resample unique patients with replacement once and reuse that patient draw for every system, model size, training seed and derangement;
2. resample training-seed blocks with replacement;
3. resample derangement blocks within training seed, or as a crossed factor if the implementation uses common derangement maps;
4. recompute raw weighted confusion matrices, five class F1s, macro F1, `Delta_bind`, numerator, denominator and Recovery in every replicate;
5. report two-sided percentile 95% CIs, plus patient-only conditional CIs, seed-wise effects/SD and leave-one-seed-out sensitivity.

Patients and training seeds are crossed because every seed predicts the same patients. Treating all repeated prediction rows as independent is prohibited pseudo-replication.

## 5. Power calibration

Use out-of-sample predictions from the complete gold, region-level, exact-64-token, frozen-VLM train/dev path. Prefer separate method-development and power-development partitions. The simulation must preserve:

- five-label prevalence and per-class patient support;
- observations/entities per patient and missingness masks;
- within-patient dependence;
- paired B4a/B4b/learned joint error patterns;
- training-seed, derangement and interaction variation;
- the nonlinear patient-balanced macro-F1 calculation.

Simulate candidate patient counts and `K in {3, 5}` under the frozen derangement count, reproducing the full bootstrap decision rule. Report power curves, Monte Carlo uncertainty and minimum detectable effect.

The full C1 gate cannot have 80% power at a true effect exactly equal to its 5 pp point-estimate threshold: the point-estimate condition alone approaches 50% at the boundary. Therefore report separately:

- power for CI lower bound above zero at a true 5 pp effect;
- full composite-gate power at a signed design alternative greater than 5 pp.

Likewise, Recovery lower-CI success at 0.60 must be powered at a true value above 0.60, including the preregistered 0.70 alternative. If the maximum legal patient sample and five seeds cannot attain at least 80% power at the signed design alternative, remove that confirmatory claim before test reveal.

## 6. Multiplicity

Use fixed-sequence gatekeeping at familywise alpha 0.05:

1. C1 assignment effect;
2. C2 qualified denominator and Recovery;
3. C3 frozen-VLM transfer;
4. C4 scaling-null equivalence and prespecified anti-artifact tests.

After the first failed gate, later results are descriptive. Use Holm correction within planned confirmatory contrast families. The five-label macro F1 is one primary endpoint; per-label F1 cannot rescue it. Exploratory ablation families use BH-FDR at `q = 0.05`.

## 7. Single-rescue rule

Before the first pilot, name exactly one rescue configuration and one allowed method change. The rescue is allowed only on train/dev when:

- the oracle denominator is qualified;
- initial Recovery is 0.40 to below 0.60;
- leakage, B4-isomorphism, data and survival audits all pass.

Run it once on the same locked patient/seed design. If it remains below 0.60, downgrade C2. Expanding from the first three to the first five seeds through the signed power rule is design calibration, not a method rescue.

## 8. Items to freeze

Before pilot:

- label mapping, eligibility/missingness rules, metric code and estimands;
- ordered seed banks, derangement algorithm and impossible-case handling;
- candidate minimum effects, Recovery thresholds and exact rescue;
- development versus power-development split;
- formal-test seal and no-reveal procedure.

After pilot and before formal test:

- patient count, `K=3` or `K=5`, derangement count and exact IDs;
- final minimum/equivalence margins and scaling checkpoints;
- prevalence, joint-error and variance-component estimates;
- power curves, design alternative, MDE and simulation code/RNG hash;
- bootstrap code, RNG, invalid-replicate handling and multiplicity families;
- final method/config/checkpoint, split, data, environment, prompt and analysis hashes.

## 9. Evidence boundary

The historical synthetic result and invalid three-label MIMIC proxy cannot parameterize formal power. They do not contain the real patient clustering, five-label annotation process, complete exact-64 frozen-VLM path or formal seed variance. They remain engineering smoke evidence only.
