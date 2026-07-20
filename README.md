# OBS 可信AI调度层 (OBS-TrustLayer)

> **GOAI 世界人工智能开源大赛 T3 赛道：AI for Research**
>
> 面向 OBS 海底地震数据处理的**模型无关可靠性调度层**——让 AI 不仅会答题，还能说"我不确定"。

[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.8%2B-blue.svg)](https://www.python.org/)

---

## 🎯 一句话定位

不再开发一个新的 OBS 拾取模型 — 我们在所有模型之上做**可信 AI 调度层**：
检查数据质量、比较多模型结果、评估风险，决定自动接受、模型融合还是人工复核。

## 🧠 为什么需要这个？

| 场景 | 模型的行为 | Trust Layer 的应对 |
|------|-----------|-------------------|
| 数据缺通道 | 强行推理，score 0.88 | 检测缺道 → 提高风险 → 拒绝/复核 |
| 陌生海域噪声 | 高置信乱报虚检 | 多模型分歧 → 提高风险 |
| 两个模型给不同答案 | 不知道该信谁 | 分歧量化 → 评估共识度 |
| P 波晚于 S 波 | 违反物理规律仍输出 | 物理约束检查 → 拦截 |

## 🏗️ 系统架构

```
OBS 波形
    │
    ├── Data Inspector ──── 数据质量检查 (通道/断点/削波/SNR)
    ├── Model Adapters ──── PhaseNet + OBSTransformer 统一推理
    ├── Evidence Engine ─── 四类证据提取
    ├── Reliability Engine ─ 风险评分 + 决策路由
    │
    └── 输出: ACCEPT / ROUTE / ABSTAIN + 原因码
```

## 📊 核心指标

> "在自动通过 X% 的样本时，系统拦截了 Y% 的错误预测。"

| 指标 | 目标 |
|------|------|
| 错误拦截率 | ≥ 80% |
| 自动覆盖率 | 60–80% |
| 选择性风险 | 显著低于单模型/最高置信度基线 |

## 🚀 快速开始

```bash
# 1. 创建环境
conda create -n trustlayer python=3.8 -y
conda activate trustlayer

# 2. 安装依赖
pip install -r requirements.txt

# 3. 运行 Demo
python run_demo.py --input sample_data/ --models obst,phasenet
```

## 📁 项目结构

```
.
├── src/
│   ├── models/          # 模型接入适配器
│   ├── quality/         # 数据质量检查
│   ├── evidence/        # 证据提取引擎
│   ├── engine/          # 可靠性引擎 + 决策路由
│   ├── api/             # FastAPI 后端
│   ├── web/             # 前端可视化
│   └── utils/           # 工具函数
├── docs/                # 项目文档
│   ├── prd/             # 产品需求文档
│   ├── design/          # 架构设计
│   ├── experiments/     # 实验日志
│   └── meetings/        # 会议纪要
├── tests/               # 测试
├── sample_data/         # 示例数据
├── AGENTS.md            # 项目规则
├── requirements.txt     # Python 依赖
└── README.md
```

## 👥 团队

| 角色 | 专业 |
|------|------|
| 算法负责人 | CS (地震探测) |
| 信号物理负责人 | 水声电子 |
| 仿真数据负责人 | 电气工程 |
| 可视化负责人 | 建筑学 |
| 工程开源负责人 | 通用 Coding |
| 文档统筹 & PM | 社会学 |

## 📚 文档

- [产品需求文档 (PRD)](docs/prd/PRD.md)
- [项目规则 (AGENTS.md)](AGENTS.md)

## 📄 致谢

本项目基于以下开源工作：

- [OBSTransformer](https://github.com/alirezaniki/OBSTransformer) — OBS 专用地震拾取模型
- [PhaseNet](https://github.com/wayneweiqiang/PhaseNet) — 经典深度学习震相拾取
- [EQTransformer](https://github.com/smousavi05/EQTransformer) — Transformer 地震检测与拾取
- [SeisBench](https://github.com/seisbench/seisbench) — 地震学机器学习工具集

## 📜 License

MIT License
