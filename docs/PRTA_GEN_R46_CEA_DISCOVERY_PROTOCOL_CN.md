# PRTA-Gen R46 Causal Evidence Arbitration Discovery 协议

> 日期：2026-07-31
> 状态：frozen pre-outcome authority
> 协议：`prta-gen-r46-cea-v1`

## 1. 问题与新颖性边界

R41A/R44A 表明 Qwen progression readout 对 correct prior 使用不足，
R45 又表明低质量 delta soft evidence 的无条件 bridge 不能解决该问题。
R46 不修改 R45 CDEB，而研究一个独立、可证伪的问题：

> 当且仅当 structured temporal head 相对 current-only counterfactual
> 显示足够强的因果证据时，允许它覆盖冻结生成器；低证据样本是否可以安全
> 保留 baseline，并在新 cohort 上提高 progression-only 两字段 JSON？

Expert-guided decoding、structured/constrained decoding、DOMINO 式形式约束
及 generic product-of-experts 都已有先例。R46 不把这些通用组件本身作为
新颖性。候选贡献限定为：

1. longitudinal true-pair / current-only 因果证据分数；
2. patient-disjoint、低证据 baseline fallback 的 selective arbitration；
3. true/current/query/shuffle controls、multiseed 与 fail-closed sealed gate。

该问题符合 ICLR 对具体研究问题、严谨证据和新知识的要求，但 discovery
结果本身不构成独立确认、SOTA、临床或外部泛化主张。

## 2. 数据与防火墙

- fit：只复用 R45 train 的 2,500 patients 与 immutable exact64 token；
- development：R46 新冻结 250 patients，每类 50，排除 R45 四个
  partitions 的全部 3,750 patients；
- R45 development outcome 不用于 R46 roster 或方法冻结；
- R45 qualification 500 与 confirmation 250 继续 sealed；
- protected 300-dev、revealed 483-test、gold、external 均不读取；
- R46 只缓存新 development 的 250 rows，不缓存任何 sealed row。

## 3. 冻结模型

### 3.1 生成器 baseline

- Qwen3-VL-4B-Instruct 完全冻结；
- 复用 R45 Seed-17 `baseline_projector` 的 immutable projector
  checkpoint；
- 在 R46 development 上一次性生成 true-pair、current-only、
  query-only、prior-shuffle 四个 arms；
- free-greedy、固定 prompt、固定 64-token 注入、两字段 JSON；
- 不训练或选择新的 generator checkpoint。

### 3.2 Structured progression expert

- `exact64_semantic_mean_features`：3,840 维；
- `ProgressionDecisionHead`：LayerNorm → 128 GELU → 五类；
- train-only mean/std；
- Seeds 17/29/43；
- 每 Seed 100 epochs、batch 128、AdamW 0.001、weight decay 0.01；
- 每 Seed 2,000 updates；
- 无 early stopping、无 checkpoint selection；
- Qwen 不加载，只有 499,973 个 head parameters 可训练。

## 4. Causal Evidence Arbitration

对同一个 head，计算 true-pair 与 current-only 的五类分布 `p_t`、`p_c`：

```text
score = JS(p_t, p_c) * max(p_t)
```

阈值不能从 R46 development 的连续数值自由搜索。每个 Seed 只允许在
R45 train score 的冻结 coverage quantiles
`0.20/0.35/0.50/0.65/0.80/0.90` 上取阈值。对每个 quantile：

- `score >= threshold`：允许 structured expert 输出；
- 其余样本：输出 inherited generator baseline；
- query-only 永不覆盖；
- 低证据输出必须与 baseline 100% 一致。

三个 Seed 共用一个 quantile。选择指标是三个 Seed 的 R46 development
mean macro-F1；并列时依次选择 mean actual override rate 更低、quantile
更高的候选。该选择是明确的 discovery model selection，后续只有固定该
quantile 才能进入 sealed qualification。

## 5. Discovery Gate

全部条件同时满足才返回 `GO_PRTA_GEN_R46_CEA_DISCOVERY`：

- 每 Seed structured true macro-F1 ≥ 0.40；
- 每 Seed CEA true macro-F1 ≥ 0.38；
- 每 Seed 五类 recall 均 ≥ 0.12；
- mean CEA − baseline ≥ +1 pp，且每 Seed均不低于 baseline；
- pooled patient-cluster bootstrap 的 CEA − baseline 95% CI 下界 > 0；
- mean CEA true − CEA prior-shuffle ≥ +1 pp，且 pooled CI 下界 > 0；
- mean eligible coverage ∈ [0.10, 0.80]；
- mean actual override rate ∈ [0.05, 0.80]；
- low-evidence baseline agreement = 1.0；
- schema validity = finding echo accuracy = 1.0。

Bootstrap 为 2,000 replicates，按 patient 聚类，三个 Seed 的同一患者作为
同一 cluster。

任一门失败则终态为 `STOP_PRTA_GEN_R46_CEA_DISCOVERY`，不得根据本次
development outcome 修改 score、quantile、训练设置或 gate 后重跑。

## 6. 后续 sealed 顺序

Discovery GO 只允许冻结所选 quantile 并进入 R45 原 qualification cohort
的一次性 R46 qualification；不得读取 confirmation。Qualification 所有
预注册门通过后才可一次性进入 confirmation。任何 STOP 都终止 R46。

## 7. 相关工作定位

- LEAD：医学 expert-guided layerwise decoding；
- CWCD：医学 structured / contrastive decoding；
- DOMINO：通用 constrained decoding；
- Product-of-Experts with LLMs：通用 PoE 融合；
- CORAL / TILA：纵向或 temporal grounding / inversion 先例。

因此 R46 的主张必须保持为“causal-evidence selective arbitration 的
受限 progression-only 证据”，不能写成 generic constrained decoding、
generic expert guidance 或开放式报告生成的新颖性。
