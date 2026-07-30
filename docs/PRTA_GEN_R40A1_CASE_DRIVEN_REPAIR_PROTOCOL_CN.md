# PRTA-Gen R40A.1 案例驱动修复冻结协议

## 结论先行

R40A 的 `STOP_PRTA_GEN_R40A_INFORMATION_SUFFICIENCY` 保持关闭且不可覆盖。
R40A.1 是一个新命名空间，只检验一个案例驱动的假设：

> 失败可能来自把 exact-64 序列压成三个均值，而不是 60 个有效 token
> 完全没有 progression 信息。

机器权威为
`configs/prta_gen/prta_gen_r40a1_case_repair_v1.json`。本协议只允许
progression-first 修复；laterality、anatomy、degree 和 evidence 继续锁定。

## 案例证据

旧 development 的 5,814 行只作描述：

- Seed 17：917 true-sensitive、623 shuffle-favored、2,298 both-correct、
  1,976 both-wrong；
- 只有 148 行在三个 Seed 都是 true-sensitive，939 行三个 Seed 都错；
- Stable/New 的净 prior sensitivity 为正，但 Improved/Worse/Resolved 为负；
- true-sensitive 行的 transition token RMS 明显大于 shuffle-favored 行；
- 四个 reserve token 的 true/shuffle RMS 恒为零。

这些结果允许提出“保留区间内统计和位置”的假设，但禁止直接用旧行选择
候选、阈值、Seed 或 checkpoint。

## 新患者边界

只从旧 R40A training roster 的 8,787 个患者按
`sha256(namespace|patient_id)` 排序，一次性分为：

1. qualification：前 1,500，任何候选选择期间不读 route outcome；
2. discovery：接下来 1,500，只用于按预注册顺序判断候选；
3. fit：剩余 5,787。

三个集合必须 patient-disjoint。任何 progression 类别低于冻结支持阈值时
直接 STOP，不允许重分。

## 候选顺序

候选只能按下列顺序运行；第一个通过 discovery gate 的候选被唯一选中：

1. `regional_moments_v1`：对 state/transition/relation 各取
   mean、population std、channelwise max，宽度 6,912；
2. `regional_cosine4_v1`：每个 20-token 区域使用固定正交 DCT-II 前四
   分量，宽度 9,216。

两者都保持原 exact-64 token、冻结 PRTA、单线性 readout 和相同训练预算。
它们不增加图像、backbone、路由标签或 VLM 参数。

## Discovery 与 qualification 门

每个候选运行 Seeds 17/29/43，并与 query-only、prior-shuffle 比较；
current-only 仅作诊断。通过条件为：

- 每个 Seed、每个必需 control 的点效应至少 +2 pp；
- 2,000 次 patient-cluster bootstrap 的 95% CI 下界大于零；
- 所有防火墙为 false。

qualification 只对 discovery 中第一个 PASS 候选执行一次，不能根据
qualification 结果换候选。只有 qualification GO 才能解锁 progression-only
的 R40B 32-row overfit smoke。

## 生成边界

R40B 第一版 schema 只能包含：

```text
finding
progression
```

未解锁字段必须完全省略。R40B smoke 只验证 exact-64、assistant-only
causal loss、no-pixel、projector/LoRA 梯度和小样本可过拟合，不构成
R41 正式生成结果。
