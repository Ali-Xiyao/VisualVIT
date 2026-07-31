# PRTA-Gen R44 独立数据支持审计冻结协议

状态：`FROZEN_PRTA_GEN_R44_INDEPENDENT_SUPPORT_AUDIT`

## 目的

R41A 已经终态 STOP。本协议不重跑 R41A，也不解锁 R42A/R43；它只回答：
是否存在一个不复用 R41A train/development、跨来源、五分类且双图完整的
silver patient cohort，可供后续单独冻结的 R44 readout survival 实验使用。

## 两条候选路径

1. R40A.2 fit 剩余患者：排除全部 R40B–R40B.4、R40C 与 R41A 患者后，
   只剩 1 名患者支持 `Resolved`，预期为五分类不可行。
2. CheXTemporal CheXpert silver：与原 MIMIC R40/R41 lineage 分离，
   只读取固定 revision 的 `silver_findings.parquet`，检查五类 patient
   support 与 prior/current 图像是否在本地完整。

## 冻结输入

- CheXTemporal repo：`anonaccount107240/CheXTemporal`
- revision：`81fd9cdd9b1208d8f8bd39d7a914c9b72fed8d79`
- 唯一允许下载：
  `silver_findings.parquet`
- bytes：`29,502,280`
- SHA-256：
  `31237F859D940D6B03748C845EC7C1C791B1837BA6E46E88E69BCA7F45E3C807`
- dataset filter：`chexpert`
- parent image root：
  `H:\Xiyao_Wang\000_Public Dataset\CheXpert-v1.0-small`

禁止下载 masks、sentences 或 studies。禁止读取 gold progression；gold parquet
只允许读取 `dataset` 与 `patient_id` 两列，用来排除全部 gold 患者。

## 支持门

按 `Resolved → New → Improved → Worse → Stable` 顺序，development 先于
train，用固定 SHA-256 无放回分配，每名患者最多一行：

| Partition | 每类患者 | 总患者 |
|---|---:|---:|
| train | 200 | 1,000 |
| development | 50 | 250 |

所有选择行必须同时存在 prior/current 图像，train/development 必须 patient
disjoint，且不得包含任何 CheXTemporal gold 患者。

任一条件失败，返回：

```text
STOP_PRTA_GEN_R44_INDEPENDENT_SUPPORT
```

全部通过，只返回数据支持：

```text
PASS_PRTA_GEN_R44_INDEPENDENT_SUPPORT
```

PASS 不会自动写 roster 或启动 GPU。它只允许继续冻结新的 R44 model、
cache、Seed、control 与 gate 协议。

## 结论边界

CheXTemporal silver progression 来自 MedGemma 标注，只能作为跨来源开发
监督，不能称 independent expert confirmation、gold generalization、临床证据
或外部科学确认。R42A/R43 在任何 R44 结果下仍保持原锁定状态。
