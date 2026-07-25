# CAPES-CI 方法学查新与 2026 会议级定位

日期：2026-07-19  
状态：主方法候选冻结；正式数据、端到端 survival gate 和主实验尚未完成  
证据边界：本报告不把 2026-07-13 的 synthetic/proxy 结果升级为正式结论

## 1. 结论先行

两份 proposal 不能以“通用多图融合 + Sinkhorn + 固定 token”直接合并投稿。2024–2026 最近邻已经分别覆盖纵向 CXR 表征、entity-aware comparative radiology、partial/unbalanced OT、medical token OT、compact relational token injection、多图 source separation 和 VLM binding intervention。

目前唯一可辩护、也可被严格证伪的主线是：

> **CAPES-CI: Causally Identified Persistent Entity Transport Tokenizer**  
> 在固定输入、固定选取支持、固定 64-token 预算和固定 frozen-VLM 计算图下，先用 assignment-only controlled intervention 识别正确跨检查实体 assignment 的模型内效应，再用不读取 oracle cardinality 的 two-sided-null partial transport tokenizer 恢复该效应。

它不是“临床因果发现”，而是受控模型干预下的 assignment effect。DIVE 的通用多图模块降为强基线或后续泛化，不再承担 headline novelty。

## 2. 核心主张与风险等级

| 候选主张 | 新颖性 | 决定 |
|---|---:|---|
| 纵向 CXR entity/change reasoning | 低 | 不作首创；只作为任务背景 |
| two-sided null partial transport / dustbin | 低 | 作为必要机制，不作算法首创 |
| fixed-budget relational tokens 注入 frozen VLM | 中低 | 作为严格控制和可复用接口，不声称 token compression 首创 |
| 同像素、同支持、同预算、同计算图，仅改变 identity assignment 的 B4 干预 | 中高 | 作为发现性主贡献 |
| learned binder 无 oracle cardinality 地恢复 B4 上界并迁移到 frozen VLM | 中高但高风险 | 作为方法性主贡献；必须由真实 gold 数据和 CI 证明 |

组合前总体新颖性约 5.5/10。只有 B4 可识别性、two-sided-null 审计和 frozen-VLM transfer 三者形成闭环，才有约 7/10 的方法论文潜力。

## 3. 最近邻与不可再使用的首创表述

| 最近邻 | 已覆盖内容 | CAPES-CI 必须证明的额外差异 |
|---|---|---|
| [Med-ST, ICML 2024](https://openreview.net/forum?id=87ZrVHDqmR) | multi-view/longitudinal CXR 时空预训练 | assignment-only effect、birth/death transport、frozen-VLM transfer |
| [MLRG, CVPR 2025](https://openaccess.thecvf.com/content/CVPR2025/html/Liu_Enhanced_Contrastive_Learning_with_Multi-view_Longitudinal_Data_for_Chest_X-ray_CVPR_2025_paper.html) | longitudinal contrastive learning、absence token | entity-level two-sided null 和可审计 transport |
| [Libra, ACL Findings 2025](https://aclanthology.org/2025.findings-acl.888/) | VLM 前融合 prior/current difference | persistent identity assignment 的单变量干预 |
| [ProTrans 2026](https://arxiv.org/abs/2606.15938) | directional transition、state/transition alignment、reverse/bidirectional reconstruction | identity/null binding 相对 transition encoder 的额外活性 |
| [CheXTemporal 2026](https://arxiv.org/abs/2605.11304) | 五类 progression 与时空 alignment 数据/评测 | 不声称首次任务；作为 gold/强评测候选 |
| [TRACE 2026](https://arxiv.org/abs/2602.02963) | comparison、change classification、grounding | assignment isolation 和固定预算接口 |
| [MedReCo 2026](https://arxiv.org/abs/2606.06407) | entity-aware cross-image radiology | two-sided null、同构干预和 local frozen adapter |
| [POT, ICLR 2025](https://openreview.net/forum?id=uDXFOurrHM) / [AAAI 2024 POT](https://ojs.aaai.org/index.php/AAAI/article/view/28648) | partial assignment 与可行性/rounding | CXR identity semantics、审计与 VLM 行为效应 |
| [Longitudinal lesion UOT, ISBI 2026](https://arxiv.org/abs/2602.09933) | new/disappearing/merge/split medical matching | CXR token interface 与 assignment-only identification |
| [OTCHA, MICCAI 2026](https://arxiv.org/abs/2606.19838) | medical multi-view token OT、conditional dustbin | temporal entity identity、directional null 与 B4 |
| [PRIMA/SQuARE](https://arxiv.org/abs/2412.15209) | compact cross-image relational tokens | persistent identity/null 和严格 64-token matched control |
| [Delimiter Token Scaling, ICLR 2026](https://openreview.net/forum?id=7QFf05KrOm) | training-free image source separation | entity correspondence 而非只增强 image boundary |
| [Visual Symbolic Mechanisms, ICLR 2026](https://openreview.net/forum?id=3RQ863cRbx) | probe、mediation、binding intervention | longitudinal identity/null 的外部可控结构注入 |
| [BridgeVLM, ICML 2026](https://arxiv.org/abs/2606.11745) | structured causal tokens 注入 decoder | frozen decoder、local adapter、temporal partial assignment 与 B4 |

禁止声称：首个 longitudinal CXR VLM、首个 entity-aware comparative radiology、首个五类 progression/change grounding、首个 partial OT/dustbin、首个 medical token OT、首个 compact relational tokens、首个 multi-image leakage/attention-collapse 发现、首个 causal binding intervention。

## 4. ProTrans 数值级近邻核验

- 预训练：98,940 个 MIMIC-CXR + Chest ImaGenome 双时点样本；排除 MS-CXR-T 重叠。
- 配置：ViT-B/16、BioClinicalBERT、3 spatiotemporal blocks、12 heads、hidden size 768。
- MS-CXR-T：1,326 pairs、5 findings、3 progression classes、10-fold SVM；ProTrans 63.54，BioViL-T 59.02，MedST 61.12；text-prototype 65.81。
- ICG：10,679 train / 760 test，冻结 BioMistral-7B；Temporal-F1 0.238，对比 Libra 0.145。
- 消融：full 63.54；w/o state 60.64；w/o transition 53.65；w/o reconstruction 61.70；w/o bidirectionality 61.98。

因此 directional-transition、时间反转和双向重建必须作为强基线/组件；CAPES-CI 只有在它们之上证明 identity/null assignment 的额外受控效应才成立。

## 5. 方法学定义

### 5.1 Two-sided-null sub-stochastic transport

对 prior/current region mass `a,b`，真实实体 transport 为：

```text
P >= 0
P 1 <= a
P^T 1 <= b
death = a - P1
birth = b - P^T1
```

审计恒等式：

```text
prior mass   = persistent outgoing + death
current mass = persistent incoming + birth
```

禁止使用“mass-preserving unbalanced OT”这一矛盾表述。训练 relaxation 和推理 hardening 都要报告非负性、row/column residual、dustbin-to-dustbin=0 和目标值；learned path 不接收 `match_count`。

### 5.2 Assignment-independent 64-token control

固定布局：

```text
4 global/context + 28 entity + 28 relation/change + 4 neutral/reserved = 64
```

support allocator 只使用 frozen unary confidence、anatomy、validity 与稳定 source key，不读取 assignment、gold entity ID 或 progression label。B4a/B4b 共用同一 AllocationPlan。超过 28 个 source 时，前 27 个固定槽 + 1 个带 provenance/mass 的 overflow summary；禁止报错或静默截断。

relation candidate 对每个 prior source 计算 persistent/death 混合，对每个 current source计算 birth mass。entity 与 relation 共享同一 28-slot allocation，使 token count/order/mask 不因 assignment 改变。

### 5.3 Frozen-VLM transfer

64 个 projected embeddings 必须精确替换 prompt 中连续 64 个 placeholder；显式保存 placeholder mask、attention mask、position IDs/M-RoPE、projector hash 和 frozen-parameter audit。端到端 gate 不传 `pixel_values`，不能回退 raw-image smoke。主指标由五个允许答案字符串的 normalized sequence log-likelihood 得到，generation/parser 只作附加 smoke。

## 6. 可识别实验

### 6.1 Persistent identity B4

- B4b：oracle persistent endpoints。
- B4a：anatomy-compatible、zero-fixed-point endpoint derangement。
- birth/death 集合保持不变；null-specific effect 在独立实验中检验。
- 保持相同 feature multiset、selected support、token types/count/order、valid mask、projector/head、initialization、optimizer、training steps、prompt 和 decoding。
- 每病例使用多个预注册 derangement seeds。

主终点：

```text
Delta_bind = macro Change F1(B4b) - macro Change F1(B4a)
```

成功门槛候选：点估计至少 +5 percentage points 且 patient-cluster 95% CI 下界 > 0；最终最小相关效应在未揭示 test 前由 pilot/power 冻结。

### 6.2 Learned recovery

```text
Recovery = (M_learned - M_B4a) / (M_B4b - M_B4a)
```

oracle gap 的 CI 必须完全大于 0，否则 recovery 不定义。`>=0.60` 为可行，`>=0.70` 为强成功，`<0.40` 硬降级，`0.40–0.60` 只允许一次预注册 rescue。

learned binder 训练禁止读取 oracle match 数、gold assignment cardinality、test bbox/progression 或 oracle-derived top-K support。oracle 只作上界和 sealed evaluation。

## 7. 强基线和关键消融

必跑类别：

1. current-only、equal-budget prior/current concat、average/difference pooling、uniform/random pooling；
2. ProTrans-style directional transition、Med-ST/MLRG/Libra 中至少可合法复现的强纵向基线；
3. cosine Hungarian+reject、balanced Sinkhorn、SuperGlue-style dustbin、feasible POT、OTCHA-style hub/dustbin（可实现等价版并标明）；
4. delimiter scaling、independent Q-Former/Perceiver compression；
5. oracle、anatomy deranged、wrong-anatomy、random endpoint、null-count-preserving shuffle。

关键消融：no identity、no null mass、no change token、no direction、no cycle/reverse、learned vs deterministic allocator、32/64/96 token budget、projector depth、second encoder/VLM transfer。

行为干预：assignment swap、null deletion、time-order swap并同步标签映射、relevant/irrelevant occlusion、same-label patient swap。仅 probe 可读性不能作为机制结论。

## 8. 正式会议 gate

| 要求 | ICLR/CVPR/AAAI 对应 | 本项目验收证据 |
|---|---|---|
| 新知识而非应用堆表 | [ICLR 2026 Reviewer Guide](https://iclr.cc/Conferences/2026/ReviewerGuide) | assignment-only effect + learned recovery + transfer 三段证据 |
| novelty 与 impact，不只 SOTA | [CVPR 2026 Reviewer Guidelines](https://cvpr.thecvf.com/Conferences/2026/ReviewerGuidelines) | 可视化 transport/null、干预曲线、外部泛化 |
| significance、soundness、broad AI relevance | [AAAI main technical track](https://aaai.org/conference/aaai/aaai-26/main-technical-track-call/) | CXR 作为严格 testbed，给出可迁移 relational tokenizer 原理 |
| reproducibility | 三会共同要求 | fixed config、hash、environment、失败 run、test-once seal、代码与统计脚本 |
| responsible research | 三会共同要求 | DUA/credential/IRB/再分发边界、patient split、泄漏审计、failure analysis |

AAAI-27 的 abstract/full 截止为 2026-07-21/07-28，当前不具备跳过合法数据、test-once 和多种子门槛的条件；不得为赶窗口制造不完整正式证据。

## 9. 当前 GO/NO-GO

- `GO_METHOD_CANDIDATE_CAPES_CI_V1`
- `GO_IMPLEMENT_SOFT_NULL_ALLOCATOR_AND_VLM_INJECTION`
- `GO_USE_RETAINED_ALLOCATION_4161_WITH_CHILD_STEPS_ONLY`
- `NO_GO_FORMAL_TEST_REVEAL`，直到许可、lineage、split、power 和 survival gate 全部通过
- `NO_GO_MAIN_CLAIM`，直到真实 gold B4、learned recovery、frozen-VLM transfer 和关键消融均有正式多种子证据

## 10. 查新过程限制

核心主张均进行了多组不同检索式和独立 reviewer red-team。当前环境未提供 `novelty-check` 所期望的跨模型 `mcp__codex__codex` 工具，OpenReview 个别全文受到 browser challenge；本报告没有冒充完成该特定工具审查，而以可访问的一手论文/会议页、独立高推理智能体与主线程逐项核验替代。对应 query/trace 保存在 `.aris/traces/novelty-check/2026-07-19_run01/`。
