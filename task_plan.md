# Task Plan: PRTA-CXR R37 Prior-Responsive Temporal Adaptation

## Authority

- User execution authority: the 2026-07-27 PRTA-CXR handoff attached to this
  task.
- Branch: `codex/r37-prior-responsive-temporal-adapter`, created from
  `85f3951`.
- Frozen predecessor result:
  `reports/R33A_CASE_STUDY_RESCUE_RESULT.md`.
- Historical R31 is a valid but non-transferable discovery result.
- R33/R33A are frozen negative evidence:
  `STOP_R33A_FROZEN_CACHE_PREMISE`.

## Objective

Build and qualify PRTA-CXR, a lightweight temporal visual adapter that learns
directional progression semantics and responsiveness to the correct prior
before any 64-token compression or frozen-VLM transfer.

The new route must use an independent longitudinal pretraining cohort with
zero patient overlap against the 300-patient dev split, 483-patient sealed
test, and all quarantined gold/external patients. It must not reuse outcome
labels from the 1,574-patient R33A train partition for further route,
threshold, seed, projection, width, voting, or coverage tuning.

## Non-Negotiable Stop Rules

- Do not run Attempt H/I/J routing or any new threshold/voting search.
- Do not reveal 300 dev, 483 sealed-test, or gold outcomes until the registered
  R37 model/loss/seed/baseline bundle is frozen.
- Do not treat pair-identity discrimination as progression reasoning.
- Do not feed R31 predictions, progression labels, or fitted logits into visual
  tokens.
- Do not unlock R38 token survival or R39 frozen-VLM transfer until R37 passes.
- Stop at the first failed gate rather than scaling downstream.

## Lightweight Provenance Policy

Do not repeatedly recompute hashes of unchanged assets. Reuse the authoritative
R32 split/quarantine identifiers, register new R37 artifacts once at freeze,
and use schema, counts, patient-disjointness, path existence, and targeted
smokes during iteration.

## Gate Order

1. **R37A — Independent data and intermediate-token cache**
   - Build an independent MIMIC-CXR longitudinal image-report pretraining pool.
   - Exclude every R32 dev/test/gold/external patient before report or outcome
     processing.
   - Freeze patient/time/report lineage and an internal train/calibration split.
   - Build current-matched counterfactual-prior (CMCP) candidates.
   - Cache reproducible BiomedCLIP Block-8 patch tokens, not final-layer tokens.
2. **R37B — Temporal adapter pretraining**
   - Freeze ViT Blocks 1-8 and base parameters in Blocks 9-12.
   - Train low-rank adapters plus query-conditioned cross-time attention.
   - Evaluate A0-A6: frozen BiomedCLIP, frozen BioViL-T when available, naive
     adapter, transition alignment, inversion, CMCP, and full PRTA-CXR.
   - Use transition alignment, CMCP, temporal inversion, static-state
     preservation, and optional grounding auxiliary losses.
3. **R37 internal qualification**
   - True pair must beat current-only by at least +2 pp with patient-bootstrap
     CI lower bound above zero and all three seeds positive.
   - True pair must beat CMCP prior by at least +2 pp with CI lower above zero.
   - Temporal-inversion consistency and static-state retention must pass
     thresholds frozen on internal calibration only.
   - PRTA transition tokens must beat frozen BiomedCLIP difference tokens by at
     least +2 pp under a capacity-matched probe.
4. **R37C — One-shot 300-patient dev**
   - Unlock only after all data/model/loss/seed/threshold/baseline choices are
     frozen and internal gates pass.
5. **R38 — Fixed 64-token survival**
   - No sample-level routing.
   - Require at least +2 pp over frozen tokens, CI lower above zero, and retain
     at least 70% of the qualified correct-prior effect.
6. **R39 — Frozen-VLM transfer**
   - Freeze Qwen3-VL-4B, prompt, 64-token budget, projector budget, candidate
     scoring, and no-pixel-bypass contract before the one-shot sealed test.

## Phases

### Phase 0 — R37 authority reset

- [x] Create the R37 branch from `85f3951`.
- [x] Archive the completed R33A planning bundle.
- [x] Freeze R33/R33A code and results as read-only lineage.
- [x] Write the executable R37 protocol and artifact contracts.
- **Status:** completed

### Phase 1 — R37A source and feasibility audit

- [x] Inventory local MIMIC-CXR images, reports, metadata, Chest ImaGenome
  relations, model checkpoints, and available storage.
- [x] Verify data-use boundaries and document any authentication dependency.
- [x] Build the forbidden-patient registry without reading dev/test/gold
  outcomes.
- [x] Measure eligible longitudinal-pair support and class/source coverage.
- [x] Confirm whether at least 30,000 independent training pairs are available.
- **Status:** completed

### Phase 2 — R37A manifests and CMCP index

- [x] Implement patient-disjoint pretrain/internal-calibration manifests.
- [x] Implement current-matched counterfactual-prior retrieval with no target
  outcome leakage at inference.
- [x] Audit >=90% CMCP coverage for dynamic rows or stop and revise the design.
- [x] Add focused unit tests and structural audits.
- **Status:** completed

### Phase 3 — Block-8 cache and minimal adapter

- [x] Implement Block-8 extraction with the shared frozen BiomedCLIP encoder.
- [x] Build a small cache smoke before any full cache.
- [x] Implement low-rank Blocks 9-12 adaptation and query-conditioned
  cross-time attention.
- [x] Implement state and transition token separation.
- **Status:** completed

### Phase 4 — Losses and internal qualification

- [x] Implement transition semantic alignment.
- [x] Implement CMCP margin loss.
- [x] Implement temporal inversion and static-state preservation.
- [x] Implement A0-A6 capacity-matched baselines and ablations.
- [x] Make A0 frozen BiomedCLIP CLS-difference probing executable from the
  merged Block-8 cache.
- [x] Resolve the availability-gated A1 BioViL-T source/checkpoint boundary and
  prove strict official-checkpoint loading before evaluation integration.
- [x] Cache and evaluate the frozen canonical A1 BioViL-T pair representation
  with the pre-frozen linear finding-conditioned probe.
- [x] Store A1 true/current-only/inverted controls once for only the
  transition-supervised pairs; forbid per-seed image re-encoding.
- [ ] Run internal patient-disjoint qualification and bootstrap gates.
- [ ] Apply the frozen 2,000-replicate patient bootstrap and three-seed gate
  without row-level resampling.
- [x] Complete only the user-selected formal A6 seeds 17 and 29; keep seed 43,
  all A0 stages, and aggregation deferred until further direction.
- [x] Repair the pre-outcome pair-count versus finding-row namespace mismatch,
  refreeze formal counts at 46,349/5,242, and resume the unchanged bundle.
- [x] Implement fail-closed seed 17/29/43 aggregation for current-only and CMCP
  controls, including exact row-order and formal-unlock checks.
- [x] Diagnose continuous representation/logit responsiveness for A6 at the
  pre-existing non-formal cap (1,000 train, 500 calibration, 3 epochs) while
  keeping seed 17, rank 32, LR 1e-4, batch size 2, and all losses unchanged.
- [x] Run seed 29 and 43 engineering replications at the identical frozen A6
  1,000/500/3-epoch configuration; do not tune from their outcomes.
- [x] Prepare the formal three-seed/bootstrap execution bundle without
  launching formal mode or protected evaluation.
- [x] Freeze one machine-readable A6 formal-run specification covering seeds,
  patient bootstrap, cache references, output layout, and stop conditions.
- [x] Implement a fail-closed formal preflight command that validates the
  specification and all non-outcome prerequisites without training.
- [x] Add end-to-end tests for seed drift, row-order drift, patient-cluster
  bootstrap validity, protected-outcome firewalls, and resumable output rules.
- [x] Produce a readiness manifest and handoff command while leaving formal
  training locked.
- [x] Operationalize the frozen inversion and state-retention gates before any
  formal result is observed.
- [x] Harden the formal A0 capacity-matched baseline and paired A6-minus-A0
  patient-bootstrap gate.
- **Status:** two_seed_formal_complete_user_paused_full_gate

### Phase 4A — Post-cache engineering chain

- [x] Install a resumable post-cache watcher with sustained-idle checks,
  per-stage PASS validation, and fail-closed partial-output handling.
- [x] Attach a thread heartbeat that resumes diagnosis/analysis when the local
  watcher changes state.
- [x] Complete and merge the Block-8 cache without competing with unrelated
  GPU jobs. The recovered strict merge covers all 144,423 images in 566
  shards without recomputing hashes.
- [x] Build and gate CMCP before any A5/A6 execution. Coverage is 100% over
  26,041 dynamic examples.
- [x] Run bounded A0, A3, and A6 engineering case studies.
- [x] Build and merge the one-time A1 three-control cache on both GPUs:
  37,391 unique pairs.
- [x] Run the cached A1 engineering probe without image re-encoding.
- **Status:** completed_engineering_only

### Phase 4B — R37.1 inversion-consistency repair

- [x] Freeze the two-seed R37 result as
  `STOP_R37_INVERSION_CONSISTENCY` without running seed 43, A0, bootstrap, or
  protected evaluation.
- [x] Produce an outcome-descriptive inversion failure case study from the
  already-observed 5,242-row R37 calibration artifacts; forbid using those
  rows for R37.1 model, loss, threshold, or checkpoint selection.
- [x] Freeze one R37.1 architectural/loss repair before evaluating any fresh
  holdout outcome.
- [x] Create a new patient-disjoint R37.1 validation roster from patients that
  belonged only to the old R37 pretraining partition, and remove those
  patients from R37.1 training.
- [ ] Add fail-closed checks for old-calibration exclusion, new train/validation
  patient disjointness, protected-outcome firewalls, and one-shot evaluation.
- [x] Run a bounded engineering smoke using training-side diagnostics only.
  The captured foreground 100/50/1-epoch diagnostic passed; the earlier
  1,000/500 background attempt remains an engineering STOP with no result.
- [x] Run R37.1 seeds 17 and 29 on the fresh validation roster. Continue to
  seed 43, A0, and patient bootstrap only if both pass the frozen inversion,
  state-retention, current-only, and CMCP gates.
- [x] Recover both incomplete R37.1 seed launches after the 2026-07-28 host
  reboot by archiving only the stale zero-byte logs/status files and relaunching
  the same frozen commands; do not recompute hashes or reuse old calibration.
- [x] Complete the capacity-matched A0 fresh-holdout Seeds 17 and 29, then run a
  separately labeled two-seed patient-cluster bootstrap screen under the same
  roster/firewalls. Seed 43 and the original three-seed gate remain deferred
  by user.
- [x] Write the two-seed fresh-holdout result report and freeze the claim
  boundary before pausing all downstream execution at user request.
- [x] Keep the reduced screen descriptive/internal only; do not call it the
  registered three-seed scientific GO and do not unlock protected evaluation.
- **Status:** pass_r37_1_two_seed_internal_screen_user_stop

### Phase 4C — R37.1 proposal and case-study consolidation

- [x] Explain and freeze the protected-evaluation boundary in reader-facing
  language: 300-dev, 483-test, gold, R38, and R39 remain locked.
- [x] Update the active Chinese proposal with the R37/R37.1 method evolution,
  two-seed A6/A0/bootstrap results, supported claims, and explicit limits.
- [x] Update the result-table authority with filled R37/R37.1 rows rather than
  leaving the completed internal evidence in empty placeholders.
- [x] Create one Chinese case-study closure that summarizes failed routes,
  the equivariant repair, fresh-holdout evidence, and the recommended
  no-more-GPU stopping point.
- [x] Validate cross-document numbers, links, Markdown structure, Git state,
  and protected-outcome firewalls; commit and push the handoff.
- **Status:** completed

### Phase 4D — R37.1 three-seed confirmatory completion

- [x] Run the already frozen R37.1 A6 Seed 43 on GPU 0 and A0 Seed 43 on
  GPU 1 with fresh outputs and unchanged roster/model/loss/threshold settings.
- [x] Validate all three A6/A0 results, inversion/state-retention gates, exact
  row order, and every protected/hash firewall.
- [x] Run the original three-seed patient-cluster bootstrap for A6 versus
  current-only, CMCP, and A0 using 2,000 replicates and seed 37001.
- [x] Emit the direct internal scientific GO/STOP and stop all downstream
  execution if any frozen gate fails.
- [x] If and only if all three-seed gates pass, freeze exactly one R37.1
  candidate and prepare the one-shot R37C 300-dev reveal.
- **Status:** GO_R37_1_THREE_SEED_INTERNAL_QUALIFICATION — the candidate and
  fail-closed R37C implementation are frozen and validated; launch is next.

### Phase 5 — Conditional R37C/R38/R39

- [x] At the end of the project, complete independent human QA over
  the frozen 200-row transition case sheet.
- [x] Write a reviewer-facing Chinese guide and fixed error taxonomy.
- [x] Add a fail-closed validator for reviewer completion, class balance, and
  the frozen 90% overall/85% per-class thresholds.
- [x] Obtain and structurally validate the completed local review CSV.
- [x] Validate the supplied reviewer name/ID, role, date, and independent
  attestation; record relevant experience when the reviewer supplies it.
- [x] Freeze exactly one candidate before any dev reveal.
- [x] Reveal the 300-patient dev once only after internal GO.
- [x] Unlock R38 only after R37C GO.
- [x] Run and pass the frozen R38 fixed-64 survival gate.
- [x] Freeze the R39 Qwen3-VL, prompt, exact-64 interface, shared projector
  capacity, training schedule, A6-versus-A0 primary comparison, current-only,
  query-only, prior-shuffle controls, seeds, and bootstrap before any sealed
  outcome reveal.
- [x] Implement outcome-free sealed Block-8/token caches, shared A6+A0
  projector training, pre-reveal sealed prediction freezing, the one-shot
  483-label reveal, and final three-seed patient bootstrap.
- [x] Commit and push R39 and launch the duplicate-safe two-GPU chain.
- [x] Monitor the active chain and stop directly on its
  registered scientific GO/STOP.
- [x] Keep gold sealed pending the separately registered post-R39 boundary.
- [x] Record the one-shot 483-patient result, interface audit, engineering
  receipt repair, limitations, and terminal evidence in the active proposal,
  result authority, and a dedicated Chinese R39 report.
- **Status:** `GO_R39_FROZEN_VLM_TRANSFER_GOLD_SEALED`

### Phase 6 — Repository closeout and experiment-gap audit

- [x] Inventory the tracked repository, identify the single active entrypoint,
  and separate current TIER-CXR-VLM authority from historical proposals,
  planning bundles, runtime-only outputs, and local caches.
- [x] Add a concise root README and durable project-status/index document that
  point readers to the R39 result, proposal, result authority, reproduction
  surfaces, and protected-data boundaries.
- [x] Archive stale root-level CAPES/DIVE proposal surfaces without deleting
  their history, and keep all runtime datasets/checkpoints/predictions outside
  the Git publication boundary.
- [x] Audit completed experiments against the current method claim and the
  proposal's ablation/control/baseline matrix. Classify each gap as required
  for core validity, recommended for a stronger paper, optional, or invalid
  after the one-shot 483 reveal.
- [x] Produce a frozen, outcome-independent next-experiment recommendation;
  do not launch GPU work or use the revealed 483 outcome for tuning.
- [x] Validate links, Markdown, Git cleanliness, and existing focused tests;
  update the three planning files, then commit and push the organized handoff.
- **Status:** completed

### Phase 7 — Outcome-independent component ablation and strong baselines

- [x] Freeze a new protocol that excludes the revealed 483-test and all gold
  outcomes from model, hyperparameter, threshold, seed, and checkpoint
  selection.
- [x] Audit the available patient-disjoint development roster and select a
  valid execution cohort without reading protected outcomes.
- [x] Implement and test a matched A2/A3/A4/A5/A6 component-ablation bundle
  with identical cache, adapter capacity, optimization budget, seeds, and
  patient-cluster statistics.
- [ ] Implement and test the strongest feasible comparison bundle: frozen
  A0, naive exact-64 prior/current concatenation, Siamese temporal pooling or
  signed-plus-absolute difference, and raw two-image frozen Qwen3-VL with its
  unequal pixel/token compute reported separately.
- [x] Freeze the VLM-level temporal-reversal audit and its mapping/statistics
  before any new inference.
- [x] Run structural preflight, process/GPU checks, and focused tests; commit
  and push the frozen protocol before any formal GPU execution.
- [ ] Launch only protocol-authorized jobs on the two GPUs, monitor without
  duplicating processes, and stop directly on engineering or scientific
  terminal conditions.
- [ ] Aggregate paired patient-cluster results, update the active reports and
  planning files, then commit and push the completed evidence package.
- **Status:** paused_by_user (2026-07-30 11:52 +08:00; no R40 GPU
  process or monitor remains active)

### Phase 8 — PRTA-Gen generative readiness (new R40A/R40B namespace)

- [x] Treat the supplied PRTA-Gen judgment as the new design authority while
  preserving the completed R39 result and the separately paused R40
  component/baseline protocol.
- [x] Freeze an outcome-independent PRTA-Gen readiness protocol that forbids
  the revealed 483-test and sealed gold/external outcomes from development,
  selection, thresholding, or checkpoint choice.
- [x] Implement R40A token-information target/audit contracts for progression,
  laterality,
  coarse anatomy, degree, and evidence-sentence retrieval, with current-only,
  query-only, and prior-shuffle controls and fail-closed label availability.
- [x] Implement `GenerativeVLMAdapter.forward_sft`,
  `GenerativeVLMAdapter.score_sequence`, and
  `GenerativeVLMAdapter.generate_text` while preserving exact-64,
  no-pixel/video, prefix-label masking, and trainable-parameter firewalls.
- [x] Add focused unit and integration tests for exact placeholder injection,
  assistant-only causal loss, generation stopping, cached/uncached first-step
  agreement, sequence scoring, and projector/LoRA-only gradients.
- [x] Build and validate only an outcome-free R40A/R40B engineering package;
  freeze and commit the protocol before any GPU launch.
- [x] Run the smallest authorized information audit: target support, 64-row
  token-cache smoke, full training/development exact-64 caches, three-Seed
  control probes, and 2,000-replicate patient-cluster bootstrap.
- [x] Stop before the R40B 32–64-row Qwen overfit smoke because progression
  failed the frozen all-Seed information gate; keep R41/R42/R43 locked.
- [x] Write the terminal report and synchronize the repository authority
  surfaces without resuming the separately paused old R40 queue.
- **Status:** `STOP_PRTA_GEN_R40A_INFORMATION_SUFFICIENCY`

### Phase 9 — Case-driven PRTA-Gen repair on a new authority

- [x] Build a descriptive R40A failure case study from already-observed
  development predictions only; summarize error clusters, control collisions,
  class/patient concentration, and token-level information loss without
  relabeling, threshold search, or changing the closed R40A result.
- [x] Summarize every prior failed route relevant to the current proposal and
  map each failure to one testable repair hypothesis rather than retrying the
  same method.
- [x] Reserve deterministic discovery and one-shot qualification patient
  partitions before inspecting their route-specific outcomes. Keep them
  disjoint, remove qualification patients from candidate fitting, and retain
  all 300-dev/483/gold/external firewalls.
- [x] Freeze a small ordered candidate family that tests whether the R40A
  failure came from lossy three-mean pooling rather than from the exact-64
  token sequence itself. Compare capacity-bounded token-statistic and
  query-conditioned token readouts against the same current/query/shuffle
  controls.
- [x] Run candidates only on the discovery boundary, stop each failed
  candidate at its first registered gate, and select at most one route using
  the predeclared rule.
- [x] Close R40A.1 after both predeclared candidates fail their first
  Seed-level prior-shuffle gate; keep its 1,500-patient qualification boundary
  unread.
- [x] Freeze R40A.2 around the newly identified token-layout mismatch:
  use the registered `4/12/16/16/12/4` query/state/global/local/relation/reserve
  boundaries, exclude the observed R40A.1 discovery patients, and reserve a
  fresh discovery2 split from the old fit partition.
- [x] Run the committed R40A.2 roster/support audit and confirm that the new
  fit2/discovery2 partitions exclude all 1,500 observed R40A.1 discovery
  patients while preserving the original sealed qualification boundary.
- [x] Freeze the selected route before the one-shot qualification boundary;
  require all three Seeds and patient-cluster confidence intervals rather than
  a favorable point estimate.
- [x] Only after a new information GO, run the 32–64-row R40B generative
  overfit smoke and its exact-64/no-pixel/assistant-only/LoRA firewalls.
- [x] Execute and close that R40B free-greedy task: the preregistered
  3/12/24-epoch ladder preserved every engineering contract but stopped below
  the required 32/32 progression generation.
- [x] Freeze a distinct R40B.1 constrained structured-decoding case study on
  a new 32-patient fit cohort that excludes every observed R40B patient.
  Score exactly the five legal two-key JSON sequences with the existing
  `score_sequence` API; do not tune the exhausted free-greedy cohort.
- [x] Execute R40B.1 once on its fresh cohort and close it at 28/32
  progression despite passing all form/contract/loss gates.
- [x] Freeze R40B.2 on a third disjoint fit cohort. Upweight only the explicit
  progression value tokens inside the assistant suffix and score only that
  value span conditioned on the legal JSON prefix; keep the rest of the
  schema, model, exact-64 path, and firewalls unchanged.
- [x] Execute R40B.2 once and close it after weighted token CE destabilizes
  the semantic decision (82.22% progression-token, 24/32 structured output).
- [x] Freeze R40B.3 on a fourth disjoint cohort with an explicit five-way
  progression decision at the first differing assistant token, plus a small
  uniform SFT auxiliary. Use unique registered first-token IDs and construct
  the legal JSON only from the selected class.
- [x] Execute R40B.3 once and close it after direct causal-LM token
  classification still reaches only 23/32 on the fresh cohort.
- [x] Freeze R40B.4 as an architecture-level convergence route on a fifth
  disjoint cohort: a capacity-bounded progression decision head consumes the
  qualification-supported semantic-layout exact64 features and emits the
  legal two-field JSON deterministically. Keep Qwen free generation locked.
- [x] Execute R40B.4 once on its fresh cohort. It passes the frozen engineering
  gate at 32/32 progression, schema, and finding echo with a
  7.33e-08 final/initial loss ratio; no protected outcomes are read.
- [x] If engineering and scientific gates both pass, update the current
  proposal, result authority, case-study report, and planning bundle; otherwise
  preserve the last STOP and define a genuinely new route instead of tuning
  the failed one.
- **Status:** `PASS_PRTA_GEN_R40B4_STRUCTURED_HEAD_SMOKE` — progression-only
  structured emission is engineering-runnable; Qwen free generation, other
  fields, generalization, and R41–R43 remain locked.

### Phase 10 — R40C patient-disjoint structured generalization preflight

- [x] Inventory only the R40A.2 fit-side support needed to freeze a new
  patient-disjoint development generalization protocol. Exclude every patient
  observed by R40B through R40B.4 and do not read 300-dev, revealed 483,
  gold, external, or any new sealed outcomes.
- [x] Freeze an R40C config and Chinese protocol before any route-specific
  outcome exists. Keep the R40B.4 semantic-layout head architecture,
  optimizer, feature standardization, class vocabulary, and deterministic
  two-field JSON surface fixed.
- [x] Implement a deterministic roster builder that assigns remaining fit
  patients to train/development partitions with one row per patient, explicit
  class support, stable hashes, and zero overlap against all five observed
  32-patient cohorts.
- [x] Implement a fail-closed CPU dry-run/preflight plus the GPU train/evaluate
  runner. Evaluation must fit normalization on training only and report
  patient-level five-class macro-F1, per-class recall, schema/finding
  contracts, and true-pair versus query-only/current-only/prior-shuffle
  controls.
- [x] Implement a registered three-Seed patient-cluster bootstrap aggregator.
  Require directionally positive true-pair effects versus query-only and
  prior-shuffle with lower confidence bounds above zero; prevent class-collapse
  PASS with a frozen per-class recall floor.
- [x] Add focused tests, Ruff, compileall, JSON parsing, local-link checks, and
  `git diff --check`; write the proposal/status/planning handoff.
- [x] Commit and push the complete pre-outcome authority, then stop before
  building the real roster or starting any GPU training.
- **Status:** `PASS_PRTA_GEN_R40C_RUNNER_PREFLIGHT` — pre-outcome package
  complete and pushed; real roster and GPU execution await explicit review.

### Phase 11 — R40C one-time real roster freeze

- [x] Revalidate the pushed R40C config/protocol, clean worktree, absent
  runtime root, real-receipt no-write preflight, and idle GPUs before writing.
- [x] Execute the committed roster builder exactly once at the registered
  runtime path. Do not start any Seed or GPU process.
- [x] Audit only receipt-level counts, class balance, patient disjointness,
  exclusion count, firewalls, file hash, and runtime contents without printing
  patient identifiers.
- [x] Update the planning/status/preflight handoff to the frozen roster
  receipt, validate diffs, commit, and push.
- **Status:** `PASS_PRTA_GEN_R40C_ROSTER_SUPPORT` — real roster frozen and
  audited, closure pushed; Seed/GPU execution remains locked.

### Phase 12 — R40C authorized automatic Seed chain

- [x] Revalidate the pushed config/protocol, immutable roster hash, fresh Seed
  output paths, runner preflight, source receipts, clean Git state, storage,
  exact process absence, and idle GPUs.
- [x] Install a fail-closed sequential runtime launcher for Seeds 17, 29, and
  43. Each next Seed may start only after the preceding `result.json` passes
  its frozen receipt audit.
- [x] Start Seed 17 on GPU 0 and monitor the automatic chain without changing
  roster, hyperparameters, thresholds, controls, checkpoints, or protected
  data boundaries.
- [x] After all three Seed receipts pass, run the frozen aggregate exactly
  once. Treat either registered GO or registered STOP as the terminal
  scientific outcome; do not tune or retry around a failed gate.
- [x] Audit final artifacts/processes/GPUs, update all authority and planning
  surfaces, validate, commit, and push the terminal evidence package.
- **Status:** `GO_PRTA_GEN_R40C_INTERNAL_GENERALIZATION` — terminal aggregate
  and documentation closeout complete and pushed.

### Phase 13 — R40D/R41–R43 downstream authority and automatic execution

- [x] Inventory existing R41–R43 code/configs, untouched cohort support,
  image/model readiness, storage, and legal/protected boundaries without
  reading any new outcome.
- [x] Freeze one explicit downstream gate order before GPU work: R41A Qwen
  progression-only SFT, R42A registered G-CMCP/reversal survival, then R43
  confirmatory readiness before any gold/external outcome or prediction.
- [x] Implement fail-closed configs, runners, aggregators, tests, and an
  automatic two-GPU launcher. Do not select Seed/checkpoint/threshold from
  R40C or later observed outcomes.
- [x] Commit and push the complete pre-outcome authority, run no-write and GPU
  preflights, then automatically execute only while every preceding survival
  gate passes.
- [x] Stop at the first registered scientific or feasibility failure; do not
  reinterpret “run all” as permission to bypass a failed gate, invent missing
  external images, violate a DUA, or tune around observed outcomes.
- [x] Audit the terminal artifacts/processes/GPUs, update the proposal,
  results, reports, and planning bundle, validate, commit, and push.
- **Status:** `STOP_PRTA_GEN_R41A_PROGRESSION_SFT_SURVIVAL` — R41A completed
  all six arms and failed eight frozen gates; R42A/R43 were not started.

### Phase 14 — R41A read-only failure case study and proposal closure

- [x] Freeze the analysis boundary before inspecting row-level predictions:
  use only the already-completed R41A 125-patient development outputs; do not
  train, tune, resplit, select a checkpoint, or read protected/gold/external
  outcomes.
- [x] Audit all six result/prediction payloads and their alignment with the
  immutable roster without printing patient identifiers.
- [x] Quantify G0/G1 class confusion, prediction migration, control-arm
  sensitivity, cross-Seed consistency, and representative de-identified
  failure categories, with special attention to `Worse` collapse.
- [x] Write `reports/PRTA_GEN_R41A_FAILURE_CASE_STUDY_CN.md` and update the
  active Proposal/status/index surfaces. Separate observed evidence from
  hypotheses and require any future experiment to use a separately frozen,
  outcome-independent protocol.
- [x] Validate hashes/firewalls, Markdown links, tests, Ruff, compileall, and
  `git diff --check`; commit and push the analysis/report terminal package.
- **Status:** complete — analyzer commit `0445a6d` and report commit `6ce4d41`
  are pushed; no new experiment or downstream stage is unlocked.

### Phase 15 — Independent post-R41A readout feasibility and R44 authority

- [x] Build a scalar-only inventory of patients not used for R40 discovery,
  qualification, R40B–R40B.4, R40C, or R41A train/development. Do not read
  protected 300-dev, revealed 483-test, gold, or external outcomes.
- [x] Require a genuinely patient-disjoint five-class cohort with a
  predeclared minimum per-class train/development support. If the rare-class
  floor is not available, record a feasibility STOP rather than reusing R41A
  development or weakening the claim after inspection.
- [x] If support exists, freeze a separately named R44A class-support survival
  protocol before any new result: fixed roster rule, G0/G1 comparison,
  true/current/query/shuffle controls, Seeds, decoding, class-support gates,
  and no checkpoint/threshold selection.
- [x] Implement fail-closed roster/preflight/runner tests and commit/push the
  complete pre-outcome authority before any roster write or GPU launch.
- [x] Execute automatically only while the new registered gates pass; stop at
  the first feasibility, engineering, or scientific STOP. R42A/R43 remain
  locked regardless of R44A.
- [x] Update the Proposal, reports, status, and planning bundle; validate and
  push the terminal evidence package.
- **Status:** complete — the one-time 1,000/250 roster and exact64 cache passed,
  all six G0/G1 × Seed arms completed 94 updates, and the frozen aggregate
  returned `STOP_PRTA_GEN_R44A_CROSS_SOURCE_SILVER_SFT_SURVIVAL` with nine
  gate failures. R42A/R43 were not started; protected/gold/external outcome
  flags remained false.

### Phase 16 — R44A read-only case study and ICLR-standard hypothesis selection

- [x] Preserve R44A as a terminal STOP and authorize only a separately named
  follow-on direction; do not tune its 250-patient development roster,
  checkpoint, Seed, decoding, threshold, or gate.
- [x] Freeze an identity-free R44A case-study analyzer before inspecting
  row-level prediction behavior. Quantify true-vs-shuffle invariance,
  per-class migrations, cross-Seed stability, G0/G1 transfer, and representative
  de-identified failure mechanisms.
- [x] Review primary related work and current official ICLR evaluation
  expectations. Require a specific question, technically motivated novelty,
  strong baselines/ablations, claim-matched statistics, reproducibility,
  ethics/data boundaries, and explicit negative-result handling.
- [x] Select one new mechanism-level hypothesis only if the case study
  discriminates it from simpler explanations. Write the case study and
  proposal addendum before implementing the new experiment.
- **Status:** complete — the committed case study identifies correct-prior
  under-use plus adapter instability, the primary-work audit rejects generic
  swap-loss/inversion novelty, and the Proposal now selects R45 CDEB.

### Phase 17 — R45 causal delta evidence-bottleneck discovery

- [x] Audit unused CheXpert silver support after excluding every R44A patient
  and all historical gold/protected patients. Freeze mutually disjoint
  discovery-train, discovery-development, sealed qualification, and optional
  confirmation partitions before model work.
- [x] Implement a separately named R45 method plus an inherited Qwen baseline
  and mechanism ablations. The new method must explicitly optimize
  progression-relevant correct-prior use without teaching an artificial
  invalid/shuffle output class or changing the five-class evaluation target.
- [x] Use only discovery-train/development for engineering iteration. Register
  model, loss, Seeds, compute, controls, decoding, primary endpoint,
  per-class floors, bootstrap gates, and fail-closed receipts before reading
  sealed qualification outcomes.
- [x] Commit and push the complete R45 pre-qualification authority, then run
  discovery automatically until one registered candidate passes or the
  discovery budget reaches its frozen STOP.
- **Status:** complete — terminal
  `STOP_PRTA_GEN_R45_CDEB_DISCOVERY`; the frozen budget completed, three gates
  failed, and qualification/confirmation remain unmaterialized and unread.

### Phase 18 — R45 sealed qualification, confirmation, and paper-ready closure

- [x] Do not execute the frozen selected candidate and strong baseline on the sealed
  patient-disjoint qualification cohort with multiseed true/current/query/
  shuffle controls and patient-cluster confidence intervals because discovery
  did not unlock qualification.
- [x] Do not execute confirmation: only if every registered qualification gate
  had passed could one frozen confirmation on a second untouched cohort have
  been revealed. A failed qualification or confirmation is terminal for R45
  and cannot be tuned around.
- [x] Produce the terminal case study, method/ablation/statistics tables,
  reproducibility and ethics statements, limitations, artifact hashes, and
  ICLR-style claim boundary; synchronize Proposal/status/index/planning files.
- [x] Validate code, artifacts, links, firewalls, processes, and GPUs; commit
  and push the terminal package.
- **Status:** complete — sealed stages were formally skipped after discovery
  STOP; terminal documentation and validation are complete, with Git handoff
  recorded in the progress log.

### Phase 19 — post-R45 independent constrained-evidence direction

- [x] Close R45 in the Proposal/status/report surfaces with exact failure
  mechanisms, hashes, process/GPU state, and the qualification firewall.
- [x] Review primary work on constrained candidate scoring, structured
  temporal heads, and product-of-experts fusion. Select a separately named
  R46 hypothesis only if it is distinguishable from generic reranking and does
  not reuse the observed R45 development outcomes as its evaluation set.
- [x] Freeze an untouched R46 development cohort from patients outside the
  entire R45 roster, while reusing only R45 train for fitting. Keep the already
  untouched R45 qualification/confirmation cohorts sealed for a later,
  independently frozen R46 gate.
- [x] Implement, preregister, commit, and push R46 before any new outcome read;
  execute discovery and only proceed to sealed qualification/confirmation if
  every newly frozen gate passes.
- **Status:** complete — R46 discovery reached terminal
  `STOP_PRTA_GEN_R46_CEA_DISCOVERY`; qualification/confirmation remain sealed.

### Phase 20 — R46 CEA discovery execution

- [x] Freeze the cache, inherited generator baseline, multiseed structured
  head, Jensen-Shannon causal score, train-quantile arbitration, fallback
  contract, bootstrap comparisons, discovery gates, and runtime firewalls.
- [x] Commit and push the complete pre-cache authority, then cache only the
  250 new development patients and pin the cache index without reading model
  outcomes. The authority is pushed and the cache is complete; its immutable
  index is now pinned and awaits validation/commit/push.
- [x] Run the inherited frozen baseline once, train/evaluate Seeds 17/29/43,
  select the shared registered train-score quantile, and aggregate exactly
  once.
- [x] Treat the registered discovery GO or STOP as terminal; do not retune
  score, coverage, thresholds, training, or gates around the result.
- **Status:** complete — terminal `STOP_PRTA_GEN_R46_CEA_DISCOVERY`; five gates
  failed and no sealed stage was unlocked.

### Phase 21 — R46 sealed qualification and confirmation

- [ ] If and only if discovery GO, freeze the selected quantile and a complete
  qualification authority before materializing tokens or reading outcomes for
  the existing R45 qualification cohort.
- [ ] Execute multiseed qualification once; if and only if every registered
  gate passes, execute the separately frozen confirmation once.
- [ ] Close with an ICLR-style result/case-study report, exact hashes,
  limitations, process/GPU audit, and synchronized reader surfaces.
- **Status:** permanently locked for R46 after discovery STOP.

### Phase 22 — post-R46 identity-free case study and independent R47

- [x] Freeze and run a read-only R46 failure-case analyzer to quantify when
  each Seed's override helped or hurt, cross-Seed causal agreement, coverage,
  and baseline preservation without exposing identities.
- [x] Select a separately named R47 hypothesis only from the case-study
  mechanism, freeze a new development roster outside all R45 and R46 patients,
  and preserve the original sealed cohorts.
- [x] Implement, preregister, commit, push, and execute R47 once; accept either
  the frozen GO or STOP and do not tune around its outcome.
- **Status:** complete — terminal `STOP_PRTA_GEN_R47_UCC_DISCOVERY`; UCC has
  robust true/shuffle separation but does not significantly beat baseline.

### Phase 23 — R48 selection-free frozen prior-responsiveness replication

- [x] Freeze a separately named, no-training/no-selection R48 protocol on the
  still-unread R45 qualification cohort. Primary question: does the immutable
  frozen baseline outperform prior-shuffle and current-only with positive
  patient-bootstrap lower bounds?
- [x] Commit/push qualification authority before caching; its registered GO
  unlocked the still-unread R45 confirmation cohort.
- [x] Run the frozen 500-patient R48 qualification and apply its registered
  bootstrap gate exactly once; status is
  `GO_PRTA_GEN_R48_FPRR_QUALIFICATION`.
- [ ] Keep the already-unlocked 250-patient R48 confirmation frozen and
  unexecuted while the user-requested raw two-image Qwen baseline runs first.
- [ ] Close R45–R48 with a case-study/negative-result synthesis, exact hashes,
  ICLR claim boundary, tests, processes/GPUs, reader surfaces, and Git handoff.
- **Status:** paused before confirmation generation at the user's requested
  ordering boundary; its cache is pinned and runner preflight passes.

### Phase 24 — Raw two-image frozen Qwen baseline first

- [ ] Reuse the previously declared R40 B3 definition and implement native
  prior/current full-image Qwen3-VL inference with the same five-label JSON
  target and frozen model.
- [ ] Run a fixed engineering smoke without changing the prompt from outcomes,
  then evaluate once on the already-read 500-patient R48 qualification cohort
  so its result is directly comparable to the R48 frozen-token baseline.
- [ ] Report macro-F1, per-class recall, schema/finding validity, runtime,
  peak VRAM, and exact cohort/model pins. Treat this as a development case
  study, not independent confirmation.
- [ ] Show the user the raw two-image result before resuming the already-frozen
  250-patient R48 confirmation.
- **Status:** in progress — repository has an older two-image Qwen2-VL smoke
  and R40 predeclares B3, but no formal Qwen3-VL raw-pixel baseline yet.

## Errors Encountered

| Error | Attempt | Resolution |
|---|---:|---|
| R46 targeted Ruff command included the JSON discovery config and parsed `true`/`false`/`null` as Python names | 1 | Validate JSON with the JSON parser and run Ruff only on Python sources; no config, roster, or runtime state changed |
| R46 authority hash inventory again piped a PowerShell `foreach` block directly | 1 | Accumulate rows in an explicit array before formatting; no file or runtime state changed |
| First R46 inspection guessed the R45 baseline checkpoint below `discovery/baseline_projector/seed_17` | 1 | Resolve the actual immutable layout `discovery/seed_17/baseline_projector/trainable_checkpoint.pt`; no runtime file was changed |
| R45 terminal report contained two Markdown hard-break spaces, and the sequential PowerShell command continued to commit after `git diff --check` failed | 1 | Keep the commit local and unpushed, remove the two spaces with an exact patch, rerun the checks independently, then amend before push |
| First Phase-16 report push failed with `OpenSSL SSL_connect: SSL_ERROR_SYSCALL` to GitHub | 1 | Preserve local commit `7e73e0d`, verify HTTPS reachability, then retry the existing branch without regenerating artifacts |
| R40B.4 implementation inspection guessed `scripts/run_prta_gen_r40b4_structured_head.py` | 1 | Resolve the actual tracked `scripts/run_prta_gen_r40b4_structured_head_smoke.py`; no runtime or result changed |
| R44A terminal authority search guessed nonexistent root `Proposal.md` and `PROJECT_STATUS.md` | 1 | Use the authoritative `TIER_CXR_VLM_Next_Stage_Proposal_CN.md` and `docs/PROJECT_STATUS_CN.md`; no experiment state was affected |
| Pure move-only planning-file patch was rejected as an empty hunk | 1 | Move each file with an explicit archived heading change, then create the new active bundle |
| Combined archive patch used the wrong findings heading | 1 | Inspect exact headings, then archive with matching context |
| First R37 inventory writeback patch expected a different `findings.md` evidence-hygiene body | 1 | Read the active planning files and reapply against exact current context |
| Attempted to inspect a guessed `tests/test_build_r29_fresh_silver_cohort.py` path that does not exist | 1 | Used the actual builder and repository search results; no file was changed |
| First full R37A audit reported `STOP_R37A_DATA_SUPPORT` even though every substantive structural check passed | 1 | The check map used negative facts (`protected_outcomes_read=false`) as PASS booleans; rename them to positive assertions and repair only the small audit JSON without rescanning manifests |
| First Block-8 smoke writeback patch matched a mojibake rendering of the Phase 3 heading | 1 | Search the live file for the exact Unicode heading and reapply the writeback |
| R37 transition extractor v1 passed count support but failed qualitative scope review | 1 | Freeze v1 as a failed case study; repair negation, section, clause, lateral-comparison, and partial-resolution rules in v2 before any training |
| R37 transition extractor v2 retained ample support but New/Worse still admitted uncertainty and alternative scope | 1 | Keep v2 as the second failed case study; reject may/could/potential/versus and ambiguous alternatives, and split neighboring findings conservatively in v3 |
| First v3 tests showed sentence-level negation/alternative context was lost after splitting on `or` | 1 | Apply negated-new and ambiguous-alternative rejection before clause splitting, then keep clause-local checks as a second layer |
| v4 source adjudication found two residual false positives despite passing the 99%/97.5% quality gate | 1 | Freeze the v4 score, then apply only a v4.1 soft-wrap and sentence-level uncertainty bugfix; do not expand the semantic lexicon further |
| DUA search included a nonexistent root `README.md` path | 1 | Use the active protocol documents; no data or repository artifact was changed |
| Combined planning cleanup patch used the console's mojibake rendering of em-dash headings | 1 | Leave the correctly encoded headings unchanged and patch only exact task lines |
| First staged diff check found Markdown trailing spaces and one extra EOF blank line | 1 | Remove the whitespace-only issues and rerun the cached diff check before commit |
| First `hf models info` call requested unsupported expandable field `license` | 1 | Query `cardData` plus repository metadata instead; no file was downloaded |
| Selective BioViL-T `hf download --dry-run` failed during parallel HEAD metadata lookup | 1 | Keep the official commit pin and retry the three required files individually instead of downloading the 1.10 GB repository snapshot |
| Individual BioViL-T download also failed against the globally configured `hf-mirror.com` endpoint | 2 | Diagnose with `hf env`, then override `HF_ENDPOINT=https://huggingface.co` for only the download process; all three required files downloaded successfully |
| Windows `rg` invocation passed Unix-style wildcard path arguments while checking optional dependency files | 1 | Treat it as a shell-glob issue, not a missing-model issue; query repository files via `rg --files` before targeted searches |
| `pip index versions health-multimodal` found no PyPI distribution | 1 | Pin the archived official Microsoft `hi-ml` source instead of installing an unrelated or guessed package |
| First real A1 pair smoke used HI-ML `ImageModel`, whose outer `forward` accepts only one image even when its encoder is multi-image | 1 | Use the official `MultiImageModel` wrapper; it has the same checkpoint parameters and the required `current_image`/`previous_image` forward contract |
| Tiny A1 probe case study produced identical true-pair/current-only predictions and zero F1 on five calibration rows | 1 | Record it only as a pipeline/control smoke, not scientific evidence; require the full frozen cache and adequately powered patient-disjoint evaluation before judging A1 |
| First combined A0/qualification patch expected a nonexistent `test_prta.py` assertion context | 1 | Confirm the patch was atomic, inspect the live test tail, and split the implementation into smaller exact-context patches |
| First A1 cached-control unit test omitted its local `torch` import | 1 | Add the explicit test import; production cache/index code was unaffected |
| A1 cache merger Ruff pass flagged imports after its intentional `src` path insertion | 1 | Add the same file-level `E402` declaration used by the other standalone repository scripts |
| First post-cache watcher start stopped on the PowerShell launcher's UTF-8 BOM | 1 | No experiment stage had started; make the shared JSON reader accept `utf-8-sig`, add a BOM regression test, and restart |
| Cache-start planning writeback twice used stale or mislocated context | 1 | Inspect each live file tail, then update the planning files with separate exact-context patches |
| PowerShell interpreted unquoted `@{upstream}` while checking branch divergence | 1 | Quote the entire revision expression before rerunning the read-only Git check |
| A PowerShell `foreach` block was piped directly in the cache snapshot command | 1 | Accumulate snapshot objects in an explicit array before formatting |
| Both Block-8 parts PASSed, but Windows PowerShell exposed null `ExitCode` values and the launcher misclassified them as failures | 1 | Require PASS part manifests, normalize only null exit codes backed by those manifests, test the launcher logic, merge the existing parts without recaching, and resume the watcher |
| Two isolated redirected exit-code diagnostics were rejected by command policy because they combined temporary-file cleanup with a child shell | 2 | Stop probing through nested temp cleanup; test manifest-backed recovery through repository-level helpers and fixtures |
| A second manifest-inspection command repeated the PowerShell direct-`foreach` pipeline parse error | 2 | Reuse the already-recorded explicit-array pattern and keep subsequent commands single-purpose |
| The terminal R39 validation again piped a PowerShell `foreach` block directly | 3 | Rerun with an explicit `$pidRows` array; terminal status, firewalls, diffs, PIDs, and both GPUs then validated successfully |
| The first cached A1 CPU probe passed FP16 cache tensors directly to an FP32 linear probe and stopped on a dtype mismatch | 1 | Cast cached or direct canonical features to FP32 at the probe tensor boundary, add an FP16 regression test, and resume only the cached probe |
| Focused preflight tests invoked through the standalone `pytest.exe` could not import the repository's namespace-style `scripts` modules | 1 | Use the repository's established `python -m pytest` invocation so the workspace root is on `sys.path`; Ruff and diff checks already passed |
| The partial-output/spec-drift test fixture created a nested temporary transition directory without its parent | 1 | Add `parents=True` to fixture directory creation; production preflight logic was not involved |
| The A6-versus-A0 aggregate test fixture inherited an A6 `calibration` object, so normalization ignored its A0 top-level fields and correctly produced a STOP | 1 | Remove the impossible inherited field from the synthetic A0 payload; production A0 artifacts already use only the top-level schema |
| The new standalone formal pipeline inserted the repository root before importing a sibling script, and Ruff flagged the intentional import order | 1 | Add the same file-level `E402` declaration used by other standalone repository scripts; direct `--help` execution already passed |
| The first formal A6 seeds both stopped before model construction because the bundle expected 33,621 eligible pairs while the runner correctly expanded 46,349 finding-level transition rows | 1 | Register pair and example counts separately, freeze formal training/calibration rows at 46,349/5,242, and resume without changing any observed-outcome-dependent setting |
| The first R37.1 case-study inspection guessed a runtime transition directory that does not exist | 1 | Resolve the transition root from the frozen formal specification before reading manifests; no data or runtime state changed |
| The next inspection guessed the formal specification at the config root instead of its registered `configs/r37` location | 1 | Use `rg --files` to resolve `configs/r37/prta_a6_formal_bundle_v1.json` and stop guessing paths |
| A read-only inspection guessed a separate `run_r37_prta_formal.py`, but formal mode is implemented inside `run_r37_prta_smoke.py` | 1 | Follow the command recorded by the formal pipeline and inspect the existing shared runner; no execution or output changed |
| The first ad hoc inversion case-study command could not import the `visualvit` namespace | 1 | Set `PYTHONPATH` to the tracked `src` directory before rerunning the read-only analysis |
| The first combined R37.1 runner patch expected a different import ordering and was rejected atomically | 1 | Inspect the exact runner import/result contexts and apply the integration in smaller patches |
| The first 1,000/500 R37.1 training-side smoke exited after about 30 minutes without a result directory or stderr | 1 | Treat it as an engineering STOP, not a scientific result; inspect Windows/GPU events, then use a smaller foreground smoke with captured exit state before any retry |
| The optional Security process-exit event query returned an invalid-parameter error | 1 | Do not depend on unavailable process auditing; use explicit foreground exit status and runner-owned stage markers for the next diagnostic |
| The host reboot at 2026-07-28 14:24 +08 interrupted both incomplete R37.1 formal seeds before either output directory existed | 1 | Verify the old PIDs are absent and both GPUs have no compute jobs, archive the stale status/zero-byte logs, and relaunch only seeds 17/29 with the unchanged frozen commands |
| The first completed-result inspection printed the full calibration prediction arrays and flooded the bounded console output | 1 | Switch to scalar-only recursive inspection plus explicit array counts; no protected result or file was accessed |
| The downstream inspection guessed `scripts/aggregate_r37_formal_results.py`, which does not exist | 1 | Resolve the tracked aggregation entrypoint with `rg`; the actual file is `scripts/aggregate_r37_internal_qualification.py` |
| The documentation inventory attempted to inspect a root `README.md`, but this branch has no root README | 1 | Use the two active TIER documents plus tracked R37/R37.1 reports as the handoff surface; do not invent a missing root index |
| The first documentation diff check found Markdown hard-break trailing spaces in newly edited metadata lines | 1 | Remove only the newly introduced trailing spaces and retain the blockquote structure before final validation |
| The authority-reference addendum repeated Markdown hard-break trailing spaces | 2 | Remove the four new hard-break markers and run a final staged diff check before commit |
| The staged check exposed three remaining hard-break spaces in the new case-study header, but PowerShell continued to commit after native `git diff --check` returned nonzero | 3 | Remove the remaining spaces, run `git diff --check` as a standalone gate, then create and push a dedicated formatting-fix commit |
| R37C Seeds 17/29 stopped before model loading because 11 structural rows used lowercase/case-variant finding names | 1 | Canonicalize finding names case-insensitively to the already frozen 12-class registry, reject all non-case variants, preserve the cache/reveal, and resume only fresh seed evaluations |
| R39 projector Seed 17 stopped before training because the parameter-count receipt came from the input-width-16 R32 smoke | 1 | Correct only the derived receipt to the unchanged input-width-768 projector's 9,873,920 parameters, add an exact regression test, preserve all outcome-free caches, and resume from fresh projector outputs |
| Initial repository-inventory command used invalid multi-property `Sort-Object` parameter syntax | 1 | Rerun with explicit property expression hash tables; inventory completed without changing files |
| A report search passed a Windows wildcard path directly to `rg` | 1 | Resolve report paths with `rg --files` before searching; no result or source file was changed |
| A stale-reference search used unsupported regex lookbehind in default `rg` mode | 1 | Use literal searches and filter known archive paths instead of enabling a more complex regex engine |
| Repository-wide Ruff found 28 preexisting issues in six utility scripts | 1 | Remove four genuine lint defects and add scoped `E402` exemptions only where scripts intentionally bootstrap the local `src` path; rerun the full lint command |
| Full pytest had one R6 frozen-manifest failure after 700 passes | 1 | The same targeted test fails at clean commit `24f57c3`; document the preexisting closed-registry drift and do not rewrite historical R6 hashes |
| First combined verification-document patch omitted valid patch-line prefixes between file hunks | 1 | Split the update into correctly delimited file hunks and reapply without changing content |
| Initial R40 roster tests omitted the required `current_view` fixture field and used guessed rather than canonical transition example IDs | 1 | Add the field and generate CMCP target IDs with the production `stable_hash` namespace; production roster code was unchanged |
| First direct R40 roster CLI stopped before reading source rows because the standalone builder did not insert the local `src` path | 1 | Add the same scoped path bootstrap used by other standalone scripts, keep the frozen roster rule unchanged, and rerun only after tests/commit/push |
| First R40 launch preflight matched its own PowerShell command line as an active `--r40-component` process | 1 | Exclude the current preflight PID; no launcher, status, output, or GPU job had started |
| First PRTA-Gen literal-target test masked the word `lung` together with `opacity`, hiding an explicit `lower lung` region | 1 | Narrow only the finding-surface mask to the lesion noun; keep missing/conflicting region labels fail-closed as `Unspecified` |
| Successful PRTA-Gen smoke created the shared `seed_17` parent that the first full-cache path treated as its own output root | 1 | Preserve the smoke and make `formal/` and `smoke_64/` fresh sibling outputs under the frozen Seed directory |
| First formal PRTA-Gen development cache read about 105 GB for only 256 rows because hashed counterfactual priors thrashed the four-shard LRU | 1 | Stop only the verified worker, preserve the partial shard, and compact required DICOM features with one source-shard read before fresh relaunch |
| First compact-cache patch passed generator expressions as a non-final function argument without parentheses | 1 | Parenthesize each generator, rerun collection/tests/Ruff, and do not relaunch before syntax validation passes |
| First direct PRTA-Gen aggregate CLI lacked the standalone repository import bootstrap | 1 | Add the standard scoped workspace/src bootstrap, rerun tests/Ruff/CLI, then retry without changing bootstrap settings |
| First Phase-9 case-study test expected the fourth synthetic row to be both-wrong even though its true-pair prediction matched the target | 1 | Correct only the fixture prediction so all four registered correctness categories occur once; keep production categorization unchanged |
| First combined R40A.2 planning writeback expected a longer moments-candidate finding sentence than the live file contained | 1 | Inspect the exact planning-file tails and reapply the writeback against current text; no runtime or result changed |
| First R40A.2 selector invocation omitted its required explicit output path | 1 | No selection receipt was written; rerun the unchanged selector with the registered `selection.json` path |
| First qualification aggregate invocation passed a selector-only `--selection` argument | 1 | Argument parsing stopped before aggregation; rerun the aggregate CLI with its registered config/roster/candidate/scope interface |
| First R40B token-shard inspection guessed the R39-era `record_ids` key | 1 | Use the registered PRTA-Gen `example_ids` key; the read-only inspection changed no artifact |
| First R40B model run stopped before baseline evaluation because Transformers 5.5 returned rendered chat text from `apply_chat_template(..., tokenize=True)` | 1 | No training/result output occurred; normalize the rendered template through the same tokenizer, add a regression test, and rerun the identical frozen attempt |
| First one-line real-tokenizer R40B.2 mask preflight mangled JSON quoting in PowerShell | 1 | Unit tests and static checks passed; reconstruct the target with `json.dumps` inside Python and rerun only the read-only tokenizer preflight |
| First R40B.3 cohort build rejected the valid R40B.2 exclusion receipt because the generic historical-status registry stopped at R40B.1 | 1 | No cohort was written; add the already-observed R40B.2 cohort status to the exclusion whitelist, test, and rerun unchanged selection |
| R40B.4 focused test expected the pre-R40B.3 exclusion registry exactly | 1 | Production correctly added the newly observed R40B.3 receipt; extend the registry assertion and rerun before freezing the fifth cohort |
| First R40B.4 runner treated its cohort-bearing runtime root as an existing result directory | 1 | No token load/training occurred; freeze a dedicated `structured_head/` result subdirectory and rerun the unchanged cohort/settings |
| Final focused-test command guessed a nonexistent R40A.2-specific aggregate test filename | 1 | No tests ran in that invocation; use the actual generalized R40A.1/R40A.2 aggregate and runner test files, then rerun the full focused set |
| Final authority-marker audit expected a machine-field spelling in the reader-facing proposal | 1 | The proposal already states the same boundary in Chinese prose; audit that actual phrase while keeping the machine field in the terminal result report |
| First R40C support inventory reused PowerShell's read-only `$PID` automatic variable inside a JSONL loop | 1 | The read-only command wrote no artifact and was stopped by exact command-line match; rename the local value to `$patientKey` and rerun only the aggregate inventory |
| R40C finding-registry search passed a Windows-incompatible `configs/r37/*.json` path to `rg` | 1 | Use `rg` on the directory to resolve the exact config, then pin the 12-value registry from `r37_1_candidate_for_r37c_v1.json` |
| First post-write audit assumed nested `audits`/`firewalls` keys and counted the training object as one row | 1 | Inspect field names and types only, then recompute every scalar against the actual flat receipt schema; the roster file was not changed |
| The one-time roster builder CLI printed patient-level row payloads to the local terminal | 1 | Stop reproducing the payload, add a tested scalar-only `receipt_summary` for future CLI output, and verify the frozen roster hash is unchanged |
| A Phase-13 read-only gold audit command printed the full quarantine manifest, including patient identifiers, instead of scalar fields | 1 | Do not reproduce the output; all subsequent gold checks must select only counts, booleans, hashes, and source-level readiness fields |
| Two Phase-13 PowerShell scalar-audit drafts piped `foreach` directly and reused the read-only `$PID` automatic variable | 2 | Keep the commands read-only, accumulate rows in an explicit array, rename the local value to `$patientKey`, and rerun without identity-level output |
| R42A reverse-cache data preflight could not find the not-yet-written R41A roster | 1 | Preserve the pre-outcome ordering: validate static R42A code now, commit the full authority, write the one-time R41A roster, then rerun the data preflight before launch |
| A wrapper around the expected R43 preflight exit code 2 still surfaced a nonzero PowerShell result | 1 | Treat the JSON STOP receipt as the evidence; use explicit captured native exit handling in the master chain, which accepts only registered 0/2 terminal codes |
| First R41A launch stopped during Seed-17 model setup because the runner expected `trainable_parameters` instead of the adapter's real `trainable_parameter_count` key | 1 | No training/result occurred; normalize the real audit keys into the registered scalar receipt, mirror the check in R42A, add a regression test, archive failed logs, and relaunch unchanged |
| Second R41A launch stopped after training but before checkpoint/result creation because the cache-equivalence audit ran twice with G1 LoRA dropout still active | 1 | Make the shared cache-semantic audit temporarily enter deterministic evaluation mode and restore the caller's prior mode; do not change training, decoding, data, or gates |
| First cache-audit verification command guessed a nonexistent `tests/test_prta_gen_r40b.py` filename | 1 | Resolve the actual tracked test path with `rg --files` and rerun the intended focused suite; no production execution was involved |
| First second-launch archive command had an unmatched PowerShell subexpression parenthesis | 1 | The script failed at parse time before mutation; rewrite the target list one path per line and rerun the same validated moves |
| First terminal document-consistency audit required the full status token in the report index even though it only listed filenames | 1 | Add the reader-facing terminal status to the index, then rerun the same audit |
| First Phase-14 field-shape audit piped PowerShell `foreach` blocks directly | 1 | The command failed at parse time before reading payloads; accumulate each scalar-only table in an explicit array and rerun |
| The corrected field-shape audit assumed a top-level development array, but the roster stores it under `partitions` | 1 | No identity value was printed; inspect only nested property names/counts, then bind the analyzer to the actual registered schema |
| A Phase-14 scalar metric audit again left an empty pipeline after a `foreach` block | 1 | The command failed at parse time before reading payloads; collect objects into `$items`, then serialize the completed array |
| First focused R41A case-study validation found one unused test import | 1 | Remove the unused `copy` import and rerun tests, Ruff, compileall, and diff validation as independent gates |
| Phase-14 full pytest retained one R6 frozen-manifest failure after 814 passes | 1 | This is the same closed R6 registry drift already reproduced on clean commit `24f57c3`; record it as preexisting and do not rewrite historical hashes |
| First ReXGradient `hf download --dry-run` failed during remote file metadata resolution | 1 | `hf datasets info` still resolves the official repository; inspect `hf env`, query official Hub file metadata directly, and retry only with an explicit verified endpoint |
| First R44 formal support audit exceeded the 120-second shell command yield during local image-existence scanning | 1 | Do not infer a gate result or create a second audit; verify the original worker/output state with bounded waits, then either accept its atomic result or stop only that worker and optimize the path scan without changing data, selection, or gates |
| First R44A authority-hash inventory piped a PowerShell `foreach` block directly | 1 | The command failed at parse time before reading files; accumulate scalar hash receipts in an explicit array and rerun without printing identity-level data |
| R44A token-loader search used a Windows-incompatible escaped regex | 1 | Read the exact `load_token_variants` function and cache-index tail directly; no source or runtime artifact changed |
| First R41A/R44A stage-contract validation exposed three unused imports and two legacy unit fixtures without the new optional keys | 1 | Remove obsolete imports and use historical defaults for `arm_complete` and `downstream_unlock_allowed`; rerun both R41A and R44A suites to preserve backward compatibility |
| First direct R44A runner alias preflight lacked the standalone workspace import bootstrap | 1 | No model, roster, token, or GPU process started; add the standard workspace/src bootstrap to all three R44A alias entrypoints and rerun static validation before retrying |
| First post-bootstrap alias validation reported E402 and the runner preflight still emitted inherited R41A schema/status | 1 | Add scoped E402 declarations to the three thin aliases and bind runner-preflight schema/status through the same optional stage contract; the actual R44A tokenizer/model contract had passed |
| Phase-16 Git push failed twice through Git for Windows OpenSSL with `SSL_ERROR_SYSCALL` while GitHub HTTPS remained reachable through the local proxy | 2 | Keep the repository and proxy configuration unchanged; use command-scoped `http.sslBackend=schannel` after resolving the exact registered remote URL |
| The first command-scoped Schannel connectivity probe guessed a public repository URL and returned `Repository not found` | 1 | Read the configured remote URL and retry only that exact endpoint; Schannel reached GitHub successfully, so this was a target error rather than another TLS failure |
| R45 roster inspection guessed a standalone `tests/test_build_prta_gen_r44a_roster.py` | 1 | Use the actual combined R44A regression surface `tests/test_prta_gen_r44a.py`; no source or runtime artifact changed |
| First post-roster planning patch matched PowerShell's mojibake rendering of an em dash instead of the UTF-8 file text | 1 | Re-read the bounded section explicitly as UTF-8 and apply the same documentation-only update against the actual text |
| First focused R45 discovery-runner Ruff pass found an unused `math` import | 1 | Remove the unused import and the unused synthetic helper, then rerun the same focused validation before preflight |
| First R48 confirmation runner preflight was invoked before its one-time cache index could be pinned | 1 | Cache preflight, tests, Ruff, compileall, and JSON validation passed; commit/push the frozen authority, materialize only confirmation tokens, pin their exact receipt, then run the model preflight |
| First raw two-image preflight summary treated its scalar row count as a result-record list | 1 | Restrict row compaction to list-valued formal results, add a regression test, and rerun the unchanged preflight before any GPU/model load |

## Next Step

Implement and run the user-prioritized raw two-image frozen Qwen3-VL baseline
on the already-read R48 qualification cohort; keep the pinned R48 confirmation
generation paused until that baseline result is shown.
