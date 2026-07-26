# Progress: R27 Binding Identifiability Audit

## 2026-07-26 — Authority reset

- Read the user-provided reset document and treated it as the new source
  authority.
- Verified the repository is a Git worktree and the pre-reset worktree was
  clean on `r25.1-semantic-repair`.
- Verified the frozen R26 runtime package exists and independently computed
  SHA-256 values for all seven files.
- Created branch `r27-binding-identifiability-audit`.
- Preserved the old active planning bundle under
  `history/2026-07-26-pre-r27-planning/`.
- Rebuilt the active planning bundle around R27 and the `STOP_C1` boundary.
- No model training, prediction regeneration, threshold change, backbone swap,
  VLM run, DIVE run, or R26 mutation was performed.

## 2026-07-26 — R26 schema inspection

- Confirmed the R26 prediction design is complete:
  774 entities × 5 systems × 3 training seeds × 3 derangements = 34,830 rows.
- Confirmed every pair has a unique anatomy-to-progression map and identical
  ordered box lists across its entity rows.
- Identified an R26 provenance limitation: the frozen isomorphism audit stores
  zero-fixed-point checks but not assignment indices.
- Chose a fail-closed deterministic reconstruction route pinned to the frozen
  R26 runner/matching source and pair-seed basis. The report will not describe
  the reconstruction as a directly serialized assignment.
- Preliminary pair-composition support is 122 / 5 / 35 / 8 patients across
  BII-0 / Low / Mid / High.

## 2026-07-26 — R27 implementation and focused verification

- Froze the R27 v1 protocol with exact R26 input and source hashes.
- Added the read-only audit runner and 14 focused tests covering input pins,
  BII toys, LPD/LCD classification, zero-fixed-point reconstruction,
  patient-cluster bootstrap, support precedence, non-training imports, and
  exclusive output behavior.
- The first focused test run found one implementation error in the monotonicity
  check: strict zip was incorrectly used for two intentionally offset
  sequences. Removed strict mode; no evidence had been generated.

## 2026-07-26 — R27 formal execution

- The original R27 process completed after the orchestration wrapper returned
  early; it generated the five required artifacts and repository report.
- A diagnostic second launch reached the output boundary after the first run
  had completed and correctly refused to overwrite the existing fresh root.
- R27 terminal verdict: `C_SPARSE_HIGH_BII_SUPPORT`.
- Audited 2,322 registered entity/derangement assignments:
  1,846 label-preserving and 476 label-changing; semantic corruption rate
  20.50%; reconstructed fixed points 0.
- BII support: 122 / 5 / 35 / 8 patients for 0 / Low / Mid / High.
- B4b minus B4a by stratum:
  - BII-0: +2.36 pp, 95% CI [-2.23, +6.97]
  - BII-Low: +4.92 pp, CI invalid (91.28% valid bootstrap)
  - BII-Mid: -1.50 pp, 95% CI [-9.11, +5.56]
  - BII-High: -6.24 pp, 95% CI [-19.10, +7.75]
- High-BII B4b-B4a direction was negative for all seeds
  (-8.04 / -6.24 / -4.44 pp). There is no monotonic binding-benefit pattern.
- High-BII also has only 8 patients / 27 entities, so the registered
  support-first verdict is sparse evidence, not a subgroup claim.
- Independent verifier passed all 31 checks, including every R26/R27 artifact
  hash, protocol/source pins, manifest self-binding, cohort conservation,
  patient-only bootstrap, report boundary, and R28 lock.
- Focused tests passed 15/15. The first lint pass found only the verifier's
  deliberate post-`sys.path` import (E402); it was given the same explicit
  file-level exemption as the formal runner.

## 2026-07-26 — Full verification closure

- Focused Ruff passed after the verifier import-boundary exemption.
- Compileall passed for `src`, `scripts`, and `tests`.
- Full regression completed: 503 passed, 1 registered xfail in 292.80 s.
- The xfail is the existing frozen R14 bundle case and is unrelated to R27.
- Runtime manifest SHA-256:
  `459de46617603936f45884b9279c3f92b3a7a119276ea5533afb725734ff49b3`.
- Repository report SHA-256:
  `a49d52fc5cb03e86c15f693798444824573fd39ac5032a4dde38a50ba43d46d6`.
- R26 remained untouched. R28 and all downstream training/VLM work remain
  locked.
- Created the final commit on branch
  `r27-binding-identifiability-audit`, including the planning-status writeback.
