"""Кластеризация детекций в очаги пожаров (DBSCAN-подобная, без sklearn).

Собственная реализация на numpy: на площадке может не оказаться scikit-learn,
а поведение нужно воспроизводимое и объяснимое на защите.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

EARTH_RADIUS_KM = 6371.0088


def haversine_km(lat1: np.ndarray, lon1: np.ndarray, lat2: float, lon2: float) -> np.ndarray:
    dlat = np.radians(lat1 - lat2)
    dlon = np.radians(lon1 - lon2)
    a = np.sin(dlat / 2) ** 2 + np.cos(np.radians(lat2)) * np.cos(np.radians(lat1)) * np.sin(dlon / 2) ** 2
    return EARTH_RADIUS_KM * 2 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def cluster_detections(
    detections: pd.DataFrame,
    radius_km: float = 12.0,
    min_samples: int = 2,
) -> pd.DataFrame:
    """Возвращает копию входного кадра с колонками cluster_id и cluster_size.

    Алгоритм: жадное «расширение» ядра по радиусу (по сути DBSCAN с
    детерминированным порядком обхода — сортировка по FRP убирает
    зависимость результата от порядка строк).
    """

    df = detections.copy().reset_index(drop=True)
    if df.empty:
        df["cluster_id"] = []
        df["cluster_size"] = []
        return df

    order = np.argsort(-df["frp"].to_numpy(), kind="stable")
    lat = df["lat"].to_numpy()
    lon = df["lon"].to_numpy()
    visited = np.zeros(len(df), dtype=bool)
    labels = np.full(len(df), -1, dtype=int)
    cid = 0

    for idx in order:
        if visited[idx]:
            continue
        neigh = np.flatnonzero(haversine_km(lat, lon, lat[idx], lon[idx]) <= radius_km)
        if len(neigh) < min_samples:
            visited[idx] = True
            continue
        visited[idx] = True
        stack = list(neigh)
        members: set[int] = set(neigh)
        while stack:
            j = stack.pop()
            if not visited[j]:
                visited[j] = True
                n2 = np.flatnonzero(haversine_km(lat, lon, lat[j], lon[j]) <= radius_km)
                if len(n2) >= min_samples:
                    for k in n2:
                        if k not in members:
                            members.add(int(k))
                            stack.append(int(k))
        for m in members:
            labels[m] = cid
            visited[m] = True
        cid += 1

    df["cluster_id"] = labels
    sizes = df.groupby("cluster_id")["cluster_id"].transform("size")
    df["cluster_size"] = sizes
    return df


def cluster_summary(clustered: pd.DataFrame) -> pd.DataFrame:
    """Агрегаты по очагам: центр, число детекций, суммарный FRP, время жизни."""

    fires = clustered[clustered["cluster_id"] >= 0]
    if fires.empty:
        return pd.DataFrame(columns=["cluster_id", "lat", "lon", "detections", "frp_sum", "first_time", "last_time"])

    g = fires.groupby("cluster_id")
    out = pd.DataFrame(
        {
            "lat": g["lat"].mean(),
            "lon": g["lon"].mean(),
            "detections": g.size(),
            "frp_sum": g["frp"].sum(),
            "frp_max": g["frp"].max(),
            "satellites": g["satellite"].nunique(),
            "first_time": g["acq_time"].min(),
            "last_time": g["acq_time"].max(),
        }
    ).reset_index()

    # Оценка уверенности очага: больше подтверждений разными спутниками — выше доверие.
    out["confidence"] = np.clip(out["detections"] / 6.0, 0, 1) * np.clip(out["satellites"] / 3.0, 0, 1)
    out["confidence"] = out["confidence"].round(2)
    return out.sort_values("frp_sum", ascending=False).reset_index(drop=True)
