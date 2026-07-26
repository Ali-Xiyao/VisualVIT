# R25.1 Pair/Entity Manifest Qualification

Date: 2026-07-26

Status: `PASS_R25_1_MANIFEST_SPLIT`

Evidence class: `NON_CONFIRMATORY_MANIFEST_QUALIFICATION`

## Result

Fresh local construction from the qualified Chest ImaGenome/MIMIC inputs
produced two distinct units:

| Manifest | Rows | Meaning |
|---|---:|---|
| Pair manifest | 189 | Independent patient-level temporal matching units |
| Entity manifest | 793 | Anatomy/label-specific progression targets for future R26 |

All 189 pairs belong to distinct patients in this cohort.

Entity target distribution:

| Target | Entities |
|---|---:|
| Stable | 371 |
| Improved | 160 |
| Worse | 262 |

## Artifact hashes

Local artifact root:
`artifacts/r25_1_semantic_repair/manifests`

| Artifact | SHA-256 |
|---|---|
| `pair_manifest.json` | `d89efc92d50058e25a40ea47259a0975a492e69455e33ba54d8f48e9fe9ed585` |
| `entity_manifest.json` | `1e0048fe7149df910f2b36d3657c7fc38225a50fc76996d121c7aefc8333fbf3` |
| `cohort_audit.json` | `5fc4cfe0cbad32976839de5ace4f6085cab351c7ce41f4aa7c729c2b8766bdbb` |

## Interpretation boundary

The 189 pair rows are the independent units for matcher qualification. The
793 entity rows carry Stable/Improved/Worse targets for an R26 classifier;
they are not 793 independent matching experiments.

No progression model was run. These manifests do not establish a progression
macro F1, `delta_bind`, learned-matcher result, frozen-VLM result, or clinical
claim.

## Anatomy constraint audit

The R25 runner currently emits zero for every `prior_anatomy` and
`current_anatomy` id. Therefore `anatomy_constrained=True` is configured but
inactive: its compatibility mask removes no candidate edges. R25.1 now records
this explicitly in the matcher mechanics output. Visual+geometry results must
not be attributed to an active anatomy constraint.
