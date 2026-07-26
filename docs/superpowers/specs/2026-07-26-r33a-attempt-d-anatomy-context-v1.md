# R33A Attempt D: Anatomy-Aware Contextual Tokens

Date frozen: 2026-07-26

Evidence class: `EXPLORATORY_TRAIN_ONLY_NESTED_OOF`

## Motivation

R29-R31's successful representation used global, exact-anatomy, and expanded
context image crops. Attempts A-C used global/top-change patch summaries and
did not transfer that localization structure.

## Scope

- Reuse the frozen R32 train patch cache.
- Use only 13,566 persistent rows and 1,574 patients from train.
- No dev case metrics, sealed-test records/images, or gold outcomes.

## Deterministic anatomy bridge

Map the registered anatomy text to a 14x14 patch mask using fixed chest-grid
rules for side, vertical zone, lung, hilum, mediastinum, cardiac silhouette,
and costophrenic angle. The context mask is a fixed two-patch dilation.

Token sources:

- query/control: finding and anatomy one-hot only;
- current state: current exact-anatomy patch pool;
- global: prior/current CLS interactions;
- robust local/relation: global patch-mean interactions;
- rich local: prior/current exact-anatomy interactions;
- rich relation: prior/current dilated-context interactions.

Robust/rich corresponding types share projections and retain the
4/12/16/16/12/4 layout. P0 has no image input.

## Evaluation

Use the Attempt A linear probes and original hard-consensus route with the
same folds, seeds, optimizer, bootstrap, controls, and seals.

Attempt D remains train-only exploratory.
