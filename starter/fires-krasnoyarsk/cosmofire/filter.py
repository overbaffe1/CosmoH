"""Отсев ложных тепловых аномалий (промышленные источники, факелы, блики).

Идея: физически осмысленные признаки + простой интерпретируемый классификатор,
поверх которого легко положить градиентный бустинг, если найдутся реальные метки.
Всё детерминировано и работает оффлайн.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

FEATURES = [
    "brightness",
    "frp",
    "n_detections_nearby",
    "frp_mean_nearby",
    "brightness_std_nearby",
    "is_night",
    "is_viirs",
]

#: Известные крупные промышленные источники (факелы, НПЗ, ГРЭС) в зоне сцены.
KNOWN_INDUSTRIAL_SITES: list[tuple[float, float, str]] = [
    (56.0106, 92.8719, "Красноярск (ТЭЦ/промзона)"),
    (56.1128, 93.1119, "Красноярск (НПЗ)"),
    (55.9950, 92.7930, "Красноярск (Академгородок/ТЭЦ)"),
    (54.3250, 91.2300, "Саяногорск (алюминиевый завод)"),
    (53.7650, 91.4300, "Абакан (ТЭЦ)"),
    (58.0100, 92.8700, "Лесосибирск (ЛДК)"),
]


def _neighbourhood_stats(df: pd.DataFrame, radius_km: float = 15.0) -> pd.DataFrame:
    """Признаки окрестности: сколько детекций рядом, насколько однородны яркость и FRP.

    Пожары дают «куст» детекций с высокой вариативностью яркости; одиночные
    промышленные источники — стабильные точки с низким FRP днём и ночью.
    """

    lat = np.radians(df["lat"].to_numpy())
    lon = np.radians(df["lon"].to_numpy())
    n = len(df)
    n_near = np.zeros(n)
    frp_mean = np.zeros(n)
    bright_std = np.zeros(n)

    for i in range(n):
        dlat = lat - lat[i]
        dlon = (lon - lon[i] + np.pi) % (2 * np.pi) - np.pi
        a = np.sin(dlat / 2) ** 2 + np.cos(lat[i]) * np.cos(lat) * np.sin(dlon / 2) ** 2
        dist = 6371.0088 * 2 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))
        near = dist <= radius_km
        n_near[i] = near.sum()
        frp_mean[i] = df["frp"].to_numpy()[near].mean()
        bright_std[i] = df["brightness"].to_numpy()[near].std(ddof=0)

    out = pd.DataFrame(
        {
            "n_detections_nearby": n_near,
            "frp_mean_nearby": frp_mean,
            "brightness_std_nearby": np.nan_to_num(bright_std),
        },
        index=df.index,
    )
    return out


def build_features(detections: pd.DataFrame, radius_km: float = 15.0) -> pd.DataFrame:
    feat = detections.copy()
    feat = pd.concat([feat, _neighbourhood_stats(feat, radius_km)], axis=1)
    feat["is_night"] = (feat["daynight"].astype(str).str.upper() == "N").astype(int)
    feat["is_viirs"] = (feat["instrument"].astype(str).str.upper() == "VIIRS").astype(int)
    return feat


def distance_to_industrial_sites_km(lat: float, lon: float) -> float:
    """Минимальное расстояние до известного промышленного источника."""

    best = np.inf
    for la, lo, _ in KNOWN_INDUSTRIAL_SITES:
        dlat = np.radians(la - lat)
        dlon = np.radians(lo - lon)
        a = np.sin(dlat / 2) ** 2 + np.cos(np.radians(lat)) * np.cos(np.radians(la)) * np.sin(dlon / 2) ** 2
        best = min(best, 6371.0088 * 2 * np.arcsin(np.sqrt(min(1.0, a))))
    return float(best)


@dataclass
class FalsePositiveModel:
    """Интерпретируемая модель правдоподобия «это лесной пожар».

    Скоринг — логистическая комбинация физических признаков. Веса подобраны
    вручную под типовые характеристики MODIS/VIIRS и вынесены в явные поля,
    чтобы на защите можно было объяснить вклад каждого признака.
    """

    #: Веса при нормированных признаках (см. predict_proba). Знак и величина
    #: отражают физику: ярче и мощнее по FRP -> вероятнее пожар; ночью MODIS
    #: чаще даёт артефакты; у известной промзоны — сильный штраф.
    w_brightness: float = 1.05
    w_frp: float = 1.20
    w_cluster: float = 0.30
    w_variability: float = 0.40
    w_night: float = -0.45
    w_viirs: float = 0.15
    w_industry: float = -1.80
    bias: float = -2.10
    industrial_radius_km: float = 6.0
    threshold: float = 0.5

    def features(self, detections: pd.DataFrame) -> pd.DataFrame:
        feat = build_features(detections)
        feat["dist_industry_km"] = [
            distance_to_industrial_sites_km(la, lo) for la, lo in zip(detections["lat"], detections["lon"])
        ]
        feat["near_industry"] = (feat["dist_industry_km"] <= self.industrial_radius_km).astype(int)
        return feat

    def predict_proba(self, detections: pd.DataFrame) -> np.ndarray:
        f = self.features(detections)
        # Нормировка на «физические опорные точки»: 320 K и 10 МВт — типичные
        # пороги разделения для MODIS/VIIRS; /10 и /5 приводят признаки к
        # сопоставимому масштабу, чтобы веса читались как вклады в лог-odds.
        z = (
            self.bias
            + self.w_brightness * ((f["brightness"] - 320.0) / 10.0)
            + self.w_frp * ((f["frp"] - 10.0) / 10.0)
            + self.w_cluster * (np.sqrt(f["n_detections_nearby"]) - 2.4)
            + self.w_variability * ((f["brightness_std_nearby"] - 8.0) / 5.0)
            + self.w_night * f["is_night"]
            + self.w_viirs * f["is_viirs"]
            + self.w_industry * f["near_industry"]
        )
        return 1.0 / (1.0 + np.exp(-z))

    def predict(self, detections: pd.DataFrame) -> np.ndarray:
        return (self.predict_proba(detections) >= self.threshold).astype(int)

    def explain(self, detections: pd.DataFrame, top_k: int = 5) -> list[dict]:
        """Топ-K детекций с раскладкой вклада признаков — для демонстрации на защите."""

        f = self.features(detections)
        p = self.predict_proba(detections)
        order = np.argsort(-p)[:top_k]
        rows = []
        for i in order:
            row = f.iloc[i]
            rows.append(
                {
                    "id": row.get("id", str(i)),
                    "lat": float(row["lat"]),
                    "lon": float(row["lon"]),
                    "p_fire": float(p[i]),
                    "fields": {
                        "brightness": float(row["brightness"]),
                        "frp": float(row["frp"]),
                        "n_detections_nearby": float(row["n_detections_nearby"]),
                        "brightness_std_nearby": float(row["brightness_std_nearby"]),
                        "dist_industry_km": float(row["dist_industry_km"]),
                    },
                    "decision": "пожар" if p[i] >= self.threshold else "ложное срабатывание",
                }
            )
        return rows
