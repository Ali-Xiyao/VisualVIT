# PRTA-Gen R45 CDEB 预注册协议

## 1. 研究问题

R44A 的 identity-free case study 显示：Qwen 自由生成在很多样本上对正确
prior 与 same-finding shuffled prior 给出相同类别，而且少量变化高度依赖
Seed。这支持一个新的、可证伪的问题：

> 若把 `true_pair - current_only` 的因果时间差显式压缩成一个固定预算的
> progression evidence block，再交给冻结的 Qwen 生成器，能否在全新患者上
> 同时提高五分类正确率和 correct-prior sensitivity？

该问题不把 Qwen 重新定义为 LLM，也不改写 R41A/R44A 的 STOP。R45 是一个
独立命名、独立 roster、独立 gate 的 cross-source silver 研究。

## 2. 数据冻结与四段 roster

冻结配置：
`configs/prta_gen/prta_gen_r45_cdeb_roster_v1.json`。

来源仍为固定 revision 的 CheXTemporal CheXpert silver finding rows，并且：

- 排除全部 77 个已登记 gold patients；
- 排除 R44A train/development 的全部 1,250 patients；
- 只保留 parent/current 两张图均存在的行；
- 每位患者只取一行；
- 使用 rare-class-first、稳定 SHA-256、无放回分配；
- 分配顺序固定为 confirmation、qualification、
  discovery-development、discovery-train。

冻结规模：

| partition | 每类患者 | 总患者 | 允许用途 |
|---|---:|---:|---|
| discovery-train | 500 | 2,500 | 训练 |
| discovery-development | 100 | 500 | 工程选择与一次候选选择 |
| sealed qualification | 100 | 500 | 方法完全冻结后只读一次 |
| sealed confirmation | 50 | 250 | qualification 全 gate 通过后只读一次 |

分配后必须至少保留 200 个未使用 Resolved patients。任何容量、图像完整性、
历史排除、partition 互斥或哈希检查失败都立即 STOP，禁止重分割。

## 3. 封存边界

当前阶段只允许构建 roster。qualification 和 confirmation 的标签虽存在于
受控 runtime roster 中，但模型代码、超参数、候选选择规则和 gate 完全提交并
推送之前，任何 runner 都不得读取这两个 partition。

明示防火墙：

- `qualification_outcomes_read=false`
- `confirmation_outcomes_read=false`
- `gold_outcomes_read=false`
- `external_outcomes_read=false`
- `scientific_claim_allowed=false`

## 4. 冻结方法

R45 的候选方法为 **Causal Delta Evidence Bottleneck (CDEB)**：

完整 discovery authority：
`configs/prta_gen/prta_gen_r45_cdeb_discovery_v1.json`。

1. 复用已冻结 PRTA exact64 表示；
2. 分别对 positions `[0,4)`, `[4,16)`, `[16,32)`, `[32,48)`,
   `[48,60)` 做 region mean，拼成 3,840 维特征；
3. delta 为 `semantic_mean(true_pair) -
   semantic_mean(current_only)`，只用 discovery-train 拟合 mean/std；
4. 一个 hidden-width 128 的五分类 head 产生 softmax distribution；
5. hidden-width 128 的 bridge 将五类分布映射成四个 2,560 维 evidence
   embeddings；
6. 只替换 Tier projector 之后原本 neutral 的 positions 60-63，positions
   0-59 保持不变，仍恰好注入 64 个 physical tokens；
7. Qwen3-VL-4B-Instruct base 完全冻结，不用 LoRA；训练 Tier projector、
   注册的 decision head 和需要时的 bridge；
8. 总 loss 为 `1.0 * assistant-only SFT + 0.5 * auxiliary five-class CE`；
9. 不加入 invalid/shuffle 第六类，不把 control 当训练标签。

必须保留的比较：

- `baseline_projector`：冻结 Qwen，只训练 Tier projector；
- `no_delta_evidence`：用 true-pair means，不做 current subtraction；
- `delta_no_bridge`：训练 delta auxiliary head，但 reserve block 保持 neutral；
- `full_cdeb`：delta head 与四-token bridge 全部启用；
- structured delta head 作为诊断性参考，不作为自由生成主结果。

Discovery 只用 Seed 17；每个方法一轮 2,500 training rows，batch size 1，
gradient accumulation 32，固定 79 optimizer updates。projector learning rate
为 `1e-4`，CDEB learning rate 为 `1e-3`，AdamW weight decay `0.01`，
gradient clip `1.0`，无 early stopping、无 checkpoint selection。解码为 free
greedy；同一 500-patient development 上固定评估 true pair、current-only、
query-only、same-finding cross-patient prior shuffle。

## 5. Discovery gate

唯一可选方法预先指定为 `full_cdeb`。只有以下全部通过才能 materialize
qualification tokens：

- true-pair macro-F1 ≥ 0.30；
- 五类 recall 各 ≥ 0.12；
- schema validity 与 finding echo 各 ≥ 0.99；
- true-pair 相对 prior-shuffle macro-F1 增益 ≥ 1 pp；
- full CDEB 相对同 roster projector baseline 增益 ≥ 1 pp；
- full CDEB 不低于 no-delta evidence；
- auxiliary true-pair macro-F1 ≥ 0.35；
- true/shuffle 预测相同率 ≤ 0.75。

Bootstrap 固定 2,000 次、Seed 45002；discovery CI 作为描述值，qualification
才要求 effect 与 pooled CI 同时过 gate。Discovery 任一 gate 失败即
`STOP_PRTA_GEN_R45_CDEB_DISCOVERY`，不得针对该 development 调阈值、改
loss 或重分割。

## 6. 已冻结 qualification / confirmation gate

若 discovery GO，qualification 只运行 `baseline_projector` 与
`full_cdeb`，Seeds 17/29/43，仍用相同训练预算与四个 evaluation arms。
每个 Seed 的 full CDEB 必须满足 macro-F1 ≥ 0.30、各类 recall ≥ 0.12、
schema/finding ≥ 0.99、相对 prior-shuffle ≥ 2 pp、相对 baseline ≥ 2 pp；
两项 paired patient-cluster bootstrap pooled CI95 lower 均必须严格大于
0 pp。

只有 qualification 全部通过才读取 250-patient confirmation。Confirmation
沿用完全相同的两方法、三 Seeds 和 gate；失败为 R45 terminal STOP，禁止围绕
结果调参。

## 7. 允许的最终主张

即使 R45 全部通过，也只允许主张：

> 在冻结的 CheXTemporal CheXpert silver、progression-only、patient-disjoint
> 范围内，CDEB 对正确 prior 的使用以及五类自由生成表现通过了预注册的内部
> qualification/confirmation。

不得外推到 gold、external、完整 report generation、开放问答、临床应用或
R42/R43 解锁。
