# TIER-CXR-VLM 消融与对比实验缺口审计

## 结论先行

**核心方法有效性目前没有必须补跑的阻断实验。** R37.1→R39 已经完成
三 Seed、capacity-matched A0、current-only、query-only、prior-shuffle、
CMCP、temporal inversion、state retention、exact-64、no-pixel 和
zero-trainable-VLM 等关键门。

如果目标从“确认核心方法有效”提升到“形成更强的方法论文”，仍建议补
三类证据：

1. PRTA 组件级消融；
2. 强 multi-image VLM/temporal baselines；
3. 生成、泛化和稳定性扩展。

新增实验不能改变已冻结的 R39 结论，也不能根据已揭示 483-test 选择设置。

## 已完成，不要重复

| 证据 | 当前状态 | 结论 |
|---|---|---|
| A6 vs capacity-matched A0 | R37.1、R37C、R39 均完成 | 核心表示和 frozen-VLM transfer 均为正 |
| Current-only | R37.1/R39 完成 | prior 提供额外信息 |
| CMCP | R37.1 完成 | 同 finding 错误 prior 会降低性能 |
| Query-only | R39 完成 | 不是 label-prior shortcut |
| Prior shuffle | R39 完成 | 使用了同一患者的时间证据 |
| Temporal inversion | R37.1 representation/logit gate 完成 | 等变一致性 1.0 |
| State retention | R37.1/R37C 完成 | cosine ≥0.99 |
| Exact 64 tokens | R38/R39 完成 | 收益在固定预算下存活 |
| No pixel bypass / frozen VLM | R39 interface audit 完成 | VLM trainable parameters = 0 |
| Seeds / patient bootstrap | Seeds 17/29/43 完成 | 全部注册比较方向为正 |

## P0：核心有效性所需

没有缺失项。不要为了“更完整”重跑 R38/R39，也不要在 483-test 上搜索
新配置。

## P1：建议优先补，形成完整方法消融

### 1. PRTA A2→A6 组件阶梯

实施仓库已经定义：

| Variant | Classification | Alignment | Inversion | CMCP | State preservation |
|---|---|---|---|---|---|
| A2 | 是 | 否 | 否 | 否 | 否 |
| A3 | 是 | 是 | 否 | 否 | 否 |
| A4 | 是 | 是 | 是 | 否 | 否 |
| A5 | 是 | 是 | 否 | 是 | 否 |
| A6 | 是 | 是 | 是 | 是 | 是 |

建议在新的 patient-disjoint development roster 上冻结：

- 相同 Block-8 cache、adapter rank、epochs、batch、LR；
- Seeds 17/29/43；
- A2/A3/A4/A5/A6 全部训练，不做中途选择；
- paired patient-cluster bootstrap；
- 报告 macro-F1、inversion、CMCP gain、state retention；
- 不读取 gold，不用 483-test 决定设置。

这是当前最重要的消融，因为它能回答 A6 的收益分别来自 alignment、
inversion、CMCP 还是 state-preservation。

### 2. 强 multi-image baseline 包

**2026-07-31 更新：** R49 已完成 Raw/Naive exact-64/PRTA 的统一 750 人
归因；R50 已完成 TILA-CE、TILA-BiCE/TCL、Siamese signed/absolute 与
TAC-adapted 三 Seed 直接分类对比。R52 又在 fresh 500 人上完成 PRTA、
TILA-exact64、B2-exact64 的同 token、同 5,991,173 参数直接头、三 Seed
比较，PRTA 对两者的 paired CI 下界均大于零。直接分类 matched-interface
缺口已关闭；exact-64 + frozen-Qwen 的系统级对比由 R51 正在执行，尚未终态。

至少补：

- Raw two-image frozen Qwen3-VL；
- Naive fixed-64 prior/current token concatenation；
- Frozen BiomedCLIP simple difference（已有 A0）；
- Siamese temporal pooling 或 signed+absolute difference；
- PRTA-CXR A6。

公平性要求：

- 同一训练/验证患者；
- 同一 prompt、label order 和 VLM；
- 固定 64-token 版本必须 matched token budget；
- projector 参数量与训练预算配平；
- 原生 raw two-image VLM 单独报告其 pixel/token 成本，不能伪装成等预算。

它回答的不是 A6 是否优于 shortcut，而是是否优于最直接的 multi-image
VLM 与常规 temporal representation。

### 3. Frozen-VLM time-reversal audit

交换 prior/current，要求：

```text
Stable → Stable
Improved ↔ Worse
New ↔ Resolved
```

优先作为冻结 checkpoint/prediction 的 audit，不训练新参数。报告三 Seed
的 mapped prediction consistency、macro-F1 和失败类型。若需要重新运行
VLM inference，必须先冻结脚本与统计规则，并标为 post-R39 secondary。

## P2：强论文建议，但不阻断核心结论

| 实验 | 价值 | 建议边界 |
|---|---|---|
| Finding-level comparative generation | 证明方法不仅做 one-word classification | 冻结模板；自动事实一致性 + 独立专家盲评 |
| 第二 frozen VLM（例如同系列 8B） | 检查是否依赖 4B 模型 | 固定同一 tokens/prompt；不据结果改方法 |
| 第二视觉 backbone | 检查 BiomedCLIP 特异性 | BioViL-T 可作候选，但现有 A1 仅工程 case study |
| Calibration / route-risk | 支持临床风险讨论 | NLL、ECE、Brier、coverage-risk；secondary |
| Per-finding / rare-state analysis | 展示 Stable/Resolved 等弱类行为 | Holm correction；不据亚组改 cohort |
| 计算成本 | 论文工程完整性 | cache、training、inference 时间及显存 |
| Gold/external descriptive | 检查 silver→external gap | 当前约 16 patients / 43 rows，功效不足，不设强显著性主门 |

## P3：可选或暂不建议

| 实验 | 原因 |
|---|---|
| 32/96-token budget curve | 对 efficiency 有用，但 exact-64 核心已通过 |
| 解冻 ViT 最后一层 | 会改变“冻结视觉主干”主张，应另立方法 |
| 不共享 projector | 主要检查参数量 shortcut；当前 shared/capacity audit 已较强 |
| ROI/patch shuffle、side swap | 只有可靠 ROI/laterality annotation 时才有解释性 |
| Grounding | 当前方法未主张 localization；需要 gold boxes/masks |
| Oracle route | 容易形成不可部署上界，不应成为主结论 |
| 大量 ensemble heuristics | 属于旧 R32 routing 路线，与当前 PRTA 方法不完全同构 |

## 方法命名必须先统一

旧 proposal 的“四级 robust/rich hard router”与最终实现的 PRTA-CXR A6
并非完全相同：

- 旧设计强调 Tier 0/1/2/3 与 robust/rich route；
- 当前实现是 query-conditioned cross-time adapter、state/transition
  resampler、alignment、inversion、CMCP 与 state-preservation。

因此不要直接把“去掉 Tier 0/1/2/3”当作当前 A6 消融。建议论文把
**PRTA-CXR 作为实现方法，TIER-CXR-VLM 作为完整 frozen-VLM 系统名**，
再使用 A2→A6 做组件消融。否则实验表会混合两个不同方法 namespace。

## 推荐执行顺序

```text
先冻结 component-ablation + strong-baseline protocol
→ 在新的 development roster 上跑 A2/A3/A4/A5/A6
→ 同 roster 跑 raw two-image / naive concat / temporal baselines
→ 做 frozen-VLM time-reversal audit
→ 再决定是否值得做 8B、第二 backbone、generation
→ gold/external 始终最后且只做独立描述性确认
```

当前建议只完成协议设计和数据可行性审计，不立即启动 GPU。
