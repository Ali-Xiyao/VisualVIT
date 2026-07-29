# Findings: PRTA-CXR R37

## Frozen predecessor conclusion

- R31 remains valid discovery evidence but its routing gain is not a stable
  transferable mechanism after fair ensemble accounting.
- R33/R33A falsify the frozen-final-layer-cache token-routing premise.
- Attempt F made robust and rich experts equally competent
  (0.50720 vs 0.50741), while routing remained negative.
- Pair identity is learnable (Attempt E AUC 0.9353) but does not imply
  progression semantics.
- No further route, threshold, projection-seed, bridge-width, voting, or
  coverage tuning is admissible on the 1,574 R33A training patients.

## R37 working hypothesis

Frozen final-layer BiomedCLIP representations encode static state and patient
identity but do not reliably encode the directional change determined by the
correct prior. A lightweight temporal adapter trained over earlier
intermediate patch tokens may learn correct-prior-responsive progression while
preserving the encoder's static medical semantics.

## Proposed method

- Cache BiomedCLIP Block-8 patch tokens.
- Freeze Blocks 1-8 and the base weights of Blocks 9-12.
- Insert low-rank adapters and query-conditioned prior/current cross-attention.
- Separate current-state tokens from directional transition tokens.
- Train with transition alignment, current-matched counterfactual prior,
  temporal inversion, and static-state preservation.
- Compress to 64 tokens and attach the frozen VLM only after representation
  qualification.

## Evidence hygiene

- The attached design cites CheXTemporal, ProTrans, TILA, GRCD, and BioViL-T.
  Those literature claims must be verified against primary sources before they
  are used in the formal protocol or paper narrative.
- The 300 dev, 483 sealed test, and gold outcomes remain protected.
- New pretraining patients must be excluded from all protected patient sets
  before report-derived supervision is created.

## Primary-source check

- CheXTemporal v1 reports a five-class progression benchmark and a
  282,214-example silver pair-finding resource spanning 34,296 patients. Its
  authors state that the silver resource is intended for evaluation rather
  than training, so it is not an eligible R37 training source:
  https://arxiv.org/html/2605.11304v1
- The same benchmark reports a meaningful static-to-temporal gap on gold
  progression classification (for example, BiomedCLIP overall accuracy 20.54
  versus BioViL-T 27.42). This supports learning temporal representations
  before testing token compression.
- ProTrans, TILA, GRCD, and BioViL-T were located as the closest primary-source
  comparators. Their exact implementation and availability claims still need
  targeted verification before the R37 baseline matrix is frozen.

## Local asset and capacity inventory

- Approximate free space is 613.8 GB on `H:`, 245.0 GB on `E:`, and 201.6 GB
  on `F:`. A new Block-8 cache should default to `H:` after row-count and
  tensor-size estimation rather than consume the constrained existing
  `F:\VisualVIT_runtime` volume.
- Local MIMIC-CXR-family junctions are present under
  `H:\Xiyao_Wang\000_Public Dataset`: `mimic-cxr`, `mimic-cxr_less`, and
  `mimic_cxr_other`. Chest ImaGenome assets are also present locally.
- A local BiomedCLIP model is present under
  `H:\Xiyao_Wang\001_models\biomedclip`.
- No BioViL-T checkpoint was visible in the top-level local model inventory.
  R37 must not claim an A1 reproduction until checkpoint availability,
  license, and inference compatibility are verified.
- Existing repository specifications already document MIMIC metadata/split
  join keys and the Chest ImaGenome DUA boundary. Reuse those assets rather
  than reacquire them.
- The junction targets resolve to `H:\xiyao\dataset\MIMIC-CXR\...`. The main
  local MIMIC root contains both `mimic-cxr-images` and
  `mimic-cxr-reports`; the auxiliary root contains the official compressed
  metadata, split, CheXpert, and NegBio tables.
- R32's protected cohort builder already created an outcome-free
  `sealed_vlm_test_manifest.json` and a `gold_quarantine_manifest.json`.
  These frozen structural artifacts can be projected into a forbidden-ID
  registry without opening `sealed_vlm_test_labels.json`.
- The 300-patient dev identifiers are co-located with train outcomes in
  `train_dev_cohort.json`. R37 needs a narrow ID-only extractor that retains
  only `patient_id` and `partition`, never serializes or reports progression
  values, and records the access as structural exclusion rather than model
  evaluation.
- R32's cohort source is only the 2,383-patient R31 sealed reserve and is not
  suitable as the R37 independent pretraining pool. R37A must enumerate the
  broader official MIMIC metadata/report timeline directly, then exclude the
  frozen R32/gold registry before deriving any supervision.
- The official metadata schema exposes `dicom_id`, `subject_id`, `study_id`,
  `ViewPosition`, `StudyDate`, and `StudyTime`; the official split table
  exposes `dicom_id`, `study_id`, `subject_id`, and `split`. These are
  sufficient to construct ordered patient timelines without progression
  outcomes.
- The outcome-free R32 sealed manifest contains 4,821 pair-finding rows across
  483 patients. The ID-only projection of the mixed train/dev file confirms
  1,574 train and 300 dev patients with zero overlap; no progression values
  were printed, retained, or used.
- To make "independent pretraining" unambiguous, R37A will conservatively
  exclude all R32 train, dev, and sealed-test patients plus every gold
  quarantine patient, not merely the 300/483 evaluation subsets. This removes
  any possibility of silently reusing the 1,574 R33A patients under new
  report-derived supervision.
- The user authority fixes the initial R37A deliverables, >=30,000-pair floor,
  >=90% CMCP coverage target on dynamic rows, Block-8 cache premise, A0-A7
  baseline family, and the one-shot R37C/R38/R39 unlock order. These are gates,
  not tunable suggestions.

## Implementation reuse boundary

- `scripts/build_mimic_proxy_manifest.py` already provides deterministic
  frontal-image selection, official-train filtering, patient timeline sorting,
  and MIMIC image-path construction. R37 can reuse these mechanics while
  replacing its small three-class proxy sampling with full independent
  patient-disjoint longitudinal manifests.
- `scripts/cache_r32_patch_tokens.py` already strictly loads the 150-key
  BiomedCLIP visual trunk and verifies the `[197, 768]` token shape, frozen
  parameters, finite values, sharded storage, and lightweight provenance.
  R37 must change the extraction boundary from final `forward_features` output
  to the state immediately after ViT Block 8.
- One FP16 `[197, 768]` token tensor occupies 302,592 bytes before container
  overhead (about 0.289 MiB per unique image). The full cache-size decision
  therefore depends on the unique-image inventory, not pair count.
- Existing R32 cache code hashes the small model config but deliberately avoids
  per-shard hashes. R37 will preserve that lightweight pattern and will not
  rehash unchanged source datasets.

## R37A structural cohort result

- The full official-train MIMIC enumeration produced 108,732 eligible
  consecutive, positive-interval longitudinal pairs after excluding all R32
  and gold-quarantine patients.
- The split contains 97,842 pretraining pairs from 24,435 patients and 10,890
  internal-calibration pairs from 2,788 patients.
- There are 144,423 unique selected images. A full FP16 `[197, 768]` Block-8
  cache is estimated at 40.70 GiB before shard/container overhead, well within
  the available `H:` capacity.
- All selected image/report paths exist; forbidden-patient overlap and
  patient/study/image cross-partition overlap are zero.
- Median interval is 8 days (range 1-1,844). View-pair counts are 54,861
  AP-to-AP, 27,596 PA-to-PA, 12,850 AP-to-PA, and 13,425 PA-to-AP.
- The >=30,000 structural pair floor passes by a wide margin. Transition-label
  support, case-study precision, cache reproducibility, and CMCP coverage are
  still open gates.

## Comparator verification

- ProTrans reports 98,940 longitudinal image-report pairs from MIMIC-CXR-JPG
  plus Chest ImaGenome progression annotations, excluding its downstream
  overlap. It aligns state and structured transition text, models reversed
  time, and uses bidirectional reconstruction. Its transition text is derived
  from Chest ImaGenome annotations rather than a free-form keyword labeler:
  https://arxiv.org/html/2606.15938v1
- TILA explicitly uses reversed image pairs as supervision across pretraining,
  fine-tuning, and inference and evaluates order sensitivity/consistency.
  Therefore inversion remains a required component/baseline, not the distinct
  PRTA claim: https://arxiv.org/abs/2604.04563
- GRCD uses a frozen BioViL-T encoder, 25 anatomical regions, region-guided
  change tokens, and an LLM. It reports 40,250 pairs and 192,755 finding-level
  stable/worsening/improvement annotations. This confirms that region tokens
  alone are not novel enough; PRTA's distinct test is correct-prior
  responsiveness under CMCP: https://arxiv.org/html/2607.02719v1
- Because ProTrans uses structured Chest ImaGenome transition annotations, the
  R37 free-text extractor must remain a separately audited supervision source
  and cannot be described as a ProTrans-equivalent annotation protocol.

## Block-8 smoke

- The exact extraction boundary is BiomedCLIP patch embedding, positional
  embedding, patch-drop/norm-pre, then ViT Blocks 1-8; final encoder norm and
  Blocks 9-12 are not applied.
- A 64-image smoke on GPU 1 passed strict visual-key loading, frozen-parameter
  checks, `[197, 768]` shape, finite values, and repeated-batch bit identity
  with maximum absolute difference 0.
- Smoke throughput was 4.55 images/s with 0.60 GB peak allocated GPU memory.
  A single-GPU full cache would take roughly 8.8 hours at this rate, so the
  formal cacher should be sharded across the two free GPUs or optimized before
  committing to a long run.
- The smoke wrote one 19.37 MB shard and recomputed no source or per-shard
  hashes.
- A 512-image batch-128 benchmark remained bit-identical and increased
  throughput to 6.57 images/s with 1.36 GB peak allocation. At this measured
  rate, the full inventory is about 6.1 hours on one GPU. The next simple
  execution improvement is two disjoint cache parts, one per 3090, rather than
  more batch-size tuning.

## Transition extractor case studies

- v1 found 46,553 pairs with transition supervision and passed raw support, but
  its 200-row stratified case sheet exposed systematic scope errors: negated
  `new`, indication questions, lateral `larger` comparisons, cues attached to
  neighboring findings, and partial resolution labeled as fully Resolved.
  Therefore v1 is a frozen qualitative failure and cannot train R37.
- v2 added section/clause parsing, broader negation, partial-resolution
  remapping, stricter size-comparison cues, and removed generic
  `persistent/remains`. It completed in about 2.5 minutes with 16 report-reader
  threads.
- v2 retains 34,114 pretraining and 3,789 internal-calibration transition
  pairs. Its weakest dynamic patient support is still ample: Resolved has
  1,221 pretraining and 135 calibration patients.
- v2's case sheet is substantially cleaner, especially Stable and Resolved,
  but New/Worse still admit uncertainty and alternative scope such as
  `may reflect`, `potential new`, and `stable or increasing`. v2 therefore
  remains below the formal per-class precision bar and cannot train R37.
- v3 rejects uncertainty/alternative scope and splits neighboring findings on
  `and/or`. It retains 32,138 pretraining and 3,575 calibration transition
  pairs, with the weakest dynamic support still 1,185/134 Resolved patients.
- v3 case review shows Stable, Improved, and Resolved are nearly clean. The
  remaining reproducible errors are narrower: malformed or indented
  `HISTORY:`/`Question` lines, negated `newly`, and technique/artifact wording
  mistaken for temporal `increased`. A final conservative v4 boundary pass is
  justified; further open-ended lexicon expansion after v4 is not.
- v4 freezes explicit section parsing, full-sentence negation, question and
  uncertainty rejection, and technique-artifact exclusion. It retains 29,092
  pretraining and 3,275 calibration pairs with transition supervision.
- v4 dynamic patient support remains far above the frozen minima: pretrain
  Improved/New/Resolved/Worse = 3,697/3,192/1,122/4,688; internal calibration =
  415/355/127/510.
- Preliminary review of the deterministic 200-row v4 sheet found only two
  context-dependent rows requiring source-report adjudication; no fifth
  open-ended ruleset will be created.
- Source-report adjudication confirmed both rows as false positives: a
  projectional density statement was not temporal worsening, and a soft line
  wrap separated `No` from `new focal consolidation`. The v4 sheet therefore
  scores 198/200 overall (99%) and 39/40 (97.5%) in each affected class,
  already above the frozen quality gate. A format/uncertainty-only v4.1 patch
  removes the known errors without expanding the semantic lexicon.
- The final deterministic v4.1 sheet scored 194/200 (97.0%) under structured
  Codex review: Stable 95.0%, Improved 100.0%, Worse 97.5%, New 92.5%, and
  Resolved 100.0%. All frozen quality thresholds pass, but this is not
  radiologist/human adjudication, so formal R37B training remains labeled
  pending human QA.
- The formal Block-8 cache is ready to launch as two disjoint parts, but both
  GPUs are currently occupied at about 19 GB each by independent
  `r1_local_differential_eval.py` repair-discovery shards (PIDs 30048 and
  4444). They are not R37 jobs and must not be interrupted or competed with.
- The idle launcher is healthy and continues to observe roughly 19.7/19.4 GB
  used, so it has not accumulated any idle confirmations and has not spawned
  cache workers.
- CMCP construction is implemented as a finding/view/partition group search
  with different-patient and different-label masks, normalized mean-pooled
  current Block-8 cosine ranking, and deterministic `example_id` tie-breaking.
- Existing protocols document local/internal MIMIC-CXR and Chest ImaGenome use
  under the user's existing credentialed access. No new login or download is
  required for R37. The repository does not certify the user's CITI/project
  DUA status or authorize redistribution of images, reports, caches, manifests,
  or derived embeddings; external release remains a user-side compliance gate.
- The A0-A7 registry now freezes which variants use classification,
  transition alignment, inversion, CMCP, state preservation, or external
  availability gates. A1 BioViL-T has passed its checkpoint/source
  availability gate; A7 ProTrans remains explicitly availability-gated.
- The frozen local BiomedCLIP text tower successfully cached 12 finding-query
  prototypes and 60 finding-by-five-class transition prototypes, all 512-D,
  finite, and outcome-free.
- The training cache index uses merged part inventories and shard counts to
  locate DICOM tensors without scanning 40 GB of features. It loads shards on
  demand through a bounded LRU.
- The unified A2-A6 runner now implements classification, structured prototype
  alignment, inversion, CMCP margin, and static-state preservation according
  to the frozen variant registry. Non-formal runs are hard-capped at small
  engineering-smoke scale; formal mode fails closed while human QA is false.
- The official `microsoft/BiomedVLP-BioViL-T` Hub repository is public and was
  inspected without authentication. Its current selected commit is
  `692f09e9be1bfe5fdd5f3efdd0e1eca7d2c10b23`; the repository contains a
  dedicated `biovil_t_image_model_proj_size_128.pt` image checkpoint, so A1
  need not inherit or redistribute the full text-model bundle.
- BioViL-T is an MIT research-only baseline whose model card explicitly
  excludes deployed clinical/medical-device use. The image encoder is a
  ResNet-50 feature extractor followed by a temporal transformer, and the
  official checkpoint can be inspected safely as a plain 372-tensor state
  dictionary.
- The current Python environment does not contain `health_multimodal`; A1
  therefore requires either the official HI-ML model definition or a
  version-pinned equivalent loader before it can be marked available.
- Microsoft archived `hi-ml` on 2025-11-21. Its final read-only HEAD is
  `b67c1d27c6b17d8e8ff01f8c507f3cabdb307388`; pinning that source gives A1 a
  reproducible implementation boundary even though the package is not
  published through the currently configured PyPI index.
- The pinned official source loads the selected checkpoint with zero missing
  and zero unexpected keys. A same-image pair yields finite 512-channel
  14x14 fused patches and a finite 512-D pooled embedding, so A1 is now
  technically available rather than a paper-only placeholder.
- The canonical A1 evaluation feature is the official normalized 128-D
  projected global image embedding. Using the internal 512-D pooled tensor
  would expose an implementation detail rather than the model's joint-space
  output, so that alternative was rejected before any outcome evaluation.
- HI-ML's `get_biovil_t_image_encoder` helper constructs the single-image
  `ImageModel` outer class around a multi-image encoder. Direct pair inference
  therefore requires the official `MultiImageModel` subclass; it introduces no
  new parameters and strictly accepts the same checkpoint.
- The corrected official pair path is exactly repeatable on the two-pair CPU
  smoke and produces the frozen canonical 128-D feature. Its CPU rate is too
  slow for 108,732 pairs, reinforcing the existing policy of waiting for free
  GPUs instead of competing with the unrelated jobs.
- A deliberately tiny A1 case study exposed no usable true-pair advantage:
  true-pair and current-only predictions were exactly the same on all five
  calibration rows. The inversion path changed predictions, so the temporal
  branch is being exercised, but the sample is far too small for a scientific
  conclusion. This is retained as a failed/underpowered method example rather
  than reported as a positive baseline result.
- The short joint-idle GPU window at 13:04 was consumed by a new unrelated R1
  control wave, not by R37. The idle launcher correctly requires three
  confirmations and therefore avoided racing those workers.
- A0 had been named in the matrix but not yet pinned to one tensor boundary.
  It is now fixed as the normalized final-layer CLS delta produced from the
  same Block-8 cache via untouched Blocks 9-12. This prevents post-result
  switching among CLS, patch mean, or older rich-bundle features.
- The qualification code now resamples patient clusters and carries every
  finding row from each sampled patient. It cannot silently fall back to
  row-level bootstrap, which would understate correlation across findings.
- Three-seed qualification now has a single executable authority: seeds
  17/29/43, 2,000 shared patient-cluster resamples, and the mean seed
  true-minus-control macro-F1 distribution. The aggregator refuses mixed row
  order or engineering-only results.
- Restricting A1 caching to v4.1 transition-supervised rows leaves 37,391
  unique pairs. The v2 cache stores all three temporal controls once, so seed
  29/43 never re-run the image encoder and findings sharing a pair reuse the
  same canonical features.
- At 15:00-15:02 the idle launcher observed three consecutive low-memory
  confirmations and started exactly two formal Block-8 cache parts: PID 36292
  on cuda:0 and PID 24792 on cuda:1. The launcher status is
  `CACHE_PARTS_RUNNING`; both outcome and source-hash firewalls remain false.
- The post-cache watcher remains alive as PID 17856 and is correctly waiting
  for the Block-8 merge. This is an engineering-stage transition, not a
  scientific result.
- Both formal Block-8 parts completed at 15:41 with 283 shards each and
  `PASS_R37_BLOCK8_FORMAL_CACHE`; their stderr logs are empty and their
  reported sizes are 21,854,593,665 and 21,854,896,321 bytes.
- The launcher nevertheless wrote `STOP_R37_BLOCK8_CACHE_PART_FAILURE`
  because Windows PowerShell returned null `ExitCode` properties after both
  child processes had already produced complete PASS manifests. This is a
  launcher-control failure, not a cache or scientific failure. Recovery must
  merge the existing PASS parts and must not recache images or hashes.
- Strict merge recovery PASSed with 144,423/144,423 unique images, 566 shards,
  43,709,489,986 bytes, exact repeated-batch equality in both parts, and all
  outcome/hash firewalls false. No image encoding was repeated.
- The launcher now rejects only known nonzero exit codes; a missing process
  exit-code property falls through to the strict manifest merger, which still
  fails closed on missing, incomplete, overlapping, or non-PASS parts.
- The stopped post-cache watcher was restarted once as PID 25564 after the
  merged manifest passed. It advanced directly to `RUNNING_CMCP`, proving the
  recovery path does not restart Block-8 work.
- CMCP passed at 100% coverage: 23,416/23,416 pretraining and 2,625/2,625
  internal-calibration dynamic examples were matched without outcome access.
- Bounded A0, A3, and A6 engineering stages all passed their pipeline and
  gradient/firewall checks. These are engineering smokes, not scientific
  results.
- The two-GPU A1 cache completed and merged 37,391 unique pairs once. The
  subsequent CPU cached probe stopped before producing a result because FP16
  cache tensors were concatenated into an FP32 linear probe. This is a narrow
  dtype-boundary bug; the cache remains valid and must be reused.
- After FP32 promotion at the probe boundary, the cached A1 smoke passed from
  the existing cache. On 100 train/50 internal-calibration rows, A1 true,
  current-only, and inverted macro-F1 were 0.4646, 0.3990, and 0.3682,
  respectively. The +6.56/+9.63 pp differences are bounded case-study signals,
  not scientific evidence.
- A0 on the same 100/50 engineering scope showed 0.3702 true, 0.1862
  current-only, and 0.1165 inverted macro-F1 (+18.41/+25.37 pp). Again this is
  a single-seed tiny smoke without bootstrap.
- A3 produced exactly identical true/current predictions on all 50 rows and
  -0.91 pp versus inverted. A6 also produced exactly identical true/current
  predictions on all 50 rows and identical true/CMCP predictions on all 40
  dynamic rows; it was only +2.09 pp versus inverted.
- Therefore the post-cache engineering chain passes mechanically, but the
  trainable PRTA path has not yet demonstrated correct-prior responsiveness.
  Scientific R37 remains `NOT_EVALUATED`, not GO.
- The next attempt is bounded by the runner's pre-existing engineering ceiling:
  A6 seed 17, 1,000 train rows, 500 calibration rows, 3 epochs, rank 32,
  learning rate 1e-4, and batch size 2. No threshold, architecture, loss,
  seed, or protected-outcome choice changes.
- Continuous diagnostics now measure embedding cosine/L2, logit L2, and
  argmax-change rate for true versus current-only, inverted, and CMCP. This
  distinguishes weak but real prior sensitivity from complete representation
  collapse.
- The prebounded A6 mechanism-scale case completed on 1,000 train and 500
  internal-calibration rows. Macro-F1 was 0.4408 true-pair, 0.3724
  current-only, and 0.2917 inverted: +6.84 and +14.91 pp.
- On 400 dynamic CMCP rows, true-pair and counterfactual-prior macro-F1 were
  0.3425 and 0.2728 (+6.97 pp). True versus CMCP changed 30.0% of predictions;
  true versus current-only changed 18.6%; true versus inverted changed 50.2%.
- Continuous differences are nonzero rather than argmax noise:
  true/current embedding L2 mean 0.1373 and logit L2 mean 0.5656;
  true/CMCP 0.1863 and 0.7628; true/inverted 0.3214 and 1.3118.
- This repairs the earlier undertrained A6 case-study failure and establishes
  a positive engineering mechanism signal. It is still one seed, a bounded
  non-formal run, and lacks patient-bootstrap confidence intervals; scientific
  R37 remains pending rather than GO.
- Human QA is a provenance gate, not another model experiment. The fixed
  `r37_transition_case_study.csv` contains 200 rows (40 per class) and already
  exposes `human_direction_correct`, `human_error_category`, and
  `human_notes` fields.
- A reviewer must judge whether the proposed finding direction follows from
  the displayed report sentence. Every row must be marked; false rows require
  an error category. Passing requires >=90% overall and >=85% within every
  class. Codex's earlier 194/200 review cannot serve as the independent
  certificate.
- Per user direction, human QA is deferred to the final project stage and is
  not part of the current work. The next permitted work is non-formal,
  outcome-firewalled engineering replication for the already-frozen seeds 29
  and 43 plus execution-chain hardening.
- The frozen seed-29 and seed-43 A6 engineering replications both completed
  with `PASS_R37_PRTA_ENGINEERING_SMOKE`; no protected or gold outcomes were
  accessed and neither run permits a scientific claim.
- True-pair versus current-only macro-F1 differences were +6.84, +8.97, and
  +7.54 pp for seeds 17, 29, and 43 (mean +7.78 pp; minimum +6.84 pp).
  True-pair versus inverted differences were +14.91, +15.15, and +16.37 pp.
- On the dynamic CMCP subsets, true-pair versus counterfactual-prior
  differences were +6.97, +8.85, and +5.77 pp (mean +7.20 pp; minimum
  +5.77 pp). Prediction-change rates were nonzero for every control and seed.
- The same frozen settings therefore replicate a positive engineering
  mechanism signal across all three prespecified seeds. This is not yet a
  scientific GO: the runs are non-formal, reuse a 500-row internal engineering
  evaluation, and do not include patient-bootstrap confidence intervals.
- The consolidated case study is
  `reports/R37_A6_ENGINEERING_MULTISEED_CASE_STUDY.md`. The next protocol-safe
  step is execution-chain hardening for the still-locked formal bundle, not
  outcome-driven tuning or a protected reveal.
- Formal-bundle inventory exposed two fail-closed runner gaps. The existing
  `run_r37_prta_smoke.py --formal` path retains engineering defaults of only
  100 train/50 calibration rows, and its seed-dependent balanced calibration
  sampling would violate the aggregator's exact cross-seed row-order contract.
- The same runner currently emits the engineering-smoke schema/status even in
  formal mode and leaves `scientific_claim_allowed` unset rather than false
  pending aggregation. A formal handoff must use all frozen transition rows in
  one seed-independent calibration order and emit a distinct training-only
  status that cannot be mistaken for internal scientific GO.
- The existing formal aggregator correctly freezes seeds 17/29/43, patient
  bootstrap at 2,000 replicates with seed 37001, shared patient-cluster draws,
  exact row-order checks, variant equality, and protected-outcome/human-QA
  firewalls. The remaining work is to connect these contracts through one
  machine-readable specification and readiness preflight.
- The transition audit records 33,621 eligible pretraining pairs and 3,770
  internal-calibration pairs under ruleset v4.1. These expand to 46,349 and
  5,242 finding-level examples respectively; pair and example counts must not
  share one metric name.
- The merged Block-8 cache is structurally ready at 144,423/144,423 images,
  566 shards, `[197,768]` FP16 features, with source/per-shard hashing disabled
  and protected outcomes unread. CMCP is 100% covered over 26,041 dynamic
  examples (23,416 pretrain and 2,625 calibration).
- The corrected formal specification freezes full finding-row selection at
  46,349/5,242 over 33,621/3,770 eligible pairs while retaining the replicated
  A6 training hyperparameters:
  3 epochs, batch 2, rank 32, learning rate 1e-4, and seeds 17/29/43.
- The real runtime preflight passes every specification, artifact, count,
  bootstrap, cache, CMCP, output-state, and outcome-firewall check. It reports
  `READY_R37_FORMAL_BUNDLE_PENDING_HUMAN_QA`, with all three formal seed
  directories fresh and `formal_execution_allowed=false`.
- The formal launch guard was exercised with the exact A6 command and current
  runtime audit. It raised the expected human-QA `PermissionError`, exited
  nonzero, created no output directory, and started no GPU work.
- A second readiness audit found that the protocol named inversion and
  state-retention gates but had not operationalized their thresholds, and the
  A0 capacity-matched baseline still had engineering-only sampling/status.
  Before any formal result, inversion is now fixed as inverse-label agreement
  >=0.90 per seed, while state retention is mean adapted-versus-frozen current
  cosine >=0.99 per seed. These definitions follow the already-frozen inverse
  mapping and state-preservation loss rather than observed outcomes.
- Formal A0 is being hardened to the same all-row, seed-independent
  calibration order with its already-frozen linear-probe settings, enabling a
  paired patient-cluster A6-minus-A0 gate instead of comparing mismatched
  engineering samples.
- The frozen human-QA sheet is present locally with exactly 200 rows and 40
  rows in each of Stable, Improved, Worse, New, and Resolved. Its three review
  columns are currently blank, so no independent judgment has yet been
  supplied.
- The sheet contains derived clinical report text and identifiers and must stay
  under the existing local data-use boundary. The reviewer guide may be
  committed, but the CSV itself must not be copied into Git, email, public
  cloud storage, or an unapproved collaboration surface.
- A local reviewer working copy and a copy of the Chinese guide now sit beside
  the frozen source sheet. The working copy retains 200 rows and has zero
  completed QA judgments; it is intentionally excluded from Git.
- The validator was exercised against the blank sheet and correctly returned
  `STOP_R37_TRANSITION_HUMAN_QA`, `completed_rows=0`, exit code 2, and
  `formal_training_unlocked=false`.
- The returned review sheet now contains all 200 judgments. It has 195 TRUE
  and five FALSE rows, for 97.5% overall agreement. Per-class agreement is
  Stable 97.5%, Improved 100%, Worse 97.5%, New 92.5%, and Resolved 100%;
  all frozen numerical thresholds pass.
- Row count, column order, case order, and every non-QA field match the frozen
  source sheet exactly. All five FALSE rows have valid error categories.
- The reviewer attestation was not returned as a separate local artifact and
  is not encoded in the CSV. Formal training therefore remains locked despite
  the passing content metrics.
- The validator is now fail-closed on frozen-source drift and can atomically
  update the transition audit only after both the sheet and attestation pass.
- The independent human-QA gate formally PASSed at 195/200 (97.5%), with all
  five classes above the frozen 85% floor. The audit is unlocked without any
  protected-outcome or hash access; reviewer experience is recorded exactly
  as unavailable rather than inferred.
- The first formal A6 launch attempt stopped before model construction on both
  GPUs with the same count guard: the bundle expected 33,621 rows but
  `flatten_partition` produced 46,349 finding-level examples. No output
  directory or scientific result was produced.
- This is a metric-namespace mismatch. The audit's 33,621/3,770 values count
  eligible image pairs with at least one transition label, while the A6/A0
  runners and patient-cluster bootstrap operate on every finding-level
  transition row: 46,349 pretrain and 5,242 internal calibration examples.
- The protocol text already requires all frozen transition rows and carrying
  every finding row within sampled patients. The smallest admissible repair is
  therefore to register both pair counts and finding-level example counts,
  freeze formal row counts at 46,349/5,242, and rerun the untouched model,
  seed, loss, threshold, and bootstrap bundle.
- After that namespace-only repair, both formal A6 seeds passed the count
  guard and remained live beyond model/cache initialization. This converts the
  earlier STOP from a launch failure into a healthy formal run; it is still
  not a scientific result until all three seeds and patient-bootstrap gates
  complete.
- The user narrowed the immediate execution scope to A6 seeds 17 and 29 only.
  Seed 43, all A0 probes, and automatic aggregation are deferred rather than
  deleted. Two-seed outputs may be inspected descriptively but cannot satisfy
  the frozen all-three-seeds, A6-minus-A0, or patient-bootstrap scientific
  gates.
- Both selected formal A6 results are structurally complete and firewall-clean.
  Seed 17 true-pair/current-only macro F1 is 0.4092/0.2905
  (+11.87 pp), while seed 29 is 0.4105/0.2690 (+14.15 pp).
- On the 2,625-row CMCP subset, seed 17 true-pair/CMCP macro F1 is
  0.2873/0.2115 (+7.58 pp), while seed 29 is 0.2895/0.2104 (+7.91 pp).
  State-retention cosine passes descriptively in both seeds (0.9938/0.9936),
  but inversion consistency is below the frozen 0.90 threshold in both
  (0.8438/0.8735).
- These two formal training artifacts are positive for correct-prior
  responsiveness but cannot produce a scientific GO/STOP: seed 43, A0, the
  three-seed patient bootstrap, and all protected reveals remain deferred.
- R37 inversion failure is not uniform. Seed 17/29 consistency is lowest for
  New (0.7249/0.8166), Resolved (0.7287/0.7926), Improved
  (0.7914/0.8253), and Worse (0.8086/0.8526), while Stable is
  0.9052/0.9144.
- The failure is finding-dependent: Consolidation, Lung Opacity, Pneumonia,
  Edema, Atelectasis, and Pleural Effusion account for nearly all inconsistent
  rows. Several other findings are exactly or nearly 1.0, which is not alone
  evidence of directional reasoning because a Stable prediction is invariant
  under the frozen label permutation.
- Only 324 failed example IDs overlap across seeds, versus 1,158 in their
  union (Jaccard 0.2798). This points to optimization/head equivariance
  instability rather than one small deterministic cohort defect.
- The current loss uses a detached soft target derived from the model's own
  forward logits. It encourages but does not guarantee the required
  Stable→Stable, Improved↔Worse, New↔Resolved group action.
- The smallest R37.1 candidate is therefore a parameter-free Z2-equivariant
  logit projection: combine forward raw logits with inverse-permuted reversed
  raw logits, then define reversed logits as the exact inverse permutation.
  This makes the inversion contract architectural rather than threshold-tuned;
  its correct-prior and CMCP behavior must still be tested once on a fresh
  patient holdout.
- The frozen failure artifact now reports
  `STOP_R37_INVERSION_CONSISTENCY`, and
  `reports/R37_INVERSION_FAILURE_CASE_STUDY.md` records the evidence boundary,
  per-label/finding localization, root-cause hypothesis, exact R37.1
  projection, and one-shot fresh-roster contract.
- The old pretraining partition contains 12,102 transition-eligible patients.
  R37.1 freezes a label-agnostic 15% holdout: sorted patient IDs, one shuffle
  with RNG seed 37101, first 1,815 patients held out. The old 1,347-patient
  calibration cohort remains excluded.
- The one-shot roster built successfully after the repair/split commit. It
  contains 39,491 training examples from 10,287 patients and 6,858 fresh
  validation examples from 1,815 patients. All five labels are present in the
  fresh holdout, including 250 Resolved examples; the roster is not revised.
- The source old-calibration manifest contains 2,788 total patients, of whom
  1,347 have transition examples. All 2,788 are excluded from R37.1, which is
  stricter than excluding only the transition-bearing subset.
- A captured foreground R37.1 training-side diagnostic passed on
  100 train / 50 evaluation rows for one epoch. The architectural inversion
  consistency is exactly 1.0 and true-current is +15.04 pp, confirming that
  the projected decision rule is wired correctly.
- The tiny diagnostic state-retention cosine is only 0.8992. This is expected
  to remain an unresolved gate at tiny scale and must not be called positive
  scientific evidence; the formal three-epoch fresh-holdout run must preserve
  the >=0.99 state gate.
- The Windows host rebooted at 2026-07-28 14:24:04 +08 while both R37.1 seeds
  were incomplete. The recorded launcher/child PIDs were absent afterward,
  both output directories were still missing, and all four redirected logs
  were zero bytes; this is an external engineering interruption, not a model
  result.
- Recovery preserved the exact frozen seed/device/model/loss arguments. The
  stale status and zero-byte logs were moved to
  `interruptions/20260728T142404_reboot_interrupt`, both GPUs were confirmed
  idle over three polls, and only seeds 17/29 were relaunched. No source or
  per-shard hash and no protected outcome was accessed.
- Both one-shot R37.1 fresh-holdout seeds completed structurally with clean
  launch/result firewalls. Seed 17 finished at 23:17 +08 and Seed 29 at 23:36
  +08; both stderr logs are empty and both GPUs were released.
- Seed 17 passes all four frozen initial gates: inversion 1.0000, state
  retention 0.9934, true-current +30.42 pp, and true-CMCP +12.76 pp.
  Seed 29 also passes: inversion 1.0000, state retention 0.9929,
  true-current +25.22 pp, and true-CMCP +11.39 pp.
- These are two-seed descriptive results, not final scientific GO. They
  satisfy the pre-registered condition for continuing to seed 43, A0 on the
  same fresh holdout, and the frozen patient-level bootstrap; protected
  300-dev/483-test/gold evaluation remains locked.
- The existing A0 formal probe and internal aggregator are explicitly pinned
  to the old R37 transition root, 46,349/5,242 row counts, and old-R37 result
  schemas. Reusing them unchanged would silently evaluate the wrong roster.
- The smallest protocol-consistent downstream repair is a separate explicit
  R37.1 mode: use the already frozen A0 hyperparameters and seeds, but require
  the R37.1 transition audit, 39,491/6,858 rows, fresh output roots, distinct
  R37.1 schemas/statuses, and aggregator schema selection. This changes no
  model, seed, loss, threshold, or bootstrap constant.
- The explicit R37.1 downstream code path passed focused validation, but the
  user paused execution before Seed 43 or any A0 process was launched. The
  current frozen interpretation is two-seed descriptive PASS, full internal
  qualification not evaluated, and protected reveal still locked.
- The user subsequently authorized a reduced continuation: run A0 only for
  Seeds 17 and 29 on the same R37.1 fresh holdout, followed by a distinct
  two-seed patient-cluster bootstrap screen for A6 versus current-only, CMCP,
  and A0. Seed 43 and the registered three-seed scientific gate remain
  explicitly deferred.
- The reduced screen must preserve the frozen 2,000 bootstrap replicates and
  bootstrap seed 37001, require both observed seed effects to be at least
  +2 percentage points with the patient-bootstrap 95% CI lower bound above
  zero, and remain descriptive/internal regardless of its outcome.
- A dedicated fail-closed two-seed screen now preserves those constants while
  leaving the original three-seed aggregator unchanged by default. Its result
  schema explicitly records that Seed 43 and the three-seed gate were not
  evaluated and that no scientific claim is allowed.
- After three consecutive idle GPU polls and fresh-output checks, A0 Seed 17
  launched on GPU 0 as launcher/Python PIDs 12348/11292 and Seed 29 launched
  on GPU 1 as 5064/19816. Both status files are RUNNING, both stderr logs are
  empty, and both processes remain responsive with model memory loaded.
- Both A0 seeds completed with exit code 0 and clean firewalls. Their true-pair
  macro F1 values are 0.3419/0.3404 for Seeds 17/29 on the identical
  1,815-patient, 6,858-row fresh holdout.
- The two-seed screen emitted `PASS_R37_1_TWO_SEED_INTERNAL_SCREEN`. A6 minus
  current-only is +30.42/+25.22 pp with pooled patient-bootstrap CI
  [+25.96, +29.50] pp; A6 minus CMCP is +12.76/+11.39 pp with
  [+10.61, +13.63] pp; A6 minus A0 is +12.62/+11.25 pp with
  [+10.24, +13.66] pp.
- Every diagnostic and reduced comparison gate passed. The result explicitly
  records `three_seed_gate_evaluated=false`,
  `scientific_claim_allowed=false`, and all protected/hash firewalls false.
- The original TIER proposal and empty-result template still ended at the old
  R32-R36/R33-STOP narrative. Without a current addendum, a new reader could
  mistake R37.1 for an unregistered side experiment or assume the protected
  stages should run immediately.
- The documentation consolidation therefore preserves the historical
  R32-R36 design while making the R37.1 addendum authoritative. It separates
  the supported two-seed fresh-holdout claims from the untested three-seed,
  300-dev, sealed-test, gold, 64-token, and frozen-VLM claims.
- The user has now explicitly authorized completing the full TIER-CXR-VLM
  chain with both GPUs. This includes Seed 43, the original three-seed gate,
  conditional 300-dev, R38, R39, 483-test, and gold in the frozen order; it
  does not authorize bypassing a failed survival gate or tuning on protected
  outcomes.
