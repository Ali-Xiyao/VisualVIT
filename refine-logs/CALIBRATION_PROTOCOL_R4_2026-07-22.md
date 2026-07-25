# CAPES-CI QPTM R4 Frozen Engineering Calibration Protocol

Status: frozen method boundary; registered execution is blocked until every
`MUST_RESOLVE_AND_FREEZE_BEFORE_DRY_RUN` item in Section 4 is replaced by a
source-hashed value before the first R4 dry-run  
Date: 2026-07-22  
Protocol ID: `CAPES_CI_QPTM_R4_2026_07_22`  
Evidence class: `SYNTHETIC_ENGINEERING_NONCONFIRMATORY`

## 1. Authority, purpose, and immutable predecessors

R4 is the next engineering calibration after
`CALIBRATION_PROTOCOL_R2_2026-07-22.md` and
`CALIBRATION_PROTOCOL_R3_2026-07-22.md`. The R3 registered primary is an
immutable `STOP_LEARNED_RECOVERY` result: its structural, oracle, marginal,
and binding checks passed, but the label-trained unstructured matcher did not
recover the assignment and did not meet baseline noninferiority. R4 neither
overwrites that run nor reclassifies it as a success. It changes the method
class and training factorization, so all R4 artifacts require a new run
directory, protocol identifier, source manifest, and evidence lineage.

R4 tests one narrow methodological proposition:

> A query-independent, two-sided-null partial transport can establish a single
> persistent correspondence structure, after which a query may gate only the
> transported relation/change representation used by the mediator.

The paper-level object is the **Query-Gated Persistent Transport Mediator
(QPTM)**: an auditable correspondence-to-difference representation under a
fixed token budget. Partial transport, Sinkhorn projection, Hungarian
assignment, dustbins, and rejection are established optimization mechanisms.
They are solvers or baselines, **not claimed as novelty**. The potential
methodological contribution is the interface and intervention design that
separates query-independent identity transport from post-transport
query-conditioned relation mediation, together with an assignment-only causal
audit under exact compute/token matching.

R4 remains synthetic engineering evidence. It is not evidence for a pretrained
vision encoder, a complete frozen VLM, clinical causality, real-data
generalization, or any ICLR/CVPR/AAAI main claim.

## 2. Frozen method family

### 2.1 Query-independent transport owner

The only assignment owner is a null-aware partial transport module. For visible
prior/current region features, validity masks, and preregistered coarse anatomy
compatibility, it emits real-real edge utilities, prior-to-null utilities, and
null-to-current utilities. A differentiable partial-transport solver produces
the soft train-time plan; a globally optimal hard solver operating on the same
utilities produces the hard evaluation plan. The augmented plan has real-real,
death, and birth mass and zero dustbin-to-dustbin mass.

The matcher and solver must be query-independent. They cannot receive a query
marker, queried row/column, query embedding, answer option, progression state,
target label, report text, oracle entity ID, oracle match count, oracle
cardinality, or test metadata. Changing only the query on a fixed image pair
must leave edge/null utilities, masks, marginals, soft plans, hard plans, and
their canonical hashes unchanged.

The R4 learned edge utility must be permutation equivariant and must use a
registered structural similarity backbone plus a bounded contextual residual.
The residual bound must be certified against the clean fixture's assignment
margin so it cannot overturn the unique clean optimum at initialization or
within the allowed parameter range. The concrete backbone, invariant context
statistics, residual parameterization, bound, initialization, and margin
certificate are implementation-dependent blockers in Section 4; no value is
invented in this document.

### 2.2 Post-transport query-gated mediator

The transport plan is computed once for the full prior/current endpoint sets.
Relation candidates are then formed from transported persistent, death, and
birth mass. Only after this operation may a query gate select or weight the
relation/change evidence used by the mediator and readout. The query gate may
not recompute, edit, mask, sharpen, renormalize, or otherwise feed back into the
transport plan or allocator.

For a fixed image pair with multiple queries, every query must reuse the same
transport-plan hash. Query-specific mediator outputs may differ only downstream
of the recorded post-transport gate. The assignment-independent entity stream,
source universe, allocation plan, physical token layout, and frozen-model
interface remain identical across queries.

### 2.3 Two-sided null and hard/soft agreement

Birth and death are first-class outcomes, not padding side effects. Padding,
anatomy incompatibility, real-to-null, null-to-real, and dustbin-to-dustbin
masks are explicit. The same visible utility contract is used by the soft and
hard solvers. Synthetic analytic null support may be used only as a fixture
positive control and must be labelled as such; it cannot be described as a
learned real-data null solution.

Soft feasibility, mass accounting, finite gradients, permutation equivariance,
hard global optimality on enumerated micro-cases, deterministic tie handling,
and reject-when-null-is-better behavior are mandatory structural checks.

## 3. Frozen strata and estimands

### 3.1 Clean correspondence stratum

The clean stratum isolates whether the registered transport learner and solver
can recover a unique, globally identifiable persistent assignment under held-out
endpoint permutations and held-out feature-basis transformations. It contains
persistent, birth, and death cases; all required assignment and null decisions
are derivable from allowed visible features and global transport constraints.

The clean stratum is not allowed to carry labels in individual coordinates,
token order, padding count, anatomy count, null count, query position, source
ID, or any repeated per-side signature. Train, inner-development, and
development instances are disjoint at the generator seed and tensor-hash level.
The clean-stratum primary estimands are hard assignment identity, soft oracle
mass, null decision accuracy, transport feasibility, and post-transport label
recovery. These are engineering estimands, not clinical endpoints.

### 3.2 Anti-equivalence challenge

The anti-equivalence challenge tests whether QPTM uses pairwise correspondence
rather than a marginal or query shortcut. Each challenge group contains
counterfactual cases with identical allowed per-side multisets, per-side
permutation-invariant summaries, anatomy/null counts, token counts, and query
location distribution. The required relation label differs only through the
globally consistent prior-current assignment encoded on the pair axis.

The full pairwise compatibility structure must identify one complete transport
plan before a query is applied. Multiple queries over the same pair select
different relations from that single plan; they may not induce different plans.
An anatomy-compatible derangement creates the matched anti-equivalence
intervention while holding every non-assignment input and every downstream
compute surface fixed.

The challenge is invalid if a current-only, prior-only, separate-pooling,
late-fusion, repeated-signature lookup, query-marker lookup, padding/count, or
source-order control can exceed its frozen bypass ceiling. A challenge failure
cannot be rescued by good clean-stratum accuracy.

### 3.3 Assignment-only binding and recovery estimands

The binding contrast uses the same visible features, candidate universe,
birth/death sets, query, token layout, projector, frozen adapter, readout,
optimizer, step count, and seed. B4b uses the correct persistent assignment;
B4a uses a preregistered anatomy-compatible derangement. The only permitted
difference is the real-real assignment and relation values causally downstream
of that assignment.

The learned-method recovery estimand remains relative to the qualified B4
contrast. If the oracle binding denominator is non-positive or otherwise fails
its registered competence gate, recovery is not evaluable; neither a solver
baseline nor clean assignment accuracy may rescue it.

## 4. Pre-dry-run resolution blockers

R4 is **not eligible for a dry-run, smoke run, or registered primary** until a
source-controlled configuration/addendum resolves and hashes every item below.
Resolution must occur before any R4 development metric is inspected. Literal
placeholder strings are fail-closed.

- `MUST_RESOLVE_AND_FREEZE_BEFORE_DRY_RUN`: clean and anti-equivalence split
  sizes, generator seeds, replicate grouping, and tensor-hash construction;
- `MUST_RESOLVE_AND_FREEZE_BEFORE_DRY_RUN`: structural similarity backbone,
  allowed invariant edge/context features, and prohibited feature channels;
- `MUST_RESOLVE_AND_FREEZE_BEFORE_DRY_RUN`: contextual residual
  parameterization, initialization, numeric bound, and analytic assignment-
  margin certificate demonstrating that the bound preserves the clean optimum;
- `MUST_RESOLVE_AND_FREEZE_BEFORE_DRY_RUN`: differentiable partial-transport
  solver, temperature/regularization, iteration count, marginal construction,
  convergence tolerance, and hard-solver tie/reject policy;
- `MUST_RESOLVE_AND_FREEZE_BEFORE_DRY_RUN`: transport-supervision loss, null
  loss, mediator loss, optimizer, learning rates, weight decay, step counts,
  gradient clipping, checkpoint selection rule, and all initialization seeds;
- `MUST_RESOLVE_AND_FREEZE_BEFORE_DRY_RUN`: numerical thresholds for new R4
  clean-stratum assignment/null competence, anti-equivalence recovery, soft/
  hard agreement, residual saturation, and optimization stability;
- `MUST_RESOLVE_AND_FREEZE_BEFORE_DRY_RUN`: exact construction and ceilings for
  any new bypass controls beyond the inherited R3 bank;
- `MUST_RESOLVE_AND_FREEZE_BEFORE_DRY_RUN`: parameter/compute matching rule for
  the learned contextual matcher and its strongest trainable baseline;
- `MUST_RESOLVE_AND_FREEZE_BEFORE_DRY_RUN`: canonical payload fields and the
  precise independent-process reproducibility tolerance for any newly added
  floating-point diagnostics.

The resolver must show that each numerical threshold follows from an analytic
fixture property, a numerical-precision bound, or an untouched design-only
calibration artifact. It may not derive a threshold from a registered R4 result.
Changing a resolved item after the first dry-run terminates R4 and requires a
new versioned protocol.

## 5. Input and leakage boundary

### 5.1 Matcher-permitted inputs

The matcher may read only source-hashed, image-derived prior/current region
features; validity/padding masks; preregistered coarse anatomy compatibility;
and explicitly registered non-outcome acquisition metadata if the resolver
proves it is available identically at train and inference time. Pairwise feature
construction is allowed, but it must be permutation equivariant and must not
encode hidden slot or gold identity.

### 5.2 Matcher-forbidden inputs

The matcher, marginal constructor, support mask, null utilities, solver, and
allocator may not read query content or position, synthetic state channels,
target/progression labels, answer candidates, report/comparison text, gold
entity IDs, oracle cardinality, oracle match count, patient/study IDs as
features, split identity, sample index, seed, checkpoint-selection metrics, or
formal-test information. Gold assignment/null labels may be used only as the
training target of the explicitly separated transport-supervision stage; they
are never model inputs and never enter development/test inference.

### 5.3 Required counterfactual audits

The registered run must prove all of the following with hashes or direct
property tests:

1. query substitution leaves all pre-mediator transport artifacts identical;
2. hidden-ID relabeling leaves plans, allocation, and scores identical;
3. endpoint permutation induces only the corresponding plan permutation and
   leaves restored scores invariant;
4. zeroing forbidden synthetic channels leaves matcher plans unchanged;
5. actual train/development tensors are bitwise unchanged by competence-probe
   or counterfactual construction;
6. B4a/B4b differ only in the assignment and causally downstream relation
   values permitted by Section 3.3.

## 6. Frozen training decoupling

R4 has two sequential training stages and forbids query-label gradients from
training the matcher in the registered primary.

1. **Transport stage.** Train edge/null utilities on the training split using
   only the registered assignment/null supervision target. Select or stop using
   only the frozen inner-development transport criterion. The query gate,
   mediator, and label readout do not participate. Then freeze the transport
   checkpoint and record its state hash.
2. **Mediator stage.** Recompute or load the frozen query-independent plans,
   form relation candidates, and train the post-transport query gate,
   projector/readout, and other explicitly registered adapter parameters on the
   label-training split. Gradients must not enter the matcher, solver, plan, or
   allocation. Checkpoint selection uses only the frozen inner-development
   mediator criterion.

Development examples are evaluation-only except for the preregistered inner-
development selection described above. Formal test data remain sealed. Joint
end-to-end label training, query-conditioned matching, pseudo-label
self-training, and unfreezing the matcher are separate ablations and cannot be
introduced as a rescue inside R4.

The transport and mediator stages must record separate model/optimizer hashes,
parameter counts, gradient-reachability audits, trainable/frozen parameter
lists, loss traces, and checkpoint-selection evidence. A nonzero matcher
gradient in the mediator stage is a structural gate failure.

## 7. Exact-64 frozen-model interface

Every main and matched-control frozen-model run uses exactly:

```text
4 global/context + 28 entity + 28 relation/change + 4 neutral/reserved = 64
```

All 64 positions physically exist. Invalid and reserved positions receive a
shared neutral representation; no method may delete masked positions or gain a
shorter attention path. Entity and relation streams share the same
assignment-independent deterministic allocation plan. Query gating occurs
inside the relation mediator and cannot change the number, order, type, source
support, or physical mask of tokens.

The exact-64 adapter must replace exactly 64 prompt placeholders, use identical
attention and registered position IDs, pass no raw pixels on the relation-token
path, and keep the region encoder and full VLM frozen. All methods use the same
frozen backbone, projector initialization rule, prompt, label strings,
normalized likelihood scorer, token order, batch order, seed bank, and training
budget. Placeholder counts, masks, positions, token/allocation hashes, frozen
parameter hashes, and observed adapter calls are mandatory evidence.

## 8. Frozen baseline and ablation families

The following families must be represented; concrete implementation names and
source hashes are frozen by the Section 4 resolver.

- interface controls: current-only, equal-budget prior/current concatenation,
  and assignment-independent separate pooling;
- causal binding controls: B4a anatomy-compatible derangement and B4b oracle
  assignment, with exact isomorphism outside assignment;
- solver controls: visible-cosine Hungarian-with-reject and visible-cosine
  balanced Sinkhorn under the same support/marginal/null contract;
- trainable matching control: a parameter/compute-matched query-independent
  contextual edge/null learner without the QPTM mediator contribution;
- main method: learned query-independent partial transport plus the
  post-transport query-gated persistent relation/change mediator;
- negative controls: random assignment, wrong-anatomy assignment, query/label
  permutation, and the inherited no-pair-axis marginal-control bank;
- structural ablations: no learned contextual residual, no two-sided null,
  no persistent identity transport, no relation/change mediator, pre-transport
  query gate, and assignment-independent relation pooling.

Hungarian and Sinkhorn are named by solver family and are never labelled as an
R4 innovation. All solver comparisons share visible features, masks, support,
null policy, marginals, allocator, token budget, projector/readout capacity,
seeds, splits, and evaluation code. A baseline may not be intentionally
undertrained; the strongest trainable baseline receives the same checkpoint-
selection access and a documented parameter/compute envelope. Oracle and
analytic fixture baselines are upper/competence controls, not deployable main
methods.

## 9. Threshold authority

Unchanged R3 estimands retain their already frozen thresholds:

- every no-pair-axis structural and trained marginal-bypass development
  macro-F1 is at most `0.45`;
- every inherited DeepSets positive-control probe has train and independent-
  development macro-F1 at least `0.99`, final train CE at most `0.05`, finite
  gradients at all `500` registered steps, endpoint-permutation logit error at
  most `1e-4`, and cyclic-derangement macro-F1 at most `0.10`;
- learned recovery uses the inherited hard-identity absolute floors (`0.50`
  every seed and `0.60` aggregate), soft-oracle-mass floors (`0.30` every seed
  and `0.35` aggregate), and Hungarian/Sinkhorn noninferiority margins
  (`0.10` every seed and `0.05` aggregate);
- the inherited primary seed bank is exactly `17/29/43`; seed deletion or
  replacement is prohibited.

These inherited thresholds apply only where the R4 implementation preserves
the same estimand and evaluator. All new R4 estimands named in Section 4 remain
fail-closed until their thresholds are resolved and source-hashed before the
first dry-run. An unresolved value is not an implicit zero, default, or tuning
range.

Passing a baseline threshold cannot rescue a failed main-method gate. Failing a
new R4 threshold cannot be reinterpreted using an inherited but non-equivalent
R3 threshold.

## 10. Registered gate order and stopping

The run stops at the first failure in this exact order:

0. **Resolution/freeze gate:** every Section 4 blocker is resolved before the
   dry-run; protocol/config/source hashes and unique output root are valid.
1. **Structural/input gate:** schema, two-sided-null mass, differentiability,
   hard global optimality, query independence, permutation equivariance,
   leakage audits, and exact-64 interface all pass.
2. **Fixture-identifiability gate:** the clean and anti-equivalence generators
   have unique oracle transport, qualified B4 binding, and all marginal/query/
   count/order bypass controls below their frozen ceilings.
3. **Transport-competence gate:** the separated matcher meets every frozen
   clean-stratum hard, soft, null, feasibility, stability, and margin-certificate
   threshold on all registered seeds.
4. **Anti-equivalence gate:** one shared query-independent plan supports all
   query-conditioned counterfactuals, defeats the qualified derangements, and
   meets every frozen challenge recovery threshold without marginal bypass.
5. **Mediator/recovery gate:** with transport frozen, the post-transport
   query-gated mediator meets the registered label-recovery and assignment-
   effect thresholds; the matcher-gradient audit remains exactly zero.
6. **Fair-baseline gate:** the main method meets the inherited absolute and
   Hungarian/Sinkhorn noninferiority criteria and the resolved comparison
   criterion against the strongest trainable matched baseline.
7. **Exact-64 bridge gate:** the same ordering holds through the exact-64 frozen
   adapter with no pixel bypass and all B4 isomorphism hashes valid.
8. **Independent reproduction gate:** two fresh sequential processes are
   eligible and match on the registered canonical payload under the frozen
   reproducibility rule.
9. **Formal-data authorization gate:** remains `HOLD` under Section 13 and is not
   executed by an R4 engineering pass.

A one-step smoke may record diagnostics but cannot pass a competence or
recovery gate. A successful primary before independent reproduction may report
only `PASS_R4_GATES_0_TO_7_AWAITING_INDEPENDENT_REPRODUCTION`. A complete R4
engineering pass may report only `PASS_R4_SYNTHETIC_ENGINEERING`; it does not
unlock a formal scientific claim or formal test reveal.

## 11. Prohibited post-result changes

After any R4 dry-run begins, the following are forbidden inside R4: changing
the architecture, allowed inputs, residual bound, solver, loss, marginal/null
construction, split or seed, step count, optimizer, checkpoint rule, threshold,
baseline capacity, token allocation, prompt/scorer, gate order, or evidence
canonicalization; deleting a seed or example; reading a sealed formal test;
selecting a favorable subgroup; adding a rescue module; or rerunning under the
same protocol ID after source drift.

Any such change requires an immutable R4 failure/supersession record and a new
versioned R5 protocol, output root, manifest, and dry-run. Negative results stay
visible. A failed gate may be diagnosed read-only, but diagnosis is not a pass
and cannot authorize the next gate.

## 12. Provenance and independent reproduction

Every artifact records the protocol/config hashes, composite source manifest,
git state if available, command, process identity, runtime/library/hardware
snapshot, environment variables affecting determinism, split/generator seeds,
ordered tensor hashes, checkpoint and optimizer hashes, gradient audits,
plan/allocation/token hashes, per-gate verdicts, and the first stopping reason.

The source manifest covers the R4 runner and reproduction launcher, all imported
method modules, R2/R3/R4 protocols, focused generator/matcher/runner tests, the
exact-64 adapter tests, and dependency specification. Source drift invalidates
earlier R4 dry-run/smoke artifacts.

Independent reproduction uses two fresh child processes launched sequentially
by the dedicated launcher. Both must exit successfully, have valid distinct
process identities and run UUIDs, pass eligibility, and match the frozen
canonical payload. Replica B is not launched if replica A fails. The concrete
thread/determinism environment and floating-point canonicalization for new R4
fields are Section 4 blockers and must be frozen before dry-run.

## 13. Evidence ladder and formal-data HOLD

Evidence is labelled and cannot be promoted across levels:

1. `E0_UNIT_ANALYTIC`: property tests, enumerated micro-cases, analytic margin
   certificates, and exact-64 interface tests;
2. `E1_SYNTHETIC_ENGINEERING_NONCONFIRMATORY`: clean and anti-equivalence R4
   registered runs, including independent process reproduction;
3. `E2_PROXY_ENCODER_NONCONFIRMATORY`: legally available train/development proxy
   images or frozen embeddings; no clinical or full-method claim;
4. `E3_FROZEN_VLM_TRAIN_DEV_BRIDGE_NONCONFIRMATORY`: exact-64 frozen-VLM
   train/development transfer with no formal test access;
5. `E4_REAL_TRAIN_DEV_PILOT`: only after data contract, license, lineage,
   annotation, de-duplication, and split gates pass;
6. `E5_FORMAL_SEALED_EVALUATION`: one frozen reveal after method, baselines,
   seeds, checkpoints, prompts, analysis, power, and external protocol are all
   preregistered.

R4 execution is limited to E0/E1 unless a separate authority explicitly
unlocks E2 or E3. **E4/E5 and all formal data remain `HOLD`.** In particular,
CheXTemporal metadata alone does not establish one-to-one per-box progression
or persistent-entity lineage, and it does not authorize parent radiographs.
CheXpert, MIMIC-CXR, MS-CXR-T, Chest ImaGenome, ReXGradient, or any replacement
dataset may enter a formal run only after applicable license/DUA/CITI access,
patient/study/image lineage, annotation granularity, cross-source de-duplication,
patient-level split, formal-test seal, and power/endpoint eligibility are
documented and source-hashed.

No model or dataset download, real-image training, GPU scale-up, or formal test
reveal is authorized merely by an R4 synthetic pass. Allocation 4161 must not
be cancelled or released by this protocol.
