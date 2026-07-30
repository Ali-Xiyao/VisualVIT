# PRTA-Gen R40B 生成过拟合烟雾测试冻结协议

## 直接结论

R40A.2 已在 fresh discovery2 和此前封存的 qualification 上同时达到
`GO`，因此只解锁 progression-only 的 R40B 工程烟雾测试。laterality、
anatomy、degree、evidence、R41、R42 和 R43 仍然锁定。

机器权威为
`configs/prta_gen/prta_gen_r40b_overfit_smoke_v1.json`。

## 32 行边界

- 只从 R40A.2 的 `fit` patient partition 取行；
- 用 `sha256(namespace|example_id)` 固定顺序；
- 每位 patient 最多一行；
- Stable/Improved/Worse/New/Resolved 固定为 7/7/6/6/6 行；
- 只读取既有 training target 和 outcome-independent exact-64 token cache；
- 不读取 300-dev、revealed 483、gold 或 external。

输出只能是：

```json
{"finding":"Lung Opacity","progression":"New"}
```

两个 key 必须恰好为 `finding`、`progression`，所有未解锁字段必须省略。

## 模型与训练边界

- Qwen3-VL-4B-Instruct 本地权重从原始 checkpoint 初始化；
- projector 每个 attempt 都 fresh 初始化，不复用 R39 的 300-dev projector；
- 只训练 `TierTokenProjector` 与 language attention
  `q_proj/k_proj/v_proj/o_proj` LoRA；
- exact-64、assistant-only、no-pixel、首步 cache 一致性和可训练参数名均
  fail closed；
- 第一 attempt 严格复现原 R40 注册的 3 epochs；
- 若且仅若上一 attempt 是纯 underfit、而不是契约错误，才按提前冻结的
  12-epoch、24-epoch 顺序继续；
- 任何 attempt 通过后立即停止，不选择最好看的结果。

## PASS

工程 PASS 同时要求：

1. final/initial teacher-forced loss 不高于 0.90；
2. teacher-forced token accuracy 不低于 95%；
3. 32/32 greedy generation 均为合法的两字段 JSON；
4. finding copy 与 progression 全部正确；
5. exact-64、mask、attention、cache、trainable boundary 与 no-pixel 全部通过。

R40B PASS 只证明当前 progression-only 生成通路可训练并可过拟合这 32
行，不是泛化结果或论文科学结论。
