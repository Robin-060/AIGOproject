"""Rule-based event triage for the Demo; this is not a trained classifier."""

from __future__ import annotations

from typing import Any, Dict


def classify_event(result: Dict[str, Any], quality: Dict[str, Any]) -> Dict[str, str]:
    risk = float(result.get("overall_risk_score", 100.0))
    pair = result.get("final_pair_status", "FAILED")
    poor_data = bool(quality.get("missing_channels")) or float(quality.get("gap_ratio", 0)) > 0.05 or float(quality.get("clipping_ratio", 0)) > 0.05

    # 从决策原因码判断拒绝的具体原因
    reason_codes = result.get("reason_codes", [])
    disagreement_reasons = {
        "MODEL_DISAGREEMENT_P", "MODEL_DISAGREEMENT_S",
        "NO_DECISIVE_EVIDENCE_BETWEEN_MODELS",
    }
    has_disagreement = any(r in disagreement_reasons for r in reason_codes)

    if pair == "COMPLETE" and risk <= 30:
        return {"label": "EARTHQUAKE_CANDIDATE", "display": "地震候选",
                "basis": "完整可信 P/S 对"}
    if poor_data:
        return {"label": "LOW_QUALITY", "display": "低质量数据",
                "basis": "缺通道、断点或削波触发质量门控"}
    if has_disagreement:
        return {"label": "MODEL_DISAGREEMENT", "display": "模型分歧待复核",
                "basis": "多模型拾取相互矛盾，拒绝自动放行"}
    return {"label": "REVIEW_REQUIRED", "display": "证据不足待复核",
            "basis": "缺少完整 P/S 对或其他必需证据，未作为地震自动放行"}
