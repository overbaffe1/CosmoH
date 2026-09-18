"""Синтетическая генерация данных ДЗЗ.

Нужна, чтобы пайплайн и метрики работали, даже если на площадке нет интернета и
не удалось скачать реальные срезы NASA FIRMS / Copernicus. Реальные данные
подключаются провайдерами из `cosmofire.providers` и имеют тот же формат.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

#: Тип детекции: 1 — очаг лесного пожара, 0 — промышленный/сельхоз-источник (ложный).
DETECTION_COLUMNS = [
    "id",
    "lat",
    "lon",
    "acq_time",
    "satellite",
    "instrument",
    "brightness",
    "frp",
    "confidence",
    "daynight",
    "is_fire",
]


@dataclass(frozen=True)
class SceneConfig:
    """Параметры сцены: сколько пожаров и сколько ложных источников."""

    n_fires: int = 8
    n_industry: int = 6
    detections_per_source: tuple[int, int] = (3, 9)
    #: Доля промышленных источников, привязанных к известным промзонам
    #: (остальные — «неизвестные» источники, которые фильтр не знает в лицо).
    industry_at_known_sites: float = 0.7
    seed: int = 20260918


def generate_thermal_anomalies(cfg: SceneConfig | None = None) -> pd.DataFrame:
    """Тепловые аномалии в формате, близком к NASA FIRMS MODIS/VIIRS."""

    cfg = cfg or SceneConfig()
    rng = np.random.default_rng(cfg.seed)
    # Сцена — центр Красноярского края / Приангарья.
    rows: list[dict] = []

    def _source(is_fire: int) -> list[dict]:
        from cosmofire.filter import KNOWN_INDUSTRIAL_SITES

        if is_fire == 0 and cfg.industry_at_known_sites > 0 and rng.random() < cfg.industry_at_known_sites:
            # Реалистичные ложные срабатывания: факелы и ТЭЦ в известных промзонах.
            base_lat, base_lon, _ = KNOWN_INDUSTRIAL_SITES[int(rng.integers(0, len(KNOWN_INDUSTRIAL_SITES)))]
            lat0 = base_lat + rng.normal(0, 0.04)
            lon0 = base_lon + rng.normal(0, 0.06)
        else:
            lat0 = rng.uniform(53.5, 60.5)
            lon0 = rng.uniform(88.0, 100.0)
        n = rng.integers(*cfg.detections_per_source)
        out = []
        for _ in range(int(n)):
            ang = rng.uniform(0, 2 * np.pi)
            r = rng.gamma(1.4, 0.012)
            lat = lat0 + r * np.cos(ang)
            lon = lon0 + r * np.sin(ang) / max(0.3, np.cos(np.radians(lat)))
            # Промышленные факелы: стабильная яркость и низкий FRP (часто недогоревший газ).
            bright = float(rng.normal(347.0 if is_fire else 318.0, 9.0))
            if not is_fire and rng.random() < 0.25:
                bright += rng.uniform(8.0, 20.0)  # «горячие» факелы, похожие на пожар
            out.append(
                {
                    "lat": round(lat, 4),
                    "lon": round(lon, 4),
                    "acq_time": f"{int(rng.integers(4, 21)):02d}{int(rng.integers(0, 60)):02d}",
                    "satellite": str(rng.choice(["Terra", "Aqua", "NOAA-20", "SUOMI NPP", "NOAA-21"])),
                    "instrument": "MODIS" if rng.random() < 0.5 else "VIIRS",
                    "brightness": round(bright, 1),
                    "frp": float(round(abs(rng.normal(18.0 if is_fire else 6.0, 8.0)), 1)),
                    "confidence": "h" if is_fire else str(rng.choice(["l", "n"])),
                    "daynight": "D" if rng.random() < 0.7 else "N",
                    "is_fire": is_fire,
                }
            )
        return out

    for _ in range(cfg.n_fires):
        rows += _source(1)
    for _ in range(cfg.n_industry):
        rows += _source(0)

    df = pd.DataFrame(rows)
    df.insert(0, "id", [f"det_{i:04d}" for i in range(len(df))])
    return df[DETECTION_COLUMNS]


def generate_active_fire_labels(detections: pd.DataFrame, radius_km: float = 12.0) -> pd.DataFrame:
    """Эталон для задачи кластеризации: агрегируем точки в очаги по расстоянию.

    Использует ту же логику, что и продакшн-кластеризация, поэтому применим
    как «эталонные» очаги для расчёта метрик на синтетике.
    """

    from cosmofire.cluster import cluster_detections

    labels = cluster_detections(detections, radius_km=radius_km)
    return pd.DataFrame(
        {
            "cluster_id": labels["cluster_id"].unique(),
            "lat": labels.groupby("cluster_id")["lat"].mean().to_numpy(),
            "lon": labels.groupby("cluster_id")["lon"].mean().to_numpy(),
            "detections": labels.groupby("cluster_id").size().to_numpy(),
            "frp_sum": labels.groupby("cluster_id")["frp"].sum().to_numpy(),
        }
    )


def generate_burn_scar_scene(size: int = 256, seed: int = 7) -> dict[str, np.ndarray]:
    """Синтетическая пара снимков Sentinel-2 (NBR до/после) для картирования гари."""

    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:size, 0:size]
    background = 0.62 + 0.05 * rng.standard_normal((size, size))

    scars = []
    for _ in range(rng.integers(1, 4)):
        cy, cx = rng.uniform(0.25 * size, 0.75 * size, 2)
        r = rng.uniform(0.08 * size, 0.2 * size)
        mask = ((yy - cy) ** 2 + (xx - cx) ** 2) <= r**2
        scars.append(mask)

    burn = np.logical_or.reduce(scars)

    # Реалистичные детали: недогоревшие «острова» внутри контура и рваная кромка.
    islands = rng.random((size, size)) < 0.06
    burn = burn & ~islands
    # Сглаженная кромка: смещаем контур на 1-2 пикселя случайной маской.
    edge_shift = np.roll(np.roll(burn, int(rng.integers(-2, 3)), axis=0), int(rng.integers(-2, 3)), axis=1)
    burn = np.logical_or(burn & ~(rng.random((size, size)) < 0.15), edge_shift & (rng.random((size, size)) < 0.25))

    nbr_pre = np.clip(background, 0, 1)
    # Гарь: падение NBR (SWIR растёт, NIR падает) с неоднородностью по площади.
    severity_field = np.clip(rng.normal(0.42, 0.10, (size, size)), 0.12, 0.7)
    nbr_post = np.clip(nbr_pre - burn * severity_field + 0.03 * rng.standard_normal((size, size)), 0, 1)
    return {
        "nbr_pre": nbr_pre.astype(np.float32),
        "nbr_post": nbr_post.astype(np.float32),
        "burn_mask": burn,
        # 20 м — Sentinel-2 в SWIR после ресэмплинга.
        "pixel_size_m": np.float32(20.0),
    }
