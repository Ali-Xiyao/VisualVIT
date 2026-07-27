# R37 A1 BioViL-T Engineering Case Study

## Verdict

The official frozen BioViL-T A1 path is technically runnable, but the first
tiny case study does **not** show a true-prior benefit. Its correct status is:

- engineering pipeline: `PASS_R37_A1_ENGINEERING_PIPELINE`;
- scientific gate: `NOT_EVALUATED_TINY_SMOKE`;
- formal R37B unlock: `false`.

This case study is retained as a negative/underpowered example. It must not be
used as evidence that A1 works or fails scientifically.

## Frozen implementation

- Hub model: `microsoft/BiomedVLP-BioViL-T`;
- Hub revision:
  `692f09e9be1bfe5fdd5f3efdd0e1eca7d2c10b23`;
- Microsoft HI-ML source revision:
  `b67c1d27c6b17d8e8ff01f8c507f3cabdb307388`;
- license: MIT, research use only under the model-card limitations;
- preprocessing: grayscale, resize 512, center crop 448, expand to three
  identical channels;
- pair order: current image as `current_image`, prior image as
  `previous_image`;
- feature: normalized canonical 128-D `projected_global_embedding`;
- probe: frozen backbone plus a 705-parameter linear five-class head
  conditioned by a fixed 12-finding one-hot query.

No protected 300-dev, 483-test, or gold outcome was read. No source or
per-shard hash was recomputed.

## API failure and repair

The first real pair smoke failed because the official
`get_biovil_t_image_encoder` helper constructs an `ImageModel` outer wrapper.
That wrapper accepts a single image even when its internal encoder is
multi-image. The checkpoint itself was not defective.

The repair uses the official parameter-compatible `MultiImageModel` subclass.
Strict checkpoint loading then reported zero missing and zero unexpected keys.
A two-pair real-image cache smoke produced finite 128-D embeddings with
repeated-inference maximum absolute difference 0.

## Tiny probe case

The deliberately bounded CPU case used:

- seed 17;
- 10 training rows, two from each progression class;
- 5 internal-calibration rows, one from each class;
- 15 unique longitudinal pairs;
- 60 probe epochs;
- true-pair, current-only, and temporally inverted controls.

The probe loss fell from 1.608 to 0.248, confirming that the probe and gradient
path were active. The frozen backbone had zero trainable parameters.

| Control | Macro F1 |
|---|---:|
| True pair | 0.000 |
| Current only | 0.000 |
| Inverted pair | 0.333 |
| True minus current | 0.0 pp |
| True minus inverted | -33.3 pp |

True-pair and current-only predictions were identical on all five calibration
rows. Inversion changed the predictions, so the temporal branch was exercised,
but five rows are not a powered evaluation.

## What this failure rules out

The result rules out only optimistic claims based on checkpoint availability,
successful loading, decreasing training loss, or changed inverted
predictions. None of those demonstrates correct-prior responsiveness.

It does not rule out BioViL-T under the frozen full-cohort evaluation because:

- the training probe saw only ten rows;
- each calibration class had one row;
- no patient-bootstrap interval can be meaningful at this size;
- the full pair cache and three-seed evaluation have not run.

## Next attempt

1. Wait for the unrelated GPU jobs to finish without interruption.
2. Complete the already queued two-GPU BiomedCLIP Block-8 cache.
3. Build and gate the CMCP index.
4. Build the frozen A1 pair cache on free GPUs using the same official
   representation.
5. Run the pre-frozen patient-disjoint, three-seed probe and report true,
   current-only, inverted, and bootstrap results.
6. Keep formal R37B locked until independent human transition QA passes.

The tiny case will not be enlarged by ad hoc threshold, label, prompt, or
feature changes.
