#!/usr/bin/env bash
# smoke_test.sh — 最小可运行环境自检 (OPEN 附件要求)
# 检查项: Python 版本 → 依赖 → 冻结数据存在性 → 单元测试
# 不运行模型推理, 全程只读仓库内冻结物。
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

echo "[1/4] Python 环境"
"$PY" - <<'PY'
import sys
assert sys.version_info >= (3, 9), "需要 Python 3.9+"
print(f"  Python {sys.version.split()[0]} OK")
PY

echo "[2/4] 依赖检查"
"$PY" - <<'PY'
import importlib
for pkg in ("numpy", "scipy", "pandas", "matplotlib", "obspy", "seisbench", "torch", "pytest"):
    importlib.import_module(pkg)
    print(f"  {pkg} OK")
PY

echo "[3/4] 冻结数据存在性"
"$PY" - <<'PY'
from pathlib import Path
required = [
    "data/batch_calibration/records_all_v2.json",
    "data/quality_manifest.csv",
    "data/manifest_phase.csv",
    "data/sta_lta_picks.csv",
    "data/eqt_predictions.json",
]
missing = [p for p in required if not Path(p).exists()]
if missing:
    raise SystemExit("冻结数据缺失: " + ", ".join(missing))
print(f"  {len(required)} 个冻结数据文件齐全")
PY

echo "[4/4] 单元测试 (52 个)"
"$PY" -m pytest src/trust_engine/tests/ -q

echo ""
echo "✓ smoke_test 通过: 环境可运行, 冻结数据齐全, 测试全过"
