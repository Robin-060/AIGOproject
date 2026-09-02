#!/usr/bin/env bash
set -euo pipefail

release_tag="${1:-goai-2026-final-v3}"
output_dir="${2:-dist}"
archive_name="OBS_Trust_Engine_GOAI_2026_Semifinal_${release_tag}.zip"
archive_path="${output_dir}/${archive_name}"

git rev-parse --verify "refs/tags/${release_tag}" >/dev/null
mkdir -p "${output_dir}"

git archive --format=zip --prefix="OBS_Trust_Engine/" \
  --output="${archive_path}" "${release_tag}"

unzip -t "${archive_path}" >/dev/null

if unzip -Z1 "${archive_path}" | grep -E \
  '(^|/)(\.git|\.pytest_cache|__pycache__|\.DS_Store)(/|$)' >/dev/null; then
  echo "ERROR: archive contains excluded development files" >&2
  exit 1
fi

mac_user_prefix="/""Users/"
sensitive_pattern="(${mac_user_prefix}|/home/[^/]+/|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{20,})"
if unzip -p "${archive_path}" | strings | grep -E \
  "${sensitive_pattern}" >/dev/null; then
  echo "ERROR: archive contains a local path or token-like string" >&2
  exit 1
fi

# DOCX/PPTX 是嵌套 ZIP：再扫描其内部 XML，避免个人路径隐藏在讲者备注或文档属性中。
nested_dir="$(mktemp -d)"
trap 'rm -rf "${nested_dir}"' EXIT
while IFS= read -r office_entry; do
  [ -n "${office_entry}" ] || continue
  unzip -p "${archive_path}" "${office_entry}" > "${nested_dir}/office.zip"
  if unzip -p "${nested_dir}/office.zip" | strings | grep -E \
    "${sensitive_pattern}" >/dev/null; then
    echo "ERROR: ${office_entry} contains a local path or token-like string" >&2
    exit 1
  fi
done < <(unzip -Z1 "${archive_path}" | grep -Ei '\.(docx|pptx)$' || true)

# 提交包只保留一套最终交付件，并确保评委入口齐全。
for required_entry in \
  OBS_Trust_Engine/README.md \
  OBS_Trust_Engine/JUDGE_QUICKSTART.md \
  OBS_Trust_Engine/SUBMISSION_MANIFEST.md \
  OBS_Trust_Engine/environment_spec.md \
  OBS_Trust_Engine/THIRD_PARTY_NOTICES.md; do
  if ! unzip -Z1 "${archive_path}" | grep -Fx "${required_entry}" >/dev/null; then
    echo "ERROR: archive is missing ${required_entry}" >&2
    exit 1
  fi
done

docx_count="$(unzip -Z1 "${archive_path}" | grep -Ec '^OBS_Trust_Engine/docs/deliverables/[^/]+\.docx$' || true)"
pptx_count="$(unzip -Z1 "${archive_path}" | grep -Ec '^OBS_Trust_Engine/docs/deliverables/[^/]+\.pptx$' || true)"
if [ "${docx_count}" -ne 1 ] || [ "${pptx_count}" -ne 1 ]; then
  echo "ERROR: expected one final DOCX and one final PPTX (found ${docx_count}/${pptx_count})" >&2
  exit 1
fi

if command -v shasum >/dev/null 2>&1; then
  shasum -a 256 "${archive_path}" > "${archive_path}.sha256"
else
  sha256sum "${archive_path}" > "${archive_path}.sha256"
fi

echo "Created ${archive_path}"
