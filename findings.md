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

## R33A starting hypotheses

- R33A is a new exploratory rescue; it does not erase or relabel the registered
  R33 STOP.
- Case-study iteration is restricted to the 1,574-patient train partition.
  The 300-patient dev split is withheld from case-level inspection and reserved
  for one frozen-candidate confirmation.
- The strongest implementation-level hypothesis is that R33 froze a randomly
  initialized `HierarchicalTemporalTokenBuilder`. BiomedCLIP inputs were
  pretrained, but query attention, slot projections, relation projection, and
  output normalization were never outcome-free pretrained or train-fitted.
  A random frozen representation is not a faithful test of the proposal's
  learned temporal token mechanism.
- The hard route target was agreement among three label probes, not predicted
  benefit of rich over robust. Agreement can select high-confidence cases
  without identifying cases where rich evidence is helpful, consistent with
  hard-route performance matching the coverage-matched random route.
- P0 is not literal query-only because type 0 pools query with prior/current
  global image controls. R33A must retain a separate pure-query feature before
  pooling.
- Any repair must be evaluated against the same robust/rich capacity and
  trained inside patient-disjoint folds; labels or fitted logits may not enter
  the visual tokens.

## R33 implementation-to-proposal gap

- The proposal explicitly allows training tier resamplers, a soft relation
  adapter, a common-width token MLP, the visual projector, and auxiliary
  probes. R33 trained only the final linear probes.
- `prepare_r33_token_features.py` instantiated three
  `HierarchicalTemporalTokenBuilder` modules from random seeds and immediately
  froze them. Therefore query attention, global/local slot projections,
  relation slots, and output normalization were random frozen transforms.
- The cached pretrained BiomedCLIP patch features were additionally compressed
  from 768 to 64 dimensions with one fixed random orthogonal projection. No
  learned or pretrained temporal bridge adapted those features to the
  progression objective.
- The proposal requested three different frozen visual-subspace perturbations.
  R33 operationalized these mostly as three independently random token
  builders, so consensus measured agreement across random bridges rather than
  stability of a competent learned bridge.
- This is a concrete underfitting/construct-validity failure, not merely an
  unlucky seed. R33 remains a valid negative result for that implementation,
  but it is not a decisive test of the proposal's allowed trainable token
  bridge.
- R28 provides a warning for the new router: large label-reading oracle
  headroom can coexist with a failed deployable router. R33A must first prove
  representation survival and then prove that a label-free route enriches for
  rich-helped rather than rich-harmed cases.

## What R31 actually transferred

- R31's successful confidence-consensus did not consume R33's random exact-64
  token builder. It reused the trained R29/R30 state, global-transition,
  local-transition, uniform-fusion, and regularized-multiscale representations.
- R31 selected the regularized prediction only when all three trained seeds
  agreed; otherwise it fell back to the three-seed uniform-fusion majority.
  On its one-shot test, regularized unanimity covered 74.59% of observations
  and changed 24.98% from the uniform majority.
- R31's strongest single expert was global transition (0.4434), uniform fusion
  was 0.4728, and consensus was 0.5033. Thus the transferable object is not
  merely an agreement bit: it depends on competent learned expert
  representations and a competent fallback.
- R33 replaced both sides of that bridge: its robust/random token summary was
  not R31 uniform fusion, and its rich token summary was not R31 regularized
  multiscale. The attempted "R31-to-token transfer" therefore changed the
  representation before testing whether the gate survived.
- The first R33A repair should reconstruct capacity-matched learned state,
  global, local/relation, robust-fusion, and rich-regularized token summaries
  from the R32 patch cache before changing the gate rule.

## R33 train-only case registry v1

- Scope is exactly 13,566 rows from the 1,574-patient R32 train partition; no
  dev case outcomes, sealed-test records/images, or gold outcomes were
  inspected.
- Robust F1 is 0.4574, rich F1 0.4520, and routed F1 0.4529. A label-reading
  robust/rich case oracle reaches 0.5634, leaving +10.60 pp theoretical
  headroom.
- Across 40,698 seed-record units, rich helps 4,476 (11.00%) and harms 4,714
  (11.58%). The opportunity is balanced but slightly harm-heavy.
- The hard route selects 1,391 helped and 1,527 harmed units, net -136. Its
  precision among help-or-harm units is only 47.67%, below chance. The
  coverage-matched random route is similarly negative (2,117 helped vs 2,261
  harmed, net -144).
- Failure is not concentrated in one endpoint: net selected help-minus-harm is
  -71 Stable, -45 Improved, and -20 Worse.
- Atelectasis is the only large finding with slightly positive routed net
  (+25); cardiomegaly (-53), edema (-40), and lung opacity (-33) are the
  largest negative contributors. This supports a representation/router
  failure rather than a single-label bug.
- The durable runtime registry is
  `F:\VisualVIT_runtime\050_routeC\r33a_case_study\failure_registry_v1`.

## R33A Attempt A design

- Reuse the frozen `[197,768]` BiomedCLIP patch cache; do not re-encode images
  or recompute cache hashes.
- Replace the random nonlinear token builder with direct, outcome-free,
  normalized transition blocks:
  current-state CLS, global CLS pair interactions, spatial patch-statistic
  interactions, and top-change patch relations.
- Materialize the same six token types and exact 4/12/16/16/12/4 physical
  layout. Corresponding robust/rich types share the same fixed projection;
  rich differs only in the local/relation source content.
- Make P0 literal query-only by deriving its four tokens solely from the
  finding vocabulary. No image feature enters type 0.
- Preserve three projection seeds 17/29/43 and the same final probe capacity.
  This attempt first tests whether semantically direct fixed-64 tokens restore
  competent robust/rich experts before introducing a benefit-trained router.
- Use train-only nested OOF for exploration. Dev remains excluded from
  case-level iteration and is not evaluated by Attempt A unless a candidate is
  frozen later.

## R33A Attempt A result

- Verdict: `STOP_R33A_TRAIN_EXPLORATION`.
- Direct transition features substantially improved the competent fixed
  baselines: query-only 0.4472, global 0.4822, robust P3 0.4874, compared with
  R33 P3 0.4583.
- Literal query-only and within-1pp-of-best controls now pass, confirming those
  R33 failures were implementation artifacts.
- Rich P4 is still weaker than robust P3 (0.4796 vs 0.4874). Hard route P6 is
  0.4828, delta -0.461 pp with 95% CI [-1.298, +0.357] pp.
- All seed deltas are negative (-0.559, -0.204, -0.616 pp). Prior shuffle again
  fails: its P6-P3 delta is +0.413 pp rather than attenuating below the primary.
- Hard route improves on matched random but still has negative net correction
  (-0.461 pp vs -0.787 pp). Representation competence improved, but rich
  benefit remains heterogeneous and unanimity is not a useful benefit target.

## R33A Attempt B design

- Keep Attempt A tokens frozen and change only the route target.
- For every outer fold, obtain robust and rich auxiliary logits with the same
  nested patient OOF discipline.
- Define a row-level benefit target only when the three seed experts have a
  nonzero net rich-helped minus rich-harmed count. Ambiguous rows do not train
  the router.
- Fit a balanced, regularized logistic benefit router using only label-free
  robust/rich probability and confidence features. Cross-fit the router across
  outer-training folds; fit the final router on all outer-training OOF
  features to predict the untouched outer fold.
- Labels determine router targets only in its training folds. Neither labels
  nor auxiliary logits enter the visual token bundle or final progression
  probe.
- Attempt B remains train-only exploratory and cannot unlock R34 directly.

## R33A Attempt B result

- Verdict: `STOP_R33A_TRAIN_EXPLORATION`.
- P6-P3 is -0.676 pp, CI [-1.539,+0.162] pp; all seed deltas are negative.
- Decisive benefit targets are almost exactly balanced in every outer fold
  (rich target rate 48.8%-50.4%), but the label-free probability/confidence
  router does not generalize benefit. Its selected-bundle P6 is worse than
  Attempt A consensus.
- Directly applying the learned benefit route to the already fitted P3/P4
  outputs gives 0.48746 versus P3 0.48740, essentially zero gain. The failure
  is therefore not caused only by retraining a heterogeneous P6 head.

## Output-fusion case study

- A faithful R31-style rule—use the unanimous rich prediction, otherwise use
  robust majority—scores 0.49963 on the train-only OOF predictions, +1.223 pp
  over pooled P3. This is materially better than Attempt A's selected-bundle
  P6 (0.48279).
- Higher-confidence per-seed expert selection reaches only 0.49015.
- This isolates a second transfer mismatch: R31 selected already competent
  expert outputs, whereas R33 selected a token bundle and trained a new probe
  over the heterogeneous distribution.
- The R31-style output rule is still below the +2 pp gate and cannot itself
  pass R33A. It suggests the token reader needs enough nonlinear capacity to
  learn a common decision surface across robust/rich bundle distributions.

## R33A Attempt C design

- Keep Attempt A direct-transition tokens and the original hard-consensus route.
- Replace the underpowered 774-to-3 linear reader with the proposal-allowed
  common-width token MLP: standardized 774 inputs, 128-unit GELU hidden layer,
  and 3-class output.
- Every P0-P6 and auxiliary probe receives the identical architecture,
  optimizer, epochs, and weighting; no system receives extra capacity.
- Scope remains train-only nested OOF with no dev/sealed/gold evaluation.

## R33A Attempt C result

- Verdict: `STOP_R33A_TRAIN_EXPLORATION`.
- MLP improves P3 to 0.4946 but P4 remains much weaker at 0.4794. P6 is
  0.4899, delta -0.468 pp with CI [-1.337,+0.358] pp.
- Only seed 29 is weakly positive (+0.104 pp); seeds 17/43 are negative.
- Because extra reader capacity improves robust but not rich, reader
  under-capacity is not the bottleneck. The rich token source itself lacks the
  anatomy/context structure that made R29-R31 successful.

## R33A Attempt D design

- Reconstruct R31's actual contextual-transition inductive bias from the R32
  14x14 patch cache instead of using outcome-blind top-change patches.
- Convert each row's registered anatomy string into a deterministic spatial
  patch mask and a dilated context mask. Use current anatomy-pooled state,
  global CLS transition, exact-anatomy transition, and context transition.
- Query tokens contain finding and anatomy identity only; P0 remains a literal
  non-image control.
- Robust uses global/coarse local content. Rich uses the exact anatomy and
  expanded context pools. Corresponding types keep the same projection,
  physical layout, and capacity.
- Validate mask geometry in unit tests. Run the original linear shared-capacity
  probes and hard-consensus route first, so the only scientific mutation from
  Attempt A is anatomy/context localization.

## R33A Attempt D result

- Verdict: `STOP_R33A_TRAIN_EXPLORATION`, but it is the strongest selected-
  bundle attempt so far.
- P3 0.49363, P4 0.49037, P6 0.49281; P6-P3 -0.082 pp with CI
  [-0.882,+0.724] pp.
- Seed 17 (+0.322 pp) and 43 (+0.149 pp) are positive; seed 29 remains negative
  (-0.715 pp). Anatomy/context localization therefore removes nearly all mean
  negative transfer but does not meet the survival gate.
- Prior shuffle remains anti-causal: its routed delta is +0.643 pp rather than
  attenuating. The learned classifier is still not forced to use a coherent
  prior-current relation.
- Fairly ensembling P3 by seed majority raises robust to 0.50964. R31-style
  unanimous-rich/fallback-majority is 0.51015, only +0.051 pp with CI spanning
  zero. Thus the apparent +1.2 pp output-fusion gain in Attempt A was mostly
  seed ensembling, not routing.
- Attempt B's logits-only benefit router achieved only 62.8%-64.7% in-sample
  benefit-target accuracy and essentially zero direct OOF gain. Before another
  formal router attempt, test whether anatomy token geometry adds cross-fold
  benefit predictability.

## Benefit-learnability case study

- On Attempt D OOF experts, 5,316/13,566 rows have a nonzero three-seed
  rich-helped-minus-harmed target; positive/negative support is nearly balanced
  (2,699/2,617).
- Logits-only cross-fold benefit prediction reaches 63.68% decisive accuracy
  and direct expert routing F1 0.50365, +1.003 pp over pooled P3. It selects
  2,535 helped vs 1,666 harmed seed-row units (net +869).
- Adding 474 anatomy-token geometry features increases training fit but lowers
  cross-fold decisive accuracy to 61.73% and routed F1 to 0.50145. This is
  classic extra-feature overfit and must not be promoted.
- A registered threshold curve from 0.50 to 0.75 peaks at 0.50. Guarding only
  high-confidence routes monotonically reduces F1; threshold tuning cannot
  supply the missing +1 pp.
- The next narrow diagnostic may add explicit finding-specific interactions to
  logits because benefit mechanisms differ by pathology. It must be tested by
  the same patient folds; raw high-dimensional token geometry remains rejected.

## Benefit-learnability v3 finding interactions

- Adding pre-registered finding-by-expert interactions gives direct routed F1
  0.50436 versus pooled P3 0.49363, a +1.074 pp exploratory gain.
- The improvement is still below the +2 pp survival gate. Decisive benefit
  accuracy falls from 63.68% for logits-only to 61.52%, so the small F1 change
  does not establish a more generalizable benefit classifier.
- The registered confidence curve again peaks at threshold 0.50; thresholds
  0.55-0.75 all reduce F1. Neither pathology interactions nor threshold
  selection closes the missing gate.
- All Attempt A-D selected-bundle systems also fail the prior-shuffle
  attenuation control. The next mechanism mutation must therefore make
  prior/current coherence explicit, rather than adding another post-hoc route
  feature family.

## R33A Attempt E result and projection audit

- The outcome-free coherence adapter generalizes to the distinct formal
  prior-shuffle mapping (AUC 0.9353, accuracy 0.8487).
- Attempt E P6-P3 is +0.571 pp with CI [-0.264,+1.423] pp; seeds 17/29 are
  positive and seed 43 is negative. Prior-shuffle delta is -0.173 pp, so the
  attenuation control passes for the first time.
- The result is not a clean candidate comparison because expanding relation
  width also changed every random-projection seed. P3 drifted from Attempt D
  0.49363 to 0.48668. E2 must preserve the Attempt D matrices and append only
  the coherence rows before judging primary survival.
- Projection-matched E2 restores P3 to 0.49375 but P6 is 0.49277
  (-0.098 pp, CI [-0.906,+0.707] pp) and prior-shuffle returns to +0.511 pp.
  The outcome-free coherence objective is therefore insufficient.

## R31 bridge audit and Attempt F design

- R29 projected each state/transition representation to 256 dimensions before
  fitting trained progression heads. R30 retained 128 dimensions per
  global/exact/context scale, concatenated them with query/geometry, and fit a
  strongly regularized trained classifier.
- R33A A-E instead applied a fixed random projection directly to 64-wide type
  summaries before progression fitting. A downstream reader cannot recover
  directions discarded by this bottleneck.
- Attempt F keeps five outcome-free source blocks at 256 dimensions and learns
  a 64-unit GELU bottleneck separately inside every patient-disjoint fit. All
  P0-P6 and auxiliary systems receive the same architecture and optimization.

## Attempt F result

- The learned bridge raises P3/P4 to 0.50720/0.50741, so rich competence is no
  longer the limiting average. P2 global is strongest at 0.50968.
- Hard-consensus P6 is 0.50597, -0.123 pp from P3 with CI
  [-0.936,+0.693] pp. Selected correction and harm rates are virtually equal
  (10.12% vs 10.15%).
- P7 remains 0.60824, proving large heterogeneous case headroom. One final
  benefit-conditioned learned-bridge attempt is justified; further route
  feature or threshold fishing is not.

## Attempt G result and frozen-cache closure

- The cross-fitted benefit-conditioned bridge scores P6 0.50504 versus P3
  0.50720: -0.217 pp, CI [-1.033,+0.581] pp. Seeds 17/29 are negative and
  seed 43 is positive.
- The selected benefit route still has slightly more harm than correction
  (10.05% vs 9.93%) despite 30 cross-fit router audits. Prior-shuffle delta is
  -0.091 pp but does not attenuate by the required 0.5 pp relative to primary.
- A-G isolate and reject every registered frozen-cache rescue family:
  representation construction, reader capacity, anatomy/context localization,
  outcome-free coherence, trained 64D compression, consensus routing, and
  cross-fitted benefit routing.
- No candidate may be promoted to the 300-patient dev confirmation. Further
  changes on the same train outcomes would be validation fishing. A new stage
  requires a distinct authority for encoder adaptation or new development
  data; R34, sealed test, and gold remain locked.
