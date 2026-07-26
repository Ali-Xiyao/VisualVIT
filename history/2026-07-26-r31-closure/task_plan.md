# Archived Task Plan: R29-R31 Case-Driven Proposal Repair

## Authority

- User explicitly requested continued case studies and materially new attempts
  until the current proposal has the strongest honest chance to pass.
- R26 `STOP_C1`, R27, R28, and R28b results remain immutable.
- Active branch: `codex/r29-case-driven-transition-repair`.
- R29 may not change prior thresholds, seeds, cases, or conclusions.

## Objective

Test whether the failed proposal is repairable by replacing underspecified
local/global expert summaries with an explicitly contextual, direction-aware
transition representation on a fresh patient cohort.

“Run through” continues to mean:

1. engineering reproduction must pass; and
2. scientific GO must pass the frozen endpoint, CI, seed, support, and leakage
   gates.

Repeated tuning on the R26-R28b 170-patient cohort is forbidden.

## R29 Gate Order

1. **G0 Fresh-data authority:** locate unused patients, verify local
   provenance/DUA boundary, and prove zero patient overlap with R26-R28b.
2. **G1 Case-derived hypothesis:** freeze failure archetypes and a
   representation repair before viewing R29 outcomes.
3. **G2 Label/report audit:** determine whether report-supervised transition
   targets are legally and technically available. If not, use image-only
   self-supervision and record the limitation.
4. **G3 Train-only survival:** on R29 training patients only, prove the new
   representation encodes change direction and beats shuffled controls.
5. **G4 Protocol freeze:** register cohort, folds, seeds, systems, primary
   metric, uncertainty, and mutation ladder before outer-test reveal.
6. **G5 One-shot evaluation:** run the minimal attempt once.
7. **G6 Reproduction and verdict:** reproduce engineering results, then record
   GO/NO-GO without threshold or subset changes.

## Allowed Mutation Ladder

1. `R29-A0`: train-only label oracle and representation survival audit.
2. `R29-A1`: contextual transition expert using target ROI, expanded ROI
   context, global pair context, geometry, and explicit signed/absolute deltas.
3. `R29-A2`: report-supervised transition target only if G2 establishes a
   legal local report source and patient-disjoint generation protocol.

No VLM/DIVE/RAD-DINO/scale-up until R29-A1 or A2 passes the survival and
scientific gates.

## Phases

### Phase 0 — Reset and provenance

- [x] Create R29 branch.
- [x] Archive R28 planning bundle.
- [x] Inventory unused patient/data/report assets.
- [x] Verify overlap, licensing/DUA boundary, and storage feasibility.
- **Status:** complete

### Phase 1 — Case-study expansion

- [x] Freeze selection rules for R28 failure cases and candidate R29 analogues.
- [x] Quantify ROI-size/context, acquisition, and anatomy-granularity effects.
- [x] Write the R29 repair hypothesis before outcome evaluation.
- **Status:** complete

### Phase 2 — Protocol and implementation

- [x] Freeze R29 protocol and hashes.
- [x] Implement cohort builder, contextual representation, audits, and tests.
- [x] Execute R29 survival and preserve its failed, sealed-test verdict.
- **Status:** complete (R29 stopped; test sealed)

### Phase 3 — Formal execution

- [x] Execute allowed R29 mutation ladder in order.
- [x] Freeze and execute R30 on R29 sealed-reserve patients.
- [x] Freeze and execute R31 on R30 sealed-reserve patients.
- [x] Fresh-process reproduce the best admissible attempt.
- [x] Write proposal/result/manifest updates.
- **Status:** complete

### Phase 4 — Verification and handoff

- [x] Run final full tests, lint, compile, and source-hash verification.
- [x] Commit and push the case-driven closure branch.
- **Status:** complete

## Next Step

No further silver tuning is authorized. The next scientific step is a newly
authorized human-gold or external confirmation protocol.

## Errors Encountered

| Error | Attempt | Resolution |
|---|---:|---|
| Initial planning-bundle move used an empty hunk | 1 | Retried with preserved heading context |
| PowerShell download audit piped directly after `foreach` | 1 | Use an explicit results array, then format it |
| Per-row H-drive `is_file` audit did not finish promptly | 1 | Stopped the owned read-only process; replace with one indexed image inventory and vectorized joins |
| Full-cohort dry-run found asymmetric anatomy granularity across timepoints | 1 | Resolve anatomy independently for each image and audit deterministic parent-region fallbacks |
| R30 cohort builder called a nonexistent console-only JSON helper after writing artifacts | 1 | Preserve failed runtime, use stdlib `json.dumps`, and rerun to a fresh `cohort_v1_1` root |
| First R30 weight test expected class balance without multiplying patient balance | 1 | Corrected the test's combined inverse-patient and inverse-class ratio; implementation unchanged |
| R30 run completed model computation but NumPy `bool_` blocked `dev_gate.json` serialization | 1 | Do not inspect partial predictions; cast the check to builtin `bool` and resume from the SHA-pinned feature cache into a fresh output root |
