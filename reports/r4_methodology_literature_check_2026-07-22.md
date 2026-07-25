# R4 Methodology Literature Check

Date: 2026-07-22  
Scope: primary/official sources most likely to challenge the CAPES-CI QPTM method claim  
Verdict: `PROCEED_WITH_CAUTION`

## Claim boundary

No direct precedent was found that jointly enforces all four properties below:

1. explicit cross-time persistent entity transport;
2. a matcher that is sealed from the query;
3. query gating only after transport, over relation/change mediation;
4. a fixed visual-token budget with direct mediator interventions.

The individual ingredients are already well represented. Therefore the paper must not claim novelty for Sinkhorn, Hungarian, partial/unbalanced OT, dustbins, longitudinal change encoding, or object/event slots. The narrow defensible object is:

> A query-sealed, null-aware persistent-entity transport that compresses identity retention, appearance/disappearance, and directional change into a fixed-budget, intervention-ready mediator; the query may only read this mediator after transport.

## Closest primary sources and required distinction

| Work | Direct overlap | Required distinction for QPTM |
|---|---|---|
| [BiOTPrompt, CVPR 2026](https://openaccess.thecvf.com/content/CVPR2026/html/Liu_BiOTPrompt_Bidirectional_Optimal_Transport_Guided_Prompting_for_Disease_Evolution-aware_Radiology_CVPR_2026_paper.html) | longitudinal chest-X-ray OT and change-aware prompting | patch-level balanced OT for report generation; QPTM must prove explicit persistent/null identity, query sealing, fixed tokens and mediator intervention |
| [D2MNet, Journal of Imaging 2026](https://pubmed.ncbi.nlm.nih.gov/42042505/) | question-independent difference representation followed by question/change prompts | spatially aligned feature difference rather than cross-time entity assignment with null transport |
| [RegioMix, MICCAI 2024](https://papers.miccai.org/miccai-2024/645-Paper2219.html) | region-level pseudo-difference followed by question alignment | retrieved/anatomy-indexed regions rather than patient-specific persistent transport |
| [EKAID, KDD 2023](https://arxiv.org/abs/2307.11986) | two-time-point anatomical graphs and graph difference for medical difference VQA | fixed anatomical nodes rather than learned partial assignment for same-type multiple entities and birth/death |
| [Unbalanced OT for Longitudinal Lesion Evolution, ISBI 2026](https://arxiv.org/abs/2602.09933) | UOT for longitudinal lesion correspondence, appearance/disappearance and merge/split | lesion matching without VLM, query-sealed mediation or fixed context budget; UOT itself is not novel here |
| [Slot-VLM, NeurIPS 2024](https://openreview.net/forum?id=7Hb03vGcJk) | fixed object/event slots for temporal language reasoning | no explicit prior-current persistent identity transport or two-sided-null relation mediator |
| [MESH, ICML 2023](https://proceedings.mlr.press/v202/zhang23ba.html) | OT view of slot attention and learned cost/tie breaking | feature-to-slot grouping rather than prior-current identity transport and causal change audit |
| [TILA, CVPR 2026](https://openaccess.thecvf.com/content/CVPR2026/papers/Ko_Temporal_Inversion_for_Learning_Interval_Change_in_Chest_X-Rays_CVPR_2026_paper.pdf) | temporal inversion and direction consistency in chest X-rays | no entity transport, but it makes time-reversal equivariance a required evaluation |
| [TempA-VLP, WACV 2025](https://openaccess.thecvf.com/content/WACV2025/html/Yang_TempA-VLP_Temporal-Aware_Vision-Language_Pretraining_for_Longitudinal_Exploration_in_Chest_X-ray_WACV_2025_paper.html) | longitudinal progression representation and phrase grounding | no persistent assignment, null identity or fixed mediator budget |
| [MOTOR, MICCAI 2025](https://papers.miccai.org/miccai-2025/0586-Paper2665.html) | OT used in medical difference VQA | OT reranks query/retrieval context rather than transporting same-patient entities across time |

## Mandatory comparison families

- Task methods: EKAID, PLURAL, ReAl, RegioMix, VED, D2MNet, LUMEN.
- Longitudinal representation: TempA-VLP and TILA; BiOTPrompt when report generation is in scope.
- Matching: spatial/anatomy-indexed difference, registration plus residual, cosine Hungarian, balanced Sinkhorn, bidirectional OT, dustbin/partial OT, UOT and learned contextual cost.
- Fixed-budget compression: mean pooling, Perceiver/Q-Former, Slot-VLM-style slots, random and top-K tokens, all with the same token count.
- Query placement: no query, query in matcher, query only after transport, query directly in decoder; parameter and compute matching are mandatory.
- At least two encoder/VLM backbones and both frozen and fine-tuned settings if the data/license gates permit them.

## Decisive ablations and audits

- Remove persistent identity, two-sided null, relation, directional change, and contextual cost one at a time.
- Compare post-transport query gate against early query-conditioned matching and ordinary cross-attention/pooling.
- Sweep token budget `K=16/32/64/128`, while keeping each comparison exactly matched at a given K.
- Time reversal must swap improved/worsened and new/resolved under a preregistered mapping.
- Query substitutions, paraphrases, irrelevant questions and adversarial questions must leave the transport plan numerically unchanged.
- Endpoint permutation must yield transport equivariance and restored-answer invariance.
- Relation-token interventions should change only the corresponding factual answer, not unrelated entities.
- Report persistent assignment and birth/death accuracy separately from final VQA/report metrics.
- Report parameters, FLOPs, memory and latency; measure the amortized benefit of caching one transport plan for multiple questions on the same image pair.

## Important inference to verify, not overstate

BiOTPrompt's paper equations appear to combine fixed uniform balanced-OT marginals with row/column-sum thresholding for new/disappeared regions. Under exact balanced OT, those sums are fixed by construction, so the threshold statistic would not depend on image content. This is an inference from the published formulation, not a verified statement about its released implementation. It motivates an explicit partial/null transport baseline, but it does not create novelty because longitudinal UOT work already exists.

## Paper-level decision

R4 synthetic calibration can validate architecture and causal-interface properties only. The method becomes paper-eligible only if later real-data experiments show that query sealing plus persistent/null identity and fixed-budget mediation outperforms the strongest solver-matched and slot/Q-Former controls under the required interventions. A synthetic pass alone cannot support a conference claim.
