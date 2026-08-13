from src.trust_engine.model_suitability import evaluate_model_suitability
from src.trust_engine.schema import AdapterStatus, QualityReport, SampleMetadata

from src.trust_engine.tests.fixtures.demo_profiles import DEMO_MODEL_PROFILES


def make_quality(sampling_rate_hz=100.0):
    return QualityReport(
        available_channels=["Z", "N", "E"],
        missing_channels=["H"],
        required_channels_for_task=["Z", "N", "E"],
        sampling_rate_hz=sampling_rate_hz,
        gap_ratio=0.0,
        clipping_ratio=0.0,
        snr_db=10.0,
        source="SIMULATED_FIXTURE",
    )


def make_sample():
    return SampleMetadata(
        sample_id="demo-sample",
        preprocessing_version="prep-v1",
    )


def make_adapter_statuses(phasenet_succeeded=True):
    return [
        AdapterStatus(
            model_name="PhaseNet",
            loaded=True,
            run_succeeded=phasenet_succeeded,
            output_comparable=True,
        ),
        AdapterStatus(
            model_name="PickBlue",
            loaded=True,
            run_succeeded=True,
            output_comparable=True,
        ),
    ]


def result_by_model():
    results = evaluate_model_suitability(
        make_sample(),
        make_quality(),
        DEMO_MODEL_PROFILES,
        make_adapter_statuses(),
    )
    return {result.model_name: result for result in results}


def test_zne_demo_data_keeps_phasenet_eligible():
    assert result_by_model()["PhaseNet"].eligible is True


def test_demo_pickblue_requires_h_and_is_ineligible_without_it():
    result = result_by_model()["PickBlue"]
    assert result.eligible is False
    assert "MODEL_REQUIRED_CHANNEL_MISSING" in result.reasons


def test_unsupported_sampling_without_resampling_is_ineligible():
    results = evaluate_model_suitability(
        make_sample(),
        make_quality(sampling_rate_hz=50.0),
        [DEMO_MODEL_PROFILES[0]],
        make_adapter_statuses(),
    )
    assert results[0].eligible is False
    assert "MODEL_SAMPLING_RATE_INCOMPATIBLE" in results[0].reasons


def test_adapter_failure_is_ineligible():
    results = evaluate_model_suitability(
        make_sample(),
        make_quality(),
        [DEMO_MODEL_PROFILES[0]],
        make_adapter_statuses(phasenet_succeeded=False),
    )
    assert results[0].eligible is False
    assert "MODEL_ADAPTER_UNAVAILABLE" in results[0].reasons


def test_demo_profile_is_explicitly_marked_demo_only():
    assert "MODEL_PROFILE_DEMO_ONLY" in result_by_model()["PhaseNet"].reasons
