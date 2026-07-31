# PRTA-Gen R51 TILA/B2 exact-64 Frozen-Qwen Matched Interface 终态报告

> 终态：`COMPLETE_PRTA_GEN_R51_MATCHED_INTERFACE_BENCHMARK`

## 直接结论

**跑通了。** 在相同 2,500 名训练患者、500 名新鲜评估患者、相同 64-token
物理预算、相同 9,873,920 参数 projector、相同初始化/训练顺序/79 updates、
相同 prompt/JSON parser/greedy decoding 和完全冻结 Qwen3-VL-4B 下，PRTA
同时显著优于 TILA-exact64 与 B2-exact64。

| 系统 | Seed 17 | Seed 29 | Seed 43 | Mean Macro-F1 | Mean accuracy |
|---|---:|---:|---:|---:|---:|
| **PRTA exact-64 + frozen Qwen** | 0.382583 | 0.369964 | 0.401842 | **0.384796** | **0.393333** |
| TILA exact-64 + frozen Qwen | 0.308364 | 0.327341 | 0.314151 | 0.316618 | 0.322667 |
| B2 exact-64 + frozen Qwen | 0.275904 | 0.213986 | 0.275378 | 0.255090 | 0.287333 |

聚合器原生保存 `control−PRTA` 方向。换算成读者更直观的 PRTA 增益为：

| 患者配对对比 | 三 Seed mean effect | 95% CI | 判定 |
|---|---:|---:|---|
| **PRTA − TILA** | **+6.818 pp** | **[+3.512,+10.080] pp** | 下界 > 0 |
| **PRTA − B2** | **+12.971 pp** | **[+9.729,+16.286] pp** | 下界 > 0 |
| TILA − B2 | +6.153 pp | [+3.466,+8.739] pp | TILA 也显著优于 B2 |

因此 R51 正式回答了先前未回答的问题：

> 在当前严格配平的 exact-64 + frozen-Qwen 系统接口下，PRTA 比
> TILA-exact64 和 B2-exact64 更准确；增益不是来自更多 token、更多
> trainable parameters、不同 prompt、不同患者或解冻 Qwen。

## 统一系统合同

- 训练：冻结的 R45 train 2,500 patients，每类 500；
- 评估：R51 新选 500 patients，每类 100，排除全部 R45、R44A 与 gold
  patients；与训练患者零重叠；
- 输入：三臂均为 `[64,768]`，60 个有效位置、4 个精确零保留位；
- 共同归一化：active token 逐 token RMS；
- 共同可训练模块：`TierTokenProjector(768→2560)`，9,873,920 参数；
- Qwen3-VL-4B 全冻结，0 trainable parameters，no pixel bypass；
- 训练：Seeds 17/29/43，每臂 1 epoch、gradient accumulation 32、79
  updates；同 seed 的 projector 初始化哈希完全相同；
- 推理：相同 finding-conditioned prompt、两字段 JSON、greedy decoding；
- 九臂 schema validity 与 finding echo accuracy 全为 1.0。

三种表示到 exact-64 的翻译均无可训练参数：

- PRTA：已有 finding-guided cross-time alignment 的 60 个 active tokens；
- TILA：官方 `projected_patch_embeddings` 中固定均匀选择 60/196 patch，
  128 维逐元素重复 6 次到 768；
- B2：冻结 BiomedCLIP 的 15 个非 CLS patch，按 prior/current/signed
  difference/absolute difference 四组拼成 60 token。

## 方法来源边界

TILA 的 image encoder、temporal interval module 和 checkpoint 是官方现成
方法；但本实验的 60-patch exact-64 翻译、共同 projector 与五类 JSON 任务是
本项目适配。B2 是本项目基于冻结 BiomedCLIP 实现的 classic Siamese control，
不是一个可下载的论文完整系统。PRTA 是本项目提出的方法。

所以 R51 可以比较当前三种**matched system adaptations**，不能表述为
“PRTA 全面击败官方 TILA 原生系统”。R50 中官方 TILA global embedding + CE
仍有 0.4577 mean F1，说明 TILA 在其自然接口上很强；R51 说明当前 TILA
patch-to-exact64 翻译在冻结 Qwen 接口下没有保留同等优势。

## 逐类 Case Study

| 系统 | Stable | Improved | Worse | New | Resolved |
|---|---:|---:|---:|---:|---:|
| **PRTA exact-64** | 0.277 | **0.503** | **0.347** | **0.280** | **0.560** |
| TILA exact-64 | 0.303 | 0.263 | 0.327 | 0.213 | 0.507 |
| B2 exact-64 | **0.347** | 0.240 | 0.110 | 0.217 | 0.523 |

PRTA 的优势主要来自 `Improved`、`New`、`Resolved` 和较稳定的 `Worse`。
B2 Seed29 出现明显类别塌缩：Improved/Worse/New recall 仅 0.03/0.04/0.08，
虽然 Stable/Resolved 为 0.64/0.63；这解释了其 accuracy 仍有 0.284、但
Macro-F1 只有 0.214。TILA 的类别覆盖比 B2 均衡，因此显著优于 B2，但其
Improved/New recall 仍低于 PRTA。

PRTA 并非每个类别都逐项最高：Stable 低于 B2/TILA。它的系统级优势来自
更均衡的五类时间变化读出，并在三 seed 与患者 bootstrap 中保持。

## 与 R49、R50、R52 的联合解释

- R49：PRTA 优于 Raw two-image Qwen 和同预算 Naive concat，支持 alignment
  本身的增益；
- R50：官方 TILA global embedding 是强直接分类 baseline，但接口不同；
- R51：在完全相同 frozen-Qwen system contract 下，PRTA 显著优于当前
  TILA/B2 exact-64 适配；
- R52：在完全相同直接分类头下，PRTA 也显著优于同两种 exact-64 表征。

R51 和 R52 的一致方向减少了“优势只来自特定 Qwen readout”或“只来自特定
direct head”的解释空间。但两者使用同一 500 人评估 cohort，而且 R52 的
假设在部分 R51 结果可见后确定，因此它们不是两次独立 confirmation。

## 工程与复现收据

- 九个结果、每臂 500 evaluation rows，三 seed；
- 每臂 79 updates；Qwen trainable parameters = 0；
- 每臂 projector trainable parameters = 9,873,920；
- schema/finding validity 全为 1.0；
- 每臂 elapsed 1,069.8–1,364.0 秒；
- aggregate：9,298 bytes；SHA-256
  `7D4467CA0CED7B8F60F1597917EC8709D31B6204F47968F7E8BFA0DFE6516545`；
- 预结果 authority commits：`5a7b3a4`、`c0082b4`、`3a24486`；
- runtime aggregate：
  `H:\VisualVIT_runtime\050_routeD\r37_prta_cxr\prta_gen_r51_matched_interface_v1\aggregate.json`。

复现入口：

```powershell
python scripts\run_prta_gen_r51_matched_interface.py --preflight-only
powershell -ExecutionPolicy Bypass -File scripts\launch_prta_gen_r51_lane.ps1 -Lane lane0
powershell -ExecutionPolicy Bypass -File scripts\launch_prta_gen_r51_lane.ps1 -Lane lane1
python scripts\aggregate_prta_gen_r51_matched_interface.py
```

## 结论边界

R51 是 fresh internal matched-interface benchmark，不是 gold/external、跨机构
独立确认或临床验证。它没有解锁开放式报告生成、laterality/anatomy/degree、
R42/R43 或任何临床主张。当前 500 人结果不得用于继续调 TILA/B2 translation、
prompt、projector、学习率或 seed 后重包装成 confirmatory evidence。
