# PRTA-Gen R40B.3 Direct Progression Class 冻结协议

## 新诊断

R40B.2 证明固定 20 倍 progression token 权重并不能稳定解决问题。Qwen
对五个 progression 值的第一个 token 却天然互异：

- Stable -> 623；
- Improved -> 81110；
- Worse -> 54；
- New -> 3564；
- Resolved -> 65394。

因此无需让共同 JSON token 间接承载五分类目标。

## 一次性新路线

R40B.3 使用第四批 32 位 fit 患者，并排除前三批共 96 位患者。每行训练
同时包含：

1. 权重 0.25 的完整 assistant-only JSON SFT；
2. 权重 1.0 的五分类 CE，位置是合法 JSON prefix 后的第一个
   progression token。

推理直接比较这五个注册 token 的 logits，选中 class 后确定性写出完整
合法 progression 值和两字段 JSON。模型、exact-64、projector、
attention-only LoRA、no-pixel、cache 和其他 firewall 不变。

只运行一个 fresh 24-epoch attempt，不继承旧权重。PASS 要求总体
teacher-forced token accuracy >=95%，且 direct structured
progression/schema/finding 全部 32/32。失败后不得继续使用第四批 cohort
调参。
