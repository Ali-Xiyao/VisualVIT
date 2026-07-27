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
- Completed v4.1 with 24 focused tests passing and 33,621/3,770 transition
  pairs in pretrain/calibration.
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
