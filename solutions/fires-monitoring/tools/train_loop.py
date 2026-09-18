#!/usr/bin/env python3
"""Цикл обучения модели степени поражения BS: 12 проходов с отчётом «стало лучше или нет».

Зачем отдельный скрипт. ``train.py`` подбирает всю конфигурацию решения (правила AF, пороги
dNBR, режим BS) и занимает ≈20 минут — гонять его после каждой идеи неудобно. Этот скрипт
работает только с моделью степени поражения: за один проход (цикл) обучает одну конфигурацию
на том же разбиении по событиям пожара, что и ``train.py`` (168 чипов обучение / 56 отложенных),
считает метрики соревнования на отложенной части и печатает разницу с лучшим результатом.

    py -3 tools\\train_loop.py --data-dir %USERPROFILE%\\Documents\\cosmo1\\train          # 12 циклов
    py -3 tools\\train_loop.py --data-dir ... --device cpu                                # без GPU
    py -3 tools\\train_loop.py --data-dir ... --cycles 4 --quick                          # быстрая проверка

Что печатается по каждому циклу: конфигурация, ``IoU_burn`` и ``mIoU_sev`` на отложенных чипах,
проекция Score соревнования (AF берётся из замера — цикл его не меняет) и вердикт
«лучше / не лучше». В конце — таблица «до и после» на всём обучающем наборе и решение, что
записать в веса: ``weights/weights.json`` + ``weights/severity_model.pkl`` (прежняя модель
сохраняется рядом как ``severity_model.prev.pkl``).

Проекция Score: ``0.35·F1_af + 0.35·IoU_burn + 0.30·mIoU_sev`` — ровно формула кейса. Так как
F1_af не зависит от модели степени поражения, берётся один замер на всём AF-наборе (из
``docs/numbers.json``, если он есть, иначе пересчитывается) и подставляется в обе оценки.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import replace
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from fires import bs as bs_module  # noqa: E402
from fires import severity as sev  # noqa: E402
from fires.chips import Dataset  # noqa: E402
from fires.metrics import score_from_pairs  # noqa: E402
from fires.weights import load_weights, save_weights  # noqa: E402
from train import SEED, SEVERITY_TRAIN_PIXELS, _split_ids, evaluate_af, evaluate_bs  # noqa: E402

#: Конфигурации циклов. Каждый цикл — либо обучение новой модели (``train``), либо шаг,
#: использующий лучшую модель на данный момент: ансамбль (``ensemble``), смещения классов
#: (``bias``), подбор морфологии (``postprocess``), переобучение на всём наборе (``all_data``).
#: Подбор идёт от простого к сложному, как в обычном цикле экспериментов: сначала ёмкость модели,
#: затем признаки, затем постобработка и ансамбли.
CYCLE_SCHEDULE: list[dict] = [
    {"name": "стартовая конфигурация из весов", "mode": "train", "features": "base",
     "params": {"iterations": 60, "learning_rate": 0.20, "leaves": 24, "min_samples_leaf": 80,
                "l2": 1.0}},
    {"name": "больше деревьев (300 при lr 0.08)", "mode": "train", "features": "base",
     "params": {"iterations": 300, "learning_rate": 0.08, "leaves": 24, "min_samples_leaf": 80,
                "l2": 1.0}},
    {"name": "крупные деревья (250 ит., 48 листьев)", "mode": "train", "features": "base", "bias": True,
     "params": {"iterations": 250, "learning_rate": 0.10, "leaves": 48, "min_samples_leaf": 40,
                "l2": 1.0}},
    {"name": "xgboost hist: 400 ит., 64 листа", "mode": "train", "features": "base", "bias": True,
     "backend": "xgboost",
     "params": {"iterations": 400, "learning_rate": 0.06, "leaves": 64, "min_samples_leaf": 80,
                "l2": 1.0, "subsample": 0.8, "colsample": 0.8}},
    {"name": "расширенные признаки (40 против 23)", "mode": "train", "features": "ext", "bias": True,
     "params": {"iterations": 250, "learning_rate": 0.10, "leaves": 48, "min_samples_leaf": 40,
                "l2": 1.0}},
    {"name": "больше пикселей на чип (x2)", "mode": "train", "features": "base", "pixels_scale": 2.0,
     "bias": True,
     "params": {"iterations": 250, "learning_rate": 0.10, "leaves": 48, "min_samples_leaf": 40,
                "l2": 1.0}},
    {"name": "жёсткая регуляризация (l2 3, colsample 0.7)", "mode": "train", "features": "ext",
     "bias": True,
     "params": {"iterations": 300, "learning_rate": 0.06, "leaves": 32, "min_samples_leaf": 120,
                "l2": 3.0, "colsample": 0.7}},
    {"name": "веса классов 1/n вместо 1/sqrt(n)", "mode": "train", "features": "base",
     "weight_mode": "inv", "bias": True,
     "params": {"iterations": 300, "learning_rate": 0.08, "leaves": 24, "min_samples_leaf": 80,
                "l2": 1.0}},
    {"name": "ансамбль трёх лучших моделей", "mode": "ensemble", "top": 3, "bias": True},
    {"name": "регрессия степени вместо классификации", "mode": "regressor", "features": "base",
     "params": {"iterations": 250, "learning_rate": 0.10, "leaves": 48, "min_samples_leaf": 40,
                "l2": 1.0}},
    {"name": "перепроверка морфологии на лучшей модели", "mode": "postprocess"},
    {"name": "переобучение лучшей конфигурации на всех чипах", "mode": "all_data"},
]

#: Сдвиги, которые перебираются при подборе смещений классов.
BIAS_GRID = (-0.08, -0.05, -0.03, -0.015, 0.0, 0.015, 0.03, 0.05, 0.08)

#: Порог «улучшения»: меньше этой разницы объектива считаем шумом.
IMPROVEMENT_EPS = 2e-4


class ValCache:
    """Признаки отложенных чипов и эталонные степени: считается один раз на набор признаков.

    Отложенная часть маленькая (56 чипов), но каждая новая модель требует её полного прохода.
    Признаки кэшируются в памяти: на 56 чипов это ≈0.8 ГБ, зато пересчёт 12 циклов не читает
    TIFF-файлы заново.
    """

    def __init__(self, dataset: Dataset, chip_ids: list[str], feature_names):
        self.feature_names = tuple(feature_names)
        self.chips: list[dict] = []
        for chip_id in chip_ids:
            chip = dataset.load(chip_id)
            if chip.mask_sev is None:
                continue
            matrix, ok = sev.chip_features(chip, self.feature_names)
            hot = sev.roi_mask(chip, sev.ROI_CUT, sev.ROI_SIZE).reshape(-1)
            indices = np.flatnonzero(ok & hot)
            self.chips.append({
                "chip_id": chip_id,
                "matrix": matrix[indices],
                "indices": indices,
                "truth": np.asarray(chip.mask_sev, dtype=np.uint8).reshape(-1),
                "shape": np.asarray(chip.mask_sev).shape,
            })

    def __len__(self) -> int:
        return len(self.chips)

    def matrix_for(self, item: dict, model: sev.SeverityModel) -> np.ndarray:
        """Столбцы кэша под набор признаков модели (базовый набор — префикс расширенного)."""

        names = tuple(model.feature_names)
        if names == self.feature_names:
            return item["matrix"]
        if tuple(self.feature_names[:len(names)]) == names:
            return item["matrix"][:, :len(names)]
        raise ValueError(f"кэш собран на наборе {self.feature_names}, а модель ждёт {names}")

    def probabilities(self, model: sev.SeverityModel) -> list[np.ndarray]:
        """Вероятности классов на области интереса каждого чипа — считаются один раз на модель.

        Дальше смещения классов и варианты морфологии перебираются уже по этим числам: полный
        проход по вероятностям занимает доли секунды, тогда как повторный обход чипов моделью —
        десятки секунд.
        """

        out = []
        for item in self.chips:
            if not item["indices"].size:
                out.append(np.zeros((0, 4), dtype=np.float32))
            elif model.kind == "regressor":
                value = np.asarray(estimator_predict(model, self.matrix_for(item, model)),
                                   dtype=np.float32)
                out.append(value)
            else:
                out.append(model.proba_matrix(self.matrix_for(item, model)))
        return out

    def score_from_probabilities(self, values: list[np.ndarray], params: bs_module.BSParams,
                                 bias=None, cuts=(0.5, 1.5, 2.5),
                                 subset: set[int] | None = None) -> dict:
        """Метрики по заранее посчитанным вероятностям (или непрерывной степени для регрессии).

        ``subset`` — позиции чипов, которые входят в замер (по умолчанию — все): на нём держится
        проверка смещений классов на второй половине отложенных чипов.
        """

        bias_array = None if bias is None else np.asarray(bias, dtype=np.float32)
        pairs = {}
        for position, (item, value) in enumerate(zip(self.chips, values)):
            if subset is not None and position not in subset:
                continue
            full = np.zeros(int(np.prod(item["shape"])), dtype=np.uint8)
            if item["indices"].size and len(value):
                if value.ndim == 1:  # регрессия: непрерывная степень
                    classes = np.zeros(value.shape, dtype=np.uint8)
                    for cls, cut in zip((1, 2, 3), cuts):
                        classes[value >= cut] = cls
                else:
                    scored = value if bias_array is None else value + bias_array
                    classes = np.argmax(scored, axis=1).astype(np.uint8)
                full[item["indices"]] = classes
            pred = bs_module.postprocess(full.reshape(item["shape"]), params)
            pairs[item["chip_id"]] = (item["truth"].reshape(item["shape"]), pred)
        result = score_from_pairs({}, pairs)
        result["n"] = len(pairs)
        return result

    def evaluate(self, model: sev.SeverityModel, params: bs_module.BSParams,
                 bias=None, chiplimit: int | None = None) -> dict:
        """Метрики BS на отложенной части для готовой модели (со смещениями и постобработкой)."""

        model.class_bias = None if bias is None else tuple(float(v) for v in bias)
        chirps = self.chips[:chiplimit] if chiplimit else self.chips
        if chiplimit:
            saved, self.chips = self.chips, chirps
        try:
            values = self.probabilities(model)
        finally:
            if chiplimit:
                self.chips = saved
        cuts = getattr(model, "cuts", (0.5, 1.5, 2.5))
        return self.score_from_probabilities(values, params, bias=bias, cuts=cuts)


def estimator_predict(model: sev.SeverityModel, matrix: np.ndarray) -> np.ndarray:
    """Предсказание непрерывной степени (регрессия) — с учётом ансамбля."""

    items = model.members or [model.estimator]
    total = None
    for estimator in items:
        part = np.asarray(estimator.predict(matrix), dtype=np.float32)
        total = part if total is None else total + part
    return total / len(items)


def objective(iou: float | None, miou: float | None) -> float:
    """Часть Score, которую меняет цикл: ``0.35·IoU_burn + 0.30·mIoU_sev``."""

    if iou is None or miou is None:
        return float("-inf")
    return 0.35 * float(iou) + 0.30 * float(miou)


def projected_score(f1_af: float | None, iou: float, miou: float) -> float:
    """Полная формула кейса с зафиксированным F1 активного горения."""

    f1 = 0.0 if f1_af is None else float(f1_af)
    return 0.35 * f1 + 0.35 * float(iou) + 0.30 * float(miou)


def measure_f1_af(dataset: Dataset, weights: dict, numbers_path: Path,
                  quick: bool = False) -> tuple[float | None, str]:
    """F1 активного горения: из уже посчитанного ``docs/numbers.json`` или замером заново.

    Правила AF цикл не меняет, поэтому значение берётся один раз и подставляется в проекцию Score
    до и после. В быстром режиме (``--quick``) замер идёт по части чипов — это только для отладки.
    """

    if numbers_path.exists() and not quick:
        try:
            data = json.loads(numbers_path.read_text(encoding="utf-8"))
            value = float(data["final"]["f1_af"])
            return value, f"из {numbers_path.name}"
        except Exception:
            pass
    from fires import af as af_module

    af_params = af_module.to_params(weights.get("af", {}))
    blob_filter = None
    if weights.get("af_mode") == "blobs" and weights.get("blob_filter"):
        path = numbers_path.parent.parent / "weights" / weights["blob_filter"]
        if path.exists():
            from fires.blobfilter import BlobFilter

            blob_filter = BlobFilter.load(path)
    ids = dataset.chip_ids("af")
    if quick:
        ids = ids[:40]
    result = evaluate_af(dataset, ids, af_params, blob_filter=blob_filter)
    return (None if result["f1_af"] is None else float(result["f1_af"])), f"замер на {len(ids)} AF-чипах"


def train_cycle(dataset: Dataset, train_ids: list[str], config: dict, pixels: int,
                device: str, seed: int, verbose: bool = True,
                pixel_cache: dict | None = None) -> sev.SeverityModel:
    """Обучает модель одного цикла (``mode`` = ``train`` или ``regressor``)."""

    features = config.get("features", "base")
    backend = config.get("backend", "auto")
    params = dict(config.get("params", {}))
    params.setdefault("kind", "regressor" if config.get("mode") == "regressor" else "classifier")
    if pixel_cache is not None and features in pixel_cache:
        X, y = pixel_cache[features]
    else:
        X, y = sev.collect_training_pixels(dataset, train_ids, pixels, features, seed=seed,
                                           verbose=verbose)
        if pixel_cache is not None:
            pixel_cache[features] = (X, y)
    return sev.train_model(X, y, params=params, backend=backend, device=device,
                           feature_names=features,
                           weight_mode=config.get("weight_mode", "sqrt"), seed=seed,
                           verbose=verbose)


def verification_split(cache: ValCache) -> tuple[list[int], list[int]]:
    """Индексы чипов для настройки и проверки смещений: чётные настраивают, нечётные проверяют.

    Смещения классов — четыре числа, подобранные на отложенной части; чтобы не подгоняться под
    шум, они выбираются на половине чипов и принимаются только если помогают и на второй половине.
    """

    fit = [i for i in range(len(cache.chips)) if i % 2 == 0]
    check = [i for i in range(len(cache.chips)) if i % 2 == 1]
    if not fit or not check:
        fit = check = list(range(len(cache.chips)))
    return fit, check


def tune_bias(cache: ValCache, model: sev.SeverityModel, params: bs_module.BSParams,
              base_bias=None) -> tuple[tuple, dict]:
    """Координатный подъём по смещениям классов: максимум объектива на отложенных чипах.

    Вероятности считаются один раз, поэтому каждый вариант смещений — это только пересчёт
    ``argmax`` и морфология (доли секунды вместо полного прохода моделью).
    """

    values = cache.probabilities(model)
    full = cache.score_from_probabilities(values, params, bias=base_bias)
    bias = list(base_bias or (0.0, 0.0, 0.0, 0.0))
    fit_ids, check_ids = verification_split(cache)

    fit_set, check_set = set(fit_ids), set(check_ids)

    def subset_score(candidate, positions) -> float:
        result = cache.score_from_probabilities(values, params, bias=candidate, subset=positions)
        return objective(result["iou_burn"], result["miou_sev"])

    best_obj = subset_score(bias, fit_set)
    for _ in range(2):
        for cls in range(4):
            current = bias[cls]
            for delta in BIAS_GRID:
                candidate = list(bias)
                candidate[cls] = current + delta
                value = subset_score(candidate, fit_set)
                if value > best_obj + 1e-5:
                    best_obj, bias = value, candidate
    # принимаем смещения, только если они улучшают и вторую половину отложенных чипов
    if check_ids != fit_ids:
        base_check = subset_score(list(base_bias or (0.0, 0.0, 0.0, 0.0)), check_set)
        tuned_check = subset_score(bias, check_set)
        if tuned_check <= base_check + 1e-5:
            bias = list(base_bias or (0.0, 0.0, 0.0, 0.0))
    result_full = cache.score_from_probabilities(values, params, bias=bias)
    result_full["bias_verified"] = bool(any(abs(v) > 1e-9 for v in bias))
    result_full["bias_full_objective"] = objective(full["iou_burn"], full["miou_sev"])
    return tuple(round(v, 4) for v in bias), result_full


def tunable_cuts(cache: ValCache, model: sev.SeverityModel, params: bs_module.BSParams) -> dict:
    """Для регрессии — подбор порогов перевода непрерывной степени в классы 1/2/3."""

    best = None
    values = cache.probabilities(model)
    variants = [tuple(model.cuts), (0.4, 1.4, 2.4), (0.6, 1.6, 2.6), (0.5, 1.6, 2.6),
                (0.55, 1.45, 2.45), (0.45, 1.5, 2.55)]
    for cuts in variants:
        result = cache.score_from_probabilities(values, params, cuts=cuts)
        value = objective(result["iou_burn"], result["miou_sev"])
        if best is None or value > best["objective"]:
            best = {"objective": value, "cuts": cuts, "iou_burn": result["iou_burn"],
                    "miou_sev": result["miou_sev"]}
    model.cuts = best["cuts"]
    return best


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Цикл обучения модели степени поражения BS")
    ap.add_argument("--data-dir", required=True, help="каталог обучающей части набора")
    ap.add_argument("--out", default=str(ROOT / "weights" / "weights.json"))
    ap.add_argument("--cycles", type=int, default=len(CYCLE_SCHEDULE), help="сколько циклов выполнить")
    ap.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto",
                    help="auto — GPU (xgboost), если он есть, иначе CPU")
    ap.add_argument("--pixels", type=int, default=SEVERITY_TRAIN_PIXELS,
                    help="сколько пикселей брать с чипа при обучении")
    ap.add_argument("--val-frac", type=float, default=0.25)
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--f1-af", type=float, default=None, help="зафиксировать F1 активного горения")
    ap.add_argument("--val-chips", type=int, default=0, help="ограничить отложенную часть (отладка)")
    ap.add_argument("--quick", action="store_true",
                    help="быстрый прогон для проверки работоспособности (мало пикселей и циклов)")
    ap.add_argument("--save", action="store_true",
                    help="записать лучшую модель в weights (по умолчанию только отчёт)")
    args = ap.parse_args(argv)

    if args.quick:
        # быстрый режим: меньше пикселей и чипов отложенной части, но все циклы на месте —
        # так проверяются и ансамбль, и смещения, и морфология, и переобучение на всём наборе
        args.pixels = min(args.pixels, 2000)
        args.val_chips = args.val_chips or 16

    device = sev.resolve_device(args.device)
    backend_note = "xgboost (GPU)" if device == "cuda" else "sklearn/xgboost (CPU)"
    print(f"=== Цикл обучения модели степени поражения: {args.cycles} циклов, устройство {device} "
          f"({backend_note}) ===")
    if args.device == "cuda" and device != "cuda":
        print(f"    GPU недоступен: {sev.gpu_report()['reason']}")

    dataset = Dataset(args.data_dir)
    bs_train, bs_val = _split_ids(dataset, "bs", args.val_frac, args.seed)
    if args.val_chips:
        bs_val = bs_val[:args.val_chips]
    weights = load_weights(args.out)
    bs_params = bs_module.to_params(weights.get("bs", {}))
    print(f"    чипов: обучение {len(bs_train)}, отложено {len(bs_val)}; "
          f"морфология {bs_params.min_patch_px} px, дыры "
          f"{'заполняются' if bs_params.fill_holes_mask else 'нет'}")

    numbers_path = ROOT / "docs" / "numbers.json"
    f1_af, f1_source = (args.f1_af, "аргумент --f1-af") if args.f1_af is not None else \
        measure_f1_af(dataset, weights, numbers_path, quick=args.quick or bool(args.val_chips))
    print(f"    F1 активного горения: {f1_af if f1_af is None else round(f1_af, 5)} ({f1_source}); "
          f"этот модуль цикл не меняет")

    t_start = time.perf_counter()
    print("\n=== Считаю признаки отложенной части (один раз) ===")
    t0 = time.perf_counter()
    val_cache = ValCache(dataset, bs_val, sev.FEATURE_NAMES_EXT)
    print(f"    готово: {len(val_cache)} чипов за {time.perf_counter() - t0:.1f} с")

    # --- точка отсчёта: модель из весов (то, что залито на платформу)
    base_model = None
    model_name = weights.get("severity_model")
    if model_name and weights.get("bs_mode") == "model":
        path = Path(args.out).parent / model_name
        if path.exists():
            try:
                base_model = sev.SeverityModel.load(path)
            except Exception as exc:
                print(f"    [warn] модель из весов не загрузилась ({exc})")
    print("\n=== Точка отсчёта (модель из весов) ===")
    baseline = None
    if base_model is not None:
        result = val_cache.evaluate(base_model, bs_params)
        baseline = {"iou_burn": result["iou_burn"], "miou_sev": result["miou_sev"],
                    "objective": objective(result["iou_burn"], result["miou_sev"])}
        print(f"    IoU_burn={baseline['iou_burn']:.4f}  mIoU_sev={baseline['miou_sev']:.4f}  "
              f"проекция Score={projected_score(f1_af, baseline['iou_burn'], baseline['miou_sev']):.5f}")
    else:
        print("    модель в весах не найдена — сравнение только между циклами")

    pixel_cache: dict = {}
    results: list[dict] = []
    best: dict | None = None
    trained_models: list[tuple[float, sev.SeverityModel, dict]] = []

    for index, config in enumerate(CYCLE_SCHEDULE[:args.cycles], start=1):
        name = config["name"]
        mode = config.get("mode", "train")
        t0 = time.perf_counter()
        note = ""
        model: sev.SeverityModel | None = None
        bias = None
        params = bs_params

        if mode in ("train", "regressor"):
            pixels = int(args.pixels * float(config.get("pixels_scale", 1.0)))
            model = train_cycle(dataset, bs_train, config, pixels, device, args.seed,
                                pixel_cache=pixel_cache)
            if mode == "regressor":
                cuts = tunable_cuts(val_cache, model, params)
                note = f"пороги классов {tuple(round(c, 2) for c in cuts['cuts'])}"
            if config.get("bias"):
                bias, result = tune_bias(val_cache, model, params)
                if any(abs(v) > 1e-9 for v in bias):
                    note = (note + "; " if note else "") + "смещения " + ", ".join(
                        f"{v:+.3f}" for v in bias)
            if not note or not config.get("bias"):
                result = val_cache.evaluate(model, params, bias=bias)
        elif mode == "ensemble":
            top = sorted(trained_models, key=lambda item: item[0], reverse=True)[:int(config.get("top", 3))]
            if not top:
                print(f"\nцикл {index:2d}/{args.cycles}: {name} — пропуск (нет обученных моделей)")
                continue
            model = sev.ensemble_model([item[1] for item in top],
                                       metrics={"members": [item[2]["name"] for item in top]})
            note = " + ".join(item[2]["name"] for item in top)
            if config.get("bias"):
                bias, result = tune_bias(val_cache, model, params)
                note += "; смещения " + ", ".join(f"{v:+.3f}" for v in bias)
            else:
                result = val_cache.evaluate(model, params)
        elif mode == "bias":
            if best is None:
                print(f"\nцикл {index:2d}/{args.cycles}: {name} — пропуск (нет базовой модели)")
                continue
            model = best["model"]
            bias, result = tune_bias(val_cache, model, params, base_bias=model.class_bias)
            note = "смещения " + ", ".join(f"{v:+.3f}" for v in bias)
        elif mode == "postprocess":
            if best is None:
                print(f"\nцикл {index:2d}/{args.cycles}: {name} — пропуск (нет базовой модели)")
                continue
            model = best["model"]
            variants = [replace(params, min_patch_px=24), replace(params, min_patch_px=96),
                        replace(params, min_patch_px=48, fill_holes_mask=True)]
            variants = [params] + variants
            values = val_cache.probabilities(model)
            chosen = None
            for candidate in variants:
                res = val_cache.score_from_probabilities(values, candidate, bias=model.class_bias)
                value = objective(res["iou_burn"], res["miou_sev"])
                if chosen is None or value > chosen[0]:
                    chosen = (value, candidate, res)
            _, params, result = chosen
            note = (f"чистка контуров < {params.min_patch_px} px, дыры "
                    f"{'заполняются' if params.fill_holes_mask else 'нет'}")
        else:  # all_data — переобучение лучшей конфигурации на всех чипах
            if best is None:
                print(f"\nцикл {index:2d}/{args.cycles}: {name} — пропуск (нет базовой модели)")
                continue
            config_best = best["config"]
            if config_best.get("mode") in ("ensemble", "bias", "all_data"):
                config_best = next((c for c in CYCLE_SCHEDULE if c.get("mode") == "train"), config_best)
            all_ids = bs_train + bs_val
            model = train_cycle(dataset, all_ids, config_best,
                                int(args.pixels * float(config_best.get("pixels_scale", 1.0))),
                                device, args.seed, pixel_cache=pixel_cache)
            result = val_cache.evaluate(model, params, bias=best.get("bias"))
            note = "обучение на всех чипах: часть оценки оптимистична"

        iou, miou = result["iou_burn"], result["miou_sev"]
        value = objective(iou, miou)
        score = projected_score(f1_af, iou, miou)
        elapsed = time.perf_counter() - t0

        previous = best["objective"] if best else (baseline["objective"] if baseline else None)
        verdict = "первый замер"
        improved = False
        if previous is not None:
            delta = value - previous
            improved = delta > IMPROVEMENT_EPS
            verdict = f"{'ЛУЧШЕ' if improved else 'не лучше'} ({delta:+.4f} объектива)"
        print(f"\nцикл {index:2d}/{args.cycles}: {name}")
        print(f"    IoU_burn={iou:.4f}  mIoU_sev={miou:.4f}  проекция Score={score:.5f}  "
              f"[{elapsed:.0f} с]  {verdict}")
        if note:
            print(f"    {note}")

        entry = {"cycle": index, "name": name, "mode": mode, "iou_burn": iou, "miou_sev": miou,
                 "objective": value, "projected_score": score, "seconds": round(elapsed, 1),
                 "improved": improved, "note": note, "device": device}
        results.append(entry)
        if mode in ("train", "regressor") and model is not None:
            trained_models.append((value, model, entry))

        if best is None or improved:
            if bias is None and mode == "postprocess":
                bias = best.get("bias") if best else None
            best = {"objective": value, "model": model, "iou_burn": iou, "miou_sev": miou,
                    "score": score, "cycle": index, "name": name, "config": config,
                    "bias": bias, "params": params, "entry": entry}

    # --- итог: сравнение «до и после» на отложенной части и на всём обучающем наборе
    print("\n=== Итог цикла ===")
    if best is None:
        print("ни один цикл не отработал")
        return 1
    best_model: sev.SeverityModel = best["model"]
    report = {"device": device, "f1_af": f1_af, "f1_source": f1_source,
              "baseline": baseline, "best": {"cycle": best["cycle"], "name": best["name"],
                                             "iou_burn": best["iou_burn"], "miou_sev": best["miou_sev"],
                                             "projected_score": best["score"]},
              "cycles": results}
    if baseline is not None:
        print(f"отложенные {len(val_cache)} чипов: было IoU={baseline['iou_burn']:.4f} "
              f"mIoU={baseline['miou_sev']:.4f} → стало IoU={best['iou_burn']:.4f} "
              f"mIoU={best['miou_sev']:.4f}")
        print(f"проекция Score на отложенной части: {projected_score(f1_af, baseline['iou_burn'], baseline['miou_sev']):.5f} "
              f"→ {best['score']:.5f} ({(best['score'] - projected_score(f1_af, baseline['iou_burn'], baseline['miou_sev'])):+.5f})")

    if not args.quick:
        print("\n=== Контроль на всём обучающем наборе (224 BS-чипа) ===")
        if baseline is not None and base_model is not None:
            full_base = evaluate_bs(dataset, dataset.chip_ids("bs"), bs_params, severity_model=base_model)
            base_score = projected_score(f1_af, full_base["iou_burn"], full_base["miou_sev"])
            print(f"    было (модель из весов): IoU_burn={full_base['iou_burn']:.4f} "
                  f"mIoU_sev={full_base['miou_sev']:.4f}  Score≈{base_score:.5f}")
            report["full_train_before"] = {"iou_burn": full_base["iou_burn"],
                                           "miou_sev": full_base["miou_sev"], "score": base_score}
        full_best = evaluate_bs(dataset, dataset.chip_ids("bs"), best.get("params", bs_params),
                                severity_model=best_model)
        best_score = projected_score(f1_af, full_best["iou_burn"], full_best["miou_sev"])
        print(f"    стало (лучшая модель):  IoU_burn={full_best['iou_burn']:.4f} "
              f"mIoU_sev={full_best['miou_sev']:.4f}  Score≈{best_score:.5f}")
        report["full_train_after"] = {"iou_burn": full_best["iou_burn"],
                                      "miou_sev": full_best["miou_sev"], "score": best_score}

    print("\n=== Циклы построчно ===")
    for entry in results:
        mark = "+" if entry["improved"] else " "
        print(f" {mark} {entry['cycle']:2d}. {entry['name'][:52]:52s} Score≈{entry['projected_score']:.5f} "
              f"({entry['seconds']:.0f} с)")

    # смещения классов должны попасть в файл модели: иначе инференс их не применит
    best_model.class_bias = None if best.get("bias") is None else tuple(best["bias"])
    if args.save:
        out_path = Path(args.out)
        prev = out_path.with_name("severity_model.prev.pkl")
        current = out_path.with_name(weights.get("severity_model") or "severity_model.pkl")
        if current.exists():
            current.replace(prev)
            print(f"\nпрежняя модель сохранена: {prev}")
        saved = best_model.save(current)
        weights["bs_mode"] = "model"
        weights["severity_model"] = saved.name
        chosen_params = best.get("params", bs_params)
        weights.setdefault("bs", {})["min_patch_px"] = chosen_params.min_patch_px
        weights.setdefault("bs", {})["fill_holes_mask"] = chosen_params.fill_holes_mask
        weights.setdefault("train_metrics", {})["bs_severity_model"] = best_model.metrics
        weights["train_metrics"]["severity_loop"] = {
            "cycle": best["cycle"], "name": best["name"], "device": device,
            "iou_burn": best["iou_burn"], "miou_sev": best["miou_sev"],
            "projected_score": best["score"],
        }
        save_weights(weights, out_path)
        print(f"модель записана: {saved}")
        print(f"веса обновлены: {out_path}")
        report["saved"] = str(saved)

    report_path = ROOT / "docs" / "severity_loop.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"отчёт о цикле: {report_path}")
    print(f"всего времени: {time.perf_counter() - t_start:.0f} с")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
