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


# ---------------------------------------------------------------- устройства и наборы признаков

def test_extended_feature_set_contains_base_as_prefix():
    """Расширенный набор — надстройка: базовые столбцы идут первыми и совпадают по значениям.

    На этом свойстве держится кэш отложенных чипов в цикле обучения: он собран на расширенном
    наборе, а модели на базовом берут из него первые 23 столбца.
    """

    from fires.severity import FEATURE_NAMES_BASE, FEATURE_NAMES_EXT

    chip = bs_chip(np.random.default_rng(11))
    base, ok_base = chip_features(chip, "base")
    ext, ok_ext = chip_features(chip, "ext")
    assert tuple(FEATURE_NAMES_EXT[:len(FEATURE_NAMES_BASE)]) == tuple(FEATURE_NAMES_BASE)
    assert base.shape[1] == 23 and ext.shape[1] == 40
    assert np.array_equal(base, ext[:, :23])
    assert np.array_equal(ok_base, ok_ext)
    assert np.isfinite(ext).all()


def test_feature_set_names_are_unique_and_documented():
    from fires.severity import FEATURE_SETS

    assert set(FEATURE_SETS) == {"base", "ext"}
    for name, names in FEATURE_SETS.items():
        assert len(names) == len(set(names)), f"в наборе {name} продублированы признаки"


def test_resolve_device_handles_all_choices():
    from fires.severity import gpu_report, resolve_device

    assert resolve_device("cpu") == "cpu"
    assert resolve_device("auto") in {"cpu", "cuda"}
    # если GPU нет, «cuda» обязана откатиться на CPU, а не упасть
    assert resolve_device("cuda") == ("cuda" if gpu_report()["runtime_ok"] else "cpu")
    with pytest.raises(ValueError):
        resolve_device("tpu")


def test_gpu_report_has_reason_when_gpu_unavailable():
    from fires.severity import gpu_report

    report = gpu_report()
    assert set(report) >= {"xgboost", "build_use_cuda", "runtime_ok", "reason"}
    if not report["runtime_ok"]:
        assert report["reason"], "при недоступном GPU должна быть причина"


def test_pick_backend_matches_device():
    from fires.severity import pick_backend

    assert pick_backend("cpu") == "sklearn"
    assert pick_backend("cpu", "xgboost") == "xgboost"
    assert pick_backend("cuda") == "xgboost"  # GPU умеет только xgboost
    with pytest.raises(ValueError):
        pick_backend("cpu", "catboost")


# ---------------------------------------------------------------- бэкенды обучения

def test_train_model_on_synthetic_chip_and_describe():
    from fires.severity import collect_training_pixels, train_model

    chip = bs_chip(np.random.default_rng(12), size=64)
    dataset = _SingleChipDataset(chip)
    X, y = collect_training_pixels(dataset, [chip.chip_id], 0, "ext")
    model = train_model(X, y, params={"iterations": 5, "leaves": 8, "min_samples_leaf": 5},
                        backend="sklearn", device="cpu", feature_names="ext", verbose=False)
    assert model.backend == "sklearn" and model.device == "cpu"
    assert len(model.feature_names) == 40
    assert "sklearn/cpu" in model.describe()
    prediction = model.predict_chip(chip)
    assert set(np.unique(prediction)) <= {0, 1, 2, 3}


def test_class_weights_modes_differ_and_normalize():
    from fires.severity import class_weights

    y = np.array([0] * 100 + [1] * 10 + [2] * 3 + [3])
    for mode in ("sqrt", "inv", "none"):
        weight = class_weights(y, mode)
        assert weight.shape == y.shape
        assert abs(weight.sum() - len(y)) < 1e-6
    assert class_weights(y, "inv").max() > class_weights(y, "sqrt").max()


def test_class_bias_changes_classes_without_retraining():
    chip = bs_chip(np.random.default_rng(13), size=96)
    model = tiny_model(chip)
    plain = model.predict_chip(chip)
    model.class_bias = (-5.0, 1.0, 1.0, 1.0)
    shifted = model.predict_chip(chip)
    assert plain.shape == shifted.shape
    assert (shifted > 0).sum() >= (plain > 0).sum(), "смещение должно подтягивать ненулевые классы"


def test_ensemble_averages_probabilities():
    from fires.severity import ensemble_model

    chip = bs_chip(np.random.default_rng(14), size=96)
    model = tiny_model(chip)
    ensemble = ensemble_model([model, model])
    assert ensemble.describe().endswith("моделей 2")
    plain = model.predict_chip(chip)
    both = ensemble.predict_chip(chip)
    assert np.array_equal(plain, both), "усреднение одинаковых моделей ничего не меняет"


def test_load_fills_new_fields_for_old_pickles(tmp_path):
    """Модель, сохранённая до появления устройств и наборов признаков, читается без изменений."""

    chip = bs_chip(np.random.default_rng(15), size=64)
    model = tiny_model(chip)
    for name in ("feature_names", "backend", "device", "class_bias", "members"):
        delattr(model, name) if name in ("feature_names", "backend", "device") else setattr(model, name, None)
    path = tmp_path / "old.pkl"
    model.save(path)
    loaded = SeverityModel.load(path)
    assert loaded.feature_names == FEATURE_NAMES
    assert loaded.backend == "sklearn" and loaded.device == "cpu"
    assert loaded.predict_chip(chip).shape == np.asarray(chip.pre["B8A"]).shape


class _SingleChipDataset:
    """Минимальный «датасет» из одного чипа — для тестов сбора пикселей."""

    def __init__(self, chip: Chip):
        self.chip = chip

    def load(self, chip_id: str) -> Chip:
        assert chip_id == self.chip.chip_id
        return self.chip
