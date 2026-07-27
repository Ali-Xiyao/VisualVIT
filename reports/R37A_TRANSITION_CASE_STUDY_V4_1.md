# R37A Transition Case Study: Ruleset v4.1

Date: 2026-07-27

Ruleset: `r37-report-transition-v4.1`

Protected outcomes read: no

CheXTemporal silver used: no

## Result

The deterministic 200-row case sheet passes the protocol's provisional
direction-quality thresholds under a structured Codex review:

| Class | Correct | Total | Accuracy |
|---|---:|---:|---:|
| Stable | 38 | 40 | 95.0% |
| Improved | 40 | 40 | 100.0% |
| Worse | 39 | 40 | 97.5% |
| New | 37 | 40 | 92.5% |
| Resolved | 40 | 40 | 100.0% |
| **Overall** | **194** | **200** | **97.0%** |

This exceeds the frozen >=90% overall and >=85% per-class thresholds. It is
not a radiologist or independent-human adjudication, so
`formal_training_unlocked` remains false until that review is supplied.

## Data support after v4.1

| Partition | Eligible transition pairs |
|---|---:|
| Pretrain | 33,621 |
| Internal calibration | 3,770 |

Dynamic unique-patient support:

| Class | Pretrain | Internal calibration |
|---|---:|---:|
| Improved | 4,287 | 468 |
| New | 3,113 | 357 |
| Resolved | 1,520 | 164 |
| Worse | 4,823 | 536 |

All frozen count-support gates pass.

## Iteration evidence

- v1 failed due to broad cue-to-finding scope, negated `new`, indications,
  lateral size comparisons, and partial-resolution errors.
- v2 fixed section/clause and negation scope but still admitted uncertain or
  alternative directions.
- v3 rejected uncertainty and split neighboring findings; source review then
  found indented history, soft-line-wrap, and technique-artifact failures.
- v4/v4.1 froze standard section parsing, sentence-level uncertainty,
  technique-artifact rejection, and soft-wrap normalization.

No protected outcome or downstream metric was used to choose these rules.

## Residual errors in the v4.1 sheet

- two Stable rows attached a stability cue to a neighboring or normal
  cardiomediastinal finding;
- one Worse row attached worsening atelectasis to an adjacent effusion;
- one New row assigned `new` to pneumonia in an explicitly ambiguous
  pneumonia-versus-atelectasis statement;
- one New row represented a low-volume technical pseudo-opacity;
- one New row missed `No substantial ... has developed` negation.

These errors are retained as an honest estimated-noise boundary. The ruleset
is frozen rather than expanded against the same case sheet.

## Artifacts

- Candidate manifests:
  `H:\VisualVIT_runtime\050_routeD\r37_prta_cxr\r37a_transitions_v4_1`
- Deterministic review sheet:
  `r37_transition_case_study.csv`
- Audit:
  `r37_transition_audit.json`

## Verdict

`PASS_R37A_TRANSITION_SUPPORT_AND_CODEX_CASE_STUDY`

Formal human/radiologist QA remains required before R37B training is labeled
formal.
