"""
DS3 判定 — 模型 P/S 拾取时间分歧与真实错误风险的关联 (C 契约表格21)

口径 (semifinal_v1.4):
  - 单元: 1306 个 (sample_id, phase), 四模型冻结预测
  - 分歧 spread: 该相位可用拾取的最大差 (≥2 个拾取才可计算)
  - 真实错误: 没有任何模型给出容差内拾取 (最好模型也失败)
  - 分相位 P/S 分带报告错误率 + 95% 置信区间 + Spearman 相关
  - 负面解释条款: 无关联或仅单域存在 → 记边界

输出: results/ds3_disagreement.json
用法: python -m src.experiments.ds3_disagreement
"""

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import warnings  # noqa: E402
warnings.filterwarnings("ignore")

import numpy as np  # noqa: E402
from scipy.stats import spearmanr  # noqa: E402

from src.experiments.phase_evaluation import (  # noqa: E402
    PHASE_TOL,
    build_phase_units,
    load_records,
)

OUT_JSON = ROOT / "results" / "ds3_disagreement.json"
BANDS = [(0.0, 0.05), (0.05, 0.34), (0.34, 0.5), (0.5, 1.0), (1.0, 99.0)]


def wilson95(wrong, n):
    """Wilson 95% 置信区间 (比例)."""
    if n == 0:
        return (0.0, 0.0)
    z = 1.96
    p = wrong / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(center - half, 0.0), min(center + half, 1.0))


def main():
    units = [u for u in build_phase_units(load_records())
             if u["primary_inclusion"]]
    report = {}
    for phase in ("P", "S"):
        tol = PHASE_TOL[phase]
        data = []  # (spread, is_error)
        for u in units:
            if u["phase"] != phase:
                continue
            picks = [p for p in u["predictions"].values() if p is not None]
            if len(picks) < 2:
                continue
            spread = max(picks) - min(picks)
            any_correct = any(abs(p - u["reference_time_s"]) <= tol
                              for p in picks)
            data.append((spread, 0 if any_correct else 1))
        spreads = np.array([d[0] for d in data])
        errors = np.array([d[1] for d in data])
        rho, pval = spearmanr(spreads, errors)

        print(f"\n[{phase} 相] n={len(data)} (≥2 模型有拾取的单元)")
        print(f"{'spread 带':>12} {'n':>5} {'错误率':>8} {'95% CI':>16}")
        bands_out = []
        for lo, hi in BANDS:
            mask = (spreads >= lo) & (spreads < hi)
            n = int(mask.sum())
            if n == 0:
                continue
            wrong = int(errors[mask].sum())
            lo95, hi95 = wilson95(wrong, n)
            bands_out.append({"spread_band": f"{lo}-{hi}",
                              "n": n, "error_rate": round(wrong / n, 3),
                              "ci95": [round(lo95, 3), round(hi95, 3)]})
            print(f"{f'{lo}-{hi}':>12} {n:>5} {wrong / n:>7.1%} "
                  f"[{lo95:.1%}, {hi95:.1%}]")
        print(f"Spearman: rho={rho:.3f}, p={pval:.2e}")
        report[phase] = {
            "n": len(data), "spearman_rho": round(float(rho), 3),
            "spearman_p": float(pval), "bands": bands_out,
        }

    OUT_JSON.write_text(json.dumps(report, indent=2, ensure_ascii=False),
                        encoding="utf-8")
    print(f"\n✓ {OUT_JSON}")


if __name__ == "__main__":
    main()
