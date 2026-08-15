"""
data_weight 校准 — 扩充版逻辑回归 (干净 + 故障注入样本合并)

方法: 895 条干净样本 (数据证据恒为 0) + 每样本 4 类故障注入变体
     (数据证据有分数变化)。合并后跑逻辑回归, 四类证据同时拟合,
     得到 data_weight 的拟合值。

边界声明: 故障注入样本的数据证据分是模拟的, 反映注入故障场景;
          对自然故障的外推需另行验证。

用法:
    python -m src.calibrate.data_weight_regression
"""

import json
import random
from pathlib import Path

import numpy as np

RECORDS_PATH = Path("data/batch_calibration/records_all.json")
OUT_PATH = Path("docs/experiments/data_weight_regression.json")

P_TOL = 0.5
S_TOL = 1.0

random.seed(42)
np.random.seed(42)

FAULTS = ["channel_missing", "clipping", "gap", "strong_noise"]


def compute_data_evidence_score(missing_channels, gap_ratio,
                                clipping_ratio, snr_db):
    """按 data_evidence.py 校准规则计算数据证据分"""
    score = 0.0
    if len(missing_channels) >= 2:
        score += 17
    elif len(missing_channels) == 1:
        score += 8.6
    if gap_ratio > 0.10:
        score += 9.9
    elif gap_ratio > 0.02:
        score += 4.9
    if clipping_ratio > 0.10:
        score += 10.7
    elif clipping_ratio > 0.02:
        score += 5.4
    if snr_db is not None:
        if snr_db < 3.0:
            score += 27.4
        elif snr_db < 8.0:
            score += 13.7
    return min(score, 30.0)


def inject_fault(record, fault_type):
    """返回 (修改后预测, 数据证据分)"""
    preds = {m: dict(p) for m, p in record["predictions"].items()}

    if fault_type == "channel_missing":
        preds["PickBlue"] = {"P_pick": None, "S_pick": None, "confidence": None}
        score = compute_data_evidence_score(["Z"], 0.0, 0.0, 20.0)

    elif fault_type == "clipping":
        for m in preds:
            if preds[m]["confidence"] is not None:
                preds[m]["confidence"] = max(0.1, preds[m]["confidence"] * 0.4)
        score = compute_data_evidence_score([], 0.0, 0.30, 20.0)

    elif fault_type == "gap":
        victim = random.choice(list(preds.keys()))
        preds[victim]["P_pick"] = None
        score = compute_data_evidence_score([], 0.15, 0.0, 20.0)

    elif fault_type == "strong_noise":
        for m in preds:
            if preds[m]["P_pick"] is not None:
                preds[m]["P_pick"] += random.uniform(-1.5, 1.5)
            if preds[m]["S_pick"] is not None:
                preds[m]["S_pick"] += random.uniform(-2.0, 2.0)
            if preds[m]["confidence"] is not None:
                preds[m]["confidence"] = max(0.1, preds[m]["confidence"] * 0.6)
        score = compute_data_evidence_score([], 0.0, 0.0, 2.0)

    return preds, score


def extract_other_features(preds):
    """单模型 / 多模型 / 物理 三类特征 (与 weight_calibration_batch 一致)"""
    confs = [p["confidence"] for p in preds.values()
             if p.get("confidence") is not None]
    single_feat = 1.0 - min(confs) if confs else 0.0

    p_times = [p["P_pick"] for p in preds.values() if p["P_pick"] is not None]
    s_times = [p["S_pick"] for p in preds.values() if p["S_pick"] is not None]
    p_spread = (max(p_times) - min(p_times)) if len(p_times) >= 2 else 0.0
    s_spread = (max(s_times) - min(s_times)) if len(s_times) >= 2 else 0.0
    multi_feat = max(p_spread, s_spread)

    physics_feat = 0.0
    for p in preds.values():
        if p["P_pick"] is not None and p["S_pick"] is not None:
            sp = p["S_pick"] - p["P_pick"]
            if sp < 0:
                physics_feat = max(physics_feat, 1.0)
            elif sp < 5 or sp > 30:
                physics_feat = max(physics_feat, 0.5)
    return single_feat, multi_feat, physics_feat


def label_wrong(record, preds):
    """相对真值, 是否存在错误拾取"""
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

    X_rows, y_rows = [], []

    for record in records:
        # 1. 干净版本 (数据证据 = 0)
        clean_preds = {m: dict(p) for m, p in record["predictions"].items()}
        s, m, ph = extract_other_features(clean_preds)
        X_rows.append([0.0, s, m, ph])
        y_rows.append(label_wrong(record, clean_preds))

        # 2. 四类故障注入版本
        for fault in FAULTS:
            preds, data_score = inject_fault(record, fault)
            s, m, ph = extract_other_features(preds)
            X_rows.append([data_score, s, m, ph])
            y_rows.append(label_wrong(record, preds))

    X = np.array(X_rows)
    y = np.array(y_rows)
    print(f"合并样本: {len(y)} (895 干净 + {len(y)-895} 故障注入)")
    print(f"错误样本: {y.sum()} ({y.mean():.1%})")
    print(f"数据证据分数分布: min={X[:,0].min():.1f} max={X[:,0].max():.1f} "
          f"非零占比={(X[:,0]>0).mean():.1%}")

    # 标准化 + 逻辑回归
    X_mean = X.mean(axis=0, keepdims=True)
    X_std = X.std(axis=0, keepdims=True) + 1e-9
    Xn = (X - X_mean) / X_std

    def sigmoid(z):
        return 1 / (1 + np.exp(-np.clip(z, -30, 30)))

    w = np.zeros(5)
    lr = 0.5
    for _ in range(3000):
        z = w[0] + Xn @ w[1:]
        w[0] -= lr * (sigmoid(z) - y).mean()
        w[1:] -= lr * (Xn.T @ (sigmoid(z) - y)) / len(y)

    names = ["bias", "data", "single_model", "multi_model", "physics"]
    print("\n标准化系数 (可比重要性):")
    for n, v in zip(names[1:], w[1:]):
        print(f"  {n:14s}: {v:+.4f}")

    pos = np.clip(w[1:], 0, None)
    total = pos.sum()
    if total > 0:
        norm = pos / total
        print("\n归一化权重:")
        for n, v in zip(names[1:], norm):
            print(f"  {n:14s}: {v:.2%}")

    z = w[0] + Xn @ w[1:]
    pred = (sigmoid(z) > 0.5).astype(int)
    acc = (pred == y).mean()
    print(f"\n拟合准确率: {acc:.1%} (基线 {1-y.mean():.1%})")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump({
            "method": "logistic regression, clean + fault-injected",
            "n_clean": 895,
            "n_injected": len(y) - 895,
            "n_total": int(len(y)),
            "n_wrong": int(y.sum()),
            "std_coefficients": {n: float(v) for n, v in zip(names[1:], w[1:])},
            "normalized_weights": {n: float(v) for n, v in zip(names[1:], norm)} if total > 0 else None,
            "fit_accuracy": float(acc),
            "caveat": "data 证据分来自注入故障模拟, 自然故障需另行验证",
        }, f, indent=2, ensure_ascii=False)
    print(f"\n✅ 结果 → {OUT_PATH}")


if __name__ == "__main__":
    main()
