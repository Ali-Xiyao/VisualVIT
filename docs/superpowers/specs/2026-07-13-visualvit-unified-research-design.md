# VisualVIT 路线 C：CAPES-first + DIVE-soft 统一研究设计

**状态**：架构已获用户确认；允许启动 `NON_CONFIRMATORY_PROXY` 预实验  
**日期**：2026-07-13  
**原始提案**：
`history/2026-07-30-legacy-proposals/CAPES_Final_Complete_Proposal_CN.md`、
`history/2026-07-30-legacy-proposals/DIVE_Proposal.md`

## 1. 目标与边界

本项目不把两份 proposal 简单并列，而是把它们收敛到一个唯一的关系建模组件：`Null-Aware Relational Tokenizer / Partial Soft MatchGraph`。第一阶段用纵向胸片验证严格受控的跨时相实体绑定；第二阶段只有在第一阶段机制、学习恢复和 frozen-VLM transfer 三个门槛全部通过后，才扩展到通用 N-image DIVE。

当前用户授权仅覆盖资格预检与预实验。所有代理数据结果必须标注 `NON_CONFIRMATORY_PROXY`，不得用于论文正式主张；正式 test、受限数据父图像和正式 B4 因果实验继续封存。

2026-07-13 终审边界：当前只证明若干组件分别可运行，尚未跑通 `soft MatchGraph -> global allocator -> 64 tokens -> projector/position/attention adapter -> frozen Qwen2-VL` 的端到端链路。因此当前状态为 `GO_NONCONFIRMATORY_COMPONENT_SMOKE_ONLY`，并同时保持 `NO_GO_FORMAL_DATA/LICENSE/ETHICS/ORACLE`、`NO_GO_END_TO_END_TRANSFER` 与 `NO_GO_PHASE_II`。

## 2. 两条核心主张

### C1：跨时相实体绑定的可识别因果效应

在相同视觉特征、token 类型/数量/顺序、projector、head、参数量、训练步数、随机种子和监督下，正确的 prior-current 实体 assignment 相对 anatomy-compatible deranged assignment 提升 patient-balanced macro Change F1。

唯一主效应：

`Delta_bind = 100 * (F_B4b - F_B4a)`，单位为绝对百分点。

### C2：可学习的 null-aware binder 恢复 oracle 收益并迁移

学习式 partial matcher 必须处理 persistent、birth/new、death/resolved 三种关系，并相对 B4a 恢复至少 60% 的 oracle gap；随后在同一 frozen Qwen2-VL constrained-QA 接口中验证迁移。

`Recovery = (F_learned - F_B4a) / (F_B4b - F_B4a)`。

若 oracle gap 不为正，Recovery 无定义，C2 自动失败。attention collapse、probe 与 scaling 仅为诊断或附录，不构成第三条 headline claim。

## 3. 统一架构

### 3.1 输入与编码

- 输入为同一患者的 prior/current 胸片、study 时间、视角和数据来源标识。
- 正式主编码器优先使用 frozen RAD-DINO；资格预实验可用本地 BiomedCLIP 作为明确标注的 proxy。
- DIVE-lite Stage 1/2 仅负责单图 query compression 与跨图 contextualization，不拥有最终 matching 决策。

### 3.2 唯一 matching owner

`Partial Soft MatchGraph` 是全系统唯一 assignment owner：

- real prior -> real current：persistent entity；
- real prior -> dustbin：death/resolved；
- dustbin -> real current：birth/new；
- dustbin -> dustbin：禁止并 mask；
- oracle、deranged 和 learned 三种模式必须走同一组张量契约与 token assembler。

核心数据契约：

- `LongitudinalPair`：patient/study/image/time/source lineage；
- `RegionBatch`：prior/current region features、boxes、anatomy ids、valid masks；
- `MatchPlan`：形状 `[B, R_prior + 1, R_current + 1]` 的 partial transport；
- `TokenBundle`：形状 `[B, 64, D]`，附 token type、valid mask、assignment audit。

### 3.3 固定全局 token 预算

每个病例严格 64 个视觉关系 token：

- 4 个 global/context；
- 28 个 persistent entity；
- 28 个 relation/change；
- 4 个 neutral/reserved/pad。

预算在全病例范围分配，禁止按 image-pair 各自 top-C 后导致 token 数随图像数二次增长。

正式实现必须包含确定性的全局选择/压缩 allocator。当前 hard qualification assembler 在 entity 输入超过 28 或 relation 输入超过 28 时会显式报错；它不会静默截断。Chest ImaGenome 可有 29 个 anatomy regions/图，故 allocator、极限形状测试和 B4 同构性在完成前是正式硬阻塞。

### 3.4 B4 同构控制

- B4b：oracle-correct assignment；
- B4a：对相同 region feature multiset 进行 anatomy-compatible seeded derangement；
- learned：partial/unbalanced Sinkhorn 或等价 soft OT，包含 dustbin；
- random 与 wrong-anatomy 是独立负对照，不替代 B4a。

B4a/B4b 必须满足：输入特征 checksum、null 数、token type/count/order、模型图、参数、优化器、训练步数、seed 完全相同，唯一变化是 assignment。任何不满足项使 C1 结果无效。

当前 token path 仅支持显式 one-hot hard assignment；fractional transport 会被 hard tokenizer 拒绝，不能阈值化后冒充 soft MatchGraph。正式 soft allocator 必须定义 fractional persistent/birth/death mass 如何进入固定预算，并通过 soft 极限与质量守恒测试。

### 3.5 两层证据接口

1. 结构化 progression/evidence classifier：验证关系表示本身是否含有效信号；
2. frozen Qwen2-VL constrained QA：相同视觉 token 预算与提示模板，验证表示能否迁移到语言接口。

classifier 成功不能自动推出 VLM 成功；两层分别报告。

## 4. 数据、许可与防污染

### 4.1 资格预实验

- 可用本地 MIMIC-CXR/CheXpert 构造 prior-current pairs 与工程 proxy 标签；
- 可用 synthetic regions 明确验证 persistent/birth/death/null、B4 同构和学习可恢复性；
- proxy 只证明管线、优化和接口可运行，不证明医学机制或论文主张。

### 4.2 正式数据

- CheXTemporal gold progression/bbox metadata；
- Chest ImaGenome anatomy/entity annotations；
- 对应父图像必须来自用户已获授权的数据源。

正式解锁要求：逐源 license/DUA、用户 credential/CITI 状态、IRB/豁免、派生 manifest/embedding 再分发边界、文件 hash、source lineage、patient-level split、跨数据集像素/患者去重与 test seal 全部落盘。CheXTemporal、Chest ImaGenome 与 MIMIC/CheXpert 可能共享图像或患者，必须以 patient id、study/image id 和必要的内容 hash 做交叉污染审计。

CheXTemporal + Chest ImaGenome 不自动构成 persistent entity/null oracle。正式数据资格必须按以下机械门槛验收；任一失败均不得签发 entity-level `GO_FORMAL_E1`：

- 入选父图像 100% 具有有效授权且 patient/study/image ID 可解析；跨源重复与 test 污染为 0；
- ontology 映射覆盖率 `>=95%`、未解析实体 `<=5%`；所选 relation slots 中具有显式 matched 或 null judgment 的比例 `>=90%`，Wilson 95% 下界 `>=85%`；
- 五个主类每类至少满足 `max(100 个 unique patients, blinded power analysis 给出的最小样本量)`，且 sealed test 每类至少 20 个 unique patients；否则必须在 split/test seal 前预注册降级到 anatomy-level 或 3-class，不能揭盲后合并类别；
- 至少 100 个 pair 的独立双人盲标校准集：progression weighted kappa 点估计 `>=0.80` 且 bootstrap 95% 下界 `>=0.70`；bbox median IoU `>=0.70` 且至少 90% bbox 的 IoU `>=0.50`；
- 所有分歧由第三人裁决，裁决后关键字段缺失率为 0；独立 10% 质检样本的关键标签错误率 `<=2%`。

### 4.3 存储

- `H:\Xiyao_Wang` 全面只读，不放 cache、日志、checkpoint 或下载；
- 代码/规格：`E:\Xiyaowang\050_VisualVIT`；
- 运行根：`F:\VisualVIT_runtime\050_routeC`；
- 项目硬上限 180 GiB，运行后 F 盘至少保留 60 GiB；
- 每 GPU 使用独立 run/output/tmp，禁止并发写同一 manifest/checkpoint。

## 5. 实验块

### E0：资格与预实验（当前允许）

- synthetic matcher、dustbin、fixed-budget、B4 isomorphism 单测；
- 32–128 个 synthetic/proxy cases 的小样本过拟合；
- 本地 encoder 单/双图特征 smoke；
- Qwen2-VL 双图离线 constrained-QA smoke；
- patient/source manifest 与 split leakage audit；
- 产物全部标注 `NON_CONFIRMATORY_PROXY`。

### E1：oracle 因果门（正式、当前封存）

比较 matched baseline、B4a、B4b、random、wrong-anatomy。主终点为 patient-balanced macro Change F1 的 `Delta_bind`。B4b 必须通过全部同构审计，且负对照不能获得同量级收益。

### E2：learned repair

比较 simple similarity matcher、DIVE Stage1/2 contextualizer、完整 null-aware soft Stage3。报告 Recovery、birth/death 子类、校准和 token/compute matched 效率。

### E3：frozen-VLM transfer

固定 Qwen2-VL、提示模板、解码、token budget 和测试病例，比较与 E1/E2 相同的 representation variants。classifier 与 VLM 结果分开门控。

### E4：稳健性与第二阶段解锁

一个无污染外部集、encoder sensitivity、效率与失败案例。外部数据集 identity、许可、跨内外部 patient/content 去重、split、类别映射、预处理、checkpoint/adaptation policy、seed、主终点和分析脚本必须在内部统一 test reveal 前冻结；为完成去重，只允许独立 data custodian 读取 external test 的 patient/study/image IDs 与非 outcome content hashes，test 标签、outcomes、预测和指标始终封存。外部评估可以后执行，但不得在内部结果后改协议。

外部复现的 Phase-II PASS 标准与内部主门槛同向且定量固定：`Delta_bind >=5.0 pp` 且 95% CI 下界 `>0`；Recovery 点估计和 95% CI 下界均 `>=0.60`；frozen-VLM learned-vs-B4a `>=2.0 pp` 且 95% CI 下界 `>0`；negative-control ratio 点估计 `<=0.25` 且 95% 上界 `<=0.50`。若外部集不能合法计算任一主终点、与内部数据有污染、或任一主门槛失败，则外部 gate FAIL，不以 domain shift 事后放宽阈值。只有 C1、Recovery、frozen-VLM transfer、该外部复现、许可/去重和独立 clean rerun 全部通过，才解锁通用 N-image DIVE。

## 6. 统计协议

- 独立单位为 patient；通用多图数据用 source-content cluster；
- 主指标为 patient-balanced macro Change F1；普通 task-weighted macro F1 为次指标；
- patient-balanced macro Change F1 的病例内所有有效 query/entity 总权重归一为 1；用该权重累计每类 TP/FP/FN，先算五类 F1 再宏平均。缺失/不确定标签 mask，不得转为阴性；若某类在 test 无有效支持则主终点不可计算，不进行事后改类。
- 预注册 seed bank：`[17, 29, 43, 71, 101, 137, 181, 233]`；blind train/dev pilot 仅用于估方差与 MDE，冻结前 S 个 seed 后一次性跑 test；
- 默认正式关键比较至少 3 seeds；不得因 test 不显著而追加 seed；
- patient × paired-seed hierarchical bootstrap，正式主分析 10,000 次；
- 主张按 fixed-sequence gatekeeping；同一主张内部 Holm，探索结果 BH-FDR；
- scaling null 必须用 TOST/90% CI 完全位于预注册等价界内，不能用 `p > 0.05` 证明；
- prior/current order swap 后标签映射为 `new <-> resolved`、`worse <-> improved`、`stable <-> stable`。
- C1 正式科学门槛冻结为 `Delta_bind` 点估计至少 5.0 pp 且 patient×seed bootstrap 95% CI 下界大于 0；固定 test 在 blinded pilot 估计下必须对 5.0 pp 达到至少 80% power，否则删除 confirmatory C1。
- 负对照比率 `max(|Delta_random|, |Delta_wrong|)/Delta_bind` 的点估计必须不超过 0.25，bootstrap 95% 上界不超过 0.50。
- frozen-VLM 主比较为 learned relation tokens 相对 compute-matched B4a 的 patient-balanced macro F1；点估计至少 +2.0 pp 且 95% CI 下界大于 0。

Recovery 判定：

- oracle denominator 的 bootstrap 95% CI 必须完全大于 0，且至少 95% bootstrap replicates 的 denominator 为正，否则 Recovery 不可判定；
- Recovery 点估计与 95% CI 下界均 `>= 0.70`：强成功；
- Recovery 点估计与 95% CI 下界均 `>= 0.60`：可行成功；
- `0.40–<0.60`：灰区，只允许一次预注册 rescue；
- `< 0.40`：方法主张失败；
- oracle gap `<= 0`：C1/C2 机制线失败。

## 7. 当前预实验运行顺序与停止规则

1. Q0：环境、GPU、磁盘、已有权重与数据路径预检；
2. Q1：核心张量契约与 synthetic fixture；
3. Q2：dustbin/partial transport/fixed-budget 单测；
4. Q3：B4a/B4b 同构审计；
5. Q4：32–128 case synthetic learnability/overfit；
6. Q5：本地 proxy encoder smoke；
7. Q6：Qwen2-VL 双图接口 smoke；
8. Q7：结果 manifest、环境快照和独立复跑。

若 Q1–Q4 任一失败，不得继续扩大到真实图像或更多 GPU；若 encoder/Qwen 环境不完整，先记录 blocker，再决定是否下载最小官方资产。预实验不能读取 sealed test，也不能据其结果修改正式假设。

正式阶段禁止按 E1 -> E2 -> E3 顺序逐次查看 test 后继续开发。所有 E1/E2/E3 variants、checkpoint hashes、seeds、prompt/decoder、分析脚本和外部集协议必须先在 train/dev 上一次性冻结；随后只执行一次统一 test reveal。fixed-sequence 只控制同一 reveal 上的统计推断顺序，不授权 test 后修改后续方法。

## 8. 下载边界

首轮优先复用本地资产，不默认下载。若本地环境通过但正式 encoder 缺失，候选最小下载为 RAD-DINO inference weights（约 346 MiB）；若需要真实 DIVE adapter validation，候选为 BLINK Multi-view validation（约 10 MiB，test 不下载/不读）。CheXTemporal gold metadata 很小，但其父图像和 Chest ImaGenome 都受源数据许可约束，未完成用户凭据/DUA 前不得把它们当正式可运行数据。

任何下载前必须记录官方 URL、license、预计 archive/unpacked 大小、目标 F 路径与 SHA-256；禁止写入 H。

## 9. 负结果与发表边界

- B4a 与 B4b 的窄等价 CI：反证 identity binding 主假设；
- oracle 有效但 learned Recovery 低：报告 oracle-learned gap、null/new/resolved 失败 taxonomy；
- classifier 有效但 frozen VLM 不提升：报告 representation-interface 边界；
- CI 过宽：结论为 inconclusive，不解释为无效或有效。

## 10. 审计产物

每次运行必须保存：run id、命令、代码状态、配置、seed、GPU/依赖快照、输入 manifest/hash、日志、指标 JSON、checkpoint hash、success/failure 判定和错误说明。表格与图必须从结构化结果重建，不手抄。

本规格是路线 C 的权威设计边界。若后续实施计划或脚本与本文件冲突，以本文件的 claim、data seal、gate order 和 stop rule 为准，除非另有用户批准的版本化修订。
