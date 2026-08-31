"""Load and validate the single frozen semifinal experiment configuration."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
from typing import Any

import yaml

from .schema import ModelProfile, TrustConfig


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = ROOT / "configs" / "semifinal_main.yaml"


def canonical_sha256(path: Path) -> str:
    """Hash text/binary content after normalising CRLF for cross-platform checks."""
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class FrozenExperimentConfig:
    path: Path
    raw: dict[str, Any]
    sha256: str

    @property
    def version(self) -> str:
        return str(self.raw["config_version"])

    @property
    def parent(self) -> str:
        return str(self.raw["parent_config"])

    @property
    def selected_profile(self) -> str:
        return str(self.raw["selected_profile"])

    @property
    def coverage_points(self) -> list[int]:
        return [int(value) for value in self.raw["equal_coverage"]["points"]]

    @property
    def random_seeds(self) -> list[int]:
        return [int(value) for value in self.raw["seeds"]["random_baseline_seeds"]]

    @property
    def bootstrap_seed(self) -> int:
        return int(self.raw["bootstrap"]["seed"])

    @property
    def bootstrap_replicates(self) -> int:
        return int(self.raw["bootstrap"]["replicates"])

    @property
    def declared_coverage_pct(self) -> float:
        return float(self.raw["bootstrap"]["declared_coverage_pct"])

    def trust_config(self, *, ranking_mode: bool = False) -> TrustConfig:
        params = dict(self.raw["trust_engine"]["parameters"])
        params["config_version"] = self.version
        params["config_hash"] = self.sha256
        params["parent_config"] = self.parent
        if ranking_mode:
            # Equal-coverage evaluation ranks all otherwise eligible outputs.
            # This is an evaluation knob, not a deployed automatic threshold.
            params["automatic_risk_threshold"] = 100.0
        return TrustConfig(**params)

    def model_profiles(self, profile_name: str | None = None) -> list[ModelProfile]:
        resolved = profile_name or self.selected_profile
        if resolved not in self.raw["model_profiles"]:
            raise ValueError(f"Unknown model profile: {resolved}")
        profile_block = self.raw["model_profiles"][resolved]
        profiles = []
        for model_name, values in profile_block.items():
            profiles.append(ModelProfile(model_name=model_name, **dict(values)))
        return profiles


def load_frozen_config(path: Path | str = DEFAULT_CONFIG_PATH) -> FrozenExperimentConfig:
    config_path = Path(path).resolve()
    if not config_path.is_file():
        raise FileNotFoundError(f"Frozen config missing: {config_path}")
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Frozen config must be a YAML mapping")

    required = (
        "config_version",
        "parent_config",
        "selected_profile",
        "experiment",
        "trust_engine",
        "model_profiles",
        "equal_coverage",
        "seeds",
        "bootstrap",
        "run_controls",
        "baseline_parameters",
        "correctness",
        "frozen_artifacts",
        "trajectory_history",
    )
    missing = [key for key in required if key not in raw]
    if missing:
        raise ValueError(f"Frozen config missing keys: {', '.join(missing)}")

    selected = str(raw["selected_profile"])
    if selected not in raw["model_profiles"]:
        raise ValueError(f"Unknown selected_profile: {selected}")
    frozen_profile = str(raw["experiment"].get("frozen_profile", ""))
    if frozen_profile != selected:
        raise ValueError(
            "experiment.frozen_profile must exactly match selected_profile"
        )
    if not raw["trust_engine"].get("parameters"):
        raise ValueError("trust_engine.parameters must be explicit and non-empty")
    if raw["run_controls"].get("profile_selection_during_reproduction") is not False:
        raise ValueError("Formal reproduction must not select profiles from results")
    hashes = raw["frozen_artifacts"]
    if not hashes or any(len(str(value)) != 64 for value in hashes.values()):
        raise ValueError("Every frozen artifact must have a full SHA-256")
    dataset = raw["dataset"]
    dataset_path = str(dataset["file"])
    dataset_digest = str(dataset["sha256"])
    if dataset_digest != hashes.get(dataset_path):
        raise ValueError(
            "dataset.sha256 must exactly match its full frozen_artifacts digest"
        )
    random_seeds = raw["seeds"]["random_baseline_seeds"]
    if len(random_seeds) != int(raw["seeds"]["random_baseline_repeats"]):
        raise ValueError("random_baseline_repeats must match the explicit seed list")

    frozen = FrozenExperimentConfig(
        path=config_path,
        raw=raw,
        sha256=canonical_sha256(config_path),
    )
    # Construct eagerly so unsupported/misspelled dataclass fields fail at startup.
    frozen.trust_config()
    frozen.model_profiles()
    return frozen
