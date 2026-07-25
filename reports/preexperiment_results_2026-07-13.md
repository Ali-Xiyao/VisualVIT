# VisualVIT 路线 C 预实验结果报告

**日期**：2026-07-13  
**结论**：`GO_NONCONFIRMATORY_COMPONENT_SMOKE_ONLY + NO_GO_FORMAL_DATA/LICENSE/ETHICS/ORACLE + NO_GO_END_TO_END_TRANSFER + NO_GO_PHASE_II`  
**证据等级**：全部为 `NON_CONFIRMATORY_PROXY`，不得用于论文正式主张。

## 1. 总结

关键组件已经分别完成 smoke：hard null/dustbin assignment、固定 64-token hard assembler、B4 fixture/实际训练契约审计、三种子 synthetic relation-token learnability、BiomedCLIP patch encoder、Qwen2-VL 原始双图接口、MIMIC 官方 train 的患者互斥 proxy manifest 与真实图像 feature/classifier。尚未跑通 `soft MatchGraph -> global allocator -> 64 tokens -> projector/position/attention adapter -> frozen Qwen2-VL` 端到端链路。

环境边界：本轮使用系统 Python 3.12 与已安装包，版本已经快照，但尚未建立正式隔离 venv/完整 lock；当前 E 工作区也不是 Git 仓库。因此它满足工程资格，不满足正式 Phase I 的代码/环境冻结标准。

结果同时给出一个明确停止信号：真实 MIMIC report-derived study-level proxy 的 raw correct-minus-same-view-deranged 均值为 `+4.29 ± 10.31` 点，但 seed 43 的 deranged 条件未收敛，因此该 aggregate 被 convergence gate 判为 `INVALID_FOR_PAIRING_EFFECT_INTERPRETATION`。现阶段不能声称真实 identity binding 信号已经成立。

## 2. Gate 结果

| Gate | 结果 | 关键证据 |
|---|---|---|
| Q0 环境/资产 | PASS | 2×RTX 3090 空闲；F 安全预算约 153.75 GiB；本轮无需下载 |
| Q1 schemas/masks | PASS | 最终测试集 21/21 PASS |
| Q2 hard null/dustbin transport | PASS-BLOCK | hard real-real/death/birth 合法；fractional plan 被显式拒绝，soft allocator 尚未实现 |
| Q3 fixed token budget | PASS-BLOCK | 4+28+28+4=64 的小规模 hard fixture 通过；>28 输入显式报错，全局 allocator 尚未实现 |
| Q4 B4 fixture/training audit | PASS for synthetic only | 两份独立 input checksums、marginals、token layout、实际初始化与训练 contract 相同；assignment 不同 |
| Q5 synthetic learnability | PASS | 3/3 seeds；独立第二进程 aggregate 精确一致 |
| Q5b BiomedCLIP smoke | PASS | strict 150/150 keys；patch shape [2,196,768]；repeat diff=0 |
| Q6 raw Qwen2-VL interface | PASS after audited adapter revision | 2B/7B 离线双图与严格输出 adapter 通过；没有 64-token 注入，不是 end-to-end transfer |
| Q7 MIMIC proxy manifest | PASS | 240 pairs/240 patients，official train only，train/dev patient-disjoint |
| Q8 MIMIC real-image proxy | FAIL_CONVERGENCE_GATE | seed 43 deranged 未收敛；raw aggregate 不可解释，不能解锁 claim |

## 3. Synthetic mechanism pilot

配置：128 train、64 dev、seeds 17/29/43，CPU；learned projection 使用 synthetic oracle cardinality 与 assignment supervision。

| Seed | B4a deranged F1 | B4b oracle F1 | Learned proxy F1 | Delta_bind (pp) | Recovery | Matcher acc. |
|---:|---:|---:|---:|---:|---:|---:|
| 17 | 0.5940 | 0.9984 | 0.9984 | 40.4464 | 1.0000 | 1.0000 |
| 29 | 0.6057 | 0.9984 | 0.9984 | 39.2784 | 1.0000 | 1.0000 |
| 43 | 0.6250 | 0.9984 | 0.9984 | 37.3408 | 1.0000 | 1.0000 |
| Mean ± SD | 0.6082 ± 0.0157 | 0.9984 ± 0.0000 | 0.9984 ± 0.0000 | 39.0219 ± 1.5687 | 1.0000 ± 0.0000 | 1.0000 ± 0.0000 |

修复审计缺口后，relation classifier 从固定 64-token bundle 的 relation slice 取输入；B4a/B4b 的实际初始化、optimizer、steps、seed 与 training contract 纳入审计，独立重跑 aggregate 逐值相同。它仍未使用 global/entity tokens 或 Qwen projector，因此只证明 synthetic relation slice 可学习，不证明完整 64-token VLM 架构或医学效应。

证据：

- `F:\VisualVIT_runtime\050_routeC\runs\pilot_synthetic_auditfix_20260713`
- `F:\VisualVIT_runtime\050_routeC\runs\pilot_synthetic_auditfix_rerun_20260713`

## 4. BiomedCLIP encoder smoke

- 权重：VIVID converted BiomedCLIP ViT-B/16；
- SHA-256：`3be6f957b2fc8b8324cc6ed6faebdcb218511b41fc0f542312e21850424a2590`；
- strict load：150/150 keys；
- 输出：`[2,197,768]`，patch `[2,196,768]`；
- finite：是；
- 两次 forward 最大绝对差：0；
- 两次 forward：0.624 s；
- peak VRAM：373,980,160 bytes。

证据：`F:\VisualVIT_runtime\050_routeC\runs\encoder_smoke_20260713T122945`

## 5. Qwen2-VL 双图接口

首次严格提示要求原始输出匹配 `^ANSWER: ...$`。2B 和 7B 都完成双图生成，但都输出裸标签 `improved`，因此原始两次运行按协议保留为 schema FAIL。

随后在非确认性阶段冻结严格 adapter：

`^(?:ANSWER:\s*)?(new|resolved|worse|improved|stable)$`

adapter 只接受五个精确标签，可有或没有字面前缀，并 canonicalize 为 `ANSWER: <label>`；任何解释、标点、未知/多标签文本都抛错，不存在默认类别回退。对应单测 8 个 adapter case 全部通过。

该 smoke 使用 Qwen 原始双图 pixels；它没有注入 MatchGraph 的 64 个 relation tokens，也没有验证 projector、M-RoPE/position ids 或 attention mask，因此只证明原始多图接口与输出 parser 可用。

| Model | Images | Raw | Canonical | Peak VRAM | Final status |
|---|---:|---|---|---:|---|
| Qwen2-VL-2B | 2 | improved | ANSWER: improved | 4,556,014,592 B | PASS |
| Qwen2-VL-7B | 2 | improved | ANSWER: improved | 16,867,590,144 B | PASS |

证据：

- `F:\VisualVIT_runtime\050_routeC\runs\qwen2vl_2b_attempt2_20260713`（原始 schema FAIL）
- `F:\VisualVIT_runtime\050_routeC\runs\qwen2vl_7b_attempt1_20260713`（原始 schema FAIL）
- `F:\VisualVIT_runtime\050_routeC\runs\qwen2vl_2b_adapter_20260713`
- `F:\VisualVIT_runtime\050_routeC\runs\qwen2vl_7b_adapter_20260713`

## 6. MIMIC 240-patient proxy

数据全部来自 MIMIC official train。Pleural Effusion 标签为报告自动抽取的 study-level CheXpert 标签；报告文本没有进入模型。

| Proxy class | Train | Dev |
|---|---:|---:|
| new (0->1) | 60 | 20 |
| resolved (1->0) | 60 | 20 |
| stable-positive (1->1) | 60 | 20 |
| Total | 180 | 60 |

资格检查：

- 240 pairs = 240 unique patients；
- train/dev patient-disjoint；
- prior/current 不同日期、相同 AP/PA view；
- official validate/test 未读取；
- uncertain `-1` 与缺失标签均 mask；
- 480/480 图像存在；
- manifest SHA-256：`341465b486a4359227bb9d4990278fbf91b682674ffdf473f2d0813b207ad438`。

证据：`F:\VisualVIT_runtime\050_routeC\data\mimic_proxy_manifest_240_20260713`

## 7. 真实图像 proxy 分类结果

BiomedCLIP CLS feature，480 unique images；3 seeds。correct-pair 与 deranged-pair 使用相同 203,011 参数、相同训练步数/优化器/初始化；derangement 只保证同 AP/PA view、无 fixed point 和 current feature multiset 相同，不能称 anatomy-compatible。current-only 只有 50,947 参数，仅作非 compute-matched 诊断。

| Seed | Current-only F1 | Correct pair F1 | Deranged pair F1 | Correct - deranged (pp) |
|---:|---:|---:|---:|---:|
| 17 | 0.5249 | 0.4244 | 0.3847 | +3.9660 |
| 29 | 0.4764 | 0.3429 | 0.4014 | -5.8528 |
| 43 | 0.4616 | 0.4959 | 0.3484 | +14.7591 |
| Mean ± SD | 0.4877 ± 0.0331 | 0.4211 ± 0.0766 | 0.3782 ± 0.0271 | +4.2908 ± 10.3098 |

### 观察

1. seed 43 的 deranged train F1=0.4705、loss=0.8739，未达到 train F1>=0.95 且 loss<=0.20 的 convergence gate；其 `+14.76 pp` 强烈驱动 raw 均值。
2. 因至少一个 paired condition 未收敛，`+4.29±10.31 pp` aggregate 无效，不解释为正向或负向 binding signal。
3. correct-pair 平均比 current-only 低 6.66 个点；180 个训练病例对 203k 参数的 pair head 存在明显过拟合风险。
4. 全局 CLS + report-derived finding 不是 entity/oracle 标注，无法直接检验 CAPES 的 region identity 假设。

### 解释边界

这不是 C1 的负面正式结论，因为数据、表示、标签与收敛都不满足正式 B4 条件；它只能作为停止信号。当前正确动作是保持正式 claim 封存，补合法 oracle、region encoder、global allocator 与 soft/end-to-end adapter，而不是扩大同一 proxy 的 seed 或数据规模来追显著性。

证据：

- 原 convergence-gated run：`F:\VisualVIT_runtime\050_routeC\runs\mimic_proxy_biomedclip_convergence_gate_20260713`；
- 将 gate 提取为可单测纯函数并收紧 strict parser 后的 current-code rerun：`F:\VisualVIT_runtime\050_routeC\runs\mimic_proxy_biomedclip_convergence_gate_unitfix_20260713`；raw 指标逐值相同，仍为 `FAIL_CONVERGENCE_GATE`。

## 8. 当前下载/授权需求

本轮预实验不需要下载，已经全部使用本地资产完成。

进入正式 Phase I 前需要：

1. **RAD-DINO inference weights**：约 346 MiB，可公开下载，写入 F，不写 H；
2. **CheXTemporal gold progression/bbox metadata**：文件很小，但父图像分别受 CheXpert/MIMIC/ReXGradient 协议约束；
3. **Chest ImaGenome annotations**：需要用户确认 PhysioNet credential、CITI 与 DUA；annotations 不能替代父图像授权。

在 credential/CITI/DUA、IRB/豁免、派生物再分发边界、CheXTemporal/Chest ImaGenome ontology/ID join 与 oracle lineage 未闭合前，正式 B4/E1 继续 NO-GO。

## 9. 下一步建议

- 先完成 deterministic global allocator、fractional soft allocator 与 MatchGraph-to-Qwen 64-token 注入 adapter；当前组件 smoke 不等于端到端。
- 获取/确认 CheXTemporal + Chest ImaGenome 权限与 gold ID，下载 RAD-DINO，建立 region-level oracle qualification。
- 在正式 gold 到位前，不继续扩大当前 240-pair CLS proxy；若要做一次预注册 rescue，应改为低容量 linear/head + region/patch pooling，而不是追加 seed。
- 所有 E1/E2/E3 方法以及 F140 external dataset/protocol/metric/adaptation policy 必须先冻结，再一次性 internal test reveal；external test 仅允许独立 custodian 用 IDs/非 outcome hashes 做去重，标签与指标继续封存。
- formal test、正式 seed bank、patient×seed bootstrap、external replication 与 Phase II 仍保持封存。
- 正式 Phase I 前还必须创建隔离环境、完整依赖 lock 和版本化代码快照，然后重跑 Q1–Q8。

## 10. 复现与证据包

- 精确复跑命令：`E:\Xiyaowang\050_VisualVIT\reports\preexperiment_commands_2026-07-13.md`；
- 统一证据 manifest：`F:\VisualVIT_runtime\050_routeC\evidence\preexperiment_evidence_manifest_20260713.json`；
- manifest 共登记 77 个 workspace/runtime/model 文件，`missing=0`，并包含 BiomedCLIP 权重与 Qwen2-VL 2B/7B 全部模型分片 SHA-256；
- 最终轻量测试在新一轮调用中为 `21 passed`；fixed/versioned plan 与 tracker 分别保持逐字节一致。

证据 manifest 的文件级 SHA-256 在最终交付消息中报告，避免把自身哈希回写进被哈希文件造成递归失效。
