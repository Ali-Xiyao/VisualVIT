# R28 TIER MVP Result

Date: 2026-07-26

Evidence class: `NON_CONFIRMATORY_R28_DEVELOPMENT`

## Boundary

R28 uses the same development cohort already examined in R26/R27 and cannot be a confirmatory or clinical result. BII, case archetype, labels, and expert correctness were forbidden router inputs.

## Representation and sanity

- Entities: 774
- Projection dimension: 128
- Router base descriptors: 12
- Sanity gate: PASS

## Attempts

| Attempt | TIER F1 | Uniform F1 | Delta | 95% CI | Engineering | Scientific |
|---|---:|---:|---:|---|---|---|
| tier_a1 | 0.4188 | 0.4368 | -1.80 pp | [-6.07, +2.49] pp | PASS | NO-GO |
| tier_a2 | 0.4307 | 0.4368 | -0.61 pp | [-4.36, +3.35] pp | PASS | NO-GO |

## Final interpretation

- Best admissible attempt: `tier_a2`
- Engineering pipeline: PASS
- Scientific gate: NO-GO
- Fresh-process reproduction: PENDING

Engineering completion does not override a scientific NO-GO. If A2 fails, the next permitted direction is a separately reviewed report-supervised transition representation; VLM/DIVE/scale-up remain locked.
