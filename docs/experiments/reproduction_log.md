# 复现日志（clean env 验证）

> 历史记录说明：本页记录的是 semifinal_v1.5 的首次 clean-env 运行。
> 当前正式口径为 v1.5.1；最新一次可审计执行及输出哈希见
> `results/run_trajectory.jsonl` 和 `results/reproduction_report.json`。

> 任务书 9/2 上午项"clean env 复现"提前执行（2026-08-31）。
> 目的：证明干净环境（仅 requirements.txt + 冻结数据）能复现核心数字、表与图。

## 1. 干净环境

| 项 | 值 |
|---|---|
| Python | 3.14.4（全新 venv，位于仓库外 `D:/Uni/AIGO/.venv_clean_repro`） |
| 依赖安装 | `pip install -r requirements.txt`（清华镜像，全部从 PyPI 解析） |
| 关键版本（clean） | seisbench 0.12.5 / torch 2.13.0 / obspy 1.5.1 / numpy 2.5.2 / scipy 1.18.1 / pandas 2.3.3 / matplotlib 3.11.1 |
| 关键版本（开发环境对照） | seisbench 0.12.3 / obspy 1.5.0 / numpy 2.5.1 / scipy 1.18.0 / pandas 3.0.5 |
| 环境变量 | `SEISBENCH_CACHE_ROOT=D:/seisbench_cache`（与开发环境同） |

注意：干净环境按 requirements.txt 约束解析到 pandas 2.3.3，而开发环境实际使用
pandas 3.0.5（超出 `<3` 上限）——两个版本下结果完全一致，跨版本稳健。

## 2. 复现命令

```bash
cd OBSTransformer-main
SEISBENCH_CACHE_ROOT=D:/seisbench_cache \
  /d/Uni/AIGO/.venv_clean_repro/Scripts/python -m src.experiments.reproduce_main
```

全程使用冻结预测，不运行模型推理，不需要网络下载数据或权重。

## 3. 结果核对

- 7 步全过（校验 → 基线 → 主实验 → 对比 → bootstrap → 主图 → 轨迹），exit 0
- 核心数字与冻结口径**完全一致**：
  - 声明点位 50%: NOT_EVALUABLE（Trust 天花板 45.64%）
  - Voting@50% = 4.59%
  - 天花板补充 Δ=+1.17pp，INCONCLUSIVE（CI 含 0）；P 相 −1.3pp / S 相 +3.4pp
- 单元测试：52 个全过（clean venv 内运行）
- **该次 Windows clean env 内产物逐字节一致**：跑完后 `git status` 仅有
  `results/reproduction_report.json` 一个文件变化，且差异只在其环境版本字段与
  时间戳字段；其余 CSV/JSON/PNG 与当时提交版本一致。该结论不外推为
  跨操作系统 PNG 必然逐字节一致；跨平台要求是核心数值和规范化表格内容一致。

## 4. 结论

clean env 复现 ✅ 通过（任务书 DoD："clean env 能复现核心表和图"）。

## 5. 增补（2026-08-31，冻结档案纪律 v1.5.1）

- requirements.txt 新增 `pyyaml>=6,<7`（复现链读取 `configs/semifinal_main.yaml`
  的 `experiment.frozen_profile` 所需）；两个环境补装 pyyaml 6.0.3 后重跑全链，
  核心数字不变，产物仍逐字节一致（仅 reproduction_report.json 的时间戳/耗时字段
  按每次运行变化）。
- 复现链不再重新比较候选档案（EXP06 历史程序改由
  `--profile-selection` 显式重放，只写 `results/profile_selection_exp06.csv`）。

## 6. 增补二（2026-08-31 晚，v1.5.1 整合后的当前状态）

- 引擎全部参数进入 `configs/semifinal_main.yaml`（`trust_engine.parameters`，
  含数据罚分/置信门槛/物理分数/分歧阈值），由 `src/trust_engine/config_loader.py`
  单一读取，`config_hash`（配置全文件 SHA-256）随所有结果行。
- cluster bootstrap 重复权重 bug 修正（EXP15）：总体与 P 相补充比较仍
  INCONCLUSIVE；**S 相在自身 45.45% 天花板处 Δ=+3.39pp，CI [+0.90,+5.96]，
  显著差于 Voting**（负结果如实记录）。
- 当前测试套件 64 个全过、`smoke_test_a.sh` 62 个通过；本页第 1-5 节的
  "52 个测试"为当时 clean-env 验证的历史数字。
- 核心数字与第 3 节一致（50% NOT_EVALUABLE、天花板 45.64%、Δ=1.17pp）。
