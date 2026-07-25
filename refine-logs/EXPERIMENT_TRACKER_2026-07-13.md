# Experiment Tracker: VisualVIT Route C

**Updated**: 2026-07-13  
**Rule**: only `NON_CONFIRMATORY_PROXY` runs are currently unlocked.

| Run ID | Milestone | Purpose | System / Variant | Split | Metrics / checks | Priority | Status | Notes |
|---|---|---|---|---|---|---|---|---|
| Q000 | M0 | environment preflight | GPU/disk/Python/models/data | N/A | free VRAM, disk, versions, paths | MUST | PASS | 3 independent read-only audits; no download required |
| Q001 | M1 | contract tests | dataclasses + masks | synthetic | shapes, masks, invalid dustbin-dustbin, strict output, convergence | MUST | PASS | final 21 tests pass |
| Q002 | M1 | transport tests | oracle/deranged/learned | synthetic | row/col mass, null birth/death | MUST | PASS | exact hard partial semantics |
| Q003 | M1 | fixed budget | TokenBundle M=64 | synthetic | type counts/order/mask | MUST | PASS | exact 4/28/28/4 |
| Q004 | M1 | B4 isomorphism | B4a vs B4b | synthetic | features/params/config/token checksums | MUST | PASS | assignment-only audit passed all seeds |
| Q005 | M2 | learnability | learned projection proxy | synthetic train/dev | loss, macro F1, recovery, rerun | MUST | PASS | 3/3 seeds; independent aggregate exact match |
| Q006 | M2 | proxy pair builder | local MIMIC | official train only | patient/source uniqueness | MUST | PASS | 240 pairs/240 patients; 180 train/60 dev; no official test |
| Q007 | M3 | encoder smoke | local BiomedCLIP | 2 images + 480 proxy images | feature shape, finite, runtime, VRAM | MUST | PASS | strict load; deterministic 2-image; proxy features complete |
| Q008 | M3 | VLM smoke | local Qwen2-VL-2B/7B | 2-image examples | offline load, strict adapter, VRAM | MUST | PASS-ADAPTER | literal prefix failed; audited no-default adapter frozen and rerun passed |
| Q009 | M3 | independent rerun | Q001-Q005 | same fixtures | deterministic result comparison | MUST | PASS-CORE | tests rerun; synthetic aggregate exact; model rerun not yet duplicated |
| Q010 | M3 | real-image proxy | BiomedCLIP CLS correct vs deranged | MIMIC official-train proxy | macro F1, assignment/convergence audit | MUST | INVALID-CONVERGENCE | raw +4.29±10.31 pp is not interpretable; current-code rerun reproduced seed43 convergence failure |
| Q011 | M3 | soft-plan safety | fractional transport into hard tokenizer | synthetic adversarial | reject silent thresholding | MUST | PASS-BLOCK | fractional plan is explicitly blocked; soft allocator still missing |
| Q012 | M3 | budget overflow safety | >28 entity inputs | synthetic adversarial | explicit hard gate | MUST | PASS-BLOCK | global allocator still missing; formal data cannot run |
| F101 | M4 | formal qualification | license/oracle/split/test seal | gold candidate | legal IDs; ontology/observability; class counts; kappa/IoU/QC thresholds | MUST | BLOCKED | legal oracle currently absent; thresholds are specified in design authority |
| F140 | M4 | external protocol freeze | external identity/license/dedup/split/mapping/adaptation/metrics/scripts | test labels/outcomes sealed; custodian-only IDs/non-outcome hashes for dedup | signed protocol; zero internal overlap; no labels/predictions/metrics read | MUST | LOCKED | must finish before F150/F199; execution remains later |
| F150 | M5 | joint train/dev + protocol freeze | all E1/E2/E3 variants plus F140 external protocol | gold train/dev only | configs/checkpoints/seeds/prompts/scripts/external protocol signed | MUST | LOCKED | requires F101/F140 + allocator + soft path + end-to-end adapter |
| F199 | M6 | single unified test reveal | frozen E1/E2/E3 bundle | sealed gold test | one batch reveal only | MUST | SEALED | no method changes after reveal |
| F201 | M6 | C1 analysis | B4 controls from F199 | same unified reveal | Delta_bind + hierarchical CI | MUST | SEALED | fixed-sequence inference only |
| F301 | M6 | C2 repair analysis | simple/Stage1-2/full from F199 | same unified reveal | Recovery CI + denominator stability | MUST | SEALED | no post-C1 development |
| F401 | M6 | frozen VLM analysis | 64-token injected Qwen from F199 | same unified reveal | paired primary contrast + CI | MUST | SEALED | raw two-image smoke is insufficient |
| F451 | M7 | execute frozen external replication | uncontaminated external set under F140 protocol | external | C1>=5 pp CI>0; Recovery CI>=0.60; VLM>=2 pp CI>0; negative-control ratio gate | MUST | LOCKED | protocol/metrics already frozen before F199; any uncomputable endpoint is FAIL |
| F499 | M7 | external + clean rerun | frozen full pipeline | external/clean env | reproduction manifest | MUST | LOCKED | prerequisite for Phase II |
| P501 | M7 | generic DIVE Phase II | N-image | external benchmarks | claim-specific | DEFERRED | LOCKED | requires F201/F301/F401/F451/F499 all green |
