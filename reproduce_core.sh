#!/usr/bin/env bash
# reproduce_core.sh — 一键复现核心数字与三张主图 (OPEN 附件要求)
# 复现范围: 冻结数据 sha256 校验 → 基线 → 主实验 → 对比 → bootstrap → 主图 → 探索轨迹
# 全程使用冻结预测, 不运行模型推理。
# 输出: results/reproduction_report.json (核心数字与环境版本)
set -euo pipefail
cd "$(dirname "$0")"

# Python 解释器: 优先 python3 (Linux 评审环境), 回退 python (Windows)
PY=python3
if ! command -v python3 >/dev/null 2>&1; then
  if command -v python >/dev/null 2>&1; then
    PY=python
  else
    echo "错误: 未找到 python3 或 python"; exit 1
  fi
fi

"$PY" -m src.experiments.reproduce_main

echo ""
echo "✓ 复现完成: 核心数字见 results/reproduction_report.json"
