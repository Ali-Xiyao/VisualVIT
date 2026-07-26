# R25.1 Chest ImaGenome Matching Qualification Protocol v1

Status: `FROZEN_BEFORE_EXECUTION`

Date: 2026-07-26

Historical baseline: commit `dd9c242`

Semantic-repair implementation: branch `r25.1-semantic-repair`

## 1. Authority and purpose

This protocol supersedes the metric interpretation and gate names in
`2026-07-25-chest-imagenome-real-data-protocol-v1.md`. Dataset selection,
input hashes, cohort construction, coordinate verification, encoder revision,
three matcher variants, deterministic seeds, and fresh-process reproduction
requirements are inherited unchanged unless this document explicitly
overrides them.

The sole question is:

> Can the fixed visual-only, geometry-only, and visual+geometry matchers
> reproducibly recover case-local cross-temporal persistent correspondences?

This protocol does not predict or evaluate Stable/Improved/Worse. Those labels
are carried only for cohort audit and future R26 use.

## 2. Frozen units

- Matching unit: one patient / prior DICOM / current DICOM pair.
- Expected patients: 189.
- Expected pairs: 189.
- Entity annotations carried inside pairs: 793.
- Entity label audit: Stable 371 / Improved 160 / Worse 262.
- Pair and entity manifests must remain separate.

The 793 entity rows must not be treated as 793 independent matching trials.

## 3. Frozen inputs

All Chest ImaGenome, MIMIC-CXR, BiomedCLIP, R24 synthetic prerequisite, and
R24 real-v3 prerequisite hashes remain exactly those pinned in the inherited
R25 protocol and runner. Parent images and annotations remain local under
their credentialed-data boundary.

No new encoder, dataset, report input, RAD-DINO checkpoint, or learned matcher
is authorized.

## 4. Matcher systems

The registered systems are:

1. `visual_only`
2. `geometry_only`
3. `visual_geometry_equal`

The implementation is a fixed multi-view cosine utility with global Hungarian
assignment. It is not a trained or learned matcher.

The runner currently emits anatomy id zero for every endpoint. Therefore
`anatomy_constrained=True` is configured but inactive. The execution must
report:

- whether the constraint is configured;
- whether it removes any candidate on the cohort;
- valid candidate count;
- removed candidate count.

No improvement may be attributed to anatomy constraints when
`active_on_cohort=false`.

## 5. Metric namespaces

### 5.1 Matching evaluation

Allowed metrics:

- `persistent_edge_precision`
- `persistent_edge_recall`
- `persistent_edge_f1`
- `exact_row_recovery`
- `matching_event_macro_f1`
- `delta_match`

The event labels for `matching_event_macro_f1` are persistent/death/birth.
Because this cohort is persistent-only, that macro metric is descriptive and
is not a survival threshold.

### 5.2 Progression evaluation

The summary must contain:

```json
{
  "status": "NOT_EVALUATED",
  "labels": ["Stable", "Improved", "Worse"]
}
```

It must not contain `progression_macro_f1`, `delta_bind`, progression
predictions, or a progression conclusion.

## 6. Gates

Gates are evaluated in this order, with first-stop semantics:

1. `Q0_ASSET_LINEAGE`
   - all registered input hashes and R24 prerequisites match exactly.
2. `Q1_COHORT_GEOMETRY`
   - 189 patients / 189 pairs / 793 entity annotations;
   - minimum 10 distinct patients per carried progression label;
   - nonempty qualified image ledger.
3. `Q2_FEATURE_INTEGRITY`
   - exact-zero repeat extraction difference;
   - every crop feature has a nonempty hash.
4. `Q3_MATCHPLAN_MECHANICS`
   - hard plans satisfy registered mass/support rules;
   - global objective is never below the greedy plan on identical utilities.
5. `Q4_MATCHING_SIGNAL`
   - primary `persistent_edge_f1 >= 0.50`;
   - patient-bootstrap lower 95% bound of correct-reference minus deranged
     persistent-edge F1 is greater than zero.
6. `Q5_B4_STRUCTURE`
   - zero-fixed-point derangement exists where required;
   - feature, null-set, allocation, token shape/type/order, initialization,
     and optimizer contracts are identical;
   - only assignment and relation values differ.
7. `Q6_FRESH_PROCESS_REPRODUCTION`
   - two independently launched processes produce identical registered
     cohort, feature-ledger, prediction, aggregate, gate, and mechanics hashes.
8. `Q7_MATCHING_POWER_ESTIMATE`
   - `delta_match` lower 95% bound is greater than zero;
   - at least 100 unique patients contribute to the registered comparison.

Q4/Q7 are matching gates. Passing them does not unlock a progression claim.

## 7. Execution contract

- Device: GPU1 (`cuda:1`) unless fresh inspection shows it is occupied.
- Processes: `a`, then `b`, launched sequentially.
- Batch size: 64.
- Bootstrap seed: 20260725.
- Derangement seed: 20260725.
- Bootstrap replicates: 10,000.
- Deterministic PyTorch algorithms required.
- Each output root must not exist before launch.
- Process B must not reuse process A's output directory or process identity.

Process-level success is
`AWAITING_FRESH_PROCESS_REPRODUCTION`. Terminal R25.1 success requires the
independent reproduction verifier to certify both processes.

## 8. Required outputs

Per process:

- cohort and image ledger;
- crop feature cache and feature ledger;
- per-row matching outputs;
- aggregate matching metrics and bootstrap intervals;
- anatomy constraint audit;
- B4 structural audit;
- gate results and first failed gate;
- source hashes and runtime provenance;
- explicit progression `NOT_EVALUATED` namespace.

Cross-process:

- reproduction certificate;
- public identifier-free result summary;
- three-variant table;
- exact hashes for all public aggregate evidence.

## 9. Stop rules

- If GPU1 becomes occupied by unrelated work, do not compete; stop before
  model loading.
- If Q0-Q3 fails, do not interpret Q4-Q7.
- If Q4 or Q7 fails, record the matching result and do not start R26.
- Do not start RAD-DINO, a learned matcher, frozen VLM, DIVE, or Slurm work.
- R26 C1 is unlocked only after Q6 terminal reproduction is green and its
  own frozen protocol has passed pre-run audit.

