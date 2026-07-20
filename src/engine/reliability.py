"""
可靠性引擎 — 汇总四类证据 → 风险评分 → 决策

负责人: D (主体) + B (router)
输入: QualityReport + List[ModelPrediction]
输出: ReliabilityResult
"""

from typing import List, Optional, Dict
from src.schema import (
    QualityReport, ModelPrediction, Evidence,
    ReliabilityResult, risk_level, action_for
)


# ═══════════════════════════════════════════════════════════
# 证据函数导入 (M1 阶段为占位，A/B 实现后替换)
# ═══════════════════════════════════════════════════════════

def _data_evidence(quality: QualityReport) -> tuple:
    """占位 — A 实现后替换为 evaluate_data_evidence()"""
    try:
        from src.evidence.data_evidence import evaluate_data_evidence
        return evaluate_data_evidence(quality)
    except ImportError:
        return _data_evidence_stub(quality)


def _single_model_evidence(predictions: List[ModelPrediction]) -> tuple:
    """占位 — B 实现后替换为 evaluate_single_model()"""
    try:
        from src.evidence.single_model import evaluate_single_model
        return evaluate_single_model(predictions)
    except ImportError:
        return _single_model_stub(predictions)


def _physics_evidence(predictions: List[ModelPrediction]) -> tuple:
    """占位 — B 实现后替换为 evaluate_physics()"""
    try:
        from src.evidence.physics import evaluate_physics
        return evaluate_physics(predictions)
    except ImportError:
        return _physics_stub(predictions)


# ═══════════════════════════════════════════════════════════
# 占位实现 (A/B 未交付时用，返回 0 分不影响联调)
# ═══════════════════════════════════════════════════════════

def _data_evidence_stub(quality: QualityReport) -> tuple:
    return (0, ["DATA_QUALITY_OK"])


def _single_model_stub(predictions: List[ModelPrediction]) -> tuple:
    return (0, ["CONFIDENCE_OK"])


def _physics_stub(predictions: List[ModelPrediction]) -> tuple:
    return (0, ["PHYSICS_OK"])


# ═══════════════════════════════════════════════════════════
# 路由函数 (B 负责，D 提供默认实现)
# ═══════════════════════════════════════════════════════════

def route(risk_score: float) -> tuple:
    """分数 → (等级, 动作)"""
    return risk_level(risk_score), action_for(risk_level(risk_score))


# ═══════════════════════════════════════════════════════════
# 主引擎
# ═══════════════════════════════════════════════════════════

def evaluate_reliability(
    quality: QualityReport,
    predictions: List[ModelPrediction],
    enable: Dict[str, bool] = None
) -> ReliabilityResult:
    """
    主入口: 综合四类证据 → 可靠性决策

    Args:
        quality: 数据质量报告
        predictions: 所有模型预测
        enable: 证据开关 {"data": True, "single": True, "multi": True, "physics": True}
                用于消融实验

    Returns:
        ReliabilityResult
    """
    if enable is None:
        enable = {"data": True, "single": True, "multi": True, "physics": True}

    # 1. 数据证据 (0-30) — A 负责
    if enable.get("data", True):
        d_score, d_reasons = _data_evidence(quality)
    else:
        d_score, d_reasons = 0, []

    # 2. 单模型证据 (0-15) — B 负责
    if enable.get("single", True):
        s_score, s_reasons = _single_model_evidence(predictions)
    else:
        s_score, s_reasons = 0, []

    # 3. 多模型证据 (0-40) — D 负责
    if enable.get("multi", True):
        from src.evidence.multi_model import evaluate_multi_model
        m_score, m_reasons = evaluate_multi_model(predictions)
    else:
        m_score, m_reasons = 0, []

    # 4. 物理证据 (0-15) — B 负责
    if enable.get("physics", True):
        p_score, p_reasons = _physics_evidence(predictions)
    else:
        p_score, p_reasons = 0, []

    # 5. 汇总
    total = d_score + s_score + m_score + p_score
    total = round(total, 1)

    # 6. 路由
    level, action = route(total)

    # 7. 原因码
    all_reasons = d_reasons + s_reasons + m_reasons + p_reasons

    # 8. 可读总结
    summary = _make_summary(total, quality, predictions, level, all_reasons)

    return ReliabilityResult(
        risk_score=total,
        risk_level=level,
        action=action,
        reason_codes=all_reasons,
        evidence_summary=summary,
    )


def _make_summary(
    total: float,
    quality: QualityReport,
    predictions: List[ModelPrediction],
    level: str,
    reasons: List[str]
) -> str:
    """生成人类可读的总结"""
    parts = [f"风险: {total:.0f}/100 ({level})"]

    # 数据质量
    parts.append(quality.summary())

    # 模型预测
    p_times = [f"{p.model}={p.time_s:.2f}s" for p in predictions
               if p.phase == "P" and p.time_s > 0]
    s_times = [f"{p.model}={p.time_s:.2f}s" for p in predictions
               if p.phase == "S" and p.time_s > 0]
    if p_times:
        parts.append(f"P: {', '.join(p_times)}")
    if s_times:
        parts.append(f"S: {', '.join(s_times)}")

    # 关键原因 (只取前 3 个)
    key_reasons = [r for r in reasons if "OK" not in r and "CONSENSUS" not in r]
    if key_reasons:
        parts.append("⚠ " + ", ".join(key_reasons[:3]))

    return " | ".join(parts)
