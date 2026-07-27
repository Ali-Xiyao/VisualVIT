# R37 胸片纵向变化标签独立人工审核说明

## 1. 审核目的

本次审核只判断自动提取的胸片报告变化方向是否被所展示的报告证据支持，
不评价模型效果，也不需要运行代码或使用 GPU。

审核表共 200 条，五个类别各 40 条：

- `Stable`：目标征象没有明确变化；
- `Improved`：目标征象较前减轻；
- `Worse`：目标征象较前加重；
- `New`：目标征象为新出现；
- `Resolved`：目标征象较前消失或已解决。

通过标准已经冻结：

- 200 条必须全部审核；
- 总体方向正确率不低于 90%；
- 每个类别的方向正确率不低于 85%。

## 2. 审阅者要求

建议由熟悉英文胸片报告的放射科医生、医学影像专业人员或具备相应临床
研究经验的人员完成。审阅者应独立于本规则提取和模型实验过程。

请不要向审阅者提供：

- Codex 之前的判断或 194/200 的内部检查结果；
- A6 工程实验结果；
- 任何模型预测；
- 300-dev、483-test 或 gold 结果。

这些信息会造成判断偏倚，而且不是本次审核所需内容。

## 3. 数据与隐私边界

原始审核表位于本机：

`H:\VisualVIT_runtime\050_routeD\r37_prta_cxr\r37a_transitions_v4_1\r37_transition_case_study.csv`

该表包含派生的临床报告文本和研究标识符，必须遵守现有数据使用权限：

- 不得提交到 Git；
- 不得上传到公共网盘、个人云盘或公开协作工具；
- 不得通过未经批准的普通邮件或聊天软件发送；
- 只能在获授权的本地设备或机构批准的安全传输环境中审阅。

开始前请复制一份工作副本，并另存为：

`r37_transition_case_study_REVIEWED.csv`

不要覆盖原始 CSV。

## 4. 每一行如何判断

主要查看以下列：

- `finding`：本行要判断的目标征象；
- `label`：系统提出的变化方向；
- `sentence`：支持该方向的报告句子；
- `section`：句子所在报告段落；
- `cue`：系统识别到的变化词；
- `chexpert_consistency`：仅供参考的结构检查，不代表人工结论。

对每一行回答：

> 针对 `finding`，`sentence` 是否足以支持 `label` 所表示的纵向变化方向？

判断原则：

1. 只判断目标 `finding`，不要把邻近的其他征象变化算进来。
2. 必须有明确的时间方向。仅描述当前存在某征象，不足以证明
   `Improved`、`Worse`、`New` 或 `Resolved`。
3. `may`、`could`、`possible`、`cannot exclude` 等不确定表达，若不足以
   确认方向，应判为错误。
4. HISTORY、INDICATION、既往病史或检查目的中的描述不能当作当前影像变化。
5. 低肺容量、旋转、便携片、曝光差等技术因素不能直接当作疾病变化。
6. `no new ...` 通常不是 `New`；`unchanged`、`stable` 通常支持
   `Stable`。
7. `improved/decreased` 支持 `Improved`，`worsened/increased` 支持
   `Worse`，但必须确实修饰当前行的目标征象。
8. 如果信息不足、存在两种同样合理的解释，按错误处理，并选择
   `INSUFFICIENT_EVIDENCE`。

## 5. 只填写这三列

不要修改、删除、排序或重排其他列和行。

### `human_direction_correct`

必须填写以下两个英文值之一：

- `TRUE`：该行证据支持所给 `label`；
- `FALSE`：证据不支持、方向错误或证据不足。

不得填写中文“对/错”、数字、问号或留空。

### `human_error_category`

当 `human_direction_correct=TRUE` 时必须留空。

当 `human_direction_correct=FALSE` 时，必须填写下列一个代码：

| 代码 | 含义 |
|---|---|
| `NEGATION_SCOPE` | 否定范围被误读，例如 `no new` |
| `UNCERTAINTY` | 不确定、可能或无法排除 |
| `HISTORY_OR_INDICATION` | 来自病史、检查目的或非当前影像段落 |
| `TECHNIQUE_OR_ARTIFACT` | 技术差异或伪影被误当成病变变化 |
| `FINDING_SCOPE` | 变化词修饰的是其他征象、部位或侧别 |
| `TEMPORAL_DIRECTION` | 改善/加重、新发/消失方向判断相反 |
| `ALTERNATIVE_OR_DIFFERENTIAL` | 备选诊断或鉴别表达被误当作确定结论 |
| `INSUFFICIENT_EVIDENCE` | 句子不足以支持所给方向 |
| `OTHER` | 其他无法归入上述类型的错误 |

### `human_notes`

- `TRUE` 行可以留空；
- `FALSE` 行建议用一句话说明原因；
- 选择 `OTHER` 时必须填写具体原因。

示例：

- `TRUE, ,`
- `FALSE,NEGATION_SCOPE,"no new opacity does not support New"`
- `FALSE,FINDING_SCOPE,"increase refers to pleural effusion, not edema"`

## 6. Excel/表格软件操作

1. 打开工作副本 `r37_transition_case_study_REVIEWED.csv`。
2. 保持 UTF-8 CSV 格式。
3. 只编辑 `human_direction_correct`、`human_error_category` 和
   `human_notes`。
4. 不要使用筛选后删除行，不要重新排序，不要修改列名。
5. 保存后关闭并重新打开一次，确认中文/英文文本没有乱码，仍为 200 行。

## 7. 审阅者声明

请审阅者随审核后的 CSV 一并提供以下信息，可写在机构批准的安全消息中：

```text
Reviewer name or institutional ID:
Professional role:
Relevant experience:
Review date (YYYY-MM-DD):

I confirm that I independently reviewed all 200 rows using the information
shown in the frozen review sheet. I did not use model predictions, protected
300-dev/483-test/gold outcomes, or prior Codex judgments.
```

## 8. 返回前检查

- [ ] 文件名为 `r37_transition_case_study_REVIEWED.csv`
- [ ] 总行数仍为 200
- [ ] 所有 `human_direction_correct` 均为 `TRUE` 或 `FALSE`
- [ ] 每个 `FALSE` 行都有合法错误代码
- [ ] `TRUE` 行的错误代码为空
- [ ] `OTHER` 行填写了说明
- [ ] 未修改其他字段、列名、顺序或行数
- [ ] 已附审阅者声明
- [ ] 文件只通过获授权的本地或机构安全路径返回

审核完成后，把文件放回同一受控目录并告诉项目负责人。项目代码会先执行
格式和门槛验证；只有验证通过，才会把 `formal_training_unlocked` 改为
`true`。审核本身不会读取或解锁任何 protected outcome。
