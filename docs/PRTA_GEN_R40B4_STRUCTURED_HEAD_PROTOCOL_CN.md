# PRTA-Gen R40B.4 Structured Decision Head 冻结协议

## 架构结论

四批互不重叠的 32-patient case study 一致表明：Qwen projector +
attention-LoRA 能稳定学习 JSON 形式，但小样本 progression 语义判别不稳定。
继续调 causal-LM loss、学习率或解码规则不再合理。

R40B.4 将语义决策和语言表面分开：

- 复用已由 R40A.2 discovery + sealed qualification 证明有效的
  `4/12/16/16/12` semantic-layout mean features；
- 用固定 499,973 参数的 `ProgressionDecisionHead` 做五分类；
- 选中 progression 后确定性输出恰好两个 JSON 字段；
- Qwen free generation、其他字段与 R41/R42/R43 继续锁定。

## 第五批 cohort

新 cohort 从 R40A.2 fit partition 固定 32 位患者，排除前四批共 128 位
患者，类别仍为 7/7/6/6/6。只做 engineering overfit，不形成泛化结论。

## 一次性 PASS

head fresh 初始化，full-batch AdamW 运行固定 2,000 epochs，不早停、不选
checkpoint。PASS 同时要求：

- 参数数恰为 499,973；
- final/initial loss <= 0.05；
- progression、schema、finding 均为 32/32；
- exact64 token cache 无 labels/sentences；
- 300-dev、483、gold、external、pixel 与旧 cohort 全部不参与 gate。

本 PASS 代表当前 proposal 的 progression-only **结构化生成** 工程路径跑通；
不代表 Qwen 自由文本生成跑通，也不解锁论文科学结论。
