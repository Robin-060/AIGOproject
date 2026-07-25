from src.trust_engine.data_evidence import evaluate_data_evidence
from src.trust_engine.schema import EvidenceStatus, QualityReport


def make_report(**overrides):
    values = {
        "available_channels": ["Z", "N", "E"],
        "missing_channels": [],
        "required_channels_for_task": ["Z", "N", "E"],
        "sampling_rate_hz": 100.0,
        "gap_ratio": 0.0,
        "clipping_ratio": 0.0,
        "snr_db": 10.0,
        "source": "SIMULATED_FIXTURE",
    }
    values.update(overrides)
    return QualityReport(**values)


def test_normal_data_has_zero_risk():
    evidence = evaluate_data_evidence(make_report())
    assert evidence.score == 0
    assert evidence.reasons == ["DATA_QUALITY_OK"]


def test_one_required_channel_missing_adds_at_least_twelve():
    evidence = evaluate_data_evidence(
        make_report(available_channels=["Z", "N"], missing_channels=["E"])
    )
    assert evidence.score is not None and evidence.score >= 12
    assert "CHANNEL_MISSING" in evidence.reasons


def test_low_snr_adds_at_least_fifteen():
    evidence = evaluate_data_evidence(make_report(snr_db=2.9))
    assert evidence.score is not None and evidence.score >= 15
    assert "LOW_SIGNAL" in evidence.reasons


def test_severe_gap_does_not_also_add_moderate_gap():
    evidence = evaluate_data_evidence(make_report(gap_ratio=0.11))
    assert evidence.score == 15
    assert "GAP_SEVERE" in evidence.reasons
    assert "GAP_MODERATE" not in evidence.reasons


def test_combined_risk_is_capped_at_thirty():
    evidence = evaluate_data_evidence(
        make_report(
            available_channels=["Z"],
            missing_channels=["N", "E"],
            gap_ratio=0.11,
            clipping_ratio=0.11,
            snr_db=2.0,
        )
    )
    assert evidence.score == 30


def test_missing_snr_is_insufficient_not_all_ok():
    evidence = evaluate_data_evidence(make_report(snr_db=None))
    assert evidence.status == EvidenceStatus.INSUFFICIENT.value
    assert evidence.score is None
    assert "SNR_UNAVAILABLE" in evidence.reasons
    assert "DATA_QUALITY_OK" not in evidence.reasons
