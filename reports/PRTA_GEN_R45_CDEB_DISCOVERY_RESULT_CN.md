# PRTA-Gen R45 CDEB Discovery 终局报告

> 日期：2026-07-31
> 终态：`STOP_PRTA_GEN_R45_CDEB_DISCOVERY`
> 性质：冻结 discovery 的终局负结果；qualification / confirmation 未解锁

## 1. 研究问题

R44A 表明扩大跨来源 silver 数据可以解决 schema、finding echo 和
query-only separation，却仍不能稳定迫使 Qwen 使用正确 prior。R45 因而
在读取任何 R45 outcome 前冻结 **Causal Delta Evidence Bottleneck
(CDEB)**：用 exact-64 表示中的 `true_pair - current_only` delta 训练五类
auxiliary evidence head，再把 soft class evidence 写入固定 token bridge，
条件化完全冻结的 Qwen 生成原两字段 JSON。

该设计没有引入 shuffled/invalid 第六类，也没有读取 gold、external、
qualification 或 confirmation outcome。

## 2. 冻结设计与执行

- roster：2,500 train / 500 development / 500 sealed qualification /
  250 sealed confirmation，五类均衡且 patient-disjoint；
- discovery：Seed 17，1 epoch，79 optimizer updates；
- 四个 frozen arms：
  `baseline_projector`、`no_delta_evidence`、`delta_no_bridge`、
  `full_cdeb`；
- 主要判据：development true-pair macro-F1、相对 prior-shuffle 和
  inherited baseline 的增益、auxiliary true-pair macro-F1，以及冻结的
  per-class / bootstrap / schema gates；
- discovery token cache：3,000 patients、6,000 images、24 shards，
  qualification / confirmation token 与 outcome 均未物化。

所有四个 arm 均完成 79 次更新，schema validity 与 finding echo 均为
1.0，缓存等价性检查通过，进程干净退出。

## 3. 结果

| Arm | True macro-F1 | Prior-shuffle macro-F1 | True/shuffle 同预测率 |
|---|---:|---:|---:|
| inherited baseline projector | 0.380648 | 0.344407 | 0.638 |
| no-delta evidence | 0.313978 | 0.278729 | 0.546 |
| delta no bridge | 0.264528 | 0.277933 | 0.822 |
| full CDEB | 0.342023 | 0.354609 | 0.628 |

Full CDEB auxiliary true-pair macro-F1 为 0.312258。三个预注册核心门失败：

1. auxiliary true-pair macro-F1 `0.312258 < 0.35`；
2. full CDEB 相对 prior-shuffle 为 `-1.258606 pp < +1 pp`，
   patient-bootstrap 95% CI 为 `[-5.7205, +3.0018] pp`；
3. full CDEB 相对 inherited baseline 为 `-3.862499 pp < +1 pp`，
   patient-bootstrap 95% CI 为 `[-7.8426, +0.2681] pp`。

Full CDEB 相对 no-delta 为 `+2.80455 pp`，但 95% CI
`[-1.8095, +7.7492] pp` 跨零，不能构成稳定机制证据。

## 4. 失败方式总结

R45 否定的是当前 bridge 设计，不是否定所有结构化 temporal evidence：

- delta auxiliary head 自身未达到可用的五类分离度；
- evidence bridge 没有把正确 prior 的因果差异稳定传递给 frozen Qwen；
- full CDEB 甚至未优于 inherited projector baseline；
- `delta_no_bridge` 的 0.822 同预测率说明仅训练 delta head、却不建立
  有效 readout 通道时，生成器仍高度忽略 prior 条件。

这与 R41A/R44A 的 “correct-prior under-use + readout instability” 一致，
但 R45 提供了更窄的反证：**把低质量 soft evidence 直接注入 frozen
generator，不会自动得到 prior-responsive generation。**

## 5. 相关工作与 ICLR 边界

Generic image-swap / temporal inversion、专家引导解码、结构约束解码和
product-of-experts 都已有直接先例。因此 R45 不能把这些通用组件本身作为
新颖性主张。ICLR 方向上可保留的贡献是：明确、可证伪的 longitudinal
causal-use 问题，严格 patient-disjoint controls、预注册 fail-closed gates，
以及对失败机制的新知识；当前结果不支持 SOTA 或临床主张。

## 6. 终局与下一步

R45 冻结为 `STOP_PRTA_GEN_R45_CDEB_DISCOVERY`：

- qualification 500 与 confirmation 250 均未读取、未生成 token；
- 不得根据本次 500-development outcome 调整 R45 的 bridge、loss、
  checkpoint、Seed、阈值或 gate 后重跑；
- R42/R43、gold/external、开放式报告生成与临床主张继续锁定。

下一方向只能另立 R46 authority。候选问题是
**Causal Evidence Arbitration (CEA)**：不再无条件把 soft evidence 注入
generator，而是在全新、排除整个 R45 roster 的 development patients 上，
预注册一个 true-pair 相对 current-only 的因果证据分数；只有证据充分时，
结构化 progression expert 才可覆盖 frozen generator，否则保留 baseline。
这是一条“选择性、安全回退的 progression-only structured generation”
路径，不是 R45 调参续跑，也不是自由文本生成。

## 7. 权威产物

- roster：
  `H:\VisualVIT_runtime\050_routeD\r37_prta_cxr\prta_gen_r45_cdeb_v1\roster.json`
  - SHA-256:
    `0387FCF0B3DA09BE4CC99727EE1278C676BD2D946A87D4377E7F0088F1F7F4D8`
- discovery cache index：
  `H:\VisualVIT_runtime\050_routeD\r37_prta_cxr\prta_gen_r45_cdeb_v1\tokens\discovery\index.json`
  - SHA-256:
    `2ECC1350A71C885CCF10BE4665CD1BDC1F532E1B309586FF5879294890A955B6`
- aggregate：
  `H:\VisualVIT_runtime\050_routeD\r37_prta_cxr\prta_gen_r45_cdeb_v1\discovery\aggregate.json`
  - SHA-256:
    `9FC9DCEC7471DD169B63555B4BA395817ACB5187B3EA1B351F8D12C742BEE75E`

Runtime 产物不进入 Git；本报告只记录冻结的标量结果、边界与 hashes。
