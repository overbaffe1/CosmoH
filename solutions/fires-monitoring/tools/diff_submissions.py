#!/usr/bin/env python3
"""Сравнение двух submission.csv: где именно расходятся ответы.

Показывает: суммарные пиксели AF/BS по классам, попиксельное согласие
(IoU/F1 между ответами) и топ чипов с biggest расхождениями — кандидатов
на разбор. Нужен, чтобы понять, откуда берётся разница платформного Score
между двумя сабмитами (AF? BS? какие чипы и классы?).

Запуск::

    py -3 tools\\diff_submissions.py --a submission.csv --b ..\\cosmo3\\submission.csv

Эталона не нужно — сравниваются два ответа между собой.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fires.submission import decode_rle, read_submission  # noqa: E402


def _shape(chip_id: str) -> tuple[int, int]:
    if chip_id.startswith("AF"):
        return (256, 256)
    return (512, 512)


def _counts(sub: dict[tuple[str, int], str]) -> dict[tuple[str, int], int]:
    out = {}
    for key, rle in sub.items():
        mask = decode_rle(rle, _shape(key[0]))
        out[key] = int(mask.sum())
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Сравнение двух submission.csv")
    ap.add_argument("--a", required=True, help="первый ответ (например, наш)")
    ap.add_argument("--b", required=True, help="второй ответ (например, cosmo3)")
    ap.add_argument("--top", type=int, default=10)
    args = ap.parse_args(argv)

    sub_a = read_submission(args.a)
    sub_b = read_submission(args.b)
    keys = sorted(set(sub_a) | set(sub_b))
    if set(sub_a) != set(sub_b):
        print(f"ВНИМАНИЕ: набор строк различается: A={len(sub_a)}, B={len(sub_b)}, "
              f"общих={len(set(sub_a) & set(sub_b))}")
    ca = _counts({k: sub_a.get(k, "") for k in keys})
    cb = _counts({k: sub_b.get(k, "") for k in keys})

    print(f"A: {args.a}\nB: {args.b}")
    print("\n--- суммарные пиксели по классам ---")
    print(f"  {'класс':<14}{'A':>12}{'B':>12}{'Δ=B−A':>12}")
    for label, sel in (("AF (огонь)", [k for k in keys if k[0].startswith("AF")]),
                       ("BS класс 1", [k for k in keys if not k[0].startswith("AF") and k[1] == 1]),
                       ("BS класс 2", [k for k in keys if not k[0].startswith("AF") and k[1] == 2]),
                       ("BS класс 3", [k for k in keys if not k[0].startswith("AF") and k[1] == 3])):
        sa = sum(ca[k] for k in sel)
        sb = sum(cb[k] for k in sel)
        print(f"  {label:<14}{sa:12d}{sb:12d}{sb - sa:+12d}")

    # попиксельное согласие: декодируем маски и сравниваем
    af_tp = af_a = af_b = 0
    burn_tp = burn_a = burn_b = 0
    cls_tp = {1: 0, 2: 0, 3: 0}
    cls_a = {1: 0, 2: 0, 3: 0}
    cls_b = {1: 0, 2: 0, 3: 0}
    chip_diff: dict[str, int] = {}
    for chip_id, class_id in keys:
        ma = decode_rle(sub_a.get((chip_id, class_id), ""), _shape(chip_id)).astype(bool)
        mb = decode_rle(sub_b.get((chip_id, class_id), ""), _shape(chip_id)).astype(bool)
        chip_diff[chip_id] = chip_diff.get(chip_id, 0) + int((ma ^ mb).sum())
        if chip_id.startswith("AF"):
            af_tp += int((ma & mb).sum())
            af_a += int(ma.sum())
            af_b += int(mb.sum())
        else:
            burn_tp += int((ma & mb).sum())
            burn_a += int(ma.sum())
            burn_b += int(mb.sum())
            cls_tp[class_id] += int((ma & mb).sum())
            cls_a[class_id] += int(ma.sum())
            cls_b[class_id] += int(mb.sum())
    af_f1 = 2 * af_tp / max(1, af_a + af_b)
    burn_iou = burn_tp / max(1, burn_a + burn_b - burn_tp)
    print(f"\n--- согласие ответов (1.0 = идентичны) ---")
    print(f"  AF: F1(A,B)={af_f1:.4f} (общих px {af_tp}, только A {af_a - af_tp}, только B {af_b - af_tp})")
    print(f"  BS гарь: IoU(A,B)={burn_iou:.4f}")
    for c in (1, 2, 3):
        iou = cls_tp[c] / max(1, cls_a[c] + cls_b[c] - cls_tp[c])
        print(f"    класс {c}: IoU={iou:.4f} (A {cls_a[c]}, B {cls_b[c]})")

    print(f"\n--- топ-{args.top} чипов по расхождению (попиксельная разница) ---")
    for chip_id, diff in sorted(chip_diff.items(), key=lambda kv: -kv[1])[: args.top]:
        if diff == 0:
            break
        print(f"  {chip_id}: {diff} px")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
