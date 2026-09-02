# 开放探索记录：评委导航版

完整 EXP01–17 逐条日志见
[`experiments/exploration_log_materials.md`](experiments/exploration_log_materials.md)。该日志按
Hypothesis → Experiment → Observation → Revision → Result → Limitation 记录，
包含所有被推翻方法、数字修订和产物出处。

## 主线

| 阶段 | 关键实验 | 主要反馈 |
|---|---|---|
| 身份与校准审计 | EXP01–06 | 改用 895 条重校准；修正质量清单、模型身份和通道档案 |
| 参照系与证据准入 | EXP07–13 | 引入 EQT；淘汰 STA/LTA 新证据；保留 DS3/DS4/DS5 负结果 |
| 严格策略冻结 | EXP14–15 | 堵住 FUSE 绕过；v1.5.1 Coverage 45.64%；S 相补充比较显著更差 |
| 复核效率 | EXP16 | 50% 预算 Trust 截获 83.6% 错误，holdout 方向一致 |
| 失败分解与修正 | EXP17 | A 恢复 Coverage；B/A+B/C 负结果留档；c2 非劣未确认 |

## 实验身份分层

- `results/exploration_trajectory.jsonl`：EXP01–15 的回顾性探索历史，不伪装为原始执行日志。
- `results/run_trajectory.jsonl`：正式复现的实际执行轨迹，含 commit/config/seed/step/hash。
- EXP16/EXP17：在完整人类可读日志中继续记录；EXP17 明确标为 post-hoc、failure-driven。

## 最终探索闭环

> 冻结负结果 → implementation audit → bugfix baseline → failure decomposition →
> truth-blind A/B 候选 → 四判据与配对 bootstrap → 参数路径复现审计。

最终裁决为：**Coverage recovery supported; safety non-inferiority inconclusive.**
