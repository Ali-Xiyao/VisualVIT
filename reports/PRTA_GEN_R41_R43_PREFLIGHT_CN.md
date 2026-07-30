# PRTA-Gen R41A–R43 自动链 Preflight

日期：2026-07-30

状态：`PRE_OUTCOME_PACKAGE_READY_PENDING_COMMIT_AND_ROSTER_WRITE`

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

正式 roster 仍未写入，因为冻结权威必须先 commit/push。提交后只允许一次 roster
write；随后固定 hash，并运行 R42 reverse-cache data preflight 与 master-chain
preflight。

## R42A/R43 边界

R42A reverse cache 尚未生成，且没有 GPU 训练启动。它将在 R41A GO 后由 master
chain 自动生成；如果 R41A STOP，不会浪费计算或越过门槛。

R43 preflight 只读取 dataset/patient/image-path 元数据来检查文件可用性，没有读取
progression outcome、metric 或 prediction。当前确认性支持不足，因此如果 R41A
和 R42A 都 GO，R43 会在 outcome 读取前 STOP。

## 启动前剩余动作

1. 提交并推送本 pre-outcome authority；
2. 一次性写入 R41A roster 并记录 SHA-256；
3. 运行 R41A sequence、R42A static/data、R43 与 master-chain preflight；
4. 确认两张 GPU 空闲、runtime 输出全新；
5. 启动 master chain，持续监控到第一处注册终态。
