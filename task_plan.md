# Task Plan: R27 Binding Identifiability Audit

## Authority

- Source authority: the user-provided 2026-07-26 project-reset document.
- Preserved terminal fact: R26 C1 remains `STOP_C1`.
- R27 evidence class: exploratory, post-hoc, read-only mechanism audit.
- Active branch: `r27-binding-identifiability-audit`.
- Frozen input root:
  `F:\VisualVIT_runtime\050_routeC\r26_c1_oracle_binding\run_v1`.

## Goal

Reorganize VisualVIT around the R26 negative result and execute the authorized
R27 audit without retraining, regenerating predictions, or modifying any R26
artifact. Produce patient-level label composition, semantic-corruption audits,
BII-stratified effects with patient-cluster bootstrap intervals, support
diagnostics, a manifest, and a formal exploratory report.

## Hard Boundaries

- Do not change R26 thresholds, seeds, protocol, report, predictions, or hashes.
- Do not train or fine-tune any model or classifier.
- Do not run learned matcher, RAD-DINO, frozen VLM, DIVE, TIER, or scale-up.
- Do not claim a confirmatory result from a post-hoc BII stratum.
- Stop after the R27 verdict. R28+ require a separately reviewed protocol.

## Formal Gate Order

1. **G0 Frozen input integrity:** all R26 files exist and match registered hashes.
2. **G1 Read-only provenance:** runner accepts only frozen R26 inputs and writes
   to a fresh R27 output root.
3. **G2 Definition correctness:** toy BII, semantic-transition, zero-fixed-point,
   LPD, and LCD tests pass.
4. **G3 Cohort conservation:** stratum patient/entity totals equal the frozen R26
   cohort, with no entity treated as an independent bootstrap cluster.
5. **G4 R27 execution:** generate all declared JSON artifacts and report.
6. **G5 Independent verification:** rerun verifier/tests, recheck input/output
   hashes, and record the exploratory terminal verdict.

## Phases

### Phase 0 — Reset and archive

- [x] Create the R27 branch.
- [x] Archive the former active planning bundle under
  `history/2026-07-26-pre-r27-planning/`.
- [x] Rebuild `task_plan.md`, `findings.md`, and `progress.md` for R27.
- **Status:** complete

### Phase 1 — Freeze the R27 protocol

- [x] Inspect frozen R26 schemas and current repository conventions.
- [x] Write `docs/superpowers/specs/2026-07-26-r27-binding-identifiability-audit-v1.md`.
- [x] Pin the protocol and all R26 input hashes in code/tests.
- **Status:** complete

### Phase 2 — Implement and test

- [x] Add `scripts/audit_r26_binding_identifiability.py`.
- [x] Add `tests/test_r27_binding_identifiability.py`.
- [x] Verify no training/import path can be invoked.
- **Status:** complete

### Phase 3 — Execute R27

- [x] Run against the frozen R26 package into a fresh runtime root.
- [x] Generate pair composition, semantic audit, stratified effects, support
  audit, and artifact manifest.
- [x] Write `reports/R27_BINDING_IDENTIFIABILITY_AUDIT.md`.
- **Status:** complete

### Phase 4 — Verify and close

- [x] Run focused and full regression tests plus lint/compile checks.
- [x] Recompute all declared hashes independently.
- [x] Record the R27 exploratory verdict and R28 lock.
- [x] Commit the organized R27 package if verification is green.
- **Status:** complete

## Completion Criteria

- R26 frozen bytes remain unchanged.
- All five required R27 output files exist and are hash-bound by the manifest.
- Report clearly says `exploratory_only=true`.
- Patient-cluster bootstrap uses patients as the resampling unit.
- The result is classified as one of:
  `A_MONOTONIC_SUPPORT`, `B_NO_HIGH_BII_GAIN`, or
  `C_SPARSE_HIGH_BII_SUPPORT`, with explicit support limitations.
- No R28/R29/TIER/VLM execution is performed.

## R27 Terminal Result

- Verdict: `C_SPARSE_HIGH_BII_SUPPORT`
- Secondary mechanism pattern: no monotonic binding-benefit trend.
- High-BII B4b minus B4a: `-6.24 pp`, 95% CI
  `[-19.10, +7.75] pp`; all three seed directions negative.
- High-BII support: 8 patients / 27 entities, below all registered support
  thresholds.
- Formal flags: `exploratory_only=true`, `formal_claim_allowed=false`,
  `r28_unlocked=false`.
- Independent verification: `PASS_R27_INDEPENDENT_VERIFICATION` (31/31).
- Full regression: 503 passed, 1 registered xfail.

## Errors Encountered

| Error | Attempt | Resolution |
|---|---:|---|
| Planning session catchup is unsupported for native Codex sessions | 1 | Used live Git status plus archived planning files as the recovery boundary |
| Monotonicity check used `zip(..., strict=True)` on offset sequences | 1 | Removed strict mode because adjacent-pair sequences intentionally differ by one element |
| A nested execution call returned before the original R27 process finished; a diagnostic second launch later found the already-created fresh root | 1 | Confirmed the first process completed all five artifacts and the report; treated the second launch's fail-closed overwrite refusal as expected protection |
| Independent verifier triggered Ruff E402 after inserting the workspace import path | 1 | Added the same explicit file-level E402 exemption used by the formal runner |
