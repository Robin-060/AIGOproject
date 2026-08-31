"""confidence_calibration.py 单元测试 (v1.5)."""

from src.trust_engine.confidence_calibration import (
    CALIBRATED_CONFIDENCE_FLOOR,
    calibrated_prob,
    is_calibrated,
)


def test_calibrated_prob_in_range():
    for model in ("PickBlue", "OBSTransformer", "EQTransformer"):
        for raw in (0.0, 0.3, 0.5, 0.8, 1.0):
            p = calibrated_prob(model, raw)
            assert 0.0 <= p <= 1.0, (model, raw, p)


def test_calibrated_prob_monotonic():
    for model in ("PickBlue", "OBSTransformer", "EQTransformer"):
        values = [calibrated_prob(model, x) for x in (0.1, 0.5, 0.9)]
        assert values[0] < values[1] < values[2], model


def test_uncalibrated_model_returns_raw():
    # PhaseNet (geofon) 校准样本不足, 保留 raw
    assert calibrated_prob("PhaseNet", 0.85) == 0.85
    assert not is_calibrated("PhaseNet")


def test_none_score_returns_none():
    assert calibrated_prob("PickBlue", None) is None


def test_floor_in_valid_range():
    assert 0.0 < CALIBRATED_CONFIDENCE_FLOOR < 1.0
