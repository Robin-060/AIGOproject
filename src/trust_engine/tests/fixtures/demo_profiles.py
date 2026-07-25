"""Demo-only model profiles copied from the P1 task card."""

from src.trust_engine.schema import ModelProfile


DEMO_MODEL_PROFILES = [
    ModelProfile(
        model_name="PhaseNet",
        model_version="demo",
        model_family="phase_picker",
        required_channels=["Z", "N", "E"],
        preferred_channels=[],
        accepted_sampling_rates_hz=[100.0],
        resampling_supported=False,
        required_preprocessing_version="prep-v1",
        profile_source="DEMO_PROFILE",
    ),
    ModelProfile(
        model_name="PickBlue",
        model_version="demo",
        model_family="phase_picker",
        required_channels=["Z", "N", "E", "H"],
        preferred_channels=[],
        accepted_sampling_rates_hz=[100.0],
        resampling_supported=False,
        required_preprocessing_version="prep-v1",
        profile_source="DEMO_PROFILE",
    ),
]
