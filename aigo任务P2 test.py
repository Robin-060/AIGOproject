"""Tests for the isolated P2 physics evidence layer."""

import pytest

from src.trust_engine.physics import (
    PhysicsReason,
    check_final_pair,
    check_model_prediction,
)
from src.trust_engine.schema import (
    ModelPrediction,
    PhysicsStatus,
    TrustConfig,
)


TIME_BASIS = "WINDOW_SECONDS"


@pytest.fixture
def config() -> TrustConfig:
    """Return explicit physical thresholds for each test."""

    return TrustConfig(min_sp_s=0.1, max_sp_s=60.0)


def _prediction(
    phase: str,
    time_s: float,
    *,
    model_name: str = "PhaseNet",
    model_version: str = "1.0",
    time_basis: str = TIME_BASIS,
) -> ModelPrediction:
    """Build one normalized prediction."""

    return ModelPrediction(
        sample_id="sample-001",
        window_id="window-001",
        model_name=model_name,
        model_version=model_version,
        phase=phase,
        time_s=time_s,
        source_time_basis=time_basis,
        score=0.9,
    )


def test_normal_p_before_s_passes(config: TrustConfig) -> None:
    """A valid P/S interval must pass."""

    result = check_model_prediction(
        _prediction("P", 10.0),
        _prediction("S", 12.0),
        config,
    )

    assert result.target_type == "MODEL"
    assert result.target_id == "PhaseNet"
    assert result.status == PhysicsStatus.PASS.value
    assert result.hard_fail is False
    assert result.score == 0.0
    assert result.reasons == [PhysicsReason.OK.value]


def test_p_after_s_is_one_hard_failure(config: TrustConfig) -> None:
    """P>S must not also receive the short-interval penalty."""

    result = check_model_prediction(
        _prediction("P", 12.0),
        _prediction("S", 10.0),
        config,
    )

    assert result.status == PhysicsStatus.FAIL.value
    assert result.hard_fail is True
    assert result.score == 10.0
    assert result.reasons == [PhysicsReason.P_AFTER_S.value]
    assert PhysicsReason.SP_TOO_SHORT.value not in result.reasons


def test_p_equal_to_s_is_one_hard_failure(config: TrustConfig) -> None:
    """P=S belongs to the P-after-S hard-failure rule."""

    result = check_model_prediction(
        _prediction("P", 10.0),
        _prediction("S", 10.0),
        config,
    )

    assert result.status == PhysicsStatus.FAIL.value
    assert result.hard_fail is True
    assert result.score == 10.0
    assert result.reasons == [PhysicsReason.P_AFTER_S.value]


def test_missing_p_is_insufficient(config: TrustConfig) -> None:
    """A missing P pick must not be treated as zero-risk evidence."""

    result = check_model_prediction(
        None,
        _prediction("S", 12.0),
        config,
    )

    assert result.status == PhysicsStatus.INSUFFICIENT.value
    assert result.hard_fail is False
    assert result.score == 0.0
    assert result.reasons == [PhysicsReason.INSUFFICIENT_DATA.value]


def test_missing_s_is_insufficient(config: TrustConfig) -> None:
    """A missing S pick must not be treated as zero-risk evidence."""

    result = check_model_prediction(
        _prediction("P", 10.0),
        None,
        config,
    )

    assert result.status == PhysicsStatus.INSUFFICIENT.value
    assert result.hard_fail is False
    assert result.score == 0.0
    assert result.reasons == [PhysicsReason.INSUFFICIENT_DATA.value]


def test_sp_interval_below_configured_minimum(config: TrustConfig) -> None:
    """A positive interval below config.min_sp_s must fail softly."""

    result = check_model_prediction(
        _prediction("P", 10.0),
        _prediction("S", 10.05),
        config,
    )

    assert result.status == PhysicsStatus.FAIL.value
    assert result.hard_fail is False
    assert result.score == 5.0
    assert result.reasons == [PhysicsReason.SP_TOO_SHORT.value]


def test_sp_interval_above_configured_maximum(config: TrustConfig) -> None:
    """An interval above config.max_sp_s must fail softly."""

    result = check_model_prediction(
        _prediction("P", 10.0),
        _prediction("S", 70.01),
        config,
    )

    assert result.status == PhysicsStatus.FAIL.value
    assert result.hard_fail is False
    assert result.score == 5.0
    assert result.reasons == [PhysicsReason.SP_TOO_LONG.value]


def test_cross_model_pair_is_rejected(config: TrustConfig) -> None:
    """P2 must not splice P and S from different models."""

    result = check_model_prediction(
        _prediction("P", 10.0, model_name="PhaseNet"),
        _prediction("S", 12.0, model_name="PickBlue"),
        config,
    )

    assert result.status == PhysicsStatus.INSUFFICIENT.value
    assert result.hard_fail is True
    assert result.score == 0.0
    assert result.reasons == [PhysicsReason.CROSS_MODEL_PAIR.value]


def test_mismatched_time_basis_is_rejected(config: TrustConfig) -> None:
    """P2 must refuse comparison across different time bases."""

    result = check_model_prediction(
        _prediction("P", 10.0, time_basis="WINDOW_SECONDS"),
        _prediction("S", 12.0, time_basis="UTC_SECONDS"),
        config,
    )

    assert result.status == PhysicsStatus.INSUFFICIENT.value
    assert result.hard_fail is True
    assert result.score == 0.0
    assert result.reasons == [PhysicsReason.TIME_BASIS_MISMATCH.value]


def test_final_pair_uses_the_same_physics_rules(config: TrustConfig) -> None:
    """P4's final pair must be checked through the same P2 rule core."""

    result = check_final_pair(
        target_id="final-pair-001",
        p_time_s=20.0,
        s_time_s=23.0,
        p_source_models=("PhaseNet", "EQTransformer"),
        s_source_models=("EQTransformer", "PhaseNet"),
        p_time_basis=TIME_BASIS,
        s_time_basis=TIME_BASIS,
        config=config,
    )

    assert result.target_type == "FINAL_PAIR"
    assert result.target_id == "final-pair-001"
    assert result.status == PhysicsStatus.PASS.value
    assert result.hard_fail is False
    assert result.score == 0.0
    assert result.reasons == [PhysicsReason.OK.value]
