#!/usr/bin/env python3
"""Локальная оценка решения на чипах с эталонными масками.

    python evaluate.py --data-dir /path/to/train [--weights weights/weights.json] [--ablation]

Печатает компоненты метрики соревнования (F1_af, IoU_burn, mIoU_sev и Score) и, при
``--ablation``, вклад отдельных механизмов: отсева техногенных источников, блика,
подтверждения по Sentinel-1, порогов по типу покрова. Абляции нужны для отчёта
(критерий «Эксперименты и сравнения»).
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
from fires.weights import load_weights


def collect(dataset: Dataset, af_params, bs_params, limit: int | None = None, blob_filter=None):
    af_pairs, bs_pairs = {}, {}
    for chip_id in dataset.chip_ids():
        chip = dataset.load(chip_id)
        if chip.kind == "af" and chip.mask is not None:
            af_pairs[chip_id] = (chip.mask.astype(bool), af_module.detect_chip(chip, af_params, blob_filter=blob_filter))
        elif chip.kind == "bs" and chip.mask_sev is not None:
            bs_pairs[chip_id] = (chip.mask_sev.astype(np.uint8), bs_module.classify_chip(chip, bs_params))
        if limit and len(af_pairs) + len(bs_pairs) >= limit:
            break
    return af_pairs, bs_pairs


def evaluate(dataset: Dataset, af_params, bs_params, blob_filter=None) -> dict:
    af_pairs, bs_pairs = collect(dataset, af_params, bs_params, blob_filter=blob_filter)
    result = score_from_pairs(af_pairs, bs_pairs)
    result["n_af"] = len(af_pairs)
    result["n_bs"] = len(bs_pairs)
    return result


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Оценка решения на чипах с масками")
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--weights", default=None)
    ap.add_argument("--ablation", action="store_true")
    ap.add_argument("--blob-filter", default=None, help="путь к weights/blob_filter.pkl")
    args = ap.parse_args(argv)

    dataset = Dataset(args.data_dir)
    weights = load_weights(args.weights)
    af_params = af_module.to_params(weights.get("af", {}))
    bs_params = bs_module.to_params(weights.get("bs", {}))

    from fires.blobfilter import BlobFilter

    blob_filter = BlobFilter.load(args.blob_filter) if args.blob_filter else None
    print("=== Итоговая конфигурация ===")
    print(json.dumps(evaluate(dataset, af_params, bs_params, blob_filter=blob_filter), ensure_ascii=False, indent=2))

    if not args.ablation:
        return 0

    print("\n=== Абляции ===")
    # В режиме классификатора очагов правила AF задают состав кандидатов, а решение
    # принимает модель, поэтому варианты отключают именно механизмы классификатора.
    import copy

    def variant(**config_changes):
        if blob_filter is None:
            return None
        clone = copy.deepcopy(blob_filter)
        for key, value in config_changes.items():
            setattr(clone.config, key, value)
        return clone

    threshold_filter = blob_filter
    if blob_filter is not None:
        threshold_filter = copy.deepcopy(blob_filter)
        threshold_filter.threshold = 0.95

    variants: list[tuple[str, object, object, object]] = [
        ("AF: только правила (без классификатора очагов)", af_params, bs_params, None),
        ("AF: классификатор с порогом 0.95 вместо подобранного", af_params, bs_params, threshold_filter),
        ("AF: кандидаты только по мягким порогам", af_params, bs_params, variant(use_soft_candidates=False)),
        ("AF: без пиксельного гейта в блобе", af_params, bs_params, variant(pixel_t4=-1000.0, pixel_delta=-1000.0)),
        ("BS: без Sentinel-1", af_params, replace(bs_params, use_sar=False), blob_filter),
        ("BS: SAR без восстановления под облаком", af_params, replace(bs_params, sar_recovery=False), blob_filter),
        ("BS: без порогов по покрову (только USGS)", af_params, replace(bs_params, semi=bs_params.forest, cropland=bs_params.forest), blob_filter),
        ("BS: без заполнения дыр", af_params, replace(bs_params, fill_holes_mask=False), blob_filter),
        ("BS: без фильтрации мелких контуров", af_params, replace(bs_params, min_patch_px=1), blob_filter),
    ]
    for name, af_p, bs_p, bf in variants:
        res = evaluate(dataset, af_p, bs_p, blob_filter=bf)
        print(f"{name:48s} Score={res['score']:.4f}  F1_af={res['f1_af']:.4f}  IoU_burn={res['iou_burn']:.4f}  mIoU_sev={res['miou_sev']:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
