# R5 runner gate implementation specification

Date: 2026-07-22  
Scope: `scripts/run_query_anchor_r4.py`,
`scripts/run_query_anchor_r4_reproduction.py`, and their runner tests  
Evidence class: synthetic engineering, non-confirmatory  
Implementation status: specification only; this document does not authorize an
R4 artifact to be relabelled as R5.

## 1. Audit verdict

R5 must be a new protocol and new source-manifest authority. The current R4
runner is a useful engineering prototype, but it is not eligible for a formal
R5 registered run for the following implementation-level reasons.

- Gate 0 is evaluated only after `_build_strata()` has materialized every train,
  inner-development, and development tensor. A Gate-0 failure therefore does
  not prove that downstream development data was unread.
- `_train_transport()` discards `seed`; all trainable matcher replicas start
  from the same state, so three reported seeds are not three optimization
  initializations.
- `_null_accuracy()` pools rare positive null decisions with many negative
  decisions. It can pass while missing every death or every birth.
- The required hidden-ID relabel, endpoint-permutation, input-immutability, and
  B4 isomorphism counterfactuals are not complete in the runner gate trace.
- `_baseline_gate()` compares against fixed solvers but has no parameter- and
  compute-matched trainable local matcher without column competition.
- Baselines are scored with the main mediator-trained projector. This does not
  isolate assignment quality under a common readout and can favor the main
  assignment distribution.
- `baseline_plans_seed_invariant` is the literal constant `True`, not an
  observed cross-seed hash equality.
- Gate 7 checks exact-64 calls but not canonical candidate/token ordering, B4
  isomorphism, or preservation of the preregistered method ordering.
- Reproduction eligibility checks selected values but not an exact recursive
  schema. Unknown fields, wrong scalar types, non-finite nested metrics, and
  incomplete evidence can survive.
- The reproduction launcher does not preserve a launcher-level `failure.json`
  for `Popen`, log-write, child-summary parse, or certificate-write exceptions.

Every item in Sections 2-12 is **P0** unless explicitly marked **P1**. A P0
failure makes a registered R5 payload ineligible. P1 items improve diagnostics
but cannot weaken a P0 check.

## 2. P0: lazy gate execution and no premature downstream-development read

### Required code shape

Replace the eager beginning of `run()` with a lazy authority/data boundary.

1. `_resolve_run_request(args, raw_argv) -> ResolvedRun` validates CLI mode,
   seeds, step count, output-root uniqueness, protocol/config/source authority,
   environment, and command evidence. It must not call `_build_strata()`, any
   split generator, `_split_manifest()`, or any model/training function.
2. `_materialize_split(stratum, split, ledger) -> batch` is the sole registered
   split accessor. It appends `{gate, stratum, split, purpose, sha256}` to an
   append-only `data_access_ledger` before returning a batch. Direct calls to
   `make_frozen_r4_*_split` from `run()` or gate functions are forbidden.
3. `_run_gate_0_resolution(resolved)` has no split accessor in its signature.
4. Each later gate receives a restricted split provider whose allowlist is
   fixed by the matrix below. Requesting a split outside the current gate raises
   `PrematureDataAccessError` and produces a technical `failure.json`.
5. On every stop, `data_access_ledger` is emitted and checked against the
   expected prefix. The stopped summary may contain evidence from completed
   gates only; downstream gate keys and downstream split hashes must be absent.

| Gate | Maximum permitted materialization |
|---|---|
| 0 resolution/freeze | none |
| 1 structural/input | frozen structural audit fixtures only; no label-scored development evaluation |
| 2 fixture identifiability | train and fixture-development required by oracle/marginal/B4 competence only |
| 3 transport competence | transport train, inner-development, then clean development after the checkpoint is frozen |
| 4 anti-equivalence | challenge development after Gate 3 passes |
| 5 mediator recovery | mediator train; development only after matcher and readout checkpoints are frozen |
| 6 fair baseline | baseline train; common-readout development after all baseline checkpoints are frozen |
| 7 exact-64 bridge | no new split; reuse immutable Gate-6 development snapshots |
| 8 reproduction | no direct data access; validate two child payloads |

The runner may cache an already authorized split, but a cache hit must be
recorded as such. Gate 1 must not compute label metrics. Gate 2 may use its
authorized fixture development data because those metrics constitute Gate 2;
it must not train or evaluate the transport matcher. Inner-development may be
logged during a training stage only if R5 explicitly freezes a checkpoint
selection rule; the current final-step-only rule must not read
inner-development until training is complete.

### Function-level changes

- `run()`: resolve Gate 0 first; construct `SplitAccessLedger` only after Gate 0
  passes; dispatch one gate at a time; return immediately on failure.
- `_build_strata()`: remove from the registered control flow or split into lazy
  `_load_clean_split()` / `_load_challenge_split()` helpers used only by the
  restricted accessor.
- `_r4_split_manifest()`: replace with `_split_manifest_for_accessed_data()`;
  it must never materialize missing splits as a side effect.
- `_stopped_summary()`: add `data_access_ledger` and
  `data_access_prefix_valid`; reject downstream fields rather than merely
  omitting their gate records.

### Mandatory negative tests

- Monkeypatch every split generator to raise; force Gate 0 failure; assert no
  generator was called and no split hash exists in the summary.
- Force each gate to fail in turn and attach spies to every later split/model
  function; assert zero downstream calls and exact ledger prefix.
- Make Gate 1 request `development` label metrics; assert
  `PrematureDataAccessError`, nonzero CLI exit, and `failure.json`.
- Mutate the final-step-only code to read inner-development inside the training
  loop; the ledger/order test must fail.

## 3. P0: complete Gate-0 resolver

### Required resolver output

`_resolve_run_request()` must return a fully canonical, JSON-serializable object
and `_resolution_gate()` must validate all fields below without touching data:

- exact R5 protocol ID, evidence class, registered status vocabulary, gate
  order, seed tuple `17/29/43`, step count, CPU device, smoke/dry-run semantics;
- source-manifest closed allowlist including the R5 protocol, runner,
  reproduction launcher, calibration source, matcher source, exact tests,
  `pyproject.toml`, and this specification; no missing or unexpected authority
  file;
- exact SHA-256 of each file and canonical manifest hash;
- every threshold, null-utility cap, residual cap, Sinkhorn setting, optimizer,
  learning rate, gradient clipping, initialization distribution/scale,
  per-seed initialization derivation, local-baseline definition, exact-64
  ordering, B4 transformation, checkpoint rule, and eligibility schema version;
- analytic margin certificate including the maximum bounded residual effect and
  maximum two-sided null alternative; no unbounded learned null term;
- canonical command, resolved executable, runner path, cwd, raw argv, parsed
  argv, start timestamp, runtime/environment contract, and output-root path;
- output root does not pre-exist at CLI entry and its parent is writable;
- formal test remains sealed, formal-data authorization is `HOLD`, and every
  scientific/formal claim flag is false;
- recursive rejection of placeholder markers including `MUST_RESOLVE`, `TODO`,
  `TBD`, `FIXME`, `CHANGEME`, `None` in required fields, and non-finite numbers.

Gate 0 must compare `config` against a programmatically constructed expected R5
config, not only scan its serialized text. It must emit one boolean per resolved
item plus a `resolver_schema_version`. A missing check is failure, not a skipped
check.

### Function-level changes

- `_registered_config()`: make it the single canonical constructor; include all
  newly resolved R5 constants and exact schemas.
- `_source_manifest()`: use a closed explicit allowlist; replace R4 protocol
  authority with R5 and add the R5 tests/specification.
- `_runtime_environment()`: add PyTorch build/CUDA availability, locale,
  timezone, thread/inter-op thread counts, deterministic debug mode, and the
  whitelisted environment contract. Do not dump secrets or the full environment.
- `_resolution_gate()`: exact-key/type/value validation; verify manifest hash,
  protocol hash, output-root condition, environment contract, and certificate.

### Mandatory negative tests

- Parametrize deletion or mutation of every required resolver field; every case
  must return `FAIL_RESOLUTION_FREEZE` before any data access.
- Insert an unknown config key, non-finite threshold, boolean where an integer is
  required, stale R4 protocol path, or unresolved marker; all must fail.
- Pre-create the output root and invoke the CLI; fail without overwriting it.
- Change one source byte after manifest construction; authority recheck must fail.

## 4. P0: seed-specific small random initialization with auditable diversity

### Frozen behavior

R5 must resolve an initialization rule before dry-run. Recommended contract:

- instantiate the matcher from deterministic zero/default construction;
- use a local `torch.Generator(device="cpu")` seeded from
  `SHA256(protocol_version || "transport-init" || seed)` reduced to a documented
  63-bit integer;
- overwrite every registered trainable scalar/tensor with independent
  `Normal(0, INIT_STD)` draws, where `INIT_STD` is frozen in the R5 protocol;
- do not call global `torch.manual_seed()` and do not allow the seed or generated
  values to enter matcher inputs;
- record derivation string, derived integer, generator device, distribution,
  scale, per-parameter tensor hash, and full initial state hash.

The initialization must be deterministic for a repeated seed, different across
17/29/43, finite, within a preregistered absolute bound, and small enough that
the analytic clean optimum remains protected. Diversity is not established by
different seed labels; it is established by distinct observed initial state
hashes.

### Function-level changes

- `_new_matcher(seed: int | None, *, initialization_kind: str)` replaces the
  seedless constructor. `seed=None` is allowed only for explicitly fixed
  nontrainable references.
- Add `_initialize_trainable_matcher(matcher, seed) -> InitEvidence`.
- `_train_transport()`: remove `del seed`; include `seed`, initialization
  evidence, initial parameter hashes, and final parameter hashes in its result.
- `_transport_gates()`: require three distinct initial hashes, correct seed-to-
  hash mapping, and exact re-derivation of each initial hash.

### Mandatory negative tests

- Same seed twice gives byte-identical parameters and hashes; 17/29/43 give
  three distinct hashes.
- Global RNG consumption before construction does not change initialization.
- Swapping a reported seed/hash pair, using zero initialization, exceeding the
  bound, or omitting one parameter hash fails Gate 3 and eligibility.
- A tiny-init margin-certificate test proves every allowed initialization
  remains within the frozen perturbation budget.

## 5. P0: counterfactual structural audits

All counterfactuals operate on cloned audit fixtures, never registered training
or development tensors. Each audit records original, transformed, and restored
hashes plus exact/max-error comparisons. Counterfactual constructors may read
the oracle only to construct the audit transformation; the evaluated matcher,
allocator, projector, and adapter must receive only their normal visible inputs.

### 5.1 Hidden-ID relabel

Add `_hidden_id_relabel_audit(batch, matcher, frozen_readout, adapter)`.

- Apply independent bijections to prior/current `RegionBatch.*_entity_ids` and
  hidden oracle IDs while preserving equality relations required by the gold
  assignment. Visible image features, masks, anatomy, query markers, labels,
  and plan are unchanged.
- Require exact equality of sanitized matcher inputs, utilities, soft/hard plan,
  relation candidates, allocation weights/order, exact-64 token bundle,
  adapter scores, and predicted labels.
- Also prove the hidden/oracle hash changed, so the test is not vacuous.

Negative tests: leak entity IDs into one edge utility, allocator tie-break, or
token source-order key; each mutation must change an audited artifact and fail
Gate 1. An identity relabel must be rejected as a vacuous counterfactual.

### 5.2 Endpoint permutation equivariance

Add `_endpoint_permutation_audit(batch, matcher, frozen_readout, adapter, seed)`.

- Generate independent non-identity prior/current permutations per case using a
  registered audit seed. Permute every endpoint-aligned visible tensor, marker,
  optional metadata field, validity/anatomy field, and the oracle plan for audit
  comparison. Keep dustbin row/column fixed.
- Run the normal pipeline on the permuted batch, inverse-permute utilities,
  plans, candidates, and source-indexed allocation evidence, then require exact
  hard-plan equality and tolerance-bounded floating equality for soft plans,
  tokens, and scores. Restored predicted labels must be identical.
- Record permutation/inverse hashes and prove each permutation is non-identity.
  Stable ordering must use an equivariant content key; raw slot index is not an
  allowed tie-break.

Negative tests: leave one optional endpoint tensor unpermuted; permute the
dustbin; sort on slot index; or use the same permutation on only one side. Each
must fail. A test with tied utilities is mandatory because index tie-breaks can
appear equivariant on untied fixtures.

### 5.3 Tensor immutability

Add `_tensor_snapshot(tree)`, `_assert_snapshot_unchanged(snapshot, tree)`, and
`_assert_counterfactual_disjoint(original, transformed)`.

- Snapshot every tensor reachable from train, fixture-development, and
  development batches: path, shape, dtype, device, stride, storage offset,
  value SHA-256, and storage data pointer for diagnostic use.
- Take snapshots before and after competence probes, counterfactual builders,
  all training stages, and all evaluation stages. Registered source tensors must
  be bitwise unchanged.
- Counterfactual tensors must not share storage with source tensors, even when a
  field was semantically unchanged; clone it. In-place views are forbidden.
- Summary/certificate evidence uses content hashes, not data pointers, because
  pointers are process-specific and excluded from canonical reproduction.

Negative tests: mutate one source element in-place, mutate through a view, alter
dtype/stride without changing values, or alias an unchanged counterfactual
field. Each must be detected at the stage that caused it.

### 5.4 B4a/B4b exact isomorphism

Add `_build_b4_pair(batch, derangement_seed)` and
`_b4_isomorphism_audit(pair, frozen_readout, adapter)`.

- B4b uses the oracle persistent assignment. B4a uses the preregistered
  anatomy-compatible derangement. They share the identical batch object/value
  snapshot, labels, query, features, masks, anatomy, null decisions, source
  universe, frozen models, adapter, allocation policy, exact-64 budget, prompt,
  call order, and scoring code.
- The allowlisted differences are only: assignment tensor/mode/hash and the
  causally downstream relation/change tensors, selected source IDs/order where
  mathematically induced by that assignment, token values at relation/change
  positions, and final scores/predictions.
- Unary/entity tokens, token types, valid/attention masks, position IDs,
  placeholder count, physical token positions, optimizer state, parameter
  hashes, and adapter-call trace must be exact. A recursive structural diff must
  report no non-allowlisted path.
- B4a must be non-oracle, anatomy-compatible, valid under the same null/support
  contract, and have a changed plan hash. B4b must exactly equal oracle plan.

Negative tests: change a query, label, null decision, seed, token mask/position,
source universe, or model state in only one branch; isomorphism must fail with
the exact offending path. Make B4a equal B4b; the audit must reject the vacuous
pair.

### Gate placement

- Gate 1: hidden-ID, endpoint-permutation, forbidden-channel, and immutability
  checks at matcher/allocator/interface level.
- Gate 2: B4 plan validity, non-vacuity, and recursive isomorphism before label
  recovery is interpreted.
- Gate 7: repeat hidden-ID/permutation/B4 checks through the exact-64 adapter and
  require their score invariants.

## 6. P0: class-balanced and exact null metrics

Replace `_null_accuracy()` with `_null_metrics(batch, hard)`. Report death and
birth separately and never allow ordinary accuracy to gate by itself.

For each event type report `tp/fp/fn/tn`, precision, recall, F1, balanced
accuracy, positive support, predicted-positive support, exact event-set match
per case, and aggregate micro/macro values. Define zero-denominator behavior in
the protocol: a positive-support split with zero predictions has precision `0`,
recall `0`, F1 `0`; a split with zero gold support is ineligible for the clean
null gate rather than assigned a perfect score.

Gate 3 must require, for every seed on clean development:

- frozen R5 thresholds for death precision/recall/F1;
- frozen R5 thresholds for birth precision/recall/F1;
- class-balanced null macro-F1 threshold;
- exact death-set, birth-set, and joint-null case-match thresholds;
- positive support for both event types;
- null predictions consistent with the hard transport residual and feasibility
  checks.

Ordinary null decision accuracy may remain a P1 diagnostic labelled
`non_gating_accuracy`.

### Function-level changes

- `_null_accuracy()` -> `_binary_event_metrics()` plus `_null_metrics()`.
- `_transport_metrics()`: nest the full null schema under `null_metrics`.
- `_transport_gates()`: gate exact named metrics; emit per-seed confusion counts
  and threshold comparisons.
- `_transport_result_eligible()`: exact-validate the null schema and supports.

### Mandatory negative tests

- Predict no deaths/births on the clean split: ordinary accuracy may be high but
  Gate 3 must fail.
- Predict all endpoints as null: recall may be high but precision/exact-set gates
  fail.
- Perfect deaths with zero birth recall fails; perfect births with zero death
  recall fails.
- Remove all positive births from an audit fixture; mark ineligible rather than
  pass by convention.
- Tamper with confusion counts so they do not sum to support; schema eligibility
  fails.

## 7. P0: matched trainable local baseline without column competition

R5 needs a trainable control that changes only the global allocation mechanism.
Call it `TrainableLocalIndependentMatcher` in evidence; the implementation may
reuse the main matcher utility module but must expose a distinct local-plan
representation if `MatchPlan.validate()` would incorrectly imply column
capacity.

### Frozen comparison contract

- Same visible input wall, support mask, identity views, learned utility/null
  parameterization, parameter count, seed-specific initializer, optimizer,
  learning rate, weight decay, gradient clipping, train batches, oracle
  supervision targets, number of optimizer steps, and final-step-only checkpoint
  rule as the main matcher.
- Replace only the global partial-OT/Hungarian column-capacity allocator with
  independent row-local normalization over anatomy-compatible current endpoints
  plus prior-null. Current-null/birth evidence is produced by the frozen local
  rule resolved in R5. No operation may renormalize, cap, sort, or select using
  competition among two prior rows for the same current column.
- The downstream relation candidate builder must consume the local weights
  directly and produce the same candidate/token budget. It must not silently
  project the local weights back through OT, Hungarian, greedy one-to-one, or a
  column-normalizing Sinkhorn.
- Report duplicate-current rate, column-overcommitment mass, row-normalization
  error, null metrics, parameters, FLOP/proxy operation count, wall time, and
  all state hashes. The baseline is invalid if it accidentally has no observed
  column conflict on the registered challenge fixture.
- Main versus local baseline comparison is per seed and aggregate under the
  common oracle-frozen readout in Section 8. Thresholds and primary estimand
  (assignment/recovery difference) must be frozen in Gate 0.

### Function-level changes

- Add `_new_local_baseline(seed)`, `_train_local_baseline()`,
  `_local_baseline_metrics()`, and `_local_baseline_gate_checks()`.
- Replace `_baseline_gate()` with a gate that includes fixed Hungarian,
  Sinkhorn, and the trainable local control. Do not describe the fixed equal-view
  matcher as the strongest trainable baseline.
- Extend result stripping, Gate-6 output, and eligibility for the local model,
  optimizer ownership, gradient counts, hashes, compute budget, and plan type.

### Mandatory negative tests

- Spy on the local allocator and fail if it calls OT, Sinkhorn, Hungarian,
  greedy one-to-one, top-k across rows, or any column normalization.
- A two-prior/one-current collision fixture must allow both row-local matches and
  report column overcommitment; forcing one-to-one must fail the baseline
  identity audit.
- Add/remove one trainable parameter or one training step; matched-envelope
  eligibility fails.
- Train the local baseline with a different batch order, dev selection, seed
  rule, or optimizer setting; Gate 6 fails before performance comparison.
- A local result with no column conflict on the challenge fixture is ineligible.

## 8. P0: one common oracle-frozen readout for fair assignment comparison

The primary Gate-6 assignment comparison must use one readout per seed that is
fit once on oracle plans, frozen, and reused unchanged for every method. Current
`mediator_results[seed]["model"]` must not be the comparison readout.

### Required flow

1. `_fit_common_oracle_readout(seed, ...)` fits exactly once using oracle plans
   and the registered joint clean/challenge training schedule.
2. Freeze projector and adapter; hash both.
3. Score, without refitting, the oracle upper bound, main matcher, trainable
   local baseline, fixed Hungarian, fixed Sinkhorn, and B4a/B4b using the exact
   same readout instance, evaluation batch, adapter, prompt, and call helper.
4. Record a readout identity hash in every result and require one unique hash per
   seed across all methods. Record `fit_count=1` and `post_freeze_update_count=0`.
5. Gate 5 may still train a separately named main mediator/readout as an
   end-to-end engineering diagnostic, but its metrics cannot be substituted for
   the Gate-6 fair comparison and must use a disjoint result key.

The common readout makes the comparison assignment-sensitive; it does not turn
the oracle control into a deployable method.

### Function-level changes

- Rename the current oracle stage result to `common_oracle_readout_results` and
  preserve the model internally until all comparisons finish.
- Generalize `_score_frozen_readout()` to record readout object/state identity,
  exact call order, plan/contract/token hashes, and zero parameter changes.
- `_baseline_gate()`: accept common oracle readouts, not mediator readouts.
- `_bridge_gate()`: require the common-readout identity equality across every
  main/baseline/B4 score.

### Mandatory negative tests

- Refit or clone-and-perturb a readout for one baseline; common-hash gate fails.
- Pass the mediator-trained readout to Gate 6; type/stage identity check fails.
- Change one projector parameter after the first score; all later results become
  ineligible and the before/after state audit identifies the call.
- Omit oracle, main, local, one fixed solver, B4a, or B4b from the common score
  bank; exact method-key schema fails.

## 9. P0: observed fixed-baseline seed-invariance evidence

Delete the literal `"baseline_plans_seed_invariant": True`.

For every fixed baseline, stratum, and authorized split, materialize the plan in
three independent calls under seeds 17/29/43 (or explicit seed-neutral contexts
that still perturb global RNG state between calls). Record the plan SHA-256,
contract SHA-256, token-order SHA-256, and adapter-input SHA-256 per seed. Gate 6
passes seed invariance only if each hash family has cardinality one and the
observed method output is bitwise equal. Also record a hash of the complete
seed-to-hash map so the evidence cannot be replaced by a boolean.

The trainable local baseline and main matcher are expected to have distinct
initial hashes; they are not subject to fixed-plan seed invariance.

### Function-level changes

- `_r4_fixed_assignment_baseline_plans()` -> seed/context-aware fixed baseline
  materializer with no trainable state.
- Add `_observed_seed_invariance(evidence_by_seed)` and include its full evidence
  in `_baseline_gate()`.
- Eligibility requires the exact seed set and recomputes the unique-hash counts.

### Mandatory negative tests

- Alter one seed's plan, token order, contract, or adapter input while leaving a
  legacy boolean `True`; Gate 6 and eligibility fail.
- Omit or duplicate a seed key; fail.
- Consume global RNG inside a fixed baseline; the repeated-context test must
  expose output drift.

## 10. P0: exact-64 bridge ordering and isomorphism

Gate 7 must certify the bridge, not merely count calls.

### Canonical execution order

Freeze in Gate 0 one exact method order, for example:
`oracle`, `main`, `local_independent`, `fixed_hungarian`, `fixed_sinkhorn`,
`B4b_oracle`, `B4a_deranged`. For each seed, stratum, and split, `_bridge_gate()`
must execute this order with the common oracle-frozen readout and an append-only
`exact64_call_ledger`. No method may be reordered by performance, loss, hash,
or data-dependent condition.

For every call record method, seed, stratum, split, ordinal, plan/weight hash,
candidate-order hash, allocation hash, token-value hash, token-type hash,
valid/attention-mask hash, position-ID hash, placeholder-position hash,
projected-embedding hash, readout hash, adapter hash, score hash, and physical
placeholder count `64`.

Gate 7 requires:

- exact ledger order and exact expected call count;
- all interface/frozen-state/no-pixel checks;
- hidden-ID and restored endpoint-permutation score invariance;
- B4 recursive isomorphism outside its allowlist;
- same common-readout hash for every method within a seed;
- preservation of the Gate-6 preregistered ordering/margins through adapter
  scores, using the exact frozen estimand; ties or missing methods fail;
- no new split access and no parameter update during the bridge.

P1 diagnostic: report rank correlations among assignment accuracy, pre-adapter
probe score, and exact-64 adapter score. It is non-gating unless frozen into R5.

### Mandatory negative tests

- Swap two method calls, skip a call, duplicate a call, or evaluate only methods
  that already passed; exact ledger validation fails.
- Keep 64 tokens but permute token order, attention/position IDs, or placeholder
  positions for one method; Gate 7 fails.
- Reverse a required main-versus-local ordering after the adapter; Gate 7 fails.
- Run a hidden-ID/permutation audit only before the adapter; missing bridge-level
  audit keys make eligibility fail.

## 11. P0: strict recursive eligibility schema

Replace boolean helpers `_readout_result_eligible()` and
`_transport_result_eligible()` with schema validators returning
`{passed, errors}`. Each error is a JSON path plus expected and observed type or
constraint. `_registered_reproduction_eligibility()` must validate the complete
summary before comparing it with current authority.

### Schema rules

- Pin `summary_schema_version` and a distinct schema version for every nested
  result family.
- Exact key sets at every registered object; unknown and missing keys fail.
- Exact scalar types: reject `bool` as `int`; reject numeric strings; reject NaN
  and infinities recursively.
- Exact seed, stratum, split, method, gate, parameter-name, and metric key sets.
- Exact list order where order is semantic; exact set expressed as sorted lists
  where order is not semantic.
- Validate all SHA-256 strings, UUIDs, absolute paths, timestamps with timezone,
  nonnegative counts, count totals, confusion-matrix arithmetic, threshold
  comparisons, state transitions, optimizer ownership, gradient-step counts,
  data-access prefixes, and exact64 ledger ordinals.
- Recompute all derived booleans, averages, deltas, unique-hash counts, canonical
  config/source/split hashes, gate records, status, stopped/not-run suffix, and
  eligibility outcome. Never trust stored `passed=True`.
- A registered success has exactly Gates 0-7, no failure object, exactly
  `not_run_gates=["independent_reproduction"]`, and no formal-data result.
- A stopped result has one failed gate, the exact completed prefix, and no keys
  from later stages.
- Canonical reproduction excludes only explicitly frozen volatile paths. Do not
  exclude command, config, environment contract, split/source hashes, ledgers,
  state hashes, or metrics. Volatile-field exclusions themselves are exact-
  schema validated.

### Function-level changes

- Add `_validate_exact_keys()`, `_validate_scalar_type()`,
  `_validate_finite_tree()`, and family validators for resolver, access ledger,
  audit, readout, main transport, local baseline, fixed baselines, B4, exact64,
  gates, and full summary.
- `_canonical_reproduction_payload()`: use a versioned exact exclusion list and
  reject any unrecognized volatile field.
- `_compare_independent_reproduction()`: report eligibility errors and mismatch
  paths for both children; canonical equality cannot rescue ineligibility.

### Mandatory negative tests

- Property/parameterized deletion, insertion, type corruption, NaN/Inf, bad
  hash, wrong seed, reordered ledger, inconsistent average, forged `passed`, and
  downstream key after stop for every result family.
- Two identically malformed child summaries must fail despite canonical equality.
- A success payload with a hidden extra field fails.
- A stop payload containing cached downstream development hashes fails.

## 12. P0: launcher exception evidence and complete provenance

### Main runner evidence

Every summary and failure must include:

- protocol/schema/evidence versions;
- UTC start/end timestamps and monotonic elapsed time;
- exact command list, raw argv, parsed arguments, executable and runner hashes,
  resolved cwd, PID, process UUID, hostname, and parent/Slurm identifiers when
  present;
- whitelisted deterministic environment contract and runtime versions;
- canonical config and hash, source manifest and hash, accessed split manifests
  and hashes, data-access ledger, seed/init evidence, and gate prefix;
- formal test/data/claim flags explicitly closed.

Do not include secrets, tokens, the full environment, or unstable memory
addresses in canonical evidence.

### Reproduction launcher transaction

Wrap parser post-processing, output-root creation, child launch, log writes,
summary parse, eligibility validation, comparison, and certificate write in a
top-level fail-closed transaction. Add
`_write_launcher_failure_safely(stage, error, context)`. On any exception it
best-effort writes `<run-dir>/failure.json` atomically via a temporary file and
rename, prints its path, and exits nonzero.

The launcher failure schema includes stage, exception type/message/traceback,
UTC timestamps, launcher command/cwd/PID/UUID/source hash, whitelisted child
environment, child command(s), child PID/return code where known, stdout/stderr
log paths and raw hashes where written, child `summary.json`/`failure.json`
paths and hashes where present, config/source authority capture or its capture
error, and all formal claim flags false. A child technical failure is referenced
by raw hash and is never rewritten as a method failure.

The launcher must:

- launch process B only after process A exits zero, has the exact pending R5
  status, and passes strict eligibility;
- refuse to overwrite any child/certificate/failure artifact;
- write stdout/stderr logs for every launched child even on parse failure;
- fsync/atomically publish the final certificate where supported;
- return zero only for exact `PASS_R5_SYNTHETIC_ENGINEERING`.

### Function-level changes

- Main `main()`: include resolver/command evidence even for failures occurring
  before `run()`; atomically write `failure.json` without masking the original
  exception.
- Reproduction `_run_child()`: return a typed launch record with command,
  whitelisted env, timestamps, PID, return code, log hashes, summary/failure
  hashes, and parse outcome.
- Reproduction `run()`: validate primary eligibility before launching replica;
  validate replica independently before comparison.
- Reproduction `main()`: add the top-level transaction and strict exit-status
  mapping.

### Mandatory negative tests

- Inject exceptions at `Popen`, `communicate`, each log write, summary read,
  JSON parse, eligibility, comparison, and certificate write. Every case exits
  nonzero and preserves a launcher `failure.json` with the correct stage.
- Child A exits zero with missing/malformed/ineligible summary: B is not
  launched.
- Child A writes `failure.json`: launcher records its raw hash and does not call
  it a scientific stop.
- Existing run directory or artifact collision fails without overwrite.
- Remove `PYTHONHASHSEED`, change thread variables, cwd, config, or split hash in
  one child; eligibility fails before canonical comparison.

## 13. P1 diagnostics that must remain non-gating unless preregistered

- Per-stage CPU time, peak RSS, and optimizer-step throughput.
- Gradient norm quantiles and local/main parameter-update norms.
- Soft-plan entropy, duplicate-current distribution, and null calibration bins.
- Compact human-readable `gate_summary.md` generated only from the validated
  JSON evidence. JSON remains authoritative.

P1 diagnostics must never be used for checkpoint selection, rerun selection, or
post-hoc threshold changes.

## 14. Minimum R5 test matrix and release order

Implementation is not ready for an R5 dry-run until all of the following pass
under the deterministic environment contract:

1. focused unit tests for resolver and schema corruption;
2. structural counterfactual tests, including tied-utility permutations;
3. seed initialization determinism/diversity/margin tests;
4. class-balanced null metric adversarial tests;
5. local-no-column-competition identity and fairness tests;
6. common oracle-readout and B4 isomorphism tests;
7. stop-first-fail/data-access tests for every gate;
8. exact64 order/tamper tests;
9. launcher fault-injection tests;
10. full test suite, Ruff check, Ruff format check, and compile check.

Only then may a new immutable R5 dry-run directory be created. The order after
that is dry-run, one-seed smoke, three-seed registered local run, and two fresh
sequential reproduction processes. A source/config/protocol change after the
R5 dry-run supersedes that dry-run and requires a new version or an explicitly
authorized preregistered revision rule. No R4 dry-run or smoke artifact may be
promoted, copied, or renamed into R5 evidence.

## 15. P0 acceptance checklist

- [ ] Gate 0 reads no split and resolves every new R5 constant/schema.
- [ ] Every stop has an exact data-access and gate-prefix proof.
- [ ] Seed 17/29/43 initial matcher hashes are deterministic and distinct.
- [ ] Hidden-ID, endpoint-permutation, tensor-immutability, and B4 audits pass at
      both structural and exact64 boundaries.
- [ ] Death and birth precision/recall/F1 plus exact-set metrics gate separately.
- [ ] Trainable local control is matched and demonstrably has no column
      competition.
- [ ] Gate 6 uses one common oracle-frozen readout per seed for every method.
- [ ] Fixed baseline seed-invariance is measured by actual hash maps.
- [ ] Gate 7 enforces canonical method/token/call order and ranking/margins.
- [ ] Full summaries and stopped summaries pass strict recursive schema checks.
- [ ] Every launcher exception produces non-overwriting `failure.json` evidence.
- [ ] Command/runtime/environment/config/source/accessed-split evidence is
      complete and secret-safe.
- [ ] Reproduction process B is never launched after an ineligible process A.
- [ ] Formal-data authorization remains `HOLD`; all claim flags remain false.
