"""
随机决策 baseline — 官方点名参照系 (Random) — 相位级口径 (semifinal_v1.1)

策略: 完全不看样本内容, 按样本以固定概率 p 接受 (放行底层单模型
      OBSTransformer 的相位拾取), 否则 ABSTAIN (转人工)。
      随机拒绝不会降低被接受子集的错误率——它与 Trust Layer 的差距即
      "选择性拒绝"带来的真实收益。

协议: configs/semifinal_main.yaml (semifinal_v1.1)
  - 评估单位: (sample_id, phase), N_eval = 1306 (P 657 + S 649)
  - 正确性: 相位级容差 P 0.5s / S 1.0s (evaluation_protocol.md)
  - 多种子: 0..99 共 100 个, 报告均值 ± 标准差与 95% 区间

用法:
    python -m src.experiments.random_baseline          # 输出 5 个 coverage 点结果
"""

import numpy as np

from src.experiments.phase_evaluation import (
    build_phase_units,
    evaluate_units,
    load_records,
)

UNDERLYING_MODEL = "OBSTransformer"
SEEDS = list(range(100))
COVERAGE_POINTS = [50, 60, 70, 80, 90]


def make_gate(units: list, p: float, seed: int):
    """按样本掷币: 每样本以 p 接受, 两个相位单元共享同一样本的门控."""
    rng = np.random.default_rng(seed)
    sample_ids = sorted({unit["sample_id"] for unit in units
                         if unit["primary_inclusion"]})
    accepted = {sid: bool(rng.random() < p) for sid in sample_ids}
    return lambda unit: accepted[unit["sample_id"]]


def underlying_output(unit):
    return unit["predictions"][UNDERLYING_MODEL]


def evaluate_at_p(units: list, p: float, seed: int) -> dict:
    """单种子: 随机门控 + 相位级指标."""
    stats = evaluate_units(units, underlying_output, make_gate(units, p, seed))
    stats["p"] = p
    stats["seed"] = seed
    return stats


def evaluate_across_seeds(units: list, p: float,
                          seeds: list = SEEDS) -> dict:
    """多种子统计, 返回均值 ± 标准差与 95% 区间 (种子间变异)."""
    runs = [evaluate_at_p(units, p, seed) for seed in seeds]
    keys = ("coverage", "unsafe_output_rate")
    out = {"p": p, "n_seeds": len(seeds)}
    for key in keys:
        values = np.array([run[key] for run in runs])
        mean = float(values.mean())
        std = float(values.std())
        out[key] = mean
        out[f"{key}_std"] = std
        out[f"{key}_ci95_lo"] = mean - 1.96 * std
        out[f"{key}_ci95_hi"] = mean + 1.96 * std
    return out


def find_p_for_coverage(units: list, target_pct: float,
                        seeds: list = SEEDS) -> float:
    """二分求 p, 使平均覆盖率对准目标点 (50/60/70/80/90%)."""
    low, high = 0.0, 1.0
    for _ in range(40):
        mid = (low + high) / 2
        cov = evaluate_across_seeds(units, mid, seeds)["coverage"]
        if cov < target_pct / 100.0:
            low = mid
        else:
            high = mid
    return (low + high) / 2


def main() -> None:
    units = build_phase_units(load_records())
    n_eval = sum(1 for u in units if u["primary_inclusion"])
    print(f"评估单位: {n_eval} 个 (sample_id, phase) | "
          f"底层模型: {UNDERLYING_MODEL} | 种子: {len(SEEDS)} 个")
    print(f"{'目标Coverage':>12} {'调得p':>8} {'实际Coverage':>13} "
          f"{'Unsafe(95%CI)':>18}")
    for target in COVERAGE_POINTS:
        p = find_p_for_coverage(units, target)
        stat = evaluate_across_seeds(units, p)
        print(f"{target:>10}% {p:>9.3f} {stat['coverage']*100:>11.1f}% "
              f"{stat['unsafe_output_rate']*100:>7.1f}% "
              f"[{stat['unsafe_output_rate_ci95_lo']*100:.1f}, "
              f"{stat['unsafe_output_rate_ci95_hi']*100:.1f}]")


if __name__ == "__main__":
    main()
