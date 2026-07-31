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

## 从这里开始

1. [当前项目状态](docs/PROJECT_STATUS_CN.md)
2. [R41A Qwen SFT 终态报告](reports/PRTA_GEN_R41A_PROGRESSION_SFT_RESULT_CN.md)
3. [R41A 失败案例研究](reports/PRTA_GEN_R41A_FAILURE_CASE_STUDY_CN.md)
4. [R40C 内部泛化终态报告](reports/PRTA_GEN_R40C_STRUCTURED_GENERALIZATION_RESULT_CN.md)
5. [PRTA-Gen R40A.2/R40B.4 结构化路线终态报告](reports/PRTA_GEN_R40A2_R40B4_STRUCTURED_ROUTE_RESULT_CN.md)
6. [R40C preflight 与 roster receipt](reports/PRTA_GEN_R40C_STRUCTURED_GENERALIZATION_PREFLIGHT_CN.md)
7. [PRTA-Gen R40A 失败案例研究](reports/PRTA_GEN_R40A_FAILURE_CASE_STUDY_CN.md)
8. [R39 终局报告](reports/R39_FROZEN_VLM_TRANSFER_FINAL_CN.md)
9. [TIER-CXR-VLM 当前 Proposal](TIER_CXR_VLM_Next_Stage_Proposal_CN.md)
10. [结果表与实验登记](TIER_CXR_VLM_Empty_Result_Tables_CN.md)
11. [消融与对比实验缺口审计](docs/TIER_CXR_VLM_EXPERIMENT_GAP_AUDIT_CN.md)

## 代码与复现入口

- `configs/r37/`：R37.1 候选与 R37C 冻结配置；
- `configs/r38/`：exact-64 survival 配置；
- `configs/r39/`：frozen-VLM transfer 配置；
- `configs/prta_gen/`：PRTA-Gen R40A–R40C probe、structured generation
  与 internal-generalization 冻结配置；
- `src/visualvit/prta.py`：PRTA-CXR adapter、loss 与等变投影；
- `src/visualvit/prta_gen.py`、`qwen_adapter.py`：生成目标/probe 与
  exact-64 generative adapter 工程面；
- `src/visualvit/r38_fixed64.py`：固定 64-token 打包；
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
