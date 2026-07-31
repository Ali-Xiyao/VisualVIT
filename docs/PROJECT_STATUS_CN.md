# VisualVIT 当前项目状态

## 直接结论

最终总体判定为：

`POSITIVE_PRTA_GEN_R48_FPRR_POOLED_INTERNAL`

Immutable R48 FPRR 在全部 750 名 patient-disjoint held-out patients 上
true-pair macro-F1 0.373614；true−shuffle +5.702 pp、
CI `[+2.529,+9.101]`；true−current +7.860 pp、
CI `[+4.629,+11.045]`。所有原数值门在 pooled descriptive analysis 中
通过。Split-specific qualification/confirmation 状态保留为异质性审计。

R49 随后完成缺失的统一归因：同一 750 人、相同 frozen Qwen 和语义任务下，
Raw/Naive exact-64/PRTA exact-64 macro-F1 为
0.192915/0.295921/0.354372。PRTA−Raw +16.146 pp，CI
`[+12.090,+20.198]`；PRTA−Naive +5.845 pp，CI
`[+2.610,+9.081]`。因此内部证据支持 PRTA 优于直接双图和同预算简单拼接，
并支持跨时间对齐带来独立增益；该结论仍是 post-hoc internal case study。

R50 随后补齐强纵向方法。相同 2,500/750 患者、三 Seed 下，TILA-CE、
Siamese signed/absolute、TILA-BiCE/TCL、TAC-adapted mean macro-F1 为
0.457693/0.417409/0.395122/0.265752。BiCE/TCL 把 mapped reversal
consistency 提高到 0.866，但相对 CE 为 −6.257 pp、CI
`[−9.579,−2.786]`；TAC-adapted 相对 B2 为 −15.166 pp、CI
`[−18.802,−11.635]`。R50 是直接分类、post-hoc internal benchmark，不能
把其相对 frozen-Qwen PRTA 的数值写成等接口替代结论。

R51 已完成系统级配平：相同 2,500-train / fresh 500-evaluation、exact-64、
9,873,920 参数 projector、prompt、JSON、三 Seed、79 updates 和完全冻结 Qwen。
PRTA/TILA/B2 mean macro-F1 为 **0.384796/0.316618/0.255090**；PRTA−TILA
+6.818 pp、CI `[+3.512,+10.080]`，PRTA−B2 +12.971 pp、CI
`[+9.729,+16.286]`。这关闭了 frozen-Qwen matched-interface 缺口。

R52 已补齐用户要求的统一直接分类头比较。沿用冻结的 2,500-train 与新鲜
500-evaluation 患者，PRTA/TILA/B2 使用相同 exact-64 budget、相同
5,991,173 参数头、初始化、训练顺序、优化器、三 Seed 和 2,000 updates。
三者 mean macro-F1 为 **0.360519/0.273051/0.267938**；PRTA−TILA
+8.747 pp、CI `[+4.481,+12.861]`，PRTA−B2 +9.258 pp、CI
`[+4.768,+13.199]`。两项预注册下界均大于零，故
`prta_strict_superiority_supported=true`。该结论只适用于当前 exact-64
适配和 fresh internal matched-head 接口。

TIER-CXR-VLM 的核心冻结链已经跑完，不需要重跑 R38 或 R39：

| 阶段 | 决策 | 核心证据 |
|---|---|---|
| R37.1 | `GO_R37_1_THREE_SEED_INTERNAL_QUALIFICATION` | A6 对 current-only、CMCP、A0 均通过三 Seed patient bootstrap |
| R37C | `GO_R37C_ONE_SHOT_DEV` | 300-dev 一次揭示；A6−A0 +3.42 pp，95% CI [+0.89,+6.20] |
| R38 | `GO_R38_FIXED64_SURVIVAL` | exact-64/no-routing 后 effect retention = 1.0 |
| R39 | `GO_R39_FROZEN_VLM_TRANSFER` | 483-test 一次揭示；A6−A0 +15.01 pp，95% CI [+13.80,+16.14] |

独立的后续生成 readiness 结论为：

| 阶段 | 决策 | 核心证据 |
|---|---|---|
| PRTA-Gen R40A | `STOP_PRTA_GEN_R40A_INFORMATION_SUFFICIENCY` | 历史三均值 readout 在 Seed 17 对 prior-shuffle 的 CI 跨零 |
| PRTA-Gen R40A.1 | `STOP_PRTA_GEN_R40A1_DISCOVERY` | moments Seed 29 为负；cosine Seed 17 为负 |
| PRTA-Gen R40A.2 | `GO_PRTA_GEN_R40A2_QUALIFICATION` | 修复真实 4/12/16/16/12/4 layout 后，三 Seed 对 query/shuffle 的 point 与 bootstrap 门全部通过 |
| PRTA-Gen R40B–B.3 | STOP | 四批互斥 cohort 上 Qwen readout 最好 29/32，未达 32/32 |
| PRTA-Gen R40B.4 | `PASS_PRTA_GEN_R40B4_STRUCTURED_HEAD_SMOKE` | 第五批全新 32-patient cohort 上 progression/schema/finding 均 32/32 |
| PRTA-Gen R40C | `GO_PRTA_GEN_R40C_INTERNAL_GENERALIZATION` | 三 Seed true-pair macro-F1 0.5058/0.4941/0.4827；对 query/shuffle 的点效应与 bootstrap CI 全部通过 |
| PRTA-Gen R41A | `STOP_PRTA_GEN_R41A_PROGRESSION_SFT_SURVIVAL` | G1 true macro-F1 0.3474/0.3632/0.4304，但 Worse recall 0.00/0.08/0.08，G1−G0 全为负；8 个门失败 |
| PRTA-Gen R44A | `STOP_PRTA_GEN_R44A_CROSS_SOURCE_SILVER_SFT_SURVIVAL` | 跨来源 1,000/250 silver cohort 上，G1 对 query-only 明显为正，但三 Seed 均未通过 prior-shuffle 门；Seed 43 进一步退化；9 个门失败 |
| PRTA-Gen R45 | `STOP_PRTA_GEN_R45_CDEB_DISCOVERY` | CDEB F1 0.3420，低于 inherited baseline 0.3806；true−shuffle 为负 |
| PRTA-Gen R46 | `STOP_PRTA_GEN_R46_CEA_DISCOVERY` | +1.06 pp 点增益但 paired bootstrap CI 跨零 |
| PRTA-Gen R47 | `STOP_PRTA_GEN_R47_UCC_DISCOVERY` | true−shuffle 显著，但 UCC−baseline 仅 +0.44 pp 且 CI 跨零 |
| PRTA-Gen R48 qualification | `GO_PRTA_GEN_R48_FPRR_QUALIFICATION` | 无训练/选择/router；true F1 0.4006，true−shuffle +7.98 pp，CI 下界 +3.87 |
| PRTA-Gen R48 confirmation | `STOP_PRTA_GEN_R48_FPRR_CONFIRMATION` | true F1 0.3186；true−shuffle +1.32 pp，CI 跨零；四门失败 |
| PRTA-Gen R48 pooled 750 | `POSITIVE_PRTA_GEN_R48_FPRR_POOLED_INTERNAL` | true F1 0.3736；true−shuffle +5.70 pp、true−current +7.86 pp，两个 CI 下界均 > 0 |
| R48-B3 Raw two-image | `COMPLETE_PRTA_GEN_R48_B3_RAW_TWO_IMAGE_QUALIFICATION` | 原生 prior/current 双图 F1 0.1417；比 FPRR 低 25.89 pp，CI [−30.77,−20.93] |
| PRTA-Gen R49 unified three-way | `COMPLETE_PRTA_GEN_R49_UNIFIED_THREE_WAY` | 同 750 人：Raw/Naive/PRTA F1 0.1929/0.2959/0.3544；PRTA−Naive +5.85 pp，CI [+2.61,+9.08] |
| PRTA-Gen R50 method benchmark | `COMPLETE_PRTA_GEN_R50_METHOD_BENCHMARK` | TILA-CE/B2/TILA-BiCE-TCL/TAC mean F1 0.4577/0.4174/0.3951/0.2658；直接分类接口，post-hoc internal |
| PRTA-Gen R51 matched frozen Qwen | `COMPLETE_PRTA_GEN_R51_MATCHED_INTERFACE_BENCHMARK` | 同 2,500/500、exact-64/projector/prompt/Qwen 和三 Seed：PRTA/TILA/B2 0.3848/0.3166/0.2551；PRTA 对两者 CI 下界均 > 0 |
| PRTA-Gen R52 matched direct head | `COMPLETE_PRTA_GEN_R52_MATCHED_DIRECT_HEAD_BENCHMARK` | 同 2,500/500、exact-64、共享头和三 Seed：PRTA/TILA/B2 0.3605/0.2731/0.2679；PRTA 对两者 CI 下界均 > 0 |

R40A 历史 STOP 不撤销 R39 GO；R40A.2 使用新的 discovery2 和原封未读
qualification 修复了明确的 token-layout mismatch。R40B.4 只跑通
progression-only structured emission 的工程 overfit smoke。R41A 随后完整
执行 progression-only Qwen SFT，但 attention-LoRA 未通过冻结 survival gate。
Raw 双图 baseline 使用冻结 Qwen 的受约束两字段生成，不解锁开放式报告、
其他字段、R42 G-CMCP/reversal 或 R43 gold/external。

R49 的 Naive 与 PRTA 两臂均完成 2,500 rows、79 updates，projector 参数量、
初始化 SHA-256 和训练顺序 SHA-256 完全一致；Qwen trainable parameters 为 0，
exact-64/no-pixel、cache-equivalence、schema 和 finding gates 全通过。Raw 的
原生 vision compute 不等于 exact-64，完整多模态序列也不声称逐字节一致。

R48 confirmation 已按冻结协议一次性完成。虽然 schema/finding 均为 100%、
Qwen/projector trainable parameters 为 0，但 true F1 0.318626 未达 0.35，
true−shuffle +1.325 pp 且 CI `[-3.709,+6.008]`，true−current CI 下界
−1.213 pp；共四门失败。Qualification GO 只保留为 development 结果，
不得表述为 internal replication。

R40C 已按冻结顺序完成 Seeds 17/29/43 和 2,000 次 patient-bootstrap
aggregate，gate failures = 0。自动 launcher 与所有 Seed 进程均已退出，
两张 GPU 回到 0 MiB/0%；protected 300-dev、revealed 483、gold 与 external
均未读取。

R41A 六个 arm 均完成 36 次 updates，schema/finding 均为 100%，cache audit
最大差均为 0；三 Seed 聚合 gate failures = 8。主链在 R41A STOP 后正常结束，
R42A/R43 runtime root 均未创建。所有进程已退出，两张 GPU 回到 0 MiB/0%。

在另立、outcome-independent 冻结的 R44A case study 中，CheXpert silver
cohort 支持 1,000 train / 250 patient-disjoint development，五类均衡。
六个 arm 均完成 94 次 updates；G1 true-pair macro-F1 为
0.3503/0.3512/0.2863，schema/finding 均为 100%。G1 相对 query-only
为 +24.42/+21.14/+18.04 pp，但相对 prior-shuffle 仅为
-0.15/+1.59/-0.25 pp，三个 bootstrap CI 下界均不大于零。Seed 43 的
`Worse` recall 为 0.02、G1−G0 为 -7.25 pp。九个门失败，R44A 正常 STOP，
R42/R43 仍未启动；全部 protected/gold/external outcome flags 保持 false。

在分析协议与代码先提交后，R44A identity-free case study 显示：
true/shuffle 同预测率为 0.732/0.700/0.836，正确性净变化为 -2/+3/0 名患者；
G0→G1 净迁移为 +7/+3/-16。当前机制判断是 correct-prior under-use 与
adapter instability 并存，不能只用 class reweighting 解释。

随后另立的 R45 CDEB 使用 2,500 train / 500 development /
500 sealed qualification / 250 sealed confirmation 的五类均衡、
patient-disjoint roster。Discovery 四臂均完成 Seed 17 的 79 次 updates。
Full CDEB true-pair macro-F1 为 0.3420，低于 inherited baseline 的
0.3806；相对 prior-shuffle 为 -1.26 pp，auxiliary head 为 0.3123。
三个核心门失败，终态为 `STOP_PRTA_GEN_R45_CDEB_DISCOVERY`。
Qualification / confirmation outcome 和 token 均未物化，所有 worker
已退出、两张 GPU 空闲。R45 不得调参续跑；当前只允许另立 R46
causal evidence arbitration，并使用排除整个 R45 roster 的新 development
patients。

只读失败案例研究进一步确认：G1 每 Seed 对 25 个真实 `Worse` 仅输出
0/7/9 次该类；G0-correct/G1-wrong 为 20/24/25，而
G0-wrong/G1-correct 为 22/11/20。跨三个 G1 Seed 只有 31/125 样本
全部正确，49/125 样本全部错误。该结果解释 STOP，但没有新训练、模型选择
或 downstream 解锁。

R39 还通过：

- A6−current-only：+3.22 pp，95% CI [+2.47,+4.02]；
- A6−query-only：+15.77 pp，95% CI [+14.59,+16.84]；
- A6−prior-shuffle：+2.19 pp，95% CI [+1.39,+3.05]；
- 三个 Seed 对全部注册比较方向为正；
- VLM trainable parameters = 0；
- no pixel bypass；
- exactly 64 visual tokens；
- 三套 predictions 在唯一一次 label reveal 前冻结；
- gold outcomes unread。

## 当前可支持的主张

可以支持：

- PRTA-CXR 的正确纵向 prior 表示优于 capacity-matched A0；
- 收益不是仅由 finding query、current image 或随机 prior shortcut 造成；
- 表示收益在固定 64-token 接口和完全冻结的 Qwen3-VL 后仍然存在。
- R49 的同预算对比支持 finding-guided alignment 优于 Naive concat；
- R50 显示官方 TILA frozen embedding 与 B2 是必须报告的强 temporal
  representation baselines；
- R51 在相同 fresh 500 人、exact-64 projector、prompt 和 frozen Qwen 下
  支持 PRTA 显著优于 TILA/B2 exact-64 适配；
- R52 在同一 fresh 500 人、exact-64 和完全相同直接头下支持 PRTA 显著优于
  TILA-exact64 与 B2-exact64，两个 paired CI 下界均大于零；
- R40A.2 semantic-layout 表示含有通过独立 qualification 的
  prior-specific progression 信息；
- 受限结构化头可在全新 32-patient engineering cohort 上把该表示输出为
  progression-only 两字段 JSON，并达到 32/32。
- 排除五批观察患者后，同类 structured head 在 1,000-train /
  500-development patient-disjoint 内部设计中通过三 Seed、query/shuffle
  controls 和 patient-bootstrap 门。

暂不支持：

- gold 或跨机构外部泛化；
- 临床部署；
- 所有视觉 backbone、VLM 尺度或 prompt 均有效；
- Qwen 自由生成、开放式比较句生成、grounding 或 localization 已改善；
- 扩大到跨来源 CheXpert silver 数据即可让 Qwen readout 稳定使用正确 prior；
- 把 R40C 结果视为独立科学确认、跨机构外部泛化或临床有效性；
- 根据已揭示 483-test 再选择的新模型属于 confirmatory 结果。
- TILA/B2 的直接分类优势等价于相同 exact-64 frozen-Qwen 接口优势；
- R52 等价于官方 TILA 原生 global-embedding classifier 的端到端复现，或
  证明 PRTA 普遍优于所有 TILA/B2 用法；
- TAC component adaptation 等价于 native Libra 复现。

## 权威阅读顺序

1. `reports/PRTA_GEN_R51_MATCHED_INTERFACE_RESULT_CN.md`
2. `reports/PRTA_GEN_R52_MATCHED_DIRECT_HEAD_RESULT_CN.md`
3. `reports/PRTA_GEN_R50_LITERATURE_METHOD_REPRODUCTION_RESULT_CN.md`
4. `reports/PRTA_GEN_R45_R48_CASE_STUDY_AND_RAW_B3_RESULT_CN.md`
5. `TIER_CXR_VLM_Next_Stage_Proposal_CN.md`
6. `reports/PRTA_GEN_R44A_CROSS_SOURCE_SILVER_SFT_RESULT_CN.md`
7. `reports/PRTA_GEN_R44A_FAILURE_CASE_STUDY_CN.md`
8. `docs/PRTA_GEN_R44A_FAILURE_CASE_STUDY_PROTOCOL_CN.md`
9. `docs/PRTA_GEN_R44A_CROSS_SOURCE_SILVER_SFT_PROTOCOL_CN.md`
10. `reports/PRTA_GEN_R41A_PROGRESSION_SFT_RESULT_CN.md`
11. `reports/PRTA_GEN_R41A_FAILURE_CASE_STUDY_CN.md`
12. `reports/PRTA_GEN_R40C_STRUCTURED_GENERALIZATION_RESULT_CN.md`
13. `reports/PRTA_GEN_R40A2_R40B4_STRUCTURED_ROUTE_RESULT_CN.md`
14. `reports/PRTA_GEN_R40C_STRUCTURED_GENERALIZATION_PREFLIGHT_CN.md`
15. `reports/PRTA_GEN_R40A_FAILURE_CASE_STUDY_CN.md`
16. `reports/R39_FROZEN_VLM_TRANSFER_FINAL_CN.md`
17. `TIER_CXR_VLM_Empty_Result_Tables_CN.md`
18. `docs/TIER_CXR_VLM_EXPERIMENT_GAP_AUDIT_CN.md`
19. `task_plan.md`、`findings.md`、`progress.md`

## Runtime 权威产物

- PRTA-Gen R51 matched frozen-Qwen aggregate：
  `H:\VisualVIT_runtime\050_routeD\r37_prta_cxr\prta_gen_r51_matched_interface_v1\aggregate.json`

- PRTA-Gen R52 matched direct-head aggregate：
  `H:\VisualVIT_runtime\050_routeD\r37_prta_cxr\prta_gen_r52_matched_direct_head_v1\aggregate.json`

- PRTA-Gen R50 method benchmark aggregate：
  `H:\VisualVIT_runtime\050_routeD\r37_prta_cxr\prta_gen_r50_method_benchmark_v1\aggregate.json`

- R39 pipeline status：
  `H:\VisualVIT_runtime\050_routeD\r37_prta_cxr\r39_pipeline_status.json`
- R39 qualification：
  `H:\VisualVIT_runtime\050_routeD\r37_prta_cxr\r39_sealed_reveal_v1\qualification.json`
- R39 reveal receipt：
  `H:\VisualVIT_runtime\050_routeD\r37_prta_cxr\r39_sealed_reveal_v1\reveal_receipt.json`
- PRTA-Gen R40A target audit：
  `H:\VisualVIT_runtime\050_routeD\r37_prta_cxr\prta_gen_r40_readiness_v1\target_audit\audit.json`
- PRTA-Gen R40A progression aggregate：
  `H:\VisualVIT_runtime\050_routeD\r37_prta_cxr\prta_gen_r40_readiness_v1\probes\progression\aggregate.json`
- PRTA-Gen R40A.2 qualification：
  `H:\VisualVIT_runtime\050_routeD\r37_prta_cxr\prta_gen_r40a2_layout_repair_v1\probes\semantic_layout_means_v1\qualification\aggregate.json`
- PRTA-Gen R40B.4 structured result：
  `H:\VisualVIT_runtime\050_routeD\r37_prta_cxr\prta_gen_r40b4_structured_head_smoke_v1\structured_head\result.json`
- PRTA-Gen R40C aggregate：
  `H:\VisualVIT_runtime\050_routeD\r37_prta_cxr\prta_gen_r40c_structured_generalization_v1\aggregate.json`
- PRTA-Gen R40C automatic sequence status：
  `H:\VisualVIT_runtime\050_routeD\r37_prta_cxr\prta_gen_r40c_structured_generalization_v1\sequence_status.json`
- PRTA-Gen R41A aggregate：
  `H:\VisualVIT_runtime\050_routeD\r37_prta_cxr\prta_gen_r41a_progression_sft_v1\aggregate.json`
- PRTA-Gen R41A descriptive failure case study：
  `H:\VisualVIT_runtime\050_routeD\r37_prta_cxr\prta_gen_r41a_failure_case_study_v1\case_study.json`
- PRTA-Gen R41–R43 master-chain status：
  `H:\VisualVIT_runtime\050_routeD\r37_prta_cxr\prta_gen_r41_r43_authorized_chain_v1\sequence_status.json`
- PRTA-Gen R44 independent support audit：
  `H:\VisualVIT_runtime\050_routeD\r37_prta_cxr\prta_gen_r44_independent_support_v1\audit.json`
- PRTA-Gen R44A aggregate：
  `H:\VisualVIT_runtime\050_routeD\r37_prta_cxr\prta_gen_r44a_cross_source_silver_sft_v1\aggregate.json`
- PRTA-Gen R44A automatic sequence status：
  `H:\VisualVIT_runtime\050_routeD\r37_prta_cxr\prta_gen_r44a_cross_source_silver_sft_v1\sequence_status.json`
- PRTA-Gen R44A identity-free failure case study：
  `H:\VisualVIT_runtime\050_routeD\r37_prta_cxr\prta_gen_r44a_failure_case_study_v1\case_study.json`

这些 runtime 产物不进入 Git。不要为了整理仓库重复计算 source、
per-shard 或 checkpoint hashes。

## 当前停止边界

R39、R40A.2 qualification、R40B.4 engineering smoke、R40C internal
generalization、R41A progression SFT 和 R44A cross-source silver SFT
均已终止。
当前只允许：

- 仓库整理、复现审计和论文材料准备；
- 使用现有聚合结果生成表格或图；
- 使用已提交的 identity-free analyzer 审阅 R41A failure modes，但不得
  把 development 错误用于模型/超参数选择；
- 对 R40B.4 做只读复现审计或独立冻结的后续开发实验；
- 审阅已冻结 R40C/R41A aggregate，或先写新的独立确认协议；
- 只读审阅 R44A aggregate，或把其终态负结果整理为论文材料；
- 独立注册的 gold/external descriptive confirmation。

禁止：

- 针对 483-test outcome 调参、换阈值、挑 Seed 或换 checkpoint；
- 把 post-hoc 483 分析改写成新的 confirmatory GO；
- 用 gold 选择模型或决定叙事。
- 把 R40B.4 写成 Qwen free-generation、科学泛化或临床结论；
- 在五批已观察 cohort 上继续搜索 learning rate、loss、decoder 或阈值；
- 根据 R40C development outcome 调参、挑 Seed/checkpoint 或重分 roster；
- 针对 R41A development outcome 调参、重分 roster、挑 Seed/checkpoint；
- 针对 R44A development outcome 调参、重分 roster、挑 Seed/checkpoint；
- 绕过 R41A/R44A STOP 启动 R42/R43 或其他生成字段。

## 仓库验证状态

- PRTA-Gen R41A/R44A/support/failure-analyzer focused tests：31 passed；
- Ruff (`src scripts tests`)：PASS；
- Python compileall：PASS；
- Markdown local links：PASS；
- `git diff --check`：PASS；
- R44A terminal artifact/hash/firewall/process/GPU audit：PASS；
- 最近一次 full pytest 基线：814 passed、1 expected xfailed、1 failed。

唯一 full-suite failure 是历史 R6 closed-manifest freeze-record hash drift。
同一 targeted test 在没有本轮整理修改的 clean commit `24f57c3` 上也失败，
因此不是本轮移动 proposal、添加索引或 lint cleanup 导致。R6 是已关闭的
旧 protocol；本轮不通过重写其 frozen registry 来制造假 PASS。
