# CAPES-CI Query-Anchor R2 Frozen Calibration Protocol

Status: frozen engineering calibration protocol, 2026-07-22  
Protocol ID: `CAPES_CI_QUERY_ANCHOR_V2_R2_2026_07_22`  
Evidence class: `QUERY_GATED_RELATION_MEDIATOR_ENGINEERING_NONCONFIRMATORY`

## 1. Scope and claim boundary

R2 is a synthetic, visible-feature engineering anchor for testing whether the
exact-64 query-relation path can learn a global one-to-one assignment mediator.
It is not evidence for a pretrained VLM, the complete CAPES-CI method, clinical
causality, or real-data generalization. The development split has been inspected
during design and is nonconfirmatory. No formal real-data test split is used.

R1 and its pooled-bypass failure remain immutable negative diagnostics. R2 does
not overwrite or reinterpret them.

## 2. Frozen construction

The split sizes are 16/8/24 cases per label for train/inner-development/
development. Split seeds are 73401/74401/75401. Labels are stable, worse,
improved, new, and resolved. Each case has 14 prior and 14 current endpoints:
two anatomy blocks with six persistent endpoints each plus two null endpoints.
The feature width is 18:

- channel 0: query marker, excluded from matcher input;
- channel 1: semantic state, excluded from matcher input;
- channels 2:8 and 8:14: independent six-dimensional anatomy identity blocks;
- channels 14:18: orthogonal null features.

For each replicate, the physical persistent query row, endpoint permutations,
and orthogonal rotations are sampled before the label loop. The same persistent
query row, visible slot after permutation, marker, and marked prior vector are
reused across stable/worse/improved. Labels alter only the query-to-state
permutation required to instantiate the counterfactual relation. No label may
select a different queried endpoint.

For each anatomy block, with `H=3`, `L=-2`, `B=10`, and `C=sqrt(35)`, the
six-by-six similarity matrix has three query rows and three guard rows. For state
`s`, the true/decoy column pair gives an assigned query `(H,L)`, other queries
`(L,H)`, `C` on all guard rows of the true column, and `B` only on guard `s` of
the decoy column. Every column has squared norm 122. The globally optimal
Hungarian assignment is unique. A balanced Sinkhorn plan at epsilon 0.05 and
2048 iterations must have exact oracle argmax and minimum oracle mass at least
0.90.

## 3. Marginal-bypass qualification

R2 makes a finite, preregistered, architecture-relative claim rather than an
information-theoretic nonidentifiability claim. Continuous QR coordinates are
never accepted as evidence through one-sample in-batch table lookup. Exact and
univariate signature lookup is evaluated only when every lookup key is repeated;
direct repeated label channels remain fail-closed.

The structural bank contains 22 no-pair-axis, per-side permutation-invariant
attacks: linear, polynomial degree 2/3, RBF bandwidth 0.25/0.5/1/2, and
log-sum-exp temperature 0.25/0.5/1/2, each with state conditioning alone and
with anatomy-plus-state conditioning. Every persistent-three-label macro-F1
must be at most 0.45.

The trained train-to-development bank contains five controls for every seed
17/29/43: current-only linear moments, prior/current separate-pooling linear
moments, current-only DeepSets, prior-only DeepSets, and prior/current late-
fusion DeepSets. None may expose a prior-by-current pair axis. Every development
macro-F1 must be at most 0.45. Each DeepSets control must first demonstrate
train macro-F1 at least 0.90, finite gradients at every step, and recorded
initial/final loss; otherwise the gate is not evaluable and stops. A one-step
smoke records but does not require this competence condition.

## 4. Exact-64 and fairness contract

All oracle, B4a, learned, Hungarian, and Sinkhorn readouts call the frozen VLM
adapter through the same exact-64 projected-token scoring path. They use the
same projector initialization per seed, the same train/development tensors and
order, 500 AdamW steps, learning rate 0.02, and zero weight decay. The adapter
must remain bitwise unchanged. Observed adapter calls, placeholder counts,
position/mask checks, complete state hashes, plan hashes, and split hashes are
recorded.

The matcher receives channels 2:18 and anatomy only; channels 0/1 are zeroed.
Hidden gold IDs and oracle cardinality are forbidden. Relabeling hidden IDs must
leave plans, allocation, and scores unchanged.

## 5. Frozen baselines and thresholds

Hungarian-with-reject and balanced Sinkhorn share one visible cosine/support/
marginal contract. Persistent/null support is an analytic synthetic-fixture
positive control, not a general real-data baseline. The reject threshold is the
analytic pre-run value 1.0; it is not selected on development. Structural checks
cover train, inner-development, and development. The same plan hash must be
observed across seed-specific readout executions.

Learned assignment absolute thresholds are:

- every-seed hard query identity at least 0.50;
- aggregate hard identity at least 0.60;
- every-seed soft oracle query mass at least 0.30;
- aggregate soft oracle query mass at least 0.35.

Relative baseline noninferiority thresholds are:

- every-seed learned hard identity at least Hungarian hard minus 0.10;
- aggregate learned hard identity at least Hungarian hard minus 0.05;
- every-seed learned soft mass at least Sinkhorn mean mass minus 0.10;
- aggregate learned soft mass at least Sinkhorn mean mass minus 0.05.

Baselines cannot rescue a failed mechanism gate.

## 6. Registered gate order and stopping

The primary run uses exactly seeds 17/29/43, 500 steps, CPU execution, and the
frozen splits above. Gates are evaluated in this order:

1. structural integrity and analytic baseline controls;
2. working-oracle competence;
3. marginal-control competence and development bypass rejection;
4. persistent binding under all three frozen derangements;
5. learned recovery plus absolute identity thresholds;
6. Hungarian/Sinkhorn noninferiority;
7. exact independent-process reproduction.

The run stops at the first failed gate. Seeds cannot be removed, thresholds
cannot be lowered, and no rescue architecture may be introduced after observing
registered results. The formal test remains sealed. A successful primary may
only report `PASS_GATES_1_TO_6_AWAITING_INDEPENDENT_REPRODUCTION`.

## 7. Independent reproduction

Two fresh child processes must be launched sequentially by the dedicated
reproduction launcher with `PYTHONHASHSEED=0`, `OMP_NUM_THREADS=1`, and
`MKL_NUM_THREADS=1`. Both must exit zero, report valid distinct UUIDs, match
launcher-observed PIDs, pass eligibility, and have identical canonical payloads.
Only walltime and process identity are excluded. A failure of replica A prevents
replica B from launching.

## 8. Frozen provenance boundary

The source manifest covers the runner, reproduction launcher, all
`src/visualvit/*.py` modules, this protocol, the focused calibration/model/runner
tests, and `pyproject.toml`. Runtime versions, environment variables, process
identity, ordered split tensor hashes, and the composite manifest hash are
written into every artifact. Any source drift invalidates prior dry-run or smoke
artifacts and requires a new unique run directory.
