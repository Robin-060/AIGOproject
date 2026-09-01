"""
Trust Layer 主实验 (D6) — 相位级评估 + 真实质量报告 + Equal-Coverage

协议: configs/semifinal_main.yaml (当前 semifinal_v1.5.1)
  - 1306 个 (sample_id, phase) 评估单元, 冻结预测
  - 质量报告来自 data/quality_manifest.csv (真实 SNR/断点/削波/缺道)
  - TrustConfig 由 configs/semifinal_main.yaml 单一加载; 门控以 threshold=100
    排序运行一次后
    外部按 phase risk 排序选样 (与基线一致的 top-k 精确覆盖率)
  - no_pick 单元按 C 契约落 ABSTAIN, 永不进入 auto

历史 v2 候选选择已在 EXP06 完成；正式复现固定读取 selected_profile，
不得再次按当前结果选择候选。`--profile-selection` 只重放历史程序，
只写历史文件，不覆盖正式产物。

用法:
    python -m src.experiments.run_main_experiment
    python -m src.experiments.run_main_experiment --profile-selection
"""

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import warnings  # noqa: E402
warnings.filterwarnings("ignore")

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from src.experiments.phase_evaluation import (  # noqa: E402
    build_phase_units,
    load_records,
    phase_verdict,
)
from src.trust_engine.schema import (  # noqa: E402
    AdapterStatus,
    ModelPrediction,
    QualityReport,
    SampleMetadata,
)
from src.trust_engine.config_loader import load_frozen_config  # noqa: E402
from src.trust_engine.data_evidence import evaluate_data_evidence  # noqa: E402
from src.trust_engine.model_suitability import evaluate_model_suitability  # noqa: E402
from src.trust_engine.single_model import evaluate_single_model_evidence  # noqa: E402
from src.trust_engine.physics import check_model_prediction  # noqa: E402
from src.trust_engine.multi_model import analyze_multi_model_consensus  # noqa: E402
from src.trust_engine.fusion import build_fusion_candidates  # noqa: E402
from src.trust_engine.reliability import evaluate_reliability  # noqa: E402

OUT_MAIN = ROOT / "results" / "main_results.csv"
OUT_BINS = ROOT / "results" / "risk_bins.csv"
OUT_EQ = ROOT / "results" / "equal_coverage_trust.csv"
OUT_FIG = ROOT / "figures" / "coverage_vs_unsafe.png"
OUT_SELECTION = ROOT / "results" / "profile_selection_exp06.csv"

# Compatibility for historical exploration scripts only. Formal main() never
# iterates or selects these candidates; it loads frozen.selected_profile once.
_FROZEN_PROFILES = load_frozen_config()
PROFILE_CANDIDATES = {
    name: _FROZEN_PROFILES.model_profiles(name)
    for name in _FROZEN_PROFILES.raw["model_profiles"]
}
ADAPTERS = [
    AdapterStatus(model_name=m, loaded=True, run_succeeded=True,
                  output_comparable=True)
    for m in ("PhaseNet", "PickBlue", "OBSTransformer", "EQTransformer")
]


def load_quality() -> dict:
    rows = {}
    with open(ROOT / "data" / "quality_manifest.csv", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows[row["sample_id"]] = row
    return rows


def load_split() -> dict:
    split = {}
    with open(ROOT / "data" / "manifest_phase.csv", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            split[(row["sample_id"], row["phase"])] = row["split"]
    return split


def trust_per_record(record, quality_row, config, profiles, penalties=None):
    """单样本跑完整 Trust 链, 返回 ReliabilityResult."""
    preds = [
        ModelPrediction(
            sample_id=record["sample_id"], model_name=m, phase=ph,
            time_s=v[f"{ph}_pick"], score=v.get("confidence"),
            adapter_status="OK", preprocessing_version="obs_raw_v1",
            prediction_source="REAL_MODEL",
        )
        for m, v in record["predictions"].items()
        for ph in ("P", "S") if v.get(f"{ph}_pick") is not None
    ]
    if not preds:
        return None

    available = [c for c in (quality_row["available_channels"] or "").split("|") if c]
    missing = [c for c in (quality_row["missing_channels"] or "").split("|") if c]
    meta = SampleMetadata(sample_id=record["sample_id"], data_source="REAL",
                          preprocessing_version="obs_raw_v1")
    quality = QualityReport(
        available_channels=available or ["Z", "N", "E", "H"],
        missing_channels=missing,
        sampling_rate_hz=100.0,
        snr_db=float(quality_row["snr_db"]) if quality_row["snr_db"] else None,
        gap_ratio=float(quality_row["gap_ratio"]) if quality_row["gap_ratio"] else 0.0,
        clipping_ratio=float(quality_row["clipping_ratio"]) if quality_row["clipping_ratio"] else 0.0,
        source="REAL_CALCULATION",
    )
    data_ev = evaluate_data_evidence(
        quality, penalties if penalties is not None else config.data_penalties
    )
    suits = evaluate_model_suitability(meta, quality, profiles, ADAPTERS)
    singles = evaluate_single_model_evidence(preds, config)
    physics = []
    seen = set()
    for p in preds:
        if p.model_name in seen:
            continue
        seen.add(p.model_name)
        p_ps = [x for x in preds if x.model_name == p.model_name and x.phase == "P"]
        s_ps = [x for x in preds if x.model_name == p.model_name and x.phase == "S"]
        physics.append(check_model_prediction(
            p_ps[0] if p_ps else None, s_ps[0] if s_ps else None,
            config, target_id=p.model_name,
        ))
    cons = analyze_multi_model_consensus(preds, suits, physics, config)
    fusions = build_fusion_candidates(preds, cons, config)
    return evaluate_reliability(
        meta, quality, profiles, preds,
        config, data_ev, suits, singles, physics, cons, fusions,
    )


def build_unit_rows(records, units, quality_map, profiles, config, record_map,
                    penalties=None):
    """逐单元产出决策与判定."""
    per_record = {}
    for i, record in enumerate(records):
        per_record[record["sample_id"]] = trust_per_record(
            record, quality_map[record["sample_id"]], config, profiles, penalties)
        if (i + 1) % 300 == 0:
            print(f"    Trust 链进度 {i + 1}/{len(records)}", flush=True)

    rows = []
    for unit in units:
        if not unit["primary_inclusion"]:
            continue
        sid, phase = unit["sample_id"], unit["phase"]
        result = per_record[sid]
        decision = (result.phase_decisions.get(phase) if result else None)
        action = decision.action if decision else "ABSTAIN"
        risk = decision.risk_score if decision else 50.0
        time_s = None
        if decision is not None:
            if decision.action == "FUSE" and decision.fused_pick is not None:
                time_s = decision.fused_pick.fused_time_s
            elif decision.selected_time_s is not None and decision.selected_time_s >= 0:
                time_s = decision.selected_time_s
            elif decision.selected_model:
                preds = (record_map[sid]["predictions"]
                         .get(decision.selected_model) or {})
                time_s = preds.get(f"{phase}_pick")
        auto_capable = action in ("ACCEPT", "ROUTE", "FUSE")
        verdict = phase_verdict(time_s if auto_capable else None,
                                unit["reference_time_s"], phase)
        rows.append({
            "sample_id": sid, "phase": phase,
            "station": unit["station"],
            "split": unit.get("split", ""),
            "reference_time_s": unit["reference_time_s"],
            "action": action, "risk": round(risk, 2),
            "selected_time_s": "" if time_s is None else round(time_s, 3),
            "auto_capable": auto_capable,
            "verdict": verdict,
        })
    return rows


def unsafe_at_coverage(rows, target_pct):
    """top-k 精确覆盖率下的 Unsafe (%), 与基线协议一致."""
    output_rows = [r for r in rows if r["verdict"] in ("correct", "wrong")]
    output_sorted = sorted(output_rows,
                           key=lambda r: (r["risk"], r["sample_id"], r["phase"]))
    k = int(round(target_pct / 100 * len(rows)))
    k = min(k, len(output_sorted))
    accepted = {(r["sample_id"], r["phase"]) for r in output_sorted[:k]}
    auto = wrong = 0
    for row in rows:
        if (row["sample_id"], row["phase"]) in accepted:
            auto += 1
            if row["verdict"] == "wrong":
                wrong += 1
    return wrong / auto * 100 if auto else float("inf"), len(output_rows) / len(rows) * 100


def main():
    frozen = load_frozen_config()
    records = load_records()
    quality_map = load_quality()
    split_map = load_split()
    units = build_phase_units(records)
    for unit in units:
        unit["split"] = split_map.get((unit["sample_id"], unit["phase"]), "main")
    record_map = {r["sample_id"]: r for r in records}
    config = frozen.trust_config(ranking_mode=True)
    profiles = frozen.model_profiles()

    main_units = [u for u in units if u["split"] == "main" and u["primary_inclusion"]]
    holdout_units = [u for u in units if u["split"] == "holdout" and u["primary_inclusion"]]
    print(f"冻结配置: {frozen.version} | parent={frozen.parent} | "
          f"sha256={frozen.sha256[:16]} | profile={frozen.selected_profile}")
    print(f"评估单元: main={len(main_units)}, holdout={len(holdout_units)}, "
          f"共 {len(main_units) + len(holdout_units)}")

    # 只运行冻结 profile。main/holdout 仅作已冻结配置的分片诊断，不再选优。
    print(f"\n正式运行 ({frozen.selected_profile}, 全部单元)...")
    final_rows = build_unit_rows(records, units, quality_map, profiles, config,
                                 record_map)
    main_rows = [row for row in final_rows if row["split"] == "main"]
    hold_rows = [row for row in final_rows if row["split"] == "holdout"]
    m_unsafe, m_ceiling = unsafe_at_coverage(main_rows, 50)
    if m_ceiling + 1e-9 < 50.0:
        print(f"  main: 50% 点位 NOT_EVALUABLE (天花板 {m_ceiling:.1f}%)")
    else:
        print(f"  main: 50%覆盖率 Unsafe = {m_unsafe:.1f}% | 天花板 = {m_ceiling:.1f}%")
    h_unsafe, h_ceiling = unsafe_at_coverage(hold_rows, 50)
    if h_ceiling + 1e-9 < 50.0:
        print(f"  holdout: 50% 点位 NOT_EVALUABLE (天花板 {h_ceiling:.1f}%)")
    else:
        print(f"  holdout: 50%覆盖率 Unsafe = {h_unsafe:.1f}% | 天花板 = {h_ceiling:.1f}%")

    write_outputs(final_rows, frozen)


def profile_selection_history():
    """显式重放 EXP06 候选比较；正式复现链不会调用。"""
    frozen = load_frozen_config()
    records = load_records()
    quality_map = load_quality()
    split_map = load_split()
    units = build_phase_units(records)
    for unit in units:
        unit["split"] = split_map.get((unit["sample_id"], unit["phase"]), "main")
    main_units = [
        unit for unit in units
        if unit["split"] == "main" and unit["primary_inclusion"]
    ]
    record_map = {record["sample_id"]: record for record in records}
    config = frozen.trust_config(ranking_mode=True)

    results_by_candidate = {}
    print("EXP06 历史程序重放（不参与正式复现，不重新冻结）")
    for name, profiles in PROFILE_CANDIDATES.items():
        rows = build_unit_rows(
            records, main_units, quality_map, profiles, config, record_map
        )
        unsafe50, ceiling = unsafe_at_coverage(rows, 50)
        results_by_candidate[name] = (unsafe50, ceiling)
        print(f"  {name}: Unsafe@50={unsafe50:.2f}% | ceiling={ceiling:.2f}%")
    winner = min(results_by_candidate, key=lambda name: results_by_candidate[name][0])

    with open(OUT_SELECTION, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["candidate", "unsafe50_pct", "ceiling_pct", "decided"])
        for name, (unsafe, ceiling) in results_by_candidate.items():
            writer.writerow([
                name,
                f"{unsafe:.2f}",
                f"{ceiling:.2f}",
                "winner" if name == winner else "",
            ])
    print(f"✓ 历史记录: {OUT_SELECTION} | winner={winner}")


def write_outputs(unit_rows, frozen):
    profile_name = frozen.selected_profile
    for row in unit_rows:
        row.update({
            "config_version": frozen.version,
            "config_hash": frozen.sha256,
            "parent_config": frozen.parent,
            "profile": profile_name,
        })
    with open(OUT_MAIN, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=list(unit_rows[0].keys()), lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(unit_rows)
    print(f"✓ {OUT_MAIN} ({len(unit_rows)} 行)")

    output_rows = [r for r in unit_rows if r["verdict"] in ("correct", "wrong")]
    output_sorted = sorted(output_rows,
                           key=lambda r: (r["risk"], r["sample_id"], r["phase"]))
    print(f"Trust 覆盖率天花板: {len(output_rows)}/{len(unit_rows)} "
          f"= {len(output_rows)/len(unit_rows)*100:.1f}%")

    print(f"\n{'目标Cov':>8} {'有效阈值':>8} {'实际Cov':>8} {'Unsafe':>8} {'Burden':>8} {'拦截率':>8} {'状态':>24}")
    eq_rows = []
    trust_curve = {"cov": [], "unsafe": []}
    for target in frozen.coverage_points:
        requested_k = int(round(target / 100 * len(unit_rows)))
        feasible = requested_k <= len(output_sorted)
        k = min(requested_k, len(output_sorted))
        accepted = {(r["sample_id"], r["phase"]) for r in output_sorted[:k]}
        eff_threshold = output_sorted[k - 1]["risk"] if k else 0.0
        auto_correct = auto_wrong = intercepted = total_errors = 0
        for row in unit_rows:
            is_error = row["verdict"] in ("wrong", "no_pick")
            if is_error:
                total_errors += 1
            if (row["sample_id"], row["phase"]) in accepted:
                if row["verdict"] == "correct":
                    auto_correct += 1
                elif row["verdict"] == "wrong":
                    auto_wrong += 1
            elif is_error:
                intercepted += 1
        auto = auto_correct + auto_wrong
        cov = auto / len(unit_rows) * 100
        unsafe = auto_wrong / auto * 100 if auto else 0.0
        burden = (len(unit_rows) - auto) / len(unit_rows) * 100
        inter = intercepted / total_errors * 100 if total_errors else 0.0
        # Selective Risk = 自动单元上的平均 0-1 loss (wrong=1, correct=0);
        # 本口径下 auto 集内仅有 correct/wrong 两类 → 数值等同 Unsafe Output Rate
        selective_risk = unsafe
        status = "COMPARABLE" if feasible else "NOT_COMPARABLE_AT_TARGET"
        eq_rows.append({
            "strategy": "TrustLayer", "target_coverage_pct": target,
            "coverage_pct": round(cov, 2),
            "unsafe_output_rate_pct": round(unsafe, 2) if feasible else "",
            "selective_risk_pct": round(selective_risk, 2) if feasible else "",
            "review_burden_pct": round(burden, 2),
            "error_interception_rate_pct": round(inter, 2) if feasible else "",
            "risk_threshold": round(eff_threshold, 2) if feasible else "",
            "profile": profile_name,
            "config_version": frozen.version,
            "config_hash": frozen.sha256,
            "parent_config": frozen.parent,
            "feasible": str(feasible).lower(),
            "comparison_status": status,
        })
        if feasible:
            trust_curve["cov"].append(cov)
            trust_curve["unsafe"].append(unsafe)
            print(f"{target:>7}% {eff_threshold:>8.2f} {cov:>7.1f}% {unsafe:>7.1f}% "
                  f"{burden:>7.1f}% {inter:>7.1f}% {status:>24}")
        else:
            print(f"{target:>7}% {'—':>8} {cov:>7.1f}% {'—':>8} {burden:>7.1f}% "
                  f"{'—':>8} NOT_EVALUABLE (天花板 {len(output_sorted)/len(unit_rows)*100:.1f}%)")

    with open(OUT_EQ, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=list(eq_rows[0].keys()), lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(eq_rows)
    print(f"✓ {OUT_EQ}")

    # 风险分箱 (仅有效输出单元, 主图2 数据)
    bins = [(0, 10), (10, 20), (20, 30), (30, 40), (40, 51)]
    bin_rows = []
    for lo, hi in bins:
        members = [r for r in output_rows if lo <= r["risk"] < hi]
        errors = sum(1 for r in members if r["verdict"] == "wrong")
        reliable = len(members) >= 10
        bin_rows.append({
            "risk_bin": f"{lo}-{hi - 1}", "n": len(members),
            "wrong": errors,
            "error_rate_pct": (round(errors / len(members) * 100, 2)
                               if members and reliable else ""),
            "reliable": str(reliable).lower(),
            "config_version": frozen.version,
            "config_hash": frozen.sha256,
        })
    with open(OUT_BINS, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=list(bin_rows[0].keys()), lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(bin_rows)
    print(f"✓ {OUT_BINS}")
    for row in bin_rows:
        flag = "" if row["reliable"] == "true" else " (n<10 不可靠)"
        print(f"  risk {row['risk_bin']:>6}: n={row['n']:4d} "
              f"错误率={row['error_rate_pct'] or '—'}{flag}")

    # 主图更新 (跳过不可达点位行)
    base_csv = ROOT / "results" / "baseline_results.csv"
    strategies = {}
    with open(base_csv, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            name = row["strategy"]
            if row.get("feasible", "true").lower() != "true":
                continue
            strategies.setdefault(name, {"cov": [], "unsafe": []})
            strategies[name]["cov"].append(float(row["coverage_pct"]))
            strategies[name]["unsafe"].append(float(row["unsafe_output_rate_pct"]))
    colors = {
        "Single-PhaseNet": "#9E9E9E", "Single-PickBlue": "#9E9E9E",
        "Single-OBSTransformer": "#607D8B", "MaxConf": "#FF9800",
        "Voting": "#2196F3", "Traditional-STA/LTA": "#795548",
        "Random": "#F44336", "TrustLayer": "#4CAF50",
    }
    fig, ax = plt.subplots(figsize=(10, 6))
    for name, data in strategies.items():
        ax.plot(data["cov"], data["unsafe"], "o-", label=name,
                color=colors.get(name, "#999999"), linewidth=2, markersize=6)
    ax.plot(trust_curve["cov"], trust_curve["unsafe"], "o-",
            label="Trust Layer", color="#4CAF50", linewidth=3, markersize=9)
    ax.set_xlabel("Coverage (%)")
    ax.set_ylabel("Unsafe Output Rate (%)")
    ax.set_title("Equal-Coverage Comparison on 1306 Phase Units "
                 f"({frozen.version}, profile={profile_name})")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUT_FIG, dpi=150)
    plt.close(fig)
    print(f"✓ {OUT_FIG}")


if __name__ == "__main__":
    if "--profile-selection" in sys.argv:
        profile_selection_history()
    else:
        main()
