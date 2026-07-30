# PRTA-Gen R41A–R43 自动执行冻结协议

日期：2026-07-30

状态：`TERMINAL_STOP_AT_R41A`

## 直接结论

R40C 已证明 progression-only structured head 在既有 R40A.2 fit 域内具有
patient-disjoint internal development generalization，但没有证明 Qwen 自由生成。
用户已授权使用两张本地 RTX 3090，并要求 R41 之后自动继续。因此本协议在读取
任何新 outcome 前冻结唯一执行顺序：

```text
R41A progression-only Qwen SFT survival
→ 若 GO：R42A G-CMCP + time-reversal survival
→ 若 GO：R43 confirmatory readiness
→ 第一处 STOP 即终态
```

实际执行在 R41A 返回
`STOP_PRTA_GEN_R41A_PROGRESSION_SFT_SURVIVAL`，共有 8 个冻结门失败。
因此 R42A/R43 均未启动，两个 runtime root 均不存在，gold/external outcome
仍未读取。完整结果见
`reports/PRTA_GEN_R41A_PROGRESSION_SFT_RESULT_CN.md`。

“自动跑完”只表示沿上述 survival gate 自动前进，不允许跳过失败门、后验调参、
重分 roster、挑 Seed/checkpoint、虚构 external 数据或读取不获准的 gold outcome。

## 历史失败如何约束新尝试

历史 Qwen case study 均使用互斥的 32-patient cohort：

| 路线 | 最好结果 | 终态 |
|---|---:|---|
| free-greedy attention-LoRA，3/12/24 epoch | 5/32、27/32、29/32 | STOP |
| 五个完整 JSON 候选评分 | 28/32 | STOP |
| progression span 20x loss/局部评分 | 24/32 | STOP |
| 首个不同 token 的直接五分类 | 23/32 | STOP |
| semantic-layout structured head | 32/32 | engineering PASS |

这些结果说明 JSON token 拟合不等于 progression binding；在已观察 cohort 上继续
加 epoch、加权或换 scorer 已没有合法解释。新尝试不复用这些患者，也不根据其
错误挑超参数。R41A 改为 500 名新的 patient-disjoint 患者，并恢复原 proposal
注册的三 epoch projector + attention-LoRA SFT。

## R41A：progression-only Qwen SFT survival

剩余未观察 R40A.2-fit 池为 2,627 名患者、5,919 行。唯一患者支持为：

| progression | 患者 |
|---|---:|
| Stable | 1,904 |
| Improved | 647 |
| Worse | 797 |
| New | 419 |
| Resolved | 106 |

Resolved 是绑定类别。因此冻结为每类 75 train + 25 development，共
375/125 名患者，并保留 6 名 Resolved 未使用。排除五批 R40B cohort 的 160 名
患者和 R40C 的 1,500 名患者。

两臂使用相同初始化、数据顺序和 36 次 optimizer update：

- G0：只训练 `TierTokenProjector`，Qwen 全冻结；
- G1：训练相同 projector + Qwen attention-only LoRA；
- 三 Seed：17/29/43；
- 三 epoch、batch 1、gradient accumulation 32；
- projector LR 1e-4、LoRA LR 2e-5；
- free-greedy 两字段 JSON，仅 `finding` 和 `progression`；
- query-only 为全零 exact-64 token，prior-shuffle 使用冻结 cache；
- 不生成 location、degree、evidence 或自由报告。

每一 Seed 的 G1 必须同时通过：macro-F1 ≥ 0.30、每类 recall ≥ 0.12、
schema/finding ≥ 0.99、相对 query/prior-shuffle 至少 +2 pp 且 patient-bootstrap
95% CI 下界大于 0、相对 G0 至少 +1 pp。

## R42A：G-CMCP 与时间反演

R42A 只在 R41A GO 后执行，并从相同 Seed 的 R41A G1 checkpoint 初始化。
它不是 evidence-grounded sentence generation；当前只有 progression 字段通过
资格门，因此继续限定两字段 JSON。

正式 R40 cache 没有 reversed token。R42A 不猜测 token permutation，而是从
原始 Block-8 prior/current 特征出发，用完全相同的冻结 PRTA 模型执行
`model(current, prior, finding_query)`，生成 500 行 reverse exact-64 cache。

比较两臂：

- `g_cmcp`：SFT + 0.25 × sequence-level prior-preference hinge；
- `g_cmcp_plus_reversal`：上述损失 + 0.25 × reversed-target SFT；
- margin 0.2，一 epoch，12 次 optimizer update；
- reversal 映射为 Stable↔Stable、Improved↔Worse、New↔Resolved。

primary combined arm 每 Seed 必须满足：true macro-F1 ≥ 0.30、每类 recall
≥ 0.12、schema/finding ≥ 0.95、correct-prior preference > 0.50、
query/shuffle effect ≥ +2 pp 且 bootstrap 下界 > 0、mapped reversal accuracy
≥ 0.90，并比冻结 R41A G1 至少 +1 pp。

## R43：确认性 readiness，而非小样本结果包装

R43 只在 R42A GO 后执行。它先做 outcome-free readiness gate：

- 当前 untouched image-complete official gold：16 名患者；
- 其中 CheXpert 7、MIMIC 9；
- ReXGradient 有 70 名 untouched annotations，但当前父图像缺失；
- `data/external` 不存在；
- 独立专家标签不可用；
- 16 名患者的 worst-case conservative MDE 约 35.02 pp；
- +2 pp confirmatory endpoint 至少需要 4,906 名患者。

因此按当前磁盘状态，若链条到达 R43，将在任何 gold outcome、metric 或 prediction
读取前返回 `STOP_PRTA_GEN_R43_CONFIRMATORY_READINESS`。这不是“少跑一步”，
而是确认性 gate 的正确结果。

## 自动执行和故障边界

master chain 每 Seed 同时占用 GPU0/GPU1 跑两臂，Seed 之间顺序推进。每个阶段：

1. 只接受冻结配置、roster hash 和前驱 GO；
2. 输出 identity-safe 标量 receipt；
3. 工程异常立即 fail closed，不自动重试；
4. 科学 STOP 立即成为链条终态；
5. gold/external outcome、protected 300-dev 和 revealed 483 始终保持未读。

运行时缓存、checkpoint、逐行 prediction 和日志只留在
`H:\VisualVIT_runtime\050_routeD\r37_prta_cxr`，不进入 Git。
