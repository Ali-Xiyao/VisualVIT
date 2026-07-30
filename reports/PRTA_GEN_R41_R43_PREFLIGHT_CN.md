# PRTA-Gen R41A–R43 自动链 Preflight

日期：2026-07-30

状态：`PASS_PRTA_GEN_R41_R43_CHAIN_PREFLIGHT`

## 已完成

- R41A no-write roster preflight：
  `PASS_PRTA_GEN_R41A_PREFLIGHT`；
- R41A real tokenizer/runner preflight：
  `PASS_PRTA_GEN_R41A_RUNNER_PREFLIGHT`；
- R42A static runner preflight：
  `PASS_PRTA_GEN_R42A_RUNNER_PREFLIGHT`；
- R43 fresh outcome-free readiness audit：
  `STOP_PRTA_GEN_R43_CONFIRMATORY_READINESS`；
- focused tests：14 passed；
- full pytest：805 passed、1 expected xfailed、1 个既有 R6 frozen-manifest
  failure；
- 新增 Python：Ruff、compileall PASS；
- JSON configs：解析 PASS；
- `git diff --check`：PASS。

## R41A 真实 receipt

| 项 | 值 |
|---|---:|
| eligible patients after all exclusions | 2,627 |
| eligible rows | 5,919 |
| train/development patients | 375 / 125 |
| train/development per class | 75 / 25 |
| Resolved reserve | 6 |
| exact placeholders | 64 |
| assistant target tokens in tokenizer smoke | 15 |
| optimizer updates per arm | 36 |
| GPUs | 2 × RTX 3090 |

冻结权威已先以 commit `c796630` 推送。随后正式 roster 只写入一次，并返回
`PASS_PRTA_GEN_R41A_ROSTER_SUPPORT`：

- bytes：118,039；
- SHA-256：
  `2BA53C95BDDC78CBE1E585CF5954708892B6106578DA812226D87F94FD4F77C0`；
- train/development overlap：0；
- 所有 1,660 名已观察患者缺席；
- protected/gold/external/revealed outcome flags：false。

## R42A/R43 边界

R42A reverse cache 尚未生成，且没有 GPU 训练启动。真实 data preflight 已返回
`PASS_PRTA_GEN_R42A_REVERSE_CACHE_PREFLIGHT`：500 patients/rows、1,000 个
required DICOM Block-8 features、missing=0、heuristic permutation=false。它将在
R41A GO 后由 master chain 自动生成；如果 R41A STOP，不会浪费计算或越过门槛。

R43 preflight 只读取 dataset/patient/image-path 元数据来检查文件可用性，没有读取
progression outcome、metric 或 prediction。当前确认性支持不足，因此如果 R41A
和 R42A 都 GO，R43 会在 outcome 读取前 STOP。

## 启动状态

- R41A runner：`PASS_PRTA_GEN_R41A_RUNNER_PREFLIGHT`；
- R41A sequence：`PASS_PRTA_GEN_R41A_SEQUENCE_PREFLIGHT`；
- R42A reverse cache：
  `PASS_PRTA_GEN_R42A_REVERSE_CACHE_PREFLIGHT`；
- master chain：`PASS_PRTA_GEN_R41_R43_CHAIN_PREFLIGHT`；
- 两张 GPU：0 MiB / 0%；
- 所有 Seed/aggregate/reverse/master runtime 输出：fresh。

剩余动作只有提交本 receipt，然后启动 master chain 并持续监控到第一处注册终态。
