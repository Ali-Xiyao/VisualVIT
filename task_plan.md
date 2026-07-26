# Task Plan: R28 Case Study and TIER MVP

## Authority

- User instruction: summarize prior failures, conduct a case study, make new
  attempts, and continue until the current proposal has a working execution.
- Scientific inheritance:
  - R26 remains `STOP_C1`.
  - R27 remains exploratory and reports no monotonic BII/binding benefit.
- Active branch: `r28-case-study-tier-mvp`.
- R26/R27 artifacts are immutable inputs, not targets for repair.

## What “run through” means

Two acceptance levels are kept separate:

1. **Engineering success:** a deterministic, leak-audited, patient-disjoint
   case-study/TIER pipeline runs end to end, reproduces from a fresh process,
   and emits a complete manifest and report.
2. **Scientific GO:** a frozen primary comparison passes its preregistered
   effect, uncertainty, support, and seed-direction gates.

Engineering success may be achieved by debugging and changing implementation.
Scientific GO may not be manufactured by changing thresholds, selecting lucky
seeds/cases, or repeatedly revealing the same held-out result. A scientifically
failed attempt must be recorded before the next materially different proposal
is frozen.

## Hard Boundaries

- Do not modify R26/R27 protocols, reports, predictions, or runtime files.
- Case selection may illustrate mechanisms but may not define the evaluation
  subset after inspecting outcomes.
- Label-derived BII, correctness, LPD/LCD class, or progression labels may be
  used for offline analysis and oracle upper bounds, never as router inputs.
- No VLM/DIVE/scale-up before the structured TIER MVP passes its survival gate.
- Preserve patient-disjoint folds and patient-cluster inference.
- Stop at the first failed survival gate; the next action is diagnosis and a
  materially changed attempt, not scale-up.

## Gate Order

1. **G0 Provenance:** verify R26/R27 hashes and locate reusable frozen features.
2. **G1 Case-study registry:** freeze representative selection rules before
   writing narrative conclusions.
3. **G2 Failure synthesis:** classify prior failures as data, intervention,
   representation, estimator, optimization, or provenance failures.
4. **G3 R28 protocol freeze:** define systems, router inputs, folds, seeds,
   primary metric, stop rules, and allowed mutation ladder.
5. **G4 Minimal overfit/sanity:** prove the implementation can learn a toy and a
   tiny train-only slice without leakage.
6. **G5 Nested patient-OOF MVP:** run the first frozen TIER attempt.
7. **G6 Reproduction:** fresh-process exact or tolerance-bound reproduction.
8. **G7 Scientific verdict:** record GO/NO-GO before any next attempt.

## Mutation Ladder

Only move downward after the previous attempt is frozen and closed:

1. **A0 Case oracle:** label-derived best-expert selector, analysis-only upper
   bound; proves whether routing headroom exists.
2. **A1 Linear TIER:** state/global/binding experts with a label-free linear
   router and frozen representations.
3. **A2 Nonlinear TIER:** capacity-matched two-layer router if A1 underfits but
   A0 shows adequate headroom.
4. **A3 Transition repair:** report-supervised training targets with image-only
   inference only if both A1/A2 show the transition representation is the
   bottleneck and a legal report source is available.

No threshold, seed, fold, or held-out-set mutation is permitted inside an
attempt.

## Phases

### Phase 0 — Reset and provenance

- [x] Create R28 branch.
- [x] Archive R27 planning bundle under
  `history/2026-07-26-r27-closure/`.
- [x] Verify frozen artifacts and reusable feature paths.
- **Status:** complete

### Phase 1 — Case study and failure taxonomy

- [x] Freeze case selection rules.
- [x] Generate case-level tables/visual panels for success, shortcut,
  derangement-robust, and binding-harm cases.
- [x] Write the prior-failure taxonomy with evidence links.
- [x] Quantify oracle routing headroom.
- **Status:** complete

### Phase 2 — Freeze R28 MVP protocol

- [x] Define state/global/binding expert representations.
- [x] Define label-free router inputs and leakage audit.
- [x] Freeze nested patient folds, metrics, seeds, and stop rules.
- [x] Add protocol hash pins and tests.
- **Status:** complete

### Phase 3 — Implement and sanity-test

- [x] Build the R28 runner.
- [x] Pass toy, shape, fold, leakage, and tiny-overfit tests.
- [x] Record peak memory/runtime and source hashes.
- **Status:** complete

### Phase 4 — Execute mutation ladder

- [x] Run A0 oracle headroom.
- [x] Run and close A1.
- [x] If authorized by the frozen ladder, run and close A2.
- [x] Close A3 as not authorized: no audited legal report-supervision source is
  established for this cycle.
- [x] Freeze and execute R28b as a separate failure-derived attempt; do not
  relabel it as A3 or mutate the R28 v1 protocol.
- **Status:** complete

### Phase 5 — Reproduce and close

- [x] Fresh-process reproduction of the frozen R28 A1/A2 attempt.
- [x] Fresh-process reproduction of the frozen R28b B1/B2 attempt.
- [x] Write final case-study, experiment report, and artifact manifest.
- [x] Run focused/full regression, lint, and compile checks.
- [x] Commit and push the completed R28 branch.
- **Status:** complete

## Expected Deliverables

- `docs/superpowers/specs/2026-07-26-r28-case-study-registry-v1.md`
- `docs/superpowers/specs/2026-07-26-r28-case-study-tier-mvp-v1.md`
- `docs/superpowers/specs/2026-07-26-r28b-calibrated-choice-tier-v1.md`
- `reports/R28_CASE_STUDY_AND_FAILURE_ANALYSIS.md`
- `reports/R28_TIER_MVP_RESULT.md`
- `reports/R28B_CALIBRATED_CHOICE_TIER_RESULT.md`
- `reports/R28_FINAL_CASE_STUDY_AND_PROPOSAL_CLOSURE.md`
- `scripts/run_r28_case_study.py`
- `scripts/run_r28_tier_mvp.py`
- `scripts/verify_r28_tier_mvp.py`
- `scripts/run_r28b_calibrated_choice_tier.py`
- `scripts/verify_r28b_calibrated_choice_tier.py`
- `tests/test_r28_case_study.py`
- `tests/test_r28_tier_mvp.py`
- Runtime outputs under
  `F:\VisualVIT_runtime\050_routeC\r28_case_study_tier\`.

## Errors Encountered

| Error | Attempt | Resolution |
|---|---:|---|
| Native Codex session catchup unsupported | 1 | Used clean Git state and archived R27 planning as the recovery boundary |
| R28 case-study lint found unused `math` import | 1 | Removed the import before any case-study execution |
| R28b protocol copied projection-date values as training seeds | 1 | Stopped before any R28b route/test result, corrected to inherited seeds 17/29/43, and refroze the protocol hash |
| R28b helpers changed R28's manifest-bound shared source hash | 1 | Split R28b helpers into `tier_choice.py`, restored the exact R28 source hash, and reran both R28b processes |
| Full-repository Ruff reports 25 legacy errors | 1 | Confirmed all are in untouched historical proxy/smoke scripts; changed-file Ruff and full compileall pass |
