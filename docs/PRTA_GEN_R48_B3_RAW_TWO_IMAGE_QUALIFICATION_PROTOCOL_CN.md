# R48-B3 Raw Two-Image Frozen Qwen3-VL Baseline

本阶段实现 R40 已预声明但尚未正式执行的强基线 B3：

> Qwen3-VL 直接按 `[prior 完整胸片, current 完整胸片]` 顺序读取两张原生
> JPEG；不经过 BiomedCLIP、projector、64-token 压缩、router 或训练。

为避免消耗仍封存的 250 人 confirmation，本次先在已经揭示的 R48
qualification 500 人上做 development case study。它与 R48 FPRR true-pair
使用完全相同的患者、finding、五分类 target 和 JSON 输出格式，因此可以做
paired comparison，但不能叫独立确认。

固定设置：

- 本地 Qwen3-VL-4B-Instruct，BF16，完全冻结，offline；
- prior 在前、current 在后，每张均使用完整视野，不裁 ROI；
- processor `min_pixels=200704`、`max_pixels=802816`；
- greedy generation，最多 64 个新 token；
- 两个确定性互斥 shard：偶数 roster row 在 GPU0，奇数 row 在 GPU1；
- prompt、图像顺序、解析器与所有模型/roster/result 哈希在运行前冻结；
- 不因 smoke 或中间 shard 输出修改 prompt、像素预算或 parser。

报告 macro-F1、五类 recall、schema/finding accuracy、invalid count、总生成
时间、峰值显存与相对 FPRR true-pair 的 patient-bootstrap 差值。此基线没有
事后 GO 阈值；结果无论正负均完整报告。
