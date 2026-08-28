"""
正确性容差敏感性分析 — C 契约 OPEN 项「correctness tolerance P/S」的证据材料

回答两个问题:
  1. 容差在常用档位间变动时, 各方法的不安全输出率结论是否稳定?
     (P: 0.2/0.3/0.5/1.0s × S: 0.5/1.0/2.0s)
  2. 正确拾取的残差分布集中在哪? (判断 0.5/1.0 是否远在标签噪声之上)

输出: results/tolerance_sensitivity.json + stdout 摘要表
用法: python -m src.experiments.tolerance_sensitivity
"""

import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RECORDS_PATH = ROOT / "data" / "batch_calibration" / "records_all.json"
OUT_PATH = ROOT / "results" / "tolerance_sensitivity.json"

P_GRID = [0.2, 0.3, 0.5, 1.0]
S_GRID = [0.5, 1.0, 2.0]


def load_eval_records():
    records = json.loads(RECORDS_PATH.read_text(encoding="utf-8"))
    return [r for r in records
            if r.get("truth_p_s") is not None and r.get("truth_s_s") is not None]


def verdict(record, p_time, s_time, p_tol, s_tol):
    """成对判定 (与冻结协议一致的口径): correct / wrong / reject."""
    if p_time is None or s_time is None:
        return "reject"
    p_ok = abs(p_time - record["truth_p_s"]) <= p_tol
    s_ok = abs(s_time - record["truth_s_s"]) <= s_tol
    return "correct" if (p_ok and s_ok) else "wrong"


# ── 各方法的拾取输出 ──

def pick_single_obst(record):
    v = record["predictions"].get("OBSTransformer", {})
    return v.get("P_pick"), v.get("S_pick")


def pick_max_conf(record):
    p_cands = [(m, v["P_pick"], v.get("confidence") or 0)
               for m, v in record["predictions"].items() if v.get("P_pick") is not None]
    s_cands = [(m, v["S_pick"], v.get("confidence") or 0)
               for m, v in record["predictions"].items() if v.get("S_pick") is not None]
    p_best = max(p_cands, key=lambda x: x[2])[1] if p_cands else None
    s_best = max(s_cands, key=lambda x: x[2])[1] if s_cands else None
    return p_best, s_best


def pick_vote(record):
    p_times = [v["P_pick"] for v in record["predictions"].values() if v.get("P_pick") is not None]
    s_times = [v["S_pick"] for v in record["predictions"].values() if v.get("S_pick") is not None]
    return ((statistics.median(p_times) if p_times else None),
            (statistics.median(s_times) if s_times else None))


def pick_trust(record):
    from src.experiments.real_baseline_final import trust_layer_pick
    return trust_layer_pick(record)


METHODS = {
    "Single(OBST)": pick_single_obst,
    "MaxConf": pick_max_conf,
    "Vote": pick_vote,
    "TrustLayer": pick_trust,
}


def evaluate_all(records, p_tol, s_tol):
    out = {}
    for name, fn in METHODS.items():
        stats = {"correct": 0, "wrong": 0, "reject": 0}
        for r in records:
            p, s = fn(r)
            stats[verdict(r, p, s, p_tol, s_tol)] += 1
        auto = stats["correct"] + stats["wrong"]
        stats["unsafe_rate"] = stats["wrong"] / auto if auto else None
        stats["coverage"] = auto / len(records)
        out[name] = stats
    return out


def residuals(records):
    """各模型 |pred - truth| 分布 (百分位)."""
    out = {}
    for model in ("PhaseNet", "PickBlue", "OBSTransformer"):
        for phase in ("P", "S"):
            diffs = []
            for r in records:
                pred = r["predictions"].get(model, {})
                truth = r[f"truth_{phase.lower()}_s"]
                value = pred.get(f"{phase}_pick")
                if truth is not None and value is not None:
                    diffs.append(abs(value - truth))
            diffs.sort()
            n = len(diffs)
            key = f"{model}-{phase}"
            out[key] = {
                "n": n,
                "p50": diffs[int(n * 0.50)] if n else None,
                "p90": diffs[int(n * 0.90)] if n else None,
                "p95": diffs[min(int(n * 0.95), n - 1)] if n else None,
            }
    return out


def main():
    records = load_eval_records()
    print(f"评估子集: {len(records)} 条")
    results = {"tolerance_grid": [], "residuals": residuals(records)}

    # 冻结档位
    frozen = (0.5, 1.0)
    print(f"\n各方法不安全输出率 (成对口径, n={len(records)}):")
    print(f"{'P_tol/S_tol':>10} | " + " | ".join(f"{m:>13}" for m in METHODS))
    for p_tol in P_GRID:
        for s_tol in S_GRID:
            stats = evaluate_all(records, p_tol, s_tol)
            row = {"p_tol": p_tol, "s_tol": s_tol, "methods": stats}
            results["tolerance_grid"].append(row)
            marker = " <- 冻结档" if (p_tol, s_tol) == frozen else ""
            cells = []
            for m in METHODS:
                u = stats[m]["unsafe_rate"]
                cells.append(f"{u*100:11.1f}%" if u is not None else f"{'—':>11}")
            print(f"{p_tol:4.1f}/{s_tol:4.1f} | " + " | ".join(cells) + marker)

    # 结论稳定性: 冻结档下 Trust 是否在各容差档都低于三个基线
    print("\n结论稳定性 (Trust 不安全率 < 各基线, 在全部 12 个容差档上):")
    for m in ("Single(OBST)", "MaxConf", "Vote"):
        holds = all(
            row["methods"]["TrustLayer"]["unsafe_rate"] is not None
            and row["methods"][m]["unsafe_rate"] is not None
            and row["methods"]["TrustLayer"]["unsafe_rate"] < row["methods"][m]["unsafe_rate"]
            for row in results["tolerance_grid"]
        )
        print(f"  Trust < {m:13s}: {'是 ✓' if holds else '否 ✗'}")

    print("\n残差分布 (|pred - truth| 百分位, 秒):")
    for key, stat in results["residuals"].items():
        if stat["n"] == 0:
            continue
        print(f"  {key:20s} n={stat['n']:3d}  p50={stat['p50']:.2f} "
              f"p90={stat['p90']:.2f} p95={stat['p95']:.2f}")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n✓ 已保存 {OUT_PATH}")


if __name__ == "__main__":
    main()
