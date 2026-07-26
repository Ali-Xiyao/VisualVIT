# R26 C1 Oracle-Binding Progression Result

Date: 2026-07-26

Terminal status: `STOP_C1`

Evidence class: `NON_CONFIRMATORY_R26_C1_MECHANISM_GATE`

## 结论

在完全相同的实体特征、分类器容量、患者折、训练种子、训练预算和标签下，
oracle-correct identity binding 相对 zero-fixed-point derangement 只提高了
`+1.1724 pp` 的 patient-balanced progression macro F1。注册的 95% bootstrap
区间为 `[-2.7765, +5.1436] pp`，跨越 0，且点估计低于预注册的 `5 pp`
最低效应门槛。

因此 C1 主门失败。该结果不支持继续训练 learned matcher，也不解锁
RAD-DINO、frozen VLM、DIVE 或 Slurm 扩展实验。

## 冻结输入

- Git commit: `8c2ea0b`
- R26 protocol SHA-256:
  `42cc4a37ba909ab88d15da865f76c8bd8c9f42f81002237ff905c39c95a75838`
- R25.1 Q6 certificate SHA-256:
  `29625d1e50797df91d34c39cbedd45f0bd1e0751c4bfc6d74de975e12d6b0530`
- R25.1 feature cache SHA-256:
  `2a1df98fb3a3d0ef430698da7846b314a7cbcbe73c9e50f6241bfa57dc623326`
- Cohort: 170 patients / 170 pairs / 774 entities
- Labels: Improved 159 / Stable 355 / Worse 260
- Training seeds: 17, 29, 43
- Derangement ids: 81001, 81002, 81003
- Patient-disjoint folds: 5
- Bootstrap replicates: 10,000

## 注册主结果

| 对比 | 点估计 | 95% bootstrap CI |
|---|---:|---:|
| B4b oracle − B4a deranged | +1.1724 pp | [-2.7765, +5.1436] pp |
| B4b oracle − current-only | +2.3250 pp | [-2.6865, +7.4973] pp |
| oracle visual − oracle geometry | +4.1463 pp | [-1.3172, +9.5958] pp |

JSON 中的 `interval.lower` / `interval.upper` 使用 F1 原始比例单位；本报告
乘以 100 后以百分点呈现。

注册 bootstrap 点指标：

| 系统 | Patient-balanced macro F1 |
|---|---:|
| B4a deranged | 0.4035 |
| B4b oracle | 0.4152 |
| Current-only | 0.3920 |
| Oracle visual-only | 0.4087 |
| Oracle geometry-only | 0.3673 |

逐种子 B4b − B4a：

| Seed | 差值 |
|---:|---:|
| 17 | +1.6368 pp |
| 29 | +1.1382 pp |
| 43 | +0.7395 pp |

三个方向均为正，但不足以满足预注册的效应量和不确定性门槛。

## Gate 结果

| Gate | Result |
|---|---|
| R25.1 Q6 green | PASS |
| Cohort and folds qualified | PASS |
| B4 isomorphism | PASS |
| Bootstrap valid | PASS |
| All seed directions positive | PASS |
| Fit finite | PASS |
| Delta bind at least 5 pp | **FAIL** |
| Delta bind CI lower positive | **FAIL** |

## 解释边界

结果说明 correct identity binding 的方向在三个种子上具有一致性，但在当前
合格真实数据、冻结特征和容量匹配分类头下，效应很小且统计区间跨零。它不能
被表述为 CAPES identity binding 已产生可辩护的 progression 机制收益。

R25.1 中强匹配信号主要由稳定空间几何主导；C1 进一步表明这种匹配资格并未
转化为足够大的 Stable/Improved/Worse 预测收益。正式和临床主张继续为 false。

## 审计产物

Runtime root:
`F:\VisualVIT_runtime\050_routeC\r26_c1_oracle_binding\run_v1`

- Summary SHA-256:
  `2fbb63a5fb97d4be30a6c13daa8c91015cfa2450bd8026c4546540ee1df8e5c0`
- Predictions SHA-256:
  `160f9c66e6009d3e2d45cb4a7b28e06d1e94b037c2112925a9d8af156be40613`
- Bootstrap SHA-256:
  `2d8bf9a2bec80fcfba5cdd9cc02222772b9390d0b6836712cec882d8ae17202a`
- B4 isomorphism SHA-256:
  `b3390da9779d580f6605469b803863ae31b44f80885941afde3312c45020a139`
- Fold audit SHA-256:
  `472ecbdaded2e2e980459c42a9cf6e8e7f854595d5e6f017d1d2b9be31b7ef2b`
- Fit audit SHA-256:
  `785d8a6ca71bb34d581d5b21d17e6a7e972a686a4827d35ca08f6834666c9cc2`

All six summary-declared artifact hashes were independently rechecked and
matched their current bytes.
