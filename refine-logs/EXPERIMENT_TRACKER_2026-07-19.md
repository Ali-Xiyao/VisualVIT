# Experiment Tracker: CAPES-CI v1

**Date**: 2026-07-19  
**Authority**: `refine-logs/EXPERIMENT_PLAN.md`  
**Formal test**: SEALED  
**Parent allocation**: `4161 / tpami / gpu01` — KEEP RUNNING

| Run ID | Evidence class | Task | Status | Decision / artifact |
|---|---|---|---|---|
| P000 | NON_CONFIRMATORY_PROXY | 2026-07-13 component smoke | COMPLETE | 21 tests and proxy report; no formal claim |
| P001 | INVALID_FORMAL | MIMIC report-derived pairing proxy | FAIL_CONVERGENCE_GATE | raw +4.29±10.31 pp invalid; seed43 nonconverged |
| M000 | METHODOLOGY_REVIEW | 2024–2026 novelty/venue audit | COMPLETE | `reports/methodology_novelty_review_2026-07-19.md` |
| H000 | INFRASTRUCTURE | live allocation 4161 audit | PASS | RUNNING; gpu01 A800 80GB; 4 CPU/64 GiB; parent retained |
| S000 | SURVIVAL | historical test regression | PASS | 21/21 on 2026-07-19 |
| S010 | SURVIVAL | schema closure | PASS | 76-test unified suite; optional metadata and exact mass validated |
| S020 | SURVIVAL | soft/null transport math | PASS | finite gradient, mass, masks, permutation tests |
| S021 | SURVIVAL | globally optimal hardening | PASS | contained Hungarian matches enumerated optimum |
| S030 | SURVIVAL | deterministic global allocator | PASS | N through >100, stable IDs, top27+overflow, exact source mass |
| S040 | SURVIVAL | projector + exact placeholder adapter unit | PASS | 64 replacement, neutral/mask/position, frozen toy LM, no pixels |
| S050 | SURVIVAL | integrated synthetic five-label chain | PASS | 30 balanced original/reversed cases; 100%; two interventions; exact two-process SHA reproduction |
| S051 | SURVIVAL | current adapter-contract synthetic refresh | PASS | seed17; enforced no-cache/full-logits toy LM; 100%; exact two-process state/metric reproduction |
| S060 | SURVIVAL | server CPU/GPU regression | PASS | 35/35 source hashes; CPU 75 pass + 1 CUDA skip; A800 GPU 76/76 pass; only 4161.batch remains |
| S070 | SURVIVAL | frozen Qwen relation-token likelihood | PASS | Qwen3-VL-4B exact-64/no-pixel/frozen; finite 5-label scores; intervention delta 0.09917; exact two-process field reproduction |
| S075 | ENGINEERING_CALIBRATION | registered three-seed synthetic anchor | FAIL_MECHANISM_GATE | technical audits pass; mean Delta_bind +2.6349 pp; seed29 negative; Recovery unqualified/low; no scaling |
| S076 | ENGINEERING_REPRODUCTION | independent-process anchor reproduction | PASS | every registered non-runtime field exact; mismatch count 0; canonical SHA `a8117be5...1079` |
| S077 | FAILURE_DIAGNOSIS | B4 identifiability/training/intervention audit | COMPLETE | bypass + decoder-seed confound + A1/A2 mismatch identified; v2 protocol red-teamed and revised |
| S078 | POST_FAILURE_DIAGNOSTIC | fixed-decoder/competence/bypass ladder | IN_PROGRESS | D1-D3 implementation; one factor per registered run; original S075 immutable |
| D010 | DATA_QUALIFICATION | official asset/license manifest | PENDING | no download until source/DUA class fixed |
| D020 | DATA_QUALIFICATION | cross-source lineage and split seal | LOCKED | requires qualified annotations |
| S080 | TRAIN_DEV_PILOT | real gold B4/learned pilot | LOCKED | requires D010/D020 and S070 |
| F100 | FORMAL_MAIN | multi-seed main table | LOCKED | requires signed pilot power/protocol |
| F200 | FORMAL_ABLATION | mandatory A1–A10 | LOCKED | requires F100 protocol freeze |
| F300 | FORMAL_EXTERNAL | uncontaminated replication | LOCKED | identity/lineage fixed before test reveal |

## Current verdict

`GO_CAPES_CI_V1_S010_S070_SURVIVAL + FAIL_S075_MECHANISM_GATE + NO_GO_REAL_PILOT_OR_FORMAL_SCALING`

Formal results, main claim, ablation claim and paper-ready status remain false until their locked rows have fresh PASS evidence.
