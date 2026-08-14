import numpy as np

from src.experiments.seisbench_noise import (
    add_noise,
    select_sample_indices,
    stable_seed,
    summarize,
    wilson_interval,
)


def test_noise_is_deterministic_and_reaches_target_snr():
    waveform = np.stack(
        [np.sin(np.linspace(0, 20, 5000, dtype=np.float32) + shift) for shift in range(4)]
    )
    noisy_a = add_noise(waveform, "L2", "sample")
    noisy_b = add_noise(waveform, "L2", "sample")
    assert np.array_equal(noisy_a, noisy_b)
    for clean, noisy in zip(waveform, noisy_a):
        signal_rms = np.sqrt(np.mean(clean**2))
        noise_rms = np.sqrt(np.mean((noisy - clean) ** 2))
        snr = 20 * np.log10(signal_rms / noise_rms)
        assert abs(float(snr) - 5.0) < 0.01


def test_seed_changes_by_level_and_sample():
    assert stable_seed("a", "L1") != stable_seed("a", "L2")
    assert stable_seed("a", "L1") != stable_seed("b", "L1")


def test_wilson_interval_does_not_claim_certainty_for_twenty_of_twenty():
    lower, upper = wilson_interval(20, 20)
    assert 0.83 < lower < 0.84
    assert upper == 1.0


def test_summary_separates_coverage_accuracy_and_safety():
    records = []
    for level in ("L0", "L1", "L2", "L3"):
        for method in ("single_model", "highest_confidence", "trust_layer"):
            records.extend(
                [
                    {"noise_level": level, "method": method, "abstained": 0, "correct": 1, "unsafe_error": 0, "p_time_s": 1.0, "s_time_s": 3.0, "truth_p_s": 1.1, "truth_s_s": 3.2},
                    {"noise_level": level, "method": method, "abstained": 1, "correct": 0, "unsafe_error": 0, "p_time_s": None, "s_time_s": None, "truth_p_s": 1.1, "truth_s_s": 3.2},
                ]
            )
    row = summarize(records)[0]
    assert row["coverage_rate"] == 0.5
    assert row["selective_accuracy"] == 1.0
    assert row["safe_handling_rate"] == 1.0
    assert row["abstention_rate"] == 0.5
