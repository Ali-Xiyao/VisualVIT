# Progress: PRTA-CXR R37

## 2026-07-27 — Scientific pivot opened

- Read the user-provided R37/PRTA-CXR execution handoff.
- Confirmed clean predecessor commit `85f3951`.
- Created branch `codex/r37-prior-responsive-temporal-adapter`.
- Archived the completed R33A planning bundle under
  `history/2026-07-27-r33a-frozen-cache-closure/`.
- Registered that R33/R33A results and routing surfaces are frozen lineage.
- Registered the protected-data boundary: no 300 dev, 483 test, or gold
  outcome access before model and protocol freeze.
- Active work is R37A protocol and read-only source/asset feasibility audit.
- Verified the CheXTemporal primary source and recorded why its silver resource
  is evaluation-only rather than an R37 training corpus.
- Located local MIMIC-CXR-family, Chest ImaGenome, and BiomedCLIP assets without
  reading protected outcomes.
- Recorded current disk capacity; `H:` is the provisional cache volume pending
  an exact Block-8 cache-size estimate.
- Confirmed that BioViL-T is not evident in the top-level local model
  inventory, so A1 remains availability-gated.
- Resolved the MIMIC junctions to their physical dataset roots and confirmed
  that images, reports, official metadata, split, CheXpert, and NegBio tables
  are locally present.
- Inspected the R32 cohort builder to identify safe structural exclusion
  sources. The sealed label file remains unopened.
- Determined that R37A must enumerate the full official MIMIC longitudinal
  timeline rather than reuse the narrow R31/R32 reserve cohort.
- Confirmed the official MIMIC metadata/split columns needed for ordered
  patient timelines and verified local image/report roots.
- Performed an ID-only protected-cohort count check: 1,574 train, 300 dev, and
  483 sealed-test patients remain structurally separable; no protected outcome
  was emitted or used.
- Chose the stricter R37 independence boundary: exclude every R32 patient
  (including the old 1,574 train patients) plus all quarantined gold patients.
- Identified reusable deterministic MIMIC timeline/image-path mechanics and the
  strict local BiomedCLIP loader.
- Confirmed that the R37 cache needs a new Block-8 extraction boundary but can
  retain R32's sharding, finite-value checks, and no-per-shard-hash policy.
- Froze the executable R37 protocol at
  `docs/superpowers/specs/2026-07-27-r37-prta-cxr-protocol-v1.md`.
- Implemented the R37 structural cohort builder and outcome-firewalled
  forbidden-patient registry.
- Added five focused tests covering deterministic patient splitting, official
  MIMIC paths, PA preference, forbidden-patient/same-day exclusion, and
  ID-only protected-registry construction; all five pass.
- Started the one-time full MIMIC structural enumeration with real image/report
  existence checks. The resulting manifest will be reused without another
  whole-dataset scan.
- Completed the structural enumeration: 108,732 pairs, 27,223 patients, and
  144,423 unique images with zero forbidden-patient or split overlap.
- Estimated the full Block-8 FP16 cache at 40.70 GiB, confirming `H:` has
  sufficient capacity.
- Corrected an audit-only reverse-boolean bug in place; the manifests were not
  regenerated and the dataset was not rescanned.
- Implemented the first deterministic report-transition extractor with
  finding-scoped cues, temporal-section filtering, negated-change rejection,
  Impression priority, and CheXpert contradiction checks.
- Added five extractor tests; the combined R37 data/extractor suite now has 10
  passing focused tests.
- Started the full transition-support pass. Its output remains provisional and
  cannot unlock adapter training until the stratified case-study gate passes.
- The full transition pass remains healthy but I/O-bound while reading the
  already-filtered report files; it is being allowed to finish once rather
  than interrupted and restarted.
- Implemented the exact Block-8 cache boundary and added two focused tests.
- Completed a 64-image GPU smoke with bit-identical repeated output, correct
  token shape, frozen encoder, and no protected outcome access.
- Deferred the 144,423-image formal cache until transition support/quality
  passes; single-GPU smoke throughput predicts an approximately 8.8-hour run.
- Completed a larger 512-image/batch-128 cache benchmark at 6.57 images/s;
  revised the one-GPU estimate to about 6.1 hours and retained exact repeated
  outputs.
- Added deterministic two-part formal-cache slicing and a merger that verifies
  complete DICOM coverage with no cross-part overlap; all three cache-focused
  tests pass.
- At the 30-minute checkpoint, the first full transition extraction remained
  responsive with bounded memory and no error output; it was not restarted or
  duplicated.
- Completed transition v1, confirmed five-class count support, then rejected it
  after a 200-row case study found systematic scope errors.
- Implemented and ran transition v2 with 16 reader threads; runtime dropped to
  roughly 2.5 minutes while all class-support gates remained above threshold.
- Rejected v2 for formal training because New/Worse still include reproducible
  uncertainty and alternative-scope errors. A conservative v3 precision pass
  is required.
- Implemented and ran v3 after fixing sentence-level context loss around
  `or`; all 19 focused tests pass.
- v3 retains broad five-class support but remains provisional because the
  case study found a small, coherent set of history/question/technique scope
  errors. One final v4 precision pass is in progress.
- Inspected the original reports behind five v3 false positives and confirmed
  their causes directly: indented HISTORY, portable-technique artifact, `No
  new`, and `No ... newly` scope. v4 targets these exact failures.
- Completed v4 with 22 focused tests passing and all five class-support gates
  retained.
- Reviewed the full deterministic 200-row v4 case sheet; two rows require
  original-report adjudication before the ruleset is frozen.
- Completed v4.1 with 24 focused tests passing and 33,621/3,770 eligible
  transition pairs in pretrain/calibration.
- Froze the v4.1 Codex case-study result at 194/200 (97.0%), with every class
  above 92.5%; documented residual errors instead of further tuning.
- Kept formal human/radiologist QA explicitly pending before R37B is called a
  formal training run.
- Checked live GPU state before formal caching. Both GPUs are occupied by
  unrelated repair-discovery evaluation shards, so the R37 full cache was
  correctly not started.
- Implemented the PRTA temporal adapter, frozen-tail gradient boundary,
  state/transition resamplers, and transition/CMCP/inversion/state losses.
- The combined R37 focused suite now has 30 passing tests.
- Added a conservative idle launcher that requires three consecutive
  low-memory polls before starting two non-overlapping cache parts, then
  automatically merges and verifies full DICOM coverage.
- Implemented the formal CMCP index builder and three focused matching tests;
  current-matched retrieval cannot run until the full Block-8 cache merges.
- Verified the idle launcher remains in `WAITING_FOR_GPU_IDLE` and has not
  started R37 cache workers while the unrelated jobs remain resident.
- Closed the R37A access-boundary audit for local internal execution: no new
  authentication is needed, while CITI/project-DUA and redistribution remain
  explicitly uncertified external-release boundaries.
- Ran the complete repository suite after the R37 checkpoint:
  612 passed and one historical xfail in 286.76 seconds.
- `git diff --check` passed; only Windows LF-to-CRLF working-copy notices were
  emitted.
- Committed the first R37 checkpoint as `83a4fda` and pushed
  `codex/r37-prior-responsive-temporal-adapter` to `origin`.
- Added the frozen A0-A7 ablation registry and trainable 512-to-768 text/visual
  heads; eight PRTA tests pass.
- Cached 12 finding and 60 transition BiomedCLIP text prototypes on CPU without
  protected outcome access.
- Added and tested the merged-cache random-access layer.
- Implemented the unified A2-A6 end-to-end engineering runner with balanced
  deterministic sampling, gradient audits, current-only control, checkpoint
  output, and formal-mode human-QA firewall.
- Verified the official public BioViL-T repository metadata through `hf`: the
  selected revision is `692f09e9be1bfe5fdd5f3efdd0e1eca7d2c10b23`, and only
  the README, config, and 110 MB image checkpoint are required for A1.
- The first selective `hf download --dry-run` encountered a local
  proxy/metadata HEAD error. No asset was downloaded; the retry is narrowed to
  one explicit file at a time and will not fetch the full 1.10 GB repository.
- Located the download failure in the global `HF_ENDPOINT=https://hf-mirror.com`
  setting. Without changing that global setting, a process-local official Hub
  endpoint downloaded the three selected files successfully.
- The local BioViL-T bundle now contains the MIT model card, 803-byte config,
  and 109,745,561-byte image checkpoint. No full text-model bundle or
  unneeded repository asset was downloaded.
- Loaded the image checkpoint on CPU with `weights_only=True`: it is a
  372-entry state dictionary rooted at `encoder.*`, consistent with the
  official ResNet-50 plus temporal-transformer implementation.
- Confirmed the linked Microsoft `hi-ml` repository is archived/read-only and
  pinned its final HEAD at `b67c1d27c6b17d8e8ff01f8c507f3cabdb307388`.
  No `health-multimodal` PyPI distribution exists in this environment, so the
  A1 loader will use this exact official source rather than an inferred clone.
- Rechecked the cache launcher after the baseline asset work: it remains
  healthy in `WAITING_FOR_GPU_IDLE`, with no R37 worker spawned.
- Cloned only the official `hi-ml-multimodal` subtree at the pinned archived
  commit into the runtime external-dependency area. It remains outside Git and
  requires no installation into the active Python environment.
- A CPU smoke constructed the official ResNet-50 multi-image encoder, loaded
  every checkpoint key strictly with `weights_only=True`, and produced finite
  `[1, 512, 14, 14]` patch plus `[1, 512]` pooled paired-image features.
- Before any A1 outcome evaluation, froze the official 512-resize/448-crop
  preprocessing, current/prior argument order, normalized canonical 128-D
  projected global feature, and a five-class linear probe conditioned by a
  fixed 12-finding one-hot vector.
- Six focused A1 loader/cache unit tests pass. The first real pair smoke then
  exposed that HI-ML's `ImageModel` outer wrapper is single-image even with a
  multi-image encoder; the implementation was corrected to the official
  parameter-compatible `MultiImageModel` before producing any A1 result.
- The corrected two-pair real-image CPU cache smoke passed with strict
  revisions, 128-D FP16 output, finite normalized features, repeated-inference
  maximum absolute difference 0, and both outcome/hash firewalls false.
- Measured CPU throughput is only 0.164 pair/s. This is sufficient for a tiny
  end-to-end probe smoke but not a substitute for the queued GPU cache.
- Completed the 10-train/5-calibration A1 engineering case study. The probe
  optimized normally and only its 705 parameters received gradients, but
  true-pair and current-only predictions were identical with zero macro F1;
  inverted predictions differed and scored 0.333 on the five-row calibration.
- Classified that result as `PASS_R37_A1_ENGINEERING_PIPELINE` with scientific
  status `NOT_EVALUATED_TINY_SMOKE`. It neither supports BioViL-T nor unlocks
  formal R37B.
- The idle launcher observed GPU 0 release first and then one joint-idle poll,
  but both devices returned to roughly 18.9/18.5 GB use before the required
  three confirmations. It correctly remained in `WAITING_FOR_GPU_IDLE`; the
  new owners must be identified before assuming they are R37 workers.
- Identified the new owners as unrelated R1
  `repair_discovery_controls_v1` workers (PIDs 18548 and 32756). They began at
  13:04 on cuda:0/1; no R37 process was spawned or killed.
- Added `reports/R37_A1_BIOVILT_ENGINEERING_CASE_STUDY.md` with the API failure,
  repair, tiny negative control result, evidence limits, and the frozen next
  attempt.
- The second-checkpoint focused suite passed 21/21 tests.
- The complete repository regression passed 627 tests with one unchanged
  historical R14 expected-xfail in 292.82 seconds.
- Created the second R37 engineering checkpoint containing only code, tests,
  protocol/planning documents, and case-study documentation. Runtime data,
  caches, official model assets, and protected artifacts remain outside Git.
- Froze the remaining A0 representation before its first result: unmodified
  Blocks 9-12 plus final norm, normalized current-minus-prior CLS, and the same
  fixed finding-conditioned linear probe/control definitions as A1.
- Froze internal confidence intervals as 2,000 deterministic patient-cluster
  percentile bootstrap replicates with seed 37001; row-level bootstrap is not
  permitted.
- Implemented the A0 final-CLS difference encoder, frozen finding-conditioned
  probe runner, generic qualification probe, patient-cluster bootstrap, and
  three-seed survival gate.
- The new A0/qualification suite passed 14 tests and Ruff reported no issues.
  A0 execution remains pending the merged full Block-8 cache.
- Added patient IDs and per-row true/current/inverted/CMCP predictions to the
  evaluation artifacts and implemented the formal seed-17/29/43 aggregator.
- The aggregator uses one shared patient-cluster draw per bootstrap replicate,
  averages the three seed differences, and fails closed on seed, row-order,
  variant, outcome-firewall, or human-QA-unlock drift.
- The expanded focused suite passed 21 tests; Ruff again reported no issues.
- Audited the A1 execution path against the user's no-recomputation request.
  The engineering runner still re-encoded controls per seed, so the formal
  contract is tightened to one transition-pair control cache reused by all
  findings and seeds before any formal result.
- Implemented A1 v2 true/current-only/inverted control shards, two-part
  merge/coverage audit, bounded random access, and formal-run cache enforcement.
- The transition-only inventory contains 37,391 unique qualified pairs rather
  than all 108,732 structural pairs.
- A two-pair real-image v2 CPU smoke passed all three 128-D controls, exact
  repeated true-pair inference, outcome/hash firewalls, and random-access
  retrieval. CPU throughput was only 0.057 pair/s for four forward passes, so
  the full cache remains GPU-only.
- Rechecked the live launcher at 13:28: both GPUs remain occupied at roughly
  20.9/19.8 GB and R37 is still correctly waiting with zero idle polls.
- The third-checkpoint complete repository regression passed 639 tests with
  one unchanged historical R14 expected-xfail in 370.81 seconds.
- Froze the post-cache engineering order: Block-8 merge, CMCP gate, bounded
  A0/A3/A6 case studies, one-time two-GPU A1 control cache, then cached A1
  probing. Every GPU stage rechecks sustained idle state and every stage is
  resumable from its own PASS artifact.
- Implemented the post-cache watcher with atomic status updates, sustained
  two-GPU idle checks, exact PASS-artifact resume rules, parallel A1 parts,
  and fail-closed handling of partial or failed outputs.
- The watcher-focused suite passed 5 tests and Ruff reported no issues.
- The first watcher process safely stopped before any experiment because the
  PowerShell launcher status contains a UTF-8 BOM. No cache/output was
  partially created; the reader is being hardened with a BOM regression test.
- The BOM regression test and Ruff pass after the repair. The watcher restarted
  as PID 17856 and now reports `WAITING_FOR_BLOCK8_CACHE` while observing the
  original launcher's `WAITING_FOR_GPU_IDLE` state.
- Created the thread heartbeat automation `r37-prta-post-cache-monitor` so this
  task periodically rechecks the two local status files, repairs protocol-safe
  STOPs, pushes tested changes, and reports changed scientific state without
  duplicating processes or touching protected outcomes.
- 2026-07-27 15:02 +08:00: the sustained-idle gate passed after three
  confirmations (`333/0 MiB` at the final poll). The existing launcher started
  exactly two formal Block-8 workers, PID 36292 on cuda:0 and PID 24792 on
  cuda:1. No duplicate worker, protected-outcome read, or source/per-shard hash
  recomputation was observed.
- 2026-07-27 15:07 +08:00: the post-cache watcher PID 17856 is alive and
  reports `WAITING_FOR_BLOCK8_CACHE`; scientific status remains not evaluated
  while the formal cache is running.
- 2026-07-27 15:41 +08:00: both Block-8 workers completed all 283 shards and
  wrote `PASS_R37_BLOCK8_FORMAL_CACHE` with empty stderr logs. The launcher
  received null process exit-code fields, falsely emitted
  `STOP_R37_BLOCK8_CACHE_PART_FAILURE`, and therefore did not run the merge.
- The post-cache watcher then stopped fail-closed on that launcher status.
  No protected outcome was read and no hash was recomputed. Recovery is
  limited to validating the existing PASS manifests, merging them, and
  restarting only the stopped post-cache watcher.
- 2026-07-27 15:46 +08:00: strict merge recovery PASSed over the existing two
  part manifests: 144,423 images, 566 shards, no overlap, no protected outcome
  read, and no source/per-shard hash computation. Block-8 was not rerun.
- Patched the launcher to classify only known nonzero child exit codes as
  process failures and retain the strict merger as the artifact authority.
  PowerShell syntax parsing, 10 focused tests, Ruff, and `git diff --check`
  passed.
- 2026-07-27 15:47 +08:00: restarted only the stopped post-cache watcher as
  PID 25564. It recognized the merged PASS manifest and advanced to
  `RUNNING_CMCP`.
- CMCP completed with `PASS_R37A_CMCP_COVERAGE` and 100% coverage over 26,041
  dynamic examples. Bounded A0, A3, and A6 then completed with engineering
  PASS artifacts and no scientific claim.
- 2026-07-27 16:00-16:06 +08:00: the one-time A1 true/current/inverted cache
  ran on both GPUs and merged with `PASS_R37_A1_CONTROL_CACHE_MERGED` over
  37,391 unique pairs.
- 2026-07-27 16:07 +08:00: the cached CPU A1 probe stopped before result
  writeback with `mat1 and mat2 must have the same dtype, but got Half and
  Float`. No image cache or hash will be recomputed; repair is limited to
  casting probe inputs to FP32.
- Promoted cached canonical features to FP32 only at the linear-probe tensor
  boundary and added an FP16 regression test. Thirteen focused tests, Ruff,
  and `git diff --check` passed.
- Restarted only the stopped watcher. It skipped every existing PASS artifact,
  reused the 37,391-pair cache, completed the A1 probe, and wrote
  `PASS_R37_POST_CACHE_ENGINEERING_PIPELINE` at 16:08.
- Case-study readout: A0 true-current +18.41 pp; A1 +6.56 pp; A3 and A6
  true-current 0.00 pp with exactly identical predictions; A6 true-CMCP also
  0.00 pp on 40 dynamic rows. These are tiny engineering results and do not
  unlock scientific qualification.
- Added continuous PRTA responsiveness diagnostics at evaluation time for
  true/current-only, true/inverted, and true/CMCP comparisons. Twelve focused
  tests, Ruff, and `git diff --check` passed.
- Froze the next engineering attempt at the already-coded non-formal cap:
  A6 seed 17, 1,000/500 rows, 3 epochs, batch size 2, rank 32, and LR 1e-4.
  Formal mode and protected outcomes remain locked.
- 2026-07-27 16:13 +08:00: after three consecutive low-memory confirmations,
  launched the frozen A6 mechanism-scale diagnostic as PID 29628 on cuda:0.
  The process is responsive; cuda:1 remains free. Output is isolated at
  `r37b_smokes/a6_seed17_mechanism_scale1000x500x3_v1`.
- 2026-07-27 16:25 +08:00: A6 mechanism scale completed with engineering
  PASS. True-current, true-inverted, and true-CMCP macro-F1 differences were
  +6.84, +14.91, and +6.97 pp, with nonzero continuous embedding/logit
  responsiveness.
- Froze this result as positive engineering evidence and stopped further
  calibration tuning. Formal qualification remains locked until independent
  transition human QA, followed by the frozen three-seed patient-bootstrap
  gate.
- The user authorized continuing all remaining work. Began a reviewer-ready
  human-QA handoff plus a fail-closed validator; only the independent judgments
  themselves require a human reviewer.
- The user then explicitly deferred human QA to the end of the project.
  Stopped that packet work before implementation and redirected the current
  phase to frozen seed-29/43 engineering replication and formal-runner
  preflight.
- 2026-07-27 16:30 +08:00: after three consecutive two-GPU idle
  confirmations, launched the frozen seed-29 and seed-43 A6 replications as
  PID 23416 on cuda:0 and PID 1952 on cuda:1. Both use the unchanged
  1,000/500/3-epoch, batch-2, rank-32, LR-1e-4 configuration; both stderr logs
  are empty at startup.
- 2026-07-27 16:42-16:45 +08:00: seed 29 and seed 43 completed with
  `PASS_R37_PRTA_ENGINEERING_SMOKE`; both stderr logs remained empty and both
  GPUs were released.
- Across seeds 17/29/43, true-current differences were +6.84/+8.97/+7.54 pp
  and true-CMCP differences were +6.97/+8.85/+5.77 pp. This is positive
  multiseed engineering evidence, not a formal scientific result.
- Added `reports/R37_A6_ENGINEERING_MULTISEED_CASE_STUDY.md` with the frozen
  settings, per-seed metrics, continuous prediction-change diagnostics,
  earlier-failure comparison, runtime evidence, and protected-outcome
  boundary.
- 2026-07-27 17:00 +08:00: began formal-bundle preflight hardening under the
  frozen A6 configuration. Scope is specification, fail-closed validation,
  fixtures/tests, readiness manifest, and handoff only; formal training and
  protected 300-dev/483-test/gold evaluation remain locked.
- Added the first machine-readable formal A6 bundle specification and a
  read-only preflight command covering transition, Block-8, text-cache, CMCP,
  seed-output, bootstrap, and outcome-firewall contracts.
- Repaired the dormant formal runner path so it requires the exact frozen A6
  configuration and all seed-independent finding rows. The later launch guard
  exposed that the original bundle mislabeled 33,621/3,770 eligible pairs as
  row counts; the corrected full-row counts are 46,349/5,242.
- Tightened the formal aggregator to accept only firewall-clean formal A6
  training artifacts and reject engineering-smoke, sealed-test, gold,
  source-hash, variant, seed, or human-unlock drift.
- Added focused tests for full seed-independent formal row selection, exact
  formal argument freezing, patient-bootstrap constants, row-order and
  outcome-firewall drift, pending/unlocked readiness states, and partial-output
  rejection. The first standalone `pytest.exe` invocation hit the known
  namespace-import path boundary; Ruff and `git diff --check` passed.
- The corrected focused suite passed 12/12. The real runtime preflight then
  passed every check and wrote
  `H:\VisualVIT_runtime\050_routeD\r37_prta_cxr\r37_formal_bundle_preflight.json`
  with `READY_R37_FORMAL_BUNDLE_PENDING_HUMAN_QA`; no hash or protected
  outcome was read and no GPU process was started.
- Operationalized the previously underspecified auxiliary gates before formal
  outcomes: inverse-label consistency >=0.90 and adapted/frozen-current cosine
  retention >=0.99 in every seed.
- Hardened the A0 formal baseline to the same complete seed-independent
  finding-row order as A6 and added paired A6-minus-A0 patient-cluster
  aggregation.
- The expanded focused suite passed 30/30 and Ruff passed. Real A6 and A0
  formal guard probes both exited nonzero on the pending human-QA audit,
  created no output directories, and started no training.
- Added `reports/R37_FORMAL_BUNDLE_PREFLIGHT.md` as the handoff surface for the
  frozen specification, checks, runtime manifest, commands, and scientific
  boundary.
- Complete repository regression passed 656 tests with one unchanged
  historical R14 expected-xfail in 202.63 seconds. Focused Ruff, compileall,
  `git diff --check`, and a final real runtime preflight also passed.
- Final runtime status remains
  `READY_R37_FORMAL_BUNDLE_PENDING_HUMAN_QA`, with
  `engineering_preflight_passed=true`,
  `formal_execution_allowed=false`, and no protected outcome or hash access.
- The user authorized preparing the independent human-QA handoff. Verified the
  frozen local sheet has exactly 200 rows, 40 per class, and blank QA fields;
  began a reviewer-facing Chinese guide plus fail-closed return validator.
- Added `reports/R37_TRANSITION_HUMAN_QA_REVIEW_GUIDE_CN.md` with the review
  question, five label definitions, fixed error taxonomy, CSV editing rules,
  privacy boundary, reviewer attestation, and return checklist.
- Added a fail-closed validator that requires 200 unique cases, 40 per class,
  complete TRUE/FALSE judgments, valid error categories, reviewer attestation,
  >=90% overall accuracy, and >=85% accuracy in every class before emitting an
  unlockable PASS.
- Validator tests passed 5/5, Ruff and `git diff --check` passed, and a real
  blank-sheet check produced the required STOP without unlocking training.
- Created the local review work copy
  `r37_transition_case_study_REVIEWED.csv` and placed the Chinese guide beside
  it in the controlled transition directory. The CSV remains outside Git.
- 2026-07-27 18:01 +08:00: received the completed local review sheet and
  checked it without reading protected outcomes or recomputing hashes. All
  200 rows are complete, 195 are TRUE, and the frozen overall/per-class
  thresholds pass.
- Verified exact source integrity without hashing: the reviewed file retains
  all 200 case IDs in order, the original column order, and unchanged non-QA
  fields. The five FALSE rows use five valid taxonomy categories.
- Hardened the reviewer validator to require the frozen source CSV, reject
  column/order/row/non-QA drift, validate the transition-audit firewall, and
  atomically apply the formal unlock only after a full PASS.
- The focused validator plus formal-preflight suite passes 12 tests; Ruff,
  compileall, and `git diff --check` pass.
- Current state is `STOP_R37_TRANSITION_HUMAN_QA` only because the reviewer
  name or institutional ID, professional role, relevant experience, ISO
  review date, and explicit independent-review confirmation have not been
  supplied. No GPU job was started.
- The user supplied reviewer ID `doctor 1`, role `professor` after obvious
  spelling normalization, review date `2026-07-27` after ISO normalization,
  and the exact independent-review confirmation. The reviewer explicitly
  declined to provide experience; this will be recorded as `not provided`
  rather than fabricated.
- Relevant experience is retained as optional attestation metadata because it
  was not a frozen numerical gate and the original validator contract required
  identity, professional role, date, and independent confirmation.
- Human QA emitted `PASS_R37_TRANSITION_HUMAN_QA`; the transition audit now
  has `formal_training_unlocked=true`, and the refreshed preflight emitted
  `READY_R37_FORMAL_BUNDLE` with all six A6/A0 seed outputs fresh.
- Added a duplicate-safe two-GPU formal pipeline with per-device queues,
  three-poll idle confirmation, fresh/complete output checks, status/log
  artifacts, and automatic current-only/CMCP/A0 patient-bootstrap aggregation.
  Sixteen focused QA/preflight/pipeline tests passed before launch.
- 2026-07-27 18:59 +08:00: the pipeline launched A6 seeds 17 and 29 after
  three idle polls, then both stopped in about seven seconds before model
  construction with `formal partition count drift: expected 33621, got
  46349`. GPUs were released, no output directory was created, and no
  protected outcome or hash was read.
- Outcome-free manifest inspection confirmed 46,349/5,242 unique
  finding-level examples over 33,621/3,770 eligible pairs. The next repair is
  count-namespace correction only; model and gate choices remain frozen.
- Registered pair and finding-level counts as separate audit/spec fields,
  updated both A6 and A0 formal constants to 46,349/5,242 finding rows, and
  retained 33,621/3,770 as eligible-pair provenance. Twenty-three focused
  runner, A0, preflight, pipeline, and QA tests pass; Ruff, compileall, and
  `git diff --check` pass.
- The refreshed real preflight again reports `READY_R37_FORMAL_BUNDLE`,
  `formal_execution_allowed=true`, all six output states `fresh`, and every
  outcome/hash firewall false.
- 2026-07-27 19:04 +08:00: relaunched the corrected formal pipeline as PID
  28840 after three sustained-idle polls. A6 seed 17 is PID 18604 on cuda:0
  and seed 29 is PID 11172 on cuda:1; both passed the corrected count guard,
  remain alive, and show increasing CPU time/GPU power.
- The queue will run A6 seed 43 on cuda:0 after seed 17, then the matching A0
  seeds, followed by automatic frozen current-only, CMCP, and A6-minus-A0
  patient-bootstrap aggregation. Linear extrapolation from the 1,000-row
  engineering runs gives an initial 18-22 hour wall-time estimate.
- Created the 20-minute thread heartbeat `r37-formal-bundle-monitor`. It checks
  the status/log/PID/GPU surfaces, forbids duplicate jobs and protected reads,
  repairs only engineering STOPs, and reports the final internal scientific
  GO/STOP.
- 2026-07-27 20:25 +08:00: the user requested a two-seed-first scope. Stopped
  only the queue parent PID 28840 after verifying its exact command; A6 seed
  17 PID 18604 and seed 29 PID 11172 remained alive with increasing CPU time
  and healthy GPU load.
- Removed only the stale single-instance lock left by the stopped parent.
  Updated runtime status to `RUNNING_R37_TWO_SEED_FORMAL_PHASE`, set seed 43
  and every A0 task to `deferred_by_user`, and kept
  `three_seed_gate_eligible=false`.
- Updated the existing heartbeat in place. It now monitors only seeds 17/29,
  must not restart the full pipeline, and will label two complete results
  `PASS_R37_TWO_SEED_FORMAL_TRAINING_ONLY` rather than scientific GO.
- 2026-07-28 02:35-02:57 +08:00: both user-selected A6 formal seeds completed
  with valid `PASS_R37_PRTA_FORMAL_TRAINING` artifacts. The shared preflight
  helper classifies both outputs as `complete`; checkpoints and result JSONs
  are present, and every protected/sealed/gold/source-hash firewall remains
  false.
- Descriptive seed 17 metrics are true-pair/current-only +11.87 pp,
  true-pair/CMCP +7.58 pp, inversion consistency 0.8438, and state retention
  0.9938. Seed 29 reports +14.15 pp, +7.91 pp, 0.8735, and 0.9936,
  respectively.
- Runtime status was closed as
  `PASS_R37_TWO_SEED_FORMAL_TRAINING_ONLY`. No seed 43, A0, bootstrap,
  aggregation, or protected evaluation was started; therefore no scientific
  GO/STOP is claimed.
- 2026-07-28: the user selected the strict repair route. R37 will be frozen at
  the inversion-consistency failure, the observed 5,242-row calibration set
  will be used only for descriptive failure analysis, and R37.1 will require a
  newly held-out patient roster plus a pre-outcome-frozen repair.
- Two initial read-only inspection paths were incorrect. They were resolved
  through the tracked formal specification; no manifest, result, GPU process,
  hash, or protected artifact was changed or accessed.
- Confirmed that R37 formal mode uses the shared PRTA runner rather than a
  separate formal script. The inversion metric compares reversed predictions
  against the fixed mapping Stable→Stable, Improved↔Worse, and New↔Resolved.
- The first case-study read failed before opening result artifacts because the
  repository `src` directory was not on `PYTHONPATH`; the retry will use the
  tracked namespace path.
- The corrected read-only case study aligned all 5,242 calibration examples
  to their frozen manifest order. Seed 17 has 819 inversion-inconsistent rows
  and seed 29 has 663; only 324 failed example IDs overlap.
- Failures concentrate in dynamic labels and six pulmonary findings rather
  than indicating a general data corruption. The next implementation target
  is an exact label-group-equivariant logit projection, frozen before any
  fresh R37.1 validation outcome is read.
- Added and tested a reproducible firewall-aware failure analyzer. Its real
  runtime artifact covers 5,242 rows and 1,347 patients, emits
  `STOP_R37_INVERSION_CONSISTENCY`, and confirms that no protected outcome or
  source/per-shard hash was accessed.
- Added `reports/R37_INVERSION_FAILURE_CASE_STUDY.md` and froze the R37.1
  Z2-equivariant logit projection plus the fresh 1,815-patient holdout rule.
- Updated the runtime formal-bundle status from the descriptive two-seed PASS
  marker to `STOP_R37_INVERSION_CONSISTENCY`. Seed 43, A0, aggregation,
  bootstrap, and protected evaluation remain untouched.
- Implemented the parameter-free equivariant logit projection, a reproducible
  inversion failure analyzer, and a one-shot R37.1 patient-holdout builder.
  Sixteen focused tests pass; Ruff and `git diff --check` also pass.
- After commit `3730f10` froze the repair and split rule, generated
  `r37_1_transitions_v1` exactly once. It reports
  `READY_R37_1_FRESH_HOLDOUT`, 10,287/1,815 disjoint train/validation
  patients, 39,491/6,858 examples, all five labels present, and every
  protected/hash firewall false.
- The first combined runner integration patch was rejected before changing the
  file because its import context did not match the live ordering. The repair
  will be applied in smaller exact-context patches.
- Integrated the frozen projection into separate R37.1 formal and
  training-side engineering modes. The engineering mode evaluates only a
  patient-disjoint sample from the R37.1 training partition and never opens
  the 1,815-patient fresh validation manifest.
- The expanded focused suite passes 22 tests; Ruff, compileall, and
  `git diff --check` pass. Both GPUs are currently idle and no R37 process is
  active.
- Launched the frozen R37.1 training-side engineering smoke as PID 14896 on
  GPU 1 after confirming both GPUs were idle. It uses Seed 17,
  1,000/500 rows, three epochs, and the new training partition only; the fresh
  1,815-patient validation outcomes remain unread.
- The process passed initialization with increasing CPU time, about 819 MiB
  GPU memory, non-idle power, and empty stderr.
- PID 14896 later exited after roughly 30 minutes without a result directory;
  both redirected logs remained empty. No Windows Application, System,
  display-driver, or GPU-driver error was recorded. This is an engineering
  STOP and has no scientific interpretation.
- The next diagnostic is a smaller foreground 100/50/1-epoch training-side
  smoke so the process exit status is captured directly. It still excludes
  the fresh 1,815-patient validation set.
- The foreground diagnostic completed with
  `PASS_R37_1_PRTA_TRAINING_SIDE_ENGINEERING`, exact inversion consistency
  1.0, true-current +15.04 pp, clean gradient/firewall checks, and a complete
  result/checkpoint pair. Its state retention is 0.8992, so it is strictly a
  code/mechanism smoke rather than a scientific result.
- Added a duplicate-safe independent Windows launcher for formal R37.1 seeds
  17 and 29. Each seed has a fixed GPU, fresh output/log boundary, atomic
  status file, exact frozen arguments, firewall checks, and fail-closed result
  validation; it contains no seed 43, A0, bootstrap, or protected stage.
- PowerShell syntax parsing, 24 focused tests, Ruff, and `git diff --check`
  pass before formal launch.
- After three consecutive idle checks, launched R37.1 Seed 17 on GPU 0 and
  Seed 29 on GPU 1 through independent WMI-created PowerShell parents. Launcher
  PIDs are 32500/7320 and Python child PIDs are 27728/22208.
- Both status files report `RUNNING_R37_1_FORMAL_SEED`; both child processes
  are alive, both GPUs loaded the models, both stderr logs are empty, and all
  protected/hash firewalls remain false.
- Created the 20-minute heartbeat automation `r37-1-two-seed-monitor`. It
  monitors only these two seeds, repairs only engineering failures without
  changing frozen settings, and may continue downstream only if both fresh
  results pass every registered internal gate.
- 2026-07-28 14:24 +08:00: a user-initiated host reboot terminated both
  incomplete R37.1 formal seeds. After restart, the old launcher/child PIDs
  were absent, both result directories were still missing, stderr/stdout were
  all empty, and both GPUs had zero compute processes.
- Archived only the stale status and zero-byte logs under
  `H:\VisualVIT_runtime\050_routeD\r37_prta_cxr\interruptions\20260728T142404_reboot_interrupt`.
  The frozen transition roster, caches, model/loss/seed/threshold settings,
  and hash/protected-outcome firewalls were unchanged.
- 2026-07-28 15:35 +08:00: after three idle GPU polls, relaunched only R37.1
  seeds 17/29 through the existing duplicate-safe launcher. New launcher PIDs
  are 12376/6512 and child Python PIDs are 19280/18092 on cuda:0/cuda:1.
  Both fresh status files report `RUNNING_R37_1_FORMAL_SEED`, both child
  processes are responsive, and both stderr logs are empty.
- Post-restart validation passed: PowerShell launcher syntax, 11 focused
  R37.1 launcher/roster/runner tests, and `git diff --check` are clean.
- 2026-07-28 23:17-23:36 +08:00: both R37.1 fresh-holdout formal seeds
  completed with `PASS_R37_1_FORMAL_SEED`, exit code 0, complete
  checkpoint/result pairs, empty stderr, and all protected/hash firewalls
  false.
- Frozen two-seed descriptive gate check passed in both seeds. Seed 17:
  inversion 1.0000, state retention 0.9934, true-current +30.42 pp,
  true-CMCP +12.76 pp. Seed 29: 1.0000, 0.9929, +25.22 pp, +11.39 pp.
- No final scientific GO is claimed from two seeds. The next authorized step
  is seed 43 plus the capacity-matched A0 fresh-holdout baseline and frozen
  patient-cluster bootstrap, still before any protected reveal.
- Began R37.1 downstream hardening. Read-only code inspection showed the A6
  runner already admits frozen seed 43, while A0 and aggregation still
  hard-code old-R37 counts/schemas. Implementation is restricted to explicit
  R37.1 roster/schema routing with unchanged frozen hyperparameters.
- Added an explicit R37.1 A0 mode, R37.1 aggregation schema selection, Seed 43
  launcher admission, and a duplicate-safe R37.1 A0 launcher. PowerShell
  syntax, 20 focused tests, Ruff, compileall, and `git diff --check` passed.
- The user then explicitly paused all downstream execution. No Seed 43, A0,
  bootstrap, aggregation, or protected process was started.
- Added `reports/R37_1_TWO_SEED_FRESH_HOLDOUT_RESULT.md` as the handoff
  surface for the two-seed metrics, reboot recovery, firewall evidence,
  scientific boundary, and paused next stage.
- Final pause verification found zero active experiment Python processes, no
  GPU compute processes, and all Seed 43/A0 output roots absent. The R37.1
  audit remains `READY_R37_1_FRESH_HOLDOUT` with every firewall false.
- 2026-07-29: the user authorized the reduced two-seed continuation. The
  active scope is A0 Seeds 17/29 plus a separately labeled two-seed
  patient-cluster bootstrap screen; Seed 43, the original three-seed
  aggregation, and every protected reveal remain deferred.
- Added the separate R37.1 two-seed screen, preserving the frozen 2,000
  patient-cluster replicates and bootstrap Seed 37001 while requiring at least
  +2 pp in each observed seed and CI lower bound above zero. Twenty-one
  focused tests, Ruff, compileall, CLI help, and `git diff --check` passed;
  commit `a0e8f74` is pushed.
- 2026-07-29 11:47 +08:00: after three idle GPU polls, launched A0 Seed 17 on
  GPU 0 (launcher/Python PIDs 12348/11292) and Seed 29 on GPU 1
  (5064/19816). Both are RUNNING with empty stderr and clean firewalls.
- Created the 20-minute heartbeat
  `r37-1-a0-two-seed-screen-monitor`. It monitors only these A0 jobs and will
  run the two-seed screen once after both valid PASS results; it forbids Seed
  43, the three-seed aggregator, hash recomputation, and protected reveals.
- 2026-07-29 14:24-14:25 +08:00: A0 Seeds 17/29 both completed with
  `PASS_R37_1_A0_FORMAL_SEED`, exit code 0, complete result/checkpoint pairs,
  empty stderr, and clean firewalls. Both GPUs were released.
- Ran the reduced screen exactly once. It emitted
  `PASS_R37_1_TWO_SEED_INTERNAL_SCREEN`: current-only, CMCP, A0, inversion,
  and state-retention gates all pass under the fixed two-seed descriptive
  boundary. No Seed 43, three-seed aggregation, protected outcome, or hash
  recomputation occurred.
- Began Phase 4C documentation consolidation at user direction. Updated the
  active Chinese proposal with the current R37.1 authority, method repair,
  results, and protected-stage explanation.
- Converted the former empty-result template into an R32-R37.1 result
  authority, added R37/R37.1 registry, STOP/GO, claim, per-seed, bootstrap,
  and protected-lock tables, and left genuinely unexecuted stages empty.
- Added `reports/R37_1_PROPOSAL_AND_CASE_STUDY_CLOSURE_CN.md` with the R33,
  R33A, R37 engineering, R37 formal inversion, R37.1 repair, fresh-holdout
  results, supported claims, and recommended no-more-GPU stopping point.
- Cross-document validation passed: all Markdown table groups have consistent
  column counts, every linked authority file exists, the key R37.1 metrics
  agree across proposal/table/case-study, 11 focused aggregation tests pass,
  and `git diff --check` passes after removing only newly introduced
  hard-break whitespace.
- Final live checks still show both GPUs idle and the screen firewalls false
  for protected, sealed-test, gold, unchanged hashes, and scientific claim;
  `three_seed_gate_evaluated` remains false.
- Final UTF-8 checks found no replacement characters in the three reader-facing
  Chinese documents, all authority links resolve locally, and the final
  unstaged diff check is clean.
- Commit `ab6a139` pushed the documentation bundle, but its combined
  PowerShell command continued after staged `git diff --check` reported three
  hard-break spaces in the new case-study header. A dedicated formatting
  follow-up removes them; scientific content and runtime state are unchanged.
- The user subsequently authorized the full confirmatory chain and both GPUs.
  The immediate scope is only frozen R37.1 A6/A0 Seed 43 plus the original
  three-seed internal bootstrap. Protected reveal and R38/R39 remain
  conditionally locked until their upstream gate passes.
- 2026-07-29 17:11 +08:00: after fresh-output and GPU-idle checks, launched
  R37.1 A6 Seed 43 on cuda:0 (launcher/Python PIDs 11272/23232) and A0
  Seed 43 on cuda:1 (14120/23436). Both launch manifests report RUNNING and
  no protected outcome or unchanged hash was accessed.
- Created the 20-minute heartbeat
  `r37-1-full-tier-confirmatory-monitor`. It monitors the two active jobs,
  runs the frozen three-seed qualification only after both PASS, and continues
  through R37C, R38, and R39 only when every upstream registered gate is GO.
- 2026-07-29 20:26 +08:00: A0 Seed 43 completed with exit code 0 and
  `PASS_R37_1_A0_FORMAL_SEED`. Its 6,858-row/1,815-patient result and
  checkpoint are complete, true-pair macro F1 is 0.3420, stderr is empty, and
  all protected/hash firewalls remain false. A6 Seed 43 is still running; the
  registered three-seed aggregation remains pending.
- 2026-07-30 03:50 +08:00: A6 Seed 43 completed with exit code 0, complete
  artifacts, empty stderr, true-current +30.53 pp, inversion 1.0000, state
  retention 0.9933, and clean protected/hash firewalls.
- Ran the original three-seed patient bootstrap exactly once for each frozen
  comparison after 7 focused aggregator tests passed. Current-only, CMCP, and
  A0 all PASS with mean gains +28.73/+12.78/+13.07 pp and CI lower bounds
  +26.99/+11.35/+11.38 pp. The internal scientific decision is GO.
- Began the fail-closed candidate-freeze/R37C preparation. The 300-dev,
  483-test, and gold outcomes remain unread; R38/R39 remain locked.
- Logged protocol deviation `R37C-PD1`: an existing R32 audit exposed only
  aggregate 300-dev label-support counts during structural inspection. No
  predictions, performance metrics, or row-level labels were read and no
  already-fixed model/gate choice may change afterward.
- Added the immutable R37.1 A6 three-seed candidate/A0 baseline/R37C gate
  manifest with one-time checkpoint hashes. R37C performance remains
  unrevealed pending runner implementation, tests, commit, and preflight.
- Implemented the fail-closed R37C chain: structural-only dev cache, separate
  one-shot label reveal, exact frozen A6/A0 seed evaluation, registered
  three-seed patient bootstrap, and a duplicate-safe two-GPU launcher.
- The runner verifies checkpoint path/byte receipts without rehashing, never
  hashes cache shards or unchanged sources, keeps 483-test/gold sealed, and
  reports `R37C-PD1` in every protected result.
- Validation passed: 9 focused tests, compileall, Ruff, and PowerShell parse.
  Live preflight found both GPUs idle, no R37C process, and no existing R37C
  runtime/status root. Commit/push precedes the single protected launch.
- Commit `f415d42` is pushed. At 2026-07-30 04:14 +08, launched the
  duplicate-safe R37C chain; structural Block-8 caching is active on GPU 0
  under launcher/cache PIDs 8896/10900 with empty stderr. The pipeline receipt
  still records `protected_300_dev_read=false`; reveal and all seed evaluation
  remain downstream of a valid cache PASS.
- Structural caching and the one-shot 300-dev reveal completed. Both first
  seed evaluators then stopped before model loading on 11 case-variant finding
  strings; neither produced a result, so no scientific metric was evaluated.
- Added strict case-only registry canonicalization and a guarded resume path
  that reuses the valid cache/reveal and starts only the fresh failed
  evaluations. Ten focused tests, Ruff, compileall, and PowerShell parse pass;
  commit/push precedes resume.
- Commit `4e9b52f` is pushed. At 2026-07-30 04:18 +08, resumed only fresh
  Seeds 17/29 on GPUs 0/1 (PIDs 9472/27816); cache and the single protected
  reveal were reused, stderr is empty, and no sealed/gold boundary changed.
- R37C completed `GO_R37C_ONE_SHOT_DEV`: A6-current +15.26 pp with CI
  [+12.71,+18.01], A6-A0 +3.42 pp with CI [+0.89,+6.20], all seed effects
  positive, inversion 1.0, and state retention >=0.9926. R38 is conditionally
  unlocked; R39/483-test/gold remain locked.
- Added and froze the R38 no-routing fixed-64 packer, per-seed evaluator,
  three-seed patient-bootstrap gate, token audits, and duplicate-safe
  two-GPU launcher. The layout is 4/12/16/16/12/4, packing has zero trainable
  parameters, and the gate requires +2 pp over frozen A0 plus >=70%
  correct-prior effect retention.
- Validation passed: 13 focused tests, compileall, Ruff after removing one
  unused import, frozen-config/upstream GO validation, and PowerShell parse.
  Commit/push precedes the first R38 launch.
- Commit `5604092` is pushed. At 2026-07-30 04:50 +08, launched R38 Seeds
  17/29 on GPUs 0/1 (PIDs 21176/31204). Both are active with empty stderr and
  clean hash/sealed/gold firewalls; Seed 43 and aggregation remain automatic
  downstream stages only after both current seeds PASS.
- R38 completed `GO_R38_FIXED64_SURVIVAL`: fixed64 A6 versus A0 is +3.42 pp
  with CI [+0.89,+6.20], every seed is positive, correct-prior effect
  retention is 1.0, and all exact-64/interface audits pass. R39 is unlocked;
  the 483 labels and gold remain sealed.
- Implemented and froze the R39 transfer protocol around local
  Qwen3-VL-4B-Instruct: exact 64 placeholders, zero trainable VLM parameters,
  one shared 9,873,920-parameter projector per seed, deterministic one-epoch
  A6+0.25*A0 training on the already revealed 300-dev set, and no pixel path.
- Corrected the pre-execution comparison boundary from A6-current-only alone
  to primary A6-versus-frozen-A0 plus current-only, query-only, and
  prior-shuffle controls, all at a preregistered +2 pp threshold with positive
  patient-bootstrap CI and every seed positive.
- Added outcome-free sealed Block-8 and four-variant fixed64 caching,
  projector training, outcome-blind sealed prediction freezing, one-shot
  sealed-label reveal, final aggregation, and a duplicate-safe two-GPU
  pipeline. Seventeen focused tests pass; compileall, Ruff, diff checking,
  frozen-config/upstream validation, and PowerShell parsing pass. No R39
  runtime root exists yet and no sealed label or gold outcome was read.
- Commit `be10d9f` pushed the frozen R39 implementation. At 2026-07-30 05:23
  +08, launched the full two-GPU chain under parent PID 29064. Initial workers
  are sealed Block-8 cache PID 28952 on GPU 0 and dev-token Seed 17 PID 30532
  on GPU 1; stderr files are empty and both shard inventories are advancing.
  The pipeline status is `RUNNING_R39`, `sealed_483_test_labels_read=false`,
  and `gold_outcomes_read=false`.
- The first Seed 17 projector process stopped before its first optimization
  step on a parameter-count receipt mismatch. The 7,948,800 value belonged to
  R32's input-width-16 smoke; the frozen input-width-768 R39 projector has
  9,873,920 parameters. This is a derived-audit repair only: architecture,
  initialization, data, loss, seeds, thresholds, controls, and bootstrap are
  unchanged. All completed caches are outcome-free and remain valid; 483
  labels and gold are still unread.
- The original launcher waited for the valid Seed 43 sealed cache to complete,
  then emitted `STOP_R39_ENGINEERING` without starting another projector.
  Commits `91f6560`/`f92822a` are pushed; 18 focused tests, Ruff, config-count
  validation, and PowerShell parsing pass. The guarded resume validated all
  six outcome-free token caches and fresh downstream roots, then launched
  projector Seeds 17/29 on GPUs 0/1 as PIDs 19020/28556 under resume parent
  22396. Protected 483 labels and gold remain unread.
- The guarded resume completed all three unchanged projectors and froze all
  three outcome-blind sealed prediction sets before label access. The
  registered one-shot 483-label reveal then ran exactly once and aggregation
  exited 0.
- Terminal status is `GO_R39_FROZEN_VLM_TRANSFER`: A6-frozen-A0 +15.01 pp
  (95% CI [+13.80,+16.14]), A6-current-only +3.22 pp
  ([+2.47,+4.02]), A6-query-only +15.77 pp ([+14.59,+16.84]), and
  A6-prior-shuffle +2.19 pp ([+1.39,+3.05]). Every Seed 17/29/43 effect is
  positive for every registered comparison.
- Interface and firewall audits PASS: zero trainable VLM parameters, no
  pixels, exact 64-token budget, matched prompt/projector capacity, predictions
  frozen before reveal, one reveal only, no unchanged hash recomputation, and
  gold unread. Both GPUs are idle and no R39 workers remain.
- Added `reports/R39_FROZEN_VLM_TRANSFER_FINAL_CN.md` and synchronized the
  proposal, result authority, findings, progress, and task plan. The experiment
  stops here; any gold/external study needs a new frozen registration.

## 2026-07-30 repository closeout

- Started Phase 6 using `planning-with-files`; no new experiment is
  authorized or launched.
- Confirmed the branch is clean and synchronized at the R39 terminal commit
  before closeout edits.
- Inventoried root files and tracked directories. Found no root README; found
  two historical proposals at the root, five dated planning-history packages,
  40 tracked reports, 33 protocol/spec documents, four active R37–R39 configs,
  and dedicated R38/R39 scripts/tests.
- Chose a conservative organization strategy: add one active entrypoint and
  indexes, archive only the two clearly stale root proposals, and avoid broad
  path churn across historical reports/specs.
- Compared the proposal's main-table, ablation, shortcut-control, grounding,
  and minimum-publishable-package sections with the frozen R39 config and
  implementation.
- Confirmed R39 implemented A0/current-only/query-only/prior-shuffle controls
  plus all core interface firewalls. Identified raw two-image/naive-concat
  baselines and VLM-level time reversal as the highest-value evidence gaps;
  no missing experiment authorizes tuning on the revealed 483 cohort.
- Audited the PRTA variant registry and formal spec. Only full A6 has the
  complete three-seed chain; a matched A2→A6 component ladder is the clearest
  missing method ablation.
- Confirmed the old four-tier routing ablation list is not directly identical
  to the implemented PRTA adapter, so it will be classified as legacy/optional
  unless the method namespace is explicitly reopened.
- Added the root `README.md`, current-status document, experiment-gap audit,
  reports index, and history index.
- Moved the CAPES/DIVE proposal files into
  `history/2026-07-30-legacy-proposals/` with explicit non-authoritative
  archive notices, and updated the one tracked spec that referenced their old
  root paths.
- Updated the package description from the stale CAPES/DIVE qualification
  wording to the current TIER-CXR-VLM / PRTA-CXR research identity.
- Focused PRTA/R38/R39 tests passed: 24 tests in 3.58 seconds.
- The first repository-wide Ruff run found 28 preexisting findings in six
  utility scripts. Removed one unused import, one unused variable, and two
  unnecessary f-string prefixes; added scoped `E402` exemptions to five
  scripts that intentionally insert the local `src` path before imports.
- Added `configs/README.md` and `data/README.md` so frozen-config lineage and
  the tracked-but-quarantined gold annotation boundary are visible without
  opening protocol or data payload files.
- Full pytest completed in 236.09 seconds: 700 passed, 1 expected xfailed, and
  1 old R6 closed-manifest test failed. Focused current-method tests remain
  24/24 PASS. Began a base-commit comparison to determine whether the R6
  failure predates this closeout.
- Created a temporary detached worktree at clean commit `24f57c3`, reran only
  the failing R6 test, reproduced the same failure, and removed the temporary
  worktree. The failure is confirmed preexisting and remains visible rather
  than being hidden by editing a closed protocol registry.
- Final closeout validation passed: local Markdown links, active archive
  references, Ruff across `src/scripts/tests`, Python compileall, and
  `git diff --check`. The temporary worktree list contains only the active
  repository.
- Phase 6 is complete. No GPU process, protected-outcome read, hash
  recomputation, checkpoint change, or new experiment occurred.

## 2026-07-30 Phase 7 start

- The user authorized the outcome-independent component-ablation and
  strong-baseline package.
- Restored the existing planning bundle with `planning-with-files` and added
  Phase 7 before touching experiment code or runtime state.
- Current boundary: audit and freeze the new roster/protocol first; do not use
  the revealed 483-test or gold for selection, do not recompute unchanged
  hashes, and do not launch duplicate GPU jobs.
- Added the first frozen R40 config, Chinese protocol, deterministic roster
  builder, and focused tests. The initial fixture failed because it omitted
  `current_view` and guessed example IDs; corrected only the test fixture to
  use the production transition-ID namespace.
- Implemented the separate R40 formal component mode in the shared PRTA
  trainer, including `A6_no_state`, protocol-local Z2 activation, full-count
  roster validation, distinct schemas/statuses, and new protected firewalls.
- Added a duplicate-safe PowerShell launcher for one registered
  variant/Seed/GPU. It requires fresh status/log/output paths and validates
  the terminal result before reporting PASS.
- Validation passes: 14 focused tests, Ruff, compileall, runner CLI help,
  PowerShell syntax parsing, and `git diff --check`. No roster was generated
  and no GPU process was launched before the protocol commit.
- Reused the exact existing R39 Qwen model path after a read-only path check;
  the first draft's guessed path did not exist and was fixed before freeze.
- Commit `835caef` was pushed before roster generation.
- The first roster CLI exited 1 before importing `visualvit`; no roster output
  directory was created. Added only the standard standalone-script `src` path
  bootstrap, with the frozen split rule and all settings unchanged.
- The frozen roster then passed with 8,787/1,500 train/development patients,
  33,677/5,814 examples, all five labels above minimum support, full CMCP
  coverage over 19,994 dynamic examples, and every protected/hash firewall
  false.
- The first launch preflight self-matched its own command text and stopped
  before spawning either launcher. Both GPUs and all R40 component output
  paths remained untouched; retry excludes only the current preflight PID.
- 2026-07-30 10:58 +08:00: after three clean GPU polls and an explicit
  duplicate-process check, launched A2 Seed 17 on cuda:0 and Seed 29 on
  cuda:1. Launcher PIDs are 29212/5552 and Python PIDs are 26336/30980.
- Both status files report `RUNNING_R40_COMPONENT_SEED`, both stderr logs are
  empty, both Python processes are responsive, and every 300-dev/483/gold/hash
  firewall remains false. These are engineering progress checks only; no
  interim development metric has been inspected.
- Created the 20-minute `r40-component-baseline-monitor` heartbeat. It fills
  free GPUs from a fixed preregistered variant/Seed queue, forbids
  outcome-dependent reordering or early stopping, and continues the already
  frozen strong-baseline/reversal implementation after fail-closed tests.
- Implemented the first outcome-independent strong-baseline slice without
  disturbing the active component jobs: B0 frozen-current-image BiomedCLIP
  and B2 Siamese prior/current plus signed/absolute-difference probes, together
  with a duplicate-safe launcher.
- Validation for this slice passes: six focused tests, Ruff, compileall,
  PowerShell syntax parsing, and `git diff --check`. No B0/B2 GPU process was
  launched, no component metric was inspected, and B1/B3 plus the VLM
  reversal execution surface remain pending.
- 2026-07-30 11:51 +08:00: stopped only the verified R40 A2 Seed 17/29
  launchers and child processes at the user's request. The two runs are
  incomplete user-paused work, not scientific results or engineering
  failures. Both R40 GPU allocations were released; a later unrelated tooth9
  job on GPU 1 was left untouched.
- Deleted the `r40-component-baseline-monitor` heartbeat. No next component
  task or strong baseline was launched; Phase 7 is paused until the user
  explicitly resumes it.

## 2026-07-30 Phase 8 PRTA-Gen start

- Restored the existing planning bundle with the user-requested
  `planning-with-files` workflow and read the full supplied PRTA-Gen design.
- Confirmed the repository is clean on
  `codex/r37-prior-responsive-temporal-adapter`; the prior R40
  component/baseline queue remains paused with no active R40 process.
- Registered a separate Phase 8 rather than silently resuming or renaming the
  old R40 protocol. The new scope is R40A token-information sufficiency plus
  R40B exact-64 generative adapter readiness.
- Preserved the hard boundary: no reuse of the revealed 483-test for
  selection, no gold/external reveal, no GPU launch before a new frozen
  protocol and focused structural tests pass.
- Added the frozen machine-readable PRTA-Gen R40 readiness config and Chinese
  protocol in a new `configs/prta_gen/` namespace.
- Implemented literal, fail-closed generative-target extraction; unchanged
  exact-64 state/transition/relation summary features; a bounded linear
  information probe; and the future-gated G-CMCP sequence-margin helper.
- Implemented `GenerativeVLMAdapter.forward_sft`, `score_sequence`,
  `generate_text`, cache-equivalence audit, LoRA parameter audit, and the
  attention-only PEFT installer. Added `peft` as an optional generation
  dependency rather than changing the existing base environment.
- The first target-extraction test exposed over-broad masking of “lung” in
  “lower lung opacity.” Narrowed only the finding mask, retained conflict-to-
  `Unspecified`, and reran the suite.
- Added the outcome-independent literal-target support audit CLI. It writes
  fresh training/development target manifests, validates patient/firewall
  lineage, and keeps every generation field locked until true-pair probe
  controls actually run.
- Focused validation passes: 23 tests, Ruff, compileall, and
  `git diff --check`. No Qwen load, GPU process, protected-outcome read, hash
  recomputation, or old R40 queue resume occurred.
- Committed and pushed the frozen readiness package as `746a0c2`.
- Ran the committed CPU-only target audit. It returned
  `PASS_PRTA_GEN_R40A_TARGET_SUPPORT` for 33,677/5,814 rows and
  8,787/1,500 patient-disjoint train/development patients, with every
  protected/hash/old-R40 firewall false.
- Froze a separate post-support R40A probe spec before observing any probe
  metric. It fixes supported class registries, PRTA Seed 17, prior-shuffle
  Seed 40011, exact-64 pooling, three linear-probe Seeds, and patient
  bootstrap settings.
- Implemented the exact-64 token-cache runner for true-pair, current-only, and
  within-finding cross-patient prior-shuffle branches. The runner reuses the
  frozen Block-8 cache/checkpoint, stores no labels or sentences, and has a
  deterministic 64-row structural smoke mode.
- Validation passes for the post-support package: 26 focused tests, Ruff,
  compileall, CLI help, and `git diff --check`. GPU 0 was idle at the last
  check; GPU 1 was occupied by an unrelated job and remains untouched.
- The committed 64-row development token-cache smoke passed on GPU 0:
  64 rows/60 patients, one 18.9 MB shard, exact `[64,768]` float16 tokens,
  three frozen variants, no labels/sentences, and every protected/hash/old-R40
  firewall false.
- Before a full-cache launch, fixed a fresh-output namespace collision exposed
  by the successful smoke: formal and smoke caches now use sibling
  `formal/` and `smoke_64/` directories. The valid smoke is preserved.
- Committed and pushed the cache-namespace repair as `27856f7`, then launched
  exactly one formal development token-cache worker on GPU 0. The first
  256-row shard is complete; no duplicate worker or probe metric exists.
- Implemented the frozen R40A linear-probe runner for progression,
  laterality, anatomy, and degree across true-pair/current-only/query-only/
  prior-shuffle controls. It retains row/patient alignment and writes each
  field/Seed result to a fresh directory with generation still locked.
- Probe-runner validation passes together with the existing package:
  30 focused tests, Ruff, compileall, CLI help, and `git diff --check`.
- The first formal development cache worker was responsive but inefficient:
  after one 256-row shard it had read about 105 GB because hash-shuffled
  counterfactual priors repeatedly evicted the four-shard LRU. No metric or
  protected outcome was involved.
- Stopped only verified PRTA-Gen PID 15212 on GPU 0 and retained its partial
  shard as failed engineering evidence. Implemented outcome-independent
  compact materialization that reads each required source shard once, clones
  only referenced Block-8 rows, and serves true/current/shuffle batches from
  the compact in-memory map.
- Committed and pushed the bounded-I/O cache repair as `ff37c26`. A fresh
  development rerun passed with 5,814 rows/1,500 patients/23 shards; training
  passed with 33,677 rows/8,787 patients/132 shards. Both have exact
  `[64,768]` tokens and clean protected/hash/old-R40 firewalls.
- Ran progression, laterality, anatomy, and degree probes only in the frozen
  order. Laterality Seed 43, anatomy Seed 43, and degree Seed 17 exposed
  negative control contrasts, so no field was opportunistically rescued.
- Added and tested the patient-cluster aggregation entrypoint with the frozen
  2,000 bootstrap replicates and Seed 40001.
- The progression aggregate reached
  `STOP_PRTA_GEN_R40A_FIELD_INFORMATION`: Seed 17 true-pair minus
  prior-shuffle was +1.061 pp with 95% CI [-0.925, +3.263] pp. Seeds 29/43
  were strongly positive, but the registered rule requires every Seed CI
  lower bound to exceed zero.
- Closed Phase 8 as `STOP_PRTA_GEN_R40A_INFORMATION_SUFFICIENCY`. Did not load
  Qwen for an R40B overfit, did not launch LoRA/SFT/G-CMCP/reversal/evidence
  retrieval, and did not read 300-dev, the historical 483 outcomes, gold, or
  external outcomes.
- Added `reports/PRTA_GEN_R40A_INFORMATION_SUFFICIENCY_RESULT_CN.md` and
  synchronized the root README, project status, report index, and persistent
  planning bundle to the terminal gate.
- Final validation: 28 PRTA-Gen focused tests passed, repository-wide Ruff and
  compileall passed, and `git diff --check` passed. Full pytest ended at
  742 passed, 1 expected xfailed, and the one preexisting R6 frozen-manifest
  failure already reproduced at clean commit `24f57c3`; the closed R6
  registry was not rewritten.

## 2026-07-30 Phase 9 case-driven PRTA-Gen repair start

- The user authorized a case-study-driven repair and asked to continue through
  the current proposal rather than stopping at the first R40A route.
- Re-entered the explicit `planning-with-files` workflow, restored the clean
  pushed Phase-8 state, and added a separate Phase 9. The closed R40A STOP and
  R39 GO remain immutable.
- The repair will first use already-observed R40A predictions descriptively,
  then freeze distinct discovery/qualification patient boundaries and a small
  ordered readout family before observing new route-specific outcomes.
- R40B remains locked until a new three-Seed patient-bootstrap information gate
  passes. The terminal request to continue does not authorize 483/gold reuse,
  outcome-guided thresholding, or interruption of unrelated GPU work.
- Added a fail-closed R40A case-study analyzer and focused tests. It validates
  the three closed progression Seeds, target/token row alignment, exact-64
  cache firewalls, per-finding/progression/quality error clusters, token-region
  true-vs-shuffle RMS, cross-Seed collision patterns, and anonymized example
  selection without patient IDs or report sentences.
- The real analyzer passed and wrote
  `H:\VisualVIT_runtime\050_routeD\r37_prta_cxr\prta_gen_r40_readiness_v1\case_study_r40a_v1\case_study.json`
  for 5,814 rows/1,500 patients with 40 anonymized examples. It kept the
  closed R40A verdict unchanged and all protected/hash firewalls false.
- Added the reader-facing R40A failure case study and a separate R40A.1
  protocol/config. The repair freezes 5,787 fit, 1,500 discovery, and 1,500
  one-shot qualification patients before new outcomes, with the first passing
  candidate rule and no resplit.
- Implemented the two diagnosis-aligned deterministic feature families:
  6,912-wide regional mean/std/max and 9,216-wide four-component orthonormal
  cosine position features. Both ignore only the four already-zero reserve
  positions while consuming the unchanged exact-64 tensor.
- Added the fail-closed R40A.1 roster builder and tests. It binds the closed
  R40A STOP and descriptive case-study receipt, validates the existing
  label-free training token-cache receipt, assigns patients only by the frozen
  SHA-256 namespace, and reports support without resplitting.
- Added the dated case-driven repair addendum to the active proposal and
  indexed the new case-study report. The older proposal body and R39 result
  remain historical/current authority rather than being overwritten.
- Committed and pushed the complete pre-outcome R40A.1 authority as `26487c7`.
- Ran the committed roster builder once. It returned
  `PASS_PRTA_GEN_R40A1_ROSTER_SUPPORT` with 5,787/1,500/1,500 disjoint
  fit/discovery/qualification patients and adequate support for every
  progression class; no resplit or protected outcome read occurred.
- Added an outcome-free, candidate-specific feature-cache builder so the three
  probe Seeds do not repeatedly recompute 64-token statistics. Its shards
  retain aligned IDs/findings and true/current/shuffle features but no labels,
  sentences, discovery outcomes, or qualification outcomes.
- Added the generic R40A.1 discovery/qualification probe runner and tests. It
  trains the same linear readout budget for true/current/shuffle branches,
  retains query-only as a finding one-hot control, binds every row to the
  frozen patient roster, and refuses qualification without a valid selected-
  candidate receipt.
- Added the generic three-Seed patient-cluster candidate aggregator and ordered
  selector. Discovery aggregates keep generation locked; the selector reads
  candidates in the frozen order and unlocks qualification only for the first
  GO, while a stopped first candidate requires the second aggregate rather
  than silently skipping it.
- Committed and pushed the R40A.1 execution surface as `dff623b`.
- GPU 0 was idle while GPU 1 remained occupied by an unrelated process. Built
  only the first ordered candidate's feature cache on GPU 0:
  `regional_moments_v1` passed with 33,677 rows, 132 shards, width 6,912, and
  no labels/sentences or protected outcomes in the cache.
- `regional_moments_v1` discovery Seed 17 completed on GPU 0. True-pair
  macro-F1 is 0.2860 versus query-only 0.2582 and prior-shuffle 0.2047,
  giving +2.78/+8.13 pp; current-only is 0.2326. These are Seed-level point
  estimates only, so candidate selection remains locked.
- `regional_moments_v1` Seed 29 completed with true-pair 0.2881, query-only
  0.2218, and prior-shuffle 0.3399. The required effects are +6.64 and
  -5.18 pp, so this candidate has a decisive registered Seed-level STOP.
  Seed 43 will not run; an early-stop aggregate must close the candidate before
  the ordered cosine candidate starts.
- Added and tested a generic early-stop receipt path for any completed Seed
  whose required point effect is already below the frozen +2 pp minimum. The
  real moments candidate is now closed as
  `STOP_PRTA_GEN_R40A1_DISCOVERY`, with Seeds 17/29 complete and Seed 43
  explicitly skipped after the first failed gate.
- Committed and pushed the early-stop implementation as `a7d8d53`, then built
  the second and final ordered candidate cache. `regional_cosine4_v1` passed
  with 33,677 rows, 132 shards, width 9,216, and all outcome/cache firewalls
  intact.
- `regional_cosine4_v1` Seed 17 completed at true-pair 0.3342 versus
  query-only 0.2582 and prior-shuffle 0.3465: +7.60/-1.23 pp. It was closed
  immediately as the second ordered discovery STOP; Seeds 29/43 and all
  R40A.1 qualification outcomes remain unread.
- The ordered selector wrote terminal
  `STOP_PRTA_GEN_R40A1_DISCOVERY` with no selected candidate and
  `qualification_unlocked=false`.
- After that terminal receipt, inspected the frozen exact-64 compiler and
  identified that the probe's 20/20/20 pooling did not match the real
  4/12/16/16/12/4 token-type layout. Began a distinct R40A.2 authority around
  this semantic-boundary repair rather than adding an outcome-tuned threshold.
- Added the frozen R40A.2 config/protocol, semantic-layout mean/moment feature
  functions, a roster builder that preserves the original qualification list
  and excludes observed R40A.1 discovery patients, and generalized the
  fail-closed cache/probe/aggregate/selection engine across R40A.1/R40A.2.
- R40A.2 focused validation currently passes 19 tests plus Ruff.
- Final pre-freeze validation passes 22 focused tests, Ruff, compileall, JSON
  parsing, and `git diff --check`.
- Committed and pushed the pre-outcome semantic-layout authority as `36224b2`.
  The committed roster builder then returned
  `PASS_PRTA_GEN_R40A2_ROSTER_SUPPORT`: excluded R40A.1 discovery is
  1,500 patients/5,869 rows; fresh discovery2 is 1,500/5,882; fit2 is
  4,287/16,154; and the unchanged sealed qualification boundary is
  1,500/5,772. All five class-support gates pass without resplitting or
  reading route-specific outcomes.
- Built `semantic_layout_means_v1` on GPU0. The outcome-free cache passed with
  33,677 rows, 132 shards, and input width 3,840; GPU1's unrelated process
  was not touched.
- `semantic_layout_means_v1` fresh discovery2 Seed 17 completed at true-pair
  macro-F1 0.3967 versus query-only 0.2062, prior-shuffle 0.3529, and
  current-only 0.2705. The required effects are +19.05/+4.38 pp, so both
  point gates pass and Seed 29 is authorized.
- Seed 29 also passed: true-pair macro-F1 0.3562, query-only 0.2234,
  prior-shuffle 0.1569, current-only 0.2750, with required effects
  +13.28/+19.94 pp. Seed 43 is now authorized under the frozen sequence.
- Seed 43 passed at true-pair macro-F1 0.3840 versus query-only 0.2522,
  prior-shuffle 0.3130, and current-only 0.2527; required effects are
  +13.18/+7.10 pp. All three discovery2 Seeds pass their point gates, so the
  preregistered patient-cluster aggregate is authorized.
- The 2,000-replicate patient-cluster aggregate returned
  `GO_PRTA_GEN_R40A2_DISCOVERY`. All six required Seed/control confidence
  intervals have lower bounds above +2 pp; the narrowest is Seed 17 versus
  prior-shuffle at +2.404 pp. Candidate selection is authorized, while
  qualification and progression generation are still locked.
- The first selector CLI invocation stopped at argument parsing because the
  explicit `--output` path was omitted. It wrote no receipt and read no new
  outcome; the unchanged committed selector will be rerun with the registered
  R40A.2 `selection.json` path.
- The corrected selector wrote
  `SELECTED_PRTA_GEN_R40A2_CANDIDATE` for
  `semantic_layout_means_v1`, unlocked only qualification, and left
  progression generation/scientific claims locked. No second discovery
  candidate was run.
- Qualification Seed 17 completed at true-pair macro-F1 0.3876 versus
  query-only 0.2083, prior-shuffle 0.3659, and current-only 0.2919. It passes
  the point gates at +17.93/+2.17 pp; the prior-shuffle margin is close enough
  that the final patient bootstrap remains decisive.
- Qualification Seed 29 passed at true-pair macro-F1 0.3512 versus query-only
  0.2248, prior-shuffle 0.1657, and current-only 0.2673. Required effects are
  +12.64/+18.55 pp, so the unchanged final qualification Seed 43 is
  authorized.
- Qualification Seed 43 passed at true-pair macro-F1 0.3900 versus query-only
  0.2515, prior-shuffle 0.3077, and current-only 0.2587; required effects are
  +13.85/+8.23 pp. The three-Seed qualification aggregate is now authorized.
- The first qualification aggregate command stopped at argument parsing
  because it was given the probe-only selection receipt argument. No
  aggregate was written; rerun the unchanged aggregator using only its
  registered config/roster/candidate/scope inputs.
- The corrected 2,000-replicate qualification aggregate returned
  `GO_PRTA_GEN_R40A2_QUALIFICATION` and
  `progression_generation_unlocked=true`. Audit confirmed the frozen rule is
  point effect >= +2 pp plus bootstrap lower bound > 0, so Seed 17's
  prior-shuffle point +2.169 pp/lower bound +0.298 pp legitimately passes.
  Laterality/anatomy/degree/evidence and scientific claims remain locked.
- Added the frozen R40B config/protocol, deterministic 32-row cohort builder,
  progression-only generative runner, and focused tests. The runner enforces
  fresh initialization, exact-64 placeholders, assistant-suffix-only labels,
  no pixel/image/video input, attention-only Qwen LoRA plus projector
  trainability, cached/uncached first-step equivalence, strict two-key JSON,
  and ordered underfit-only retries.
- R40B pre-outcome validation passes 13 focused tests (including the existing
  generative-adapter suite), Ruff, compileall, JSON parsing, and
  `git diff --check`.
- Committed and pushed the full pre-outcome R40B authority as `6164b6f`.
  The committed cohort builder then froze 32 unique fit patients with the
  registered 7/7/6/6/6 class counts and returned
  `PASS_PRTA_GEN_R40B_SMOKE_COHORT`; all protected-data firewalls remain
  false.
- The first `registered_3epoch_v1` launch loaded Qwen successfully but stopped
  before its initial baseline forward: Transformers 5.5 returned rendered
  chat text instead of integer IDs from the requested template call. No
  optimizer step or result directory exists; only prompt tokenization
  compatibility will be repaired before rerunning the same attempt.
- Repaired only the Transformers 5.5 `BatchEncoding["input_ids"]` extraction,
  added a regression test, and verified the real local tokenizer returns a
  171-position prompt containing exactly 64 placeholders. Eleven focused
  tests, Ruff, and `git diff --check` pass.
- Reran the fresh original `registered_3epoch_v1`. All engineering contracts
  passed and loss fell 1.3338 -> 0.5545, but teacher-forced token accuracy was
  87.83% and greedy progression accuracy only 15.625% despite 100% valid JSON
  and finding echo. It closed as
  `STOP_R40B_REGISTERED_3EPOCH_UNDERFIT`, which authorizes only the
  preregistered 12-epoch attempt.
- The fresh 12-epoch attempt also preserved every engineering contract and
  improved final loss to 0.0456, token accuracy to 98.70%, and greedy
  progression to 27/32 while keeping schema/finding at 32/32. Because the
  registered overfit gate requires progression 32/32, it closed as
  `STOP_R40B_BOUNDED_12EPOCH_UNDERFIT`, authorizing the final frozen
  24-epoch attempt.
- The final fresh 24-epoch attempt reached loss 0.0185, teacher-forced token
  accuracy 99.35%, valid JSON 32/32, finding echo 32/32, and progression
  29/32. All contracts passed, but it closed as
  `STOP_R40B_BOUNDED_24EPOCH_UNDERFIT`; the preregistered free-greedy ladder
  is exhausted and cannot be tuned further on those patients.
- Began a distinct R40B.1 authority around exact-schema sequence scoring on a
  new 32-patient fit cohort that excludes the observed R40B cohort. This
  changes the diagnosed decoding mechanism, not the upstream tokens or
  scientific gate.
- Added the R40B.1 config/protocol, fresh-cohort exclusion support, generic
  stage/result receipts, and exact-schema five-candidate sequence scoring to
  the existing fail-closed runner. Sixteen focused tests, Ruff, compileall,
  JSON parsing, and `git diff --check` pass before the new cohort is built.
- Committed and pushed the pre-outcome R40B.1 authority as `0afb0dd`. The
  committed builder then returned `PASS_PRTA_GEN_R40B1_SMOKE_COHORT` with
  32 unique new fit patients, registered class balance, and zero parent-cohort
  overlap.
- The single R40B.1 attempt preserved every engineering contract and reached
  loss 0.0152/token accuracy 99.14%, but exact-schema sequence scoring was
  only 28/32 on progression. It closed as
  `STOP_PRTA_GEN_R40B1_CONSTRAINED_UNDERFIT`; that cohort is now observed and
  frozen.
- Began R40B.2 around the diagnosed semantic-token dilution: progression-span
  weighted assistant loss plus progression-span-only conditional scoring on
  a third cohort excluding both earlier 32-patient sets.
- Added the frozen R40B.2 config/protocol, multi-cohort exclusion, tokenizer
  offset-based progression masks, weighted assistant loss, span accuracy
  audit, and span-only conditional scoring. Seventeen focused tests, Ruff,
  and compileall pass; a separate PowerShell quoting error affected only the
  first read-only real-tokenizer preflight command.
- Repeated the real-tokenizer preflight with safely constructed JSON. It
  passed: the progression mask selects only Qwen token 3564 for `New`, while
  config JSON parsing and `git diff --check` also pass.
- Committed and pushed the pre-outcome R40B.2 authority as `27c426a`. The
  committed builder then returned `PASS_PRTA_GEN_R40B2_SMOKE_COHORT` with
  32 unique new fit patients and zero overlap with both observed cohorts
  (64 excluded patients).
- The single R40B.2 run passed engineering contracts and reached overall token
  accuracy 98.07%, but progression-token accuracy was 82.22% and structured
  progression 24/32. It closed as
  `STOP_PRTA_GEN_R40B2_PROGRESSION_SPAN_UNDERFIT`; the third cohort is frozen.
- Began R40B.3 around direct five-way classification at the unique first
  progression token, with a uniform SFT auxiliary and a fourth cohort
  excluding all 96 observed patients.
- Added the frozen R40B.3 config/protocol, direct-class training/decoding,
  fourth-cohort exclusion, and regression tests. Eighteen focused tests,
  Ruff, compileall, the real five-token registry preflight, JSON parsing, and
  `git diff --check` pass pre-outcome.
- Committed and pushed R40B.3 as `58ef113`. Its first cohort build stopped
  before writing because the generic exclusion whitelist omitted the valid
  R40B.2 cohort status; only that receipt registry will be repaired.
- Added the missing historical status with a regression test, committed and
  pushed `0974c4f`, then reran the unchanged builder. It returned
  `PASS_PRTA_GEN_R40B3_SMOKE_COHORT` with 32 unique fit patients and zero
  overlap with all 96 observed patients.
- The single R40B.3 attempt passed all engineering contracts but reached only
  77.78% progression-token and 23/32 direct-class output. It closed as
  `STOP_PRTA_GEN_R40B3_DIRECT_CLASS_UNDERFIT`; all four generative cohorts
  are now observed and immutable.
- Began R40B.4 as an architecture-level convergence route: a bounded
  semantic-layout progression head plus deterministic legal JSON on a fifth
  cohort excluding all 128 observed patients. Qwen free generation stays
  locked.
- Added the R40B.4 config/protocol, 499,973-parameter head, standalone runner,
  fifth-cohort exclusion, and tests. The first focused run found only that the
  exact exclusion-registry assertion had not yet added R40B.3; production
  behavior and all static checks passed.
- Updated the assertion and completed pre-outcome validation: eight focused
  tests, Ruff, compileall, JSON parsing, and `git diff --check` pass.
- Committed and pushed the pre-outcome R40B.4 authority as `371fc09`. Its
  committed builder returned `PASS_PRTA_GEN_R40B4_SMOKE_COHORT` with 32 new
  unique patients and zero overlap with all 128 observed Qwen-route patients.
- The first runner invocation stopped before token loading because the cohort
  already occupied the configured runtime root. No training/output occurred;
  results will be isolated under a frozen `structured_head/` child directory.
- Isolated the unchanged R40B.4 result under `structured_head/`, committed and
  pushed the repair as `d59facd`, then reran the same frozen cohort and
  settings on GPU0.
- R40B.4 returned `PASS_PRTA_GEN_R40B4_STRUCTURED_HEAD_SMOKE`: initial/final
  loss 1.6262604/1.1920928e-07 (ratio 7.33027e-08), training and structured
  progression 32/32, schema 32/32, finding echo 32/32, and 499,973 trainable
  parameters. Exact64/no-pixel and every protected-data firewall passed.
- Closed Phase 9 with the progression-only structured route engineering-ready.
  Qwen free generation and all untested fields/stages remain explicitly
  locked; no generalization or scientific-generation claim is made.
- Updated the proposal, root README, project-status authority, report index,
  failure case study, and a new R40A.2/R40B.4 terminal report to the same
  bounded verdict.
- Final validation passes 32 focused tests, Ruff, compileall, all nine
  PRTA-Gen config parses, modified-document local-link checks, and
  `git diff --check`. Full pytest reports 777 passed, 1 expected xfailed,
  and the same one historical R6 frozen-manifest failure documented before
  this route; the closed R6 registry remains untouched.
- Post-closeout `nvidia-smi` shows both RTX 3090 devices at 0 MiB used and
  0% utilization.

## 2026-07-30 Phase 10 R40C pre-outcome start

- User authorized the recommended next stage.
- Reopened the active planning bundle with a new Phase 10. The authorized
  scope is protocol/config/roster/runner/aggregator/tests and dry-run
  validation only; formal GPU execution remains behind a new review gate.
- Preserved R40B.4 as an engineering-only 32-row overfit PASS and kept Qwen
  free generation, scientific generalization, other fields, R41–R43, and all
  protected outcomes locked.
- Completed aggregate fit-side support inventory without protected reads:
  4,127 patients/14,687 rows remain after excluding all 160 patients from the
  five observed R40B cohorts. The limiting Resolved label still has 489
  unique patients, supporting a frozen balanced 1,000-train/500-development
  design.
- The first inventory command used PowerShell's reserved `$PID` name and was
  stopped by exact process match after producing only repeated shell errors.
  The corrected read-only aggregation used `$patientKey` and completed
  normally; no artifact or outcome boundary changed.
- Inspected the existing R40B.4 head, token loader, R40A.2 feature/control
  logic, and patient-bootstrap aggregator. Froze the R40C design at four
  capacity-matched arms, three Seeds, 1,000 balanced training patients,
  500 balanced development patients, and a no-tuning 100-epoch schedule.
- Added the pre-outcome R40C JSON config and Chinese frozen protocol. They
  register the source/exclusion receipts, balanced roster, four arms,
  architecture/training schedule, three-Seed bootstrap gate, internal-only
  claim tier, and the explicit stop-before-real-roster/GPU boundary.
- Added the deterministic fail-closed R40C roster builder with an in-memory
  `--preflight-only` mode. It validates predecessor/upstream/token/cohort
  receipts, excludes exactly 160 historical patients, assigns rare classes
  first, enforces one row per patient and train/development disjointness, and
  writes nothing during preflight.
- Roster-builder validation passes four focused tests and Ruff. Tests cover
  deterministic assignment, balanced/disjoint output, no-write preflight, and
  protected-parent fail-closed behavior; no real runtime roster was created.
- Added the R40C GPU runner. It loads all three token variants in one shard
  pass, derives semantic-layout means, constructs a padded 12-finding
  query-only control, fits normalization on training only, trains four fresh
  capacity-matched heads, and records held-out metrics plus descriptive
  true-head counterfactuals.
- Added the three-Seed R40C aggregator with patient-cluster bootstrap,
  absolute macro-F1 and per-class recall gates, query/shuffle effect gates,
  deterministic structured-interface checks, and locked downstream claims.
- The combined R40C/R40B.4 focused suite passes 13 tests and Ruff. No real
  roster, Seed output, aggregate, checkpoint, or GPU process exists.
- Ran both real-receipt CPU preflights in no-write mode. The roster path
  returned `PASS_PRTA_GEN_R40C_PREFLIGHT`; the runner returned
  `PASS_PRTA_GEN_R40C_RUNNER_PREFLIGHT`, with 1,000/500 in-memory counts,
  four arms, Seeds 17/29/43, 499,973 parameters, and 800 updates per arm.
- Before and after preflight, the R40C runtime root/roster were absent, no
  R40C process existed, and both GPUs were at 0 MiB/0% utilization. Every
  protected/gold/external flag remained false.
- Updated the root README, current proposal, project status, report index, and
  a dedicated R40C preflight report to the same review-gated prelaunch state.
- Final focused validation passes 18 tests, repository-wide Ruff, compileall,
  R40C JSON parsing, modified-document link checks, and `git diff --check`.
  Full pytest reports 787 passed, 1 expected xfailed, and the same historical
  R6 frozen-manifest failure; the sealed R6 authority remains untouched.
- Committed and pushed the complete R40C pre-outcome authority as `de4c85d`.
  Phase 10 preparation is closed at
  `PASS_PRTA_GEN_R40C_RUNNER_PREFLIGHT`; the next action is user review before
  the one-time real roster write. No formal command was launched.

## 2026-07-30 Phase 11 R40C roster authorization

- User authorized the next action. Interpreted the incomplete phrase against
  the immediately preceding gate as authorization for the one-time real
  roster write and receipt audit only, not for Seed/GPU execution.
- Opened Phase 11 with an explicit roster-only boundary. The committed
  pre-outcome authority remains unchanged; all protected outcomes and every
  GPU command stay locked until the roster receipt is reviewed.
- Revalidated the clean pushed authority, exact config/protocol hashes,
  absent runtime root, real-receipt no-write preflight, zero R40C workers,
  and both GPUs at 0 MiB/0% before writing.
- Executed the committed roster builder exactly once at the registered path.
  It returned `PASS_PRTA_GEN_R40C_ROSTER_SUPPORT`; no Seed, training, or
  aggregate command was launched.
- Scalar-only post-write audit confirms 1,000/500 unique patients, 200/100 per
  class, zero train/development patient overlap, all 160 observed patients
  excluded, one row per patient, and every protected/gold/external/revealed
  outcome flag false.
- The runtime root contains only the 350,714-byte `roster.json`, SHA-256
  `9C076B684BC258EFA60E568004F851CD9EE079EA4DDEA549BD0D2ABCFBF9B0CB`.
  There are no R40C Seed workers, results, checkpoints, or aggregates; both
  GPUs remain idle.
- The one-time builder printed full rows to its local terminal. Added a
  tested scalar-only receipt formatter for future CLI use and did not
  reproduce any row identifiers in the planning/status handoff.
- Closure verification passes: 26 R40C/R40B.4 focused tests, repository-wide
  Ruff, compileall, config JSON parsing, modified-document local links, and
  `git diff --check`.
- Committed and pushed the roster receipt, CLI evidence-hygiene fix, authority
  docs, and planning evidence as `b4837eb`. Phase 11 is closed at
  `PASS_PRTA_GEN_R40C_ROSTER_SUPPORT`; the next gate is separate authorization
  for Seed 17, not an automatic GPU launch.

## 2026-07-30 Phase 12 R40C automatic execution authorization

- User explicitly authorized Seed launch and automatic continuation. Opened a
  new execution phase covering the frozen sequential Seed 17 → 29 → 43 chain
  and aggregate after per-Seed receipt validation.
- Authorization does not permit roster changes, tuning, threshold/Seed
  selection, retries around a scientific STOP, or protected/gold/external
  reads. Either registered aggregate GO or STOP is terminal.
- Added a tracked automatic sequence runner. It launches one Seed at a time on
  the registered device, validates the complete Seed receipt before advancing,
  runs aggregate only after all three receipts pass, accepts aggregate exit 2
  as a registered scientific STOP, and fails closed without retries on
  engineering errors.
- Reduced the individual Seed CLI handoff to a scalar receipt that excludes
  patient/example IDs, targets, predictions, counterfactual arrays, and
  structured row outputs.
- Validation passes 16 focused tests, targeted Ruff, compileall, and
  `git diff --check`.
- Real launch preflight returned both
  `PASS_PRTA_GEN_R40C_SEQUENCE_PREFLIGHT` and
  `PASS_PRTA_GEN_R40C_RUNNER_PREFLIGHT`. The roster hash remains
  `9C076B684BC258EFA60E568004F851CD9EE079EA4DDEA549BD0D2ABCFBF9B0CB`;
  all three Seed directories, aggregate, and sequence status are absent.
  H: has 529.31 GiB free, no compute process exists, and both GPUs are at
  0 MiB/0%.
- Committed and pushed the automatic sequence authority as `5bf56bc`, then
  launched it hidden with PID 20904 on `cuda:0`.
- Live process audit confirms launcher PID 20904 and Seed 17 worker PID 6000
  with exact frozen command lines. `sequence_status.json` reports
  `RUNNING_PRTA_GEN_R40C_AUTHORIZED_SEQUENCE`, `current_stage=seed_17`,
  zero completed Seeds, `retry_allowed=false`, and every protected outcome
  flag false. Launcher and Seed stderr logs are empty.
- Seed 17 passed and automatically unlocked Seed 29: true-pair macro-F1
  0.5058, query/shuffle effects +19.72/+10.50 pp, schema/finding 1.0.
- Seed 29 passed and automatically unlocked Seed 43: true-pair macro-F1
  0.4941, query/shuffle effects +20.10/+10.91 pp, schema/finding 1.0.
- Seed 43 passed: true-pair macro-F1 0.4827, query/shuffle effects
  +17.42/+9.64 pp, schema/finding 1.0. The launcher then ran aggregate exactly
  once.
- Aggregate returned `GO_PRTA_GEN_R40C_INTERNAL_GENERALIZATION`, gate failures
  0. All three Seeds pass the macro-F1, every-class recall, point-effect,
  patient-bootstrap CI, schema, and finding gates.
- Final runtime audit confirms all four stderr logs are empty, aggregate
  SHA-256 is
  `34E2D09C7E2734B34AD028D6E3CDDFE6F08BD84F50D38541B8BD643F14EC0027`,
  no launcher/Seed process remains, and both GPUs are back at 0 MiB/0%.
- Added the dedicated Chinese terminal report and updated README, proposal,
  project status, reports index, preflight handoff, and result registry to the
  same bounded internal-development GO.
- Terminal closeout validation passes 31 R40C/R40B.4 focused tests,
  repository-wide Ruff, compileall, modified-document local links,
  cross-document R40C markers, aggregate terminal consistency, and
  `git diff --check`.
- Committed and pushed the terminal report and authority update as `8f58ec7`.
  Post-push audit confirms aggregate and sequence status both remain
  `GO_PRTA_GEN_R40C_INTERNAL_GENERALIZATION`, three completed Seed receipts,
  unchanged roster/aggregate hashes, all protected flags false, no matching
  process, both GPUs idle, clean Git state, and upstream divergence 0/0.

## 2026-07-30 Phase 13 downstream automatic authorization

- User authorized continued work through R41 and later stages, requested
  automatic downstream execution until the terminal outcome, and explicitly
  confirmed both GPUs may be used directly.
- Opened a new gate-bound phase. “Run all” means advance automatically through
  frozen survival gates; it does not authorize bypassing a failed gate,
  outcome-driven tuning, invented external support, or protected-data/DUA
  violations.
- Initial inventory finds no ready R41–R43 runner/config. Recovered the
  original roadmap and existing GenerativeVLMAdapter/LoRA engineering
  surfaces; downstream work must be newly frozen and tested before launch.
- Local external support is incomplete: the official repo tree contains
  CheXTemporal annotations but no external image tree. The historical gold
  availability audit exists only under the older F: runtime and must be
  refreshed without reading outcomes.
- Confirmed the complete local Qwen snapshot and required Torch/Transformers/
  PEFT runtime. Formal exact-64 caches cover all 33,677/5,814 R40 rows, and
  2,627 R40A.2-fit patients remain outside the R40C roster.
- The historical gold audit remains descriptive-only: 16 untouched
  image-complete patients, about 35 pp conservative MDE, and no available
  ReXGradient images.
- Re-audited the untouched R40A.2-fit remainder after excluding all five R40B
  smoke cohorts and the complete R40C roster. The remaining 2,627 patients
  supply 5,919 rows; per-class unique-patient support is
  1,904/647/797/419/106 for Stable/Improved/Worse/New/Resolved.
- Confirmed both GPUs are currently fully idle (0 MiB, 0% and no compute
  process). No downstream model process has been launched because the R41
  roster, gates, and fail-closed runner are not frozen yet.
- Added the frozen R41A config and identity-safe roster builder. The real
  no-write preflight passes with 375/125 balanced patient-disjoint rows, all
  1,660 previously observed patients excluded, and a six-patient Resolved
  reserve. JSON parsing, focused Ruff, compileall, and diff checks pass.
- Implemented the R41A Qwen runner, invalid-output-aware aggregate/bootstrap,
  and automatic two-GPU G0/G1 launcher. The runner preflight passes against the
  real local tokenizer/model contract; seven new focused tests, Ruff,
  compileall, and `git diff --check` pass.
- Confirmed R42 cannot consume a pre-existing reverse cache because none
  exists. The frozen PRTA cache path can nonetheless produce a valid reverse
  cache by swapping current/prior Block-8 features, so R42A preparation
  continues before any R41A outcome is observed.
- Added the frozen R42A reverse-cache builder, G-CMCP/reversal runner,
  invalid-output-aware aggregate, and two-GPU launcher. Static runner
  preflight passes with the involutive five-class mapping and 12 fixed updates;
  the reverse-cache data preflight is intentionally deferred until the
  committed R41A roster exists.
- Added a fresh read-only R43 confirmation-readiness audit and frozen gate.
  It reproduces 16 untouched image-complete gold patients, zero executable
  external patients, a 35.02 pp conservative MDE, and no independent labels;
  it reads no outcome, metric, or prediction.
- Added the automatic R41A -> R42A -> R43 master chain and expanded focused
  tests to 14 passing cases. All new R41-R43 scripts pass Ruff, compileall, and
  `git diff --check`.
- Full pytest completed with 805 passed, one expected xfail, and the known
  preexisting R6 frozen-manifest failure; repository-wide Ruff passes.
- Committed and pushed the complete pre-outcome authority as `c796630`.
  Only after that push, wrote the real R41A roster once. Its scalar receipt is
  `PASS_PRTA_GEN_R41A_ROSTER_SUPPORT`, 118,039 bytes, SHA-256
  `2BA53C95BDDC78CBE1E585CF5954708892B6106578DA812226D87F94FD4F77C0`.
- Real R41A runner/sequence, R42A reverse-cache data, and full master-chain
  preflights all pass. The reverse-cache preflight resolves all 1,000 required
  DICOM features for 500 rows with zero missing. Both GPUs remain idle.
- Launched the master chain. Seed-17 G0/G1 loaded tokens and Qwen weights, then
  stopped before training because R41A referenced the wrong scalar key in the
  model trainable-parameter audit. No result directory or scientific outcome
  was created; both GPUs returned to 0 MiB.
- Corrected only the audit-key adapter (`trainable_parameter_count`), mirrored
  the fix in R42A, added a regression test, and passed 22 focused tests plus
  Ruff, compileall, and diff checks. The failed runtime logs are retained for
  archival before a fresh engineering relaunch.
- Committed and pushed the outcome-free repair as `95a0fac`. Moved all failed
  launch logs/status artifacts, without deletion, to
  `H:\VisualVIT_runtime\050_routeD\r37_prta_cxr\history\20260730T233927_r41a_engineering_stop_trainable_audit_key`;
  the frozen `roster.json` remained active and unchanged.
- Repeated the real R41 runner, R41 two-GPU sequence, R42 reverse-cache data,
  and full R41-R43 master-chain preflights. All four returned their registered
  PASS status with the frozen roster SHA-256, 500 R42 rows/1,000 available
  DICOM features, and no outcome reads or GPU work.
- Relaunched the unchanged master chain at 2026-07-30 23:40:57 +08:00 from
  clean commit `517f4e1` (master PID 27736). R41A Seed-17 G0/G1 are active on
  GPU0/GPU1; live utilization reached 10,039/9,905 MiB and 42%/27%.
  Both R41 and master status receipts remain RUNNING with zero completed arms.
- The second launch trained Seed-17 for about ten minutes, then stopped before
  any checkpoint, prediction, or result was written. G1's cache-equivalence
  check compared two forward passes while the trained LoRA dropout remained
  active; the paired launcher terminated G0 and both GPUs returned to idle.
- Updated the shared cache-semantic audit to enter `eval()` only for the two
  compared passes and restore the previous training mode afterward. This
  changes no model weight, optimizer, data, decoding, or gate. A stochastic
  dropout regression test now covers the exact failure; 30 focused tests,
  Ruff, compileall, and `git diff --check` pass.
- Committed and pushed the repair as `d665221`, then preserved the second
  failed-launch receipts under
  `H:\VisualVIT_runtime\050_routeD\r37_prta_cxr\history\20260730T235423_r41a_engineering_stop_cache_audit_dropout`.
  The active R41 root again contains only the unchanged frozen roster, with
  both GPUs idle and no downstream Python process.
- Repeated all four real preflights successfully and launched the unchanged
  chain at 2026-07-30 23:55:23 +08:00 (master PID 28948). Seed-17 G0/G1
  workers are active on GPU0/GPU1; the status receipts are RUNNING with no
  result yet.
- The third launch completed all six R41A arms across Seeds 17/29/43. Every
  arm completed 36 optimizer updates, returned
  `PASS_PRTA_GEN_R41A_ARM_EVALUATION`, achieved 100% schema/finding validity,
  and passed cache equivalence with maximum absolute difference 0.
- The terminal aggregate returned
  `STOP_PRTA_GEN_R41A_PROGRESSION_SFT_SURVIVAL` with eight gate failures.
  G1 true macro-F1 was 0.3474/0.3632/0.4304; `Worse` recall was
  0.00/0.08/0.08; G1−G0 was -0.46/-13.40/-6.85 pp. Seed 17 also failed the
  prior-shuffle point and CI gates.
- The master chain stopped normally at R41A. `r42_unlocked=false`,
  `r43_unlocked=false`; neither downstream runtime root exists. Protected
  300-dev, revealed 483, gold, and external outcomes remained unread. All
  matching Python processes exited and both GPUs returned to 0 MiB/0%.
- Added the terminal R41A report and updated README, project status, frozen
  protocol, proposal, result table, report index, and planning bundle to the
  same first-failed-gate conclusion.
- Final validation passed: 23 focused tests, repository-wide Ruff, compileall,
  `git diff --check`, seven-file local Markdown link audit, and a scalar-only
  terminal audit of six results/checkpoints, eight gate failures, aggregate
  SHA-256, firewalls, absent R42A/R43 roots, zero workers, and idle GPUs.
- 2026-07-31: began Phase 14 after explicit user authorization. Scope is a
  read-only R41A failure case study plus Proposal/status closure using only the
  already-completed 125-patient development outputs. New training, tuning,
  resplitting, checkpoint selection, R42A/R43 execution, and protected/gold/
  external outcome reads remain forbidden.
- Selected the technical-report shape and a repository-native Markdown report
  with a reproducible static figure. Audited the six result schemas and metric
  payloads without printing identities; all contain the registered four
  evaluation arms, 36 optimizer updates, exact-64 inputs, and no pixel input.
- Froze the analyzer design to validate the immutable roster/result alignment,
  emit no patient/example identifier, and quantify only descriptive confusion,
  G0/G1 migration, control sensitivity, finding/class concentration, and
  cross-Seed patterns. The analyzer and tests will be committed before the
  one-time real read.
- Committed and pushed the analyzer/tests/planning boundary as `0445a6d`, then
  ran it once against the six closed result files and roster SHA-256
  `2BA53C...F77C0`. It returned
  `DESCRIPTIVE_PRTA_GEN_R41A_FAILURE_CASE_STUDY`, 125 rows/patients, 14
  de-identified representative cases, zero identity-bearing keys, and no new
  training.
- Rendered and visually inspected the static two-panel performance figure.
  Labels, zero baselines, Seed grouping, G0/G1 non-color distinction, and the
  explicit frozen-development/descriptive-only subtitle are all readable.
- The read-only diagnostics confirm three linked failure modes: near-absence
  of G1 `Worse` emission, net-negative G0-to-G1 migration in Seeds 29/43, and
  weak cross-Seed stability (31 unanimous correct, 49 wrong in all Seeds).
  Prior-shuffle sensitivity is present in Seeds 29/43 but insufficient under
  the frozen conjunction and cannot override the terminal STOP.
- Wrote the technical failure case study with the inspected figure, exact
  confusion/migration/control/cross-Seed tables, de-identified counterexamples,
  methods, limitations, and an outcome-independent next-step boundary.
  Updated the active Proposal, root/project status, report index, and terminal
  R41A report without changing the frozen STOP.
- Focused validation currently passes 27 tests across the new analyzer, R41A
  protocol/aggregate path, and Qwen adapter; repository-wide Ruff also passes.
- Python compileall, `git diff --check`, and a six-file local Markdown/image
  link audit pass. The figure path resolves from the report and the report is
  promoted consistently from the root, Proposal, project status, result
  report, and reports index.
- The scalar-only terminal audit passes: derived JSON SHA-256 is
  `59C64E...EA37A`, all 125 rows reconcile, 14 de-identified cases are present,
  identity-key hits are zero, scientific/training/reuse flags are false, and
  R42A/R43 runtime roots remain absent. No matching R41–R43 Python worker or
  GPU compute process is active.
- Full pytest completed with 814 passed, 1 expected xfailed, and the same
  single historical R6 frozen-manifest failure previously reproduced at clean
  commit `24f57c3`. No Phase-14/R41A test failed, and this task does not rewrite
  the closed R6 registry to manufacture a green suite.
- Final repository identity-text audit finds no patient/example identifier
  values in the report or promoted authority surfaces. The tracked asset
  directory contains only the inspected 81,511-byte R41A performance figure;
  final `git diff --check` passes.
- Committed and pushed the complete technical report, figure, Proposal,
  project status, indexes, terminal report link, and planning evidence as
  `6ce4d41`. Phase 14 is formally closed; the earlier pre-analysis analyzer
  remains independently frozen at pushed commit `0445a6d`.

## 2026-07-31 Phase 15 independent continuation

- User asked to continue after the Phase-14 handoff. Opened a new R44
  feasibility phase rather than bypassing the R41A STOP or launching the
  still-locked R42A/R43 chain.
- The first action is inventory-only: identify genuinely unused patients and
  five-class support after excluding all observed R40/R41 cohorts. No roster,
  outcome read, model process, or GPU command is authorized before this
  feasibility gate is recorded.
- Completed the first scalar-only inventory over the R40A.2 fit lineage. After
  excluding 2,160 observed/used patients, 2,127 patients and 4,153 rows remain,
  but only one remaining patient supports `Resolved`. No identity was printed
  and protected 300-dev, revealed 483-test, gold, and external outcomes were
  not read. This partition cannot support an independent five-class R44 run.
- Audited the frozen source authority: the R40 registry has only the already
  assigned 8,787 training and 1,500 development patients, and R43's protected
  gold/external surfaces are confirmation-only rather than a legal development
  fallback. A fresh readiness check remains to confirm that no external
  images/labels have appeared since the prior audit.
- Ran the fresh R43 outcome-free preflight. It again returns the registered
  readiness STOP: 16 image-complete untouched gold patients, zero external
  patients, absent external root, no independent labels, and 70 ReXGradient
  annotations with 238 missing image references. No outcome or prediction was
  read and no artifact was written.
- Checked the official ReXGradient paper and Hugging Face repository. The
  downsampled images are publicly distributed as ten archive parts with
  train/validation/test metadata, so acquisition may be feasible. Began a
  download-size/selectivity audit only; no dataset file has been downloaded.
- Confirmed the repository is gated and the local HF client is unauthenticated.
  Its configured endpoint is `hf-mirror.com`, which caused the failed dry-run
  metadata lookup. No credential or dataset agreement was assumed; acquisition
  remains behind explicit account access and terms acceptance.
- Read the official gated-use terms and audited the local CheXTemporal
  checkout. The terms require account-holder acceptance and minimum-necessary
  download; the local checkout has no silver files. No agreement was accepted,
  credential created, or image/annotation file downloaded.
- The open CheXTemporal Hub repository supplies silver annotations separately.
  A dry run at the official endpoint shows that only 57.6 MB of findings and
  studies parquet is needed for support/image-path auditing; the 207.2 MB masks
  and sentence parquet are unnecessary. No silver file has been downloaded
  yet because the scalar-only audit contract must be committed first.
- Pinned the open annotation source to revision
  `81fd9cdd9b1208d8f8bd39d7a914c9b72fed8d79`. Confirmed both registered
  CheXpert/MIMIC roots and 524.84 GiB free on H:. Reduced the planned download
  further to the 29.5 MB `silver_findings.parquet` only.
- Froze the pre-outcome R44 support-audit config, Chinese protocol, scalar-only
  implementation, and three synthetic regression tests. The initial focused
  validation passes: 3 tests, Ruff, Python compilation, and `git diff --check`.
  No CheXTemporal silver file, patient roster, model process, or GPU job has
  been created.
- The missing-source preflight reproduces the frozen R40 remainder exactly and
  returns the expected formal `STOP_PRTA_GEN_R44_INDEPENDENT_SUPPORT` with
  `chextemporal_silver_file_missing`; all outcome-read, roster, training, and
  scientific-claim flags remain false.
- Before the first real silver read, corrected the implementation to enforce
  image completeness on selected rows rather than requiring every source row
  to have local images. Insufficient patient-disjoint class support now returns
  a scalar support failure that the top-level audit converts to formal STOP.
  The same 3 tests, Ruff, compilation, missing-source preflight, and whitespace
  checks pass after the correction.
- Committed and pushed the entire pre-outcome R44 support-audit authority as
  `6d306d9`. After that freeze, downloaded only the allowed CheXTemporal
  `silver_findings.parquet` from the official endpoint and pinned revision.
  The local artifact is exactly 29,502,280 bytes with SHA-256
  `31237F...3C807`; the fresh audit destination does not yet exist.
- The first formal audit command exceeded the 120-second shell yield while
  performing selection-independent local image existence checks. The verified
  Python worker remains active, the atomic audit output is still absent, and
  no result or roster was partially written. Two bounded 45-second checks show
  continuing CPU progress; this is an execution-latency event, not a support
  PASS/STOP.
- After one final bounded wait, stopped only the verified R44 audit worker.
  It had written no audit output. The CheXpert subset contains 197,449 rows but
  only 112,934 unique image references; a single read-only `rg --files` index
  enumerated all 223,650 local parent-root files in 36.4 seconds. Replaced only
  the per-reference filesystem calls with an equivalent case-insensitive
  one-pass image index.
- Post-optimization validation passes 29 focused tests across R44 support,
  R41A authority, R40 support utilities, and the closed case-study path, plus
  Ruff, Python compilation, and whitespace checks.
- The single formal audit completed in 31.7 seconds and returned
  `PASS_PRTA_GEN_R44_INDEPENDENT_SUPPORT`. After excluding 77 CheXpert gold
  patients, all 197,449 source rows / 22,638 patients are image-complete.
  Unique-patient support is Stable 18,260; Improved 10,037; Worse 13,076;
  New 10,826; Resolved 1,439. The in-memory deterministic check fills 1,000
  train and 250 development patients at exactly 200/50 per class with zero
  overlap. No roster or GPU job was created.
- The immutable audit is 2,231 bytes with SHA-256
  `8DE158995C983F7295F68545AE7A65007B98DBB819ACBD33327AA70EC78A5777`.
  It keeps R42/R43 locked and every protected/gold/external outcome-read and
  scientific-claim flag false.
- Began the pre-roster R44A protocol freeze. The inherited 12-finding registry
  leaves 196,616 eligible rows and retains at least 1,430 patients in every
  progression class after gold exclusion. The planned experimental contrast
  keeps R41A's G0/G1 arms, Seeds, target, decoding, controls, optimizer, and
  gates fixed; only the independently sourced cohort size and required
  CheXpert image-to-exact64 cache are new.
- Added the frozen R44A config, Chinese protocol, fail-closed roster builder,
  and four unit tests. JSON parsing, tests, Ruff, compilation, and whitespace
  checks pass.
- The real roster preflight passes without writing a roster: 196,616 eligible
  rows / 22,622 patients after exact-finding and gold exclusion; deterministic
  in-memory selection fills 1,000 train and 250 development patients; all
  selected images exist; train/development are disjoint; 1,075 patients with
  Resolved support remain outside the selection versus the frozen minimum 500.
  No GPU job or protected/gold/external outcome read occurred.
- Added the targeted CheXpert image-to-exact64 cache implementation. It
  deduplicates selected JPEGs, enforces same-finding cross-patient prior
  shuffles, materializes frozen BiomedCLIP block-8 features once, applies the
  unchanged Seed-17 PRTA/checkpoint/query path, and writes token-only
  true/current/shuffled shards compatible with the existing loader. Six
  R44A tests, Ruff, compilation, and whitespace checks pass.
- Generalized the existing R41A runner, aggregate, and two-GPU sequence through
  optional stage contracts while preserving historical defaults. R44A now has
  separate runner/aggregate/sequence entrypoints and schema/status registries;
  a dedicated regression proves that even R44A GO leaves R42/R43 locked.
  Combined R41A/R44A validation passes 22 tests, Ruff, and compilation.
- The R44A cache preflight passes with the frozen candidate hash, present PRTA
  checkpoint/text cache, 1,250 in-memory selected rows, and a fresh token root.
  The first direct runner-alias preflight stopped at import time because the
  thin alias lacked the standalone workspace bootstrap; it started no model,
  roster, cache, or GPU process. Added that bootstrap to all R44A aliases.
- After bootstrap, the substantive runner preflight passes: local Qwen is
  present, the prompt contains exactly 64 placeholders and 15 assistant target
  tokens, both G0/G1 and all four evaluation arms are registered, and the
  expected optimizer-update count is 94. Bound the receipt to R44A-specific
  schema/status and corrected only alias lint declarations before final rerun.
- The final alias rerun emits the R44A-specific preflight receipt and passes
  the 64-placeholder, 15-target-token, 94-update contract. All current
  R41A/R44A compatibility tests (22) and targeted Ruff pass. The complete
  roster/cache/runner/aggregate/two-GPU sequence authority is ready for the
  required pre-roster commit; runtime roster and token roots remain absent.
- Final pre-outcome validation passes 36 focused regressions, repository-wide
  Ruff, compileall, `git diff --check`, and a machine consistency audit of the
  94-update/downstream-lock contract. The R44A runtime root, roster, and token
  root are all absent, and `nvidia-smi` reports no compute process before the
  authority commit.
- Committed and pushed the complete pre-outcome R44A authority as `d767311`.
  Only afterward, wrote the one-time roster. It passes with exactly 1,000
  train and 250 development patients, balanced 200/50 per class, complete
  selected images, disjoint partitions, excluded gold patients, and no
  protected/gold/external outcome read.
- The frozen roster is 967,619 bytes with SHA-256
  `60FE40D3483B85C9B462D69BF631D82DE68620BA722606862D263F095271C292`.
- Re-ran the cache preflight against the committed authority: PASS, fresh token
  root, present PRTA checkpoint/text cache, both RTX 3090 GPUs idle, and
  524.81 GiB free on H:. Started the single registered exact64 cache worker on
  GPU0 (PID 4968). The token root now exists as an active output, the final
  index is not yet present, and both stdout/stderr remain empty at startup.
- The cache worker completed cleanly in 98.0 seconds. Its terminal index is
  `PASS_PRTA_GEN_R44A_EXACT64_TOKEN_CACHE`: 1,250 rows/patients, 2,500 unique
  images, 10 shards, deterministic repeated block-8 batch, zero labels or
  sentences in cache, exact roster SHA match, and empty stderr. Index SHA-256
  is `8ADA1A1116375B66BA951F17174B8D391EE906814FCCF23B1F8960C444820546`.
- Full cache consumption preflight loads all 1,250 examples for each of
  true/current/shuffled, verifies finite 64×768 tensors, and reconciles every
  patient/finding receipt to the roster. The two-GPU sequence preflight then
  passes with the exact roster hash, 1,000/250 counts, three Seeds, G0/G1, and
  retry disabled. Both GPUs are idle immediately before launch.
- Started the single authorized R44A sequence. The launcher and two registered
  Seed-17 arm workers are active; sequence status is
  `RUNNING_PRTA_GEN_R44A_AUTHORIZED_SEQUENCE` at
  `seed_17_parallel_arms`, with zero completed arms and empty launcher
  stdout/stderr at startup.
- Seed 17 G0/G1 remain healthy in training across repeated bounded checks:
  three expected Python processes, roughly 10 GiB allocated per GPU, nonzero
  utilization, zero stderr bytes, no partial result file, and no sequence-state
  transition. This is active execution, not a completed arm or gate result.
- Further Seed-17 checks remain unchanged in the meaningful fields: both GPUs
  allocated, utilization fluctuating as expected for per-example SFT, all
  three registered processes alive, stderr zero, and no result file. The arm
  runtime includes 3,000 training examples plus four 250-row free-generation
  evaluations per GPU, so this duration is not itself an error.
- Seed 17 continues without resource or error drift: GPU memory remains stable
  near 10 GiB per arm, utilization is repeatedly nonzero, and stderr/result
  state remains 0/absent. No intervention is warranted while forward progress
  and the registered process set remain intact.
- Around ten minutes into Seed 17, both arms remain synchronized and healthy.
  The frozen runner writes history only inside the terminal result after all
  training and four evaluation arms complete, so absent epoch/result files are
  expected while GPU utilization and zero-stderr evidence continue.
- Two later bounded checks again show transient utilization variation rather
  than a stall: GPU0 sampled from 0% to 45% and GPU1 from 25% to 33%, with
  stable allocations, live workers, zero stderr, and unchanged sequence stage.
- Subsequent Seed-17 samples remain in the same healthy contract, with both
  GPUs returning to roughly 37–39% utilization and no stderr or partial
  outputs. The sequence has not advanced and no gate can yet be evaluated.
- A later low-utilization sample (6%/13%) recovered on the next bounded check
  to 32%/22%, while allocations, workers, stage, and zero-stderr state stayed
  constant. This confirms normal per-example/evaluation cadence rather than a
  stalled worker.
- Seed 17 remains compute-bound with later utilization samples of 42%/27% and
  25%/24%. No resource, stderr, process-count, or atomic-output condition has
  changed, so the fail-closed sequence continues without intervention.
- Another pair of bounded samples rose to 51–57% on G0 and recovered from 7%
  to 42% on G1, still with zero stderr and no partial results. Both arms are
  demonstrably executing, not orphaned or idle.
- Later Seed-17 samples fluctuate down to 20%/13% after 39%/28%, with stable
  memory and zero stderr. This remains consistent with the transition between
  training and serial free-generation evaluations; no terminal receipt exists
  yet.
- An evaluation-like 7–8% utilization sample recovered on the next check to
  39%/44%, with unchanged memory, workers, stage, and zero stderr. This further
  rules out a persistent GPU stall.
- Seed 17 continues at 27%/20% then 42%/25% utilization with all fail-closed
  health indicators unchanged. No scientific metric is available until both
  complete receipts are written.
- At 27.5–28.4 minutes elapsed, Seed 17 remains healthy at 45%/31% then
  35%/30% GPU utilization, stable allocations, zero stderr, and no partial
  result. The measured duration is now recorded without inferring a gate.
- At 29.5–30.4 minutes, the same Seed remains active with utilization ranging
  25–51%, stable memory, zero stderr, and no output contract violation.
- At 31.4–32.4 minutes, a 19%/15% sample recovered to 27%/25%; the registered
  workers and zero-stderr contract remain intact and no result is yet complete.
- At 33.4–34.4 minutes, utilization remained active at 53%/39% then 30%/24%,
  with unchanged memory, process set, zero stderr, and absent terminal files.
- At 36.3 minutes, Seed-17 G0 completed atomically and released GPU0; G1
  remains active on GPU1 at roughly 10.3 GiB/29%. Total stderr is still zero.
  The sequence correctly holds at `seed_17_parallel_arms` until the paired G1
  receipt exists, so the completed G0 outcome is not inspected in isolation.
- At 37.4–38.4 minutes, G1 continues alone at 41% then 36% utilization with
  stable memory and zero stderr. G0 remains complete and untouched; the
  sequence has not yet accepted the pair.
- At 39.5–40.4 minutes, G1 remains healthy at 32% utilization with zero
  stderr; G0 remains atomically complete and GPU0 idle. No pair transition yet.
- At 41.5–42.5 minutes, G1 continues at 27–29% utilization with the same
  stable allocation and zero stderr; G0 remains complete and untouched.
- At 43.5–44.4 minutes, G1 remains active at 23–30% utilization with zero
  stderr; the paired Seed-17 result is still incomplete.
- At 45.4–46.4 minutes, G1 continues at 35% then 31%, with no stderr or
  resource drift. G0 remains complete and GPU0 remains idle by design.
- At 47.4–48.4 minutes, G1 remains live at 26% then 14% utilization with zero
  stderr. The paired receipt is still incomplete; no retry or second process
  has been started.
- At 49.4–50.4 minutes, G1 utilization swings from 56% to 13% while memory and
  zero-stderr state remain fixed, continuing to demonstrate live serialized
  generation rather than a dead worker.
- At 51.4–52.4 minutes, G1 continues at 27% then 42% utilization with zero
  stderr. Its longer runtime relative to completed G0 is accepted as the
  registered LoRA-arm cost, not used to alter the comparison.
- At 53.4 minutes, both Seed-17 arms completed and passed the sequence's
  engineering-receipt checks. The sequence automatically advanced to
  `seed_29_parallel_arms` with two completed receipts and both GPUs allocated
  to the new pair.
- The 582 Seed-17 stderr bytes are benign Transformers progress/warnings:
  successful 713/713 weight loading and ignored sampling flags under frozen
  greedy generation. There is no traceback, failed stage, or sequence error;
  Seed-29 stderr starts at zero. Seed-17 scientific metrics remain unreviewed
  until aggregate.
- Seed 29 is healthy at 54.7–55.7 total minutes: both GPUs hold roughly
  10.3–10.7 GiB at 30–35% utilization, completed-arm count remains two, no new
  stderr bytes appear, and neither Seed-29 result is partial.
- Seed-29 training continues with later utilization at 45–51% on G0 and 37%
  on G1, stable allocations, no new stderr, and unchanged completed-arm count.
- Seed-29 later sampled at 41%/34% and then transiently 0%/14%, while memory,
  workers, stderr, stage, and partial-output state remained unchanged. This
  matches the non-stall cadence already observed and recovered in Seed 17.
- The next two Seed-29 checks recovered to 47%/34% and then 24%/21%, with no
  new stderr or output state, confirming continued execution.
- At 62.8–63.8 total minutes, Seed 29 remains healthy at 37%/33% then 28%/21%.
  Relative to the 53.4-minute transition, it is only about ten minutes into
  the registered workload; no timeout inference is appropriate.
- Later Seed-29 checks continue at 35%/27% then 41%/35%, with stable memory,
  no new stderr, and neither arm result yet complete.
- Seed-29 utilization continues to fluctuate productively from 22%/37% to
  47%/35%, with all receipt and error indicators unchanged.
- Two later Seed-29 samples show G0 at 33–50% while G1 is transiently 3–5%.
  G1 memory remains allocated and stderr/output state is unchanged; verify its
  process CPU progress on the next check before considering any intervention.
- The 20-second activity audit confirms both Seed-29 arm workers advanced by
  about 16.8 CPU-seconds, retain roughly 2.2–2.3 GiB working sets, and still
  drive their assigned GPUs. G1 is active; no intervention is justified.
- Later Seed-29 samples return to 31%/23%, then a transient 0%/29%; the recent
  CPU-delta proof and unchanged zero-error state keep this within normal
  execution cadence.
- Seed-29 utilization subsequently recovered from 10%/17% to 31%/43%, with no
  new stderr or receipt-state change.
- Later Seed-29 checks remain active at 15%/17% then 26%/22%; stderr and
  result-state remain unchanged.
- Seed-29 utilization later recovers from 16%/14% to 33%/23%, with the same
  stable error and output state.
- Subsequent Seed-29 checks remain active at 26%/27% then 19%/21%, with no new
  stderr or result file.
- At 81.5–82.5 total minutes (about 28–29 minutes into Seed 29), utilization
  rises from 35%/28% to 52%/41%, with stable memory and unchanged stderr.
- Later Seed-29 checks remain strongly active at 46%/38% then 43%/48%, with no
  terminal or error-state change.
- Seed-29 remains strongly active in the next two checks at 47%/34% and
  47%/41%; no result has yet crossed the atomic boundary.
- At 88.4 total minutes (about 35 minutes into Seed 29), G0 completed
  atomically and released GPU0. G1 remains active on GPU1 at roughly
  10.7 GiB/29%, total stderr is unchanged, and the sequence correctly waits for
  the pair before accepting either outcome.
- Seed-29 G1 continues alone at 32% then 19% utilization, with stable memory
  and no new stderr; G0 remains complete and unreviewed in isolation.
- Later Seed-29 G1 checks remain healthy at 39% then 35%, with no new stderr
  or terminal receipt.
- Seed-29 G1 continues at 38% then 34%, with stable allocation and unchanged
  zero-error state.
- A transient Seed-29 G1 sample at 13% recovers to 34% on the next check,
  without any stderr or output-state change.
- At 98.5 total minutes (about 45 minutes into Seed 29), G1 remains steady at
  roughly 33% utilization, with G0 complete and no new stderr.
- Later Seed-29 G1 utilization changes from 24% to 36%, with stable memory and
  unchanged zero-error state.
- Seed 29 then completed as a validated pair; the sequence advanced
  automatically to the final `seed_43_parallel_arms` with four completed arm
  receipts and both GPUs allocated to the new workers.
- All Seed-17/29 stderr files contain no `Traceback` or `Error:` marker; the
  size increase is limited to the same model-loading/generation warnings.
  Seed-43 stderr begins at zero, and the sequence has no failed stage or error
  type. Scientific metrics remain deferred to aggregate.
- Seed 43 enters stable training at roughly 10.2/10.6 GiB per GPU, with
  utilization rising from 54%/37% to 58%/43%. The startup stderr increment is
  warning-sized, and neither final-Seed result is partial.
- Seed-43 later remains at 55%/15% then 50%/41%; G1's transient dip recovers,
  while stderr and result state stay unchanged.
- Seed-43 G0 remains at 53% across two checks while G1 moves from 39% to a
  transient 4%; stable allocation and zero new stderr preserve the healthy
  classification pending the next recovery check.
- Seed-43 G1 recovers from 4% to 38% and remains 36%; G0 moves from 45% to a
  transient 4%. These alternating dips occur without stderr/memory drift and
  remain consistent with live serialized work.
- Both Seed-43 arms then return to strong activity at 45%/37% and 54%/35%,
  with no new stderr or terminal receipt.
- Seed-43 remains active at 51%/32% then 36%/36%, with stable memory and error
  state.
- Later Seed-43 checks remain at 37%/29% and 37%/35%, without stderr or output
  changes.
- Seed-43 then continues at 44%/31% and 43%/43%, with no new stderr or partial
  result.
- Later Seed-43 checks hold at 24%/23% then 24%/35%, with stable error and
  output state.
- At 121.6 total minutes (roughly 16 minutes into Seed 43), utilization moves
  from 38%/33% to 21%/23%; no stderr or result-state change appears.
- Seed-43 later steadies at 36%/24% then 36%/32%, with no new stderr or partial
  result.
- Seed-43 remains strongly active at 40%/31% then 46%/33%, with unchanged
  error and output state.
- Later Seed-43 utilization remains active at 27%/24% then 34%/29%, with no
  new stderr or terminal output.
- Seed-43 later rises to 43%/30% and 53%/37%, with unchanged healthy state.
- Seed-43 G0 then completed atomically and released GPU0. G1 remains active on
  GPU1 at roughly 10.6 GiB/23%, with no new stderr; the sequence correctly
  waits for the final arm before aggregation.
- Final Seed-43 G1 continues alone at 41% then 24% utilization with stable
  memory, unchanged stderr, and no aggregate yet.
- Final G1 later runs at 37% then 45%, with no terminal result or aggregate
  yet.
- Final G1 then moves from 24% to 40% utilization, with the same stable
  pre-terminal state.
- Final G1 remains at 41% then 36% utilization; no result or aggregate is yet
  complete.
- Final G1 later remains active at 35% then 42%, with unchanged terminal state.
- At 141.9 total minutes (roughly 37 minutes into Seed 43), final G1 remains
  active at 39% then 31%, with no aggregate yet.

# 2026-07-31 R44A terminal closure

- The authorized R44A six-arm sequence and aggregation completed with terminal status `STOP_PRTA_GEN_R44A_CROSS_SOURCE_SILVER_SFT_SURVIVAL`.
- R42/R43 remain locked and were not launched. Terminal documentation, integrity checks, and Git handoff are now in progress.
- The current authority surfaces are `TIER_CXR_VLM_Next_Stage_Proposal_CN.md`, `docs/PROJECT_STATUS_CN.md`, `README.md`, and `reports/README.md`.
- Fresh terminal audit confirmed six valid arm receipts, 94 optimizer updates per arm, nine gate failures, false protected-outcome reads, and immutable aggregate/sequence hashes.
- The initial authority inventory showed every reader surface still stopped at R41A; the proposal, status, README, report index, and R44A protocol now carry the terminal R44A addendum and refreshed reading order.
- The terminal artifacts match the frozen R44A protocol exactly: 1,000/250 patient-disjoint roster, inherited G0/G1 settings, three Seeds, 94 updates per arm, and unchanged all-Seed survival gates.
- Final combined R41A/R44A/support/failure-analyzer regression suite: 31 passed in 14.82 seconds.
- Repository-wide Ruff, Python compileall, and `git diff --check` passed. No dedicated tracked Markdown-link checker exists, so the terminal pass uses a bounded local-link audit over the edited authority documents.
- Edited-document Markdown local-link audit passed (5 authority documents).
- Terminal integrity audit passed: exact STOP status and four registered hashes, six arm receipts, nine gate failures, all protected/unlock flags false, zero R44A workers, and both GPUs at 0 MiB/0%.
- Final diff review confirmed consistent R44A STOP and R42/R43 lock markers across all authority documents.

# 2026-07-31 R45 case-study and new-direction authorization

- Recovered the complete planning state and confirmed clean commit `44a48d4`.
- Added Phases 16–18 for a read-only R44A case study, an independently frozen
  R45 discovery program, and sealed qualification/confirmation.
- Recorded current official ICLR rigor/reproducibility expectations and kept
  them separate from the scientific protocol. No new roster, model, runtime
  root, or GPU process has been created.
- Audited the R44A result/roster schemas without printing identities. The six
  aligned prediction payloads are sufficient for a self-contained,
  identity-free mechanism analysis; no image/token/checkpoint read is needed.
- Reused only stable analytical primitives from the R41A analyzer design
  (metric recomputation, alignment/firewall checks, anonymized cases). R44A
  will receive a separately named analyzer/schema rather than mutating the
  closed R41A output.
- Implemented the separately named R44A identity-free analyzer and five
  fail-closed tests. The output contract includes true-vs-control agreement,
  correctness-changing flips, G0→G1 migrations, cross-Seed sensitivity, and
  anonymized mechanism cases while excluding identity-bearing keys.
- New and legacy analyzer tests pass together (10 passed); focused Ruff and
  compileall pass. Frozen the case-study protocol with exact hashes for all
  six R44A results and the roster before any row-level prediction analysis.
- Committed/pushed the frozen analyzer authority as `4f1e40d`, then executed
  the single identity-free analysis. It completed with 250 rows, 12 anonymous
  cases, no identity fields, and no training.
- Visually checked the generated sensitivity figure. It faithfully shows
  70.0–83.6% true/shuffle prediction agreement and nearly balanced
  true-only/shuffle-only correctness flips; labels and scales are legible.
- Completed the first related-work novelty pass. Generic counterfactual
  swap-loss and temporal-inversion ideas are already occupied by recent
  primary work, so the R45 hypothesis was narrowed to a causal delta evidence
  bottleneck that bridges the existing qualified exact64 representation to
  free generation.
- Wrote the full R44A case-study report and synchronized the Proposal before
  R45 implementation. Phase 16 is complete; Phase 17 begins with an untouched
  support/roster audit, not model code.
- Phase-16 terminal validation passes: 10 analyzer regressions, repository-wide
  Ruff, compileall, edited-document link audit, and `git diff --check`.
- Committed the Phase-16 report/proposal package as `7e73e0d`. Its first push
  hit a transient GitHub TLS `SSL_ERROR_SYSCALL`; the local commit and runtime
  artifacts remain intact and no experiment was restarted.
- Reproduced the Git OpenSSL failure a second time and isolated it to the
  command path: GitHub HTTPS succeeds through the configured local
  `127.0.0.1:7897` proxy, while direct no-proxy HTTPS times out.
- A command-scoped Git Schannel probe reached GitHub and returned a normal
  repository-level response. The first probe used a guessed repository name;
  the next attempt will use the exact configured remote without changing
  global Git or Clash settings.
- Retried the exact registered origin with command-scoped Schannel and pushed
  Phase-16 commit `7e73e0d` successfully. Global Git and Clash settings remain
  unchanged.
- Phase 17 is now active. The R44A builder already contains the needed
  authority validation, identity-safe source loading, gold exclusion,
  image-completeness contract, rare-class-first deterministic assignment, and
  one-row-per-patient mechanics; R45 needs a separately named four-part
  extension that also excludes the complete R44A roster.
- Completed an identity-free residual-support simulation. The provisional
  balanced design is 2,500 discovery-train, 500 discovery-development, 500
  sealed qualification, and 250 sealed confirmation patients; all partitions
  are patient-disjoint and assigned sealed-first. Exact image-complete support
  remains a fail-closed builder gate.
- Implemented the separately named R45 roster freeze, builder, five focused
  regressions, and Chinese preregistration protocol. The builder pins all
  R44A terminal/case/roster hashes, excludes R44A and gold patients, filters
  image-complete rows, assigns sealed cohorts first, requires a 200-patient
  Resolved reserve, and hides identity rows from CLI receipts.
- R45 plus inherited R44A roster regressions pass (12 tests); focused Ruff,
  compileall, JSON parsing, and `git diff --check` pass. No R45 runtime roster
  or GPU process has been created yet.
- Committed and pushed the pre-roster authority as `df75aca`, then ran the
  single exact image-complete preflight. It passed with 224 Resolved patients
  left in reserve and both sealed-outcome flags false.
- Wrote the formal R45 roster once: 3,750 balanced, patient-disjoint,
  image-complete rows across the four frozen partitions; SHA-256
  `0387FCF0B3DA09BE4CC99727EE1278C676BD2D946A87D4377E7F0088F1F7F4D8`.
  No GPU process or model output exists yet.
- Began the outcome-free method-interface audit. The existing structured
  3,840-wide semantic feature path and exact64 Qwen adapter can support CDEB
  without changing the five-class target or the single-injection contract.
- Froze the architectural placement decision: CDEB uses only the four formerly
  neutral reserve positions 60-63 after Tier projection. The qualified
  positions 0-59 and exact-64 physical interface remain unchanged.
- Audited the R44A cache compiler for reuse. R45 will extend it with a
  stage-specific authority/partition contract and initially cache only the
  3,000 discovery patients, keeping both sealed partitions outside the token
  index until the full method/gate freeze.
- Implemented and validated the core CDEB module plus five focused tests.
  Delta/no-delta feature modes, five-class probability normalization,
  reserve-only injection, qualified-position preservation, and the
  delta-no-bridge neutral path all pass; focused Ruff/compileall/diff checks
  also pass.
- Added the full frozen discovery config and a separately named discovery-only
  cache compiler. It structurally excludes qualification/confirmation
  partitions and records both sealed-token flags as false. Combined new and
  inherited regressions pass (18 tests), with focused Ruff/compileall/JSON/diff
  checks also passing.
- Implemented the separately named discovery runner with frozen-Qwen SFT,
  auxiliary five-class loss, reserve-only bridge injection, all four controls,
  cache-equivalence checks, and identity-hidden CLI receipts. Its nine core
  runner/CDEB tests pass; the first lint pass found one unused import, now
  removed before the full validation rerun.
- Implemented the discovery aggregator and synchronized the protocol with all
  exact architecture, optimizer, budget, controls, gate, qualification, and
  confirmation settings. The combined focused suite now passes 24 tests;
  focused Ruff, compileall, and diff validation pass.
- Pre-outcome authority validation passes: 29 focused new/inherited tests,
  repository-wide Ruff, full `src/scripts/tests` compileall, and
  `git diff --check`. The complete method/cache/runner/aggregate authority is
  ready for staged review, commit, and push before any GPU execution.
- Committed and pushed the complete pre-outcome discovery authority as
  `9483ae0`; the worktree was clean at launch.
- The formal discovery-cache preflight passed for exactly 3,000 train/
  development rows, with both sealed-token and sealed-outcome flags false.
  Started the authorized GPU0 cache worker with runtime-owned stdout/stderr
  logs; no training process has started.
- Cache PID 7512 remains healthy in the one-pass image-materialization stage:
  GPU0 memory rose from 637 to roughly 987 MiB with observed utilization, the
  worker accumulates CPU time, stderr is empty, and no premature index or shard
  receipt exists.
- Discovery cache completed successfully after 159.4 seconds with the expected
  3,000 rows and 24 shards. Index SHA-256 is
  `2ECC1350A71C885CCF10BE4665CD1BDC1F532E1B309586FF5879294890A955B6`;
  reproducibility passed exactly and all sealed-token/outcome flags remain
  false. GPU0 released the cache model before training.
- Added a post-cache, pre-training integrity pin for the 5,992-byte token index
  and a formal runner preflight covering the roster/index hashes, sampled shard
  schema, local Qwen path, exact sentinel ID, and fresh output roots. This is
  outcome-free hardening; no method has started.
- Post-cache runner validation passes (11 focused tests, Ruff, compileall,
  JSON/diff checks) and the formal preflight returns
  `PASS_PRTA_GEN_R45_CDEB_RUNNER_PREFLIGHT`. Commit/push this final integrity
  pin before launching any discovery method.
- Committed/pushed the final cache pin as `d774672`, then launched the first
  discovery pair: baseline PID 9780 on GPU0 and full-CDEB PID 23524 on GPU1.
  Both runtime logs are fresh and empty at startup; sealed partitions remain
  unavailable to the runner.
- Both first-pair workers loaded all 713 Qwen weight shards and entered active
  training at roughly 9.7-10.2 GiB per GPU with observed utilization. The only
  stderr content is the normal weight-loading progress display; no error,
  checkpoint, or partial result exists.
- First-pair training remains healthy: both PIDs continue accumulating CPU
  time, GPU utilization was observed around 32-35%, memory remains stable near
  10 GiB per device, and stderr byte counts have not changed from the normal
  loader display.
- At six elapsed minutes, both first-pair methods remain active with stable
  roughly 10 GiB allocations and unchanged stderr. No result directory is
  exposed before the runner's atomic terminal write.
- Both lanes continue active beyond eight minutes with repeated 24-30% sampled
  utilization, steadily increasing CPU time, stable memory, and unchanged
  loader-only stderr.
- At 10.3 elapsed minutes, baseline and full CDEB remain synchronized and
  active at sampled 23-26% utilization; neither has written a partial terminal
  artifact.
- The next two bounded checks continue to show healthy synchronized training,
  stable memory, 20-34% sampled utilization, increasing CPU time, and no
  stderr growth.
- At 14.9 elapsed minutes, both workers remain active and continue accumulating
  CPU time; instantaneous utilization is asynchronous (0%/49% in one sample)
  while allocations remain stable, with no terminal result or new stderr.
- Subsequent samples return to balanced 26-40% utilization on both GPUs; CPU
  time exceeds 1,000 seconds per worker, memory remains stable, and stderr is
  still unchanged.
- At 19.4 minutes, both methods remain active with repeated 18-50% sampled GPU
  utilization and no output/error state change.
- Around 21 minutes, both stderr files grew by the same 153 bytes while both
  lanes remained active with stable memory/utilization. Inspect the identical
  new message before classifying it; no result or process failure occurred.
- The new stderr line is the same harmless Transformers notice that stale
  sampling flags are ignored under greedy generation. Both methods have
  therefore completed training/cache-equivalence and entered the registered
  four-arm free-greedy evaluation; utilization remains active.
- At 24.8 total minutes, both evaluation lanes remain active at sampled
  35-43% utilization, with unchanged warning-only stderr and no premature
  result file.
- Evaluation continues in lockstep with repeated 35-43% utilization and
  steadily increasing CPU time on both lanes; output and error state remain
  unchanged.
- At 29.1 total minutes, both four-arm evaluations remain healthy at sampled
  36-39% utilization, with stable allocations and no terminal artifact yet.
- First-pair evaluation continues with 26-48% sampled utilization and no
  output/error state change; both workers remain closely synchronized.
- At 33.2 minutes, both evaluation workers remain healthy at 36-38% sampled
  utilization; stderr is unchanged at the single greedy-generation notice.
- The next two evaluation checks remain active at 20-36% utilization with
  steadily increasing CPU time and no result/error transition.
- At 37.4 total minutes, both methods remain active in evaluation with stable
  allocations and sampled 20-32% utilization; no terminal result yet.
- Evaluation remains healthy across the next checks at sampled 26-42%
  utilization, with unchanged warning-only stderr and increasing CPU time.
- At 41.5 total minutes, both 2,000-generation matrices remain active at
  roughly 33-34% sampled utilization, still synchronized and error-free.
- The next two evaluation checks remain healthy at sampled 24-42%
  utilization, with no result/error transition.
- At 45.6 total minutes, both evaluations remain active around 29-31%
  utilization; stderr is still fixed at the single generation notice.
- Evaluation remains strongly active in the next samples (32-52% utilization)
  with stable memory and no output/error transition.
- At 49.9 total minutes, both first-pair processes exited and released their
  GPUs. Verify atomic result/checkpoint/status receipts before classifying
  either lane or launching ablations.
- Baseline and full-CDEB arm receipts both pass engineering contracts. Their
  scalar outcomes show baseline ahead of full CDEB and full true-pair below its
  prior-shuffle control; keep this preliminary only and run the two frozen
  ablations before aggregation.
- Launched the second pair: no-delta-evidence PID 20316 on GPU0 and
  delta-no-bridge PID 10792 on GPU1. Both logs and output roots are fresh at
  startup.
- Both ablation workers entered active training at roughly 10.4-11.1 GiB with
  23-41% sampled utilization and synchronized CPU-time growth. Their identical
  139-byte stderr entries require a bounded check but neither process or
  output contract has failed.
- The ablation stderr entries are only complete Qwen weight-loading progress.
  Both lanes continue healthy training at sampled 21-27% utilization with no
  result/error transition.
- Ablation training remains synchronized and healthy with sampled 30-42%
  utilization, stable memory, increasing CPU time, and unchanged loader-only
  stderr.
- At 7.8 ablation-pair minutes, both workers remain active with sampled 28-44%
  utilization, stable allocations, and no output/error transition.
- Ablation training continues with synchronized CPU-time growth and unchanged
  stderr; one instantaneous GPU1 sample was 0% while its worker CPU time still
  advanced, so no stall is inferred.
- At 12.2 ablation-pair minutes, both workers remain healthy with repeated
  26-55% sampled utilization, stable memory, and no output/error change.
- Ablation training remains synchronized at 38%/38% in the latest sample with
  unchanged loader-only stderr and steadily increasing CPU time.
- At 16.5 minutes, both ablations remain strongly active at sampled 43-51%
  utilization, stable memory, and no partial result.
- Near 19 minutes, both ablation stderr logs grew by the same 153 bytes while
  utilization remained 43-47%; inspect the identical message to confirm the
  expected transition into greedy evaluation.
- The identical message is again only the greedy-generation flag notice.
  Both ablations completed training/cache-equivalence and entered their
  registered four-arm evaluations, currently active at 42-47%.
- At 22 ablation-pair minutes, both evaluations remain strongly active at
  sampled 44-50% utilization, synchronized and error-free.
- Subsequent evaluation checks remain balanced at 40-45% utilization with
  stable memory and unchanged warning-only stderr.
- At 26.2 ablation-pair minutes, both evaluations remain active with sampled
  39-52% utilization and no result/error transition.
- The next checks remain synchronized at 38-49% utilization, stable memory,
  and unchanged output/error state.
- At 30.3 ablation-pair minutes, both evaluations remain active at sampled
  31-35% utilization, with no terminal artifact yet.
- Subsequent samples show strong 45-53% evaluation utilization on both GPUs,
  stable memory, and unchanged warning-only stderr.
- At 34.6 ablation-pair minutes, both evaluations remain synchronized at
  sampled 46-47% utilization, with no output/error transition.
- No-delta-evidence completed and released GPU0 first; delta-no-bridge remains
  strongly active on GPU1 at 48% with unchanged stderr. Do not inspect or
  aggregate until the final arm exits.
- Delta-no-bridge then completed and released GPU1. Both ablation arm receipts
  pass all engineering contracts; all four discovery results are now present
  and both GPUs are idle. Execute the frozen aggregate next.
- Frozen aggregation completed with terminal
  `STOP_PRTA_GEN_R45_CDEB_DISCOVERY` and three gate failures. Aggregate
  SHA-256 is
  `9FC9DCEC7471DD169B63555B4BA395817ACB5187B3EA1B351F8D12C742BEE75E`.
- Qualification/confirmation remain locked, unmaterialized, and unread; zero
  R45 workers remain and both GPUs are idle. Phase 17 is complete at its
  preregistered STOP; Phase 18 cannot execute.
- Opened Phase 19 for a separately named post-R45 direction. It must use an
  untouched development cohort and cannot modify or reinterpret the failed
  CDEB gate.
- Completed the first primary-work novelty audit for the post-R45 direction.
  Expert injection, medical contrastive decoding, generic constrained decoding,
  and generic product-of-experts fusion are already occupied. Narrowed R46 to
  current-only causal-margin arbitration between a structured temporal head
  and the frozen generator, with head-safety as an explicit gate.
- Added the R45 terminal discovery report and synchronized the Proposal,
  project status, root README, report index, and planning bundle. Qualification
  and confirmation are explicitly recorded as skipped and still unread after
  the discovery STOP; validation and Git handoff remain before R46 authority
  construction.
- Corrected the Phase-18 checklist so sealed qualification and confirmation
  are recorded as deliberately unexecuted after discovery STOP, rather than
  as pending scientific work.
- Revalidated R45 closure: 17 focused tests passed, repository-wide Ruff and
  compileall passed, all local Markdown links resolve, `git diff --check`
  passed, runtime hashes match the terminal report, every sealed firewall
  remains false, no worker remains, and both GPUs are idle.
- The first closeout commit command exposed two report-header trailing spaces
  but continued after the failed diff check. The commit remains local and
  unpushed; remove the spaces, rerun checks independently, and amend it before
  any network handoff.
- Removed the two spaces, reran both worktree and staged diff checks, amended
  the unpushed closeout as commit `10668d1`, and pushed it to
  `origin/codex/r37-prior-responsive-temporal-adapter` using command-scoped
  Schannel. R45 is now formally closed; R46 authority work may begin.
- Inspected the frozen R45 roster/cache and the audited R40C structured-head
  primitives. R46 will use a 250-patient balanced fresh development roster,
  immutable R45 train tokens, newly cached development tokens, multiseed
  structured heads, and causal evidence arbitration with a baseline fallback.
- Confirmed the R45 baseline artifact is a projector-only checkpoint with
  frozen Qwen, and identified the reusable cache, generation, head-training,
  counterfactual, JSON, and receipt primitives needed for R46.
- A read-only R46 hash inventory repeated the known PowerShell direct-`foreach`
  pipeline parse error. No state changed; rerun with an explicit result array.
- Completed the corrected immutable-authority inventory for the R45 roster,
  aggregate, token index, and inherited baseline checkpoint. Begin the
  separately named R46 roster config, builder, tests, and protocol.
- Implemented the R46 CEA roster config, deterministic builder, focused tests,
  and pre-outcome protocol. Seven focused tests, targeted Ruff, and compileall
  pass. The in-memory-only preflight returns
  `PASS_PRTA_GEN_R46_CEA_ROSTER_PREFLIGHT` with 250 balanced patients and a
  170-patient Resolved reserve; no real roster or GPU work has started.
- Pre-commit R46 roster-authority validation also passes repository-wide Ruff,
  repository compileall, the seven focused tests, and `git diff --check`.
- Committed and pushed R46 roster authority as `57eebc3`, verified the runtime
  root was absent and both GPUs idle, then wrote the real roster exactly once.
  It returns `PASS_PRTA_GEN_R46_CEA_ROSTER_SUPPORT` with 250 balanced,
  all-R45-disjoint development patients; no model outcome has been read.
- Audited the one-time roster receipt and pinned its 195,166-byte size and
  SHA-256 before constructing the cache/method authority.
- The first targeted cache-authority check mistakenly passed the JSON config
  to Ruff, which treated JSON booleans/null as Python names. No runtime work
  started; split JSON parsing from Python linting and rerun.
- Corrected validation passes: three focused tests, Python Ruff, JSON parsing,
  and compileall are clean. The cache preflight returns
  `PASS_PRTA_GEN_R46_CEA_CACHE_PREFLIGHT`; implement the frozen baseline,
  multiseed head/arbitration, aggregate, and protocol before any GPU cache.
- Implemented the complete R46 discovery authority: confidence-weighted
  Jensen-Shannon temporal score, train-quantile baseline arbitration,
  inherited frozen-Qwen/projector baseline, three structured-head Seeds,
  bootstrap aggregate/gates, protocol, tests, and fail-closed receipts. Seven
  focused tests and all targeted static/CLI checks pass; cache remains absent.
- Final pre-cache validation passes 12 focused tests, repository-wide Ruff,
  repository compileall, `git diff --check`, and an explicit absent-token-root
  check. The authority is ready to commit and push.
- Committed and pushed the complete R46 discovery authority as `20d1708`.
  Started the authorized 250-row development-only cache on GPU0 as PID 18820;
  stderr is empty, GPU1 remains idle, and no model outcome is being read.
- The cache exited cleanly after 37.7 seconds and returned
  `PASS_PRTA_GEN_R46_CEA_DEVELOPMENT_TOKEN_CACHE`: 250 rows, 500 images, two
  shards, reproducibility exact, no labels/sentences, all sealed flags false.
  Pinned index SHA-256 `3296E5EA...72AE` into the discovery config.
- The pinned runner preflight returns
  `PASS_PRTA_GEN_R46_CEA_RUNNER_PREFLIGHT` with 2,500 training rows, 250 new
  development rows, local Qwen/sentinel/checkpoint validation, fresh outputs,
  and no protected or sealed read.
- Post-pin validation again passes 12 focused tests, repository-wide Ruff,
  compileall, JSON parsing, and `git diff --check`; commit/push the immutable
  cache receipt before baseline generation.
- Committed and pushed the development cache pin as `61a9b29`, then launched
  the authorized inherited frozen baseline on GPU0 as PID 22372. It is active
  with empty stderr; GPU1 remains idle until the baseline predictions exist.
- R46 baseline loaded all 713 Qwen weight tensors and entered free-greedy
  generation at about 9.1 GiB / 39% sampled GPU utilization. Stderr contains
  only the expected weight-loader progress and ignored sampling-flag notice.
- Baseline generation remains healthy across subsequent checks at 43-46%
  sampled utilization, stable memory, steadily increasing CPU time, and
  unchanged warning-only stderr; no partial result is being treated as final.
- Through 4.8 elapsed minutes the baseline remains active at sampled 49-50%
  utilization, stable 9.1 GiB memory, and increasing CPU time. No result or
  error transition has occurred.
- Through 6.7 minutes the baseline remains healthy at sampled 48-49%
  utilization with unchanged memory/logs and continuing CPU-time growth.
- Through 8.6 minutes baseline generation remains active; sampled utilization
  rose to 57% with stable memory and no result/error transition.
- Through 10.4 minutes the baseline remains healthy at sampled 47%
  utilization, stable memory, increasing CPU time, and unchanged logs.
- The baseline exited cleanly at about 11 minutes with
  `PASS_PRTA_GEN_R46_CEA_BASELINE`: true macro-F1 0.39981, current 0.30742,
  query 0.13114, shuffle 0.38993, schema/finding 1.0, cache-equivalence PASS,
  zero trainable Qwen/projector parameters, and all sealed flags false.
- Launched lightweight structured-head Seeds 17/29 in parallel as PIDs
  9832/2944 on GPUs 0/1. Both processes are alive; initial 0 MiB samples
  occurred before their CUDA training tensors were materialized.
- Seeds 17/29 exited cleanly within 15 seconds and returned
  `PASS_PRTA_GEN_R46_CEA_SEED`, each with 2,000 updates. Structured true F1 is
  0.36275/0.38093, preliminary failures of the 0.40 per-Seed gate; complete
  Seed 43 and aggregate without modifying any frozen setting.
- Launched Seed 43 on GPU0; it exited cleanly within 12 seconds and wrote its
  result. Inspect its registered receipt, then execute the frozen aggregate
  exactly once.
- Seed 43 passed engineering contracts with 2,000 updates and structured true
  F1 0.36679. Frozen aggregation then returned
  `STOP_PRTA_GEN_R46_CEA_DISCOVERY` with five failures. CEA raised mean F1 to
  0.41031 (+1.057 pp) but both registered pooled confidence intervals crossed
  zero; no sealed cohort was unlocked.
- Audited aggregate SHA-256 `FCB30C80...C2D4B`, zero remaining workers, both
  GPUs idle, and all qualification/confirmation token/outcome flags false.
  Opened a separate identity-free R46 case study before any R47 design.
- Implemented and validated the pre-analysis R46 identity-free case-study
  protocol, analyzer, and three focused tests. It freezes three causal-consensus
  rules and suppresses identities/row predictions; commit/push it before use.
- Committed/pushed the analyzer authority as `44acaeb` and ran it once.
  Strict 3/3 true consensus plus 3/3 current disagreement is the only tested
  rule with positive net recovery (+3), true F1 0.41638 versus shuffle 0.38376.
  Select it as R47 UCC on an entirely new 500-patient development cohort.
- Implemented R47 roster config/builder/tests/protocol. Focused tests, Ruff,
  and compileall pass; in-memory preflight returns
  `PASS_PRTA_GEN_R47_UCC_ROSTER_PREFLIGHT` with 500 balanced patients and a
  70-patient Resolved reserve.
- Committed/pushed R47 roster authority as `c090fa1`, verified a fresh runtime
  root, and wrote the roster exactly once. It returns
  `PASS_PRTA_GEN_R47_UCC_ROSTER_SUPPORT`: 500 balanced patients, all 4,000
  R45/R46 patients absent, sealed flags false, and 70 Resolved patients left.
- Implemented the R47 cache, inherited baseline/Seed wrapper, fixed UCC
  aggregate, gates, protocol, and tests. All targeted checks pass and cache
  preflight returns `PASS_PRTA_GEN_R47_UCC_CACHE_PREFLIGHT` for 500 rows with
  a fresh token root.
- Repository-wide validation passed and the complete R47 pre-outcome authority
  was committed/pushed as `ece7112`. Started the 500-row development-only
  cache on GPU0 as PID 29880; it is active and no outcome has been read.
- R47 cache exited cleanly after 45.9 seconds with
  `PASS_PRTA_GEN_R47_UCC_DEVELOPMENT_TOKEN_CACHE`: 500 rows, 1,000 images,
  four shards, exact reproducibility, no labels/sentences, and all sealed
  flags false. Pinned index SHA-256 `2786C403...52C9`.
- Post-pin runner preflight returns `PASS_PRTA_GEN_R47_UCC_RUNNER_PREFLIGHT`
  with 2,500 fit rows, 500 fresh development rows, four shards, inherited
  checkpoint/local-Qwen validation, fresh outputs, and sealed flags false.
  Repository-wide Ruff/compileall and five focused tests also pass.
- Committed/pushed the cache pin as `f7b6835` and launched R47 inherited
  baseline as PID 21924 on GPU0. It loaded into the expected 9.1 GiB footprint,
  is active at sampled 52%, and has only the known loader/sampling notices.
- Through 2.7 minutes R47 baseline remains healthy at sampled 54-55%
  utilization, stable memory, increasing CPU time, and no result/error
  transition.
- Through 4.8 minutes baseline generation remains active at sampled 48-57%
  utilization with stable memory/logs and increasing CPU time.
- Through 6.8 minutes R47 baseline remains healthy at sampled 47-56%
  utilization; no output/error transition.
- Through 8.8 minutes baseline remains active at sampled 47-55% utilization,
  stable memory, and steadily increasing CPU time.
- Through 10.9 minutes R47 baseline remains healthy at sampled 49-55%
  utilization with no result/error transition.
- Through 13.1 minutes baseline generation remains active at sampled 42-51%
  utilization, stable memory/logs, and increasing CPU time.
- Through 15.1 minutes the baseline remains alive with continuing CPU-time
  growth; one instantaneous 22% GPU sample is not treated as a stall because
  memory/log state remains stable.
- Through 17.2 minutes R47 baseline remains active with continuing CPU growth
  and sampled 31-41% utilization; no error or partial result.
- Through 19.3 minutes baseline remains alive with continuing CPU growth; the
  latest 19% GPU sample is again treated as transient because memory and logs
  are unchanged.
- Through 21.4 minutes baseline is strongly active again at sampled 43-54%
  utilization with stable memory and no error/result transition.
- Through 23.4 minutes R47 baseline remains active at sampled 38-40%
  utilization and continuing CPU-time growth.
- R47 baseline completed and released GPU0 after about 25 minutes. Its atomic
  result exists; inspect the receipt before launching head Seeds.
- Baseline receipt passes: true F1 0.39292, current 0.30953, query 0.13471,
  shuffle 0.35399, schema/finding 1.0, cache-equivalence PASS, and zero
  trainable Qwen/projector parameters.
- Launched Seeds 17/29 in parallel on GPUs 0/1; both completed within 15
  seconds and wrote atomic results. Inspect receipts before Seed 43.
- Seeds 17/29 pass with 2,000 updates and structured true F1
  0.39660/0.39422. Launched Seed 43 on GPU0 with all frozen settings unchanged.
- Seed 43 exited cleanly with 2,000 updates and structured true F1 0.40276.
  All baseline/Seed artifacts are present; run the frozen UCC aggregate once.
- Frozen R47 aggregation returned `STOP_PRTA_GEN_R47_UCC_DISCOVERY`: robust
  true-minus-shuffle +5.921 pp with positive CI, but only +0.440 pp over
  baseline with CI crossing zero and absolute F1 0.39731. Three gates fail.
- Audited aggregate SHA-256 `94003D27...D719`, zero workers, and idle GPUs.
  Opened R48 selection-free frozen baseline replication on the still-sealed
  R45 qualification/confirmation cohorts; no router may be tuned further.
- Implemented the R48 qualification config, cache, immutable-baseline runner,
  bootstrap aggregate, protocol, and tests. Static checks pass and the
  preflight returns `PASS_PRTA_GEN_R48_FPRR_CACHE_PREFLIGHT` for the still-
  unread 500-patient qualification cohort.
- Committed/pushed R48 qualification authority as `5f07e76` and started the
  one-time qualification-only cache on GPU0 as PID 9768. Confirmation remains
  unmaterialized and no qualification generation outcome is being read.
- Qualification cache exited cleanly after 62.3 seconds with 500 rows, 1,000
  images, four shards, exact reproducibility, and confirmation flags false.
  Pinned index SHA-256 `CE1D58AA...24B2` before any generation.
- Post-pin runner preflight passes with the immutable checkpoint, 500
  qualification rows, four token shards, zero Seeds/training, fresh output,
  and confirmation still absent. Repository-wide static checks and the
  focused aggregate test pass.
- Committed/pushed the qualification cache pin as `7ca6995` and launched the
  sole R48 qualification baseline as PID 17016 on GPU0. It is active at the
  latest 2026-07-31 monitor (4.1 minutes elapsed, about 9,454 MiB GPU0 memory,
  30% utilization); the result file is not yet present, stderr contains only
  model-load progress plus the known ignored generation-flag warning, and no
  gate or protocol setting has changed.
- R48 qualification remained healthy through 6.3 minutes: PID 17016 was alive,
  GPU0 held about 9.1 GB with active utilization, GPU1 remained idle, and no
  result had yet been atomically published. Continue bounded monitoring of this
  single frozen run.
- At 8.3 minutes the same R48 PID remained active (GPU0 about 9.1 GB and 44%
  utilization), GPU1 was still idle, and the atomic result was still pending;
  no duplicate evaluator was started.
- At 10.3 minutes PID 17016 remained healthy with active GPU0 utilization and
  no result/error publication. The run is still within the expected duration
  for 500 deterministic generations.
- At 12.4 minutes the same evaluator remained active; stderr was unchanged
  except for the already-known ignored sampling-flag warning, with no traceback
  or partial result. Continue the single frozen evaluation.
- At 14.4 minutes PID 17016 and active GPU0 utilization still showed forward
  progress; GPU1 remained idle and the result file was not yet published.
- At 16.5 minutes the evaluator remained healthy (GPU0 about 9.1 GB and 52%
  utilization); no duplicate process or partial result was created.
- Through 18.6 minutes R48 continued normally on GPU0. The duration is
  consistent with the four frozen prior conditions over 500 examples; there is
  still no traceback or atomic result.
- Through 20.6 minutes PID 17016 stayed alive with ongoing GPU work and no
  error/result publication. No intervention was made.
- Through 22.6 minutes the same process remained active on GPU0 with stable
  memory and no traceback. Continue bounded monitoring; do not infer a result
  before the atomic receipt exists.
- Through 24.7 minutes R48 remained active and error-free on GPU0; the atomic
  result remained pending.
- R48 qualification completed at approximately 26.8 minutes: PID 17016 exited,
  both GPUs returned idle, and the atomic baseline result appeared at
  `qualification/baseline/result.json` (74,091 bytes). Proceed to scalar-only
  inspection and the one registered aggregate invocation.
- Ran the registered R48 qualification aggregate exactly once. It returned
  `GO_PRTA_GEN_R48_FPRR_QUALIFICATION`, zero failures, and unlocked
  confirmation while preserving confirmation-token/outcome reads as false.
  True-minus-shuffle is +7.982 pp (CI95 +3.873 to +11.991), and
  true-minus-current is +9.733 pp (CI95 +5.818 to +13.706). The aggregate is
  2,796 bytes, SHA-256
  `6EC0E6B616CB74034F5F6049D7ABCE8DF9A8D36D38A868376C6B03DC2B97EF1A`.
- Froze the R48 confirmation config/protocol and separate cache, runner, and
  aggregate entrypoints. The stage fixes the same checkpoint, prompt, four
  arms, 2,000 bootstrap replicates/seed, and all qualification thresholds on
  the untouched 250-patient cohort.
- Confirmation JSON validation, two focused tests, Ruff, compileall, and cache
  preflight pass. The first runner preflight correctly stopped because the
  confirmation cache receipt is not yet pinned; commit/push authority first,
  then cache and pin before repeating model preflight.
