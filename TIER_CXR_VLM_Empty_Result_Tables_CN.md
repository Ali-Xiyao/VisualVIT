# TIER-CXR-VLM / PRTA-CXR 结果表与实验登记

> **用途：** R32–R39 结果权威表；未执行阶段保留为空，已完成阶段必须填入。
> **当前更新：** 2026-07-31，R50 强 temporal method benchmark 已完成；R42A/R43 未启动，gold 仍封存。
> **规则：** sealed test / gold 未揭示前不得预填；所有百分比统一使用 pp；所有 CI 必须注明 bootstrap 单位与次数。

---

# A. 全局实验注册表

| Run ID | 阶段 | Protocol SHA256 | Commit | Cohort SHA256 | Feature Cache SHA256 | Model/Seed | Test 是否揭示 | 状态 | 结果文件 |
|---|---|---|---|---|---|---|---|---|---|
| R32-COHORT-v1.1 | R32 | b0331ea0… | working tree from 7c4c51e | 6868d76d… | N/A | deterministic split | 否 | PASS | `F:\VisualVIT_runtime\050_routeC\r32_tier_cxr_vlm\cohort_v1` |
| R32-CACHE-v1 | R32 | f9a75b0c… | working tree from 7c4c51e | 6868d76d… | 7d5f3864… | frozen BiomedCLIP | 否 | PASS | `F:\VisualVIT_runtime\050_routeC\r32_tier_cxr_vlm\patch_cache_train_dev_v1` |
| R32-QWEN-v1.2 | R32 | f9a75b0c… | working tree from 7c4c51e | 6868d76d… | 7d5f3864… | Qwen3-VL-4B BF16/FP32 ref | 否 | PASS | `F:\VisualVIT_runtime\050_routeC\r32_tier_cxr_vlm\qwen3vl_4b_exact64_v1_2_verification.json` |
| R37-A6-formal-17/29 | R37 | tracked frozen spec；未重算 unchanged hash | R37 branch | frozen R37 roster | frozen Block-8 cache | A6 Seeds 17/29 | 否 | `STOP_R37_INVERSION_CONSISTENCY` | `reports/R37_INVERSION_FAILURE_CASE_STUDY.md` |
| R37.1-A6-17/29 | R37.1 | tracked frozen repair；未重算 unchanged hash | `18353da` lineage | 10,287/1,815 patient roster | 复用 frozen Block-8 cache | A6 Seeds 17/29 | 否 | PASS | `reports/R37_1_TWO_SEED_FRESH_HOLDOUT_RESULT.md` |
| R37.1-A0-17/29 | R37.1 | frozen A0 protocol | `18353da` lineage | 同一 1,815-patient holdout | frozen BiomedCLIP CLS difference | A0 Seeds 17/29 | 否 | PASS | `H:\VisualVIT_runtime\050_routeD\r37_prta_cxr\r37_1_formal\a0_v1` |
| R37.1-two-seed-screen | R37.1 | bootstrap 2,000 / seed 37001 | `18353da` | 1,815 patients / 6,858 rows | N/A | Seeds 17/29 | 否 | `PASS_R37_1_TWO_SEED_INTERNAL_SCREEN` | `H:\VisualVIT_runtime\050_routeD\r37_prta_cxr\r37_1_formal\two_seed_screen_v1\result.json` |
| R37.1-three-seed | R37.1 | bootstrap 2,000 / seed 37001 | R37.1 frozen lineage | 1,815 patients / 6,858 rows | frozen Block-8 cache | Seeds 17/29/43 | 否 | `GO_R37_1_THREE_SEED_INTERNAL_QUALIFICATION` | `H:\VisualVIT_runtime\050_routeD\r37_prta_cxr\r37_1_formal` |
| R37C-one-shot-dev | R37C | frozen candidate + bootstrap 2,000 | `4e9b52f` lineage | 300 patients / 2,453 rows | reused structural cache | Seeds 17/29/43 | 300-dev：是，一次 | `GO_R37C_ONE_SHOT_DEV` | `H:\VisualVIT_runtime\050_routeD\r37_prta_cxr\r37c_one_shot_dev_v1` |
| R38-fixed64 | R38 | exact-64 no-routing survival | `5604092` | 300 patients / 2,453 rows | frozen R37C inputs | Seeds 17/29/43 | 483-test：否 | `GO_R38_FIXED64_SURVIVAL` | `H:\VisualVIT_runtime\050_routeD\r37_prta_cxr\r38_fixed64_survival_v1` |
| R39-frozen-vlm | R39 | bootstrap 2,000 / seed 39001 | `be10d9f` + receipt-only repair | 483 patients / 4,821 rows | outcome-blind exact-64 token caches | Seeds 17/29/43 | 483-test：是，一次；gold：否 | `GO_R39_FROZEN_VLM_TRANSFER` | `H:\VisualVIT_runtime\050_routeD\r37_prta_cxr\r39_sealed_reveal_v1\qualification.json` |
| PRTA-Gen-R40C | R40C | bootstrap 2,000 / seed 40001 | `5bf56bc` + runtime receipt | 1,000 train / 500 patient-disjoint development；排除 observed 160 | frozen exact-64 semantic-layout cache | structured head Seeds 17/29/43 | protected 300-dev/483/gold/external：否 | `GO_PRTA_GEN_R40C_INTERNAL_GENERALIZATION` | `H:\VisualVIT_runtime\050_routeD\r37_prta_cxr\prta_gen_r40c_structured_generalization_v1\aggregate.json` |
| PRTA-Gen-R41A | R41A | bootstrap 2,000 / seed 41001 | `c796630` authority + `d665221` engineering repair | 375 train / 125 patient-disjoint development；排除 observed 1,660 | frozen exact-64 semantic-layout cache | G0/G1 Seeds 17/29/43 | protected 300-dev/483/gold/external：否 | `STOP_PRTA_GEN_R41A_PROGRESSION_SFT_SURVIVAL` | `H:\VisualVIT_runtime\050_routeD\r37_prta_cxr\prta_gen_r41a_progression_sft_v1\aggregate.json` |
| PRTA-Gen-R50 | R50 | bootstrap 2,000 / seeds 50001–50006 | frozen R50 authority；post-hoc internal | 2,500 train / 750 evaluation；一人一行 | official TILA / frozen BiomedCLIP / R49 Block-8 tokens | TILA-CE、TILA-BiCE/TCL、B2、TAC Seeds 17/29/43 | protected 483/gold/external：否 | `COMPLETE_PRTA_GEN_R50_METHOD_BENCHMARK` | `H:\VisualVIT_runtime\050_routeD\r37_prta_cxr\prta_gen_r50_method_benchmark_v1\aggregate.json` |

---

# B. 数据来源与许可审计

| 数据源 | Annotation Revision | Parent Image Version | License/DUA | 本地路径 | 图像可用 | 可训练 | 可评测 | 可发布内容 | 审计结论 |
|---|---|---|---|---|---|---|---|---|---|
| CheXTemporal Silver | `81fd9cdd…` | parent MIMIC-CXR | CC-BY-NC 4.0 + parent DUA | `F:\VisualVIT_runtime\050_routeC\r29_contextual_transition\inputs_81fd9cdd` | 训练/开发图像全可用 | 是，非商业研究 | R33 development | 仅代码、聚合结果、manifest | PASS |
| CheXTemporal Gold | `81fd9cdd…` | MIMIC/CheXpert/ReXGradient | annotation CC-BY-NC + 各 parent 条款 | `data\official\chextemporal_81fd9cdd` | untouched 本地 16 人 | 否 | descriptive only | 不发布原图/逐病例 | LIMITED |
| MIMIC-CXR | v2.0.0 local | PhysioNet MIMIC-CXR | credentialed DUA | `H:\Xiyao_Wang\000_Public Dataset\mimic-cxr` | 是 | 是，受 DUA 约束 | 是，受 quarantine 约束 | 不发布原图/派生可逆特征 | PASS |
| CheXpert | v1.0-small local | CheXpert | Research Use Agreement | `H:\Xiyao_Wang\000_Public Dataset\CheXpert-v1.0-small` | untouched gold 7 人可用 | 否 | descriptive only | 不发布原图 | LIMITED |
| ReXGradient | official gold annotations only | parent images 未落地 | parent access 未闭合 | `H:\Xiyao_Wang\000_Public Dataset\ReXGradient`（不存在） | 否 | 否 | 否 | annotations 聚合审计 | BLOCKED |

---

# C. Cohort 与零重叠审计

| Split | 患者数 | Pair 数 | Row 数 | Stable | Improved | Worse | New | Resolved | 历史患者重叠 | Gold 重叠 | 完整图像率 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Train | 1574 | 6847 | 15750 | 6712 | 2686 | 4168 | 1957 | 227 | 0 | 0 | 100% |
| Dev/Calibration | 300 | 1077 | 2453 | 1035 | 507 | 590 | 283 | 38 | 0 | 0 | 100% |
| Sealed VLM Test | 483 | 2098 | 4821 | 1995 | 828 | 1302 | 605 | 91 | 0 | 0 | 100%（R32 仅路径审计，未生成 prediction） |
| Gold MIMIC | 9 untouched | — | 24 | 未揭示 | 未揭示 | 未揭示 | 未揭示 | 未揭示 | 0 | 独立 quarantine | 100% |
| Gold CheXpert | 7 untouched | — | 19 | 未揭示 | 未揭示 | 未揭示 | 未揭示 | 未揭示 | 0 | 独立 quarantine | 100% |
| Gold ReXGradient | 70 untouched / 0 image-ready | — | 0 可运行 | 未揭示 | 未揭示 | 未揭示 | 未揭示 | 未揭示 | 0 | 独立 quarantine | 0% |

---

# D. Finding 支持表

| Finding | Train Patients | Dev Patients | Silver Test Patients | Gold Patients | Stable | Improved | Worse | New | Resolved | Primary 可用 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Atelectasis | 921 | 196 | 298 | 未揭示 | 1583 | 503 | 947 | 592 | 15 | 是 |
| Cardiomegaly | 933 | 180 | 277 | 未揭示 | 2637 | 227 | 578 | 73 | 8 | 是 |
| Consolidation | 458 | 82 | 138 | 未揭示 | 497 | 220 | 401 | 199 | 7 | 是 |
| Edema | 752 | 134 | 243 | 未揭示 | 680 | 927 | 863 | 374 | 21 | 是 |
| Pleural Effusion | 1059 | 203 | 329 | 未揭示 | 1912 | 989 | 1471 | 691 | 61 | 是 |
| Pneumothorax | 279 | 41 | 99 | 未揭示 | 361 | 197 | 156 | 183 | 158 | 是 |
| 其他 5 findings | 见 cohort audit | 见 cohort audit | 见 cohort audit | 未揭示 | 仅聚合记录 | 仅聚合记录 | 仅聚合记录 | 仅聚合记录 | 仅聚合记录 | Secondary |

---

# E. Gold 功效与可检测效应

| Gold Cohort | N Patients | N Rows | Expected Δ | Estimated SE | MDE @ 80% Power | MDE @ 90% Power | 预注册角色 | 是否允许揭示 |
|---|---:|---:|---:|---:|---:|---:|---|---|
| Overall | 16 image-ready | 43 | +2 pp | 未用 outcome 估计 | 35.02 pp（保守 Bernoulli 近似） | 未估计 | descriptive external | 否，R35 前继续 quarantine |
| MIMIC | 9 | 24 | +2 pp | 未用 outcome 估计 | 46.69 pp | 未估计 | descriptive same-domain | 否 |
| CheXpert | 7 | 19 | +2 pp | 未用 outcome 估计 | 52.94 pp | 未估计 | descriptive external | 否 |
| ReXGradient | 0 image-ready | 0 | +2 pp | N/A | N/A | N/A | blocked | 否 |

---

# F. 64-Token 布局审计

| Token Type | Index Range | Physical Count | Robust Active Count | Rich Active Count | Feature Dim | Metadata | Neutral 规则 | 验证 |
|---|---|---:|---:|---:|---:|---|---|---|
| Query/Control | 0–3 | 4 | 4 | 4 | 64 | type/time/control | invalid 时 shared neutral | PASS |
| State | 4–15 | 12 | 12 | 12 | 64 | current/query confidence | invalid 时 shared neutral | PASS |
| Global Transition | 16–31 | 16 | 16 | 16 | 64 | temporal/confidence | invalid 时 shared neutral | PASS |
| Local Transition | 32–47 | 16 | 16 | 16 | 64 | temporal/query confidence | invalid 时 shared neutral | PASS |
| Relation/Context | 48–59 | 12 | 4 | 12 | 64 | entropy/relevance | robust 8 槽 shared neutral | PASS |
| Reserved | 60–63 | 4 | 0 | 0 | 64 | none | 全部 shared neutral | PASS |
| **Total** | 0–63 | **64** | **52** | **60** | **64** | label/logit 未嵌入 | physical attention 全为 1 | **PASS** |

---

# G. R32 工程门

| Gate | 要求 | 实测 | PASS/FAIL | 证据文件 |
|---|---|---|---|---|
| G0 Patient overlap | 0 | patient/study/image 跨 split 均 0 | PASS | `cohort_audit.json` |
| G1 Gold quarantine | 0 leaked IDs | master 26 quarantined；active 0 leaked | PASS | `gold_quarantine_manifest.json` / `gold_access_log.jsonl` |
| G2 Image completeness | 按协议 | 23,024 rows 引用路径完整；missing=0 | PASS | `cohort_audit.json` |
| G3 Patch cache repeatability | 一次冻结 identifier + 结构核验 | 10,562 images，42 shards，identifier `7d5f3864…`；按用户要求未逐 shard 重哈希 | PASS | `patch_cache_train_dev_v1/cache_manifest.json` |
| G4 64 placeholders | exactly 64 | 64；布局 4/12/16/16/12/4 | PASS | `qwen3vl_4b_exact64_v1_2_verification.json` |
| G5 Frozen ViT | 0 trainable | strict 150/150；0 trainable | PASS | `patch_cache_train_dev_v1/cache_manifest.json` |
| G6 Frozen VLM | 0 trainable | 4,437,815,808 params；0 trainable | PASS | `qwen3vl_4b_exact64_smoke_v2.json` |
| G7 Pixel bypass | false | false | PASS | `qwen3vl_4b_exact64_v1_2_verification.json` |
| G8 Vectorized candidate equality | protocol v1.2 tolerance 内 | FP32 max abs `2.96e-5` ≤ `1e-4`，argmax 同；BF16 argmax 同 | PASS | `qwen3vl_4b_exact64_v1_2_verification.json` |
| G9 Full test/lint | 全通过 | 559 passed，1 registered xfail；R32 scoped ruff/compile PASS（仓库旧脚本仍有既存 lint debt） | PASS | `progress.md` |

---

# H. R33 Token Survival 主表

> 本表只填写 Train+Dev nested OOF 结果；不得填写 483 名 Sealed VLM Test。

| System | Token Budget | Trainable Params | Patient-balanced Macro F1 | 95% CI | Δ vs Robust (pp) | Δ 95% CI | Balanced Acc | NLL | ECE | Gate |
|---|---:|---:|---:|---|---:|---|---:|---:|---:|---|
| P0 Query-only | 64 | 2,325 | 0.4622 | [0.4498, 0.4748] | +0.385 | [-0.474, +1.224] | 0.4904 | 1.0378 | 0.0269 | INVALID：实际为 query/control proxy |
| P1 Current-state | 64 | 2,325 | 0.4601 | [0.4479, 0.4721] | +0.175 | [-0.592, +0.945] | 0.4868 | 1.0447 | 0.0408 | Baseline |
| P2 Global temporal | 64 | 2,325 | 0.4583 | [0.4460, 0.4708] | -0.000 | [-0.754, +0.767] | 0.4840 | 1.0424 | 0.0431 | Baseline |
| P3 Robust fixed-64 | 64 | 2,325 | 0.4583 | [0.4461, 0.4703] | 0.00 | [0.000, 0.000] | 0.4817 | 1.0548 | 0.0689 | Reference |
| P4 Always-rich fixed-64 | 64 | 2,325 | 0.4534 | [0.4416, 0.4655] | -0.491 | [-1.261, +0.295] | 0.4776 | 1.0645 | 0.0796 | FAIL |
| P5 Random route | 64 | 2,325 | 0.4514 | [0.4396, 0.4633] | -0.688 | [-1.468, +0.116] | 0.4750 | 1.0659 | 0.0771 | Negative control |
| P6 TIER hard gate | 64 | 2,325 | 0.4516 | [0.4401, 0.4634] | -0.669 | [-1.443, +0.109] | 0.4739 | 1.0624 | 0.0761 | **STOP_R33** |
| P7 Oracle route | 64 | 0 | 0.5657 | [0.5536, 0.5777] | +10.744 | [+10.209, +11.301] | 0.5908 | 1.0067 | 0.0818 | Upper bound |

---

# I. R33 每 Seed 结果

| Seed | Robust F1 | Always-rich F1 | TIER F1 | TIER−Robust (pp) | 95% CI | Route Coverage | Direction Positive |
|---:|---:|---:|---:|---:|---|---:|---|
| 17 | 0.4483 | 0.4532 | 0.4524 | +0.405 | [-1.003, +1.841] | 46.91% | 是 |
| 29 | 0.4585 | 0.4505 | 0.4512 | -0.734 | [-2.033, +0.589] | 46.91% | 否 |
| 43 | 0.4678 | 0.4562 | 0.4512 | -1.665 | [-2.987, -0.379] | 46.91% | 否 |
| Mean | 0.4583 | 0.4534 | 0.4516 | -0.669 | [-1.443, +0.109] | 46.91% | 否（1/3 正向） |

---

# J. R33 GO 检查

| 条件 | 预注册门槛 | 实测 | PASS/FAIL |
|---|---|---|---|
| Δ Token | ≥ +2.0 pp | -0.669 pp | FAIL |
| 95% CI lower | > 0 | -1.443 pp | FAIL |
| 三 seed | 全部正向 | 1/3 正向 | FAIL |
| 与最强非 oracle 差距 | ≥ −1.0 pp | -1.054 pp vs P0 proxy | FAIL |
| Prior shuffle | 收益显著下降 | shuffled Δ +0.422 pp；门槛 ≤ -1.169 pp | FAIL |
| Query-only | 低于完整系统 | P0 实为 query/control proxy，且高于 P6 1.054 pp | FAIL/INVALID |
| Label/logit leakage | 无 | 无；sealed/gold outcome 未读 | PASS |
| Fresh-process reproduction | exact | 科学门未通过，按 protocol 不启动 | N/A |

---

# K. R34 Frozen-VLM 三分类主表

| ID | System | Vision Path | Token Budget | VLM Trainable | Visual Trainable Params | Macro F1 | 95% CI | Δ vs V5 (pp) | Δ 95% CI | Balanced Acc | NLL | ECE |
|---|---|---|---:|---:|---:|---:|---|---:|---|---:|---:|---:|
| V0 | Query-only VLM | 64 neutral tokens | 64 | 0 |  |  |  |  |  |  |  |  |
| V1 | Current native VLM | native pixels | native | 0 |  |  |  |  |  |  |  |  |
| V2a | Raw two-image VLM | native pixels | native | 0 |  |  |  |  |  |  |  |  |
| V2b | Parameter-matched native temporal adapter | native + adapter | native | 0 |  |  |  |  |  |  |  |  |
| V3 | Naive concat | custom tokens | 64 | 0 |  |  |  |  |  |  |  |  |
| V4 | Global difference | custom tokens | 64 | 0 |  |  |  |  |  |  |  |  |
| V5 | Robust/uniform | custom tokens | 64 | 0 |  |  |  | 0.00 |  |  |  |  |
| V6 | Always-rich | custom tokens | 64 | 0 |  |  |  |  |  |  |  |  |
| V7 | Random route | custom tokens | 64 | 0 |  |  |  |  |  |  |  |  |
| V8 | TIER hard gate | custom tokens | 64 | 0 |  |  |  |  |  |  |  |  |
| V9 | Continuous TIER | custom tokens | 64 | 0 |  |  |  |  |  |  |  |  |
| V10 | Oracle route | custom tokens | 64 | 0 |  |  |  |  |  |  |  |  |

---

# L. R34 每 Seed 结果

| Projector Seed | Robust F1 | Always-rich F1 | TIER F1 | TIER−Robust (pp) | 95% CI | Best Baseline | TIER−Best (pp) | Positive |
|---:|---:|---:|---:|---:|---|---|---:|---|
| 17 |  |  |  |  |  |  |  |  |
| 29 |  |  |  |  |  |  |  |  |
| 43 |  |  |  |  |  |  |  |  |
| Mean |  |  |  |  |  |  |  |  |

---

# M. R34 GO 检查

| 条件 | 门槛 | 实测 | PASS/FAIL |
|---|---|---|---|
| Δ VLM | ≥ +2.0 pp |  |  |
| 95% CI lower | > 0 |  |  |
| 三 projector seeds | 全部正向 |  |  |
| 与最强 baseline | ≥ −1.0 pp |  |  |
| Random route | 不复制收益 |  |  |
| Frozen VLM | 0 trainable |  |  |
| Pixel bypass | false |  |  |
| Fixed token/layout | exact match |  |  |
| Reproduction | exact hashes |  |  |

---

# N. 路由行为与可靠性

| System/Gate | Rich Coverage | Robust Coverage | Override Rate | Correction Rate | Harm Rate | Net Corrected | Accepted F1 | Fallback F1 | Risk @ Coverage |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Hard 3/3 | 46.91% | 53.09% | 30.51% | 11.02% | 11.66% | -0.643 pp | N/A | N/A | N/A |
| 2/3 Majority |  |  |  |  |  |  |  |  |  |
| Entropy Gate |  |  |  |  |  |  |  |  |  |
| Margin Gate |  |  |  |  |  |  |  |  |  |
| Continuous TIER |  |  |  |  |  |  |  |  |  |
| Random Matched | 47.41% | 52.59% | 30.27% | 10.90% | 11.61% | -0.713 pp | N/A | N/A | N/A |

---

# O. 核心消融表

| Variant | Tier 0 | Tier 1 | Tier 2 | Tier 3 | Gate | Shared Projector | Token Budget | Macro F1 | Δ vs Full (pp) | 95% CI |
|---|---|---|---|---|---|---|---:|---:|---:|---|
| Full TIER | ✓ | ✓ | ✓ | ✓ | 3/3 | ✓ | 64 |  | 0.00 |  |
| − State |  | ✓ | ✓ | ✓ | 3/3 | ✓ | 64 |  |  |  |
| − Global | ✓ |  | ✓ | ✓ | 3/3 | ✓ | 64 |  |  |  |
| − Local | ✓ | ✓ |  | ✓ | 3/3 | ✓ | 64 |  |  |  |
| − Relation | ✓ | ✓ | ✓ |  | 3/3 | ✓ | 64 |  |  |  |
| Always-rich | ✓ | ✓ | ✓ | ✓ | none | ✓ | 64 |  |  |  |
| Always-robust | ✓ | ✓ | coarse | neutral | none | ✓ | 64 |  |  |  |
| 2/3 Gate | ✓ | ✓ | ✓ | ✓ | 2/3 | ✓ | 64 |  |  |  |
| Same Projection ×3 | ✓ | ✓ | ✓ | ✓ | 3/3 | ✓ | 64 |  |  |  |
| Separate Projectors | ✓ | ✓ | ✓ | ✓ | 3/3 |  | 64 |  |  |  |
| 32 Tokens | ✓ | ✓ | ✓ | ✓ | 3/3 | ✓ | 32 |  |  |  |
| 96 Tokens | ✓ | ✓ | ✓ | ✓ | 3/3 | ✓ | 96 |  |  |  |

---

# P. Shortcut / Intervention Controls

| Control | Expected Behavior | Baseline F1 | TIER F1 | Δ (pp) | 95% CI | PASS/FAIL | 解释 |
|---|---|---:|---:|---:|---|---|---|
| Query-only | 明显下降 | 0.4622（query/control proxy） | 0.4516 | -1.054 | N/A | FAIL/INVALID | type 0 混入 prior/current global control，不能作为 literal query-only |
| Current-only | 暴露 state shortcut | 0.4583 | 0.4601 | +0.175 | [-0.592, +0.945] | FAIL | P1 未显示可靠增益 |
| Prior shuffle | 时间收益下降 | 0.4031 | 0.4073 | +0.422 | N/A | FAIL | 路由收益未下降，反而由 -0.669 变为 +0.422 pp |
| Time reversal | 标签方向按映射翻转 |  |  |  |  |  |  |
| Patch shuffle | local/relation 收益下降 |  |  |  |  |  |  |
| Image blank | 接近 query prior |  |  |  |  |  |  |
| Random route | 低于 TIER | 0.4514 | 0.4516 | +0.019 | N/A | FAIL | matched coverage 下几乎完全相同 |
| Label permutation | 接近机会水平 |  |  |  |  |  |  |
| Side swap | laterality 错误上升 |  |  |  |  |  |  |

---

# Q. R35 Human-Gold 五分类主表

| System | Overall Macro F1 | 95% CI | Δ vs Robust (pp) | Δ 95% CI | Balanced Acc | Accuracy | NLL | ECE | Brier |
|---|---:|---|---:|---|---:|---:|---:|---:|---:|
| Query-only |  |  |  |  |  |  |  |  |  |
| Current native VLM |  |  |  |  |  |  |  |  |  |
| Raw two-image VLM |  |  |  |  |  |  |  |  |  |
| Robust token VLM |  |  | 0.00 |  |  |  |  |  |  |
| Always-rich token VLM |  |  |  |  |  |  |  |  |  |
| TIER hard gate |  |  |  |  |  |  |  |  |  |
| Continuous TIER |  |  |  |  |  |  |  |  |  |
| Oracle route |  |  |  |  |  |  |  |  |  |

---

# R. Gold 每类性能

| System | Stable F1 | Improved F1 | Worse F1 | New F1 | Resolved F1 | Persistent 3-Class F1 |
|---|---:|---:|---:|---:|---:|---:|
| Robust token VLM |  |  |  |  |  |  |
| Always-rich token VLM |  |  |  |  |  |  |
| TIER hard gate |  |  |  |  |  |  |
| Continuous TIER |  |  |  |  |  |  |

---

# S. Gold / External 来源分层

| Source | Patients | Rows | Robust F1 | TIER F1 | Δ (pp) | 95% CI | Direction | Confirmatory/Descriptive |
|---|---:|---:|---:|---:|---:|---|---|---|
| MIMIC |  |  |  |  |  |  |  |  |
| CheXpert |  |  |  |  |  |  |  |  |
| ReXGradient |  |  |  |  |  |  |  |  |
| Overall |  |  |  |  |  |  |  |  |

---

# T. Finding 亚组

| Finding | N Patients | N Rows | Robust F1 | Rich F1 | TIER F1 | Δ TIER−Robust | 95% CI | Rich Coverage |
|---|---:|---:|---:|---:|---:|---:|---|---:|
| Atelectasis |  |  |  |  |  |  |  |  |
| Cardiomegaly |  |  |  |  |  |  |  |  |
| Consolidation |  |  |  |  |  |  |  |  |
| Edema |  |  |  |  |  |  |  |  |
| Pleural Effusion |  |  |  |  |  |  |  |  |
| Pneumothorax |  |  |  |  |  |  |  |  |
| 其他 |  |  |  |  |  |  |  |  |

---

# U. Grounding 结果

| System | Pointing Acc | Attention-in-Box | IoU@0.1 | IoU@0.25 | IoU@0.5 | Laterality Acc | Anatomy Acc | Temporal Grounding Consistency |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Raw two-image VLM |  |  |  |  |  |  |  |  |
| Robust token VLM |  |  |  |  |  |  |  |  |
| Always-rich token VLM |  |  |  |  |  |  |  |  |
| TIER-CXR-VLM |  |  |  |  |  |  |  |  |

---

# V. 比较句生成结果

| System | Progression EM | Finding Acc | Anatomy Acc | Laterality Acc | Temporal Direction Acc | Unsupported Change ↓ | Wrong-Time ↓ | Wrong-Side ↓ | RadGraph F1 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Current-only VLM |  |  |  |  |  |  |  |  |  |
| Raw two-image VLM |  |  |  |  |  |  |  |  |  |
| Robust token VLM |  |  |  |  |  |  |  |  |  |
| Always-rich token VLM |  |  |  |  |  |  |  |  |  |
| TIER-CXR-VLM |  |  |  |  |  |  |  |  |  |

---

# W. 专家人工评价

| System | N Cases | Clinical Correctness | Temporal Correctness | Evidence Faithfulness | Harmful Hallucination | Preferred (%) | Inter-rater Agreement |
|---|---:|---:|---:|---:|---:|---:|---:|
| Raw two-image VLM |  |  |  |  |  |  |  |
| Robust token VLM |  |  |  |  |  |  |  |
| TIER-CXR-VLM |  |  |  |  |  |  |  |

---

# X. Calibration 与风险—覆盖率

| System | ECE | Brier | NLL | Coverage @ Risk 5% | Coverage @ Risk 10% | AURC | Selective F1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Robust |  |  |  |  |  |  |  |
| Always-rich |  |  |  |  |  |  |  |
| Hard TIER |  |  |  |  |  |  |  |
| Continuous TIER |  |  |  |  |  |  |  |

---

# Y. 计算与效率

| System | Encoder | VLM | Token Count | Trainable Params | Feature Cache GB | Peak VRAM GB | Train GPU-Hours | Inference ms/Sample | FLOPs | Throughput |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Current native VLM |  |  |  |  |  |  |  |  |  |  |
| Raw two-image VLM |  |  |  |  |  |  |  |  |  |  |
| Robust token VLM |  |  | 64 |  |  |  |  |  |  |  |
| Always-rich token VLM |  |  | 64 |  |  |  |  |  |  |  |
| TIER-CXR-VLM |  |  | 64 |  |  |  |  |  |  |  |

---

# Z. 多 Backbone / VLM 鲁棒性

| Vision Encoder | VLM | Robust F1 | TIER F1 | Δ (pp) | 95% CI | Rich Coverage | Direction Consistent |
|---|---|---:|---:|---:|---|---:|---|
| BiomedCLIP | Qwen3-VL-4B |  |  |  |  |  |  |
| BioViL-T | Qwen3-VL-4B |  |  |  |  |  |  |
| RAD-DINO | Qwen3-VL-4B |  |  |  |  |  |  |
| BiomedCLIP | Qwen3-VL-8B |  |  |  |  |  |  |

---

# AA. 复现证书

| Check | Process A | Process B | Exact/Within Tol | PASS/FAIL |
|---|---|---|---|---|
| Protocol hash |  |  | exact |  |
| Cohort hash |  |  | exact |  |
| Gold quarantine hash |  |  | exact |  |
| Patch cache manifest |  |  | exact |  |
| Model weights hash |  |  | exact |  |
| Route predictions |  |  | exact |  |
| VLM label scores |  |  | protocol tolerance |  |
| Final predictions |  |  | exact |  |
| Bootstrap result |  |  | exact |  |
| Scientific verdict |  |  | exact |  |

---

# AB. STOP / GO 总表

| 阶段 | Primary Δ | 95% CI | Seed Gate | Leakage Gate | Reproduction | Verdict | 下一步 |
|---|---:|---|---|---|---|---|---|
| R32 Authority | N/A | N/A | N/A | PASS：gold/test outcome 未揭示 | engineering smoke + full tests | **GO_R32_READY_R33** | 仅启动 R33 Train+Dev nested OOF |
| R33 Token Survival | -0.669 pp | [-1.443, +0.109] pp | FAIL：1/3 正向 | PASS：sealed/gold 未读；P0 control 语义审计失败 | 未触发（科学门失败） | **STOP_R33_TOKEN_SURVIVAL** | 停止；不得启动 R34 |
| R34 Frozen VLM | N/A | N/A | N/A | sealed test 保持未读 | N/A | **LOCKED** | 不执行 |
| R35 Human-Gold | N/A | N/A | N/A | gold outcomes 保持未读 | N/A | **LOCKED** | 仍需独立专家标注 |
| R36 Full Paper | N/A | N/A | N/A | N/A | N/A | **LOCKED** | 不执行 |
| R37 A6 formal | +13.01 pp vs current（两 Seed均值） | 未聚合；在 inversion gate 先 STOP | 17/29 正向；Seed 43 未运行 | PASS：300-dev/483-test/gold/hash 未读 | 两 Seed结构完成 | **STOP_R37_INVERSION_CONSISTENCY** | 冻结旧 calibration，仅允许预先冻结的 R37.1 repair |
| R37.1 A6 vs current-only | +27.82 pp | [+25.96, +29.50] pp | 17/29 均 ≥ +2 pp | PASS：protected/sealed/gold 未读 | two-seed patient bootstrap | **PASS_TWO_SEED_INTERNAL** | 仅内部描述性结论 |
| R37.1 A6 vs CMCP | +12.08 pp | [+10.61, +13.63] pp | 17/29 均 ≥ +2 pp | PASS | two-seed patient bootstrap | **PASS_TWO_SEED_INTERNAL** | 不外推到三 Seed |
| R37.1 A6 vs A0 | +11.93 pp | [+10.24, +13.66] pp | 17/29 均 ≥ +2 pp | PASS | two-seed patient bootstrap | **PASS_R37_1_TWO_SEED_INTERNAL_SCREEN** | 停止 GPU；整理 proposal/case study |
| R37.1 three-seed | +13.07 pp vs A0 | [+11.38,+14.70] pp | 17/29/43 全正向 | PASS：protected outcome 未用于选择 | patient bootstrap 2,000 | **GO_R37_1_THREE_SEED_INTERNAL_QUALIFICATION** | 冻结唯一候选 |
| R37C 300-dev | +3.42 pp vs A0 | [+0.89,+6.20] pp | 17/29/43 全正向 | PASS：一次 reveal；`R37C-PD1` 已披露且未改候选/门槛 | patient bootstrap 2,000 | **GO_R37C_ONE_SHOT_DEV** | 解锁 R38 |
| R38 64-token survival | +3.42 pp vs A0 | [+0.89,+6.20] pp | 17/29/43 全正向；effect retention 1.0 | PASS：483-test/gold 未读 | exact-64 + patient bootstrap | **GO_R38_FIXED64_SURVIVAL** | 冻结并执行 R39 |
| R39 frozen-VLM transfer | +15.01 pp vs A0 | [+13.80,+16.14] pp | +6.54/+16.08/+22.42 pp | PASS：预测先冻结；483 一次 reveal；gold 未读 | patient bootstrap 2,000 | **GO_R39_FROZEN_VLM_TRANSFER** | 停止；gold 另行注册 |

---

# AC. 最终论文 Claim Matrix

| Claim | 所需证据 | 当前结果 | 支持/不支持 | 放置位置 |
|---|---|---|---|---|
| Universal binding 是必要机制 | R26 correct vs deranged |  |  | Diagnostic/Limitations |
| Rich temporal evidence 条件有效 | R31 / R33 | R31 fresh-silver 正向，但 R33 nested-OOF P6-P3 为 -0.669 pp | 不支持迁移 claim；仅保留 R31 范围 | Main motivation / Limitation |
| Token routing 优于 uniform tokens | R34 | R33 生存门失败，R34 未启动 | 不支持 | 不进入 Main result |
| 收益迁移到 frozen VLM | R39 | A6−A0 +15.01 pp，95% CI [+13.80,+16.14]；三个 Seed 全正向 | 支持冻结协议与 sealed silver cohort 范围内的 transfer claim | Main result |
| PRTA-CXR 对正确 prior 有响应 | R37/R37.1 true vs current/CMCP | 三 Seed内部 GO；A6−current +28.73 pp，A6−CMCP +12.78 pp | 支持冻结 fresh-holdout 内部 claim | Main internal result |
| Z2 projection 修复 inversion inconsistency | R37 vs R37.1 fresh holdout | R37 0.8438/0.8735；R37.1 1.0000/1.0000 | 支持机制级 case-study claim，不作因果泛化 | Method / Case study |
| PRTA-CXR 优于 capacity-matched A0 | R37.1 A6 vs A0 | 三 Seed均值 +13.07 pp；95% CI [+11.38,+14.70] | 支持内部三 Seed confirmatory claim | Main internal result |
| R37.1 达到三 Seed confirmatory GO | Seed 17/29/43 + original bootstrap | 三组比较均通过原 patient bootstrap 门槛 | 支持 | Main internal result |
| 专家 gold 泛化 | R35 | gold outcomes 未读；仅 16 位可用 | 不支持/未检验 | Limitation |
| 外部来源泛化 | R35 |  |  | Main result |
| Grounding 改善 | R36 |  |  | Secondary result |
| Comparative generation 改善 | R36 |  |  | Secondary result |
| 临床可部署 | Prospective study |  |  | 不主张 |

---

# AD. 错误与变更日志

| Date | Run ID | Error/Observation | 是否看到 Outcome | 允许的修复类别 | Patch Commit | 是否需新 Protocol | 处理结果 |
|---|---|---|---|---|---|---|---|
| 2026-07-26 | R32-COHORT-v1 | 2,383 reserve 中 26 人属于 Chest ImaGenome gold，literal 1,600/300/483 不可同时满足 quarantine | 否 | 数据 authority 修复 | working tree | 是，v1.1 | 冻结 1,574/300/483，26 人保留 quarantine |
| 2026-07-26 | R32-QWEN-v1 | standalone import path 缺失；修复后 BF16 batch-shape score 有 0.17 数值差但 argmax 同 | 否 | M0 工程修复 | working tree | 是，v1.2 | FP32 reference `2.96e-5`，组合 verification PASS |
| 2026-07-26 | R32-CACHE-v1 | 用户要求简化 provenance | 否 | 记录策略 | working tree | 否 | 仅冻结一次 cache identifier；不逐 shard 重复哈希 |
| 2026-07-26 | R33-OOF-v1-attempt1 | PyTorch deterministic cuBLAS guard 要求 workspace config | 否 | M0 运行环境修复 | working tree | 否 | 首个 probe 前停止；设置 `CUBLAS_WORKSPACE_CONFIG=:4096:8` 后重启 |
| 2026-07-26 | R33-OOF-v1 | primary Δ -0.669 pp；CI 跨 0；1/3 seed 正向；prior-shuffle FAIL | 是（仅 train/dev nested OOF） | 不允许 outcome-conditioned rescue | working tree | 否 | **STOP_R33_TOKEN_SURVIVAL**；R34 sealed test 保持未读 |
| 2026-07-26 | R33-P0-AUDIT | type 0 summary 同时含 query 与三个 image-derived global controls | 是（在结果解释审计中发现） | 报告语义更正；不改 primary | working tree | 否 | P0 降级为 query/control proxy；多个 P0-independent gate 已足够 STOP |
| 2026-07-28 | R37-A6-17/29 | 正确 prior 收益为正，但 inversion consistency 0.8438/0.8735 低于 0.90 | 是（仅旧 R37 internal calibration） | 冻结失败；仅允许预先冻结的新 roster 与结构修复 | `3730f10` lineage | 是，R37.1 | `STOP_R37_INVERSION_CONSISTENCY` |
| 2026-07-28 | R37.1-reboot | 主机重启中断未完成 Seed 17/29；无结果目录，日志为空 | 否 | M0 运行恢复 | unchanged command | 否 | 归档 stale status/log，仅重启相同 Seed |
| 2026-07-29 | R37.1-two-seed-screen | A6/A0 Seeds 17/29 和三组 two-seed patient bootstrap 全部通过 | 是（仅 frozen fresh holdout） | 结果登记；不得调参或扩张 claim | `18353da` | 否 | `PASS_R37_1_TWO_SEED_INTERNAL_SCREEN` |
| 2026-07-30 | R37C-case-normalization | 11 行 finding 仅大小写不一致，首轮 evaluator 在建模前停止 | 否（无科学指标） | 仅大小写 canonicalization；复用一次 reveal | `4e9b52f` | 否 | `GO_R37C_ONE_SHOT_DEV` |
| 2026-07-30 | R39-projector-receipt | input-width-16 smoke 的参数数目误用于冻结的 768-D projector receipt | 否（训练前停止） | 仅修正派生 receipt；复用 outcome-free caches | `91f6560` / `f92822a` | 否 | `GO_R39_FROZEN_VLM_TRANSFER` |

---

# AE. R37 → R37.1 方法修复表

| 版本 | Inversion 机制 | 验证患者/Rows | Seed 17 | Seed 29 | State retention | Verdict |
|---|---|---:|---:|---:|---:|---|
| R37 | detached soft-target inversion KL | 1,347 / 5,242 old calibration | 0.8438 | 0.8735 | 0.9938 / 0.9936 | `STOP_R37_INVERSION_CONSISTENCY` |
| R37.1 | parameter-free Z2-equivariant projection | 1,815 / 6,858 fresh holdout | 1.0000 | 1.0000 | 0.9934 / 0.9929 | `PASS_R37_1_TWO_SEED_INTERNAL_SCREEN` |

R37.1 的 fresh holdout 在任何 outcome 被读取前一次性冻结；旧 R37
calibration patients 不进入 R37.1 train 或 validation。

---

# AF. R37.1 A6 / A0 每 Seed 主表

| Seed | A6 true F1 | Current-only F1 | A6−Current | A6 CMCP true F1 | CMCP control F1 | A6−CMCP | A0 true F1 | A6−A0 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 17 | 0.4680 | 0.1638 | +30.42 pp | 0.3534 | 0.2258 | +12.76 pp | 0.3419 | +12.62 pp |
| 29 | 0.4529 | 0.2007 | +25.22 pp | 0.3443 | 0.2304 | +11.39 pp | 0.3404 | +11.25 pp |

---

# AG. R37.1 两 Seed Patient-Cluster Bootstrap

| Comparison | Patients | Rows | Replicates / Seed | Seed effects | Mean Δ | 95% CI | Gate |
|---|---:|---:|---|---|---:|---|---|
| A6 vs current-only | 1,815 | 6,858 | 2,000 / 37001 | +30.42 / +25.22 pp | +27.82 pp | [+25.96, +29.50] pp | PASS |
| A6 vs CMCP | 1,296 | 3,422 | 2,000 / 37001 | +12.76 / +11.39 pp | +12.08 pp | [+10.61, +13.63] pp | PASS |
| A6 vs A0 | 1,815 | 6,858 | 2,000 / 37001 | +12.62 / +11.25 pp | +11.93 pp | [+10.24, +13.66] pp | PASS |

Gate：两个观察 Seed 均至少 +2 pp，且 patient-bootstrap 95% CI lower > 0。

---

# AH. 当前受保护阶段锁定表

| 阶段 | 当前状态 | 可以做什么 | 禁止做什么 | 解锁条件 |
|---|---|---|---|---|
| R37.1 内部结果 | 三 Seed scientific GO | proposal、case study、代码复现 | 针对后续保护结果调参 | 已完成 |
| 300-dev | 一次 reveal 完成 / GO | 只作冻结证据归档 | 再选候选、阈值或 checkpoint | 已完成，不得重开选择 |
| 483-test | 一次 reveal 完成 / GO | 只作冻结结果归档 | 探索、模型选择或叙事筛选 | 已完成，不得二次调参 |
| gold | QUARANTINED / unread | 保留独立描述性确认用途 | 调参、选方法、逐病例观察 | 必须另行预注册 |
| R38 | `GO_R38_FIXED64_SURVIVAL` | 复现 exact-64 审计 | 依据 R39 outcome 修改接口 | 已完成 |
| R39 | `GO_R39_FROZEN_VLM_TRANSFER` | 归档、复现、论文报告 | 针对 483 outcome 调参或重选 | 已完成；gold 仍封存 |

---

# AI. R39 Frozen-VLM Transfer 终局结果

| Comparison | Seed effects (pp) | Mean Δ (pp) | Patient-bootstrap 95% CI | Gate |
|---|---|---:|---|---|
| A6 vs frozen A0 | +6.54 / +16.08 / +22.42 | +15.01 | [+13.80,+16.14] | PASS |
| A6 vs current-only | +2.69 / +5.01 / +1.95 | +3.22 | [+2.47,+4.02] | PASS |
| A6 vs query-only | +6.50 / +16.08 / +24.73 | +15.77 | [+14.59,+16.84] | PASS |
| A6 vs prior-shuffle | +1.18 / +2.51 / +2.89 | +2.19 | [+1.39,+3.05] | PASS |

| Seed | A6 true-pair F1 | Frozen A0 F1 | Current-only F1 | Query-only F1 | Prior-shuffle F1 |
|---:|---:|---:|---:|---:|---:|
| 17 | 0.2096 | 0.1442 | 0.1827 | 0.1446 | 0.1978 |
| 29 | 0.2502 | 0.0894 | 0.2000 | 0.0894 | 0.2251 |
| 43 | 0.3089 | 0.0848 | 0.2894 | 0.0616 | 0.2800 |

审计边界：483 patients / 4,821 rows；patient-cluster bootstrap 2,000
replicates，seed 39001；Qwen trainable parameters = 0；无 pixel path；
exactly 64 tokens；prompt 与 projector capacity 匹配；三套 prediction 在
唯一一次 label reveal 前冻结。Gold outcomes 仍未读取。

---

# AJ. R50 强 Temporal Method Benchmark

| Method | Reproduction type | Seed 17 | Seed 29 | Seed 43 | Mean F1 | Mean reversal consistency | Trainable params |
|---|---|---:|---:|---:|---:|---:|---:|
| TILA-CE | official frozen embedding transfer | 0.453228 | 0.458893 | 0.460959 | **0.457693** | 0.360000 | 700 |
| Siamese signed/absolute | strong representation baseline | 0.415895 | 0.414092 | 0.422242 | 0.417409 | 0.290222 | 15,420 |
| TILA-BiCE/TCL | five-class contract adaptation | 0.396846 | 0.390419 | 0.398101 | 0.395122 | **0.865778** | 700 |
| TAC-adapted | Libra component adaptation, not native Libra | 0.267522 | 0.246597 | 0.283137 | 0.265752 | 0.252000 | 10,645,308 |

| Registered contrast | Mean Δ | Patient-bootstrap 95% CI | Interpretation |
|---|---:|---|---|
| TILA-BiCE/TCL − TILA-CE | −6.257 pp | [−9.579,−2.786] | reversal consistency improves but standard F1 falls |
| TAC-adapted − Siamese signed/absolute | −15.166 pp | [−18.802,−11.635] | partial TAC transfer is worse |
| TILA-CE − R49 PRTA exact-64 | +10.332 pp | [+6.599,+14.005] | descriptive cross-interface only |
| B2 − R49 PRTA exact-64 | +6.304 pp | [+2.695,+9.903] | descriptive cross-interface only |

R50 使用同一 2,500 train / 750 evaluation 患者、Seeds 17/29/43 与 2,000
次 patient bootstrap。R49 PRTA 经 frozen Qwen JSON generation；R50 methods
使用直接 finding-conditioned classifier，因此最后两项不是 matched-interface
system claims。483-test、gold 与 external outcomes 均未读取。
