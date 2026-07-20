# AGENTS.md — OBS 可信AI调度层 项目规则

> 本项目参加 GOAI 世界人工智能开源大赛 T3 赛道：AI for Research
>
> 核心定位：面向 OBS 地震数据处理，构建模型无关的 AI 可靠性调度层

---

## 文档规则

1. **所有项目文档必须使用 Markdown 格式（`.md`）**，包括但不限于 PRD、会议纪要、实验日志、API 规范。
2. 文档统一存放在 `docs/` 目录下，按类别分子目录：
   ```
   docs/
   ├── prd/              # 产品需求文档
   ├── design/           # 架构设计、技术方案
   ├── experiments/      # 实验日志、评测报告
   ├── meetings/         # 会议纪要
   └── references/       # 参考文献、外部资料
   ```
3. 每个 Markdown 文件必须包含：标题、日期、作者（或小组）、版本号。
4. 中文撰写，技术术语保留英文并附必要注释。
5. 图片统一存放在 `docs/assets/` 下，使用相对路径引用。

---

## 代码规则

1. **项目根目录保持整洁**，源码按功能分子目录：
   ```
   src/
   ├── models/           # 模型接入适配器
   ├── quality/          # 数据质量检查
   ├── evidence/         # 证据提取（单模型/多模型/物理）
   ├── engine/           # 可靠性引擎 + 决策路由
   ├── api/              # API 接口
   ├── web/              # 前端可视化
   └── utils/            # 工具函数
   ```
2. Python 代码遵循 PEP 8，函数需有 docstring。
3. 每个核心模块必须有对应的测试文件和示例 notebook。
4. 所有依赖写入 `requirements.txt` 或 `environment.yml`。
5. 环境配置必须可一键复现（`conda env create -f environment.yml`）。

---

## 协作规则

1. **每日 15 分钟站会**，只核对：交付、接口变化、阻塞项。
2. 功能分支开发，`main` 分支仅通过 PR 合并。
3. 提交信息格式：`[模块] 简短描述`，如 `[engine] 添加风险评分规则`。
4. 接口变更必须同步更新文档并通知相关组员。

---

## 技术栈

| 层级 | 技术选型 |
|------|----------|
| 模型接入 | SeisBench、EQTransformer、PhaseNet |
| 后端 | Python 3.8+, FastAPI |
| 前端 | HTML/CSS/JS 或 Streamlit（轻量） |
| 数据格式 | JSON（统一输出）、HDF5（数据存储） |
| 版本控制 | Git + GitHub |
| 环境管理 | Conda |

---

## 团队角色速查

| 角色 | 负责 |
|------|------|
| 算法负责人 (CS) | 模型接入、风险引擎、评测指标 |
| 信号物理负责人 (水声) | 深海噪声分析、滤波预处理 |
| 仿真数据负责人 (电气) | 仿真数据生成、数据标准化 |
| 可视化负责人 (建筑学) | Web 面板、波形展示 |
| 工程开源负责人 (通用 coding) | 仓库建设、CI/CD、文档 |
| 文档统筹 (社会学) | PRD、4 页问题定义、合规 |

---

## 参考资料

- [GOAI 大赛官网](https://goaihz.com)
- [OBSTransformer](https://github.com/alirezaniki/OBSTransformer)
- [EQTransformer](https://github.com/smousavi05/EQTransformer)
- [SeisBench](https://github.com/seisbench/seisbench)
