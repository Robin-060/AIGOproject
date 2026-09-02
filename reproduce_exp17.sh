#!/usr/bin/env bash
# reproduce_exp17.sh — EXP17 一键复现入口 (基线: semifinal_v1.5.1-bugfix)
#
# 串联 (任何一步失败即整体退出非零):
#   [0] v1.5.1 默认路径对账 — 差异必须为 0 (证明 EXP17 未改写冻结主链)
#   [1] EXP17-A Consensus Route — 重跑并落盘 main_results_exp17_A.csv + exp17_summary_A.json
#   [2] 配对 station-cluster bootstrap — Gate c2 唯一数字源 (paired_bootstrap_A.json, seed 42 × 1000)
#   [3] R1 robustness 核验 — 只核验冻结裁决记录, 不重算 (R1 JSON 为冻结产物)
#   [4] 核心数字核验 — 54.13% / 5.51% / 94.26% / Δ+0.92pp / upper95 +2.24pp / c1-c4 裁决
#   [5] 只读终检 — scripts/verify_exp17_evidence.py (B 的 release check)
#
# 全程使用冻结预测, 不运行模型推理。核验以数值对账为准, 不比较文件字节 (行尾规范跨平台)。
# 统一结论 (全链通过后输出): Coverage recovery supported; safety non-inferiority inconclusive.
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

echo "=================================================="
echo "[0] v1.5.1 默认路径对账 (EXP17 开关关闭, 差异必须为 0)"
echo "=================================================="
"$PY" - <<'PYEOF'
import sys
from pathlib import Path
sys.path.insert(0, str(Path('.').resolve()))
import warnings
warnings.filterwarnings("ignore")
from src.experiments.exp17_policy_refinement import chain_rows, baseline_parity_check
rows, _frozen = chain_rows(None)
diffs, n_ref = baseline_parity_check(rows, Path("results/main_results.csv"))
print(f"对账: 参照 {n_ref} 单元, 差异 {diffs} 个")
sys.exit(0 if diffs == 0 else 1)
PYEOF

echo ""
echo "=================================================="
echo "[1] EXP17-A Consensus Route (最终采用路径)"
echo "=================================================="
"$PY" -m src.experiments.exp17_policy_refinement --intervention A

echo ""
echo "=================================================="
echo "[2] 配对 cluster bootstrap (Gate c2 唯一数字源)"
echo "=================================================="
"$PY" -m src.experiments.paired_bootstrap --tag A

echo ""
echo "=================================================="
echo "[3] R1 robustness 核验 (只核验冻结裁决记录, 不重算)"
echo "=================================================="
"$PY" - <<'PYEOF'
import json
import sys
from pathlib import Path

import yaml

d = json.loads(Path("results/exp17_robustness_R1.json").read_text(encoding="utf-8"))
cfg = yaml.safe_load(Path("configs/semifinal_main.yaml").read_text(encoding="utf-8"))
tp = cfg["trust_engine"]["parameters"]

fail = []
if not str(d.get("verdict", "")).startswith("PASS"):
    fail.append("R1 verdict 非 PASS")
if not d.get("result_under_alternative", {}).get("identical_to_frozen_exp17_A"):
    fail.append("R1 与冻结 EXP17-A 不一致")
alt = d.get("alternative_value", {})
if alt != {"P": 0.34, "S": 0.51}:
    fail.append(f"替代值不符: {alt}")
p_s, s_s = tp["consensus_tolerance_p_s"], tp["consensus_tolerance_s_s"]
if (float(p_s), float(s_s)) != (0.34, 0.51):
    fail.append(f"运行路径容差非 0.34/0.51: {p_s}/{s_s}")
print("R1 verdict:", d["verdict"][:60], "| 替代值:", alt,
      "| 运行路径容差:", p_s, "/", s_s)
if fail:
    print("R1 核验失败:", "; ".join(fail))
    sys.exit(1)
print("R1 核验通过: 显式参数路径与冻结 EXP17-A 一致, 不依赖 legacy 0.30/0.50")
PYEOF

echo ""
echo "=================================================="
echo "[4] 核心数字核验 (54.13 / 5.51 / 94.26 / +0.92 / +2.24)"
echo "=================================================="
"$PY" - <<'PYEOF'
import json
import sys
from pathlib import Path


def check_round(got, want):
    return abs(float(got) - float(want)) < 0.005


fails = []
d = json.loads(Path("results/exp17_summary_A.json").read_text(encoding="utf-8"))
m, c = d["metrics"], d["criteria"]
checks = [
    ("Coverage", check_round(m["ceiling_pct"], 54.13)),
    ("Unsafe@50", check_round(m["unsafe_50_pct"], 5.51)),
    ("Interception@50预算", check_round(m["interception_50_budget_pct"], 94.26)),
    ("c1", c["c1_ceiling_ge_50"]["pass"] is True),
    ("c2", c["c2_non_inferiority_vs_voting_2pp"]["pass"] is False),
    ("c2 点估计", check_round(c["c2_non_inferiority_vs_voting_2pp"]["point_delta_pp"], 0.92)),
    ("c2 上界", check_round(c["c2_non_inferiority_vs_voting_2pp"]["one_sided_upper95_pp"], 2.24)),
    ("c3", c["c3_review_curve_preserved"]["pass"] is True),
    ("c4", c["c4_risk_bin_ordering_preserved"]["pass"] is True),
]
for name, ok in checks:
    print(f"  A {name}: {'✓' if ok else '✗'}")
    if not ok:
        fails.append(f"A {name}")

p = json.loads(Path("results/paired_bootstrap_A.json").read_text(encoding="utf-8"))
for name, got, want in (("paired 点估计", p["point_delta_pp"], 0.92),
                        ("paired 上界", p["one_sided_upper95_pp"], 2.24)):
    ok = check_round(got, want)
    print(f"  {name}: {got} {'✓' if ok else '✗'}")
    if not ok:
        fails.append(name)

if fails:
    print("\n✗ 核验失败:", "; ".join(fails))
    sys.exit(1)
print("\n✓ EXP17 复现与核验全部通过: 54.13% / 5.51% / 94.26% / Δ+0.92pp / upper95 +2.24pp")
print("  统一结论: Coverage recovery supported; safety non-inferiority inconclusive.")
PYEOF

echo ""
echo "=================================================="
echo "[5] 只读终检 (scripts/verify_exp17_evidence.py)"
echo "=================================================="
"$PY" scripts/verify_exp17_evidence.py

echo ""
echo "✓ reproduce_exp17.sh 完成 (v1.5.1 对账 0 差异 + 核心数字全部对上)"
