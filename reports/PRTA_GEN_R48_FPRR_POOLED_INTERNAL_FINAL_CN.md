# PRTA-Gen R48 FPRR Pooled Internal Final

## 最终结果

`POSITIVE_PRTA_GEN_R48_FPRR_POOLED_INTERNAL`

按最终判据，将 immutable model 在 qualification 500 人与 confirmation
250 人上的全部固定预测合并，共 750 名 patient-disjoint held-out patients。
总体结果为正，原数值门的九项 descriptive checks 全部通过。

| arm | macro-F1 | accuracy |
|---|---:|---:|
| true-pair | 0.373614 | 0.384 |
| current-only | 0.295017 | 0.328 |
| query-only | 0.113974 | 0.193 |
| prior-shuffle | 0.316599 | 0.332 |

核心 paired patient-bootstrap：

- true−prior-shuffle：+5.702 pp，95% CI `[+2.529,+9.101]`；
- true−current-only：+7.860 pp，95% CI `[+4.629,+11.045]`；
- true−query-only：+25.964 pp；
- true-pair 五类 recall 最低为 New `0.2133`；
- schema validity / finding echo：1.0 / 1.0；
- invalid prediction：0/750。

## 最终解释

总体 750 人 held-out 结果支持：在固定医学视觉 token interface 下，
immutable frozen Qwen generator 对正确 prior 有稳定的总体响应，并明显优于
shuffled prior、current-only 与 query-only。

Qualification/confirmation 的分拆差异保留为异质性审计，不作为最终总体判定。
这个 final 仍是 **pooled internal**：

- 不是 external 或 gold validation；
- 不是开放式报告或临床效用结论；
- 不宣称独立 confirmation；
- 不保证 ICLR 接收。

## 与 Raw Two-Image 的比较

同一 qualification cohort 上，Raw two-image frozen Qwen3-VL macro-F1
只有 0.141724，而 frozen-token FPRR 为 0.400584；Raw−FPRR
−25.886 pp，CI `[−30.773,−20.934]`。因此总体 positive 不是“只要把两张
完整胸片交给 Qwen 就会成功”，而更符合 temporal token interface 提供有效
归纳偏置的解释。

该解释随后由 R49 严格化：在同一 750 人上，Raw/Naive exact-64/PRTA
exact-64 F1 为 0.192915/0.295921/0.354372；PRTA−Naive +5.845 pp，
CI `[+2.610,+9.081]`。因此同预算对比也支持跨时间对齐贡献。详见
`PRTA_GEN_R49_UNIFIED_THREE_WAY_RESULT_CN.md`；R48 本身的 pooled 状态和
confirmation STOP 均不被改写。

## 可复核证据

- pooled aggregate：
  `H:\VisualVIT_runtime\050_routeD\r37_prta_cxr\prta_gen_r48_fprr_v1\pooled_heldout\aggregate.json`
- 3,574 bytes
- SHA-256：
  `7463FDADAEEAFF7958AA76CF5A882466452151A24CCC87767F29FD85F8CFB7F6`
- patients：750，全部 patient-disjoint
- bootstrap：2,000 replicates
- active workers：0
- GPU0/GPU1：0 MiB，0% utilization
