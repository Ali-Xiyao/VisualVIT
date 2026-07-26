# R33A Attempt C: Common-Width Nonlinear Token Reader

Date frozen: 2026-07-26

Evidence class: `EXPLORATORY_TRAIN_ONLY_NESTED_OOF`

## Fixed components

- Reuse Attempt A direct-transition exact-64 summaries without modification.
- Restore the registered three-probe hard-consensus route.
- Keep patient folds, seeds, training weights, 20 epochs, batch size 128,
  AdamW learning rate `1e-4`, weight decay `1e-2`, bootstrap, shortcuts, and
  data seals unchanged.

## Reader mutation

The proposal explicitly allows a common-width token MLP. Replace every
774-to-3 linear auxiliary/final probe with the same:

`LayerNorm-by-training-standardization -> Linear(774,128) -> GELU ->
Linear(128,3)`.

All P0-P6 systems and all route probes use this identical architecture and
training budget. Trainable parameter count is 99,587 per probe.

No label, prediction, or auxiliary logit enters the visual tokens.

Attempt C is train-only exploratory. Passing permits candidate freezing but
does not unlock R34.
