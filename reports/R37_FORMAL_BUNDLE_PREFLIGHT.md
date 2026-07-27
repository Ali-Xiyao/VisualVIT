# R37 Formal Bundle Preflight

## Verdict

The frozen R37 A6 formal training and internal-qualification bundle is
engineering-ready but intentionally locked:

`READY_R37_FORMAL_BUNDLE_PENDING_HUMAN_QA`

The real runtime preflight passed every specification, artifact, count,
bootstrap, cache, CMCP, output-state, and outcome-firewall check. Formal
execution remains disallowed because the frozen transition audit still reports
`formal_training_unlocked=false`. Exact A6 and A0 formal commands were both
exercised against that gate; each exited nonzero before loading a model,
created no output directory, and started no GPU work.

This is a readiness result, not a scientific GO. No 300-dev, 483-test, sealed
label, or gold outcome was read.

## Frozen Bundle

| Component | Frozen value |
|---|---|
| Candidate | A6 full PRTA-CXR |
| Training seeds | 17, 29, 43 |
| Training rows | All 33,621 qualified pretraining examples |
| Internal calibration rows | All 3,770 examples in one seed-independent order |
| Epochs / batch | 3 / 2 |
| Learning rate / adapter rank | 1e-4 / 32 |
| Bootstrap | 2,000 patient-cluster draws, seed 37001 |
| Primary controls | Current-only and CMCP |
| Inversion consistency | At least 0.90 in every seed |
| State retention | Mean adapted/frozen-current cosine at least 0.99 in every seed |
| Capacity-matched baseline | A0 frozen BiomedCLIP CLS difference |
| A6 minus A0 gate | At least +2.0 pp, all seeds positive, CI lower above zero |

The A0 probe uses the same all-row calibration order and seeds, with its frozen
100-epoch, batch-16, learning-rate-0.01 linear-probe configuration.

## Implemented Fail-Closed Contracts

- Formal A6 rejects any variant, seed, scale, epoch, batch, learning-rate, or
  adapter-rank drift.
- Formal A0 rejects seed, scale, epoch, batch, or learning-rate drift.
- Engineering sampling is never reused in formal mode. Formal calibration is
  complete and seed-independent so paired aggregation cannot compare different
  rows.
- Training outputs use distinct formal schemas and remain
  `scientific_claim_allowed=false` until all aggregation gates pass.
- Aggregation accepts only three firewall-clean, human-QA-unlocked formal
  artifacts for seeds 17/29/43.
- Current-only, CMCP, inversion, state retention, and A6-versus-A0 gates fail
  closed on row-order, seed, variant, status, bootstrap, protected-outcome, or
  source-hash drift.
- Seed output directories must be either absent or contain a complete valid
  result/checkpoint pair. Partial or invalid directories STOP the preflight;
  they are never silently overwritten.

## Runtime Evidence

- Preflight manifest:
  `H:\VisualVIT_runtime\050_routeD\r37_prta_cxr\r37_formal_bundle_preflight.json`
- Bundle specification:
  `configs/r37/prta_a6_formal_bundle_v1.json`
- Runtime status:
  `engineering_preflight_passed=true`
- Formal execution:
  `formal_execution_allowed=false`
- A6 output states: seed 17/29/43 all `fresh`
- A0 output states: seed 17/29/43 all `fresh`
- Protected outcomes read: false
- Source hashes recomputed: false
- Per-shard hashes computed: false

## Scientific Boundary

The earlier three-seed 1,000/500 engineering cases remain positive mechanism
evidence only. They are not substituted into this formal bundle and cannot
unlock R37C. Formal training may start only after the independent transition
case-study gate changes the authoritative audit to an unlocked PASS. R37C,
R38, the 300-dev reveal, the 483-test reveal, and gold remain locked.
