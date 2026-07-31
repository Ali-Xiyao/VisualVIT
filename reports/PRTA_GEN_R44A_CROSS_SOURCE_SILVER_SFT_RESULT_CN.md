# PRTA-Gen R44A 跨来源 Silver SFT 终态报告

状态：`STOP_PRTA_GEN_R44A_CROSS_SOURCE_SILVER_SFT_SURVIVAL`

日期：2026-07-31

## 直接结论

R44A 已按冻结协议完成 G0/G1 × Seeds 17/29/43 共六个训练臂及三 Seed
聚合。工程链完整，JSON schema 与 finding echo 均为 100%，而且 G1 相对
query-only 的效果很大；但是正确 prior 相对 prior-shuffle 的效果没有稳定
达到冻结门，Seed 43 还出现 G1 true-pair macro-F1、`Worse` recall 和
G1−G0 同时失败。因此：

- `gate_passed = false`；
- gate failures = 9；
- `cross_source_silver_survival_supported = false`；
- `qwen_free_generation_survival_unlocked = false`；
- `r42_unlocked = false`；
- `r43_unlocked = false`；
- `scientific_claim_allowed = false`。

这说明把训练/开发数据换成更大的跨来源 CheXpert silver cohort，能够解决
格式、finding echo 和 query-only 分离问题，但**仅靠扩充 silver 数据没有
建立稳定的正确 prior grounding**。该结果是本冻结 case study 的科学 STOP，
不是按开发结果继续调参的依据。

## 冻结设计与完成性

R44A 在读取任何 R44A development outcome 前冻结，完整继承 R41A 的
progression-only 目标和训练设置：

| 项目 | 冻结值 | 实际完成 |
|---|---:|---:|
| Train patients | 1,000 | 1,000 |
| Development patients | 250 | 250 |
| 每类 train/development | 200 / 50 | 200 / 50 |
| Seeds | 17, 29, 43 | 17, 29, 43 |
| 模型臂 | G0 projector-only；G1 attention-LoRA | 六臂全部完成 |
| Epochs | 3 | 3 |
| Optimizer updates/arm | 94 | 六臂均为 94 |
| 评估臂 | true/current/query/shuffle | 六臂全部完成 |
| Bootstrap | patient-cluster，2,000 次 | 完成 |

roster 为 patient-disjoint、一名患者一行、gold 患者排除、五类均衡。exact64
cache 共 1,250 行、2,500 张图像、10 个 shard；缓存不含 progression label、
句子或报告文本。六臂均生成非空 checkpoint 和
`PASS_PRTA_GEN_R44A_ARM_EVALUATION` receipt。

## True-pair 结果

| Seed | G0 macro-F1 | G1 macro-F1 | G1−G0 (pp) | G1 recalls：Stable / Improved / Worse / New / Resolved |
|---:|---:|---:|---:|---|
| 17 | 0.3099 | 0.3503 | +4.0414 | 0.18 / 0.54 / 0.32 / 0.22 / 0.52 |
| 29 | 0.3329 | 0.3512 | +1.8306 | 0.18 / 0.44 / 0.30 / 0.28 / 0.62 |
| 43 | 0.3588 | 0.2863 | -7.2465 | 0.56 / 0.38 / 0.02 / 0.14 / 0.46 |

所有 true-pair 输出的 schema validity 与 finding echo accuracy 均为 1.0。
这证明生成格式与 finding 复制不是本轮 STOP 的原因。

## 对照效应

以下为 G1 true-pair macro-F1 相对注册对照的 patient-cluster bootstrap
结果：

| Seed | vs query-only effect (pp) | 95% CI | vs prior-shuffle effect (pp) | 95% CI |
|---:|---:|---|---:|---|
| 17 | +24.4157 | [+17.3889, +31.2186] | -0.1474 | [-4.3047, +4.3959] |
| 29 | +21.1441 | [+13.9661, +27.7779] | +1.5886 | [-3.9349, +6.7221] |
| 43 | +18.0435 | [+11.9185, +24.0488] | -0.2486 | [-3.0713, +2.5368] |

G1 在每个 Seed 都显著优于 query-only，说明模型不是只靠 finding query
完成任务。然而正确 prior 并未稳定优于跨患者 shuffled prior：三个 Seed
的点效应都低于冻结的 +2 pp 门，bootstrap CI 下界也都不大于零。

## 九个冻结门失败

| Seed | Gate | 观察值 | 要求 |
|---:|---|---:|---:|
| 17 | G1 vs prior-shuffle effect | -0.1474 pp | ≥ +2 pp |
| 17 | G1 vs prior-shuffle CI lower | -4.3047 pp | > 0 |
| 29 | G1 vs prior-shuffle effect | +1.5886 pp | ≥ +2 pp |
| 29 | G1 vs prior-shuffle CI lower | -3.9349 pp | > 0 |
| 43 | G1 true macro-F1 | 0.2863 | ≥ 0.30 |
| 43 | G1 `Worse` recall | 0.02 | ≥ 0.12 |
| 43 | G1 vs prior-shuffle effect | -0.2486 pp | ≥ +2 pp |
| 43 | G1 vs prior-shuffle CI lower | -3.0713 pp | > 0 |
| 43 | G1−G0 true macro-F1 | -7.2465 pp | ≥ +1 pp |

失败具有两个层次：

1. 三个 Seed 共同失败于 correct-prior 对 shuffled-prior 的冻结门，说明
   prior 身份绑定没有建立；
2. Seed 43 进一步出现类别支持与 G1 对照退化，说明 attention-LoRA 的
   readout 仍存在跨 Seed 不稳定。

## 与 R41A 的 case-study 对照

R41A 在较小的原 MIMIC fit 域中以 `Worse` 类崩塌、G1−G0 全负和八个门
失败终止。R44A 在新的跨来源 silver cohort 上扩大到 1,000/250 患者，并
保持相同模型、Seed 和门：

- Seeds 17/29 的 G1 macro-F1 与类别发射有所改善；
- 六臂全部实现 100% schema validity/finding echo；
- 三个 Seed 对 query-only 均产生大幅正效应；
- 但三个 Seed 对 prior-shuffle 均未通过；
- Seed 43 仍出现 `Worse` recall 0.02 与 G1−G0 -7.2465 pp。

因此新尝试排除了“只要换成更大 silver cohort 就能让 Qwen readout
稳定使用正确 prior”这一假设。它没有撤销 R40C structured-head 的有限
internal-development GO，也没有改变 R41A 的原终态。

## 防火墙与执行完整性

- protected 300-development outcome：未读；
- revealed 483-test outcome：未读；
- gold progression outcome：未读；
- external outcome：未读；
- R42/R43：未启动；
- retry：不允许；
- 自动 sequence：在 R44A aggregate 后正常终止；
- 训练/聚合 worker：终局审计为 0；
- 两张 GPU：终局审计为 0 MiB、0%；
- launcher stderr：0 bytes；
- arm stderr 仅含模型权重加载进度与 greedy decoding 下被忽略的 sampling
  参数提示，无 traceback 或 error marker。

## 权威运行时产物

运行时根目录：

`H:\VisualVIT_runtime\050_routeD\r37_prta_cxr\prta_gen_r44a_cross_source_silver_sft_v1`

| 产物 | SHA-256 |
|---|---|
| `aggregate.json` | `8860C6A7AF52665148713271B98B89592411FE57BEA70644E1B6E65E9F5DF335` |
| `sequence_status.json` | `9C075CD28192509C0F19C2F748059301E3459F2E38278FCA31F30D0675960A3B` |
| `roster.json` | `60FE40D3483B85C9B462D69BF631D82DE68620BA722606862D263F095271C292` |
| `tokens/index.json` | `8ADA1A1116375B66BA951F17174B8D391EE906814FCCF23B1F8960C444820546` |

R44 独立支持审计状态为
`PASS_PRTA_GEN_R44_INDEPENDENT_SUPPORT`，审计 SHA-256 为
`8DE158995C983F7295F68545AE7A65007B98DBB819ACBD33327AA70EC78A5777`。

## 最终边界与下一步

本轮已完成用户授权的 R44A 新尝试并得到终态。接下来不应：

- 针对这 250 名 development 患者调学习率、LoRA、类别权重、prompt、
  roster、Seed、checkpoint 或阈值；
- 把 R44A 写成独立科学确认、跨机构泛化、临床有效性或开放式报告生成；
- 绕过 STOP 启动 R42/R43。

可以继续的工作仅限只读复现、论文负结果整理，或另行提出一个真正独立、
outcome-independent 且在新数据 outcome 可见前冻结的科学假设。该新假设
必须另立阶段，不能被表述为 R44A 的调参重跑。
