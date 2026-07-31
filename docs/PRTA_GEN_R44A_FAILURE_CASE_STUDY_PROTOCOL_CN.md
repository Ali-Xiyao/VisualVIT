# PRTA-Gen R44A Identity-Free Failure Case Study 冻结协议

状态：`FROZEN_PRTA_GEN_R44A_FAILURE_CASE_STUDY`

日期：2026-07-31

## 目的与边界

本分析只解释已经终止的
`STOP_PRTA_GEN_R44A_CROSS_SOURCE_SILVER_SFT_SURVIVAL`，不修改该结论，
不启动训练，不选择模型/Seed/checkpoint/threshold，也不把 R44A 的 250 名
development 患者用于后续候选选择。

允许读取：

- R44A 冻结 roster；
- 六个已完成 arm 的 aligned targets 与四组 class-index predictions；
- 已记录的 scalar metrics 和 firewall fields。

禁止读取或输出：

- patient/example identity；
- 图像、token、checkpoint tensor 或报告文本；
- protected 300-development、revealed 483-test、gold 或 external outcome；
- R42/R43 数据或结果。

## 不可变输入

Runtime root：

`H:\VisualVIT_runtime\050_routeD\r37_prta_cxr\prta_gen_r44a_cross_source_silver_sft_v1`

| 输入 | SHA-256 |
|---|---|
| `roster.json` | `60FE40D3483B85C9B462D69BF631D82DE68620BA722606862D263F095271C292` |
| `seed_17/g0_projector_only/result.json` | `E4087514C9EDDBF422D2D991006E4E508EAEC30488037D44495734BEA31BCAE5` |
| `seed_17/g1_attention_lora/result.json` | `7BC865CC7AC31E17DCFA4052BC8A60BEF5779424BA3BD9FB0E3140677D876B96` |
| `seed_29/g0_projector_only/result.json` | `D5D6DB0EDD59ACE7620EAEE7366DDE5272153A5BFFC00D5B88D9A29A5869C0C9` |
| `seed_29/g1_attention_lora/result.json` | `695EBA66F10D9AFC2827D4AE60ADF2B286EE21413C46B19B1AA8277E283C83BA` |
| `seed_43/g0_projector_only/result.json` | `A6C2455A340BAE47A68315833E44F3356FE8428189537F49E1C506D34A098C4F` |
| `seed_43/g1_attention_lora/result.json` | `432484A45C210F5BDA98832B10C2C2C75E5B271BE5C6C4179501504A886579B4` |

任何 hash、schema、row alignment、metric recomputation 或 firewall drift
均使分析 fail closed。

## 预先声明的分析

### 1. Correct-prior sensitivity

逐 Seed 比较 G1 `true_pair` 与 `prior_shuffle`：

- same/changed prediction rows 与比例；
- true-only correct 与 shuffle-only correct；
- net true-sensitive rows；
- 按 progression class 和 finding 分组；
- 跨三个 Seed 每个样本发生 0/1/2/3 次 prediction change 的分布。

同时描述 `current_only` 与 `query_only`，但 hypothesis selection 以
prior-shuffle 为核心。

### 2. G0→G1 迁移

逐 Seed 统计：

- both correct；
- G1 recovery；
- G1 regression；
- both wrong with same/different prediction；
- net G1 rows；
- progression/finding 分组。

### 3. 类别与跨 Seed 稳定性

- 每 Seed 的完整 confusion 与 prediction distribution；
- G1 true-pair unanimous correct、unanimous same-wrong、mixed；
- `Worse` 与其他四类分开报告，判断问题是否只是单一类别发射崩塌。

### 4. 匿名案例

每个预注册 pattern 最多四个 deterministic row-order case，只输出：

- `CASE-nnn`；
- finding；
- target class；
- Seed/arm/control 的 class-name prediction；
- descriptive-only/reuse-for-selection=false。

不得输出原始 row index、patient ID、example ID 或可逆 hash。

## 机制判别规则

- 若 true/shuffle 高度一致且跨多个类别/Seed 存在，支持
  **correct-prior under-use**；
- 若错误主要局限在单一 target class，而其他类具有稳定正
  true-vs-shuffle sensitivity，支持 **class-emission bottleneck**；
- 若 G1 recovery 与 regression 随 Seed 改变且净迁移不稳定，支持
  **adapter optimization instability**；
- 多种机制可以同时成立。该分析不能证明因果，只能为新的、独立冻结的
  R45 hypothesis 提供方向。

## 输出与后续

输出 schema：
`visualvit.prta-gen.r44a-failure-case-study.v1`

输出状态：
`DESCRIPTIVE_PRTA_GEN_R44A_FAILURE_CASE_STUDY`

只有在本协议、分析器和测试提交并推送后，才允许对六个 row-level prediction
payload 执行一次分析。任何 R45 实验都必须另立数据分区、方法和 gate；
不得直接把本 case study 当作 R44A retry。
