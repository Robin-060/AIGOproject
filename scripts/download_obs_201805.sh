#!/bin/sh
set -eu

root_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
data_dir="$root_dir/data/seisbench/obs"
base_url="https://seisbench.gfz.de/mirror/datasets/obs"

mkdir -p "$data_dir"
curl --fail --location --retry 8 --retry-all-errors --continue-at - \
  "$base_url/metadata201805.csv" \
  --output "$data_dir/metadata201805.csv"
curl --fail --location --retry 8 --retry-all-errors --continue-at - \
  "$base_url/waveforms201805.hdf5" \
  --output "$data_dir/waveforms201805.hdf5"

echo "OBS chunk 201805 downloaded to $data_dir"
