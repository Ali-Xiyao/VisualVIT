# R48 Frozen Prior-Responsiveness Replication Confirmation

R48 qualification 在预注册门槛下得到
`GO_PRTA_GEN_R48_FPRR_QUALIFICATION`。本阶段只验证同一个窄命题：

> 不训练、不选 checkpoint、不设 router 或阈值时，同一个 immutable
> Qwen + projector 是否能在另一个 patient-disjoint 的 250 人确认集上，
> 稳定利用正确 prior？

确认集在本协议冻结前从未物化 token、读取 outcome 或运行生成。模型、prompt、
四个 generator arms、2,000 次 patient-cluster bootstrap、随机种子和所有数值门槛
与 qualification 完全相同；只把 cohort 从 `qualification` 改成
`confirmation`。

全部条件通过才记为 `GO_PRTA_GEN_R48_FPRR_CONFIRMATION`：

- true macro-F1 >= 0.35；
- 五类 recall 均 >= 0.12；
- true-shuffle >= +2 pp 且 bootstrap 95% CI 下界 > 0；
- true-current >= +2 pp 且 bootstrap 95% CI 下界 > 0；
- true-query >= +10 pp；
- schema validity 与 finding echo accuracy 均为 1.0。

GO 只允许“同一内部数据源上的 patient-disjoint frozen replication”这一窄主张；
不等于 external validation、gold validation、临床效用或 ICLR 接收保证。任一门槛
失败即 STOP，不调门槛、不换 checkpoint、不重复抽 cohort。
