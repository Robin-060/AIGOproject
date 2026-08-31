"""Regression tests for multiplicity-preserving cluster bootstrap statistics."""

import math

from src.experiments.bootstrap_analysis import (
    fixed_selection_stats,
    method_stats,
)


def _unit(sample_id, truth=0.0):
    return {
        "sample_id": sample_id,
        "phase": "P",
        "reference_time_s": truth,
    }


def test_method_stats_preserves_duplicate_cluster_occurrences():
    # A represents a station unit sampled twice; its error must count twice.
    units = [_unit("A"), _unit("A"), _unit("B")]
    trust = {
        ("A", "P"): {"verdict": "wrong", "risk": 0.1, "station": "STA"},
        ("B", "P"): {"verdict": "correct", "risk": 0.2, "station": "STB"},
    }
    voting_output = {("A", "P"): 2.0, ("B", "P"): 0.0}
    voting_risk = {("A", "P"): 0.1, ("B", "P"): 0.2}

    trust_unsafe, vote_unsafe = method_stats(
        units, trust, voting_output, voting_risk, 100.0
    )
    assert round(trust_unsafe, 6) == round(200 / 3, 6)
    assert round(vote_unsafe, 6) == round(200 / 3, 6)


def test_method_stats_marks_unequal_coverage_infeasible():
    units = [_unit("A"), _unit("B")]
    trust = {
        ("A", "P"): {"verdict": "wrong", "risk": 0.1, "station": "STA"},
        ("B", "P"): {"verdict": "no_pick", "risk": 0.2, "station": "STB"},
    }
    voting_output = {("A", "P"): 2.0, ("B", "P"): 0.0}
    voting_risk = {("A", "P"): 0.1, ("B", "P"): 0.2}
    trust_unsafe, vote_unsafe = method_stats(
        units, trust, voting_output, voting_risk, 100.0
    )
    assert math.isnan(trust_unsafe) and math.isnan(vote_unsafe)


def test_fixed_selection_bootstrap_counts_repeated_station_units():
    units = [_unit("A"), _unit("A"), _unit("B")]
    trust = {
        ("A", "P"): {"verdict": "wrong", "risk": 0.1, "station": "STA"},
        ("B", "P"): {"verdict": "correct", "risk": 0.2, "station": "STB"},
    }
    voting_output = {("A", "P"): 2.0, ("B", "P"): 0.0}
    t, v = fixed_selection_stats(
        units, trust, voting_output,
        trust_accept={("A", "P"), ("B", "P")},
        vote_accept={("A", "P"), ("B", "P")},
    )
    assert round(t, 6) == round(200 / 3, 6)
    assert round(v, 6) == round(200 / 3, 6)
