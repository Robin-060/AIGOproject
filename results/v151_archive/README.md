# v1.5.1 冻结产物归档（2026-09-01）

> 本目录保存 ROUTE invalid-pick bug 修复**之前**的 v1.5.1 冻结结果，
> 用于 v1.5.1-bugfix 的前后对照与永久留档。评估口径一律以
> v1.5.1-bugfix 重跑结果为准；本目录只读、不再改动。

- 归档时 config 版本: semifinal_v1.5.1
- 归档时 config sha256 前缀: cba251c80f7c28be
- 归档内容: main_results.csv / equal_coverage_trust.csv / risk_bins.csv /
  bootstrap_ci.json / reproduction_report.json / coverage_vs_unsafe.png
- bug 描述: 8 条 ROUTE 中 7 条选中模型无该相位真实拾取
  (action 有 ROUTE 标签但无 pick, 不得计入 Coverage);
  修复规则: 选中模型必须具有该相位有效预测, 否则 ABSTAIN
  (reason: ONLY_SURVIVOR_<model>_NO_VALID_PICK)。
