# CAPES-CI 数据与权重获取状态

日期：2026-07-19  
原则：先完成不依赖新资产的 survival gates；restricted 数据只在现有合法授权可核验时下载，绝不绕过 credential/DUA。

## 立即结论

- **当前 S010–S070 不需要下载新模型**：服务器已有 Qwen3-VL-4B/8B，MIMIC-CXR images/reports 与 BiomedCLIP 也已存在；本地另有 Qwen2-VL 2B/7B。
- **正式真实数据 pilot 需要新标注或确认已有授权**：优先 MS-CXR-T v1.0.0 与 Chest ImaGenome v1.0.0；两者都是 PhysioNet restricted resources。
- CheXTemporal 目前只可作为条件候选。论文公开摘要确认五类 gold/silver 任务；StanfordAIMI Hugging Face 仓库存在，但当前 dataset card 缺少清楚的 YAML/license/version pin，不能把匿名镜像或未固定 main 分支直接当正式权威资产。

## 资产表

| Asset | 当前状态 | 获取/许可 | 本项目用途 | 决定 |
|---|---|---|---|---|
| Qwen3-VL-4B-Instruct | 服务器已有，约 8.3 GiB | 本地模型目录，待记录模型卡/license/hash | 首个服务器 64-token survival | 直接复用，不下载 |
| Qwen3-VL-8B-Instruct | 服务器已有，约 17 GiB | 同上 | 第二规模/VLM transfer | survival 后再启用 |
| Qwen2-VL 2B/7B | 本地已有完整分片 | 已有本地 hash；服务器无 | 本地兼容性与主模型候选 | 暂不复制大权重，先用 Qwen3-VL server gate |
| BiomedCLIP | 本地/服务器已有且既往 hash 一致 | 已有 checkpoint | v1 region encoder | 直接复用 |
| MIMIC-CXR | 本地/服务器已有 images/reports | [PhysioNet credentialed license](https://physionet.org/content/mimic-cxr/view-license/2.1.0/)；禁止共享访问，要求培训和研究用途 | parent images / train data | 只在授权归属和版本 manifest 复核后使用 |
| MS-CXR-T v1.0.0 | 未在 H 或服务器找到 | [PhysioNet project](https://physionet.org/content/ms-cxr-t/1.0.0/)；credential + CITI + project DUA；两个 CSV | 1,326 pairs、5 findings、3-class gold benchmark | **需要用户已有 PhysioNet 合法访问**；确认后可下载 |
| Chest ImaGenome v1.0.0 | 未在 H 或服务器找到 | [PhysioNet project](https://physionet.org/content/chest-imagenome/1.0.0/)；credential + CITI + project DUA | scene graphs、comparison relations、500-patient gold、bbox | **需要用户已有 PhysioNet 合法访问**；确认后可下载 |
| CheXTemporal | 未在 H 或服务器找到 | [paper](https://arxiv.org/abs/2605.11304)；[StanfordAIMI HF repo](https://huggingface.co/datasets/StanfordAIMI/chextemporal) 当前约 840 MB、main 可变且 card/license 不够清楚 | 五类 gold/silver progression 与 external coverage | 暂不下载；先等官方 version/license pin 或作者正式说明 |
| RAD-DINO | 未在服务器找到 | 公开模型权重，正式下载前固定官方 revision/license/hash | 第二 encoder transfer | S080 之后按需下载，不阻塞 survival |

## PhysioNet 合规边界

MS-CXR-T 官方页说明其文件只有 credentialed、完成 CITI 且签署 project DUA 的用户可访问；数据只有两个 CSV。Chest ImaGenome 同样需要 credential、培训与 project DUA。MIMIC/PhysioNet license 还禁止把 restricted-data access 分享给其他人。

因此，当前不能仅凭磁盘上存在 MIMIC 图片推断当前执行者也已对 MS-CXR-T/Chest ImaGenome 完成各项目授权。下载前必须做不泄露凭据的 access check；若无现成授权，需要用户完成或确认 PhysioNet 账户、CITI 与对应 DUA。

## 推荐最小正式数据路线

1. **机制 pilot**：MS-CXR-T gold image pairs 作三类方向性机制检查，同时用 Chest ImaGenome comparison/bbox 构造 persistent/null identity audit；全部 train/dev 化，不揭示预留 test。
2. **五类主终点**：只有 CheXTemporal 的正式 gold release、许可和 split 可固定后才进入；否则不能把 MS-CXR-T 三类结果冒充五类 main endpoint。
3. **外部复现**：必须从与 MIMIC/Chest ImaGenome patient/image lineage 不重叠的 parent source中冻结，不能把同一 MIMIC 衍生集换名当 external。

## 下载前清单

- official URL / DOI / exact version or commit;
- access class and license/DUA owner confirmation;
- expected file list and byte size;
- destination under server project data boundary；restricted raw data不得同步回公开代码目录；
- SHA256 and immutable source manifest;
- patient/study/image identifiers needed for cross-source dedup;
- redistribution prohibition and paper citation.

当前状态：`NO_NEW_MODEL_DOWNLOAD_NEEDED_FOR_SURVIVAL + USER_AUTH_CONFIRMATION_NEEDED_BEFORE_PHYSIONET_ANNOTATION_DOWNLOAD`。
