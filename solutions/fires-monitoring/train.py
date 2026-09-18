#!/usr/bin/env python3
"""Подбор порогов («обучение») на обучающей части набора.

    python train.py --data-dir /path/to/train --out weights/weights.json

Модель решения — физически интерпретируемая: контекстный алгоритм детекции и пороги
индекса dNBR по типам покрова. Обучаемых параметров немного, поэтому вместо градиентного
спуска используется детерминированный поиск по сетке на отложенной части обучающих чипов
(по ``fire_event_id``, чтобы чипы одного пожара не попадали одновременно в обучение
и валидацию — так же, как организаторы разделяют выборки).

Скрипт фиксирует:
* ``seed`` и состав валидации;
* метрики до и после подбора (в отчёте требуются абляции — см. docs/report.md);
* значения параметров в ``weights.json``.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path

import numpy as np

from fires import af as af_module
from fires import bs as bs_module
from fires.chips import Dataset
from fires.metrics import score_from_pairs
from fires.weights import save_weights

SEED = 20260918


def _split_ids(dataset: Dataset, kind: str, val_frac: float = 0.25, seed: int = SEED) -> tuple[list[str], list[str]]:
    """Делит чипы по событиям пожара: чипы одного события целиком в одной части."""

    ids = dataset.chip_ids(kind)
    events: dict[str, list[str]] = {}
    for chip_id in ids:
        row = dataset.meta.get(chip_id, {})
        event = str(row.get("fire_event_id") or chip_id)
        events.setdefault(event, []).append(chip_id)
    keys = sorted(events)
    rng = np.random.default_rng(seed)
    rng.shuffle(keys)
    n_val = max(1, int(round(len(keys) * val_frac)))
    val_keys = set(keys[:n_val])
    train_ids = [c for k in keys if k not in val_keys for c in events[k]]
    val_ids = [c for k in keys if k in val_keys for c in events[k]]
    return train_ids, val_ids


def evaluate_af(dataset: Dataset, chip_ids: list[str], params: af_module.AFParams, blob_filter=None) -> dict:
    pairs = {}
    for chip_id in chip_ids:
        chip = dataset.load(chip_id)
        if chip.mask is None:
            continue
        pred = af_module.detect_chip(chip, params, blob_filter=blob_filter)
        pairs[chip_id] = (chip.mask.astype(bool), pred)
    if not pairs:
        return {"f1_af": None, "n": 0}
    result = score_from_pairs(pairs, {})
    return {"f1_af": result["f1_af"], "counts": result["af_counts"], "n": len(pairs)}


def evaluate_bs(dataset: Dataset, chip_ids: list[str], params: bs_module.BSParams) -> dict:
    pairs = {}
    for chip_id in chip_ids:
        chip = dataset.load(chip_id)
        if chip.mask_sev is None:
            continue
        pred = bs_module.classify_chip(chip, params)
        pairs[chip_id] = (chip.mask_sev.astype(np.uint8), pred)
    if not pairs:
        return {"iou_burn": None, "miou_sev": None, "n": 0}
    result = score_from_pairs({}, pairs)
    return {
        "iou_burn": result["iou_burn"],
        "miou_sev": result["miou_sev"],
        "iou_per_class": result["iou_per_class"],
        "n": len(pairs),
    }


#: Сетка поиска для AF. Диапазоны взяты вокруг значений, найденных на реальной
#: обучающей части: днём фон τ4 прогревается, поэтому порог кандидатов выше «школьных» 320 K,
#: а ночью, наоборот, ниже. Отдельная ось — ночной порог кандидатов: по этим чипам
#: ошибка предыдущего приближения была максимальной.
AF_GRID = {
    "k_sigma": [2.0, 3.0],
    "delta_day": [20.0, 25.0, 30.0],
    "candidate_t4": [325.0, 330.0, 335.0],
    "candidate_t4_night": [293.0, 295.0, 300.0],
    "min_cluster_px": [1, 3],
}

#: Пороги dNBR по группам покрова: тройка (t1, t2, t3) на каждую группу, вокруг значений,
#: измеренных на реальных чипах (границы классов — середины между распределениями соседних
#: классов).
BS_GRID = {
    "forest": [(0.15, 0.27, 0.55), (0.20, 0.30, 0.60), (0.25, 0.35, 0.65), (0.20, 0.25, 0.50)],
    "semi": [(0.08, 0.19, 0.37), (0.12, 0.21, 0.38), (0.14, 0.22, 0.40), (0.16, 0.25, 0.44)],
    "cropland": [(0.08, 0.17, 0.34), (0.10, 0.19, 0.37), (0.12, 0.19, 0.37), (0.14, 0.22, 0.42)],
}


def tune_af(dataset: Dataset, train_ids: list[str], val_ids: list[str], verbose: bool = True) -> dict:
    """Две стадии: (1) подбор порогов правил, (2) обучение классификатора очагов.

    Выбирается вариант с лучшим F1 на отложенной части; результат попадает в weights.json
    вместе с режимом (``rules`` или ``blobs``), чтобы инференс был воспроизводим.
    """

    import itertools

    # --- стадия 1: пороги правил
    best = {"f1_af": -1.0, "params": {}}
    keys = list(AF_GRID)
    combos = list(itertools.product(*[AF_GRID[k] for k in keys]))
    if verbose:
        print(f"AF/rules: перебор {len(combos)} конфигураций на {len(val_ids)} чипах")
    for combo in combos:
        values = dict(zip(keys, combo))
        result = evaluate_af(dataset, val_ids, af_module.to_params(values))
        if result["f1_af"] is None:
            continue
        if result["f1_af"] > best["f1_af"]:
            best = {"f1_af": result["f1_af"], "params": values, "counts": result["counts"]}
            if verbose:
                print(f"  новое лучшее F1={result['f1_af']:.4f} {values}")

    # --- стадия 2: классификатор очагов
    from fires.blobfilter import BlobFilter, BlobFilterConfig, extract_features, label_blobs

    # Признаки считаются с теми же параметрами правил, что попадут в weights.json:
    # иначе состав кандидатов при обучении и при инференсе различается.
    rule_params = af_module.to_params(best.get("params", {}))
    Xs, ys = [], []
    for chip_id in train_ids:
        chip = dataset.load(chip_id)
        if chip.mask is None:
            continue
        feats, masks = extract_features(chip, rule_params)
        if len(masks):
            Xs.append(feats)
            ys.append(label_blobs(chip, masks))
    blob_result = {"f1_af": -1.0}
    if Xs:
        X = np.vstack(Xs)
        y = np.concatenate(ys)
        if verbose:
            print(f"AF/blobs: обучение на {X.shape[0]} блобах (положительных {int(y.sum())}, отрицательных {int((1 - y).sum())})")
        model = BlobFilter().fit(X, y, class_weight="balanced")
        importances = None
        for threshold in (0.3, 0.5, 0.7):
            for pixel_t4, pixel_delta in ((305.0, 4.0), (315.0, 6.0), (320.0, 8.0)):
                model.threshold = threshold
                model.config.pixel_t4 = pixel_t4
                model.config.pixel_delta = pixel_delta
                result = evaluate_af(dataset, val_ids, rule_params, blob_filter=model)
                if result["f1_af"] is None:
                    continue
                if result["f1_af"] > blob_result["f1_af"]:
                    blob_result = {
                        "f1_af": result["f1_af"],
                        "threshold": threshold,
                        "pixel_t4": pixel_t4,
                        "pixel_delta": pixel_delta,
                    }
                    if verbose:
                        print(f"  лучшее F1={result['f1_af']:.4f} (порог {threshold}, пиксельные {pixel_t4}/{pixel_delta})")
        if blob_result["f1_af"] > 0:
            model.threshold = blob_result["threshold"]
            model.config.pixel_t4 = blob_result["pixel_t4"]
            model.config.pixel_delta = blob_result["pixel_delta"]
            model.metrics = {"val_f1": blob_result["f1_af"], "n_blobs_train": int(X.shape[0]), "pos": int(y.sum())}
            blob_result["model"] = model
            try:  # важности признаков для отчёта
                from sklearn.inspection import permutation_importance

                idx = np.random.default_rng(args_seed()).choice(len(y), size=min(400, len(y)), replace=False)
                perm = permutation_importance(model.model, X[idx], y[idx], n_repeats=5, random_state=args_seed())
                importances = dict(sorted(zip(model.feature_names, perm.importances_mean.tolist()), key=lambda kv: -kv[1])[:8])
            except Exception:
                importances = None
            blob_result["importances"] = importances

    winner = "blobs" if blob_result.get("f1_af", -1) > best["f1_af"] else "rules"
    return {"rules": best, "blobs": blob_result, "mode": winner, "params": best.get("params", {})}


def args_seed() -> int:
    return SEED


def tune_bs(dataset: Dataset, train_ids: list[str], val_ids: list[str], verbose: bool = True) -> dict:
    """Поиск порогов dNBR по группам покрова (максимизируем 0.35*IoU_burn + 0.30*mIoU_sev)."""

    import itertools

    best = {"objective": -1.0, "params": {}}
    combos = list(itertools.product(BS_GRID["forest"], BS_GRID["semi"], BS_GRID["cropland"]))
    if verbose:
        print(f"BS: перебор {len(combos)} конфигураций на {len(val_ids)} чипах")

    def build(forest, semi, cropland):
        return bs_module.to_params({"forest": list(forest), "semi": list(semi), "cropland": list(cropland)})

    for forest, semi, cropland in combos:
        params = build(forest, semi, cropland)
        result = evaluate_bs(dataset, val_ids, params)
        if result["iou_burn"] is None:
            continue
        objective = 0.35 * result["iou_burn"] + 0.30 * result["miou_sev"]
        if objective > best["objective"]:
            best = {
                "objective": round(float(objective), 5),
                "params": {"forest": list(forest), "semi": list(semi), "cropland": list(cropland)},
                "iou_burn": result["iou_burn"],
                "miou_sev": result["miou_sev"],
            }
            if verbose:
                print(f"  новое лучшее objective={objective:.4f} IoU_burn={result['iou_burn']:.4f} mIoU={result['miou_sev']:.4f}")

    # --- стадия 2: восстановление гари под облаком по Sentinel-1
    # Оптические наблюдения под облаком/тенью недостоверны, но радиолокация видит потерю
    # биомассы. Коэффициент «дБ на единицу dNBR» физически зависит от типа покрова и
    # подбирается по валидации; вариант без SAR используется, если он не хуже.
    sar_variants: list[tuple[bool, tuple[float, float]]] = [(False, (3.0, 1.5))]
    sar_variants += [(True, scale) for scale in ((2.0, 1.0), (3.0, 1.5), (4.0, 2.0), (5.0, 2.5))]
    sar_min_drops = (0.8, 1.2, 1.6)
    if best["params"]:
        th = best["params"]
        base_params = build(th["forest"], th["semi"], th["cropland"])
        # Валидационная часть мала, поэтому вариант по SAR выбирается по двум фолдам
        # (перекрёстная проверка по событиям пожара): итог — среднее objective.
        folds = [(train_ids, val_ids), (val_ids, train_ids)]
        best_sar = {"objective": -1.0, "sar_recovery": False, "sar_scale": [3.0, 1.5], "sar_min_drop_db": 1.0}
        for enabled, scale in sar_variants:
            for min_drop in sar_min_drops if enabled else (1.0,):
                params = replace(
                    base_params,
                    sar_recovery=enabled,
                    sar_scale=scale,
                    sar_min_drop_db=min_drop,
                )
                scores = []
                for _, fold_val in folds:
                    result = evaluate_bs(dataset, fold_val, params)
                    if result["iou_burn"] is not None:
                        scores.append(0.35 * result["iou_burn"] + 0.30 * result["miou_sev"])
                if not scores:
                    continue
                objective = float(np.mean(scores))
                if objective > best_sar["objective"]:
                    result = evaluate_bs(dataset, val_ids, params)
                    best_sar = {
                        "objective": round(objective, 5),
                        "sar_recovery": enabled,
                        "sar_scale": list(scale),
                        "sar_min_drop_db": min_drop,
                        "iou_burn": result["iou_burn"],
                        "miou_sev": result["miou_sev"],
                        "fold_scores": [round(v, 5) for v in scores],
                    }
                    if verbose:
                        print(
                            f"  SAR: recovery={enabled} scale={scale} drop≥{min_drop} дБ "
                            f"objective(2 фолда)={objective:.4f} "
                            f"val: IoU_burn={result['iou_burn']:.4f} mIoU={result['miou_sev']:.4f}"
                        )
        best["params"]["sar_recovery"] = best_sar["sar_recovery"]
        best["params"]["sar_scale"] = best_sar["sar_scale"]
        best["params"]["sar_min_drop_db"] = best_sar["sar_min_drop_db"]
        best["sar"] = {k: v for k, v in best_sar.items() if k != "objective"}
        train_params = replace(
            base_params,
            sar_recovery=best_sar["sar_recovery"],
            sar_scale=tuple(best_sar["sar_scale"]),
            sar_min_drop_db=best_sar["sar_min_drop_db"],
        )
        train_result = evaluate_bs(dataset, train_ids, train_params)
        best["train_iou_burn"] = train_result["iou_burn"]
    return best


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Подбор порогов решения «КосмоФАЙР-2»")
    ap.add_argument("--data-dir", required=True, help="каталог обучающей части")
    ap.add_argument("--out", default="weights/weights.json")
    ap.add_argument("--val-frac", type=float, default=0.25)
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--fast", action="store_true", help="уменьшенные сетки поиска (для тестов и черновых прогонов)")
    args = ap.parse_args(argv)
    if args.fast:
        AF_GRID.update({k: v[:2] for k, v in AF_GRID.items()})
        BS_GRID.update({k: v[:2] for k, v in BS_GRID.items()})

    dataset = Dataset(args.data_dir)
    af_train, af_val = _split_ids(dataset, "af", args.val_frac, args.seed)
    bs_train, bs_val = _split_ids(dataset, "bs", args.val_frac, args.seed)

    print("=== Модуль детекции активного горения (AF) ===")
    baseline_af = evaluate_af(dataset, af_val, af_module.AFParams())
    print(f"baseline (значения по умолчанию): F1={baseline_af['f1_af']} на {baseline_af['n']} чипах")
    af_result = tune_af(dataset, af_train, af_val)
    best_af = af_result["rules"]
    blob_result = af_result.get("blobs", {})

    print("=== Модуль картирования гарей (BS) ===")
    baseline_bs = evaluate_bs(dataset, bs_val, bs_module.BSParams())
    print(f"baseline: IoU_burn={baseline_bs['iou_burn']} mIoU_sev={baseline_bs['miou_sev']} на {baseline_bs['n']} чипах")
    best_bs = tune_bs(dataset, bs_train, bs_val)

    model_path = None
    if af_result["mode"] == "blobs" and blob_result.get("model") is not None:
        model_path = Path(args.out).with_name("blob_filter.pkl")
        blob_result["model"].save(model_path)
        print(f"классификатор очагов сохранён: {model_path}")

    weights = {
        "version": 2,
        "seed": args.seed,
        "af_mode": af_result["mode"],
        "blob_filter": None if model_path is None else str(model_path.name),
        "af": best_af.get("params", {}),
        "bs": best_bs.get("params", {}),
        "train_metrics": {
            "af_val_f1": best_af.get("f1_af"),
            "af_train_f1": best_af.get("train_f1_af"),
            "af_baseline_f1": baseline_af.get("f1_af"),
            "bs_val_iou_burn": best_bs.get("iou_burn"),
            "bs_val_miou_sev": best_bs.get("miou_sev"),
            "bs_baseline_iou_burn": baseline_bs.get("iou_burn"),
            "bs_baseline_miou_sev": baseline_bs.get("miou_sev"),
            "af_blob_filter_val_f1": blob_result.get("f1_af"),
            "af_blob_filter_features_top": blob_result.get("importances"),
            "af_chosen_mode": af_result["mode"],
            "bs_sar_selection": best_bs.get("sar"),
        },
        "split": {"af_train": len(af_train), "af_val": len(af_val), "bs_train": len(bs_train), "bs_val": len(bs_val)},
    }
    path = save_weights(weights, args.out)
    print(f"веса сохранены: {path}")
    print(json.dumps(weights, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
