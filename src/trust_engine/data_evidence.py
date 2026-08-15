"""P1 data-quality risk evidence.

The scoring is calibrated with fault-injection experiments on 895 real
labelled OBS samples (see src/calibrate/internal_score_calibration.py).
Calibrated scores are proportional to the model error rate each fault
induces:

    channel_missing: 28.6% error rate → 8.6
    clipping:        35.8% error rate → 10.7
    gap:             32.8% error rate → 9.9
    strong_noise:    91.3% error rate → 27.4

Caveat: calibrated against injected faults, not natural faults.
"""

from src.trust_engine.schema import EvidenceScore, EvidenceStatus, QualityReport


CALIBRATED_VERSION = "calibrated_v1.0"


def evaluate_data_evidence(report: QualityReport) -> EvidenceScore:
    """Return data-risk evidence without making a routing decision."""

    risk_score = 0
    reasons = []

    required_channels = set(report.required_channels_for_task)
    available_channels = set(report.available_channels)
    missing_required_count = len(required_channels - available_channels)

    if missing_required_count >= 2:
        risk_score += 17    # 校准: 双缺通道危害翻倍近似 (8.6×2)
        reasons.append("CHANNEL_MULTI_MISSING")
    elif missing_required_count == 1:
        risk_score += 8.6
        reasons.append("CHANNEL_MISSING")

    if report.gap_ratio > 0.10:
        risk_score += 9.9
        reasons.append("GAP_SEVERE")
    elif report.gap_ratio > 0.02:
        risk_score += 4.9
        reasons.append("GAP_MODERATE")

    if report.clipping_ratio > 0.10:
        risk_score += 10.7
        reasons.append("CLIPPING_SEVERE")
    elif report.clipping_ratio > 0.02:
        risk_score += 5.4
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
        risk_score += 27.4   # 校准: 强噪声危害 91.3%
        reasons.append("LOW_SIGNAL")
    elif report.snr_db < 8.0:
        risk_score += 13.7   # 校准: 中噪按半档
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
