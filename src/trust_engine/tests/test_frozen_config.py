"""Frozen configuration identity and executable-contract tests."""

from src.trust_engine.config_loader import load_frozen_config


def test_frozen_config_is_executable_and_profile_is_preselected():
    frozen = load_frozen_config()
    assert frozen.version == "semifinal_v1.5.1-bugfix"
    assert frozen.parent == "semifinal_v1.5.1"
    assert frozen.selected_profile == "hydrophone_v2"
    assert frozen.raw["experiment"]["frozen_profile"] == frozen.selected_profile
    assert frozen.raw["run_controls"]["profile_selection_during_reproduction"] is False
    assert {p.model_name for p in frozen.model_profiles()} == {
        "PhaseNet", "PickBlue", "OBSTransformer", "EQTransformer"
    }


def test_trust_config_carries_trace_identity():
    frozen = load_frozen_config()
    config = frozen.trust_config()
    assert config.config_version == frozen.version
    assert config.config_hash == frozen.sha256
    assert config.parent_config == frozen.parent
    assert config.automatic_risk_threshold == 10.0
    assert frozen.trust_config(ranking_mode=True).automatic_risk_threshold == 100.0


def test_all_frozen_artifacts_have_full_sha256_values():
    frozen = load_frozen_config()
    hashes = frozen.raw["frozen_artifacts"]
    assert hashes
    assert all(len(str(value)) == 64 for value in hashes.values())


def test_primary_dataset_hash_matches_frozen_artifact_registry():
    frozen = load_frozen_config()
    dataset = frozen.raw["dataset"]
    assert dataset["sha256"] == frozen.raw["frozen_artifacts"][dataset["file"]]
