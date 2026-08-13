"""Evaluate classic STA/LTA as an event-trigger baseline on SeisBench OBS."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.experiments.seisbench_noise import DATA_DIR, OUTPUT_DIR, load_dataset, select_sample_indices
from src.signal.io import WaveformBundle
from src.signal.preprocessing import PreprocessConfig, preprocess_waveform
from src.signal.stalta import classic_sta_lta, detect_triggers


def evaluate(dataset, indices, tolerance_s: float = 2.0):
    records = []
    for index in indices:
        waveform, metadata = dataset.get_sample(index, sampling_rate=100.0)
        bundle = WaveformBundle(waveform, 100.0, ["Z", "N", "E", "H"])
        processed, _ = preprocess_waveform(bundle, PreprocessConfig())
        ratio = classic_sta_lta(processed.data[0], 100.0)
        triggers = detect_triggers(ratio, 100.0)
        truth_p = float(metadata["trace_p_arrival_sample"]) / 100.0
        detected = bool(triggers)
        matched = any(abs(trigger.onset_s - truth_p) <= tolerance_s for trigger in triggers)
        false_triggers = sum(abs(trigger.onset_s - truth_p) > tolerance_s for trigger in triggers)
        records.append(
            {
                "sample_id": str(metadata["trace_name_original"]),
                "truth_p_s": truth_p,
                "detected": int(detected),
                "matched": int(matched),
                "missed": int(not matched),
                "false_triggers": false_triggers,
                "trigger_count": len(triggers),
                "first_trigger_s": triggers[0].onset_s if triggers else None,
            }
        )
    total = len(records)
    summary = {
        "scope": "positive event windows only",
        "total": total,
        "event_recall": sum(row["matched"] for row in records) / total,
        "miss_rate": sum(row["missed"] for row in records) / total,
        "false_triggers_per_window": sum(row["false_triggers"] for row in records) / total,
        "limitation": "False-positive rate requires labelled noise windows and is not claimed here.",
    }
    return records, summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--count", type=int, default=20)
    args = parser.parse_args()
    dataset = load_dataset(args.data_dir)
    records, summary = evaluate(dataset, select_sample_indices(dataset, args.count))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    import pandas as pd

    pd.DataFrame(records).to_csv(args.output_dir / "stalta_records.csv", index=False)
    (args.output_dir / "stalta_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
