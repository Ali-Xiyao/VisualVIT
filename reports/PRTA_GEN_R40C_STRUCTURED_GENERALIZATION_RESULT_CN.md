# PRTA-Gen R40C 结构化头内部泛化终态报告

## 直接结论

R40C 已按冻结的 1,000-train / 500-development、四臂、三 Seed 和
patient-cluster bootstrap 协议完整运行，终态为：

```text
GO_PRTA_GEN_R40C_INTERNAL_GENERALIZATION
```

三 Seed 的 true-pair development macro-F1、每类 recall、相对 query-only
与 prior-shuffle 的点效应和 2,000 次 patient-bootstrap CI 下界全部通过。
gate failure 数为 0，schema validity 与 finding echo 均为 100%。

这是 **internal development generalization** GO，不是独立科学确认、Qwen
自由生成、gold/external 泛化或临床部署结论。

## 冻结设计

- 来源：已经参与方法开发的 R40A.2 fit partition；
- 排除：R40B–R40B.4 五批共 160 名已观察患者；
- train：1,000 名患者，每类 200；
- development：500 名患者，每类 100；
- train/development patient overlap：0；
- Seeds：17、29、43；
- arms：true-pair、current-only、query-only、prior-shuffle；
- 每 arm：499,973 参数、800 updates；
- bootstrap：patient cluster、2,000 replicates、seed 40001；
- 不早停、不挑 checkpoint、不重分 roster。

冻结 roster SHA-256：
`9C076B684BC258EFA60E568004F851CD9EE079EA4DDEA549BD0D2ABCFBF9B0CB`。

## 三 Seed 结果

| Seed | true-pair macro-F1 | 最低类别 recall | vs query-only，pp（95% CI） | vs prior-shuffle，pp（95% CI） | vs current-only，pp（95% CI） |
|---:|---:|---:|---:|---:|---:|
| 17 | 0.5058 | 0.38 | +19.72 [+14.97, +24.25] | +10.50 [+5.75, +15.12] | +11.71 [+7.15, +16.40] |
| 29 | 0.4941 | 0.38 | +20.10 [+15.68, +24.52] | +10.91 [+6.52, +15.26] | +7.38 [+2.84, +11.98] |
| 43 | 0.4827 | 0.36 | +17.42 [+12.64, +22.00] | +9.64 [+5.27, +14.19] | +8.75 [+3.89, +13.63] |

true-pair 的逐类 recall：

| Seed | Stable | Improved | Worse | New | Resolved |
|---:|---:|---:|---:|---:|---:|
| 17 | 0.57 | 0.38 | 0.44 | 0.49 | 0.65 |
| 29 | 0.57 | 0.38 | 0.40 | 0.47 | 0.65 |
| 43 | 0.56 | 0.36 | 0.40 | 0.47 | 0.62 |

所有 Seed 均满足：

1. true-pair macro-F1 >= 0.30；
2. 五类 recall 均 >= 0.15；
3. 相对 query-only 和 prior-shuffle 的效应均 >= +2 pp；
4. 两项 primary comparison 的 bootstrap 95% CI 下界均 > 0；
5. schema validity = 1.0，finding echo accuracy = 1.0。

current-only 是注册的描述性 control，其三 Seed CI 下界也均大于 0，但不替代
冻结的 query-only/prior-shuffle 主门。

## Case study 结论

此前四批 Qwen causal-LM readout 的最好成绩仍未达到 32/32；R40B.4 证明
受限 structured head 能在第五批 32-row cohort 上过拟合。R40C 进一步证明：
在排除全部五批观察患者、固定 patient-disjoint development 后，同一类
semantic-layout structured head 的收益可以跨患者保留，并且不是 finding
query 或随机 prior shortcut 单独造成。

因此新的、可支持的有限主张是：

> 在已经参与方法开发的 R40A.2 fit 域内，exact-64 semantic-layout
> true-pair 表示可支持 progression-only structured head 的
> patient-disjoint internal development generalization。

这不会把历史 Qwen readout STOP 改写为 PASS，也不意味着 Qwen 不是 LLM。
R40C 跑通的是“语义决策与语言实现分离”的结构化路线。

## Firewalls 与停止边界

终态仍为：

- `qwen_free_generation_unlocked=false`；
- `r41_qwen_sft_unlocked=false`；
- `scientific_claim_allowed=false`；
- `protected_300_dev_read=false`；
- `revealed_483_test_read=false`；
- `gold_outcomes_read=false`；
- `external_outcomes_read=false`。

`independent_confirmation_planning_unlocked=true` 只表示可以另行设计新的
独立确认协议，不授权自动启动 gold/external、R41–R43 或其他生成字段。
本轮结果之后不得依据 development outcome 调 learning rate、阈值、Seed、
checkpoint 或 roster。

## 终态产物

运行根：
`H:\VisualVIT_runtime\050_routeD\r37_prta_cxr\
prta_gen_r40c_structured_generalization_v1`

| Artifact | SHA-256 |
|---|---|
| `aggregate.json` | `34E2D09C7E2734B34AD028D6E3CDDFE6F08BD84F50D38541B8BD643F14EC0027` |
| `sequence_status.json` | `989DA284BB430160C999912C3268C156DE417E49C8D4DA14D86339F56738CD40` |
| `seed_17/result.json` | `45D6AB3A4F491699D4FC9713A5CF37C2A2E3121B0E43C443F8E040B8317FE4E4` |
| `seed_29/result.json` | `8B286DE24549DC3353DDE88E5E2C5F82ECC42E2AF4B6508D9A9C52391CCBE142` |
| `seed_43/result.json` | `50AB4AD39D46CFE2891861C9D95579898E1FC5443DEAD44FDFEA4C42D0A351D6` |

三个 checkpoint 均为 2,034,204 bytes。Seed 17/29/43 与 aggregate 的
stderr 日志均为 0 bytes。自动 launcher 和 Seed 进程均已退出，两张 GPU
终态均为 0 MiB/0%。

终态收口验证为 31 项 R40C/R40B.4 focused tests、repository-wide Ruff、
compileall、配置 JSON、修改文档本地链接、跨文档终态 marker 和
`git diff --check` 全部通过。
