# R40 组件消融与强基线冻结协议

## 直接边界

R40 是 R39 完成后的独立二级实验，不改变
`GO_R39_FROZEN_VLM_TRANSFER`。R40 不使用已经揭示的 483-test、R37.1
旧 validation 或 gold 来选择模型、超参数、阈值、Seed、checkpoint、
prompt 或停止时点。

机器可读权威为
`configs/r40/r40_component_and_baseline_v1.json`。若本文与配置冲突，以配置
为准并停止执行。

## 新 development roster

- 唯一来源：`r37_1_transitions_v1` 的 training partition；
- 该来源已经排除旧 R37 calibration 和已经观察过的 R37.1 validation；
- 按
  `sha256("r40-development-roster-v1|40701|patient_id")`
  排序；
- 前 1,500 个患者作为一次性 R40 development，其余患者全部作为
  training；
- 分组后才允许统计标签支持；
- 若任一标签低于冻结的最低支持，不重新换 Seed 或重分组，直接 STOP；
- 复用现有 Block-8/text/CMCP cache，不重算不变 hash。

## 组件消融

所有变体使用相同的 patient roster、Block-8 cache、adapter rank 32、
3 epochs、batch size 2、learning rate 1e-4 和 Seeds 17/29/43。

| Variant | Classification | Alignment | Z2 inversion | CMCP | State preservation |
|---|---:|---:|---:|---:|---:|
| A2 | ✓ |  |  |  |  |
| A3 | ✓ | ✓ |  |  |  |
| A4 | ✓ | ✓ | ✓ |  |  |
| A5 | ✓ | ✓ |  | ✓ |  |
| A6_no_state | ✓ | ✓ | ✓ | ✓ |  |
| A6 | ✓ | ✓ | ✓ | ✓ | ✓ |

这里把 R37.1 的 inversion 明确定义为无参数 Z2 logit projection，而不是
旧 R37 的 KL 辅助 loss。新增 `A6_no_state` 是必要的：仅有 A2–A6
原始阶梯无法把 state-preservation 与 inversion/CMCP 单独分离。

冻结对比：

1. A3−A2：alignment；
2. A4−A3：Z2 inversion；
3. A5−A3：无 inversion 时的 CMCP；
4. A6_no_state−A4：有 inversion 时的 CMCP；
5. A6_no_state−A5：有 CMCP 时的 inversion；
6. A6−A6_no_state：state preservation。

全部 Seed 都运行，不按中间结果挑 Seed 或提前停止。统计单位为患者，
2,000 次 patient-cluster bootstrap，bootstrap Seed 40001。

## 强基线

| ID | 定义 | 比较边界 |
|---|---|---|
| B0 | frozen BiomedCLIP CLS current−prior + finding-conditioned probe | 现有 A0 的同 roster 重跑 |
| B1 | 30 prior + 30 current + 4 shared-zero 的 naive exact-64 concat | 与 A6 同 VLM、prompt、projector 容量和训练预算 |
| B2 | prior/current CLS、signed difference、absolute difference | representation baseline；不宣称等 token 预算 |
| B3 | raw two-image frozen Qwen3-VL | 原生 pixel baseline；单独报告时间/显存/像素成本 |

B3 不伪装成等计算量基线。B1 才是 fixed-64、同 projector 容量的直接系统
对比。

## Frozen-VLM time reversal

交换 prior/current，并使用冻结映射：

- Stable→Stable；
- Improved↔Worse；
- New↔Resolved。

报告三 Seed 的 mapped prediction consistency、正向 macro-F1、反向映射后
macro-F1 和每类失败计数。该 audit 不允许反向修改模型或 prompt。

## 终止条件

- 工程 STOP：schema、roster、patient-disjointness、cache、梯度或 exact-64
  接口不满足；
- 数据 STOP：冻结分组后标签支持不足；
- 科学结果：完整报告 effect 和 95% CI，不根据结果临时改 +2 pp 门槛或改
  叙事；
- 483-test 和 gold 全程不再读取。
