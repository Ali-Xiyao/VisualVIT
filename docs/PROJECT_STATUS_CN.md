# VisualVIT 当前项目状态

## 直接结论

TIER-CXR-VLM 的核心冻结链已经跑完，不需要重跑 R38 或 R39：

| 阶段 | 决策 | 核心证据 |
|---|---|---|
| R37.1 | `GO_R37_1_THREE_SEED_INTERNAL_QUALIFICATION` | A6 对 current-only、CMCP、A0 均通过三 Seed patient bootstrap |
| R37C | `GO_R37C_ONE_SHOT_DEV` | 300-dev 一次揭示；A6−A0 +3.42 pp，95% CI [+0.89,+6.20] |
| R38 | `GO_R38_FIXED64_SURVIVAL` | exact-64/no-routing 后 effect retention = 1.0 |
| R39 | `GO_R39_FROZEN_VLM_TRANSFER` | 483-test 一次揭示；A6−A0 +15.01 pp，95% CI [+13.80,+16.14] |

独立的后续生成 readiness 结论为：

| 阶段 | 决策 | 核心证据 |
|---|---|---|
| PRTA-Gen R40A | `STOP_PRTA_GEN_R40A_INFORMATION_SUFFICIENCY` | 历史三均值 readout 在 Seed 17 对 prior-shuffle 的 CI 跨零 |
| PRTA-Gen R40A.1 | `STOP_PRTA_GEN_R40A1_DISCOVERY` | moments Seed 29 为负；cosine Seed 17 为负 |
| PRTA-Gen R40A.2 | `GO_PRTA_GEN_R40A2_QUALIFICATION` | 修复真实 4/12/16/16/12/4 layout 后，三 Seed 对 query/shuffle 的 point 与 bootstrap 门全部通过 |
| PRTA-Gen R40B–B.3 | STOP | 四批互斥 cohort 上 Qwen readout 最好 29/32，未达 32/32 |
| PRTA-Gen R40B.4 | `PASS_PRTA_GEN_R40B4_STRUCTURED_HEAD_SMOKE` | 第五批全新 32-patient cohort 上 progression/schema/finding 均 32/32 |

R40A 历史 STOP 不撤销 R39 GO；R40A.2 使用新的 discovery2 和原封未读
qualification 修复了明确的 token-layout mismatch。R40B.4 只跑通
progression-only structured emission 的工程 overfit smoke。Qwen 自由生成、
开放式报告、其他字段、R41 SFT、R42 G-CMCP/reversal 与 R43 gold/external
仍未解锁。

R39 还通过：

- A6−current-only：+3.22 pp，95% CI [+2.47,+4.02]；
- A6−query-only：+15.77 pp，95% CI [+14.59,+16.84]；
- A6−prior-shuffle：+2.19 pp，95% CI [+1.39,+3.05]；
- 三个 Seed 对全部注册比较方向为正；
- VLM trainable parameters = 0；
- no pixel bypass；
- exactly 64 visual tokens；
- 三套 predictions 在唯一一次 label reveal 前冻结；
- gold outcomes unread。

## 当前可支持的主张

可以支持：

- PRTA-CXR 的正确纵向 prior 表示优于 capacity-matched A0；
- 收益不是仅由 finding query、current image 或随机 prior shortcut 造成；
- 表示收益在固定 64-token 接口和完全冻结的 Qwen3-VL 后仍然存在。
- R40A.2 semantic-layout 表示含有通过独立 qualification 的
  prior-specific progression 信息；
- 受限结构化头可在全新 32-patient engineering cohort 上把该表示输出为
  progression-only 两字段 JSON，并达到 32/32。

暂不支持：

- gold 或跨机构外部泛化；
- 临床部署；
- 所有视觉 backbone、VLM 尺度或 prompt 均有效；
- Qwen 自由生成、开放式比较句生成、grounding 或 localization 已改善；
- R40B.4 的 32-row overfit smoke 具有 patient-level 泛化能力；
- 根据已揭示 483-test 再选择的新模型属于 confirmatory 结果。

## 权威阅读顺序

1. `reports/PRTA_GEN_R40A2_R40B4_STRUCTURED_ROUTE_RESULT_CN.md`
2. `reports/PRTA_GEN_R40A_FAILURE_CASE_STUDY_CN.md`
3. `reports/R39_FROZEN_VLM_TRANSFER_FINAL_CN.md`
4. `TIER_CXR_VLM_Next_Stage_Proposal_CN.md`
5. `TIER_CXR_VLM_Empty_Result_Tables_CN.md`
6. `docs/TIER_CXR_VLM_EXPERIMENT_GAP_AUDIT_CN.md`
7. `task_plan.md`、`findings.md`、`progress.md`

## Runtime 权威产物

- R39 pipeline status：
  `H:\VisualVIT_runtime\050_routeD\r37_prta_cxr\r39_pipeline_status.json`
- R39 qualification：
  `H:\VisualVIT_runtime\050_routeD\r37_prta_cxr\r39_sealed_reveal_v1\qualification.json`
- R39 reveal receipt：
  `H:\VisualVIT_runtime\050_routeD\r37_prta_cxr\r39_sealed_reveal_v1\reveal_receipt.json`
- PRTA-Gen R40A target audit：
  `H:\VisualVIT_runtime\050_routeD\r37_prta_cxr\prta_gen_r40_readiness_v1\target_audit\audit.json`
- PRTA-Gen R40A progression aggregate：
  `H:\VisualVIT_runtime\050_routeD\r37_prta_cxr\prta_gen_r40_readiness_v1\probes\progression\aggregate.json`
- PRTA-Gen R40A.2 qualification：
  `H:\VisualVIT_runtime\050_routeD\r37_prta_cxr\prta_gen_r40a2_layout_repair_v1\probes\semantic_layout_means_v1\qualification\aggregate.json`
- PRTA-Gen R40B.4 structured result：
  `H:\VisualVIT_runtime\050_routeD\r37_prta_cxr\prta_gen_r40b4_structured_head_smoke_v1\structured_head\result.json`

这些 runtime 产物不进入 Git。不要为了整理仓库重复计算 source、
per-shard 或 checkpoint hashes。

## 当前停止边界

R39 已终止；R40A.2 qualification 与 R40B.4 engineering smoke 也已终止。
当前只允许：

- 仓库整理、复现审计和论文材料准备；
- 使用现有聚合结果生成表格或图；
- 对 R40B.4 做只读复现审计或独立冻结的后续开发实验；
- 独立注册的 gold/external descriptive confirmation。

禁止：

- 针对 483-test outcome 调参、换阈值、挑 Seed 或换 checkpoint；
- 把 post-hoc 483 分析改写成新的 confirmatory GO；
- 用 gold 选择模型或决定叙事。
- 把 R40B.4 写成 Qwen free-generation、科学泛化或临床结论；
- 在五批已观察 cohort 上继续搜索 learning rate、loss、decoder 或阈值；
- 绕过当前锁定状态启动 R41/R42/R43 或其他生成字段。

## 仓库验证状态

- PRTA-Gen R40A.2/R40B.4 focused tests：32 passed；
- Ruff (`src scripts tests`)：PASS；
- Python compileall：PASS；
- Markdown local links：PASS；
- `git diff --check`：PASS；
- full pytest：777 passed、1 expected xfailed、1 failed。

唯一 full-suite failure 是历史 R6 closed-manifest freeze-record hash drift。
同一 targeted test 在没有本轮整理修改的 clean commit `24f57c3` 上也失败，
因此不是本轮移动 proposal、添加索引或 lint cleanup 导致。R6 是已关闭的
旧 protocol；本轮不通过重写其 frozen registry 来制造假 PASS。
