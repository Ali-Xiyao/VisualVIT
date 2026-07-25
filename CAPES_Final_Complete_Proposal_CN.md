---
title: "CAPES (Final) — Diagnosing and Repairing the Relational Blind Spot of Longitudinal Medical VLMs"
aliases:
  - CAPES Final
  - Change-Aware Persistent Entity Slots
  - Relational Blind Spot
  - Finding + Method
tags:
  - research/proposal
  - medical-ai
  - vlm
  - visual-tokenizer
  - longitudinal-cxr
  - oral-target
status: proposal-final-merged
version: final (merged v1 + v2 + v3)
updated: 2026-07-05
target: CVPR / AAAI oral · TMI landmark
merges: Change_Aware_Persistent_Entity_Slots_Proposal_CN.md (v1) · CAPES_v2_VisualSide_Proposal_CN.md (v2) · CAPES_v3_Finding_and_Method_Proposal_CN.md (v3)
---

# CAPES — Change-Aware Persistent Entity Slots
## Diagnosing and Repairing the Relational Blind Spot of Longitudinal Medical VLMs
### 最终完整版（合并 v1 方法/实验深度 + v2 视觉侧收窄 + v3 发现↔方法双核）

> [!summary] 双主贡献快照（发现 + 方法，缺一不可）
> - **发现（Finding）**：单图 VLM 文献已证明瓶颈在"视觉→语言的交接"(编码器有信息、LLM 用不上)。我们证明**纵向/比较**体制里存在一个**性质不同、更严重**的失败模式——模型需要的是**跨检查实体对应(cross-study entity correspondence)**,这是**关系型信息**,在"每张图独立 token 化"的接口里**不可访问地缺失(structurally inaccessible)**。因此**再大的 LLM、再多的 token、再强的单图编码器都补不回来**。
> - **方法（Method）**：Change-Aware Persistent Entity Slots(CAPES)——一个**把这份缺失的关系信息重新注入视觉 token**的 tokenizer:把同一解剖实体在 prior/current 绑定成**跨检查持久槽 + 显式 change token**,作为**冻结 VLM** 的即插视觉接口,在**固定 token 预算**下部署,单卡可跑。
> - **为什么二者缺一不可(本文的因果闭环)**:发现预测"只注入对应关系就能补上、注入其它一切(更多 token/监督/更强编码器)都不能";方法就是那次**因果干预**。**方法奏效 = 发现被证明**。发现让方法从"更好的接口"升格为"某个结构性信息缺口的必要修复";方法让发现从"诊断"升格为"诊断 + 可部署的治疗"。
> - **一句话 thesis**:*Longitudinal VLMs fail not because the language model cannot reason, but because cross-study correspondence is never written into the visual tokens — we prove this causally and put it back with a frozen-LLM, fixed-budget tokenizer.*
> - **目标**:CVPR / AAAI **oral**,TMI **标杆论文**。共同核心 + venue 分叉(§12)。
> - **纪律**:Week-2 oracle kill test + 星标 B4b−B4a 决定 go/no-go;learned matcher 恢复率决定是否降级为纯诊断/upper-bound 论文(仍可发)。

---

## 版本沿革与合并说明（读者须知）

本文件是把三份历史提案**合并成一份自洽的最终提案**,已消除所有"见 v1 / 承 v2"式跨版本引用,可独立阅读。三版脉络:

| 版本 | 主贡献定位 | 体质 | 本文如何吸收 |
|---|---|---|---|
| v1 | "纵向医学 VLM 的 token 接口方法" | poster | 保留其**方法数学、完整实验协议、图表模板、审稿模拟、伦理/复现、附录** |
| v2 | "VLM 视觉侧 visual tokenizer 方法"(补齐 Libra/Slot-MLLM 区分、加干净对照、诚实化 token 预算叙事) | 好 poster | 吸收其**视觉侧收窄、Slot-MLLM/Libra 区分、supervision-matched 干净对照、等预算接口归纳偏置的诚实叙事** |
| **v3** | **"发现 + 方法"双主贡献:诊断出新失败模式(关系信息结构性缺失)+ 注入式修复,方法奏效即发现的因果证明** | **oral 体质** | 作为**框架主脊**:因果闭环、关系信息形式化、B4a/B4b 星标对照、scaling null、correspondence probe、CVPR/AAAI/TMI 分叉 |

**引用真实性(2026-07-05 已核实,沿用 v3 的核实状态,本次合并未重新联网核实)**:CheXTemporal(2605.11304)、TRACE(2602.02963)、MedReCo(2606.06407)、Libra(2411.19378)、Slot-MLLM(2505.17726)、CORE(2511.14072)、Diagnosing Bottlenecks(2510.21740)、LLMs Can Compensate(2506.05439)、Semantic Alignment for MLLMs(2408.12867)、Slot Attention(2006.15055)、RAD-DINO(2401.10815)、Chest ImaGenome(2108.00316)、MS-CXR-T/BioViL-T、CheXRelNet(2208.03873)、MAIRA-2(2406.04449)、LLaVA-Med(2306.00890)、MANTIS(2405.01483)、CLIP4IDC(2206.00629)均已核实存在。**Med-MIM(2505.19031)投稿前仍需自行复核标题/作者/ID。STAND(2604.23309)、VIDIC(video difference captioning 2025)在最终定稿前建议再复核。**

---

## 导航
- [[#1. Executive Summary]]
- [[#2. One-Page Proposal]]
- [[#3. 核心论证:发现↔方法的因果闭环]]
- [[#4. Introduction:背景、动机、Research Gap]]
- [[#5. Literature Map(2026-07 重新调研,含瓶颈诊断线)]]
- [[#6. Problem Definition & 关系信息的形式化]]
- [[#7. Research Questions & Hypotheses]]
- [[#8. Related Work & Differentiation]]
- [[#9. Method — CAPES 作为"可探针、可部署"的注入]]
- [[#10. Experimental Protocol — 把方法设计成发现的因果证明]]
- [[#11. Contributions(双主贡献 + 互为必要)]]
- [[#12. Venue 分叉:CVPR / AAAI / TMI]]
- [[#13. Feasibility]]
- [[#14. Risks & Kill Criteria]]
- [[#15. Ethics, Safety & Reproducibility]]
- [[#16. Timeline & Milestones]]
- [[#17. Figure Plan]]
- [[#18. Main Tables]]
- [[#19. 审稿模拟(CCF-A / oral committee)]]
- [[#20. Go / No-Go Checklist]]
- [[#21. References(已核实)]]
- [[#Appendix A. 分 venue 一句话定位]]
- [[#Appendix B. Implementation Pseudocode]]
- [[#Appendix C. Data Verification Checklist]]
- [[#Appendix D. Error Taxonomy Annotation Sheet]]
- [[#Appendix E. Proposal Self-Score Rubric]]

---

## 1. Executive Summary

放射科医生读片几乎从不孤立看单图:他们比较 prior/current,判断同一病灶是 **new / worse / stable / improved / resolved**。当前纵向医学 VLM 处理 prior/current 有两条主流:(a) **每图独立 token 化后拼接**(含多图 instruction tuning,如 Med-Mantis 路线);(b) **dense temporal 融合**(如 Libra 的 Temporal Alignment Connector)。两者共享一个隐蔽缺陷:送进 LLM 的视觉 token **不携带"prior 的 left lower lung 与 current 的 left lower lung 是同一临床实体"这一对应关系**。

**发现(Finding)**:这不是"LLM 不会推理",也不是单图文献所说的"信息在编码器里、handoff 丢了"。这是一个**更根本的失败模式**——跨检查对应是**关系型**的,在"每图独立 token"接口里**根本没被计算、没被写入**,因此**线性探针从拼接 token 里读不出它**(与单图空间信息可被线性探出形成鲜明对照),而且**放大 LLM / 增加 token / 换更强单图编码器都无法恢复**。这三类可观测后果就是临床关键错误:

1. **Wrong-time**:把 prior 中已存在的病灶误判为 current 新发,或把 current 变化归因到 prior。
2. **Wrong-side / wrong-region**:左右侧或解剖区域混淆。
3. **Unsupported-change**:生成 "worsened / improved / resolved" 等变化结论,但没有对应视觉证据。

**方法(Method)**:Change-Aware Persistent Entity Slots(CAPES)——一个把这份缺失关系信息**重新注入**的视觉 tokenizer:把同一实体在 prior/current **绑定成跨检查持久槽**,再为每槽生成**显式 change token**,在**固定 LLM 视觉 token 预算**下替代拼接/融合,LLM 全程冻结,单卡可跑 MVP。

**因果闭环**:若发现为真,则"**只注入对应关系**"应补上大部分差距,而"注入其它一切"(更多 token、更多区域监督但不配对、单图 slot、dense 融合、更大 LLM)都不应。CAPES 就是这次干预;**它奏效,发现即被证明**。第一阶段做 oracle kill test + 星标对照(配对 vs 不配对),不成立即停或转为纯诊断论文(仍可发表)。

---

## 2. One-Page Proposal

### 2.1 题目(主 + 备选见 Appendix A)
**Change-Aware Persistent Entity Slots: Diagnosing and Repairing the Relational Blind Spot of Longitudinal Medical VLMs**

### 2.2 双主贡献
1. **发现**:纵向 VLM 的失败是"跨检查对应关系在视觉 token 接口中结构性缺失",区别于单图 handoff 瓶颈,且 scaling 不可修复(因果 + 探针证据)。
2. **方法**:CAPES,一个把该关系信息注入冻结 VLM 的固定预算 tokenizer,恢复大部分 oracle 上界,单卡可部署。
3. **互为必要**:方法的因果成功 = 发现的证明;发现赋予方法必要性;二者合成一个闭环,而非两个拼贴。

### 2.3 唯一战场
> 冻结 LLM、固定视觉 token 预算下,**视觉 token 是否编码了跨检查实体对应**,是否是纵向推理的决定性变量;把它显式注入能否因果性地消除 wrong-time / wrong-side / unsupported-change,而更多 token / 监督 / 更大 LLM 不能?

### 2.4 与最近邻边界(§8 详述)
- **vs 单图瓶颈诊断线**(Diagnosing Bottlenecks / R-Probe / VLMs-are-blind):它们是**单图 handoff**(信息在、读不出);我们是**跨图关系**(信息从未被写入)——**不同失败模式**。
- **vs 已注意到"per-image token 缺跨图对齐"**(Semantic Alignment for MLLMs 2408.12867、MiCo):他们把它当**训练/数据/查询引导**问题;我们把它当**信息缺口**做**因果 + 探针**的机制性证明,并给出结构性注入。
- **vs Slot-MLLM / CORE**(通用单图 object-centric token):我们是**跨检查、身份持久、带显式变化**的槽。
- **vs Libra**(dense temporal connector):我们是**可枚举、身份显式、固定预算、change token 可消融**,并证明"显式绑定"优于"dense 融合"。
- **vs MedReCo / TRACE**:他们是大规模能力 / 联合解码;我们是**公开数据、可复现、机制性**的诊断 + 修复。

### 2.5 Research Questions(全表见 §7)
- **RQ-F1(发现)**:纵向失败是否**不是** LLM 推理力问题?
- **RQ-F2(发现)**:跨检查对应是否**探不出**拼接 token,而单图空间信息探得出?
- **RQ-F3(发现)**:放大 LLM / 加 token / 换强编码器是否**都补不回来**?
- **RQ-M1(方法)**:等预算下,注入对应(oracle 持久槽)是否优于 patch-concat / 单图 slot / Libra 融合 / TRACE-concat?
- **RQ-M2(方法,星标)**:同样 oracle 区域框下,"**配对**"是否显著优于"**不配对**"?(绑定是否为活性成分)
- **RQ-M3(方法)**:learned cross-study matcher 能否恢复 oracle 收益 60–70%?
- **RQ-M4(方法)**:显式 change token 是否进一步降 wrong-time / unsupported-change?

### 2.6 实验骨架(§10)
- **数据**:CheXTemporal(首选,finding-level 5 类)+ Chest ImaGenome / MS-CXR-T(anatomy-level MVP fallback)+ Med-MIM(二阶段外部验证);**CVPR 分叉加通用域 change captioning / video difference**。
- **因果对照谱系**:current-only / patch-concat / **框但不配对(B4a)** / **框且配对=oracle 槽(B4b,星标)** / 单图 slot / Libra 融合 / TRACE-concat / random / wrong-anatomy / learned / ±change / **LLM 放大 null 实验** / **线性探针可读性**。
- **指标**:Change F1、Anatomy/Finding 证据、Wrong-Time/Side/Region、Unsupported-Change、Order-Sensitivity、**correspondence probe accuracy**、端到端 FLOPs/latency、trainable params。

### 2.7 主风险(§14)
learned matcher 恢复不了 oracle,或 B4b≈B4a(绑定非活性成分)。前者 → 降级为"发现 + oracle 上界 + 探针 + scaling null"的诊断论文(仍可发);后者 → 发现证伪,停或 pivot。

---

## 3. 核心论证:发现↔方法的因果闭环

这是全文的脊柱,写作时应作为 Introduction 的主线。

```text
(1) 观察   纵向 VLM 系统性犯 wrong-time / wrong-side / unsupported-change
                     │
(2) 定位   这不是 LLM 推理力问题,也不是单图 handoff(信息在编码器、读不出);
           线性探针显示:单图空间信息可读,但"跨检查对应"从拼接 token 里读不出
                     │
(3) 归因   因为对应是"关系型",在每图独立 token 化时从未被计算/写入
           → 预测:放大 LLM / 加 token / 换强编码器都补不回来
                     │
(4) 预言   若归因成立,"只注入对应关系"应补上大部分差距;
           "注入其它一切"都不应 —— 这是可证伪的
                     │
(5) 干预   CAPES = 把对应关系写进 token 身份(oracle→learned)
                     │
(6) 证明   ✓ oracle 配对补上差距;✗ 框但不配对(B4a)不补;✗ 更多 token 不补;
           ✗ 单图 slot 不补;✗ dense 融合部分补;✗ 更大 LLM 不补;
           learned 恢复大部分;跨数据集/跨域成立;探针在注入后可读
                     │
(7) 闭环   方法奏效 ⇔ 发现为真。二者缺一不可。
```

**为什么这个闭环是 oral 体质**:
- 它是**概念贡献**(一个新失败模式 + 一条"关系信息 vs 单图信息"的清晰界线),不是方法微调;
- 它先接上社区已在乎的瓶颈问题,再说一句**反直觉、可证伪、且被证明**的新话("scaling 补不回来,便宜的上游注入能");
- 它的证明用的是 interp 社区当下最认的**因果干预 + 探针**;
- 修复**冻结 LLM、便宜、可部署**,不是只做个诊断就走。

---

## 4. Introduction:背景、动机、Research Gap

### 4.1 Background
医学影像诊断通常不是孤立图像理解任务。在放射学工作流中,医生会结合 prior/current studies,判断同一解剖区域或病灶的变化——新发、恶化、稳定、改善或消退。对于胸片,纵向比较尤其常见:治疗是否有效、病灶是否进展、是否出现新异常,往往依赖对同一 anatomical finding 的跨时间比较。

与此同时,医学 VLM 已从单图问答、报告生成扩展到多图推理。Med-MIM / Med-Mantis 等开始覆盖医学多图 temporal understanding、comparison、co-reference;TRACE、CheXTemporal 等近期工作强调 temporal change 与 spatial grounding 的结合;Libra 在视觉侧用 Temporal Alignment Connector 融合 prior/current。然而,主流多图输入接口仍停留在 **image-/patch-level token concatenation** 或 **dense 融合**:模型可以接收多张图,但 visual tokens 缺少稳定的跨检查实体身份。

### 4.2 Motivation
在纵向医学推理中,错误往往不是语言模型不会表达,而是视觉接口没有把比较对象组织好。设想模型需要回答:

> "Compared with the prior study, has the left lower lung opacity worsened?"

如果视觉 token 只是 prior patches + current patches 的拼接,LLM 必须**隐式**完成三步高风险推理:

1. 找到 current left lower lung;
2. 找到 prior left lower lung;
3. 判断二者是否为同一临床实体,并比较其变化。

对有限数据、有限算力、轻量微调的医学 VLM,这三步并不稳:模型可能把 prior 的 finding 当成 current 的 new finding(wrong-time),或把左侧异常和右侧区域混淆(wrong-side);若最终答案没有明确 evidence region,还可能输出 unsupported-change。

**关键洞察(本文的升级)**:上面第 3 步——"跨检查实体对应"——不是 LLM 推理力不足,而是**这份信息在"每图独立 token 化 + 固定预算"之后,已不再以可访问的形式存在于视觉接口里**。它是**关系型 / 组合型**的,需要在两张图之间求解一个(近似)指派问题;当两张图各自独立 token 化,这个指派**从未被计算,也从未被写入任何 token**。这使纵向失败区别于单图文献所诊断的 handoff 瓶颈(信息在编码器里、只是 LLM 读不出)。

### 4.3 Research Gap
已有工作的 gap 不在于"没人研究 temporal radiology",而在于:

1. **医学多图 instruction tuning**(LLaVA-Med / MANTIS / Med-MIM)让模型看多张图,但不显式约束 visual token 的跨图实体身份;
2. **Temporal CXR classification**(CheXRelNet / MS-CXR-T)能预测 improved/worsened/stable,但不研究 VLM 的 visual token interface;
3. **Grounded / temporal report generation**(MAIRA-2 / TRACE)能输出定位,但从解码器侧出发,不把"同一实体跨 prior/current 的 persistent slot"作为受控研究对象;
4. **Entity-aware comparative radiology**(MedReCo)已提出大问题 framing,但尚未回答:在同等 token budget 下,persistent entity slots 是否比 patch concat 更适合作为 VLM 输入接口,以及**收益到底来自"身份绑定"还是别的**;
5. **单图瓶颈诊断线**(Diagnosing Bottlenecks / LLMs Can Compensate / VLMs-are-blind)只诊断了**单图 handoff**,没有指出**纵向体制是一个不同且更严重的失败模式**。

因此,本研究的 gap 是一个**受控、可证伪、且带机制解释**的问题:

> 冻结 LLM、固定视觉 token 预算下,**视觉 token 的"跨检查实体对应"本身**是否是纵向推理的决定性变量;把它显式注入能否因果性地消除 wrong-time / wrong-side / unsupported-change,而更多 token / 监督 / 更大 LLM 不能?——且这一失败模式**区别于**单图 handoff 瓶颈。

---

## 5. Literature Map(2026-07 重新调研,含瓶颈诊断线)

> 本节所有条目均在 2026-07-05 联网核实(沿用 v3 状态)。arXiv ID 与标题一致者标 ✅;未独立复核者标注。

| 方向 | 代表作 | 已解决什么 | 与 CAPES 关系 |
|---|---|---|---|
| **单图瓶颈诊断(发现的对照系)** | Diagnosing Bottlenecks 2510.21740 ✅;LLMs Can Compensate 2506.05439 ✅;VLMs are blind 2407.06581 ✅;R-Probe 2603.20020(待复核) | 证明**单图**任务瓶颈在 handoff(信息在编码器、LLM 读不出) | v3 指出纵向是**不同失败模式**(关系信息从未写入),据此推进这条线 |
| **跨图 token 独立的既有观察** | Semantic Alignment for MLLMs 2408.12867 ✅;MiCo 2506.22434(待复核) | 已指出"每图独立 token 化损害跨图关联" | **不能 claim first 注意到**;他们当训练/数据/查询问题,v3 当**信息缺口**做因果/探针 + 结构性注入 |
| 通用 object-centric tokenizer | Slot-MLLM 2505.17726 ✅;CORE 2511.14072 ✅;Slot Attention 2006.15055 ✅ | 单图、面向重建/生成/压缩的 slot token | 用它做 baseline 隔离"跨检查持久性"(B5) |
| 医学多图 VLM(隐式路线) | LLaVA-Med 2306.00890 ✅;MANTIS 2405.01483 ✅;Med-MIM 2505.19031(待复核) | instruction tuning 获得多图能力 | baseline / 二阶段外部验证 |
| **纵向医学 VLM(视觉侧最强竞品)** | **Libra 2411.19378 ✅**(RAD-DINO + TAC,ACL 2025 Findings) | 视觉侧融合 prior/current,CXR temporal report SOTA | **最强视觉侧 baseline**;证明显式绑定 > dense 融合 |
| temporal grounded generation | TRACE 2602.02963 ✅;MAIRA-2 2406.04449 ✅ | temporal+grounding 联合,change detection 为 emergent | 解码器视角 baseline |
| entity-aware comparative | MedReCo 2606.06407 ✅ | 大规模 entity-aware 比较,690K 多中心库 | 最大 novelty 压力;v3 收窄为机制性诊断 + 修复 |
| temporal 数据 | CheXTemporal 2605.11304 ✅;Chest ImaGenome 2108.00316 ✅;MS-CXR-T / BioViL-T ✅;CheXRelNet 2208.03873 ✅ | 数据源与 temporal benchmark | 首选/fallback/外部/classification baseline |
| 医学视觉编码器 | RAD-DINO 2401.10815 ✅;BioViL-T ✅ | 冻结 CXR encoder | 冻结 ROI encoder |
| 通用域 temporal/change(CVPR 分叉) | CLIP4IDC 2206.00629 ✅;STAND(遥感变化描述)2604.23309(待复核);Video Difference Captioning 2025(待复核) | 自然图/遥感/视频的 difference captioning | 跨域泛化实验落点 |

**关键相关工作深读**(写 Related Work 时展开):

- **CheXTemporal**:paired prior-current CXR,finding-level temporal/spatial annotations,五类 progression taxonomy(new/worse/stable/improved/resolved),含 gold + 280K silver。若可访问,应作**第一优先级数据源**。
- **Chest ImaGenome**:29 个 CXR 解剖位置、scene graph、bounding boxes、670K+ localized comparison relations。适合构建 anatomy-level persistent slots 与 temporal comparison labels;但许多标注来自自动 pipeline,**anatomy-level box ≠ finding-level pathology box**,须区分 Anatomy Evidence Acc 与 Finding IoU。
- **TRACE**:联合 temporal comparison、change classification、spatial localization,change detection 是联合学习的 emergent(>90% grounding acc)。架构偏 prior/current concat + grounded decoder,**必须实现 TRACE-style concat baseline**。
- **MedReCo**:把放射学比较定义为 entity-aware cross-image reasoning,690K 多中心库训练 entity-aware encoder + 生成式 VLM,longitudinal follow-up 大幅提升。**因此本文不能 claim "首次 entity-aware cross-image reasoning"**,应收窄为"冻结 VLM + 固定预算下的机制性受控研究"。
- **Libra**:RAD-DINO + Temporal Alignment Connector(Layerwise Feature Extractor + Temporal Fusion Module),视觉侧融合 prior/current。**closest related on visual side**:TAC 是 dense 融合,无显式实体身份 / 固定预算 / 独立 change token。

---

## 6. Problem Definition & 关系信息的形式化

### 6.1 任务
给定同患者 prior/current CXR 与可选问题 $q$:$x=(I^{prior},I^{current},q)$。$q$ 例如:"Has the left lower lung opacity worsened compared with the prior study?" / "Is the pleural effusion improved, stable, or worsened?" / "Which region supports the predicted progression?"

输出:
1. **Progression label** $z\in\{new,worse,stable,improved,resolved\}$(CheXTemporal 5 类;跨数据集主指标可退化为 3 类 improving/stable/worsening 以降标签噪声)。
2. **Evidence** $g=(r^{prior},r^{current},a)$:支持判断的 prior/current 区域与解剖/finding 实体。
3. **Optional constrained answer** $y$(第一阶段不做自由 report generation)。

**LLM 全程冻结**,唯一变量是"视觉 token 如何从两张图组织出来"。所有对照共享同一冻结 LLM、同一冻结 vision encoder、同一 LLM 视觉 token 预算。

**暂不研究**:自由报告生成、CT/MRI 全模态、临床部署、从零训练 VLM、语言侧微调(除对所有对照一致的轻量 projector / LoRA-on-projector)。

### 6.2 关系信息缺口(发现的形式化,注意不过度声称)
设任意**每图独立**的 tokenizer $T$ 产出 $T(I^{prior}),T(I^{current})$,拼接得 $V_{concat}$。跨检查对应
$$\pi^\ast:\ \{\text{prior entities}\}\to\{\text{current entities}\},\qquad \delta^\ast:\ \text{per-entity change}$$
是**图对**的函数,需要求解一个(近似)指派问题。

**精确表述(避免过度声称)**:$\pi^\ast$ 并非在信息论意义上从像素中消失,而是在**独立 token 化 + 固定预算**之后,**不再以可访问(cheaply/linearly decodable)的形式存在于 token 接口中**,且冻结 LLM 经验上无法恢复它。

- **与单图 handoff 的关键区别**:单图空间信息在编码器里**可被线性探出**(prior work),失败在下游解码;而跨检查对应在 $V_{concat}$ 上**探不出**——因为它是关系型、组合型的,从未被写入。→ **不同失败模式**。
- **CAPES 的作用**:显式计算 $\pi$ 并把它写进 token 身份 $a_k$,使对应在接口层**可访问**。

> **不确定性(显式标注)**:探针设计是真实方法学工作——"线性探针探不出对应"需谨慎设计(不能只用"最终答案不可线性读"这种平凡结论)。见 §10.6 的探针协议与其局限。

### 6.3 五个挑战
1. **Entity definition**:医学实体不是通用 object;第一阶段只做 anatomy/finding 槽,不做 device/report 实体。
2. **Cross-time alignment**:同区域跨时间会位移/形变/外观变化,cosine 易错配相邻区。
3. **Evidence granularity**:anatomy-level ≠ finding-level(left lower lung box 只能证明定位到解剖区,不等于定位到病灶本体),指标必须分开报。
4. **Causal attribution**:提升须归因于**身份绑定**,而非监督/算力/encoder → 星标对照 B4a/B4b。
5. **Novelty boundary**:不 claim first 注意到 per-image 独立(Semantic Alignment)、不 claim first entity-aware 比较(MedReCo)、不 claim first temporal connector(Libra)、不 claim first object-centric token(Slot-MLLM);claim 的是**因果诊断 + 结构性注入 + scaling null**。

---

## 7. Research Questions & Hypotheses

### 7.1 发现侧(诊断)
- **RQ-F1**:纵向失败是否**不是** LLM 推理力问题?(冻结 LLM + oracle 对应 → 若大幅修复,则语言侧非瓶颈)
- **RQ-F2**:跨检查对应是否**探不出** $V_{concat}$,而单图空间信息探得出?(可读性对照)
- **RQ-F3**:放大 LLM / 加 token / 换强编码器是否**都补不回来**?(scaling & capacity null)
- **H-F**:纵向失败的主因是"关系型对应在视觉 token 接口中不可访问地缺失",一个不同于单图 handoff 的失败模式。

### 7.2 方法侧(修复)
- **RQ-M1**:等预算下,注入对应(oracle 持久槽)是否优于 patch-concat / 单图 slot / Libra 融合 / TRACE-concat?
- **RQ-M2(星标)**:在**同样的 oracle 区域框**下,"**配对**"(B4b)是否显著优于"**不配对**"(B4a)?——绑定是否为活性成分。
- **RQ-M3**:learned cross-study matcher 能否恢复 oracle 收益 60–70%?
- **RQ-M4**:显式 change token 是否进一步降 wrong-time / unsupported-change?
- **H-M**:只注入对应关系即可补上大部分差距,且此增益来自"绑定"而非监督/算力/编码器。

### 7.3 支撑假设(承 v1/v2,统一表述)
- **H1(身份假设)**:视觉 token 显式绑定跨检查同一实体 → 更准区分 5 类 progression。
- **H2(change-token 假设)**:每槽显式 change token → 语言侧不必从两块无结构 token 隐式推变化 → wrong-time / unsupported-change 下降。
- **H3(接口归纳偏置假设,替代 v1 的"token-efficient")**:相同 LLM 视觉 token 预算下,持久槽比 dense patch/融合 token 保留更多与纵向比较相关的信息;效率收益体现在 LLM 端算力,但须报告**含上游的端到端总算力**。
- **H4(oracle→learned 可行性)**:learned matcher 恢复 oracle 收益大部分则方法有工程价值,否则降级为 upper-bound 分析。

### 7.4 成功标准
| 层级 | 标准 |
|---|---|
| 最低 | 冻结 LLM + oracle 对应 + patch-concat + B4a/B4b 四条跑通 |
| 发现成立 | oracle 修复 ≥ +5 Change F1 或 wrong-time/side 相对 ↓≥20%;**且 B4b≫B4a**(绑定是活性成分);**且 scaling null 成立** |
| 干净归因 | oracle 槽同时优于 **B4a(patch + oracle-box 不配对)**(证明是接口而非监督) |
| 探针支持 | 对应在 $V_{concat}$ 不可读、在 CAPES 后可读 |
| 方法成立 | learned 恢复 60–70%;优于 Libra 融合 |
| 理想(oral) | 上述全成立 + 跨数据集稳健 +(CVPR)跨域泛化 |
| 停止 | oracle 修复 < 2 分,或 B4b≈B4a(绑定无效),或探针 / scaling 与假设相悖 → 转纯诊断论文或 pivot |

---

## 8. Related Work & Differentiation

**8.1 单图瓶颈诊断线(发现的最近邻)** — Diagnosing Bottlenecks、LLMs Can Compensate、VLMs-are-blind、R-Probe 证明**单图**任务瓶颈在 handoff(信息在编码器、LLM 读不出)。**差异**:v3 的纵向失败是**关系信息从未写入**,探针在 $V_{concat}$ 上**探不出**对应——**新的、更严重的失败模式**,而非同一现象的搬运。

**8.2 跨图 token 独立的既有观察** — Semantic Alignment for MLLMs 已指出"每图独立 token 化损害跨图关联",MiCo 用 RL 做多图对比。**差异**:他们当**训练/数据/查询引导**问题解决;本文当**信息缺口**做**因果干预 + 可读性探针**的机制性证明,并给出结构性注入 + 临床错误学。**因此不 claim first 注意到 per-image 独立**,claim 的是诊断的机制性与修复的结构性。

**8.3 通用 object-centric tokenizer** — Slot-MLLM 首次让 slot attention 在 in-the-wild 自然图上服务生成式 MLLM,产出单图 object-centric slot token;CORE / object-centric token pruning / Victor registers 用紧凑 object-centric token 做 LVLM token merging。**差异**:这些都是**单图、面向重建/生成/压缩**;CAPES 是**跨检查、时间配对、身份持久**的解剖实体槽 + 显式变化,用它做 baseline(B5)隔离"跨检查持久性"这一变量。

**8.4 纵向医学 VLM 视觉侧(最强竞品)** — Libra 的 TAC 产出 dense、无显式实体身份、无固定预算、无独立 change token 的融合表示,目标是 report。**差异 + 必做 baseline**:CAPES(1)token 单元是**可枚举、身份持久的实体槽**而非 dense 融合;(2)**固定 LLM 视觉 token 预算**下受控比较;(3)把变化做成**独立可消融的 change token**。需证明"显式身份 + 固定预算"在等条件下优于"dense 融合"。

**8.5 temporal grounded generation** — MedReCo(大规模能力)、TRACE(联合解码涌现 change detection)、MAIRA-2(grounded report)。**差异**:v3 是**视觉 token 组织的机制性诊断 + 冻结 LLM 的注入修复**,公开数据、可复现、单卡。MedReCo 回答"能不能、能多好"(能力/规模);CAPES 回答"为什么、靠什么"(机制/接口)。

**8.6 Gap 一句话**:现有工作分别解决了训练医学 VLM、多图 instruction tuning、通用 slot tokenizer、temporal connector、grounded generation、entity-aware 大规模比较、单图 handoff 诊断。**仍缺一个受控 + 因果证据**:冻结 VLM + 等视觉 token 预算下,视觉 token 的"跨检查实体对应"本身是否是纵向推理的决定性变量,它相对通用 slot 与 dense connector 的净增益,以及它是否为一个**区别于单图 handoff 的、scaling 不可修复的**失败模式。

### 8.7 定位表(closest-work table,写作放 §1/Related Work)
| Work | Multi-image | Medical | Temporal | Entity Identity | Evidence Grounding | Fixed Token Budget | Failure-mode Diagnosis | VLM Interface |
|---|---|---|---|---|---|---|---|---|
| LLaVA-Med | no/limited | yes | no | no | limited | no | no | general VLM |
| MANTIS | yes | no | yes | implicit | no | no | no | instruction tuning |
| Med-MIM / Med-Mantis | yes | yes | yes | implicit | limited | no | no | instruction tuning |
| CheXRelNet | pair | yes | yes | anatomy-aware | no/limited | no | no | classifier |
| TRACE | pair | yes | yes | implicit/grounded | yes | no | no | grounded decoder |
| Libra | pair | yes | yes | implicit (dense) | limited | no | no | temporal connector |
| MedReCo | yes | yes | yes | yes | yes/related | no | no | comparative VLM |
| Diagnosing Bottlenecks / LLMs-Compensate | single | no | no | — | — | — | **single-image handoff** | probe/analysis |
| **Ours (CAPES)** | pair/multi | yes | yes | **explicit persistent slots** | yes | **yes** | **cross-study relational (new)** | **token interface + causal probe** |

---

## 9. Method — CAPES 作为"可探针、可部署"的注入

> 设计要求:同一模块既能当**探针**(证明发现),又能当**修复**(部署方法)。**只产 token,不改 LLM。** CAPES 是可插在任意冻结 VLM 前的视觉 token 生成模块,输出固定预算的视觉 token 序列。

### 9.1 总流程
```text
Prior CXR ─┐
           ├─► Frozen Vision Encoder (RAD-DINO / BioViL-T) ──► feature maps + feature cache
Current CXR┘
                     │
                     ▼
     Entity Region Source (oracle box / pseudo detector / anatomy grid)
                     │
                     ▼
        Per-study ROI features  e^{prior}_k , e^{current}_k
                     │
     ┌── Persistent Entity Binder (cross-study matcher) ──► 持久槽 s_k (含身份 a_k) ──┐
     │                                                                              │  (显式输出 π → correspondence probe)
     ▼                                                                              │
     Change-Aware Token Encoder ──► c_k                                              │
                     │                                                              │
                     ▼                                                              │
   Fixed-Budget Visual Token Assembler  V = [G^{pr}, G^{cur}, S_1..S_K, C_1..C_K] ◄─┘
                     │
                     ▼
     Lightweight Projector (对所有对照一致) ──► Frozen LLM ──► z, g, (optional y)
```
**贡献边界**:从 vision encoder 之后到 projector 之间的一切是"视觉侧";LLM 冻结。

### 9.2 模块 1:Persistent Entity Binder(本文视觉侧核心)
**动机**:patch token 与 Libra 的 dense 融合 token 都没有"可枚举的实体身份"。Binder 让每个视觉单元对应"同一临床实体跨时间的一条轨迹"。

**Region source(三层可靠性,支撑 oracle→learned 谱系)**:
1. **Oracle**:CheXTemporal / Chest ImaGenome 已有 finding/anatomy box。
2. **Pseudo**:anatomy detector / report-derived / weak grounding。
3. **Anatomy grid**:标准胸片解剖模板固定分区(无 box 时 fallback)。

**ROI 特征**(冻结 encoder + ROI pooling):
$$e^{prior}_k = \text{ROIEnc}(I^{prior}, r^{prior}_k), \qquad e^{current}_k = \text{ROIEnc}(I^{current}, r^{current}_k)$$

**持久槽(关键:身份写进 token)**:
$$s_k = [\,e^{prior}_k,\; e^{current}_k,\; a_k,\; p_k,\; \Delta t\,]$$
- $a_k$:解剖/finding **identity embedding**(同一实体跨检查共享 → "持久");
- $p_k$:空间位置编码;$\Delta t$:时间间隔 / 顺序编码。
- 语义:"同一个 anatomical/finding entity 在 prior 与 current 中的 paired representation"——一个 **cross-study visual unit**,而非普通 region token。

**Cross-study matcher(learned 版,RQ-M3)**:把 prior 实体集合与 current 实体集合配对。
- baseline 谱系:cosine → Hungarian → **anatomy-constrained Hungarian** → small graph matcher;
- 约束:同解剖先验(laterality/region 一致性)大幅降低相邻区错配。

**探针接口**:Binder 显式输出 $\pi$,可直接喂给 correspondence probe(§10.6)。

### 9.3 模块 2:Change-Aware Token Encoder
**动机**:无 change token 时,语言侧仍需从槽内两特征自行推变化。change token 把"变化"做成**显式、可消融**的视觉输入。
$$c_k = \text{ChangeEnc}(e^{prior}_k, e^{current}_k, a_k, \Delta t)$$
候选实现(消融对比):
1. **Delta MLP**:$c_k = \text{MLP}([\,e^{cur}_k - e^{pr}_k,\; e^{cur}_k,\; e^{pr}_k,\; a_k\,])$
2. **Tiny temporal transformer**:$c_k = \text{Transformer}([e^{pr}_k, e^{cur}_k, a_k, \Delta t])$
3. **Bilinear**:$c_k = W_1 e^{pr}_k + W_2 e^{cur}_k + W_3 (e^{pr}_k \odot e^{cur}_k)$

### 9.4 固定 LLM 视觉 token 预算(公平比较的地基)
所有方法送进 LLM 的视觉 token 数**严格相等**(例:64):

| Method | Token 组成 | 送 LLM 总数 |
|---|---|---:|
| Patch concat | 32 prior + 32 current patch | 64 |
| **Patch + oracle-box 不配对(B4a)** | 32 prior + 32 current patch,注入相同 oracle 区域信息但**不建立跨检查身份** | 64 |
| Libra-style temporal connector | 64 dense 融合 token | 64 |
| 通用 object-centric slot(Slot-MLLM 风格,无跨检查身份) | 64 单图 slot token | 64 |
| **CAPES(ours)** | 8 global + 28 entity slots + 28 change tokens | 64 |
| CAPES-lite | 8 global + 28 entity slots + 0 change | 36 |

> **诚实化(承 v2,替代 v1 的 "token-efficient" claim)**:等 token 数 ≠ 等信息 / 等算力。一个 slot token 是 ROI-pool 的浓缩,信息密度高于 patch token。因此本文**不主张"更省 token"**,只主张**"等 LLM 视觉 token 预算下更好的接口归纳偏置"**;效率仅在 LLM 端成立,须同时报告**含上游 ROI/matcher/change 的端到端 FLOPs/latency**(§10.7)。

### 9.5 输出头(轻量,对所有对照一致)
- **Progression head**:$\hat z = \text{Softmax}(W_z \cdot \text{pool}(V,q))$,5 类(或 3 类)。
- **Evidence head**:从槽/区域中选证据 $\hat g = \arg\max_k P(g=k\,|\,q,V)$;有 box 时回归/选择 box,否则输出 anatomy evidence label。
- **Optional projector→frozen LLM(第三阶段)**:把 $V$ 投影到 LLM embedding 空间做 constrained QA;**只训 projector / change-adapter / optional LoRA on projector**,LLM 冻结。constrained QA 输出样式:

```text
Question: Compared with the prior study, is the left pleural effusion improved, stable, or worsened?
Answer: Worsened.
Evidence: current left lower lung / prior left lower lung.
Confidence: 0.82.
```

### 9.6 训练目标(pilot 极简,消融后再加)
**Pilot 只上**(避免小数据上多 λ 过拟合):
$$\mathcal{L}_{prog} = \text{CE}(\hat z, z)\quad(\text{+ 若有 box, } \mathcal{L}_{ground\text{-}cls} = \text{CE}(\hat a, a))$$
**消融证明有用后再加**:
- 证据 grounding(有 box 且 regression 稳定时):$\mathcal{L}_{ground} = 1 - \text{IoU}(\hat r, r)$;
- 槽内对齐对比:$\displaystyle \mathcal{L}_{align} = -\log \frac{\exp(\text{sim}(e^{pr}_k,e^{cur}_k)/\tau)}{\sum_j \exp(\text{sim}(e^{pr}_k,e^{cur}_j)/\tau)}$;
- oracle→learned 蒸馏:$\mathcal{L}_{distill} = \text{KL}(P_{learned}(z|s_k)\,\|\,P_{oracle}(z|s_k))$;
- 总损失(仅在需要时启用各项):$\mathcal{L} = \lambda_1\mathcal{L}_{prog} + \lambda_2\mathcal{L}_{ground} + \lambda_3\mathcal{L}_{align} + \lambda_4\mathcal{L}_{distill}$。

冻结 LLM 与 vision encoder,只训 projector / change-adapter / matcher /(optional)LoRA-on-projector。

### 9.7 推理
提取 global + ROI 特征 → learned matcher 成槽 → change token → 按 query 选槽 → 输出 progression + evidence;**若最高证据置信 < 阈值则输出 uncertain**,避免无证据变化结论(对应临床安全,§15)。

---

## 10. Experimental Protocol — 把方法设计成发现的因果证明

**设计哲学**:每个实验对应闭环里的一步。表格不是"我方法更好",而是"**只有注入对应关系才修复,其它一切都不**"。

### 10.1 数据
- **首选**:CheXTemporal(5 类、finding-level 时空标注、gold + 280K silver;用于 oracle kill test、强弱监督比较)。
- **MVP fallback(去风险)**:Chest ImaGenome(anatomy-level 槽 + 比较关系 + scene graph 证据监督)+ MS-CXR-T(3 类外部 temporal benchmark)。**MVP 设计成即使 CheXTemporal 不可得也能成立,finding-level 作 bonus。**
- **二阶段外部验证**:Med-MIM 多图医学 QA(temporal/comparison/co-reference 子任务)。
- **CVPR 分叉**:通用域 change captioning / video difference(CLIP4IDC / STAND / VIDIC)。

### 10.2 预处理
patient-level split 防泄漏;prior/current 按时间排序;过滤缺 view/time metadata 样本;标准化 view(frontal/AP/PA);构建 progression label(CheXTemporal 5 类;ImaGenome 映射 improved/worsened/no-change;MS-CXR-T 映射 improving/stable/worsening)与 evidence label(anatomy-level / finding-level 分开);**feature cache 避免重复跑 encoder**。

### 10.3 因果对照谱系(核心)
| # | 条件 | 隔离的变量 | 对应闭环步 | 必要性 |
|---|---|---|---|---|
| B1 | current-only / prior-only | prior 有用性 / 标签泄漏 | (1) | 下界 / sanity |
| B3 | patch concat | 主对照(无对应) | (2) | 必须 |
| **B4a** | **oracle 框,但不配对** | **区域监督(无绑定)** | **(6) 星标** | **必须** |
| **B4b** | **oracle 框,且配对 = oracle 持久槽** | **绑定 = 活性成分** | **(6) 星标** | **必须** |
| B5 | 单图 object-centric slot(Slot-MLLM 风格) | 跨检查持久性 | (6) | 必须 |
| B6 | Libra 风格 dense temporal 融合 | 显式绑定 vs 融合 | (6) | 必须 |
| B7 | TRACE 风格 concat | temporal+grounding 强相关 | (6) | 必须 |
| B8/B9 | random / wrong-anatomy 槽 | identity 正确性(negative control) | (6) | 必须 |
| B10 | learned 持久槽(最终方法) | 可行性 | (6) | 必须 |
| B11 | ± change token | change 的贡献 | (6) | 必须 |
| (opt) | temporal transformer / token pruning | image-level 时序建模 / 纯 token 削减 | (2)(6) | 建议 |

**核心读法**:B4b − B4a = 绑定的净因果效应(同像素/同监督/同 token 数)。若 ≈0,发现证伪 → 停。

### 10.4 Scaling / capacity null(发现的关键图)
冻结 LLM 从小到大(如 7B→13B→更大)在 patch-concat 下 temporal 错误**不随规模下降**;而 CAPES 在**最小** LLM 上即接近 oracle。→ "scaling 补不回来,便宜上游注入能"。这是最能制造反直觉、也是 oral 最吃的一张图。**scaling null 用现成公开权重即可,不训 LLM。**

### 10.5 主任务与错误学指标
- **主任务**:Change F1(macro)、Balanced Acc、per-class F1(关注 stable/resolved subtle 类)。
- **证据**:Anatomy Evidence Acc、Finding IoU@0.3/0.5、Pointing Acc(**anatomy vs finding 分开报**)、Evidence Precision/Recall。
- **错误学**:Wrong-Time、Wrong-Side、Wrong-Region、Unsupported-Change、Order-Sensitivity(prior/current 交换后不一致率)。

### 10.6 Correspondence probe(发现的探针证据,含局限)
- **协议**:在冻结表示上训练轻量探针预测"prior 实体 k ↔ current 实体 j"的对应,比较 $V_{concat}$ 与 CAPES-$V$ 的可读性;并与"单图空间信息可读性"对照(复现单图 handoff 现象作为标尺)。
- **局限(显式标注)**:关系型对应对线性探针本就困难,须用**匹配容量**的探针 + **单图空间信息**作为"可读"标尺,避免"任何关系都探不出"的平凡结论。探针设计本身是一项方法学贡献 / 风险。

### 10.7 效率(端到端)
LLM 视觉 token 数、**端到端 FLOPs/latency(含 ROI encoder + matcher + change encoder)**、trainable params、feature cache size、peak GPU mem、单 case 推理成本。

### 10.8 主实验
- **Exp-1 Oracle kill test**:B1 / B3 / B4a / B4b / B6 / B8 / (B4b+change)。**Go**:B4b(oracle 配对)vs patch concat ≥ +5 Change F1,或 wrong-time/wrong-side ↓ ≥ 20%,**且 B4b 优于 B4a(干净归因)**。**Stop**:< +2 且错误分析无 identity 收益,或 B4b≈B4a。
- **Exp-2 Learned matcher**:cosine / Hungarian / anatomy-constrained / graph matcher,计算 $\text{Recovery} = \frac{F1_{learned}-F1_{patch}}{F1_{oracle}-F1_{patch}}$,继续条件 ≥ 60–70%。
- **Exp-3 Change token 消融**:patch / slots-only / change-only / slots+change × {Change F1, Wrong-Time, Unsupported-Change}。
- **Exp-4 Scaling null**:多规模冻结 LLM × {patch-concat, CAPES},画"错误 vs 规模"曲线。
- **Exp-5 VLM 集成**:frozen LLM + projector/LoRA 做 constrained QA,对比 LLaVA-Med 单图 / Med-Mantis / patch-concat-VLM / **Libra-style** / ours。

### 10.9 消融与稳健性
去 slots / 去 change / random / wrong-anatomy / shuffled order;$K \in \{8,16,28,56\}$;预算 $B \in \{32,64,128\}$;oracle vs pseudo vs learned region;encoder ∈ {RAD-DINO, BioViL-T, CLIP};change encoder 三选一。稳健性:order swap、去 prior、加 distractor、laterality 扰动、unseen disease、cross-dataset(ImaGenome→MS-CXR-T,或 CheXTemporal→ImaGenome)、silver→gold 迁移;**CVPR 分叉**再加通用域 change captioning / video difference。

### 10.10 错误分析
每错误样本标 8 类(correct / wrong-time / wrong-side / wrong-region / unsupported-change / missed-subtle / noisy-region / q-label-mismatch);产出 30-case 定性 + 每类数量比例 + 每类 baseline vs ours 的 error reduction(标注表见 Appendix D)。

---

## 11. Contributions(双主贡献 + 互为必要)

1. **发现(Finding)**:首次把纵向 VLM 的失败**因果性地**定位为"跨检查对应在视觉 token 接口中不可访问地缺失",并证明它是**区别于单图 handoff 瓶颈的新失败模式**——scaling / 更多 token / 更强单图编码器均不可修复(因果对照 + 探针 + scaling null)。
2. **方法(Method)**:CAPES——把该关系信息注入冻结 VLM 的**固定预算、可部署** tokenizer(持久槽 + change token),恢复大部分 oracle 上界,单卡可跑。
3. **互为必要(闭环)**:方法的因果成功 = 发现的证明;发现赋予方法结构性必要性(而非又一接口 tweak)。**这是本文区别于"纯诊断"与"纯方法"两类工作的核心**。
4. **评测协议**:固定预算 + 星标"配对 vs 不配对"对照 + correspondence probe + scaling null,为"视觉 token 关系信息"提供可复用的因果评测范式。
5. **临床错误学**:wrong-time/side/region/unsupported-change 的系统分解(TMI 分叉重心)。
6. **可复现工程**:不从零训练 VLM,冻结 vision encoder + LLM,只训 matcher/projector/change encoder,单张 3090 可跑 MVP;开源全 pipeline(§15)。

> **诚实预案(降下限)**:即使 learned matcher 恢复不足,"发现 + oracle 上界 + 探针 + scaling null"仍是完整可发表的诊断论文(poster/journal),不至归零。双核结构同时**抬上限、护下限**。

---

## 12. Venue 分叉:CVPR / AAAI / TMI

共同核心(§1–§11)不变;以下是**每家改什么**。三家是三篇不同重心的论文,**不一稿通吃**。

### 12.1 CVPR(冲 oral,上限最高、最难)
- **headline claim**:关系信息缺失是**多图视觉 tokenization 的一般性失败**,医学只是最干净的验证场。
- **headline figure**:scaling null(跨规模不降)+ **跨域泛化**(CXR + change captioning + video difference 同一曲线)。
- **必加**:≥1–2 个通用域 temporal/change 任务(CLIP4IDC/STAND/VIDIC),证明原理非 CXR-specific;强化与 Slot-MLLM/CORE 的通用 tokenizer 对话。
- **可弱化**:临床错误学细节、finding-level 医学语义。
- **题名倾向**:"Cross-Study Correspondence is the Missing Ingredient in Multi-Image VLMs"。
- **主风险**:CXR 为主仍是逆风;oral 取决于跨域结果是否够响,否则落 highlight/poster。

### 12.2 AAAI(冲 oral,最现实)
- **headline claim**:冻结 LLM 下的**因果诊断 + 结构性修复**——一个清晰、可证伪、被证明的机制发现。
- **headline figure**:因果对照谱系(尤其 B4b≫B4a)+ 探针可读性。
- **必强**:星标对照的干净性、scaling null、恢复率曲线;论证驱动、篇幅紧凑。
- **可保留**:医学为主 testbed;跨域作为附加而非必需。
- **题名倾向**:"Diagnosing and Repairing the Relational Blind Spot of Longitudinal VLMs"。
- **主风险**:与 Semantic Alignment/MiCo 的 novelty 区分要写透(机制性 vs 训练性)。

### 12.3 TMI(标杆论文,拿高影响最稳)
- **headline claim**:纵向 CXR 的**证据可追溯视觉接口** + **临床错误学** + 便宜可复现修复。
- **headline figure**:finding-level grounding + wrong-time/side/unsupported-change 的临床错误分解 + gold/silver 稳健性。
- **必加**:多源稳健性、reader-style/临床相关性评估、安全(unsupported-change + uncertainty)、finding-level IoU。
- **可弱化/删**:跨域泛化、通用 tokenizer 对话。
- **题名倾向**:"Persistent Entity Slots for Evidence-Grounded Longitudinal Chest-Radiograph Interpretation"。
- **主风险**:期刊周期长;需更深临床验证。

### 12.4 推荐路线
**AAAI(冲 oral)为主线**(oral 最现实、与"发现+方法"双核最契合),**TMI 版兜底**(平移临床重心、拿稳高影响);**CVPR 仅当跨域实验真正打响时升级冲击**。写作时先写 AAAI 版共同核心,§12.1/§12.3 作为可切换的 headline 与实验补丁。**不要一句话同时讨好三家。**

---

## 13. Feasibility

- **数据**:Chest ImaGenome / MS-CXR-T 公开;CheXTemporal 论文已核实存在,数据访问需 48h 内确认(不可得则 anatomy-level MVP,finding-level 作 bonus)。
- **算力**:
  - **单 3090 24GB MVP**:冻结 encoder + feature cache + 只训 matcher/change/projector,batch 1–8,不做全量 VLM finetune。
  - **A100 全量**:LoRA-on-projector、多 seed、scaling null 的多规模 LLM、Med-MIM / 跨域。scaling null 需多个冻结 LLM 规模——用现成公开权重即可,不训 LLM。
- **工程模块**:data pairing / region loader / feature cache / patch-concat / **Libra-TAC 复现** / oracle-slot builder(**配对 B4b 与不配对 B4a 两版**)/ random-wrong builder / learned matcher / change encoder / **correspondence probe** / metrics / error logger / projector 集成。
- **关键决策点**:W2 oracle kill test + 星标 B4b−B4a;W3 learned recovery。

---

## 14. Risks & Kill Criteria
| 风险 | 级别 | 应对 |
|---|---|---|
| B4b≈B4a(绑定非活性成分) | Critical | 发现证伪 → 停或 pivot;这是最重要的单点闸 |
| scaling null 不成立(大 LLM 修复了) | Critical | "结构性缺失"主张削弱 → 降为"接口更高效"较弱 claim |
| 与 Semantic Alignment/MiCo novelty 撞 | Critical | 写透"机制性因果诊断 + 结构性注入"vs"训练性缓解" |
| MedReCo/Libra/TRACE 竞争 | Critical | 全部设为 baseline;定位为诊断+修复而非能力竞赛 |
| oracle 无收益 | Critical | Week-2 停止或 pivot 到错误学/benchmark |
| oracle 收益来自监督而非接口 | Critical | **B4a patch+oracle-box 对照**;oracle(B4b)须同时优于 B4a |
| learned 恢复不足 | Major | 降级为诊断论文(发现+oracle+探针+scaling null 仍可发) |
| 探针平凡结论(关系本就难探) | Major | 匹配容量探针 + 单图信息作标尺;显式讨论局限 |
| 效率 claim 被质疑 | Major | 不主张省 token;报端到端 FLOPs |
| 数据 annotation noisy | Major | anatomy vs finding 指标分开;gold 抽检 |
| CheXTemporal 不可得 | Major | ImaGenome + MS-CXR-T anatomy-level MVP,finding-level 作 bonus |
| CXR-only 泛化弱(CVPR 逆风) | Major | 跨域实验;或走 AAAI/TMI |
| LLM 忽略 slots | Major | 先做 classifier;再加 evidence supervision 与 projector ablation |

**最可能被拒的单一原因**:审稿人认为"per-image token 缺对应"是已知观察(Semantic Alignment),未看到机制性/因果增量 → 必须让**星标对照(B4b−B4a)+ scaling null + correspondence probe**成为无法忽视的新证据。次高风险:learned matcher 恢复不了 oracle(H4 硬闸,Week-3 决策)→ 落回上界+诊断论文。

---

## 15. Ethics, Safety & Reproducibility

### 15.1 数据隐私
使用公开/受控医学影像数据集,遵守原数据集许可与 DUA;若用 MIMIC-CXR / Chest ImaGenome 系列,遵守 PhysioNet 数据访问要求与患者隐私保护。

### 15.2 临床安全
research prototype,不替代医生,不声称临床诊断可靠。即使能输出 evidence region 也不保证临床可靠;以 **unsupported-change rate + evidence confidence + uncertainty 输出**降低无证据结论风险(§9.7 阈值机制)。

### 15.3 偏差与公平
胸片数据可能存在机构/设备/人群/疾病分布偏差;按数据源、view、疾病类别分组报告表现。

### 15.4 Hallucination 与过度依赖
医学 VLM 错误输出高风险;本文以 unsupported-change 指标 + evidence confidence + uncertainty 输出为缓解目标之一。

### 15.5 环境成本
冻结 backbone + feature cache + LoRA + 轻量模块,避免从零训练大模型,降低算力与碳排。

### 15.6 可复现清单(计划开源/记录)
数据构建脚本 · patient-level split 文件 · region extraction 配置 · feature cache 生成脚本 · **全 baseline 实现(含 Libra-style TAC 复现、B4a/B4b 两版 oracle slot)** · token 预算参数 · 模型配置与超参 · 随机种子 · 训练日志 · evaluation scripts · correspondence probe 代码 · error analysis notebook · 失败实验记录 · GPU 型号/显存/训练时长 · 若数据不能再分发则提供处理说明与可复现 index。

---

## 16. Timeline & Milestones

### 16.1 4-Week MVP + 8-12 Week Full
| 周 | 任务 | 产出 | Go/No-Go |
|---|---|---|---|
| W1 | 数据确认;pairing;region 加载;feature cache;**Libra-TAC 复现** | data report + 1–5K subset | 数据不可用 → fallback |
| W2 | patch-concat / **B4a 不配对** / **B4b 配对 oracle** / random → kill test | 因果表 v0 | oracle<+2 或 **B4b≈B4a** → 停 |
| W3 | learned matcher + 恢复率;**correspondence probe v0** | matcher/probe 表 | recovery<40% → 降诊断论文 |
| W4 | **scaling null(多规模冻结 LLM)** + change 消融 + 30-case 错误学 | 发现三证据(对照+探针+scaling)+ MVP | 三证据齐 → full |
| W5-6 | 全数据 + TRACE/Libra/Slot baseline + 多 seed | 完整 baseline/ablation | |
| W7-8 | 稳健性 + 外部验证;(CVPR)通用域 change captioning/video diff | 泛化表 | |
| W9-10 | 探针深化 + 错误学 + figures(scaling null / B4b-B4a / probe) | 主图 1-4 | |
| W11-12 | 按选定 venue 定 headline;写作;审稿模拟 | full draft | |

### 16.2 6-Month Paper Plan
| 月 | 任务 | 产出 |
|---|---|---|
| M1 | 文献矩阵、数据确认、MVP、kill test + 星标对照 | proposal + kill test |
| M2 | baseline 与 learned matcher + 恢复率 | main experiments |
| M3 | VLM integration、scaling null、ablations | method + 发现三证据 |
| M4 | robustness、external validation、错误学 | analysis section |
| M5 | paper writing、figures、appendix | full draft |
| M6 | rebuttal-style stress test、按 venue 定稿 | submission-ready paper |

---

## 17. Figure Plan

### Figure 1:Motivation(发现的直觉)
- 左:prior/current CXR pair;
- 中:patch concat baseline 错误输出(把 prior lesion 当 current new lesion = wrong-time);
- 右:persistent entity slot 连接同一 anatomical region,输出正确 progression + evidence region。
- **Caption 核心句**:*Patch-token concatenation lets the model see both studies, but never writes which visual tokens correspond to the same anatomical entity across time — so cross-study correspondence is structurally absent from the interface.*

### Figure 2:Method Overview
```text
Prior/Current CXR → Region Extraction → Persistent Entity Slots → Change Tokens
→ Fixed-Budget Visual Token Interface → Frozen LLM → Progression + Evidence
```
标注:global tokens / entity slots / change tokens / fixed token budget / evidence head / **π 输出→probe**。

### Figure 3(oral 主图 A):Scaling Null
折线:横轴 LLM 规模,纵轴 wrong-time(或 Change F1)。patch-concat 曲线**平**(scaling 补不回来);CAPES 在最小规模即接近 oracle。

### Figure 4(oral 主图 B):星标对照 B4b − B4a + Probe
Grouped bar:patch / B4a(框不配对)/ B4b(框且配对)/ 单图 slot / Libra / learned,指标 Change F1 + Wrong-Time;并排 correspondence probe accuracy($V_{concat}$ vs CAPES)。

### Figure 5:Case Study
三案例:(1)baseline wrong-time,ours correct;(2)baseline wrong-side,ours correct;(3)ours failure due to noisy region proposal(诚实展示失败)。

---

## 18. Main Tables(模板;数值待实验填充)

### Table 1:Literature Positioning
见 §8.7 的 closest-work table。

### Table 2:Main Causal Table(核心)
| Method | Token Budget | Extra Supervision | Cross-study Binding | Change F1 | Balanced Acc | Anatomy Ev. Acc | Finding IoU | Wrong-Time ↓ | Wrong-Side ↓ | Unsupported ↓ | End-to-end FLOPs | Latency |
|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Current only | low | no | — | | | | | | | | | |
| Patch concat (B3) | 64 | no | no | | | | | | | | | |
| **Patch + oracle-box, unpaired (B4a)** | 64 | oracle box | **no** | | | | | | | | | |
| **Oracle persistent slots, paired (B4b)** | 64 | oracle box | **yes** | | | | | | | | | |
| Single-image slot (B5) | 64 | — | no | | | | | | | | | |
| Libra-style fusion (B6) | 64 | — | dense | | | | | | | | | |
| TRACE-style concat (B7) | 64 | grounding | implicit | | | | | | | | | |
| Random / wrong-anatomy (B8/B9) | 64 | same as ours | corrupted | | | | | | | | | |
| Learned persistent slots (B10) | 64 | same as ours | learned | | | | | | | | | |
| + change token (B11) | 64 | same as ours | learned | | | | | | | | | |

**关键行读法**:B4b − B4a = 绑定净因果效应。

### Table 3:Learned Matcher Recovery
| Matcher | Alignment Acc | Change F1 | Oracle Gain Recovery | Wrong-Time ↓ | Latency |
|---|---:|---:|---:|---:|---:|
| Cosine | | | | | |
| Hungarian | | | | | |
| Anatomy-constrained Hungarian | | | | | |
| Small graph matcher | | | | | |
| Oracle (B4b) | | | 100% | | |
| Random | | | 0% | | |

### Table 4:Scaling Null
| LLM size | Patch-concat Wrong-Time | Patch-concat Change F1 | CAPES Wrong-Time | CAPES Change F1 |
|---|---:|---:|---:|---:|
| small (e.g. 7B) | | | | |
| mid (e.g. 13B) | | | | |
| large | | | | |

### Table 5:Ablation
| Variant | Slots | Change | Align Loss | Distill | Change F1 | Wrong-Time ↓ | Unsupported ↓ | Evidence Acc |
|---|---|---|---|---|---:|---:|---:|---:|
| Full | yes | yes | yes | yes | | | | |
| w/o slots | no | yes | no | no | | | | |
| w/o change | yes | no | yes | yes | | | | |
| w/o align loss | yes | yes | no | yes | | | | |
| w/o distill | yes | yes | yes | no | | | | |

### Table 6:Budget / K Sensitivity
| Method | B=32 | B=64 | B=128 | K=8 | K=16 | K=28 | K=56 | Latency |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Patch concat | | | | — | — | — | — | |
| CAPES | | | | | | | | |

### Table 7:Correspondence Probe(发现证据)
| Representation | Cross-study Correspondence Probe Acc | Single-image Spatial Probe Acc(标尺) |
|---|---:|---:|
| $V_{concat}$ (patch) | | |
| Libra fusion | | |
| CAPES-$V$ | | |

---

## 19. 审稿模拟(CCF-A / oral committee)

### Reviewer 1(Novelty)
**Critique**:MedReCo 已做 entity-aware cross-image reasoning,Libra 已做 temporal connector,Slot-MLLM 已做 object-centric token,Semantic Alignment 已注意到 per-image token 缺跨图对齐——本文是否只是换名字?
**Response**:不 claim first。本文 claim 的是**因果诊断(关系信息结构性缺失,区别于单图 handoff)+ 结构性注入 + scaling null**。让 §8.7 closest-work table、星标 B4b−B4a、correspondence probe、scaling null 成为无法归约到上述任一工作的新证据。

### Reviewer 2(Experiments)
**Critique**:收益可能来自更多 supervision / 更多 token / 更强 encoder / 额外预处理,而非"身份绑定"。
**Response**:固定 token budget;报告 trainable params、端到端 FLOPs/latency、token count;**B4a(patch+oracle-box 不配对)与 B4b(配对)只差"是否绑定"**;加 random/wrong-anatomy negative control、oracle upper bound、learned recovery、scaling null。

### Reviewer 3(Clinical / Data)
**Critique**:Chest ImaGenome annotation 自动生成,anatomy-level evidence 不代表病灶定位;模型可能只学 noisy labels。
**Response**:anatomy-level 与 finding-level 指标分开;gold subset / 人工抽检;仅在证据粒度匹配时 claim grounding;有 CheXTemporal 时优先报 finding-level。

### Reviewer 4(Writing / Positioning)
**Critique**:同时讲 token efficiency、temporal reasoning、grounding、hallucination,主线发散。
**Response**:主 claim 收敛为一句——*cross-study correspondence is structurally absent from the visual tokens, scaling can't fix it, a cheap tokenizer-level injection can*;token efficiency 改为"等预算接口归纳偏置"、hallucination 仅作 unsupported-change 辅助指标、report generation 不作主任务。

### Reviewer 5(oral committee 视角)
**Critique**:方法类论文很多,凭什么 oral?
**Response**:这不是方法微调,而是**一个新失败模式的因果证明 + 可部署修复的闭环**:先接社区已在乎的瓶颈问题,再给一句反直觉、可证伪、被证明的新话,用 interp 社区最认的因果干预 + 探针证明,且修复冻结 LLM、便宜、可部署。

---

## 20. Go / No-Go Checklist

### Before Coding
- [ ] CheXTemporal 是否可访问?
- [ ] Chest ImaGenome region 与 comparison relations 是否可解析?
- [ ] MS-CXR-T 是否可作外部评测?
- [ ] 能否构建 patient-level split?
- [ ] progression label mapping / evidence granularity / token budget 是否定义?
- [ ] Libra-TAC 复现路径是否明确?

### Week-2 Decision(发现的第一闸)
继续:
- [ ] B4b(oracle 配对)比 patch concat Change F1 ↑ ≥ 5,或 wrong-time/side 相对 ↓ ≥ 20%;且
- [ ] **B4b ≫ B4a**(绑定是活性成分);且
- [ ] random/wrong-anatomy 无明显收益。
停止/pivot:
- [ ] oracle 提升 < 2 分;或 B4b ≈ B4a;或错误分析显示问题主要不是 identity;或数据 label 噪声不可控。

### Week-3 Decision(方法可行性闸)
- [ ] learned recovery ≥ 60–70% → 继续方法线;
- [ ] recovery < 40% → 降级为"发现 + oracle 上界 + 探针 + scaling null"诊断论文。

### Week-4 Decision(发现三证据)
- [ ] 因果对照(B4b−B4a)、correspondence probe、scaling null 三者齐 → full;缺一 → 补齐或调整定位。

### Before Paper Writing
- [ ] ≥1 强 related baseline(Libra / TRACE);
- [ ] oracle upper bound(B4b);
- [ ] random/wrong negative control(B8/B9);
- [ ] ≥1 external dataset;
- [ ] 主表报告 token count + 端到端 FLOPs/latency;
- [ ] 每条 claim 都有对应实验支撑;
- [ ] 引用真实性全部复核(尤其 Med-MIM 2505.19031、STAND 2604.23309、VIDIC)。

---

## 21. References(已核实,2026-07-05;未复核者标注)

1. **Diagnosing Bottlenecks in Data Visualization Understanding by VLMs.** arXiv:2510.21740 ✅
2. **LLMs Can Compensate for Deficiencies in Visual Representations.** arXiv:2506.05439 ✅
3. **Vision Language Models are Blind.** arXiv:2407.06581 ✅
4. **Semantic Alignment for Multimodal Large Language Models.** arXiv:2408.12867 ✅
5. **MiCo: Multi-image Contrast for Reinforcement Visual Reasoning.** arXiv:2506.22434（待复核）
6. **Slot-MLLM: Object-Centric Visual Tokenization for Multimodal LLM.** arXiv:2505.17726 ✅
7. **CORE: Compact Object-centric Representations for Token Merging in LVLMs.** arXiv:2511.14072 ✅
8. Locatello et al. **Object-Centric Learning with Slot Attention.** arXiv:2006.15055 ✅
9. Zhang et al. **Libra: Leveraging Temporal Images for Biomedical Radiology Analysis.** arXiv:2411.19378（ACL 2025 Findings）✅
10. Rahman Aranya & Desai. **TRACE: Temporal Radiology with Anatomical Change Explanation.** arXiv:2602.02963 ✅
11. Zhang et al. **MedReCo: A Vision-language Framework for Comparative Reasoning in Radiology.** arXiv:2606.06407 ✅
12. Prakash et al. **CheXTemporal: A Dataset for Temporally-Grounded Reasoning in Chest Radiography.** arXiv:2605.11304 ✅
13. Wu et al. **Chest ImaGenome Dataset.** arXiv:2108.00316 / PhysioNet ✅
14. Bannur et al. **MS-CXR-T / BioViL-T**（Learning to Exploit Temporal Structure for Biomedical VLP）PhysioNet + CVPR 2023 ✅
15. Karwande et al. **CheXRelNet: An Anatomy-Aware Model for Tracking Longitudinal Relationships Between Chest X-rays.** arXiv:2208.03873 ✅
16. Bannur et al. **MAIRA-2: Grounded Radiology Report Generation.** arXiv:2406.04449 ✅
17. Pérez-García et al. **RAD-DINO.** arXiv:2401.10815 ✅
18. Li et al. **LLaVA-Med: Training a Large Language-and-Vision Assistant for Biomedicine in One Day.** arXiv:2306.00890 ✅
19. Jiang et al. **MANTIS: Interleaved Multi-Image Instruction Tuning.** arXiv:2405.01483 ✅
20. Yang et al. **Medical Large Vision Language Models with Multi-Image Visual Ability (Med-MIM / Med-Mantis).** arXiv:2505.19031（**待复核标题/作者/ID**）
21. **CLIP4IDC: CLIP for Image Difference Captioning.** arXiv:2206.00629 ✅
22. **STAND: Remote Sensing Image Change Captioning.** arXiv:2604.23309（待复核）
23. **R-Probe / Reasoning Probe for VLMs.** arXiv:2603.20020（待复核）
24. **Video Difference Captioning (VIDIC), 2025**（待复核 ID）
25. NeurIPS. **Paper Checklist & Ethics Guidelines.** https://neurips.cc/public/guides/PaperChecklist

---

## Appendix A. 分 venue 一句话定位(写 intro / rebuttal 用)

**通用(AAAI / 闭环版)**
> Longitudinal VLMs fail not because the language model cannot reason, but because cross-study entity correspondence is never written into the visual tokens. We prove this causally — a frozen-LLM, fixed-budget oracle-identity intervention closes the gap, while more tokens, more region supervision without binding, stronger single-image encoders, and larger LLMs do not — and we repair it with Change-Aware Persistent Entity Slots, a deployable tokenizer that recovers most of the oracle bound.

**CVPR 版**
> We identify a failure mode of multi-image visual tokenization — relational correspondence is structurally absent from independently tokenized images — show it is not fixed by scale, and demonstrate a cheap tokenizer-level repair that generalizes from longitudinal radiology to natural-image and video difference reasoning.

**TMI 版**
> We show that the temporal-reasoning errors of longitudinal chest-radiograph VLMs (wrong-time, wrong-side, unsupported-change) stem from visual tokens that discard cross-study entity identity, and we provide an evidence-grounded, frozen-LLM tokenizer that restores it — improving progression classification and finding-level grounding at fixed cost.

**边界声明(rebuttal 用)**
> We do not claim the first entity-aware comparative radiology (MedReCo does), nor the first temporal visual connector (Libra does), nor the first object-centric visual tokenizer (Slot-MLLM does), nor the first observation that per-image tokenization hurts cross-image association (Semantic Alignment does). We contribute the causal, probe-backed diagnosis that this is a distinct, scaling-irreparable failure mode in the longitudinal regime, and a structural injection that repairs it.

---

## Appendix B. Implementation Pseudocode

```python
# Pseudocode only — visual side; LLM frozen.

for sample in dataset:
    prior_img, current_img, question = sample["prior"], sample["current"], sample["question"]

    # 1. Frozen encoder + cache
    prior_feat   = vision_encoder(prior_img)      # frozen (RAD-DINO / BioViL-T)
    current_feat = vision_encoder(current_img)

    # 2. Region source: oracle box / pseudo detector / anatomy grid
    prior_regions   = load_regions(sample, time="prior")
    current_regions = load_regions(sample, time="current")

    # 3. ROI features
    prior_entities   = roi_pool(prior_feat,   prior_regions)
    current_entities = roi_pool(current_feat, current_regions)

    # 4. Cross-study binding (the intervention variable)
    if mode == "B4b_oracle_paired":     # oracle box AND paired -> persistent slots
        slots = oracle_align(prior_entities, current_entities)
    elif mode == "B4a_oracle_unpaired": # oracle box but NOT paired -> supervision w/o binding
        slots = concat_no_binding(prior_entities, current_entities)
    elif mode == "random":
        slots = random_align(prior_entities, current_entities)
    elif mode == "single_image_slot":   # Slot-MLLM style, no cross-study identity
        slots = single_image_slots(prior_entities, current_entities)
    else:                               # learned matcher (cosine/Hungarian/graph)
        slots = learned_matcher(prior_entities, current_entities)

    # 5. Change tokens (ablatable)
    change_tokens = change_encoder(slots)          # delta-MLP / tiny-transformer / bilinear

    # 6. Fixed-budget visual interface (equal token count across all conditions)
    visual_tokens = build_visual_tokens(global_tokens, slots, change_tokens, budget=64)

    # 7. Frozen LLM (only projector/adapter/optional-LoRA trained)
    z_hat = progression_head(visual_tokens, question)
    g_hat = evidence_head(visual_tokens, question)

    # 8. Loss (pilot: prog only; add align/distill/ground after ablation)
    loss = ce(z_hat, label) + (ce(a_hat, anatomy) if has_box else 0)

    # Probe hook: Binder exposes pi for correspondence probe
    log_correspondence(slots.pi)
```

---

## Appendix C. Data Verification Checklist

| Item | CheXTemporal | Chest ImaGenome | MS-CXR-T |
|---|---|---|---|
| paired prior/current | | | |
| patient-level split | | | |
| progression labels | | | |
| spatial labels | | | |
| anatomy labels | | | |
| finding labels | | | |
| license usable | | | |
| preprocessing complexity | | | |
| MVP priority | high | high | medium |

---

## Appendix D. Error Taxonomy Annotation Sheet

```text
Sample ID:
Predicted label:      Gold label:
Predicted evidence:   Gold evidence:

Error type:
[ ] correct
[ ] wrong-time            (prior finding judged as current new)
[ ] wrong-side            (left/right confusion)
[ ] wrong-region          (region mismatch)
[ ] unsupported-change    (change claim w/o evidence)
[ ] missed-subtle change  (stable/improved/resolved confusion)
[ ] noisy region proposal (detector gave wrong anatomy)
[ ] question-label mismatch
[ ] other

Notes:
```

产出:30-case 定性 + 每类数量比例 + 每类 baseline vs ours 的 error reduction。

---

## Appendix E. Proposal Self-Score Rubric

| 维度 | 分值 | 当前预估 | 需要加强 |
|---|---:|---:|---|
| 问题重要性 | 15 | 14 | 真实 clinical workflow 例子 |
| Research Gap / 发现新颖性 | 15 | 13 | 写透"关系型缺失 ≠ 单图 handoff" |
| 创新性(发现+方法双核) | 15 | 13 | 星标对照 + scaling null 的因果强度 |
| 方法合理性 | 15 | 12 | learned matcher 细节 + 探针容量设计 |
| 实验设计 | 15 | 14 | B4a/B4b、scaling null、probe 三证据齐 |
| 可行性 | 10 | 8 | 48h 内确认 CheXTemporal 访问 |
| 伦理与复现 | 10 | 8 | DUA 说明 + 全 pipeline 开源 |
| 写作表达 | 5 | 4 | Figure 1/3/4 需真实 case 与曲线 |
| **总分** | **100** | **86** | kill test + 星标对照成功后可上探 oral 体质 |
