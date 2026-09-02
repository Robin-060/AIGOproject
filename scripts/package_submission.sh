#!/usr/bin/env bash
set -euo pipefail

release_tag="${1:-goai-2026-final-v3}"
output_dir="${2:-dist}"
archive_name="OBS_Trust_Engine_GOAI_2026_Semifinal_${release_tag}.zip"

git rev-parse --verify "refs/tags/${release_tag}" >/dev/null
mkdir -p "${output_dir}"

git archive --format=zip --prefix="OBS_Trust_Engine/" \
  --output="${output_dir}/${archive_name}" "${release_tag}"

unzip -t "${output_dir}/${archive_name}" >/dev/null

if unzip -Z1 "${output_dir}/${archive_name}" | grep -E \
  '(^|/)(\.git|\.pytest_cache|__pycache__|\.DS_Store)(/|$)' >/dev/null; then
  echo "ERROR: archive contains excluded development files" >&2
  exit 1
fi

mac_user_prefix="/""Users/"
sensitive_pattern="(${mac_user_prefix}|/home/[^/]+/|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{20,})"
if unzip -p "${output_dir}/${archive_name}" | strings | grep -E \
  "${sensitive_pattern}" >/dev/null; then
  echo "ERROR: archive contains a local path or token-like string" >&2
  exit 1
fi

if command -v shasum >/dev/null 2>&1; then
  shasum -a 256 "${output_dir}/${archive_name}" > "${output_dir}/${archive_name}.sha256"
else
  sha256sum "${output_dir}/${archive_name}" > "${output_dir}/${archive_name}.sha256"
fi

echo "Created ${output_dir}/${archive_name}"
