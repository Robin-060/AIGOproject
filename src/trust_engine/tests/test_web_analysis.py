import json

from src.signal.io import WaveformBundle
from src.web.app import run_analysis, waveform_frame


def test_uploaded_json_reaches_complete_result(tmp_path):
    payload = {
        "sample_metadata": {"sample_id": "web-sample", "window_id": "window", "preprocessing_version": "obs_raw_v1"},
        "quality_report": {"available_channels": ["Z", "N", "E"], "sampling_rate_hz": 100.0, "snr_db": 10.0},
        "model_profiles": {},
        "model_predictions": [],
        "adapter_statuses": [],
    }
    for index, name in enumerate(("M1", "M2")):
        payload["model_profiles"][name] = {
            "model_name": name,
            "required_channels": ["Z", "N", "E"],
            "accepted_sampling_rates_hz": [100.0],
            "required_preprocessing_version": "obs_raw_v1",
            "validation_domain_known": True,
        }
        payload["adapter_statuses"].append(
            {"model_name": name, "loaded": True, "run_succeeded": True, "output_comparable": True}
        )
        for phase, base in (("P", 10.0), ("S", 20.0)):
            payload["model_predictions"].append(
                {"sample_id": "web-sample", "window_id": "window", "model_name": name, "phase": phase, "time_s": base + index * 0.05, "score": 0.9, "preprocessing_version": "obs_raw_v1"}
            )

    # Round-trip mirrors file-uploader JSON decoding.
    analysis = run_analysis(json.loads(json.dumps(payload)))

    assert analysis["result"]["sample_id"] == "web-sample"
    assert analysis["result"]["evidence_status"] == "COMPLETE"
    assert len(analysis["result"]["model_assessments"]) == 2
    assert "overall" in analysis["result"]["evidence_breakdown"]


def test_waveform_frame_downsamples_long_inputs():
    bundle = WaveformBundle([[0.0] * 12001], 100.0, ["Z"])
    frame = waveform_frame(bundle, max_points=1000)
    assert 900 <= len(frame) <= 1100
    assert set(frame.columns) == {"时间 (s)", "振幅", "通道"}
