"""Провайдеры реальных данных космической погоды (NOAA SWPC) с дисковым кэшем.

Эндпоинты (публичные, без ключей):
  * Kp:        https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json
  * Dst:       https://services.swpc.noaa.gov/products/geospace/geospace_dst_1m.json
  * Протоны:   https://services.swpc.noaa.gov/json/goes/primary/integral-protons-1-day.json
  * Рентген:   https://services.swpc.noaa.gov/json/goes/primary/xrays-1-day.json
  * F10.7:     https://services.swpc.noaa.gov/json/solar-cycle/observed-solar-cycle-indices.json

Функция `live_weather()` собирает всё в единый DataFrame с колонками из
`cosmorisk.synthetic.SERIES_COLUMNS` — дальше он идёт впрямую в `risk.compute_risk`.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

SWPC = "https://services.swpc.noaa.gov"
ENDPOINTS = {
    "kp": f"{SWPC}/products/noaa-planetary-k-index.json",
    "dst": f"{SWPC}/products/geospace/geospace_dst_1m.json",
    "protons": f"{SWPC}/json/goes/primary/integral-protons-1-day.json",
    "xrays": f"{SWPC}/json/goes/primary/xrays-1-day.json",
    "f107": f"{SWPC}/json/solar-cycle/observed-solar-cycle-indices.json",
}


class OfflineError(RuntimeError):
    """Сеть недоступна — используйте синтетический ряд."""


def _get_json(url: str, cache_path: Path | None = None, timeout: int = 25):
    if cache_path and Path(cache_path).exists():
        return json.loads(Path(cache_path).read_text(encoding="utf-8"))
    try:
        import requests

        r = requests.get(url, timeout=timeout)
        r.raise_for_status()
        data = r.json()
    except Exception as exc:  # pragma: no cover - зависит от сети
        raise OfflineError(f"SWPC недоступен ({url}): {exc}") from exc
    if cache_path:
        Path(cache_path).parent.mkdir(parents=True, exist_ok=True)
        Path(cache_path).write_text(json.dumps(data), encoding="utf-8")
    return data


def fetch_endpoint(name: str, cache_dir: Path | str | None = None):
    if name not in ENDPOINTS:
        raise KeyError(f"Неизвестный эндпоинт: {name}. Доступны: {sorted(ENDPOINTS)}")
    cache = Path(cache_dir) / f"{name}.json" if cache_dir else None
    return _get_json(ENDPOINTS[name], cache)


def _rows(payload, time_key: str) -> pd.DataFrame:
    """SWPC отдаёт либо список словарей, либо список списков с заголовком в [0]."""

    if isinstance(payload, dict):
        payload = payload.get("data", payload)
    if payload and isinstance(payload[0], list):
        header = [str(h).strip().lower() for h in payload[0]]
        df = pd.DataFrame(payload[1:], columns=header)
    else:
        df = pd.DataFrame(payload)
    time_col = next((c for c in df.columns if time_key in str(c)), df.columns[0])
    df["time"] = pd.to_datetime(df[time_col], utc=True, errors="coerce", format="mixed")
    return df.dropna(subset=["time"]).sort_values("time").reset_index(drop=True)


def live_weather(cache_dir: Path | str | None = None, hours: int = 168, flare_class_fn=None) -> pd.DataFrame:
    """Живой ряд космической погоды, приведённый к формату пайплайна.

    Часовое разрешение, окно `hours`. Если какой-то источник недоступен, его
    колонка заполняется умеренным фоновым значением и в отчёт попадает пометка.
    """

    from cosmorisk.synthetic import _flare_class

    flare_class_fn = flare_class_fn or _flare_class
    frames: dict[str, pd.Series] = {}

    kp = _rows(fetch_endpoint("kp", cache_dir), "time")
    kp_val_col = next((c for c in kp.columns if "kp" in c and c != "time"), None)
    if kp_val_col:
        frames["kp"] = kp.set_index("time")[kp_val_col].astype(float)

    dst = _rows(fetch_endpoint("dst", cache_dir), "time")
    dst_val_col = next((c for c in dst.columns if "dst" in c), None)
    if dst_val_col:
        frames["dst"] = dst.set_index("time")[dst_val_col].astype(float)

    protons = _rows(fetch_endpoint("protons", cache_dir), "time")
    p_col = next((c for c in protons.columns if "10" in str(c) and "p" in str(c)), None) or next(
        (c for c in protons.columns if "flux" in str(c)), None
    )
    if p_col:
        frames["proton_flux_10mev"] = protons.set_index("time")[p_col].astype(float)

    xrays = _rows(fetch_endpoint("xrays", cache_dir), "time")
    x_col = next((c for c in xrays.columns if "flux" in str(c)), None)
    if x_col:
        frames["xray_flux"] = xrays.set_index("time")[x_col].astype(float)

    if not frames:
        raise OfflineError("Не удалось получить ни одного ряда SWPC")

    df = pd.concat(frames, axis=1).sort_index().resample("1h").mean()
    df = df.tail(hours).interpolate(limit_direction="both").reset_index()

    f107 = _rows(fetch_endpoint("f107", cache_dir), "time")
    f_col = next((c for c in f107.columns if "f10" in str(c).replace(".", "")), None)
    df["f107"] = float(f107[f_col].dropna().iloc[-1]) if f_col and f107[f_col].notna().any() else 150.0

    for col, default in (("kp", 2.0), ("dst", -8.0), ("proton_flux_10mev", 0.3), ("xray_flux", 1e-7)):
        if col not in df.columns:
            df[col] = default
        df[col] = df[col].fillna(default)
    df["proton_flux_10mev"] = np.clip(df["proton_flux_10mev"], 1e-3, None)
    df["xray_flux"] = np.clip(df["xray_flux"], 1e-9, 1e-2)
    df["electron_flux_2mev"] = df.get("electron_flux_2mev", pd.Series([1e3] * len(df)))
    df["flare_class"] = [flare_class_fn(float(v)) for v in df["xray_flux"]]
    return df[["time", "f107", "kp", "dst", "proton_flux_10mev", "electron_flux_2mev", "xray_flux", "flare_class"]]
