"""Синтетический ряд космической погоды + события для оффлайн-демонстрации.

Модель: спокойный фон + редкие геомагнитные бури (Kp, Dst) + солнечные
протонные события (SPE) + вспышки. Значения в диапазонах реальных наблюдений
NOAA SWPC / GOES / DSCOVR, но сгенерированы, чтобы не зависеть от сети.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

SERIES_COLUMNS = ["time", "f107", "kp", "dst", "proton_flux_10mev", "electron_flux_2mev", "xray_flux", "flare_class"]


@dataclass(frozen=True)
class WeatherConfig:
    hours: int = 168  # неделя с часовым шагом
    n_storms: int = 2
    n_spe: int = 1
    n_flares: int = 4
    seed: int = 20260918


def _flare_class(flux: float) -> str:
    if flux >= 1e-4:
        return "X"
    if flux >= 1e-5:
        return "M"
    if flux >= 1e-6:
        return "C"
    if flux >= 1e-7:
        return "B"
    return "A"


def generate_space_weather(cfg: WeatherConfig | None = None) -> pd.DataFrame:
    cfg = cfg or WeatherConfig()
    rng = np.random.default_rng(cfg.seed)
    t = pd.date_range("2026-09-18 00:00", periods=cfg.hours, freq="h", tz="UTC")

    f107 = 145 + 12 * np.sin(np.linspace(0, 3 * np.pi, cfg.hours)) + rng.normal(0, 3.0, cfg.hours)
    kp = np.clip(rng.normal(2.0, 0.9, cfg.hours), 0, 9)
    dst = rng.normal(-8, 6, cfg.hours)
    proton = 10 ** rng.normal(-0.7, 0.25, cfg.hours)  # pfu, лог-нормальное
    electron = 10 ** rng.normal(3.2, 0.3, cfg.hours)
    xray = 10 ** rng.normal(-7.2, 0.5, cfg.hours)

    for _ in range(cfg.n_storms):
        start = int(rng.integers(0, max(1, cfg.hours - 30)))
        dur = int(rng.integers(10, 26))
        amp = rng.uniform(3.0, 6.0)
        idx = np.arange(start, min(cfg.hours, start + dur))
        shape = np.exp(-((idx - idx.mean()) ** 2) / (2 * (dur / 3.0) ** 2))
        kp[idx] = np.clip(kp[idx] + amp * shape, 0, 9)
        dst[idx] = dst[idx] - rng.uniform(60, 180) * shape

    for _ in range(cfg.n_spe):
        start = int(rng.integers(0, max(1, cfg.hours - 40)))
        dur = int(rng.integers(18, 40))
        idx = np.arange(start, min(cfg.hours, start + dur))
        rise = np.clip((idx - idx[0]) / 4.0, 0, 1)
        decay = np.exp(-(idx - idx[0]) / (dur / 2.5))
        proton[idx] = np.maximum(proton[idx], 10 ** (rng.uniform(1.6, 3.0)) * rise * decay)

    for _ in range(cfg.n_flares):
        i = int(rng.integers(0, cfg.hours))
        xray[i : min(cfg.hours, i + 3)] *= rng.uniform(50, 900)

    xray = np.clip(xray, 1e-9, 1e-2)
    df = pd.DataFrame(
        {
            "time": t,
            "f107": f107.round(1),
            "kp": kp.round(1),
            "dst": dst.round(0),
            "proton_flux_10mev": proton,
            "electron_flux_2mev": electron,
            "xray_flux": xray,
            "flare_class": [_flare_class(v) for v in xray],
        }
    )
    return df[SERIES_COLUMNS]


def generate_eva_windows(cfg: WeatherConfig | None = None) -> pd.Series:
    """Истинные «безопасные окна» — для оценки метрик (на синтетике)."""

    sw = generate_space_weather(cfg)
    bad = (sw["kp"] >= 5) | (sw["proton_flux_10mev"] >= 10) | (sw["dst"] <= -50)
    return ~bad
