# PRTA-Gen R41A progression-only Qwen SFT 终态报告

日期：2026-07-31

终态：`STOP_PRTA_GEN_R41A_PROGRESSION_SFT_SURVIVAL`

## 直接结论

R41A 已按预先冻结的 375-train / 125-development、Seeds 17/29/43、
G0 projector-only 与 G1 attention-LoRA、每臂 36 次 optimizer update
完整执行。六个 arm 均返回
`PASS_PRTA_GEN_R41A_ARM_EVALUATION`，但三 Seed 聚合共有 8 个冻结门失败，
因此 R41A 是科学 STOP，不解锁 R42A 或 R43。

这不表示 Qwen 不是 LLM，也不撤销 R40C 的 structured-head internal
development GO。它表示在本次已冻结的 progression-only、两字段
free-greedy Qwen SFT 设计下，attention-LoRA 没有稳定优于 projector-only，
并且 `Worse` 类发生了跨 Seed 的低召回。

## 冻结设计

- roster：375 train + 125 patient-disjoint development，每类 75/25；
- roster SHA-256：
  `2BA53C95BDDC78CBE1E585CF5954708892B6106578DA812226D87F94FD4F77C0`；
- Seeds：17、29、43；
- G0：仅训练 `TierTokenProjector`，Qwen 全冻结；
- G1：相同 projector + attention-only LoRA；
- 三 epoch、batch 1、gradient accumulation 32、每臂 36 updates；
- 评估：true-pair、current-only、query-only、prior-shuffle；
- 输出：free-greedy 两字段 JSON，仅 `finding` 与 `progression`；
- patient-cluster bootstrap：2,000 次，seed 41001。

## 主要结果

| Seed | G0 true macro-F1 | G1 true macro-F1 | G1−G0 (pp) | G1 最低类 recall | schema / finding |
|---:|---:|---:|---:|---:|---:|
| 17 | 0.3520 | 0.3474 | -0.46 | Worse 0.00 | 1.00 / 1.00 |
| 29 | 0.4971 | 0.3632 | -13.40 | Worse 0.08 | 1.00 / 1.00 |
| 43 | 0.4989 | 0.4304 | -6.85 | Worse 0.08 | 1.00 / 1.00 |

G1 对 query-only 的效应为 +25.53 / +27.10 / +31.49 pp，三 Seed 的
95% CI 下界均大于 0。G1 对 prior-shuffle 的效应为
+1.69 / +8.53 / +10.52 pp；Seed 17 未达到 +2 pp，且 95% CI
[-4.77, +7.73] 跨零。

## 八个冻结门失败

1. Seed 17 `Worse` recall = 0.00，低于 0.12；
2. Seed 17 true−prior-shuffle = +1.69 pp，低于 +2 pp；
3. Seed 17 true−prior-shuffle CI 下界 = -4.77 pp，不大于 0；
4. Seed 17 G1−G0 = -0.46 pp，低于 +1 pp；
5. Seed 29 `Worse` recall = 0.08，低于 0.12；
6. Seed 29 G1−G0 = -13.40 pp，低于 +1 pp；
7. Seed 43 `Worse` recall = 0.08，低于 0.12；
8. Seed 43 G1−G0 = -6.85 pp，低于 +1 pp。

macro-F1、schema validity、finding echo 和 query-only control 本身通过，
但冻结 gate 要求所有条件、所有 Seed 同时通过，不能用通过项抵消失败项。

## 工程执行与失败方式

第一次授权启动在训练前因 trainable-audit 字段名不一致而 fail closed；
第二次在 Seed-17 训练后、结果写入前，因 cache-equivalence audit 在 LoRA
dropout 仍为 training mode 时比较两次 forward 而 fail closed。两次都没有
产生 checkpoint、prediction 或科学结果，日志已分别归档。

修复只规范审计字段，并让 cache audit 临时进入 deterministic `eval()` 后
恢复原模式；数据、roster、Seed、模型臂、训练超参、解码与科学门均未改变。
第三次运行六臂 cache audit 全部通过，最大绝对差均为 0。

## 防火墙与自动链终态

- protected 300-dev：未读；
- revealed 483-test：未读；
- gold outcomes：未读；
- external outcomes：未读；
- R42A runtime root：不存在；
- R43 runtime root：不存在；
- `r42_unlocked=false`；
- `r43_unlocked=false`；
- Qwen free-generation survival：未解锁；
- laterality/anatomy/degree/evidence：未解锁；
- 科学或临床主张：不允许。

主链在 R41A 第一处科学 STOP 正常结束，没有启动 R42A reverse cache、
G-CMCP/reversal 或 R43 readiness。两张 GPU 已回到 0 MiB/0%，所有匹配
Python 进程已退出。

## 权威产物

- aggregate：
  `H:\VisualVIT_runtime\050_routeD\r37_prta_cxr\prta_gen_r41a_progression_sft_v1\aggregate.json`
- aggregate SHA-256：
  `73532ADA33B5B16499DDE98F0910CF1CFFD29FA410EA30B9A438CC7420A75171`
- R41A sequence status：
  `H:\VisualVIT_runtime\050_routeD\r37_prta_cxr\prta_gen_r41a_progression_sft_v1\sequence_status.json`
- master-chain status：
  `H:\VisualVIT_runtime\050_routeD\r37_prta_cxr\prta_gen_r41_r43_authorized_chain_v1\sequence_status.json`

## 下一步边界

不要针对本次 development outcome 调 learning rate、loss、LoRA rank、
Seed、checkpoint、roster 或门槛，也不要绕过 R41A STOP 启动 R42A/R43。
若未来继续，必须先提出与本次 outcome 无关、具有新数据或新机制依据的
独立预注册方案；现有结果适合用于失败案例研究和 proposal 收束。

只读失败案例研究已经完成：
`reports/PRTA_GEN_R41A_FAILURE_CASE_STUDY_CN.md`。它使用预先提交的
identity-free analyzer 重算 confusion、G0/G1 migration、controls 与
cross-Seed consistency，没有启动新训练，也不改变本报告的终态。
