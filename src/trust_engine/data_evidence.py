"""P1 data-quality risk evidence.

两套罚分 (默认 = 注入故障校准, 候选 = 自然故障校准, 见 ds4_natural_hazard.py):
    fault                injected rate → score     natural rate → score
    channel_missing      28.6% → 8.6               5.0% → 1.5
    clipping             35.8% → 10.7              0.0% → 0.0
    gap                  32.8% → 9.9               9.5% → 2.8
    strong_noise         91.3% → 27.4              4.5% → 1.3

默认保留注入校准值 (历史口径); 自然校准候选经 validation 程序
(main/holdout, 预注册准则) 通过后由配置升版切换。
"""

from src.trust_engine.schema import EvidenceScore, EvidenceStatus, QualityReport

CALIBRATED_VERSION = "natural_v1.0"

CALIBRATED_PENALTIES = {
    "channel_missing": 8.6,
    "channel_multi_missing": 17.0,   # 8.6×2 近似
    "gap_severe": 9.9,
    "gap_moderate": 4.9,
    "clipping_severe": 10.7,
    "clipping_moderate": 5.4,
    "strong_noise": 27.4,
    "moderate_signal": 13.7,         # 强噪声半档
}

# DS4 自然危害率校准候选 (30 分预算 × 自然最好模型错误率)
NATURAL_PENALTIES = {
    "channel_missing": 1.5,
    "channel_multi_missing": 3.0,
    "gap_severe": 2.8,
    "gap_moderate": 1.4,
    "clipping_severe": 0.0,
    "clipping_moderate": 0.0,
    "strong_noise": 1.3,
    # 冻结值 1.0 (v1.4); ds4_natural_hazard.json 的 raw 候选分为 2.0 (30×rate),
    # 差异自冻结提交起即存在, 全部实验以本表为准 — 对账见
    # src/trust_engine/tests/test_frozen_parameters.py
    "moderate_signal": 1.0,
}

# 默认罚分: 自然校准 (DS4 validation 程序通过: main 4.2%→3.82%,
# holdout 12.31%→11.54%, 方向一致, 2026-08-29 冻结为 v1.4)
DEFAULT_PENALTIES = NATURAL_PENALTIES


def evaluate_data_evidence(report: QualityReport, penalties=None) -> EvidenceScore:
    """Return data-risk evidence without making a routing decision.

    penalties: 罚分表, 默认 DEFAULT_PENALTIES (自然校准 v1.4);
    CALIBRATED_PENALTIES (注入校准) 保留作历史对照/消融。
    """
    p = penalties if penalties is not None else DEFAULT_PENALTIES

    risk_score = 0
    reasons = []

    required_channels = set(report.required_channels_for_task)
    available_channels = set(report.available_channels)
    missing_required_count = len(required_channels - available_channels)

    if missing_required_count >= 2:
        risk_score += p["channel_multi_missing"]
        reasons.append("CHANNEL_MULTI_MISSING")
    elif missing_required_count == 1:
        risk_score += p["channel_missing"]
        reasons.append("CHANNEL_MISSING")

    if report.gap_ratio > 0.10:
        risk_score += p["gap_severe"]
        reasons.append("GAP_SEVERE")
    elif report.gap_ratio > 0.02:
        risk_score += p["gap_moderate"]
        reasons.append("GAP_MODERATE")

    if report.clipping_ratio > 0.10:
        risk_score += p["clipping_severe"]
        reasons.append("CLIPPING_SEVERE")
    elif report.clipping_ratio > 0.02:
        risk_score += p["clipping_moderate"]
        reasons.append("CLIPPING_MODERATE")

    if report.snr_db is None:
        reasons.append("SNR_UNAVAILABLE")
        return EvidenceScore(
            score=None,
            reasons=reasons,
            status=EvidenceStatus.INSUFFICIENT.value,
            source=report.source,
            version=CALIBRATED_VERSION,
        )

    if report.snr_db < 3.0:
        risk_score += p["strong_noise"]
        reasons.append("LOW_SIGNAL")
    elif report.snr_db < 8.0:
        risk_score += p["moderate_signal"]
        reasons.append("MODERATE_SIGNAL")

    if not reasons:
        reasons.append("DATA_QUALITY_OK")

    return EvidenceScore(
        score=min(risk_score, 30),
        reasons=reasons,
        status=EvidenceStatus.AVAILABLE.value,
        source=report.source,
        version=CALIBRATED_VERSION,
    )
