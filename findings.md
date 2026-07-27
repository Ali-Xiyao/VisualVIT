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
