# PRTA-Gen R40A 失败案例研究

## 直接结论

R40A 不是因为目标不足或代码中断而停止，而是因为三均值线性 readout
无法在 Seed 17 上稳定证明正确 prior 优于 prior shuffle。案例研究进一步
显示：失败集中在动态类别和部分 finding，同时 token 内部仍存在与
true/shuffle 敏感性相关的强度差异。

因此，下一次尝试不应继续调整 Seed、阈值或分类投票；应检验三均值是否
丢失了 exact-64 序列中的区间内分布和位置信息。

## 数据边界

- 旧 R40A development：5,814 rows / 1,500 patients；
- 只读已关闭的 Seeds 17/29/43 progression predictions；
- 没有读取 300-dev、483-test、gold/external；
- 没有报告 patient ID、DICOM ID 或原始报告句；
- 40 个示例只保留 SHA-256 example ID、finding、progression、预测类别和
  token RMS；
- 本案例集不得参与新候选选择。

机器产物：

`H:\VisualVIT_runtime\050_routeD\r37_prta_cxr\prta_gen_r40_readiness_v1\case_study_r40a_v1\case_study.json`

## Seed 17 错误结构

| 类别 | 行数 |
|---|---:|
| true-pair 对、shuffle 错 | 917 |
| shuffle 对、true-pair 错 | 623 |
| 两者都对 | 2,298 |
| 两者都错 | 1,976 |

三个 Seed 中，只有 148 行持续表现为 true-sensitive；939 行持续
both-wrong。说明问题不是删除少数离群病例就能解决。

## 类别与 finding 聚集

Seed 17 的净敏感率定义为：

`(true-sensitive - shuffle-favored) / rows`

| Progression | 净敏感率 |
|---|---:|
| Stable | +14.68% |
| New | +6.20% |
| Improved | -3.52% |
| Resolved | -4.85% |
| Worse | -9.27% |

Pneumothorax 的 finding-level 净敏感率为 -21.99%，是最明显的负簇。
这表明三均值 readout 更容易保留 Stable/New 的粗信号，但对有方向的
Improved/Worse/Resolved 不稳定。

## Token 案例

Seed 17 的 transition-region true/shuffle RMS：

- true-sensitive 平均 4.78；
- shuffle-favored 平均 4.00；
- both-correct 平均 3.36；
- both-wrong 平均 3.98。

持续 shuffle-favored 的 Atelectasis/Stable 示例中，transition RMS 可低至
0.21；持续 true-sensitive 的 New 示例可达到 13.5–14.3。四个 reserve
positions 的 RMS 恒为 0。

这支持一个有限结论：prior 信息强度与成功读取有关，但固定区域均值没有
保留足够的区间内结构来稳定解码方向类别。

## 之前失败方式总结

1. R33：prediction-level routing 不能直接转化为 token survival。
2. R33A：在同一 observed cache 上连续搜索 projection、context、bridge 和
   routing，没有形成稳定 prior control，最终成为 frozen-cache premise STOP。
3. R37 tiny case：训练不足时模型对 prior 完全不响应；增加到预先存在的
   工程预算后响应出现，说明工程 smoke 不能冒充科学结论。
4. R37：正确 prior 收益为正，但 soft inversion loss 不能保证群等变，
   inversion gate 失败。
5. R37.1：用一个无参数 Z2-equivariant 结构修复明确机制，并在 fresh
   holdout 上验证，最终成功。
6. R40A：目标和缓存通过，但三均值 readout 的 Seed-17 prior-shuffle CI
   跨零，因此生成未解锁。

共同教训是：成功修复必须针对可验证机制，并在新边界一次确认；不能用更多
Seed、弱化 CI 或在同一 observed cohort 上搜索到一个有利结果。

## 新尝试

新冻结 R40A.1 依次测试：

1. 区域 mean/std/max；
2. 区域内固定四分量 cosine/DCT 位置基。

它们都使用原 exact-64 token 和单线性 classifier。第一个通过 discovery
三 Seed/两 control/bootstrap 门的候选将被唯一冻结，再接受一次
qualification。若 qualification GO，只解锁 progression-only R40B smoke；
其他生成字段仍省略。

协议：
`docs/PRTA_GEN_R40A1_CASE_DRIVEN_REPAIR_PROTOCOL_CN.md`

## R40A.1 结果与新发现

R40A.1 两个候选均未进入 qualification：

- regional moments：Seed 17 对 prior-shuffle +8.13 pp，但 Seed 29
  为 -5.18 pp；
- regional cosine4：Seed 17 对 prior-shuffle -1.23 pp。

这排除了“只要增加区域内统计或固定位置分量即可”的解释。

随后审计 `pack_fixed64` 发现，真实布局是 query 4、state 12、global
transition 16、local transition 16、relation 12、reserve 4，而失败 probe
使用了 20/20/20 分段。这会混合 query/state 并切开两个 transition 类型。

因此 R40A.2 不增加模型容量，而是首先修复 token-type 语义边界，并使用
新的 discovery2 验证。原 R40A.1 qualification 保持未读。

## 案例驱动修复终局

R40A.2 的 semantic-layout means 在 discovery2 和一次性 qualification
上均通过。qualification 的三个 Seed true-pair macro-F1 分别为
0.3876、0.3512、0.3900；相对 query-only 为 +17.93、+12.64、+13.85 pp，
相对 prior-shuffle 为 +2.17、+18.55、+8.23 pp。所有注册 point gate 和
patient-cluster bootstrap 下界均通过，终态为：

```text
GO_PRTA_GEN_R40A2_QUALIFICATION
```

生成工程随后使用五批互不重叠的 32-patient fit cohort。每次新方法都先冻结，
没有回到已经观察的患者上挑设置。

| 路线 | 核心改变 | progression | 结论 |
|---|---|---:|---|
| R40B 3 epochs | Qwen attention-LoRA free greedy | 5/32 | underfit STOP |
| R40B 12 epochs | 冻结的第二级预算 | 27/32 | underfit STOP |
| R40B 24 epochs | 冻结的最终预算 | 29/32 | underfit STOP |
| R40B.1 | 五个完整合法 JSON 候选评分 | 28/32 | constrained STOP |
| R40B.2 | 20x progression span loss + span score | 24/32 | weighted-span STOP |
| R40B.3 | 首个不同 token 的五分类 | 23/32 | direct-class STOP |
| R40B.4 | semantic-layout MLP + 确定性 JSON | 32/32 | engineering PASS |

前三类修复没有解决问题：共同 JSON token 会稀释 progression 分数；固定
20x 权重反而使语义 token 不稳定；即使直接比较五个首 token，Qwen 的
causal-LM 决策仍未在小样本冻结预算内完成精确记忆。继续调学习率、loss
权重或 decoding，实质上会在同一失败假设上调参。

R40B.4 的成功机制是把语义决策和语言实现分开。499,973 参数的受限 head
直接消费 R40A.2 已验证的 3,840 维 semantic-layout means，并只确定性发出
`finding` 与 `progression` 两个键。第五批 cohort 排除了前四批共 128 名
已观察患者，最终 progression/schema/finding 均为 32/32，loss ratio 为
`7.33027e-08`。

这不是把失败改名为成功：Qwen 是真正的 LLM，但 Qwen free-generation
路线仍为 STOP；跑通的是 progression-only structured engineering smoke。
它不提供泛化证据，也不解锁其他字段、R41–R43、gold 或 external。
