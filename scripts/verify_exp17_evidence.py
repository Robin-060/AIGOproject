import json
from pathlib import Path

SUMMARY = Path("results/exp17_summary_A.json")
PAIRED = Path("results/paired_bootstrap_A.json")
MANIFEST = Path("results/evidence_manifest.json")

for path in (SUMMARY, PAIRED, MANIFEST):
    if not path.exists():
        raise SystemExit(f"Missing required evidence file: {path}")

summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
paired = json.loads(PAIRED.read_text(encoding="utf-8"))
manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

metrics = summary["metrics"]
criteria = summary["criteria"]
summary_paired = summary["unsafe_delta_bootstrap_paired"]
c2 = criteria["c2_non_inferiority_vs_voting_2pp"]

def same(a, b, tol=1e-9):
    return abs(float(a) - float(b)) <= tol

def find_key(obj, key):
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for value in obj.values():
            found = find_key(value, key)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for value in obj:
            found = find_key(value, key)
            if found is not None:
                return found
    return None

# 1. Frozen headline values
assert round(float(metrics["ceiling_pct"]), 2) == 54.13
assert round(float(metrics["unsafe_50_pct"]), 2) == 5.51
assert round(float(metrics["interception_50_budget_pct"]), 2) == 94.26

# 2. paired_bootstrap_A.json is the authoritative c2 source
for key in (
    "point_unsafe_exp_50_pct",
    "point_unsafe_voting_50_pct",
    "point_delta_pp",
    "one_sided_upper95_pp",
    "threshold_pp",
):
    assert same(summary_paired[key], paired[key]), (
        f"EXP17 evidence mismatch for {key}: "
        f"summary={summary_paired[key]} paired={paired[key]}"
    )

assert round(float(paired["point_delta_pp"]), 2) == 0.92
assert round(float(paired["one_sided_upper95_pp"]), 2) == 2.24
assert round(float(paired["threshold_pp"]), 2) == 2.00

# 3. Final gate interpretation
assert criteria["c1_ceiling_ge_50"]["pass"] is True
assert c2["pass"] is False
assert c2["bootstrap_source"] == "paired_bootstrap_A.json"
assert criteria["c3_review_curve_preserved"]["pass"] is True
assert criteria["c4_risk_bin_ordering_preserved"]["pass"] is True
assert float(paired["one_sided_upper95_pp"]) >= float(paired["threshold_pp"])

# 4. Evidence manifest must agree with final frozen evidence
expected_manifest = {
    "coverage_ceiling_pct": 54.13,
    "unsafe_50_pct": 5.51,
    "error_interception_50_budget_pct": 94.26,
    "delta_unsafe_point_pp": 0.92,
    "paired_bootstrap_one_sided_upper95_pp": 2.24,
    "threshold_pp": 2.0,
}

for key, expected in expected_manifest.items():
    actual = find_key(manifest, key)
    assert actual is not None, f"Manifest missing key: {key}"
    assert same(actual, expected), (
        f"Manifest mismatch for {key}: {actual} != {expected}"
    )

manifest_c2_pass = find_key(manifest, "c2_pass")
manifest_c2_verdict = str(find_key(manifest, "c2_verdict") or "")

assert manifest_c2_pass is False, (
    f"Unexpected manifest c2_pass: {manifest_c2_pass}"
)

assert "NOT ESTABLISHED" in manifest_c2_verdict.replace("_", " ").upper(), (
    f"Unexpected manifest c2 verdict: {manifest_c2_verdict}"
)

print(
    "EXP17 EVIDENCE OK | "
    "Coverage=54.13% | Unsafe=5.51% | "
    "Interception=94.26% | DeltaUnsafe=+0.92pp | "
    "paired upper95=+2.24pp | c2=NOT ESTABLISHED"
)
