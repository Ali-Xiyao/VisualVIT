# VisualVIT：TIER-CXR-VLM / PRTA-CXR

本仓库研究纵向胸片中的时间变化表示，以及这些表示能否在固定
64-token 视觉接口下迁移到完全冻结的 VLM。

当前核心实验链已完成：

```text
R37.1 three-seed internal GO
→ R37C one-shot 300-dev GO
→ R38 exact-64 survival GO
→ R39 frozen-VLM transfer GO
```

终局状态为 `GO_R39_FROZEN_VLM_TRANSFER`。该结论适用于已冻结的
silver cohort、Qwen3-VL-4B、PRTA-CXR A6、Seeds 17/29/43 及注册 controls。
Gold outcomes 仍未读取，当前结果不等于临床部署或外部泛化证明。

R49/R50 已补齐当前最重要的系统与方法学对比。同一 750 人上，Raw two-image、
Naive exact-64、PRTA exact-64 F1 为 0.1929/0.2959/0.3544，PRTA−Naive
+5.85 pp、CI `[+2.61,+9.08]`。随后三 Seed 直接分类 benchmark 中，
TILA-CE、Siamese signed/absolute、TILA-BiCE/TCL、TAC-adapted mean F1 为
0.4577/0.4174/0.3951/0.2658。TILA/B2 与 PRTA 的读出接口不同，因此只作
post-hoc cross-interface 描述；完整边界见 R50 报告。

R52 随后在新的 500 人、相同 2,500-train、相同 exact-64 cache 与完全相同
5,991,173 参数直接分类头下完成三 Seed matched comparison。PRTA/TILA/B2
mean Macro-F1 为 **0.3605/0.2731/0.2679**；PRTA−TILA +8.75 pp、CI
`[+4.48,+12.86]`，PRTA−B2 +9.26 pp、CI `[+4.77,+13.20]`。因此可在该
fresh internal matched-head 边界内正式写 PRTA 显著优于两个 exact-64
适配；这不等于原生 TILA 系统或 frozen-Qwen 接口结论。

后续 PRTA-Gen 案例驱动修复已经跑通一个严格限定的结构化路径：

```text
GO_PRTA_GEN_R40A2_QUALIFICATION
→ PASS_PRTA_GEN_R40B4_STRUCTURED_HEAD_SMOKE
→ GO_PRTA_GEN_R40C_INTERNAL_GENERALIZATION
→ STOP_PRTA_GEN_R41A_PROGRESSION_SFT_SURVIVAL
```

R40A.2 修复 semantic token layout 后，在独立 qualification 上证明
progression 信息可读；R40B.4 在第五批全新 32-patient engineering cohort
上以受限结构化头达到 progression/schema/finding 32/32。四条 Qwen
free/constrained causal-LM readout 路线仍为 STOP，因此这不是 Qwen 自由
生成或科学泛化结论。

R40C 已在排除五批共 160 名已观察患者后，以 1,000 名 train / 500 名
patient-disjoint development、三 Seed、四个容量匹配控制臂和
patient-bootstrap 跑到 `GO_PRTA_GEN_R40C_INTERNAL_GENERALIZATION`。
这是 progression-only structured head 的内部开发泛化结果。随后独立冻结的
R41A Qwen SFT case study 完成六个 arm 和三 Seed 聚合；G1 true-pair
macro-F1 为 0.3474/0.3632/0.4304，但 `Worse` recall 为
0.00/0.08/0.08，且 G1−G0 为 -0.46/-13.40/-6.85 pp，共 8 个门失败。
因此 R41A 科学 STOP，R42A/R43 未启动；gold/external 与临床主张仍锁定。
只读 failure case study 进一步显示：G1 每 Seed 对 25 个真实 `Worse`
只输出 0/7/9 次该类，且 49/125 个样本在三个 G1 Seed 中全部答错。
这是对 STOP 的机制性描述，不是新实验或重启依据。

另立的 R44A 跨来源 silver case study 随后在 CheXpert silver 上以
1,000 train / 250 patient-disjoint development、相同 G0/G1、Seeds
17/29/43 和冻结门完整执行。六个 arm 均完成 94 次 updates，schema 与
finding echo 均为 100%；G1 相对 query-only 为
+24.42/+21.14/+18.04 pp，但相对 prior-shuffle 仅为
-0.15/+1.59/-0.25 pp，三个 95% CI 下界均不大于零。Seed 43 还出现
macro-F1 0.2863、`Worse` recall 0.02 和 G1−G0 -7.25 pp。九个门失败，
终态为 `STOP_PRTA_GEN_R44A_CROSS_SOURCE_SILVER_SFT_SURVIVAL`。
这说明扩大跨来源 silver 数据仍未建立稳定的正确 prior grounding；
R42/R43 继续锁定。
预注册的 identity-free case study 进一步发现，G1 在
70.0%–83.6% 的患者上对 true/shuffled prior 输出同一类别，且正确性改变
几乎对称；attention-LoRA 的 G0→G1 净迁移为 +7/+3/-16 名患者。后续新
方向因此被限定为另立 untouched roster 的 R45 causal delta evidence
bottleneck，而不是 R44A 调参重跑。R45 四臂 discovery 随后完整执行，
但 full CDEB 的 true-pair macro-F1 仅 0.3420，低于 inherited baseline
0.3806；相对 prior-shuffle 为 -1.26 pp，auxiliary head macro-F1 为
0.3123。三个核心门失败，终态为
`STOP_PRTA_GEN_R45_CDEB_DISCOVERY`。R45 qualification / confirmation
未读取、未物化，不能根据本次 outcome 调参重跑。下一步只允许另立 R46
causal evidence arbitration，在排除整个 R45 roster 的新 development
patients 上预注册和验证。

## 从这里开始

1. [当前项目状态](docs/PROJECT_STATUS_CN.md)
2. [R52 统一 exact-64 直接分类头结果](reports/PRTA_GEN_R52_MATCHED_DIRECT_HEAD_RESULT_CN.md)
3. [R50 文献方法复现与强基线结果](reports/PRTA_GEN_R50_LITERATURE_METHOD_REPRODUCTION_RESULT_CN.md)
4. [R49 统一三系统结果](reports/PRTA_GEN_R49_UNIFIED_THREE_WAY_RESULT_CN.md)
5. [R45 CDEB discovery 终局报告](reports/PRTA_GEN_R45_CDEB_DISCOVERY_RESULT_CN.md)
6. [R44A 跨来源 silver SFT 终态报告](reports/PRTA_GEN_R44A_CROSS_SOURCE_SILVER_SFT_RESULT_CN.md)
7. [R44A failure case study 与 R45 方向选择](reports/PRTA_GEN_R44A_FAILURE_CASE_STUDY_CN.md)
8. [R41A Qwen SFT 终态报告](reports/PRTA_GEN_R41A_PROGRESSION_SFT_RESULT_CN.md)
9. [R41A 失败案例研究](reports/PRTA_GEN_R41A_FAILURE_CASE_STUDY_CN.md)
10. [R40C 内部泛化终态报告](reports/PRTA_GEN_R40C_STRUCTURED_GENERALIZATION_RESULT_CN.md)
11. [PRTA-Gen R40A.2/R40B.4 结构化路线终态报告](reports/PRTA_GEN_R40A2_R40B4_STRUCTURED_ROUTE_RESULT_CN.md)
12. [R40C preflight 与 roster receipt](reports/PRTA_GEN_R40C_STRUCTURED_GENERALIZATION_PREFLIGHT_CN.md)
13. [PRTA-Gen R40A 失败案例研究](reports/PRTA_GEN_R40A_FAILURE_CASE_STUDY_CN.md)
14. [R39 终局报告](reports/R39_FROZEN_VLM_TRANSFER_FINAL_CN.md)
15. [TIER-CXR-VLM 当前 Proposal](TIER_CXR_VLM_Next_Stage_Proposal_CN.md)
16. [结果表与实验登记](TIER_CXR_VLM_Empty_Result_Tables_CN.md)
17. [消融与对比实验缺口审计](docs/TIER_CXR_VLM_EXPERIMENT_GAP_AUDIT_CN.md)

## 代码与复现入口

- `configs/r37/`：R37.1 候选与 R37C 冻结配置；
- `configs/r38/`：exact-64 survival 配置；
- `configs/r39/`：frozen-VLM transfer 配置；
- `configs/prta_gen/`：PRTA-Gen R40A–R40C probe、structured generation、
  internal-generalization、R44A cross-source silver 与 R49–R52 对比配置；
- `src/visualvit/prta.py`：PRTA-CXR adapter、loss 与等变投影；
- `src/visualvit/prta_gen.py`、`qwen_adapter.py`：生成目标/probe 与
  exact-64 generative adapter 工程面；
- `src/visualvit/r38_fixed64.py`：固定 64-token 打包；
- `src/visualvit/r50_method_baselines.py`：TILA inversion、B2 与 TAC-adapted
  方法学对比实现；
- `scripts/`：cache、train、predict、reveal 与 aggregate 入口；
- `tests/`：单元测试和 fail-closed 协议测试；
- `docs/superpowers/specs/`：各阶段冻结规范；
- `reports/`：科学结果与失败分析；
- `history/`：已关闭规划包和历史 proposal。

默认验证命令：

```powershell
python -m pytest
python -m ruff check src scripts tests
git diff --check
```

Current-method focused tests pass. The complete historical suite currently
reports `787 passed, 1 expected xfailed, 1 failed`; the single failure is a
preexisting R6 frozen-manifest hash drift reproduced unchanged at clean commit
`24f57c3`. It is intentionally not “fixed” by rewriting the closed R6
registry. See `docs/PROJECT_STATUS_CN.md`.

不要直接重启 R37C/R38/R39 launcher。483-test 已经按协议揭示一次，任何
新增模型或消融在该 cohort 上只能作为明确标注的 post-hoc secondary
analysis，不能覆盖现有 confirmatory 结论。

## 数据与发布边界

Git 中只发布源代码、配置、协议、聚合结果和不含身份信息的审计记录。
Credentialed images、feature/token caches、checkpoint 和逐行 prediction
保留在本地 runtime，不进入仓库。`data/official/` 中的 gold annotation
仍受 quarantine 约束；不要为探索、阈值选择或模型选择读取其 outcome。

当前工作分支：`codex/r37-prior-responsive-temporal-adapter`。
