# R26 C1 Oracle-Binding Progression Protocol v1

Status: `DRAFT_AWAITING_R25_1_Q6`

Date: 2026-07-26

## 1. Question

> With identical entity features, classifier capacity, patient folds, seeds,
> training budget, token shape, and target labels, does correct cross-temporal
> entity binding improve Stable/Improved/Worse prediction relative to a
> zero-fixed-point derangement?

The primary estimand is:

`delta_bind = 100 * (progression_macro_f1_B4b - progression_macro_f1_B4a)`

R26 C1 is a structured-classifier mechanism gate. It is not a frozen-VLM,
learned-matcher, clinical, or confirmatory test.

## 2. Prerequisite

Execution is locked until R25.1 process A/B and the Q6 verifier establish:

- identical cohort and crop-feature hashes;
- all R25.1 matching gates green;
- explicit progression `NOT_EVALUATED`;
- no source, protocol, or anatomy-audit drift.

The terminal R25.1 reproduction certificate hash and reproduced feature-cache
hash will be pinned when this draft is frozen.

## 3. Data and split

- Source: R25.1 entity manifest, 793 entity targets from 189 patients/pairs.
- Labels: `Improved`, `Stable`, `Worse`.
- Unit of prediction: one `qualification_id` / anatomy entity.
- Cluster: patient; every patient and all entities from its temporal pair stay
  in one fold.
- Evaluation: deterministic five-fold out-of-fold prediction on the qualified
  official-train cohort.
- Fold salt: `r26-c1-b3-v1`.
- Every train and held-out fold must contain all three labels.
- This cross-validation is non-confirmatory development evidence; no separate
  formal test is revealed.

## 4. Frozen representation

For target anatomy `a`, let `p_a` be its prior endpoint feature. A MatchPlan
selects current endpoint `c`. The relation vector is:

`[p_a, c, c-p_a, c*p_a, onehot(persistent)]`

The feature slices and tensor order are identical for all systems.

Registered systems:

1. `B4a_deranged_visual_geometry`
2. `B4b_oracle_visual_geometry`
3. `oracle_visual_only`
4. `oracle_geometry_only`
5. `current_only_visual_geometry`

For B4a/B4b, only the real-real assignment changes. B4a uses three registered
zero-fixed-point derangements per pair; B4b is invariant and its predictions
are repeated across derangement ids only for paired inference.

## 5. Classifier and optimization

- Head: non-affine LayerNorm + Linear.
- Loss: inverse-frequency weighted cross entropy computed on each training
  fold only.
- Seeds: 17, 29, 43.
- Derangement ids: 81001, 81002, 81003.
- Steps: 300.
- Learning rate: 0.01.
- Optimizer: AdamW, weight decay `1e-4`.
- No encoder, matcher, projector, or feature update.
- Identical model seed for B4a and B4b within each fold/seed.
- Deterministic PyTorch algorithms required.

## 6. Metrics and inference

Report:

- patient-balanced progression macro F1;
- ordinary entity-level macro F1;
- balanced accuracy;
- per-class F1;
- patient, pair, and entity counts;
- three-seed direction;
- hierarchical patient/seed/derangement bootstrap with 10,000 replicates.

Primary GO gate:

- `delta_bind >= 5 pp`;
- patient-bootstrap 95% lower bound `> 0`;
- B4b-B4a direction positive for every registered training seed;
- bootstrap inference valid;
- non-deranged predictions invariant across derangement ids.

Secondary diagnostics:

- oracle visual-only vs geometry-only;
- B4b vs current-only;
- per-class changes;
- training convergence and finite loss.

## 7. Isomorphism checks

For every pair and derangement:

- zero fixed persistent edges;
- assignments differ;
- null sets unchanged;
- prior/current source tensors identical;
- target ordering identical;
- relation vector shape identical;
- classifier architecture, initialization seed, optimizer, steps, and
  training indices identical.

Any failed isomorphism check stops C1 before training.

## 8. Stop rules

- If R25.1 Q6 is not terminal green, do not run.
- If any fold lacks a label, do not run.
- If C1 primary GO fails, record the result and stop CAPES identity-binding
  scale-up.
- Do not train a learned matcher after C1 failure.
- Do not start RAD-DINO, frozen VLM, DIVE, or Slurm scaling from this draft.
- Only a green C1 may unlock a separately frozen C2 learned-recovery protocol.

## 9. Required artifacts

- frozen protocol and source hashes;
- R25.1 certificate and feature-cache pins;
- patient fold assignment and audit;
- entity-level OOF predictions;
- fit audit;
- B4 isomorphism audit;
- block metrics;
- hierarchical bootstrap result;
- gate certificate and interpretation boundary.

