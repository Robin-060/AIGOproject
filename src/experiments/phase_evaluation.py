"""
相位级评估模块 — C 契约 v1.2 评价单位 (Primary: (sample_id, phase))

冻结口径 (configs/semifinal_main.yaml, semifinal_v1.1):
  - N_eval = primary_inclusion=True 的 (sample_id, phase) 单元数 = 1306
    (P 真值 657 + S 真值 649)
  - 正确性容差: P 0.5s / S 1.0s (依据与敏感性证据见 evaluation_protocol.md 2.1)
  - 成对判定降级为 Secondary (事件级完整性声明用), 本模块只做 Primary
  - NO_PICK: 真值要求该相位时为错误 (计入拦截口径), 不进入自动输出

用法:
    from src.experiments.phase_evaluation import (
        build_phase_units, phase_verdict, evaluate_units, PHASE_TOL
    )
"""

import json
from pathlib import Path
from typing import Callable, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[2]
RECORDS_PATH = ROOT / "data" / "batch_calibration" / "records_all.json"

PHASE_TOL = {"P": 0.5, "S": 1.0}
MODELS = ("PhaseNet", "PickBlue", "OBSTransformer")


def phase_verdict(pred: Optional[float], truth: float, phase: str) -> str:
    """相位级判定: correct / wrong / no_pick."""
    if pred is None:
        return "no_pick"
    if abs(pred - truth) <= PHASE_TOL[phase]:
        return "correct"
    return "wrong"


def build_phase_units(records: List[dict]) -> List[dict]:
    """
    把样本级记录展开为相位级评估单元。

    primary_inclusion=True 当且仅当该相位存在参考到时。
    已自查 (2026-08-28): 全部 895 条均有 source_id, 均为事件窗口;
    真值缺失 = 事件窗口但该相位在源数据集中无标注 (trace_*_status 为空),
    按 C 契约 Unknown 不进入 primary。
    """
    units = []
    for record in records:
        parts = record["sample_id"].split(".")
        station = parts[1] if len(parts) > 1 else "UNKNOWN"
        deployment = parts[0] if parts else "UNKNOWN"
        for phase in ("P", "S"):
            truth = record.get(f"truth_{phase.lower()}_s")
            preds = {
                model: (record["predictions"].get(model) or {}).get(f"{phase}_pick")
                for model in MODELS
            }
            units.append({
                "sample_id": record["sample_id"],
                "chunk": record["chunk"],
                "station": station,
                "deployment": deployment,
                "phase": phase,
                "reference_time_s": truth,
                "expected_event": "EVENT",
                "predictions": preds,
                "primary_inclusion": truth is not None,
                "exclusion_reason": (
                    None if truth is not None
                    else "event_phase_unpicked_in_source_dataset"
                ),
            })
    return units


def evaluate_units(
    units: List[dict],
    output_fn: Callable[[dict], Optional[float]],
    gate_fn: Optional[Callable[[dict], bool]] = None,
) -> Dict[str, float]:
    """
    相位级指标计算 (C 契约表格29/31 口径)。

    output_fn(unit) -> 该策略在此相位输出的拾取时间 (None = 无输出/NO_PICK)
    gate_fn(unit)   -> 是否自动放行 (None = 全部自动, 无门槛)

    返回: n_eval, coverage, unsafe_output_rate, review_burden,
          error_interception_rate, auto_correct, auto_wrong, review_errors
    """
    n_eval = 0
    auto_correct = auto_wrong = 0
    review_errors = 0        # 被拦下的错误 (含真值要求相位的 no_pick)
    total_errors = 0         # 全部错误 (自动放行的 wrong + 被拦下的错误)

    for unit in units:
        if not unit["primary_inclusion"]:
            continue
        n_eval += 1
        out = output_fn(unit)
        v = phase_verdict(out, unit["reference_time_s"], unit["phase"])
        is_error = v == "wrong" or v == "no_pick"  # no_pick 在真值要求相位时计错误
        if is_error:
            total_errors += 1
        auto = gate_fn is None or gate_fn(unit)
        if auto and v != "no_pick":
            if v == "correct":
                auto_correct += 1
            else:
                auto_wrong += 1
        else:
            # 未自动放行 (门控拒绝或 NO_PICK 落 ABSTAIN)
            if is_error:
                review_errors += 1

    auto = auto_correct + auto_wrong
    coverage = auto / n_eval if n_eval else 0.0
    unsafe = auto_wrong / auto if auto else 0.0
    review = (n_eval - auto) / n_eval if n_eval else 0.0
    interception = review_errors / total_errors if total_errors else 0.0
    return {
        "n_eval": n_eval,
        "auto": auto,
        "auto_correct": auto_correct,
        "auto_wrong": auto_wrong,
        "coverage": coverage,
        "unsafe_output_rate": unsafe,
        "review_burden": review,
        "error_interception_rate": interception,
    }


def load_records() -> List[dict]:
    return json.loads(RECORDS_PATH.read_text(encoding="utf-8"))
