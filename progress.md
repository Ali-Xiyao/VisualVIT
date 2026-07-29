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
  one shared 7,948,800-parameter projector per seed, deterministic one-epoch
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
