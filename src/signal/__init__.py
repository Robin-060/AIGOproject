"""Waveform I/O, preprocessing, triggering, and transparent event triage."""

from src.signal.io import WaveformBundle, read_waveform, read_waveform_bytes
from src.signal.preprocessing import PreprocessConfig, preprocess_waveform
from src.signal.stalta import Trigger, classic_sta_lta, detect_triggers

__all__ = [
    "WaveformBundle",
    "PreprocessConfig",
    "Trigger",
    "classic_sta_lta",
    "detect_triggers",
    "preprocess_waveform",
    "read_waveform",
    "read_waveform_bytes",
]
