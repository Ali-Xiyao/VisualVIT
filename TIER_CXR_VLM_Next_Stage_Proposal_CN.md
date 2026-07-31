# TIER-CXR-VLM：面向纵向胸片视觉语言模型的扰动一致性分层时间视觉 Token 路由

> **文档性质：** 正式 Proposal / R39 终局交接文档 / 历史方案谱系
> **原始日期：** 2026-07-26
> **当前状态更新：** 2026-07-31
> **项目：** VisualVIT  
> **当前分支：** `codex/r37-prior-responsive-temporal-adapter`
> **当前结果提交：** R39 frozen lineage + R40C internal GO + R48 pooled internal positive + R49 alignment attribution + R50 method benchmark
> **当前方法版本：** **PRTA-CXR R37.1 / TIER-CXR-VLM R39 / PRTA-Gen R50**
> **暂定方法名：** **TIER-CXR-VLM**  
> **英文全称：** *Perturbation-Consistent Hierarchical Temporal Visual Token Routing for Longitudinal Chest X-ray VLMs*

---

# 2026-07-31 PRTA-Gen R44A 跨来源 Silver Case Study 终态

R41A STOP 后没有按其 development outcome 调参。新的 R44A 在任何 R44A
outcome 可见前另立冻结协议，把数据来源换成 CheXTemporal CheXpert silver，
按 patient-disjoint、gold 患者排除、五类均衡规则固定 1,000 train / 250
development，同时原样继承 R41A 的 G0/G1、Seeds 17/29/43、训练设置与
生存门。

六个 arm 均完成 94 次 optimizer update 和四个注册对照评估。G1 true-pair
macro-F1 为 0.3503/0.3512/0.2863；schema validity 与 finding echo 均为
100%。G1 相对 query-only 为 +24.42/+21.14/+18.04 pp，说明模型不是仅凭
finding query 完成任务。然而 G1 相对 prior-shuffle 仅为
-0.15/+1.59/-0.25 pp，三个 patient-bootstrap 95% CI 下界均不大于零。
Seed 43 还出现 `Worse` recall 0.02 与 G1−G0 -7.25 pp。冻结 aggregate
共有九个 gate failure，终态为：

`STOP_PRTA_GEN_R44A_CROSS_SOURCE_SILVER_SFT_SURVIVAL`

Proposal 由此新增一个更明确的负结论：**扩大跨来源 silver 数据可以解决
格式、finding echo 和 query-only separation，但不能单独建立稳定的正确
prior grounding。** R44A 不撤销 R40C progression-only structured-head 的
有限 internal-development GO，也不改写 R41A 原 STOP；它不是独立专家
确认、gold/external 泛化或临床证据。R42/R43 仍未启动且继续锁定。

终态报告：
`reports/PRTA_GEN_R44A_CROSS_SOURCE_SILVER_SFT_RESULT_CN.md`

未来如需继续，只能先提出另一个真正独立、outcome-independent 且在新数据
outcome 可见前冻结的新假设；不得针对 R44A 的 250 名 development 患者
调整 roster、Seed、checkpoint、LoRA、学习率、prompt、类别权重或门。

## 2026-07-31 R44A Failure Case Study 与 R45 新方向

在 identity-free analyzer、输入 hashes 和判别规则先提交后，R44A 六个
arm 的一次性只读 case study 显示：

- G1 true-vs-prior-shuffle prediction agreement 为
  0.732/0.700/0.836；
- true-only/shuffle-only correct 为 17/19、22/19、6/6；
- 250 名患者中 135 名在三个 Seed 下都不因 shuffle 改变输出；
- G0→G1 recovery/regression 为 35/28、22/19、19/35。

因此 R44A 的主要机制不是 schema、finding echo 或单纯 class imbalance，
而是 **correct-prior under-use + attention-LoRA optimization
instability**；Seed 43 `Worse` emission collapse 是叠加的局部问题。
完整报告见：
`reports/PRTA_GEN_R44A_FAILURE_CASE_STUDY_CN.md`。

结合相关工作审计，generic hard-negative image-swap grounding 与
prior/current temporal inversion 已有直接先例。Proposal 因此选择一个更
窄、可证伪的新问题：**R45 Causal Delta Evidence Bottleneck (CDEB)**。
它从 `true_pair - current_only` exact64 delta 学习五类 auxiliary evidence，
把 soft class distribution 映射为固定 64-token budget 内的 evidence
tokens，再条件化冻结 Qwen 生成原两字段 JSON。它不增加 shuffled/invalid
第六类，且必须与 inherited Qwen baseline、structured delta-head、
no-delta 与 no-bridge ablations 比较。

R45 必须使用排除全部 R44A patients 的新 roster，只允许 discovery
train/development 选方法；sealed qualification 与 confirmation 在完整
authority 提交后各揭示一次。R42/R43、gold/external 与开放式报告仍锁定。

## 2026-07-31 R45 CDEB Discovery 终态与 R46 边界

R45 authority 在任何 R45 outcome 可见前完成提交。冻结 roster 为
2,500 train / 500 development / 500 sealed qualification /
250 sealed confirmation，五类均衡、patient-disjoint。四个 discovery
arms 均完成 Seed 17、79 次 optimizer updates；schema、finding echo 与
cache-equivalence 工程门全部通过。

科学门没有通过。Full CDEB true-pair macro-F1 为 0.342023，低于
inherited baseline 0.380648；相对 prior-shuffle 为 -1.258606 pp，
95% CI `[-5.7205, +3.0018] pp`；auxiliary true-pair macro-F1 为
0.312258。三个核心 gate failure 使终态冻结为：

`STOP_PRTA_GEN_R45_CDEB_DISCOVERY`

这说明把低质量 delta soft evidence 直接桥接进 frozen Qwen，不能自动
建立稳定的正确 prior grounding。Qualification / confirmation outcome
与 token 均未物化，R45 不得根据 development outcome 调整 bridge、loss、
checkpoint、Seed 或 gate 后重跑。完整报告：
`reports/PRTA_GEN_R45_CDEB_DISCOVERY_RESULT_CN.md`。

## 2026-07-31 R46–R48 与 Raw Two-Image 强基线

R46 CEA 与 R47 UCC 在两个新的 patient-disjoint development cohort 上继续
检验 learned arbitration。两者都出现正向点估计或 true/shuffle separation，
但相对 inherited baseline 的 paired bootstrap CI 均跨零，因此分别冻结为
STOP。这个序列排除了“再加一个 router”作为合理下一步。

R48 随后删除 training、checkpoint selection、threshold 和 router，只用
immutable R45 Seed-17 generator 在原封存 500 人 qualification 上做
selection-free replication。true-pair macro-F1 0.400584，true−shuffle
+7.982 pp、CI `[+3.873,+11.991]`，true−current +9.733 pp、
CI `[+5.818,+13.706]`，资格门全部通过：

`GO_PRTA_GEN_R48_FPRR_QUALIFICATION`

按用户要求，下一步顺序先执行 R40 已预声明的 B3 Raw two-image frozen
Qwen3-VL。它在同一 500 人 qualification cohort 上直接读取 prior/current
两张完整未裁剪胸片，schema/finding 均为 100%，但 macro-F1 只有 0.141724，
并有 370/500 输出为 `Worse`。Raw−FPRR 为 −25.886 pp，
patient-bootstrap 95% CI `[−30.773,−20.934]`。因此“原生看到两张完整图”
不是充分的 temporal progression baseline；固定医学 encoder + temporal
token interface 提供了实质归纳偏置。

该比较不等计算量，也不是独立确认。随后完全沿用已冻结的 R48 confirmation
协议，在 250 人封存 cohort 上一次性运行。True F1 0.318626，
true−shuffle +1.325 pp、CI `[−3.709,+6.008]`，true−current CI 下界
−1.213 pp；四门失败，终态：

`STOP_PRTA_GEN_R48_FPRR_CONFIRMATION`

因此 R48 qualification GO 不能升级为 internal replication。完整 case study：
`reports/PRTA_GEN_R45_R48_CASE_STUDY_AND_RAW_B3_RESULT_CN.md`。

## 2026-07-31 R48 750 人 Pooled Internal Final

按最终总体判据，将 qualification 500 与 confirmation 250 的 immutable
predictions 合并。750 名 patients 全部 patient-disjoint，模型、checkpoint、
prompt 与输出解析在两次运行之间均未改变。Pooled true-pair macro-F1 为
0.373614；true−shuffle +5.702 pp、CI `[+2.529,+9.101]`；
true−current +7.860 pp、CI `[+4.629,+11.045]`；五类 recall 最低 0.213，
schema/finding 均为 1.0。九个原数值检查全部通过，最终总体状态为：

`POSITIVE_PRTA_GEN_R48_FPRR_POOLED_INTERNAL`

Proposal 的主结果采用该 750 人 pooled internal positive。Split-specific
confirmation STOP 作为 cohort heterogeneity 审计保留，不覆盖总体结论。
边界仍是 internal pooled evidence，不扩展为 external/gold、临床效用或
独立 confirmation。

## 2026-07-31 R49 统一三系统 Alignment Attribution

R48 仍未回答 64-token 方法的增益究竟来自跨时间对齐，还是只来自 frozen
medical visual tokens。R49 因而在同一固定 750 人 evaluation union 上重新运行
三个系统：Raw two-image frozen Qwen、30 prior + 30 current + 4 zero 的 Naive
exact-64，以及 finding-guided PRTA exact-64。三者使用相同语义任务和 JSON
输出合同；Naive/PRTA 进一步严格匹配 64-token 预算、9,873,920 参数 projector、
初始化哈希、2,500 人训练顺序、Seed 17、79 updates 和优化器设置。

| 系统 | macro-F1 |
|---|---:|
| Raw two-image Qwen | 0.192915 |
| Naive exact-64 | 0.295921 |
| PRTA exact-64 | **0.354372** |

PRTA−Raw 为 **+16.146 pp**，paired 95% CI `[+12.090,+20.198]`；
PRTA−Naive 为 **+5.845 pp**，paired 95% CI `[+2.610,+9.081]`。两项 CI
下界均大于零。因此当前 proposal 获得内部机制证据：PRTA 优于直接双图
VLM，也优于同 token 预算的简单拼接；后一项支持增益的一部分确实来自
finding-guided 跨时间对齐，而不是输入 token 或 projector 容量更多。

终态为 `COMPLETE_PRTA_GEN_R49_UNIFIED_THREE_WAY`。Raw 的原生视觉算力不与
exact-64 相等；完整 multimodal serialization 也因图像与 placeholder 模态
不同而不可能逐字节一致，只有语义任务与输出合同相同。R49 仍是内部 post-hoc
case study，不覆盖 R48 confirmation STOP，不扩展为 gold/external、临床或
独立确认。完整报告：
`reports/PRTA_GEN_R49_UNIFIED_THREE_WAY_RESULT_CN.md`。

## 2026-07-31 R50 文献方法复现与强时间表征基线

R49 回答了 PRTA 是否优于 Raw two-image Qwen 和同预算 Naive concat，但这两者
不是最强纵向医学表征。R50 因而先审计 TILA、Libra、TempA-VLP、MLRG、TIM
与 CheXTemporal 的官方论文、代码、权重、许可和任务适配，再在任何 R50
outcome 可见前冻结四个可运行方法：官方 TILA frozen embedding + CE、
TILA-style BiCE+TCL、BiomedCLIP Siamese signed/absolute，以及 Libra TAC
temporal-fusion adapted。

四个方法均使用 R49 的 2,500 train / 750 evaluation 患者、相同 finding 与
五类标签，完整运行 Seeds 17/29/43。三 Seed mean macro-F1 为：

| 方法 | Mean macro-F1 | Mean mapped reversal consistency |
|---|---:|---:|
| TILA frozen embedding + CE | **0.457693** | 0.360000 |
| Siamese signed/absolute | 0.417409 | 0.290222 |
| TILA-style BiCE+TCL | 0.395122 | **0.865778** |
| TAC temporal fusion adapted | 0.265752 | 0.252000 |

在相同直接分类接口上，BiCE+TCL−CE 为 −6.257 pp，95% CI
`[−9.579,−2.786]`：时间反转一致性大幅提高，但五类标准 F1 显著下降，
主要代价出现在 New/Resolved。TAC-adapted−Siamese 为 −15.166 pp，CI
`[−18.802,−11.635]`，说明缺少 Libra 的 12-layer RAD-DINO LFE 与原生生成
对齐时，复杂 fusion block 不如简单 signed/absolute 表征。

相对 R49 PRTA exact-64，TILA-CE 与 B2 的跨接口描述效应分别为 +10.332 pp
和 +6.304 pp，CI 下界均为正。但 R50 使用直接 structured classifier，
PRTA 使用 frozen-Qwen JSON generation，因此不能写成等接口系统替代。新的
论文结论是：R49 的 alignment attribution 仍成立，同时强 temporal encoder
baseline 是必须补充的；下一步若继续，应把 TILA/B2 接入完全相同的 exact-64、
projector 和 frozen-Qwen 合同，而不是继续堆叠 router。

终态为 `COMPLETE_PRTA_GEN_R50_METHOD_BENCHMARK`。R50 是 outcome 已可见后的
post-hoc internal benchmark，不覆盖 R48 confirmation STOP，也不解锁
gold/external 或临床主张。完整报告：
`reports/PRTA_GEN_R50_LITERATURE_METHOD_REPRODUCTION_RESULT_CN.md`。

历史上，R45 后曾据相关工作审计另立 **R46 Causal Evidence Arbitration
(CEA)**；R46 与后续 R47 的实际 STOP 已由上节覆盖，不再把它们写成未来
动作。R48 confirmation 也已完成并 STOP；当前没有继续追显著性的合法
下游门。

# 2026-07-30 PRTA-Gen 案例驱动修复附录

## 终态更新

案例驱动修复已经按“新边界、先冻结、后读取、首失败门停止”的顺序跑通一个
严格限定的 proposal 路径：

```text
GO_PRTA_GEN_R40A2_QUALIFICATION
→ PASS_PRTA_GEN_R40B4_STRUCTURED_HEAD_SMOKE
→ GO_PRTA_GEN_R40C_INTERNAL_GENERALIZATION
→ STOP_PRTA_GEN_R41A_PROGRESSION_SFT_SURVIVAL
```

R40A.2 修正了此前错误的 20/20/20 pooling，按真实
`4/12/16/16/12/4` semantic layout 读取 exact-64 token。独立 discovery2
和原封未读的 qualification 均通过三 Seed、query-only、prior-shuffle 与
patient-cluster bootstrap 门；因此 progression-only engineering generation
被合法解锁。

随后四类 Qwen readout 在四批互不重叠的 32-patient fit cohort 上依次失败：
free-greedy 最好 29/32、整段候选评分 28/32、progression-span 加权 24/32、
首 token 五分类 23/32。它们都能学习 JSON 形式和 finding echo，但没有在
冻结预算内稳定完成 progression 语义绑定。这里的结论不是“Qwen 不是
LLM”，而是当前 Qwen causal-LM readout 路线没有通过工程 overfit 门。

R40B.4 因而把已 qualification 的 semantic-layout 表示接入一个
499,973 参数的受限 progression head，再确定性输出唯一合法的两字段 JSON。
它在第五批、排除前 128 名已观察患者的全新 32-patient cohort 上达到：

- progression 32/32；
- schema validity 32/32；
- finding echo 32/32；
- loss ratio `7.33027e-08`；
- exact64/no-pixel PASS，300-dev/483/gold/external 全部未读。

R40C 随后把同类 structured head 放到排除五批观察患者后的
1,000-train / 500-development patient-disjoint 设计中，三 Seed 对
query-only/prior-shuffle 的冻结门全部通过。因此当前 proposal 已跑通
**progression-only structured emission internal development
generalization path**。Qwen 自由生成、开放式报告、
laterality/anatomy/degree/evidence、独立科学确认与临床主张仍锁定，不能由
R40C 代替或外推。

R41A 随后以 375 train / 125 patient-disjoint development、Seeds
17/29/43、projector-only 与 attention-LoRA、每臂 36 updates 完整执行。
G1 true macro-F1 为 0.3474/0.3632/0.4304，但 `Worse` recall 为
0.00/0.08/0.08，且 G1−G0 为 -0.46/-13.40/-6.85 pp。三 Seed aggregate
共有 8 个冻结门失败，终态为
`STOP_PRTA_GEN_R41A_PROGRESSION_SFT_SURVIVAL`。因此 proposal 在 R41A
收束，R42A/R43 未启动，也不得按本次 outcome 调参后重跑。

终态报告：
`reports/PRTA_GEN_R41A_PROGRESSION_SFT_RESULT_CN.md`

## 2026-07-31 R41A 失败案例研究结论

在不启动新训练、不改变 roster/Seed/checkpoint/gate、也不读取任何
protected/gold/external outcome 的前提下，预先提交的只读分析器进一步
定位了 R41A STOP：

- G1 在每 Seed 各 25 个真实 `Worse` 样本上只输出 0/7/9 次 `Worse`，
  recall 为 0.00/0.08/0.08；错误类别还会随 Seed 改变；
- G0 正确但 G1 错误的样本为 20/24/25，G1 修复 G0 的样本为
  22/11/20，因此 attention-LoRA 在 Seed 29/43 为净负迁移；
- 三个 G1 Seed 只有 31/125 样本全部正确，49/125 样本全部错误；
- true pair 相对 prior shuffle 有局部正向响应，但 Seed 17 只有
  11 个 true-sensitive 对 9 个 control-favored 样本，不能覆盖冻结
  bootstrap、类别支持与 G0 对照门失败。

因此失败的精确表述是：**当前 Qwen attention-LoRA free-greedy
progression readout 未形成跨类别、跨 Seed、优于 projector-only 的稳定
绑定**。这不是“Qwen 不是 LLM”，也不是输入完全无信号。Proposal 当前
保留 R40C structured head 的有限内部开发 GO，同时把 R41A 作为终态负
结果；不得在同一 125-patient development 上针对已观察错误调参后重跑。

案例研究：
`reports/PRTA_GEN_R41A_FAILURE_CASE_STUDY_CN.md`

任何未来 readout 尝试必须另立 outcome-independent protocol，并在新
patient cohort 的 outcome 可见前冻结类别支持、G0/G1、Seed 和控制门。
本案例研究不解锁 R42A/R43。

## R40C 终态：内部开发泛化 GO

R40B.4 只证明 32-row overfit。下一阶段不继续调 Qwen，而是冻结
`PRTA-Gen R40C Structured Generalization`，检验同一结构化头的
patient-disjoint internal development generalization：

- 排除 R40B–R40B.4 五批共 160 名已观察患者；
- 从剩余 R40A.2 fit 固定 1,000 train / 500 development，每类分别
  200/100 名患者；
- Seeds 17/29/43；
- true-pair、current-only、query-only、prior-shuffle 四个
  499,973 参数容量匹配 arm；
- train-only mean/std，AdamW 0.001、batch 128、100 epochs、800
  updates/arm，不早停、不选 checkpoint；
- 主门为 held-out macro-F1、五类 recall、相对 query/shuffle 的 +2 pp
  point effect 与 2,000 次 patient-bootstrap CI 下界。

preflight、roster 与终态 aggregate 依次返回：

```text
PASS_PRTA_GEN_R40C_PREFLIGHT
PASS_PRTA_GEN_R40C_RUNNER_PREFLIGHT
PASS_PRTA_GEN_R40C_ROSTER_SUPPORT
GO_PRTA_GEN_R40C_INTERNAL_GENERALIZATION
```

三 Seed true-pair macro-F1 为 0.5058 / 0.4941 / 0.4827，最低类别 recall
为 0.38 / 0.38 / 0.36。相对 query-only 的效应为
+19.72 / +20.10 / +17.42 pp，95% CI 下界均 >= +12.64 pp；相对
prior-shuffle 的效应为 +10.50 / +10.91 / +9.64 pp，95% CI 下界均
>= +5.27 pp。schema 与 finding echo 均为 100%，gate failures = 0。

R40C 只允许称 internal development generalization，因为 source 仍是已经
参与方法开发的 R40A.2 fit partition。它不会自动解锁 Qwen free generation、
R41–R43、gold/external 或独立科学主张。

冻结协议：
`docs/PRTA_GEN_R40C_STRUCTURED_GENERALIZATION_PROTOCOL_CN.md`

终态报告：
`reports/PRTA_GEN_R40C_STRUCTURED_GENERALIZATION_RESULT_CN.md`

R39 之后的第一版 PRTA-Gen R40A 信息审计已经关闭为：

```text
STOP_PRTA_GEN_R40A_INFORMATION_SUFFICIENCY
```

它不撤销下方 R39 Frozen-VLM Transfer GO。失败来自新生成问题的更严格
门槛：三均值 progression readout 在 Seed 17 相对 prior-shuffle 的效应为
+1.06 pp，但 patient-cluster 95% CI 为 [-0.93,+3.26] pp。

案例研究显示，旧 readout 对 Stable/New 的净 prior sensitivity 为正，
对 Improved/Worse/Resolved 为负；true-sensitive 病例的 token 区域 RMS
通常更高。这支持“区间内分布/位置被三均值丢失”的有限修复假设。

当前已经冻结 R40A.1：

1. 从原 R40A training 患者一次性划分 5,787 fit、1,500 discovery、
   1,500 one-shot qualification；
2. 依次测试 regional mean/std/max 和固定四分量 DCT-II position basis；
3. 第一个通过 discovery 三 Seed、query-only/prior-shuffle、patient
   bootstrap 门的候选被唯一选中；
4. qualification 不允许重新选候选；
5. 只有 qualification GO 才解锁 progression-only 的 R40B 32-row
   generative overfit smoke；
6. laterality、anatomy、degree、evidence、R41/R42/R43 仍锁定。

R40A.1 后续已经按首失败门关闭：regional moments 在 Seed 29 相对
prior-shuffle 为 -5.18 pp；regional cosine 在 Seed 17 为 -1.23 pp。
其 qualification 未读取。

关闭后审计发现 20/20/20 probe 分区与真实
`4/12/16/16/12/4` token layout 不一致。当前进一步冻结 R40A.2：

- 保留原 qualification 不动；
- 排除已观察 R40A.1 discovery；
- 从原 fit 新划 1,500 discovery2 / 4,287 fit2；
- 先测 semantic-layout means，再测同边界 moments；
- 仍使用三 Seed、query/prior-shuffle controls 和 patient bootstrap。

权威文件：

- `reports/PRTA_GEN_R40A_FAILURE_CASE_STUDY_CN.md`
- `docs/PRTA_GEN_R40A1_CASE_DRIVEN_REPAIR_PROTOCOL_CN.md`
- `configs/prta_gen/prta_gen_r40a1_case_repair_v1.json`
- `docs/PRTA_GEN_R40A2_LAYOUT_REPAIR_PROTOCOL_CN.md`
- `configs/prta_gen/prta_gen_r40a2_layout_repair_v1.json`

---

# 当前执行状态：R39 Frozen-VLM Transfer 科学 GO

> 2026-07-30 终局权威更新：下方原“两 Seed内部 PASS”内容作为历史快照
> 保留；当前链路已经按冻结顺序完成 R37.1 三 Seed、R37C 300-dev、
> R38 exact-64 survival 和 R39 one-shot 483-test。

```text
GO_R37_1_THREE_SEED_INTERNAL_QUALIFICATION
→ GO_R37C_ONE_SHOT_DEV
→ GO_R38_FIXED64_SURVIVAL
→ GO_R39_FROZEN_VLM_TRANSFER
```

R39 使用 483 patients / 4,821 rows，三 Seed patient-cluster bootstrap
2,000 次（seed 39001）。主比较 A6 versus frozen A0 为 +15.01 pp，
95% CI [+13.80,+16.14]；current-only、query-only、prior-shuffle 三个
注册控制也全部通过，分别为 +3.22、+15.77、+2.19 pp，CI 下界均大于
零且每个 Seed 方向为正。

全部三套 projector checkpoint 和 outcome-blind sealed prediction 在
唯一一次 483-label reveal 前冻结。Qwen 的可训练参数为 0，无 pixel
bypass，视觉接口严格为 64 tokens，prompt 与 projector capacity 匹配。
Gold outcomes 仍未读取。

因此，可以确认 **TIER-CXR-VLM 在本项目预注册的 silver cohort、
固定 Qwen/64-token/projector/seed/control 边界内有效，并通过 frozen-VLM
transfer gate**。这不等价于 gold 外部泛化、临床可部署或绝对性能已经充分；
三 Seed A6 absolute macro-F1 为 0.2096/0.2502/0.3089，仍有明显 Seed
差异。后续若做 gold，只能作为另行预注册的描述性确认，不能回头调参。

完整终局报告：`reports/R39_FROZEN_VLM_TRANSFER_FINAL_CN.md`。

---

# 历史执行快照：R37.1 两 Seed 内部 PASS

> 本节是截至 2026-07-29 的当前权威状态；后续 R32–R36 内容保留为
> TIER-CXR-VLM 的历史设计与失败谱系，不得覆盖本节结论。

## 当前结论

R37 原版虽然对正确 prior 有明显响应，但两个正式 Seed 的 inversion
consistency 仅为 0.8438/0.8735，未达到冻结门槛 0.90，因此已经冻结为：

```text
STOP_R37_INVERSION_CONSISTENCY
```

R37.1 在任何 fresh-holdout outcome 被读取前，冻结了一个无可训练参数的
Z2-equivariant logit projection：

```text
L_forward = 0.5 * (z_forward + P(z_reverse))
L_reverse = P(L_forward)
```

其中 `P` 固定执行 Stable→Stable、Improved↔Worse、New↔Resolved。该修复
只保证时间反转的结构一致性，不保证分类正确、正确 prior 收益、CMCP 收益
或 state retention；这些仍由独立 fresh holdout 实测。

## R37.1 冻结队列与结果

- 训练：10,287 patients / 39,491 finding rows；
- fresh holdout：1,815 patients / 6,858 finding rows；
- old R37 calibration patients：在 roster 冻结时完全排除；
- A6 Seeds：17、29；
- capacity-matched A0 Seeds：17、29；
- bootstrap：patient-cluster，2,000 replicates，seed 37001；
- Seed 43：按用户决定暂不运行。

| Gate / comparison | Seed 17 | Seed 29 | Two-seed mean | 95% CI | 结果 |
|---|---:|---:|---:|---:|---|
| Inversion consistency | 1.0000 | 1.0000 | 1.0000 | N/A | PASS |
| State retention cosine | 0.9934 | 0.9929 | 0.9931 | N/A | PASS |
| A6 − current-only | +30.42 pp | +25.22 pp | +27.82 pp | [+25.96, +29.50] pp | PASS |
| A6 − CMCP | +12.76 pp | +11.39 pp | +12.08 pp | [+10.61, +13.63] pp | PASS |
| A6 − A0 | +12.62 pp | +11.25 pp | +11.93 pp | [+10.24, +13.66] pp | PASS |

当前机器结论为：

```text
PASS_R37_1_TWO_SEED_INTERNAL_SCREEN
```

它支持“PRTA-CXR 在这两个冻结 Seed 和独立 fresh holdout 上具有强、
方向一致的正确-prior收益，并优于 capacity-matched A0”这一内部描述性
结论。它不等价于原协议要求的三 Seed scientific GO。

## 为什么当时暂不解锁 300-dev、483-test、gold、R38/R39

这些不是当前训练缺失的数据，而是不同用途的受保护后续门：

| 受保护阶段 | 用途 | 当前保持锁定的原因 |
|---|---|---|
| 300-dev | 冻结候选后的单次内部确认 | 原三 Seed内部 scientific gate 未执行 |
| 483-test | 最终 sealed test | 防止测试集参与模型、阈值或叙事选择 |
| gold | 专家/外部标签确认 | 防止独立确认集退化为调参集 |
| R38 | 固定 64-token survival | 必须先有被完整资格化的 R37 表示 |
| R39 | frozen-VLM transfer | 必须先通过 R38，且 VLM/prompt/projector 全冻结 |

以下是 2026-07-29 两 Seed快照下的原始判断；300-dev、483-test、R38 和
R39 后来已按顶部终局更新中的注册顺序完成，gold 仍保持锁定。

因此“暂不解锁”表示主动维持防泄漏边界，不表示 R37.1 工程失败。当时推荐
动作是整理 proposal、结果表和 case study，并以两 Seed 描述性内部 PASS
停止 GPU 实验。若未来需要 confirmatory scientific GO，唯一协议一致路径是
补齐 Seed 43 的 A6/A0 和原三 Seed patient bootstrap，再重新判断是否允许
一次性 300-dev reveal。

---

# 0. 最终决策

下一阶段不再继续搜索新的 silver 分类投票规则，不恢复已经失败的 universal-binding/CAPES 主命题，也不直接把 R31 的类别答案交给语言模型。

本阶段唯一主线是：

> **把 R31 已经验证的“复杂时间证据稳定时采用、不稳定时回退”的原则，从 prediction-level routing 升级为 visual-token-level routing；在严格固定 64 个视觉 Token、冻结视觉主干和冻结 VLM 的条件下，让 VLM 自己完成最终进展判断与比较式文本生成。**

最终系统结构：

```text
Prior CXR + Current CXR + Finding Query
                    ↓
           Frozen CXR ViT Encoder
                    ↓
       Prior / Current Patch Tokens
                    ↓
┌────────────────────────────────────────────┐
│ Tier 0：Current-state evidence             │
│ Tier 1：Global temporal evidence           │
│ Tier 2：Query-conditioned local evidence   │
│ Tier 3：Soft cross-time relation evidence  │
└────────────────────────────────────────────┘
                    ↓
     Perturbation-consistency reliability gate
                    ↓
 Robust Token Bundle  或  Rich Token Bundle
                    ↓
       固定 64-token Visual Interface
                    ↓
           Shared Trainable Projector
                    ↓
          Frozen Qwen3-VL-4B-Instruct
                    ↓
  3/5 类 progression + VQA + grounded comparison
```

---

# 1. 当前科学状态与不可撤销结论

## 1.1 R26：原 universal-binding 主命题没有通过

R26 检验的是：

```text
Oracle-correct entity binding
vs
Deranged entity binding
```

结果：

| 项目 | 结果 |
|---|---:|
| 主效应 | +1.17 pp |
| 95% CI | [-2.78, +5.14] pp |
| 预注册门槛 | ≥ +5 pp 且 CI 不跨零 |
| 正式结论 | `STOP_C1` |

因此，以下说法不能再作为论文主张：

> 精确跨时间实体绑定是所有纵向胸片样本的决定性缺失机制。

R26 不是程序失败，不能通过换 backbone、换阈值或改 seed 撤销。

---

## 1.2 R31：条件可靠的丰富时间证据已经得到 fresh-silver 支持

R31 检验的是：

```text
若三个 regularized multiscale 模型完全一致：
    采用 rich prediction
否则：
    回退 uniform fusion majority
```

结果：

| 项目 | 结果 |
|---|---:|
| Consensus macro F1 | 0.5033 |
| Uniform macro F1 | 0.4728 |
| 提升 | +3.05 pp |
| 95% CI | [+0.42, +5.60] pp |
| 三个 seed | 全部正向 |
| Bootstrap | 10,000 / 10,000 有效 |
| 复现 | 新进程逐文件哈希一致 |
| 正式状态 | `PASS_R31_SCIENTIFIC_GO_REPRODUCED` |

R31 支持的命题是：

> 丰富的多尺度时间证据不是对每个病例都可靠；跨扰动预测一致性可以识别其中一部分较可靠的病例，并在其他病例上安全回退。

它仍然只是：

- fresh-silver development GO；
- prediction-level 路由；
- 浅层分类 probe；
- 三分类；
- 非最终 VLM。

---

## 1.3 本阶段要回答的新问题

本阶段不是重复 R31，而是提出新的、独立冻结的问题：

> **R31 的条件可靠性规律能否在表示 Token 化之后继续存在，并进一步转移到 frozen VLM，使同一个 VLM 在相同 Token 数量、相同参数量和相同 prompt 下取得真实收益？**

---

# 2. 核心研究假设

## H1：Token Survival

R31 的 rich-versus-robust 视觉信号在转换成固定预算视觉 Token 后仍能被一个共享轻量 probe 读出。

形式化为：

\[
\Delta_{\text{token}}
=
F1(\text{gated token bundle})
-
F1(\text{robust token bundle})
>0
\]

这是进入 VLM 前的必要生存门。

---

## H2：Frozen-VLM Transfer

在相同 frozen VLM、相同 64-token 预算、相同 projector 容量和相同训练数据下：

\[
F1(\text{TIER-CXR-VLM})
>
F1(\text{uniform temporal token VLM})
\]

即收益不能只存在于浅层分类器。

---

## H3：Outcome-Free Routing

测试时路由器只读取：

- 视觉 Token；
- 三个扰动模型的预测一致性；
- 模型间分布差异；
- 局部/全局证据冲突；

不得读取：

- 测试标签；
- 报告中的 progression 词；
- R31 的最终真实类别；
- gold bounding box；
- gold correspondence。

---

## H4：Human-Gold / External Confirmation

完全冻结的方法在未用于模型选择的专家标签或外部来源上仍优于 robust/uniform token baseline。

---

## H5：Grounded Temporal Reasoning

方法不仅提高类别 F1，还应减少：

- wrong-time；
- wrong-side；
- unsupported-change；
- finding/anatomy 不一致；

并提高局部证据 grounding。

---

# 3. 论文主张与明确不主张的内容

## 3.1 计划主张

1. 复杂时间证据具有**条件可靠性**，不是越复杂越普遍有效。
2. 跨合理视觉扰动的一致性可以作为 rich temporal evidence 的可靠性代理。
3. 在固定 64-token 预算下，可靠性门控的分层时间 Token 优于统一 Token 融合。
4. 该收益可以从浅层 probe 迁移至 frozen VLM。
5. 方法在 human-gold / external 数据上仍具有正向价值。

## 3.2 不主张

1. 不主张 universal exact entity binding。
2. 不主张端到端自动发现所有病灶；主任务是 **finding-conditioned progression reasoning**。
3. 不把监督训练称为 label-free；准确措辞为 **outcome-free test-time routing**。
4. 不把 R31 的预测标签直接输入 VLM。
5. 不声称 silver 自动标签等价于放射科专家 gold。
6. 不声称临床可部署或可替代放射科医生。
7. 不恢复 learned Hungarian matcher、DIVE 或通用多图路线。

---

# 4. 与现有工作的差异边界

纵向胸片领域已经存在：

- 直接拼接 prior/current 表征；
- temporal feature fusion；
- Temporal Alignment Connector；
- directional semantic transition pretraining；
- temporal inversion；
- region-guided change tokens；
- grounded multi-finding report generation。

因此，以下组件单独不能作为主要创新：

```text
prior-current difference
ROI token
change token
cross-attention
时间反转
报告监督
把视觉 Token 接入 LLM
```

本工作的创新组合应明确限定为：

> **在固定 Token 预算下，对 state、global、local、soft-relation 四级视觉证据进行可靠性驱动的选择；可靠性来自跨视觉子空间/patch 扰动的一致性，最终答案由冻结 VLM 读取被路由的视觉 Token 后产生。**

---

# 5. 任务定义

## 5.1 输入

每个样本为：

```text
Prior frontal chest X-ray
Current frontal chest X-ray
Finding query
Optional fixed anatomy prior
```

主系统禁止使用逐病例报告中抽取的 progression 和 case-specific anatomy 作为输入。

## 5.2 Primary 输出

第一阶段三分类：

```text
Stable
Improved
Worse
```

第二阶段五分类：

```text
Stable
Improved
Worse
New
Resolved
```

## 5.3 Secondary 输出

### Temporal VQA

```text
Compared with the prior study, how has the pleural effusion changed?
```

### Grounded comparative sentence

```text
The right pleural effusion has improved compared with the prior study,
with decreased opacity at the right lung base.
```

---

# 6. 模型结构

## 6.1 冻结视觉主干

Primary encoder：

```text
Frozen BiomedCLIP ViT
```

原因：

- 与 R31 保持连续；
- 避免把收益归因于换 backbone；
- 先证明视觉接口本身有效。

不再只读取 `[CLS]`，而是读取：

\[
P \in \mathbb{R}^{N_p\times d},
\qquad
C \in \mathbb{R}^{N_c\times d}
\]

其中 \(P\) 和 \(C\) 分别是 prior/current 的 patch tokens。

CLS 仍可作为 global control，但不是唯一视觉输入。

---

## 6.2 Finding Query

finding 文本通过冻结的医学文本编码器得到：

\[
q_f \in \mathbb{R}^{d}
\]

Primary 输入只使用 finding 名称，例如：

```text
pleural effusion
pneumothorax
consolidation
cardiomegaly
```

逐病例 report-derived anatomy 不进入 Primary。

Secondary 对照可使用：

- 固定 finding→anatomy 映射；
- 自动图像 anatomy locator；
- gold box upper bound。

---

# 7. 四级视觉证据

## Tier 0：Current-State Tokens

目的：

> 建立稳健的当前状态保底证据，显式保留 current-only shortcut 作为控制，而不是让其他分支暗中学习它。

计算：

\[
T_0
=
\operatorname{Resampler}_{state}(C,q_f)
\]

包含：

- current CLS/global；
- query-attended current patches；
- current image acquisition/view metadata（若合法且完整）。

---

## Tier 1：Global Temporal Tokens

目的：

> 捕捉双肺整体变化、大范围密度变化、心影或全局成像状态变化。

先得到 prior/current global summary：

\[
g_p=\operatorname{Pool}(P), \qquad g_c=\operatorname{Pool}(C)
\]

构造方向与幅度交互：

\[
\phi(g_p,g_c)
=
[g_p,g_c,g_c-g_p,|g_c-g_p|,g_p\odot g_c]
\]

然后通过 global resampler 产生固定数量 Token。

---

## Tier 2：Query-Conditioned Local Transition Tokens

目的：

> 针对当前 finding，从两张图中提取最相关的局部 patch，再比较变化。

query relevance：

\[
a^p_i
=
\operatorname{softmax}_i
\left(
\frac{(W_q q_f)^\top (W_k p_i)}{\sqrt d}
\right)
\]

\[
a^c_j
=
\operatorname{softmax}_j
\left(
\frac{(W_q q_f)^\top (W_k c_j)}{\sqrt d}
\right)
\]

得到 query-conditioned local summaries：

\[
\tilde p=\sum_i a^p_i p_i,
\qquad
\tilde c=\sum_j a^c_j c_j
\]

并构造：

\[
[\tilde p,\tilde c,\tilde c-\tilde p,
|\tilde c-\tilde p|,\tilde p\odot\tilde c]
\]

该层不要求 gold ROI。

---

## Tier 3：Soft Cross-Time Relation / Context Tokens

目的：

> 仅在 rich 分支中提供更细粒度的跨图局部关系，但不恢复 universal hard matching。

soft correspondence：

\[
A_{ij}
=
\operatorname{softmax}_{j}
\left(
\frac{Q(p_i)K(c_j)^\top}{\sqrt d}
\right)
\]

prior patch 的 current 软对应：

\[
\hat c_i=\sum_j A_{ij}c_j
\]

relation feature：

\[
r_i
=
\operatorname{MLP}
[
p_i,\hat c_i,\hat c_i-p_i,
|\hat c_i-p_i|,p_i\odot \hat c_i,
H(A_i),s_i
]
\]

其中：

- \(H(A_i)\)：匹配分布熵；
- \(s_i\)：query relevance；
- 允许加入 null prototype 以支持 New/Resolved；
- 这是一种 soft relational evidence，不声称真实 lesion identity。

---

# 8. 两套等预算 Token Bundle

## 8.1 Robust Bundle

用于：

- rich 表示不稳定；
- 三个扰动 probe 不一致；
- 模型应优先降低方差。

内容：

- 稳健 current-state tokens；
- global temporal tokens；
- 低容量 query-local summary；
- relation 槽位使用 coarse relation 或 neutral token。

## 8.2 Rich Bundle

用于：

- rich 多尺度视觉表示在三个扰动视角下完全一致。

内容：

- state/global；
- query-conditioned local；
- context；
- soft cross-time relation；
- confidence/entropy metadata。

## 8.3 关键公平性约束

两套 bundle 必须保持：

- 完全相同的 64 个物理 Token；
- 完全相同的 Token 顺序；
- 完全相同的 Token type layout；
- 完全相同的 projector；
- 完全相同的 VLM；
- 完全相同的 prompt；
- 完全相同的训练样本；
- 完全相同的可训练参数量；
- 仅 Token 内容和 logical validity 不同。

---

# 9. 固定 64-token 布局

| 位置 | Token 类型 | 数量 | 主要内容 |
|---|---|---:|---|
| 0–3 | Query / Control | 4 | finding query、时间方向、全局控制 |
| 4–15 | State | 12 | current-state patch summaries |
| 16–31 | Global Transition | 16 | prior/current global interaction |
| 32–47 | Local Transition | 16 | query-conditioned local changes |
| 48–59 | Relation / Context | 12 | soft cross-time relations / context |
| 60–63 | Reserved | 4 | neutral / future extension |
| **总计** |  | **64** | 固定 |

建议新增 Token type：

```text
TYPE_QUERY = 0
TYPE_STATE = 1
TYPE_GLOBAL_TRANSITION = 2
TYPE_LOCAL_TRANSITION = 3
TYPE_RELATION = 4
TYPE_RESERVED = 5
```

现有 `RelationProjector` 可扩展为 6 个 Token type；neutral embedding、metadata、固定 64 个 physical attention positions 可以继续复用。

---

# 10. R31 Gate 如何转为 Token Gate

## 10.1 Primary：Hard Perturbation-Consensus Gate

三个 rich auxiliary probes：

```text
Probe-17
Probe-29
Probe-43
```

每个 probe 使用不同的、冻结的视觉子空间扰动。

定义：

\[
g(x)=
\mathbf 1[
\arg\max p_{17}
=
\arg\max p_{29}
=
\arg\max p_{43}
]
\]

最终视觉 Token：

\[
T(x)
=
g(x)T_{\text{rich}}(x)
+
[1-g(x)]T_{\text{robust}}(x)
\]

注意：

- \(g(x)\) 只是 bundle 选择信号；
- probe 的类别名称不写入 Token；
- VLM 看不到 “Improved/Worse/Stable” 的 probe 预测；
- VLM 必须独立读取视觉 Token 并输出答案。

---

## 10.2 训练集上的 OOF Gate

若 probe 在训练自己的样本上产生预测，unanimity 会被高估。

因此必须：

1. 将 training patients 分成 5 个 patient-disjoint folds；
2. 每次在 4 folds 训练 probes；
3. 对剩余 fold 生成 out-of-fold route；
4. 拼接得到所有训练样本的 OOF route；
5. dev/test route 由完整 train 上训练的 probe family 产生。

禁止使用 in-sample route 训练 VLM projector。

---

## 10.3 Secondary：Continuous Stability Router

仅在 Hard Gate 通过 Token Survival、但 VLM transfer 弱时，才允许作为预注册 mutation。

定义：

\[
\bar p
=
\frac{1}{K}\sum_kp_k
\]

\[
D(x)
=
\frac{1}{K}\sum_k
JS(p_k,\bar p)
\]

\[
S(x)=1-\operatorname{Normalize}(D(x))
\]

在 dev calibration set 上冻结阈值 \(\tau\)：

```text
S(x) ≥ τ → rich
S(x) < τ → robust
```

该版本不是首轮默认方法，避免再次无边界探索路由规则。

---

# 11. Frozen VLM 接口

## 11.1 Primary VLM

```text
Qwen/Qwen3-VL-4B-Instruct
```

原因：

- 4B 规模更适合 24GB 单卡；
- 仓库已有 Qwen3-VL exact-64-placeholder 路径；
- 可保持 VLM 全冻结；
- 先验证视觉接口，而不是模型规模。

Secondary robustness：

```text
Qwen3-VL-8B-Instruct
```

仅在 Primary 完成后运行。

## 11.2 冻结范围

必须冻结：

- Qwen3-VL 全部参数；
- BiomedCLIP 主干；
- tokenizer / word embeddings；
- language decoder。

允许训练：

- tier resamplers；
- soft relation adapter；
- common-width token MLP；
- visual projector；
- auxiliary probes。

## 11.3 严禁 pixel bypass

TIER token path 不得同时传入：

```text
pixel_values
image_grid_thw
deepstack_visual_embeds
任何原生 image/video key
```

视觉信息只能通过 64 个新 Token 进入 VLM。

Raw two-image VLM 是独立 baseline，不与 token path 混用。

## 11.4 标签评分

复用现有 candidate likelihood 机制：

```text
stable
worse
improved
new
resolved
```

Primary 三分类阶段只在：

```text
stable / worse / improved
```

三个候选中取 argmax，但仍保留相同 adapter 实现。

五分类阶段使用全部候选。

---

# 12. Prompt 模板

## 12.1 三/五分类模板

```text
You are comparing a current chest radiograph with its prior study.

Finding of interest: {finding}

The following 64 visual tokens summarize the current state and the
longitudinal visual evidence:
<vis_00> ... <vis_63>

Question:
Compared with the prior study, what is the progression of the finding?

Answer with exactly one word:
stable, worse, improved, new, or resolved.
```

Primary 三分类评分时只比较前三个适用候选。

## 12.2 VQA 模板

```text
Finding: {finding}
How has this finding changed between the prior and current studies?
Use only evidence supported by the images.
```

## 12.3 生成模板

```text
Write one concise comparative radiology sentence for {finding}.
State the progression and the supporting visual location.
Do not invent a change that is not supported.
```

---

# 13. 数据协议

## 13.1 Silver Master Cohort

当前仓库记录：

- R31 后仍有 2,383 名患者处于 sealed reserve；
- 这些患者不得与 R24–R31 active patients 重叠；
- master manifest 先包含五类，再从中派生三分类子任务。

建议新 split：

| Split | 目标患者数 | 用途 |
|---|---:|---|
| Train | 1,600 | probe、tokenizer、projector 训练 |
| Dev/Calibration | 300 | early stopping、唯一阈值冻结 |
| Sealed VLM Test | 483 | 只在 R34 首次一次性揭示 |
| Gold/External | 独立 | 最终一次性确认 |

**测试使用规则：**

- R33 Token Survival 只在 Train+Dev 上做 nested patient-disjoint OOF 评测；
- 483 名 Sealed VLM Test 患者在 R33 全程保持未读；
- R34 是第一次也是唯一一次揭示这 483 名患者；
- R34 之后若修改方法，禁止再次把同一批 483 人作为 confirmatory test；
- 后续 mutation 必须由独立 gold/external cohort 承担确认。

若 deterministic patient stratification 无法同时保持类别与来源支持：

1. 先执行纯数据支持审计；
2. 生成第一个满足预注册支持条件的 split；
3. 在任何模型运行前冻结 JSON、SHA256 和排除列表；
4. 不得根据模型结果重建 split。

## 13.2 Patient-Level Split

同一患者的：

- 所有 study pairs；
- 所有 findings；
- 所有 labels；
- 所有图像；

必须只属于一个 split。

## 13.3 Gold Quarantine

建立：

```text
gold_quarantine_manifest.json
gold_patient_ids.sha256
gold_access_log.jsonl
```

在方法、超参数和主表全部冻结前：

- 不生成 gold predictions；
- 不读取 gold metrics；
- 不根据 gold finding 支持修改模型；
- 不用 gold 做 early stopping。

## 13.4 Human-Gold / External 可用性门

目前本地只有 16 名可用且 untouched 的 gold 患者，不能承担正式统计确认。

R32 必须先解决：

1. 官方 CheXTemporal gold 的 parent images；
2. CheXpert / ReXGradient 来源图像的合法本地访问；
3. 与 R24–R31 的零 patient overlap；
4. 各类 support；
5. 最小可检测效应（MDE）和功效。

若有效 gold 患者不足，则：

- 不提前揭示；
- 将 official gold 作为 descriptive external；
- 另行获取独立专家标注；
- 不通过反复调 silver 代替 gold。

## 13.5 数据治理

必须固定：

- Hugging Face dataset revision；
- parquet SHA256；
- parent MIMIC/CheXpert/ReXGradient DUA；
- CC-BY-NC 使用边界；
- silver 用于训练的书面解释；
- 原始图像和受限数据不得随 GitHub 发布。

---

# 14. 训练流程

## Stage A：Patch Token Cache

对 prior/current 每张图只提取一次：

```text
final-layer CLS
final-layer patch tokens
image/view metadata
```

建议：

- FP16/BF16 cache；
- 每个 image feature 文件带 encoder hash；
- 逐文件 SHA256；
- 不缓存标签派生特征；
- cache 与 split 解耦。

## Stage B：Auxiliary Probe Family

使用 R31 的三种子原则训练：

```text
seed = 17, 29, 43
```

每个 probe 输入 rich multiscale token summary，输出 progression logits。

要求：

- 5-fold OOF train predictions；
- 完整 train→dev/test predictions；
- 强正则；
- 不把类别 embedding 写入视觉 Token。

## Stage C：Token Survival Probe

使用一个**共享、同容量** probe 分别读取：

```text
Robust bundle
Rich bundle
Hard-gated bundle
Random-route bundle
```

目的：

> 证明 Token 构造没有破坏 R31 的条件收益。

## Stage D：Frozen VLM Training

每个样本同时构造 robust、rich 和 selected bundle。

推荐损失：

\[
\mathcal L
=
\mathcal L_{\text{selected}}
+
0.25\mathcal L_{\text{robust}}
+
0.25\mathcal L_{\text{rich}}
\]

其中每一项均来自 frozen VLM candidate-label likelihood。

原因：

- 防止某个分支因很少被路由而没有训练；
- 保证 robust/rich standalone baseline 可公平比较；
- 不增加 VLM 参数。

初版不加入复杂多任务损失。

只有主转移通过后，才在正式消融中增加：

- temporal reversal；
- grounding；
- perturbation consistency；
- report-supervised transition distillation。

## Stage E：五分类与生成

三分类 VLM transfer 通过后：

1. 加入 New/Resolved；
2. 引入 null/presence token；
3. 使用完整五候选 likelihood；
4. 再进行 VQA 和比较句生成。

---

# 15. 建议训练超参数

## 15.1 Token Bridge / Probe

| 参数 | 冻结值 |
|---|---|
| Projection seeds | 17, 29, 43 |
| OOF folds | 5 patient-disjoint |
| Optimizer | AdamW |
| Learning rate | 1e-4 |
| Weight decay | 1e-2 |
| Max epochs | 20 |
| Early stopping | dev macro F1, patience 3 |
| Effective batch | 128 |
| Class weighting | inverse class |
| Patient weighting | inverse rows per patient |

## 15.2 Frozen VLM

| 参数 | 冻结值 |
|---|---|
| VLM | Qwen3-VL-4B-Instruct |
| VLM trainable | 0 |
| Vision backbone trainable | 0 |
| Token budget | 64 |
| Precision | BF16 |
| Optimizer | AdamW |
| Projector/resampler LR | 1e-4 |
| Weight decay | 1e-2 |
| Max epochs | 10 |
| Early stopping | dev patient-balanced macro F1, patience 2 |
| Effective batch | 32–64，依显存用 accumulation 实现 |
| Gradient clip | 1.0 |
| Seeds | 17, 29, 43 |
| Candidate labels | 3 → 5 |

任何超参数修改必须发生在 sealed test 揭示之前，并写入 protocol diff。

---

# 16. R32–R36 执行阶段

# R32：Authority、数据与工程冻结

## 目标

建立一个完全新的、零重叠的 VLM 路线，不触碰 R31 结果解释。

## 必做事项

1. 新建 `codex/r32-tier-cxr-vlm`。
2. 把 R26/R31 结果标为 immutable historical evidence。
3. 建立 2,383 reserve patient manifest。
4. 排除全部历史 active patients 和全部 gold patient IDs。
5. 完成 1,600/300/483 split。
6. 固定数据与协议 hash。
7. 完成 gold/external availability 和功效审计。
8. 验证 Qwen3-VL-4B exact-64 injection smoke。
9. 实现 vectorized five-candidate scoring，并与旧逐候选版本逐元素一致。
10. 不运行正式 test。

## R32 GO

- 零 patient/study/image overlap；
- 五类 support 达到协议最低值；
- 所有图像路径可用；
- 数据治理通过；
- 64-placeholder smoke 通过；
- VLM、vision encoder 冻结审计通过；
- gold 未揭示。

---

# R33：Token Bridge Survival

## 目标

回答：

> R31 条件收益能否在固定 64-token 表示中存活？

R33 是 **development survival gate**，仅使用 Train+Dev 的 nested OOF predictions。不得读取 483 名 Sealed VLM Test 患者。

## 系统

| ID | 系统 |
|---|---|
| P0 | Query-only |
| P1 | Current-state tokens |
| P2 | Global temporal tokens |
| P3 | Robust fixed-64 bundle |
| P4 | Always-rich fixed-64 bundle |
| P5 | Random route，coverage 匹配 |
| P6 | R31 hard-gated fixed-64 bundle |
| P7 | Oracle route，仅上界 |

## Primary 比较

\[
\Delta_{\text{R33}}
=
F1(P6)-F1(P3)
\]

## R33 GO

必须同时满足：

1. \(\Delta_{\text{R33}}\ge +2.0\) pp；
2. patient-bootstrap 95% CI 下界 > 0；
3. 三个训练 seed 的差值都 > 0；
4. P6 不比最强非 oracle baseline 低超过 1 pp；
5. prior shuffle 后收益明显下降；
6. query-only 明显低于完整图像系统；
7. Token 中不存在类别 ID、probe logits 或预测词；
8. 新进程复现 hash 一致。

## R33 STOP

若 Token bridge 无法保留 R31 信号：

- 483 名 Sealed VLM Test 继续保持未揭示；
- 停止 VLM 训练；
- 不通过换 LLM、加 LoRA 或增大模型 rescue；
- 先证明 Token 构造错误在哪里。

---

# R34：Frozen VLM Transfer

## 目标

回答：

> 同样的视觉 Token 选择原则能否提升 frozen VLM？

R34 是 483 名 Sealed VLM Test 患者的第一次正式揭示。R34 的模型、prompt、token layout、损失、seeds 和 baseline 必须在揭示前全部冻结。

## 主系统

| ID | 系统 | 视觉路径 |
|---|---|---|
| V0 | Query-only VLM | 64 个 neutral visual tokens |
| V1 | Current-image native VLM | current 原生视觉塔 |
| V2a | Raw two-image native VLM | prior+current 原生视觉塔 |
| V2b | Parameter-matched native temporal adapter | 原生视觉塔 + 等容量 adapter |
| V3 | Naive prior/current token concat | 固定 64 |
| V4 | Global-difference token VLM | 固定 64 |
| V5 | Robust/uniform token VLM | 固定 64 |
| V6 | Always-rich token VLM | 固定 64 |
| V7 | Random-route token VLM | coverage 匹配 |
| V8 | **TIER-CXR-VLM hard gate** | 固定 64 |
| V9 | Continuous stability gate | Secondary |
| V10 | Oracle route | 上界 |

## Primary 比较

\[
\Delta_{\text{VLM}}
=
F1(V8)-F1(V5)
\]

## R34 GO

1. \(\Delta_{\text{VLM}}\ge +2.0\) pp；
2. 95% patient-bootstrap CI 下界 > 0；
3. 三个 projector seed 均为正；
4. V8 不低于 V1/V2/V6 中最强者超过 1 pp；
5. random-route 不复现相同收益；
6. image shuffle / prior shuffle 控制通过；
7. VLM 参数确认为 0 trainable；
8. 无 pixel bypass；
9. 64-token 数、顺序、prompt、projector 参数量完全匹配；
10. fresh-process reproduction 通过。

## R34 NO-GO 解释

若 R33 GO 而 R34 NO-GO：

> 表示中存在可读信号，但 frozen VLM 视觉接口没有有效利用它。

此时允许研究：

- projector；
- token type；
- token order；
- continuous stability；

但不允许直接解冻整个 VLM 掩盖接口失败。

---

# R35：五分类 Human-Gold / External Confirmation

## 目标

在所有模型与阈值冻结后，一次性回答：

> TIER-CXR-VLM 是否能泛化到专家标签及外部来源？

## Primary

```text
Stable / Improved / Worse / New / Resolved
patient-balanced macro F1
```

## Key Secondary

```text
Persistent 3-class macro F1
per-class F1
balanced accuracy
NLL
ECE
```

## 来源分层

- MIMIC gold：同域；
- CheXpert gold：外部来源；
- ReXGradient gold：外部来源；
- 若某来源 support 不足，只做 descriptive，不单独宣称显著。

## Gold GO

在正式 power audit 通过后，建议预注册：

1. Overall gold \(\Delta\ge +2.0\) pp；
2. paired patient-bootstrap 95% CI 下界 > 0；
3. external source 的点估计方向为正；
4. Stable/Resolved 等弱类不出现明显灾难性下降；
5. ECE 不恶化超过 0.02；
6. 无 gold 调参；
7. 新进程完全复现。

若 official gold 功效不足，则在揭示前将其降级为 secondary，并通过独立专家标注补充 confirmatory cohort。

---

# R36：Grounding、生成与完整论文实验

## 任务

1. Finding-level progression；
2. Temporal VQA；
3. Grounded comparative sentence；
4. Five-class progression；
5. 多 backbone；
6. 外部验证；
7. 临床错误分析；
8. 计算成本。

## 最终输出

不生成完整长报告作为唯一主指标；先生成 finding-level 比较句，减少语言风格对视觉方法评价的干扰。

---

# 17. 主实验设计

## 17.1 Primary Main Table

必须在同一 split、同一 prompt、同一 VLM、同一 token budget 下比较：

1. Current-only；
2. Raw two-image VLM；
3. Naive token concat；
4. Robust token bundle；
5. Always-rich；
6. Random-route；
7. TIER hard gate；
8. Continuous TIER；
9. Oracle route。

## 17.2 强不确定性/路由基线

需要比较：

- probability average；
- logit average；
- majority vote；
- max-softmax confidence gate；
- entropy gate；
- margin gate；
- all-six majority；
- shallow learned stacking；
- random gate with matched coverage；
- deep-ensemble disagreement。

这决定 TIER 是否优于普通 ensemble heuristic。

## 17.3 Temporal 表示基线

- current-only；
- prior-only；
- simple difference；
- signed + absolute difference；
- Siamese temporal pooling；
- cross-attention；
- temporal inversion；
- directional transition；
- region-guided change token；
- raw multi-image VLM。

能否公平复现 Libra、ProTrans、GRCD 等方法，取决于其代码、权重和数据协议；无法公平复现时必须写明。

---

# 18. 核心消融

| 消融 | 回答的问题 |
|---|---|
| 去掉 Tier 0 | 是否必须保留 current-state 保底 |
| 去掉 Tier 1 | 全局时间变化的贡献 |
| 去掉 Tier 2 | query-conditioned local 的贡献 |
| 去掉 Tier 3 | soft relation 是否真正有增益 |
| relation→neutral | relation 内容而非槽位数量是否有效 |
| rich always-on | gate 是否必要 |
| robust always-on | rich 分支是否有额外信息 |
| 3/3→2/3 gate | unanimity 是否必要 |
| 三个相同投影 | 多样性而非重复投票是否有效 |
| 去掉 query | finding 条件是否必要 |
| report anatomy→fixed map | case-specific report prior 的影响 |
| 64→32/96 tokens | 性能—预算曲线 |
| 不共享 projector | 收益是否来自额外参数 |
| 解冻最后一层 ViT | 仅作为后期 robustness，不是主方法 |
| Qwen3-VL-4B→8B | 方法是否依赖模型规模 |

---

# 19. 必须通过的 Shortcut / Causal Controls

## Query-only

保留 finding/anatomy，删除图像。

目的：

> 测量 label prior shortcut。

## Current-only

删除 prior。

目的：

> 测量当前状态 shortcut。

## Prior shuffle

在相同 finding 内随机替换另一患者的 prior。

目的：

> 检验是否真正使用同一患者的时间信息。

## Time reversal

交换 prior/current，并映射：

```text
Improved ↔ Worse
New ↔ Resolved
Stable → Stable
```

目的：

> 检验方向性。

## ROI / Patch shuffle

打乱 local patch 顺序或跨患者交换局部 evidence。

## Image blank

所有视觉 Token 置 neutral，仅保留 prompt。

## Random route

保持 rich coverage 与 TIER 完全相同，但随机选择病例。

## Label permutation

仅在 train-only sanity check 中执行，正式性能应回到机会水平。

## Side swap

若有 laterality，交换左右局部 token，检测 wrong-side 敏感性。

---

# 20. 指标与统计

## 20.1 Primary 指标

```text
Patient-balanced macro F1
```

必须复用 R31 定义，避免指标漂移。

## 20.2 Secondary 指标

- per-class F1；
- balanced accuracy；
- accuracy；
- NLL；
- ECE；
- Brier score；
- route coverage；
- accepted-subset F1；
- fallback-subset F1；
- correction rate；
- harm rate；
- risk–coverage curve；
- AUROC/AUPRC（适用时）。

## 20.3 Bootstrap

- 10,000 次；
- patient-cluster bootstrap；
- 每次抽中患者时保留其全部 rows/findings；
- 计算 paired delta；
- 报告 percentile 95% CI；
- 必须 10,000/10,000 有效。

## 20.4 多重比较

- 唯一 Primary 对比不校正；
- Secondary pairwise comparisons 使用 Holm correction；
- 亚组分析标为 secondary/exploratory；
- 不根据亚组结果修改主 cohort。

## 20.5 Seed

- projector/resampler：17、29、43；
- 每个 seed 与 matched baseline 配对；
- GO 要求三个方向均正；
- 报告 mean、每 seed 和 paired CI。

---

# 21. Grounding 与生成评测

## 21.1 Grounding

若有 gold boxes/masks，报告：

- pointing accuracy；
- attention mass inside box；
- IoU@0.1 / 0.25 / 0.5；
- laterality accuracy；
- anatomy accuracy；
- prior/current grounding consistency。

## 21.2 比较句

自动指标：

- progression exact match；
- finding mention accuracy；
- anatomy/laterality accuracy；
- temporal-direction accuracy；
- unsupported-change rate；
- wrong-time rate；
- wrong-side rate；
- RadGraph F1；
- BLEU/ROUGE/CIDEr 仅作 secondary。

## 21.3 专家评价

最终稿建议抽取固定、预注册病例：

- 2 名放射科医生独立评分；
- disagreement adjudication；
- 临床正确性；
- 是否忠实于图像；
- 是否正确比较 prior/current；
- 是否存在可能误导的 temporal statement。

---

# 22. 代码实施清单

建议新增：

```text
docs/superpowers/specs/
  2026-07-26-r32-tier-cxr-vlm-protocol-v1.md

src/visualvit/
  hierarchical_temporal_tokens.py
  perturbation_consensus_router.py
  tier_token_projector.py
  tier_cxr_vlm.py
  gold_quarantine.py
  statistical_evaluation.py

scripts/
  build_r32_tier_cxr_cohort.py
  audit_r32_gold_external_support.py
  cache_r32_patch_tokens.py
  train_r33_oof_probes.py
  run_r33_token_survival.py
  run_r34_frozen_vlm_transfer.py
  run_r35_gold_external_confirmation.py
  run_r36_grounded_generation.py
  verify_r32_r36_reproduction.py

tests/
  test_hierarchical_temporal_tokens.py
  test_perturbation_consensus_router.py
  test_tier_token_projector.py
  test_tier_cxr_vlm.py
  test_gold_quarantine.py
  test_vlm_candidate_vectorization.py
  test_patient_bootstrap.py
```

---

# 23. 必须实现的单元测试

1. 每个样本恰好 64 个物理 Token。
2. robust/rich 的 Token type layout 完全一致。
3. 所有 physical attention 均为 1。
4. logical invalid slots 使用同一个 neutral embedding。
5. token 中不存在 label ID、label text、probe logits。
6. route 不读取测试标签。
7. train route 为 OOF，不是 in-sample。
8. VLM 全冻结。
9. ViT 全冻结。
10. token path 禁止 pixel/image keys。
11. prior/current swap 后时间 metadata 正确交换。
12. New/Resolved null token 语义正确。
13. patient split 零重叠。
14. gold quarantine ID 不进入 train/dev/test。
15. candidate vectorized scoring 与旧实现数值一致。
16. 10,000 bootstrap 全有效。
17. 新进程预测和结果 hash 一致。
18. 不同 seed 产生不同 perturbation，但数据 split 不变。
19. random-route coverage 与真实 gate 一致。
20. matched baseline 参数量与 Token 数一致。

---

# 24. 工程与显存策略

## 24.1 Patch Cache

单层 ViT-B/16 patch cache 的粗略存储：

\[
197\times768\times2\text{ bytes/image}
\]

约为每图 0.3 MB；数千张图的 final-layer cache 为低个位数 GB。

必须实际 dry-run 后写入 storage audit，不根据估算直接假定。

## 24.2 24GB GPU 策略

Primary：

- Qwen3-VL-4B；
- BF16；
- batch 1–4；
- gradient accumulation；
- frozen VLM；
- gradient checkpointing；
- 只训练小型 visual modules；
- patch features 离线缓存。

## 24.3 Candidate Scoring

现有五候选逐次 forward 成本较高。

建议实现：

```text
score_labels_vectorized()
```

把 5 个候选沿 batch 维展开，并验证与旧实现完全一致。

---

# 25. 允许修改阶梯

## M0：纯工程修复

允许：

- serialization；
- dtype；
- device；
- path；
- batched scoring；
- 无语义变化的内存优化。

## M1：Hard Two-Bundle Token Gate

Primary 正式方案。

## M2：Continuous Stability

只有 R33 GO 且 R34 方向正但未达门，才允许在新的 dev-only protocol 中测试。该 mutation 不得在已经揭示的 483 人上重新形成 confirmatory 结论，必须等待独立 gold/external 评测。

## M3：轻量 ViT Adapter

只有明确证明 frozen patch tokens 是瓶颈，且 gold/test 未揭示时，才建立独立新 protocol。

## 禁止

- 在同一 sealed test 上不断改 gate；
- 恢复 universal matcher；
- 把 R31 标签传给 VLM；
- 解冻整个 VLM；
- 根据 gold 选 threshold；
- 根据亚组选择最终 cohort；
- 在失败后更换主指标；
- 继续搜索任意投票规则。

---

# 26. 正式 STOP / GO 决策树

```text
R32 数据/冻结审计失败
    → STOP，先解决数据与 gold 支持

R33 Token Survival 失败
    → STOP VLM 路线，不得靠大模型掩盖

R33 GO，R34 VLM Transfer 失败
    → 说明视觉信号未被 frozen VLM 接口利用
    → 只允许 projector/token-order/continuous-stability 受控修复

R34 GO，R35 Gold 失败
    → 不允许正向临床主张
    → 论文只能讨论 silver→gold generalization gap

R34/R35 均 GO
    → 固定方法，全面跑消融、生成、外部与多 backbone

R36 完成
    → 进入 TMI/MIA 写作与投稿
```

---

# 27. 预期论文结构

## 1. Introduction

- 纵向胸片需要多粒度时间证据；
- universal complexity 并非总是有效；
- 需要条件可靠的视觉 Token 接口。

## 2. Diagnostic Findings

- R26：universal binding 未被支持；
- R29/R30：rich representation 有信息但不稳定；
- R31：perturbation consensus 可识别可靠子集。

## 3. Method

- hierarchical temporal tokens；
- robust/rich bundles；
- perturbation-consensus gate；
- fixed 64-token projector；
- frozen VLM scoring。

## 4. Experiments

- silver token survival；
- frozen VLM transfer；
- human-gold/external；
- five-class；
- grounding/generation；
- ablation/controls。

## 5. Discussion

- 为什么 binding 不是 universal；
- 为什么一致性是条件风险代理；
- silver/gold 差距；
- finding-conditioned setting；
- 临床限制。

---

# 28. Minimum Publishable Package

若目标 TMI/MIA，最低完整包应包含：

1. R31 历史证据链；
2. R33 token survival GO；
3. R34 frozen VLM transfer GO；
4. human-gold 或外部专家标签确认；
5. 五分类；
6. strong VLM/temporal baselines；
7. query-only、prior-shuffle、time-reversal 控制；
8. grounding；
9. 至少 finding-level comparative generation；
10. calibration 和 route-risk 分析；
11. 完整复现与数据治理；
12. 至少一个第二 backbone。

仅有 R31 silver 三分类，或仅把标签交给 VLM，不构成完整方法论文。

---

# 29. 最终交接指令

交给实验同学的第一条正式任务：

> **从提交 `7c4c51e` 新建 `codex/r32-tier-cxr-vlm`。冻结 R26/R31 所有历史产物；先完成 2,383 reserve patients 的零重叠五类 master split、gold quarantine、Qwen3-VL-4B exact-64 smoke 和 patch-token cache。禁止在 R33 Token Survival GO 之前运行正式 VLM 训练，禁止读取 gold outcome。**

第二条任务：

> **实现 robust/rich 两套同布局 64-token bundle，并用 5-fold OOF 三 probe 生成 hard route。R33 只验证 Token 生存，不接 VLM；只有达到 +2 pp、CI 下界大于 0、三个 seed 正向和所有 shortcut controls 后，才启动 R34。**

第三条任务：

> **R34 使用同一个 frozen Qwen3-VL、同一个 projector 参数预算和同一个 prompt 比较 robust、always-rich、random-route 与 TIER hard-gate。任何收益必须来自视觉 Token 组织，而不是 probe 标签、额外 Token、pixel bypass 或额外语言模型参数。**

---

# 30. 参考与实现依据

1. VisualVIT R31 final report  
   https://raw.githubusercontent.com/Ali-Xiyao/VisualVIT/codex/r29-case-driven-transition-repair/reports/R31_CONFIDENCE_CONSENSUS_FINAL.md

2. VisualVIT task plan  
   https://raw.githubusercontent.com/Ali-Xiyao/VisualVIT/codex/r29-case-driven-transition-repair/task_plan.md

3. VisualVIT fixed-64 projector  
   https://raw.githubusercontent.com/Ali-Xiyao/VisualVIT/codex/r29-case-driven-transition-repair/src/visualvit/projector.py

4. VisualVIT Qwen frozen adapter  
   https://raw.githubusercontent.com/Ali-Xiyao/VisualVIT/codex/r29-case-driven-transition-repair/src/visualvit/qwen_adapter.py

5. CheXTemporal  
   https://arxiv.org/abs/2605.11304  
   https://huggingface.co/datasets/anonaccount107240/CheXTemporal

6. Qwen3-VL-4B-Instruct  
   https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct

7. Libra  
   https://arxiv.org/abs/2411.19378

8. ProTrans  
   https://arxiv.org/abs/2606.15938

9. TILA  
   https://arxiv.org/abs/2604.04563

10. GRCD  
    https://arxiv.org/abs/2607.02719

11. R37 PRTA-CXR frozen protocol
    `docs/superpowers/specs/2026-07-27-r37-prta-cxr-protocol-v1.md`

12. R37 inversion failure case study
    `reports/R37_INVERSION_FAILURE_CASE_STUDY.md`

13. R37.1 two-seed fresh-holdout result
    `reports/R37_1_TWO_SEED_FRESH_HOLDOUT_RESULT.md`

14. R37.1 Chinese proposal/case-study closure
    `reports/R37_1_PROPOSAL_AND_CASE_STUDY_CLOSURE_CN.md`

---

# 31. 一句话最终版本

> **TIER-CXR-VLM 不是把一个分类器答案交给语言模型，而是在固定 64-token 预算下，根据跨扰动稳定性选择稳健或丰富的分层纵向视觉证据，并让冻结 VLM 独立完成进展推理与比较式生成。**
