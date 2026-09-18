"""Провайдеры реальных данных: NASA FIRMS (тепловые аномалии) и Sentinel-2 (гарь).

Все функции рассчитаны на работу через обычный HTTP (requests) и умеют кэшировать
ответ на диск, чтобы на площадке без стабильной сети хватило одного успешного
запроса. Если сети нет — поднимается `OfflineError`, и вызывающий код использует
синтетический провайдер.

Ссылки:
  * NASA FIRMS Area API: https://firms.modaps.eosdis.nasa.gov/api/area/
  * Copernicus STAC:     https://catalogue.dataspace.copernicus.eu/stac
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

FIRMS_AREA_URL = "https://firms.modaps.eosdis.nasa.gov/api/area/csv/{map_key}/{source}/{bbox}/{days}"
STAC_SEARCH_URL = "https://catalogue.dataspace.copernicus.eu/stac/search"

FIRMS_RENAME = {
    "latitude": "lat",
    "longitude": "lon",
    "acq_date": "acq_date",
    "acq_time": "acq_time",
    "bright_ti4": "brightness",
    "bright_ti5": "brightness_ti5",
    "brightness": "brightness",
    "frp": "frp",
    "confidence": "confidence",
    "daynight": "daynight",
    "satellite": "satellite",
    "instrument": "instrument",
}


class OfflineError(RuntimeError):
    """Сеть недоступна — использовать синтетический провайдер."""


def _http_get_csv(url: str, cache: Path | None, timeout: int = 25) -> pd.DataFrame:
    if cache and Path(cache).exists():
        return pd.read_csv(cache)
    try:
        import requests

        r = requests.get(url, timeout=timeout)
        r.raise_for_status()
    except Exception as exc:  # pragma: no cover - зависит от сети
        raise OfflineError(f"FIRMS недоступен: {exc}") from exc
    df = pd.read_csv(io.StringIO(r.text))
    if cache:
        Path(cache).parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(cache, index=False)
    return df


def firms_area_csv(url: str, cache: Path | str | None = None) -> pd.DataFrame:
    """Загружает срез FIRMS по готовому URL и приводит к формату пайплайна."""

    raw = _http_get_csv(url, Path(cache) if cache else None)
    df = raw.rename(columns=FIRMS_RENAME).copy()
    if "acq_date" in df.columns:
        df["acq_date"] = df["acq_date"].astype(str)
    df["acq_time"] = df.get("acq_time", pd.Series(["0000"] * len(df))).astype(str).str.zfill(4)
    for col in ("brightness", "frp"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    if "instrument" not in df.columns:
        df["instrument"] = "MODIS" if "brightness" in raw.columns else "VIIRS"
    df["is_fire"] = 1  # в реальном срезе метки нет: её даёт модель или Авиалесоохрана
    keep = [c for c in ["lat", "lon", "acq_time", "satellite", "instrument", "brightness", "frp", "confidence", "daynight", "is_fire"] if c in df.columns]
    return df[keep].dropna(subset=["lat", "lon"]).reset_index(drop=True)


@dataclass
class StacScene:
    """Пара растров NBR (до/после) для картирования гари."""

    nbr_pre: np.ndarray
    nbr_post: np.ndarray
    pixel_size_m: float
    cloud_mask: np.ndarray | None = None


def stac_search(
    bbox: tuple[float, float, float, float],
    date_range: tuple[str, str],
    max_cloud: int = 30,
    limit: int = 20,
) -> list[dict]:
    """Поиск сцен Sentinel-2 L2A в STAC Copernicus (только метаданные).

    Возвращает список объектов-сцен с полями `id`, `datetime`, `cloud_cover`,
    `assets` (содержит ссылки на B08/B12 в формате COG).
    """

    payload = {
        "collections": ["sentinel-2-l2a"],
        "bbox": list(bbox),
        "datetime": f"{date_range[0]}T00:00:00Z/{date_range[1]}T23:59:59Z",
        "limit": limit,
        "query": {"eo:cloud_cover": {"lt": max_cloud}},
    }
    try:
        import requests

        r = requests.post(STAC_SEARCH_URL, json=payload, timeout=30)
        r.raise_for_status()
        items = r.json().get("features", [])
    except Exception as exc:  # pragma: no cover - зависит от сети
        raise OfflineError(f"STAC недоступен: {exc}") from exc
    return [
        {
            "id": it.get("id"),
            "datetime": it.get("properties", {}).get("datetime"),
            "cloud_cover": it.get("properties", {}).get("eo:cloud_cover"),
            "assets": it.get("assets", {}),
        }
        for it in items
    ]


def read_band_window(asset_url: str, bbox: tuple[float, float, float, float]) -> tuple[np.ndarray, float]:
    """Читает окно растра из COG. Требуется rasterio: `pip install rasterio`.

    Возвращает массив значений и размер пикселя в метрах.
    """

    try:
        import rasterio
        from rasterio.windows import from_bounds
    except ImportError as exc:  # pragma: no cover
        raise NotImplementedError(
            "Для чтения Sentinel-2 COG нужен rasterio: pip install rasterio. "
            "Альтернатива — скачать GeoTIFF вручную и передать массив в burnscar.map_burn_scar."
        ) from exc

    with rasterio.open(asset_url) as src:
        win = from_bounds(*bbox, transform=src.transform)
        arr = src.read(1, window=win).astype("float32")
        px = float(abs(src.transform.a)) * 111_320 * np.cos(np.radians((bbox[1] + bbox[3]) / 2))
    return arr, px


def nbr(nir: np.ndarray, swir: np.ndarray) -> np.ndarray:
    """NBR = (NIR - SWIR) / (NIR + SWIR), устойчиво к нулям в знаменателе."""

    num = nir.astype("float32") - swir.astype("float32")
    den = nir.astype("float32") + swir.astype("float32")
    return np.where(np.abs(den) < 1e-6, 0.0, num / np.maximum(np.abs(den), 1e-6)).astype("float32")


def burn_scar_from_stac(
    bbox: tuple[float, float, float, float],
    date_range: tuple[str, str],
    max_cloud: int = 30,
) -> StacScene:
    """Собирает пару NBR (до/после) из двух наименее облачных сцен Sentinel-2 L2A.

    Требует rasterio (чтение COG) и сеть. Если ни того, ни другого нет —
    используйте `cosmofire.synthetic.generate_burn_scar_scene()`: формат тот же.
    """

    items = stac_search(bbox, date_range, max_cloud=max_cloud)
    if len(items) < 2:
        raise OfflineError("Нужно минимум две сцены для расчёта dNBR")
    items = sorted(items, key=lambda it: it["cloud_cover"] if it["cloud_cover"] is not None else 100)
    pre, post = items[0], items[-1]

    def _nbr_of(item: dict) -> tuple[np.ndarray, np.ndarray | None, float]:
        assets = item["assets"]
        b08 = next((v["href"] for k, v in assets.items() if k.lower() in {"b08", "b08_10m"}), None)
        b12 = next((v["href"] for k, v in assets.items() if k.lower() in {"b12", "b12_20m"}), None)
        scl = next((v["href"] for k, v in assets.items() if k.lower() in {"scl", "scl_20m"}), None)
        if not b08 or not b12:
            raise OfflineError(f"В сцене {item['id']} нет каналов B08/B12")
        nir, px = read_band_window(b08, bbox)
        swir, _ = read_band_window(b12, bbox)
        cloud = None
        if scl:
            try:
                scl_arr, _ = read_band_window(scl, bbox)
                cloud = np.isin(scl_arr.astype(int), [3, 8, 9, 10, 11])  # тени, облака, циррус
            except Exception:  # pragma: no cover
                cloud = None
        return nbr(nir, swir), cloud, px

    nbr_pre, _, px = _nbr_of(pre)
    nbr_post, cloud_post, _ = _nbr_of(post)
    return StacScene(nbr_pre=nbr_pre, nbr_post=nbr_post, pixel_size_m=px, cloud_mask=cloud_post)
