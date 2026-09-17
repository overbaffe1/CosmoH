"""Метрики качества: детекция (precision/recall/F1), кластеризация, площадь гари.

Метрики считаются как по точке, так и по очагу — на защите важно показать,
что система не «рисует» лишние пожары и не теряет реальные.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def point_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    y_true = np.asarray(y_true).astype(int)
    y_pred = np.asarray(y_pred).astype(int)
    tp = int(np.sum((y_true == 1) & (y_pred == 1)))
    fp = int(np.sum((y_true == 0) & (y_pred == 1)))
    fn = int(np.sum((y_true == 1) & (y_pred == 0)))
    tn = int(np.sum((y_true == 0) & (y_pred == 0)))
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "accuracy": round((tp + tn) / max(1, len(y_true)), 4),
    }


def cluster_metrics(truth: pd.DataFrame, pred: pd.DataFrame, radius_km: float = 12.0) -> dict[str, float]:
    """Сопоставление очагов 1-к-1 по расстоянию (жадный матчинг).

    Возвращает precision/recall по очагам и локализационную ошибку в км.
    """

    from cosmofire.cluster import haversine_km

    if truth.empty or pred.empty:
        return {"site_precision": 0.0, "site_recall": 0.0, "site_f1": 0.0, "mean_loc_error_km": None}

    t_lat = truth["lat"].to_numpy()
    t_lon = truth["lon"].to_numpy()
    p_lat = pred["lat"].to_numpy()
    p_lon = pred["lon"].to_numpy()

    pairs: list[tuple[float, int, int]] = []
    for i in range(len(p_lat)):
        d = haversine_km(t_lat, t_lon, p_lat[i], p_lon[i])
        for j in np.argsort(d):
            if d[j] <= radius_km:
                pairs.append((float(d[j]), i, int(j)))
                break
    pairs.sort()

    used_p: set[int] = set()
    used_t: set[int] = set()
    errs: list[float] = []
    for dist, i, j in pairs:
        if i in used_p or j in used_t:
            continue
        used_p.add(i)
        used_t.add(j)
        errs.append(dist)

    matched = len(used_p)
    precision = matched / len(p_lat) if p_lat.size else 0.0
    recall = matched / len(t_lat) if t_lat.size else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {
        "truth_sites": int(len(t_lat)),
        "pred_sites": int(len(p_lat)),
        "matched_sites": matched,
        "site_precision": round(precision, 4),
        "site_recall": round(recall, 4),
        "site_f1": round(f1, 4),
        "mean_loc_error_km": round(float(np.mean(errs)), 3) if errs else None,
    }


def area_metrics(pred_ha: float, truth_ha: float) -> dict[str, float]:
    if truth_ha <= 0:
        return {"abs_error_ha": None, "rel_error": None}
    return {
        "pred_ha": round(pred_ha, 2),
        "truth_ha": round(truth_ha, 2),
        "abs_error_ha": round(pred_ha - truth_ha, 2),
        "rel_error": round((pred_ha - truth_ha) / truth_ha, 4),
    }
