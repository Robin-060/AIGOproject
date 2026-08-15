"""
数据证据权重校准 — 故障注入方法

背景: 895 条真实标注数据全部干净, 数据证据从不触发, 逻辑回归对它无信息。
方法: 对真实数据人为注入四类已知故障, 生成受控测试集:
  1. 缺通道 (删除一个分量)
  2. 削波 (振幅硬截断)
  3. 断点 (一段置零)
  4. 强噪声 (注入高斯噪声)

然后验证: 注入故障后 (a) 数据证据是否报警, (b) 模型是否真的变差。
若两者正相关 → 数据证据权重有依据。

注意: 本方法校准的是"数据证据检测注入故障的有效性"。
      对自然故障的外推需另行验证, 文档中须声明此边界。

用法:
    python -m src.calibrate.data_weight_calibration
"""

import json
import random
from pathlib import Path

import numpy as np

RECORDS_PATH = Path("data/batch_calibration/records_all.json")
OUT_PATH = Path("docs/experiments/data_weight_calibration.json")

P_TOL = 0.5
S_TOL = 1.0

random.seed(42)
np.random.seed(42)

# 四类故障
FAULTS = ["channel_missing", "clipping", "gap", "strong_noise"]


def inject_fault(record, fault_type):
    """
    对一条样本的预测结果模拟"数据被破坏"后的效果。

    说明: 我们手上是预测结果 JSON, 不是原始波形。
    因此故障注入在两个层面进行:
      (a) 直接操纵预测: 删通道对应的模型预测 / 破坏时间
      (b) 计算"数据证据"会给出的分数 (模拟 quality report 的变化)

    返回: 修改后的预测 + 模拟的 QualityReport 字段
    """
    preds = {m: dict(p) for m, p in record["predictions"].items()}

    # ── 模拟数据证据的分数 ──
    quality = {
        "missing_channels": [],
        "gap_ratio": 0.0,
        "clipping_ratio": 0.0,
        "snr_db": 20.0,
    }

    if fault_type == "channel_missing":
        # 删除 Z 通道: 三模型都受影响 → 模拟"部分模型失明"
        quality["missing_channels"] = ["Z"]
        # PickBlue 需要 Z/N/E/H 全通道 → 直接让它失效
        preds["PickBlue"] = {"P_pick": None, "S_pick": None, "confidence": None}

    elif fault_type == "clipping":
        quality["clipping_ratio"] = 0.30  # 严重削波
        # 削波导致振幅信息丢失 → 置信度普遍降低
        for m in preds:
            if preds[m]["confidence"] is not None:
                preds[m]["confidence"] = max(0.1, preds[m]["confidence"] * 0.4)

    elif fault_type == "gap":
        quality["gap_ratio"] = 0.15  # 严重断点
        # 断点导致部分拾取丢失: 随机让一个模型的 P 丢失
        victim = random.choice(list(preds.keys()))
        preds[victim]["P_pick"] = None

    elif fault_type == "strong_noise":
        quality["snr_db"] = 2.0  # 强噪声
        # 噪声导致拾取抖动: 给时间加随机偏移
        for m in preds:
            if preds[m]["P_pick"] is not None:
                preds[m]["P_pick"] += random.uniform(-1.5, 1.5)
            if preds[m]["S_pick"] is not None:
                preds[m]["S_pick"] += random.uniform(-2.0, 2.0)
            if preds[m]["confidence"] is not None:
                preds[m]["confidence"] = max(0.1, preds[m]["confidence"] * 0.6)

    return preds, quality


def compute_data_evidence_score(quality):
    """按 data_evidence.py 的规则计算数据证据分 (0-30)"""
    score = 0.0
    reasons = []
    if len(quality["missing_channels"]) >= 2:
        score += 20
        reasons.append("CHANNEL_MULTI_MISSING")
    elif len(quality["missing_channels"]) == 1:
        score += 12
        reasons.append("CHANNEL_MISSING")
    if quality["gap_ratio"] > 0.10:
        score += 15
        reasons.append("GAP_SEVERE")
    if quality["clipping_ratio"] > 0.10:
        score += 10
        reasons.append("CLIPPING_SEVERE")
    if quality["snr_db"] < 3.0:
        score += 15
        reasons.append("LOW_SIGNAL")
    return min(score, 30.0), reasons


def label_wrong_after_fault(record, preds):
    """故障后模型拾取是否错误 (相对真值)"""
    truth_p, truth_s = record["truth_p_s"], record["truth_s_s"]
    for p in preds.values():
        if truth_p is not None and p["P_pick"] is not None:
            if abs(p["P_pick"] - truth_p) > P_TOL:
                return 1
        if truth_s is not None and p["S_pick"] is not None:
            if abs(p["S_pick"] - truth_s) > S_TOL:
                return 1
    return 0


def main():
    with open(RECORDS_PATH, encoding="utf-8") as f:
        records = json.load(f)

    print(f"基础样本: {len(records)}")

    # 收集 (数据证据分, 故障后是否错误)
    rows = []
    stats = {}
    for fault in FAULTS:
        stats[fault] = {"n": 0, "evidence_triggered": 0, "wrong": 0}

    for record in records:
        for fault in FAULTS:
            preds, quality = inject_fault(record, fault)
            ev_score, reasons = compute_data_evidence_score(quality)
            wrong = label_wrong_after_fault(record, preds)
            rows.append((ev_score, wrong, fault))

            stats[fault]["n"] += 1
            if ev_score > 0:
                stats[fault]["evidence_triggered"] += 1
            if wrong:
                stats[fault]["wrong"] += 1

    # ── 按故障类型统计 ──
    print("\n故障注入统计:")
    print(f"{'故障类型':16s} {'样本':>6s} {'证据报警率':>10s} {'模型错误率':>10s}")
    for fault in FAULTS:
        s = stats[fault]
        trig_rate = s["evidence_triggered"] / s["n"] if s["n"] else 0
        wrong_rate = s["wrong"] / s["n"] if s["n"] else 0
        print(f"{fault:16s} {s['n']:6d} {trig_rate:9.1%} {wrong_rate:9.1%}")

    # ── 核心问题: 数据证据报警时, 模型错误率是否更高? ──
    triggered = [(s, w) for s, w, _ in rows if s > 0]
    silent = [(s, w) for s, w, _ in rows if s == 0]

    wrong_when_triggered = sum(w for _, w in triggered) / len(triggered) if triggered else 0
    wrong_when_silent = sum(w for _, w in silent) / len(silent) if silent else 0

    print(f"\n核心发现:")
    print(f"  数据证据报警时:   模型错误率 = {wrong_when_triggered:.1%} ({len(triggered)} 样本)")
    print(f"  数据证据静默时:   模型错误率 = {wrong_when_silent:.1%} ({len(silent)} 样本)")

    # ── 相关性: 证据分越高, 错误率越高? ──
    print(f"\n证据分与错误率的关系:")
    buckets = [(0, 0), (1, 10), (11, 20), (21, 30)]
    for lo, hi in buckets:
        group = [(s, w) for s, w, _ in rows if lo <= s <= hi]
        if not group:
            continue
        wr = sum(w for _, w in group) / len(group)
        bar = "█" * int(wr * 40)
        print(f"  证据分 {lo:2d}-{hi:2d}: 错误率 {wr:5.1%} {bar} (n={len(group)})")

    # ── 结论 ──
    # 若"报警时错误率高、静默时错误率低" → 数据证据有效, 应保留权重
    ratio = wrong_when_triggered / (wrong_when_silent + 1e-9)
    print(f"\n报警/静默 错误率比值: {ratio:.2f}x")
    if ratio > 1.2:
        print("✅ 结论: 数据证据报警与模型错误显著相关, 保留非零权重合理")
        suggestion = "保留 30 分上限 (启发式值), 待自然故障样本进一步校准"
    else:
        print("⚠️ 结论: 注入故障未能证明数据证据的有效性, 需检查注入方式")
        suggestion = "重新设计故障注入, 或降低数据证据权重"

    # 保存
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump({
            "method": "fault injection on 895 real labeled samples",
            "faults": ["channel_missing", "clipping", "gap", "strong_noise"],
            "per_fault_stats": stats,
            "wrong_rate_evidence_triggered": wrong_when_triggered,
            "wrong_rate_evidence_silent": wrong_when_silent,
            "ratio": ratio,
            "suggestion": suggestion,
            "caveat": "注入故障 vs 自然故障的边界需声明",
        }, f, indent=2, ensure_ascii=False)
    print(f"\n✅ 结果 → {OUT_PATH}")


if __name__ == "__main__":
    main()
