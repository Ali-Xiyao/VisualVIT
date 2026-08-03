# PRTA-CXR 最终论文实验计划与空结果登记表

> **文档类型**：实验执行、阶段确认与论文空表一体化 Markdown 文档  
> **版本**：v1.0  
> **主方法定位**：PRTA-CXR 原生纵向 ViT 分类器  
> **附加工作定位**：最终 PRTA 表征部署到一个 VLM，仅作附加迁移展示  
> **标签策略**：Luna 全量结构化打标/复核 + 确定性校验 + 临床医生分层抽检  
> **重要术语**：Luna 自动生成或复核的标签统一称为 **verified silver / report-derived weak supervision**，不得直接称为人工 Gold。

---

## 0. 文档使用说明

本文件由原实验工作簿转换而来，适合直接放入新项目：

```text
docs/PRTA_CXR_实验计划与空结果表_CN.md
```

填写规则：

1. 所有结果、负责人、日期、路径、状态和统计字段默认留空，实验完成后再填写。
2. 固定的方法名称、任务 ID、实验条件和验收标准属于预先定义内容，不应在看到正式测试结果后随意修改。
3. 每次训练或推理都必须同时填写“统一 Run Registry”。
4. Internal Test 与 Expert Gold 只允许在协议冻结后读取；不得用于模型选择、温度拟合、Prompt 修改或标签规则修改。
5. 表格不够时，复制最后一行继续填写，不要改变原列名。
6. 所有路径应填写相对于新仓库根目录的路径，避免使用个人电脑的绝对盘符。
7. 状态建议使用：`未开始 / 进行中 / 已完成 / 阻塞 / 暂停 / 不适用`。
8. 阶段决策建议使用：`GO / HOLD / STOP`。

---

# 1. 项目总览

## 1.1 最终主线

```text
旧 VisualVIT 冻结只读
        ↓
新建 PRTA-CXR 干净项目
        ↓
扩大纵向 Pair + Luna 报告标签审核
        ↓
医生分层抽检 + 标签版本冻结
        ↓
仅在 Train/Dev 上提升原生 ViT 指标
        ↓
冻结方法、数据、指标和测试协议
        ↓
正式 Baseline + 正式消融
        ↓
PRIOR 干预 + 时间反转 + 校准 + 亚组 + 可视化
        ↓
一次性 Expert Gold / Internal Test
        ↓
最终 PRTA → 单一 VLM 附加部署
```

## 1.2 阶段总表

| Phase | 工作包 | 计划任务数 | 负责人 | 计划完成 | 当前状态 | 完成率 | 出口门 | 阶段决策 | 证据/报告 |
|---|---|---:|---|---|---|---:|---|---|---|
| Phase 0 | 新项目重构与 Parity | 10 |  |  |  |  | Parity / Tests / Leakage |  |  |
| Phase 1 | 数据扩展、Luna 标签与临床抽检 | 12 |  |  |  |  | 标签质量门 |  |  |
| Phase 2 | 主方法性能开发 | 13 |  |  |  |  | Dev 出口门 |  |  |
| Phase 3 | 正式协议冻结 | 5 |  |  |  |  | Freeze Receipt |  |  |
| Phase 4 | 正式 Baseline | 5 |  |  |  |  | 三 Seed 完成 |  |  |
| Phase 5 | 正式 Ablation | 8 |  |  |  |  | 核心消融完成 |  |  |
| Phase 6 | 可信性、校准与亚组 | 14 |  |  |  |  | Trust Evidence |  |  |
| Phase 7 | 可视化与错误分析 | 8 |  |  |  |  | 正文图完成 |  |  |
| Phase 8 | VLM 附加部署 | 6 |  |  |  |  | 不影响 ViT 主线 |  |  |

## 1.3 近期决策与风险登记

| 日期 | 类型 | 决策/风险 | 当前结论 | 负责人 | 状态 | 解除条件/下一步 | 证据/路径 | 备注 |
|---|---|---|---|---|---|---|---|---|
|  | 主线定位 | 原生 ViT 为主；VLM 最后附加 |  |  |  |  |  |  |
|  | 标签术语 | Luna 标签不得直接称为 Gold |  |  |  |  |  |  |
|  | 数据许可 | 仅处理去标识且许可允许的报告 |  |  |  |  |  |  |
|  | 测试泄漏 | 历史 Test 不得作为新项目 Dev |  |  |  |  |  |  |
|  | 其他 |  |  |  |  |  |  |  |

## 1.4 项目启动前总确认

- [ ] 已确认新项目名称、仓库地址和负责人。
- [ ] 已确认旧 `VisualVIT` 仓库只读，不再从旧仓启动新正式实验。
- [ ] 已确认现有历史 Test、Audit 和 Gold 患者隔离名单。
- [ ] 已确认 Luna 的实际 Codex model ID、调用权限和批处理额度。
- [ ] 已确认报告均已去标识，且数据许可允许用于模型辅助标注。
- [ ] 已确认 Internal Test 与 Expert Gold 的解封负责人不是主要调参人员，或已建立不可逆日志。
- [ ] 已确认所有正式结果按患者聚类统计，而不是把 pair×finding 当作独立患者。

**启动确认人**：  
**日期**：  
**结论**：`GO / HOLD / STOP`  
**备注**：

---

# 2. Phase 0：新项目重构与 Parity

## 2.1 简单说明

这一阶段的目标不是修改方法，而是把旧仓库中的最终有效代码迁移到一个干净、可复现、可交接的新项目。只有新旧实现能够在同一小 cohort 上复算一致，才允许进入数据扩展和性能开发。

建议新项目结构：

```text
PRTA-CXR/
├── configs/
├── prompts/
├── schemas/
├── src/prta_cxr/
│   ├── data/
│   ├── models/
│   ├── training/
│   ├── evaluation/
│   ├── visualization/
│   └── vlm/
├── scripts/
├── manifests/
├── tests/
├── results/
├── paper/
└── docs/
```

## 2.2 重构任务清单

| 任务 ID | 任务 | 交付物/验收标准 | 优先级 | 负责人 | 计划完成 | 状态 | 实际完成 | 证据/路径 | 前置依赖 | 阶段决策 | 风险 | 备注 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| R001 | 创建独立 PRTA-CXR 仓库 | Repo 可独立 clone/install | P0 |  |  |  |  |  |  |  |  |  |
| R002 | 建立目录骨架与 pyproject | 目录、包与 CLI 符合执行协议 | P0 |  |  |  |  |  | R001 |  |  |  |
| R003 | 白名单迁移 PRTA 核心 | 仅迁移 adapter/alignment/resampler/losses | P0 |  |  |  |  |  | R002 |  |  |  |
| R004 | 迁移数据 pairing/report rules | 单测覆盖主要边界条件 | P0 |  |  |  |  |  | R002 |  |  |  |
| R005 | 迁移 bootstrap/metrics/reversal | 与旧实现逐项一致 | P0 |  |  |  |  |  | R002 |  |  |  |
| R006 | 建立 Luna schema/parser | 非法输出 fail-closed | P0 |  |  |  |  |  | R002 |  |  |  |
| R007 | 建立 leakage 与 manifest tests | Patient overlap = 0 | P0 |  |  |  |  |  | R002 |  |  |  |
| R008 | 小 cohort 新旧 Parity | 逐行预测或指标差异在容差内 | P0 |  |  |  |  |  | R003–R005 |  |  |  |
| R009 | 生成 migration receipt | 记录旧 commit、新 commit、hash 和环境 | P1 |  |  |  |  |  | R008 |  |  |  |
| R010 | 旧 VisualVIT 进入只读 | 新实验只从新仓库运行 | P1 |  |  |  |  |  | R009 |  |  |  |

## 2.3 Parity 记录

| 检查项 | 旧项目值 | 新项目值 | 容差/标准 | 是否通过 | 证据路径 | 解释/备注 |
|---|---|---|---|---|---|---|
| 样本 manifest hash |  |  | 完全一致 |  |  |  |
| 预测文件行数 |  |  | 完全一致 |  |  |  |
| 逐行预测 checksum |  |  | 完全一致，或解释浮点差异 |  |  |  |
| Macro-F1 |  |  | 差异 ≤ 0.0001 |  |  |  |
| Balanced Accuracy |  |  | 差异 ≤ 0.0001 |  |  |  |
| Patient leakage |  |  | 0 |  |  |  |
| Unit tests |  |  | 100% pass |  |  |  |
| Ruff / compile / type checks |  |  | 全部通过 |  |  |  |
| 单 GPU smoke train |  |  | 成功保存 checkpoint |  |  |  |

## 2.4 Phase 0 出口确认

- [ ] 新项目可从零安装。
- [ ] 新旧 PRTA 复算通过。
- [ ] 数据、模型、评估和统计代码均有最小测试。
- [ ] 没有硬编码个人盘符和本地秘密信息。
- [ ] 旧仓库已打只读 Tag 或明确停止新实验。
- [ ] `LEGACY_MIGRATION_MAP.md` 已完成。

**确认人**：  
**日期**：  
**决策**：`GO / HOLD / STOP`  
**未解决问题**：

---

# 3. Phase 1：数据扩展、Luna 标签与临床抽检

## 3.1 简单说明

Luna 负责全量第一轮结构化打标或复核；代码负责 Schema、证据原文、时间顺序、否定、不确定性、finding 归属和患者隔离检查；医生只做分层抽检与争议复核。

建议输出层级：

- **Tier-A**：证据充分、无冲突，进入主训练集；
- **Tier-B**：较可信但证据不完全，保留用于质量—数量实验；
- **Reject**：比较对象、finding、否定、不确定性或时间关系存在冲突。

## 3.2 数据与标签任务清单

| 任务 ID | 任务 | 交付物/验收标准 | 优先级 | 负责人 | 计划完成 | 状态 | 实际完成 | 证据/路径 | 前置依赖 | 阶段决策 | 风险 | 备注 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| L101 | 盘点已批准数据源与许可 | 数据卡与可用字段 | P0 |  |  |  |  |  |  |  |  |  |
| L102 | 构建纵向 Pair Candidates | 相邻 Study 配对 manifest | P0 |  |  |  |  |  | L101 |  |  |  |
| L103 | 运行规则候选提取 | Rule-valid 与拒绝原因 | P0 |  |  |  |  |  | L102 |  |  |  |
| L104 | 设计 Luna Prompt + JSON Schema | 固定 v1 Prompt/Schema | P0 |  |  |  |  |  | L103 |  |  |  |
| L105 | Luna Pilot 100–200 条 | 结构合法率、一致性和吞吐报告 | P0 |  |  |  |  |  | L104 |  |  |  |
| L106 | 第一次全量 Luna 审核 | Tier-A/B/Reject manifests | P0 |  |  |  |  |  | L105 |  |  |  |
| L107 | 分层抽取约 300 条医生审核 | 约 250 Accept + 50 Reject/Conflict | P0 |  |  |  |  |  | L106 |  |  |  |
| L108 | 计算总体与类别一致率 | 总体建议 ≥90%，各类建议 ≥80% | P0 |  |  |  |  |  | L107 |  |  |  |
| L109 | 冻结 Prompt/Rules/Schema | 生成 Freeze Receipt | P0 |  |  |  |  |  | L108 |  |  |  |
| L110 | 按冻结版本全量重跑 | 不得逐行人工修补 | P0 |  |  |  |  |  | L109 |  |  |  |
| L111 | 排除历史 Test/Audit/Gold | 排除 manifest hash | P0 |  |  |  |  |  | L110 |  |  |  |
| L112 | 患者级冻结 Train/Dev/Test | Patient overlap = 0 | P0 |  |  |  |  |  | L111 |  |  |  |

## 3.3 Luna Pilot 确认

| 检查项 | 目标/标准 | 实际结果 | 是否通过 | 证据/路径 | 备注 |
|---|---|---|---|---|---|
| 实际可调用的 Model ID | 记录完整 Model ID |  |  |  |  |
| Codex CLI 版本 | 固定并保存 |  |  |  |  |
| JSON Schema 合法率 | 建议 ≥99% |  |  |  |  |
| Evidence 原文命中率 | 建议 ≥98% |  |  |  |  |
| 重复 Sample ID | 0 |  |  |  |  |
| 未知标签/字段缺失 | 0 或全部 Fail-closed |  |  |  |  |
| 平均每批耗时 | 记录 |  |  |  |  |
| 批量失败率 | 记录 |  |  |  |  |
| 否定/不确定性 Stress Set | 达到预设召回 |  |  |  |  |
| 错误 PRIOR Reference 检出 | 达到预设召回 |  |  |  |  |

## 3.4 数据漏斗汇总

| Source | Candidate Patients | Candidate Pairs | Candidate Rows | Rule-valid | Luna Tier-A | Tier-B | Reject | Train Rows | Dev Rows | Test Rows | Audit Rows | Gold Quarantine |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| MIMIC-CXR |  |  |  |  |  |  |  |  |  |  |  |  |
| CheXpert |  |  |  |  |  |  |  |  |  |  |  |  |
| Other Approved Source |  |  |  |  |  |  |  |  |  |  |  |  |
| Total |  |  |  |  |  |  |  |  |  |  |  |  |

## 3.5 Luna 批次运行日志

> 复制模板行继续增加批次。每批必须保存 Prompt、Schema、Input 和 Output Hash。

| Batch ID | 样本数 | Model ID | Prompt Hash | Schema Hash | Input Hash | Output Hash | Tier-A | Tier-B | Reject | Invalid | Retries | 开始时间 | 结束时间 | 状态 | 备注 |
|---|---:|---|---|---|---|---|---:|---:|---:|---:|---:|---|---|---|---|
| batch_0001 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| batch_0002 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| batch_0003 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| batch_0004 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| batch_0005 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| batch_XXXX |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |

## 3.6 临床抽检与一致性

| Audit ID | Progression | Finding | Source | Luna Decision | Luna Label | Clinician Decision | Agreement | Second Review | Adjudicated Label | Evidence Sufficient? | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
|  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |

## 3.7 标签质量汇总

| Label Pipeline | Coverage | Clinician Agreement | New PPV | Resolved PPV | Improved PPV | Stable PPV | Worse PPV | Reject Precision | 95% CI | Notes |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| Rule-only |  |  |  |  |  |  |  |  |  |  |
| Luna Tier-A |  |  |  |  |  |  |  |  |  |  |
| Luna Tier-A+B |  |  |  |  |  |  |  |  |  |  |

## 3.8 标签冻结确认

- [ ] Pairing 规则已冻结。
- [ ] Luna Prompt、Schema 和 Model ID 已冻结。
- [ ] 非法输出处理为 Fail-closed。
- [ ] 抽检样本在全量标注完成前已通过固定随机种子抽取。
- [ ] 医生抽检只用于质量估计和规则级修订，不逐行手工修补全量标签。
- [ ] Prompt 或规则若修改，所有标签按新版本全量重跑。
- [ ] 历史 Test、Audit 和 Expert Gold 患者已全部排除。
- [ ] Train/Dev/Internal Test 的患者交集为 0。
- [ ] 数据许可、隐私和报告去标识已由负责人确认。

**数据版本**：  
**Label Manifest Hash**：  
**Split Manifest Hash**：  
**确认人**：  
**日期**：  
**决策**：`GO / HOLD / STOP`

---

# 4. Phase 2：主方法性能开发

## 4.1 简单说明

该阶段只使用 Train 和 Dev，目标是先明确绝对性能偏低来自数据规模、标签质量、类别不平衡、分类头还是 Adapter 范围。未达到开发出口门前，不批量运行正式 Baseline 和消融。

数据配置：

- **D0**：旧规模 + 旧规则标签；
- **D1**：扩展规模 + 旧规则标签；
- **D2**：扩展规模 + Luna Tier-A；
- **D3**：扩展规模 + Tier-A+B。

开发轴：

- Head：H0 / H1 / H2；
- Loss：Weighted CE / Balanced Softmax / Class-balanced Focal；
- Adapter Scope：最多两个候选；
- Screening 使用单 Seed；最终候选使用 Seeds 17/29/43。

## 4.2 开发任务清单

| 任务 ID | 任务 | 交付物/验收标准 | 优先级 | 负责人 | 计划完成 | 状态 | 实际完成 | 证据/路径 | 前置依赖 | 阶段决策 | 风险 | 备注 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| D201 | D0：旧规模 + 旧规则标签 | 新项目开发基准 | P0 |  |  |  |  |  |  |  |  |  |
| D202 | D1：扩展规模 + 旧规则标签 | 测量纯数据规模收益 | P0 |  |  |  |  |  | D201 |  |  |  |
| D203 | D2：扩展规模 + Luna Tier-A | 测量标签质量收益 | P0 |  |  |  |  |  | D202 |  |  |  |
| D204 | D3：扩展规模 + Tier-A+B | 质量—数量权衡 | P1 |  |  |  |  |  | D203 |  |  |  |
| M301 | H0/H1/H2 Head Screening | Seed 17 单轴筛选 | P0 |  |  |  |  |  | D203 |  |  |  |
| M302 | 类别不平衡 Loss Screening | WCE/BalSoftmax/CB-Focal | P0 |  |  |  |  |  | M301 |  |  |  |
| M303 | Adapter 范围 Screening | 最多两个候选 | P1 |  |  |  |  |  | M302 |  |  |  |
| M304 | 最终候选三 Seed 确认 | Seeds 17/29/43 | P0 |  |  |  |  |  | M303 |  |  |  |
| M305 | Dev 错误与类别诊断 | 低于出口门时执行 | P1 |  |  |  |  |  | M304 |  |  |  |
| M306 | Dev Performance Gate | F1/Recall/Prior Gap/ODER | P0 |  |  |  |  |  | M304 |  |  |  |
| M307 | 冻结最终 Checkpoint 选择规则 | 仅基于 Dev | P0 |  |  |  |  |  | M306 |  |  |  |
| M308 | 生成 Performance-development Report | 记录所有尝试与停止理由 | P1 |  |  |  |  |  | M307 |  |  |  |
| M309 | 确定 GO/HOLD/STOP | 进入正式实验前决策 | P0 |  |  |  |  |  | M308 |  |  |  |

## 4.3 开发结果登记

| Run ID | Axis | Data Config | Head | Loss | Adapter Scope | Seed | Dev Macro-F1 | Balanced Acc | Accuracy | Min Recall | Prior Gap | ODER | Train Hours | VRAM GB | Status | Decision | Evidence/Notes |
|---|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|
| D201 | Data | D0 | H0 | Weighted CE | Current | 17 |  |  |  |  |  |  |  |  |  |  |  |
| D202 | Data | D1 | H0 | Weighted CE | Current | 17 |  |  |  |  |  |  |  |  |  |  |  |
| D203 | Data | D2 | H0 | Weighted CE | Current | 17 |  |  |  |  |  |  |  |  |  |  |  |
| D204 | Data | D3 | H0 | Weighted CE | Current | 17 |  |  |  |  |  |  |  |  |  |  |  |
| M301-H0 | Head | D2 | H0 | Weighted CE | Current | 17 |  |  |  |  |  |  |  |  |  |  |  |
| M301-H1 | Head | D2 | H1 | Weighted CE | Current | 17 |  |  |  |  |  |  |  |  |  |  |  |
| M301-H2 | Head | D2 | H2 | Weighted CE | Current | 17 |  |  |  |  |  |  |  |  |  |  |  |
| M302-WCE | Loss | D2 |  | Weighted CE | Current | 17 |  |  |  |  |  |  |  |  |  |  |  |
| M302-BS | Loss | D2 |  | Balanced Softmax | Current | 17 |  |  |  |  |  |  |  |  |  |  |  |
| M302-CBF | Loss | D2 |  | CB-Focal | Current | 17 |  |  |  |  |  |  |  |  |  |  |  |
| M303-A | Adapter | D2 |  |  | Candidate-A | 17 |  |  |  |  |  |  |  |  |  |  |  |
| M303-B | Adapter | D2 |  |  | Candidate-B | 17 |  |  |  |  |  |  |  |  |  |  |  |
| M304-S17 | Confirm | Final | Final | Final | Final | 17 |  |  |  |  |  |  |  |  |  |  |  |
| M304-S29 | Confirm | Final | Final | Final | Final | 29 |  |  |  |  |  |  |  |  |  |  |  |
| M304-S43 | Confirm | Final | Final | Final | Final | 43 |  |  |  |  |  |  |  |  |  |  |  |

## 4.4 Scaling 结果

| Train Fraction | Patients | Rows | Label Tier | Strong Baseline F1 | PRTA F1 | Gain | CI Low | CI High | Seed Count | Notes |
|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---|
| 10% |  |  |  |  |  |  |  |  |  |  |
| 25% |  |  |  |  |  |  |  |  |  |  |
| 50% |  |  |  |  |  |  |  |  |  |  |
| 75% |  |  |  |  |  |  |  |  |  |  |
| 100% |  |  |  |  |  |  |  |  |  |  |

## 4.5 开发出口门

建议门，不代表临床部署门：

- Dev Macro-F1 建议 ≥ 0.52，理想目标 ≥ 0.55；
- 相对最强简单 Temporal Baseline 建议 ≥ +3 pp；
- 最差类别 Recall 建议 ≥ 0.20，理想 ≥ 0.30；
- True PRIOR 明显优于 Matched-wrong PRIOR；
- ODER 不高于最强 Baseline；
- 三 Seed 无单一 Seed 崩溃。

| 指标 | 预设门槛 | 实际结果 | 是否通过 | 备注 |
|---|---:|---:|---|---|
| Dev Macro-F1 |  |  |  |  |
| 相对最强 Baseline 增益 |  |  |  |  |
| Min-class Recall |  |  |  |  |
| True–Wrong PRIOR Gap |  |  |  |  |
| ODER |  |  |  |  |
| 三 Seed 稳定性 |  |  |  |  |

**开发结论**：`GO / HOLD / STOP`  
**冻结候选 Config**：  
**负责人**：  
**日期**：  
**说明**：

---

# 5. Phase 3：正式协议冻结

## 5.1 冻结任务

| 任务 ID | 任务 | 交付物/验收标准 | 优先级 | 负责人 | 计划完成 | 状态 | 实际完成 | 证据/路径 | 前置依赖 | 阶段决策 | 风险 | 备注 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| F301 | 冻结 Data/Label Manifests | SHA256 Receipt | P0 |  |  |  |  |  |  |  |  |  |
| F302 | 冻结方法与 Baseline Configs | 不可因 Test 修改 | P0 |  |  |  |  |  | F301 |  |  |  |
| F303 | 冻结指标、统计和 Seeds | Macro-F1 为主指标 | P0 |  |  |  |  |  | F302 |  |  |  |
| F304 | 冻结案例选择规则 | 成功/失败桶随机抽取 | P1 |  |  |  |  |  | F303 |  |  |  |
| F305 | 生成 Protocol Freeze Receipt | 允许正式 Test 一次读取 | P0 |  |  |  |  |  | F304 |  |  |  |

## 5.2 Freeze Receipt

| 项目 | 冻结值/Hash | 文件路径 | 确认人 | 日期 | 备注 |
|---|---|---|---|---|---|
| Git Commit |  |  |  |  |  |
| Environment Lock |  |  |  |  |  |
| Train Manifest |  |  |  |  |  |
| Dev Manifest |  |  |  |  |  |
| Internal Test Manifest |  |  |  |  |  |
| Gold Quarantine Manifest |  |  |  |  |  |
| Label Manifest |  |  |  |  |  |
| Luna Prompt |  |  |  |  |  |
| Luna Schema |  |  |  |  |  |
| Final PRTA Config |  |  |  |  |  |
| Baseline Config Bundle |  |  |  |  |  |
| Metrics/Bootstrap Script |  |  |  |  |  |
| Case Selection Rule |  |  |  |  |  |

## 5.3 正式测试解封确认

- [ ] 所有开发仅基于 Train/Dev 完成。
- [ ] Internal Test Outcome 尚未被任何开发脚本读取。
- [ ] Expert Gold Outcome 尚未被读取。
- [ ] Temperature、Threshold 和 Checkpoint 选择规则已经冻结。
- [ ] Baseline 和 Ablation 列表已经冻结。
- [ ] 正式结果空表已经创建。
- [ ] 正式预测脚本只写预测，不修改模型。
- [ ] 解封时间和执行人会写入不可覆盖日志。

**批准解封人**：  
**执行人**：  
**批准日期**：  
**允许读取的数据**：  
**解封决策**：`GO / HOLD / STOP`

---

# 6. Phase 4：正式 Baseline 对比

## 6.1 简单说明

正式比较只回答“PRTA 作为纵向 ViT 分类器是否优于合理的替代方法”。不再做 matched-representation benchmark，也不把 Baseline 强行部署到 VLM。

最小 Baseline 集：

1. Current-only BiomedCLIP；
2. Siamese Signed/Absolute Difference；
3. TILA 或等价强 Temporal Attention；
4. PRTA-CXR；
5. BioViL-T 仅在能够稳定公平复现时作为可选项。

## 6.2 Baseline 任务清单

| 任务 ID | 方法 | 交付物/验收标准 | 是否必需 | 负责人 | 状态 | 证据/路径 | 风险 | 备注 |
|---|---|---|---|---|---|---|---|---|
| B401 | Current-only BiomedCLIP | 三 Seed + 正式预测 | 必需 |  |  |  |  |  |
| B402 | Siamese Signed/Absolute Diff | 三 Seed + 正式预测 | 必需 |  |  |  |  |  |
| B403 | TILA / Strong Temporal Attention | 合理原生实现 | 必需 |  |  |  |  |  |
| B404 | PRTA-CXR Final | 最终主方法 | 必需 |  |  |  |  |  |
| B405 | BioViL-T | 仅稳定可复现时 | 可选 |  |  |  |  |  |

## 6.3 正式结果汇总

| Method | Required | Backbone | Temporal Fusion | Params M | Trainable M | Macro-F1 Mean | SD | CI Low | CI High | Balanced Acc | Accuracy | Min Recall | ODER | Train Hours | VRAM GB | Latency | Notes |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Current-only | 必需 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| Siamese Diff | 必需 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TILA | 必需 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| PRTA-CXR | 必需 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| BioViL-T | 可选 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |

## 6.4 Seed 级运行结果

| Exp ID | Method | Seed | Backbone | Fusion | Head | Params M | Trainable M | Train h | VRAM | Latency | Macro-F1 | Balanced Acc | Accuracy | Min Recall | ODER | NLL | Brier | ECE | CI Low | CI High | Status | Checkpoint | Predictions | Metrics | Notes |
|---|---|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|---|---|
| B401-S17 | Current-only | 17 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| B401-S29 | Current-only | 29 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| B401-S43 | Current-only | 43 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| B402-S17 | Siamese Diff | 17 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| B402-S29 | Siamese Diff | 29 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| B402-S43 | Siamese Diff | 43 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| B403-S17 | TILA | 17 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| B403-S29 | TILA | 29 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| B403-S43 | TILA | 43 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| B404-S17 | PRTA-CXR | 17 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| B404-S29 | PRTA-CXR | 29 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| B404-S43 | PRTA-CXR | 43 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| B405-S17 | BioViL-T | 17 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| B405-S29 | BioViL-T | 29 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| B405-S43 | BioViL-T | 43 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |

## 6.5 公平性确认

- [ ] 所有方法使用同一患者划分和同一标签版本。
- [ ] 所有方法使用同一图像预处理和 finding 集合。
- [ ] 所有方法使用相同 Seeds 17/29/43。
- [ ] 各方法可使用合理原生 Head，但参数量和训练预算已登记。
- [ ] 未因为某一方法 Test 表现较差而额外调参。
- [ ] Optional Baseline 的缺失不会改变主结论定义。
- [ ] 所有配对统计均由同一评估脚本生成。

**确认人**：  
**日期**：  
**结论**：

---

# 7. Phase 5：正式消融实验

## 7.1 简单说明

消融只删除一个科学组件，其他数据、分类头、损失、训练预算和 Seeds 保持一致。消融不只观察 Macro-F1，还要观察 Prior Gap、时间方向和 ODER。

## 7.2 消融任务

| 任务 ID | Variant | 移除内容 | 验收目的 | 优先级 | 负责人 | 状态 | 证据/路径 | 备注 |
|---|---|---|---|---|---|---|---|---|
| A500 | Full PRTA | 无 | 正式参考 | P0 |  |  |  |  |
| A501 | w/o Finding Conditioning | 移除 q_f | 检验 finding 条件控制 | P0 |  |  |  |  |
| A502 | w/o Cross-time Alignment | 移除 Patch Alignment | 检验软对应价值 | P0 |  |  |  |  |
| A503 | w/o Dual Branch | 合并 State/Transition | 检验显式解耦 | P0 |  |  |  |  |
| A504 | w/o CMCP | 移除 Counterfactual PRIOR | 检验正确 PRIOR 依赖 | P0 |  |  |  |  |
| A505 | w/o Temporal Inversion | 移除反转约束 | 检验时间方向性 | P0 |  |  |  |  |
| A506 | w/o State Preservation | 移除 State Loss | 检验当前状态保持 | P0 |  |  |  |  |
| A507 | Rule-only Labels | 替换 Luna Tier-A | 数据监督消融，可选 | P2 |  |  |  |  |

## 7.3 消融汇总

| Variant | Finding | Alignment | Dual Branch | CMCP | Inversion | State Preserve | Macro-F1 | Δ Full | Prior Gap | ODER | CI Low | CI High | Status | Interpretation |
|---|---|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---|---|
| Full PRTA | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |  |  |  |  |  |  |  |  |
| w/o Finding |  | ✓ | ✓ | ✓ | ✓ | ✓ |  |  |  |  |  |  |  |  |
| w/o Alignment | ✓ |  | ✓ | ✓ | ✓ | ✓ |  |  |  |  |  |  |  |  |
| w/o Dual Branch | ✓ | ✓ |  | ✓ | ✓ | ✓ |  |  |  |  |  |  |  |  |
| w/o CMCP | ✓ | ✓ | ✓ |  | ✓ | ✓ |  |  |  |  |  |  |  |  |
| w/o Inversion | ✓ | ✓ | ✓ | ✓ |  | ✓ |  |  |  |  |  |  |  |  |
| w/o State Preserve | ✓ | ✓ | ✓ | ✓ | ✓ |  |  |  |  |  |  |  |  |  |
| Rule-only Labels | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |  |  |  |  |  |  |  |  |

## 7.4 Seed 级结果

| Exp ID | Variant | Seed | Macro-F1 | Balanced Acc | Accuracy | Min Recall | Prior Gap | ODER | NLL | Brier | Train h | VRAM | Status | Checkpoint | Predictions | Metrics | Notes |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|---|---|
| A500-S17 | Full PRTA | 17 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| A500-S29 | Full PRTA | 29 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| A500-S43 | Full PRTA | 43 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| A501-S17 | w/o Finding | 17 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| A501-S29 | w/o Finding | 29 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| A501-S43 | w/o Finding | 43 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| A502-S17 | w/o Alignment | 17 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| A502-S29 | w/o Alignment | 29 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| A502-S43 | w/o Alignment | 43 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| A503-S17 | w/o Dual Branch | 17 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| A503-S29 | w/o Dual Branch | 29 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| A503-S43 | w/o Dual Branch | 43 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| A504-S17 | w/o CMCP | 17 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| A504-S29 | w/o CMCP | 29 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| A504-S43 | w/o CMCP | 43 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| A505-S17 | w/o Inversion | 17 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| A505-S29 | w/o Inversion | 29 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| A505-S43 | w/o Inversion | 43 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| A506-S17 | w/o State Preserve | 17 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| A506-S29 | w/o State Preserve | 29 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| A506-S43 | w/o State Preserve | 43 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| A507-S17 | Rule-only Labels | 17 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| A507-S29 | Rule-only Labels | 29 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| A507-S43 | Rule-only Labels | 43 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |

## 7.5 消融执行确认

- [ ] 每个变体只删除一个组件。
- [ ] 所有变体共享同一数据和标签版本。
- [ ] 所有变体共享最终分类头和训练预算。
- [ ] 所有变体使用 Seeds 17/29/43。
- [ ] 变体定义在读取正式 Test 前冻结。
- [ ] 不因为某个变体结果异常而增加额外训练轮数。
- [ ] 解释同时基于性能指标和机制指标。

---

# 8. Phase 6：可信性、校准与亚组

## 8.1 简单说明

该阶段多数实验只对最终冻结 Checkpoint 做推理，不重新训练模型。核心不是证明“任意扰动都会改变预测”，而是验证正确 PRIOR、错误 PRIOR、缺失 PRIOR 和错误 Query 对预测与置信度造成的变化是否符合方法主张。

## 8.2 任务清单

| 任务 ID | 任务 | 交付物/验收标准 | 优先级 | 负责人 | 状态 | 证据/路径 | 备注 |
|---|---|---|---|---|---|---|---|
| T601 | True PRIOR Reference | 冻结 Checkpoint 推理 | P0 |  |  |  |  |
| T602 | Current-only / Null PRIOR | 缺失信息实验 | P0 |  |  |  |  |
| T603 | Random PRIOR | 任意历史扰动 | P1 |  |  |  |  |
| T604 | Matched-wrong PRIOR | 困难错误历史 | P0 |  |  |  |  |
| T605 | Reversed Pair | 时间方向 | P0 |  |  |  |  |
| T606 | Wrong Finding Query | Finding 条件检验 | P0 |  |  |  |  |
| T607 | Temperature Scaling | 只在 Dev 拟合 | P0 |  |  |  |  |
| T608 | ECE/Brier/NLL | 测试校准 | P0 |  |  |  |  |
| T609 | Risk-coverage / AURC | 选择性预测 | P0 |  |  |  |  |
| T610 | Progression Subgroup | 五类结果 | P1 |  |  |  |  |
| T611 | Finding Subgroup | 按 Finding | P1 |  |  |  |  |
| T612 | Source Subgroup | 跨来源 | P1 |  |  |  |  |
| T613 | View / Interval Subgroup | 视图与时间间隔 | P1 |  |  |  |  |
| T614 | Multiple-comparison Correction | 多重比较校正 | P1 |  |  |  |  |

## 8.3 PRIOR / Query 干预结果

| Input Condition | Seed | Macro-F1 | Δ vs True | NLL | Brier | Mean Confidence | Flip Rate | C→W | W→C | ODER | CI Low | CI High | Status | Prediction Path | Notes |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|
| True PRIOR | 17 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| True PRIOR | 29 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| True PRIOR | 43 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| Current-only | 17 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| Current-only | 29 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| Current-only | 43 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| Null PRIOR | 17 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| Null PRIOR | 29 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| Null PRIOR | 43 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| Random PRIOR | 17 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| Random PRIOR | 29 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| Random PRIOR | 43 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| Matched-wrong PRIOR | 17 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| Matched-wrong PRIOR | 29 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| Matched-wrong PRIOR | 43 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| Reversed Pair | 17 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| Reversed Pair | 29 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| Reversed Pair | 43 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| Wrong Query | 17 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| Wrong Query | 29 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| Wrong Query | 43 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |

## 8.4 校准与选择性预测

| Method | NLL | Brier | ECE | AURC | Risk@90% | Risk@80% | Risk@70% | Temperature | Status | Notes |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| Strongest Baseline |  |  |  |  |  |  |  |  |  |  |
| PRTA-CXR |  |  |  |  |  |  |  |  |  |  |

## 8.5 亚组结果

| Subgroup Type | Subgroup | N Patients | N Rows | Macro-F1 | Balanced Acc | Min Recall | ODER | CI Low | CI High | p Raw | p Adjusted | Notes |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Progression |  |  |  |  |  |  |  |  |  |  |  |  |
| Finding |  |  |  |  |  |  |  |  |  |  |  |  |
| Source |  |  |  |  |  |  |  |  |  |  |  |  |
| View |  |  |  |  |  |  |  |  |  |  |  |  |
| Interval |  |  |  |  |  |  |  |  |  |  |  |  |

## 8.6 Trust 阶段确认

- [ ] True PRIOR 使用完全相同的冻结预测协议。
- [ ] Wrong/Random PRIOR 的构造规则在看到结果前冻结。
- [ ] Reversed Pair 使用固定标签置换。
- [ ] Wrong Query 不改变图像对，仅改变 Finding Query。
- [ ] Temperature 只在 Dev 拟合。
- [ ] Internal Test 和 Gold 只评价冻结温度。
- [ ] 亚组同时报告样本量与置信区间。
- [ ] 不把输入干预描述为现实世界临床因果效应。

**阶段决策**：`GO / HOLD / STOP`  
**主要发现**：  
**主要风险**：

---

# 9. Phase 7：可视化与失败分析

## 9.1 简单说明

可视化必须服务于一个明确问题：数据如何构建、性能如何随数据规模变化、错误集中在哪里、模型是否使用正确 PRIOR、置信度是否可信。不能只放装饰性 Attention Map，也不能只展示成功病例。

## 9.2 Figure 任务清单

| 任务 ID | Figure | 内容 | 验收目的 | 优先级 | 负责人 | 状态 | 证据/路径 | 备注 |
|---|---|---|---|---|---|---|---|---|
| V701 | Figure 1 | 方法 + 标签 Pipeline | 主流程图 | P0 |  |  |  |  |
| V702 | Figure 2 | 数据漏斗/分布/拒绝原因 | 数据可信性 | P0 |  |  |  |  |
| V703 | Figure 3 | Scaling Curve | 数据规模作用 | P0 |  |  |  |  |
| V704 | Figure 4 | Paired-effect Forest Plot | 主效应与 CI | P0 |  |  |  |  |
| V705 | Figure 5 | Confusion Matrix + ODER | 错误结构 | P0 |  |  |  |  |
| V706 | Figure 6 | Finding × Progression Heatmap | 亚组困难度 | P1 |  |  |  |  |
| V707 | Figure 7 | Calibration + Risk Coverage | 不确定性 | P0 |  |  |  |  |
| V708 | Figure 8 | PRIOR/Query 干预案例 | 机制与失败案例 | P0 |  |  |  |  |

## 9.3 Figure 生产登记

| Figure | Title | Input Dependencies | Plot Type | Case Selection Rule | Must Include Failure? | Main/Supp | Status | Owner | Output Path | Caption Draft | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| F1 | 方法与标签构建总 Pipeline |  | Diagram | N/A | 否 | Main |  |  |  |  |  |
| F2 | 数据漏斗与拒绝原因 |  | Funnel + Hist | N/A | 否 | Main |  |  |  |  |  |
| F3 | Data Scaling Curve |  | Line | 全部冻结运行 | 否 | Main |  |  |  |  |  |
| F4 | Paired-effect Forest Plot |  | Forest | 全部正式 Baseline | 否 | Main |  |  |  |  |  |
| F5 | Confusion Matrix + ODER |  | Heatmap | 全部测试样本 | 是 | Main |  |  |  |  |  |
| F6 | Finding × Progression |  | Heatmap | 全部合格单元格 | 否 | Main/Supp |  |  |  |  |  |
| F7 | Calibration / Risk Coverage |  | Line + Reliability | 全部测试样本 | 是 | Main |  |  |  |  |  |
| F8 | PRIOR/Query Intervention Cases |  | Multi-panel | 冻结桶内随机抽取 | 是 | Main |  |  |  |  |  |

## 9.4 案例选择记录

| Bucket | Eligible N | Random Seed | Selected Case IDs | Reviewer | Failure Included? | Selection Script | Notes |
|---|---:|---:|---|---|---|---|---|
| 正确高置信 |  |  |  |  |  |  |  |
| 正确低置信 |  |  |  |  |  |  |  |
| 错误高置信 |  |  |  |  |  |  |  |
| 正确拒答/低覆盖 |  |  |  |  |  |  |  |
| Wrong PRIOR 敏感案例 |  |  |  |  |  |  |  |
| Wrong Query 敏感案例 |  |  |  |  |  |  |  |

## 9.5 可视化确认

- [ ] 所有图由脚本生成，不手工修改数据点。
- [ ] 所有图保留输入数据路径和生成命令。
- [ ] Forest Plot 使用配对效应和患者聚类 CI。
- [ ] Heatmap 同时报告样本量或在补充材料给出 N。
- [ ] 案例按冻结规则抽取。
- [ ] 正文至少包含一个失败案例。
- [ ] Attention/Heatmap 不被描述为因果解释。

---

# 10. Phase 8：PRTA → VLM 附加部署

## 10.1 简单说明

这不是第二条主方法。只有 ViT 的正式结果、消融和可信性分析全部完成后，才允许使用最终唯一 PRTA Checkpoint 接入一个 VLM。结果好坏不反向修改 PRTA。

## 10.2 任务清单

| 任务 ID | 任务 | 交付物/验收标准 | 优先级 | 负责人 | 状态 | 证据/路径 | 备注 |
|---|---|---|---|---|---|---|---|
| X801 | 冻结最终 PRTA Checkpoint | 不得因 VLM 回改 ViT | P0 |  |  |  |  |
| X802 | 迁移 Fixed-token/Projector 代码 | 仅迁移最终需要模块 | P1 |  |  |  |  |
| X803 | 训练轻量 Projector/Post-train | 一个固定协议 | P1 |  |  |  |  |
| X804 | 结构化 Progression 评估 | Macro-F1 + Schema Validity | P1 |  |  |  |  |
| X805 | 简短比较句定性展示 | 成功 + 失败案例 | P2 |  |  |  |  |
| X806 | 生成附加结果表与讨论 | 不引入 VLM Baseline 矩阵 | P1 |  |  |  |  |

## 10.3 附加部署结果

| Visual Model | VLM | LLM Training | Output | Macro-F1 | Schema Validity | Finding Consistency | Temporal Contradiction | Trainable M | Train Hours | Status | Notes |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---|---|
| Final PRTA-CXR |  | Frozen / Light Post-train | Structured Progression |  |  |  |  |  |  |  |  |

## 10.4 定性案例登记

| Case ID | Finding | Reference Progression | ViT Prediction | VLM Structured | VLM Sentence | PRIOR Used Correctly? | Hallucination? | Temporal Contradiction? | Use in Paper? | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
|  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |

## 10.5 VLM 范围确认

- [ ] 使用最终唯一 PRTA Checkpoint。
- [ ] 不把 Baseline 强行部署成 VLM。
- [ ] 不做完整 VLM 架构搜索和消融矩阵。
- [ ] VLM 结果不反向修改 ViT 方法。
- [ ] 自由文本只作定性展示；没有医生评价时不声称报告生成已被临床验证。
- [ ] VLM 失败时允许删除该小节，不影响主论文结论。

---

# 11. 统一 Run Registry

> 每个训练、评估、干预、校准和图表生成任务都必须登记。复制模板行继续添加。

| Run ID | Experiment ID | Date | Owner | Git Commit | Config Path | Config Hash | Split Hash | Label Hash | Seed | GPU | Start Time | End Time | Duration h | Status | Checkpoint Path | Prediction Path | Metrics Path | Log Path | Notes |
|---|---|---|---|---|---|---|---|---|---:|---|---|---|---:|---|---|---|---|---|---|
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |

## 11.1 单次 Run 关闭确认

- [ ] Run ID 唯一。
- [ ] Commit、Config、Split 和 Label Hash 已记录。
- [ ] Checkpoint、Prediction、Metrics 和 Log 均存在。
- [ ] 运行失败时保留日志，不覆盖原 Run。
- [ ] 样本数、患者数和 Label 分布与 Manifest 一致。
- [ ] 没有 NaN、重复 Sample ID 或缺失预测。
- [ ] 结果由脚本生成，没有手工改 CSV/JSON。
- [ ] 本 Run 是否允许进入论文汇总已经记录。

**关闭人**：  
**日期**：  
**Run 结论**：`有效 / 无效 / 需重跑 / 仅诊断`

---

# 12. 论文正文空表

> 以下表格面向论文正文或补充材料，所有结果字段保持空白。方法和条件名称可在协议冻结前调整一次，冻结后不得因结果改变。

## Table 1：数据与标签构建

| Source | Candidate Patients | Candidate Pairs | Candidate Rows | Rule-valid | Luna Tier-A | Tier-B | Reject | Train | Dev | Test | Gold Quarantine |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| MIMIC-CXR |  |  |  |  |  |  |  |  |  |  |  |
| CheXpert |  |  |  |  |  |  |  |  |  |  |  |
| Other |  |  |  |  |  |  |  |  |  |  |  |
| Total |  |  |  |  |  |  |  |  |  |  |  |

## Table 2：标签质量审计

| Label Pipeline | Coverage | Clinician Agreement | New PPV | Resolved PPV | Improved PPV | Stable PPV | Worse PPV | Reject Precision | 95% CI |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Rule-only |  |  |  |  |  |  |  |  |  |
| Luna Tier-A |  |  |  |  |  |  |  |  |  |
| Luna Tier-A+B |  |  |  |  |  |  |  |  |  |

## Table 3：正式主结果

| Method | Backbone | Temporal Fusion | Params | Trainable Params | Macro-F1 | Balanced Acc | Accuracy | Min Recall | ODER | 95% CI |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| Current-only |  |  |  |  |  |  |  |  |  |  |
| Siamese Diff |  |  |  |  |  |  |  |  |  |  |
| TILA |  |  |  |  |  |  |  |  |  |  |
| PRTA-CXR |  |  |  |  |  |  |  |  |  |  |
| BioViL-T（可选） |  |  |  |  |  |  |  |  |  |  |

## Table 4：数据规模与标签质量

| Train Fraction | Patients | Rows | Label Tier | Strong Baseline F1 | PRTA F1 | Gain | 95% CI |
|---|---:|---:|---|---:|---:|---:|---|
| 10% |  |  |  |  |  |  |  |
| 25% |  |  |  |  |  |  |  |
| 50% |  |  |  |  |  |  |  |
| 75% |  |  |  |  |  |  |  |
| 100% |  |  |  |  |  |  |  |

## Table 5：方法消融

| Variant | Finding | Alignment | Dual Branch | CMCP | Inversion | State Preserve | Macro-F1 | Prior Gap | ODER | 95% CI |
|---|---|---|---|---|---|---|---:|---:|---:|---|
| Full PRTA | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |  |  |  |  |
| w/o Finding |  | ✓ | ✓ | ✓ | ✓ | ✓ |  |  |  |  |
| w/o Alignment | ✓ |  | ✓ | ✓ | ✓ | ✓ |  |  |  |  |
| w/o Dual Branch | ✓ | ✓ |  | ✓ | ✓ | ✓ |  |  |  |  |
| w/o CMCP | ✓ | ✓ | ✓ |  | ✓ | ✓ |  |  |  |  |
| w/o Inversion | ✓ | ✓ | ✓ | ✓ |  | ✓ |  |  |  |  |
| w/o State Preserve | ✓ | ✓ | ✓ | ✓ | ✓ |  |  |  |  |  |
| Rule-only Labels | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |  |  |  |  |

## Table 6：可信输入干预

| Input Condition | Macro-F1 | Δ vs True | NLL | Brier | Confidence | Flip Rate | C→W | W→C | ODER | 95% CI |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| True PRIOR |  |  |  |  |  |  |  |  |  |  |
| Current-only |  |  |  |  |  |  |  |  |  |  |
| Null PRIOR |  |  |  |  |  |  |  |  |  |  |
| Random PRIOR |  |  |  |  |  |  |  |  |  |  |
| Matched-wrong PRIOR |  |  |  |  |  |  |  |  |  |  |
| Reversed Pair |  |  |  |  |  |  |  |  |  |  |
| Wrong Query |  |  |  |  |  |  |  |  |  |  |

## Table 7：校准与选择性预测

| Method | NLL | Brier | ECE | AURC | Risk@90% | Risk@80% | Risk@70% |
|---|---:|---:|---:|---:|---:|---:|---:|
| Strongest Baseline |  |  |  |  |  |  |  |
| PRTA-CXR |  |  |  |  |  |  |  |

## Table 8：VLM 附加部署

| Visual Model | VLM Setting | Output | Macro-F1 | Schema Validity | Finding Consistency | Temporal Contradiction | Notes |
|---|---|---|---:|---:|---:|---:|---|
| Final PRTA-CXR |  | Structured Progression |  |  |  |  |  |

---

# 13. 补充确认与审计表

## 13.1 数据许可与隐私确认

| 检查项 | 负责人 | 状态 | 证据/路径 | 备注 |
|---|---|---|---|---|
| 数据集许可允许研究训练/评估 |  |  |  |  |
| 报告已经去标识 |  |  |  |  |
| 未向 Codex 提交真实患者身份信息 |  |  |  |  |
| 原始报告与模型输出不进入公开 Git |  |  |  |  |
| 审计医生仅访问获准数据 |  |  |  |  |
| 数据删除/缓存策略已记录 |  |  |  |  |

## 13.2 Patient Leakage 确认

| 检查 | Train | Dev | Internal Test | Audit | Expert Gold | 是否通过 | 证据 |
|---|---:|---:|---:|---:|---:|---|---|
| 患者数 |  |  |  |  |  |  |  |
| 与 Train 重叠 | — |  |  |  |  |  |  |
| 与 Dev 重叠 |  | — |  |  |  |  |  |
| 与 Internal Test 重叠 |  |  | — |  |  |  |  |
| 与 Audit 重叠 |  |  |  | — |  |  |  |
| 与 Expert Gold 重叠 |  |  |  |  | — |  |  |

## 13.3 协议偏差登记

> 任何偏离冻结协议的行为必须在运行前登记；事后补记不能作为正常变更。

| Deviation ID | Date | 原协议 | 拟修改内容 | 修改原因 | 是否接触 Test/Gold | 批准人 | 决策 | 新版本/Hash | 影响范围 | 备注 |
|---|---|---|---|---|---|---|---|---|---|---|
|  |  |  |  |  |  |  |  |  |  |  |
|  |  |  |  |  |  |  |  |  |  |  |

## 13.4 Gold 解封与运行登记

| 项目 | 内容 |
|---|---|
| Gold Manifest Hash |  |
| 冻结 Model Checkpoint Hash |  |
| 冻结 Config Hash |  |
| 冻结 Temperature/Threshold |  |
| 执行日期 |  |
| 执行人 |  |
| 监督/见证人 |  |
| 原始 Predictions Path |  |
| Predictions Hash |  |
| Metrics Path |  |
| 是否第一次读取 Outcome |  |
| 是否发生异常 |  |
| 异常处理 |  |

## 13.5 论文提交前确认

- [ ] 主结论不依赖单个 Seed。
- [ ] 主结果包含患者聚类置信区间。
- [ ] 训练数据、开发数据、Internal Test 和 Gold 的患者重叠为 0。
- [ ] Luna 标签在全文中没有被错误称为人工 Gold。
- [ ] 医生抽检规模、抽样方法和局限已经公开说明。
- [ ] Baseline 使用合理原生实现，未强行适配 VLM。
- [ ] 消融只删除一个组件，且使用相同数据与预算。
- [ ] Wrong PRIOR、Null PRIOR、Wrong Query 和 Reverse 测试已完成。
- [ ] Calibration 和 Risk-coverage 已完成。
- [ ] 正文同时展示成功与失败案例。
- [ ] 没有把 Attention Map 描述成内部因果证明。
- [ ] 没有宣称达到临床部署水平。
- [ ] VLM 明确写为 Additional Deployment，而非第二主方法。
- [ ] 代码、配置、Manifest、Prompt、Schema 和最终预测均有 Hash。
- [ ] 所有最终表格数字可由脚本自动复算。

**最终内部评审结论**：`GO / HOLD / STOP`  
**评审人**：  
**日期**：  
**剩余阻断项**：

---

# 14. 字段字典

## 14.1 推荐状态

| 字段 | 可选值 |
|---|---|
| 状态 | 未开始 / 进行中 / 已完成 / 阻塞 / 暂停 / 不适用 |
| 优先级 | P0 / P1 / P2 / P3 |
| Seed | 17 / 29 / 43 / N/A |
| Split | Train / Dev / Internal-test / Expert-Gold / Audit / N/A |
| 标签层级 | Rule-only / Tier-A / Tier-B / Tier-A+B / Reject / N/A |
| Progression | Stable / Improved / Worse / New / Resolved / N/A |
| Luna Decision | Accept / Tier-B / Reject / Conflict / Uncertain / N/A |
| 阶段决策 | GO / HOLD / STOP |

## 14.2 关键指标定义

| 指标 | 含义 | 统计单位/备注 |
|---|---|---|
| Macro-F1 | 五类 F1 的等权平均 | 主指标 |
| Balanced Accuracy | 各类 Recall 的平均 | 类别不平衡补充指标 |
| Min Recall | 五类中最低 Recall | 检查是否完全放弃少数类 |
| ODER | Improved↔Worse、New↔Resolved 的相反方向错误率 | 时间方向严重错误 |
| Prior Gap | True PRIOR 与 Wrong/Null PRIOR 的性能差 | 必须说明具体定义 |
| ECE | 置信度校准误差 | Bin 方案需固定 |
| AURC | Risk–Coverage 曲线下面积 | 越低通常越好 |
| C→W | 原正确预测在干预后变错 | Correct to Wrong |
| W→C | 原错误预测在干预后变对 | Wrong to Correct |

---

# 15. GO / HOLD / STOP 建议门

| 阶段 | GO | HOLD | STOP / 降低主张 |
|---|---|---|---|
| 重构 | Parity、Tests、Leakage 全通过 | 存在可解释的非核心差异 | 无法复现核心 PRTA |
| 标签 | 总体医生一致率建议 ≥90%，各类建议 ≥80% | 修 Prompt/Rules 后全量重跑 | 报告无法稳定支持五类任务 |
| 开发 | Dev F1 达到预设门并优于强 Baseline | 0.48–0.52 或少数类不足，先诊断 | <0.48 且 Scaling 已饱和 |
| 正式对比 | PRTA 跨 Seed 稳定优于强 Baseline | 均值正向但 CI/功效不足 | 趋势反转或依赖单 Seed |
| 可信性 | True PRIOR 优于 Wrong/Null，且置信度合理下降 | 少数亚组异常 | Wrong PRIOR 不降或产生更高错误置信 |
| Gold | 总体和多数来源趋势支持 | 正向但 CI 宽 | Gold 趋势明显反转 |
| VLM | 附加部署有效且不破坏主线 | 仅保留定性展示 | 删除附加部分，不影响主论文 |

---

# 16. 最终填写顺序

```text
1. 先填写 Phase 0 重构和 Parity
2. 再填写 Phase 1 Luna Pilot、数据漏斗和医生抽检
3. 填写 Phase 2 开发结果，确定最终方法
4. 完成 Freeze Receipt 和测试解封确认
5. 填写 Baseline 和 Ablation
6. 填写 Trust、Calibration 和 Subgroup
7. 生成并登记全部 Figure
8. 最后填写 Expert Gold 与 VLM 附加结果
9. 将正式结果同步回论文 Table 1–8
10. 完成提交前确认
```

