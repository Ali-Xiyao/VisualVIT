# PRTA-Gen R52 统一 exact-64 直接分类头 Case Study 与终态结果

> 终态：`COMPLETE_PRTA_GEN_R52_MATCHED_DIRECT_HEAD_BENCHMARK`
> 严格判据：`prta_strict_superiority_supported=true`

## 直接结论

**跑通了。** 在相同 2,500 名训练患者、500 名新鲜评估患者、相同 exact-64
输入、相同 5,991,173 参数分类头、相同初始化/训练顺序/优化器/2,000 updates
和三粒 seed 下，PRTA 同时显著优于 TILA-exact64 与 B2-exact64：

| 方法 | Seed 17 | Seed 29 | Seed 43 | Mean Macro-F1 | Mean accuracy |
|---|---:|---:|---:|---:|---:|
| **PRTA exact-64** | 0.354955 | 0.370107 | 0.356495 | **0.360519** | **0.362000** |
| TILA exact-64 | 0.268596 | 0.271473 | 0.279085 | 0.273051 | 0.274000 |
| B2 exact-64 | 0.297222 | 0.241118 | 0.265473 | 0.267938 | 0.270000 |

| 患者配对对比 | 三 Seed mean effect | 95% CI | 判定 |
|---|---:|---:|---|
| **PRTA − TILA** | **+8.747 pp** | **[+4.481,+12.861] pp** | 下界 > 0 |
| **PRTA − B2** | **+9.258 pp** | **[+4.768,+13.199] pp** | 下界 > 0 |
| TILA − B2 | +0.511 pp | [−3.100,+4.069] pp | 无可靠差异 |

预注册判据要求前两项 CI 下界同时严格大于 0；实际两项都通过。因此可以在
本实验边界内正式写：

> PRTA 在统一 exact-64 直接分类接口下显著优于 TILA-exact64 和
> B2-exact64。

## 为什么需要 R52

历史 R40C 的 PRTA structured head mean Macro-F1 约 0.4942，R50 的
TILA-CE/B2 分别约 0.4577/0.4174，看起来 PRTA 有潜力超过它们，但两个实验
使用不同患者、训练规模、token 结构和分类器，不能直接比较。

R52 消除了这些主要混杂：

- 三种方法使用完全相同的 R51 2,500-train / 500-evaluation 患者；
- 每位患者一行，评估集五类各 100 人；
- 三种输入均为冻结、无标签的 `[64,768]` cache，60 个有效位置加 4 个
  精确零保留位；
- 三者都把有效位置展平为 46,080 维，再进入同一
  `LayerNorm → Linear(128) → GELU → Linear(5)` 分类头；
- 相同 seed 的初始化 SHA-256、minibatch 顺序、训练预算和优化器完全一致；
- 无 arm-specific trainable adapter、early stopping、checkpoint/seed 选择
  或 outcome 后调参。

没有使用 PRTA 专属的 4/12/16/16/12 语义池化。原因是 TILA token 是空间
patch 顺序，B2 token 是 prior/current/signed/absolute 分组；将 PRTA 的语义
边界强加给它们会引入结构性偏置。统一展平保留了三种表示的全部 60 个有效
位置，同时让读出实现逐字节一致。

## 方法来源边界

- **TILA**：图像编码器、temporal interval 表征和 checkpoint 来自官方
  TILA；但把 196 个 projected patches 固定翻译为 60 个 exact-64 token，
  再接本项目五类统一头，是本项目适配，不是原论文原样系统。
- **B2**：冻结 BiomedCLIP 上的 prior/current/signed difference/absolute
  difference 是本项目实现的经典 Siamese 控制；它不是可下载的完整命名方法。
- **PRTA**：本项目提出的 finding-guided cross-time alignment exact-64 表征。

因此 R52 比较的是三种**冻结表征在共同 exact-64 直接头下的可读性**，不是
“官方 TILA 原论文系统 vs PRTA”的端到端原生复现。

## 逐类 Case Study

| 方法 | Stable | Improved | Worse | New | Resolved |
|---|---:|---:|---:|---:|---:|
| **PRTA exact-64** | **0.320** | **0.343** | 0.330 | 0.270 | **0.547** |
| TILA exact-64 | 0.227 | 0.333 | 0.283 | **0.280** | 0.247 |
| B2 exact-64 | 0.163 | 0.303 | **0.350** | 0.233 | 0.300 |

PRTA 的最大优势来自 `Resolved`，三 Seed recall 为 0.52/0.53/0.59；同时
Stable 也明显高于两个控制。TILA 在 `New` 上略高于 PRTA，B2 在 `Worse`
上略高，因此结果不是 PRTA 对每个类别逐项支配。总体显著增益来自更均衡的
类别覆盖，尤其是跨时间消失/恢复状态，而不是单一 seed 或单一类别偶然性。

## 与 R40C、R50 的关系

R52 不复现 R40C 的 0.4942 绝对值；本次 PRTA mean 为 0.3605。原因是 R52
换成新的 500 人评估 cohort、2,500 人训练集和 representation-neutral flatten
head。R52 的价值不是抬高绝对分数，而是让三种方法在同一接口下可归因比较。

R50 的官方 TILA global embedding + CE 得到 0.4577，显著高于本次
TILA-exact64 的 0.2731。这说明官方 TILA 全局表示在其自然分类接口上很强，
但当前 parameter-free patch-to-exact64 翻译没有保留同等可读性。该下降不能
归咎于 TILA 官方方法本身，也不能用 R52 声称 PRTA 普遍优于所有 TILA 用法。

同理，R52 B2 是 patchwise exact-64 适配，不等于 R50 的 global
signed/absolute B2。R52 真正坐实的是：**在当前统一 64-token 表征合同中，
PRTA 的 finding-guided alignment 比这两种已冻结适配更适合直接五类读出。**

## 工程与复现收据

- 每臂训练 2,000 optimizer updates；九臂全部通过注册状态；
- 每臂约 14.8–21.2 秒；peak CUDA allocated 均约 0.967 GiB；
- 分类头参数均为 5,991,173；arm-specific trainable parameters 均为 0；
- 聚合使用 500 名相同患者、三 seed、2,000 次 patient-paired bootstrap；
- aggregate：8,719 bytes；SHA-256
  `DDA3235C5517E8557A44E843B14B5D36916CF73C95FC89BB476990EF225F8ABB`；
- 预结果 authority commit：`a3f00a9`；
- runtime aggregate：
  `H:\VisualVIT_runtime\050_routeD\r37_prta_cxr\prta_gen_r52_matched_direct_head_v1\aggregate.json`。

复现入口：

```powershell
python scripts\run_prta_gen_r52_matched_direct_head.py --preflight-only
powershell -ExecutionPolicy Bypass -File scripts\launch_prta_gen_r52_lane.ps1 -Lane lane0
powershell -ExecutionPolicy Bypass -File scripts\launch_prta_gen_r52_lane.ps1 -Lane lane1
python scripts\aggregate_prta_gen_r52_matched_direct_head.py
```

## 不能外推的结论

R52 是由已观察 R40C/R50 结果推动的 internal case study；冻结前还已看见
R51 PRTA-Qwen Seeds 17/29。因此它不是全局 outcome-blind 独立确认。它没有
读取 protected 483、gold 或 external outcomes，不支持临床主张，也不回答
frozen-Qwen 生成接口。后一个问题由仍在执行的 R51 单独回答。

本结果不得用于在同一 500 人上继续调 token translation、头结构、学习率、
epoch 或 seed 后再把新结果包装成 confirmatory evidence。
