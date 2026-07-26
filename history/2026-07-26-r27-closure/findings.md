# Findings: R27 Binding Identifiability Audit

## Authority interpretation

- The old CAPES strong claim is rejected for the tested R26 endpoint.
- R26 reported B4b oracle minus B4a deranged `+1.1724 pp`, 95% CI
  `[-2.7765, +5.1436] pp`, so `STOP_C1` is preserved.
- The only newly authorized experiment is an exploratory, read-only R27 audit
  of frozen predictions and assignments.
- R27 may generate hypotheses; it cannot be presented as a new confirmatory
  result on the same 170-patient cohort.

## Frozen R26 inputs observed

Runtime root:
`F:\VisualVIT_runtime\050_routeC\r26_c1_oracle_binding\run_v1`

| File | SHA-256 |
|---|---|
| `summary.json` | `2fbb63a5fb97d4be30a6c13daa8c91015cfa2450bd8026c4546540ee1df8e5c0` |
| `predictions.json` | `160f9c66e6009d3e2d45cb4a7b28e06d1e94b037c2112925a9d8af156be40613` |
| `bootstrap.json` | `2d8bf9a2bec80fcfba5cdd9cc02222772b9390d0b6836712cec882d8ae17202a` |
| `b4_isomorphism.json` | `b3390da9779d580f6605469b803863ae31b44f80885941afde3312c45020a139` |
| `folds.json` | `472ecbdaded2e2e980459c42a9cf6e8e7f854595d5e6f017d1d2b9be31b7ef2b` |
| `fit_audit.json` | `785d8a6ca71bb34d581d5b21d17e6a7e972a686a4827d35ca08f6834666c9cc2` |
| `cohort.json` | `71013a070cba1133512408b62d232c13440f343cbafe03aa27be4a7bb8d3fd03` |

Observed cohort: 170 patients, 170 pairs, 774 entities; labels Improved 159,
Stable 355, Worse 260.

## Analysis definitions to freeze

- Pair-level BII is the mean fraction of label-changing targets over the
  registered derangements consumed by R26.
- Semantic corruption is evaluated on the actual R26 B4a assignments, not a
  newly sampled derangement.
- Strata:
  - BII-0: `BII == 0`
  - BII-Low: `0 < BII <= 0.33`
  - BII-Mid: `0.33 < BII <= 0.66`
  - BII-High: `BII > 0.66`
- Effects:
  - B4b oracle minus B4a deranged
  - B4b oracle minus current-only
- Uncertainty: patient-cluster bootstrap, with all entities/seeds/derangements
  for a patient retained together.

## Open schema questions

- `cohort.json` contains one row per qualification entity with patient/pair
  IDs, anatomy, progression label, and the common ordered prior/current boxes.
- `predictions.json` contains the complete crossed
  system/seed/derangement/entity OOF predictions and patient-balanced weights.
- `b4_isomorphism.json` proves zero fixed points and records each deterministic
  pair-seed basis, but it does **not** serialize selected assignment indices.
- Anatomy names and full pair compositions are available in `cohort.json`.

## Frozen-assignment provenance limitation

The reset document assumes R26 serialized assignment maps. It did not. Direct
semantic-corruption calculation is therefore impossible from
`b4_isomorphism.json` alone.

R27 will remain read-only and reconstruct the already-defined deterministic
assignment from:

1. frozen `cohort.json` box order;
2. frozen registered derangement ids;
3. the recorded pair-seed basis;
4. the exact R26 seed function and Torch `randperm` algorithm.

This is not model training or prediction regeneration. The output must label
the assignment source as `DETERMINISTIC_RECONSTRUCTION`, pin the R26 runner and
matching-source hashes, and fail closed if those sources differ from the
frozen commit. This limitation must remain explicit in the final report.

## Preliminary support distribution

Using the closed-form expected label-changing rate over zero-fixed-point
derangements gives the following patient/pair counts before any prediction
effect analysis:

- BII-0: 122
- BII-Low: 5
- BII-Mid: 35
- BII-High: 8

The high-BII stratum is already below a reasonable formal support threshold,
so any apparent high-stratum gain will remain sparse exploratory evidence.

## R27 final evidence

- Actual registered assignment semantics:
  - total: 2,322
  - label-preserving: 1,846
  - label-changing: 476
  - semantic corruption rate: 20.50%
  - reconstructed fixed points: 0
- B4b oracle minus B4a deranged:
  - BII-0: +2.36 pp, 95% CI [-2.23, +6.97]
  - BII-Low: +4.92 pp; CI invalid because only 91.28% of patient-bootstrap
    replicates retained all three labels
  - BII-Mid: -1.50 pp, 95% CI [-9.11, +5.56]
  - BII-High: -6.24 pp, 95% CI [-19.10, +7.75]
- High-BII seed directions are all negative:
  - seed 17: -8.04 pp
  - seed 29: -6.24 pp
  - seed 43: -4.44 pp
- The binding-benefit effect is not monotonic in BII. The registered terminal
  verdict remains `C_SPARSE_HIGH_BII_SUPPORT` because support precedence is
  evaluated first, but the observed mechanism pattern also provides no support
  for the proposed high-BII binding gain.
- B4b oracle minus current-only is +23.42 pp in High-BII, but this does not
  isolate binding because B4a deranged performs even better than B4b there.
  It may motivate an independently powered state-vs-temporal question, not an
  R26 rescue.
- Independent verifier passed all 31 checks. Full tests: 503 passed, one
  registered xfail; focused Ruff and compileall passed.

## Current scientific boundary

R26 remains the formal negative mechanism gate. R27 is a post-hoc explanatory
audit and does not justify learned matcher, TIER, RAD-DINO, frozen VLM, DIVE,
or scale-up. Any R28/R29 work requires a new independently reviewed protocol
and adequate binding-critical support.
