import numpy as np

from src.signal.io import WaveformBundle, read_waveform_bytes
from src.signal.preprocessing import PreprocessConfig, preprocess_waveform
from src.signal.stalta import classic_sta_lta, detect_triggers
from src.signal.triage import classify_event


def test_csv_reader_infers_sampling_rate_and_channels():
    text = "time_s,Z,N\n0.00,0,1\n0.01,1,2\n0.02,0,1\n"
    bundle = read_waveform_bytes(text.encode(), "wave.csv")
    assert bundle.data.shape == (2, 3)
    assert abs(bundle.sampling_rate_hz - 100.0) < 1e-6
    assert bundle.channels == ["Z", "N"]


def test_preprocessing_removes_offset_and_normalizes():
    rate = 100.0
    time = np.arange(4000) / rate
    values = 5.0 + 2.0 * time + np.sin(2 * np.pi * 5 * time)
    bundle = WaveformBundle(np.stack([values, values]), rate, ["Z", "N"])
    processed, report = preprocess_waveform(bundle, PreprocessConfig())
    assert processed.data.shape == bundle.data.shape
    assert abs(float(np.mean(processed.data))) < 0.05
    assert report["version"] == "obs_preprocess_v1"
    assert np.isfinite(processed.data).all()


def test_sta_lta_detects_energy_onset():
    rate = 100.0
    rng = np.random.default_rng(7)
    values = rng.normal(0, 0.01, 4000)
    values[2000:2050] += 2.0
    ratio = classic_sta_lta(values, rate)
    triggers = detect_triggers(ratio, rate)
    assert triggers
    assert any(19.5 <= trigger.onset_s <= 20.5 for trigger in triggers)


def test_rule_triage_is_explicit_and_conservative():
    accepted = classify_event(
        {"overall_risk_score": 12, "final_pair_status": "COMPLETE"},
        {"missing_channels": [], "gap_ratio": 0, "clipping_ratio": 0},
    )
    rejected = classify_event(
        {"overall_risk_score": 80, "final_pair_status": "FAILED"},
        {"missing_channels": ["Z"], "gap_ratio": 0, "clipping_ratio": 0},
    )
    assert accepted["label"] == "EARTHQUAKE_CANDIDATE"
    assert rejected["label"] == "LOW_QUALITY"
