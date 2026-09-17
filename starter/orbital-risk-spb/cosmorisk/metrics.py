"""Метрики детекции опасных периодов (событийное качество).

Для оперативной системы важнее recall (не пропустить SPE/бурю), но
precision влияет на «отмены» выходов, поэтому считаем оба + запас по времени
заблаговременности.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def event_metrics(truth_bad: np.ndarray, pred_bad: np.ndarray) -> dict[str, float]:
    truth_bad = np.asarray(truth_bad).astype(int)
    pred_bad = np.asarray(pred_bad).astype(int)
    tp = int(((truth_bad == 1) & (pred_bad == 1)).sum())
    fp = int(((truth_bad == 0) & (pred_bad == 1)).sum())
    fn = int(((truth_bad == 1) & (pred_bad == 0)).sum())
    tn = int(((truth_bad == 0) & (pred_bad == 0)).sum())
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "csi": round(tp / (tp + fp + fn), 4) if (tp + fp + fn) else 1.0,
    }


def lead_time_hours(truth_bad: np.ndarray, pred_bad: np.ndarray) -> float | None:
    """Сколько часов между первым предупреждением и началом опасного периода."""

    truth_bad = np.asarray(truth_bad).astype(int)
    pred_bad = np.asarray(pred_bad).astype(int)
    starts_truth = np.flatnonzero((truth_bad[1:] == 1) & (truth_bad[:-1] == 0)) + 1
    if truth_bad[0] == 1:
        starts_truth = np.r_[0, starts_truth]
    leads: list[int] = []
    for s in starts_truth:
        prior = np.flatnonzero(pred_bad[:s] == 1)
        if prior.size:
            leads.append(int(s - prior[-1]))
    return round(float(np.mean(leads)), 2) if leads else None


def dose_budget(cumulative_msv: float, limit_msv: float = 1.0) -> dict[str, float]:
    return {
        "cumulative_msv": round(cumulative_msv, 3),
        "limit_msv": limit_msv,
        "utilization": round(cumulative_msv / limit_msv, 3),
        "exceeded": bool(cumulative_msv > limit_msv),
    }
