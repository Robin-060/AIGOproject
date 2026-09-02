# OBS Trust Layer：评委快速验收入口

> 建议阅读时间：5 分钟；核心复现不需下载原始波形或模型权重。

## 1. 一句话成果

OBS Trust Layer 用组合风险证据优先排序有限人工复核，并在保留科研边界的前提下探索自动化覆盖恢复。

| 成果 | 冻结数字 | 裁决 |
|---|---|---|
| Review Efficiency（EXP16） | 50% 复核预算：Trust 83.6%，Random 50.0%；95% CI [+19.0,+35.65] | 明确正结果 |
| Automation Coverage（EXP17-A） | 45.64% → 54.13%，Unsafe 5.51% | Coverage recovery supported |
| Safety boundary | ΔUnsafe +0.92pp；单侧 95% 上界 +2.24pp > +2.0pp | non-inferiority inconclusive |

统一裁决：**Coverage recovery supported; safety non-inferiority inconclusive.**

## 2. 90 秒核心复现

```bash
python3 -m pip install -r requirements-core.txt
bash smoke_test_a.sh
python3 scripts/verify_exp17_evidence.py
```

预期：冻结输入 hash 与 config 身份校验通过；EXP17-A 输出 54.13% / 5.51% / 94.26%；
c2 显示 `NOT ESTABLISHED`；R1 只显示参数路径复现一致。

完整重放：

```bash
bash reproduce_core.sh
bash reproduce_exp17.sh
python3 -m pytest -q
```

预期为 76 tests passed。完整命令、产物与已知边界见 `docs/reproduction.md`。

## 3. 1 分钟 Demo 路线

```bash
python3 -m pip install -r requirements.txt
bash scripts/run_demo.sh
```

1. 打开 Fixed Feedback，指出 EXP16 复核曲线；
2. 打开 EXP17/R1，同时指出 `+2.24pp` 和 `c2 NOT ESTABLISHED`；
3. 打开 Case Explorer，展示“多数一致仍可能错”的 S 相反例；
4. 调整一个允许参数，观察真实后端返回的 action/reason codes。

主持人话术和故障切换方案见 `docs/demo_runbook.md`。

## 4. 证据导航

| 要检查的问题 | 入口 |
|---|---|
| 科研问题、RQ2 与 Scientific Claim | `docs/problem_definition.md` |
| 完整 EXP01–17 探索与负结果 | `docs/exploration_log.md` |
| 最终报告 | `docs/final_report.md` |
| 数据、模型、参数、产物 hash | `results/evidence_manifest.json` |
| 数据/模型/许可证披露 | `docs/data_and_model_sources.md`、`THIRD_PARTY_NOTICES.md` |
| 系统流程和参考框架 | `docs/architecture_diagrams.md`、`environment_spec.md` |

## 5. 阅读数字时的三条边界

- v1.5.1 冻结负结果与 EXP17 分轨，后者不覆盖前者。
- EXP17 为 post-hoc、failure-driven refinement，不是独立盲测或严格预注册确证。
- holdout Primary 仅作方向一致性佐证，不支持跨数据集普适泛化。
