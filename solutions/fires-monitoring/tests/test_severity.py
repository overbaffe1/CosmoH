"""Тесты обучаемой модели степени поражения (``fires.severity``)."""

from __future__ import annotations

import numpy as np
import pytest

from fires import bs as bs_module
from fires.chips import Chip
from fires.severity import FEATURE_NAMES, SeverityModel, chip_features, roi_mask
from fires.synthetic import generate_bs_chip


def bs_chip(rng, size: int = 96) -> Chip:
    """Собирает BS-чип так же, как его вернул бы ``Dataset.load`` (pre/post разделены)."""

    data = generate_bs_chip(rng, size)
    severity = data.pop("target_sev")
    return Chip(
        chip_id="bs_sev",
        kind="bs",
        layers={"SCL": data["scl"], "landcover": data["landcover"], "valid": data["valid"]},
        pre=dict(data["pre"]),
        post=dict(data["post"]),
        s1_pre=dict(data["s1_pre"]),
        s1_post=dict(data["s1_post"]),
        meta={},
        mask_sev=severity.astype(np.uint8),
    )


def tiny_model(chip: Chip) -> SeverityModel:
    """Обучает крошечный бустинг на признаках одного синтетического чипа."""

    from sklearn.ensemble import HistGradientBoostingClassifier

    matrix, ok = chip_features(chip)
    truth = np.asarray(chip.mask_sev, dtype=np.uint8).reshape(-1)
    indices = np.flatnonzero(ok)
    estimator = HistGradientBoostingClassifier(max_iter=5, max_leaf_nodes=4, random_state=0,
                                               early_stopping=False)
    estimator.fit(matrix[indices], truth[indices])
    return SeverityModel(estimator=estimator)


def test_chip_features_shape_and_finiteness():
    chip = bs_chip(np.random.default_rng(1))
    matrix, ok = chip_features(chip)
    height, width = np.asarray(chip.pre["B8A"]).shape
    assert matrix.shape == (height * width, len(FEATURE_NAMES))
    assert matrix.dtype == np.float32
    assert np.isfinite(matrix).all(), "в признаках не должно быть NaN/inf"
    assert ok.shape == (height * width,)
    assert ok.any()


def test_feature_names_match_matrix():
    chip = bs_chip(np.random.default_rng(2), size=64)
    matrix, _ = chip_features(chip)
    assert len(FEATURE_NAMES) == matrix.shape[1] == 23


def test_roi_mask_includes_burned_pixels():
    chip = bs_chip(np.random.default_rng(3), size=128)
    mask = roi_mask(chip)
    assert mask.shape == np.asarray(chip.pre["B8A"]).shape
    burned = np.asarray(chip.mask_sev) > 0
    # гейт может не покрыть единичные пиксели на краю пятна, но основную часть обязан
    assert (burned & mask).sum() / max(burned.sum(), 1) > 0.9


def test_model_predicts_valid_classes_and_roundtrips(tmp_path):
    chip = bs_chip(np.random.default_rng(4))
    model = tiny_model(chip)
    severity = model.predict_chip(chip)
    assert severity.shape == np.asarray(chip.pre["B8A"]).shape
    assert severity.dtype == np.uint8
    assert set(np.unique(severity)) <= {0, 1, 2, 3}

    path = model.save(tmp_path / "severity_model.pkl")
    restored = SeverityModel.load(path)
    assert np.array_equal(restored.predict_chip(chip), severity)


def test_regressor_model_maps_continuous_to_classes():
    class ConstantRegressor:
        def __init__(self, value):
            self.value = value

        def predict(self, matrix):
            return np.full(matrix.shape[0], self.value)

    chip = bs_chip(np.random.default_rng(5), size=64)
    shapes = (chip.pre["B8A"]).shape
    _, ok = chip_features(chip)
    # модель вызывается только внутри области интереса и только по валидным пикселям
    gate = roi_mask(chip).reshape(-1) & ok
    for value, expected in ((0.1, 0), (0.9, 1), (1.9, 2), (2.9, 3)):
        model = SeverityModel(estimator=ConstantRegressor(value), kind="regressor")
        severity = model.predict_chip(chip).reshape(-1)
        assert severity.shape == gate.shape
        # вне области интереса модель не вызывается, там ноль; внутри — класс по порогам регрессии
        assert set(np.unique(severity[gate])) == {expected}, value
        assert (severity[~gate] == 0).all(), value


def test_classify_chip_uses_model_and_keeps_postprocess():
    chip = bs_chip(np.random.default_rng(6))
    model = tiny_model(chip)
    with_model = bs_module.classify_chip(chip, bs_module.BSParams(), severity_model=model)
    truth = np.asarray(chip.mask_sev, dtype=np.uint8)
    assert with_model.shape == truth.shape
    # постобработка применяется и к модели: дыр внутри контура не остаётся
    from fires.morphology import fill_holes

    burned = with_model > 0
    assert (fill_holes(burned) & ~burned).sum() == 0
    noisy = bs_module.classify_chip(chip, bs_module.BSParams(), severity_model=model, return_details=True)
    assert noisy[1]["mode"] == "model"


def test_postprocess_is_shared_between_modes():
    severity = np.zeros((32, 32), dtype=np.uint8)
    severity[8:24, 8:24] = 2
    severity[14:18, 14:18] = 0  # дыра в контуре
    out = bs_module.postprocess(severity, bs_module.BSParams(min_patch_px=6, fill_holes_mask=True))
    assert out[15, 15] == 1, "дыра внутри контура заполняется слабой степенью"
    speck = np.zeros((32, 32), dtype=np.uint8)
    speck[3, 3] = 3
    speck[20:28, 20:28] = 1
    out = bs_module.postprocess(speck, bs_module.BSParams(min_patch_px=6, fill_holes_mask=True))
    assert out[3, 3] == 0, "мелкие контуры удаляются в обоих режимах"


def test_inference_skips_model_when_mode_is_thresholds(tmp_path):
    from inference import _load_solution

    weights = tmp_path / "weights.json"
    weights.write_text('{"bs_mode": "thresholds", "severity_model": "severity_model.pkl"}', encoding="utf-8")
    _, _, _, severity_model = _load_solution(weights)
    assert severity_model is None


def test_inference_loads_model_when_mode_is_model(tmp_path):
    from inference import _load_solution

    chip = bs_chip(np.random.default_rng(7), size=64)
    model = tiny_model(chip)
    model.save(tmp_path / "severity_model.pkl")
    weights = tmp_path / "weights.json"
    weights.write_text('{"bs_mode": "model", "severity_model": "severity_model.pkl"}', encoding="utf-8")
    _, _, _, severity_model = _load_solution(weights)
    assert isinstance(severity_model, SeverityModel)


def test_inference_falls_back_when_model_file_is_broken(tmp_path, capsys):
    """Битый (или собранный другой версией sklearn) файл модели не должен ронять инференс."""

    from inference import _load_solution

    (tmp_path / "severity_model.pkl").write_bytes(b"not a pickle")
    weights = tmp_path / "weights.json"
    weights.write_text('{"bs_mode": "model", "severity_model": "severity_model.pkl"}', encoding="utf-8")
    _, _, _, severity_model = _load_solution(weights)
    assert severity_model is None
    assert "не загрузилась" in capsys.readouterr().err


@pytest.mark.parametrize("cut", [0.05, 0.2])
def test_roi_cut_is_monotone(cut):
    """Строгий порог ROI не шире мягкого — иначе гейт терял бы пиксели."""
    chip = bs_chip(np.random.default_rng(8), size=96)
    assert (roi_mask(chip, cut=0.2) & ~roi_mask(chip, cut=cut)).sum() == 0
