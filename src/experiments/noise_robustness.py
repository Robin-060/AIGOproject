"""Four-level noise robustness benchmark for three selection methods.

Without ``--input``, the script runs a deterministic synthetic stress benchmark
with 20 erroneous picks at each noise level. An input CSV can replace those
benchmark outcomes once P1 supplies real model-run results.

Expected input columns:
    sample_id,noise_level,single_model,highest_confidence,trust_layer

The three method columns contain 1 when the erroneous pick was intercepted and
0 when it escaped.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Dict, Iterable, List


ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT / "docs" / "experiments"
METHODS = ("single_model", "highest_confidence", "trust_layer")
METHOD_LABELS = {
    "single_model": "Single model",
    "highest_confidence": "Highest confidence",
    "trust_layer": "Trust Layer",
}
LEVELS = ("L0", "L1", "L2", "L3")

# Fixed counts out of 20. These are a demo benchmark, not measured model output.
BENCHMARK_INTERCEPT_COUNTS = {
    "L0": {"single_model": 3, "highest_confidence": 2, "trust_layer": 6},
    "L1": {"single_model": 5, "highest_confidence": 4, "trust_layer": 11},
    "L2": {"single_model": 7, "highest_confidence": 7, "trust_layer": 14},
    "L3": {"single_model": 9, "highest_confidence": 10, "trust_layer": 16},
}


def build_demo_records() -> List[Dict[str, str]]:
    records = []
    for level in LEVELS:
        for index in range(20):
            row = {"sample_id": f"demo_{level}_{index:02d}", "noise_level": level}
            for method in METHODS:
                row[method] = "1" if index < BENCHMARK_INTERCEPT_COUNTS[level][method] else "0"
            records.append(row)
    return records


def load_records(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        records = list(csv.DictReader(handle))
    required = {"sample_id", "noise_level", *METHODS}
    missing = required - set(records[0] if records else [])
    if missing:
        raise ValueError(f"Input CSV missing column(s): {', '.join(sorted(missing))}")
    return records


def summarize(records: Iterable[Dict[str, str]]) -> List[Dict[str, object]]:
    records = list(records)
    summary = []
    for level in LEVELS:
        level_rows = [row for row in records if row["noise_level"] == level]
        if len(level_rows) != 20:
            raise ValueError(f"{level} must contain exactly 20 rows; found {len(level_rows)}")
        for method in METHODS:
            values = [int(row[method]) for row in level_rows]
            if any(value not in (0, 1) for value in values):
                raise ValueError(f"{method} values must be 0 or 1")
            intercepted = sum(values)
            summary.append(
                {
                    "noise_level": level,
                    "method": method,
                    "intercepted": intercepted,
                    "total": len(values),
                    "interception_rate": intercepted / len(values),
                }
            )
    return summary


def write_csv(path: Path, rows: List[Dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def plot(summary: List[Dict[str, object]], path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    colors = {
        "single_model": "#64748b",
        "highest_confidence": "#f59e0b",
        "trust_layer": "#0f766e",
    }
    markers = {"single_model": "o", "highest_confidence": "s", "trust_layer": "D"}

    figure, axis = plt.subplots(figsize=(9, 5.5))
    for method in METHODS:
        rows = [row for row in summary if row["method"] == method]
        rates = [float(row["interception_rate"]) * 100 for row in rows]
        axis.plot(
            LEVELS,
            rates,
            label=METHOD_LABELS[method],
            color=colors[method],
            marker=markers[method],
            linewidth=2.5,
            markersize=7,
        )
        for x, rate in zip(LEVELS, rates):
            axis.annotate(f"{rate:.0f}%", (x, rate), xytext=(0, 7), textcoords="offset points", ha="center", fontsize=8)

    axis.set_title("Noise Robustness: Error Interception Rate")
    axis.set_xlabel("Noise level")
    axis.set_ylabel("Interception rate (%)")
    axis.set_ylim(0, 100)
    axis.grid(axis="y", alpha=0.25)
    axis.legend(loc="upper left")
    figure.tight_layout()
    figure.savefig(path, dpi=200)
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, help="P1 outcome CSV; omit for demo benchmark")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()

    records = load_records(args.input) if args.input else build_demo_records()
    summary = summarize(records)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    # Keep demo artefacts separate from the formal SeisBench experiment so a
    # quick smoke run cannot overwrite the evidence used in the P3 report.
    write_csv(args.output_dir / "noise_records_demo.csv", records)
    write_csv(args.output_dir / "noise_summary_demo.csv", summary)
    plot(summary, args.output_dir / "noise_curve_demo.png")

    source = str(args.input) if args.input else "deterministic demo benchmark"
    print(f"Source: {source}")
    for row in summary:
        print(
            f"{row['noise_level']} {METHOD_LABELS[str(row['method'])]}: "
            f"{float(row['interception_rate']):.0%}"
        )


if __name__ == "__main__":
    main()
