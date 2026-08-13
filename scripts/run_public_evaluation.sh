#!/bin/sh
set -eu

root_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$root_dir"

python3 -m src.experiments.stalta_baseline
python3 -m src.experiments.seisbench_noise --summary-only
python3 -m src.experiments.cpu_benchmark --repeats 3

echo "Public-data evaluation outputs are in docs/experiments/."
