# CAPES-CI Query-Anchor R3 Frozen Calibration Protocol

Status: frozen engineering calibration protocol, 2026-07-22  
Protocol ID: `CAPES_CI_QUERY_ANCHOR_V2_R3_2026_07_22`  
Evidence class: `QUERY_GATED_RELATION_MEDIATOR_ENGINEERING_NONCONFIRMATORY`

## 1. Authority and immutable predecessor

R3 inherits every construction, split, seed, threshold, baseline, exact-64,
fairness, stopping, reproduction, provenance, and claim-boundary requirement in
`CALIBRATION_PROTOCOL_R2_2026-07-22.md`, whose hash is included in the source
manifest. This addendum changes exactly one preregistered item: how the
trainability of a marginal-control architecture is established.

The R2c primary run is an immutable `STOP_MARGINAL_CONTROL` result. Its
prior-only DeepSets branch obtained actual-data train macro-F1 below 0.30 because
the prior-side persistent inputs are deliberately label-identical. That failure
shows the R2 competence criterion was logically impossible for a valid negative
control; it is not reclassified as a method success or failure.

## 2. Separation of bypass and competence estimands

The actual-data bypass estimand is unchanged. Each of the five controls is
trained on the frozen R2 train split and evaluated on the independent frozen R2
development split. Every persistent-three-label development macro-F1 must be at
most 0.45. These models never receive injected signals.

Architecture/optimizer competence is now tested on dedicated positive-control
train/development batches generated with seeds 76401/77401 and 16/24 cases per
label. These batches and feature copies cannot replace, mutate, or be evaluated
as the actual bypass batches. Channels 15:18 on the accessible side are first
zeroed; a three-class one-hot of amplitude 4 is then written on every valid
token for the persistent labels:

- current-only DeepSets: current side;
- prior-only DeepSets: prior side;
- prior/current late-fusion DeepSets: prior side.

The positive control uses the same architecture, learning rate, weight
decay, number of steps, and seed-derived initialization rule as the corresponding
control, but a separately initialized model and optimizer with initialization
seed `seed+1,000,000`. Its weights are never returned to downstream training. It remains
per-side permutation invariant and has no prior-by-current pair axis.

For every seed 17/29/43 and every DeepSets mode, the positive-control train
and independent-development macro-F1 must each be at least 0.99, final train CE
must be at most 0.05, all 500 gradient steps must be finite, endpoint permutation
must change logits by at most `1e-4`, and a cyclically deranged injected code
must yield macro-F1 at most 0.10. Initial/final loss and state hashes are recorded. Failure is
`NOT_EVALUABLE_MARGINAL_CONTROL_INCOMPETENT`. Development bypass failure remains
`FAIL_ASSIGNMENT_BYPASS`. Competence never rescues a development bypass.

A one-step smoke records the probe but does not enforce these thresholds. The
registered primary uses exactly 500 steps and enforces it before any B4,
learned-matcher, or noninferiority training.

## 3. Contamination and provenance checks

The runner must record `uses_separate_feature_copies=true`, injected side,
channels/amplitude, dedicated split/model seeds and tensor hashes, probe losses,
gradient counts, F1, invariance/derangement checks, and initial/final state hashes.
The actual train/development visible hashes must be identical before and after
each control/probe. Unit tests must prove
that the actual input batch is bitwise unchanged after probe construction and
that an incompetent probe fails closed. The R2 parent protocol, this addendum,
runner, reproduction launcher, focused tests, all `src/visualvit/*.py`, and
`pyproject.toml` are included in the composite source hash.

## 4. Gate order and claims

The seven-stage order remains structural integrity, working oracle, marginal
bypass plus independent competence probe, persistent binding, learned recovery,
baseline noninferiority, and exact independent-process reproduction. The first
failure stops the run. No seed deletion, threshold change, formal-test access,
or post-result rescue is permitted inside R3. Even a complete R3 pass remains a
synthetic engineering result and cannot support a pretrained-VLM, full-method,
clinical, or real-data claim.
