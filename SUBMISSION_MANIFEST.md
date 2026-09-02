# GOAI 2026 复赛提交包清单

> 赛道：赛道三·前沿探索 AI for Research  
> 项目：OBS Trust Engine / OBS Trust Layer  
> 发布身份：`goai-2026-final-v3`（包装验收完成后创建的不可变标签）

## 1. 必要材料对应

| 复赛要求 | 交付入口 | 状态 |
|---|---|---|
| 研究问题、过程与意义 | `docs/problem_definition.md`、`docs/final_report.md` | COMPLETE |
| 最小可运行探索环境 | `environment_spec.md`、`src/web/`、`src/demo_backend/` | COMPLETE |
| 完整探索日志 | `docs/exploration_log.md`、`docs/experiments/exploration_log_materials.md` | COMPLETE |
| 参考框架与 baselines | `docs/architecture_diagrams.md`、`src/experiments/run_baselines.py` | COMPLETE |
| README / 安装 / 配置 / 预期输出 | `README.md`、`docs/reproduction.md`、`JUDGE_QUICKSTART.md` | COMPLETE |
| 代码和自动验证 | `smoke_test*.sh`、`reproduce_*.sh`、`.github/workflows/ci.yml` | COMPLETE |
| 可交互 Demo | `scripts/run_demo.sh`、`docker-compose.yml` | COMPLETE |
| 现场陈述与问答 | `docs/defense_script.md`、`docs/demo_runbook.md`、`docs/qa_cards.md` | COMPLETE |
| 答辩 PPT | `docs/deliverables/` 中标注“包装验收版”的 PPTX | COMPLETE |
| C 部分 Scientific Discovery Report | `docs/deliverables/` 中标注“包装验收版”的 DOCX | COMPLETE |
| 数据/模型/许可证披露 | `THIRD_PARTY_NOTICES.md`、`docs/data_and_model_sources.md`、`SBOM.md` | COMPLETE |

## 2. 核心科研身份

| 对象 | 冻结值 |
|---|---|
| Config | `semifinal_v1.5.1-bugfix` |
| Config SHA-256 | `9727570d238aa4925add04bf363f7611e85e83ea4914f5cf5f8a976c58202b6d` |
| Primary evaluation | 1306 phase units（P 657 / S 649） |
| Review result | Trust 83.6% @ 50% budget；holdout Primary 80.1% |
| EXP17-A | Coverage 54.13%；Unsafe 5.51%；Interception 94.26% |
| c2 | ΔUnsafe +0.92pp；one-sided upper 95% +2.24pp；NOT ESTABLISHED |
| Tests | 76 passed |

## 3. 历史保护

- `results/v151_archive/` 保留 v1.5.1 冻结产物；
- EXP17 使用独立后缀结果文件，不改写 v1.5.1；
- 早期问题定义和失败案例放在 `docs/experiments/legacy/`，显式标注为历史口径；
- 上一版 DOCX/PPTX 保留在 Git 中的 `docs/deliverables/archive/` 用于审计，并通过 `export-ignore` 排除出评审提交压缩包，避免双版本混淆；
- ROUTE invalid-pick bugfix 与 EXP17 算法 refinement 分轨。

## 4. 不包含

- 原始 OBS 波形、SeisBench 数据缓存、模型 checkpoint；
- 虚拟环境、临时渲染文件、个人绝对路径、密钥或 token；
- 无法核实来源或再分发权限的第三方权重/代码。

## 5. 包装验收

最终压缩包应通过：解压完整性、重要文件存在、私密/个人路径扫描、
冻结证据校验、核心复现和 76 项测试。只有完成这些验收后，
`goai-2026-final-v3` 才可作为提交身份。
