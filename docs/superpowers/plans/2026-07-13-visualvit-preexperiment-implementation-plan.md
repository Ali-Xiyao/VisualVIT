# VisualVIT Route C Pre-experiment Implementation Plan

**Date**: 2026-07-13  
**Authority**: `docs/superpowers/specs/2026-07-13-visualvit-unified-research-design.md`  
**Scope**: only `NON_CONFIRMATORY_PROXY`; no sealed test or formal claim.
**Execution status**: completed for component-level smoke；soft/global allocators and MatchGraph-to-Qwen injection remain unimplemented formal blockers.

## Task 1: Fresh preflight and runtime lock

- Verify GPU, free disk, Python/Torch/CUDA, local model/data paths.
- Keep `H:\Xiyao_Wang` read-only.
- Create runtime only at `F:\VisualVIT_runtime\050_routeC`.
- Write environment, storage and model/data inventory evidence.
- Gate: no experiment starts if F would fall below 60 GiB or any job would write H.

## Task 2: Core package and data contracts

Create:

- `src/visualvit/schemas.py`: RegionBatch, MatchPlan, TokenBundle contracts.
- `src/visualvit/matching.py`: oracle, anatomy-compatible deranged and supervised projected hard matching with dustbin；fractional input is explicitly blocked，not silently converted.
- `src/visualvit/tokenizer.py`: exact 64-token global/entity/relation/reserved hard-fixture assembler；inputs above 28 entities are blocked until a deterministic global allocator exists.
- `src/visualvit/audit.py`: assignment-only B4 isomorphism and checksums.
- `src/visualvit/synthetic.py`: deterministic persistent/birth/death fixtures.

Gate: tensor shapes, dustbin semantics and token counts are exact and deterministic.

## Task 3: Unit and mechanism tests

Create tests for:

- real-real, real-dustbin, dustbin-real, forbidden dustbin-dustbin;
- transport mass and valid masks;
- exact token counts `4/28/28/4`;
- B4a/B4b same feature/config/token-type/parameter checksums with different assignment only;
- same seed reproducibility and order-swap label mapping.

Gate: final suite passes twice in clean Python processes；executed result is 21/21 PASS.

## Task 4: Synthetic learnability pilot

Create `scripts/run_synthetic_pilot.py`:

- train/dev only; 128/64 cases by default;
- seeds 17, 29, 43;
- variants B4a deranged, B4b oracle, supervised learned projection proxy with oracle cardinality/assignment supervision；this is not the planned soft matcher;
- same classifier architecture/steps/batch/optimizer per B4 comparison;
- report macro F1, `Delta_bind`, oracle gap, Recovery, runtime and peak memory;
- save config, per-seed JSONL, summary JSON, stdout log and manifest.

Gate: run completes deterministically. Metrics diagnose engineering signal only and are never represented as medical evidence.

## Task 5: Local encoder smoke

- Use one existing local medical encoder only after the preflight identifies an executable environment.
- Read 2–16 train/dev or explicitly non-test images.
- Save only small features/logs to F; do not cache into H.
- Gate: finite feature tensor, expected shape, deterministic preprocessing and bounded VRAM.

If no executable local encoder environment exists, record blocker before any download. RAD-DINO is a later optional ~346 MiB official download, not required for Tasks 2–4.

## Task 6: Local Qwen2-VL two-image smoke

- Use the existing full local Qwen2-VL-2B and 7B paths, offline mode.
- Use two non-test images and fixed constrained response schema.
- Frozen inference only, batch 1, conservative precision.
- Gate: no hidden network download; output parses; log includes exact model hash/path, runtime and VRAM.

If dependency or VRAM gate fails, stop at the interface blocker and do not quantize/change the model silently.

## Task 7: Results, audit and decision

- Update `refine-logs/EXPERIMENT_TRACKER.md`.
- Write synthetic per-run manifests and all run summaries under `F:\VisualVIT_runtime\050_routeC\runs\<run-id>`，the unified evidence manifest at `F:\VisualVIT_runtime\050_routeC\evidence\preexperiment_evidence_manifest_20260713.json`，and `reports/preexperiment_results_2026-07-13.md`.
- Independently rerun core tests/pilot and compare manifests.
- Issue the executed four-part verdict:
  - `GO_NONCONFIRMATORY_COMPONENT_SMOKE_ONLY`;
  - `NO_GO_FORMAL_DATA/LICENSE/ETHICS/ORACLE`;
  - `NO_GO_END_TO_END_TRANSFER`;
  - `NO_GO_PHASE_II`.

## Parallel ownership

- Lane A: environment/model/GPU/storage preflight.
- Lane B: data paths, lineage, proxy pair feasibility.
- Lane C: reference code and dependency reuse.
- Main lane: specification, core package, tests, run orchestration and evidence integration.

Each lane is read-only until its evidence is merged; only the main lane writes shared implementation files during the first pilot.
