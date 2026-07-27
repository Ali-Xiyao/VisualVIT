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
- [ ] Audit >=90% CMCP coverage for dynamic rows or stop and revise the design.
- [x] Add focused unit tests and structural audits.
- **Status:** in_progress

### Phase 3 — Block-8 cache and minimal adapter

- [x] Implement Block-8 extraction with the shared frozen BiomedCLIP encoder.
- [x] Build a small cache smoke before any full cache.
- [x] Implement low-rank Blocks 9-12 adaptation and query-conditioned
  cross-time attention.
- [x] Implement state and transition token separation.
- **Status:** in_progress

### Phase 4 — Losses and internal qualification

- [x] Implement transition semantic alignment.
- [x] Implement CMCP margin loss.
- [x] Implement temporal inversion and static-state preservation.
- [x] Implement A0-A6 capacity-matched baselines and ablations.
- [x] Make A0 frozen BiomedCLIP CLS-difference probing executable from the
  merged Block-8 cache.
- [x] Resolve the availability-gated A1 BioViL-T source/checkpoint boundary and
  prove strict official-checkpoint loading before evaluation integration.
- [ ] Cache and evaluate the frozen canonical A1 BioViL-T pair representation
  with the pre-frozen linear finding-conditioned probe.
- [x] Store A1 true/current-only/inverted controls once for only the
  transition-supervised pairs; forbid per-seed image re-encoding.
- [ ] Run internal patient-disjoint qualification and bootstrap gates.
- [ ] Apply the frozen 2,000-replicate patient bootstrap and three-seed gate
  without row-level resampling.
- [x] Implement fail-closed seed 17/29/43 aggregation for current-only and CMCP
  controls, including exact row-order and formal-unlock checks.
- **Status:** in_progress

### Phase 4A — Post-cache engineering chain

- [x] Install a resumable post-cache watcher with sustained-idle checks,
  per-stage PASS validation, and fail-closed partial-output handling.
- [x] Attach a thread heartbeat that resumes diagnosis/analysis when the local
  watcher changes state.
- [ ] Wait for the merged Block-8 cache without competing with unrelated GPU
  jobs.
- [ ] Build and gate CMCP before any A5/A6 execution.
- [ ] Run bounded A0, A3, and A6 engineering case studies.
- [ ] Build and merge the one-time A1 three-control cache on both GPUs.
- [ ] Run the cached A1 engineering probe without image re-encoding.
- **Status:** watcher_ready_pending_cache

### Phase 5 — Conditional R37C/R38/R39

- [ ] Freeze exactly one candidate before any dev reveal.
- [ ] Reveal the 300-patient dev once only after internal GO.
- [ ] Unlock R38 only after R37C GO.
- [ ] Unlock R39/test/gold only in the registered order.
- **Status:** locked

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

## Next Step

Install a resumable post-cache watcher, then wait for the existing GPU jobs to
release both devices. It must complete/merge Block-8, build CMCP, run bounded
A0/A3/A6 case studies, build the one-time A1 control cache, and run cached A1
without reading protected outcomes.
