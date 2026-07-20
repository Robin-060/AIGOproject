# 项目路线图：M0 → M3 完整步骤 (v2.0)

> **版本**: v2.0
> **日期**: 2026-07-18
> **目标**: GOAI T3 赛道 8月1日初稿交付
> **变更**: 集成 SeisBench，简化模型接入

---

## M0：项目初始化 ✅ 已完成

| 完成项 | 说明 |
|--------|------|
| OBSTransformer 模型跑通 | `detection.py` → 成功检测 6 个事件 |
| 团队认知同步 | 全组理解 OBS + AI 拾取 + Trust Layer 定位 |
| PRD 文档 | `docs/prd/PRD.md` — 13 章完整 PRD |
| AGENTS.md | 项目规则：全部文档用 .md |
| README.md | 项目首页已更新为 TrustLayer 定位 |
| Schema 设计 | `src/schema.py` 数据结构已定稿 |
| 项目架构讨论 | 四层架构：Data → Model → Evidence → Trust Engine |

---

## M1：基础设施搭建 (7.18 – 7.21)

> **目标**: 仓库可用、SeisBench 接入两个模型、数据质量检查跑通、仿真数据就绪

---

### M1.1 SeisBench 安装 + 两个模型下载

**负责人**: 算法
**截止**: 7.18 晚

```bash
conda activate obst
pip install seisbench
```

```python
# 验证两个模型都能加载
import seisbench.models as sbm
pn = sbm.PhaseNet.from_pretrained("original")
obst = sbm.OBSTransformer.from_pretrained("original")
```

**产出**: 两个模型可本地调用

---

### M1.2 核心代码文件创建

**负责人**: 算法
**截止**: 7.19 晚

按这个顺序创建：

```
src/
├── schema.py              ← 全组共用数据结构（已完成）
├── quality/
│   └── checker.py         ← 缺道/断点/削波/SNR
├── models/
│   ├── adapter.py         ← ModelAdapter 基类 (~15行)
│   └── seisbench_adapter.py ← SeisBench 统一接入 (~70行)
├── evidence/
│   ├── data_evidence.py   ← 数据质量 → 0-30分
│   ├── single_model.py    ← 模型自信度 → 0-15分
│   ├── multi_model.py     ← 多模型一致性 → 0-40分 ★
│   └── physics.py         ← 物理约束 → 0-15分
├── engine/
│   └── reliability.py     ← 汇总 → 风险评分 → 等级 → 路由
└── pipeline.py            ← 主流程
```

**产出**: 全部 10 个 .py 文件，代码已在对话中给出

---

### M1.3 GitHub 仓库初始化

**负责人**: 工程开源
**截止**: 7.19 晚

```
□ 创建 GitHub 仓库 (OBS-TrustLayer)
□ 推送当前代码 + 项目结构
□ 编写 .gitignore
□ 创建 environment.yml
□ 编写 requirements.txt（加入 seisbench）
```

**产出**: 全组可 clone + 运行

---

### M1.4 数据准备

**负责人**: 信号物理 + 仿真数据
**截止**: 7.20

| 子任务 | 产出 |
|--------|------|
| 整理 YM 台网真实数据 | `data/real/YM.01/*.npy` (≥5个) |
| 生成仿真地震波形 (M2.0-4.0) | `data/synthetic/events/*.npy` + `labels.csv` |
| 生成仿真噪声 (洋流/电气/热液) | `data/synthetic/noise/*.npy` |
| 生成故障样本 (缺道/断点/削波) | `data/synthetic/faults/*.npy` |

**产出**: 真实 ≥5 段 + 仿真 ≥30 段 + 噪声 ≥5 段 + 故障 ≥5 段

---

### M1.5 配置文件

**负责人**: 算法
**截止**: 7.20

创建 `config/thresholds.yaml`：

```yaml
# 证据权重
evidence_weights:
  data: 0.30
  single_model: 0.15
  multi_model: 0.40
  physics: 0.15

# 多模型一致性容差 (秒)
model_tolerance:
  p: 0.3
  s: 0.5

# 风险等级阈值
risk_thresholds:
  low_max: 30
  medium_max: 60
  # 61-100 → HIGH
```

**产出**: `config/thresholds.yaml`

---

### M1 完成检查 (7.21 晚，全员 15 分钟)

```
□ GitHub 仓库可访问，全组 clone 成功
□ SeisBench 两个模型可加载
□ src/pipeline.py demo 模式跑通（三个场景输出正确）
□ 数据质量检查 4 项可运行
□ 真实 + 仿真数据就绪
□ 全组每人一句话复述: 输入→输出→我们比单模型好在哪
```

---

## M2：核心引擎 + 实验 (7.22 – 7.28)

> **目标**: 端到端跑通、Web 面板可用、基线对比实验完成

---

### M2.1 端到端 Pipeline 调通

**负责人**: 算法
**截止**: 7.23

```
任务:
□ 用真实 YM 数据跑通 pipeline.py（不模拟）
  - SeisBench 加载 OBSTransformer + PhaseNet
  - 对同一波形分别推理
  - 质量检查 → 证据提取 → 可靠性引擎
  - 输出完整 reliability.json

□ 验证: 输出 Schema 和 PRD 6.3 节一致
```

**产出**: 给定真实波形 → 输出 `reliability.json`

---

### M2.2 参数调优

**负责人**: 算法 + 信号物理
**截止**: 7.25

```
任务:
□ 在仿真数据上（标签已知）调优参数:
  - 调整 model_tolerance (P的0.3s是否合理？)
  - 调整风险等级阈值 (30/60 是否合理？)
  - 调整证据权重

□ 记录每次调参结果到实验日志
□ 固定最终参数
```

**产出**: `docs/experiments/param_tuning.md`

---

### M2.3 Web 可视化面板

**负责人**: 可视化 (建筑学)
**截止**: 7.25

```
任务:
□ 选择框架: Streamlit (推荐, 最轻量)
□ 页面1: 样本列表（按风险等级筛选）
□ 页面2: 样本详情
  - 三通道波形图 (matplotlib)
  - 每个模型的 P/S 标记（不同颜色）
  - 风险报告卡片: 分数 + 等级 + 动作 + 原因码
□ 页面3: 简易统计
  - 风险分布饼图
  - 模型一致性统计

□ 输入: 读取 reliability.json
□ 启动: streamlit run src/web/app.py
```

**产出**: `src/web/app.py` + 截图

---

### M2.4 基线对比实验

**负责人**: 算法
**截止**: 7.27

```
任务:
□ 实现三个基线:
  1. 单模型 (固定 OBSTransformer)
  2. 最高置信度 (每样本选最高分)
  3. 简单投票 (多模型时间平均)

□ 在仿真数据上 (N≥50) 对比:
  方法           错误拦截率  自动覆盖率  选择性风险
  ─────────────────────────────────────────────────
  单模型 (基线1)     0%        100%        ??%
  最高置信度 (基线2)  5%        100%        ??%
  简单投票 (基线3)    10%       100%        ??%
  Trust Layer (我们)  ≥80%      60-80%     显著更低

□ 生成核心图表: 风险-覆盖率曲线
□ 生成消融实验: 去掉某个证据 → 性能下降？
```

**产出**: `docs/experiments/baseline_comparison.md` + 图表

---

### M2 完成检查 (7.28 晚，全员 15 分钟)

```
□ 给定波形 → 端到端输出 reliability.json
□ Web 面板可用: 波形 + 标记 + 风险报告
□ Trust Layer 在至少一个指标上优于所有基线
□ 全组看懂核心图表（风险-覆盖率曲线）
```

---

## M3：联调交付 (7.29 – 8.1)

> **目标**: 一键复现、文档齐全、材料提交

---

### M3.1 一键复现脚本

**负责人**: 工程开源
**截止**: 7.29

```
□ run_demo.py
  - 检查环境 (Python/Conda)
  - 自动下载模型 (SeisBench)
  - 运行完整流程
  - 输出结果 + 启动 Web 面板

□ run_demo.sh / run_demo.bat 跨平台脚本

□ README.md 完善:
  - 安装步骤 (Win/Mac/Linux)
  - 使用说明 (带截图)
  - 常见问题 FAQ
```

**产出**: 一人一行命令跑通全流程

---

### M3.2 评测报告终版

**负责人**: 算法
**截止**: 7.30

```
□ 正式实验报告:
  - 实验设置 (数据/模型/标准/参数)
  - 核心图表: 风险-覆盖率曲线
  - 消融实验表
  - 典型案例展示 (3-5个)
  - 局限性与下一步
```

**产出**: `docs/experiments/final_report.md`

---

### M3.3 Demo 视频

**负责人**: 可视化
**截止**: 7.31 中午

```
3-5 分钟:
  0:00-0:30  项目介绍 (一句话定位)
  0:30-1:30  运行 Demo (一行命令)
  1:30-2:30  展示低风险自动通过
  2:30-3:30  展示高风险被拦截 (核心亮点)
  3:30-4:30  评测结果 + 对比基线
  4:30-5:00  开源 + 团队
```

**产出**: 视频链接

---

### M3.4 4 页问题定义文档

**负责人**: 文档统筹 (社会学)
**截止**: 7.31 晚

```
第1页: 问题定义
  - OBS 是什么、为什么重要
  - AI 拾取的可靠性问题 (用数据支撑)
  - 为什么需要 Trust Layer

第2页: 我们的方案
  - 系统架构图 (四层)
  - 核心创新 (与现有方案的区别)
  - 技术路线

第3页: 实验验证
  - 风险-覆盖率曲线 (最重要)
  - 消融实验表
  - 典型案例

第4页: 开源计划 + 团队
  - 代码仓库 + License
  - 数据集说明
  - 团队分工
  - 后续计划
```

**产出**: 4 页 PDF + 可编辑源文件

---

### M3.5 最终检查 + 提交

**负责人**: 文档统筹 + 全员
**截止**: 8.1

```
合规清单:
  □ 代码开源 (GitHub Public)
  □ LICENSE 文件 (MIT)
  □ README / 部署说明 / 依赖清单
  □ 数据来源声明 / 第三方依赖声明
  □ 无侵权内容
  □ 4 页文档 PDF
  □ Demo 视频链接
  □ 团队信息完整

提交:
  □ GOAI 官网提交
  □ GitHub Release v0.1.0-mvp
```

**产出**: 提交确认

---

## 📊 总览

```
M1 (7.18-21)       M2 (7.22-28)           M3 (7.29-8.1)
基础设施             核心开发                联调交付

SeisBench ✅         Pipeline 调通          一键复现
质量检查            参数调优                评测报告
仓库+环境            Web 面板               Demo 视频
数据就绪            基线实验                4页文档
配置文件             消融实验                提交
```

## 🔥 每日红线

| 日期 | 红线 | 未达标应对 |
|------|------|------------|
| 7.19 | SeisBench 模型下载失败 | 回退到原始 .h5 文件手动加载 |
| 7.20 | 仿真数据不够 | 先只用真实数据跑 pipeline.py |
| 7.23 | Pipeline 跑不通 | 先去掉真实模型，用模拟数据验证逻辑 |
| 7.27 | 基线实验没做完 | 至少 Trust Layer vs 单模型 一组 |
| 7.31 | Demo 视频没录 | 用截图 slideshow 替代 |
| 8.1 | 4页文档缺图表 | 文字先行，图表用草图 |

> **原则**: 先跑通，再优化。宁可 MVP 粗糙但完整，不可某个模块完美但整体不可用。
