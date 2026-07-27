# Archived Progress: TIER-CXR-VLM R32-R36

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

R33A forensic case study on the 1,574-patient train partition. Preserve the
300-patient dev split for one frozen-candidate confirmation and keep the
483-patient sealed test and gold outcomes unread.

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

## 2026-07-26 — R33A rescue opened

- User authorized continued case-study-driven mechanism repair after R33 STOP.
- Preserved R33 as immutable negative evidence and opened R33A as a distinct
  exploratory protocol lane.
- Restricted case-level iteration to the 1,574-patient train partition; the
  300-patient dev split is reserved for one frozen-candidate confirmation.
- Initial code audit identifies two high-priority hypotheses: a randomly frozen
  token builder and a route target based on label-prediction agreement rather
  than expected rich-over-robust benefit.
- R34 sealed test and gold outcomes remain locked.
- Compared the implementation against proposal Sections 11 and 14. The
  proposal permits trained resamplers/relation adapters/token MLP/projector,
  while R33 froze a randomly initialized token builder and fixed random
  768-to-64 compression. Registered this as the first mechanism-level failure
  rather than rerunning the same configuration.
- Built the R33A train-only failure registry (13,566 rows, 1,574 patients).
  Rich-helped and rich-harmed rates are 11.00% and 11.58%; hard consensus has
  only 47.67% help precision and net -136 selected help-minus-harm units.
- Confirmed substantial case-oracle headroom (+10.60 pp) but no deployable
  route enrichment. This motivates rebuilding competent expert/token
  representations before testing a new router.
- Attempt A direct-transition features completed in 19.2 seconds from the
  existing cache. Nested OOF completed in 185.3 seconds.
- Attempt A improved robust P3 to 0.4874 and made literal query-only/global
  controls meaningful, but P6 remained below P3 by 0.461 pp
  (CI [-1.298,+0.357] pp) with all three seed deltas negative.
- Registered Attempt B before execution: preserve Attempt A tokens and replace
  unanimity with a fully cross-fitted rich-benefit router.
- Attempt B completed in 193.7 seconds and failed: P6-P3 -0.676 pp,
  CI [-1.539,+0.162] pp, all seed directions negative.
- Post-attempt output-fusion case study found R31-style unanimous-rich /
  robust-majority reaches 0.49963 (+1.223 pp over pooled P3), while direct
  benefit routing gives essentially zero gain. Registered Attempt C to test a
  capacity-matched nonlinear common token reader rather than tuning routes.
- Attempt C completed in 296.1 seconds and failed: P6-P3 -0.468 pp,
  CI [-1.337,+0.358] pp. P3 improved to 0.4946 while P4 stayed at 0.4794,
  excluding reader capacity as the main bottleneck.
- Registered Attempt D to restore R31's anatomy-aware exact/context transition
  structure from cached 14x14 patches.
- Attempt D's first preflight stopped before feature output on a mixed
  costophrenic/upper-lung anatomy string. Corrected multi-anatomy handling to
  union independently valid component masks rather than intersect conflicting
  vertical constraints.
- Attempt D features completed in 17.7 seconds; nested OOF completed in 193.8
  seconds. P6-P3 improved to -0.082 pp (CI [-0.882,+0.724]) with two positive
  seeds, but prior shuffle still failed.
- A fair seed-majority analysis shows R31-style output routing adds only 0.051
  pp over majority P3 on Attempt D. Opened a train-only benefit-learnability
  case study before choosing the next mechanism mutation.
- Benefit-learnability v2 found a real but sub-threshold signal: logits-only
  cross-fold routing gives +1.003 pp over P3. Token geometry and confidence
  thresholds worsen it, so both are rejected.
- Benefit-learnability v3 added fixed finding-by-expert interactions. Direct
  routed F1 is 0.50436, +1.074 pp over pooled P3, but decisive accuracy drops
  to 61.52% and every threshold above 0.50 is worse. This route family remains
  below gate and is closed.
- Attempt E is now the active hypothesis: introduce an explicit
  prior/current-coherence relation while preserving the cached patch tensors,
  train-only scope, and sealed dev/test/gold boundaries.
- Froze Attempt E before execution. Both GPUs are currently occupied by
  unrelated `r1_local_differential_eval.py` shards, so feature preparation is
  assigned to CPU and no existing GPU process will be stopped or contended.
- Attempt E feature preparation completed on CPU in 122.1 seconds. The
  outcome-free adapter separates real pairs from the untouched formal
  prior-shuffle mapping with AUC 0.9353 and accuracy 0.8487.
- Pre-run payload validation found that v1 omitted three legacy boolean audit
  fields required by the common R33 runner. The underlying tensors are valid;
  register the booleans in a fresh v2 payload without recomputing cached
  patches, hashes, or adapter features.
- Attempt E OOF completed on CPU in 313.5 seconds. It is the first attempt to
  pass prior-shuffle attenuation and has a positive +0.571 pp mean delta, but
  misses +2 pp, CI, and all-seed gates.
- Full-metric review found a projection-seed confound: P3 drifted to 0.48668
  because all block projections changed. E2 was frozen before execution to
  preserve every Attempt D projection row and append only the new coherence
  rows. Attempt E remains immutable and cannot be promoted.
- E2 features completed from the existing patch cache in 136.6 seconds. The
  robust and prior-shuffle-robust summaries match Attempt D within one
  float16 quantization step (maximum absolute difference 0.001953125 for every
  seed). Projection-matched train-only OOF is running on CPU.
- E2 projection-matched OOF stopped: P6-P3 -0.098 pp, CI
  [-0.906,+0.707] pp, prior-shuffle +0.511 pp. The projection-matched result
  rejects the coherence adapter as a sufficient bridge.
- Froze Attempt F before execution: outcome-free 256-dimensional per-type
  prebridge followed by a fold-trained 64-unit bottleneck for every
  capacity-matched system. Seven focused tests pass; the only scoped lint issue
  was an unused import removed before feature generation.
- Attempt F completed in 810.2 seconds and stopped: P3 0.50720, P4 0.50741,
  P6 0.50597, delta -0.123 pp with CI [-0.936,+0.693] pp. The rich expert is
  now capacity-matched and equally competent, but consensus selection has
  essentially zero net correction and prior-shuffle still fails.
- Froze Attempt G before execution. It keeps the learned bridge and changes
  only the route target to the previously implemented fully cross-fitted
  rich-benefit rule. A failure closes benefit routing on this frozen cache.
- Attempt G completed in 930.8 seconds and stopped: P6 0.50504 versus P3
  0.50720, delta -0.217 pp with CI [-1.033,+0.581] pp. Seeds 17/29 are
  negative; prior-shuffle does not meet registered attenuation.
- Registered `STOP_R33A_FROZEN_CACHE_PREMISE`. No train-only candidate can be
  frozen for dev; the 300 dev patients, 483 sealed-test patients, and all gold
  outcomes remain uninspected in R33A.
- Final verification passed: 579 pytest tests passed with one registered
  historical xfail; all R33A scoped Ruff checks and script compilation passed.
