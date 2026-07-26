# R25.1 语义勘误与 R26 进展分类执行规范

状态：`ACTIVE_EXECUTION_AUTHORITY`

日期：2026-07-26

历史基线：`dd9c242`（仅作为 R25 Session 5 dry-run 历史证据保留）

执行分支：`r25.1-semantic-repair`

## 1. 总判断

VisualVIT 值得继续。核心研究问题不是“给 ViT 加一个模块”，而是：

> 在纵向影像推理中，模型失败的关键原因之一，是否是它没有显式知道上一张图中的哪个实体对应当前图中的哪个实体？

当前 R25 不能回答 Stable/Improved/Worse 是否可由 BiomedCLIP 特征预测，也不能回答正确身份绑定是否改善该预测。原因不是模型已经被证伪，而是指标空间混淆：

- `record["progression"]` 虽在 cohort 中保存，但没有进入 R25 `_evaluate` 的预测或评估；
- `three_event_macro_f1` 来自 persistent/death/birth 匹配事件混淆矩阵；
- R25 cohort 是 persistent-only，因此另两个无支持类别被按零 F1 纳入宏平均，完美 persistent 事件识别也约为 `1/3`；
- R25 的 B4 只比较 assignment 与 derangement 的结构一致性/恢复，不是进展分类的 B4b-B4a 效应。

因此，R25 Q4 的失败不得解释为“视觉特征无法判断 Stable/Improved/Worse”，也不得触发 RAD-DINO rescue。

## 2. 本勘误立即生效的术语

### 2.1 Matching 空间

对象是跨时间对应关系，允许的指标名仅包括：

- `persistent_edge_precision`
- `persistent_edge_recall`
- `persistent_edge_f1`
- `exact_row_recovery`
- `matching_event_macro_f1`，类别为 persistent/death/birth
- `delta_match`，正确 assignment 与随机/deranged assignment 的匹配指标差

任何 matching 指标都不得带有 `progression`、`change classification` 或 Stable/Improved/Worse 的解释。

### 2.2 Progression 空间

对象是实体级临床变化标签，标签闭集为：

- `Stable`
- `Improved`
- `Worse`

允许的指标名包括：

- `progression_macro_f1`
- `progression_balanced_accuracy`
- `progression_per_class_f1`
- `delta_bind = 100 * (F1_B4b - F1_B4a)`

只有当每条预测记录同时包含真实 `progression_target` 和模型产生的 `progression_prediction`，并且二者进入三类混淆矩阵时，才允许报告 progression 指标。

## 3. R25.1 的范围

R25.1 是 semantic repair，不增加模型与算力。

### 3.1 必须完成

1. 把 `three_event_macro_f1` 重命名为 `matching_event_macro_f1`。
2. 把 R25 `Q4_REAL_SIGNAL` 改为匹配资格门，不再使用任何伪 progression 指标。
3. 在产物中显式写入两个命名空间：
   - `matching_evaluation.status = EVALUATED`
   - `progression_evaluation.status = NOT_EVALUATED`
4. 产出 pair-level matching manifest 与 entity-level progression manifest，禁止用 793 个实体行重复计数 189 个独立 matching pair。
5. 审计 anatomy constraint：
   - 若 coarse anatomy mask 不排除任何候选，报告 `inactive_on_cohort=true`；
   - geometry-only、visual-only、visual+geometry 必须分开报告；
   - 不能把 visual+geometry 的结果归因于视觉特征单独。
6. 增加回归测试，保证：
   - persistent-only 完美匹配不会被标为 progression macro F1；
   - 修改 `record["progression"]` 不会改变 matcher 输出；
   - 没有 progression prediction 时，progression 状态只能是 `NOT_EVALUATED`；
   - progression 评估必须真实使用 `record["progression"]` 作为 target。

### 3.2 R25.1 允许的结论

- 固定的 visual-only、geometry-only 或 visual+geometry 匹配器在真实数据上恢复跨时间区域对应的能力；
- assignment correct-vs-deranged 的结构控制是否成立；
- 189 pair / 793 entity 的数据几何、类别覆盖、坐标与复现资格。

### 3.3 R25.1 禁止的结论

- BiomedCLIP 能或不能判断 Stable/Improved/Worse；
- 正确身份绑定提高 Stable/Improved/Worse 分类；
- 当前 matcher 是 learned matcher；
- anatomy constraint 带来增益，除非存在激活且有受控消融；
- `delta_match` 是 `delta_bind`；
- frozen VLM、临床效果或 DIVE Phase II 已解锁。

## 4. R26：真正的 Stable/Improved/Worse 实验

研究问题：

> 在相同实体特征、相同容量、相同训练预算和相同测试样本下，正确的跨时间实体绑定是否比零固定点 derangement 更有利于 Stable/Improved/Worse 分类？

### 4.1 数据单位

- Pair manifest：每个 patient / prior study / current study 只出现一次，用于 matcher 资格和 patient split。
- Entity manifest：每个 pair / anatomy / label_name 对应一条 progression target，用于 classifier。
- 所有划分必须 patient-disjoint；同一 pair 的实体不得跨 fold。
- 正式 test 在协议、代码、超参和种子冻结前保持封存。

### 4.2 容量匹配系统

至少运行：

1. current-only local feature；
2. paired global feature；
3. geometry-only relation；
4. visual-only correct assignment；
5. visual+geometry correct assignment；
6. B4a deranged assignment；
7. B4b oracle correct assignment；
8. learned assignment（仅在 oracle gate 通过后解锁）。

B4a 与 B4b 必须保持完全一致：

- region feature；
- token 数量、类型、顺序和 mask；
- allocator；
- classifier/head；
- 初始化、优化器、训练步数与 seed；
- 唯一变化是 persistent assignment，且 derangement 为零固定点。

### 4.3 主指标与统计

主终点：

`delta_bind = 100 * (progression_macro_f1_B4b - progression_macro_f1_B4a)`

统计单位为 patient，使用 patient-cluster paired bootstrap；报告点估计、95% CI、每类 F1、balanced accuracy、患者数、pair 数和 entity 数。

GO 条件：

- `delta_bind >= 5 pp`；
- patient-bootstrap 95% CI lower `> 0`；
- 三个注册 seed 的方向一致；
- 非 deranged 系统在不同 derangement_id 下预测严格不变。

若 oracle correct 与 deranged 的 CI 不支持正差异，则停止 CAPES identity-binding 主张，不训练 learned matcher，不进入 frozen VLM。

## 5. 分阶段门控

1. **S0 文档与语义门**：本勘误、命名空间、禁止结论和测试契约落盘。
2. **S1 matcher repair 门**：R25.1 代码与测试通过；历史产物只读保留。
3. **S2 manifest 门**：pair/entity 两类 manifest 的计数、哈希、patient split 和 lineage 通过。
4. **C1 oracle binding 门**：真正的 progression B4b-B4a 达到注册 GO 条件。
5. **C2 learned recovery 门**：仅 C1 通过后训练，Recovery 至少 60%。
6. **VLM transfer 门**：仅 structured classifier 已证明信号后，测试固定 64-token frozen-VLM 接口。
7. **DIVE Phase II**：仅 C1、C2 和 VLM transfer 全部通过后解锁。

第一处 survival gate 失败后，后续阶段保持锁定；下一步只能诊断或缩窄修复该 gate。

## 6. 明确禁止的当前动作

- 不启动 RAD-DINO rescue；
- 不下载新 encoder；
- 不训练 learned matcher；
- 不启动 frozen VLM；
- 不使用保留的 Slurm allocation 做扩大实验；
- 不将 R25 Session 5 的 `0.333` 或 `+97.9 pp` 写成 progression 结果。

## 7. 交付物

R25.1：

- `docs/R25_1_ERRATUM.md`
- `reports/R25_SESSION5_DRYRUN_SUMMARY.md`
- `reports/R25_SESSION5_AGGREGATE.json`
- `reports/R25_SESSION5_Q6_CERTIFICATE.json`
- `reports/R25_SESSION5_VARIANT_TABLE.md`
- 修复后的 matcher 指标命名空间与回归测试

R26（C1 解锁后）：

- 冻结协议与配置
- pair/entity manifests 及哈希
- patient-disjoint fold audit
- progression predictions
- B4 isomorphism audit
- patient-bootstrap 统计
- gate certificate

## 8. 当前执行决定

立即执行 S0 和 S1：

1. 冻结 `dd9c242` 为历史 dry-run；
2. 在 `r25.1-semantic-repair` 分支修复指标命名和 Q4 语义；
3. 增加防止 matching/progression 混淆的测试；
4. 运行 focused tests 与全量回归；
5. 只有 S1 通过后，才构建 R26 manifest 和最小 structured-classifier pipeline。
