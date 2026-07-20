"""
多模型证据 — Trust Layer 核心模块 (满分 40 分)

负责人: D
输入: List[ModelPrediction]
输出: (score: 0-40, reasons: [str])

核心逻辑:
  1. 按 phase 分组 (P 组、S 组)
  2. 组内计算最大时间差
  3. 判断一致程度: CONSENSUS / MILD / SEVERE / MISSING
  4. 打分
"""

from typing import List, Tuple
from src.schema import ModelPrediction


def evaluate_multi_model(
    predictions: List[ModelPrediction],
    p_tolerance_s: float = 0.3,
    s_tolerance_s: float = 0.5
) -> Tuple[float, List[str]]:
    """
    多模型交叉验证 (满分 40)

    Args:
        predictions: 所有模型的预测
        p_tolerance_s: P 波一致性容差 (秒)
        s_tolerance_s: S 波一致性容差 (秒)

    Returns:
        (score, reasons)
    """
    score = 0.0
    reasons = []

    # 1. 按震相分组
    p_preds = [p for p in predictions if p.phase == "P" and p.time_s > 0]
    s_preds = [p for p in predictions if p.phase == "S" and p.time_s > 0]

    # 2. 统计模型总数
    model_names = set(p.model for p in predictions)
    model_count = len(model_names) if model_names else 1

    # 3. P 波分歧判断
    p_result = _phase_disagreement(p_preds, model_count, "P", p_tolerance_s)
    score += p_result[0]
    reasons.extend(p_result[1])

    # 4. S 波分歧判断 (容差更大，严重阈值 2.0s)
    s_result = _phase_disagreement(s_preds, model_count, "S", s_tolerance_s, severe_threshold=2.0)
    score += s_result[0]
    reasons.extend(s_result[1])

    # 5. 有模型漏检但不是全漏
    total_picks = len(p_preds) + len(s_preds)
    max_possible = model_count * 2  # 每个模型最多 P+S
    if 0 < total_picks < max_possible:
        score += 10
        reasons.append("MODEL_MISSING_PICK")

    # 6. 全一致
    if not reasons:
        reasons.append("MODEL_CONSENSUS")

    return min(score, 40), reasons


def _phase_disagreement(
    preds: List[ModelPrediction],
    model_count: int,
    phase_name: str,
    tolerance_s: float,
    severe_threshold: float = 1.0
) -> Tuple[float, List[str]]:
    """
    判断同一震相的多模型分歧程度

    Args:
        preds: 该震相的所有预测
        model_count: 模型总数
        phase_name: "P" 或 "S"
        tolerance_s: 一致性容忍度
        severe_threshold: 严重分歧阈值

    Returns:
        (加分, 原因码列表)
    """
    # 全漏检
    if len(preds) == 0:
        return (15, [f"MODEL_ALL_MISSING_{phase_name}"])

    # 只有一个模型检出 → 无法判断一致性，但也算漏检
    if len(preds) == 1 and model_count > 1:
        return (10, [f"MODEL_MISSING_PICK_{phase_name}"])

    # 只有一个模型有输出 → 一致性就是一致的
    if len(preds) <= 1:
        return (0, [])

    # 计算最大时间差
    times = [p.time_s for p in preds]
    max_diff = max(times) - min(times)

    # 判断
    if max_diff <= tolerance_s:
        return (0, [])
    elif max_diff <= severe_threshold:
        return (8, [f"MODEL_MILD_DISAGREEMENT_{phase_name}"])
    else:
        return (20, [f"MODEL_DISAGREEMENT_{phase_name}"])
