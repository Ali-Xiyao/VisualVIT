# Findings: R28 Case Study and TIER MVP

## Inherited evidence

- R26: oracle binding minus deranged binding was only `+1.17 pp`, with CI
  crossing zero; the universal-binding proposal failed.
- R27: only 20.50% of registered derangements changed progression semantics.
- R27 B4b minus B4a was not monotonic in BII; High-BII was `-6.24 pp`, with
  all three seed directions negative.
- High-BII nevertheless showed oracle minus current-only `+23.42 pp`. This
  suggests temporal information may matter for some cases, while precise
  identity binding is not the demonstrated reason.

## Working hypothesis

The viable proposal is no longer “binding is conditionally necessary as
measured by BII.” It is:

> Longitudinal cases differ in whether current state, global transition, or
> entity-local transition evidence is useful; a label-free router may allocate
> capacity among these experts more effectively than a single uniform fusion.

This remains a hypothesis until the case oracle establishes headroom and a
label-free nested-OOF router survives its frozen gate.

## Failure categories to investigate

- **Endpoint shortcut:** current-only may solve many progression labels.
- **Intervention weakness:** identity derangement often preserves label
  semantics.
- **Representation weakness:** frozen ROI features may not encode change
  direction.
- **Estimator adaptation:** separately trained B4a heads may learn to ignore
  corrupted prior evidence.
- **Support failure:** binding-critical cases are sparse.
- **Model-selection leakage risk:** repeated use of the same 170 patients can
  create optimistic development evidence.
- **Provenance gaps:** R26 did not serialize assignment indices.

## Open questions

- Where is the exact frozen feature cache consumed by R26?
- Can global prior/current pair summaries be constructed without image
  re-encoding?
- Does an analysis-only best-expert selector show enough headroom for routing?
- Which label-free descriptors correlate with expert advantage without using
  BII or outcome labels at inference?

## Frozen case registry

Before inspecting individual images or case outcomes, the selection rules were
frozen in
`docs/superpowers/specs/2026-07-26-r28-case-study-registry-v1.md`.
Five descriptive archetypes are selected deterministically from frozen
correctness summaries: state-sufficient, temporal-helped, binding-helped,
binding-harmed, and all-experts-fail.

The registry deliberately retains inconvenient or visually unclear selected
cases and discloses overlaps. It is exploratory and cannot become the TIER
evaluation set.

## Provenance and representation inspection

- The exact R26 feature cache is available, contains 1,586 deterministic
  float32 vectors, and each crop embedding has dimension 768.
- Source images referenced by the frozen cohort remain readable as
  de-identified 224×224 grayscale JPEGs, so deterministic prior/current ROI
  panels can be produced without new downloads or re-encoding.
- A newly surfaced intervention flaw is material: the R25.1 summary states
  `anatomy_constraint.active_on_cohort=false`, with all emitted anatomy IDs
  identical and zero candidates removed. Therefore R26's
  `anatomy_compatible_derangement` name overstates the realized constraint:
  derangements were zero-fixed-point across the whole pair, not restricted by
  a meaningful anatomy-group mask.
- This does not reverse `STOP_C1`; it strengthens the need for case-level
  transition analysis and a new protocol. It also means “binding harmed” cases
  may partly reflect implausible cross-anatomy corruption rather than precise
  within-group identity perturbations.

## Frozen case-study result

- Registry support is broad enough for descriptive analysis:
  - state-sufficient: 319 eligible
  - temporal-helped: 135
  - binding-helped: 125
  - binding-harmed: 130
  - all-experts-fail: 135
- The deterministic registry selected 24 unique cases; one case legitimately
  overlaps state-sufficient and binding-harmed.
- The analysis-only label oracle selects:
  - current-only for 556 entities
  - oracle binding for 136 entities
  - deranged expert for 82 entities
- Label-oracle routing headroom over the best fixed consensus expert is
  `+25.61 pp`, with patient-bootstrap 95% CI `[+22.87, +28.37] pp`.
- This is not a model result because the selector reads the target label, but
  it decisively passes the “is routing headroom present?” prerequisite.

## Non-clinical panel observations

Visual inspection was restricted to the immutable registered cases. No case
was replaced after viewing.

- A state-sufficient Stable right-lung example shows broadly similar target
  appearance across acquisitions despite exposure/position differences,
  consistent with current-state sufficiency.
- A temporal-helped mediastinum example contains substantial whole-image
  acquisition and support-device differences. This argues for a global
  transition expert and warns that local binding alone may encode nuisance.
- A binding-helped Improved right-lung example shows subtle diffuse
  prior/current changes under different positioning; the local ROI is useful
  but not obviously sufficient by itself.
- A binding-harmed Worse hilar example shows large global deterioration while
  the registered hilar ROI is small. A deranged/global shortcut can outperform
  the oracle-local representation when the endpoint is globally visible.
- An all-experts-fail costophrenic-angle example uses a very small edge ROI.
  The crop captures little context, supporting a representation/ROI-context
  failure rather than a matching failure.

These observations motivate three concrete changes: preserve a state expert,
add global pair context, and let the binding expert operate as one optional
source rather than the universal representation.

## Implementation feasibility

- The existing R26 classifier is a non-affine LayerNorm plus Linear head,
  trained independently per outer fold/system/seed. It can be reused as the
  capacity reference.
- A proper TIER stack must avoid training the router on in-sample expert
  outputs. The admissible design is nested patient OOF:
  inner-fold expert logits train the router on the outer-training patients;
  experts are then refit on the full outer-training set and evaluated once on
  the outer-held-out patients.
- Both RTX 3090 GPUs currently have unrelated Python workloads and about
  11–12 GiB allocated. Per shared-GPU policy, R28 will run the small frozen-head
  MVP on CPU and will not stop or compete with those jobs.
- The CPU route is practical because all 1,586 image crops are already encoded
  and the new models operate only on small tensors.

## A1/A2 TIER result

- Engineering gates passed for both attempts: complete nested OOF predictions,
  finite fits, patient-disjoint inner/outer folds, and valid bootstrap.
- Expert performance:
  - state: 0.4037 patient-balanced macro F1
  - global: 0.4388
  - binding: 0.4187
  - uniform fusion: 0.4368
- A1 linear TIER: 0.4188; delta versus uniform `-1.80 pp`, 95% CI
  `[-6.07, +2.49]`; scientific NO-GO.
- A2 nonlinear TIER: 0.4307; delta versus uniform `-0.61 pp`, 95% CI
  `[-4.36, +3.35]`; scientific NO-GO.
- A2 is within 1 pp of the strongest single expert, but fails the registered
  positive-effect, CI, and all-seed gates.
- Mean router weights diagnose a selection problem:
  - A1: state 0.423 / global 0.289 / binding 0.287
  - A2: state 0.370 / global 0.325 / binding 0.305
- The strongest expert is global, yet both routers overweight the weakest
  state expert. This is consistent with uncalibrated expert-logit scales and an
  indirect mixture-loss signal, not an absence of expert diversity.

## Next admissible mutation

The frozen A1/A2 protocol does not authorize another silent router change.
After fresh-process reproduction, a separate attempt may test:

1. temperature calibration learned only from inner-OOF outer-training logits;
2. direct OOF best-expert pseudo-label supervision with fixed cost tie-break
   state → global → binding;
3. hard or guarded routing at outer-test inference;
4. the same folds, seeds, representations, metrics, and GO thresholds.

This changes the supervision/mixture mechanism rather than tuning the failed
A2 architecture.

## Fresh-process reproduction

- The R28 v1 verifier passed all 43 checks across the formal and reproduction
  roots.
- The two independent processes produced the same registered metric table and
  the same deterministic prediction digest:
  `982591076381cacb5597015a3dfdea399d22c3ef74186e6d25691630fc825135`.
- Reproduction status is `PASS_R28_TIER_FRESH_PROCESS_REPRODUCTION`.
- The engineering objective is therefore complete for R28 v1; the scientific
  verdict remains NO-GO for both A1 and A2.
- The reproduction certificate is stored outside Git at
  `F:\VisualVIT_runtime\050_routeC\r28_case_study_tier\tier_mvp_v1_reproduction_certificate.json`.

## R28b authority boundary

R28b will be a new, separately hashed development protocol. It may use labels
only on outer-training patients to construct inner-OOF expert-choice targets
and calibration parameters. Outer-test inference remains image/geometry only.
It inherits the exact folds, seeds, representations, metrics, and scientific
thresholds from R28 v1. This preserves the failed A1/A2 record and prevents
post-result threshold, seed, or evaluation-set tuning.

## R28b calibrated-choice result

- B1 hard choice routing reached 0.4225 macro F1 versus 0.4368 for uniform
  fusion: `-1.43 pp`, 95% CI `[-5.98,+2.82]`; scientific NO-GO.
- B2 registered guarded routing reached 0.4281: `-0.87 pp`, 95% CI
  `[-5.13,+3.20]`; scientific NO-GO.
- Both attempts passed complete-prediction, finite-fit, bootstrap, and nested
  patient-disjoint engineering checks.
- Calibration was active: 45 fitted temperatures ranged from 4.23 to 6.88.
- Mean choice-router training accuracy was 93.50%, so failure is not an
  optimizer crash.
- The cost-ordered first-correct target created a new shortcut: 51.55% of
  training choice targets were state, 28.59% global, and 19.86% binding.
- The hard router selected state on 1,114/2,322 seed-entity predictions.
  Guarded routing still accepted 86.22% of routes, so global fallback did not
  prevent negative transfer.
- This target-design diagnosis is post-result. It cannot authorize retuning the
  same held-out cohort.

## Terminal interpretation

- R28 and R28b are both fresh-process reproducible.
- R28b source-closed verifier passed 42/42 checks with deterministic predictions SHA-256
  `44bbe466d5199f328a9ffdb9ca9e85b9be3ac9835e9a5678834ae1d2505c565a`.
- Engineering status: `REPRODUCED`.
- Scientific status: `NO_GO_CURRENT_PROPOSAL`.
- Further work requires a fresh cohort, or a separately audited legal report
  source/new representation followed by one-shot evaluation on fresh patients.
