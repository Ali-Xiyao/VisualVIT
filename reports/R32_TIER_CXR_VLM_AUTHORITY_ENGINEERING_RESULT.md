# R32 TIER-CXR-VLM Authority and Engineering Result

Date: 2026-07-26

Status: `GO_R32_READY_R33`

## Cohort authority

- R31 reserve authority: 2,383 patients.
- Chest ImaGenome gold quarantine overlap: 26 patients.
- Active zero-gold cohort: 2,357 patients.
- Frozen split: 1,574 train / 300 dev / 483 sealed VLM test.
- Active gold overlap: 0.
- Cross-split patient, study, and image overlap: 0.
- Missing referenced images: 0.
- All five label-support gates pass.

The original 1,600/300/483 proposal arithmetic conflicted with mandatory gold
quarantine. Protocol v1.1 made the smallest pre-model correction by preserving
dev and sealed-test sizes and reducing train to 1,574. No outcome-dependent
balancing or replacement cohort was used.

## Gold/external boundary

- Untouched image-ready official gold: 16 patients total.
- MIMIC: 9 patients; CheXpert: 7 patients.
- ReXGradient: annotations present but parent images absent.
- Conservative overall 80%-power MDE: 35.02 pp.

Gold is therefore descriptive only. R35 remains
`BLOCKED_PENDING_INDEPENDENT_EXPERT_LABELS`. No gold outcome, metric, or
prediction was read in R32.

## Visual cache

- Encoder: frozen BiomedCLIP ViT-B/16 visual trunk.
- Strict visual load: 150/150 keys.
- Trainable vision parameters: 0.
- Scope: train/dev only; sealed-test images were not read.
- Images: 10,562.
- Shape: `[197,768]` FP16 per image.
- Shards: 42.
- Size: 3,196,577,676 bytes.
- Runtime: 160.54 seconds on GPU 0.
- Cache identifier: `7d5f386442b27a1d9d10e199072e3849baf523e59c203d40130c7cb2096dd63f`.

Per user direction, unchanged large files and individual cache shards were not
repeatedly hashed.

## Exact-64 frozen Qwen interface

- Model: local Qwen3-VL-4B-Instruct.
- VLM parameters: 4,437,815,808; trainable: 0.
- Physical token layout: 4/12/16/16/12/4, exactly 64.
- All physical attention values: 1.
- Pixel bypass: false.
- Five candidate scores: finite.
- Relation intervention changes scores: yes.
- FP32 serial/vectorized max absolute difference: `2.9564e-5`.
- Serial/vectorized argmax: identical.

Protocol v1.2 records the real-model FP32 equivalence tolerance at `1e-4`.
Deterministic toy-model tests remain at `1e-6`.

## Verification

- Full pytest: 559 passed, 1 registered xfail.
- R32 scoped Ruff: pass.
- Source/script compilation: pass.
- Historical frozen R10/R31 source hashes remain intact; R32 vectorization is
  isolated in a new adapter instead of modifying the historical adapter.

## Decision

R32 is GO. R33 may start on the 1,900 train+dev patients using nested
patient-disjoint OOF predictions only. The 483-patient sealed VLM test and all
gold outcomes remain unavailable.
