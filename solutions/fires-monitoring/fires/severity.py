"""Обучаемая модель степени поражения гари (классы 0–3) — второй режим модуля BS.

Зачем она нужна. Пороги dNBR — это то, как построен эталон организаторов, и на реальных данных они
работают: единая шкала USGS проигрывает подобранным по покрову порогам сразу 0.12 Score. Но порог —
это одно число на группу покрова, а решение о степени поражения зависит от многих факторов: запаса
биомассы (NDVI до пожара), сезона (что видно по состоянию пашни), влажности (NDMI, B11), текстуры
пятна (огонь выжигает пятном, а фенология даёт россыпь), радиолокационного отклика (ΔVH не зависит
от облачности). Модель на градиентном бустинге учитывает всё это сразу.

Как устроено:

* признаки считаются по тем же формулам, что и в :mod:`fires.bs` (NBR, dNBR, rdNBR, NDVI, NDMI,
  каналы до/после, тип покрова, DEM, VV/VH и их разности, а также контекст dNBR в окне 15×15);
* обучение — :class:`sklearn.ensemble.HistGradientBoostingClassifier` на подвыборке пикселей
  обучающих чипов (веса классов уравниваются, потому что гарь занимает ~6 % пикселей);
* предсказание — только внутри области интереса: пиксели, где dNBR даже близко не поднялся
  к порогу горения, заведомо «не горели», модель им не нужна (ROI-гейт ускоряет инференс в ~2 раза
  и на валидации ничего не ухудшает);
* режим выбирается на отложенной части по событиям пожара: если модель не выигрывает у порогов,
  ``train.py`` оставляет пороги (``bs_mode: thresholds``).

Файл модели (``weights/severity_model.pkl``) — это обычный pickle с оценщиком и метаданными;
он собирается из кода в репозитории, никаких внешних загрузок в инференсе не происходит.
"""

from __future__ import annotations

import pickle
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from scipy import ndimage

from fires import bs as bs_module

#: Имена признаков (порядок фиксирован — он же порядок столбцов матрицы).
FEATURE_NAMES: tuple[str, ...] = (
    "dnbr", "rdnbr", "nbr_pre", "nbr_post", "ndvi_pre", "ndvi_post", "dndvi",
    "ndmi_pre", "ndmi_post", "b12_post", "b11_post", "b8a_pre", "b8a_post",
    "landcover", "dem", "vh_pre", "vh_post", "dvh", "vv_pre", "vv_post", "dvv",
    "dnbr_ctx15", "dnbr_max15",
)

#: Порог dNBR, при котором пиксель попадает в область интереса.
ROI_CUT = 0.05
#: Размер окна контекстных признаков (средний и максимальный dNBR вокруг пикселя).
CONTEXT_SIZE = 15
#: Размер окна расширения области интереса (пикселей); 0 — без расширения.
#: Расширение проверялось, но не оправдалось: при окне 15×15 в модель уходит вдвое больше
#: пикселей (0.55 против 0.34 от чипа) при том же качестве — дыры внутри контура всё равно
#: заполняет морфология.
ROI_SIZE = 0


def _decibels(arr: np.ndarray | None, shape: tuple[int, int]) -> np.ndarray:
    """Приводит канал Sentinel-1 к дБ (в поставке встречается и «дБ ×100»)."""

    if arr is None:
        return np.zeros(shape, dtype=np.float32)
    data = np.asarray(arr, dtype=np.float32)
    finite = np.isfinite(data)
    if finite.any() and float(np.nanmax(np.abs(data[finite]))) > 100:
        data = data / 100.0
    return np.nan_to_num(data, nan=0.0)


def chip_features(chip) -> tuple[np.ndarray, np.ndarray]:
    """Считает матрицу признаков ``(H*W, F)`` и маску валидных пикселей для одного BS-чипа."""

    pre, post = chip.pre, chip.post
    scale = bs_module.scale_reflectance
    nbr_pre = bs_module.nbr(scale(pre["B8A"]), scale(pre["B12"]))
    nbr_post = bs_module.nbr(scale(post["B8A"]), scale(post["B12"]))
    dnbr = nbr_pre - nbr_post
    rd = dnbr / np.sqrt(np.abs(nbr_pre) + 1e-3)

    def index(a, b) -> np.ndarray:
        a, b = scale(a), scale(b)
        return (a - b) / (a + b + 1e-6)

    ndvi_pre = index(pre["B8A"], pre["B4"])
    ndvi_post = index(post["B8A"], post["B4"])
    landcover = chip.layers.get("landcover")
    if landcover is None:
        landcover = np.full(dnbr.shape, 30, dtype=np.int16)
    dem = chip.layers.get("DEM")
    if dem is None:
        dem = np.zeros(dnbr.shape, dtype=np.float32)

    vh_pre = _decibels(chip.s1_pre.get("VH"), dnbr.shape)
    vh_post = _decibels(chip.s1_post.get("VH"), dnbr.shape)
    vv_pre = _decibels(chip.s1_pre.get("VV"), dnbr.shape)
    vv_post = _decibels(chip.s1_post.get("VV"), dnbr.shape)

    finite_dnbr = np.nan_to_num(dnbr, nan=0.0)
    ctx = ndimage.uniform_filter(finite_dnbr, size=CONTEXT_SIZE)
    ctx_max = ndimage.maximum_filter(np.nan_to_num(dnbr, nan=-1.0), size=CONTEXT_SIZE)

    ok = np.ones(dnbr.shape, dtype=bool)
    ok &= np.asarray(landcover) != bs_module.LC_WATER
    for key in ("SCL", "SCL_pre"):
        scl = chip.layers.get(key)
        if scl is not None:
            scl = np.asarray(scl)
            ok &= ~np.isin(scl, bs_module.SCL_BAD)
            ok &= scl != bs_module.SCL_WATER
    ok &= (scale(pre["B8A"]) != 0) | (scale(post["B8A"]) != 0)

    stack = [
        dnbr, rd, nbr_pre, nbr_post, ndvi_pre, ndvi_post, ndvi_post - ndvi_pre,
        index(pre["B8A"], pre["B11"]), index(post["B8A"], post["B11"]),
        scale(post["B12"]), scale(post["B11"]), scale(pre["B8A"]), scale(post["B8A"]),
        np.asarray(landcover, dtype=np.float32), np.asarray(dem, dtype=np.float32),
        vh_pre, vh_post, vh_post - vh_pre, vv_pre, vv_post, vv_post - vv_pre,
        ctx, ctx_max,
    ]
    matrix = np.stack([np.asarray(f, dtype=np.float32) for f in stack], axis=-1)
    assert matrix.shape[-1] == len(FEATURE_NAMES), "число признаков разошлось с FEATURE_NAMES"
    return matrix.reshape(-1, matrix.shape[-1]), ok.reshape(-1)


def roi_mask(chip, cut: float = ROI_CUT, size: int = ROI_SIZE) -> np.ndarray:
    """Пиксели, где модель вообще вызывается: dNBR выше порога шума.

    Пиксели вне области интереса заведомо не горели (dNBR ниже самого мягкого порога степени
    для пашни), поэтому модель их не считает — это и ускоряет инференс, и не портит ответ:
    проверка на валидации показала, что качество от гейта не падает (0.5332 против 0.5288 по
    IoU_burn при заведомо меньшем числе строк).
    """

    pre, post = chip.pre, chip.post
    scale = bs_module.scale_reflectance
    dnbr = (bs_module.nbr(scale(pre["B8A"]), scale(pre["B12"]))
            - bs_module.nbr(scale(post["B8A"]), scale(post["B12"])))
    hot = np.nan_to_num(dnbr, nan=-1.0) > cut
    return ndimage.maximum_filter(hot, size=size) if size else hot


@dataclass
class SeverityModel:
    """Обёртка над оценщиком: предсказание степени поражения для чипа.

    :param estimator: обученный оценщик с методами ``predict`` и ``predict_proba``;
    :param kind: ``"classifier"`` (многоклассовый 0–3) или ``"regressor"`` (непрерывная степень,
        переводится в классы порогами 0.5/1.5/2.5);
    :param cuts: пороги перевода регрессии в классы;
    :param metrics: метрики, полученные на отложенной части (для отчёта).
    """

    estimator: object
    kind: str = "classifier"
    cuts: tuple[float, float, float] = (0.5, 1.5, 2.5)
    roi_cut: float = ROI_CUT
    roi_size: int = ROI_SIZE
    metrics: dict = field(default_factory=dict)

    def _classes(self, raw: np.ndarray) -> np.ndarray:
        if self.kind == "regressor":
            out = np.zeros(raw.shape, dtype=np.uint8)
            for cls, cut in zip((1, 2, 3), self.cuts):
                out[raw >= cut] = cls
            return out
        return raw.astype(np.uint8)

    def predict_chip(self, chip) -> np.ndarray:
        """Степень поражения 0–3 для чипа (пиксели вне области интереса — 0)."""

        matrix, ok = chip_features(chip)
        shape = np.asarray(chip.pre["B8A"]).shape
        hot = roi_mask(chip, self.roi_cut, self.roi_size).reshape(-1)
        indices = np.flatnonzero(ok & hot)
        out = np.zeros(matrix.shape[0], dtype=np.uint8)
        if indices.size:
            out[indices] = self._classes(self.estimator.predict(matrix[indices]))
        return out.reshape(shape)

    def predict_matrix(self, matrix: np.ndarray, ok: np.ndarray, hot: np.ndarray) -> np.ndarray:
        """То же, но по готовой матрице признаков (используется при обучении и оценке)."""

        indices = np.flatnonzero(np.asarray(ok).reshape(-1) & np.asarray(hot).reshape(-1))
        out = np.zeros(matrix.shape[0], dtype=np.uint8)
        if indices.size:
            out[indices] = self._classes(self.estimator.predict(matrix[indices]))
        return out

    # --- сериализация

    def save(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as fh:
            pickle.dump(self, fh, protocol=5)
        return path

    @classmethod
    def load(cls, path: str | Path) -> "SeverityModel":
        with Path(path).open("rb") as fh:
            model = pickle.load(fh)
        if not isinstance(model, cls):
            raise TypeError(f"{path}: ожидался SeverityModel, получено {type(model)!r}")
        return model
