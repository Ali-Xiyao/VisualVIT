# PRTA-Gen R40A.2 / R40B.4 结构化路线终态报告

## 直接结论

是，当前 proposal 已经跑通一个严格限定的工程路径：

```text
GO_PRTA_GEN_R40A2_QUALIFICATION
→ PASS_PRTA_GEN_R40B4_STRUCTURED_HEAD_SMOKE
```

跑通的是从 exact-64 semantic-layout token 到 progression-only 两字段 JSON
的结构化生成。Qwen 自由生成没有跑通，科学泛化也没有被本次 32-row
overfit smoke 证明。

## 信息门：R40A.2

旧 R40A/R40A.1 将 exact-64 token 错误池化为 20/20/20 三段；源码审计确认
真实布局为 query 4、state 12、global transition 16、local transition 16、
relation 12、reserve 4。R40A.2 不增加模型容量，只修复这条语义布局边界。

它排除已经观察的 1,500 名 R40A.1 discovery 患者，从原 fit 冻结新的
1,500-patient discovery2，并保留原 1,500-patient qualification 未读。
semantic-layout means 是按注册顺序通过 discovery2 的唯一候选。

| Qualification Seed | true-pair macro-F1 | 对 query-only | 对 prior-shuffle |
|---:|---:|---:|---:|
| 17 | 0.3876 | +17.93 pp | +2.17 pp |
| 29 | 0.3512 | +12.64 pp | +18.55 pp |
| 43 | 0.3900 | +13.85 pp | +8.23 pp |

三个 Seed 的注册 point gate 和 patient-cluster bootstrap 下界全部通过。
Seed 17 对 prior-shuffle 是最窄边界：point +2.169 pp，95% CI 下界
+0.298 pp。冻结规则要求 point 至少 +2 pp 且 CI 下界大于零，因此该结果
合法通过，但必须保留“边界较窄”的解释。

## Qwen 生成失败谱系

所有路线均使用 exact-64、无 pixel bypass、assistant-only supervision，
并在新的 patient-disjoint 32-row cohort 上执行。Qwen 能稳定学会 JSON
外壳和 finding echo，但 progression 语义决策没有通过 32/32 冻结门。

| 路线 | 主要假设 | 最终 progression | 终态 |
|---|---|---:|---|
| R40B 3 epoch | 原注册 free-greedy LoRA | 5/32 | STOP |
| R40B 12 epoch | 增加到注册第二级预算 | 27/32 | STOP |
| R40B 24 epoch | 注册最终预算 | 29/32 | STOP |
| R40B.1 | 五个完整 JSON 的长度归一化评分 | 28/32 | STOP |
| R40B.2 | progression span 20x loss 与局部评分 | 24/32 | STOP |
| R40B.3 | 首个不同 token 的直接五分类 | 23/32 | STOP |

R40B 24 epoch 已达到 99.35% teacher-forced token accuracy，却仍有 3 个
progression 错误，说明 JSON 形式拟合不等于语义 binding。R40B.1 的完整
序列评分仍被公共 JSON/finding token 稀释；R40B.2 的固定高权重使语义
分类更不稳定；R40B.3 直接五分类仍未闭合。继续在这些 observed cohort 上
调学习率、权重或 decoding 不再是独立验证。

## 跑通路线：R40B.4

R40B.4 将语义决策与语言实现分开：

1. 输入保持 qualification 支持的 exact-64 semantic-layout means，
   展平宽度为 3,840；
2. 使用 LayerNorm、128 维 MLP 和五分类输出，共 499,973 个参数；
3. 根据五分类结果确定性输出唯一合法的
   `{"finding":"...","progression":"..."}`；
4. 不把该结果记作 Qwen free generation。

第五批 cohort 有 32 名全新患者，类别为 7/7/6/6/6，并排除前四条 Qwen
路线观察过的 128 名患者。

| 工程门 | 结果 |
|---|---:|
| 初始 loss | 1.6262604 |
| 最终 loss | 1.1920928e-07 |
| final / initial | 7.33027e-08 |
| progression | 32/32 |
| schema validity | 32/32 |
| finding echo | 32/32 |
| exact-64 | PASS |
| pixel input | 未使用 |

终态为：

```text
PASS_PRTA_GEN_R40B4_STRUCTURED_HEAD_SMOKE
```

## 防火墙与可主张范围

本次没有读取 protected 300-dev、revealed 483-test、gold 或 external
outcomes；R40B.4 result 明确记录：

```text
qwen_free_generation_unlocked = false
scientific_claim_allowed = false
r41_qwen_sft_unlocked = false
```

当前可主张：

- R40A.2 的 semantic-layout exact64 表示在独立 qualification 上含有
  prior-specific progression 信息；
- 该表示可在一个全新 32-patient engineering overfit smoke 上驱动
  progression-only 结构化 JSON 达到 32/32。

当前不可主张：

- Qwen 自由生成或开放式报告已经跑通；
- 结构化头具有 patient-level 泛化能力；
- laterality、anatomy、degree、evidence 已解锁；
- R41–R43、gold、external 或临床部署已获授权。

## Runtime 权威产物

- R40A.2 qualification：
  `H:\VisualVIT_runtime\050_routeD\r37_prta_cxr\prta_gen_r40a2_layout_repair_v1\probes\semantic_layout_means_v1\qualification\aggregate.json`
  （SHA-256 `C208D5F56082AF117820F91C0B86110686BF9B13CC910D54B9AE156BC124D722`）
- R40B.4 cohort：
  `H:\VisualVIT_runtime\050_routeD\r37_prta_cxr\prta_gen_r40b4_structured_head_smoke_v1\cohort.json`
  （SHA-256 `B2A1AA1706A5B93FC296CDD30E6D8559960D8A214619C3953C945D7661D91622`）
- R40B.4 result：
  `H:\VisualVIT_runtime\050_routeD\r37_prta_cxr\prta_gen_r40b4_structured_head_smoke_v1\structured_head\result.json`
  （SHA-256 `CF888F8FE5C4CA13185E2C9CD9FE9FD8D01AB76857AE1A83233A2D2043685745`）
