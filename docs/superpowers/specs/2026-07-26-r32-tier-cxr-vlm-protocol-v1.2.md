# R32 TIER-CXR-VLM Engineering Precision Amendment v1.2

Date frozen: 2026-07-26

This amendment inherits the cohort, quarantine, token layout, model, and gate
boundaries of protocol v1.1. It changes no patient, label, route, model
prediction, or scientific threshold.

## Candidate-score equivalence

Expanded-batch and serial Qwen scoring use the same autoregressive
mean-token-log-likelihood formula. On the real frozen 4B model, changing the
GEMM batch shape produces expected precision-dependent numerical differences
even with eager attention and deterministic CuBLAS:

- BF16 preserved the candidate argmax but showed up to 0.17 absolute
  log-likelihood difference;
- FP32 preserved the candidate argmax and reduced the maximum difference to
  `2.96e-5`.

R32 engineering equivalence is therefore frozen as:

1. the FP32 reference has identical candidate argmax and maximum absolute
   score difference at most `1e-4`;
2. the BF16 production smoke has identical candidate argmax and reports its
   score difference as a precision diagnostic;
3. unit-scale deterministic models remain equivalent at `atol=rtol=1e-6`.

This amendment was made during R32 engineering smoke. No silver test or gold
outcome was read.
