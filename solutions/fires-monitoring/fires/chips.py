"""Чтение чипов: автоопределение раскладки файлов и каналов.

Организаторы не публикуют точные имена файлов, поэтому модуль:

1. находит ``meta.csv`` и ``sample_submission.csv`` в корне набора;
2. для каждого ``chip_id`` собирает файлы, начинающиеся с этого идентификатора;
3. распознаёт канал/слой по имени файла (``I1``…``I5``, ``B2``…``B12``, ``B8A``, ``SCL``,
   ``VV``, ``VH``, ``DEM``, ``landcover``, ``valid``, ``slope``, ``mask``, ``mask_sev``,
   ``pre``/``post``, ``t1``/``t2`` …);
4. поддерживает два варианта поставки: отдельный файл на канал и многоканальный стек,
   где порядок каналов соответствует таблицам постановки.

Диагностика раскладки доступна командой ``python -m fires.chips --data-dir <путь>``:
она печатает, какие каналы найдены для каждого типа чипа. Это первое, что нужно
запустить на реальных данных организаторов.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import tifffile

#: Порядок каналов в многоканальном стеке (таблицы постановки).
AF_STACK_ORDER = ("I1", "I2", "I3", "I4", "I5")
BS_STACK_ORDER = ("B2", "B3", "B4", "B5", "B6", "B7", "B8A", "B11", "B12", "SCL")

#: Регулярные выражения распознавания слоёв. Порядок важен: более специфичные — раньше.
LAYER_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("B8A", re.compile(r"(?:^|[^a-z0-9])b8a(?:[^a-z0-9]|$)", re.I)),
    ("B12", re.compile(r"(?:^|[^a-z0-9])b12(?:[^a-z0-9]|$)", re.I)),
    ("B11", re.compile(r"(?:^|[^a-z0-9])b11(?:[^a-z0-9]|$)", re.I)),
    ("SCL", re.compile(r"(?:^|[^a-z0-9])scl(?:[^a-z0-9]|$)", re.I)),
    ("B2", re.compile(r"(?:^|[^a-z0-9])b0?2(?:[^a-z0-9]|$)", re.I)),
    ("B3", re.compile(r"(?:^|[^a-z0-9])b0?3(?:[^a-z0-9]|$)", re.I)),
    ("B4", re.compile(r"(?:^|[^a-z0-9])b0?4(?:[^a-z0-9]|$)", re.I)),
    ("B5", re.compile(r"(?:^|[^a-z0-9])b0?5(?:[^a-z0-9]|$)", re.I)),
    ("B6", re.compile(r"(?:^|[^a-z0-9])b0?6(?:[^a-z0-9]|$)", re.I)),
    ("B7", re.compile(r"(?:^|[^a-z0-9])b0?7(?:[^a-z0-9]|$)", re.I)),
    ("I1", re.compile(r"(?:^|[^a-z0-9])i0?1(?:[^a-z0-9]|$)", re.I)),
    ("I2", re.compile(r"(?:^|[^a-z0-9])i0?2(?:[^a-z0-9]|$)", re.I)),
    ("I3", re.compile(r"(?:^|[^a-z0-9])i0?3(?:[^a-z0-9]|$)", re.I)),
    ("I4", re.compile(r"(?:^|[^a-z0-9])i0?4(?:[^a-z0-9]|$)", re.I)),
    ("I5", re.compile(r"(?:^|[^a-z0-9])i0?5(?:[^a-z0-9]|$)", re.I)),
    ("VV", re.compile(r"(?:^|[^a-z0-9])vv(?:[^a-z0-9]|$)", re.I)),
    ("VH", re.compile(r"(?:^|[^a-z0-9])vh(?:[^a-z0-9]|$)", re.I)),
    ("DEM", re.compile(r"(?:^|[^a-z0-9])(dem|elevation|height)(?:[^a-z0-9]|$)", re.I)),
    ("slope", re.compile(r"(?:^|[^a-z0-9])(slope|уклон)(?:[^a-z0-9]|$)", re.I)),
    ("aspect", re.compile(r"(?:^|[^a-z0-9])(aspect|экспозиц)(?:[^a-z0-9]|$)", re.I)),
    ("landcover", re.compile(r"(?:^|[^a-z0-9])(landcover|lulc|worldcover)(?:[^a-z0-9]|$)", re.I)),
    ("valid", re.compile(r"(?:^|[^a-z0-9])(valid|validity|quality)(?:[^a-z0-9]|$)", re.I)),
    ("mask_sev", re.compile(r"(?:^|[^a-z0-9])(mask_sev|sev_mask|severity)(?:[^a-z0-9]|$)", re.I)),
    ("mask", re.compile(r"(?:^|[^a-z0-9])(mask|target|label)(?:[^a-z0-9]|$)", re.I)),
]

#: Токены для колонок meta.csv, где встречается идентификатор канала.
META_ALIASES = {
    "chip_id": ("chip_id", "id", "chip"),
    "kind": ("kind", "type", "task"),
    "width": ("width", "w"),
    "height": ("height", "h"),
    "gsd": ("gsd", "resolution", "pixel_size"),
    "valid_frac": ("valid_frac",),
    "cloud_frac": ("cloud_frac", "cloud"),
    "acq_datetime": ("acq_datetime", "datetime", "acq_time", "date"),
    "date_pre": ("date_pre",),
    "date_post": ("date_post",),
}


def gapless(path: Path) -> bool:
    return path.suffix.lower() in {".tif", ".tiff", ".tff"}


def read_raster(path: str | Path) -> np.ndarray:
    """Читает растр; для 3-канальных изображений возвращает первый канал.

    Возвращает 2D-массив (или 3D, если каналов больше одного и это многоканальный стек —
    тогда решение принимает вызывающий код). Геопривязка в тестовой части скрыта, поэтому
    она не требуется: координаты восстанавливаются сервисом из каталога сцен.
    """

    arr = tifffile.imread(str(path))
    if arr.ndim == 3 and arr.shape[-1] in (3, 4) and arr.shape[0] > 8:
        arr = arr[..., 0]  # RGB-превью: берём первый канал
    return arr


@dataclass
class Chip:
    """Один чип: словари слоёв, метаданные и (для train) эталонные маски."""

    chip_id: str
    kind: str
    layers: dict[str, np.ndarray] = field(default_factory=dict)
    pre: dict[str, np.ndarray] = field(default_factory=dict)
    post: dict[str, np.ndarray] = field(default_factory=dict)
    s1_pre: dict[str, np.ndarray] = field(default_factory=dict)
    s1_post: dict[str, np.ndarray] = field(default_factory=dict)
    meta: dict = field(default_factory=dict)
    mask: np.ndarray | None = None
    mask_sev: np.ndarray | None = None

    @property
    def height(self) -> int:
        for value in list(self.layers.values()) + list(self.pre.values()) + list(self.post.values()):
            return int(value.shape[0])
        raise ValueError(f"{self.chip_id}: нет ни одного слоя")

    @property
    def width(self) -> int:
        for value in list(self.layers.values()) + list(self.pre.values()) + list(self.post.values()):
            return int(value.shape[1])
        raise ValueError(f"{self.chip_id}: нет ни одного слоя")

    @property
    def shape(self) -> tuple[int, int]:
        return (self.height, self.width)


class Dataset:
    """Набор чипов: индексация по ``meta.csv`` или по именам файлов."""

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.meta: dict[str, dict] = self._read_meta()
        self.files: dict[str, list[Path]] = {}
        self._index_files()

    def _read_meta(self) -> dict[str, dict]:
        import csv

        path = self.root / "meta.csv"
        if not path.exists():
            return {}
        out: dict[str, dict] = {}
        with path.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                chip_id = row.get("chip_id") or row.get("id") or row.get("chip")
                if chip_id:
                    out[str(chip_id)] = row
        return out

    def _index_files(self) -> None:
        for path in sorted(self.root.rglob("*")):
            if not path.is_file() or not gapless(path):
                continue
            name = path.stem
            for meta_id in self.meta:
                if name.startswith(meta_id):
                    self.files.setdefault(meta_id, []).append(path)
                    break
            else:
                # чип без meta.csv: идентификатор — часть имени до последнего токена слоя
                stem = re.sub(r"_(pre|post|s1|mask|mask_sev|valid|scl|landcover|dem|slope|aspect|i[1-5]|b\d+a?)$", "", name, flags=re.I)
                self.files.setdefault(stem, []).append(path)

    def chip_ids(self, kind: str | None = None) -> list[str]:
        ids = sorted(self.files)
        if kind is None:
            return ids
        out = []
        for chip_id in ids:
            k = self.kind_of(chip_id)
            if k == kind:
                out.append(chip_id)
        return out

    def kind_of(self, chip_id: str) -> str:
        meta = self.meta.get(chip_id, {})
        kind = str(meta.get("kind") or "").lower()
        if kind in {"af", "bs"}:
            return kind
        return "af" if chip_id.lower().split("_")[0].endswith("af") else ("bs" if "bs" in chip_id.lower() else "af")

    def _classify(self, path: Path) -> tuple[str, str | None]:
        """Возвращает (слой, дата) где дата ∈ {None, 'pre', 'post'}."""

        stem = path.stem
        suffix = stem
        for token, date in (("_pre", "pre"), ("_post", "post"), ("_t1", "pre"), ("_t2", "post"),
                            ("_before", "pre"), ("_after", "post")):
            if token in stem.lower():
                suffix = re.sub(token, "", stem, flags=re.I)
                date = date
                break
        else:
            date = None
        for name, pattern in LAYER_PATTERNS:
            if pattern.search(suffix):
                return name, date
        return "unknown", date

    def load(self, chip_id: str) -> Chip:
        paths = self.files.get(chip_id, [])
        if not paths:
            raise KeyError(f"Чип {chip_id} не найден в {self.root}")
        kind = self.kind_of(chip_id)
        chip = Chip(chip_id=chip_id, kind=kind, meta=self.meta.get(chip_id, {}))
        stacks: list[np.ndarray] = []

        for path in paths:
            layer, date = self._classify(path)
            arr = read_raster(path)
            if arr.ndim == 3 and arr.shape[0] <= 12:  # (C, H, W) — многоканальный стек
                stacks.append(arr)
                continue
            if layer == "unknown":
                continue
            if kind == "af" and date is None:
                chip.layers[layer] = arr
            elif kind == "bs":
                if layer in {"SCL", "landcover", "valid", "slope", "aspect", "DEM"}:
                    chip.layers[layer] = arr
                elif layer in {"VV", "VH"} and date in {"pre", "post"}:
                    (chip.s1_pre if date == "pre" else chip.s1_post)[layer] = arr
                elif date in {"pre", "post"}:
                    (chip.pre if date == "pre" else chip.post)[layer] = arr
                elif date is None and layer in BS_STACK_ORDER:
                    chip.layers[layer] = arr
            if layer == "mask":
                chip.mask = arr
            elif layer == "mask_sev":
                chip.mask_sev = arr

        for stack in stacks:
            if kind == "af":
                for i, name in enumerate(AF_STACK_ORDER):
                    if i < stack.shape[0]:
                        chip.layers.setdefault(name, stack[i])
            else:
                for i, name in enumerate(BS_STACK_ORDER):
                    if i < stack.shape[0]:
                        chip.layers.setdefault(name, stack[i])

        # если BS подан единым стеком pre/post без явных дат — делим по порядку каналов
        if kind == "bs" and not chip.pre and any(k in chip.layers for k in BS_STACK_ORDER):
            pass  # слои уже в chip.layers, решение работает и так

        return chip

    def describe(self, max_chips: int = 2) -> dict:
        """Диагностика раскладки: какие каналы реально найдены."""

        out: dict = {"root": str(self.root), "n_meta": len(self.meta), "n_chips": len(self.files), "kinds": {}}
        for kind in ("af", "bs"):
            ids = self.chip_ids(kind)
            out["kinds"][kind] = {"count": len(ids), "examples": []}
            for chip_id in ids[:max_chips]:
                chip = self.load(chip_id)
                out["kinds"][kind]["examples"].append(
                    {
                        "chip_id": chip_id,
                        "layers": sorted(chip.layers),
                        "pre": sorted(chip.pre),
                        "post": sorted(chip.post),
                        "s1_pre": sorted(chip.s1_pre),
                        "s1_post": sorted(chip.s1_post),
                        "mask": None if chip.mask is None else list(chip.mask.shape),
                        "mask_sev": None if chip.mask_sev is None else list(chip.mask_sev.shape),
                        "shape": list(chip.shape),
                    }
                )
        return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Диагностика раскладки чипов организаторов")
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--max-chips", type=int, default=2)
    args = ap.parse_args(argv)
    print(json.dumps(Dataset(args.data_dir).describe(args.max_chips), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
