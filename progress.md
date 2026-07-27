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
