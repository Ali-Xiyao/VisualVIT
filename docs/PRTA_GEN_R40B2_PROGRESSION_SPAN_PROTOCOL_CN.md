# PRTA-Gen R40B.2 Progression Span 冻结协议

## R40B.1 为什么仍失败

R40B.1 在第二批新患者上达到 99.14% uniform teacher-forced token
accuracy，但 progression 仅 28/32。每行约 14-15 个 assistant tokens 中，
绝大多数是共同 JSON 语法或从 prompt 复制的 finding；真正决定语义的
progression value 只占少量 token。统一 CE 与完整 JSON 平均似然会稀释
这部分监督。

## 唯一新尝试

R40B.2 在第三批 32 位患者上：

- 排除 R40B 和 R40B.1 共 64 位已观察患者；
- 保持 exact-64、Qwen、projector、attention-only LoRA、assistant-only
  suffix 和两字段 JSON 不变；
- progression value token 的 loss 权重冻结为 20，其余 assistant token
  权重为 1；
- 推理时仍只允许五个 progression 值，但候选分数只累计 progression
  value span 的条件 log-likelihood；
- 只运行一个 fresh 24-epoch attempt，不继承任何旧权重。

## PASS

除原 exact-64、mask、cache、trainable、no-pixel、loss 与总体 token gate
外，还要求：

- progression value teacher-forced token accuracy = 100%；
- 第三批 cohort 的 structured progression = 32/32；
- schema 与 finding = 32/32。

失败后不得继续在这第三批患者上改权重或解码规则。PASS 仍只表示
progression-only 32-row engineering smoke 跑通，不是泛化结论。
