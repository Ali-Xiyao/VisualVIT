# PRTA-Gen R52 统一 exact-64 直接分类头预注册协议

## 要回答的问题

R52 只回答一个受限问题：在同一批 2,500 名训练患者、500 名新鲜评估患者、
相同 64-token 物理预算和完全相同直接分类头下，PRTA 表征是否优于 TILA 与
B2 表征。

本实验不使用 Qwen，也不回答自由生成、临床有效性、gold 或外部泛化问题。
TILA 是官方预训练表征经本项目 exact-64 接口适配；B2 是本项目实现的经典
Siamese signed/absolute 控制，不是一个可直接下载的完整命名系统。

## 统一接口

- 数据：沿用冻结的 R51 2,500-train / 500-evaluation 患者，患者互斥、每类
  progression 各 100 个评估病例，不重新划分。
- 输入：三种方法都只使用各自已冻结、无标签的 `[64,768]` cache；位置
  0–59 为有效 token，60–63 必须保持精确零且不进入分类头。
- 特征：统一把 60 个有效位置展平为 46,080 维。禁止使用 PRTA 专属的
  五段语义池化，因为 TILA 的位置表示空间 patch、B2 的位置表示
  prior/current/signed/absolute 分组，套用 PRTA 分段会造成结构性偏置。
- 分类头：三者逐字节共享 `LayerNorm(46080) -> Linear(46080,128) -> GELU
  -> Linear(128,5)`，总计 5,991,173 个可训练参数；没有方法专属可训练适配器。
- 标准化：每个方法只以其训练分区估计逐维 mean/std，std 下限 `1e-6`；
  评估数据不参与拟合。
- 优化：Seed 17/29/43，100 epochs，batch 128，AdamW，学习率 `1e-3`，
  weight decay 0，gradient clip 1.0；每臂固定 2,000 updates。相同 seed 的
  初始化和 minibatch 顺序必须一致。
- 禁止 early stopping、checkpoint selection、阈值调参、seed 选择与结果后
  改协议。

## 统计与判据

主指标为 500 名相同患者上的 Macro-F1，次指标为 accuracy 和逐类 recall。
对三个 seed 的预测进行 2,000 次患者配对 bootstrap，报告：

- PRTA − TILA；
- PRTA − B2；
- TILA − B2（描述性）。

只有当 `PRTA−TILA` 与 `PRTA−B2` 的 95% CI 下界都严格大于 0，才判定
`prta_strict_superiority_supported=true`。点估计领先但 CI 跨 0 不得写成
“严格优于”。

## 预注册边界

这个假设由已经观察到的 R40C 与 R50 结果推动；R52 冻结前，R51 的
PRTA-Qwen Seed 17/29 结果也已出现。因此 R52 不能声称全局 outcome-blind。
但在本文件、JSON authority、runner、聚合器和测试提交发布时，尚无任何
R52 直接分类预测或结果，且后续不得基于 R52 结果改变方法、患者、训练预算
或 seed。

机器 authority：
`configs/prta_gen/prta_gen_r52_matched_direct_head_v1.json`。
