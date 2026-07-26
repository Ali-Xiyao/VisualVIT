# R29 Fresh-Silver Contextual Transition Repair Protocol v1.1

Date frozen: 2026-07-26

Evidence class: `NON_CONFIRMATORY_FRESH_SILVER_DEVELOPMENT`

## Motivation

R28/R28b established reproducible negative results for routers over frozen
state/global/local experts. Case panels implicated representation failure:
small edge ROIs lack context, global change can dominate a local box, and
acquisition/device changes contaminate naive deltas.

R29 tests a representation repair, not another threshold or router search.
No R29 model result was viewed before this protocol was frozen.

## Data authority and pins

- CheXTemporal revision:
  `81fd9cdd9b1208d8f8bd39d7a914c9b72fed8d79`.
- `silver_findings.parquet` SHA-256:
  `31237f859d940d6b03748c845ec7c1c791b1837ba6e46e88e69bca7f45e3c807`.
- `silver_studies.parquet` SHA-256:
  `b53e5a491850e5d839158847efcdae6ca840bef0070ed9598fd2021e0fc148a2`.
- Source restriction: `dataset == "mimic"`.
- Parent MIMIC images/reports remain under their PhysioNet terms. CheXTemporal
  annotations are CC-BY-NC 4.0. R29 is noncommercial research only.
- Exclude the union of every R24-MIMIC, R25, and R26 patient before partition.
- Primary labels inherit R28: `Stable`, `Improved`, `Worse`.
- Require both DICOM IDs in the pinned MIMIC metadata and both scene graphs in
  the local Chest ImaGenome archive.

## Frozen patient partition

Sort eligible patients by
`SHA256("r29-patient-v1|" + patient_id)`, then assign:

- first 700: `train`;
- next 200: `dev`;
- next 300: `test`;
- all remaining: `sealed_reserve`.

Within each active patient, sort rows by SHA-256 of patient, prior/current
study, finding token, and anatomy; retain at most 12 rows. Labels are not used
in row ordering. Test predictions/metrics remain sealed until the development
survival gate passes.

## Anatomy and context

Only image-derived Chest ImaGenome object boxes are used. Report-derived scene
graph attributes/relationships are forbidden model inputs.

Anatomy phrases are split on commas and mapped independently on each
timepoint by a frozen alias table:

- `upper/mid/lower lung` -> corresponding `lung zone`;
- `apex` -> `apical zone`;
- `hilum/hilar` -> `hilar structures`;
- `heart` -> `cardiac silhouette`;
- unspecified/bilateral lung or pleural phrases -> left/right lung;
- when a requested fine pulmonary region is absent on one timepoint, use the
  closest available same-side pulmonary parent/landmark in the frozen order
  `lung`, lower/mid/upper lung zone, costophrenic angle, hemidiaphragm, apical
  zone, hilar structures;
- otherwise unmatched phrases fall back to available left/right lungs, then
  registered thoracic boxes, and are audited.

This v1.1 operational clarification was frozen after a label-free full-cohort
scene-graph dry-run found asymmetric box granularity and before any encoder
features, model fits, dev predictions, or test predictions were produced.

For each prior/current image:

1. global crop: full image;
2. exact crop: union of mapped anatomy boxes;
3. contextual crop: exact union expanded by 1.5 around its center and clipped
   to 224-space.

## Systems

All systems use the same frozen BiomedCLIP ViT-B encoder, finding/anatomy query
fields, patient partitions, seeds, optimizer budget, and three-class endpoint.

- `state`: current global evidence.
- `global_transition`: prior/current global evidence with signed, absolute,
  and product interactions.
- `local_transition`: exact prior/current anatomy crops with the same
  interactions.
- `uniform_fusion`: mean of the three expert logits.
- `context_transition`: global + exact + expanded-context prior/current
  evidence, signed/absolute/product interactions, and geometry/view change.

Each representation is projected by a fixed signed 256-dimensional projection.
Every system uses the same LayerNorm + 128-hidden GELU MLP head. Training seeds
are 17, 29, and 43.

## Development survival gate

Before any test prediction:

- contextual minus uniform dev macro F1 >= +1.00 pp;
- at least two of three seed directions positive;
- all fits finite and train/dev patients disjoint;
- shuffled-label holdout below 0.45;
- no forbidden report/evidence/reasoning/progression field in model inputs.

If the gate fails, test remains sealed and R29 stops.

## Test scientific GO

After survival, refit each system on train+dev and reveal test once. GO requires:

- patient-balanced macro F1(context) - macro F1(uniform) >= +2.00 pp;
- patient-bootstrap 95% CI lower bound > 0;
- all three seed directions positive;
- context no more than 1.00 pp below the strongest single expert;
- valid bootstrap, complete predictions, zero patient overlap, finite fits;
- fresh-process reproduction.

Thresholds, seeds, partition, row cap, context expansion, and representations
may not change after dev or test results.

## Stop and continuation

- A test GO supports only fresh-silver development and unlocks acquisition of
  new human labels; it does not reverse R26 by itself.
- A dev or test NO-GO closes R29. Another attempt must use the sealed reserve
  under a newly frozen protocol and a materially different representation.
- VLM/DIVE/RAD-DINO/scale-up remain locked.
