import json

from src.trust_engine.pipeline import load_from_mapping, run_pipeline


def _payload():
    profiles = {}
    predictions = []
    adapters = []
    for index, name in enumerate(("M1", "M2", "M3")):
        profiles[name] = {
            "model_name": name,
            "required_channels": ["Z", "N", "E"],
            "accepted_sampling_rates_hz": [100.0],
            "required_preprocessing_version": "obs_raw_v1",
            "validation_domain_known": True,
        }
        adapters.append(
            {"model_name": name, "loaded": True, "run_succeeded": True, "output_comparable": True}
        )
        predictions.extend(
            [
                {"sample_id": "sample", "window_id": "window", "model_name": name, "phase": "P", "time_s": 10.0 + index * 0.05, "score": 0.9, "preprocessing_version": "obs_raw_v1"},
                {"sample_id": "sample", "window_id": "window", "model_name": name, "phase": "S", "time_s": 20.0 + index * 0.05, "score": 0.9, "preprocessing_version": "obs_raw_v1"},
            ]
        )
    return {
        "sample_metadata": {"sample_id": "sample", "window_id": "window", "preprocessing_version": "obs_raw_v1"},
        "quality_report": {"available_channels": ["Z", "N", "E"], "sampling_rate_hz": 100.0, "snr_db": 20.0},
        "model_profiles": profiles,
        "model_predictions": predictions,
        "adapter_statuses": adapters,
    }


def test_pipeline_serializes_object_and_exposes_risk_breakdown():
    inputs = load_from_mapping(_payload())
    result = run_pipeline(**inputs)
    decoded = json.loads(result.to_json())

    assert isinstance(decoded, dict)
    assert decoded["evidence_status"] == "COMPLETE"
    assert decoded["phase_decisions"]["P"]["action"] == "FUSE"
    assert decoded["evidence_breakdown"]["P"] == {
        "data": 0.0,       # snr 20 → 数据证据无异常
        "single_model": 0.0,
        "multi_model": 0.0,
        "physics": 0.0,
        "total": 0.0,
    }
    assert decoded["overall_risk_score"] == 0.0
    assert decoded["config_version"] == "semifinal_v1.5.1-bugfix"
    assert len(decoded["config_hash"]) == 64
    assert decoded["parent_config"] == "semifinal_v1.5.1"


def test_missing_required_section_is_rejected():
    payload = _payload()
    del payload["quality_report"]
    try:
        load_from_mapping(payload)
    except ValueError as exc:
        assert "quality_report" in str(exc)
    else:
        raise AssertionError("Expected malformed payload to be rejected")
