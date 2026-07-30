# PRTA-Gen R40C 结构化头内部泛化冻结协议

## 研究问题

R40B.4 已证明 499,973 参数的结构化 progression head 可以在 32 名患者上
完成工程 overfit，但没有证明未见患者上的有效性。R40C 只回答：

> 冻结的 semantic-layout structured head 能否在 patient-disjoint
> development 患者上保留 progression 分类能力，并优于 query-only 与
> prior-shuffle 控制？

R40C 使用已经参与方法开发的 R40A.2 fit partition，因此即使 PASS，也只能
称为 **internal development generalization**，不能称独立科学确认、gold
泛化、外部泛化或临床验证。

## 不可撤销边界

- R40B、R40B.1、R40B.2、R40B.3、R40B.4 的五批 32-patient cohort
  共 160 名患者全部排除；
- protected 300-dev、revealed 483-test、gold、external 全部不读；
- Qwen free generation、laterality、anatomy、degree、evidence 与
  R41–R43 保持锁定；
- 不允许根据 development 结果改变 split、head 宽度、学习率、epoch、
  batch、Seed、control 或 gate；
- 不早停、不选择 checkpoint，不在失败后重划患者。

## 冻结 roster

只从 R40A.2 fit partition 选择：

| Partition | Stable | Improved | Worse | New | Resolved | 总患者 |
|---|---:|---:|---:|---:|---:|---:|
| train | 200 | 200 | 200 | 200 | 200 | 1,000 |
| development | 100 | 100 | 100 | 100 | 100 | 500 |

每名患者只保留一行。为保证稀缺类别支持，按
Resolved、New、Improved、Worse、Stable 顺序分配；每类先用独立 namespace
的稳定 SHA-256 顺序选择 development，再选择 training。两个 partition、
五个旧 cohort 与未选择患者均严格分离，禁止 resplit。

## 模型与四个控制臂

四个 arm 每个 Seed 都 fresh 初始化同一个 499,973 参数 head：

1. `true_pair`：真实 prior/current exact64 semantic-layout means；
2. `current_only`：current/current token；
3. `prior_shuffle`：跨患者同 finding 的 shuffled-prior token；
4. `query_only`：12 类 finding one-hot，零填充到相同 3,840 输入宽度。

每个 arm 只用自己的 training features 拟合 mean/std，并原样应用到
development。禁止用 development 统计量标准化。query-only 与其他 arm
拥有相同 head 参数量，避免容量差异。

固定训练为 AdamW、learning rate 0.001、weight decay 0、batch 128、
100 epochs、每 arm 800 updates、gradient clip 1.0。Seeds 为 17、29、43。

## 指标与一次性门

每个 Seed 必须同时满足：

- true-pair development macro-F1 >= 0.30；
- 五个 progression 类别 recall 均 >= 0.15；
- true-pair 相对 query-only 与 prior-shuffle 均 >= +2 pp；
- 上述两项 patient-cluster bootstrap 95% CI 下界均严格大于 0；
- 两字段 JSON schema validity = 100%；
- finding echo = 100%。

bootstrap 固定为 2,000 次，seed 40001。current-only 是注册描述性控制；
true-head 输入 current/shuffle 的 counterfactual 结果也只能描述，不能代替
主比较。

## 终态解释

```text
GO_PRTA_GEN_R40C_INTERNAL_GENERALIZATION
```

只表示内部 development 泛化门通过，可以另行规划独立确认；不解锁 Qwen
SFT 或科学主张。

```text
STOP_PRTA_GEN_R40C_INTERNAL_GENERALIZATION
```

表示 R40B.4 继续只保留为 engineering smoke。停止后不得在同一 development
上调参或重划 roster。

## 当前执行授权

本轮只允许完成配置、协议、roster builder、runner、aggregator、测试和
CPU/dry-run preflight，并将 pre-outcome authority 提交推送。正式 roster
写入与任何 GPU 训练必须在下一次明确确认后进行。
