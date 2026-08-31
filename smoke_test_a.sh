#!/usr/bin/env bash
# A-only smoke test: frozen config/artifacts + Trust Engine/experiment tests.
# It intentionally excludes B's Streamlit web test and does not run model inference.
set -euo pipefail
cd "$(dirname "$0")"

PY=python3
if ! command -v python3 >/dev/null 2>&1; then
  if command -v python >/dev/null 2>&1; then
    PY=python
  else
    echo "错误: 未找到 python3 或 python"; exit 1
  fi
fi

echo "[1/4] A 核心环境"
"$PY" - <<'PY'
import importlib
import sys
assert sys.version_info >= (3, 10), "A 核心环境需要 Python 3.10+"
for pkg in ("numpy", "scipy", "pandas", "matplotlib", "pytest", "yaml"):
    importlib.import_module(pkg)
print(f"  Python {sys.version.split()[0]} + core dependencies OK")
PY

echo "[2/4] 唯一冻结配置"
"$PY" - <<'PY'
from src.trust_engine.config_loader import load_frozen_config
frozen = load_frozen_config()
print(f"  {frozen.version} parent={frozen.parent}")
print(f"  profile={frozen.selected_profile} sha256={frozen.sha256}")
PY

echo "[3/4] 冻结产物完整 SHA-256"
"$PY" - <<'PY'
from src.experiments.reproduce_main import verify_inputs
from src.trust_engine.config_loader import load_frozen_config
checked = verify_inputs(load_frozen_config())
assert checked and all(item["verified"] for item in checked.values())
print(f"  {len(checked)} 个冻结产物全部匹配")
PY

echo "[4/4] A 单元测试（排除 B 的 web 测试）"
"$PY" -m pytest src/trust_engine/tests/ \
  --ignore=src/trust_engine/tests/test_web_analysis.py -q

echo ""
echo "✓ A smoke test 通过"
