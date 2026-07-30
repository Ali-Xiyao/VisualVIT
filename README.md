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
```

R40A.2 修复 semantic token layout 后，在独立 qualification 上证明
progression 信息可读；R40B.4 在第五批全新 32-patient engineering cohort
上以受限结构化头达到 progression/schema/finding 32/32。四条 Qwen
free/constrained causal-LM readout 路线仍为 STOP，因此这不是 Qwen 自由
生成或科学泛化结论，R41–R43 与其他字段仍锁定。

下一阶段 R40C 的 pre-outcome authority 已准备完成：冻结 1,000 名 train /
500 名 development、三 Seed、四个容量匹配控制臂与 patient-bootstrap
门。真实 roster 已一次性写入并通过 receipt 审计；Seed result、checkpoint、
aggregate 与 GPU 训练均未启动，下一门是单独授权 Seed 17。

## 从这里开始

1. [当前项目状态](docs/PROJECT_STATUS_CN.md)
2. [PRTA-Gen R40A.2/R40B.4 结构化路线终态报告](reports/PRTA_GEN_R40A2_R40B4_STRUCTURED_ROUTE_RESULT_CN.md)
3. [R40C 内部泛化 preflight](reports/PRTA_GEN_R40C_STRUCTURED_GENERALIZATION_PREFLIGHT_CN.md)
4. [PRTA-Gen 失败案例研究](reports/PRTA_GEN_R40A_FAILURE_CASE_STUDY_CN.md)
5. [R39 终局报告](reports/R39_FROZEN_VLM_TRANSFER_FINAL_CN.md)
6. [TIER-CXR-VLM 当前 Proposal](TIER_CXR_VLM_Next_Stage_Proposal_CN.md)
7. [结果表与实验登记](TIER_CXR_VLM_Empty_Result_Tables_CN.md)
8. [消融与对比实验缺口审计](docs/TIER_CXR_VLM_EXPERIMENT_GAP_AUDIT_CN.md)

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
