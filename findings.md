# Findings: PRTA-CXR R37

## 2026-08-01 — 论文方法文档的范围

- 新文档应把 PRTA-CXR 讲成一个完整的分层方法：双时相影像与 finding query
  输入、BiomedCLIP intermediate patch features、finding-guided cross-time
  alignment、层次化 64-token bundle，以及两种可选读出部署。
- R52 的独立 direct head 与 R51 的 frozen-Qwen 结构化生成是同一核心
  representation 的两种 downstream interfaces；文档应以共同方法为主、以
  两者为部署分支，不将它们误写成两篇不同的主方法。
- 最终文档确认核心 pipeline 的准确粒度：Block-8 `[197,768]` token 经
  共享 frozen tail 与 rank-32 adapters、finding query 条件化 cross-time
  attention 后，产生 20 state tokens、20 transition tokens 和 aligned-prior
  tokens；`r38_fixed64.py` 再以无参数 mean-preserving reduction 形成
  `4/12/16/16/12/4` 的 fixed-64 bundle。
- A6 的最终时间方向性不是笼统的“数据增强反转”，而是五类标签置换上的
  Z2 logit projection；这与 classification、transition-text alignment、CMCP
  margin 和 state-preservation 共同构成方法叙事。

## 2026-07-31 — R51/R52 报告的术语与叙事边界

- 用户口述中的“两个 251 和 52”按当前项目权威解释为 R51 与 R52；“单独
  ViT/表征部署”对应 R52 的统一 direct head，“作为 VLM 部署”对应 R51 的
  exact-64→shared projector→frozen Qwen 系统接口。
- 两项实验共享三种 `[64,768]` 表征、2,500 名训练患者和 500 名评估患者；
  主要变化是下游读出接口，因此报告必须先讲共享表征，再讲部署分支，不能把
  R51/R52 误写成两套独立的视觉编码方法。
- TILA 的预训练图像编码器和 temporal projected patches 来自官方实现，但
  60-patch exact-64 翻译及本地五分类部署是项目适配；B2 是基于冻结
  BiomedCLIP 的本地透明 Siamese 对照，不是官方命名的完整论文系统；PRTA 是
  本项目提出的 finding-guided cross-time alignment 表征。
- 最终报告采用“共享表征层 + 两种读出部署层”的统一解释：R52 训练 5,991,173
  参数共同分类头，R51 训练 9,873,920 参数共同 projector 且 Qwen 为 0
  trainable parameters。两者均显示 PRTA 对 TILA/B2 的患者配对 CI 下界大于
  0；TILA 对 B2 仅在 R51 显著，说明不同读出器会改变控制方法的相对可读性。

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
- At 2026-07-29 17:11 +08:00, frozen R37.1 A6 Seed 43 launched on GPU 0 and
  matching A0 Seed 43 launched on GPU 1. Launcher/child PIDs are
  11272/23232 and 14120/23436 respectively; both status files are RUNNING,
  both output roots are fresh, and all protected/hash firewalls remain false.
- The active heartbeat `r37-1-full-tier-confirmatory-monitor` owns the
  sequential gate boundary. It may aggregate the registered three seeds only
  after both Seed 43 artifacts validate, and may unlock R37C/R38/R39 only
  after each preceding scientific GO.
- R37.1 A0 Seed 43 completed at 2026-07-29 20:26 +08:00 with launcher status
  `PASS_R37_1_A0_FORMAL_SEED`, process exit code 0, and result status
  `PASS_R37_1_A0_FORMAL_PROBE`. The result has 6,858 rows from 1,815 patients,
  true-pair macro F1 0.3420, a complete checkpoint/result pair, empty stderr,
  and every protected/hash firewall false. A6 Seed 43 remains in progress, so
  no three-seed aggregation has run.
- R37.1 A6 Seed 43 completed at 2026-07-30 03:50 +08:00 with exit code 0,
  complete checkpoint/result artifacts, empty stderr, true-current +30.53 pp,
  inversion consistency 1.0000, state retention 0.9933, and clean firewalls.
- The registered three-seed qualification ran exactly once per comparison.
  A6-current is +28.73 pp with 95% CI [+26.99,+30.33], A6-CMCP is +12.78 pp
  with [+11.35,+14.24], and A6-A0 is +13.07 pp with [+11.38,+14.70].
  Every Seed effect is positive, all inversion values are 1.0000, and all
  state-retention values are at least 0.9929. The direct internal scientific
  decision is `GO_R37_1_THREE_SEED_INTERNAL_QUALIFICATION`.
- This GO unlocks candidate freezing only. The 300-dev outcomes remain unread
  until exactly one A6 three-seed bundle, the matched A0 baseline, thresholds,
  bootstrap, and fail-closed R37C runner are committed and validated.
- During structural R32 asset inspection before the candidate manifest was
  committed, the existing outcome-summary `cohort_audit.json` was printed and
  exposed aggregate 300-dev label-support counts. No model prediction,
  performance metric, or row-level label was read, and the A6 candidate,
  Seeds, thresholds, losses, and bootstrap had already been fixed by the
  registered internal GO. Record this as protocol deviation `R37C-PD1`;
  prohibit any post-exposure candidate/gate change and report it with R37C.
- `configs/r37/r37_1_candidate_for_r37c_v1.json` freezes the unique A6
  three-seed bundle, matched A0 checkpoints, checkpoint hashes, exact R37C
  cohort boundary, two primary comparisons, diagnostics, 2,000-replicate
  patient bootstrap, and fail-on-any-gate rule before any performance reveal.
- The fail-closed R37C implementation is now complete. Structural projection
  persists no progression/target/prediction fields; the cache uses the exact
  frozen BiomedCLIP Block-8 boundary and no source, checkpoint, or shard hash
  recomputation. A separate fresh-root reveal records the single authorized
  300-dev label access before any seed evaluator can run.
- Each R37C seed evaluator loads only the frozen A6/A0 checkpoint receipt,
  validates path and byte size, reproduces the registered equivariant
  true/current/inverted logic, and emits aligned per-row A6/current/A0
  predictions. The aggregator requires Seeds 17/29/43, identical row order,
  both registered patient-cluster comparisons, inversion >=0.90, state
  retention >=0.99, and reports `R37C-PD1`.
- Nine focused qualification/R37C tests, Python compilation, Ruff, and
  PowerShell parsing pass. Both GPUs are idle and no R37C runtime/status root
  exists, so a duplicate-safe first launch is ready after commit/push.
- Commit `f415d42` pushed the validated R37C implementation before protected
  execution. The first duplicate-safe launch began at 2026-07-30 04:14 +08;
  launcher PID 8896 and cache PID 10900 are healthy on GPU 0, stderr is empty,
  and the status remains `RUNNING_R37C` at structural cache with protected
  300-dev outcomes, 483-test, and gold still unread.
- The structural cache and one-shot reveal both PASSed, then Seeds 17/29
  stopped before model construction because 11 of 2,453 rows used only case
  variants of registered findings: `Pleural effusion`, `atelectasis`, `edema`,
  and `lung opacity`. This is an engineering schema-normalization failure, not
  a scientific result.
- The minimal repair maps case-insensitively to the unchanged frozen registry,
  logs the 11 normalization events, and still rejects every value not matching
  a registry member by case alone. It changes no checkpoint, model, seed,
  loss, threshold, label, bootstrap, or protected outcome.
- A guarded evaluation-only resume now requires the prior engineering STOP,
  existing cache/reveal receipts, and absent fresh seed output roots. It never
  rereads the mixed source or repeats the one-shot label reveal. Ten focused
  tests, Ruff, compilation, and PowerShell parsing pass.
- Commit `4e9b52f` pushed the repair. The guarded resume started at
  2026-07-30 04:18 +08 with Seeds 17/29 on GPUs 0/1 under PIDs 9472/27816;
  both GPUs are active, stderr is empty, outputs were fresh, and the pipeline
  remains `RUNNING_R37C` without repeating cache or label reveal.
- R37C completed with direct scientific status `GO_R37C_ONE_SHOT_DEV`.
  Fixed A6 versus current-only is +15.26 pp, patient-bootstrap 95% CI
  [+12.71,+18.01], with seed effects +18.44/+12.31/+15.03 pp. Fixed A6
  versus frozen A0 is +3.42 pp, CI [+0.89,+6.20], with seed effects
  +3.18/+2.69/+4.38 pp.
- Inversion consistency is 1.0000 for every seed and state-retention cosine
  is 0.9932/0.9926/0.9930. All three result files and aggregation completed
  with empty stderr. The 483-test and gold boundaries remain sealed, and
  `R37C-PD1` remains reported without any candidate/gate change.
- R38 is now frozen as a deterministic no-routing, zero-trainable-parameter
  fixed-64 packing test using the registered 4/12/16/16/12/4 layout. Its
  primary gate remains fixed64 A6 versus frozen A0 at +2 pp with CI lower
  above zero and all seeds positive; it must also retain at least 70% of the
  qualified correct-prior effect.
- The mean-preserving packer carries no label or probe logits, keeps all 64
  physical positions attended, uses shared zero reserved tokens, and applies
  the already frozen PRTA transition norm/classifier. Thirteen focused tests,
  compilation, config/upstream validation, and PowerShell parsing pass.
- Commit `5604092` froze and pushed R38 before its first run. At
  2026-07-30 04:50 +08, Seeds 17/29 launched on GPUs 0/1 under PIDs
  21176/31204; both processes are active, stderr is empty, and status is
  `RUNNING_R38`. R39, 483-test, and gold remain locked.
- R38 completed with direct scientific status `GO_R38_FIXED64_SURVIVAL`.
  Fixed64 A6 versus frozen A0 remains +3.42 pp with patient-bootstrap 95% CI
  [+0.89,+6.20] and all three seeds positive. Correct-prior effect retention
  is 1.0 for every seed; exact-64 layout, physical attention, reserved-token,
  zero-routing, and transition-equivalence audits all pass.
- The first uncommitted R39 draft compared A6 only with current-only. That
  would establish longitudinal responsiveness but not frozen-VLM superiority
  over the registered frozen A0 baseline, so it was blocked before any sealed
  cache, model training, or label access.
- The corrected frozen R39 primary is A6 true-pair versus the same-projector
  A0 frozen BiomedCLIP difference representation. The same frozen Qwen3-VL,
  prompt, 64 physical positions, 9,873,920-parameter projector, seeds, and
  training data are shared. Current-only, query-only, and deterministic
  within-finding cross-patient prior shuffle each have their own preregistered
  +2 pp/positive-CI/all-seed gate.
- R39 trains each retained projector for one deterministic epoch on the
  already revealed 300-dev rows with effective batch 32, LR 1e-4, and shared
  loss `A6 + 0.25*A0`. The VLM remains BF16/eager and entirely frozen. A0 is
  the already registered normalized frozen current-minus-prior CLS feature
  repeated across 60 active positions with four zero reserved positions;
  neither labels nor probe logits enter any token cache.
- All three sealed prediction sets are computed and frozen before the
  protected 483 labels may be opened once. The final aggregation reads only
  the frozen predictions and aligned copied labels. Gold remains sealed even
  if R39 GO.
- Commit `be10d9f` froze and pushed the complete R39 chain before execution.
  At 2026-07-30 05:23 +08:00 the duplicate-safe launcher started as PID 29064.
  The first outcome-free stage runs sealed Block-8 caching on GPU 0 as PID
  28952 and dev fixed64 caching for Seed 17 on GPU 1 as PID 30532. Both
  processes are alive, stderr is empty, both GPUs own only their registered
  worker, and shard counts are increasing. The 483 labels and gold remain
  unread.
- Projector Seed 17 stopped before training because the frozen parameter-count
  receipt incorrectly reused R32 smoke's 7,948,800 count. That smoke used
  input width 16, while the already frozen R39 architecture consumes 768-D
  PRTA tokens and therefore has 9,873,920 parameters. No checkpoint or
  projector output was created and no protected outcome was read. Correcting
  this derived receipt changes neither architecture nor training/gate choices;
  valid outcome-free caches remain reusable.
- Commits `91f6560` and `f92822a` pushed the exact receipt repair, regression
  test, and guarded cache-preserving resume. All six dev/sealed token indices
  are valid PASS artifacts with labels absent. At 2026-07-30 05:51 +08:00 the
  resume launcher started as PID 22396; projector Seeds 17/29 are now fresh
  processes 19020/28556 on GPUs 0/1. The 483 labels and gold remain sealed.
- R39 reached the registered terminal verdict
  `GO_R39_FROZEN_VLM_TRANSFER`. All three projector checkpoints and all three
  outcome-blind sealed prediction sets were frozen before the single
  483-label reveal. Gold remained unread.
- On 483 patients / 4,821 rows, A6 versus frozen A0 gained +15.01 pp macro-F1
  with patient-bootstrap 95% CI [+13.80,+16.14]. A6 versus current-only gained
  +3.22 pp [+2.47,+4.02], versus query-only +15.77 pp
  [+14.59,+16.84], and versus prior-shuffle +2.19 pp [+1.39,+3.05].
  Every comparison had positive effects in Seeds 17/29/43 and passed its
  preregistered pooled +2 pp/positive-CI gate.
- A6 true-pair macro-F1 was 0.2096/0.2502/0.3089 for Seeds 17/29/43. The
  corresponding frozen-A0 values were 0.1442/0.0894/0.0848 and current-only
  values were 0.1827/0.2000/0.2894. These modest and seed-dependent absolute
  scores limit the claim to registered relative transfer, not clinical
  deployment or gold generalization.
- The final interface audit PASSed: Qwen trainable parameters 0, no pixel
  input, exactly 64 tokens, matched prompt and projector capacity, and sealed
  predictions frozen before reveal. The reveal count is exactly one; source,
  per-shard, and checkpoint hashes were not recomputed.
- The parameter-count incident was purely a pre-training engineering receipt
  mismatch: 7,948,800 came from an input-width-16 smoke while the unchanged
  768-to-2560 projector has 9,873,920 parameters. No protected outcome had
  been read, all valid outcome-free caches were reused, and no frozen
  architecture, loss, seed, control, threshold, or bootstrap choice changed.
- The complete registered chain is now R37.1 three-seed internal GO → R37C
  one-shot 300-dev GO → R38 fixed-64 survival GO → R39 frozen-VLM transfer
  GO. This confirms TIER-CXR-VLM under the frozen silver-cohort protocol;
  expert gold remains quarantined and cannot be used to strengthen the claim
  without a separately registered descriptive confirmation.

## Repository closeout and experiment-gap audit

- The repository has no root `README.md`, so a new reader currently encounters
  nine root-level authority/planning/proposal files with no declared reading
  order. This is the largest handoff problem; code organization itself is
  already conventional (`configs/`, `docs/`, `reports/`, `scripts/`, `src/`,
  `tests/`).
- `history/2026-07-30-legacy-proposals/CAPES_Final_Complete_Proposal_CN.md`
  and `history/2026-07-30-legacy-proposals/DIVE_Proposal.md` are now labeled
  historical proposal surfaces. The active TIER authority is
  instead `TIER_CXR_VLM_Next_Stage_Proposal_CN.md`,
  `TIER_CXR_VLM_Empty_Result_Tables_CN.md`, and
  `reports/R39_FROZEN_VLM_TRANSFER_FINAL_CN.md`. Moving CAPES/DIVE into a
  dated history package will reduce ambiguity without deleting provenance.
- The repository already preserves prior planning closures under five dated
  `history/` packages. A matching closeout package and a small history index
  are preferable to deleting old documents.
- R39 has a compact reproducibility surface: one frozen config, dedicated
  cache/train/predict/reveal/aggregate scripts, focused tests, and a terminal
  report. Runtime data, checkpoints, predictions, and credentialed images are
  outside Git and must remain so.
- Historical reports and protocol specs are numerous but appropriately named;
  they should be indexed rather than physically reorganized, because moving
  them would break many existing local references and add little reader value.
- The active R39 evidence already covers the core shortcut boundary:
  capacity-matched frozen A0, current-only, query-only, within-finding
  cross-patient prior shuffle, exact-64/no-pixel/zero-trainable-VLM audits,
  three paired Seeds, and patient-cluster bootstrap. These should not be
  described as missing ablations.
- The original proposal's Sections 17–21 contain a much broader R32-era paper
  wish list. It includes raw two-image VLM, naive concatenation, always-rich,
  random-route, continuous/oracle routing, multiple ensemble heuristics,
  per-tier removals, 32/96-token budgets, unshared projectors, 8B VLM,
  time reversal, ROI shuffle, image blank, label permutation, side swap,
  grounding, generation, external/gold, and second-backbone studies.
  Completing every row is neither necessary for the already registered R39
  core GO nor protocol-valid on the revealed 483 cohort.
- The strongest current paper gap is not another Seed. It is a fair strong
  baseline package: raw two-image frozen VLM and naive fixed-64 concatenation,
  evaluated on a new outcome-independent cohort or under a separately frozen
  post-reveal protocol. Without it, the result establishes A6 over A0 and
  shortcut controls, but does not yet show superiority over the most direct
  multi-image VLM formulation.
- A VLM-level time-reversal control is also high value. R37.1 proves
  representation/logit equivariance before the VLM, while R39 does not report
  whether frozen-VLM predictions reverse according to
  Improved↔Worse/New↔Resolved. This should be an audit of frozen predictions
  where possible, not a tuning signal.
- PRTA-CXR has a clean component registry: A2 classification only; A3 adds
  transition alignment; A4 adds inversion; A5 adds CMCP; A6 combines
  classification, alignment, inversion, CMCP, and state preservation. Only A6
  received the full formal three-seed qualification; A3/A6 evidence outside
  that chain is engineering-only, and A2/A4/A5 are not a matched formal
  component ablation series.
- Therefore the most informative method ablation is a frozen A2/A3/A4/A5/A6
  ladder on a new development cohort, with equal training budget and paired
  Seeds. It would attribute the A6 gain to alignment, inversion, CMCP, and
  state preservation rather than merely showing full A6 beats A0.
- Per-tier removal and routing ablations from the old TIER proposal do not map
  one-to-one onto the implemented PRTA-CXR A6 architecture. The implemented
  model uses a query-conditioned cross-time adapter with state and transition
  resamplers, not the original robust-versus-rich hard router. Before running
  any “remove Tier 0/1/2/3” experiment, the paper must decide whether its
  method claim is PRTA-CXR or the older four-tier router. Mixing these
  namespaces would create an invalid ablation story.
- CAPES/DIVE are clearly historical proposal families and are safe to archive
  from the root. Their content remains useful as provenance and should be
  labeled non-authoritative rather than deleted.
- The closeout organization now has one root README, a current-status document,
  a reports index, a history index, and a dedicated experiment-gap audit. Only
  CAPES/DIVE moved; protocol specs and historical result paths remain stable.
- `pyproject.toml` previously described the package as non-confirmatory
  CAPES-first/DIVE-soft code. That description was stale after the completed
  TIER/PRTA chain and is updated to the current project identity.
- The advertised repository-wide Ruff command initially exposed 28 preexisting
  issues in six historical/utility scripts: three genuinely unused or
  unnecessary constructs and 25 intentional imports after local `src` path
  insertion. The cleanup removes the unused constructs and marks only those
  five path-bootstrap files with file-level `E402` exemptions; no experiment
  behavior or protocol is changed.
- The tracked `data/official` package contains small pinned CheXTemporal gold
  annotation files but no credentialed images. Because those files remain
  quarantined even though tracked, the repository now has an explicit
  `data/README.md` warning that file presence is not outcome-access authority.
- The four active frozen configs now have a compact index that distinguishes
  the historical R37 STOP lineage from the terminal R37C/R38/R39 GO chain and
  forbids editing a completed config into a new 483-test claim.
- Full pytest reached 700 PASS / 1 expected XFAIL / 1 FAIL. The failure is an
  old R6 closed-manifest resolution test:
  `test_r6_resolution_and_nested_manifests_are_exact_and_fail_closed`.
  Its false checks concern frozen R6 implementation-observation and
  freeze-record hashes; the changed closeout files are outside that R6 source
  allowlist. A clean base-commit comparison is required before classifying it
  as preexisting drift.
- The exact targeted R6 test also fails at clean detached commit `24f57c3`
  with the same `gate["passed"] is False` versus expected frozen `True`
  assertion. This proves the failure predates the repository closeout. Do not
  “repair” it by changing closed R6 registry hashes; document it as historical
  frozen-manifest drift while retaining 24/24 current-method focused PASS.

## Phase 7 component-ablation and strong-baseline execution

- The user explicitly authorized the P1 package: matched A2/A3/A4/A5/A6
  component ablations plus strong temporal/VLM baselines.
- The revealed 483-test cannot be reused for model, hyperparameter, threshold,
  seed, or checkpoint selection. Gold remains sealed.
- The first action is protocol and cohort feasibility, not GPU launch. Existing
  caches and registered receipts should be reused without recomputing unchanged
  source, shard, or checkpoint hashes.
- The existing `PRTAVariant` registry already defines the required ladder:
  A2 classification-only, A3 + alignment, A4 + inversion, A5 + CMCP, and A6
  + inversion + CMCP + state preservation. The shared runner already switches
  these losses, but locked formal mode currently admits only A6.
- R37.1 used a one-time 1,815-patient holdout drawn from the former R37
  pretraining partition and removed those patients from its 10,287-patient
  training set. Those observed validation outcomes must not be reused for the
  new ablation selection.
- A valid new roster can be constructed deterministically from only the
  remaining R37.1 training patients, while retaining the existing Block-8 and
  text caches. Its split rule and size must be frozen before reading its label
  support; inadequate post-freeze support must cause STOP rather than a
  resplit.
- The current formal trainer uses the same adapter and head construction for
  A2-A6, so a new formal mode can preserve capacity and optimization exactly.
  It needs separate schema/status/output roots, full-count validation, and
  outcome-independent roster/firewall checks.
- The current exact-64 R39 surface contains A6, A0, current-only, and shuffled
  tokens only. Naive concatenation, Siamese/signed-absolute temporal tokens,
  raw two-image Qwen3-VL, and VLM-level reversal require newly frozen
  implementations; they cannot be inferred from the already revealed R39
  outcomes.
- R40 is now frozen as a post-R39 secondary protocol. The deterministic
  development split uses only the remaining 10,287 R37.1 training patients,
  selects 1,500 by SHA-256 order with namespace/Seed fixed in advance, and
  requires STOP without resplitting if label or CMCP support is inadequate.
- Component attribution includes `A6_no_state`. This is necessary because the
  original A2-A6 ladder confounds state preservation with inversion and CMCP;
  A6 minus A6_no_state is the only registered state-only contrast.
- The R40 runner keeps all trainable capacity and optimization settings
  matched, activates Z2 projection only for A4/A6_no_state/A6, validates every
  roster and protected-outcome firewall, and writes separate formal schemas
  and outputs instead of mutating closed R37/R37.1 artifacts.
- Fourteen focused tests, Ruff, compileall, CLI help, PowerShell parsing, and
  `git diff --check` pass for the frozen roster/runner/launcher package.
- A final pre-commit path check caught that the draft R40 config pointed at a
  nonexistent guessed Qwen directory. It was corrected to the already proven
  local R39 model path `H:\Xiyao_Wang\001_models\Qwen3-VL-4B-Instruct`;
  no download, model load, or outcome access occurred.
- The first direct roster command stopped at Python import time because the
  standalone builder lacked the repository `src` bootstrap. No source row,
  label support, roster manifest, cache, or protected outcome was read; the
  runtime root contains only the empty stdout and import traceback.
- The first strong-baseline implementation slice is outcome-independent and
  covers the registered B0 frozen-current-image probe and B2 Siamese
  prior/current plus signed/absolute-difference probe. Both reuse the frozen
  BiomedCLIP encoder and the R40 patient-disjoint roster; all backbone
  parameters remain frozen and no protected outcome or interim R40 metric is
  an input to their construction.
- B2 encodes prior and current images once per batch, concatenates normalized
  prior CLS, normalized current CLS, their signed difference, and their
  absolute difference, then trains only the registered finding-conditioned
  linear probe. The resulting feature width is 3,072 and the directionality
  behavior is covered by focused reversal tests.
- The B0/B2 launcher is fail-closed on baseline/Seed/GPU choices, refuses
  duplicate active commands and non-fresh status/log/output paths, and does
  not start work merely because the component jobs are still running.
- Six focused runner/launcher tests, Ruff, compileall, PowerShell syntax
  parsing, and `git diff --check` pass for this partial strong-baseline slice.
  B1 naive exact-64 concatenation, B3 raw two-image Qwen3-VL, and the VLM
  reversal execution surface remain pending, so the full comparison-bundle
  task is not yet complete.
- At 2026-07-30 11:51 +08:00 the user explicitly paused R40. Exact command-line
  verification tied launcher PIDs 29212/5552 and child PIDs 26336/30980 only
  to A2 Seeds 17/29 before they were stopped. Both stderr logs remained empty;
  neither task produced a complete valid result, and no interim metric was
  inspected.
- The launcher's generic external-termination status was reclassified as
  `PAUSED_R40_COMPONENT_SEED_BY_USER`, not an engineering or scientific STOP.
  Both R40 GPU allocations were released and no R40 component command remains
  active. A later poll found unrelated tooth9 PID 3664 using GPU 1; it was not
  interrupted. A future R40 resume must archive the incomplete boundaries and
  relaunch the same frozen A2 tasks fresh before advancing the fixed queue.

## Phase 8 PRTA-Gen authority and namespace

- The supplied design correctly reclassifies R39 as a frozen-Qwen
  five-candidate sequence scorer: it demonstrated progression transfer through
  exact-64 PRTA tokens, not unconstrained or evidence-grounded generation.
- The next valid scientific gate is representation sufficiency, not immediate
  LoRA report generation. Laterality, coarse anatomy, degree, and dynamic
  evidence retrieval must each be measured before those fields are authorized
  in generated text.
- The proposed generative system keeps BiomedCLIP, PRTA, alignment, and the
  exact-64 compiler frozen; trains the projector plus attention-only Qwen LoRA;
  masks system/user/visual-prefix labels; and optimizes assistant-token causal
  loss. G-CMCP and temporal-reversal losses belong after the R40 readiness
  gate, not in the first adapter smoke.
- A naming collision exists: `configs/r40/r40_component_and_baseline_v1.json`
  already freezes a post-R39 component/baseline protocol that the user paused.
  The new work will live under a distinct `configs/prta_gen/` namespace and
  will refer to its stages as PRTA-Gen R40A/R40B without mutating the older
  frozen config or its incomplete runtime artifacts.
- The revealed 483 cohort is historical/descriptive only for all PRTA-Gen
  development. Gold/external outcomes remain sealed. Existing R37.1
  training-side patients and caches may be considered only after a new
  patient-disjoint roster and label-availability audit pass.
- The R37 transition annotations contain a reliable original comparative
  sentence plus finding/progression, but no pre-existing trusted laterality,
  coarse-anatomy, or degree columns. The new extractor therefore masks the
  finding surface, accepts only literal location/degree expressions, maps
  conflicts or absence to `Unspecified`, and never synthesizes evidence.
- `GenerativeVLMAdapter` now supports teacher-forced assistant-only SFT,
  arbitrary target-sequence likelihood, and autoregressive `generate()` from
  a single injected exact-64 prefix. Its runtime audit rejects pixel/image/
  video paths and any trainable Qwen parameter outside registered LoRA names.
- The optional PEFT entrypoint freezes the model first and permits exactly
  `q_proj/k_proj/v_proj/o_proj` with rank 16, alpha 32, and dropout 0.05 in
  the frozen config. G-CMCP code is present only as a later-gated loss helper;
  the config keeps R41/R42 locked.
- The committed literal-target audit passed on 33,677 training and 5,814
  development rows from 8,787/1,500 disjoint patients. No protected cohort or
  old R40 process was touched.
- Supported probe classes under the pre-frozen thresholds are all five
  progression classes; Left/Right/Bilateral; Minimal/Mild/Moderate/Marked;
  and six coarse anatomy classes (Upper lung, Lower lung, Hilar, Cardiac
  silhouette, Mediastinal, Diffuse).
- Midline laterality, Middle lung, and Pleural lack frozen support; they stay
  excluded. `Unspecified` rows are not converted into pseudo-labels. The audit
  produced 17,710/3,049 Tier-A training/development rows, so evidence sentence
  retrieval may be probed, but evidence generation remains locked.
- The post-support probe freeze selects exact-64 PRTA Seed 17 only for the
  representation audit, a within-partition/finding cross-patient shuffle with
  Seed 40011, and a deterministic 64-row cache smoke before any full cache.
  Probe performance has not been observed.
- The formal probe runner trains separate capacity-bounded linear readouts for
  true-pair, current-only, prior-shuffle, and finding-one-hot query-only
  features. It selects only the pre-frozen supported target rows and refuses
  any token/target example or patient-order drift.
- Formal field decisions remain deferred until all three registered probe
  Seeds and the patient-cluster bootstrap exist. A single probe run cannot
  unlock generation.
- The repaired compact cache completed without changing token semantics:
  development contains 5,814 rows in 23 shards and training contains 33,677
  rows in 132 shards. Both receipts report exact `[64,768]` tensors, no
  labels/sentences, and false protected/hash/old-R40 firewalls.
- Progression point estimates were positive against current-only, query-only,
  and prior-shuffle for all three probe Seeds. However, the frozen
  2,000-replicate patient-cluster bootstrap failed the decisive Seed 17
  prior-shuffle comparison: +1.061 pp with 95% CI
  [-0.925, +3.263] pp. The required lower bound is strictly above zero.
- Therefore the formal progression aggregate is
  `STOP_PRTA_GEN_R40A_FIELD_INFORMATION`, and the overall readiness decision
  is `STOP_PRTA_GEN_R40A_INFORMATION_SUFFICIENCY`. This is a new generative
  information result, not a reversal of the completed R39 classifier GO.
- Stop-before-bootstrap diagnostics also found field instability:
  laterality Seed 43 was negative against current-only/prior-shuffle, anatomy
  Seed 43 was negative against current-only, and degree Seed 17 was negative
  against query-only. They cannot supply a field-level escape from the failed
  upstream progression gate.
- No rescue, threshold change, Seed selection, Qwen overfit, evidence
  retrieval, LoRA SFT, G-CMCP/reversal, 483 reuse, or gold/external reveal is
  authorized. The implemented generative adapter remains an audited
  engineering surface only.

## Phase 9 case-driven repair framing

- The old R40A field probe compressed each 64-token sequence into only three
  means: state, transition, and relation. Its STOP proves that this registered
  readout did not robustly distinguish the true prior from prior shuffle; it
  does not yet prove that every individual token in the exact-64 sequence lacks
  recoverable information.
- A valid repair must therefore test the compression hypothesis directly. It
  cannot merely add epochs, choose Seed 29/43, remove the Seed-17 comparison,
  weaken the CI gate, or call the already implemented Qwen adapter a success.
- The case study may inspect old-development predictions and token behavior,
  but those rows become descriptive-only. Any new route decision must be made
  on a separately frozen discovery boundary and confirmed once on a distinct
  qualification boundary.
- The success target has two layers: a scientific information gate for the
  exact-64 sequence under registered controls, followed by a small R40B
  engineering overfit that verifies causal-LM plumbing. Passing only the
  overfit smoke cannot rescue a failed information gate.
- The current proposal still contains its older robust/rich routing narrative
  alongside the terminal R39 update. The operative PRTA-Gen protocol is more
  precise: progression/laterality/anatomy/degree/evidence must unlock before
  generative LoRA, and only observed fields may enter the output schema.
  Phase 9 must add a top-level case-study repair addendum rather than silently
  rewriting the historical proposal body.
- The failed R40A implementation reduced each token region to one mean,
  yielding 2,304 features. The cache itself retains all 64×768 values for
  true/current/shuffled branches, so token-level variance, maxima, matched
  differences, and query-conditioned weighting remain auditable without
  changing the frozen token sequence.
- Each formal shard stores aligned `true_tokens`, `current_tokens`, and
  `shuffled_tokens` with shape `[rows,64,768]`, plus hashed example/patient IDs
  and finding names. Labels and report sentences remain outside the token
  cache. This is sufficient for a descriptive token-collision case study
  without re-encoding images or touching protected cohorts.
- The complete old-development prediction surface exists for progression
  (three Seeds), laterality (three), anatomy (three), and degree (Seed 17
  only, correctly stopped before Seeds 29/43). The case study must not fill the
  missing degree Seeds because they are part of the closed stop sequence.
- Existing R37 failure-analysis code establishes the repository pattern:
  validate schema/status/firewalls and exact row alignment first, emit only
  descriptive aggregates and hashed failure overlap, and mark observed rows
  unavailable for repair selection. The new PRTA-Gen case study will follow
  that pattern and add anonymized true-vs-shuffle collision categories.
- The real 5,814-row/1,500-patient case study completed. Seed 17 contains 917
  true-sensitive, 623 shuffle-favored, 2,298 both-correct, and 1,976
  both-wrong rows. Only 148 rows are true-sensitive in all three Seeds, while
  939 are both-wrong in all three; this is broad class/readout instability,
  not one small fixed bad-case list.
- Seed-17 prior sensitivity is strongly label-dependent. Net
  `(true-sensitive - shuffle-favored)/rows` is +14.68% for Stable and +6.20%
  for New, but -3.52% for Improved, -9.27% for Worse, and -4.85% for
  Resolved. Pneumothorax is the clearest finding-level negative cluster at
  -21.99%.
- True-sensitive rows have much larger true-vs-shuffle token RMS than
  shuffle-favored rows: Seed-17 transition 4.78 versus 4.00 and state 2.76
  versus 2.31. Persistent collision examples can have extremely small
  transition RMS (0.21–0.96), whereas persistent true-sensitive New examples
  reach 13.5–14.3. This supports testing content-aware token evidence strength,
  not another global mean or class-voting rule.
- All four reserved token positions have exactly zero true-vs-shuffle RMS.
  The practical evidence sequence is 60 active tokens; Phase 9 must keep the
  exact-64 interface but should not pretend the four padding/reserve positions
  contain recoverable temporal signal.
- Historical case-study lineage reinforces the same lesson: R33/R33A failed
  after repeated routing/projection/bridge searches on one observed cache,
  while R37.1 succeeded only after translating a diagnosed symmetry failure
  into one parameter-free Z2-equivariant repair and validating it on a fresh
  holdout. Phase 9 should emulate the latter pattern.
- The active proposal begins with the terminal R39 GO but its main body is a
  historical robust/rich routing design. The Phase-9 repair will keep that
  history intact and add a dated top-level addendum: the immediate goal is a
  progression-only generative route, not unsupported grounded multi-field
  report generation.
- The smallest diagnosis-aligned candidate family is deterministic and
  capacity-bounded: (1) per-region mean/std/max features and (2) four
  orthonormal cosine position components per active 20-token region. Both use
  the unchanged first 60 active positions of the exact-64 sequence, leave the
  four zero reserve positions untouched, and keep a single linear classifier.
  This tests within-region distribution/layout loss without introducing a
  second backbone or a high-capacity rescue model.
- The committed deterministic roster passed without resplitting: fit has
  5,787 patients/22,036 rows, discovery 1,500/5,869, and one-shot
  qualification 1,500/5,772. All five progression classes exceed the frozen
  support threshold in every partition; the smallest is Resolved with
  830/210/205 rows.
- The first ordered repair candidate did not survive discovery. Seed 17 was
  positive versus query-only/prior-shuffle (+2.78/+8.13 pp), but Seed 29 was
  +6.64 pp versus query-only and **-5.18 pp versus prior-shuffle**. Regional
  mean/std/max therefore increases information capacity without producing
  Seed-stable correct-prior specificity. Seed 43 is unnecessary under the
  predeclared first-failed-gate rule.
- The second ordered cosine candidate also stopped immediately: Seed 17 was
  +7.60 pp versus query-only but -1.23 pp versus prior-shuffle. R40A.1 is
  formally closed with qualification unread.
- Source inspection after closing R40A.1 found a more specific architectural
  mismatch in the failed probes. The actual R38 layout is
  `query 4 | state 12 | global transition 16 | local transition 16 |
  relation 12 | reserve 4`, but R40A/R40A.1 pooled arbitrary
  `0:20 | 20:40 | 40:60` blocks. Those cuts mix query with state and split
  both global/local transition groups. The Qwen path sees all positions, so
  this mismatch plausibly explains why R39 transferred while shallow probes
  were unstable.
- R40A.2 should first respect the registered token-type boundaries rather than
  add a nonlinear rescue model. Its discovery2 must be newly drawn from
  R40A.1 fit patients; observed R40A.1 discovery rows are excluded, while the
  original qualification list remains sealed.
- The committed R40A.2 roster audit passed without resplitting. It excluded
  exactly 1,500 observed R40A.1 discovery patients/5,869 rows, assigned a
  fresh discovery2 of 1,500 patients/5,882 rows from the old fit boundary,
  retained fit2 at 4,287 patients/16,154 rows, and preserved the sealed
  qualification boundary at 1,500 patients/5,772 rows. The smallest
  discovery2 class is Resolved with 215 rows, so every registered support
  threshold passes before any R40A.2 outcome is read.
- The first R40A.2 candidate cache passed on GPU0 with 33,677 aligned rows,
  132 shards, and width 3,840. `semantic_layout_means_v1` keeps separate
  means for query/state/global-transition/local-transition/relation groups
  and retains the outcome-free exact-64 cache boundary.
- Fresh discovery2 Seed 17 strongly supports the semantic-layout diagnosis:
  true-pair macro-F1 is 0.3967 versus query-only 0.2062 and prior-shuffle
  0.3529, for +19.05/+4.38 pp. Current-only is 0.2705. This passes both
  registered Seed-level point gates but is not yet a three-Seed GO.
- Seed 29 independently passes by a wide margin: true-pair macro-F1 0.3562
  versus query-only 0.2234 and prior-shuffle 0.1569, for +13.28/+19.94 pp;
  current-only is 0.2750. The candidate has now passed both registered point
  gates in two Seeds, authorizing the final discovery Seed 43.
- Seed 43 completes the point-gate sweep: true-pair macro-F1 0.3840 versus
  query-only 0.2522 and prior-shuffle 0.3130, for +13.18/+7.10 pp;
  current-only is 0.2527. All three Seeds pass both +2 pp requirements, but
  selection still depends on the frozen 2,000-replicate patient bootstrap.
- The preregistered discovery2 aggregate is
  `GO_PRTA_GEN_R40A2_DISCOVERY`. Every Seed's 95% patient-cluster lower bound
  remains above +2 pp versus both required controls. The narrowest bound is
  Seed 17 versus prior-shuffle at +2.404 pp; the other prior-shuffle lower
  bounds are +18.329 and +5.765 pp. Query-only lower bounds are +16.975,
  +11.562, and +11.721 pp. This is sufficient to select the first candidate,
  but progression generation remains locked until qualification.
- The ordered selector chose `semantic_layout_means_v1` and read only its
  discovery aggregate. `qualification_unlocked=true`, while qualification
  outcomes, protected 300-dev, revealed 483, gold, and old R40A development
  remain outside selection. The higher-capacity semantic-moments candidate is
  now skipped by design.
- One-shot qualification Seed 17 passes both point gates, but the
  prior-specific margin is narrow: true-pair macro-F1 0.3876 versus
  query-only 0.2083 and prior-shuffle 0.3659, for +17.93/+2.17 pp;
  current-only is 0.2919. The eventual bootstrap lower bound, not this point
  estimate alone, will determine the route.
- Qualification Seed 29 is robustly positive: true-pair macro-F1 0.3512
  versus query-only 0.2248 and prior-shuffle 0.1657, for +12.64/+18.55 pp;
  current-only is 0.2673. This reproduces the discovery direction on the
  previously sealed patients and authorizes the final Seed 43.
- Qualification Seed 43 also passes: true-pair macro-F1 0.3900 versus
  query-only 0.2515 and prior-shuffle 0.3077, for +13.85/+8.23 pp;
  current-only is 0.2587. All three one-shot qualification Seeds pass point
  gates, leaving only the patient-bootstrap lower-bound criterion.
- The frozen qualification rule is correctly implemented as two simultaneous
  conditions: every Seed's point effect is at least +2 pp, and every
  patient-bootstrap 95% CI lower bound is above zero. It does not require the
  CI lower bound itself to exceed +2 pp. Under that registered rule,
  qualification is `GO_PRTA_GEN_R40A2_QUALIFICATION`: Seed 17 versus
  prior-shuffle has point +2.169 pp and lower bound +0.298 pp, while all other
  required lower bounds are wider. Progression generation is now unlocked;
  all other fields remain locked.
- R40B now has a pre-outcome bounded engineering ladder rather than an
  open-ended tuning loop. It starts with the originally registered 32-row,
  3-epoch settings; only a pure underfit STOP may unlock preregistered
  12-epoch and then 24-epoch attempts. Every attempt starts from fresh Qwen
  base/projector state and uses the identical fixed cohort, exact-64 prompt,
  attention-only LoRA targets, two-field JSON schema, and pass gate.
- The frozen 32-row cohort rule draws only from R40A.2 fit patients, uses one
  row per patient, and fixes progression counts at 7/7/6/6/6. It explicitly
  refuses the R39 projector because that checkpoint was trained on the
  separately revealed 300-dev boundary.
- The committed cohort builder returned `PASS_PRTA_GEN_R40B_SMOKE_COHORT`
  with 32 unique fit patients and the exact registered 7 Stable, 7 Improved,
  6 Worse, 6 New, and 6 Resolved rows. Targets contain only finding and
  progression; 300-dev, revealed 483, gold, and external remain unread.
- Transformers 5.5 returns a `BatchEncoding` from the real Qwen chat-template
  call. Treating it as a list iterated the string key `input_ids`; extracting
  that registered field produces a 171-position prompt with exactly 64
  placeholder IDs. This is an API-shape compatibility fix, not a prompt or
  training change.
- The original registered 3-epoch R40B attempt is an engineering-contract
  PASS but a formal underfit STOP. Mean teacher-forced loss fell from 1.3338
  to 0.5545 (ratio 0.416), cache/exact-64/mask/no-pixel/trainable boundaries
  passed, and generated schema/finding copy were both 100%. However
  teacher-forced token accuracy was only 87.83% and greedy progression
  accuracy was 5/32 (15.625%), so it is
  `STOP_R40B_REGISTERED_3EPOCH_UNDERFIT`, not a runnable generator.
- This failure is informative rather than another interface failure: Qwen
  learned the exact JSON envelope and finding copy but did not bind the
  progression value to the visual tokens in three optimizer updates. That is
  exactly the preregistered condition that unlocks the 12-epoch/accumulation-8
  bounded overfit attempt on the same cohort.
- The second, fresh 12-epoch attempt nearly but not fully overfits. Contract,
  cache, JSON schema, and finding copy remain 100%; loss falls 1.3338 to
  0.0456 (ratio 0.0342) and teacher-forced token accuracy reaches 98.70%.
  Greedy progression rises from 5/32 to 27/32 (84.375%), but the frozen gate
  requires 32/32. It is therefore
  `STOP_R40B_BOUNDED_12EPOCH_UNDERFIT` and authorizes only the final
  preregistered 24-epoch attempt.
- The remaining error is no longer schema learning: all 32 rows generate a
  valid exact-key JSON object and copy finding correctly. The final attempt
  specifically tests whether more optimizer updates on the unchanged
  visual-to-progression binding close the last five memorization errors.
- The final 24-epoch free-greedy attempt still fails the exact overfit gate.
  Loss reaches 0.0185 (ratio 0.0139), teacher-forced token accuracy 99.35%,
  and schema/finding stay 32/32, but progression is 29/32. The three residual
  errors are Edema Worse->New, Lung Opacity Worse->Improved, and Lung Opacity
  Resolved->New. The status is
  `STOP_R40B_BOUNDED_24EPOCH_UNDERFIT`; the greedy ladder is exhausted.
- This terminal pattern separates token information and JSON form from local
  autoregressive choice. R40A.2 already proved prior-specific progression
  information on a sealed cohort, and R40B teacher forcing is nearly exact;
  the failures arise when one early progression token commits the rest of the
  free sequence. A genuinely new engineering route is constrained structured
  decoding: score exactly five complete legal JSON sequences with the
  already-required length-normalized `score_sequence` method and emit the
  highest-scoring one.
- R40B.1 must use a new deterministic 32-patient fit cohort excluding all
  observed R40B patients. The old cohort may support the diagnosis but cannot
  be reused to claim the constrained route passed.
- The R40B.1 authority freezes one fresh 24-epoch attempt and exactly five
  complete legal JSON candidates per row. Scores use mean token
  log-likelihood with registered-order tie breaking; free-greedy output is
  descriptive history only and is not part of the new gate.
- The committed R40B.1 cohort passed with 32 unique patients, exact 7/7/6/6/6
  class counts, and zero overlap with all 32 observed R40B patients. Protected
  300-dev, revealed 483, gold, and external remain unread.
- R40B.1 closed as `STOP_PRTA_GEN_R40B1_CONSTRAINED_UNDERFIT`. Loss fell
  1.3086 to 0.0152 and uniform teacher token accuracy reached 99.14%, but
  whole-JSON mean-likelihood selection achieved only 28/32 progression. The
  four errors all have close top-two candidate scores, while schema and
  finding remain 32/32.
- Uniform assistant CE and whole-sequence mean scoring dilute the semantic
  decision: only a few of 465 supervised tokens encode the progression value,
  while most tokens are common JSON syntax or prompt-copied finding text.
  R40B.2 will address that exact imbalance with a frozen progression-span
  loss weight and span-only conditional likelihood. It must use a third
  patient-disjoint cohort; neither observed 32-row set can be reused.
- The real Qwen tokenizer offset audit confirms the compact `New` value is one
  distinct token (ID 3564) and the span mask selects only that token, not JSON
  punctuation, finding copy, or EOS. R40B.2 can therefore upweight and score
  the semantic field without weakening assistant-only supervision.
- The committed R40B.2 cohort passed with 32 unique patients, the exact
  7/7/6/6/6 class counts, and zero overlap with all 64 patients observed by
  R40B/R40B.1. All protected-data firewalls remain false.
- R40B.2 closed as `STOP_PRTA_GEN_R40B2_PROGRESSION_SPAN_UNDERFIT`.
  Weighted training reached 98.07% overall token accuracy but only 82.22% on
  the 45 progression tokens and 24/32 span decisions. A fixed 20x weight under
  the unchanged high learning rate destabilized the semantic class instead of
  solving dilution.
- Qwen tokenization reveals a cleaner discriminative interface: the first
  progression tokens are unique across all five values (`Stable` starts 623,
  `Improved` 81110, `Worse` 54, `New` 3564, `Resolved` 65394), even though
  Stable/Worse have a second subtoken. R40B.3 can therefore optimize an
  explicit five-way CE at the first differing assistant position and
  deterministically emit the registered full value.
- R40B.3 must use a fourth new cohort excluding all 96 observed patients.
  The direct class loss will be combined with a small uniform assistant-SFT
  auxiliary, rather than another scalar reweighting of the same token loss.
- The real tokenizer confirms every finding shares a nine-token legal JSON
  prefix before the progression decision and returns the exact unique
  first-token registry `[623, 81110, 54, 3564, 65394]`. The direct five-way
  logit comparison is therefore well-defined before the fourth cohort exists.
- The repaired committed builder froze R40B.3 with 32 unique patients, exact
  7/7/6/6/6 class counts, and zero overlap with all 96 patients from the first
  three cohorts. Protected data remain unread.
- R40B.3 closed as `STOP_PRTA_GEN_R40B3_DIRECT_CLASS_UNDERFIT`. Overall
  teacher token accuracy reached 97.83%, but progression-token accuracy was
  77.78% and direct five-way output only 23/32. All engineering contracts
  passed; the causal-LM semantic decision itself remained unstable.
- Four independent 32-patient cohorts now show that projector plus
  attention-LoRA can learn JSON form but does not reliably memorize the
  progression mapping under preregistered small-sample budgets. Continuing to
  change LM loss weights, learning rates, or decoding would be tuning the same
  failed assumption.
- The convergent architecture is to separate semantic decision from language
  realization. R40A.2 already qualified a semantic-layout readout on sealed
  patients. R40B.4 will put a small fresh progression head on the same five
  semantic token groups and emit the two-field JSON deterministically. Qwen
  free generation remains explicitly locked rather than being declared a
  success by proxy.
- R40B.4 freezes a 499,973-parameter LayerNorm-MLP head over the 3,840-wide
  semantic-layout means. It uses only a fifth 32-row training cohort,
  full-batch optimization, and deterministic two-field emission; its PASS
  cannot be interpreted as a Qwen or free-text result.
- The fifth cohort passed with 32 unique fit patients, exact 7/7/6/6/6 class
  counts, and zero overlap with all 128 patients observed by the four failed
  Qwen routes. All protected-data firewalls remain false.
- R40B.4 passed its frozen overfit gate. The 499,973-parameter structured head
  reduced full-batch training loss from 1.6262604 to 1.1920928e-07
  (ratio 7.33027e-08) and produced 32/32 correct progression values, 32/32
  valid two-key JSON objects, and 32/32 finding echoes on the fifth fresh
  cohort.
- The successful claim is deliberately narrow: a semantic-layout exact64
  representation can drive a deterministic progression-only structured
  emitter in an engineering overfit smoke. The result does not unlock Qwen
  free generation, anatomy/laterality/degree/evidence fields, R41 Qwen SFT,
  scientific generalization, gold, or external evaluation.
- The case-study sequence isolates two different facts. R40A.2 proves
  prior-specific progression information survives on a sealed qualification
  boundary; R40B through R40B.3 shows that four Qwen causal-LM readout
  variants do not reliably bind that information under the frozen
  small-sample budgets. R40B.4 runs by separating the semantic decision from
  language realization, not by claiming Qwen is not an LLM or by silently
  weakening the original gate.

## Phase 10 R40C framing

- The highest-priority evidence gap is patient-level generalization of the
  R40B.4 structured decision head, not another Qwen loss/decoding variant.
- R40C must remain an internal development-generalization study because its
  source is the already-used R40A.2 fit partition. A patient-disjoint split
  prevents direct row leakage but does not create a new scientific
  confirmation cohort.
- The five observed R40B cohorts contain 160 patients in total and are
  immutable diagnostic evidence. R40C must exclude all of them before
  deterministic train/development assignment.
- Schema validity and finding echo are deterministic interface contracts, not
  primary evidence. The primary outcome must be held-out five-class
  progression macro-F1 with true-pair controls and patient-cluster bootstrap.
- R41 Qwen SFT, other generation fields, protected 300-dev, revealed 483,
  gold, and external evaluation remain locked during the entire R40C
  pre-outcome package.
- Aggregate-only support inventory confirms the R40A.2 fit partition contains
  4,287 patients/16,154 rows. Excluding all five observed 32-patient cohorts
  removes exactly 160 patients and leaves 4,127 patients/14,687 eligible rows.
- Remaining unique-patient label support is Stable 2,968, Improved 1,405,
  Worse 1,601, New 990, and Resolved 489. Resolved is the limiting class, so
  the frozen R40C one-row-per-patient roster must select rare classes first
  and retain a safety margin instead of attempting to exhaust all 489.
- A balanced 1,000-patient train / 500-patient development design
  (200/100 patients per class) is supported with substantial margin even
  after enforcing global patient uniqueness. This is large enough to test
  held-out behavior while keeping the first run bounded and outcome-blind.
- The existing formal token cache provides `true_tokens`, `current_tokens`,
  and `shuffled_tokens` for every training example without labels or report
  sentences. Query-only remains a finding-registry control rather than a
  token-cache payload.
- R40C will therefore train four independent, capacity-matched heads per Seed:
  true-pair, current-only, prior-shuffle, and a 12-class finding one-hot padded
  to the identical 3,840-wide input. This preserves the 499,973-parameter head
  budget across every arm.
- The primary gate will compare held-out true-pair macro-F1 to query-only and
  prior-shuffle. Current-only remains a registered descriptive control.
  A true-head counterfactual evaluation on current/shuffled tokens may be
  reported diagnostically but cannot replace the primary arm comparison.
- Frozen training scales R40B.4's optimizer to 1,000 patients without
  route-specific tuning: AdamW at 0.001, no weight decay, batch 128,
  100 epochs, fixed 800 update steps, gradient clip 1.0, no early stopping,
  and no checkpoint selection.
- The proposed internal GO requires, for every Seed: true-pair macro-F1 at
  least 0.30, every class recall at least 0.15, true minus query/shuffle at
  least +2 pp, and patient-bootstrap 95% CI lower bounds above zero. These
  thresholds are frozen before any R40C roster or prediction exists.
- The query-only arm is now pinned to the same canonical 12-finding registry
  used by the frozen R37.1 candidate. Its one-hot vector is zero-padded to
  width 3,840 before the identical head, preventing an implicit registry or
  parameter-budget change.
- Real-receipt no-write preflight passes. It confirms 4,127 remaining fit
  patients/14,687 rows, the exact 160-patient historical exclusion, sufficient
  support for 1,000/500 balanced selection, four registered arms, three Seeds,
  499,973 parameters, and exactly 800 updates per arm.
- The preflight explicitly reports `real_roster_written=false` and
  `gpu_training_started=false`; the R40C runtime root does not exist. Both
  GPUs remained idle, and protected 300-dev, revealed 483, gold, and external
  flags stayed false.

## Phase 11 R40C frozen roster receipt

- The one-time real roster write returned
  `PASS_PRTA_GEN_R40C_ROSTER_SUPPORT`. Its immutable receipt is 350,714 bytes
  with SHA-256
  `9C076B684BC258EFA60E568004F851CD9EE079EA4DDEA549BD0D2ABCFBF9B0CB`.
- Recomputed scalar audit confirms 1,000 training patients/rows and 500
  development patients/rows. Stable, Improved, Worse, New, and Resolved are
  balanced at 200 each in training and 100 each in development.
- Training and development patient overlap is zero. All 160 patients from the
  five observed R40B–R40B.4 cohorts remain absent, and the one-row-per-patient
  invariant holds.
- Development outcomes, protected 300-dev, revealed 483, gold, and external
  outcomes remain unread. Resplitting and scientific claims remain disabled.
- The runtime root contains only `roster.json`; there are no Seed results,
  checkpoints, aggregates, or R40C Python workers. Both GPUs remain at
  0 MiB/0% utilization.
- The committed builder returned the full roster payload to its local CLI.
  This did not change selection or gate state, but it was unnecessary
  identity-level output. The CLI handoff is now reduced to a tested scalar
  receipt summary; the roster bytes and hash must remain unchanged.

## Phase 12 R40C internal generalization result

- The authorized automatic Seed 17 → 29 → 43 → aggregate chain completed
  without retries or engineering errors. The terminal status is
  `GO_PRTA_GEN_R40C_INTERNAL_GENERALIZATION` with zero gate failures.
- True-pair development macro-F1 is 0.5058, 0.4941, and 0.4827 for Seeds
  17/29/43. The minimum class recall is 0.38, 0.38, and 0.36, comfortably
  above the frozen 0.15 floor for every Seed.
- True-pair minus query-only effects are +19.72, +20.10, and +17.42 pp with
  95% CI lower bounds +14.97, +15.68, and +12.64 pp. True-pair minus
  prior-shuffle effects are +10.50, +10.91, and +9.64 pp with lower bounds
  +5.75, +6.52, and +5.27 pp.
- The registered descriptive current-only comparison is also positive for
  every Seed: +11.71, +7.38, and +8.75 pp, with all bootstrap lower bounds
  above zero.
- All comparisons use 500 development patients, 2,000 patient-cluster
  replicates, and bootstrap seed 40001. Schema validity and finding echo are
  1.0 for all Seeds; each arm completed exactly 800 updates.
- The result supports patient-disjoint internal development generalization of
  the progression-only structured head within the already-used R40A.2 fit
  domain. It is not independent confirmation and does not reverse the failed
  Qwen causal-LM routes.
- Qwen free generation, R41 Qwen SFT, other generation fields, scientific
  claims, protected 300-dev, revealed 483, gold, and external evaluation all
  remain locked. Independent-confirmation planning is unlocked, execution is
  not.
- Aggregate SHA-256 is
  `34E2D09C7E2734B34AD028D6E3CDDFE6F08BD84F50D38541B8BD643F14EC0027`.
  All Seed/aggregate stderr logs are empty, no matching process remains, and
  both GPUs returned to 0 MiB/0%.

## Phase 13 downstream inventory

- No tracked R41, R42, R43, or R40D runner/config currently exists. The
  repository contains the implemented `GenerativeVLMAdapter`, attention-LoRA
  installer, R40B Qwen engineering runners, and early roadmap/lock fields,
  so downstream execution requires a new frozen authority rather than a
  direct command.
- The original PRTA-Gen roadmap defines R41 as structured generative Qwen SFT,
  R42 as G-CMCP plus time-reversal evidence-grounded generation, and R43 as
  untouched gold/external one-shot confirmation. It explicitly keeps the
  exact-64 PRTA interface fixed and requires projector plus attention LoRA
  before any optional MLP-LoRA mutation.
- The original roadmap recommends 20,000–50,000 high-quality pair×finding SFT
  rows, with real comparative sentences preferred and field availability
  gated by literal source support. R40C itself only established progression
  information for the structured head; laterality, anatomy, degree, and
  evidence remain unqualified.
- Local official CheXTemporal files contain annotations only
  (`gold_progression_pairs.parquet`, `gold_bboxes.parquet`, datasheet/license);
  there is no `data/external` tree. The last known runtime availability audit
  is under the older F: R32 root and must be refreshed read-only before any
  R43 design.
- The existing R40 readiness config registered Qwen3-VL-4B, attention LoRA
  rank 16/alpha 32/dropout 0.05, projector LR 1e-4, LoRA LR 2e-5, three
  epochs, effective batch 32, Seeds 17/29/43, G-CMCP weight 0.25/margin 0.2,
  and reversal weight 0.25, but all R41/R42/gold unlock flags remain false.
- Both GPUs are explicitly user-authorized, but GPU availability does not
  override missing code, insufficient field supervision, external image
  availability, DUA constraints, or the first-failed-gate rule.
- The local Qwen3-VL-4B-Instruct snapshot is complete at 8.28 GiB. Runtime
  dependencies are available (`torch 2.5.1+cu121`, Transformers 5.5.3,
  PEFT 0.18.1) on two 24 GiB RTX 3090 GPUs.
- The formal R40 token caches cover 33,677 training rows in 132 shards and
  5,814 development rows in 23 shards, with true/current/shuffled variants,
  no labels or sentences embedded, and protected/gold flags false.
- R40C used 1,500 of 4,127 eligible R40A.2 fit patients after historical
  exclusions, leaving 2,627 not selected into its train or development
  roster. These are a possible internal R41 development pool, not independent
  scientific confirmation.
- The original R41 gate cannot be copied literally: only progression has a
  passed patient-disjoint generalization result. Laterality Midline, anatomy
  Middle-lung/Pleural, and all fine evidence claims remain unsupported or
  unqualified. A defensible first R41 must therefore be progression-only and
  keep location/degree/evidence fields omitted.
- Historical gold readiness is unchanged at 16 untouched image-complete
  patients (9 MIMIC, 7 CheXpert); conservative overall MDE is about 35 pp.
  ReXGradient has 70 untouched annotated patients but zero resolved images.
  R43 can only be descriptive unless new independent images/labels arrive.
- A fresh scalar-only audit of the 2,627 patients left outside R40C finds
  5,919 eligible pair-by-finding rows. Unique-patient progression support is
  Stable 1,904, Improved 647, Worse 797, New 419, and Resolved 106. Resolved
  is therefore the binding class for a new patient-disjoint R41 split.
- A balanced 100/50-per-class train/development design is impossible after
  R40C because it would require 150 Resolved patients. The largest conservative
  fixed split that preserves a rare-class reserve is 50 training plus 25
  development patients per class; the remaining unselected patients may
  contribute additional training rows only after their partition is frozen.
- The live GPU audit now shows both RTX 3090 cards at 0 MiB and 0% utilization,
  with no compute application listed. Both devices are technically available
  for the user-authorized downstream sequence.
- The frozen R41A roster rule now passes a no-write preflight: 375 training
  and 125 development patients, exactly 75/25 per progression class, with six
  eligible Resolved patients still unused. It excludes all 160 historical
  Qwen-smoke patients plus all 1,500 R40C patients before hashing rows.
- R41A is explicitly a bounded internal progression-only survival study.
  Its registered G0 arm trains only the exact-64 projector; G1 trains the same
  projector plus attention-only LoRA. Both use three epochs, effective batch
  32, no checkpoint selection, and free greedy two-field JSON decoding.
- The formal token cache has only true-pair, current-only, and shuffled-prior
  variants; it contains no reversed-time tokens. However, the frozen cache
  builder already reconstructs exact-64 tokens from prior/current Block-8
  features, so a legitimate R42A reverse cache can be built by calling the
  unchanged PRTA model with current and prior swapped. No heuristic token
  permutation is needed.
- The repository already contains the registered sequence-level
  `generative_prior_preference_loss` and the five-class involutive reversal
  mapping. This makes progression-only G-CMCP plus reversal technically
  implementable if and only if R41A passes; evidence-grounded sentence
  generation remains outside the qualified fields.
- R41A now has a fail-closed two-GPU sequence launcher and aggregate gate.
  It runs G0/G1 concurrently per Seed, never retries, accepts only a registered
  aggregate GO/STOP, and exposes scalar receipts rather than row identities.
  Seven focused unit tests pass.
- R42A is now frozen before any R41A outcome. It initializes from the matching
  R41A G1 Seed checkpoint and compares one-epoch `G-CMCP` against
  `G-CMCP + time reversal`, with weights/margin 0.25/0.25/0.2 and no checkpoint
  selection. Reverse exact-64 tokens are rebuilt by swapping input order in the
  unchanged PRTA model.
- The R42A primary gate requires every Seed to retain macro-F1/class support,
  at least 95% schema/finding consistency, correct-prior preference above
  chance, positive query/shuffle effects with bootstrap lower bounds above
  zero, at least 90% mapped reversal accuracy, and at least +1 pp over the
  frozen R41A G1 baseline.
- A fresh outcome-free R43 readiness audit still finds only 16 untouched
  image-complete official-gold patients (7 CheXpert, 9 MIMIC), no resolved
  ReXGradient parents, no external tree, and no independent expert labels.
  Worst-case +2 pp confirmation requires 4,906 patients; the current
  conservative MDE remains about 35.02 pp. Therefore R43 is pre-registered to
  stop before any gold outcome or prediction if reached.
- The master R41A -> R42A -> R43 chain is fail-closed and automatic. It stops
  at the first aggregate/readiness STOP, never retries, and reaches R43 only
  after both upstream survival gates pass. Fourteen focused tests now pass.
- Repository-wide validation reports 805 passed, one expected xfail, and the
  same preexisting R6 frozen-manifest failure already reproduced on clean
  commit `24f57c3`; the new R41–R43 package introduces no additional failure.
- The complete pre-outcome authority was committed and pushed as `c796630`
  before any roster write or GPU launch. The one-time real R41A roster then
  returned `PASS_PRTA_GEN_R41A_ROSTER_SUPPORT`; it is 118,039 bytes with
  SHA-256
  `2BA53C95BDDC78CBE1E585CF5954708892B6106578DA812226D87F94FD4F77C0`.
- Real post-write preflights pass for the R41A runner, two-GPU R41A sequence,
  R42A reverse cache (500 rows, 1,000 required Block-8 DICOM features,
  zero missing), and the complete master chain. No GPU work has started and
  all execution output directories remain fresh.
- The first authorized launch stopped during Seed-17 model setup before any
  training update, checkpoint, prediction, or scientific result. G0 accessed
  a nonexistent normalized audit key (`trainable_parameters`) instead of the
  adapter's real `trainable_parameter_count`; the paired launcher then
  terminated G1. This is an implementation-contract failure, not an outcome.
- The repair changes only audit-field normalization in R41A and the matching
  R42A check. Data, roster/hash, Seeds, losses, hyperparameters, gates, and
  output schema remain unchanged. A regression test now pins the real
  Qwen-audit field names; 22 focused tests pass.
- Failed pre-training artifacts were preserved under a timestamped runtime
  `history/` directory; the active R41 root now contains only the immutable
  roster. Repeated real preflights confirm the same roster hash and frozen
  R41A/R42A/R43 authority before relaunch.
- The second engineering stop exposed a deterministic-audit bug, not a model
  outcome: G1 LoRA dropout (`0.05`) was still in training mode when uncached
  and cached first-step logits were computed sequentially. Cache equivalence
  must be checked with stochastic layers disabled; the audit now temporarily
  uses evaluation mode and restores the original mode in `finally`.
- R41A is now formally terminal STOP. All six arms completed, so the result is
  not an engineering failure. G1 cleared macro-F1, schema/finding, and the
  query-only effect gates, but `Worse` recall failed in every Seed, G1 never
  exceeded G0, and Seed 17 additionally failed the prior-shuffle point/CI
  gates. The frozen conjunction therefore records eight failures.
- This narrows the interpretation of the prior R40C GO: the exact-64
  semantic-layout representation supports a structured progression head, but
  the registered Qwen attention-LoRA free-greedy readout did not establish
  stable progression binding. It does not justify R42A, R43, free-report
  generation, other fields, external/gold, or clinical claims.
- Phase 14 is analysis-only. Row-level predictions may be used solely to
  aggregate de-identified failure modes on the same completed development
  cohort; observed errors cannot authorize post-hoc tuning or turn a new run
  on that cohort into confirmatory evidence.
- Each R41A arm result already contains aligned `targets` plus four 125-value
  integer prediction arrays (`true_pair`, `current_only`, `query_only`,
  `prior_shuffle`). The payload therefore supports reproducible confusion,
  migration, and control-sensitivity analysis without joining patient
  identities or reading any new outcome.
- The immutable roster stores train/development rows below `partitions`, not
  as a top-level development array. The analyzer must validate the result's
  registered ID ordering against that nested schema but must emit no ID field.
- The existing R40A case-study analyzer supplies the correct repository
  precedent: fail closed on seed/alignment/firewall drift, write only to a
  fresh output, label the result descriptive-only, and prohibit reuse of the
  observed development cohort for selection.
- R41A does not require reopening token caches for this diagnosis. The six
  frozen result files plus the immutable nested roster are sufficient to
  recompute confusion, G0/G1 migration, control sensitivity, and cross-Seed
  stability. This keeps the new analysis narrower than the earlier R40A
  token-distance case study.
- The technical report contract is frozen before implementation: result-first
  summary, visual evidence, explicit 125-patient development scope and metric
  definitions, reproducible method, limitations/robustness, then only
  outcome-independent next steps. A static tracked figure is appropriate
  because the selected source-of-truth surface is the repository Markdown
  report, not a dashboard.
- The pre-analysis analyzer was committed and pushed as `0445a6d` before its
  one-time real run. The derived case-study artifact has SHA-256
  `59C64E21B1520F439CB41F729E4720137D2A6803BEFA4E25A9D51684B86EA37A`,
  contains 125 rows/125 patients, emits zero `example_id`/`patient_id` keys,
  and records `new_training_started=false`.
- The dominant G1 failure is not merely a small average-score miss. G1 emits
  `Worse` 0, 7, and 9 times out of 125 predictions across Seeds 17/29/43,
  despite 25 true `Worse` targets per Seed; its corresponding recall is
  0.00/0.08/0.08. Error destinations are unstable: Seed 17 spreads `Worse`
  mainly into Stable/Improved, Seed 29 mainly into Resolved, and Seed 43
  mainly into New/Improved.
- Adding attention LoRA does not supply a stable improvement over G0. At the
  row level, G0-correct/G1-wrong cases number 20/24/25, versus G0-wrong/
  G1-correct cases 22/11/20 for Seeds 17/29/43. This is nearly balanced only
  for Seed 17 and net harmful for Seeds 29/43, matching the registered
  macro-F1 deltas of -0.46/-13.40/-6.85 pp.
- Across G1 Seeds, only 31/125 development rows are unanimously correct.
  Another 45 have at least one correct Seed, while 49/125 are wrong in every
  Seed (12 with the same wrong label, 37 with differing wrong labels). This
  supports seed-instability and persistent-error descriptions, not causal
  explanations.
- Controls show some real-pair signal but not a stable binding solution. For
  true pair versus prior shuffle, G1 has true-sensitive/control-favored counts
  of 11/9, 15/4, and 20/7. Seed 17's two-row net is weak and its registered
  bootstrap gate still fails; the other Seeds' positive point differences do
  not rescue the failed class-support and G0-comparison conjunction.
- Finding slices are descriptive and often small. The strongest visible
  contrast is that G1 is consistently better on Cardiomegaly and Enlarged
  Cardiomediastinum but worse on Pleural Effusion, Atelectasis, and Lung
  Opacity; Lung Lesion has zero G1 accuracy but too little support for a
  standalone claim. These slices must not become post-hoc tuning targets on
  the same cohort.
- Finding denominators are materially uneven: 28 Edema, 28 Lung Opacity, 27
  Pleural Effusion, 17 Atelectasis, 11 Cardiomegaly, 6 Enlarged
  Cardiomediastinum, 5 Pneumothorax, 2 Pneumonia, and 1 Lung Lesion. The report
  will foreground class-level and cross-Seed evidence; low-support finding
  slices remain illustrative only.
- The active Proposal already states the R41A STOP and no-retry boundary, so
  Phase 14 should add a dated read-only diagnosis subsection rather than
  rewrite the broader historical proposal. Project status and both indexes
  should promote the new case-study report immediately after the terminal
  R41A result.
- Phase-14 validation introduces no new full-suite regression: 814 tests pass
  and one is expected xfail. The sole failure remains the documented R6
  closed-manifest hash drift, which is outside the R41A analysis surface and
  already reproduces on clean commit `24f57c3`.
- Phase 15 is a distinct post-R41A development authority, not a retry of the
  failed gate. It must first prove genuinely unused five-class patient support;
  otherwise the correct terminal result is a feasibility STOP. The observed
  R41A error pattern may motivate a hypothesis but may not select patients,
  thresholds, checkpoints, Seeds, or class weights on the same cohort.
- The first scalar-only R44 inventory finds 2,127 unused patients and 4,153
  eligible rows inside the remaining R40A.2 fit partition, but unique-patient
  class support is 1,584 Stable / 451 Improved / 580 Worse / 272 New /
  **1 Resolved** after excluding all five R40B cohorts, the 1,500-patient R40C
  roster, and all 500 R41A patients. A five-class R44 cohort is therefore
  impossible from this partition without reusing an observed patient.
- The earlier R41A preflight's six-patient `Resolved` reserve cannot be treated
  as six currently eligible patients. Five reserve patients were selected for
  R41A through another label and are excluded at the patient level; the
  post-R41A inventory correctly leaves only one patient with any Resolved row.
- The R40 target registry already exhausts the available outcome-independent
  source roster into 8,787 training and 1,500 development patients. The
  development outcomes were used by the closed R40A information audit, while
  the training patients were partitioned across R40A.1/R40A.2 and downstream
  cohorts. There is no undeclared third split in the frozen target authority.
- The only separately registered confirmation sources are not a usable R44
  development cohort: R43 requires 4,906 gold patients for the frozen worst-
  case +2 pp target, while the last readiness audit found only 16 untouched
  image-complete official-gold patients, no executable external patients, and
  no independent labels. Gold/external also remain protected and cannot be
  repurposed for post-R41A method development.
- A fresh 2026-07-31 outcome-free readiness preflight reproduces exactly 16
  untouched image-complete official-gold patients (7 CheXpert, 9 MIMIC), zero
  executable external patients, absent `data/external`, and no independent
  labels. ReXGradient contributes 70 untouched annotations but all 238 image
  references are locally missing. The conservative MDE remains 35.02 pp.
- Taken together, both candidate sources fail before modeling: the unused R40
  fit remainder lacks five-class support (`Resolved` n=1), while the protected
  confirmation surfaces lack scale/images/labels and cannot be converted into
  a development set. No GPU experiment is currently protocol-valid.
- Official ReXGradient sources change the acquisition assessment: the
  `rajpurkarlab/ReXGradient-160K` Hub repository publicly lists 273,004
  downsampled PNG images from 160,000 studies / 109,487 patients, split into
  train/validation/public test, with ten `deid_png.part00`–`part09` archive
  parts and per-split metadata. The dataset images are therefore obtainable in
  principle, although CheXTemporal itself redistributes annotations only.
- R44 must not use ReXGradient public test images for development. A viable
  acquisition would have to map the 70 CheXTemporal patients to the official
  ReXGradient split metadata, prove they belong to an allowed split, and
  download the containing archive safely. The repository exposes only ten
  monolithic archive parts, not patient-addressable image files.
- The first `hf download --dry-run` for metadata and image parts failed during
  remote file metadata resolution despite `hf datasets info` succeeding. This
  is a client/endpoint or proxy metadata issue, not evidence that the files are
  absent; inspect the active HF endpoint and use the Hub API for size metadata
  before retrying.
- Deeper official Hub inspection shows `rajpurkarlab/ReXGradient-160K` is a
  **gated** dataset with `license: other`, despite being publicly discoverable.
  The local HF client has no saved token and is not logged in, so image
  acquisition requires the user/account holder to review and accept the
  dataset terms and authorize access.
- The local HF client is also configured to `https://hf-mirror.com`. That
  explains why repository listing could work while `hf download --dry-run`
  metadata resolution failed. Any authorized retry must use an explicit
  `HF_ENDPOINT=https://huggingface.co` process-local override, not mutate the
  user's global HF configuration.
- The official ReXGradient agreement is a hard authorization boundary. It
  requires the account holder to share contact information and accept a
  non-commercial/non-clinical research agreement, maintain safeguards, and
  download only the portion necessary for the research. The repository's ten
  concatenated tar parts do not expose patient-addressable files, so blindly
  downloading the full image archive for a small R44 cohort would conflict
  with the minimum-necessary clause unless separately justified by the user/
  institution.
- The local CheXTemporal checkout contains only README/DATASHEET/LICENSE plus
  the two gold parquet files; no silver annotations are present. Therefore the
  larger CheXTemporal silver pool cannot be used locally without a separate
  annotation acquisition and parent-image access plan.
- The open CheXTemporal repository does expose four silver artifacts. An
  official-endpoint dry run succeeds without authentication: 29.5 MB
  `silver_findings.parquet`, 28.1 MB `silver_studies.parquet`, 15.2 MB
  `silver_sentences.parquet`, and a 207.2 MB mask ZIP. R44 support auditing
  needs only the first two parquet files; masks and sentence text are not
  needed and should not be downloaded.
- CheXTemporal silver is the first plausible independent path: its card reports
  22,638 CheXpert and 8,497 MIMIC silver patients. The local machine already
  has the registered CheXpert/MIMIC parent roots. A CheXpert-only cohort could
  avoid the MIMIC-derived R40/R41 lineage, but this must be proven from
  patient/source metadata and on-disk image coverage before any label outcome
  or model run is inspected.
- The acquisition must remain two-stage and outcome-blind: first freeze a
  script that downloads only the necessary open parquet metadata and emits
  scalar source/class/image coverage; only if that support gate passes may a
  deterministic patient roster be frozen. Silver annotations are development
  labels, not independent expert confirmation.
- CheXTemporal `silver_findings.parquet` is sufficient by itself for the
  support audit: it contains dataset, patient, finding, five-way progression,
  and both parent-image relative paths. `silver_studies`, sentences, and masks
  are unnecessary for R44 progression-only feasibility.
- The exact open annotation revision is
  `81fd9cdd9b1208d8f8bd39d7a914c9b72fed8d79`; the local gold checkout already
  pins that same revision. The Hub reports `gated=false`, and the official-
  endpoint dry run works unauthenticated.
- Local prerequisites are plausible: the registered CheXpert and MIMIC image
  roots both exist and H: has 524.84 GiB free. Phase 15 should start with
  CheXpert-only support because it is cross-source relative to the MIMIC-based
  R40/R41 lineage and avoids the gated ReXGradient acquisition entirely.
- The frozen R44 audit code reads only the eight required silver finding
  columns and only `dataset`/`patient_id` from the gold registry. Its synthetic
  tests cover patient-disjoint rare-first selection, gold-patient exclusion,
  missing-image failure, and progression-registry drift. Focused tests, Ruff,
  compilation, and whitespace validation pass before any real silver outcome
  is acquired.
- The correct image gate is selection-scoped: every chosen train/development
  row must have both prior and current images, but unusable rows elsewhere in
  the source pool may be excluded. Requiring zero missing references across
  all CheXpert silver rows would be stricter than the frozen protocol and could
  create a false STOP despite adequate image-complete support.
- The one allowed CheXTemporal file matches both frozen acquisition checks
  exactly (29,502,280 bytes; SHA-256 `31237F...3C807`). No masks, report/study
  parquet, sentence parquet, or ReXGradient image archive was downloaded.
- The official silver paths are uniform five-component `.jpg` references
  rooted under the literal `chexpert/` prefix. The CheXpert subset contains
  197,449 pair-finding rows and 112,934 unique image references. The local
  parent root contains 223,650 files, so a one-pass relative-path index is
  semantically equivalent to repeated `Path.is_file` resolution after stripping
  that prefix and is substantially faster on this NTFS/H: layout.
- The independent CheXpert silver support gate is decisively feasible after
  gold-patient exclusion: the rare class `Resolved` still has 1,439 unique
  patients versus the frozen total need of 250. Every registered source row
  has both local images, and the rare-first deterministic in-memory allocation
  fills the exact 1,250-patient balanced roster without train/development
  overlap.
- This PASS proves data/readiness support only. It does not validate a model,
  authorize reuse of R41A development outcomes, unlock R42/R43, or convert
  MedGemma-derived silver labels into expert/gold/external confirmation.
- R44A can inherit the exact R41A progression target registry without
  normalization. After gold-patient exclusion, 196,616 CheXpert silver rows
  use one of the 12 frozen finding strings; 833 casing-variant rows are
  outcome-independently excluded. Five-class unique-patient support remains
  Stable 18,244; Improved 10,023; Worse 13,061; New 10,819; Resolved 1,430,
  still far above the frozen 250-per-class total need.
- The original R41A runner assumes an existing MIMIC exact64 token cache.
  R44A requires a new targeted CheXpert cache path: load only the roster's
  local JPEGs through the same frozen BiomedCLIP block-8 boundary, apply the
  same frozen PRTA Seed-17 checkpoint and exact64 compiler, then cache the
  true/current/shuffled variants. This is a source adapter, not a model or gate
  change.
- The R44A authority can pin the closed R41A terminal aggregate at SHA-256
  `73532A...5171`, the CheXTemporal gold registry at `22CDA4...D14B`, and the
  unchanged R37 candidate config at `8D4437...DEF0`. The frozen PRTA source
  remains Seed 17 with the existing BiomedCLIP text cache; only selected
  CheXpert JPEG block-8 features must be materialized anew.
- The exact deterministic R44A allocation remains well inside the rare-class
  boundary after cross-label patient consumption: 1,075 unselected patients
  still have at least one `Resolved` row. The selected 1,250 rows have complete
  local prior/current images, so the roster gate is feasible without relaxing
  any class, image, patient-disjointness, or gold-exclusion rule.
- The pre-outcome package preserves the closed-chain firewall in both config
  and executable aggregation: `downstream_unlock_allowed=false` forces
  `qwen_free_generation_survival_unlocked=false` and `r42_unlocked=false`
  even if the separately named R44A survival gate passes.
- The one-time roster realizes the preflight exactly; no post-selection
  replacement was needed. Its SHA-256 `60FE40...1C292` is now the runtime
  authority for the exact64 cache and all downstream R44A Seed/arm receipts.
- Targeted CheXpert exact64 generation is operational: all 2,500 selected
  images encoded without replacement or missing-file repair, and the frozen
  PRTA path produced all three registered token variants for 1,250 examples in
  98 seconds. The cache contains identity/finding alignment receipts but no
  progression labels, sentences, reports, or Qwen pixel inputs.

# R44A terminal finding (2026-07-31)

- R44A completed all six registered arms (G0/G1 × seeds 17/29/43), each with 94 optimizer updates and a valid checkpoint/evaluation receipt.
- The frozen aggregate returned `STOP_PRTA_GEN_R44A_CROSS_SOURCE_SILVER_SFT_SURVIVAL` with nine gate failures. G1 true-pair macro-F1 was 0.3503/0.3512/0.2863; its true-vs-prior-shuffle effects were -0.1474/+1.5886/-0.2486 pp, so correct-prior grounding did not survive the frozen multiseed gate.
- Query-only separation was large (+24.4157/+21.1441/+18.0435 pp), and schema validity plus finding echo were 1.0, but those properties are insufficient for the intended prior-sensitive scientific claim.
- R44A aggregate SHA-256 is `8860C6A7AF52665148713271B98B89592411FE57BEA70644E1B6E65E9F5DF335`; sequence-status SHA-256 is `9C075CD28192509C0F19C2F748059301E3459F2E38278FCA31F30D0675960A3B`.
- All protected outcome flags remained false, and R42/R43 remained locked. This terminal result is a STOP, not a tuning invitation.

# R45 direction-selection evidence (2026-07-31)

- The new user authorization broadens scope only to a separately named,
  outcome-independent follow-on direction. It does not authorize tuning or
  relabeling the closed R44A 250-patient development result.
- Official ICLR 2026 reviewer guidance evaluates whether the work asks a
  specific question, is well motivated and placed in literature, supports its
  claims with technically correct and rigorous evidence, and contributes
  significant new knowledge; state of the art is not itself required.
- The official author guide strongly encourages reproducibility and ethics
  statements plus code/data-processing details. For this project, that maps to
  immutable rosters/configs, multiseed controls, patient-cluster intervals,
  exact hashes, outcome firewalls, license/DUA boundaries, and a narrow
  clinical-claim boundary.
- A credible follow-on must address the shared R41A/R44A mechanism: schema and
  finding echo are solved, query-only separation is strong, but correct prior
  does not reliably beat shuffled prior. Simply scaling data, changing a
  threshold, adding Seeds, or teaching an explicit “shuffled” output would not
  constitute the required scientific contribution.
- Candidate direction for case-study testing: counterfactual prior-grounded
  generation, where training adds a representation-level hard-negative
  objective for correct versus shuffled/current-only evidence while retaining
  the same legal five-class free-generation target. The case study must first
  show that prediction invariance or migration supports this mechanism rather
  than class imbalance alone.
- R44A preserves the same row-level result contract as R41A but with explicit
  R44A schema/protocol/status, 250 development patients, 1,000 training
  patients, and 94 updates. All six results expose aligned targets and
  true/current/query/shuffle predictions, so a new identity-free analyzer can
  recompute every scalar without loading tokens, checkpoints, or images.
- The case-study authority will predeclare three mechanism discriminators:
  true-vs-shuffle prediction agreement and beneficial/harmful flip rates;
  G0-to-G1 correction/regression migrations by class; and cross-Seed
  consistency. High shuffle agreement across classes supports prior
  under-use, whereas failures confined to one class would instead support a
  class-emission explanation.
- R44A's frozen config explicitly disallows outcome-driven tuning, checkpoint
  selection, class reweighting, and downstream unlock. Its result payloads
  retain the four legal five-class prediction arms, so the new analyzer can
  measure correct-prior sensitivity without inventing a new output class or
  modifying the closed experiment.
- The committed one-time case study shows high G1 true-vs-prior-shuffle
  prediction agreement: 0.732/0.700/0.836 for Seeds 17/29/43. Of 250
  patients, 135 never change their predicted class under prior shuffling in
  any Seed; only 11 change in all three Seeds.
- Correctness-changing prior sensitivity is weak and nearly symmetric:
  true-only versus shuffle-only correct rows are 17/19, 22/19, and 6/6,
  producing net rows -2/+3/0. Thus the observed shuffle intervention changes
  outputs, but not reliably in the correct direction.
- G0→G1 migration is also unstable: recovery/regression rows are 35/28,
  22/19, and 19/35 (net +7/+3/-16). This directly supports an adapter
  optimization-instability mechanism alongside correct-prior under-use.
- The failure is not only a single-class emission problem. True/shuffle
  invariance appears across all five balanced classes, although Seed 43
  `Worse` remains especially severe (zero both-correct rows, 36/50 both-wrong
  with the same prediction). The case study therefore selects a
  representation-level counterfactual prior-grounding hypothesis rather than
  class reweighting.
- Identity-free case-study artifact:
  `DESCRIPTIVE_PRTA_GEN_R44A_FAILURE_CASE_STUDY`, 172,643 bytes, SHA-256
  `06CF579923BA8C061DA0D3017BE5305DDE6B1C3F4505F48B6195D55EDD3EC483`;
  12 anonymized cases, no identity fields, no new training.
- Novelty audit changes the candidate design. CORAL (arXiv:2607.03647, July
  2026) already penalizes answer invariance under generic hard-negative image
  swaps for medical VQA, so a generic contrastive swap loss would not be a
  defensible standalone contribution.
- TILA (ICLR 2026 submission) already uses temporal pair inversion, a
  change-aware contrastive loss, bidirectional CE, and temporal-consistency
  loss for three-class progression. Therefore R45 should not claim novelty
  from merely reversing prior/current order or enforcing an inverse label.
- Existing longitudinal report methods (longitudinal anatomical-token fusion
  and Libra's temporal alignment connector) establish multi-image fusion, and
  LUNGUAGE establishes structured longitudinal evaluation. The remaining
  project-specific gap is narrower: converting an already-qualified
  prior-sensitive delta representation into stable five-class free generation
  while proving correct-prior specificity against same-finding shuffled priors.
- The differentiated R45 candidate is a **Causal Delta Evidence Bottleneck
  (CDEB)**: learn a five-class auxiliary head from the explicit
  `true_pair - current_only` exact64 delta, convert its predicted distribution
  into a small fixed-budget soft evidence token block, and condition a frozen
  Qwen generator on those tokens. It retains the legal five-class JSON target,
  does not label shuffled priors as an artificial sixth class, and can be
  ablated into no-delta, no-evidence-token, and structured-head-only variants.
# 2026-07-31 Git transport diagnosis

- The process environment and user Git config both route HTTP(S) through the
  local Clash/Mihomo proxy at `127.0.0.1:7897`; the running `verge-mihomo`
  process is present.
- Proxied `curl.exe -I https://github.com` returns HTTP 200, while an explicit
  no-proxy request times out. Direct transport is therefore not a valid
  fallback on this host.
- Git for Windows is system-configured for OpenSSL and reproduces
  `SSL_ERROR_SYSCALL`; a command-scoped Schannel `ls-remote` reaches GitHub and
  gets a repository-level response. Use Schannel only for the exact registered
  remote and avoid persistent proxy/config changes.
- The exact configured origin succeeds with command-scoped Schannel. This is a
  delivery workaround only and does not change experiment authority.

# 2026-07-31 R45 roster design reuse boundary

- `build_prta_gen_r44a_roster.py` validates the frozen silver source and gold
  registry by hash, excludes gold patients, enforces the five-class registry,
  assigns one row per patient by stable SHA-256, and verifies both parent
  images. Those mechanics can be reused, but the closed R44A builder and roster
  must not be modified.
- R45 requires a separately named builder/schema with four partitions and an
  explicit exclusion of every patient in both R44A train and development.
  Qualification and confirmation assignment must be frozen before any model
  implementation or outcome read.
- After excluding the 1,250 R44A patients and the 77 registered CheXTemporal
  gold patients, the silver table contains 169,853 candidate rows from 21,388
  patients. Unique per-label patient support is Stable 17,131, Improved 9,137,
  Worse 12,081, New 9,935, and Resolved 1,084 before the final image-complete
  filter.
- A deterministic sealed-first simulation can fill 600/100/100/50 patients per
  class for train/development/qualification/confirmation, but leaves only 143
  unassigned Resolved patients after cross-label exclusivity. The more
  conservative 500/100/100/50 design fills all 3,750 rows and leaves 231
  Resolved patients, so it is the provisional R45 roster size pending the exact
  image-complete builder audit.
- The R44A roster writer serializes only stable example/image identifiers,
  paths, finding, progression, and study/patient keys into the protected
  runtime roster, while its CLI summary strips row payloads. R45 can preserve
  this identity-safe console behavior and extend the explicit pairwise
  disjointness check across all four partitions.
- The existing R44A unit coverage is consolidated in
  `tests/test_prta_gen_r44a.py`, not a builder-specific test file. R45 will
  receive its own test module so the new partition order and historical
  exclusions remain independently reviewable.
- The R45 builder now computes image completeness before deterministic
  assignment, rather than selecting a patient and only then discovering a
  missing image. This makes the frozen selection rule fail-closed and
  reproducible from the pinned source plus image-root inventory.
- Qualification and confirmation are assigned before discovery partitions.
  This protects rare-class support for the sealed cohorts and prevents later
  discovery behavior from influencing their membership.
- The exact image-complete preflight passed with 21,372 available patients and
  per-label support Stable 17,116, Improved 9,123, Worse 12,066, New 9,928,
  Resolved 1,075. It filled all four frozen partitions and left 224 unused
  Resolved patients, above the frozen reserve of 200.
- The one-time roster contains 3,750 mutually disjoint, one-row-per-patient,
  image-complete rows: train 2,500, development 500, qualification 500, and
  confirmation 250. Its byte size is 2,898,864 and SHA-256 is
  `0387FCF0B3DA09BE4CC99727EE1278C676BD2D946A87D4377E7F0088F1F7F4D8`.
- Both sealed outcome-read flags remain false. Building the roster necessarily
  used silver labels for stratified membership, but no qualification or
  confirmation prediction, model output, or metric was computed.

# 2026-07-31 R45 method-interface audit

- The qualified structured path pools the five registered exact64 semantic
  regions independently and concatenates their means into 3,840 features
  (`5 x 768`). This is the correct interface for an auxiliary delta head; it
  does not mix semantic token types or consume the four reserve positions.
- The existing free-generation path applies a fresh `TierTokenProjector` to all
  64 input-width-768 tokens and injects the resulting hidden-size-2560 block
  into Qwen exactly once. Its adapter already enforces assistant-only loss,
  exact placeholder count, frozen-base/LoRA boundaries, greedy decoding, and
  first-step cache equivalence.
- A minimal CDEB implementation can therefore remain compatible with the
  established adapter: compute `mean(true_pair) - mean(current_only)`, predict
  five-class logits with the existing small progression head, and transform
  the soft five-class distribution into an additive fixed-budget token-space
  evidence block before the unchanged Tier projector. The exact token
  placement and trainable boundary still need to be frozen after inspecting
  token-type metadata and projector internals.
- Positions 60-63 are physically present and attended but are currently mapped
  to one shared neutral embedding because they use the reserved token type and
  `valid_mask=false`. They are the only four positions that can carry a new
  evidence block without overwriting the qualified query/state/transition/
  relation regions at positions 0-59.
- R45 should therefore preserve the base Tier projector for positions 0-59,
  map the five-way soft delta distribution to four hidden-size evidence
  embeddings, replace only positions 60-63 in the projected bundle, and mark
  those four positions logically valid in the R45 audit. This keeps exactly 64
  physical injections while making the bottleneck explicit and ablatable.
- The full method's auxiliary head will use 3,840-wide
  `semantic_mean(true_pair) - semantic_mean(current_only)` features. The
  no-delta ablation will use true-pair semantic means; the delta-no-bridge
  ablation will optimize the auxiliary loss but leave reserve embeddings
  neutral. None introduces a sixth label or trains on shuffled-control labels.
- The existing cache compiler already materializes true/current/shuffled
  exact64 variants with zeroed reserve positions, no labels/sentences, and a
  one-pass compact image feature map. It can be generalized through an
  explicit R45 stage contract and a thin R45 entrypoint; duplicating the full
  cache implementation would create avoidable drift.
- The cache must include only train and development during discovery. Sealed
  qualification/confirmation tokens should be materialized only after the
  candidate and qualification protocol are frozen; this makes an accidental
  early sealed evaluation structurally impossible.
- The implemented `CausalDeltaEvidenceBottleneck` preserves the registered
  3,840-wide structured feature interface, uses a five-way softmax only, and
  replaces exactly positions 60-63 after Tier projection. Its injection helper
  preserves embeddings 0-59 byte-for-byte and records the four positions in
  the projected-bundle audit.
- The frozen discovery config limits the token cache to the 2,500 train and
  500 development patients, uses one Seed (17) for the four preregistered
  mechanism arms, and keeps Qwen fully frozen in every arm. This isolates the
  evidence bottleneck from the R44A LoRA-instability mechanism.
- Discovery compares projector-only baseline, true-pair/no-delta evidence,
  delta auxiliary loss without bridge, and full CDEB under the same one-epoch,
  79-update budget. The full candidate alone can unlock qualification, and
  the selection gate is already specified in the config rather than chosen
  after observing outcomes.
- The discovery runner keeps Qwen at zero trainable parameters, trains only
  the registered projector/CDEB modules, evaluates the same four control arms,
  and stores alignment arrays only inside protected runtime results. Its CLI
  receipt removes patients, example IDs, targets, and predictions.
- The aggregator uses paired patient-cluster macro-F1 bootstrap comparisons
  and enforces the predeclared accuracy, per-class, schema, specificity,
  baseline, no-delta, auxiliary-head, and true/shuffle-agreement gates.
- The discovery-only exact64 cache completed in 159.4 seconds: 3,000 rows,
  3,000 patients, 6,000 images, 24 shards, and 885,120,680 shard bytes.
  Repeated first-batch features were bit-identical, peak CUDA allocation was
  0.49 GiB, and stderr remained empty.
- Cache index SHA-256 is
  `2ECC1350A71C885CCF10BE4665CD1BDC1F532E1B309586FF5879294890A955B6`.
  It contains neither labels nor sentences; qualification/confirmation token
  and outcome-read flags all remain false.
- The post-cache runner preflight passed: 2,500 training rows, 500 development
  rows, 24 token shards, sampled shard shape 128 x 64 x 768 for all three
  variants, local Qwen present, sentinel ID 151662 exact, and all four method
  outputs fresh. Both GPUs were idle before method launch.
- First-pair arm receipts are structurally valid with 79 updates,
  cache-equivalence PASS, 100% schema/finding validity, checkpoints, and clean
  exits. Baseline true macro-F1 is 0.38065 versus prior-shuffle 0.34441;
  full-CDEB true macro-F1 is 0.34202 versus prior-shuffle 0.35461.
- Full CDEB's auxiliary true macro-F1 is 0.31226 and its true/shuffle same-
  prediction rate is 0.628. These preliminary values fail some registered
  discovery thresholds, but no terminal verdict is allowed until both
  mechanism ablations and the frozen aggregate are complete.
- Both ablations completed their 79 updates, cache-equivalence checks, 100%
  schema/finding validity, checkpoints, and clean exits. No-delta evidence
  reaches true macro-F1 0.31398 versus shuffle 0.27873, auxiliary macro-F1
  0.38697, and same-prediction rate 0.546. Delta-no-bridge reaches true
  macro-F1 0.26453 versus shuffle 0.27793, auxiliary macro-F1 0.30622, and
  same-prediction rate 0.822.
- Mechanistically, the no-delta bridge is more shuffle-sensitive and has a
  stronger auxiliary head than the delta variants, while the full bridge raises
  free-generation performance over delta-no-bridge but not over baseline.
  The frozen aggregate must quantify these comparisons and set the terminal
  unlock.
- R45 aggregate is terminal `STOP_PRTA_GEN_R45_CDEB_DISCOVERY`, SHA-256
  `9FC9DCEC7471DD169B63555B4BA395817ACB5187B3EA1B351F8D12C742BEE75E`.
  Exactly three registered gates fail: auxiliary true macro-F1 0.31226 <
  0.35; true-minus-shuffle -1.25861 pp < +1 pp; full-minus-baseline
  -3.86250 pp < +1 pp.
- The paired bootstrap intervals reinforce the same boundary:
  full-minus-shuffle CI95 [-5.72, +3.00] pp and full-minus-baseline
  [-7.84, +0.27] pp. Full CDEB does beat the no-delta generator by +2.80 pp,
  but this does not rescue correct-prior specificity or the strong-baseline
  comparison.
- Qualification and confirmation are not unlocked, no sealed tokens were
  materialized, no sealed outcomes were read, zero R45 workers remain, and both
  GPUs are idle.
- R45 must not be tuned around these failures. A further attempt requires a
  separately named hypothesis and an untouched development cohort. One
  promising mechanism to audit is constrained causal-evidence
  product-of-experts scoring: combine five legal JSON sequence scores from the
  frozen generator with a structured temporal head, rather than teaching Qwen
  arbitrary reserve embeddings.

# 2026-07-31 post-R45 novelty audit

- Generic expert-guided medical decoding is already occupied: LEAD injects
  pathology-classifier expert signals into every decoder layer and explicitly
  ablates auxiliary classification without injection. R46 cannot claim
  "structured expert guides Qwen" as its novelty.
- Generic structured/contrastive medical decoding is also occupied: CWCD uses
  category-specific structured generation and masked-image contrastive
  decoding. R46 cannot claim structured decoding or contrastive controls alone
  as new.
- Generic constrained decoding is mature (for example, DOMINO addresses
  subword-aligned formal constraints), and product-of-experts sequence fusion
  is also established in general-domain LLM work. A simple five-candidate
  reranker would not meet the intended novelty bar.
- The defensible new question is narrower: **can an explicit current-only
  causal margin arbitrate when a structured temporal expert is allowed to
  override a strong frozen generator, while preserving the generator on
  low-evidence cases?** This selective, head-safe temporal arbitration and its
  true/current/shuffle causal evaluation—not constrained JSON or PoE by
  themselves—would be the contribution.
- A likely R46 formulation is therefore Causal Evidence Arbitration (CEA):
  train a multiseed structured head on R45 train only; compare its true-pair
  confidence/margin against the current-only counterfactual; use a
  preregistered development-selected threshold to choose between the structured
  class and the frozen baseline class. Output remains the same legal two-field
  JSON, but the claim changes from free generation to selective
  progression-only structured generation.
- R45 terminal writeback now records the exact three gate failures, roster,
  cache and aggregate hashes, sealed-cohort firewall, mechanism interpretation,
  and R46 boundary in the dedicated report, Proposal, project status, root
  README, and report index. This documentation does not alter any runtime
  result or unlock a sealed stage.
- Fresh terminal validation passed 17 focused R45 tests, repository-wide Ruff,
  compileall, diff checking, and local Markdown-link resolution. The aggregate
  still reports every qualification/confirmation token, outcome, and unlock
  flag false; no R45 worker exists and both RTX 3090 GPUs are at 0 MiB / 0%.

# 2026-07-31 R46 authority design

- R45's frozen roster already separated 2,500 train, 500 observed development,
  500 sealed qualification, and 250 sealed confirmation patients. R46 may
  reuse only the 2,500 train patients for fitting; its discovery-development
  cohort must exclude every patient in all four R45 partitions.
- The R45 freeze retained 224 unselected image-complete `Resolved` patients.
  A balanced R46 development target of 50 patients per class is therefore
  feasible in principle and leaves at least 174 `Resolved` patients, subject
  to a fresh exact exclusion/support preflight.
- The existing exact64 cache contains only R45 train/development. R46 can reuse
  the immutable R45 train shards and must cache only its new 250-patient
  development cohort under a separately named runtime root; it must not
  materialize R45 qualification or confirmation tokens.
- R46 should train only the structured progression head, not Qwen or the failed
  CDEB bridge. The causal arbitration score must compare the head's true-pair
  and current-only distributions, and a registered fallback rule must preserve
  a separately frozen generator baseline on low-evidence cases.
- The existing `ProgressionDecisionHead` is a 3,840→128→5 LayerNorm MLP, and
  the R40C runner already provides train-only normalization, deterministic
  fixed-epoch training, counterfactual evaluation, legal JSON emission, and
  checkpoint receipts. R46 can reuse these audited primitives without
  inheriting R40C outcomes or altering the head architecture.
- The R45 source inventory has 1,075 image-complete `Resolved` patients before
  its four-way selection and 224 afterward; the other four classes have much
  larger support. A 50-per-class R46 development cohort is the largest
  conservative balanced choice that preserves a substantial rare-class
  reserve.
- The inherited R45 baseline checkpoint contains only the 12 projector tensors
  plus immutable method/Seed metadata; Qwen remained fully frozen. R46 can
  evaluate this exact checkpoint on the new development cache without
  retraining or selecting a new generator checkpoint.
- The R45 cache implementation can be adapted to cache only R46 development,
  while its loader can join immutable R45 train shards and new R46 development
  shards by example ID. This avoids rereading 5,000 training images and keeps
  every R45 sealed partition absent.
- Baseline controls should be generated once for true-pair, current-only,
  query-only, and prior-shuffle. Multiseed CEA then changes only the lightweight
  structured head and arbitration; it must never re-fit Qwen or the inherited
  projector.
- The immutable R45 inputs required by R46 are now pinned: roster SHA-256
  `0387FCF...F4D8`, aggregate `9FC9DCEC...75E`, train/development token index
  `2ECC1350...5B6`, and baseline projector checkpoint
  `41A0A3D1...C966`. The new authority must validate full hashes and byte
  lengths before any roster or GPU work.
- R46 roster preflight passes with 17,622 eligible patients after excluding
  every R45 patient. Exact remaining per-class support is
  Stable 13,833 / Improved 6,702 / Worse 9,266 / New 7,374 / Resolved 224.
  The frozen 50-per-class selection leaves 170 Resolved patients, above the
  registered reserve floor of 150.
- The preflight writes no real roster, starts no GPU process, and preserves all
  R45 qualification/confirmation token and outcome flags as false.
- After commit `57eebc3` was pushed, the R46 roster was written exactly once:
  250 development patients, 50 per progression class, no overlap with any
  R45 partition, 2,500 R45 train rows referenced for fit, and 170 unselected
  Resolved patients remaining. All protected and sealed flags remain false.
- The frozen R46 roster is 195,166 bytes with SHA-256
  `C5D22B38D88A26610FA69E093AFE234D22EF34266D3D47C94A3C8267245F1C91`.
- The R46 cache preflight passes for exactly the new 250-patient development
  partition, with the frozen PRTA checkpoint/text cache present and a fresh
  token root. It does not touch the immutable R45 training cache or either
  sealed R45 cohort.
- R46 can reuse the audited R45 free-greedy evaluation path by loading the
  frozen projector checkpoint instead of training it. The lightweight head
  path can reuse R40C's fixed-epoch train-only normalization and counterfactual
  logic, while the new code is limited to Jensen-Shannon causal scoring,
  coverage-quantile arbitration, and baseline fallback receipts.
- The frozen CEA authority uses Seeds 17/29/43, 100 epochs and 2,000 updates
  per lightweight head. Thresholds are derived only from R45-train score
  quantiles; one shared quantile is selected on the new R46 development cohort.
  Low-evidence predictions must equal the inherited baseline exactly.
- Seven focused CEA/cache/roster tests, targeted Ruff, compileall, JSON parsing,
  and both runner/aggregator CLI imports pass before any R46 token cache or
  model outcome exists.
- The R46 development-only cache completed in 37.7 seconds: 250 patients,
  500 images, two shards, 73,759,854 shard bytes, exact repeated-batch
  reproducibility, and 0.481 GiB peak CUDA allocation. It contains no labels
  or sentences and no sealed tokens.
- Its 1,954-byte index SHA-256 is
  `3296E5EA438537430D131293824A89CBB1851BBA837814C9063DE02BAC0272AE`;
  the config now pins this immutable receipt before outcome execution.
- Post-pin runner preflight passes: immutable 2,500-row R45 train cache plus
  250-row R46 development cache align, the inherited checkpoint has exactly
  12 projector tensors, local Qwen and sentinel 151662 are valid, all baseline
  and Seed outputs are fresh, and every sealed flag remains false.
- The inherited R46 baseline completed with true/current/query/shuffle
  macro-F1 0.39981 / 0.30742 / 0.13114 / 0.38993. Schema and finding echo are
  1.0, cache equivalence passes, Qwen/projector trainable counts are zero, and
  the result SHA-256 is `F3469195...5813`.
- Baseline true minus shuffle is only +0.99 pp on the new cohort, so R46 must
  earn its registered causal-control and bootstrap gates through the
  structured arbitration rather than inheriting a large generator effect.
- Seeds 17/29 both completed all 2,000 registered head updates with 499,973
  parameters and 0.098 GiB peak CUDA allocation. Their structured true
  macro-F1 values are 0.36275 and 0.38093, below the registered 0.40 per-Seed
  gate; the final verdict must still wait for Seed 43 and frozen aggregation.
- Seed 17's structured shuffle F1 (0.38870) exceeds its true F1, while Seed 29
  is nearly tied (0.37949 vs 0.38093). This preliminary pattern suggests the
  structured head may again lack stable correct-prior specificity, but it is
  not yet a terminal aggregate.
- R46 is terminal `STOP_PRTA_GEN_R46_CEA_DISCOVERY`. Quantile 0.65 was selected;
  CEA true F1 is 0.41843 / 0.40043 / 0.41207 with mean 0.41031, a pooled
  +1.057 pp over the inherited baseline. Eligible coverage is
  0.092 / 0.132 / 0.112 and actual override rate 0.056 / 0.084 / 0.072;
  low-evidence agreement is exactly 1.0.
- Five registered gates fail: all three raw structured heads are below 0.40,
  CEA-minus-baseline CI95 is [-0.914, +3.273] pp, and CEA true-minus-shuffle
  CI95 is [-2.845, +8.534] pp. Qualification and confirmation remain locked.
- The terminal aggregate is 183,421 bytes with SHA-256
  `FCB30C804D8A3A58A9F7337FE12819BFF37ACE6591D558A54B787D24A65C2D4B`;
  no R46 worker remains and both GPUs are idle.
- The frozen identity-free case study shows 66.4% raw structured unanimity and
  91.2% selected-CEA unanimity. Broad majority rules regress the baseline, but
  the strict 3/3 true consensus plus 3/3 current-only disagreement rule changes
  31/250 cases, recovers 8, regresses 5, and raises true macro-F1 from 0.39981
  to 0.41638.
- The same strict rule on prior-shuffle reaches only 0.38376 macro-F1 with
  8 recoveries and 12 regressions. This true/shuffle asymmetry motivates the
  separate R47 **Unanimous Counterfactual Consensus (UCC)** hypothesis.
- The case-study artifact contains no identities or row predictions; it is
  5,005 bytes with SHA-256
  `FF263268544D0658D1F48A8D54D0E9090C710CAB2DB98E519D9135EF3CA38651`.
  These R46 values may define R47 but cannot modify or rescue R46.
- R47 roster preflight passes after excluding all 4,000 R45+R46 patients.
  Remaining support is 17,372 patients, including 170 Resolved; the frozen
  100-per-class selection leaves exactly 70 Resolved patients as registered.
  No real roster, cache, GPU job, or sealed read occurred.
- R47 real roster is 387,900 bytes with SHA-256
  `A5EC3A579F9C283F67B74E11C0B7F98C1C1B39CE50754B078CF716E86A16A90C`.
- R47 method/cache authority implements the fixed 3/3 true and 3/3
  current-disagreement UCC rule with no threshold or quantile selection. Five
  focused tests, Ruff, compileall, JSON parsing, and the 500-row cache
  preflight pass before any R47 token or outcome read.
- R47 development cache completed in 45.9 seconds: 500 patients, 1,000 images,
  four shards, exact reproducibility, no labels/sentences, and no sealed
  tokens. Its 2,342-byte index SHA-256 is
  `2786C4037807B563935E7908E694E3B7AF2513F3410CAD670F02147CC3B252C9`.
- R47 inherited baseline completed with true/current/query/shuffle macro-F1
  0.39292 / 0.30953 / 0.13471 / 0.35399. True-minus-shuffle is +3.89 pp,
  materially larger than R46's +0.99 pp. Schema/finding/cache checks pass and
  both trainable counts remain zero.
- R47 Seeds 17/29 complete 2,000 updates with structured true F1
  0.39660/0.39422 and shuffle F1 0.34659/0.37204. Unlike R46, both observed
  Seeds show positive true-minus-shuffle direction; UCC still requires Seed 43
  and the frozen 3/3 rule.
- Seed 43 also completes 2,000 updates with structured true/current/shuffle F1
  0.40276/0.39257/0.37761. All three Seeds therefore show positive
  true-minus-shuffle direction on R47; execute the fixed UCC aggregate next.
- R47 is terminal `STOP_PRTA_GEN_R47_UCC_DISCOVERY`. UCC true F1 is 0.39731
  versus baseline 0.39292: only +0.440 pp, CI95 [-1.984, +2.921]. It also
  misses the absolute 0.40 floor.
- UCC does show robust true-minus-shuffle specificity: +5.921 pp, CI95
  [+1.423, +10.786], with 61/500 true overrides, 19 recoveries, 17 regressions,
  and net recovery +2. Thus strict consensus identifies temporal signal but
  does not add reliable predictive value over the frozen generator.
- Aggregate SHA-256 is
  `94003D276C376E32A46223E63C563CC3F15B841324C0599DE81F19348CC0D719`;
  no worker remains and both GPUs are idle.
- The next defensible question is therefore selection-free replication, not a
  third router: test the immutable frozen baseline on the still-unread R45
  qualification/confirmation cohorts with true/current/shuffle bootstrap
  gates and no training, threshold, or checkpoint selection.
- R48 freezes that narrower question on the original 500-patient R45
  qualification cohort. Its cache preflight passes with a fresh token root,
  qualification outcomes unread, confirmation tokens/outcomes absent, and
  training disabled.
- R48 qualification cache completed in 62.3 seconds: 500 patients, 1,000
  images, four shards, exact reproducibility, confirmation still absent.
  Index SHA-256 is
  `CE1D58AA4F54A452AA6228562B84572EE8814F06F0D1192252565B0AB1D124B2`.
- The immutable R48 qualification baseline completed on all 500
  patient-disjoint examples: true-pair macro-F1 `0.400584`, current-only
  `0.303250`, query-only `0.113459`, and shuffled-prior `0.320763`. Every
  true-pair class recall exceeds `0.12` (minimum `New=0.23`); Qwen remains
  frozen with zero trainable parameters and cache equivalence is exact. The
  registered bootstrap aggregate, rather than these point estimates alone,
  decides whether confirmation unlocks.
- The one registered R48 qualification aggregate is
  `GO_PRTA_GEN_R48_FPRR_QUALIFICATION` with zero gate failures. True-minus-
  shuffled-prior is `+7.982 pp`, bootstrap 95% CI `[+3.873,+11.991]`;
  true-minus-current-only is `+9.733 pp`, CI `[+5.818,+13.706]`. Its 2,796-byte
  SHA-256 is
  `6EC0E6B616CB74034F5F6049D7ABCE8DF9A8D36D38A868376C6B03DC2B97EF1A`.
- The still-unmaterialized R45 confirmation partition contains 250 unique
  patients. R48 confirmation must reuse the identical immutable checkpoint,
  four arms, bootstrap design, and gate thresholds; only the partition and
  stage-specific receipt names may change.
- R48 confirmation caching completed before any confirmation outcome read:
  250 patients, 500 images, two shards, exact repeated-batch reproducibility,
  and no labels or sentences in cache. The 1,774-byte index SHA-256 is
  `5740A3762BF51AF82E36616B2ECF2D907591A4E9F4E6E335806311BBE15ADA83`.
- Raw two-image implementation support exists locally: Transformers `5.5.3`
  exposes `Qwen3VLForConditionalGeneration`, `qwen_vl_utils` is installed, and
  the local model config declares `model_type=qwen3_vl` with that architecture.
  The older `run_qwen2vl_smoke.py` already demonstrates the native two-image
  message schema and `process_vision_info` flow, but is Qwen2-specific and only
  a two-image smoke.
- Every row in the 500-patient R48 qualification partition has existing
  `prior_path` and `current_path` JPEGs. This permits a direct raw-pixel
  Qwen3-VL baseline without DICOM conversion or any new data acquisition.
- The raw baseline can be tied to the predeclared R40 B3 authority SHA
  `A97EA29E...F8AB5`, the local Qwen3-VL config SHA
  `EDAC7703...5224D`, preprocessor SHA `27225450...E516`, model-index SHA
  `58A7841D...CF2B`, and the exact R48 qualification baseline/aggregate hashes.
  These pins permit a fresh two-shard runtime without altering the existing
  frozen-token result.
- Two-GPU raw-Qwen smoke passes after the partial-class summary fix: all four
  outputs are strict two-key JSON and all four echo the requested finding.
  Two of four progression labels match, but that sample is engineering-only.
  Each GPU peaks at about 8.55 GiB; two generations take 3.16–3.47 seconds
  after a 14.27-second model load. The full frozen setup is therefore feasible
  without reducing pixels or changing the prompt.
- Formal raw two-image B3 completes on all 500 qualification patients with
  schema validity and finding echo both 1.0, but macro-F1 only `0.141724` and
  accuracy `0.216`. Recall is highly imbalanced: Improved `0.12`, New `0.09`,
  Resolved `0.02`, Stable `0.03`, Worse `0.82`.
- The matched frozen-token FPRR true-pair macro-F1 is `0.400584`. Raw-minus-
  FPRR is `-25.886 pp`, patient-bootstrap 95% CI
  `[-30.773,-20.934]`; thus direct full-image ingestion is decisively worse on
  this development cohort despite perfect output formatting.
- Raw B3 uses 621.6 aggregate GPU-seconds, about 312.3 seconds parallel
  generation wall upper bound, max 8.55 GiB allocated per card, 264,395 input
  tokens, and 831,888 vision-grid tokens. It is not compute-matched to the
  exact-64 FPRR baseline.
- Raw prediction counts are Stable 4, Improved 52, Worse 370, New 71, and
  Resolved 3, confirming a 74% `Worse` collapse rather than formatting failure.
  The 1,904-byte aggregate SHA-256 is
  `4D57F6AF0AD2B5D84A35566B643A512A51C3D8A31FD4631C73460ED2EC231BDF`.
- R48 confirmation is terminal `STOP_PRTA_GEN_R48_FPRR_CONFIRMATION`.
  True-pair macro-F1 is `0.318626`, below the unchanged `0.35` floor;
  true-minus-shuffle is only `+1.325 pp`, CI95 `[-3.709,+6.008]`, and
  true-minus-current is `+4.028 pp`, CI95 `[-1.213,+9.151]`.
- Four confirmation gates fail: absolute F1, true-minus-shuffle point effect,
  true-minus-shuffle CI lower bound, and true-minus-current CI lower bound.
  The qualification GO therefore does not replicate on the separately sealed
  confirmation cohort. No internal replication claim is allowed.
- Confirmation baseline SHA-256 is
  `18191438A8B330E8BE3BD34346B70666583C9D65B9AE4B01B4EAF708D3DBD6FE`;
  terminal aggregate SHA-256 is
  `46EC22D90E0B662284116CE5DD24ED464857F60407D73B7596A5319BBFB3B6BB`.
  No R48/Raw worker remains and both GPUs are idle.
- A post-hoc pooled view over all 750 patient-disjoint held-out predictions is
  positive: true/current/query/shuffle F1 =
  `0.373614/0.295017/0.113974/0.316599`. True-minus-shuffle is `+5.702 pp`,
  CI95 `[+2.529,+9.101]`; true-minus-current is `+7.860 pp`,
  CI95 `[+4.629,+11.045]`. All true-pair class recalls are at least `0.213`.
- This supports cohort heterogeneity/randomness as a plausible explanation for
  the split contrast, but it is a pooled descriptive analysis after both
  outcomes were visible. It cannot erase the preregistered confirmation STOP
  or be called independent replication.
- The durable pooled receipt passes every original numerical gate
  descriptively and is titled
  `POSITIVE_PRTA_GEN_R48_FPRR_POOLED_INTERNAL`. Its 3,574-byte SHA-256 is
  `7463FDADAEEAFF7958AA76CF5A882466452151A24CCC87767F29FD85F8CFB7F6`.
- The strict three-way alignment attribution is not yet complete. Raw and PRTA
  share the R48 qualification 500 patients, but Raw has no confirmation arm,
  the two user prompts are not identical, and Naive exact-64 exists only as an
  R40 protocol declaration with no R48/R49 runtime result.
- R49 must therefore rerun all three through one common harness. The fair
  token comparison fixes Naive to 30 prior + 30 current + 4 reserved tokens
  and matches PRTA on encoder, projector capacity, training rows/steps/seed,
  frozen Qwen, prompt task/output contract, and the 750-patient evaluation set.
- R45 supplies the matched training template for R49: frozen Qwen3-VL-4B,
  fresh `TierTokenProjector`, Seed 17, one epoch over 2,500 training rows,
  effective batch size 32, projector LR 1e-4, and exact 64x768 FP16 inputs.
  Its existing prompt is token-specific, so R49 must freeze a shared task/output
  instruction plus arm-only modality wrapper instead of falsely claiming the
  complete serialized multimodal prompts are byte-identical.
- The R45 PRTA cache is produced from frozen Block-8 features through the R37
  model and `pack_fixed64`; positions 60:64 are verified zero. This confirms
  that Naive exact-64 can use the same 768-wide frozen image-token source and
  reserve the same four zero positions without changing the Qwen or projector.
- The existing raw runner already freezes the exact local Qwen weights and
  supports modulo sharding across both GPUs, but it is qualification-only and
  binds upstream R48 results. R49 therefore needs a new authority/runner that
  selects qualification plus confirmation (750 unique patients) directly from
  the frozen roster and uses the new common task contract.
- Raw inference consumes two full images through Qwen's vision processor; the
  exact-64 arms replace only the modality content with 64 projected positions.
  Comparable scientific claims must therefore report raw vision-token compute
  separately and define prompt parity at the semantic task/output-contract
  level, not as identical serialized token IDs.
- R40 is the still-relevant B1 authority: 30 deterministic prior Block-8
  visual tokens + 30 current tokens + four shared zero-reserved positions,
  using one projector with the same one-epoch, accumulation-32, LR-1e-4,
  weight-decay-0.01 schedule. It did not freeze the 30 indices, so R49 must pin
  an outcome-independent rule before execution; evenly spaced non-CLS patch
  indices across the 14x14 grid are the least arbitrary deterministic choice.
- The live PRTA indices are exactly the R45 train/development index plus the
  R48 qualification and confirmation indices under their respective
  `tokens/qualification` and `tokens/confirmation` roots. The earlier scalar
  inventory queried two incorrect nested paths; configs now provide the exact
  hash-pinned locations.
- R49 Raw shard 0/2 completed 375/375 rows with frozen Qwen, full schema and
  finding validity, macro-F1 0.196221, and 8.48 minutes of generation. Its
  small stderr is limited to Transformers weight-loading progress and ignored
  sampling-flag warnings; no traceback or contract failure occurred.
- R49 Raw shard 1/2 also completed 375/375 with schema/finding 1.0 and
  macro-F1 0.188608. Both raw shards are therefore formally complete; their
  unified 750-row metric remains intentionally deferred to the final aggregate
  so example order and targets are checked against both exact-64 arms first.
- The reader-facing R49 writeback must update four live surfaces together:
  the proposal, `docs/PROJECT_STATUS_CN.md`, `reports/README.md`, and the
  R45-R48 case study (or a dedicated R49 report linked from it). Existing text
  explicitly says the Naive same-budget attribution was still missing, so a
  result-only JSON without these synchronized edits would leave the proposal
  scientifically stale.
- R49 formally answers the missing attribution comparison on the same 750
  patients. Macro-F1 is Raw 0.192915, Naive exact-64 0.295921, and PRTA
  exact-64 0.354372. Paired effects are PRTA−Raw +16.146 pp (CI95 +12.090 to
  +20.198) and PRTA−Naive +5.845 pp (CI95 +2.610 to +9.081). Both lower bounds
  are positive, so the frozen support rule answers both questions positively
  and specifically supports a cross-time-alignment gain over naive concat.
- Exact-64 fairness receipts pass: identical 9,873,920-parameter projector,
  initialization SHA-256 `C8B61AF7...896BE2`, training-order SHA-256
  `99314669...2FEEC7`, 2,500 rows, 79 updates, frozen Qwen, exact-64/no-pixel,
  cache equivalence, schema 1.0, and finding echo 1.0 in both arms.

## R50 literature-method reproduction audit

- Primary-source search identifies three directly relevant method families.
  (1) TILA / Temporal Inversion (CVPR 2026, arXiv 2604.04563) explicitly targets
  interval-change/progression classification and adds inversion-aware training
  and inference to temporal CXR encoders. (2) TempA-VLP (WACV 2025) uses a
  cross-exam encoder and reports disease-progression classification plus
  dynamic phrase grounding. (3) Libra (Findings ACL 2025) uses a radiology
  encoder plus Temporal Alignment Connector and publishes code/weights with
  Qwen-family backbone support. These are stronger and more task-relevant than
  adding another generic single-image classifier.
- Additional longitudinal report-generation methods are useful architectural
  references but not automatically task-equivalent: MLRG (CVPR 2025) combines
  multi-view longitudinal contrastive learning and absence tokens; TIM (CVPR
  2026) temporally decouples pathology/progression and iteratively refines
  reports; BiOTPrompt (CVPR 2026) uses bidirectional optimal transport. Their
  published primary objective is free-text report generation, so any five-class
  reproduction here must be labeled component-faithful or contract-adapted.
- CheXTemporal (arXiv 2605.11304) independently uses the same five-class
  taxonomy (new/worse/stable/improved/resolved) with finding-level temporal and
  spatial supervision, and reports that current VLMs particularly struggle on
  stable/resolved. This supports the relevance of R49's classwise audit, but it
  is a dataset/evaluation resource rather than a baseline method by itself.
- Reproducibility changes the ranking. TILA has an official Hugging Face model
  (`lukeingawesome/TILA`), MIT license, custom code, a 0.2B BioViL-T-style
  ResNet-50 + temporal ViT pooler, 128-d image/text embeddings, and a packaged
  change head. The paper's fine-tuning principle is bidirectional CE under
  reversal (improved↔worsened, stable fixed), making TILA the best candidate
  for one paper-backed frozen-embedding baseline plus one inversion-aware
  five-class adaptation.
- Libra has official public code (`X-iZhang/Libra`) and Qwen-family support,
  but its released objective/output is longitudinal free-text report generation
  and the full checkpoint/connector stack may be substantially heavier. It is
  a credible TAC architectural reference, but running its native report model
  would not be an apples-to-apples five-class reproduction without a separately
  declared adapter/evaluator.
- Primary search did not locate an official TempA-VLP code/weight release or a
  BiOTPrompt repository. These can support component-level reimplementations
  from the papers, but cannot be presented as official-checkpoint reproduction.
- The official TILA model card fixes the executable surface more precisely:
  `lukeingawesome/TILA` is a 643 MB / approximately 0.2B-parameter custom
  Transformers model with a 448x448 processor, 128-dimensional L2-normalized
  pair embeddings, MIT license, and a packaged binary change classifier. Its
  released binary head is not the local five-class target; the defensible R50
  use is therefore frozen official pair embeddings followed by a newly trained
  five-class head, with a second arm adding the paper's inversion constraint.
- Libra's official repository confirms that TAC is trained in a report-
  generation stack with RAD-DINO and an MLLM, not as a five-class progression
  classifier. The documented native run is also infeasible for this benchmark:
  about 385 hours of connector pretraining plus 213 hours of LoRA fine-tuning
  on one 48 GB A6000. R50 may reproduce the TAC component at matched local
  scale, but must not call that a native Libra reproduction.
- A shallow checkout of the official Libra repository locates TAC in
  `libra/model/multimodal_projector/builder.py` and confirms released 3B/7B
  models plus standalone `mm_tac_projector.bin` files. This gives R50 an
  auditable source-level component reference without requiring the full native
  training run. The repository also already contains an unexecuted R40 B2
  signed-plus-absolute Siamese implementation, so that baseline can be reused
  after contract migration instead of reimplemented from scratch.
- Official TAC is not a generic one-layer projector. It first collapses 12
  RAD-DINO layer features with squeeze-excitation plus 1x1 convolutions, then
  applies separate current/prior self-attention, current-to-prior cross-
  attention, residual LayerNorm blocks, a transition MLP, and a four-layer
  output MLP. A local Block-8 adaptation can faithfully reproduce the temporal
  fusion block, but cannot reproduce the 12-layer LFE because the frozen cache
  stores one encoder layer. R50 must name this `TAC-temporal-fusion adapted`,
  not `Libra TAC exact`.
- The existing R40 B2 representation is precisely normalized `[prior,
  current, current-prior, abs(current-prior)]` CLS features followed by the
  same finding-conditioned probe. It was frozen for a different 10,287/1,500
  roster and 100-epoch probe, so R50 should reuse the implementation but refit
  it under the new common 2,500/750 contract rather than mix its old authority
  with R49 outcomes.
- The official TILA Hub revision is now pinned to commit
  `a9c6da4b07651de5469e54b5903a63d33f4dfc6a`; its repository has exactly the
  model card, config, custom config/model/processor/preprocessing/inference
  code, and one safetensors file. R50 must record this revision and verify the
  downloaded cache rather than depend on mutable `main`.
- R49's roster loader already provides the complete R50 data contract: 2,500
  one-row-per-patient training rows and 750 disjoint qualification+confirmation
  rows, each with prior/current JPG paths, finding, and one of the five labels.
  This means TILA, B2, and TAC-adapted arms can share exactly the same row order
  and targets without touching protected 483-test or gold outcomes.
- The first `hf download` attempt for TILA code failed during Hub metadata HEAD
  resolution despite `hf models info` working. A Git checkout with LFS smudge
  disabled succeeded at the exact pinned revision, so the custom code can be
  audited independently of the 642,508,642-byte weight transfer. The official
  LFS object SHA-256 is
  `b16b6bcf47ac6e4e79c4d9da2db88055b297adca22715935e4522184f87ce101`.
- Source inspection confirms TILA concatenates current and prior ResNet-50
  features through a three-block temporal ViT pooler with learned time-type
  embeddings, concatenates current and temporal-fused maps, and projects them
  to a normalized 128-d vector. `get_embeddings(current, previous)` is the
  correct frozen transfer surface; its released classifier is only binary and
  its calibrated thresholds are not valid for the local five-class task.
- The CVPR 2026 paper specifies the supervised TILA recipe: BiCE averages
  forward CE and reversed-order CE under the label inversion map; TCL is mean
  squared distance between forward probabilities and inversion-adjusted
  reversed probabilities; inference averages forward probabilities with the
  adjusted reversed probabilities. The paper trains 20 epochs with BiCE then
  adds TCL for 30 epochs (50 total), with `lambda=50`, and warns that applying
  consistency too early can collapse predictions toward Stable.
- The paper's native supervised labels are only Improved/Stable/Worsened.
  Extending the involution to New<->Resolved is clinically logical and already
  frozen in this repository, but it is an R50 five-class contract adaptation.
  Any resulting arm must be named TILA-style BiCE+TCL rather than an exact
  reproduction of the paper's three-class fine-tuning experiment.
- R50 method selection is frozen in principle before outcomes: (A) official
  TILA frozen pair embedding plus standard five-class CE linear probe; (B) the
  same official embedding and probe trained/evaluated with TILA-style BiCE,
  delayed TCL, and bidirectional scoring; (C) frozen BiomedCLIP Siamese
  `[prior,current,signed,absolute]` plus the same probe family; (D) Libra's
  self-/cross-attention temporal-fusion block adapted to the cached 30+30
  Block-8 tokens plus the same finding-conditioned classifier. A/B are official
  checkpoint transfer and contract-adapted reproduction; C is a strong classic
  representation baseline; D is component-faithful except for Libra's omitted
  12-layer RAD-DINO feature extractor.
- The cached R49 naive tokens provide an outcome-free, hash-pinned 30-prior +
  30-current + 4-zero tensor for all 3,250 rows. TAC-adapted can therefore use
  the exact same selected Block-8 positions as the prior R49 comparison, while
  B2 can reuse the full Block-8 cache and frozen Blocks 9-12 implementation.
  Both GPUs are idle and the host has sufficient H/E disk space.
- The CVPR PDF confirms 50 supervised epochs: first 20 BiCE, then 30 with TCL,
  AdamW, and `lambda=50`; the paper does not state the supervised learning rate
  in its main method paragraph. R50 will pin an explicit head/adapter learning
  rate before outcomes and report it as a local adaptation rather than infer a
  hidden value from results.
- The reused 3,250-row roster is exactly balanced at 650 rows for each of the
  five progression classes and spans 11 findings. Therefore class weighting or
  resampling is unnecessary and would introduce avoidable post-hoc degrees of
  freedom. All arms will use ordinary CE and the same fixed row order per seed.
- The repository's `FindingConditionedLinearProbe` concatenates a one-hot
  finding vector to each representation before one linear five-class layer.
  Reusing it keeps the downstream classifier family identical across TILA and
  B2; TAC-adapted additionally trains its published temporal-fusion component,
  so parameter counts must be reported rather than described as capacity
  matched.
- R50 will pin the completed R49 aggregate as a historical comparison surface:
  3,727 bytes, SHA-256
  `AB1328DF6D90CF65DB0F21CCB2D3631B8DE8ED49159B6FB8A1A2F14D97AECFB4`.
  The new runtime and stable TILA model directories are currently absent, so
  the authority can require fresh creation and fail closed on accidental reuse.
- R49 retains row-level 750-patient predictions for both exact-64 arms under
  `exact64/seed_17/*/result.json` (PRTA 84,884 bytes; Naive 84,900 bytes).
  R50 can therefore compute paired patient-bootstrap effects against the
  existing PRTA system without reconstructing predictions from aggregate
  metrics. This remains a cross-interface descriptive contrast because R50
  methods are direct classifiers rather than frozen-Qwen JSON generators.
- The new outcome-free R50 JSON freezes all four methods, official source
  revisions/licenses, roster/cache/reference hashes, three seeds, 50 epochs,
  TILA's epoch-21 TCL start and weight 50, probe LR 1e-3, TAC LR 1e-4,
  AdamW, no weighting/resampling/early stopping, 2,000 patient bootstraps, and
  a fresh runtime root. No method output exists at freeze time.
- B2 can be cached efficiently by loading each full Block-8 tensor once,
  running only frozen BiomedCLIP Blocks 9-12, and storing normalized forward
  and reversed 3,072-d representations. This preserves the existing strong
  baseline definition while moving only its roster/training contract to R50.
- The R49 config itself is now pinned in R50 at 8,414 bytes and SHA-256
  `A8C6CB998563AE49993952A6CD091FB13EF54D913570E2AA7D596EA3BA76615C`.
  The shared validator also checks all historical result/token hashes, exact
  five-class balance, patient disjointness, method registry, and row schema.
- R49's compact cache used `prior_image_id/current_image_id` as the same keys
  indexed by the formal Block-8 cache. R50 B2 can therefore retrieve full
  tokens directly from the roster without a new image-to-cache mapping or any
  label-bearing cache artifact.
- First R50 static/test pass found only implementation-surface issues before
  any runtime: one unused `os` import and pytest collection failing to resolve
  the new namespace module `scripts.r50_common`, although direct Python import
  from the workspace succeeds and existing tests use the same namespace form.
  Remove the import and make the new test establish the workspace path
  explicitly; no scientific contract or output changes are needed.
- The corrected focused suite passes 11 tests, including the prior R49 tests;
  the only remaining static message was Ruff E402 after the deliberate test
  path bootstrap and is now explicitly scoped with a file-level noqa.
- The pinned Hugging Face Git checkout succeeded, but `git lfs pull` ended with
  an EOF from the LFS batch endpoint and left the 134-byte pointer in place.
  The subsequent shell commands made the overall command exit zero, so file
  size/SHA validation correctly catches the incomplete model. Retry the exact
  immutable resolve URL into a separate partial file and replace the pointer
  only after the 642,508,642-byte SHA-256 matches.
- Direct immutable-URL retry succeeded and the stable TILA weight now exactly
  matches 642,508,642 bytes and SHA-256
  `B16B6BCF47AC6E4E79C4D9DA2DB88055B297ADCA22715935E4522184F87CE101`.
  Focused Ruff and 11 tests pass; fail-closed preflight verifies all 6,500 image
  paths, 2,500/750 rows, the weight hash, fresh runtime root, and two CUDA
  devices without starting GPU work.
- Two outcome-free cache workers are now live: TILA on PID 21904 / GPU0 and B2
  on PID 26776 / GPU1. Both stdout/stderr logs are initially empty and no GPU
  allocation was visible at the first snapshot, consistent with startup
  imports/hash/manifest loading rather than a failed or duplicate launch.
- Both first cache attempts stopped before writing a cache or observing any R50
  outcome. TILA hit Python's dataclass dynamic-import requirement because its
  module was not registered in `sys.modules` before execution. B2 revealed
  that the R49 CheXpert image IDs are not in the older MIMIC formal Block-8
  cache; R49 Naive had re-encoded the same 6,500 source images directly.
- The outcome-free repair is fixed without changing patients, labels, model,
  or feature definition: register TILA's module before execution, and make B2
  reuse R49's frozen image loader/checkpoint to encode the same 6,500 images
  through all 12 BiomedCLIP blocks before constructing CLS signed/absolute
  features. Only four log files exist in the R50 runtime; no cache/result file
  or worker remains.
- Repaired code passes focused Ruff and 6 focused R50 tests. A strict one-pair
  official TILA smoke loads the pinned safetensors into `TILAImageEncoder` with
  `strict=True` and produces finite forward/reverse tensors of shape `[1,128]`.
  The second cache attempts are live: TILA PID 28396/GPU0 (257 MiB at first
  snapshot) and B2 PID 25324/GPU1 (637 MiB), with empty stderr logs.
- Both repaired caches completed once with PASS receipts and exact roster row
  order. TILA stores finite `[3250,128]` forward/reverse FP16 embeddings in
  2,048,264 bytes, took 115.84 s, and peaked at 860,663,296 CUDA bytes. B2
  stores finite `[3250,3072]` forward/reverse embeddings in 40,320,282 bytes,
  took 81.68 s, and peaked at 478,247,936 CUDA bytes. Neither cache contains
  labels, and both GPUs returned to 0 MiB.
- Post-cache Ruff and six focused tests passed, then both frozen training lanes
  launched. The first terminal method receipt is TILA-CE Seed17 macro-F1
  0.453228; this is one seed only and cannot select or terminate a method.
  Lane0 has advanced to TILA-CE Seed29, while lane1 is training TILA-BiCE/TCL
  Seed17. Both lane stderr logs are empty.
- Six of twelve registered method seeds are complete. TILA-CE Seeds 17/29/43
  score 0.453228/0.458893/0.460959. TILA-style BiCE+TCL Seeds 17/29/43 score
  0.396846/0.390419/0.398101. The inversion-aware arm is therefore lower on
  standard macro-F1 in every seed, but its registered consistency and paired-CI
  analysis remains pending. TAC Seed17 and B2 Seed17 are live; no stderr.
- Ten of twelve seeds are complete. B2 signed/absolute Seeds 17/29/43 score
  0.415895/0.414092/0.422242. TAC-adapted Seed17 scores 0.267522, substantially
  below the other direct classifiers, while Seeds 29/43 remain live on the two
  GPUs. The poor first TAC seed is retained under the no-selection contract;
  no retry, tuning, or seed filtering is allowed.
- Eleven of twelve seeds are complete. TAC-adapted Seed29 scores 0.246597 and
  GPU1 lane completed cleanly. TAC Seed43 is the sole remaining run on GPU0;
  both observed TAC seeds confirm that the local one-layer Block-8 adaptation
  does not inherit native Libra performance, but the registered aggregate and
  final seed remain mandatory before a formal verdict.
- All 12 runs completed with zero lane stderr; TAC Seed43 is 0.283137 and both
  GPUs returned to 0 MiB. The registered aggregate completed on the identical
  750 patients: mean macro-F1 is TILA-CE 0.457693, B2 signed/absolute 0.417409,
  TILA-style BiCE+TCL 0.395122, and TAC-adapted 0.265752. Inspect registered
  paired CIs and reversal consistency next before writing the scientific
  interpretation.
- Paired bootstrap resolves the two same-interface method questions. TILA-style
  BiCE+TCL minus TILA-CE is -6.257 pp with CI [-9.579,-2.786]: inversion
  training greatly raises mapped reversal consistency (mean about 0.866 versus
  0.360) but significantly reduces standard five-class F1 under the local
  New/Resolved extension. TAC-adapted minus B2 is -15.166 pp with CI
  [-18.802,-11.635], so the partial TAC transfer is decisively worse than the
  simple signed/absolute representation.
- Cross-interface descriptive comparisons against R49 PRTA exact-64 are:
  TILA-CE +10.332 pp, CI [+6.599,+14.005]; B2 +6.304 pp, CI
  [+2.695,+9.903]; TILA-BiCE/TCL +4.075 pp, CI [-0.234,+8.368]; TAC-adapted
  -8.862 pp, CI [-12.764,-5.151]. Direct classifiers do not use Qwen JSON
  generation, so these effects do not establish an equal-interface replacement
  for PRTA, but they show strong frozen temporal representations remain a key
  missing comparison in the paper story.
- Parameter/compute receipts explain the practical tradeoff. TILA probes train
  only 700 parameters and take roughly 4-14 s/seed after caching; B2 trains
  15,420 parameters and takes 8-13 s/seed; TAC-adapted trains 10,645,308
  parameters, takes 93-100 s/seed, yet performs worst. Aggregate is 11,101
  bytes with SHA-256
  `A011FBA55BB536CA89FB4F72EEBD86814E8EB0C256FA6C47EC1953AEA1C2E01E`.
- Reader-facing R50 writeback must update the active proposal header and add a
  section directly after R49, then update root README, project-status table and
  claims, reports index, the R45-R49 case study, and the planning bundle. The
  first Python attempt to print the proposal hit the Windows GBK console on a
  Unicode minus sign; UTF-8 PowerShell reading succeeded and no file changed.
- R50 documentation is now synchronized across all active surfaces. The
  dedicated report records the literature-source taxonomy, exact four-method
  protocol, per-seed and per-class results, paired confidence intervals,
  compute/capacity receipts, failure history, and the key interface caveat:
  TILA/B2 direct-head performance is not evidence of equal-interface superiority
  over R49 exact-64 frozen-Qwen generation. The next legitimate scientific test
  is a prospectively frozen TILA/B2-to-exact-64 translation study on new
  outcome-independent development data, not post-hoc tuning on these 750 rows.
- Full repository pytest adds six R50 tests relative to the prior terminal
  suite: 878 pass and 1 is expected-xfail. The sole failure remains the known
  historical R6 resolution/frozen-manifest gate in
  `tests/test_query_anchor_r4_runner.py`; it is unrelated to R50 and must not
  be repaired by rewriting the closed R6 registry.
- Terminal artifact closure is internally consistent. The aggregate is 11,101
  bytes with SHA-256
  `A011FBA55BB536CA89FB4F72EEBD86814E8EB0C256FA6C47EC1953AEA1C2E01E`,
  reports 750 matched patients and 12 unique receipts, and each method has
  exactly three seeds. The immutable R50 config SHA-256 is
  `56877CD2ACE9BC2D0325F58E98C106B73381A2F3F4B9928C4FAAFE6166ABC03A`;
  the dedicated report SHA-256 is
  `78A7CC879782BB654B033297A1B3FCFA860EF235E0EDDE2F9F090665C913438C`.
  Both GPUs and the R50 process set are idle at closure.
- R51 provenance boundary: official TILA supplies the pretrained image encoder,
  interval module, 128-dimensional pair embedding, checkpoint, and published
  BiCE/TCL formulation. The repository's five-class finding-conditioned CE
  probe and New/Resolved inversion are task adaptations. B2 is not an official
  named end-to-end system: it is a transparent classic Siamese feature
  construction `[prior, current, current-prior, abs(current-prior)]` using the
  already frozen BiomedCLIP encoder. The proposed R51 system translation will
  therefore be labelled `official representation adapted to matched interface`
  for TILA and `locally implemented classic control` for B2.
- Prior R41A evidence cautions against adding Qwen LoRA to this comparison:
  exact-64 attention-LoRA completed technically but failed the registered
  scientific survival gate. R51 should first freeze Qwen and equalize the
  projector/readout so representation source is the sole intended difference.
- R49's frozen authority already contains most of the desired R51 parity
  surface: 64 physical visual positions, local Qwen3-VL-4B-Instruct, common
  training order and projector initialization, and the same serialized task
  prompt/JSON parser for Naive and PRTA. R51 should extend that runner contract
  rather than invent a second evaluation stack. The actual entrypoints are
  `scripts/run_prta_gen_r49_exact64.py` and
  `scripts/run_prta_gen_r41a_progression_sft.py`.
- Concrete R49 system parity surface: each exact-64 arm yields a float16
  `[64,768]` tensor with 60 active positions and four reserved zeros;
  `TierTokenProjector` maps 768 to Qwen hidden size 2560; Qwen3-VL-4B is frozen;
  target schema, prompt, greedy decoding, one-epoch 2,500-patient training,
  seed 17, AdamW settings, and 79 updates are shared. This is the correct base
  for R51. TILA's native 128-d pair vector and B2's 3,072-d vector therefore
  cannot simply be repeated 64 times without confounding capacity; R51 needs a
  deterministic, equally parameterized representation-to-64 adapter followed
  by the same Qwen projector and training contract.
- Fairness decision refined after reading the runner: keep representation
  translation deterministic and parameter-free, then train exactly the same
  `TierTokenProjector` for every arm from the same seeded initialization. A
  TILA/B2-only learned bridge would increase trainable capacity relative to
  PRTA and invalidate the attribution. The translation may differ in fixed
  layout because native representation shapes differ, but its algorithm and
  absence of trainable parameters must be preregistered and disclosed.
- A genuinely fresh R51 evaluation cohort is feasible. After excluding R44A,
  the gold patient registry, and all 3,750 R45 patients, the image-complete
  unused pool has 17,622 patients. The bottleneck is Resolved with 224 unique
  patients; allocating 100 Resolved plus 100 in each other class yields a
  balanced 500-patient evaluation and leaves at least 124 Resolved candidates
  before cross-label patient competition. Reuse the existing 2,500 R45 train
  patients and exclude development/qualification/confirmation plus all new
  evaluation patients from each other.
- PRTA cache generation is reusable through the established R45 cache engine:
  R48 already wraps its config/roster validator for new partitions, while
  retaining the same frozen PRTA checkpoint, finding text cache, 64-token
  bundle, label-free cache receipt, and no protected/gold/external outcome
  reads. R51 should implement the same narrow wrapper for its fresh evaluation
  roster instead of duplicating alignment code.
- Final outcome-free R51 representation contract: TILA exact-64 is an adapted
  use of official temporal projected patches, not the official global-embedding
  classifier; uniformly select 60 of the 196 grid positions and tile each
  128-d patch six times to 768. B2 exact-64 is a patchwise extension of the
  locally implemented signed/absolute baseline: uniformly select 15 non-CLS
  positions and concatenate prior, current, signed difference, and absolute
  difference groups. Apply identical per-token RMS normalization to every
  arm's active positions, retain four exact-zero reserved slots, and train only
  the same TierTokenProjector from a shared seed-specific initialization.
- Cache implementation can remain source-faithful. TILA's official
  `TILAImageEncoder` returns `projected_patch_embeddings` directly. B2 can
  reuse the frozen BiomedCLIP encoder through Block 8 and then
  `FrozenBiomedCLIPDifference.encode` for all 197 final tokens, not merely CLS.
  PRTA evaluation can reuse the R45 engine via the already established narrow
  validator-wrapper pattern. All three cache receipts can therefore remain
  label-free and no Qwen model needs to load during cache generation.
- R51 label-free caches are terminal and reproducible. PRTA evaluation index is
  2,347 bytes / SHA-256
  `58BBAFCEB198747548798F9BBDD25CA4C4A6F6AFEE95FA667330335A58487405`;
  TILA is 6,856 bytes /
  `B1242083A14DA5183A16D20D09A670E1F15D2D3B5F0F76C07285914B5DE354C1`;
  B2 is 6,431 bytes /
  `1B1F58FD74055EDB639FD3DE923AF0F1304B2CD2D8053D32D30733E3C8403BC3`.
  All row orders match the frozen rosters, all tensors are finite with four
  exact-zero reserved slots, and cache generation produced no model outcome.
- R51 roster authority should reuse the R45 source validation and exact hashes,
  exclude every patient in all four R45 partitions, use stable rare-class-first
  selection with class order Resolved/New/Improved/Worse/Stable, allocate 100
  per class to a single fresh evaluation partition, and leave training fixed
  to R45's 2,500 balanced patients. This avoids both outcome-dependent resplit
  and unnecessary new training-label selection.
- The frozen selection instantiated cleanly: 500/500 unique patients/examples,
  100 per progression class, zero R45 overlap, all image paths present, and 121
  unused Resolved patients still reserved. Roster authority is 388,228 bytes
  with SHA-256
  `8EBA5E1B112F3591FF4C4276673523D78B0B9305F725CC364601CF78EC0D9DE0`.
  This is the sole R51 evaluation roster; resplitting after model outcomes is
  forbidden.
- R52 priority/design boundary: the user specifically requested the direct-head
  comparison suggested by the prior R40C-vs-R50 observation. Reusing R51's
  frozen 2,500/500 patient split and exact64 caches removes the earlier cohort,
  sample-size, and interface confounds. A neutral shared readout should flatten
  the same 60 active `[60,768]` positions to 46,080 features; applying PRTA's
  five semantic-region pooling to TILA spatial patches or B2 component groups
  would silently privilege PRTA's layout. The same `ProgressionDecisionHead`,
  training-only per-feature normalization, seeded initialization, epoch order,
  AdamW schedule, and patient-paired evaluation must be used for every arm.
- R52 cannot be described as globally outcome-blind: the hypothesis and design
  were motivated by observed historical R40C/R50 results, and PRTA-Qwen R51
  Seeds 17/29 had completed before the user's reprioritization. It remains
  outcome-blind with respect to every R52 direct-head prediction; freeze and
  publish all R52 choices before launching its first classifier.
- R52 completed all nine registered runs. Mean macro-F1 is PRTA 0.360519,
  TILA-exact64 0.273051, and B2-exact64 0.267938. Patient-paired three-seed
  bootstrap gives PRTA−TILA +8.747 pp, CI [+4.481,+12.861], and PRTA−B2
  +9.258 pp, CI [+4.768,+13.199]. Both preregistered lower bounds are positive,
  so `prta_strict_superiority_supported=true`. TILA−B2 is only +0.511 pp with
  CI [−3.100,+4.069].
- The class pattern is informative: PRTA's strongest separation is Resolved
  recall 0.547 mean versus 0.247 TILA and 0.300 B2; PRTA does not dominate every
  class (TILA is slightly higher on New and B2 on Worse). The aggregate gain is
  broad enough to survive patient bootstrap, not a single-seed artifact.
- R52 does not invalidate R50's strong official TILA global-embedding result.
  The TILA exact64 arm is an adapted 60-patch representation; its much lower
  0.273 mean shows that the current parameter-free translation loses native
  global-interface readability. The valid claim is PRTA superiority under the
  registered matched exact64 direct head, not universal superiority over TILA.
- R51 completed all nine frozen-Qwen system runs. Mean macro-F1 is PRTA
  0.384796, TILA-exact64 0.316618, and B2-exact64 0.255090. Reversing the
  aggregate's stored control-minus-PRTA direction gives PRTA−TILA +6.818 pp,
  CI [+3.512,+10.080], and PRTA−B2 +12.971 pp, CI [+9.729,+16.286]. TILA also
  exceeds B2 by +6.153 pp, CI [+3.466,+8.739].
- R51 and R52 agree: PRTA is best under both the shared frozen-Qwen projector
  interface and the shared direct head. This narrows the readout-confound
  explanation, but the two studies share the same 500 evaluation patients and
  R52 was initiated after partial R51 outcomes, so they are complementary
  interfaces rather than independent confirmations.
- R51 class behavior shows B2 instability: Seed29 preserves Stable/Resolved
  recall 0.64/0.63 but collapses Improved/Worse/New to 0.03/0.04/0.08. PRTA's
  mean advantage instead comes from Improved 0.503, Worse 0.347, New 0.280,
  and Resolved 0.560, although its Stable recall 0.277 is not best.
