# R28 Case Study and Prior-Failure Analysis

Date: 2026-07-26

Evidence class: `EXPLORATORY_CASE_STUDY`

## Executive finding

R26/R27 did not fail because correspondence could not be computed. They failed because correct binding produced little average progression gain, the derangement often preserved label semantics, and the high-BII subset did not show a positive binding effect. The case-study route therefore tests routing headroom before training TIER.

## Failure taxonomy

| Failure mode | Evidence | Consequence for the new attempt |
|---|---|---|
| Endpoint shortcut | Current-only was close to oracle on average | Keep a state expert |
| Weak semantic intervention | Only 20.50% of R26 assignments changed the target label | Do not use BII as a router target |
| Inactive anatomy constraint | R25.1 emitted all-zero anatomy IDs | Treat prior B4a corruption as cross-pair derangement, not a clean anatomy-local intervention |
| Representation bottleneck | Frozen ROI heads weakly separated change direction | Add a global transition expert before a larger binding module |
| Estimator adaptation | B4a and B4b heads trained separately | Evaluate fixed-expert routing and end-to-end utility separately |
| Sparse support | High-BII had only 8 patients | Do not claim a binding-critical subgroup |
| Reuse/model-selection risk | Same 170 patients informed R26/R27 | R28 remains development evidence; use nested patient folds |

## Registry support

| Archetype | Eligible | Selected |
|---|---:|---:|
| STATE_SUFFICIENT | 319 | 5 |
| TEMPORAL_HELPED | 135 | 5 |
| BINDING_HELPED | 125 | 5 |
| BINDING_HARMED | 130 | 5 |
| ALL_EXPERTS_FAIL | 135 | 5 |

## Analysis-only routing headroom

- Best fixed consensus expert: `B4a_deranged`
- Case-oracle minus best fixed: +25.61 pp; 95% patient-bootstrap CI [+22.87, +28.37] pp
- Oracle expert selections: B4a_deranged=82, B4b_oracle=136, current_only=556

This oracle reads the target label and is not a usable model. It only tests whether expert diversity leaves enough theoretical headroom for a label-free router.

## Registered cases

### STATE_SUFFICIENT

| Case | Anatomy | Target | Current | Oracle | Deranged | BII |
|---|---|---|---:|---:|---:|---:|
| `013ca89e7a9c13acc20b` | right lung | Stable | 1.00 | 1.00 | 0.33 | 0.00 |
| `01c4cedf09c4affc0ac8` | left lung | Improved | 1.00 | 1.00 | 0.67 | 0.00 |
| `0211080f48e215c1bb87` | right hilar structures | Worse | 1.00 | 0.00 | 1.00 | 0.00 |
| `04a9155cfb1faf68e4f6` | cardiac silhouette | Stable | 1.00 | 1.00 | 1.00 | 1.00 |
| `0589bc206ac10d495540` | right lower lung zone | Worse | 1.00 | 1.00 | 1.00 | 0.00 |

### TEMPORAL_HELPED

| Case | Anatomy | Target | Current | Oracle | Deranged | BII |
|---|---|---|---:|---:|---:|---:|
| `0037682c4764c6838526` | mediastinum | Stable | 0.00 | 1.00 | 1.00 | 0.00 |
| `03d8a5695d3ce95fb740` | left lung | Stable | 0.00 | 1.00 | 0.67 | 0.00 |
| `04096caaa6de1ee07b82` | left hilar structures | Improved | 0.00 | 1.00 | 0.67 | 0.00 |
| `0449067810fad4b99854` | mediastinum | Stable | 0.00 | 1.00 | 1.00 | 0.00 |
| `059e89e6957af2cc5397` | left lung | Worse | 0.00 | 1.00 | 1.00 | 0.00 |

### BINDING_HELPED

| Case | Anatomy | Target | Current | Oracle | Deranged | BII |
|---|---|---|---:|---:|---:|---:|
| `01b75753d54c95df5680` | right lung | Improved | 0.67 | 1.00 | 0.00 | 0.57 |
| `06b07c35418b6cdf8c74` | right lower lung zone | Stable | 0.00 | 1.00 | 0.00 | 0.00 |
| `089555f5c2ee7e1bf102` | right lower lung zone | Improved | 0.00 | 1.00 | 0.00 | 0.48 |
| `0cfe28ee3feb69a44be4` | left costophrenic angle | Worse | 1.00 | 1.00 | 0.00 | 0.00 |
| `12e33bb21fa277e1f52a` | left hilar structures | Improved | 0.00 | 1.00 | 0.00 | 0.53 |

### BINDING_HARMED

| Case | Anatomy | Target | Current | Oracle | Deranged | BII |
|---|---|---|---:|---:|---:|---:|
| `0211080f48e215c1bb87` | right hilar structures | Worse | 1.00 | 0.00 | 1.00 | 0.00 |
| `0a1941b53a567f4ad8dc` | right lower lung zone | Worse | 1.00 | 0.00 | 1.00 | 0.53 |
| `1623466b311126033300` | left hilar structures | Stable | 0.67 | 0.00 | 1.00 | 0.00 |
| `1d0c0908d17351e843d5` | right lung | Improved | 0.00 | 0.00 | 1.00 | 0.40 |
| `30a7d3d70f36ec71921c` | left hilar structures | Improved | 1.00 | 0.00 | 1.00 | 0.40 |

### ALL_EXPERTS_FAIL

| Case | Anatomy | Target | Current | Oracle | Deranged | BII |
|---|---|---|---:|---:|---:|---:|
| `003cac83736ae94f25a7` | left costophrenic angle | Improved | 0.00 | 0.00 | 0.00 | 0.00 |
| `00797b2d25e81241662a` | left lung | Worse | 0.00 | 0.00 | 0.00 | 0.00 |
| `01dae3af155eaf600587` | cardiac silhouette | Worse | 0.00 | 0.00 | 0.00 | 0.00 |
| `039bf6e34efe4e1045aa` | right mid lung zone | Stable | 0.00 | 0.00 | 0.00 | 0.00 |
| `044c9c0c988ad7a819e3` | right hilar structures | Stable | 0.00 | 0.00 | 0.00 | 0.00 |

## Local panel boundary

The generated image panels remain under the restricted runtime root and are not committed to Git. Their manifest paths are recorded in `case_panel_manifest.json`. No selected case was removed after image inspection.

Unique local panels generated: 24.

## Implication for TIER

Proceed only if the case oracle shows material headroom. The first admissible attempt must use label-free features, a state expert, a global prior/current transition expert, and a local binding expert under nested patient-disjoint evaluation. BII, case archetype, target label, and expert correctness are forbidden router inputs.
