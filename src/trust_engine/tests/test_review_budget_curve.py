"""Review Budget 曲线纯函数测试 (v1.5.1).

只测纯函数不变量, 不依赖结果文件:
  - 可疑度与错误同序时截获率最大化
  - Random 100 种子平均 ≈ 预算 (对角线)
  - 截获率/精确率落在 [0, 100]
"""

import numpy as np

from src.experiments.review_budget_curve import (
    interception_at,
    random_interception_at,
)


def _n_errors(is_error):
    return int(np.asarray(is_error).sum())


def test_interception_maximised_when_sorted():
    n = 100
    is_error = np.zeros(n, dtype=bool)
    is_error[80:] = True            # 后 20 个是错误
    suspicion = np.arange(n)        # 与错误同序: 越靠后越可疑
    inter, prec = interception_at(suspicion, is_error, 20)
    assert abs(inter - 100.0) < 1e-9
    assert abs(prec - 100.0) < 1e-9
    # 反序 → 20% 预算一个错误都截不到
    inter_rev, _ = interception_at(-suspicion, is_error, 20)
    assert inter_rev == 0.0


def test_random_close_to_diagonal():
    n = 400
    is_error = np.zeros(n, dtype=bool)
    is_error[:80] = True            # 20% 错误率
    for budget in (5, 10, 30, 50):
        inter, _ = random_interception_at(is_error, budget, n_seeds=100)
        assert abs(inter - budget) < 3.0, (budget, inter)


def test_metrics_in_range():
    n = 50
    is_error = np.zeros(n, dtype=bool)
    is_error[::5] = True
    suspicion = np.random.default_rng(0).random(n)
    for budget in (0, 1, 10, 33, 50, 100):
        inter, prec = interception_at(suspicion, is_error, budget)
        assert 0.0 <= inter <= 100.0
        assert 0.0 <= prec <= 100.0
