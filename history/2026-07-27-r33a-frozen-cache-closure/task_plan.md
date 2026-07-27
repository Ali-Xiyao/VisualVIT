# Archived Task Plan: TIER-CXR-VLM R33A Case-Study Rescue

## Authority

- Primary protocol: `TIER_CXR_VLM_Next_Stage_Proposal_CN.md`.
- Result registry: `TIER_CXR_VLM_Empty_Result_Tables_CN.md`.
- Inherited scientific boundary: R31 is a reproduced fresh-silver development
  GO; R26 human-gold `STOP_C1` remains immutable.
- Branch: `codex/r32-tier-cxr-vlm`, created from `7c4c51e`.
- Historical R26-R31 artifacts are frozen and may only be read for lineage.

## Objective

Preserve the completed R32 GO and R33 STOP as immutable evidence, then diagnose
R33 at case level and develop a mechanistically different R33A candidate. Use
only the 1,574-patient train partition for case-study-driven iteration. Freeze
one candidate before a single 300-patient dev confirmation. Unlock R34 only if
the new registered gate passes. Never read the 483-patient sealed VLM test or
gold outcomes during R33A.

Passing is not guaranteed by repeated attempts: every attempt must correspond
to a distinct, documented hypothesis, and the formal candidate is evaluated
once after freeze.

## Lightweight provenance policy

Per user direction, do not repeatedly recompute large file or cache hashes.
Record existing authoritative lineage once, compute a protocol/cohort/cache
identifier only when an artifact is first frozen, and use existence, schema,
row-count, split-disjointness, and smoke checks during ordinary iteration.

## Gate order

1. **R32 Authority and engineering freeze**
   - Build the 2,383-patient zero-overlap five-class master cohort with
     1,574 Train, 300 Dev/Calibration, and 483 Sealed VLM Test patients after
     quarantining 26 registered gold patients from the 2,383-person master.
   - Quarantine all gold/external patient IDs and establish an access log.
   - Audit data/license/support/power without reading gold outcomes.
   - Implement exact-64 robust/rich token bundles and OOF routing contracts.
   - Build/reuse the BiomedCLIP patch cache.
   - Pass Qwen3-VL-4B exact-64 injection smoke.
   - Run unit tests; do not reveal formal test outcomes.
2. **R33 Token Survival**
   - Run patient-disjoint 5-fold OOF probe routing on Train+Dev only.
   - Compare P3/P4/P5/P6/P7, seeds 17/29/43, bootstrap and shortcuts.
   - GO only if all proposal gates pass; otherwise STOP VLM scale-up.
3. **R34 Frozen-VLM Transfer**
   - Unlock only after R33 GO.
   - Freeze model/prompt/layout/loss/seeds, then reveal the 483 test once.
4. **R35 Human-Gold / External**
   - Unlock only with adequate registered support and quarantine intact.
5. **R36 Grounding, generation, and paper tables**
   - Unlock only according to the proposal decision tree.

## Phases

### Phase 0 — Reset and audit

- [x] Create R32 branch from `7c4c51e`.
- [x] Archive the completed R31 planning bundle.
- [x] Reconstruct the exact remaining R31 reserve and local model/data assets.
- [x] Freeze the minimal R32 execution specification.
- **Status:** complete

### Phase 1 — R32 implementation

- [x] Implement master split and gold quarantine.
- [x] Implement exact-64 token bundle and OOF route contracts.
- [x] Implement lightweight cache and exact-64 smoke paths.
- [x] Add focused unit tests.
- **Status:** complete

### Phase 2 — R32 execution

- [x] Run cohort/quarantine/support audits.
- [x] Build or reuse patch cache.
- [x] Run exact-64 Qwen smoke and R32 test suite.
- [x] Fill R32 result tables and issue GO/STOP.
- **Status:** complete — `GO_R32_READY_R33`

### Phase 3 — R33 execution

- [x] Run only if R32 GO.
- [x] Fill R33 tables, shortcuts, uncertainty, and decision.
- **Status:** complete — `STOP_R33_TOKEN_SURVIVAL`

### Phase 4 — Conditional R34-R36

- [x] Follow the first failed gate and stop downstream scaling when required.
- **Status:** complete — R34-R36 remain locked after R33 STOP

### Phase 5 — R33A forensic case study

- [x] Build train-only correction/harm case registry from R33 OOF artifacts.
- [x] Quantify failures by label, finding, fold, route confidence, and
  robust-vs-rich disagreement.
- [x] Audit representation construction, route target, and control semantics.
- [x] Select non-overlapping rescue hypotheses and freeze each before use.
- **Status:** complete

### Phase 6 — R33A exploratory rescue

- [x] Implement Attempt A direct-transition tokens with patient-disjoint inner
  validation; retained as a documented failure.
- [x] Implement Attempt B cross-fitted benefit routing; retained as a
  documented failure.
- [x] Implement Attempt C common-width nonlinear token reader; retained as a
  documented failure.
- [x] Implement Attempt D anatomy/context token bridge; retained as the
  strongest selected-bundle failure.
- [x] Reject raw token geometry, finding interactions, and confidence-threshold
  tuning as benefit-router rescues.
- [x] Implement Attempt E/E2 explicit prior/current coherence bridge and
  projection-matched audit.
- [x] Require Attempt E to improve the prior-shuffle control before considering
  another routing mutation.
- [x] Implement Attempt F fold-trained 64-dimensional bridge.
- [x] Implement Attempt G cross-fitted benefit-conditioned learned bridge.
- [x] Continue train-only case-study experiments and reject failed hypotheses.
- [x] Close the frozen-cache premise after no candidate passes all gates.
- **Status:** complete — `STOP_R33A_FROZEN_CACHE_PREMISE`

### Phase 7 — One-shot dev confirmation

- [x] Do not fit/evaluate dev because no train-only candidate survived.
- [ ] Fit the frozen candidate on train only and evaluate the 300-patient dev
  split once.
- [ ] Require primary delta, uncertainty, seed, random-route, prior-shuffle,
  query-only, and leakage gates.
- [ ] Reproduce only after scientific GO.
- **Status:** locked — no surviving R33A candidate

### Phase 8 — Conditional R34-R36

- [ ] Unlock R34 only after R33A confirmation GO.
- [ ] Keep the 483-patient sealed test and gold outcomes unread until then.
- **Status:** locked — R33A survival gate failed

## Errors Encountered

| Error | Attempt | Resolution |
|---|---:|---|
| Vectorized toy scoring differed from serial by floating-point batch-order roundoff | 1 | Test elementwise numerical equivalence at `atol=rtol=1e-6`; formulas and predictions are unchanged |
| Literal 1,600/300/483 split left only 2,357 patients after mandatory gold quarantine | 1 | Registered protocol v1.1 before any model run: preserve 300 dev and 483 sealed test; use 1,574 train and keep the 26 gold patients quarantined |
| First v1.1 audit reported the 26 deliberately quarantined master patients as active gold leakage | 1 | Separate `quarantined_master_patients=26` from `active_gold_patient_overlap=0`; cohort selection itself was correct |
| Qwen smoke script could not import `visualvit` outside an editable install | 1 | Add the repository `src` directory to `sys.path`, matching the other standalone runners |
| Real Qwen BF16 expanded-batch scores preserved argmax but differed from serial scores by 0.17 | 1 | Preserve the failed BF16 diagnostic; run the engineering equivalence reference in FP32 while retaining a separate BF16 exact-64/freeze/no-pixel audit |
| FP32 real-Qwen batch-shape roundoff was 2.96e-5, above the toy-scale 1e-6 assertion | 1 | Protocol v1.2 freezes real-model FP32 equivalence at max abs diff <=1e-4 plus identical argmax; toy deterministic tests remain 1e-6 |
| R33 feature preflight retained the proposal's pre-quarantine 1,900 train+dev count | 1 | Correct to the registered v1.1 split: 1,574 train + 300 dev = 1,874 patients; no feature output had been created |
| First R33 GPU launch was rejected by PyTorch deterministic cuBLAS guard | 1 | Set `CUBLAS_WORKSPACE_CONFIG=:4096:8` before importing torch; failure occurred before any fitted probe or result output |
| R33A Attempt A scoped lint found an unused `defaultdict` import | 1 | Removed the import before feature generation; tests already passed |
| Attempt D treated a comma-separated multi-anatomy string as one intersected region and produced an empty mask | 1 | Split registered anatomy components, build each fixed mask independently, and use their union; failure occurred before feature output |
| Attempt E v1 omitted three legacy runner audit booleans although its adapter and cache were frozen | 1 | Add the explicit audit fields and promote the already-built binary payload to a fresh v2 path without recomputing patches or adapter features |
| Attempt E changed all projection seeds while expanding the relation input, confounding its P3 reference | 1 | Freeze E2 before rerun: preserve every Attempt D projection row and append only the 64 new coherence rows |
| First E2 tensor-comparison command indexed payload keys instead of `payload["features"]` | 1 | Corrected the read-only comparison; no artifact was written or changed |
| Attempt F scoped lint found an unused `Any` import | 1 | Removed the import before feature generation; all focused tests already passed |
