# R28 Case-Study Registry Protocol v1

Status: `FROZEN_BEFORE_CASE_SELECTION`

Date: 2026-07-26

Evidence class: `EXPLORATORY_CASE_STUDY`

## 1. Purpose

Select representative R26/R27 cases for mechanism diagnosis before designing
the TIER MVP. Case-study outcomes may motivate a new model, but they are not an
inferential evaluation set and may not be used to change R26/R27 conclusions.

## 2. Frozen inputs

- R26 `cohort.json`
- R26 `predictions.json`
- R27 `pair_label_composition.json`
- R27 `derangement_semantic_audit.json`

All inputs must match the hashes in their existing manifests.

## 3. Per-entity correctness summaries

For every frozen `qualification_id`:

- `current_accuracy`: mean correctness over training seeds 17/29/43, using one
  derangement copy because current-only predictions are invariant.
- `oracle_accuracy`: mean correctness over training seeds 17/29/43, using one
  derangement copy because B4b predictions are invariant.
- `deranged_accuracy`: mean correctness over all 3 seeds × 3 registered
  derangements.

No probability, feature, or image inspection is allowed before registry
selection.

## 4. Frozen archetypes

Cases may belong to more than one descriptive archetype:

1. `STATE_SUFFICIENT`
   - `current_accuracy >= 2/3`
   - `oracle_accuracy - current_accuracy <= 1/3`
2. `TEMPORAL_HELPED`
   - `oracle_accuracy - current_accuracy >= 2/3`
3. `BINDING_HELPED`
   - `oracle_accuracy - deranged_accuracy >= 4/9`
4. `BINDING_HARMED`
   - `deranged_accuracy - oracle_accuracy >= 4/9`
5. `ALL_EXPERTS_FAIL`
   - all three accuracies equal 0

These are descriptive correctness archetypes, not latent ground-truth routes.

Frozen ranking margins:

- `STATE_SUFFICIENT`: `current_accuracy`
- `TEMPORAL_HELPED`: `oracle_accuracy - current_accuracy`
- `BINDING_HELPED`: `oracle_accuracy - deranged_accuracy`
- `BINDING_HARMED`: `deranged_accuracy - oracle_accuracy`
- `ALL_EXPERTS_FAIL`: constant 0

## 5. Deterministic selection

For each archetype:

1. sort by the defining margin descending;
2. then by `qualification_id` ascending;
3. retain the first 5 cases;
4. do not replace a selected case because its image is visually unclear or its
   narrative is inconvenient.

If fewer than 5 cases qualify, retain all and report the support shortage.
Overlap between archetypes is retained and disclosed.

## 6. Case panel

For each selected case, report:

- anonymous `qualification_id`;
- anatomy and frozen progression label;
- prior/current de-identified ROI crops with identical display scaling;
- pair label composition, BII stratum, and actual semantic-corruption rate;
- the three correctness summaries;
- seed/derangement prediction table;
- which frozen archetype rule selected it.

Images are for interpretation only. No case is excluded after viewing.

## 7. Case-study questions

- Is current-only success associated with obvious current-state severity?
- Does temporal help appear when prior/current appearance differs globally?
- Do binding-helped cases show heterogeneous regional directions?
- Do binding-harmed cases suggest representation noise, target mismatch, or
  estimator adaptation?
- Do all-expert-fail cases indicate a direction-encoding failure?

Answers must be phrased as hypotheses, not causal conclusions.

## 8. Output and stop rule

Required runtime outputs:

- `case_registry.json`
- `case_level_predictions.json`
- `case_panel_manifest.json`

Required repository report:

- `reports/R28_CASE_STUDY_AND_FAILURE_ANALYSIS.md`

The registry is immutable after generation. TIER design begins only after the
registry, support counts, and oracle routing headroom are written down.
