"""random_baseline.py + phase_evaluation.py 单元测试 (纯统计, 不加载模型)."""

import numpy as np

from src.experiments.phase_evaluation import (
    build_phase_units,
    evaluate_units,
    load_records,
    phase_verdict,
)
from src.experiments.random_baseline import (
    evaluate_at_p,
    make_gate,
    underlying_output,
)


# ── phase_verdict ──

def test_phase_verdict_correct():
    assert phase_verdict(10.2, 10.0, "P") == "correct"   # 0.2 ≤ 0.5
    assert phase_verdict(15.5, 15.0, "S") == "correct"   # 0.5 ≤ 1.0


def test_phase_verdict_wrong():
    assert phase_verdict(11.0, 10.0, "P") == "wrong"     # 1.0 > 0.5
    assert phase_verdict(16.5, 15.0, "S") == "wrong"     # 1.5 > 1.0


def test_phase_verdict_no_pick():
    assert phase_verdict(None, 10.0, "P") == "no_pick"


# ── build_phase_units ──

def test_build_phase_units_n_eval_1306():
    units = build_phase_units(load_records())
    assert len(units) == 1790
    primary = [u for u in units if u["primary_inclusion"]]
    assert len(primary) == 1306
    assert sum(1 for u in primary if u["phase"] == "P") == 657
    assert sum(1 for u in primary if u["phase"] == "S") == 649


def test_build_phase_units_excluded_have_reason():
    units = build_phase_units(load_records())
    excluded = [u for u in units if not u["primary_inclusion"]]
    assert excluded
    assert all(u["exclusion_reason"] == "expected_event_unknown_pending_data_team"
               for u in excluded)


# ── evaluate_units / 随机门控 ──

def _fake_unit(pred, truth=10.0, phase="P"):
    return {
        "sample_id": "S1", "phase": phase, "reference_time_s": truth,
        "predictions": {"OBSTransformer": pred}, "primary_inclusion": True,
    }


def test_evaluate_units_ungated():
    units = [_fake_unit(10.1), _fake_unit(20.0), _fake_unit(None)]
    stats = evaluate_units(units, underlying_output, None)
    assert stats["n_eval"] == 3
    assert stats["auto"] == 2
    assert stats["auto_correct"] == 1 and stats["auto_wrong"] == 1
    assert stats["unsafe_output_rate"] == 0.5
    assert stats["coverage"] == 2 / 3


def test_make_gate_deterministic_and_samplified():
    units = [dict(_fake_unit(10.0), sample_id=f"S{i}") for i in range(100)]
    gate_a = make_gate(units, p=0.5, seed=7)
    gate_b = make_gate(units, p=0.5, seed=7)
    decisions_a = [gate_a(u) for u in units]
    decisions_b = [gate_b(u) for u in units]
    assert decisions_a == decisions_b
    assert 0.3 < np.mean(decisions_a) < 0.7  # 大样本下接近 p


def test_evaluate_at_p_seed_reproducible():
    units = build_phase_units(load_records())
    a = evaluate_at_p(units, p=0.5, seed=3)
    b = evaluate_at_p(units, p=0.5, seed=3)
    assert a["coverage"] == b["coverage"]
    assert a["unsafe_output_rate"] == b["unsafe_output_rate"]
