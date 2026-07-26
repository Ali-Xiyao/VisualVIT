# Archived Findings: R29 Case-Driven Contextual Transition Repair

## Inherited failures

- R26 universal binding effect: `+1.17 pp`, CI crosses zero.
- R27 high-BII binding effect: `-6.24 pp`, all seeds negative.
- R28 A1/A2 router effects: `-1.80 pp` and `-0.61 pp`.
- R28b B1/B2 effects: `-1.43 pp` and `-0.87 pp`.
- R28 case oracle headroom remains large at `+25.61 pp`, but it reads labels.

## Case-derived repair hypothesis

The next attempt should not optimize another router over the same expert
logits. The failure panels indicate the expert representations themselves are
underspecified:

- tiny edge ROIs lose surrounding change context;
- global disease change can dominate a local registered box;
- acquisition/device/position changes contaminate naive global deltas;
- first-correct route targets reward the cheap state shortcut.

R29 will test an expanded-ROI plus global-context transition representation
with explicit signed direction features and train-only survival controls.

## Hard boundary

No scientific result can be called new if it reuses the repeatedly inspected
170 R26-R28b patients as the outer evaluation cohort. A fresh zero-overlap
patient set is the first survival gate.

## Preliminary asset audit

- The repository contains SHA-pinned CheXTemporal gold annotations and its
  dataset card describes a much larger silver training corpus with report
  impressions and anatomy masks.
- The local CheXTemporal directory did not surface silver/report files in the
  first filesystem filter; exact inventory is still required.
- Local MIMIC metadata and split files exist under
  `H:\Xiyao_Wang\000_Public Dataset\mimic_cxr_other`.
- The first guessed Chest ImaGenome root did not exist; use the runner's exact
  pinned `CI_ROOT_DEFAULT` before concluding the asset is absent.
- Historical R24/R25 cohort and summary artifacts are present, enabling an
  explicit patient/DICOM overlap audit rather than relying on naming.

## Resolved local data surfaces

- The exact Chest ImaGenome root is present under
  `F:\VisualVIT_runtime\050_routeC\data\chest_imagenome\...`.
- It contains the full silver scene-graph package, split CSVs, processed report
  sentences, gold comparison/attribute files, and license/hash manifests.
- Raw MIMIC-CXR images and de-identified reports are both present locally under
  `H:\Xiyao_Wang\000_Public Dataset\mimic-cxr\mimic-cxr`.
- The official CheXTemporal dataset page states that silver annotations are
  CC-BY-NC 4.0, parent MIMIC images remain governed by PhysioNet terms, and
  individual clinical use/commercial use is out of scope.
- The official silver schema provides 282,214 finding-level pair rows with
  progression, anatomy, evidence, and optional anatomy masks. This is a viable
  training/development source if we restrict to locally authorized MIMIC rows
  and exclude every previously used patient.
- The local repository currently has only CheXTemporal gold parquet files, so
  silver annotations would need an official pinned download; MIMIC images and
  reports do not need to be downloaded again.

## Official silver registry

- Hugging Face repository metadata confirms the annotation license tag
  `cc-by-nc-4.0`, a May 2026 update, and that images are not redistributed.
- Dataset Viewer reports one train split for each config:
  - `silver_findings`: 282,214 rows;
  - `silver_sentences`: 695,929 rows;
  - `silver_studies`: 128,071 rows.
- R29 needs only `silver_findings` and possibly `silver_studies`; sentence rows
  and the full mask archive are not authorized until the minimal cohort audit
  proves they are necessary.
- The current Hub revision is the same SHA already pinned by the repository:
  `81fd9cdd9b1208d8f8bd39d7a914c9b72fed8d79`.
- Exact LFS pins:
  - `silver_findings.parquet`: 29,502,280 bytes, SHA-256
    `31237f859d940d6b03748c845ec7c1c791b1837ba6e46e88e69bca7f45e3c807`;
  - `silver_studies.parquet`: 28,072,434 bytes, SHA-256
    `b53e5a491850e5d839158847efcdae6ca840bef0070ed9598fd2021e0fc148a2`.
- Storage is not a blocker: E, F, and H each have more than 200 GB free.

## Fresh MIMIC silver support

- Silver MIMIC contains 79,476 finding rows from 8,497 patients.
- 79,464 rows / all 8,497 patients resolve both prior and current DICOM IDs in
  MIMIC metadata and both scene graphs in the local Chest ImaGenome archive.
- A deterministic 100-row probe verified all 200 referenced image files.
- Class support among complete rows is large:
  - Stable 33,115;
  - Worse 21,513;
  - Improved 13,518;
  - New 9,965;
  - Resolved 1,353.
- The known R24 MIMIC qualification cohort has zero patient overlap with the
  silver rows. The first R26 lookup used the wrong root leaf; the correct
  immutable cohort is under `r26_c1_oracle_binding\run_v1\cohort.json` and
  still needs an exact overlap check.
- Scene graphs provide 36 fixed anatomical boxes per image, including small
  costophrenic/hilar ROIs and broader lung/mediastinal/card cardiac regions.
  Silver anatomy phrases concentrate strongly in these regions, so expanded
  ROI context can be constructed without downloading the separate mask ZIP.

## Exact exclusion and compute boundary

- R25/R26 patients do overlap CheXTemporal silver, so a blanket “silver is
  fresh” assumption would have been wrong:
  - R26 overlap: 72 patients / 94 DICOMs;
  - R25 overlap: 78 patients / 99 DICOMs.
- After excluding the union of R24-MIMIC, R25, and R26 patients:
  - 8,419 fresh patients remain;
  - 78,877 finding rows remain;
  - 34,419 prior/current study pairs remain;
  - 45,989 unique images remain.
- Every class has ample patient support after exclusion; the smallest,
  Resolved, still has 1,125 patients.
- GPU 0 is currently effectively free (366 MiB display/system use), while GPU
  1 has an unrelated 11.4 GiB Python workload. R29 may use only GPU 0 and must
  not stop or compete with GPU 1.

## Human-gold availability boundary

- CheXTemporal gold has only 197 patients total: 77 CheXpert, 43 MIMIC, and 77
  ReXGradient.
- Prior formal work already consumed 70/77 CheXpert and 34/43 MIMIC patients.
  Only 7 CheXpert and 9 MIMIC patients remain untouched, which is far below a
  defensible confirmation sample.
- All 77 ReXGradient gold patients are untouched, but their parent images are
  not present locally and Resolved has only three rows.
- Therefore R29 can be a genuinely fresh, patient-disjoint silver-development
  experiment, but cannot honestly be labeled human-gold confirmatory evidence.
  A later external confirmation still requires new expert labels or a new
  licensed image source.

## Frozen R29 cohort

- Cohort freeze status: `PASS_R29_FRESH_COHORT_FREEZE`.
- Cohort SHA-256:
  `0a52d2c84c99c9c3cdc91063b801eb3c0d1304dfa454c16e55c86edbd2197d6e`.
- Active support:
  - train: 700 patients / 3,977 rows;
  - dev: 200 patients / 1,074 rows;
  - sealed test: 300 patients / 1,657 rows.
- Reserve remains sealed at 6,883 patients / 57,879 three-label rows.
- All partitions are patient-disjoint, prior-patient overlap is zero, and all
  6,708 active records have both local images.

## Pre-outcome case audit and repair hypothesis

- A label-free full-cohort scene-graph pass resolved all 6,708 active records.
- Exact target boxes are often small: median area is 18.24% of image area and
  the tenth percentile is 6.20%. This supports the R28 case-study diagnosis
  that exact local crops can remove clinically relevant surrounding context.
- Acquisition-view changes are uncommon (0.27%), so view transition is a
  useful nuisance feature but cannot plausibly explain most failures.
- 114 records (1.70%) have different available anatomy granularity across
  timepoints. Protocol v1.1 therefore freezes per-image anatomy resolution and
  a same-side parent/landmark fallback before any encoder or model outcome.
- Frozen repair hypothesis: a single context-transition representation that
  combines global, exact ROI, 1.5x ROI context, signed/absolute/product
  temporal interactions, and geometry will outperform post-hoc uniform fusion
  because it can condition direction on both local evidence and surrounding
  change instead of choosing among independently trained summaries.
- Protocol v1.1 SHA-256:
  `e2e1f00f2ba66dcf11fd8583e0818b87496a213f8db3877f41c0967403450be8`.
- Rebuilt cohort v1.1 preserves the exact cohort SHA-256
  `0a52d2c84c99c9c3cdc91063b801eb3c0d1304dfa454c16e55c86edbd2197d6e`;
  only the protocol/manifest pins changed.

## R29 formal stop and R30 selection

- R29 formal status is `STOP_R29_DEV_SURVIVAL`; the test remained sealed.
- Context minus uniform was -1.80 pp. Only seed 17 was positive; seeds 29 and
  43 were negative.
- Base global/local heads reached near-perfect train accuracy but weak dev
  macro F1, establishing overfit as the dominant actionable failure.
- Retrospective R29 train/dev capacity audit selected a standardized,
  patient/class-weighted logistic head with `C=0.001`.
- With independent per-scale 128-dimensional projections, the selected repair
  scored 0.5331, 0.5210, and 0.5283 across seeds, while train accuracy stayed
  near 0.53. No R29 test row was used.
- R30 will use only R29 sealed-reserve patients under a new protocol and
  patient split.

## R30 formal stop and R31 selection

- R30 passed development survival at +2.30 pp with all three seed directions
  positive, then failed the one-shot test at +0.77 pp with CI
  [-1.61, +3.18] pp.
- The R30 test is now development evidence for R31; its formal NO-GO remains
  immutable.
- Regularized and uniform majorities agree on only 61.46% of observations;
  their selection oracle is 0.6781 macro F1.
- Among five disclosed label-free discrete rules, using regularized prediction
  only under three-seed unanimity and otherwise falling back to uniform
  majority reached 0.5276.
- Retrospective R30 case-study contrast versus pooled uniform is +3.15 pp with
  CI [+0.91, +5.34] pp.
- R31 will validate this exact consensus rule on R30 sealed-reserve patients.

## R31 reproduced scientific GO

- R31 dev survival passed at +4.53 pp versus pooled uniform; all three
  per-uniform-seed directions were positive.
- The one-shot 500-patient test scored 0.5033 for confidence consensus versus
  0.4728 for uniform, a +3.05 pp gain.
- Patient-bootstrap 95% CI is [+0.42, +5.60] pp with 10,000/10,000 valid
  replicates.
- Test per-seed directions are +4.26, +2.90, and +2.00 pp.
- A fresh process reproduced the exact dev predictions, dev gate, test
  predictions, test result, representation manifests, and report hashes.
- Final status: `PASS_R31_SCIENTIFIC_GO_REPRODUCED`.
- Claim boundary: this is a fresh-silver development GO for label-free
  confidence consensus. R26 human-gold `STOP_C1` remains unchanged.
