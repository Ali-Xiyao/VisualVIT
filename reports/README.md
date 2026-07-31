# VisualVIT Reports Index

## 当前 TIER-CXR-VLM 主线

1. `PRTA_GEN_R49_UNIFIED_THREE_WAY_RESULT_CN.md`
2. `PRTA_GEN_R48_FPRR_POOLED_INTERNAL_FINAL_CN.md`
3. `PRTA_GEN_R48_FPRR_CONFIRMATION_RESULT_CN.md`
4. `PRTA_GEN_R45_R48_CASE_STUDY_AND_RAW_B3_RESULT_CN.md`
5. `PRTA_GEN_R45_CDEB_DISCOVERY_RESULT_CN.md`
6. `PRTA_GEN_R44A_CROSS_SOURCE_SILVER_SFT_RESULT_CN.md`
7. `PRTA_GEN_R44A_FAILURE_CASE_STUDY_CN.md`
8. `PRTA_GEN_R41A_PROGRESSION_SFT_RESULT_CN.md`
9. `PRTA_GEN_R41A_FAILURE_CASE_STUDY_CN.md`
10. `PRTA_GEN_R41_R43_PREFLIGHT_CN.md`
11. `PRTA_GEN_R40C_STRUCTURED_GENERALIZATION_RESULT_CN.md`
12. `PRTA_GEN_R40A2_R40B4_STRUCTURED_ROUTE_RESULT_CN.md`
13. `PRTA_GEN_R40C_STRUCTURED_GENERALIZATION_PREFLIGHT_CN.md`
14. `PRTA_GEN_R40A_FAILURE_CASE_STUDY_CN.md`
15. `PRTA_GEN_R40A_INFORMATION_SUFFICIENCY_RESULT_CN.md`
16. `R39_FROZEN_VLM_TRANSFER_FINAL_CN.md`
17. `R37_1_PROPOSAL_AND_CASE_STUDY_CLOSURE_CN.md`
18. `R37_1_TWO_SEED_FRESH_HOLDOUT_RESULT.md`
19. `R37_INVERSION_FAILURE_CASE_STUDY.md`
20. `R37_FORMAL_BUNDLE_PREFLIGHT.md`

最终总体状态为 `POSITIVE_PRTA_GEN_R48_FPRR_POOLED_INTERNAL`：合并全部
750 名 patient-disjoint held-out patients 后，true F1 0.373614，
true−shuffle +5.702 pp、CI [2.529, 9.101]，true−current +7.860 pp、
CI [4.629, 11.045]。Qualification/confirmation 分拆结果作为异质性审计
保留。同 qualification cohort 的
Raw two-image frozen Qwen3-VL B3 已完成，但 macro-F1 仅 0.141724，
相对 FPRR true-pair 为 −25.886 pp，95% CI [−30.773, −20.934]。
R42A/R43 与 gold/external 仍锁定。
R49 已在同一 750 人上补齐 Raw/Naive exact-64/PRTA exact-64 三系统归因。
三者 F1 为 0.192915/0.295921/0.354372；PRTA−Raw +16.146 pp，CI
[+12.090,+20.198]；PRTA−Naive +5.845 pp，CI [+2.610,+9.081]。后一个
同 token/projector/训练预算对比支持 finding-guided 跨时间对齐本身带来增益。
该结果仍是 internal post-hoc case study，不升级为独立确认。
R44A 在更大的跨来源 silver cohort 上解决了 schema、finding echo 和
query-only separation，但三个 Seed 均未通过正确 prior 对 prior-shuffle
的冻结门，Seed 43 还发生 G1 退化。该结论不撤销 R40C 的有限 structured
internal GO，也不改写 R41A 原 STOP。
Identity-free case study 将主要机制定位为 70.0%–83.6% true/shuffle
prediction invariance 与跨 Seed G0→G1 instability。另立的 R45 causal
delta evidence-bottleneck 已完成四臂 discovery，但 full CDEB 未优于
baseline、也未形成正向 prior-shuffle 分离，三个核心门失败。后续只能
另立 R46 authority，不能调参绕过 R45 STOP。

## R32–R33 TIER 前序

- `R32_TIER_CXR_VLM_AUTHORITY_ENGINEERING_RESULT.md`
- `R33_TOKEN_SURVIVAL_RESULT.md`
- `R33A_CASE_STUDY_RESCUE_RESULT.md`

## R27–R31 失败与修复谱系

- `R27_BINDING_IDENTIFIABILITY_AUDIT.md`
- `R28_FINAL_CASE_STUDY_AND_PROPOSAL_CLOSURE.md`
- `R29_FAILURE_CASE_STUDY.md`
- `R30_FAILURE_CASE_STUDY.md`
- `R31_CONFIDENCE_CONSENSUS_FINAL.md`
- `R31_CONFIDENCE_CONSENSUS_REPRO.md`

## R25–R26 CAPES 谱系

- `R25_1_MANIFEST_QUALIFICATION.md`
- `R26_C1_ORACLE_BINDING_RESULT.md`

其他文件为早期工程、数据、统计或失败审计。当前状态与受保护边界以根目录
`README.md`、`docs/PROJECT_STATUS_CN.md`、PRTA-Gen R44A/R41A/R40C 终态
报告和 R39 终局报告为准。
