# Progress: R28 Case Study and TIER MVP

## 2026-07-26 — Authority reset

- User authorized a new case-study-driven proposal attempt and iterative
  execution.
- Preserved the distinction between engineering completion and scientific GO.
- Created branch `r28-case-study-tier-mvp`.
- Archived the complete R27 active planning bundle under
  `history/2026-07-26-r27-closure/`.
- Rebuilt the active planning surface around a gated mutation ladder:
  A0 oracle headroom, A1 linear TIER, A2 nonlinear TIER, and conditional A3
  transition repair.
- R26/R27 artifacts remain immutable.

## 2026-07-26 — Case registry freeze

- Located the exact R25.1 process-A feature cache consumed by R26:
  `F:\VisualVIT_runtime\050_routeC\r25_1_matching_qualification\process_a\crop_features.pt`.
- Confirmed its registered SHA-256 is
  `2a1df98fb3a3d0ef430698da7846b314a7cbcbe73c9e50f6241bfa57dc623326`.
- Froze deterministic case archetype and tie-break rules before viewing
  individual case images or per-case outcomes.
- Verified the cache schema: 1,586 vectors × 768 float32 dimensions.
- Verified a frozen cohort source image opens successfully at 224×224.
- Recorded the previously implicit R25/R26 limitation that anatomy constraints
  were configured but inactive because all emitted anatomy IDs were zero.
- Implemented the frozen case-registry runner and nine focused tests.
- First focused test run passed 9/9; Ruff found one unused import, removed
  before generating the registry.
- Generated the frozen registry, 24 restricted local case panels, case-level
  prediction table, case panel manifest, and repository failure-analysis
  report.
- Case oracle headroom passed strongly: +25.61 pp, patient-bootstrap 95% CI
  [+22.87, +28.37] pp over the best fixed consensus expert.
- Inspected one immutable representative panel per archetype and recorded
  non-clinical observations without changing the registry.
- Inspected the R26 head/training implementation and selected it as the
  capacity reference.
- Verified both GPUs are occupied by unrelated jobs; chose CPU-only TIER MVP
  execution to preserve ownership boundaries.
- Froze the R28 TIER MVP protocol before any model execution. It defines exact
  state/global/binding representations, label-free descriptors, nested
  patient-OOF stacking, A1/A2 mutation rules, scientific gates, and engineering
  completion criteria.
- Implemented capacity-matched 128-dimensional signed projections, three
  linear experts, linear/nonlinear routers, nested patient-OOF stacking,
  patient/seed bootstrap inference, sanity gates, and fail-closed manifests.
- TIER-focused verification passed: 8/8 pytest tests, Ruff clean, and
  compileall clean.
- Completed A1 and protocol-authorized A2 on CPU.
- Both attempts passed engineering gates but failed scientific GO:
  A1 -1.80 pp and A2 -0.61 pp versus uniform fusion.
- Diagnosed that both routers overweight the weakest state expert while the
  global expert is strongest; recorded this before defining any next attempt.
- Re-ran the complete R28 v1 pipeline in a fresh process and separate runtime
  root.
- The reproduction verifier passed 43/43 checks. Both processes have identical
  results and deterministic prediction SHA-256
  `982591076381cacb5597015a3dfdea399d22c3ef74186e6d25691630fc825135`.
- Closed R28 v1 as engineering-reproduced and scientific NO-GO.
- Declared any calibration/choice-supervision repair to be a separate R28b
  protocol rather than a silent mutation of A1/A2.
- Froze the initial R28b protocol and passed 13 focused R28/R28b tests.
- The expert-cache startup log exposed a protocol transcription error before
  any R28b router or outer-test result: the document listed date-like values
  instead of inherited training seeds 17/29/43.
- Stopped the invalid pre-run, corrected the protocol, and required a new hash
  pin before formal execution.
- Refroze R28b with protocol SHA-256
  `9f5fe2779662f1b976dbf2df5f3dab88d48d5e596e8290b4e784e9f233207034`.
- Completed B1 and protocol-authorized B2. Both passed engineering gates and
  failed scientific GO: B1 -1.43 pp and B2 -0.87 pp versus uniform fusion.
- Completed a second independent R28b process. The verifier passed 40/40 checks
  with deterministic prediction SHA-256
  `44bbe466d5199f328a9ffdb9ca9e85b9be3ac9835e9a5678834ae1d2505c565a`.
- Wrote the final case-study/proposal closure and updated the active CAPES
  proposal with an execution addendum that supersedes its historical claims.
- Full regression initially reached 526 pass / 1 expected xfail / 1 fail. The
  failure correctly detected that adding R28b helpers to the R28 `tier.py`
  invalidated R28's historical source hash.
- Moved all R28b-only helpers into `src/visualvit/tier_choice.py`, restoring the
  exact R28 `tier.py` SHA-256
  `e7c4427eaf9ede73bc8676c2859ffbd43e0036b663377fab120653789743467e`.
- Re-executed both R28b processes from the source-closed layout. R28 remained
  43/43 reproduced; R28b passed an expanded 42/42 verifier with the same
  deterministic prediction digest and unchanged scientific NO-GO.
- Final full regression passed: 527 tests passed and one registered historical
  xfail remained.
- All changed Python files pass Ruff and the full `src/scripts/tests` tree
  passes compileall. Repository-wide Ruff still reports 25 pre-existing errors
  in untouched historical proxy/smoke scripts; they were not mixed into R28.
