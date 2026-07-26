# R33A Attempt E: Outcome-Free Prior/Current Coherence Adapter

Date frozen: 2026-07-26

Evidence class: `EXPLORATORY_TRAIN_ONLY_NESTED_OOF`

## Motivation

Attempts A-D all fail the registered prior-shuffle attenuation control. Their
relation blocks contain pooled pair interactions, but no objective requires the
bridge to distinguish a coherent longitudinal pair from a cross-patient prior.
Attempt E changes that mechanism directly rather than tuning the downstream
route.

## Scope and seals

- Reuse the frozen R32 patch cache; do not re-encode images or recompute
  provenance hashes.
- Use only the 13,566 persistent rows and 1,574 patients in train.
- Do not inspect dev case outcomes, sealed-test records/images, or gold
  outcomes.
- Preserve Attempt D anatomy and context masks, exact-64 layout, progression
  probes, folds, seeds, bootstrap, and hard-consensus route.

## Coherence pretext

For every train row, construct:

- a positive context pair from its registered prior/current images;
- a finding-matched, cross-patient negative prior using a new deterministic
  salt, distinct from the registered prior-shuffle control mapping.

Fit one outcome-free adapter on the context-pair interaction:

`3840 -> 64 GELU + LayerNorm -> 1 coherence logit`.

The adapter sees only positive/negative pair identity. It never receives
progression labels, probe logits, fold assignments, or dev/test/gold data.
Use 12 epochs, AdamW, learning rate 3e-4, weight decay 1e-2, batch size 256,
and seed 20263350. Report discrimination against the untouched registered
prior-shuffle mapping as an engineering audit, not a progression result.

## Token mutation

- Robust relation: Attempt D coarse relation plus a zero 64-vector.
- Rich relation: Attempt D context relation plus the learned normalized
  64-vector, scaled by `sqrt(3840/64)` so its expected block energy is not
  erased by the shared fixed projection.
- Robust and rich relation inputs have the same 3904 width and share every
  seed-specific projection.
- Query, state, global, local, token layout, and all downstream readers remain
  unchanged.

## Registered interpretation

Attempt E advances only if the train-only primary gate improves and the
prior-shuffle delta attenuates by at least 0.5 pp relative to the primary
delta. A positive primary result with a failed prior-shuffle control remains a
STOP. No hyperparameter or threshold tuning is permitted after seeing this
run.
