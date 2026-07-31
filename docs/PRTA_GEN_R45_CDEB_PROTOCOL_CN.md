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

## 4. 预注册方法骨架

R45 的候选方法为 **Causal Delta Evidence Bottleneck (CDEB)**：

1. 复用已冻结 PRTA exact64 表示；
2. 从 `true_pair` 与 `current_only` 得到相同 finding query 下的表示；
3. 以显式 delta 特征预测五类 progression 辅助分布；
4. 把该分布映射为固定数量的 evidence tokens；
5. 只用合法五类目标训练同一两字段 compact JSON 生成任务；
6. 不加入 invalid/shuffle 第六类，不把 control 当训练标签。

必须保留的比较：

- inherited Qwen free-generation baseline；
- no-delta evidence bottleneck；
- delta auxiliary head without evidence-token bridge；
- full CDEB；
- structured delta head 作为诊断性参考，不作为自由生成主结果。

方法的精确层数、token 预算、loss 权重、Seeds、训练预算、解码、primary
endpoint、bootstrap 和 per-class gates 必须在 discovery 开始前写入第二阶段
冻结配置。discovery 只能使用 train/development；qualification 不参与任何
调参或候选选择。

## 5. 允许的最终主张

即使 R45 全部通过，也只允许主张：

> 在冻结的 CheXTemporal CheXpert silver、progression-only、patient-disjoint
> 范围内，CDEB 对正确 prior 的使用以及五类自由生成表现通过了预注册的内部
> qualification/confirmation。

不得外推到 gold、external、完整 report generation、开放问答、临床应用或
R42/R43 解锁。
