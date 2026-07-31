# R48 Frozen Prior-Responsiveness Replication Qualification

R46/R47 显示 router 本身没有可靠增益，但 frozen generator 在全新 R47
cohort 上对 true prior 相对 shuffle 有明显分离。R48 因而停止设计 router，
只检验一个 selection-free 问题：

> 同一个 immutable Qwen + projector checkpoint，在最初为 R45 封存且从未
> 读取的 qualification cohort 上，是否稳定利用正确 prior？

R48 不训练、不选 checkpoint、不设阈值。500 名 qualification patients、
五类均衡，与 R45 train patient-disjoint。一次性缓存和生成
true/current/query/shuffle。

全部 gate 通过才 GO：

- true macro-F1 ≥ 0.35；
- 五类 recall 均 ≥ 0.12；
- true−shuffle ≥ +2 pp 且 bootstrap 95% CI 下界 > 0；
- true−current ≥ +2 pp 且 95% CI 下界 > 0；
- true−query ≥ +10 pp；
- schema/finding 1.0。

GO 只解锁另行冻结的 R48 confirmation；STOP 不得调门重跑。
