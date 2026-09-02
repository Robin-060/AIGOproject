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

python3 - "${archive_path}" <<'PY'
import io
import re
import sys
import zipfile

archive_path = sys.argv[1]
root = "OBS_Trust_Engine/"
required = {
    root + "README.md",
    root + "JUDGE_QUICKSTART.md",
    root + "SUBMISSION_MANIFEST.md",
    root + "environment_spec.md",
    root + "THIRD_PARTY_NOTICES.md",
}
patterns = (
    re.compile(b"/" + b"Users/"),
    re.compile(b"/" + b"home/" + b"[^/]+/"),
    re.compile(b"AK" + b"IA" + b"[0-9A-Z]{16}"),
    re.compile(b"gh" + b"p_" + b"[A-Za-z0-9]{20,}"),
)


def scan_blob(label: str, blob: bytes) -> None:
    for pattern in patterns:
        if pattern.search(blob):
            raise SystemExit(f"ERROR: sensitive path/token pattern in {label}")


with zipfile.ZipFile(archive_path) as outer:
    corrupt = outer.testzip()
    if corrupt:
        raise SystemExit(f"ERROR: corrupt archive entry: {corrupt}")

    names = outer.namelist()
    missing = sorted(required.difference(names))
    if missing:
        raise SystemExit("ERROR: missing required entries: " + ", ".join(missing))

    excluded_parts = {".git", ".pytest_cache", "__pycache__", ".DS_Store"}
    for name in names:
        if excluded_parts.intersection(name.rstrip("/").split("/")):
            raise SystemExit(f"ERROR: excluded development entry: {name}")

    docx = [
        name for name in names
        if name.startswith(root + "docs/deliverables/")
        and "/" not in name[len(root + "docs/deliverables/"):]
        and name.lower().endswith(".docx")
    ]
    pptx = [
        name for name in names
        if name.startswith(root + "docs/deliverables/")
        and "/" not in name[len(root + "docs/deliverables/"):]
        and name.lower().endswith(".pptx")
    ]
    if len(docx) != 1 or len(pptx) != 1:
        raise SystemExit(
            f"ERROR: expected one final DOCX and one final PPTX; found {len(docx)}/{len(pptx)}"
        )

    for name in names:
        if name.endswith("/"):
            continue
        blob = outer.read(name)
        if name.lower().endswith((".docx", ".pptx")):
            try:
                with zipfile.ZipFile(io.BytesIO(blob)) as office:
                    corrupt = office.testzip()
                    if corrupt:
                        raise SystemExit(f"ERROR: corrupt Office entry: {name}!{corrupt}")
                    for inner_name in office.namelist():
                        if not inner_name.endswith("/"):
                            scan_blob(f"{name}!{inner_name}", office.read(inner_name))
            except zipfile.BadZipFile as exc:
                raise SystemExit(f"ERROR: invalid Office artifact: {name}: {exc}") from exc
        else:
            scan_blob(name, blob)

print(f"Archive audit OK: {len(names)} entries; one DOCX; one PPTX; deep scan clean")
PY

if command -v shasum >/dev/null 2>&1; then
  shasum -a 256 "${archive_path}" > "${archive_path}.sha256"
else
  sha256sum "${archive_path}" > "${archive_path}.sha256"
fi

echo "Created ${archive_path}"
