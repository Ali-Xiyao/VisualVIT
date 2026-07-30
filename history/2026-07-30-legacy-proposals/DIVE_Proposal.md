# DIVE: Divided Intra-inter Visual Encoding for Multi-Image VLMs（历史提案）

> **归档状态：** 本文档保留为方法谱系，不是当前 TIER-CXR-VLM
> 实验或主张的授权入口。

> **一句话**：当前多图 VLM 把所有跨图推理都甩给 LLM 的 self-attention，但 LLM 在深层会发生跨图注意力坍塌。DIVE 在视觉侧预计算跨图关系，分离"对应"与"差异"信息，让 LLM 收到的是已经结构化的跨图 token。

---

## 1. Problem

当前所有主流多图 VLM（LLaVA-NeXT, InternVL, Qwen2-VL, Mantis 等）处理多张图片的方式完全相同：

```
 图1 → ViT → patch tokens₁ ─┐
   图2 → ViT → patch tokens₂ ─┤→ 拼接 → LLM self-attention → 输出
图N → ViT → patch tokens_N ─┘
```

**每张图独立编码，拼接后全靠 LLM 的 self-attention 发现跨图关系。**

这个范式有三个已被论文证实的结构性缺陷：

| 缺陷 | 证据 | 来源 |
|------|------|------|
| **跨图注意力坍塌**：LLM 在深层逐渐退化为图内注意力 | 浅层有跨图关联，深层 >80% 注意力转向图内 | ACL Anthology 分析论文 |
| **注意力沉没**：无信息量 patch 持续吸引注意力 | 背景 token 浪费注意力预算 | ICLR 2025 (Kang et al.) |
| **跨图信息泄漏**：图间分隔符无法隔离信息 | delimiter token 失效，不随 LLM 增大改善 | ICLR 2026 (Lee et al.) |

**后果**：在需要跨图感知的 benchmark 上，最强 VLM 与人类差距巨大：
- **BLINK**（ECCV 2024）：人类 95.7% vs GPT-4V 45-51%（视觉对应、空间关系等）
- **MuirBench**：开源多图模型 <33.3%（低于四选一随机）
- **MMIU**：空间/时序关系类任务系统性失败

---

## 2. Core Hypothesis

> **跨图视觉关系应该在视觉编码阶段被显式计算，而不是留给 LLM 从拼接的 token 中隐式推断。**

类比已有成功案例：

| 领域 | "拼接后让下游自己推断" | "视觉侧预计算" | 哪个赢？ |
|------|----------------------|----------------|---------|
| **视频理解** | 拼接帧 token → LLM | TimeSformer 分解式时空注意力 | ✅ 预计算 |
| **立体视觉** | 拼接左右图 → 网络 | Cost volume 显式匹配 | ✅ 预计算 |
| **双眼视觉** | "拼接"两眼信号 → 高级认知 | V1/V2 皮层早期融合 | ✅ 预计算（生物） |

**DIVE 的核心洞察**：跨图 token 包含两类信息——

1. **对应信息 (Correspondence)**：图间共享的内容（同一物体、同一背景、同一结构）→ **冗余，应压缩**
2. **差异信息 (Difference)**：图间不同的内容（变化、新增、缺失）→ **关键，应放大**

当前范式把这两类信息混在一起全部丢给 LLM，迫使 LLM 同时做"找对应"和"判差异"两件事。DIVE 把第一件事在视觉侧完成，让 LLM 只专注第二件事。

---

## 3. Why Now

1. **问题刚被量化**：BLINK（ECCV 2024）、MMIU、MuirBench 等 benchmark 在 2024 年密集出现，首次系统性量化了多图 VLM 的失败程度
2. **注意力坍塌刚被发现**：跨图注意力在深层退化的分析论文是 2024-2025 年的新发现
3. **Scaling 不修复的证据刚出现**：ICLR 2026 论文证明分隔符失效不随 LLM 增大改善
4. **竞争窗口开放**：唯一接近的工作是 SQuARE/PRIMA（仅限分割任务），通用多图推理的视觉侧编码**无人做过**
5. **架构组件成熟**：cross-attention、slot attention、Perceiver 等都有成熟实现，不需要从头发明

---

## 4. Method

### 4.1 整体架构

```
图1 → Frozen ViT → V₁ (P tokens) ─┐
图2 → Frozen ViT → V₂ (P tokens) ─┤
...                                 ├→ [ DIVE Module ] → M cross-image tokens → Projector → Frozen LLM
图N → Frozen ViT → V_N (P tokens) ─┘
                                         ↑
                                    唯一训练部分
                                    (轻量, <2% total params)
```

**设计原则**：
- ViT 和 LLM 全部冻结，**只训 DIVE 模块 + projector**
- 输出固定数量 M 个 token（M << N×P），与图数无关
- 可即插即用到任意现有 VLM

### 4.2 DIVE 模块：三阶段流水线

#### Stage 1: Intra-Image Compression（图内压缩）

每张图独立处理，用 K 个 learnable queries 做 cross-attention 压缩：

$$Z_i = \text{CrossAttn}(Q_{intra}, V_i) \quad \in \mathbb{R}^{K \times d}, \quad i = 1, ..., N$$

- $Q_{intra} \in \mathbb{R}^{K \times d}$：共享的可学习 queries（K << P）
- 作用：把 P 个 patch tokens 压缩到 K 个语义 token
- **关键**：所有图共享同一组 queries → 输出在同一语义空间，方便后续比较

#### Stage 2: Inter-Image Fusion（跨图融合）⭐ 核心创新

将 N 组压缩 token 放在一起，运行 L 层**分解式注意力**（inspired by TimeSformer）：

```
每层包含:
(a) Intra-Image Self-Attention:  Z_i ← SelfAttn(Z_i)          // 图内精炼
(b) Inter-Image Cross-Attention: Z_i ← CrossAttn(Z_i, Z_{≠i})  // 跨图交换
```

其中 (b) 的具体实现：

$$Z_i' = Z_i + \text{MHA}(Q = Z_i, \; K = \text{Concat}(Z_1, ..., Z_{i-1}, Z_{i+1}, ..., Z_N), \; V = \text{same})$$

- **分解式设计**：不是把所有 token 混在一起做 self-attention（那和 LLM 没区别），而是**显式分离图内 vs 跨图的注意力通道**
- **为什么这比 LLM 自己做更好**：
  1. 双向注意力（LLM 是 causal 的，跨图注意力受因果掩码限制）
  2. 专用的跨图注意力头（LLM 的注意力头需要同时服务语言和视觉）
  3. 在压缩后的 K 个 token 上操作（LLM 在 P 个原始 patch 上操作）

#### Stage 3: Correspondence-Difference Decomposition（对应-差异分解）⭐ 关键创新

经过 Stage 2 后，每张图的 token 已经包含了跨图上下文。现在做信息分解：

**Step 3a: 对应矩阵计算**

$$S_{ij} = \text{softmax}\left(\frac{\hat{Z}_i \hat{Z}_j^T}{\sqrt{d}}\right) \quad \in \mathbb{R}^{K \times K}$$

**Step 3b: 对应 token 生成（压缩共享信息）**

对高相似度的 token 对，生成对应摘要：

$$c_k^{(ij)} = \text{MLP}\left(\left[\hat{z}_i^{a_k}; \; \hat{z}_j^{b_k}; \; \hat{z}_i^{a_k} - \hat{z}_j^{b_k}\right]\right)$$

其中 $(a_k, b_k)$ 是 $S_{ij}$ 中 top-C 个匹配对。每个对应 token 同时编码"是什么"和"有多大差异"。

**Step 3c: 差异 token 提取（保留独有信息）**

未被高置信度匹配的 token 保留为差异 token：

$$D_i = \{\hat{z}_i^k \mid \max_j S_{ij}[k, :] < \tau\}$$

**Step 3d: 最终输出**

$$\text{DIVE}(V_1, ..., V_N) = \text{Concat}(C_{1,2}, ..., C_{i,j}, ..., D_1, ..., D_N, g)$$

其中 $g$ 是全局摘要 token（所有图的均值池化），总共 M 个 token。

### 4.3 Token 预算分析

| 方法 | 2 张图 | 5 张图 | 10 张图 |
|------|--------|--------|---------|
| 拼接（LLaVA 风格，P=576） | 1152 | 2880 | 5760 |
| **DIVE**（K=32, C=16, M 自适应） | ~80 | ~120 | ~160 |
| LLM self-attention 成本比 | 1× | 6.25× | 25× |
| **DIVE 成本比** | 1× | ~1.5× | ~2× |

> DIVE 的输出 token 数随图数**亚线性增长**（对应 token 被压缩），而拼接方案是**线性增长**。对 LLM 来说，self-attention 成本从 O(N²P²) 降到 O(M²)。

---

## 5. Key Novelty

| 层次 | 贡献 |
|------|------|
| **发现级** | 系统性量化 LLM 中跨图注意力坍塌现象（可独立发表的 finding） |
| **原理级** | 提出"对应-差异分解"原则：跨图信息应在视觉侧被结构化为对应（压缩）和差异（保留）两类 |
| **架构级** | 分解式图内-跨图注意力 + 可微对应-差异分解模块 |
| **系统级** | 即插即用、ViT/LLM 全冻结、token 数亚线性增长 |

---

## 6. Difference from Closest Prior Work

| 工作 | 它做了什么 | DIVE 的差异 |
|------|-----------|-----------|
| **SQuARE/PRIMA** | Learnable queries 跨图 cross-attend，用于分割 | DIVE: (1) 通用推理不限分割 (2) 有对应-差异分解（SQuARE 无） (3) 在 LLM 前而非 SAM 前 |
| **CrossLMM** | LLM 内部 V2V cross-attention | DIVE: 在视觉侧预计算（避免 LLM 层内注意力坍塌） |
| **Slot-VLM** | 视频帧的 slot attention | DIVE: (1) 任意多图不限视频 (2) 有显式对应-差异分解 |
| **Flamingo/Perceiver** | 固定 latent 瓶颈压缩 | DIVE: (1) 有跨图交互（Flamingo 无） (2) 有结构化分解 |
| **TimeSformer** | 分解式时空注意力 | DIVE: 将分解式注意力从视频帧推广到任意多图；增加对应-差异分解 |
| **Token 压缩（FastV/PruMerge）** | 图内 token 剪枝 | DIVE: 跨图冗余压缩（图内压缩正交可叠加） |

---

## 7. Experiments

### 7.1 设计哲学

实验不是"证明 DIVE 更好"，而是回答一系列因果问题：

| 实验 | 回答的问题 |
|------|-----------|
| 注意力坍塌分析 | 跨图注意力真的在深层坍塌了吗？（发现的验证） |
| 主实验 | DIVE 在多个多图 benchmark 上是否显著优于拼接？ |
| 跨架构泛化 | DIVE 能否即插即用到不同 VLM（LLaVA, InternVL, Qwen2-VL）？ |
| 消融实验 | 每个模块（跨图注意力、对应-差异分解）各贡献多少？ |
| 效率分析 | Token 压缩带来的实际 FLOPs/延迟改善？ |
| Scaling 行为 | 图数增加时，DIVE vs 拼接的性能衰减曲线？ |

### 7.2 Benchmarks

| Benchmark | 任务类型 | 图数 | 为什么选 |
|-----------|---------|:---:|---------|
| **BLINK** (ECCV 2024) | 视觉对应、相对深度、空间关系、拼图等 14 类 | 2-4 | **人类 95.7% vs GPT-4V 45%**，最大 gap 来自跨图感知 |
| **MMIU** | 52 个多图任务，7 类图间关系 | 2-8 | 最全面的多图理解 benchmark |
| **MuirBench** | 12 类任务 + "不可回答"变体 | 2-4 | 有 unanswerable 设计，能检测假推理 |
| **Q-Bench+** | 跨图质量比较 | 2 | 细粒度属性比较 |
| **Mantis-Eval** | 共指、比较、时序、推理 4 类 | 2-5 | 多图指令跟随 |
| **Spot-the-Diff** (CLEVR-Change / Image-Edit-Bench) | 差异检测与描述 | 2 | 直接测试"对应-差异"能力 |

### 7.3 Base VLMs（即插即用验证）

| Base VLM | 参数量 | 视觉编码器 | 为什么选 |
|----------|--------|-----------|---------|
| **LLaVA-NeXT-7B** | 7B | SigLIP-400M | 最广泛使用，社区标杆 |
| **InternVL2-8B** | 8B | InternViT-300M | 强多图能力，中国社区主流 |
| **Qwen2-VL-7B** | 7B | ViT + M-RoPE | 有 M-RoPE 位置编码，测试 DIVE 是否在有位置信号时仍有增益 |

每个 base VLM 跑两个版本：
- **Baseline**：原始多图处理（拼接 token）
- **+ DIVE**：插入 DIVE 模块，冻结 ViT/LLM，只训 DIVE + projector

---

## 8. Baselines

### 8.1 主对照

| # | 方法 | 描述 | 隔离变量 |
|---|------|------|---------|
| B0 | **Single-image** | 只看一张图 | 下界，多图信息的价值 |
| B1 | **Concat (标准)** | 独立编码 + 拼接 | 主对照（当前范式） |
| B2 | **Concat + 更多 token** | 拼接但不压缩（给 LLM 更多 token） | 排除 "DIVE 赢是因为 token 多" |
| B3 | **Concat + 等量 token** | 拼接后随机/均匀下采样到与 DIVE 等量 token | 排除 "DIVE 赢是因为压缩本身好" |
| B4 | **Q-Former 独立压缩** | 每图独立用 Q-Former 压缩，再拼接 | 有图内压缩但**无跨图交互** |
| B5 | **Perceiver 联合压缩** | 所有图 patch token 拼接后用 Perceiver 压缩 | 有压缩但**无分解式注意力、无对应-差异分解** |
| B6 | **Self-attention 联合** | 所有图 token 拼接后做 self-attention（不分解） | 有跨图交互但**不区分图内/跨图注意力** |

### 8.2 关键对照解读

| 对比 | 如果 DIVE 赢 | 证明了什么 |
|------|-------------|-----------|
| DIVE vs B1 | 视觉侧预编码 > LLM 隐式推断 | 核心 claim |
| DIVE vs B4 | 跨图交互 > 独立压缩 | 跨图注意力是活性成分 |
| DIVE vs B5 | 分解式注意力 + 对应-差异 > 简单 Perceiver 压缩 | 结构化分解是活性成分 |
| DIVE vs B6 | 分解式注意力 > 不分解的 self-attention | "divided" 设计的价值 |
| DIVE vs B2/B3 | 不是 token 数的问题 | 排除混淆因素 |

---

## 9. Ablations

### 9.1 模块消融

| 变体 | Stage 1 | Stage 2 | Stage 3 | 测试 |
|------|:-------:|:-------:|:-------:|------|
| **DIVE-full** | ✅ | ✅ | ✅ | 完整方法 |
| **w/o Inter-Attn** | ✅ | ❌ (只有 intra) | ✅ | 跨图注意力的贡献 |
| **w/o CD-Decomp** | ✅ | ✅ | ❌ (直接拼接输出) | 对应-差异分解的贡献 |
| **w/o Intra-Compress** | ❌ (直接用 patch) | ✅ | ✅ | 图内压缩的贡献 |
| **Only Inter-Attn** | ❌ | ✅ (on raw patches) | ❌ | 纯跨图注意力够不够 |

### 9.2 超参数消融

| 超参数 | 扫描范围 | 关键问题 |
|--------|---------|---------|
| K（图内压缩 query 数） | 8, 16, 32, 64 | 压缩到多少 token 是最优平衡？ |
| L（跨图注意力层数） | 1, 2, 4, 6 | 几层跨图注意力就够了？ |
| C（对应 token 数） | 4, 8, 16, 32 | 多少对应 token 能充分编码共享信息？ |
| τ（差异阈值） | 0.3, 0.5, 0.7, 0.9 | 多低的相似度才算"差异"？ |

### 9.3 诊断实验

| 实验 | 目的 |
|------|------|
| **注意力可视化**：可视化 Stage 2 的 cross-attention 热图 | 验证模块确实在发现有意义的跨图对应 |
| **对应-差异质量**：在有 GT 对应标注的数据上评估匹配准确率 | 验证 Stage 3 的分解质量 |
| **LLM 层内注意力对比**：有/无 DIVE 时 LLM 深层的跨图注意力比例 | 验证 DIVE 是否缓解了注意力坍塌 |
| **N 图 scaling 曲线**：N = 2, 3, 5, 8, 10 时的性能曲线 | DIVE 的 token 亚线性增长优势在多图时放大 |

---

## 10. Failure Modes

| 失败模式 | 触发条件 | 后果 | 缓解策略 |
|---------|---------|------|---------|
| **对应误匹配** | 多图中有视觉相似但语义不同的区域 | 对应 token 编码了错误的绑定 | Stage 2 的跨图注意力应学到语义区分；消融中测试 |
| **过度压缩** | K 太小或 C 太大 | 丢失关键差异信息 | 超参数消融 + 差异 token 保底 |
| **无关图集** | 多图之间完全无关（如 VQA 中的上下文图） | 跨图注意力浪费计算 | 差异阈值 τ 会让大部分 token 保留为差异 token，退化为独立编码 |
| **训练不稳定** | 对应-差异分解中的 top-C 选择不可微 | 梯度无法回传 | 用 Sinkhorn soft matching 替代 hard top-C |
| **小 VLM 上 overhead 占比高** | DIVE 模块在 1-2B VLM 上占比 >5% | 效率优势被模块开销抵消 | 报告含 DIVE 模块的端到端 FLOPs |

---

## 11. Reviewer Objections & Rebuttal Strategy

### Objection 1: "LLM 够大就能自己做跨图推理了，不需要额外模块"

**预期概率**：极高（几乎必问）

**Rebuttal**：
1. **直接证据**：Lee et al. (ICLR 2026) 证明跨图信息泄漏**不随 LLM 增大改善**——这是结构性问题
2. **类比论据**：立体视觉领域早已证明，显式 cost volume **数据效率和精度**都优于端到端隐式学习，即使在大模型时代依然成立
3. **效率论据**：即使大 LLM 能做到，它也是以 O(N²P²) 的代价做的。DIVE 在视觉侧以远更低的代价预计算，让 LLM 接收 O(M²) 的 token —— 是"更好的分工"而非"不得已的替代"
4. **实验佐证**：Scaling 消融——在 7B 和 70B LLM 上都加 DIVE，看增益是否在大模型上消失。**如果不消失**，说明即使大模型也受益于更好的视觉输入

### Objection 2: "这和 Q-Former / Perceiver 有什么本质区别？"

**预期概率**：高

**Rebuttal**：
1. Q-Former/Perceiver 是**图内压缩**——每张图独立处理，无跨图交互
2. DIVE 的 Stage 2（分解式跨图注意力）和 Stage 3（对应-差异分解）在 Q-Former 中**完全不存在**
3. **消融实验 B4 vs DIVE** 直接证明：Q-Former 独立压缩 + 拼接 < DIVE
4. 即使把 Perceiver 扩展为联合处理所有图（B5），它也**没有分解式注意力和结构化分解**

### Objection 3: "和 SQuARE/PRIMA 有什么区别？"

**预期概率**：中高

**Rebuttal**：
1. **任务范围**：SQuARE 专为分割设计（输出 mask token → SAM decoder），DIVE 输出通用 token → 任意 LLM，适用于 QA/比较/推理等所有多图任务
2. **架构位置**：SQuARE 在 SAM decoder 前，DIVE 在 LLM 前——两者服务的下游模块不同
3. **结构化分解**：SQuARE 的 relational queries 是通用的，不区分对应 vs 差异。DIVE 显式分解这两类信息
4. **实验**：在通用多图 benchmark（BLINK, MMIU）上比较，SQuARE 未在这些 benchmark 上验证

### Objection 4: "跨图注意力的计算开销不值得"

**预期概率**：中

**Rebuttal**：
1. DIVE 在**压缩后的 K 个 token** 上做跨图注意力（K=32），不是在原始 P 个 patch（P=576）上
2. 模块参数量 < 总量的 2%，FLOPs 增量远小于 LLM 侧节省的 O(N²P²) → O(M²)
3. 端到端延迟实测（必须报告）

### Objection 5: "对应-差异分解的质量无法保证"

**预期概率**：中

**Rebuttal**：
1. **可视化**：展示 cross-attention 热图，证明模块发现了有意义的对应
2. **定量评估**：在有 GT 对应标注的数据上（如 BLINK visual correspondence 子集）测试匹配准确率
3. **退化安全**：即使对应检测失败，DIVE 退化为"所有 token 都是差异 token" ≈ Q-Former 独立压缩，不会比 baseline 更差

### Objection 6: "只在 2 图场景有用，多图不行"

**预期概率**：中低

**Rebuttal**：
1. **N 图 scaling 曲线**：测试 N=2,3,5,8,10，展示 DIVE 的亚线性 token 增长优势
2. **多图 benchmark**：MMIU 包含 2-8 图的任务
3. **架构设计**：Stage 2 的 cross-attention 天然支持 N>2（每图 attend 所有其他图）

---

## 12. Training Strategy

### 12.1 数据

| 阶段 | 数据 | 规模 | 目的 |
|------|------|------|------|
| **Pre-train** | LLaVA-NeXT-Interleave 多图数据 + Mantis-Instruct | ~700K 多图样本 | 学习跨图注意力和对应-差异分解 |
| **Fine-tune** | 各 benchmark 的训练集（如有） | 视 benchmark 而定 | 任务适配 |

### 12.2 训练策略

- **冻结**：ViT encoder + LLM backbone（全部冻结）
- **可训练**：DIVE 模块（Stage 1 queries, Stage 2 attention layers, Stage 3 MLP + matching）+ projector
- **可选 LoRA**：LLM 上加轻量 LoRA 做任务适配
- **损失**：标准的下一 token 预测损失（与 base VLM 一致），无额外辅助损失
- **可选辅助损失**：对应匹配损失（如有 GT 对应标注）→ 仅在消融中测试

### 12.3 计算预算

| 组件 | 估算 |
|------|------|
| DIVE 模块参数量 | ~50-100M（Stage 1: ~10M, Stage 2: ~30-60M, Stage 3: ~10-30M） |
| 训练 GPU 时 | ~200-500 A100 GPU-hours（700K 样本，batch=128） |
| 推理 overhead | DIVE 模块 <5% 端到端延迟（在压缩 token 上操作） |

---

## 13. Final Top-Conference Positioning

### CVPR Oral 定位

| 维度 | 评估 | 说明 |
|------|:---:|------|
| **问题重要性** | ⭐⭐⭐⭐⭐ | 多图 VLM 是 2024-2025 最热方向之一，BLINK 50% gap 是公认难题 |
| **发现新颖性** | ⭐⭐⭐⭐ | 跨图注意力坍塌的定量分析是新发现 |
| **方法新颖性** | ⭐⭐⭐⭐ | 分解式注意力 + 对应-差异分解是新原则 |
| **通用性** | ⭐⭐⭐⭐⭐ | 即插即用、多 VLM 架构、多 benchmark |
| **故事完整性** | ⭐⭐⭐⭐⭐ | 发现（坍塌）→ 原理（分解）→ 方法（DIVE）→ 验证（6+ benchmarks） |
| **实验量** | ⭐⭐⭐⭐ | 3 个 base VLM × 6 个 benchmark + 完整消融 |

### 投稿策略

| 目标 | 定位 | 故事侧重 |
|------|------|---------|
| **CVPR 2026** (主目标) | Oral/Highlight | "发现跨图注意力坍塌 + 提出分解式预编码" |
| **ICLR 2026** (备选) | Spotlight | 偏理论：跨图注意力行为的系统性分析 |
| **NeurIPS 2026** (备选) | Oral | 偏方法：对应-差异分解的信息论论证 |

### 最可能的拒稿理由

> "The improvement is primarily from additional cross-attention computation, not from the correspondence-difference decomposition."

**对策**：消融实验 B5（Perceiver 联合压缩，有跨图交互但无分解）vs DIVE 是关键。如果 DIVE ≫ B5，说明**分解是活性成分**，不仅仅是"多了几层 attention"。

---

## 14. 执行路线图

| 阶段 | 时间 | 任务 | 交付物 |
|------|------|------|--------|
| **Phase 0: 验证发现** | Week 1-2 | 在现有 VLM 上量化跨图注意力坍塌 | 分析论文/figure |
| **Phase 1: MVP** | Week 3-5 | 在 LLaVA-NeXT-7B 上实现 DIVE（仅 Stage 1+2），在 BLINK 上测试 | 初步数据点 |
| **Phase 2: 完整方法** | Week 6-8 | 加入 Stage 3（对应-差异分解），完整消融 | 消融表格 |
| **Phase 3: 扩展验证** | Week 9-11 | 3 个 base VLM × 6 个 benchmark | 主实验表格 |
| **Phase 4: 论文撰写** | Week 12-14 | 写作 + 补充实验 + rebuttal 预演 | 完整论文 |

> [!IMPORTANT]
> **Phase 0 是 kill test**：如果跨图注意力坍塌在实际 VLM 中**不可复现或不显著**，核心 finding 不成立，需要调整故事角度（转向效率论证或对应-差异的任务增益论证）。
