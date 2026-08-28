"""random_baseline.py 单元测试 (纯统计, 不加载模型)."""

import numpy as np

from src.experiments.random_baseline import (
    evaluate_at_p,
    load_eval_records,
    verdict,
)


def _record(p=10.0, s=15.0):
    return {
        "sample_id": "X1",
        "truth_p_s": 10.0,
        "truth_s_s": 15.0,
        "predictions": {
            "OBSTransformer": {"P_pick": p, "S_pick": s, "confidence": 0.9}
        },
    }


def test_verdict_correct():
    assert verdict(_record(10.2, 15.5)) == "correct"  # 容差内


def test_verdict_wrong():
    assert verdict(_record(20.0, 15.0)) == "wrong"     # P 超差


def test_verdict_reject_when_missing_pick():
    record = _record()
    record["predictions"]["OBSTransformer"]["P_pick"] = None
    assert verdict(record) == "reject"


def test_load_eval_records_has_411_truth_complete():
    records = load_eval_records()
    assert len(records) == 411
    assert all(r["truth_p_s"] is not None and r["truth_s_s"] is not None for r in records)


def test_evaluate_at_p_deterministic():
    records = [_record(10.0, 15.0) for _ in range(50)]
    a = evaluate_at_p(records, p=0.5, seed=7)
    b = evaluate_at_p(records, p=0.5, seed=7)
    assert a == b
    assert 0.0 <= a["coverage_pct"] <= 100.0
    assert a["unsafe_output_rate_pct"] == 0.0  # 全部 correct
