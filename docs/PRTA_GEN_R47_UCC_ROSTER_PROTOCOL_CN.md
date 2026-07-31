# PRTA-Gen R47 UCC Development Roster 冻结协议

R47 **Unanimous Counterfactual Consensus (UCC)** 来自已冻结的 R46
identity-free case study：三个 structured Seed 对 true-pair 完全一致、
且三个 current-only 都不支持该类时，才允许覆盖 frozen generator
baseline。

本阶段只冻结新 roster：

- 复用 R45 train 2,500 patients 作 fit；
- 排除 R45 全部 3,750 patients 与 R46 development 全部 250 patients；
- 从剩余 CheXTemporal CheXpert silver 中固定 500 名新 development
  patients，每类 100；
- stable SHA-256、one row per patient、图像完整；
- 选择后至少保留 70 名未选 Resolved patients；
- R45 qualification/confirmation 继续 sealed；
- 不训练、不缓存、不读取 R47 outcome。

Config、builder、tests 与本协议提交推送后，真实 roster 才可写一次。
