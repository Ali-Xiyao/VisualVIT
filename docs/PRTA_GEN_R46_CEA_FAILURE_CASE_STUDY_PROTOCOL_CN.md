# R46 CEA Identity-Free Failure Case Study 协议

> 日期：2026-07-31
> 状态：pre-analysis frozen

R46 discovery 已终止为 `STOP_PRTA_GEN_R46_CEA_DISCOVERY`。本分析只读取
已完成 baseline、Seeds 17/29/43 与 aggregate，不训练模型、不修改阈值、
不读取 sealed cohort。

## 固定统计

- 三 Seed raw structured true prediction 的一致率；
- 三 Seed selected CEA prediction 的一致率；
- 至少一个 Seed 改变 baseline 的样本比例；
- 三个预定义共识规则的 override count/rate、macro-F1、五类 recall、
  recovered、regressed 与 net recovery：
  - true 至少 2/3 同意且 current-only 至少 2/3 不支持该类；
  - true 3/3 同意且 current-only 至少 2/3 不支持；
  - true 3/3 同意且 current-only 3/3 不支持；
- 同一规则在 prior-shuffle 上的描述性结果。

输出禁止 patient ID、example ID 与逐行 prediction。任何结果只用于提出
独立 R47 假设；不得回写 R46 score、quantile、训练或 gate。
