# R37.1 Proposal 与 Case Study 收敛总结

> 日期：2026-07-29
> 分支：`codex/r37-prior-responsive-temporal-adapter`
> 当前机器状态：GPU 空闲，无 R37/R38/R39 实验进程
> 当前结论：`PASS_R37_1_TWO_SEED_INTERNAL_SCREEN`

## 1. 一句话结论

R37.1 已经把 R37 的“正确 prior 有收益但时间反转不严格一致”修复为：

- 两个冻结 Seed 的 inversion consistency 均为 1.0000；
- state retention 均高于 0.99；
- A6 相比 current-only、CMCP 和 capacity-matched A0 均有大幅正收益；
- 三组两 Seed patient-cluster bootstrap 的 95% CI lower 均显著大于零。

这证明当前 PRTA-CXR 表示在两个 Seed 和独立 fresh holdout 上具有强、
方向一致的内部证据。它仍是两 Seed描述性内部 PASS，不是原三 Seed
confirmatory scientific GO。

## 2. 为什么 300-dev、483-test、gold、R38/R39 现在不运行

这些阶段分别承担单次内部确认、最终 sealed test、独立专家/外部确认、
固定 64-token survival 和 frozen-VLM transfer。它们一旦被用于选择模型、
阈值、叙事或 checkpoint，就不再是独立确认。

当前主动保持：

```text
protected_outcomes_read = false
sealed_test_read = false
gold_outcomes_read = false
source_hashes_recomputed = false
scientific_claim_allowed = false
```

所以“暂不解锁”是防止 outcome leakage 的科学设计，不是工程未完成。

## 3. 失败方式与为什么失败

### 3.1 R33：固定 Token 路由没有 survival

R33 的 TIER hard gate 相比 robust fixed-64 为 -0.669 pp，95% CI
[-1.443, +0.109] pp，仅 1/3 Seed 正向；prior shuffle 和 query-only
语义审计也未通过。

结论：

```text
STOP_R33_TOKEN_SURVIVAL
```

说明 prediction-level 的条件可靠性不能直接等价为 token-level 收益。

### 3.2 R33A：冻结 cache 上的轻量 rescue 不能恢复核心命题

连续的 routing、projection、anatomy/context 和 benefit-bridge 尝试没有
形成满足预注册门的稳定收益。继续在同一 observed cohort 上搜索会把失败
结果变成调参信号，因此 R33A 被冻结，不再通过新阈值或新路由规则救援。

### 3.3 R37 早期 tiny case：表示对 prior 不响应

早期小样本/低训练量 case 中，true/current 和 true/CMCP prediction
完全一致。这个结果只能说明机制尚未被激活，不能当作科学阴性。

在预先存在的工程上限 1,000 train / 500 evaluation / 3 epochs 下，不改变
Seed、rank、LR、batch 或 loss，三个工程 Seed 的 true-current 和 true-CMCP
点估计全部转为正向，证明 prior responsiveness 可以被训练出来。

### 3.4 R37 正式结果：响应正确，但 inversion gate 失败

| Metric | Seed 17 | Seed 29 |
|---|---:|---:|
| True − current-only | +11.87 pp | +14.15 pp |
| True − CMCP | +7.58 pp | +7.91 pp |
| State retention | 0.9938 | 0.9936 |
| Inversion consistency | 0.8438 | 0.8735 |
| Inconsistent rows | 819 | 663 |

两个 Seed 的失败样本重叠有限，说明不是少量固定坏样本。旧 detached
soft-target inversion KL 只能鼓励近似一致，不能保证时间反转群作用严格成立。

结论：

```text
STOP_R37_INVERSION_CONSISTENCY
```

旧 5,242-row calibration 随即冻结为描述性 failure analysis，禁止用于
R37.1 模型、loss、阈值或 checkpoint 选择。

## 4. R37.1 的最小协议一致修复

R37.1 保留 R37 的：

- BiomedCLIP Block-8 cache；
- encoder 与 adapter 主体；
- rank 32、3 epochs、batch 2、LR 1e-4；
- transition alignment、CMCP 和 state-preservation；
- Seeds 17/29；
- outcome 和 hash firewalls。

唯一科学修复是把 soft inversion regularizer 替换为无参数的
Z2-equivariant projection：

```text
L_f = 0.5 * (z_f + P(z_r))
L_r = P(L_f)
```

该结构保证 `L_r = P(L_f)`，但不会人为保证分类性能、正确 prior 收益、
CMCP 收益或 state retention。

在任何 R37.1 validation outcome 被读取前，使用固定 RNG seed 37101
一次性冻结新 roster：

- train：10,287 patients / 39,491 rows；
- fresh holdout：1,815 patients / 6,858 rows；
- old R37 calibration patients：全部排除。

## 5. R37.1 正式结果

### 5.1 A6 每 Seed

| Metric | Gate | Seed 17 | Seed 29 |
|---|---:|---:|---:|
| Inversion consistency | ≥ 0.90 | 1.0000 | 1.0000 |
| State retention | ≥ 0.99 | 0.9934 | 0.9929 |
| A6 true-pair F1 | descriptive | 0.4680 | 0.4529 |
| Current-only F1 | descriptive | 0.1638 | 0.2007 |
| A6 − current-only | ≥ +2 pp | +30.42 pp | +25.22 pp |
| A6 CMCP true F1 | descriptive | 0.3534 | 0.3443 |
| CMCP control F1 | descriptive | 0.2258 | 0.2304 |
| A6 − CMCP | ≥ +2 pp | +12.76 pp | +11.39 pp |

### 5.2 Capacity-matched A0

| Seed | A0 true-pair F1 | A6 − A0 |
|---:|---:|---:|
| 17 | 0.3419 | +12.62 pp |
| 29 | 0.3404 | +11.25 pp |

A0 与 A6 使用同一 1,815-patient / 6,858-row fresh holdout。

### 5.3 两 Seed patient-cluster bootstrap

| Comparison | Mean Δ | 95% CI | Gate |
|---|---:|---|---|
| A6 vs current-only | +27.82 pp | [+25.96, +29.50] pp | PASS |
| A6 vs CMCP | +12.08 pp | [+10.61, +13.63] pp | PASS |
| A6 vs A0 | +11.93 pp | [+10.24, +13.66] pp | PASS |

三项均使用 2,000 replicates、bootstrap seed 37001。每个观察 Seed 均
至少 +2 pp，且 CI lower > 0。

## 6. 当前可以写进 Proposal 的主张

可以写：

1. R37 的 temporal inversion failure 被一个预先冻结、无参数、群等变
   projection 在独立 fresh holdout 上修复。
2. R37.1 A6 在 Seeds 17/29 上对正确 prior 有强响应，并显著优于
   current-only、CMCP 和 capacity-matched A0。
3. 结果来自 patient-disjoint roster、patient-cluster bootstrap 和明确的
   protected-outcome firewall。

不可以写：

1. 已完成原三 Seed confirmatory GO；
2. 已在 300-dev、483-test 或 gold 上确认；
3. 已证明固定 64-token survival 或 frozen-VLM transfer；
4. 已证明临床可部署或外部泛化；
5. 已证明 universal lesion/entity binding。

## 7. 当前推荐停止点

用户已经选择本阶段只保留两个 Seed。因此推荐：

```text
R37.1 = two-seed descriptive internal PASS
Seed 43 = deferred
300-dev / 483-test / gold = unread
R38 / R39 = locked
GPU work = stop
```

接下来只做文档、表格、图表和论文叙事整理，不再运行新模型。

如果未来必须获得原协议意义上的 scientific GO，则不能改阈值、换 Seed
或复用受保护 outcome；唯一合规路径是补齐 Seed 43 的 A6/A0，运行原三
Seed patient bootstrap，再决定是否冻结唯一候选并单次揭示 300-dev。

## 8. 权威证据

- `reports/R37_INVERSION_FAILURE_CASE_STUDY.md`
- `reports/R37_A6_ENGINEERING_MULTISEED_CASE_STUDY.md`
- `reports/R37_1_TWO_SEED_FRESH_HOLDOUT_RESULT.md`
- `TIER_CXR_VLM_Next_Stage_Proposal_CN.md`
- `TIER_CXR_VLM_Empty_Result_Tables_CN.md`
- Runtime screen:
  `H:\VisualVIT_runtime\050_routeD\r37_prta_cxr\r37_1_formal\two_seed_screen_v1\result.json`
