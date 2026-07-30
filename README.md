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

## 从这里开始

1. [当前项目状态](docs/PROJECT_STATUS_CN.md)
2. [R39 终局报告](reports/R39_FROZEN_VLM_TRANSFER_FINAL_CN.md)
3. [TIER-CXR-VLM 当前 Proposal](TIER_CXR_VLM_Next_Stage_Proposal_CN.md)
4. [结果表与实验登记](TIER_CXR_VLM_Empty_Result_Tables_CN.md)
5. [消融与对比实验缺口审计](docs/TIER_CXR_VLM_EXPERIMENT_GAP_AUDIT_CN.md)

## 代码与复现入口

- `configs/r37/`：R37.1 候选与 R37C 冻结配置；
- `configs/r38/`：exact-64 survival 配置；
- `configs/r39/`：frozen-VLM transfer 配置；
- `src/visualvit/prta.py`：PRTA-CXR adapter、loss 与等变投影；
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
reports `700 passed, 1 expected xfailed, 1 failed`; the single failure is a
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
