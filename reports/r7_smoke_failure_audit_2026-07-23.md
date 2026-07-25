# R7 seed17 one-step smoke failure audit

## Verdict

`TECHNICAL_FAILURE_R7_UNHANDLED_EXCEPTION` — immutable technical-negative artifact. This is not a method verdict and does not authorize the R7 registered-local run.

## Execution evidence

- Command: `python scripts\run_query_anchor_r4.py --run-dir E:\Xiyaowang\050_VisualVIT\artifacts\calibration\capes_ci_qptm_r7_smoke_seed17_20260722_v1 --smoke --seeds 17`
- Supervised elapsed time: `27.546000000002095` seconds
- Child return code: `4`
- Output root contains only `failure.json`; `summary.json` was not published.
- `failure.json` SHA-256: `24462e5ece275ab532ac81fcd3235bece5224976056fe380c01353ab8ec8986f`
- Supervisor result SHA-256: `3997204be904cc9fdf96c97e33708722d4986ff3a43ce23f0882ede6b8e20eea`
- stdout SHA-256: `9a891de26b2c5bc4d412fd1556106b51925708d486282585bd38538b712395ef`
- stderr SHA-256: `01bc16f94079a6c204ed07159e491137dad45cbc95bf45752e9ed28800c24ab3`

## Strict-validation errors

The fail-closed pre-publication validator reported exactly four derived-field mismatches:

1. `/fair_baseline_gate/assignment_metrics/challenge/hungarian/query/soft_query_nll`: producer `18.42068099975586`, independent recomputation `18.420680743952367`.
2. `/transport_competence_gate/checks/initial_hashes_rederive_exactly`: producer `true`, independent recomputation `false`.
3. `/transport_competence_gate/passed`: producer `true`, independent recomputation `false`.
4. `/transport_competence_gate/status`: producer `PASS`, independent recomputation `FAIL_TRANSPORT_COMPETENCE`.

The NLL mismatch comes from Torch float32 log in the producer versus binary64 `math.log` over persisted probability rows in the independent validator. The three transport mismatches share one cause: the validator directly compared the R6 scalar-evidence hash with the separately encoded runtime module `state_dict` hash.

## Scientific and data boundary

- The one-step smoke is explicitly non-gating. Anti-equivalence, mediator-recovery, and fair-baseline failures after one step are recorded observations, not method decisions.
- The ledger contains only frozen synthetic audit, train, inner-development, and development entries. No formal test or real clinical data was accessed.
- `formal_test_used=false`, `formal_data_authorization=HOLD`, and all formal/full-method claim flags remain false.
- Allocation `4161` was not used, cancelled, or released.

## Required next action

R7 already has a valid independently audited dry-run and a frozen 35-path source closure. Therefore the governed source cannot be patched in place. R8 must introduce only the two corrective semantics above, freeze new source/protocol hashes and output roots, then repeat dry-run and seed17 smoke with independent post-run audits before any 500-step registered-local run.
