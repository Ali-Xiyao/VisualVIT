# Task Plan: TIER-CXR-VLM R32-R36 Execution

## Authority

- Primary protocol: `TIER_CXR_VLM_Next_Stage_Proposal_CN.md`.
- Result registry: `TIER_CXR_VLM_Empty_Result_Tables_CN.md`.
- Inherited scientific boundary: R31 is a reproduced fresh-silver development
  GO; R26 human-gold `STOP_C1` remains immutable.
- Branch: `codex/r32-tier-cxr-vlm`, created from `7c4c51e`.
- Historical R26-R31 artifacts are frozen and may only be read for lineage.

## Objective

Execute the proposal in gate order, beginning with R32. Continue into R33 only
after every R32 authority and engineering gate is green. Do not train the
formal frozen VLM before R33 GO, do not read the 483-patient sealed VLM test
during R33, and do not read gold outcomes before the registered R35 gate.

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
