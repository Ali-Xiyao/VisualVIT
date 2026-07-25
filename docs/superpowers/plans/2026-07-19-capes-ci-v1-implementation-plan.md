# CAPES-CI v1 Survival Implementation Plan

Authority: `docs/superpowers/specs/2026-07-19-capes-ci-v1.md`  
Execution target: retained Slurm allocation `4161 / tpami / gpu01`; never cancel parent allocation.

## Wave 1: Interface closure

1. Extend schemas without breaking the 2026-07-13 hard-smoke API.
2. Implement learned two-sided-null MatchGraph and exact optional hardening.
3. Implement assignment-independent deterministic 28-slot allocator.
4. Implement soft RelationCandidates and fixed 4/28/28/4 assembly.
5. Implement RelationProjector and a model-agnostic 64-placeholder adapter.
6. Add Qwen2-VL/Qwen3-VL compatibility shim after inspecting installed model signatures.

Acceptance: all historical tests remain green and new CPU unit/property tests pass from two fresh processes.

## Wave 2: Local/server survival

1. Sync a SHA256-verified focused payload to `~/projects/xiyaowang/050_VisualVIT`.
2. Record server environment and source manifest.
3. Run compile and CPU tests in `dsr_stage2_gpu`.
4. Run GPU differentiability/determinism tests inside `4161` as child steps.
5. Run a frozen Qwen relation-token forward with exactly 64 placeholders and no pixel inputs.
6. Run 8–16-case five-label overfit and independent-process reproduction.

Acceptance: all survival summaries PASS, no NaN/Inf, no oracle cardinality, no pixel bypass, parent allocation still RUNNING and idle after child steps exit.

## Wave 3: Asset and data qualification

1. Reuse server MIMIC-CXR/BiomedCLIP only after manifest and DUA boundary validation.
2. Download only public weights/annotations with official source, version, license, size and SHA256.
3. For credentialed PhysioNet assets, detect access without exposing credentials; do not bypass login/DUA.
4. Build cross-source patient/study/image/hash lineage and fail-closed split audit.
5. Freeze train/dev; keep formal test outcomes sealed.

Acceptance: zero missing files, zero cross-split patient/image overlap, explicit license/DUA/ethics status, sealed test manifest hash.

## Wave 4: Mechanism pilot and protocol freeze

Rows: current-only, equal-budget concat, ProTrans-style transition, B4a, B4b, learned CAPES-CI, Hungarian+reject, balanced Sinkhorn, wrong-anatomy/random controls.

Run the first three training seeds from the preregistered ordered seed bank plus at least three independently namespaced derangement seeds on train/dev only. A one-training-seed pilot is forbidden because it cannot estimate between-training-seed variance. Estimate variance and simulation-based power; expand automatically to the first five training seeds only if the signed power rule requires it; then freeze the minimum relevant effect, sample size, exact seeds, test-once procedure and single-rescue rule.

Acceptance: B4 oracle gap is positive and stable enough to power; learned path has no oracle leakage and shows non-trivial recovery. Otherwise diagnose/pivot without opening formal test.

## Wave 5: Formal main experiments and ablations

- 3–5 training seeds, preregistered derangement seeds.
- gold internal and non-overlapping external set.
- frozen-VLM main result plus second encoder/VLM transfer.
- mandatory ablations: identity, null, change, direction, cycle, allocator, token 32/64/96, projector.
- interventions: assignment swap, null deletion, order swap, image/region occlusion, same-label patient swap.
- patient/seed hierarchical bootstrap, 95% CI, multiplicity control, compute/latency/VRAM.

Acceptance: registered main effect, learned recovery, transfer and key ablation direction all hold; failures and negative results remain in the evidence package.

## Wave 6: Paper evidence closure

Produce method equations, algorithm, nearest-neighbor table, dataset card, reproducibility checklist, configs, manifests, hashes, environment lock, result tables/plots, failure analysis and a completion audit against ICLR/CVPR/AAAI criteria.
