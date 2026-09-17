"""Картирование гарей (burn scar) по разнице индексов NBR: dNBR = NBR_pre - NBR_post.

Классификация по порогам USGS (Key & Benson, 2006) в адаптации для Sentinel-2:
  < 0.10  — не горело / регенерация
  0.10-0.27 — низкая тяжесть
  0.27-0.66 — средняя/высокая
  > 0.66  — высокая

Плюс морфологическая чистка: убираем одиночные пиксели и мелкие пятна,
чтобы площадь не завышалась из-за облачности и теней.
"""

from __future__ import annotations

import numpy as np

SEVERITY_THRESHOLDS = (0.10, 0.27, 0.66)
SEVERITY_LABELS = ("unburned", "low", "moderate", "high")


def dnbr(nbr_pre: np.ndarray, nbr_post: np.ndarray) -> np.ndarray:
    return np.clip(nbr_pre.astype(np.float32) - nbr_post.astype(np.float32), -2, 2)


def classify_severity(d: np.ndarray) -> np.ndarray:
    return np.digitize(d, SEVERITY_THRESHOLDS).astype(np.uint8)


def remove_small_objects(mask: np.ndarray, min_pixels: int = 8) -> np.ndarray:
    """Убирает связные компоненты меньше min_pixels (4-связность, стек)."""

    if not mask.any():
        return mask
    h, w = mask.shape
    seen = np.zeros_like(mask, dtype=bool)
    out = np.zeros_like(mask, dtype=bool)
    for y in range(h):
        for x in range(w):
            if mask[y, x] and not seen[y, x]:
                stack = [(y, x)]
                comp = []
                seen[y, x] = True
                while stack:
                    cy, cx = stack.pop()
                    comp.append((cy, cx))
                    for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
                        if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not seen[ny, nx]:
                            seen[ny, nx] = True
                            stack.append((ny, nx))
                if len(comp) >= min_pixels:
                    for cy, cx in comp:
                        out[cy, cx] = True
    return out


def burn_area_ha(severity: np.ndarray, pixel_size_m: float = 20.0) -> dict[str, float]:
    """Площадь по классам тяжести в гектарах."""

    px_ha = (pixel_size_m**2) / 10_000.0
    result = {}
    for i, label in enumerate(SEVERITY_LABELS):
        result[label] = float(np.count_nonzero(severity == i) * px_ha)
    result["burned_total"] = float(np.count_nonzero(severity > 0) * px_ha)
    return {k: round(v, 2) for k, v in result.items()}


def map_burn_scar(
    nbr_pre: np.ndarray,
    nbr_post: np.ndarray,
    pixel_size_m: float = 20.0,
    min_pixels: int = 8,
) -> dict:
    """Полный проход: dNBR -> пороги -> чистка мелких пятен -> площади в га."""

    d = dnbr(nbr_pre, nbr_post)
    severity = classify_severity(d)
    burned = severity > 0
    cleaned = remove_small_objects(burned, min_pixels=min_pixels)
    severity_clean = np.where(cleaned, severity, 0).astype(np.uint8)
    return {
        "dnbr": d,
        "severity": severity_clean,
        "area_ha": burn_area_ha(severity_clean, pixel_size_m),
        "mean_dnbr": float(d[cleaned].mean()) if cleaned.any() else 0.0,
        "max_dnbr": float(d.max()),
    }


def iou(pred: np.ndarray, truth: np.ndarray) -> float:
    inter = np.logical_and(pred, truth).sum()
    union = np.logical_or(pred, truth).sum()
    return float(inter / union) if union else 1.0


def dice(pred: np.ndarray, truth: np.ndarray) -> float:
    inter = np.logical_and(pred, truth).sum()
    return float(2 * inter / (pred.sum() + truth.sum())) if (pred.sum() + truth.sum()) else 1.0
