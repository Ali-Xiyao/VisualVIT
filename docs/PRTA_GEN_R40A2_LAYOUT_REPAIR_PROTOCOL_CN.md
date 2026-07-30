# PRTA-Gen R40A.2 Token Layout 修复冻结协议

## 直接结论

R40A.1 的两个候选均因 prior-shuffle control 失败而关闭，qualification
仍未读取。关闭后进行的源代码审计发现，失败 probe 使用的 20/20/20 分区
与真实 exact-64 layout 不一致：

```text
query 4
state 12
global transition 16
local transition 16
relation context 12
reserve 4
```

20/20/20 会把 query 与 state 混合，并切开 global/local transition。
R40A.2 只修复这个语义边界，不改变 PRTA、token 数、训练预算、Seed 或 gate。

机器权威：
`configs/prta_gen/prta_gen_r40a2_layout_repair_v1.json`

## 新数据边界

- 原 R40A.1 qualification 1,500 patients 原样保留，继续 one-shot sealed；
- 已观察的 R40A.1 discovery 1,500 patients 完全排除；
- 只对原 fit 5,787 patients 使用新 namespace 排序；
- 前 1,500 作为 discovery2；
- 剩余 4,287 作为 fit2；
- 不允许重分。

## 候选顺序

1. `semantic_layout_means_v1`：严格对五个非 reserve token type 分别取均值；
2. `semantic_layout_moments_v1`：在相同五个边界内取 mean/std/max。

第一个候选如果任一 Seed 对 query-only 或 prior-shuffle 小于 +2 pp，
立即 STOP 并进入下一个候选。只有三个 Seed 点门全部通过，才运行 2,000 次
patient-cluster bootstrap。

## Qualification 与生成

discovery2 第一个 GO 候选将唯一冻结，并在原 qualification 上评价一次。
qualification GO 才能解锁 progression-only R40B 32-row overfit smoke。
laterality、anatomy、degree、evidence 与 R41/R42/R43 继续锁定。
