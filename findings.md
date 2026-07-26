# Findings: TIER-CXR-VLM R32-R36

## Inherited evidence

- R31 consensus macro F1 was 0.5033 versus 0.4728 uniform, a +3.05 pp
  improvement with 95% CI [+0.42, +5.60] pp and all three seed directions
  positive.
- This is fresh-silver development evidence only. It does not overturn R26
  human-gold `STOP_C1`.
- The proposal reports 2,383 patients remaining in the R31 sealed reserve and
  allocates 1,600 Train, 300 Dev/Calibration, and 483 Sealed VLM Test patients.
- The R31 cohort file contains 19,943 reserve rows but only the persistent
  three labels because R29-R31 deliberately filtered to Stable/Improved/Worse.
  Rejoining the same 2,383 patient IDs to the pinned official silver findings
  yields 23,161 rows with all five labels: Stable 9,797, Worse 6,095,
  Improved 4,051, New 2,861, and Resolved 357. Thus the R32 master cohort can
  honor the proposal without introducing new patients.
- The ID-only gold audit found 26 of the 2,383 reserve patients in the
  500-patient Chest ImaGenome gold registry; official CheXTemporal gold has
  zero overlap. The proposal's literal 1,600/300/483 allocation is therefore
  incompatible with its stronger gold-exclusion rule. R32 v1.1 retains the
  2,383-person authority set, quarantines 26, and freezes 1,574/300/483 before
  any model execution.

## Execution boundaries

- R33 may use Train+Dev nested patient-disjoint OOF predictions only.
- The 483-patient sealed test must remain unread until a fully frozen R34.
- Gold IDs may be inventoried and excluded, but gold outcomes and metrics may
  not be read during R32-R34.
- The 64-token physical layout, projector budget, prompt, and lack of pixel
  bypass are fairness constraints, not optional reporting fields.
- GPU 0 is currently available; GPU 1 has an unrelated active process and must
  not be disturbed or used.
- Local primary assets are present:
  `H:\Xiyao_Wang\001_models\biomedclip` and
  `H:\Xiyao_Wang\001_models\Qwen3-VL-4B-Instruct`.

## Provenance simplification

The user explicitly requested a simpler workflow without repeated hash
recomputation. One-time identifiers remain useful at artifact freeze, but
iteration will use structural checks rather than hashing unchanged inputs.

## R32 verdict

- R32 is `GO_R32_READY_R33`.
- The corrected active cohort is 1,574/300/483 after quarantining 26 of the
  2,383 master patients; all five support and overlap gates pass.
- Train/dev patch cache contains 10,562 images in 42 shards (3.20 GB), with no
  sealed-test image access.
- Exact-64 frozen Qwen verification passes. Real-model FP32
  serial/vectorized difference is `2.96e-5` with identical argmax.
- Full pytest is 559 passed plus one registered xfail. R32 scoped lint and
  compile pass.
- R35 remains blocked: only 16 untouched image-ready gold patients are local,
  with conservative MDE 35.02 pp.

## R33 verdict

- R33 is `STOP_R33_TOKEN_SURVIVAL`.
- On 15,698 persistent-label train/dev rows from 1,874 patients, nested-OOF P6
  macro F1 is 0.4516 versus 0.4583 for P3: -0.669 pp, 95% patient-bootstrap CI
  [-1.443, +0.109] pp.
- Seed deltas are +0.405, -0.734, and -1.665 pp; only one of three is positive.
- Prior shuffle does not attenuate the routed delta: shuffled P6-P3 is +0.422
  pp, whereas the registered maximum was -1.169 pp.
- Hard consensus (46.91% rich coverage, F1 0.4516) is nearly identical to the
  matched-random route (47.41%, F1 0.4514); net corrected is negative.
- The P0 summary is only a query/control proxy because type 0 also contains
  prior/current global image controls. This makes the literal query-only
  control invalid, but it cannot rescue the independently failed primary,
  confidence-interval, seed, and prior-shuffle gates.
- The 483-patient R34 sealed test and all gold outcomes remain unread.
