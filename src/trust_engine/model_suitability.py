"""P1 per-model data compatibility and candidate eligibility evidence."""

from typing import List

from src.trust_engine.schema import (
    AdapterStatus,
    ModelProfile,
    ModelSuitability,
    QualityReport,
    SampleMetadata,
    SuitabilityLevel,
)


def evaluate_model_suitability(
    sample: SampleMetadata,
    quality: QualityReport,
    profiles: List[ModelProfile],
    adapter_statuses: List[AdapterStatus],
) -> List[ModelSuitability]:
    """Return a separate suitability result for each supplied model profile."""

    status_by_model = {
        adapter_status.model_name: adapter_status
        for adapter_status in adapter_statuses
    }
    available_channels = set(quality.available_channels)
    results = []

    for profile in profiles:
        hard_reasons = []
        soft_reasons = []

        if set(profile.required_channels) - available_channels:
            hard_reasons.append("MODEL_REQUIRED_CHANNEL_MISSING")

        sampling_rate_supported = (
            quality.sampling_rate_hz in profile.accepted_sampling_rates_hz
        )
        traceable_resampling_available = (
            profile.resampling_supported
            and sample.resampling_applied
            and bool(sample.resampling_trace_id)
        )
        if not sampling_rate_supported and not traceable_resampling_available:
            hard_reasons.append("MODEL_SAMPLING_RATE_INCOMPATIBLE")

        if sample.preprocessing_version != profile.required_preprocessing_version:
            hard_reasons.append("MODEL_PREPROCESSING_INCOMPATIBLE")

        adapter_status = status_by_model.get(profile.model_name)
        if (
            adapter_status is None
            or not adapter_status.loaded
            or not adapter_status.run_succeeded
        ):
            hard_reasons.append("MODEL_ADAPTER_UNAVAILABLE")
        elif not adapter_status.output_comparable:
            hard_reasons.append("MODEL_OUTPUT_NOT_COMPARABLE")

        if set(profile.preferred_channels) - available_channels:
            soft_reasons.append("MODEL_PREFERRED_CHANNEL_MISSING")

        if not profile.validation_domain_known:
            soft_reasons.append("MODEL_VALIDATION_DOMAIN_UNKNOWN")

        if profile.profile_source == "DEMO_PROFILE":
            soft_reasons.append("MODEL_PROFILE_DEMO_ONLY")

        eligible = not hard_reasons
        if hard_reasons:
            suitability_level = SuitabilityLevel.INCOMPATIBLE.value
        elif soft_reasons:
            suitability_level = SuitabilityLevel.DEGRADED.value
        else:
            suitability_level = SuitabilityLevel.COMPATIBLE.value

        results.append(
            ModelSuitability(
                model_name=profile.model_name,
                eligible=eligible,
                suitability_level=suitability_level,
                penalty=0.0,
                reasons=hard_reasons + soft_reasons,
                profile_source=profile.profile_source,
            )
        )

    return results
