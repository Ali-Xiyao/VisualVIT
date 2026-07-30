# PRTA-Gen R40B.1 约束式结构化生成冻结协议

## 为什么不是继续加 epoch

R40B 的 3/12/24-epoch free-greedy 梯子已全部执行。最终 attempt 的
teacher-forced token accuracy 为 99.35%，32/32 输出都是合法 JSON 且
finding 全部正确，但 progression 仍为 29/32。继续在同一 32 行上增加
epoch 属于事后调参，因此禁止。

## 新机制与新边界

R40B.1 保持 exact-64、projector、attention-only LoRA、assistant-only
训练和两字段目标不变，只替换诊断所指向的解码机制：

1. 为当前 finding 构造五个完整合法 JSON；
2. 用既有 `GenerativeVLMAdapter.score_sequence` 计算每个候选的平均
   token log-likelihood；
3. 选择分数最高者；
4. 平分时按冻结 progression 顺序裁决。

新 cohort 仍从 R40A.2 fit partition 取 32 位不同患者，但必须排除旧
R40B 的全部 32 位患者。旧 cohort 只用于形成失败诊断，不参与 R40B.1
PASS。

## 一次性门

- 只运行一个 fresh 24-epoch attempt；
- 不继承旧 projector/LoRA；
- teacher-forced loss ratio <= 0.90、token accuracy >= 95%；
- exact-64、mask、cache、trainable boundary、no-pixel 全过；
- 五候选约束输出必须 32/32 schema、finding、progression 全正确；
- 失败后不得在这个新 cohort 上继续调参。

PASS 只代表 progression-only 工程通路在 32 行上跑通，不是泛化或
论文科学结论。
