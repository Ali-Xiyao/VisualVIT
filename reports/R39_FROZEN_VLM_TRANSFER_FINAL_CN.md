# R39 TIER-CXR-VLM Frozen-VLM Transfer 终局报告

## 结论

R39 已达到预注册终局：

```text
GO_R39_FROZEN_VLM_TRANSFER
```

这意味着 TIER-CXR-VLM 在冻结的 silver cohort、Qwen3-VL、exact-64
视觉接口、projector 容量、训练方案、Seeds 17/29/43、四组比较和
patient-bootstrap 门槛下，成功把 PRTA-CXR 的纵向视觉表示收益迁移到
冻结 VLM。Gold outcomes 始终未读取。

## 完整资格链

| 阶段 | 结论 | 作用 |
|---|---|---|
| R37.1 | `GO_R37_1_THREE_SEED_INTERNAL_QUALIFICATION` | 三 Seed验证正确 prior、CMCP 与 A0 收益 |
| R37C | `GO_R37C_ONE_SHOT_DEV` | 唯一冻结候选通过一次 300-dev 确认 |
| R38 | `GO_R38_FIXED64_SURVIVAL` | 收益在零路由、固定 64-token 打包后存活 |
| R39 | `GO_R39_FROZEN_VLM_TRANSFER` | 冻结 VLM 上通过一次 483-test transfer gate |

## R39 冻结协议

- 483 patients / 4,821 finding rows；
- Seeds 17、29、43；
- patient-cluster bootstrap：2,000 replicates，seed 39001；
- frozen Qwen3-VL：可训练参数 0；
- 无 pixel input 或 probe-logit bypass；
- 每例 exactly 64 个视觉 Token；
- 相同 prompt 与 capacity-matched projector；
- 主比较：A6 true-pair versus frozen A0；
- 控制：current-only、query-only、within-finding prior-shuffle；
- 三套 projector checkpoint 与三套 outcome-blind sealed predictions
  必须在唯一一次 483-label reveal 前冻结。

## 注册比较结果

| Comparison | Seed 17 | Seed 29 | Seed 43 | Mean Δ | 95% CI | 结果 |
|---|---:|---:|---:|---:|---|---|
| A6 vs frozen A0 | +6.54 pp | +16.08 pp | +22.42 pp | +15.01 pp | [+13.80,+16.14] | PASS |
| A6 vs current-only | +2.69 pp | +5.01 pp | +1.95 pp | +3.22 pp | [+2.47,+4.02] | PASS |
| A6 vs query-only | +6.50 pp | +16.08 pp | +24.73 pp | +15.77 pp | [+14.59,+16.84] | PASS |
| A6 vs prior-shuffle | +1.18 pp | +2.51 pp | +2.89 pp | +2.19 pp | [+1.39,+3.05] | PASS |

门槛按冻结协议判断 pooled mean 至少 +2 pp、bootstrap CI lower > 0，
并要求三个 Seed 的方向均为正。四组比较全部通过。

## 每 Seed absolute macro-F1

| Seed | A6 true-pair | Frozen A0 | Current-only | Query-only | Prior-shuffle |
|---:|---:|---:|---:|---:|---:|
| 17 | 0.2096 | 0.1442 | 0.1827 | 0.1446 | 0.1978 |
| 29 | 0.2502 | 0.0894 | 0.2000 | 0.0894 | 0.2251 |
| 43 | 0.3089 | 0.0848 | 0.2894 | 0.0616 | 0.2800 |

相对门槛全部通过，但 absolute F1 仍然不高且存在 Seed 差异。因此当前
结论是“冻结协议下的相对 transfer 有效”，不是临床部署证明。

## 防泄漏与接口审计

| Check | 结果 |
|---|---|
| 三个 checkpoint 在 reveal 前冻结 | PASS |
| 三套 sealed predictions 在 reveal 前冻结 | PASS |
| 483-label reveal 次数 | 1 |
| Gold outcomes | 未读取 |
| VLM trainable parameters | 0 |
| Pixel inputs | 未使用 |
| Token budget | 64 |
| Prompt / projector capacity matched | PASS |
| unchanged source/per-shard/checkpoint hash 重算 | 未执行 |

## 工程偏差与处理

首个 Seed 17 projector 在训练前因参数数目 receipt 不匹配而停止。
`7,948,800` 来自 input-width-16 的 R32 smoke；冻结的 R39
768-to-2560 projector 实际为 `9,873,920` 参数。修复仅更正派生审计
receipt，没有改变 architecture、initialization、data、loss、seed、
control、threshold 或 bootstrap。停止发生在训练和受保护 outcome
读取前；已完成的 outcome-free caches 被原样复用。

相关提交：

- `be10d9f`：冻结 R39 protocol 与实现；
- `91f6560`：修正 projector 参数 receipt；
- `f92822a`：保护 receipt-only resume；
- `f46b233`：记录受控恢复。

## 科学解释与边界

可以直接主张：

- 在本项目冻结的 483-patient silver test 上，TIER-CXR-VLM 的 A6
  true-pair 表示优于 capacity-matched A0；
- 收益也通过 current-only、query-only 和 prior-shuffle shortcut
  controls；
- 表示收益在 exactly-64 接口并经过完全冻结的 Qwen3-VL 后仍然存在。

不能直接主张：

- gold 或跨机构外部泛化；
- 临床可部署性；
- 所有 backbone、VLM 或 prompt 均有效；
- 根据当前 483 outcome 再调参后仍属于本次注册结果。

## 权威产物

- Pipeline status：
  `H:\VisualVIT_runtime\050_routeD\r37_prta_cxr\r39_pipeline_status.json`
- Qualification：
  `H:\VisualVIT_runtime\050_routeD\r37_prta_cxr\r39_sealed_reveal_v1\qualification.json`
- Reveal receipt：
  `H:\VisualVIT_runtime\050_routeD\r37_prta_cxr\r39_sealed_reveal_v1\reveal_receipt.json`

实验链在 R39 GO 后停止。Gold 保持 quarantine；任何后续 gold 或外部
确认必须先建立新的、独立冻结的描述性协议。
