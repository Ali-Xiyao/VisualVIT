# Progress: R29 Case-Driven Contextual Transition Repair

## 2026-07-26 — Authority reset

- User explicitly requested continued case-study-driven attempts after R28b
  scientific NO-GO.
- Created branch `codex/r29-case-driven-transition-repair`.
- Archived the complete R28 active planning bundle under
  `history/2026-07-26-r28-closure/`.
- Defined R29 as a representation repair on a fresh zero-overlap cohort, not a
  threshold/seed/router retune on the exhausted R28 development patients.
- Next action is a read-only asset, report-source, overlap, and legality audit.
- Began the read-only inventory. Confirmed local MIMIC metadata/split and
  historical R24/R25 cohort artifacts; CheXTemporal silver/report availability
  and the exact Chest ImaGenome root remain to be resolved.
- Resolved the exact Chest ImaGenome and MIMIC roots. Full local reports,
  images, silver scene graphs, and split tables exist.
- Verified from the official CheXTemporal source that silver annotations are
  available for noncommercial research under CC-BY-NC 4.0 while parent MIMIC
  terms continue to apply.
- Queried the official Dataset Viewer API and confirmed exact silver config
  row counts and parquet availability. No download has been performed yet.
- Resolved the exact pinned Hub revision, LFS SHA-256 values, and file sizes
  for the two minimal silver parquet inputs. Storage feasibility passed.
- First download command failed at PowerShell parse time before any network or
  file action; corrected the output collection structure for the next attempt.
- Downloaded both minimal silver parquet files and verified both exact hashes.
- The first full-support audit was stopped because 150k+ individual H-drive
  path probes were I/O-bound. The next audit will use an indexed image
  inventory rather than repeating per-row filesystem calls.
- Replaced per-row filesystem probing with MIMIC-metadata and scene-archive
  indexes plus a deterministic 100-row real-file probe.
- Established 79,464 complete fresh-source silver rows across all five
  progression labels; R24 MIMIC overlap is zero.
- Located the correct R26 cohort leaf for the remaining exact overlap audit.
- Completed exact overlap: R25/R26 do overlap silver, so their full patient
  union is now a mandatory exclusion.
- After exclusion, 8,419 patients and 78,877 rows remain with strong five-class
  support.
- Inspected shared GPU state: GPU 0 is available; GPU 1 is owned by an
  unrelated Python workload and remains untouched.
- Audited remaining CheXTemporal human-gold patients. Only 16 locally usable
  CheXpert/MIMIC patients are untouched, so human-gold confirmation is not
  supportable in R29; the evidence class must remain fresh silver development.
- Froze and executed the R29 cohort builder. The active 1,200-patient cohort is
  zero-overlap and complete; 6,883 patients remain sealed for later protocols.
- A full-cohort scene-graph dry-run exposed time-asymmetric anatomy coverage;
  repaired the label-free mapper to resolve each image independently and audit
  cross-time parent-region fallbacks.
- Froze the pre-outcome clarification as protocol v1.1, rebuilt the cohort
  manifest, and proved the cohort JSON hash remained identical.
- Focused implementation suite passes 7/7; changed Python sources pass Ruff
  and compilation. The next action is the formal development survival run.
- R29 formal dev survival failed at -1.80 pp versus uniform; the test remained
  sealed and empty as registered.
- Completed a disclosed R29 train/dev failure audit. Strong regularization and
  separate scale projections removed memorization and beat uniform for all
  three projection seeds.
- Froze the audit narrative in `reports/R29_FAILURE_CASE_STUDY.md`; next is a
  new R30 cohort drawn only from R29 sealed-reserve patients.
- The first R30 builder reached artifact creation but failed at its final
  console print because of a nonexistent helper. Preserved that runtime,
  corrected the print, and reserved a fresh `cohort_v1_1` formal root.
- The first R30 formal run completed feature/model computation but stopped
  while serializing a NumPy boolean in `dev_gate.json`. Partial predictions
  were not inspected. Pinned the completed feature cache and prepared a
  model-identical recovery run to a fresh output root.
- R30 recovery proved dev survival but closed `STOP_R30_TEST_NO_GO`: +0.77 pp
  on test with CI crossing zero.
- Verified identical dev-prediction hashes between the pre-serialization
  failure and recovery.
- Completed a disclosed five-rule R30 disagreement study and froze a
  three-seed confidence-consensus controller for independent R31 validation.
- Built a zero-overlap R31 cohort from R30 reserve: 1,200 train, 300 dev, 500
  sealed test, with 2,383 patients still reserved.
- R31 passed dev and one-shot test: +3.05 pp, CI [+0.42, +5.60], all three
  seed directions positive.
- Fresh-process reproduction produced exact scientific artifact hashes.
- Final verifier status is `PASS_R31_SCIENTIFIC_GO_REPRODUCED`; updated the
  active CAPES proposal while preserving R26 `STOP_C1`.
- Final repository verification: 545 passed, 1 expected xfail; changed-source
  Ruff, compileall, and `git diff --check` all pass.
