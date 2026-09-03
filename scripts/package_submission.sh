#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 2 ]; then
  echo "Usage: bash scripts/package_submission.sh RELEASE_TAG TEAM_NAME [WORK_NAME] [OUTPUT_DIR]"
  echo "Example: bash scripts/package_submission.sh goai-2026-final-v4 团队名 OBS_Trust_Layer dist"
  exit 2
fi

release_ref="$1"
team_name="$2"
work_name="${3:-OBS_Trust_Layer}"
output_dir="${4:-dist}"

if [ -z "${team_name//[[:space:]]/}" ] || [ "$team_name" = "团队名" ] || [ "$team_name" = "队伍名" ]; then
  echo "ERROR: TEAM_NAME must be the actual competition team name, not a placeholder."
  exit 2
fi

git rev-parse --verify "${release_ref}^{commit}" >/dev/null
mkdir -p "$output_dir"

python3 - "$release_ref" "$team_name" "$work_name" "$output_dir" <<'PY'
from __future__ import annotations

import hashlib
import io
import json
import re
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

release_ref, team_name, work_name, output_dir = sys.argv[1:]
output = Path(output_dir)


def clean_component(value: str) -> str:
    value = re.sub(r"\s+", "_", value.strip())
    value = value.replace("/", "_").replace("\\", "_").replace(":", "_")
    if not value:
        raise SystemExit("ERROR: empty package-name component")
    return value


team = clean_component(team_name)
work = clean_component(work_name)
commit = subprocess.check_output(
    ["git", "rev-parse", f"{release_ref}^{{commit}}"], text=True
).strip()
archive_bytes = subprocess.check_output(
    ["git", "archive", "--format=tar", release_ref]
)

files: dict[str, bytes] = {}
with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:") as archive:
    for member in archive.getmembers():
        if not member.isfile():
            continue
        stream = archive.extractfile(member)
        if stream is not None:
            files[member.name] = stream.read()

deliverable_root = "docs/deliverables/"
final_docx = sorted(
    p for p in files
    if p.startswith(deliverable_root)
    and "/" not in p[len(deliverable_root):]
    and p.lower().endswith(".docx")
)
final_pptx = sorted(
    p for p in files
    if p.startswith(deliverable_root)
    and "/" not in p[len(deliverable_root):]
    and p.lower().endswith(".pptx")
)
if len(final_docx) != 1 or len(final_pptx) != 1:
    raise SystemExit(
        "ERROR: release must contain exactly one top-level final DOCX and PPTX; "
        f"found {len(final_docx)} DOCX / {len(final_pptx)} PPTX"
    )

base = f"AI4R_OPEN_{team}_{work}"
packages = {
    "code": output / f"{base}_代码材料.zip",
    "noncode": output / f"{base}_非代码材料.zip",
    "ppt": output / f"{base}_非代码材料_PPT.zip",
}
roots = {
    "code": f"{base}_代码材料/",
    "noncode": f"{base}_非代码材料/",
    "ppt": f"{base}_非代码材料_PPT/",
}


def include_code(path: str) -> bool:
    return not path.startswith(deliverable_root)


def include_noncode(path: str) -> bool:
    top_level = {
        "README.md", "JUDGE_QUICKSTART.md", "SUBMISSION_MANIFEST.md",
        "environment_spec.md", "THIRD_PARTY_NOTICES.md", "LICENSE", "CITATION.cff",
    }
    prefixes = ("docs/", "results/", "figures/", "configs/")
    data_evidence = {
        "data/manifest.csv", "data/manifest_phase.csv", "data/quality_manifest.csv",
        "data/sta_lta_picks.csv",
    }
    return path in top_level or path in data_evidence or path.startswith(prefixes)


selections = {
    "code": sorted(p for p in files if include_code(p)),
    "noncode": sorted(p for p in files if include_noncode(p)),
    "ppt": final_pptx,
}

patterns = (
    re.compile(b"/" + b"Users/"),
    re.compile(b"/" + b"home/" + rb"[^/\s]+/"),
    re.compile(b"AK" + b"IA" + rb"[0-9A-Z]{16}"),
    re.compile(b"gh" + b"p_" + rb"[A-Za-z0-9]{20,}"),
    re.compile(b"-----BEGIN " + rb"(?:RSA |EC |OPENSSH )?" + b"PRIVATE KEY-----"),
)


def scan_blob(label: str, blob: bytes) -> None:
    for pattern in patterns:
        if pattern.search(blob):
            raise SystemExit(f"ERROR: sensitive path/token pattern in {label}")


def write_package(kind: str) -> None:
    path = packages[kind]
    root = roots[kind]
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        identity = {
            "competition": "GOAI 2026 Track 3 AI for Research semifinal",
            "direction": "OPEN",
            "team": team_name,
            "work": work_name,
            "release_ref": release_ref,
            "commit": commit,
            "package_kind": kind,
        }
        zf.writestr(
            root + "PACKAGE_IDENTITY.json",
            json.dumps(identity, ensure_ascii=False, indent=2).encode("utf-8"),
        )
        for source in selections[kind]:
            blob = files[source]
            scan_blob(source, blob)
            if source.lower().endswith((".docx", ".pptx")):
                try:
                    with zipfile.ZipFile(io.BytesIO(blob)) as office:
                        corrupt = office.testzip()
                        if corrupt:
                            raise SystemExit(f"ERROR: corrupt Office entry: {source}!{corrupt}")
                        for inner in office.namelist():
                            if not inner.endswith("/"):
                                scan_blob(f"{source}!{inner}", office.read(inner))
                except zipfile.BadZipFile as exc:
                    raise SystemExit(f"ERROR: invalid Office artifact: {source}: {exc}") from exc
            zf.writestr(root + source, blob)

    with zipfile.ZipFile(path) as zf:
        corrupt = zf.testzip()
        if corrupt:
            raise SystemExit(f"ERROR: corrupt output archive entry: {corrupt}")
        names = set(zf.namelist())
        if root + "PACKAGE_IDENTITY.json" not in names:
            raise SystemExit(f"ERROR: missing package identity in {path}")


for package_kind in packages:
    write_package(package_kind)

code_required = {
    roots["code"] + "README.md",
    roots["code"] + "environment_spec.md",
    roots["code"] + "smoke_test.sh",
    roots["code"] + "reproduce_core.sh",
    roots["code"] + "reproduce_exp17.sh",
    roots["code"] + "docs/reproduction.md",
    roots["code"] + "results/exploration_trajectory.jsonl",
    roots["code"] + "results/run_trajectory.jsonl",
    roots["code"] + "results/exp17_final_runlog.jsonl",
    roots["code"] + "results/baseline_results.csv",
}
noncode_required = {
    roots["noncode"] + final_docx[0],
    roots["noncode"] + final_pptx[0],
    roots["noncode"] + "docs/final_report.md",
    roots["noncode"] + "docs/problem_definition.md",
    roots["noncode"] + "docs/exploration_log.md",
    roots["noncode"] + "results/exploration_trajectory.jsonl",
    roots["noncode"] + "results/run_trajectory.jsonl",
    roots["noncode"] + "results/exp17_final_runlog.jsonl",
    roots["noncode"] + "results/baseline_results.csv",
    roots["noncode"] + "results/evidence_manifest.json",
    roots["noncode"] + "THIRD_PARTY_NOTICES.md",
}
ppt_required = {roots["ppt"] + final_pptx[0]}

for kind, required in (
    ("code", code_required), ("noncode", noncode_required), ("ppt", ppt_required)
):
    with zipfile.ZipFile(packages[kind]) as zf:
        missing = sorted(required.difference(zf.namelist()))
        if missing:
            raise SystemExit(f"ERROR: {kind} package missing: {', '.join(missing)}")

checksum_lines = []
for kind, path in packages.items():
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    checksum_lines.append(f"{digest}  {path.name}")
    Path(str(path) + ".sha256").write_text(f"{digest}  {path.name}\n", encoding="utf-8")
    print(f"Created {path} ({kind})")

(output / f"{base}_SHA256SUMS.txt").write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")
print(f"Package audit OK: release={release_ref}; commit={commit}; 3 archives; deep scan clean")
PY
