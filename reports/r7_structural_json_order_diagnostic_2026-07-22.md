# R7 Structural JSON-Order Diagnostic

Date: 2026-07-22  
Status: `ROOT_CAUSE_CONFIRMED_AWAITING_R7_FIX_AND_FREEZE`

## Purpose

Determine why the frozen R6 CPU dry-run exited successfully and passed all in-memory tests, while its independently reloaded `summary.json` failed strict structural validation with 10 errors.

## Setting

- Immutable source artifact: `artifacts/calibration/capes_ci_qptm_r6_dryrun_20260722_v1/summary.json`
- Immutable audit: `artifacts/calibration/capes_ci_qptm_r6_dryrun_20260722_v1/postrun_audit.json`
- Structural producer: `run_r6_structural_audits`
- Native validator: `validate_r6_structural_audit`
- Runner-independent validator: `validate_r6_metric_evidence` through `_strict_summary_validation`
- Publication rule: `json.dump(..., sort_keys=True)`
- No training, dataset access, model download, or Slurm child step was used.

## Results

1. The in-memory producer emits the eight `microcases` in the explicit `R6_STRUCTURAL_CASE_IDS` order and passes native validation.
2. The durable summary retains the explicit `required_case_ids` array in that registered order.
3. Sorted-key JSON publication alphabetically reorders only the keys of the `microcases` object.
4. Both validators require `list(microcases)` to equal `required_case_ids`, even though JSON object order is not a stable semantic contract.
5. Reordering the loaded mapping by `required_case_ids`, without changing any value or registered report hash, changes native validation from FAIL to PASS and strict validation from 10 errors to zero.

## Analysis

The failure has one sufficient cause: object iteration order was incorrectly treated as protocol evidence. The other nine errors are downstream recomputation failures from this first false condition. Disabling deterministic serialization would hide rather than fix the problem. The registered order already has a correct representation in the `required_case_ids` array.

## Next Steps

1. Create a new R7 corrective protocol that records the immutable R6 failure and forbids reinterpreting it as a PASS.
2. Remove mapping-order semantics from both structural validators while preserving exact key membership, required-ID array order, per-case evidence, derived arithmetic, and self-hash validation.
3. Version the changed structural validation contract and add sorted-key JSON round-trip tests plus missing/extra/required-ID mutation tests.
4. Add an exact terminal dry-run write/read/strict-validation regression.
5. Recompute the closed source manifest and freeze a new R7 authority before running a new output root.
6. Run one new CPU dry-run and a separate post-run audit. Smoke remains locked unless that audit passes.
