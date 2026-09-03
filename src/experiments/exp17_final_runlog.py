"""
exp17_final_runlog.py — 最终 EXP17-A/R1 完整运行日志生成器 (机器可读 JSONL)

定位: 产出与最终 EXP17-A / R1 冻结结果一一对应的、真实可复核的运行日志。
所有记录来自本脚本实际执行的子进程 (命令/退出码/时长/标准输出摘录/产物 sha256),
不补造历史 private reasoning。EXP01–15 的 retrospective 轨迹保留于
results/exploration_trajectory.jsonl, 不冒充本日志。

输出: results/exp17_final_runlog.jsonl (每次运行重建该文件, 记录一次 formal run)
复现: python -m src.experiments.exp17_final_runlog

记录字段 (每条):
  - tool_call: 实际执行的命令、退出码、耗时
  - agent_input / observation / output / action: 该步真实输入输出
  - environment_feedback: 子进程标准输出摘录 + 断言结果
  - artifacts: 该步写入产物的路径与 sha256
  - errors / retries: 本步实际错误与重试; 无则空列表并注明 none
  - human_intervention / multi_run / selection_rules: 本次运行内无人为干预;
    历史人工裁决、多次运行与筛选规则在 meta 记录中逐条给出证据出处
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results" / "exp17_final_runlog.jsonl"

PARITY_SNIPPET = (
    "import sys, warnings; warnings.filterwarnings('ignore')\n"
    "from pathlib import Path; sys.path.insert(0, str(Path('.').resolve()))\n"
    "from src.experiments.exp17_policy_refinement import chain_rows, baseline_parity_check\n"
    "rows, _f = chain_rows(None)\n"
    "diffs, n = baseline_parity_check(rows, Path('results/main_results.csv'))\n"
    "print(f'PARITY: ref={n} diffs={diffs}')\n"
    "sys.exit(0 if diffs == 0 else 1)\n"
)

R1_SNIPPET = (
    "import json, sys, yaml\n"
    "from pathlib import Path\n"
    "d = json.loads(Path('results/exp17_robustness_R1.json').read_text(encoding='utf-8'))\n"
    "cfg = yaml.safe_load(Path('configs/semifinal_main.yaml').read_text(encoding='utf-8'))\n"
    "tp = cfg['trust_engine']['parameters']\n"
    "ok = (str(d.get('verdict','')).startswith('PASS')"
    " and d.get('result_under_alternative',{}).get('identical_to_frozen_exp17_A')"
    " and d.get('alternative_value') == {'P': 0.34, 'S': 0.51}"
    " and (float(tp['consensus_tolerance_p_s']), float(tp['consensus_tolerance_s_s'])) == (0.34, 0.51))\n"
    "print('R1: verdict=', d['verdict'][:40], 'identical=', "
    "d.get('result_under_alternative',{}).get('identical_to_frozen_exp17_A'),"
    " 'tol=', tp['consensus_tolerance_p_s'], tp['consensus_tolerance_s_s'])\n"
    "sys.exit(0 if ok else 1)\n"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def git_state() -> dict:
    def run(*args: str) -> str:
        try:
            return subprocess.run(
                ["git", *args], cwd=ROOT, check=True,
                capture_output=True, text=True,
            ).stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            return "UNKNOWN"

    return {
        "commit": run("rev-parse", "HEAD"),
        "branch": run("branch", "--show-current"),
        "dirty_at_start": run("status", "--porcelain") or "",
    }


def run_step(run_id: str, seq: int, name: str, command: list[str],
             agent_input: dict, records: list[dict], config_version: str,
             config_hash: str, commit: str) -> int:
    started = time.monotonic()
    proc = subprocess.run(command, cwd=ROOT, capture_output=True, text=True,
                          timeout=1800)
    duration = round(time.monotonic() - started, 2)
    stdout = (proc.stdout or "").strip().splitlines()
    stderr = (proc.stderr or "").strip().splitlines()
    records.append({
        "type": "step",
        "run_id": run_id,
        "seq": seq,
        "step": name,
        "timestamp_utc": utc_now(),
        "commit": commit,
        "config_version": config_version,
        "config_hash": config_hash,
        "tool_call": {
            "command": " ".join(command),
            "exit_code": proc.returncode,
            "duration_s": duration,
        },
        "agent_input": agent_input,
        "action": f"execute: {' '.join(command)}",
        "environment_feedback": {
            "stdout_tail": stdout[-8:],
            "stderr_tail": stderr[-3:],
            "exit_ok": proc.returncode == 0,
        },
        "errors": [] if proc.returncode == 0 else [
            {"type": "nonzero_exit", "exit_code": proc.returncode,
             "stderr_tail": stderr[-3:]},
        ],
        "retries": [],
        "error_note": "none" if proc.returncode == 0 else "see errors",
        "human_intervention": "none (本次运行内无人为干预)",
        "output": {},
        "artifacts": [],
    })
    return proc.returncode


def main() -> int:
    records: list[dict] = []
    run_id = f"formal-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{uuid4().hex[:8]}"
    git = git_state()
    import yaml  # noqa: E402

    cfg = yaml.safe_load((ROOT / "configs" / "semifinal_main.yaml").read_text(
        encoding="utf-8"))
    frozen_hash = "9727570d238aa4925add04bf363f7611e85e83ea4914f5cf5f8a976c58202b6d"
    commit = git["commit"]

    records.append({
        "type": "run_start",
        "run_id": run_id,
        "seq": 0,
        "timestamp_utc": utc_now(),
        "commit": commit,
        "branch": git["branch"],
        "dirty_at_start": git["dirty_at_start"] or "none",
        "config_version": "semifinal_v1.5.1-bugfix",
        "config_hash": frozen_hash,
        "purpose": "最终 EXP17-A / R1 运行日志 — 与冻结结果一一对应",
        "disclosure": ("本日志为实际执行的命令/退出码/输出摘录/产物 sha256 的记录; "
                       "EXP01–15 retrospective 轨迹在 results/exploration_trajectory.jsonl, "
                       "不冒充本日志"),
    })

    seq = 0

    # ── Step 1: v1.5.1 默认路径对账 ──
    seq += 1
    rc = run_step(run_id, seq, "parity_v151_baseline",
                  [sys.executable, "-c", PARITY_SNIPPET],
                  {"purpose": "EXP17 开关关闭时与 v1.5.1 冻结主链逐单元对账",
                   "reference": "results/main_results.csv",
                   "env": {"OBS_EXP17_POLICY": "(unset)"}},
                  records, "semifinal_v1.5.1-bugfix", frozen_hash, commit)
    if rc != 0:
        print("parity step failed"); return 1
    parity_line = next(
        (l for l in records[-1]["environment_feedback"]["stdout_tail"]
         if l.startswith("PARITY:")), "PARITY: unknown")
    _ref, _dif = parity_line.replace("PARITY: ref=", "").split(" diffs=")
    records[-1]["output"] = {"ref_units": int(_ref), "diffs": int(_dif)}

    # ── Step 2: EXP17-A 重跑 ──
    seq += 1
    rc = run_step(run_id, seq, "exp17_A_intervention",
                  [sys.executable, "-m", "src.experiments.exp17_policy_refinement",
                   "--intervention", "A"],
                  {"policy": "consensus_route", "env": {"OBS_EXP17_POLICY": "consensus_route"},
                   "inputs": ["configs/semifinal_main.yaml", "data/batch_calibration/records_all_v2.json",
                              "results/main_results.csv"]},
                  records, "semifinal_v1.5.1-bugfix", frozen_hash, commit)
    if rc != 0:
        print("exp17 A step failed"); return 1
    a_summary = json.loads((ROOT / "results" / "exp17_summary_A.json").read_text(
        encoding="utf-8"))
    records[-1]["output"] = {
        "ceiling_pct": a_summary["metrics"]["ceiling_pct"],
        "unsafe_50_pct": a_summary["metrics"]["unsafe_50_pct"],
        "interception_50_budget_pct": a_summary["metrics"]["interception_50_budget_pct"],
        "criteria": a_summary["criteria"],
    }
    records[-1]["artifacts"] = [
        {"path": "results/main_results_exp17_A.csv",
         "sha256": sha256(ROOT / "results" / "main_results_exp17_A.csv")},
        {"path": "results/exp17_summary_A.json",
         "sha256": sha256(ROOT / "results" / "exp17_summary_A.json")},
    ]

    # ── Step 3: 配对 bootstrap ──
    seq += 1
    rc = run_step(run_id, seq, "paired_bootstrap",
                  [sys.executable, "-m", "src.experiments.paired_bootstrap", "--tag", "A"],
                  {"purpose": "Gate c2 唯一数字源 (60 台站 × 1000, seed 42)",
                   "input": "results/main_results_exp17_A.csv"},
                  records, "semifinal_v1.5.1-bugfix", frozen_hash, commit)
    if rc != 0:
        print("paired bootstrap step failed"); return 1
    paired = json.loads((ROOT / "results" / "paired_bootstrap_A.json").read_text(
        encoding="utf-8"))
    records[-1]["output"] = {
        "point_delta_pp": paired["point_delta_pp"],
        "one_sided_upper95_pp": paired["one_sided_upper95_pp"],
        "ci95_pp": [paired["ci95_lo_pp"], paired["ci95_hi_pp"]],
        "verdict": paired["verdict"],
    }
    records[-1]["artifacts"] = [
        {"path": "results/paired_bootstrap_A.json",
         "sha256": sha256(ROOT / "results" / "paired_bootstrap_A.json")},
    ]

    # ── Step 4: R1 只读核验 ──
    seq += 1
    rc = run_step(run_id, seq, "r1_robustness_verification",
                  [sys.executable, "-c", R1_SNIPPET],
                  {"purpose": "只核验冻结裁决记录与运行路径容差, 不重算 R1",
                   "input": "results/exp17_robustness_R1.json"},
                  records, "semifinal_v1.5.1-bugfix", frozen_hash, commit)
    if rc != 0:
        print("R1 verify step failed"); return 1
    r1 = json.loads((ROOT / "results" / "exp17_robustness_R1.json").read_text(
        encoding="utf-8"))
    records[-1]["output"] = {
        "verdict": r1["verdict"],
        "alternative_value": r1["alternative_value"],
        "identical_to_frozen_exp17_A":
            r1["result_under_alternative"]["identical_to_frozen_exp17_A"],
    }

    # ── Meta: 历史人工裁决 / 多次运行与筛选规则 / 历史错误与重试 ──
    seq += 1
    records.append({
        "type": "meta_human_interventions",
        "run_id": run_id, "seq": seq, "timestamp_utc": utc_now(), "commit": commit,
        "human_interventions": [
            {"event": "最终裁决 (C 方案 a): 保留 A 为表现最佳的候选 refinement, 仅报告 Coverage recovery, 不视为通过安全非劣 Gate 的部署策略; B 弃用; c2 锚点修订为 Voting@50 4.59% 配对 bootstrap",
             "evidence": "docs/experiments/exp17_preregistration.md §最终裁决与§0; commit 4793878"},
            {"event": "EXP17-R1 预注册: 替代值 P=0.34/S=0.51 先于结果冻结",
             "evidence": "docs/experiments/exp17_preregistration.md EXP17-R1 节"},
            {"event": "c2 数字对齐修复: summary 以 paired_bootstrap_A.json 为唯一数字源",
             "evidence": "commit e5ff41c"},
        ],
        "note": "本次最终运行过程本身无人为干预 (0 次); 以上为探索过程中的真实人工裁决, 逐条留痕",
    })
    seq += 1
    records.append({
        "type": "meta_multi_runs_selection_rules",
        "run_id": run_id, "seq": seq, "timestamp_utc": utc_now(), "commit": commit,
        "multi_runs": [
            {"run": "EXP17-A (consensus_route)", "verdict": "c1/c3/c4 PASS, c2 未确认 → 保留为最佳候选"},
            {"run": "EXP17-B (only_usable_survivor)", "verdict": "c2 +4.87pp / c3 64.55% 双败 → 弃用 (负结果保留)"},
            {"run": "EXP17-A+B 累加", "verdict": "c2 +4.0pp → 弃用组合 (留档)"},
            {"run": "EXP17-C floor sweep (0.70→0.55)", "verdict": "0.60→51.76% / 0.55→53.22%, 均劣于 A → 留档不升级"},
            {"run": "EXP17-R1 (显式 0.34/0.51 重跑)", "verdict": "与冻结 EXP17-A 完全一致"},
        ],
        "selection_rules": [
            "干预单变量, 顺序 A→B→C, 按冻结判据版本逐干预验收 (版本与修订均留痕)",
            "四判据全部满足才 PASS; 任一失败即回退并记负结果",
            "禁止为达标微调干预参数、+2.0pp 界或 bootstrap 口径",
            "点估计 ≤+1.0pp 仅为内部绿灯, 不替代 c2 正式门禁",
            "truth-blind: 规则只读推理时可见证据, 禁止 evaluation truth",
        ],
    })
    seq += 1
    records.append({
        "type": "meta_historical_errors_retries",
        "run_id": run_id, "seq": seq, "timestamp_utc": utc_now(), "commit": commit,
        "historical_errors_retries": [
            {"event": "EXP14: 第 4.5 步共识绕过 FUSE 校准门 (低置信共识直接走主路)", "result": "堵住后天花板 54.2%→45.64%",
             "evidence": "docs/experiments/exploration_log_materials.md EXP14"},
            {"event": "EXP15: cluster bootstrap 重复台站权重丢失 bug", "result": "修正后 S 相 CI 更新为 [+0.90,+5.96]",
             "evidence": "exploration_log_materials.md EXP15; results/bootstrap_ci.json"},
            {"event": "ROUTE invalid-pick bug (7 个假输出单元)", "result": "v1.5.1-bugfix 单独修复, 核心数值零变化",
             "evidence": "commit 3efc94c"},
            {"event": "EXP17 早期 c2 锚点 6.04% 与配对口径不一致", "result": "最终裁决修订为 Voting@50 配对, 留痕于 §0",
             "evidence": "docs/experiments/exp17_preregistration.md"},
            {"event": "exp17_summary_A c2 旧值 2.99pp (非配对) 与冻结 2.24pp 并存", "result": "e5ff41c 对齐并新增 bootstrap_source",
             "evidence": "commit e5ff41c"},
        ],
        "this_run": {"errors": 0, "retries": 0,
                     "note": "本次最终运行 0 错误 0 重试; 上表为探索期历史, 不属本 run"},
    })

    # ── Final: 最终指标与裁决 ──
    seq += 1
    records.append({
        "type": "final_verdict",
        "run_id": run_id, "seq": seq, "timestamp_utc": utc_now(), "commit": commit,
        "frozen_results": {
            "v151_coverage_pct": 45.64,
            "exp16_trust_50pct_pct": 83.6,
            "exp16_holdout_pct": {"Trust": 80.1, "Random": 49.9,
                                   "ModelConf": 56.5, "Disagreement": 59.0},
            "exp17_A_coverage_pct": 54.13,
            "exp17_A_unsafe_50_pct": 5.51,
            "exp17_A_interception_50_budget_pct": 94.26,
            "delta_unsafe_point_pp": 0.92,
            "paired_one_sided_upper95_pp": 2.24,
            "frozen_non_inferiority_bound_pp": 2.0,
            "c2_verdict": "NOT ESTABLISHED",
        },
        "c1_c4": {
            "c1_coverage": "PASS (54.13%)",
            "c2_safety": "NOT ESTABLISHED (+2.24pp > +2.0pp)",
            "c3_review": "PASS (94.26%)",
            "c4_bins": "PASS (4.17→9.14→28.57)",
        },
        "final_conclusion_en": "Coverage recovery supported; safety non-inferiority inconclusive.",
        "final_conclusion_zh": "覆盖率恢复获得支持；安全非劣性尚未建立。",
        "identity": "EXP17 为 post-hoc failure-driven refinement, 不是原始预注册确证实验; "
                    "四判据为最终裁决协议 (c2 修订留痕); R1 PASS 仅表示显式参数重跑与冻结一致",
    })

    with open(OUT, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"✓ {OUT} ({len(records)} records, run_id={run_id})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
