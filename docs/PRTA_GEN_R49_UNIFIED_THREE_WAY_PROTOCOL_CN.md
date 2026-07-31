# PRTA-Gen R49 统一三系统归因协议

## 要回答的问题

R48 已显示 frozen PRTA token generator 在内部 750 人 pooled 分析中具有
correct-prior responsiveness，也显示 Raw two-image Qwen 在 qualification
500 人上明显较弱，但这两项旧结果不能单独回答增益是否来自跨时间对齐。
R49 因此只回答两个配对问题：

1. PRTA exact-64 是否优于直接读取 prior/current 两张完整胸片的 frozen
   Qwen3-VL；
2. PRTA exact-64 是否优于相同 64-token 预算、相同 projector 容量和训练
   预算的简单 prior/current token 拼接。

## 三个系统

| 系统 | 输入 | 可训练部分 |
|---|---|---|
| Raw two-image Qwen | prior、current 两张完整 JPEG，顺序固定 | 无；Qwen 全冻结 |
| Naive exact-64 | 30 prior Block-8 patch token + 30 current token + 4 个零 | 共享容量 projector |
| PRTA exact-64 | finding-guided、跨时间对齐的 60 个有效 token + 4 个零 | 同容量 projector |

Naive 的 30 个位置在任何 R49 outcome 或训练结果产生前固定为：
`round(i*195/29)+1, i=0..29`，即在 14x14 非 CLS patch 网格的展平顺序中
等距取样。顺序固定为 prior 30、current 30、zero 4；禁止 routing、额外
token、标签 token 或 pixel bypass。

## 公平性合同

- frozen roster：train 2,500 人；evaluation 为 qualification 500 与
  confirmation 250 的固定并集，共 750 人；每人一行，train/evaluation
  patient-disjoint；
- frozen model：同一本地 `Qwen3-VL-4B-Instruct`；
- exact-64 两臂：Seed 17，同一 projector 架构与初始化哈希，同一训练行
  顺序哈希，同一 AdamW、LR 1e-4、weight decay 0.01、1 epoch、accumulation
  32、79 updates；
- 输出：相同 system prompt、相同 finding-conditioned 两字段 JSON 任务、
  相同五类 progression registry、greedy generation 和 64-token 最大输出；
- 只允许 modality wrapper 不同：Raw 必须序列化两张图片，exact-64 必须
  序列化 64 个 placeholder。因此“相同 prompt”严格解释为相同语义任务与
  输出合同，不虚假声称完整 multimodal token 序列逐字节相同；
- Raw 的原生视觉 token/算力不与 exact-64 相等，必须单独报告；Naive 与
  PRTA 才是严格同 64-token 预算对照。

## 统计与判定

主指标为 750 人 macro-F1。固定做 2,000 次 patient-cluster paired
bootstrap：

- `PRTA exact-64 - Raw two-image Qwen`；
- `PRTA exact-64 - Naive exact-64`。

只有点差大于零且 95% CI 下界大于零，才写“支持 PRTA 更优”。第二个对比
同时决定是否支持“增益来自跨时间对齐而非仅仅有 64 个视觉 token”。无论
正负都必须保留结果；不得根据 R49 outcome 改位置、prompt、训练预算、Seed、
阈值或 evaluation cohort。

## 解释边界

R49 是同一内部 silver 数据源上的 post-hoc attribution case study，不是
独立 gold/external confirmation，也不解锁临床效用、开放式报告、R42/R43
或 ICLR 接收主张。它可以增强或削弱“跨时间对齐贡献”的内部机制证据，但
不能覆盖 R48 confirmation 的 split-specific STOP。

机器可执行权威：
`configs/prta_gen/prta_gen_r49_unified_three_way_v1.json`。
