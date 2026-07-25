"""P1 data-quality risk evidence.

The thresholds are provisional ``heuristic_v0.1`` rules from the P1 task card.
They must be calibrated with labelled OBS data before being treated as
domain-wide standards.
"""

from src.trust_engine.schema import EvidenceScore, EvidenceStatus, QualityReport


HEURISTIC_VERSION = "heuristic_v0.1"


def evaluate_data_evidence(report: QualityReport) -> EvidenceScore:
    """Return data-risk evidence without making a routing decision."""

    risk_score = 0
    reasons = []

    required_channels = set(report.required_channels_for_task)
    available_channels = set(report.available_channels)
    missing_required_count = len(required_channels - available_channels)

    if missing_required_count >= 2:
        risk_score += 20
        reasons.append("CHANNEL_MULTI_MISSING")
    elif missing_required_count == 1:
        risk_score += 12
        reasons.append("CHANNEL_MISSING")

    if report.gap_ratio > 0.10:
        risk_score += 15
        reasons.append("GAP_SEVERE")
    elif report.gap_ratio > 0.02:
        risk_score += 8
        reasons.append("GAP_MODERATE")

    if report.clipping_ratio > 0.10:
        risk_score += 10
        reasons.append("CLIPPING_SEVERE")
    elif report.clipping_ratio > 0.02:
        risk_score += 5
        reasons.append("CLIPPING_MODERATE")

    if report.snr_db is None:
        reasons.append("SNR_UNAVAILABLE")
        return EvidenceScore(
            score=None,
            reasons=reasons,
            status=EvidenceStatus.INSUFFICIENT.value,
            source=report.source,
            version=HEURISTIC_VERSION,
        )

    if report.snr_db < 3.0:
        risk_score += 15
        reasons.append("LOW_SIGNAL")
    elif report.snr_db < 8.0:
        risk_score += 8
        reasons.append("MODERATE_SIGNAL")

    if not reasons:
        reasons.append("DATA_QUALITY_OK")

    return EvidenceScore(
        score=min(risk_score, 30),
        reasons=reasons,
        status=EvidenceStatus.AVAILABLE.value,
        source=report.source,
        version=HEURISTIC_VERSION,
    )
