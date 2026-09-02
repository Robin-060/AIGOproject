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

历史冻结基线 v1.5.1（1306 个相位级评估单元）在严格 FUSE 门槛下的自动 Coverage 为 45.64%，该负结果及其 Equal-Coverage 判定保持独立，不被后续实验覆盖。在同一数据、模型和评价单元上，EXP16 表明组合风险证据能够提高固定人工复核预算下的错误截获效率；post-hoc、failure-driven 的 EXP17-A 将 Coverage 恢复至 54.13%，Unsafe 为 5.51%，Error Interception 为 94.26%。相对 Voting@50，ΔUnsafe 点估计为 +0.92pp，但配对 station-cluster bootstrap 的单侧 95% 上界为 +2.24pp，超过最终裁决的 +2.0pp 非劣界。因此冻结结论为：**Coverage recovery supported; safety non-inferiority inconclusive**。

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

> 完整图示（业务流程图 / 6 步路由决策图 / 四证据层 / 模块调用关系 / 复现链 /
> 探索闭环 / Demo 部署）见 [架构与流程图示](docs/architecture_diagrams.md)。

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

| 指标 | 结果 |
|---|---|
| 评估单元 | 1306 个（P 657 + S 649） |
| EXP17-A Coverage | **54.13%** |
| Unsafe Output Rate | **5.51%** |
| Error Interception | **94.26%** |
| 配对 bootstrap 非劣界 | ΔUnsafe 单侧 95% 上界 **+2.24pp**；点估计 **+0.92pp** |
| 科研结论 | Coverage 已恢复；Unsafe 点估计与 Voting 接近，但 +2.0pp 非劣界尚未统计确认 |
| Risk ranking | 保持有效，不因 R1 robustness check 改变 |
| R1 explicit-parameter reproduction | **PASS**；运行路径使用校准容差 P=0.34s / S=0.51s，复算与冻结 EXP17-A 一致；R1 reproduction PASS ≠ EXP17 safety Gate PASS |
| 参数审计 | 红灯参数 **0**；legacy P0.30/S0.50 不在正式运行路径 |
| 测试 | **76 tests passed** |

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
| [C 部分科研主文档](docs/deliverables/9c%20部分%20GOAI_OBS_科研边界与实验契约_v1.9_AB验收与发布身份对齐版.docx) | 最终 Scientific Discovery Report、证据契约与 No-Go |
| [复赛答辩 PPT](docs/deliverables/8GOAI_OBS_复赛答辩主体_v3.3_AB验收与发布身份对齐版.pptx) | 三分钟成果主线与附录证据链 |
| [架构与流程图示](docs/architecture_diagrams.md) | 业务流、6 步路由、四证据层、模块调用、复现链、探索闭环、Demo 部署 |
| [DS 判定汇总](docs/experiments/ds_findings_v15.md) | 五个研究问题的最终判定与依据 |
| [评估协议](docs/experiments/evaluation_protocol.md) | Equal-Coverage 与 NOT_EVALUABLE 纪律 |
| [参数溯源表](docs/parameter_provenance.md) | 每个参数的来源与校准方法 |
| [数据与模型来源](docs/data_and_model_sources.md) | 数据合规声明 |
| [第三方声明](THIRD_PARTY_NOTICES.md) | 数据、软件、模型权重与许可证边界 |
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

- 数据：Zenodo OBS / PickBlue 数据集，DOI `10.5281/zenodo.10277799`，CC BY 4.0；
  原始波形不随仓库重新分发。
- 模型：PhaseNet `geofon`、PhaseNet/PickBlue `obs`、OBSTransformer `obst2024`、
  EQTransformer `obs`；权重由 SeisBench 下载，不随仓库打包。
- 训练—评估重叠：OBS checkpoint 当前为 UNKNOWN，因此不据此声称独立跨数据集泛化。
- 未使用闭源模型服务、第三方商业 API、南海受限或涉密 OBS 数据。
- 顶层 MIT 仅覆盖团队有权许可的原创代码与文档；完整边界见
  [数据与模型来源](docs/data_and_model_sources.md)和[第三方声明](THIRD_PARTY_NOTICES.md)。

## License

[MIT](LICENSE)

MIT 仅覆盖本项目团队自行编写的代码。数据集、SeisBench、预训练模型权重及其他第三方依赖仍分别受其原始许可证和使用条款约束。
