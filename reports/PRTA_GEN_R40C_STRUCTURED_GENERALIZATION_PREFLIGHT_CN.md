# PRTA-Gen R40C 结构化头内部泛化 Preflight 与 Roster Receipt

## 直接结论

R40C 的 pre-outcome package 已准备并通过真实 receipt 的 CPU/no-write
preflight：

```text
PASS_PRTA_GEN_R40C_PREFLIGHT
PASS_PRTA_GEN_R40C_RUNNER_PREFLIGHT
PASS_PRTA_GEN_R40C_ROSTER_SUPPORT
```

真实 R40C roster 已一次性写入并通过标量级 receipt 审计。当前没有 Seed
result、checkpoint、aggregate 或 GPU 进程。这个报告仍是启动前交接，
不是实验结果。

## 研究边界

R40C 检验 R40B.4 的 499,973 参数 structured head 能否从 32-row overfit
扩展到 patient-disjoint held-out development。数据仍来自已经参与方法开发的
R40A.2 fit partition，因此未来 PASS 也只能称 internal development
generalization。

以下内容保持锁定：

- Qwen free generation；
- laterality、anatomy、degree、evidence；
- protected 300-dev 与 revealed 483；
- gold、external、R41–R43；
- 独立科学或临床主张。

## 支持与 roster

只读 inventory：

| 项目 | 数量 |
|---|---:|
| R40A.2 fit patients | 4,287 |
| R40A.2 fit rows | 16,154 |
| 排除的五批 observed patients | 160 |
| 剩余 patients | 4,127 |
| 剩余 rows | 14,687 |

剩余 unique-patient label support：

| Stable | Improved | Worse | New | Resolved |
|---:|---:|---:|---:|---:|
| 2,968 | 1,405 | 1,601 | 990 | 489 |

冻结选择为：

| Partition | 每类 | 总患者 |
|---|---:|---:|
| train | 200 | 1,000 |
| development | 100 | 500 |

选择按 rare-class-first、稳定 SHA-256、每患者一行执行。development 先于
train 分配，五批 observed cohort、两个新 partition 与未选择患者互斥。

真实 receipt：

| 项目 | 审计值 |
|---|---|
| status | `PASS_PRTA_GEN_R40C_ROSTER_SUPPORT` |
| train | 1,000 patients；每类 200 |
| development | 500 patients；每类 100 |
| train/development patient overlap | 0 |
| excluded observed patients | 160；全部未进入 roster |
| one row per patient | true |
| roster bytes | 350,714 |
| roster SHA-256 | `9C076B684BC258EFA60E568004F851CD9EE079EA4DDEA549BD0D2ABCFBF9B0CB` |

后续 receipt 审计只输出标量，不登记患者标识。首次构建器 CLI 曾把完整行
载荷打印到本地终端；收口时已把 CLI 改成经过测试的标量摘要，未改变 roster
文件及其 hash。protected 300-dev、revealed 483、gold、external 均保持
未读取，`resplit_allowed=false`、`scientific_claim_allowed=false`。

## 模型与门

- Seeds：17、29、43；
- arms：true-pair、current-only、query-only、prior-shuffle；
- 每 arm：499,973 参数；
- query-only：12 finding one-hot 零填充到 3,840；
- 标准化：只拟合 training arm；
- AdamW 0.001、batch 128、100 epochs、800 updates/arm；
- 无 early stopping、无 checkpoint selection。

每个 Seed 的 GO 条件：

1. true-pair development macro-F1 >= 0.30；
2. 每类 recall >= 0.15；
3. true-pair 相对 query-only/prior-shuffle 均 >= +2 pp；
4. 两项 2,000-replicate patient-bootstrap 95% CI 下界 > 0；
5. schema 与 finding echo 均为 100%。

## 已完成验证

- roster preflight 在内存中选择 train 1,000 / development 500；
- runner preflight 验证四臂、三 Seed、12x3,840 query control；
- head 参数数为 499,973；
- 每臂 update 数为 800；
- `real_roster_written=true`，且 roster 是运行目录中的唯一文件；
- `gpu_training_started=false`；
- 300-dev、483、gold、external 均未读取；
- 本轮 26 项 R40C/R40B.4 closure focused tests、Ruff、compileall、JSON
  与链接检查通过；
- full pytest 为 787 passed、1 expected xfailed、1 个既有 R6 failure；
- preflight 前后两张 RTX 3090 均为 0 MiB / 0%。

## 下一次明确确认后的命令

roster 已完成，不得重写或重分。只有新的明确授权才允许从 Seed 17 开始：

```powershell
python scripts/run_prta_gen_r40c_structured_generalization.py `
  --config configs/prta_gen/prta_gen_r40c_structured_generalization_v1.json `
  --roster H:\VisualVIT_runtime\050_routeD\r37_prta_cxr\prta_gen_r40c_structured_generalization_v1\roster.json `
  --seed 17 `
  --device cuda:0
```

每个 Seed 必须 fresh 输出并完成审计，最终才运行：

```powershell
python scripts/aggregate_prta_gen_r40c_generalization.py `
  --config configs/prta_gen/prta_gen_r40c_structured_generalization_v1.json `
  --roster H:\VisualVIT_runtime\050_routeD\r37_prta_cxr\prta_gen_r40c_structured_generalization_v1\roster.json
```

本轮没有执行任何 Seed、aggregate 或 GPU 命令。
