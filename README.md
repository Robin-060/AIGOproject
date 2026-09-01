# OBS Trust Engine

> 面向海底地震仪（OBS）数据的模型无关可信 AI 调度层
> GOAI 世界人工智能开源大赛 · T3 AI for Research 赛道

**一句话定位**：不再开发新的拾取模型，而是在多个拾取模型之上构建可靠性评估层——检查数据质量、比较多模型结果、验证物理约束，决定自动接受、模型融合还是人工复核。

## 为什么需要

深度学习拾取模型（PhaseNet / PickBlue / OBSTransformer）在真实部署中会系统性犯错：

- **数据质量退化**：缺通道、削波、强噪声下模型照常输出高置信结果
- **领域偏移**：陆地训练的模型部署到新海域，论文性能无法迁移
- **模型分歧**：两个模型给出相差数秒的拾取，不知道该信谁
- **物理不可能**：P 波拾取晚于 S 波，荒谬结果流入下游分析

当前实验口径（semifinal_v1.5.1-bugfix，1306 个相位级评估单元，容差 P 0.5s / S 1.0s）：Trust Layer 在严格 FUSE 门槛下覆盖率为 45.64%，风险排序严格单调（DS2 成立）；预声明 50% 点位 NOT_EVALUABLE。修正 cluster bootstrap 后，总体天花板补充比较仍为 INCONCLUSIVE（Δ=+1.17pp，95% CI [−1.09,+2.93]），但 S 相在自身 45.45% 天花板处显著差于 Voting（Δ=+3.39pp，95% CI [+0.90,+5.96]）。这些均为补充结果，不替代预声明点判定。

## 系统架构

```
数据层: PhaseNet(geofon) / PickBlue / OBSTransformer / EQTransformer → 统一预测格式
   ↓
证据层:
  ├─ 数据质量证据      0-30 分
  ├─ 单模型证据        0-24 分
  ├─ 多模型一致性      0-37 分  ★核心
  └─ 物理约束证据      0-40 分
   ↓
风险聚合 + 决策路由: 0-100 分 → ACCEPT / FUSE / ABSTAIN
   ↓
输出: 风险等级 + 决策 + 完整原因链
```

核心机制：**证据不足时，系统说"我不确定"而不是猜答案。**

## 快速开始

```bash
# 1. 安装依赖 (Python 3.10+)
python3 -m pip install -r requirements.txt

# 2. 完整链路 (从原始数据到决策)
python src/data_layer/download_obs_dataset.py            # 下载数据 (可选, ~34GB)
python src/data_layer/data_layer.py --output result.json # 三模型推理
python -m src.trust_engine.pipeline --input result.json  # Trust Engine 决策

# 3. 启动 Demo
streamlit run src/web/app.py                             # 或: sh scripts/run_demo.sh
```

### Demo 使用说明

页面打开后上传数据组产出的 `result.json`，Demo 会展示每个模型的状态、P/S 最终决策、四证据风险分解和实验图表。如同时上传对应 `.csv`、MiniSEED 或 SEG-Y 波形，页面还会展示原始与预处理后波形、模型 P/S 拾取竖线和经典 STA/LTA 触发结果（CSV 列格式 `time_s,Z,N,E,H`；MiniSEED/SEG-Y 由 ObsPy 读取）。

### 运行正式实验

```bash
bash smoke_test_a.sh                      # A 最小环境: 配置/hash/A 测试
bash smoke_test.sh                        # 全仓库环境自检（含 B Web 测试）
bash reproduce_core.sh                    # 一键复现核心数字与三张主图
# 等价于: python3 -m src.experiments.reproduce_main
```

复现范围（全程使用冻结预测，不运行模型推理）：冻结数据 sha256 校验 → 8 策略基线 → 主实验 → 全方法对比 → cluster paired-bootstrap → 三张主图 → 探索轨迹 JSONL。核心数字落在 `results/reproduction_report.json`，详细口径见 [复现说明](docs/reproduction.md)。

## 实验结论摘要

| 指标 | 结果 (semifinal_v1.5.1-bugfix) |
|------|------|
| 评估单元 | 1306 个 (P 657 + S 649)，容差 P 0.5s / S 1.0s |
| Trust 覆盖率天花板 | 45.64%（严格 FUSE 门槛；596/1306 有安全自动路径） |
| 预声明 50% 点位 | NOT_EVALUABLE（不等覆盖不比较，纪律见 [评估协议](docs/experiments/evaluation_protocol.md)） |
| 风险排序 | 分箱严格单调 4.07→9.2→28.57%（DS2 成立） |
| A 测试 | `smoke_test_a.sh` 全部通过 |
| 一键复现 | `bash reproduce_core.sh`（冻结数据 sha256 校验） |

## 复赛证据链（Evidence Chain）

提交材料按以下主键可追溯，任何一段都能倒查到具体 run：

> 代码版本 → config → 数据版本 → trajectory → result → Figure/Table → Scientific Claim

| 环节 | 载体 | 入口 |
|------|------|------|
| 代码版本 | git 提交记录（integration 分支） | `git log` |
| config | `configs/semifinal_main.yaml`（semifinal_v1.5.1-bugfix，seed 42，冻结 hydrophone_v2） | `config_loader.py` |
| 数据版本 | 冻结预测 + 真值 + 质量清单（sha256 校验） | `reproduce_main` 第 1 步 |
| exploration history | `results/exploration_trajectory.jsonl`（EXP01–15，Observation→Action→Tool→Feedback） | `src/experiments/generate_trajectory.py` |
| actual run trajectory | `results/run_trajectory.jsonl`（commit/config/seed/逐步状态/输出 hash/干预披露） | `src.experiments.reproduce_main` |
| result | `results/*.csv` + `bootstrap_ci.json` + `reproduction_report.json` | `bash reproduce_core.sh` |
| Figure/Table | `figures/*.png` + `results/equal_coverage_table.csv` | 同上 |
| Scientific Claim | 由 C 按实验冻结（候选口径见 [DS 判定汇总](docs/experiments/ds_findings_v15.md)） | `docs/final_report.md` |

探索历史 JSONL 由脚本从历史材料生成，引用缺失会直接失败；真实正式运行另由 `reproduce_main` 逐步写入 `run_trajectory.jsonl`，两者不再混称。

## 文档索引

| 文档 | 内容 |
|------|------|
| [问题定义文档](docs/problem_definition.md) | 4 页问题定义（比赛主材料） |
| [最终实验报告](docs/final_report.md) | 完整实验设置、结果与分析 |
| [复现说明](docs/reproduction.md) | 一键复现入口、环境、核心数字 |
| [DS 判定汇总](docs/experiments/ds_findings_v15.md) | 五个研究问题的最终判定与依据 |
| [评估协议](docs/experiments/evaluation_protocol.md) | Equal-Coverage 与 NOT_EVALUABLE 纪律 |
| [参数溯源表](docs/parameter_provenance.md) | 每个参数的来源与校准方法 |
| [数据与模型来源](docs/data_and_model_sources.md) | 数据合规声明 |
| [开源计划](docs/open_source_plan.md) | 开源路线图 |
| [范围与合规](docs/scope_and_compliance.md) | 项目边界与合规说明 |
| [失败案例分析](docs/experiments/failure_cases.md) | 已知失效模式 |
| [实验日志模板](docs/experiment_log_template.md) | 实验记录格式 |

## 代码结构

```
src/
├── data_layer/    # 数据下载 → 三模型推理 → 四合一输出
├── trust_engine/  # 核心引擎: 证据层 + 路由 + 流水线
├── calibrate/     # 参数校准脚本 (差值统计/逻辑回归/故障注入)
├── experiments/   # 基线/消融/噪声实验
├── signal/        # 信号预处理 + STA/LTA 基线
├── web/           # Streamlit Demo
└── demo_backend/  # Demo 后端 API
```

## 数据与模型合规

- 数据：SeisBench OBS 数据集（Zenodo 公开，Bornstein et al., 2023）
- 模型：全部公开预训练权重（SeisBench 仓库）
- 无闭源模型、无受限数据、无第三方商业 API
- 不接触南海受限或涉密 OBS 数据，不进行海上采集

## License

[MIT](LICENSE)
