# PRTA-Gen R40A 信息充分性终局报告

## 直接结论

PRTA-Gen R40A 的冻结终局为：

`STOP_PRTA_GEN_R40A_INFORMATION_SUFFICIENCY`

这不是 R39 失败。R39 仍然保持
`GO_R39_FROZEN_VLM_TRANSFER`，证明冻结 Qwen 可以利用 exact-64 PRTA
表示完成五分类候选序列评分。R40A 回答的是更严格的新问题：这些 token
是否已经稳定保留了足够的信息，可以安全解锁开放式、可溯源的比较句生成。

答案是否定的。progression 虽然在三个 probe Seed 上都有正的点估计，但
Seed 17 的 true-pair 相对 prior-shuffle 差值为 +1.06 pp，
2,000 次 patient-cluster bootstrap 的 95% CI 为
[-0.93, +3.26] pp。下界未严格大于零，因此冻结的 all-seed gate 失败。
按照预注册顺序，R40B projector + Qwen attention-LoRA overfit smoke、R41
正式 SFT、R42 G-CMCP/reversal 和 R43 gold/external 全部保持锁定。

## 冻结输入与防火墙

- 协议：`configs/prta_gen/prta_gen_r40a_probe_v1.json`
- PRTA：既有冻结 Seed 17 checkpoint
- 接口：exactly 64 tokens，768 维；无 pixel/image/video bypass
- 训练 roster：33,677 rows / 8,787 patients
- development roster：5,814 rows / 1,500 patients
- patient overlap：0
- 64-row cache smoke：PASS
- full token cache：training 132 shards；development 23 shards
- `300-dev`：未读取
- 已揭示 `483-test`：未用于开发、选择、阈值或 checkpoint
- gold/external：未读取
- 旧 R40 component/baseline queue：未恢复

literal target audit 支持全部五个 progression 类别、三种 laterality、
六种 coarse anatomy 和四种 degree；不受支持的类别以及
`Unspecified` 没有被伪造为监督标签。Tier-A evidence rows 为
training 17,710、development 3,049，但 evidence retrieval 没有越过
上游信息门槛执行。

## Progression 正式结果

以下均为 true-pair macro-F1 减 control macro-F1，单位为百分点。区间按
1,500 个 development patient 聚类、bootstrap Seed 40001、2,000 次重采样。

| Probe Seed | vs current-only | vs query-only | vs prior-shuffle |
|---:|---:|---:|---:|
| 17 | +6.58 [4.71, 8.45] | +12.13 [10.43, 13.87] | **+1.06 [-0.93, 3.26]** |
| 29 | +21.31 [19.39, 23.34] | +23.56 [21.58, 25.54] | +19.82 [17.77, 21.92] |
| 43 | +15.77 [13.73, 17.81] | +22.22 [20.25, 24.18] | +10.42 [8.32, 12.48] |

冻结 gate 要求每个注册 Seed、每个必需 control 的点估计为正且 95% CI
下界严格大于零。Seed 17 / prior-shuffle 是唯一但决定性的失败单元。
聚合权威产物：

`H:\VisualVIT_runtime\050_routeD\r37_prta_cxr\prta_gen_r40_readiness_v1\probes\progression\aggregate.json`

## 其他字段的停止前诊断

这些数值只用于说明为什么不存在绕过 progression gate 的字段级生成路线；
没有把未完成 bootstrap 的字段宣称为正式科学结论。

| 字段 | 观察到的非稳健性 |
|---|---|
| laterality | Seed 43 true-pair 相对 current-only 为 -1.69 pp，相对 prior-shuffle 为 -2.83 pp |
| anatomy | Seed 43 true-pair 相对 current-only 为 -1.02 pp |
| degree | Seed 17 true-pair 相对 query-only 为 -0.75 pp；按首个失败即停止，未运行 Seeds 29/43 |

因此 laterality、anatomy、degree 均没有获得生成字段解锁资格，也没有进行
rescue、换 Seed、换阈值、换 checkpoint 或 outcome-guided 调整。

## 已完成的代码面

- `src/visualvit/prta_gen.py`：literal target、exact-64 summary、线性 probe、
  future-gated G-CMCP helper
- `src/visualvit/qwen_adapter.py`：assistant-only SFT、sequence scoring、
  autoregressive generation、cache-equivalence 与 LoRA trainable boundary
- `scripts/audit_prta_gen_targets.py`：target support 审计
- `scripts/cache_prta_gen_r40a_tokens.py`：smoke/full token cache 与
  bounded-I/O compact materialization
- `scripts/run_prta_gen_r40a_probe.py`：冻结四 control 线性 probe
- `scripts/aggregate_prta_gen_r40a_field.py`：patient-cluster bootstrap 与
  fail-closed field gate

这些代码保留为可复核的工程实现，不代表 R40B 已被授权。特别是
`GenerativeVLMAdapter` 的存在不能替代 R40A 科学门槛。

## 后续边界

当前不应继续训练生成模型。若未来要继续 PRTA-Gen，需要先建立一个新的、
独立冻结的信息表示方案或监督来源，并重新注册 R40A；不能在当前
development 结果上调 token compiler、挑 Seed 或删除 prior-shuffle
control。R39 的已完成分类结论与本次 R40A STOP 应并列保留。
