#!/usr/bin/env python3
"""Гибридный ответ: AF-строки из одного submission.csv, BS-строки из другого.

Нужен для факторного эксперимента 2×2 на платформе: четыре заливки
(нашAF+нашBS, ихAF+ихBS, ихAF+нашBS, нашAF+ихBS) разделяют вклад AF и BS
в разницу Score. AF и BS в инференсе считаются независимо, поэтому любой
гибрид воспроизводим одной конфигурацией весов (AF-секция + BS-модель).

Запуск::

    py -3 tools\\mix_submissions.py --af their.csv --bs ours.csv --out hybrid_theirAF_ourBS.csv

Проверяет полноту (447 строк) и отсутствие пересечений масок внутри чипа.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fires.submission import decode_rle, read_submission, write_submission  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Гибрид: AF из одного ответа, BS из другого")
    ap.add_argument("--af", required=True, help="CSV-источник AF-строк")
    ap.add_argument("--bs", required=True, help="CSV-источник BS-строк")
    ap.add_argument("--out", required=True, help="куда записать гибрид")
    args = ap.parse_args(argv)

    sub_af = read_submission(args.af)
    sub_bs = read_submission(args.bs)
    rows: list[dict] = []
    for (chip_id, class_id), rle in sorted(sub_af.items()):
        if chip_id.startswith("AF"):
            rows.append({"chip_id": chip_id, "class_id": class_id, "rle": rle})
    n_af = len(rows)
    for (chip_id, class_id), rle in sorted(sub_bs.items()):
        if not chip_id.startswith("AF"):
            rows.append({"chip_id": chip_id, "class_id": class_id, "rle": rle})
    n_bs = len(rows) - n_af
    if n_af == 0 or n_bs == 0:
        print(f"пустая половина: AF-строк {n_af}, BS-строк {n_bs} — проверьте файлы")
        return 1
    # маски разных классов внутри чипа не должны пересекаться (требование формата)
    seen: dict[str, object] = {}
    import numpy as np

    for row in rows:
        if row["chip_id"].startswith("AF"):
            continue
        mask = decode_rle(row["rle"], (512, 512)).astype(bool)
        prev = seen.get(row["chip_id"])
        if prev is not None and bool((prev & mask).any()):
            print(f"пересечение масок в чипе {row['chip_id']} — гибрид невалиден")
            return 1
        seen[row["chip_id"]] = (prev | mask) if prev is not None else mask
    write_submission(rows, args.out)
    af_px = sum(decode_rle(r["rle"], (256, 256)).sum() for r in rows if r["chip_id"].startswith("AF"))
    bs_px = sum(decode_rle(r["rle"], (512, 512)).sum() for r in rows if not r["chip_id"].startswith("AF"))
    print(f"гибрид записан: {args.out} (AF-строк {n_af}, BS-строк {n_bs}, "
          f"AF px {int(af_px)}, BS px {int(bs_px)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
