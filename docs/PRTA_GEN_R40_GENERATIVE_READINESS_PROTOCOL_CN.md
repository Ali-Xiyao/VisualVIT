# PRTA-Gen R40 生成就绪冻结协议

## 直接结论

R39 已证明冻结 Qwen 能从 PRTA exact-64 token 中读出五分类 progression，
但没有证明这些 token 足以支持位置、程度或视觉证据生成。PRTA-Gen 因而不能
直接进入自由文本 LoRA 训练；必须先完成 R40A 信息充分性审计和 R40B
生成适配器工程门槛。

机器可读权威为
`configs/prta_gen/prta_gen_r40_readiness_v1.json`。本协议不改写或恢复已经
暂停的 `configs/r40/r40_component_and_baseline_v1.json`，两者是不同实验
命名空间。

## 数据与保护边界

- 仅复用 R37.1 training 患者产生的 outcome-independent R40 roster；
- 已揭示的 483-test 只保留历史描述角色，不能选择任何 PRTA-Gen 设置；
- sealed gold/external 在 R40 全程不读取；
- 不使用已观察的 R37.1 validation；
- 不重算不变的 source、shard 或 checkpoint hash；
- R40 只允许工程与 development 结论，不形成新的 confirmatory claim。

## R40A：Exact-64 信息充分性

冻结 PRTA 和 exact-64 布局，分别审计：

1. progression；
2. laterality；
3. coarse anatomy；
4. degree；
5. 原始动态比较句检索。

分类 probe 只读取三组固定特征：0–19 state token 均值、20–39
transition token 均值、40–59 relation token 均值。60–63 reserved token
保持无效，不改变 R38/R39 布局。

所有细粒度标签只能从原始比较句的显式词面得到。禁止：

- 根据 finding 名补位置；
- 用 LLM 补 laterality、anatomy、degree 或 evidence；
- 在冲突标签中挑一个看起来合理的值；
- 支持不足后换 split 或换 Seed。

缺失或冲突统一记为 `Unspecified`。任一显式类别训练少于 100 行或
development 少于 30 行时，该字段标记为不可用，而不是合并或推断。
生成字段只有在 true-pair probe 明确优于 query-only 与 prior-shuffle
控制后才解锁；evidence 还必须通过原句检索控制。

## R40B：GenerativeVLMAdapter

R40B 保持 BiomedCLIP、PRTA、alignment、exact-64、Qwen vision tower、
Qwen base、embedding 与 LM head 冻结，只训练：

- `TierTokenProjector`；
- Qwen language attention 的 `q_proj/k_proj/v_proj/o_proj` LoRA。

适配器必须提供：

```python
forward_sft(...)
score_sequence(...)
generate_text(...)
```

并通过以下 fail-closed 门槛：

1. 每行恰好替换 64 个 placeholder；
2. system、user、视觉位置和 padding 的 label 全为 `-100`；
3. 监督 token 是 attended 序列的连续 assistant 后缀；
4. 推理只在首步注入视觉 embedding，禁止 pixel/image/video 旁路；
5. cached 与 uncached 首步 logits 一致；
6. 只有 projector 和 LoRA 参数可训练；
7. 32 行开始、最多 64 行的小样本 smoke 能过拟合；
8. 结构化输出 schema validity 为 100%。

R40B 不加入 G-CMCP 或时间反演，也不改 token layout。它们属于 R42，
只有 R40A/R40B 与后续 R41 结构化生成通过后才能解锁。

## 第一版输出边界

目标构造分三档：

- Tier A：有真实动态句和显式细粒度字段，可监督结构化字段与原句；
- Tier B：有显式结构化字段但不满足 evidence 条件，只监督已观察字段；
- Tier C：只有 finding 与 progression，只做 progression QA。

任何未被 R40A 解锁的字段都必须从输出 schema 中省略，不能输出
`Unspecified` 后再让语言模型在 summary 中猜测具体内容。

## 停止条件

- 数据 STOP：显式标签支持不足或来源/患者防火墙漂移；
- 工程 STOP：exact-64、mask、cache、梯度或 no-pixel 契约失败；
- R40 PASS：只表示允许准备 R41，不代表 R41/R42/R43 已执行；
- 未单独冻结 R41 前，不启动正式 LoRA SFT；
- 未冻结全部生成设置前，不读取 gold/external。
