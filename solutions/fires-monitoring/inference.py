#!/usr/bin/env python3
"""Единая точка входа инференса (требование постановки).

    python inference.py --data-dir /path/to/test --output /path/to/submission.csv

Скрипт:

* читает ``sample_submission.csv`` из каталога данных и обрабатывает **все** чипы из шаблона,
  включая сильно заоблачные (они не должны приводить к падению);
* формирует файл строго в требуемом формате (RLE, пары ``chip_id,class_id`` как в шаблоне);
* не требует интерактивного ввода, печатает тайминг и завершается с кодом 0;
* детерминирован: пороги берутся из ``weights.json`` (или значения по умолчанию), случайных
  операций нет — повторный запуск даёт тот же файл.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

from fires import af as af_module
from fires import bs as bs_module
from fires.chips import Dataset
from fires.submission import read_template, validate_submission, write_submission
from fires.weights import load_weights


def process(data_dir: Path, output: Path, weights_path: Path | None = None, limit: int | None = None,
            verbose: bool = True) -> dict:
    t0 = time.perf_counter()
    weights = load_weights(weights_path)
    af_params = af_module.to_params(weights.get("af", {}))
    bs_params = bs_module.to_params(weights.get("bs", {}))

    blob_filter = None
    if weights.get("af_mode") == "blobs" and weights.get("blob_filter"):
        from fires.blobfilter import BlobFilter

        base = Path(weights_path).parent if weights_path else Path(__file__).resolve().parent / "weights"
        blob_filter = BlobFilter.load(base / weights["blob_filter"])

    dataset = Dataset(data_dir)
    template_path = data_dir / "sample_submission.csv"
    if not template_path.exists():
        raise FileNotFoundError(f"Не найден шаблон ответа: {template_path}")
    template = read_template(template_path)
    template_ids = sorted({chip_id for chip_id, _ in template})
    if limit:
        template_ids = template_ids[:limit]

    rows: list[dict] = []
    shapes: dict[str, tuple[int, int]] = {}
    stats: dict[str, dict] = {"af": {}, "bs": {}}
    af_px_total = bs_px_total = 0
    processed = skipped = 0

    for chip_id in template_ids:
        try:
            chip = dataset.load(chip_id)
        except Exception as exc:  # чип не должен «ронять» инференс
            if verbose:
                print(f"[warn] {chip_id}: {exc}", file=sys.stderr)
            skipped += 1
            continue

        kind = dataset.kind_of(chip_id)
        shape = chip.shape
        shapes[chip_id] = shape

        if kind == "af":
            try:
                mask, details = af_module.detect_chip(chip, af_params, return_details=True, blob_filter=blob_filter)
                stats["af"] = details
            except Exception as exc:
                if verbose:
                    print(f"[warn] {chip_id}: AF не посчитан ({exc}), пишем пустую маску", file=sys.stderr)
                mask = np.zeros(shape, dtype=bool)
            af_px_total += int(mask.sum())
            rows.append({"chip_id": chip_id, "class_id": 1, "rle": _rle(mask)})
        else:
            try:
                severity, details = bs_module.classify_chip(chip, bs_params, return_details=True)
                stats["bs"] = details
            except Exception as exc:
                if verbose:
                    print(f"[warn] {chip_id}: BS не посчитан ({exc}), пишем пустые маски", file=sys.stderr)
                severity = np.zeros(shape, dtype=np.uint8)
            for class_id in (1, 2, 3):
                mask = severity == class_id
                bs_px_total += int(mask.sum())
                rows.append({"chip_id": chip_id, "class_id": class_id, "rle": _rle(mask)})

        processed += 1

    write_submission(rows, output)
    elapsed = time.perf_counter() - t0

    report = {
        "chips_processed": processed,
        "chips_skipped": skipped,
        "rows_written": len(rows),
        "af_fire_px": af_px_total,
        "bs_burned_px": bs_px_total,
        "seconds": round(elapsed, 2),
        "output": str(output),
        "details": stats,
    }
    if verbose:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


def _rle(mask: np.ndarray) -> str:
    from fires.submission import encode_rle

    return encode_rle(mask)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Инференс решения «КосмоФАЙР-2»")
    ap.add_argument("--data-dir", required=True, help="каталог с тестовыми чипами и sample_submission.csv")
    ap.add_argument("--output", required=True, help="путь к submission.csv")
    ap.add_argument("--weights", default=None, help="путь к weights.json (по умолчанию weights/weights.json)")
    ap.add_argument("--limit", type=int, default=None, help="обработать только первые N чипов (отладка)")
    ap.add_argument("--validate", action="store_true", help="проверить результат по шаблону и границам чипов")
    args = ap.parse_args(argv)

    report = process(Path(args.data_dir), Path(args.output), Path(args.weights) if args.weights else None,
                     limit=args.limit)

    if args.validate:
        shapes = {cid: (int(a), int(b)) for cid, (a, b) in report_shapes(Path(args.data_dir)).items()}
        check = validate_submission(args.output, Path(args.data_dir) / "sample_submission.csv", shapes, strict=False)
        print(json.dumps({"validation": check}, ensure_ascii=False, indent=2))
        return 0 if check["ok"] else 1
    return 0


def report_shapes(data_dir: Path) -> dict[str, tuple[int, int]]:
    """Размеры чипов из meta.csv (для валидации границ RLE)."""

    dataset = Dataset(data_dir)
    shapes: dict[str, tuple[int, int]] = {}
    for chip_id in dataset.chip_ids():
        row = dataset.meta.get(chip_id, {})
        try:
            shapes[chip_id] = (int(row.get("height")), int(row.get("width")))
        except (TypeError, ValueError):
            try:
                shapes[chip_id] = dataset.load(chip_id).shape
            except Exception:
                continue
    return shapes


if __name__ == "__main__":
    raise SystemExit(main())
