# R33A Attempt E2: Projection-Matched Coherence Adapter

Date frozen: 2026-07-27

Evidence class: `EXPLORATORY_TRAIN_ONLY_NESTED_OOF`

## Reason for amendment

Attempt E changed the random-projection seed family for every token block while
adding a 64-wide coherence relation. Its P3 robust reference consequently
drifted from Attempt D 0.49363 to 0.48668. The positive routed delta and passed
prior-shuffle control are useful mechanism evidence, but the primary comparison
is confounded.

## Single correction

- Query, state, global, and local projections use the exact Attempt D seeds.
- The first 3840 rows of the relation projection use the exact Attempt D
  relation matrix.
- Append only 64 new rows for the coherence embedding. Their variance is
  adjusted to match the pre-registered coherence scale.
- Preserve every other Attempt E pretext, feature, reader, fold, seed, route,
  and gate setting.

This amendment is frozen before E2 features or progression results exist.
Attempt E artifacts remain immutable.
