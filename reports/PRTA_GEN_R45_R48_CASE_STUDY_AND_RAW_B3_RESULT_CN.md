# PRTA-Gen R45–R50 Case Study、统一三系统与强方法结果

## 最终总体结论

最终项目判定为：

`POSITIVE_PRTA_GEN_R48_FPRR_POOLED_INTERNAL`

Qualification 500 与 confirmation 250 合并后的 750 人 pooled held-out
true F1 为 0.373614；true−shuffle +5.702 pp、CI `[+2.529,+9.101]`；
true−current +7.860 pp、CI `[+4.629,+11.045]`。分拆结果作为 cohort
heterogeneity 审计保留，不覆盖最终 pooled overall 判定。

这条实验链已经把“为什么前面的修复失败”与“什么最小命题可以复现”分开：

- R45–R47 的 learned bridge/router 没有带来可靠的 baseline 增益；
- R48 不再训练或选择，复现了 frozen generator 对正确 prior 的响应；
- 用户优先要求的 Raw two-image Qwen3-VL 已在同一 500 人 qualification
  cohort 跑完，但显著弱于 R48 frozen-token baseline。

R49 随后补上此前缺失的同预算 Naive exact-64 归因。它不复用旧 Raw 500 人
比较，而在同一 750 人 evaluation union、相同语义任务与 frozen Qwen 下
重新运行 Raw、Naive exact-64 和 PRTA exact-64。Naive 与 PRTA 的 64-token
预算、projector 容量和初始化、训练顺序、Seed、优化器和 updates 完全匹配。

| R49 系统 | macro-F1 |
|---|---:|
| Raw two-image Qwen | 0.192915 |
| Naive exact-64 | 0.295921 |
| PRTA exact-64 | **0.354372** |

PRTA−Raw 为 +16.146 pp，CI `[+12.090,+20.198]`；PRTA−Naive 为
+5.845 pp，CI `[+2.610,+9.081]`。因此 case study 现在不仅能说 PRTA
系统优于直接看双图，也能说在相同 64-token/projector/训练预算下，
finding-guided 跨时间对齐优于简单 prior/current token 拼接。详细公平性审计
与哈希见 `PRTA_GEN_R49_UNIFIED_THREE_WAY_RESULT_CN.md`。

R50 随后补齐强 temporal representation baselines。相同 2,500/750 roster
与三 Seed 下，TILA-CE、B2 signed/absolute、TILA-BiCE/TCL 与 TAC-adapted
mean F1 为 0.457693/0.417409/0.395122/0.265752。BiCE/TCL 相对 CE
−6.257 pp、CI `[−9.579,−2.786]`，但 mapped reversal consistency 从约
0.360 提高到 0.866；TAC-adapted 相对 B2 −15.166 pp、CI
`[−18.802,−11.635]`。这些是直接 structured classification 结果，不能
冒充相同 frozen-Qwen 接口。完整文献、复现性质和边界见
`PRTA_GEN_R50_LITERATURE_METHOD_REPRODUCTION_RESULT_CN.md`。

Raw B3 的完整结果为：

| 指标 | Raw two-image Qwen3-VL | R48 FPRR true-pair |
|---|---:|---:|
| macro-F1 | 0.141724 | 0.400584 |
| accuracy | 0.216 | 0.412 |
| schema validity | 1.000 | 1.000 |
| finding echo | 1.000 | 1.000 |
| invalid | 0/500 | 0/500 |

paired patient-bootstrap 的 Raw−FPRR 差值为 **−25.886 pp**，
95% CI **[−30.773, −20.934] pp**。这是明确的负结果，不是波动或统计不确定。

## Raw B3 做了什么

- 同一个本地 frozen `Qwen3-VL-4B-Instruct`；
- 每例按 `[prior 完整胸片, current 完整胸片]` 顺序输入两张未裁剪 JPEG；
- processor 只做模型所需的内部 resize，固定
  `min_pixels=200704`、`max_pixels=802816`；
- 没有 BiomedCLIP、projector、64-token 压缩、router、LoRA 或训练；
- 同一个 finding-conditioned 两字段 JSON prompt；
- greedy generation，最多 64 个新 token；
- GPU0/GPU1 按 roster row 奇偶分成两个互斥 250 人 shard。

两张卡均完成并原子写出结果。每卡峰值约 8.55 GiB；两卡并行 generation
wall-time 上界约 312.3 秒，累计 621.6 GPU 秒。总 input token 为 264,395，
vision-grid token 为 831,888，因此它与 exact-64 FPRR **不等计算量**。

## 失败模式

Raw Qwen 的格式能力没有问题：500/500 schema 合法、500/500 finding
复制正确。问题是 progression 判别塌缩：

| 类别 | recall | 预测次数 |
|---|---:|---:|
| Stable | 0.03 | 4 |
| Improved | 0.12 | 52 |
| Worse | 0.82 | 370 |
| New | 0.09 | 71 |
| Resolved | 0.02 | 3 |

它把 74% 的病例预测成 `Worse`。所以失败不是 parser、JSON 或 finding
conditioning，而是 raw full-field pixels 没有自动形成可靠的五类纵向状态
比较。

## R45–R48 case-study 轨迹

### R45 CDEB

把 `true_pair-current_only` delta soft evidence 桥接进 frozen Qwen。
Full CDEB F1 0.3420，低于 baseline 0.3806；true−shuffle −1.26 pp。结论：
低质量 delta evidence 进入生成器并不会自动建立正确-prior grounding。

### R46 CEA

在排除 R45 roster 的新 250 人 cohort 上做 selective arbitration。点估计
比 baseline 高约 +1.06 pp，但 bootstrap CI `[−0.914,+3.273]` 跨零，
structured heads 也没有稳定达到绝对门槛。结论：router 的选择性不足以
形成可靠增益。

### R47 UCC

在另一个新 500 人 cohort 上使用无阈值的 3/3 true-consensus +
3/3 current-disagreement。UCC−baseline 只有 +0.440 pp，
CI `[−1.984,+2.921]`。但 true−shuffle 为 +5.921 pp，
CI `[+1.423,+10.786]`。结论：存在 prior signal，但 router 没有把它转化为
可重复的额外预测价值。

### R48 FPRR

由此删除所有 training、selection、threshold 和 router，只测试 immutable
R45 Seed-17 frozen generator。500 人 qualification：

- true-pair F1 0.400584；
- current-only 0.303250；
- query-only 0.113459；
- prior-shuffle 0.320763；
- true−shuffle +7.982 pp，CI `[+3.873,+11.991]`；
- true−current +9.733 pp，CI `[+5.818,+13.706]`。

资格门全部通过，状态为 `GO_PRTA_GEN_R48_FPRR_QUALIFICATION`。它证明的不是
router 成功，而是冻结 token interface 下存在可重复的 correct-prior
responsiveness。

## ICLR 标准下的解释

Raw B3 是必要的强基线，而且结果必须保留：直接把两张完整胸片交给通用
Qwen3-VL 并不等于模型会做细粒度 longitudinal progression reasoning。
R48 的优势更可能来自医学视觉 encoder 与固定 temporal token interface
提供的归纳偏置，而不是仅仅“看到了两张图”。

但当前边界仍然很窄：

- Raw B3 与 R48 qualification 都是同一内部 development 数据源；
- Raw B3 是 qualification 上的 development case study，不是独立确认；
- R48 confirmation 随后按原冻结设置完成，但四个 gate 失败，终态为
  `STOP_PRTA_GEN_R48_FPRR_CONFIRMATION`；
- gold、external、开放式报告、临床效用和 ICLR 接收主张都未解锁。

## R48 Confirmation 最终结果

Raw B3 交付后，未改任何 R48 设置即运行 250 人 confirmation：

- true/current/query/shuffle F1 =
  0.318626/0.278350/0.114373/0.305379；
- true−shuffle +1.325 pp，CI `[−3.709,+6.008]`；
- true−current +4.028 pp，CI `[−1.213,+9.151]`；
- true F1、true−shuffle 点效应及两个 CI 下界共四门失败。

因此 qualification GO 不能升级为 split-specific independent replication；
但 750 人 pooled internal 的总体结果为 positive。它仍不是 external/gold
或临床 confirmation。

## 可复核证据

- Raw aggregate：
  `H:\VisualVIT_runtime\050_routeD\r37_prta_cxr\prta_gen_r48_b3_raw_two_image_v1\formal\aggregate.json`
- aggregate：1,904 bytes，SHA-256
  `4D57F6AF0AD2B5D84A35566B643A512A51C3D8A31FD4631C73460ED2EC231BDF`
- shard 0 SHA-256：
  `089D266E88ECFE09CD4BF583CDE23F6F1AEAD61A49242B843F8145531C2DC8EC`
- shard 1 SHA-256：
  `582EAE01BC3FBD5617ECA9E607732A460B6EFF7BC17975E4B34B72FA98ED14AD`
- 冻结代码提交：`ad745ee`
- smoke 修复与正式执行代码提交：`d4c9472`
- R48 confirmation aggregate SHA-256：
  `46EC22D90E0B662284116CE5DD24ED464857F60407D73B7596A5319BBFB3B6BB`
