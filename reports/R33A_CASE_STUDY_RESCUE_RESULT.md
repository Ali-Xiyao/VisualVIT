# R33A Case-Study Rescue Result

Updated: 2026-07-27

Current evidence class: `EXPLORATORY_TRAIN_ONLY_NESTED_OOF`

## Direct status

The original R33 remains an immutable `STOP_R33_TOKEN_SURVIVAL`. R33A has
repaired several implementation mismatches and raised the train-only robust
reference from 0.4583 to about 0.494, but no selected-bundle candidate has
passed the registered +2 pp survival gate and prior-shuffle control. R34 and
all test/gold-dependent stages remain locked.

## Evidence boundary

- Case iteration uses 13,566 persistent rows from 1,574 train patients.
- The 300-patient dev partition is reserved for one frozen confirmation.
- The 483-patient sealed test remains unread.
- Human-gold outcomes remain unread.
- The frozen R32 patch cache is reused; image encoding and cache provenance
  hashes are not recomputed.

## Failure ledger

| Attempt | Hypothesis | P3 robust | P4 rich | P6 routed | P6-P3 | Prior-shuffle | Verdict |
|---|---|---:|---:|---:|---:|---:|---|
| Original R33 | Random frozen hierarchical token builder + unanimity route | 0.4583 | not superior | 0.4516 | -0.669 pp | +0.422 pp | STOP |
| A | Direct fixed transition summaries remove random builder failure | 0.4874 | 0.4796 | 0.4828 | -0.461 pp | +0.413 pp | STOP |
| B | Cross-fitted rich-benefit route replaces agreement target | 0.4874 | 0.4796 | 0.4806 | -0.676 pp | +0.161 pp | STOP |
| C | Common 128-unit GELU reader removes linear under-capacity | 0.4946 | 0.4794 | 0.4899 | -0.468 pp | +0.512 pp | STOP |
| D | Anatomy-aware exact/context pooling restores R31 locality | 0.4936 | 0.4904 | 0.4928 | -0.082 pp | +0.643 pp | STOP |
| E | Outcome-free coherence adapter, but changed all projection seeds | 0.4867 | 0.4876 | 0.4924 | +0.571 pp | -0.173 pp | CONFOUNDED STOP |
| E2 | Coherence adapter with Attempt D projection rows preserved | 0.4938 | 0.4965 | 0.4928 | -0.098 pp | +0.511 pp | STOP |
| F | Outcome-free 256-wide prebridge + fold-trained 64-wide bridge | 0.5072 | 0.5074 | 0.5060 | -0.123 pp | +0.147 pp | STOP |
| G | Attempt F bridge + fully cross-fitted benefit route | 0.5072 | 0.5074 | 0.5050 | -0.217 pp | -0.091 pp | STOP |

Attempt D has two positive seed directions, but the confidence interval
[-0.882, +0.724] pp spans zero and the prior-shuffle behavior remains
anti-causal.

## What the case studies established

1. The original R33 tested a randomly frozen bridge, not the trained
   resampler/projector allowed by the proposal. Direct summaries repair the
   strongest query/global control failures but do not create a competent rich
   expert.
2. Agreement is not equivalent to expected rich-over-robust benefit. The
   original hard route selects more harms than corrections.
3. A stronger common reader improves robust P3 but not rich P4, excluding
   reader capacity as the main bottleneck.
4. R31's anatomy/context inductive bias is real: restoring it removes nearly
   all average negative transfer. It still does not make the model depend
   causally on the registered prior.
5. Benefit routing has real but insufficient headroom. Cross-fold logits-only
   routing gains +1.003 pp; fixed finding interactions reach +1.074 pp.
   High-dimensional token geometry overfits, and every confidence threshold
   above 0.50 reduces F1.
6. Seed-majority accounting shows that the earlier apparent +1.2 pp
   R31-style fusion gain was mostly ensembling. The fair rich-unanimous
   increment is only +0.051 pp.

## Attempt E: explicit temporal coherence

Attempt E is frozen before progression evaluation. It trains an outcome-free
`3840 -> 64 -> 1` adapter to discriminate a registered prior/current pair from
a finding-matched cross-patient negative. Its negative mapping differs from the
formal prior-shuffle control.

The adapter's engineering audit against the untouched formal control mapping:

- AUC: 0.9353
- accuracy: 0.8487
- real-pair mean logit: +2.548
- held-out shuffled-pair mean logit: -1.518

The learned normalized 64-vector enters only the rich relation block; robust
receives an equal-width zero block.

Attempt E initially appeared to pass the shortcut control with a +0.571 pp
primary delta. Full-metric audit found that expanding the relation input also
changed every block's projection seed, moving P3 from 0.4936 to 0.4867. This
result is retained but cannot be promoted. Projection-matched E2 restores P3
to 0.4938 and yields P6-P3 -0.098 pp, CI [-0.906,+0.707] pp, with
prior-shuffle +0.511 pp. The apparent E rescue therefore does not reproduce
under the controlled comparison.

## Attempt F: learned 64-dimensional bridge

Attempt F restores the remaining proposal-authorized component that R33 never
executed: a progression-trained projector. Each outcome-free query/state/
global/local/relation source is retained at 256 dimensions, then every
capacity-matched system learns a fold-specific `1286 -> 64 GELU -> 3`
classifier. The 64 hidden units are the only supervised bottleneck, and every
outer patient remains absent from its bridge fit.

Feature preparation reused the patch cache and completed in 51.1 seconds.
Train-only nested OOF completed in 810.2 seconds. P3/P4 are equally competent
at 0.50720/0.50741, but P6 is 0.50597: -0.123 pp with CI
[-0.936,+0.693] pp. Prior-shuffle is +0.147 pp and does not attenuate.

Attempt G is the final registered routing test on this frozen prebridge. It
keeps every Attempt F component and replaces consensus only with the fully
cross-fitted benefit route. No new features or thresholds are introduced.

Attempt G completed in 930.8 seconds. P6 is 0.50504 versus P3 0.50720:
-0.217 pp with CI [-1.033,+0.581] pp. Seeds 17/29 are negative and seed 43 is
positive. Its selected route still has more harm than correction. The frozen
cache verdict is therefore `STOP_R33A_FROZEN_CACHE_PREMISE`.

## Decision tree

1. Do not inspect the 300-patient dev split because no train-only candidate
   survived.
2. Keep the 483-patient sealed test and all gold outcomes locked.
3. Do not tune more routes, thresholds, or widths on these train outcomes.
4. Resume only under a new protocol that authorizes a scientifically distinct
   encoder-adaptation objective or fresh development data.
