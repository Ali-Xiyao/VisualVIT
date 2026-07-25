# CheXTemporal 正式数据入口审计

审计日期：2026-07-19  
技术对象：CAPES-CI 真实 train/dev 与正式评测入口  
数据版本：`anonaccount107240/CheXTemporal@81fd9cdd9b1208d8f8bd39d7a914c9b72fed8d79`  
证据类别：`PUBLIC_ANNOTATION_ENTRY_AUDIT`  
正式测试：`SEALED`  

## 技术结论

公开注释包已经按固定 commit 下载并通过文件哈希核验，但它**尚不能解锁真实训练、B4 因果机制估计或正式测试**。

| 门 | 当前判定 | 依据 |
|---|---|---|
| 公开注释取得 | **PASS** | 5 个下载对象均在固定 commit 下取得；两个 parquet 与预登记 SHA256 一致；下载清单明确 `contains_images=false`、`formal_claim_allowed=false` |
| 注释结构资格 | **HOLD / current profile `FAIL_DATA_QUALITY`** | 1,787 行 pair 表满足声明行数与基础 schema，但存在 258 个同一精确影像对×finding 对应多个 progression target 的 key；bbox 文件实际 1,565 行而数据卡写 1,562 行 |
| `D010` 正式资产/许可资格 | **HOLD** | 仅注释包可核验；三类父影像未进入完整 asset ledger，访问授权、逐文件解析、哈希与许可状态尚未闭合 |
| `D020` lineage/split seal | **HOLD（继续锁定）** | 无父影像 manifest，无法完成跨源 patient/study/image/hash 去重、`images_to_avoid` 排除、patient-level split seal；bbox 也未建立可用于 B4 的跨时 persistent-entity 身份 |
| `S080` 真实 train/dev pilot | **LOCKED** | 按门顺序必须等待 `D010` 和 `D020` 均 PASS |

本审计只读取 schema、哈希、行数和聚合分布。**没有运行任何模型、生成预测、计算模型指标或用 gold 行选择方法/超参数。** 下列类别/来源计数仅用于资格与可行性审计，不构成方法开发证据。

## 1. 来源、版本与许可

- 论文入口：[CheXTemporal: A Longitudinal Chest X-Ray Dataset for Temporal Progression Understanding](https://arxiv.org/abs/2605.11304)。
- 公共发布仓库：[anonaccount107240/CheXTemporal](https://huggingface.co/datasets/anonaccount107240/CheXTemporal)。本地下载固定到 commit [`81fd9cdd9b1208d8f8bd39d7a914c9b72fed8d79`](https://huggingface.co/datasets/anonaccount107240/CheXTemporal/tree/81fd9cdd9b1208d8f8bd39d7a914c9b72fed8d79)，而不是可变的 `main`。
- 注释许可为 [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/)；要求署名、仅限非商业用途。此许可**不覆盖父影像**。
- 发布包声明自身仅含注释，父影像来自 CheXpert、MIMIC-CXR 与 ReXGradient，必须分别按上游访问协议取得；本地下载没有包含任何影像。

固定本地入口为 `data/official/chextemporal_81fd9cdd/`。`download_manifest.json` 的取得状态为 `PASS`，但该 PASS 只代表公开注释文件的取得与固定，不代表正式数据资格。

| 文件 | bytes | SHA256 | 核验状态 |
|---|---:|---|---|
| `gold_progression_pairs.parquet` | 51,915 | `22cda4e85c01c1d67d905fbba0c8a1a9169e2e5b99f754b93782b5c67dfed14b` | 下载并与预登记哈希一致 |
| `gold_bboxes.parquet` | 91,676 | `20f114c7f81a66986ed0a697d4056d2b9c4029e7df77c97217db4908726f2064` | 下载并与预登记哈希一致 |
| `LICENSE` | 2,326 | `64b72273169c3b87e317c965f9a03b14f9f2e28462326e705219c900ca18483a` | 下载并记录哈希 |
| `README.md` | 10,546 | `dddc0a9deae853c4968e15394c6a3dd33c515e4753800f9c09255eb30e0bfc38` | 下载并记录哈希 |
| `DATASHEET.md` | 7,132 | `2e04fb08f129fd442f8b51f58cecf2781cf1b0f83c0cc74443386a65d90deefc` | 下载并记录哈希 |

## 2. 实际 schema 与基数

### `gold_progression_pairs.parquet`

- 实际形状：**1,787 × 8**。
- 预期粒度：`patient × exact prior/current image pair × finding`。
- 字段：`patient_id`, `study_id_prev`, `study_id_curr`, `img_path_prev`, `img_path_curr`, `disease_name`, `progression`, `dataset`。
- 197 个 `(dataset, patient_id)` 唯一患者；原始 patient ID 没有跨来源复用记录。
- 8 个必填字段均无 null；完整 8 字段 row key 无重复；5 个 progression 值与数据卡一致。

### `gold_bboxes.parquet`

- 实际形状：**1,565 × 10**，而 README 声明 1,562 行；固定 parquet 比数据卡多 3 行，必须按 commit/hash 披露并等待发布方解释或正式规则。
- 字段为上述 8 个 pair 字段，加 `prior_bboxes` 与 `current_bboxes`。
- 1,565 个 bbox 行全部能在 pair 表找到对应完整 row key；覆盖 pair 表的 87.58%，无 orphan row、无完整 row-key 重复、必填字段无 null。
- 共 4,702 个 boxes；结构字段与非负/有序坐标的几何检查没有发现错误。由于父影像不在包中，坐标是否越过真实影像边界仍为 `NOT_EVALUABLE_WITHOUT_PARENT_IMAGES`。
- 190 个唯一患者出现在 bbox 表。

## 3. 类别、来源与 finding 分布

### 五类 progression

| 类别 | 总计 | CheXpert | MIMIC | ReXGradient |
|---|---:|---:|---:|---:|
| Stable | 654 | 391 | 218 | 45 |
| Worse | 440 | 260 | 146 | 34 |
| Improved | 424 | 250 | 147 | 27 |
| New | 154 | 105 | 39 | 10 |
| Resolved | 115 | 68 | 44 | 3 |
| **总计** | **1,787** | **1,074** | **594** | **119** |

### Finding

| Finding | 行数 | Finding | 行数 |
|---|---:|---|---:|
| pleural effusion | 455 | lung opacity | 453 |
| edema | 222 | atelectasis | 200 |
| cardiomegaly | 133 | consolidation | 104 |
| pneumothorax | 67 | pneumonia | 63 |
| lung lesion | 34 | enlarged cardiomediastinum | 32 |
| pleural other | 24 |  |  |

这些分布表揭示明显的类与来源不平衡，后续若数据通过资格门，应使用 patient-balanced 指标、按来源/类别分层报告和 patient-cluster uncertainty；但当前不得据此搜索方法、阈值或 seed。

## 4. 阻止正式使用的实质问题

### 4.1 progression target 不是唯一值

当前 profile 对 `(dataset, patient_id, study_id_prev, study_id_curr, disease_name)` 分组后发现 **258 个 key 含多个 progression 值**。复核把 `img_path_prev` 和 `img_path_curr` 也纳入 key 后，冲突仍为 258 个，因此这不是由同一 study 的多视图被错误合并造成的假冲突。共有 **548 行**落在这些冲突组；组大小为 2–4 行。

发布 schema 没有 annotator ID、重复标注轮次、共识或裁决字段。因此，现阶段不能判断这些行是合法的多标注者原始记录、未裁决分歧，还是发布重复/错误；更不能在观察结果后自行做多数票、挑选标签或删行。只有发布方说明或**预先签名、与模型结果无关**的确定性裁决/排除规则，才能形成单一 target cohort。

### 4.2 bbox 不能自动充当 persistent-entity oracle

- `Box1`/`Box2` 等标签在数据卡中只作为单侧标注标签出现，没有文档证明它们是跨时间持续实体或病灶 ID。
- 以朴素五类语义检查侧占用时，22 个 persistent 行不是双侧均有框，68 个 `New` 行不满足“prior 空、current 非空”，73 个 `Resolved` 行不满足“prior 非空、current 空”。这 **163 行**并不单独证明数据损坏，但证明“progression 类别 + 两侧 bbox”不能未经规则验证就等同于 CAPES-CI 的 persistent/birth/death 身份 oracle。
- 仅作候选上界，558 个 bbox 行同时属于 persistent 三类、两侧各至少两个框且至少共享两个单侧 box label；在确认 box label 跨时语义以前，这个计数不能称为 B4-eligible 样本。
- 同一侧共记录到 37 个重复 box-label occurrence，也需要结合发布规范或原图审计后再解释。

### 4.3 注释包与父影像分离

没有父影像时，无法验证路径解析、像素哈希、图像尺寸、坐标边界、patient/study/image lineage、跨源重复、`images_to_avoid`，也无法生成合规的冻结视觉特征。因此当前注释 profile 的结构通过项不能外推为真实端到端数据通过。

## 5. 资格边界

当前允许：

- 固定公共注释 commit、文件哈希和许可文本；
- 进行 schema、null、重复、类别/来源基数与 bbox 几何的聚合资格审计；
- 设计 asset ledger、split seal、去重和 power 方案；
- 在不读取 row-level gold outcome 作决策的前提下判断样本支持是否可能满足后续门槛。

当前禁止：

- 使用 gold progression 或 bbox 行调方法、调超参数、筛 seed、选择 checkpoint 或做 rescue；
- 把 1,787 行 gold 当作 train/dev 而不先签署 patient-level 封存方案；
- 把 box label、同 anatomy 或共享 bbox label 称为 persistent lesion/entity identity；
- 在缺少父影像授权、manifest 与 lineage 审计时运行真实图像实验；
- 报告 B4 gap、learned recovery、正式消融、主实验或任何 confirmatory 结果。

## 6. Gold 测试封存原则

数据卡把 1,787 行 gold 明确定义为 held-out evaluation。当前资格脚本已经读取其结构和聚合标签计数，但**没有**读取模型预测或执行评测。为避免后续方法开发污染正式测试，执行规则应为：

1. 优先把完整 gold cohort 作为最终一次性评测；方法开发与 power-development 使用合法取得的 silver/train 来源、独立标注 cohort 或其他预先声明的数据，且不得用 gold 反馈修改方法。
2. 如果样本条件迫使项目从 gold 中建立 `method_dev`、`power_dev` 和 `formal_test`，必须在任何模型运行前按规范化 `(source, patient_id)` 做确定性 hash 分配；分配规则、salt、患者清单、行清单和每个 split 的 manifest SHA256 一次性冻结。
3. split 必须 patient-disjoint，并在所有 CheXTemporal、MIMIC-CXR、Chest ImaGenome、MS-CXR-T 及其他 MIMIC 派生面之间对 patient/study/image ID 与内容哈希做交叉去重。数据集名称不同不能作为独立性的证据。
4. 封存分配不得根据类别计数、单行标签、bbox 可用性或模型结果反复重采样。若预先签名的支持门失败，应 fail closed，而不是重切 test。
5. `formal_test` 的 row-level outcome、预测和指标在代码、方法、seed、最小效应、统计方案、排除规则与 checkpoint policy 签名以前保持不可读；解封后只运行一次。任何基础设施重跑必须保持完全相同输入并留存失败尝试。
6. 当前 profile 及本报告只能作为资格审计证据；不得作为正式测试性能或方法选择依据。

## 7. 父影像访问依赖

| 来源 | 注释内行数 | 父影像许可/访问边界 | 当前缺口 |
|---|---:|---|---|
| CheXpert | 1,074 | [Stanford CheXpert Data Use Agreement](https://stanfordmlgroup.github.io/competitions/chexpert/) | 需确认用户授权状态；解析 100% 引用路径；建立 image SHA256 与 patient/study lineage |
| MIMIC-CXR | 594 | [PhysioNet MIMIC-CXR](https://physionet.org/content/mimic-cxr/) credentialed access、CITI 与数据使用协议 | 需确认当前 credential/CITI/project access 状态；不得记录或索取密码/token；需与所有 MIMIC 派生集交叉去重 |
| ReXGradient | 119 | CheXTemporal LICENSE 指定遵循作者发布条款并联系维护者 | 正式分发入口、授权/DUA 状态、文件版本和 lineage 尚未闭合 |

只需要记录“已授权/未授权/待确认”及协议引用，不应把凭据、cookie、token 或密码写入仓库。没有新增模型权重是通过本数据入口审计的前置条件；当前缺的是合规父影像与身份/划分证据。

## 8. `D010` / `D020` 解锁条件

### `D010`：保持 `HOLD`

要转为 PASS，至少需要：

- 三个父来源的许可、访问类别、用户授权状态、允许用途与再分发边界写入完整 asset ledger；
- gold 表引用的所有必需 prior/current 影像 100% 解析，缺失为零，文件 SHA256 与尺寸可复核；
- 注释、父影像版本和路径映射固定，任何 `images_to_avoid` 入口可定位；
- 1,562/1,565 bbox 行数漂移形成书面版本说明；
- 258 个冲突 target key 获得发布方语义说明以及预先签名的确定性保留/裁决/排除规则。未解决前不得生成训练 target。

### `D020`：保持 `HOLD / LOCKED`

即使 `D010` 通过，仍需独立完成：

- patient-level `train/method_dev/power_dev/formal_test/external_test` seal；
- 跨来源 patient/study/image ID 与内容 hash 零重叠，零 `images_to_avoid`；
- 五类 target 在 primary entity unit 上非空；
- gold persistent link 的官方字段或签名确定性规则，且 learned path 不接触 fine identity/gold cardinality；
- train、method-dev、power-dev 中均有非空、可做 anatomy-compatible zero-fixed-point derangement 的 B4-eligible cohort；
- 记录每一类非 derangeable 排除原因与计数；
- 生成并签署 sealed formal-test manifest SHA256。

若合法 cohort 中“五类 progression target”与“非平凡 persistent endpoint identity”不能同时成立，则 CAPES-CI confirmatory 主张不具备可识别性；三类 image-level benchmark 只能作为 secondary evidence，不能替代该主终点。

## 9. 可复核证据

- 下载与固定清单：`data/official/chextemporal_81fd9cdd/download_manifest.json`
- 本地许可与发布说明：`data/official/chextemporal_81fd9cdd/LICENSE`、`README.md`、`DATASHEET.md`
- 当前聚合 profile：`reports/data_quality/chextemporal_81fd9cdd_profile.json`
- 资格门定义：`docs/superpowers/specs/2026-07-19-capes-ci-real-pilot-data-contract.md`

最终判定：**公开注释入口可复现；D010 HOLD；D020 HOLD/LOCKED；formal test 保持 SEALED；真实 main/ablation 不得启动。**
