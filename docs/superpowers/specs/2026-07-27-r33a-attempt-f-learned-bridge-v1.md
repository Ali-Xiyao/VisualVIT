# R33A Attempt F: Fold-Trained 64-Dimensional Bridge

Date frozen: 2026-07-27

Evidence class: `EXPLORATORY_TRAIN_ONLY_NESTED_OOF`

## Motivation

R31 trained progression heads over 128/256-dimensional state and multiscale
representations. R33 and R33A A-E instead compressed each source through a
fixed random 64-dimensional bridge before any progression training. Attempt F
tests the proposal-authorized learned projector while retaining exact-64 as the
only supervised bottleneck.

## Prebridge representation

- Reuse Attempt D anatomy masks and cached BiomedCLIP patch tensors.
- Project query, state, global, local, and relation sources independently to a
  fixed outcome-free 256-dimensional prebridge space.
- Robust and rich corresponding blocks share projection matrices.
- Rich uses exact-anatomy local and dilated-context relation sources; robust
  uses coarse global sources.
- Build the same cross-patient prior-shuffle control.

The prebridge is not a claimed deployable token bundle. It is input to the
fold-trained bridge below.

## Learned exact-64 bridge

Every auxiliary and P0-P6 model uses the identical architecture:

`1286 standardized inputs -> 64 GELU units -> 3 progression logits`.

The 64 hidden units are the learned bridge bottleneck. Training uses the
existing 20 epochs, AdamW settings, class/patient weights, nested
patient-disjoint route construction, three seeds, and 10,000 patient
bootstraps. No bridge fitted on an outer evaluation patient is used to predict
that patient.

## Scope and decision

- Train-only 13,566 rows / 1,574 patients.
- No dev, sealed-test, or gold access.
- Preserve original +2 pp, CI, all-seed, strongest-control, query-only,
  prior-shuffle, and leakage gates.
- No hidden width, optimizer, threshold, or routing changes after the run.
