# Experiment Plan: VisualVIT Route C

**Problem**: 在纵向胸片与多图 VLM 中，视觉实体跨图身份绑定是否是独立且可学习的性能瓶颈。
**Method Thesis**: 由唯一的 null-aware partial soft MatchGraph 在固定全局 token 预算下显式表示 persistent、birth 与 death，可隔离 oracle identity binding 效应并学习恢复该收益。
**Date**: 2026-07-13
**Design Authority**: `docs/superpowers/specs/2026-07-13-visualvit-unified-research-design.md`

**Current gate**: `GO_NONCONFIRMATORY_COMPONENT_SMOKE_ONLY + NO_GO_FORMAL_DATA/LICENSE/ETHICS/ORACLE + NO_GO_END_TO_END_TRANSFER + NO_GO_PHASE_II`

## Claim Map

| Claim | Why It Matters | Minimum Convincing Evidence | Linked Blocks |
|---|---|---|---|
| C1 同构 identity binding 因果效应 | 证明收益来自正确 assignment，而非额外特征、token 或参数 | Delta_bind 点估计 >=5 pp 且 95% CI 下界>0；B4 端到端同构；negative-control ratio 通过 | E1 |
| C2 learned null-aware recovery + transfer | 证明机制可以落地且不只在 oracle/classifier 中成立 | oracle denominator CI>0；Recovery 点估计及 CI 下界>=0.60；frozen-VLM >=2 pp 且 CI 下界>0 | E2, E3 |

**Anti-claims to rule out**: 更多 token、更多参数、错误的 anatomy shortcut、患者/图像泄漏、报告标签泄漏、test-driven seed/模型选择。

## Paper Storyline

- 主文必须证明：数据与同构资格；oracle 因果门；learned repair；单一 frozen-VLM transfer。
- 附录：normalized attention、controlled probe、order swap、encoder sensitivity、错误 taxonomy。
- 切除/后置：70B、三 VLM×六 benchmark、TRACE 大表、完整通用 DIVE、广泛 scaling。
- 基线家族最多三类：independent/compressed tokens；compute-matched fusion；supervision-matched identity controls。

## Experiment Blocks

### E0: Non-confirmatory qualification and pilot

- Claim tested: 不检验论文 claim，只检验工程和统计接口。
- Dataset / split / task: synthetic persistent/birth/death fixtures；本地 train/dev proxy pairs；sealed test 禁止读取。
- Systems: identity/oracle/deranged/learned MatchGraph；BiomedCLIP proxy；本地 Qwen2-VL 双图接口。
- Metrics: shape/mass/budget/isomorphism checks，overfit accuracy/F1，runtime，VRAM，deterministic rerun。
- Success: 组件 smoke 与负向 gate 行为均有证据；所有产物带 `NON_CONFIRMATORY_PROXY`。该块不宣称 end-to-end。
- Failure: 停在失败 gate，诊断后重跑同一规模，不扩数据/模型。
- Priority: MUST-RUN，当前已获授权。

### E1: Oracle causal gate

- Claim tested: C1。
- Dataset: 合法 gold longitudinal subset；patient-level train/dev/test；跨源去重。
- Systems: matched baseline、B4a、B4b、random、wrong-anatomy。
- Primary metric: patient-balanced macro Change F1；`Delta_bind=100*(F_B4b-F_B4a)`。
- Controls: features/token types/count/order/model/params/steps/seeds/checksums identical。
- Success: pilot-frozen mechanism margin and 95% CI gate；negative controls 不能复制 B4b。
- Failure: narrow equivalence refutes C1；wide CI is inconclusive。
- Priority: MUST-RUN，当前 SEALED。

### E2: Learned null-aware repair

- Claim tested: C2 representation component。
- Systems: simple similarity matcher、Stage1/2 contextualizer、full partial soft MatchGraph。
- Metrics: Recovery、macro Change F1、new/resolved subclass、calibration、token/compute。
- Success: Recovery >= 0.60；>=0.70 强成功。
- Failure: 0.40–<0.60 only one preregistered rescue；<0.40 stop learned claim。
- Priority: MUST-RUN；必须与 E1/E3 一起在 train/dev 上冻结，不能查看 E1 test 后再开发。

### E3: Frozen VLM transfer

- Claim tested: C2 interface transfer。
- Model: frozen local Qwen2-VL-7B；fixed prompt/decoding/64-token budget。
- Metrics: constrained-QA exact/macro F1、evidence consistency、runtime/VRAM。
- Success: preregistered paired improvement aligned with classifier result。
- Failure: retain representation result but report interface boundary。
- Priority: MUST-RUN；必须与 E1/E2 一起在 train/dev 上冻结，随后统一 test reveal。

### E4: External robustness and Phase-II gate

- One uncontaminated external set，encoder sensitivity，efficiency and failure taxonomy。
- External dataset identity/license/dedup/split/class mapping/preprocessing/checkpoint-adaptation policy/seeds/metrics/scripts must be signed before the internal unified test reveal；an independent custodian may use test IDs and non-outcome content hashes only for dedup，while labels/outcomes/predictions/metrics remain sealed；execution may occur later without protocol changes。
- PASS requires external `Delta_bind >=5.0 pp` with 95% CI lower `>0`，Recovery point and CI lower `>=0.60`，frozen-VLM learned-vs-B4a `>=2.0 pp` with CI lower `>0`，and negative-control ratio point `<=0.25` with 95% upper `<=0.50`；uncomputable endpoints or contamination are FAIL，not post-hoc domain-shift exemptions。
- Phase II only if C1、Recovery、frozen-VLM transfer、uncontaminated external replication、license/dedup 和 independent rerun 全部通过。
- Priority: MUST-RUN for full paper; generic DIVE is deferred。

## Run Order and Milestones

| Milestone | Goal | Runs | Decision Gate | Cost | Risk |
|---|---|---|---|---|---|
| M0 | Fresh preflight | GPU/disk/env/data/model inventory | H read-only; F >=60 GiB free; executable env | CPU minutes | stale paths/env |
| M1 | Contract correctness | synthetic null/mass/budget/B4 tests | all deterministic tests PASS | CPU <1 h | incorrect dustbin semantics |
| M2 | Learnability | 32–128 synthetic cases, seeds 17/29/43 | overfit and rerun PASS | CPU/GPU <2 h | optimization bug |
| M3 | Encoder/VLM smoke | BiomedCLIP feature + Qwen2-VL two-image | finite output, bounded VRAM, saved logs | 1–4 GPU h | dependency mismatch |
| M4 | Formal data qualification | license/hash/lineage/dedup/test seal | all six formal gates PASS | CPU + annotation | credentials/oracle missing |
| M5 | Joint train/dev + external-protocol freeze | E1/E2/E3 variants/checkpoints/prompts/seeds/scripts plus external dataset/protocol/metric/adaptation lock | signed freeze manifest before any internal test | 30–90 GPU h est. | test-driven development |
| M6 | Single unified test reveal | run frozen E1/E2/E3 once in one batch | no post-reveal method changes | 10–30 GPU h est. | multiplicity/denominator |
| M7 | Execute frozen external + independent rerun | uncontaminated E4 under the pre-reveal protocol and clean reproduction | all quantitative external/license/dedup/repro gates pass | 20–80 GPU h est. | interface/contamination |

## Compute and Data Budget

- Local: 2× RTX 3090 24 GiB；并行任务必须独立输出目录。
- Runtime: `F:\VisualVIT_runtime\050_routeC`；项目硬上限 180 GiB，始终保留 >=60 GiB。
- H drive: absolute read-only。
- Current pilot: first reuse local assets；no download unless a qualified gap is confirmed。
- Likely minimum later downloads: RAD-DINO ~346 MiB；optional BLINK validation ~10 MiB。
- Formal oracle needs: CheXTemporal/Chest ImaGenome annotations plus legally accessible parent images。
- Formal oracle qualification: 100% licensed/resolved parent IDs and zero overlap；ontology coverage >=95%；explicit matched/null judgment >=90% with Wilson lower >=85%；each primary class has at least max(100 patients, power-derived minimum) and sealed test >=20 patients/class。
- Human evaluation: at least 100 double-blind calibration pairs；weighted kappa point >=0.80 and 95% lower >=0.70；bbox median IoU >=0.70 and >=90% boxes IoU >=0.50；all disagreements adjudicated，critical missingness 0，independent 10% QC error <=2%。

## Statistical Lock

- Patient/source-content cluster is the resampling unit。
- Seed bank: 17, 29, 43, 71, 101, 137, 181, 233；pilot selects first S before test。
- Formal bootstrap: patient × paired-seed hierarchical, 10,000 iterations。
- Fixed-sequence claims；Holm within claim；BH-FDR exploratory。
- No seed additions or model choices after test reveal。
- Patient-balanced macro F1 gives each patient total weight 1 before five-class macro averaging；missing/uncertain labels are masked。
- C1: Delta_bind point >=5 pp and 95% CI lower>0；fixed test must have >=80% power for 5 pp。
- C2: oracle denominator 95% CI wholly >0 and >=95% bootstrap replicates positive；Recovery point and 95% CI lower >=0.60。
- Frozen-VLM: learned vs compute-matched B4a point >=2 pp and 95% CI lower>0。
- Negative controls: ratio point <=0.25 and bootstrap 95% upper <=0.50。
- Scaling null only by TOST/90% CI inside preregistered equivalence bounds。

## Risks and Mitigations

- Missing legal oracle: run only engineering proxy and issue `NO_GO_FORMAL_ORACLE`。
- B4 non-isomorphism: automated config/tensor/parameter/checksum audit blocks E1。
- Global budget overflow: current hard assembler explicitly blocks >28 entity/relation inputs until deterministic compression/selection allocator is implemented。
- Soft transport: current hard tokenizer rejects fractional plans until a dedicated mass-preserving soft allocator is implemented。
- Null instability: start synthetic exact fixtures and simple matcher before Sinkhorn。
- VLM dependency/VRAM: offline local smoke, frozen weights, low batch, no hidden download。
- End-to-end transfer: raw two-image Qwen smoke does not qualify; MatchGraph-to-64-token projector/position/attention injection must pass separately。
- Leakage: patient/study/image/source lineage plus content hash across candidate datasets。
- Weak effect: stop/downgrade according to CI rather than scaling blindly。

## Final Checklist

- [x] Two claims only
- [x] Main paper blocks are compact
- [x] Novelty isolation is explicit
- [x] Simplicity and frontier necessity are controlled
- [x] Must-run vs deferred runs separated
- [x] Negative-result interpretations defined
- [x] E0 preflight evidence collected
- [x] E0 pilot completed
- [ ] Formal data/oracle gates unlocked
