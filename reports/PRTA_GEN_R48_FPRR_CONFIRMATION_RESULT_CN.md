# PRTA-Gen R48 FPRR Confirmation 终态

## 结论

`STOP_PRTA_GEN_R48_FPRR_CONFIRMATION`

R48 qualification 的 selection-free prior-responsiveness 正结果没有在另一个
预先封存的 250 人 confirmation cohort 上复现。确认协议、checkpoint、prompt、
四臂、bootstrap 和门槛均在 outcome 可见前冻结，运行后没有调整。

| arm | macro-F1 | accuracy |
|---|---:|---:|
| true-pair | 0.318626 | 0.328 |
| current-only | 0.278350 | 0.312 |
| query-only | 0.114373 | 0.192 |
| prior-shuffle | 0.305379 | 0.324 |

所有 arm 的 schema validity 与 finding echo accuracy 都是 1.0，Qwen 与
projector trainable parameters 都是 0，cache-equivalence 通过。因此 STOP
是科学门失败，不是工程故障。

## 冻结门

| gate | observed | required | result |
|---|---:|---:|---|
| true macro-F1 | 0.318626 | >= 0.35 | FAIL |
| true−shuffle | +1.325 pp | >= +2 pp | FAIL |
| true−shuffle CI95 lower | −3.709 pp | > 0 | FAIL |
| true−current | +4.028 pp | >= +2 pp | PASS |
| true−current CI95 lower | −1.213 pp | > 0 | FAIL |
| true−query | +20.425 pp | >= +10 pp | PASS |
| all class recall | min 0.16 | >= 0.12 | PASS |
| schema/finding | 1.0/1.0 | 1.0/1.0 | PASS |

总计四个 gate failure。`internal_replication_claim_allowed=false`。

## 与 qualification 的关系

Qualification 500 人曾得到：

- true F1 0.400584；
- true−shuffle +7.982 pp，CI `[+3.873,+11.991]`；
- true−current +9.733 pp，CI `[+5.818,+13.706]`。

Confirmation 则下降到 true F1 0.318626，true−shuffle 的点效应和 CI 都未
通过。正确解释是 qualification-only development signal，不是稳定的内部
复制，更不是 external/gold 或临床证据。

## 终止边界

- 不根据 confirmation 调 F1 floor、bootstrap、prompt、pixel budget、
  checkpoint、router 或 cohort；
- 不再另开 R49 追求显著性；
- R42/R43、gold/external、开放式报告和临床主张继续锁定；
- Raw two-image B3 的负结果与 R48 confirmation STOP 一并完整报告。

## 可复核证据

- baseline：
  `H:\VisualVIT_runtime\050_routeD\r37_prta_cxr\prta_gen_r48_fprr_v1\confirmation\baseline\result.json`
- baseline：38,710 bytes，SHA-256
  `18191438A8B330E8BE3BD34346B70666583C9D65B9AE4B01B4EAF708D3DBD6FE`
- aggregate：
  `H:\VisualVIT_runtime\050_routeD\r37_prta_cxr\prta_gen_r48_fprr_v1\confirmation\aggregate.json`
- aggregate：3,375 bytes，SHA-256
  `46EC22D90E0B662284116CE5DD24ED464857F60407D73B7596A5319BBFB3B6BB`
- active workers：0
- GPU0/GPU1：0 MiB，0% utilization
