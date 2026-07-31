# PRTA-Gen R50 文献方法复现与强基线结果

> 终态：`COMPLETE_PRTA_GEN_R50_METHOD_BENCHMARK`
> 日期：2026-07-31
> 层级：post-hoc internal method reproduction benchmark

## 直接结论

R50 已经把 R49 之后缺失的纵向胸片方法学对比跑完。四个注册方法在同一批
2,500 名训练患者、750 名评估患者、相同五类标签与 finding 条件下完成
Seeds 17/29/43：

| 方法 | 复现性质 | mean macro-F1 | mean accuracy | mean 反转一致率 |
|---|---|---:|---:|---:|
| TILA frozen embedding + CE | 官方 checkpoint 冻结迁移 | **0.457693** | **0.462222** | 0.360000 |
| Siamese signed/absolute | 强经典表征基线 | 0.417409 | 0.427111 | 0.290222 |
| TILA-style BiCE+TCL | 五类契约适配复现 | 0.395122 | 0.396444 | **0.865778** |
| Libra TAC temporal fusion adapted | 组件级适配复现 | 0.265752 | 0.269778 | 0.252000 |
| R49 PRTA exact-64 | frozen-Qwen 系统参考 | 0.354372 | 0.361333 | N/A |

最重要的结果不是简单排名，而是三个可解释结论：

1. 官方 TILA 时间表征非常强。只训练 700 参数的 finding-conditioned 线性头，
   就在三 Seed 上稳定达到约 0.458 macro-F1。
2. TILA 的 BiCE+TCL 在本地五类扩展下把反转一致率从约 0.360 提高到
   0.866，但标准 macro-F1 显著下降 6.257 pp。这是明确的 accuracy–equivariance
   trade-off，而不是全面增益。
3. 只移植 Libra TAC 的时间融合块、但没有其 12 层 RAD-DINO LFE 与原生报告
   生成训练，显著弱于简单的 signed/absolute 表征。不能把 TAC 组件名本身
   当作性能保证。

R50 没有读取 483-test、gold 或 external outcomes，也没有根据 R50 outcome
调学习率、挑 Seed、换 checkpoint 或重分 roster。由于 R49 outcome 在 R50
冻结前已可见，本结果不是新的独立确认。

## 文献与可复现性审计

| 方法 | 原生任务 | 官方代码/权重 | 本次处理 |
|---|---|---|---|
| [TILA, CVPR 2026](https://openaccess.thecvf.com/content/CVPR2026/html/Ko_Temporal_Inversion_for_Learning_Interval_Change_in_Chest_X-Rays_CVPR_2026_paper.html) | 三类 improved/stable/worsened progression、retrieval、change screening | [MIT 官方 0.2B checkpoint](https://huggingface.co/lukeingawesome/TILA) | 官方 128-d pair embedding 冻结迁移；BiCE/TCL 扩展为 New↔Resolved |
| [Libra, ACL Findings 2025](https://aclanthology.org/2025.findings-acl.888/) | 纵向报告生成/VQA | [Apache-2.0 官方代码](https://github.com/X-iZhang/Libra) 与 3B/7B 权重 | 保留 TAC self/cross-attention 与 MLP；省略本地 cache 不具备的 12-layer RAD-DINO LFE |
| [TempA-VLP, WACV 2025](https://openaccess.thecvf.com/content/WACV2025/html/Yang_TempA-VLP_Temporal-Aware_Vision-Language_Pretraining_for_Longitudinal_Exploration_in_Chest_X-ray_WACV_2025_paper.html) | progression classification、dynamic phrase grounding | 未定位到可审计的官方 checkpoint | 只纳入相关工作，不伪装复现 |
| [MLRG, CVPR 2025](https://openaccess.thecvf.com/content/CVPR2025/html/Liu_Enhanced_Contrastive_Learning_with_Multi-view_Longitudinal_Data_for_Chest_X-ray_CVPR_2025_paper.html) | longitudinal report generation | 任务不等价 | 作为多视角对比学习参考，不进入五类主表 |
| [TIM, CVPR 2026](https://github.com/yihengd/TIM) | temporal decoupling + iterative report refinement | 官方代码可见，原生生成任务 | 作为未来生成式对照，不在本轮直接分类合同内重训 |
| [CheXTemporal](https://arxiv.org/abs/2605.11304) | 五类 temporal annotation/evaluation | 数据集而非方法 | 支持本地五类 taxonomy 的任务意义，不作为 baseline |

### 为什么没有跑“原生 Libra”

Libra 官方配置是 RAD-DINO + TAC + 3B/7B MLLM 的两阶段报告生成。官方仓库
报告单张 A6000 48GB 上 connector pretraining 约 385 小时、LoRA fine-tuning
约 213 小时。它既不属于相同五分类输出合同，也无法在两张 3090 上以合理
成本完成原生复现。因此 R50 只做来源可追溯的 TAC temporal-fusion component
adaptation，并把它明确标成 `not native Libra`。

## 冻结协议

- roster：复用 R49 的 2,500 train + qualification/confirmation union 750；
- 评估患者：750 人，一人一行，五类各 150；
- 全部 3,250 行：五类各 650，共 11 个 findings；
- seeds：17/29/43；
- epochs：50；
- optimizer：AdamW；不使用 class weighting、resampling、early stopping、
  checkpoint selection 或 seed selection；
- TILA-style：Epochs 1–20 使用 BiCE；Epochs 21–50 加入 `lambda=50` TCL；
- statistics：2,000 次 patient-cluster bootstrap；
- 受保护边界：483-test/gold/external outcome flags 全为 false。

官方 TILA revision 固定为
`a9c6da4b07651de5469e54b5903a63d33f4dfc6a`；权重为
642,508,642 bytes，SHA-256
`B16B6BCF47AC6E4E79C4D9DA2DB88055B297ADCA22715935E4522184F87CE101`。

## 三 Seed 结果

| 方法 | Seed 17 | Seed 29 | Seed 43 | Mean |
|---|---:|---:|---:|---:|
| TILA-CE | 0.453228 | 0.458893 | 0.460959 | **0.457693** |
| Siamese signed/absolute | 0.415895 | 0.414092 | 0.422242 | 0.417409 |
| TILA-BiCE/TCL | 0.396846 | 0.390419 | 0.398101 | 0.395122 |
| TAC-adapted | 0.267522 | 0.246597 | 0.283137 | 0.265752 |

### 平均类别 recall

| 方法 | Stable | Improved | Worse | New | Resolved |
|---|---:|---:|---:|---:|---:|
| TILA-CE | 0.344 | 0.484 | 0.451 | 0.347 | **0.684** |
| Siamese signed/absolute | 0.240 | **0.491** | 0.420 | 0.287 | **0.698** |
| TILA-BiCE/TCL | **0.400** | 0.487 | **0.464** | 0.229 | 0.402 |
| TAC-adapted | 0.240 | 0.258 | 0.311 | 0.296 | 0.244 |

BiCE/TCL 的主要代价集中在 New 与 Resolved：方向约束改善 Stable/Worse 和
反转一致性，却压低 birth/death 类别。这与原论文只使用三类连续进展标签的
边界一致；New↔Resolved 并不保证和 Improved↔Worsened 同样可逆。

## 注册 paired bootstrap

### 同一直接分类接口

| 对比 | mean Δ macro-F1 | 95% CI | 判定 |
|---|---:|---:|---|
| TILA-BiCE/TCL − TILA-CE | **−6.257 pp** | **[−9.579,−2.786]** | 一致性上升，但标准 F1 显著下降 |
| TAC-adapted − Siamese signed/absolute | **−15.166 pp** | **[−18.802,−11.635]** | TAC 组件适配显著更差 |

### 相对 R49 PRTA exact-64 的跨接口描述

| 直接分类方法 − PRTA exact-64 | mean Δ macro-F1 | 95% CI |
|---|---:|---:|
| TILA-CE | **+10.332 pp** | **[+6.599,+14.005]** |
| Siamese signed/absolute | **+6.304 pp** | **[+2.695,+9.903]** |
| TILA-BiCE/TCL | +4.075 pp | [−0.234,+8.368] |
| TAC-adapted | **−8.862 pp** | **[−12.764,−5.151]** |

这四项不能解释为“替换 PRTA 后 frozen Qwen 仍然更好”，因为 R50 直接分类器
不经过 Qwen JSON generation。它们回答的是：在相同患者和标签上，其他
temporal representation + structured readout 能达到什么水平。若要做严格
VLM-level 方法替换，下一轮必须把 TILA/B2 表征压成同一 exact-64 budget，
使用相同 projector、冻结 Qwen、prompt 和输出解析后再比较。

## 失败方式与新认识

1. **“加入 inversion 就会同时提升准确率”失败。** 五类 taxonomy 中
   New/Resolved 的临床可逆性弱于 Improved/Worse。TCL 达成了它优化的
   consistency，却过度约束了标准预测。
2. **“复杂 TAC 一定优于简单差分”失败。** TAC-adapted 有 10,645,308 个
   trainable parameters，远多于 B2 的 15,420，却低 15.166 pp。原生 TAC 的
   12 层 RAD-DINO LFE、生成对齐训练与数据规模不可被一个 fusion block 替代。
3. **“R49 已经覆盖强时间表征 baseline”被否定。** Raw 与 Naive 是必要
   attribution controls，但不是最强 temporal encoder。TILA-CE 与 B2 显示，
   论文必须同时报告强 representation baselines。
4. **先前 router/bridge 失败与本结果一致。** R45–R47 的 learned bridge
   没有稳定提高 baseline；R50 再次显示，在小规模五类训练上增加 10M 参数
   的 fusion module 可能过拟合，而冻结医学时间表征 + 小头更稳。

## 对 ICLR 方向的影响

当前最稳妥的主张应收窄为：

> 在相同 750 人内部 case study 中，PRTA exact-64 相对同预算 Naive concat
> 有可靠增益；但直接 structured classification 的最好方法是官方 TILA
> frozen temporal embedding。PRTA 的后续研究问题不应是继续堆叠 router，
> 而应是能否在相同 exact-64 + frozen-Qwen 接口下保留 TILA/B2 的强表征，
> 同时保持 PRTA 的 finding-guided prior responsiveness。

这比“PRTA 全面优于其他纵向方法”更可信，也给出一个新的、可证伪的下一步：
**TILA/B2-to-exact64 matched-interface benchmark**。本轮 outcome 不得用于在
同一 750 人上挑选其 projector 或超参数；需要另立训练/开发 roster，或把
下一轮严格标记为 post-hoc system translation study。

## 复现入口与产物

- authority：`configs/prta_gen/prta_gen_r50_method_benchmark_v1.json`；
- method primitives：`src/visualvit/r50_method_baselines.py`；
- caches：`scripts/cache_prta_gen_r50_features.py`；
- per-seed runner：`scripts/run_prta_gen_r50_method.py`；
- two-GPU lanes：`scripts/launch_prta_gen_r50_method_lane.ps1`；
- aggregate：`scripts/aggregate_prta_gen_r50_methods.py`；
- focused tests：`tests/test_prta_gen_r50_method_benchmark.py`；
- runtime aggregate：
  `H:\VisualVIT_runtime\050_routeD\r37_prta_cxr\prta_gen_r50_method_benchmark_v1\aggregate.json`；
- aggregate bytes/SHA-256：11,101 /
  `A011FBA55BB536CA89FB4F72EEBD86814E8EB0C256FA6C47EC1953AEA1C2E01E`。

## 边界

- TILA-CE 是官方 checkpoint 的 frozen-embedding transfer，不是原论文全量
  fine-tuning；
- TILA-BiCE/TCL 是五类契约适配，不是原论文三类 exact reproduction；
- TAC-adapted 不是 native Libra；
- R50 是 post-hoc internal benchmark，不是独立确认、gold/external 泛化或
  临床证据；
- 不得根据本轮结果在同一 roster 上调参重跑并升级主张。
