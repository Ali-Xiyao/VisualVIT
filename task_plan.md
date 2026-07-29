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

### Phase 5 — Conditional R37C/R38/R39

- [ ] At the end of the project, complete independent human QA over
  the frozen 200-row transition case sheet.
- [x] Write a reviewer-facing Chinese guide and fixed error taxonomy.
- [x] Add a fail-closed validator for reviewer completion, class balance, and
  the frozen 90% overall/85% per-class thresholds.
- [x] Obtain and structurally validate the completed local review CSV.
- [x] Validate the supplied reviewer name/ID, role, date, and independent
  attestation; record relevant experience when the reviewer supplies it.
- [ ] Freeze exactly one candidate before any dev reveal.
- [ ] Reveal the 300-patient dev once only after internal GO.
- [ ] Unlock R38 only after R37C GO.
- [ ] Unlock R39/test/gold only in the registered order.
- **Status:** human_qa_pass_formal_internal_running

## Errors Encountered

| Error | Attempt | Resolution |
|---|---:|---|
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

## Next Step

User-paused. Do not start Seed 43, A0, bootstrap, aggregation, or any protected
reveal. Resume only after new user direction and fresh duplicate/output/GPU/
firewall checks.
