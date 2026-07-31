# PRTA-Gen R44A 跨来源 silver progression-only SFT 冻结协议

状态：`FROZEN_PRTA_GEN_R44A_CROSS_SOURCE_SILVER_SFT`

## 问题

R41A 在原 MIMIC fit 域内终止为 STOP。R44A 不重跑、调参或改写该结论，而是检验一个预先声明的新假设：
当训练/开发样本换成 patient-disjoint 的 CheXpert silver cohort，并把规模扩大到 1,000/250
名患者时，同一 progression-only Qwen G0/G1 对比能否通过原 R41A 生存门。

R44A 是跨来源 silver development case study，不是独立专家确认、gold generalization、
临床证据或 R42/R43 解锁路径。

## 冻结数据与 roster

- 支持审计：`PASS_PRTA_GEN_R44_INDEPENDENT_SUPPORT`
- 审计 SHA-256：`8DE158995C983F7295F68545AE7A65007B98DBB819ACBD33327AA70EC78A5777`
- 数据：CheXTemporal revision `81fd9cdd9b1208d8f8bd39d7a914c9b72fed8d79`
- 唯一 silver 输入：`silver_findings.parquet`
- dataset：`chexpert`
- finding：只允许继承自 R41A 的 12 个精确字符串；不做大小写归一化
- 全部 CheXTemporal CheXpert gold 患者按 `dataset/patient_id` 排除，不读取 gold progression
- 一名患者最多一行；按 `Resolved → New → Improved → Worse → Stable`，development
  先于 train，以固定 SHA-256 无放回选择

| Partition | 每类患者 | 总患者 |
|---|---:|---:|
| train | 200 | 1,000 |
| development | 50 | 250 |

roster 写入后不允许重分割、替换患者或根据结果选择样本。

## 图像与 exact64 cache

仅处理 roster 所需的本地 CheXpert prior/current JPEG。使用与 R40/R41 相同的：

1. 冻结 BiomedCLIP ViT-B/16，到 block 8；
2. 冻结 PRTA Seed-17 checkpoint 与 finding query；
3. exact64 compiler；
4. `true_pair`、`current_only`、同 finding 跨患者 `prior_shuffle` 三种缓存；
5. `query_only` 在 runner 内构造全零 64×768 token。

cache 不保存 progression label、句子或报告文本。Qwen 不接收 pixel inputs。

## 模型、训练与评估

完全继承 R41A，避免在失败结果后调参：

- G0：只训练 `TierTokenProjector`；
- G1：训练 projector 加 Qwen attention LoRA；
- Seeds：17、29、43；
- 3 epochs，gradient accumulation 32；
- projector LR `1e-4`，LoRA LR `2e-5`；
- 每臂固定 94 次 optimizer update；
- 无 early stopping、checkpoint selection、class reweighting；
- free-greedy decoding；
- development 上评估 `true_pair/current_only/query_only/prior_shuffle`。

## 冻结生存门

逐 Seed 同时要求：

- G1 true-pair macro-F1 ≥ 0.30；
- G1 五类 recall 均 ≥ 0.12；
- schema validity ≥ 0.99；
- finding echo accuracy ≥ 0.99；
- G1 对 query-only 与 prior-shuffle 的 macro-F1 效应均 ≥ 2 pp；
- 上述两个 paired patient-bootstrap 95% CI 下界均严格大于 0；
- G1 true-pair 相对 G0 true-pair ≥ 1 pp。

任一条件失败即
`STOP_PRTA_GEN_R44A_CROSS_SOURCE_SILVER_SFT_SURVIVAL`。全部通过仅记为本 case
study 的 `GO_PRTA_GEN_R44A_CROSS_SOURCE_SILVER_SFT_SURVIVAL`，也不解锁
R42/R43。

## 执行边界

代码、配置、测试和 preflight 必须在 roster 写入与 GPU 启动前提交。roster、cache、每个
Seed/arm 和 aggregate 输出都必须是 fresh path。首个工程或科学门失败即停止，不允许根据
development 结果重选 cohort、改训练设置或追加 Seed。

## 终态附记（2026-07-31）

冻结 sequence 已完成六个 arm 与三 Seed aggregate，终态为
`STOP_PRTA_GEN_R44A_CROSS_SOURCE_SILVER_SFT_SURVIVAL`。九个门失败；
R42/R43 未启动，protected 300-development、revealed 483-test、gold 与
external outcome 均未读取。完整结果和边界见
`../reports/PRTA_GEN_R44A_CROSS_SOURCE_SILVER_SFT_RESULT_CN.md`。

该附记只记录冻结协议的执行结果，不修改本页任何数据、模型、训练或 gate
定义，也不授权 outcome-dependent retry。
