# R28b Calibrated Choice-Supervised TIER Result

Date: 2026-07-26

Evidence class: `NON_CONFIRMATORY_R28B_DEVELOPMENT`

## Boundary

R28b is a separate failure-derived attempt. Temperatures and route targets use only nested inner-OOF logits and outer-training labels; outer-test inference remains label-free. R28 A1/A2 are unchanged.

## Attempts

| Attempt | TIER F1 | Uniform F1 | Delta | 95% CI | Engineering | Scientific |
|---|---:|---:|---:|---|---|---|
| tier_b1_choice_hard | 0.4225 | 0.4368 | -1.43 pp | [-5.98, +2.82] pp | PASS | NO-GO |
| tier_b2_choice_guarded | 0.4281 | 0.4368 | -0.87 pp | [-5.13, +3.20] pp | PASS | NO-GO |

## Registered diagnostics

- Guarded-route acceptance: 86.22%
- Final engineering gate: PASS
- Final scientific gate: NO-GO
- Fresh-process reproduction: PENDING

A scientific NO-GO is retained even when the software pipeline passes. The registered thresholds, folds, seeds, and cases are not changed after this result.
