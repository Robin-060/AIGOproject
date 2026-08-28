"""
随机决策 baseline — 官方点名参照系 (Random)

策略: 完全不看样本内容, 以固定概率 p 接受 (放行底层单模型 OBSTransformer 的输出),
      否则 ABSTAIN (转人工)。随机拒绝不会降低被接受子集的错误率——它与
      Trust Layer 的差距即"选择性拒绝"带来的真实收益。

协议: configs/semifinal_main.yaml (semifinal_v1.0)
  - 评估子集: P+S 真值完整的 411 条
  - 正确性: P 容差 0.5s, S 容差 1.0s (与所有 baseline 相同)
  - 多种子: 0..99 共 100 个, 报告均值 ± 标准差

用法:
    python -m src.experiments.random_baseline          # 输出 5 个 coverage 点结果
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
RECORDS_PATH = ROOT / "data" / "batch_calibration" / "records_all.json"

P_TOL = 0.5
S_TOL = 1.0
UNDERLYING_MODEL = "OBSTransformer"
SEEDS = list(range(100))
COVERAGE_POINTS = [50, 60, 70, 80, 90]


def load_eval_records() -> List[dict]:
    """加载 P+S 真值完整的评估子集 (n=411)."""
    records = json.loads(RECORDS_PATH.read_text(encoding="utf-8"))
    return [
        r for r in records
        if r.get("truth_p_s") is not None and r.get("truth_s_s") is not None
    ]


def verdict(record: dict) -> Optional[str]:
    """按冻结判定协议返回 correct / wrong / reject."""
    picks = record["predictions"].get(UNDERLYING_MODEL, {})
    p_time, s_time = picks.get("P_pick"), picks.get("S_pick")
    if p_time is None or s_time is None:
        return "reject"  # 底层模型无完整拾取, 没有可放行的输出
    p_ok = abs(p_time - record["truth_p_s"]) <= P_TOL
    s_ok = abs(s_time - record["truth_s_s"]) <= S_TOL
    return "correct" if (p_ok and s_ok) else "wrong"


def evaluate_at_p(records: List[dict], p: float, seed: int) -> Dict[str, float]:
    """单种子下: 以概率 p 接受, 统计 coverage / wrong / correct / reject."""
    rng = np.random.default_rng(seed)
    n = len(records)
    accepts = rng.random(n) < p
    correct = wrong = 0
    for accepted, record in zip(accepts, records):
        if not accepted:
            continue
        v = verdict(record)
        if v == "correct":
            correct += 1
        elif v == "wrong":
            wrong += 1
    auto = correct + wrong
    return {
        "p": p,
        "coverage_pct": 100.0 * auto / n,
        "unsafe_output_rate_pct": 100.0 * wrong / auto if auto else 0.0,
        "interception_pct": 0.0,  # 随机门不识别错误, 拦截率 = 拒绝比例
        "correct": correct,
        "wrong": wrong,
    }


def evaluate_across_seeds(records: List[dict], p: float,
                          seeds: List[int] = SEEDS) -> Dict[str, float]:
    """多种子统计, 返回均值 ± 标准差."""
    runs = [evaluate_at_p(records, p, seed) for seed in seeds]
    keys = ("coverage_pct", "unsafe_output_rate_pct")
    out: Dict[str, float] = {"p": p}
    for key in keys:
        values = np.array([run[key] for run in runs])
        out[key] = float(values.mean())
        out[f"{key}_std"] = float(values.std())
    return out


def find_p_for_coverage(records: List[dict], target_pct: float,
                        seeds: List[int] = SEEDS) -> float:
    """二分求 p, 使平均覆盖率对准目标点 (50/60/70/80/90%)."""
    low, high = 0.0, 1.0
    for _ in range(40):
        mid = (low + high) / 2
        cov = evaluate_across_seeds(records, mid, seeds)["coverage_pct"]
        if cov < target_pct:
            low = mid
        else:
            high = mid
    return (low + high) / 2


def main() -> None:
    records = load_eval_records()
    print(f"评估子集: {len(records)} 条 (P+S 真值完整) | "
          f"底层模型: {UNDERLYING_MODEL} | 种子: {len(SEEDS)} 个")
    print(f"{'目标Coverage':>12} {'调得p':>8} {'实际Coverage':>13} {'Unsafe±std':>12}")
    for target in COVERAGE_POINTS:
        p = find_p_for_coverage(records, target)
        stat = evaluate_across_seeds(records, p)
        print(f"{target:>10}% {p:>9.3f} {stat['coverage_pct']:>11.1f}% "
              f"{stat['unsafe_output_rate_pct']:>9.1f}%±{stat['unsafe_output_rate_pct_std']:.1f}")


if __name__ == "__main__":
    main()
