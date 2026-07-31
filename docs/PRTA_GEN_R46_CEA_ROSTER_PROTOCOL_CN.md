# PRTA-Gen R46 CEA 新 Development Roster 冻结协议

> 日期：2026-07-31
> 状态：pre-outcome authority
> 协议：`prta-gen-r46-cea-v1`

## 目的

R45 CDEB 已在 discovery 冻结为
`STOP_PRTA_GEN_R45_CDEB_DISCOVERY`。R46 不是修改 R45 bridge 或门后重跑，
而是另立 **Causal Evidence Arbitration (CEA)**：使用结构化 temporal
expert 的 true-pair / current-only 因果证据，决定何时覆盖一个冻结生成器
baseline，低证据样本保持 baseline。

本文件只冻结 R46 development roster。它不训练模型、不选择阈值、不读取
R45 qualification / confirmation outcome。

## 固定数据边界

- fitting：只允许复用 R45 `train` 的 2,500 patients 与已存在 token；
- R46 development：从 CheXTemporal CheXpert silver 中选择 250 名新
  patients，每类 50；
- 必须排除 R45 四个 partitions 的全部 3,750 patients；
- R45 原 500 qualification 与 250 confirmation 继续 sealed；
- protected 300-dev、revealed 483-test、gold 与 external 不读取；
- one row per patient，五类均衡，图像必须完整可用；
- 使用固定 namespace 与 stable SHA-256 排序，不允许 outcome-driven
  resplit；
- 选择后至少保留 150 名未选 `Resolved` patients。

## 执行顺序

1. 校验 R45 roster config、roster 与 terminal aggregate 的 bytes、SHA-256
   和 status；
2. 校验 R45 qualification / confirmation 的 unlock、token、outcome flags
   全部为 false；
3. 只在内存中执行 support preflight；
4. config、builder、tests 与本协议提交并推送后，真实 roster 只写一次；
5. 仅审计 counts、disjointness、reserve、hash 与 firewall，不输出患者身份。

通过 roster support 只允许进入 R46 method/cache authority 编写，不构成
科学 GO，也不自动解锁任何 sealed cohort。
