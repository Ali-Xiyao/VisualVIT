# Progress: TIER-CXR-VLM R32-R36

## 2026-07-26 — R32 authority reset

- Read the proposal, empty result registry, R31 final closure, and R31 frozen
  protocol.
- Confirmed HEAD `7c4c51e` and created `codex/r32-tier-cxr-vlm`.
- Archived the completed R29-R31 planning bundle under
  `history/2026-07-26-r31-closure/`.
- Confirmed two RTX 3090 GPUs; GPU 0 is available and GPU 1 is occupied by an
  unrelated Python process.
- Adopted a lightweight provenance policy: no repeated large hash passes;
  identifiers are recorded once at freeze and normal iteration uses structural
  validation.

## Current action

Closed at the first failed survival gate: `STOP_R33_TOKEN_SURVIVAL`. Preserve
the unread 483-patient sealed test and do not start R34-R36.

## 2026-07-26 — R32 source reconstruction

- Confirmed the R31 sealed reserve contains exactly 2,383 patient IDs.
- Rejoined those IDs to the pinned full silver findings and confirmed all five
  labels are present with 23,161 total eligible rows.
- Confirmed local BiomedCLIP and Qwen3-VL-4B-Instruct model directories and a
  compatible CUDA/PyTorch/Transformers environment.
- Corrected the planning wording: "five-class" is a label requirement; the
  frozen split is 1,600/300/483, not five separate partitions.

## 2026-07-26 — Candidate scoring implementation

- Added a single-forward expanded-batch `score_labels_vectorized()` path.
- Added serial-versus-vectorized tests including right-padded prompts.
- The first exact-bit assertion exposed only expected floating-point
  batch-order roundoff; the registered engineering equivalence tolerance is
  now `atol=rtol=1e-6`.

## 2026-07-26 — Pre-model gold-overlap correction

- The first cohort build stopped before split materialization because mandatory
  gold quarantine reduced 2,383 reserve patients to 2,357.
- ID-only source audit localized all 26 overlaps to Chest ImaGenome gold;
  official CheXTemporal gold overlap is zero.
- Registered R32 protocol v1.1 before model execution: master 2,383,
  quarantined 26, train/dev/sealed split 1,574/300/483.
- Gold outcomes, sealed-test metrics, and predictions remain unread.

- The first v1.1 materialization passed counts, five-label support, path, and
  cross-split checks but the audit wired the 26 deliberately quarantined
  master IDs into the active-overlap field. The runtime was preserved as a
  failed engineering artifact; the corrected audit distinguishes master
  quarantine count from active leakage.

## 2026-07-26 — R32 cohort and encoder smoke

- Corrected cohort materialization passed: 1,574/300/483 patients, all five
  support gates, zero active gold overlap, zero cross-split patient/study/image
  overlap, and zero missing images.
- Added the hierarchical exact-64 robust/rich token builder, hard consensus
  router, matched random route, OOF contract, and six-type projector.
- Focused token/cache tests pass; the 8-image BiomedCLIP cache smoke passed
  strict 150/150 loading with frozen `[197,768]` features on GPU 0.
- The first Qwen CLI attempt exposed a missing standalone `src` import path;
  fixed before model loading or inference.
- The BF16 Qwen exact-64 path passed placeholder, physical-attention, frozen,
  no-pixel, finite-score, and intervention checks, but expanded-batch versus
  serial scores differed by up to 0.17 despite identical argmax. This is an
  engineering precision issue, not a scientific outcome; the failed diagnostic
  is preserved and an FP32 equivalence reference is being run.
- FP32 reduced real-Qwen serial/vectorized maximum difference to `2.96e-5`
  with identical argmax. Protocol v1.2 records a standard `1e-4` FP32
  real-model tolerance; deterministic toy tests remain at `1e-6`.

## 2026-07-26 — R32 formal closure

- Full patch cache completed for 10,562 train/dev images in 42 shards,
  3,196,577,676 bytes, 160.54 seconds on GPU 0.
- Gold availability audit confirmed 16 untouched image-ready patients and
  blocked confirmatory R35 claims without reading outcomes.
- Full pytest passed: 559 passed and one registered xfail.
- R32 scoped Ruff and compile checks passed. The repository-wide lint command
  also surfaced pre-existing E402/F401/F541 debt in historical scripts; those
  frozen files were intentionally not mutated.
- Restored the historical `qwen_adapter.py` byte-for-byte after the full-suite
  frozen-hash test detected drift; R32 vectorization now lives only in the new
  `tier_cxr_vlm.py`.
- Filled the R32 result registry and wrote
  `reports/R32_TIER_CXR_VLM_AUTHORITY_ENGINEERING_RESULT.md`.
- Formal verdict: `GO_R32_READY_R33`.

## 2026-07-26 — R33 feature preparation

- First preflight stopped before feature output because it still expected the
  proposal's pre-quarantine 1,900 train+dev patients.
- Corrected the invariant to the v1.1 authority count, 1,874 patients
  (1,574+300); 15,698 persistent-label rows are eligible.
## 2026-07-26 R33 execution note

- The first formal R33 launch stopped before its first fitted probe because
  deterministic CUDA requires `CUBLAS_WORKSPACE_CONFIG=:4096:8`.
- Registered the environment setting in the runner before importing torch.
- No result artifact was created and no sealed-test or gold data was accessed.

## 2026-07-26 — R33 formal closure

- Prepared 15,698 exact-64 token summaries for 1,874 train/dev patients from
  the frozen R32 patch cache; no sealed-test image was read.
- Completed true 5-fold nested patient-OOF route construction and P0-P7
  evaluation in 229.92 seconds on GPU 0.
- P6 hard-consensus TIER scored 0.4516 versus 0.4583 for P3 robust:
  -0.669 pp with 10,000-bootstrap 95% CI [-1.443, +0.109] pp.
- Seed deltas were +0.405, -0.734, and -1.665 pp.
- Prior-shuffle routed delta was +0.422 pp and did not attenuate as required.
- Registered `STOP_R33_TOKEN_SURVIVAL`; scientific gates did not qualify for
  fresh-process reproduction.
- Audited that P0 is a query/control proxy rather than literal query-only
  because token type 0 contains three image-derived global controls. The STOP
  remains supported by multiple P0-independent failures.
- R34-R36 remain locked; the 483-patient sealed test and gold outcomes remain
  unread.
