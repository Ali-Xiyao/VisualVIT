# R33A Attempt B: Cross-Fitted Rich-Benefit Router

Date frozen: 2026-07-26

Evidence class: `EXPLORATORY_TRAIN_ONLY_NESTED_OOF`

## Fixed components

- Reuse Attempt A direct-transition features without modification.
- Keep P0-P5/P7, the shared final probes, seeds, patient folds, optimizer,
  bootstrap, shortcut controls, and all data seals unchanged.
- Scope remains the 1,574-patient train partition. Dev, sealed test, and gold
  outcomes are not evaluated.

## Route mutation

For each outer fold, fit robust and rich auxiliary label probes. Generate
auxiliary predictions for outer-training rows with inner patient OOF fits.

For a row, count across seeds:

- rich helped: rich correct and robust wrong;
- rich harmed: robust correct and rich wrong.

The benefit target is rich only when helped minus harmed is positive, robust
when negative, and excluded when zero.

The router receives only label-free robust/rich softmax probabilities,
probability differences, entropies, confidence margins, and seed-agreement
statistics. It is balanced L2 logistic regression with fixed `C=0.1`.

Training routes are themselves router-cross-fitted across the four
outer-training folds. The final outer-evaluation router is fit on all
outer-training OOF benefit examples. Prior-shuffle routes use the same already
fitted outer router.

Labels and auxiliary logits are forbidden from the visual tokens and final
progression probe.

Attempt B is exploratory. A train-only GO permits candidate freezing but does
not unlock R34.
