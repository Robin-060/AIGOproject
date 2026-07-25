"""P2 physics evidence checks for model predictions and final P/S pairs.

This module only evaluates physics evidence. It does not select models, fuse
picks, calculate overall reliability, or make routing/policy decisions.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional, Sequence

from src.trust_engine.schema import (
    ModelPrediction,
    PhysicsCheck,
    PhysicsStatus,
    TrustConfig,
)


class PhysicsReason(str, Enum):
    """Stable machine-readable reason codes emitted by P2."""

    OK = "PHYSICS_OK"
    INSUFFICIENT_DATA = "PHYSICS_INSUFFICIENT_DATA"
    P_AFTER_S = "PHYSICS_P_AFTER_S"
    SP_TOO_SHORT = "PHYSICS_SP_TOO_SHORT"
    SP_TOO_LONG = "PHYSICS_SP_TOO_LONG"
    CROSS_MODEL_PAIR = "PHYSICS_CROSS_MODEL_PAIR"
    TIME_BASIS_MISMATCH = "PHYSICS_TIME_BASIS_MISMATCH"
    PHASE_MISMATCH = "PHYSICS_PHASE_MISMATCH"


# Evidence weights follow the agreed P2 score budget. Physical thresholds are
# always read from TrustConfig and are never hard-coded in this module.
_P_AFTER_S_SCORE = 10.0
_SP_INTERVAL_SCORE = 5.0


def check_model_prediction(
    p_prediction: Optional[ModelPrediction],
    s_prediction: Optional[ModelPrediction],
    config: TrustConfig,
    *,
    target_id: Optional[str] = None,
) -> PhysicsCheck:
    """Check one model's already-associated P/S predictions.

    P and S must belong to the same model family and version and use the same
    time basis. The caller must resolve multiple picks and event association
    before invoking P2; this function never selects between candidates.
    """

    resolved_target_id = target_id or _model_target_id(
        p_prediction, s_prediction
    )

    if p_prediction is None or s_prediction is None:
        return _insufficient(
            target_type="MODEL",
            target_id=resolved_target_id,
            hard_fail=False,
            reason=PhysicsReason.INSUFFICIENT_DATA,
        )

    if p_prediction.phase.upper() != "P" or s_prediction.phase.upper() != "S":
        return _insufficient(
            target_type="MODEL",
            target_id=resolved_target_id,
            hard_fail=True,
            reason=PhysicsReason.PHASE_MISMATCH,
        )

    p_source = (p_prediction.model_name, p_prediction.model_version)
    s_source = (s_prediction.model_name, s_prediction.model_version)
    if p_source != s_source:
        return _insufficient(
            target_type="MODEL",
            target_id=resolved_target_id,
            hard_fail=True,
            reason=PhysicsReason.CROSS_MODEL_PAIR,
        )

    return _check_comparable_pair(
        target_type="MODEL",
        target_id=resolved_target_id,
        p_time_s=p_prediction.time_s,
        s_time_s=s_prediction.time_s,
        p_time_basis=p_prediction.source_time_basis,
        s_time_basis=s_prediction.source_time_basis,
        config=config,
    )


def check_final_pair(
    *,
    target_id: str,
    p_time_s: Optional[float],
    s_time_s: Optional[float],
    p_source_models: Sequence[str],
    s_source_models: Sequence[str],
    p_time_basis: Optional[str],
    s_time_basis: Optional[str],
    config: TrustConfig,
) -> PhysicsCheck:
    """Check the final P/S pair assembled by P4.

    Selected picks must come from the same model. Fused P and S picks are
    comparable only when both have the same non-empty contributor set. P2
    returns evidence and never changes P4's final action.
    """

    if p_time_s is None or s_time_s is None:
        return _insufficient(
            target_type="FINAL_PAIR",
            target_id=target_id,
            hard_fail=False,
            reason=PhysicsReason.INSUFFICIENT_DATA,
        )

    p_sources = frozenset(p_source_models)
    s_sources = frozenset(s_source_models)
    if not p_sources or p_sources != s_sources:
        return _insufficient(
            target_type="FINAL_PAIR",
            target_id=target_id,
            hard_fail=True,
            reason=PhysicsReason.CROSS_MODEL_PAIR,
        )

    return _check_comparable_pair(
        target_type="FINAL_PAIR",
        target_id=target_id,
        p_time_s=p_time_s,
        s_time_s=s_time_s,
        p_time_basis=p_time_basis,
        s_time_basis=s_time_basis,
        config=config,
    )


def _check_comparable_pair(
    *,
    target_type: str,
    target_id: str,
    p_time_s: float,
    s_time_s: float,
    p_time_basis: Optional[str],
    s_time_basis: Optional[str],
    config: TrustConfig,
) -> PhysicsCheck:
    """Apply mutually exclusive S-P rules to a comparable-source pair."""

    if config.min_sp_s >= config.max_sp_s:
        raise ValueError("TrustConfig.min_sp_s must be lower than max_sp_s")

    if (
        not p_time_basis
        or not s_time_basis
        or p_time_basis != s_time_basis
    ):
        return _insufficient(
            target_type=target_type,
            target_id=target_id,
            hard_fail=True,
            reason=PhysicsReason.TIME_BASIS_MISMATCH,
        )

    sp_interval_s = s_time_s - p_time_s

    # Return immediately so P>=S is never also penalized as SP_TOO_SHORT.
    if p_time_s >= s_time_s:
        return PhysicsCheck(
            target_type=target_type,
            target_id=target_id,
            status=PhysicsStatus.FAIL.value,
            hard_fail=True,
            score=_P_AFTER_S_SCORE,
            reasons=[PhysicsReason.P_AFTER_S.value],
        )

    if sp_interval_s < config.min_sp_s:
        return PhysicsCheck(
            target_type=target_type,
            target_id=target_id,
            status=PhysicsStatus.FAIL.value,
            hard_fail=False,
            score=_SP_INTERVAL_SCORE,
            reasons=[PhysicsReason.SP_TOO_SHORT.value],
        )

    if sp_interval_s > config.max_sp_s:
        return PhysicsCheck(
            target_type=target_type,
            target_id=target_id,
            status=PhysicsStatus.FAIL.value,
            hard_fail=False,
            score=_SP_INTERVAL_SCORE,
            reasons=[PhysicsReason.SP_TOO_LONG.value],
        )

    return PhysicsCheck(
        target_type=target_type,
        target_id=target_id,
        status=PhysicsStatus.PASS.value,
        hard_fail=False,
        score=0.0,
        reasons=[PhysicsReason.OK.value],
    )


def _insufficient(
    *,
    target_type: str,
    target_id: str,
    hard_fail: bool,
    reason: PhysicsReason,
) -> PhysicsCheck:
    """Build an unscored result when a valid comparison cannot be made."""

    return PhysicsCheck(
        target_type=target_type,
        target_id=target_id,
        status=PhysicsStatus.INSUFFICIENT.value,
        hard_fail=hard_fail,
        score=0.0,
        reasons=[reason.value],
    )


def _model_target_id(
    p_prediction: Optional[ModelPrediction],
    s_prediction: Optional[ModelPrediction],
) -> str:
    """Resolve the model identifier expected by P4's assessment map."""

    prediction = p_prediction or s_prediction
    return prediction.model_name if prediction is not None else "UNKNOWN_MODEL"
