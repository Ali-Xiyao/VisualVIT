# CAPES-CI v2 Post-Failure Calibration Protocol

Date frozen: 2026-07-19  
Evidence class: `POST_FAILURE_ENGINEERING_DIAGNOSTIC_NONCONFIRMATORY`  
Formal test: `SEALED`  
Supersedes: none; S075/v1 remains an immutable failed anchor

## Why v2 exists

S075 executed and reproduced exactly but could not identify persistent identity binding. Its label-generating state changes were directly visible through assignment-independent global/entity tokens, every training seed also changed the random frozen toy VLM, B4b development performance remained near chance, and the implemented A1/A2 label-direction gate did not match the written manipulation checks.

This protocol creates new run IDs. It must never rewrite S075, lower its thresholds, remove seed 29, or retroactively label S075 as passed.

## Frozen seed factors

- Trainable initialization seeds: `[17, 29, 43]`.
- Frozen toy-VLM seed: `91001`, identical for every training seed and every compared system.
- Existing data seeds for D1-D3: train `3401`, inner-development `4401`, development `5401`.
- v2 query-anchor data seeds: train `63401`, inner-development `64401`, development `65401`.
- Crossed derangement seeds for an evaluable v2 mechanism gate: `[81001, 81002, 81003]`.
- Failed/low seeds are retained. Infrastructure reruns must use the identical seed/config and preserve both attempts.

Each `derangement_id` uses the same case/patient-hash mapping for all training seeds. A B4a model is trained independently for every `(training_seed, derangement_id)` cell. B4b, learned and all derangement-independent systems are trained once per training seed; their weights and predictions must be bitwise invariant when paired across D. Effects are averaged within training seed over D before averaging over training seeds; the nine B4a cells are never treated as nine independent repetitions.

The run must record separate hashes for frozen VLM state, trainable initial state, complete initial state and final state. Frozen-VLM hashes must be equal across training seeds; within a seed, B4a/B4b trainable initial-state hashes must be equal.

## Diagnostic ladder

Each registered diagnostic changes exactly one factor from its parent.

### D1: fixed frozen VLM

Parent: S075. Change only the frozen toy-VLM initialization to seed `91001`; keep 80 steps, current v1 data, token contents, optimizer and all other settings.

Discriminating outcome: if Delta_bind signs/predictions stabilize materially, S075 seed variance was confounded by decoder changes. Regardless of outcome, D1 cannot repair the assignment-independent information bypass.

### D2: competence budget

Parent: D1. Change only training steps from 80 to 500. Add train five-label metrics; do not alter the loss, data or architecture.

Predeclared interpretation:

- train macro-F1 >=0.95 and development <=0.25: task/shortcut/generalization problem, not underfitting;
- train and development both materially improve: 80 steps caused absolute underfitting, but B4 identifiability still requires D3/v2;
- train macro-F1 <0.80: the frozen random readout/optimization path is incompetent; stop and replace the engineering readout before any mechanism estimate.

`Materially improve` is descriptive only and never controls admission to D3. D3 is eligible if and only if every registered seed's B4b train five-label macro-F1 is at least `0.80` and every D2 technical gate passes. Any seed below `0.80`, an incomplete registered seed bank, or any technical failure yields `FAIL_PREREQUISITE`; no across-seed mean may rescue it.

### D3: remove assignment-independent content bypass

Eligible only if D2 establishes train competence. Parent: D2. Change only token content: replace all 4 global and 28 entity payloads with the same neutral embedding for every system while retaining physical 64 tokens, token types, masks, positions, relation payloads, prompt, optimizer and budget.

Interpretation:

- every seed's Delta_bind is positive and mean Delta_bind >=5 pp: the v1 global/entity bypass was causal;
- B4b train high but development low: relation signal is fit but not generalizable under v1 data;
- B4 gap established but learned persistent assignment remains <0.40: classification-only matcher supervision is insufficient; no oracle matching loss may be added without a separately frozen oracle-free objective protocol.

All D1-D3 results are diagnostics. None can make the original anchor pass.

### R1: registered engineering-readout replacement after D2 stop

D2 failed its every-seed `0.80` admission rule, so D3 remains forbidden. The query-conditioned anchor therefore receives a new run family rather than modifying D2/D3:

- Replace the incompetent random frozen toy decoder with a deterministic, differentiable frozen causal-LM-shaped readout whose five registered label-token logits are the first five coordinates of the single query-relation embedding.
- Initialize one trainable query-relation projector from the public six-field anchor semantics `[constant, prior_state, current_state, real_mass, death_mass, birth_mass]`. The initialization is fixed before outcomes and contains no case label, hidden identity, oracle cardinality or dataset statistic.
- B4a and B4b receive separately trained copies from the same seed-specific projector state; learned-soft receives the same projector state plus its matcher. Only the assignment path may differ within a B4 pair.
- All 64 placeholders still pass through `ProjectedTokenBundle` and `FrozenVLMAdapter`; 63 projected payloads remain literal zero. A registered audit must prove that direct five-coordinate training logits and adapter label log-likelihoods differ only by a per-case constant, so their softmax loss and gradients are identical.
- This replacement is an engineering competence probe, not a CAPES-CI rescue, a pretrained-VLM result or paper evidence. A later full-token real-Qwen train/development bridge remains mandatory.

## v2 query-conditioned binding anchor

After D1-D3 diagnosis, build a new synthetic task whose label cannot be inferred from assignment-independent marginals.

### Visible versus hidden information

- A fixed binary query marker is model-visible and identifies the queried observation, not its hidden entity ID. Continuous or label-valued markers are forbidden.
- Gold persistent links may be constructed from hidden IDs, but model-visible IDs must be independently salted/relabelled in disjoint prior/current namespaces with no cross-time equality. Gold links live only in the separate oracle object.
- Learned and deterministic baselines receive the same visible query marker, coarse anatomy, validity and frozen features. They never receive gold match count, hidden ID, oracle cardinality or an oracle-derived top-K.
- Hidden IDs may not participate in query selection, sorting, slot routing, allocation, top-K, cardinality, cache keys or feature construction. Arbitrarily permuting or regenerating hidden IDs must leave every visible tensor, baseline cost, learned plan and score bitwise unchanged.

### Five-label construction

- For stable/worse/improved, the queried prior state is exactly 0 and the oracle-matched current queried state is respectively `0/+1/-1`.
- For new, the visible query marker occurs on a true current-side birth endpoint.
- For resolved, the visible query marker occurs on a true prior-side death endpoint.
- Distractor states are exactly counterbalanced across label, case and derangement so that the prior/current marginal multisets and all assignment-independent summaries are label-balanced.
- For the three persistent labels, query identity/slot/order/mask are sampled before label/state and are exactly balanced across labels. Each query compatibility group contains exactly six persistent endpoints, with two current endpoints at each state `-1/0/+1`. Six is the minimum feasible size: after removing any label-specific correct endpoint, three distinct wrong targets can still realize all three states without changing the current-side marginal multiset. The three registered derangements map the query to three distinct wrong targets with states `-1/0/+1`, and all three plan hashes must differ.
- Every case has the same total endpoint counts and exactly two death plus two birth endpoints. One predeclared, model-hidden carrier-control death/birth pair is excluded from the background-null count in every label; new/resolved place the visible marker on its current/prior side. The remaining background non-query null events are therefore exactly one death and one birth in every case. New/resolved necessarily expose a side-specific query carrier and are isolated as null controls rather than included in the persistent causal estimand.
- B4a and B4b retain identical null sets. New/resolved are therefore null-event controls, not evidence for the persistent-identity component of Delta_bind.

### Query relation gate

- Preserve `4 global + 28 entity + 28 relation + 4 reserved = 64` physical tokens, masks, token types and position IDs.
- Neutralize global/entity/reserved payloads and all non-query relation payloads with a literal fixed zero vector in projected space, identically for every system. The neutral value is not trainable.
- Preserve only the relation payload anchored to the visible query endpoint. Stable slot identity must derive from the visible source/query marker, not hidden gold identity.
- The same gate applies to B4a, B4b, learned, Hungarian and Sinkhorn. Assignment remains the only B4 difference.
- All non-query masks, positions, validity flags and physical slot indices remain label-invariant; neutralization may not create a mask/position side channel.

This is explicitly a **query-gated relation-mediator identification anchor**, not the complete CAPES-CI method. Passing it only shows that assignment matters in the controlled gated interface. A separately registered full-token train/dev bridge must later retain the effect before a full-method claim is considered.

## Structural survival checks before training

Training is forbidden unless all checks pass:

1. a deterministic oracle query-relation decoder recovers all five labels exactly;
2. wrong-persistent-query state is exactly counterbalanced with respect to the three persistent labels and derangement;
3. current-only and equal-budget separate-pooling controls over every model-visible feature channel, anatomy and marker cannot reconstruct the three persistent labels above the frozen development threshold; these controls may not perform cross-time pairwise attention, matching or equality joins;
4. gold-ID relabeling leaves learned plans, baseline costs and scores bitwise unchanged;
5. equality-joining model-visible IDs recovers zero gold persistent links, and arbitrary hidden-ID permutation/regeneration leaves all model-visible artifacts bitwise unchanged;
6. exact 64 tokens, physical masks/positions and frozen/no-pixel audits pass;
7. B4a has zero fixed points on persistent query endpoints and preserves null sets;
8. the mechanism gate refuses `D<3`, non-distinct query wrong targets and insufficient per-label development support.

The oracle decoder receives only the same model-visible tensors plus an assignment plan. It may not read labels or hidden entity/state fields.

## Frozen sample and optimization contract

- Synthetic unit is one independent case/patient.
- Per label: 16 train, 8 inner-development and 24 development cases; totals are 80/40/120.
- Every case has identical total prior/current endpoint counts, two anatomy groups, exactly six persistent endpoints in the query group, a matched fixed distractor structure, one fixed carrier-control null pair and the same one-death/one-birth background-null counts.
- Data order and full-batch/minibatch schedule are fixed and hashed. If minibatching is used, the exact patient order is common to every system.
- Training budget is 500 steps after the D2 competence diagnosis; optimizer, scheduler, learning rate and weight decay are identical for B4a/B4b and registered matched rows.
- The final fixed step is evaluated; there is no early stopping or checkpoint search. Inner-development is used only for prespecified deterministic baseline thresholds. Development is evaluated once per registered run and never used to change the run.

## Competence and mechanism gates

Gate order is fixed:

1. **Technical integrity:** all structural, feasibility, finite, exact-64, no-pixel and frozen audits pass.
2. **Working oracle:** B4b must reach five-label train/development macro-F1 >=0.90/0.75 and persistent-three-label train/development macro-F1 >=0.95/0.85 in every training seed. Otherwise the mechanism effect is `NOT_EVALUABLE_ANCHOR_INCOMPETENT`.
3. **Marginal-control identifiability:** current-only and equal-budget unordered prior/current controls must each remain at or below persistent-three-label development macro-F1 0.45 in every seed; otherwise the task still has a bypass. The 0.45 threshold is a frozen engineering tolerance above balanced three-class chance, not a significance test.
4. **Persistent binding:** define `M_pers` as macro-F1 over only stable/worse/improved, `Delta_(s,d)=100*(M_pers(B4b_s)-M_pers(B4a_(s,d)))`, `Delta_s=mean_d Delta_(s,d)` and `Delta_bind=mean_s Delta_s`. Every `Delta_s` must be positive, at least two of three derangement-cell effects must be positive within each training seed, and aggregate mean must be >=5 pp. New/resolved and the five-label metric are secondary and may not rescue this gate.
5. **Learned recovery:** use the same `M_pers` estimand and evaluate only after Gate 4 qualifies every seed-level denominator. Define `A_s=mean_d M_pers(B4a_(s,d))`, `B_s=M_pers(B4b_s)`, `L_s=M_pers(learned_s)`, `Recovery_s=(L_s-A_s)/(B_s-A_s)` and `Recovery=mean_s Recovery_s`. Recovery remains unbounded and is `NOT_EVALUABLE` if any `B_s-A_s<=0`. This gate passes only when `Recovery>=0.60` and `L_s-A_s>0` in every registered seed; a mean cannot hide a seed-level learned-method reversal. Five-label or null-control metrics cannot rescue it.
6. **Independent-process reproduction:** every registered non-runtime field must match exactly.

These thresholds are engineering survival gates, not formal significance claims or power inputs.

### B4 end-to-end fairness contract

B4a and B4b are separately trained from the same trainable initialization for each paired seed/cell. They share frozen VLM, visible tensors, query routing, null sets, allocation, token layout, prompt, data/batch order, optimizer/scheduler, step count and fixed-final-step checkpoint policy. During both training and development the only permitted difference is persistent real-real assignment and values causally downstream of that assignment. Training one model and swapping the plan only at inference is diagnostic and cannot estimate Delta_bind.

## Manipulations and metrics

- Rename the v1 whole-input intervention to `D_input_identity_channel_mask`; it is stress-only.
- Implement `D_match_only_identity_mask` so only pairwise real-edge identity utility/transport and its downstream query-relation payload may change; original regions, null logits, allocation and assignment-independent tokens remain bitwise equal.
- Rename v1 null collapse to `D_oracle_null_collapse`; report new/resolved target log probability, margin, NLL and score delta. It is not a trained ablation.
- A formal A1 requires matched retraining without pair-specific real-edge identity utility.
- A formal A2 requires matched retraining of a learned no-null variant. Deterministic cosine Sinkhorn is a baseline, not A2.

Assignment reporting is decomposed:

- hard patient-balanced persistent identity accuracy/F1;
- soft oracle-mass overlap/NLL/Brier, under separate names;
- birth and death precision/recall/F1 on null-positive cases;
- pooled three-component transport-mass macro only as a descriptive diagnostic.

## Required tests

- fixed VLM hash equal across trainable seeds while trainable initialization hashes differ;
- B4 pair same trainable initialization within seed;
- query prior state and distractor counterbalancing invariants;
- oracle decoder 100% and marginal-control non-identifiability;
- non-query payload neutralization with exact physical 64-token contract;
- hidden-ID relabeling invariance and no model-visible reconstruction;
- match-only identity intervention bitwise invariants;
- null-collapse locality and null-mass checks;
- persistent hard metrics separated from soft/pooled metrics;
- incompetent oracle returns `NOT_EVALUABLE`, never mechanism `FAIL` or `PASS`;
- `D<3`, tiny development support and nonpositive Recovery denominator fail closed;
- diagnostic interventions can never set `formal_ablation=true` or unlock a formal run.

## Stop rules

- Stop at the first failed gate; do not open broad baselines, real train/dev, formal ablations or sealed test.
- Do not add seeds, search a rescue menu or weaken thresholds after observing results.
- The learned single rescue remains ineligible until the B4 denominator is qualified on legal real train/dev data.
- Allocation `4161/tpami/gpu01` remains running and is not released or replaced.
