"""Модель риска ВКД: композитный индекс + дозовая оценка.

Физика (упрощённо, но с реальными порогами):
  * Kp >= 5 — геомагнитная буря: рост потоков захваченных частиц на НОО.
  * Протоны >= 10 pfu (>10 МэВ) — солнечное протонное событие: опасность для ВКД.
  * Dst <= -50 нТл — сильная буря, рост дозы на внешней стороне орбиты.
  * Вспышка класса M/X — рост мягкого рентгена + риск последующего SPE.
  * Наведённая радиация за защитой скафандра (2 г/см² Al эквивалент) — доза
    в мЗв/ч, сравнивается с лимитом ВКД 1 мЗв/сутки (NASA STD-3001, упрощённо).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

#: Пороговые уровни (NOAA G/S/R-шкалы, упрощённо).
KP_STORM = 5.0
DST_STORM = -50.0
PROTON_SPE = 10.0
XRAY_M = 1e-5
XRAY_X = 1e-4

#: Лимит дозы за ВКД, мЗв (упрощённо; NASA STD-3001 даёт ~1 мЗв/сут для ВКД).
EVA_DOSE_LIMIT_MSV = 1.0

#: Типовая длительность ВКД для оценки накопленной дозы, часы.
TYPICAL_EVA_HOURS = 7.0


def _norm(x, lo, hi):
    return np.clip((np.asarray(x, dtype=float) - lo) / (hi - lo), 0, 1)


@dataclass
class RiskWeights:
    kp: float = 0.35
    proton: float = 0.35
    dst: float = 0.15
    flare: float = 0.15
    #: Порог композитного индекса (0..1), выше которого ВКД считать рискованной.
    threshold: float = 0.45
    #: Коэффициент дозы за защитой, мЗв/ч на «единицу» потока протонов ≥10 МэВ.
    dose_coeff: float = 0.02
    #: Фоновая доза внутри станции / скафандра при спокойной обстановке, мЗв/ч.
    background_dose: float = 0.006
    weights_meta: dict = field(default_factory=dict)


def compute_risk(sw: pd.DataFrame, w: RiskWeights | None = None) -> pd.DataFrame:
    w = w or RiskWeights()
    out = sw.copy()
    # Нормировки подобраны так, чтобы каждое пороговое событие по отдельности
    # давало вклад около 0.5: G1-буря (Kp 5), SPE (10 pfu), умеренная буря
    # (Dst -50 нТл), вспышка класса M.
    kp_term = _norm(out["kp"], 1.0, 9.0)
    proton_term = _norm(np.log10(out["proton_flux_10mev"] + 1e-6), -1.0, 3.0)
    dst_term = _norm(-out["dst"], 0.0, 100.0)
    flare_term = _norm(np.log10(out["xray_flux"] + 1e-12), -7.0, -2.0)

    # Правило доминирующей опасности (worst-case): как в оперативных правилах
    # ВКД — выход отменяется, если ХОТЯ БЫ ОДИН фактор выше порога. Поэтому
    # индекс = максимум нормированных вкладов, а не среднее: спокойный Kp не
    # «маскирует» солнечное протонное событие. Веса w.* задают относительную
    # жёсткость критериев (используются для сценарного анализа риска).
    terms = np.vstack([kp_term, proton_term, dst_term, flare_term]) * np.array(
        [w.kp, w.proton, w.dst, w.flare]
    )[:, None] / max(w.kp, w.proton, w.dst, w.flare)
    out["risk_index"] = np.round(np.max(terms, axis=0), 3).clip(0, 1)
    out["dominant_factor"] = np.array(["kp", "proton", "dst", "flare"])[np.argmax(terms, axis=0)]
    out["term_kp"] = kp_term.round(3)
    out["term_proton"] = proton_term.round(3)
    out["term_dst"] = dst_term.round(3)
    out["term_flare"] = flare_term.round(3)

    # Доза за защитой скафандра: фон + вклад протонов/захваченных частиц.
    proton_flux = out["proton_flux_10mev"].to_numpy()
    kp_excess = np.clip(out["kp"].to_numpy() - 4.0, 0, None)
    dose = w.background_dose + w.dose_coeff * np.clip(np.log10(proton_flux + 1.0), 0, None) + 0.003 * kp_excess
    out["dose_rate_msv_h"] = np.round(dose, 4)
    out["dose_eva_msv"] = np.round(dose * TYPICAL_EVA_HOURS, 3)

    out["eva_allowed"] = (out["risk_index"] < w.threshold) & (out["dose_eva_msv"] < EVA_DOSE_LIMIT_MSV)
    return out


def risk_class(index: float) -> str:
    if index < 0.2:
        return "низкий"
    if index < 0.35:
        return "умеренный"
    if index < 0.5:
        return "повышенный"
    if index < 0.7:
        return "высокий"
    return "критический"


def find_windows(risk: pd.DataFrame, min_hours: int = 3) -> list[dict]:
    """Непрерывные окна, где ВКД допустима не меньше min_hours."""

    allowed = risk["eva_allowed"].to_numpy()
    times = pd.to_datetime(risk["time"]).to_numpy()
    windows: list[dict] = []
    start = None
    for i, ok in enumerate(allowed):
        if ok and start is None:
            start = i
        elif not ok and start is not None:
            if i - start >= min_hours:
                seg = risk.iloc[start:i]
                windows.append(
                    {
                        "from": str(pd.Timestamp(times[start])),
                        "to": str(pd.Timestamp(times[i - 1])),
                        "hours": int(i - start),
                        "max_risk_index": float(seg["risk_index"].max()),
                        "max_dose_eva_msv": float(seg["dose_eva_msv"].max()),
                        "class": risk_class(float(seg["risk_index"].mean())),
                    }
                )
            start = None
    if start is not None and len(allowed) - start >= min_hours:
        seg = risk.iloc[start:]
        windows.append(
            {
                "from": str(pd.Timestamp(times[start])),
                "to": str(pd.Timestamp(times[-1])),
                "hours": int(len(allowed) - start),
                "max_risk_index": float(seg["risk_index"].max()),
                "max_dose_eva_msv": float(seg["dose_eva_msv"].max()),
                "class": risk_class(float(seg["risk_index"].mean())),
            }
        )
    return windows


def recommend(risk: pd.DataFrame, now: pd.Timestamp | None = None) -> dict:
    """Оперативная рекомендация: можно ли выходить сейчас и когда лучше."""

    now = now or pd.Timestamp(risk["time"].iloc[0])
    cur = risk.iloc[(pd.to_datetime(risk["time"]) - now).abs().argmin()]
    windows = [w for w in find_windows(risk) if pd.Timestamp(w["from"]) >= now][:3]
    return {
        "now": str(now),
        "current_risk_index": float(cur["risk_index"]),
        "current_class": risk_class(float(cur["risk_index"])),
        "current_dose_eva_msv": float(cur["dose_eva_msv"]),
        "eva_allowed_now": bool(cur["eva_allowed"]),
        "next_windows": windows,
        "drivers": {
            "kp": float(cur["kp"]),
            "dst": float(cur["dst"]),
            "proton_flux_10mev": float(cur["proton_flux_10mev"]),
            "flare_class": str(cur["flare_class"]),
        },
    }
