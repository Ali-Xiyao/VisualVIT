# PRTA-Gen R49 统一三系统归因结果

## 直接结论

R49 已完整跑通，终态为：

`COMPLETE_PRTA_GEN_R49_UNIFIED_THREE_WAY`

在相同 750 名 patient-disjoint evaluation patients、相同 progression 任务和
JSON 输出合同、相同 frozen Qwen3-VL-4B 下，三系统结果为：

| 系统 | macro-F1 | accuracy | schema | finding echo |
|---|---:|---:|---:|---:|
| Raw two-image Qwen | 0.192915 | 0.258667 | 1.000 | 1.000 |
| Naive exact-64 | 0.295921 | 0.321333 | 1.000 | 1.000 |
| PRTA exact-64 | **0.354372** | **0.361333** | 1.000 | 1.000 |

2,000 次 patient-cluster paired bootstrap 给出：

| 对比 | 点差 | 95% CI | 冻结判定 |
|---|---:|---:|---|
| PRTA exact-64 − Raw two-image | **+16.146 pp** | **[+12.090,+20.198]** | 支持 PRTA 更优 |
| PRTA exact-64 − Naive exact-64 | **+5.845 pp** | **[+2.610,+9.081]** | 支持 PRTA 更优 |

因此，这个内部 post-hoc attribution case study 同时支持：

1. 64-token PRTA 方法优于让同一个 frozen Qwen 直接读取两张完整胸片；
2. PRTA 优于相同 64-token 预算的简单 prior/current 拼接；
3. 在本实验合同内，增益不能只解释为“输入了两张图”或“用了更多 token”，
   而有可分辨的一部分来自 finding-guided 跨时间对齐表示。

## 为什么旧比较还不够

R45–R47 的 learned bridge/router 尝试没有形成相对 inherited baseline 的可靠
增益：R45 CDEB 低于 baseline；R46 CEA 与 R47 UCC 的增益 CI 均跨零。R48
随后证明 frozen generator 对 correct prior 有响应，并在 750 人 pooled 分析
中为 positive，但当时仍缺少同患者、同 prompt family、同训练预算的 Naive
exact-64 对照。旧 Raw B3 也只覆盖 qualification 500 人，不能与 pooled 750
直接构成严格三系统归因。

R49 没有围绕这些 outcome 调 router 或阈值，而是重新冻结一个最小对比：
Raw、Naive、PRTA 都在同一 750 人上评估；Naive 与 PRTA 从同一 Seed-17
初始化重新拟合相同 projector。由此补上了 R48 没有回答的 alignment
attribution 缺口。

## 严格公平性审计

### 共同部分

- training：固定 2,500 人；evaluation：qualification 500 + confirmation
  250，共 750 人；train/evaluation patient-disjoint；
- frozen Qwen：两条 exact-64 arm 的 Qwen trainable parameters 均为 0；
- 语义任务与输出：同一 system prompt、同一 finding-conditioned 两字段 JSON、
  同一五类 progression registry、greedy generation、最大 64 个新 token；
- 三系统 example 顺序和 targets 逐行一致，schema/finding 均为 750/750。

Raw 必须序列化两张图，exact-64 必须序列化 64 个 placeholder，因此完整的
multimodal token IDs 不可能逐字节相同。本实验只声称语义任务和输出合同相同，
不虚假声称 modality serialization 相同。

### Naive 与 PRTA 的严格同预算部分

| 项目 | Naive exact-64 | PRTA exact-64 |
|---|---|---|
| physical token budget | 64 | 64 |
| 有效/保留位置 | 60 + 4 zeros | 60 + 4 zeros |
| projector 参数 | 9,873,920 | 9,873,920 |
| projector 初始化 SHA-256 | `C8B61AF7...896BE2` | `C8B61AF7...896BE2` |
| 训练顺序 SHA-256 | `99314669...2FEEC7` | `99314669...2FEEC7` |
| training rows / updates | 2,500 / 79 | 2,500 / 79 |
| epoch / LR / accumulation | 1 / 1e-4 / 32 | 1 / 1e-4 / 32 |
| pixel input to Qwen | false | false |
| cache equivalence | PASS, max diff 0 | PASS, max diff 0 |

Naive 的 60 个有效 token 是 30 个 prior + 30 个 current frozen BiomedCLIP
Block-8 patch token；位置在结果产生前按 14x14 非 CLS 网格等距冻结。PRTA
使用 finding query、state/transition 和 aligned-prior 布局。两者唯一的核心方法
差异是 token 表示的跨时间组织与对齐方式。

## 类别层面

| 类别 recall | Raw | Naive | PRTA |
|---|---:|---:|---:|
| Stable | 0.013 | 0.293 | **0.353** |
| Improved | 0.427 | **0.567** | 0.487 |
| Worse | 0.667 | 0.033 | **0.147** |
| New | 0.153 | 0.153 | **0.240** |
| Resolved | 0.033 | 0.560 | **0.580** |

Raw 仍明显偏向 `Worse`，并几乎不识别 Stable/Resolved。Naive 已从 frozen
medical visual tokens 获得大幅提升，说明医学视觉编码本身很重要；PRTA 又在
同 token/Qwen/projector 预算上进一步改善 Stable、Worse、New 和 Resolved，
形成总体 +5.845 pp 的可靠增益。这比只比较 PRTA 与 Raw 更能定位 alignment
贡献。

## 计算量解释

Raw 两卡累计 generation 965.74 GPU 秒，并产生 1,247,696 个 vision-grid
tokens；两卡并行 generation wall-time 上界约 508.73 秒。Raw 与 exact-64
不等计算量，因此 PRTA−Raw 回答的是系统性能比较，不是等算力效率比较。

Naive 与 PRTA 均为 exact-64、相同 projector 和相同训练预算，端到端耗时分别
1,447.42 与 1,462.11 秒。这一对比才是跨时间对齐归因的主要证据。

## 证据与哈希

- aggregate：3,727 bytes，SHA-256
  `AB1328DF6D90CF65DB0F21CCB2D3631B8DE8ED49159B6FB8A1A2F14D97AECFB4`；
- Naive result：84,900 bytes，SHA-256
  `499116D2C1591679924F60A5DCDA9027E7AC84B23CB5C1938C0B84FA96938EE5`；
- PRTA result：84,884 bytes，SHA-256
  `1EBAB92A417007633B4055513F5E34B2FF0BE2DA7815ACE78E236F2D3CDEEB68`；
- Raw shard 0：125,585 bytes，SHA-256
  `050E785297FD6CB45B8C8ECA0D5CF90BE254F5B01DCF844DFB0B02728816BAF0`；
- Raw shard 1：125,508 bytes，SHA-256
  `CCEDDFD5276A318740143CB94F3A18BFA0ADFA77BE1822A3C5688969374510EC`；
- Naive token index：6,731 bytes，SHA-256
  `0B18B112FE81EDF484DB0E7F77BDDECEC10AA4D09EFFC7766F9A3643FF93264F`。

运行根：
`H:\VisualVIT_runtime\050_routeD\r37_prta_cxr\prta_gen_r49_unified_three_way_v1`。

## 结论边界

R49 是内部 silver、post-hoc mechanism attribution，不是独立 gold/external
confirmation。它不撤销 R48 confirmation 的 split-specific STOP，也不解锁
临床效用、开放式报告、R42/R43 或 ICLR 接收主张。可以安全写的是：

> 在同一 750 人内部 cohort、相同 frozen Qwen 和同 64-token/projector/训练
> 预算下，PRTA 的跨时间对齐表示显著优于简单 prior/current token 拼接；同时
> PRTA 系统也显著优于 frozen Qwen 直接读取两张完整胸片。
