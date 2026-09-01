"""
Review Budget–Error Interception Curve (C 追加分析)

问题: 在固定"复核预算"下, 各策略能截获多少错误?
口径 (完全基于冻结物, 不重训模型 / 不重调 Trust / 不改变 DS):
  - 单元: 1306 个 (sample_id, phase), 错误定义与主实验一致
    (verdict in {"wrong", "no_pick"}, 共 746 个, 见 failure_raw.csv)
  - 四种策略按各自"可疑度"对全部单元排序, 前 k 个送人工复核:
      1. Random          — 100 种子平均 (期望 = 对角线)
      2. Model confidence— 1 - 该相位可用模型的最大置信度 (缺拾取 → 0, 排最后)
      3. Disagreement    — 该相位可用拾取的最大差 spread (s); <2 拾取 → 0
      4. Trust risk      — main_results.csv 冻结风险分 (v1.5.1)
  - 指标: 复核预算 b% → 截获错误率 (%) 与精确率 (%)
  - 附加: Trust 实际运行点 (review burden 54.36% 处) 标注在曲线上

输出:
  results/review_budget_curve.csv     (长表: 策略 × 预算点)
  results/review_budget_summary.json  (固定预算对比 + Trust 运行点)
  figures/review_budget_curve.png
  --holdout 模式: 仅在 holdout 分片 (260 单元, 冻结协议定位"一致性佐证")
  上重复同一对比, 输出 *_holdout.{csv,json,png} — 最小追加验证 (样本外一致性)

用法:
  python -m src.experiments.review_budget_curve            # 全量 (1306 单元)
  python -m src.experiments.review_budget_curve --holdout  # holdout 佐证
"""

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import warnings  # noqa: E402
warnings.filterwarnings("ignore")

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from src.experiments.phase_evaluation import (  # noqa: E402
    build_phase_units,
    load_records,
)
from src.trust_engine.config_loader import load_frozen_config  # noqa: E402

SWEEP_BUDGETS = list(range(0, 61))          # 1% 步长, 供曲线
TABLE_BUDGETS = [5, 10, 20, 30, 50]          # 固定预算对比表
RANDOM_SEEDS = 100
RANDOM_SEED = 0


def interception_at(suspicion, is_error, budget_pct):
    """按可疑度降序取前 budget_pct% 送审, 返回 (截获错误率%, 精确率%)."""
    n = len(suspicion)
    order = np.argsort(-suspicion, kind="stable")
    k = int(round(budget_pct / 100 * n))
    reviewed = order[:k]
    errors_total = int(is_error.sum())
    errors_found = int(is_error[reviewed].sum())
    interception = errors_found / errors_total * 100 if errors_total else 0.0
    precision = errors_found / k * 100 if k else 0.0
    return interception, precision


def random_interception_at(is_error, budget_pct, n_seeds=RANDOM_SEEDS):
    """Random 策略: n_seeds 个随机排序的平均截获率 (期望≈预算)."""
    n = len(is_error)
    k = int(round(budget_pct / 100 * n))
    values = []
    for seed in range(n_seeds):
        rng = np.random.default_rng(RANDOM_SEED + seed)
        order = rng.permutation(n)[:k]
        values.append(int(is_error[order].sum()))
    errors_total = int(is_error.sum())
    return (np.mean(values) / errors_total * 100 if errors_total else 0.0,
            np.mean(values) / k * 100 if k else 0.0)


def build_signals(split_filter=None):
    """返回 {strategy: suspicion 数组} 与 is_error 数组 (与 units 同序).

    split_filter: None=全部单元; "main"/"holdout"=仅该分片。
    """
    frozen = load_frozen_config()
    records = load_records()
    units = [u for u in build_phase_units(records) if u["primary_inclusion"]]
    record_map = {r["sample_id"]: r for r in records}

    trust_rows = list(csv.DictReader(
        open(ROOT / "results" / "main_results.csv", encoding="utf-8")))
    risk_map = {(r["sample_id"], r["phase"]): float(r["risk"])
                for r in trust_rows}
    verdict_map = {(r["sample_id"], r["phase"]): r["verdict"]
                   for r in trust_rows}
    split_map = {(r["sample_id"], r["phase"]): r["split"]
                 for r in trust_rows}
    if split_filter:
        units = [u for u in units
                 if split_map.get((u["sample_id"], u["phase"])) == split_filter]

    trust = np.zeros(len(units))
    conf = np.zeros(len(units))
    spread = np.zeros(len(units))
    is_error = np.zeros(len(units), dtype=bool)

    for i, u in enumerate(units):
        key = (u["sample_id"], u["phase"])
        trust[i] = risk_map.get(key, 50.0)
        is_error[i] = (verdict_map.get(key, "correct") in ("wrong", "no_pick"))

        rec = record_map[u["sample_id"]]
        picks = [(m, t) for m, t in u["predictions"].items() if t is not None]
        if picks:
            confs = [rec["predictions"][m].get("confidence") for m, _ in picks]
            confs = [c for c in confs if c is not None]
            conf[i] = 1.0 - max(confs) if confs else 0.0
        if len(picks) >= 2:
            times = [t for _, t in picks]
            spread[i] = max(times) - min(times)
    return {"Random": None, "ModelConf": conf, "Disagreement": spread,
            "TrustRisk": trust}, is_error, frozen


def main():
    split_filter = "holdout" if "--holdout" in sys.argv else None
    suffix = "_holdout" if split_filter else ""
    out_csv = ROOT / "results" / f"review_budget_curve{suffix}.csv"
    out_summary = ROOT / "results" / f"review_budget_summary{suffix}.json"
    out_fig = ROOT / "figures" / f"review_budget_curve{suffix}.png"

    frozen = load_frozen_config()
    signals, is_error, _frozen = build_signals(split_filter)
    n = len(is_error)
    errors_total = int(is_error.sum())
    scope = split_filter or "all"
    print(f"单元 {n} | 错误 (wrong+no_pick) {errors_total} | scope={scope} | "
          f"config {frozen.version} ({frozen.sha256[:12]}…)")

    rows = []
    for strategy, suspicion in signals.items():
        for b in SWEEP_BUDGETS:
            if strategy == "Random":
                inter, prec = random_interception_at(is_error, b)
            else:
                inter, prec = interception_at(suspicion, is_error, b)
            rows.append({
                "strategy": strategy, "review_budget_pct": b,
                "errors_intercepted": round(inter / 100 * errors_total, 1),
                "total_errors": errors_total,
                "interception_rate_pct": round(inter, 2),
                "precision_pct": round(prec, 2),
                "config_version": frozen.version,
                "config_hash": frozen.sha256,
            })
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"✓ {out_csv}")

    # 固定预算对比表
    table = {}
    for b in TABLE_BUDGETS:
        table[str(b)] = {}
        for strategy, suspicion in signals.items():
            if strategy == "Random":
                inter, _p = random_interception_at(is_error, b)
            else:
                inter, _p = interception_at(suspicion, is_error, b)
            table[str(b)][strategy] = round(inter, 1)
    print(f"\n{'复核预算':>8} " + "".join(f"{s:>18}" for s in signals))
    for b, vals in table.items():
        print(f"{b + '%':>8} " + "".join(f"{vals[s]:>17.1f}%" for s in signals))

    # Trust 实际运行点 (仅全量模式有意义: burden 来自主实验全单元口径)
    if split_filter is None:
        eq_rows = list(csv.DictReader(
            open(ROOT / "results" / "equal_coverage_trust.csv", encoding="utf-8")))
        burden = float(eq_rows[0]["review_burden_pct"])
        op_inter, op_prec = interception_at(signals["TrustRisk"], is_error, burden)
        print(f"\nTrust 实际运行点: 复核 {burden:.1f}% → 截获 {op_inter:.1f}% "
              f"(精确率 {op_prec:.1f}%)")
        op_point = {
            "review_burden_pct": round(burden, 2),
            "interception_rate_pct": round(op_inter, 2),
            "precision_pct": round(op_prec, 2),
        }
    else:
        burden, op_inter, op_prec = None, None, None
        op_point = None

    summary = {
        "config_version": frozen.version, "config_hash": frozen.sha256,
        "scope": scope, "n_units": n, "total_errors": errors_total,
        "table_budgets_pct": TABLE_BUDGETS,
        "fixed_budget_interception_pct": table,
        "trust_operating_point": op_point,
    }
    out_summary.write_text(json.dumps(summary, indent=2, ensure_ascii=False),
                           encoding="utf-8")
    print(f"✓ {out_summary}")

    # ── 图 ──
    colors = {"Random": "#9E9E9E", "ModelConf": "#FF9800",
              "Disagreement": "#795548", "TrustRisk": "#4CAF50"}
    labels = {"Random": "Random (100-seed mean)",
              "ModelConf": "Model confidence (1-max conf)",
              "Disagreement": "Disagreement (pick spread)",
              "TrustRisk": "Trust risk (v1.5.1)"}
    fig, ax = plt.subplots(figsize=(9, 6))
    ax.plot([0, 60], [0, 60], "--", color="#BBBBBB", label="diagonal")
    for strategy in ("Random", "ModelConf", "Disagreement", "TrustRisk"):
        ys = [float(r["interception_rate_pct"]) for r in rows
              if r["strategy"] == strategy]
        ax.plot(SWEEP_BUDGETS, ys, "-", label=labels[strategy],
                color=colors[strategy], linewidth=2)
    if burden is not None:
        ax.plot(burden, op_inter, "o", color="#4CAF50", markersize=10,
                label=f"Trust operating point ({burden:.0f}% review)")
    ax.set_xlabel("Review Budget (% of units sent to human review)")
    ax.set_ylabel("Error Interception Rate (% of all errors caught)")
    scope_label = " (holdout 260 units)" if split_filter else ""
    ax.set_title(f"Review Budget vs Error Interception "
                 f"({frozen.version}{scope_label})")
    ax.legend(fontsize=9)
    ax.grid(alpha=0.3)
    ax.set_xlim(0, 60)
    ax.set_ylim(0, 100)
    fig.tight_layout()
    fig.savefig(out_fig, dpi=150)
    plt.close(fig)
    print(f"✓ {out_fig}")


if __name__ == "__main__":
    main()
