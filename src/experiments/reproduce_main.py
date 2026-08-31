"""
reproduce_main.py — 一键复现核心数字与三张主图 (v1.5)

复现范围 (全部基于冻结数据, 不运行模型推理):
  1. 冻结数据完整性校验 (sha256)
  2. 基线对比 → baseline_results.csv + 主图1 (含 Trust 曲线的基线图由主实验更新)
  3. 主实验 (冻结档案 hydrophone_v2, 不选优) → main_results/equal_coverage/risk_bins
  4. 全方法对比 → method_comparison_v2.csv
  5. cluster paired-bootstrap → bootstrap_ci.json
  6. 三张主图最终版 + failure raw data
  7. 探索轨迹导出 → exploration_trajectory.jsonl

输出: results/reproduction_report.json (环境版本/seed/校验和/核心数字)

用法:
    python -m src.experiments.reproduce_main
"""

import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import warnings  # noqa: E402
warnings.filterwarnings("ignore")

OUT_REPORT = ROOT / "results" / "reproduction_report.json"

FROZEN_INPUTS = {
    "data/batch_calibration/records_all_v2.json":
        "e5cc0a28a61a4a91",
    "data/quality_manifest.csv": None,
    "data/sta_lta_picks.csv": None,
    "data/manifest_phase.csv": None,
    "data/eqt_predictions.json": None,
}


def canonical_digest(path: Path) -> str:
    """规范化内容哈希: 统一 CRLF→LF 后计算 (跨平台稳定, 免疫 git autocrlf)."""
    raw = path.read_bytes()
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def verify_inputs() -> dict:
    """校验冻结数据存在且 sha256 一致 (前 16 位)."""
    checked = {}
    for rel, expect in FROZEN_INPUTS.items():
        path = ROOT / rel
        if not path.exists():
            raise FileNotFoundError(f"冻结数据缺失: {rel}")
        digest = canonical_digest(path)
        ok = expect is None or digest.startswith(expect)
        checked[rel] = {"sha256_prefix": digest[:16], "verified": bool(ok)}
        if not ok:
            raise ValueError(f"冻结数据校验失败: {rel} (期望前缀 {expect}, "
                             f"实际 {digest[:16]})")
    return checked


def env_info() -> dict:
    import importlib.metadata as md
    versions = {}
    for pkg in ("seisbench", "torch", "obspy", "numpy", "scipy", "pandas"):
        try:
            versions[pkg] = md.version(pkg)
        except Exception:
            versions[pkg] = "unknown"
    return versions


def step(title):
    print(f"\n{'=' * 64}\n{title}\n{'=' * 64}", flush=True)


def main():
    started = time.time()
    print("OBS Trust Layer 一键复现 (semifinal_v1.5)")
    print("范围: 冻结数据 → 基线 → 主实验 → 对比 → bootstrap → 主图")
    print("注意: 全程使用冻结预测, 不运行模型推理", flush=True)

    step("1/7 冻结数据校验")
    checked = verify_inputs()
    for rel, info in checked.items():
        print(f"  ✓ {rel} (sha256 {info['sha256_prefix']})")

    step("2/7 基线对比 (8 策略)")
    from src.experiments.run_baselines import main as baselines_main
    baselines_main()

    step("3/7 主实验 (冻结档案, 不选优)")
    from src.experiments.run_main_experiment import main as mainexp_main
    mainexp_main()

    step("4/7 全方法对比表")
    from src.experiments.compare_methods_v2 import main as compare_main
    compare_main()

    step("5/7 cluster paired-bootstrap")
    from src.experiments.bootstrap_analysis import main as boot_main
    boot_main()

    step("6/7 主图与 failure data")
    from src.experiments.final_figures import main as figures_main
    figures_main()

    step("7/7 探索轨迹导出")
    from src.experiments.generate_trajectory import main as trajectory_main
    trajectory_main()

    # ── 复现报告 (NOT_EVALUABLE 纪律: 不可达点位不填 Unsafe) ──
    import csv
    trust50 = voting50 = None
    trust_ceiling = 0.0
    trust_50_feasible = False
    with open(ROOT / "results" / "equal_coverage_trust.csv", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["target_coverage_pct"] == "50":
                trust_50_feasible = row.get("feasible", "false").lower() == "true"
                if trust_50_feasible and row["unsafe_output_rate_pct"]:
                    trust50 = float(row["unsafe_output_rate_pct"])
            trust_ceiling = max(trust_ceiling, float(row["coverage_pct"]))
    with open(ROOT / "results" / "baseline_results.csv", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["strategy"] == "Voting" and row["target_coverage_pct"] == "50":
                voting50 = float(row["unsafe_output_rate_pct"])
    with open(ROOT / "results" / "bootstrap_ci.json", encoding="utf-8") as f:
        boot = json.load(f)["ALL"]
    if boot.get("verdict") == "NOT_EVALUABLE":
        # 声明点位不可达: 报告天花板补充比较 (非声明点位)
        supp = json.load(open(ROOT / "results" / "bootstrap_ci.json",
                              encoding="utf-8")).get("ALL_ceiling_supplementary", {})
        core = {
            "trust_unsafe_pct_at_50": None,
            "voting_unsafe_pct_at_50": voting50,
            "declared_point_50": "NOT_EVALUABLE",
            "trust_ceiling_pct": round(trust_ceiling, 2),
            "ceiling_supplementary_delta_pp": supp.get("point_delta_pp"),
            "ceiling_supplementary_verdict": supp.get("verdict"),
        }
    else:
        core = {
            "trust_unsafe_pct_at_50": trust50,
            "voting_unsafe_pct_at_50": voting50,
            "delta_trust_minus_voting_pp": round(boot["point_delta_pp"], 2),
            "ci95": [boot["ci95_lo"], boot["ci95_hi"]],
            "verdict": boot["verdict"],
        }

    report = {
        "config_version": "semifinal_v1.5",
        "seed": 42,
        "environment": env_info(),
        "frozen_inputs": checked,
        "core_numbers": core,
        "duration_s": round(time.time() - started, 1),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }
    OUT_REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False),
                          encoding="utf-8")
    print(f"\n✓ 复现报告: {OUT_REPORT}")
    if trust_50_feasible:
        print(f"核心数字: Trust {trust50}% @50% | Voting {voting50}% @50% | "
              f"Δ={boot['point_delta_pp']}pp, {boot['verdict']}")
    else:
        supp = json.load(open(ROOT / "results" / "bootstrap_ci.json",
                              encoding="utf-8")).get("ALL_ceiling_supplementary", {})
        print(f"声明点位 50%: NOT_EVALUABLE (Trust 天花板 {trust_ceiling:.2f}%) | "
              f"Voting {voting50}% @50% | 天花板补充 Δ={supp.get('point_delta_pp')}pp, "
              f"{supp.get('verdict')}")


if __name__ == "__main__":
    main()
