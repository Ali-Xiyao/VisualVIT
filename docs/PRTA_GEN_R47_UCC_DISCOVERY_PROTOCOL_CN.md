# PRTA-Gen R47 Unanimous Counterfactual Consensus Discovery

R47 UCC 是 R46 STOP 后另立的独立验证，不修改 R46。

## 冻结方法

- R45 train 2,500 patients 拟合三个 499,973 参数 structured heads；
- Seeds 17/29/43，100 epochs、2,000 updates/Seed；
- inherited frozen Qwen/projector baseline 一次性生成
  true/current/query/shuffle；
- 无阈值、无 quantile selection；
- 仅当三个 Seed 的 true-pair class 完全一致、三个 current-only class
  全部不同于该 consensus，且 consensus 不同于 baseline 时覆盖；
- 其余样本严格回退 baseline；
- 同一规则应用到 prior-shuffle control。

## 新 cohort

R47 development 为 500 名新患者，每类 100；排除 R45 全部 3,750 与 R46
全部 250 patients。R45 qualification/confirmation 继续 sealed。

## 冻结 discovery gate

全部满足才 GO：

- UCC true macro-F1 ≥ 0.40，五类 recall 均 ≥ 0.12；
- UCC−baseline ≥ +1 pp，patient-bootstrap 95% CI 下界 > 0；
- UCC true−shuffle ≥ +1 pp，95% CI 下界 > 0；
- override rate ∈ [0.05, 0.25]；
- recovered−regressed ≥ 1；
- low-evidence baseline agreement、schema、finding echo 均为 1.0。

任一失败则 `STOP_PRTA_GEN_R47_UCC_DISCOVERY`，不得重调规则或门。
