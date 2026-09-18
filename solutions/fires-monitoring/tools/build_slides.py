"""Сборка презентации боевого решения «КосмоФАЙР-2» (HTML + PDF).

Запуск:

    python tools/build_slides.py            # docs/presentation.pdf и docs/presentation.html
    python tools/build_slides.py --preview  # плюс PNG-страницы в docs/preview/

HTML самодостаточен (картинки в base64) и корректно печатается в PDF; PDF собирается
через matplotlib со шрифтом DejaVu (кириллица). Контент описан декларативно — текст
можно править перед защитой, не трогая вёрстку.
"""

from __future__ import annotations

import base64
import html
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs"
ACCENT = "#4fc3ff"
ACCENT2 = "#ffb03a"
BG = "#0e1116"
FG = "#e6edf3"
MUTED = "#93a4b8"


# --------------------------------------------------------------------------- контент

DECK: dict = {
    "slug": "cosmofire2",
    "title": "КосмоФАЙР-2",
    "subtitle": "Двухэтапный мониторинг природных пожаров по данным ДЗЗ",
    "kicker": "КосмоХакатон · Красноярск · 18–20 сентября 2026 · кейс «Двухэтапный мониторинг природных пожаров по данным ДЗЗ»",
    "images": {
        "detection": ROOT / "docs" / "figures" / "detection.png",
        "severity": ROOT / "docs" / "figures" / "severity.png",
        "map": ROOT / "docs" / "figures" / "service_map.png",
        "ablations": ROOT / "docs" / "figures" / "ablations.png",
    },
    "slides": [
        {"type": "bullets", "title": "Задача кейса и метрика", "bullets": [
            "**Два модуля.** AF: по чипу VIIRS 375 м (I1–I5, WorldCover, DEM, углы, ERA5) — бинарная маска природного горения. BS: по паре Sentinel-2 до/после (20 м, B2–B12 + SCL) и Sentinel-1 — степень поражения 0/1/2/3.",
            "**Метрика.** Score = 0.35 · F1_af + 0.35 · IoU_burn + 0.30 · mIoU_sev; счёт идёт по пулу пикселей (микро), пустой класс считается идеальным.",
            "**Формат.** submission.csv с RLE (пары «начало длина», нумерация с 1, без пересечений и соприкосновений), строки строго по sample_submission.",
            "**Жёсткие условия.** `python inference.py --data-dir … --output …` без интерактива, обработка < 30 с, воспроизводимость ±0.005, только открытые модели, техногенные факелы — ноль.",
        ]},
        {"type": "table", "title": "Данные", "header": ["Часть", "Размер", "Что в чипе", "Особенность"],
         "rows": [
             ["AF train", "420 чипов, 96×96 км", "I1–I5, landcover, DEM, углы, ERA5, valid, маска", "горение всего 0.035 % пикселей — редкое событие"],
             ["BS train", "224 чипа, 10.2×10.2 км", "S2 pre/post B2…B12, SCL, S1 VV/VH pre/post, маска 0–3", "236 360 га гари; 40/37/23 % по классам 1/2/3"],
             ["Test", "180 + 89 строк шаблона", "то же без эталона и без геопривязки", "геопривязка скрыта — сервис работает на своём каталоге"],
             ["Демо-набор", "синтетика репозитория", "воспроизводит все слои и артефакты (облака, факелы, блик)", "позволяет прогнать весь конвейер без доступа к диску организаторов"],
         ]},
        {"type": "code", "title": "Архитектура", "code": [
            "data/ ──▶ fires/chips.py ──▶ ┬─ fires/af.py (правила, контекстный тест, отсев факелов/блика)",
            "       (раскладка, каналы,   │        └─▶ fires/blobfilter.py (ML-фильтр очагов, HistGB)",
            "        стеки, маски)        └─ fires/bs.py (dNBR по типам покрова + подтверждение Sentinel-1)",
            "                                              │",
            "inference.py ──▶ fires/submission.py (RLE) ──▶ submission.csv (+ автовалидация по шаблону)",
            "train.py     ──▶ weights/weights.json + weights/blob_filter.pkl (сетки + классификатор)",
            "evaluate.py  ──▶ метрика соревнования + абляции для отчёта",
            "service/     ──▶ catalog.py (каталог сцен) ──▶ app.py (FastAPI: REST + GeoJSON + Shp + веб-карта)",
        ]},
        {"type": "bullets", "title": "AF: физика + обучаемый фильтр очагов", "bullets": [
            "**Скрининг.** Вода, невалидные пиксели и облака исключаются; блик не выбрасывается, а переводится в режим повышенных требований (ΔT выше порога на 9 K или I4 ≥ 335 K) — иначе терялись бы настоящие очаги внутри пятна.",
            "**Абсолютные тесты.** I4 ≥ 367 K (насыщение) и I4 ≥ 360 K. **Контекстный тест:** I4 > μ_фона + k·σ_фона в окне 71×71 и ΔT (I4 − I5) > 15 K днём / 10 K ночью — как в операционном продукте VIIRS 375 м.",
            "**Отсев техногенных источников.** В застройке (WorldCover 50) очаг должен быть заметно сильнее (ΔT > порог + 8 K или I4 ≥ 367 K) и крупнее 4 px; слабые одиночки на пашне и открытой почве убираются.",
            "**Главный механизм.** Кандидаты (мягкие пороги + правила) собираются в блобы 8-связностью и закрытием, а решение принимает HistGradientBoosting по 23 признакам блоба: площадь, форма, яркость, ΔT, признаки блика, состав типов покрова, контекст соседей.",
            "**Почему ML.** Газовый факел неотличим от пожара по одному пикселю: I4 насыщен, ΔT даже выше. Отличают его именно форма, площадь и окружение — это и видит классификатор.",
        ]},
        {"type": "bullets", "title": "BS: гарь по dNBR и Sentine-1", "bullets": [
            "**Индексы.** NBR = (B8A − B12)/(B8A + B12) для дат до/после; dNBR = NBR_pre − NBR_post; rdNBR используется как дополнительный признак.",
            "**Маскировка.** SCL (облака, тени, вода, снег), слой валидности, вода по WorldCover.",
            "**Пороги по типам покрова.** Лес и кустарник — шкала USGS (0.10 / 0.27 / 0.66); степь и пойма масштабируются вниз (0.04 / 0.12 / 0.28), пашня и открытая почва — (0.05 / 0.12 / 0.26); застройка и снег не картируются.",
            "**Sentinel-1.** Восстановление гари под облаком/тенью по падению VH: эквивалентный dNBR = −ΔVH / чувствительность (лес ≈ 3 дБ на единицу dNBR, остальное ≈ 1.5), минимум 1 дБ падения. Всё подбирается на обучающей части.",
            "**Постобработка.** Заполнение внутренних «дыр», удаление контуров меньше 6 px, сглаживание границ.",
        ]},
        {"type": "image", "title": "AF: пример детекции", "image": "detection",
         "caption": "Слева — яркостная температура I4, в центре — эталон (62 px горения на чипе), справа — ответ алгоритма: зелёный — верно найдено, красный — ложное, серый — пропуск. F1 на этом чипе 0.93."},
        {"type": "image", "title": "BS: пример картирования гари", "image": "severity",
         "caption": "Слева — dNBR, в центре — эталонная степень поражения 0–3, справа — ответ алгоритма. Классы: жёлтый — слабая, оранжевый — средняя, красный — сильная."},
        {"type": "metrics", "title": "Результаты на локальном стенде (синтетика)", "metrics": [
            ("Score на 180 чипах (dev-набор)", "0.9497"),
            ("F1_af (микро по пулу)", "0.9476"),
            ("IoU_burn", "0.9735"),
            ("mIoU_sev (классы 1/2/3)", "0.9243"),
            ("Скорость inference.py (180 чипов)", "5.1 с при лимите 30 с"),
            ("Воспроизводимость (повторный запуск)", "побайтово одинаковый submission.csv"),
        ]},
        {"type": "table", "title": "Абляции: вклад механизмов", "header": ["Вариант", "Score", "F1_af", "IoU_burn", "mIoU_sev"],
         "rows": [
             ["Итоговая конфигурация", "0.9497", "0.9476", "0.9735", "0.9243"],
             ["AF без классификатора очагов (только правила)", "0.8822", "0.7549", "0.9735", "0.9243"],
             ["AF без пиксельного гейта в блобе", "0.9269", "0.8825", "0.9735", "0.9243"],
             ["AF с порогом 0.95 вместо подобранного", "0.9482", "0.9434", "0.9735", "0.9243"],
             ["BS без порогов по типу покрова (только USGS)", "0.6828", "0.9476", "0.7810", "0.2595"],
             ["BS без Sentinel-1", "0.9509", "0.9476", "0.9579", "0.9465"],
             ["BS без заполнения дыр", "0.9388", "0.9476", "0.9539", "0.9109"],
             ["BS без фильтрации мелких контуров", "0.9037", "0.9476", "0.9010", "0.8556"],
         ],
         "widths": [6, 2, 2, 2, 2],
         "caption": "Ключевые выводы: классификатор очагов добавляет +0.067 Score (F1 0.755 → 0.948) — без него факелы и блик не отсекаются; пороги по типам покрова дают +0.27 (в степи и на пашне лесные пороги не работают); Sentinel-1 поднимает IoU_burn на 0.016 в облачных сценах, но на синтетике чуть проигрывает по mIoU — поэтому вариант по SAR выбирается на двух фолдах, а на реальных данных переобучается."},
        {"type": "bullets", "title": "Сервис: REST, GeoJSON, справка", "bullets": [
            "**Запрос.** Прямоугольник (`bbox`) или произвольный полигон + интервал дат; `POST /api/query` принимает всё одним вызовом.",
            "**Карта термоточек.** `GET /api/thermopoints` → GeoJSON FeatureCollection с датой, ΔT и температурой канала.",
            "**Контуры гари.** `GET /api/burn-contours` → GeoJSON с атрибутами id, severity, area_ha, chip_id, date; полигоны построены обходом границы компонент и упрощены Дугласом—Пекером.",
            "**Справка.** `GET /api/report` → суммарная площадь гари в гектарах, распределение по трём степеням, число контуров; `?format=csv` — машиночитаемая выгрузка.",
            "**Выгрузки.** `GET /api/export/contours.geojson` и `.shp` (архив .shp/.shx/.dbf/.prj, чистый Python, без GDAL).",
            "**Веб-карта и текстовая справка.** `GET /` — карта без CDN и тайлов: работает на площадке без интернета; весь функционал доступен и без интерфейса.",
        ]},
        {"type": "image", "title": "Сервис: каталог сцен", "image": "map",
         "caption": "Каталог собирается командой python -m service.catalog --data-dir <набор>: контуры гари по степеням поражения и термоточки. Геопривязка берётся из chips_geo.csv, если организаторы её дают; иначе каталог строится в демонстрационном режиме и это явно указано в ответе API."},
        {"type": "bullets", "title": "Воспроизводимость и ограничения", "bullets": [
            "**Детерминизм.** Все источники случайности зафиксированы (seed 20260918), обучение воспроизводится: `python train.py --data-dir <train> --out weights/weights.json`.",
            "**Проверяемость.** `evaluate.py` считает метрику соревнования тем же кодом, что и организаторы (микро-пул), `--ablation` печатает вклад механизмов; `inference.py --validate` проверяет формат ответа по шаблону.",
            "**Ограничение 1.** Реальные данные кейса (Яндекс.Диск) недоступны из среды разработки: все числа получены на синтетическом стенде, воспроизводящем раскладку и артефакты. На реальном наборе первым делом запускается диагностика `python -m fires.chips --data-dir <набор>` — она печатает распознанные каналы.",
            "**Ограничение 2.** Точность под облаками ограничена физикой: оптики там нет, помогает только Sentinel-1 при достаточном падении VH.",
            "**Ограничение 3.** Классы 1 и 2 в степи различаются слабо (запас биомассы мал) — часть ошибок неизбежна и видна в per-class IoU отчёта.",
        ]},
        {"type": "table", "title": "Соответствие критериям", "header": ["Критерий", "Что сдаём"],
         "rows": [
             ["Метрика (40)", "Score 0.9497 на локальном стенде; evaluate.py считает ровно те же компоненты"],
             ["Презентация (8)", "docs/presentation.pdf + HTML, фигуры собраны кодом решения"],
             ["Отчёт (20)", "docs/report.md: постановка, данные, метод, абляции, результаты, ограничения"],
             ["Качество кода (12)", "Модульная структура, docstrings, 38 тестов pytest, отсутствие «магии» в параметрах"],
             ["Сервис (12)", "REST + GeoJSON + Shapefile + справка (JSON/CSV) + веб-карта без интернета"],
             ["Скорость (8)", "5.1 с на 180 чипах при пороге 30 с (полный набор 447 строк — секунды)"],
             ["Воспроизводимость (±0.005)", "Зафиксированные seed, детерминированный инференс, повторный прогон совпадает побайтово"],
         ], "widths": [3, 8]},
        {"type": "bullets", "title": "Что делаем на реальных данных (первые 30 минут)", "bullets": [
            "`python -m fires.chips --data-dir <набор>` — убедиться, что все каналы распознаны (при новых именах файлов правила дополняются в одном месте).",
            "`python train.py --data-dir <train> --out weights/weights.json` — переобучение порогов и классификатора очагов на реальной обучающей части (1–2 минуты на 420 + 224 чипах).",
            "`python evaluate.py --data-dir <train> --ablation` — контроль метрики и абляций, проверка, что SAR-режим выбран корректно.",
            "`python inference.py --data-dir <test> --output submission.csv --validate` — сборка ответа и автопроверка формата по шаблону.",
            "`python -m service.catalog …` + `uvicorn service.app:app` — каталог и сервис для защиты.",
        ]},
        {"type": "bullets", "title": "Раскрытие (по положению хакатона)", "bullets": [
            "Использованы только открытые библиотеки: numpy, scikit-learn, scipy, tifffile, FastAPI, uvicorn, pydantic, pyshp, matplotlib, pytest.",
            "Физика и пороги — из открытых публикаций и продуктов: алгоритм VIIRS 375 м (Schroeder et al., 2014), шкала dNBR USGS, ESA WorldCover, Sentinel-1.",
            "Каркас решения (раскладка чипов, метрика, генератор синтетики, тесты) подготовлен до старта хакатона; объём работы в окне 18–20.09.2026 фиксируется историей коммитов.",
            "Воспроизводимость: весь конвейер работает офлайн, без обращения к внешним сервисам и без закрытых моделей.",
        ]},
    ],
}


# --------------------------------------------------------------------------- renderers

def _wrap(text: str, width: int = 96) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 <= width:
            cur = f"{cur} {w}".strip()
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _clean_md(text: str) -> str:
    """Убирает **жирный** и `код` — для PDF и HTML используем свои акценты."""

    return text.replace("**", "").replace("`", "")


def _maybe_png(fig, preview_dir: Path | None, name: str) -> None:
    if preview_dir is None:
        return
    preview_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(preview_dir / f"{name}.png", facecolor=BG, dpi=80)


def render_pdf(deck: dict, path: Path, preview_dir: Path | None = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with PdfPages(path) as pdf:
        # титульный слайд
        fig = plt.figure(figsize=(13.33, 7.5), facecolor=BG)
        fig.text(0.07, 0.70, deck["title"], color=FG, fontsize=44, weight="bold")
        fig.text(0.07, 0.62, deck["subtitle"], color=ACCENT, fontsize=22)
        fig.text(0.07, 0.52, deck["kicker"], color=MUTED, fontsize=12, wrap=True)
        fig.add_artist(Rectangle((0.07, 0.46), 0.20, 0.006, color=ACCENT2))
        fig.text(0.07, 0.10, "Воспроизводимо оффлайн · открытые данные · тесты в комплекте", color=MUTED, fontsize=11)
        pdf.savefig(fig, facecolor=BG)
        _maybe_png(fig, preview_dir, "00_title")
        plt.close(fig)

        for idx, slide in enumerate(deck["slides"], start=1):
            fig = plt.figure(figsize=(13.33, 7.5), facecolor=BG)
            fig.text(0.06, 0.90, slide["title"], color=FG, fontsize=26, weight="bold")
            fig.add_artist(Rectangle((0.06, 0.875), 0.10, 0.004, color=ACCENT))

            kind = slide["type"]
            if kind in {"bullets"}:
                y = 0.80
                for b in slide["bullets"]:
                    bold_prefix = b.startswith("**")
                    text = _clean_md(b)
                    lines = _wrap(text, 108)
                    fig.text(0.075, y, "—", color=ACCENT2, fontsize=14)
                    for i, line in enumerate(lines):
                        fig.text(0.098, y - i * 0.042, line, color=FG if not bold_prefix else "#ffffff",
                                 fontsize=13.5 if i == 0 else 13, va="top")
                    y -= 0.042 * len(lines) + 0.028
                    if y < 0.08:
                        break
            elif kind == "table":
                rows = slide["rows"]
                n = len(rows) + 1
                # ширины колонок: либо заданы явно, либо равные
                weights = slide.get("widths") or [1] * len(slide["header"])
                total = sum(weights)
                xs, acc = [], 0.06
                for w in weights:
                    xs.append(acc)
                    acc += 0.88 * w / total
                y = 0.80
                for j, h in enumerate(slide["header"]):
                    fig.text(xs[j] + 0.005, y, h, color=ACCENT, fontsize=12.5, weight="bold")
                fig.add_artist(Rectangle((0.06, y - 0.02), 0.88, 0.002, color="#2a3441"))
                y -= 0.055
                for row in rows:
                    cell_lines = []
                    for j, cell in enumerate(row):
                        cell_lines.append(_wrap(_clean_md(str(cell)), max(14, int(60 * weights[j] / max(weights))))
                    )
                    height = 0.05 * max(len(c) for c in cell_lines)
                    for j, lines in enumerate(cell_lines):
                        for i, line in enumerate(lines):
                            fig.text(xs[j] + 0.005, y - i * 0.038, line, color=FG, fontsize=11.5, va="top")
                    y -= height + 0.03
                if slide.get("caption"):
                    fig.text(0.06, max(0.08, y - 0.02), _clean_md(slide["caption"]), color=MUTED, fontsize=10.5, wrap=True)
            elif kind == "metrics":
                y = 0.78
                for label, value in slide["metrics"]:
                    fig.text(0.075, y, label, color=MUTED, fontsize=14)
                    fig.text(0.70, y, value, color=ACCENT2, fontsize=15, weight="bold")
                    fig.add_artist(Rectangle((0.075, y - 0.018), 0.80, 0.001, color="#222c38"))
                    y -= 0.105
            elif kind == "image":
                img = deck["images"].get(slide["image"])
                if img and Path(img).exists():
                    ax = fig.add_axes([0.055, 0.22, 0.89, 0.60])
                    ax.imshow(plt.imread(img))
                    ax.axis("off")
                if slide.get("caption"):
                    fig.text(0.06, 0.13, "\n".join(_wrap(_clean_md(slide["caption"]), 120)), color=MUTED, fontsize=10.5, va="top")
            elif kind == "code":
                code = "\n".join(slide["code"])
                fig.text(0.075, 0.78, code, color="#9cd2ff", fontsize=11.5, family="DejaVu Sans Mono", va="top")
            pdf.savefig(fig, facecolor=BG)
            _maybe_png(fig, preview_dir, f"{idx:02d}_slide")
            plt.close(fig)

        # финальный слайд
        fig = plt.figure(figsize=(13.33, 7.5), facecolor=BG)
        fig.text(0.07, 0.55, "Спасибо! Вопросы?", color=FG, fontsize=34, weight="bold")
        fig.text(0.07, 0.47, f"{deck['title']} · {deck['subtitle']}", color=ACCENT, fontsize=16)
        fig.text(0.07, 0.38, "Репозиторий: README с запуском, архитектурой, данными и лицензиями.\n"
                             "Демо поднимается одной командой, интернет не требуется.",
                 color=MUTED, fontsize=12.5)
        pdf.savefig(fig, facecolor=BG)
        plt.close(fig)
    return path


def render_html(deck: dict, path: Path) -> Path:
    def img_b64(p: Path) -> str:
        return "data:image/png;base64," + base64.b64encode(Path(p).read_bytes()).decode("ascii")

    parts = [
        "<!doctype html><html lang='ru'><head><meta charset='utf-8'>",
        f"<title>{html.escape(deck['title'])} — презентация</title><style>",
        "body{margin:0;background:#0b0f14;color:#e6edf3;font-family:system-ui,'Segoe UI',Roboto,sans-serif}",
        ".slide{width:min(1180px,94vw);margin:26px auto;background:#0e1116;border:1px solid #222c38;border-radius:14px;padding:34px 40px;box-shadow:0 8px 30px #0006}",
        "h1{font-size:44px;margin:0 0 6px}h2{font-size:26px;margin:0 0 18px;color:#e6edf3}",
        ".kicker{color:#93a4b8;font-size:14px;margin-bottom:26px}",
        ".sub{color:#4fc3ff;font-size:20px;margin-bottom:8px}",
        "ul{margin:0;padding-left:22px;line-height:1.65;font-size:17px}li{margin:7px 0}",
        "b{color:#fff}code{color:#9cd2ff}",
        "table{width:100%;border-collapse:collapse;font-size:15.5px}th,td{text-align:left;padding:8px 10px;border-bottom:1px solid #222c38;vertical-align:top}",
        "th{color:#4fc3ff;font-weight:600}",
        "img{width:100%;border-radius:10px}figcaption{color:#93a4b8;font-size:14px;margin-top:10px;line-height:1.5}",
        ".metrics{display:grid;grid-template-columns:1fr auto;gap:10px 26px;font-size:17px}",
        ".metrics .v{color:#ffb03a;font-weight:700}",
        ".rule{height:3px;width:110px;background:#ffb03a;border-radius:2px;margin:14px 0 22px}",
        "pre{background:#0b0f14;border:1px solid #222c38;border-radius:10px;padding:16px;overflow:auto;color:#9cd2ff;font-size:14.5px}",
        ".meta{color:#93a4b8;font-size:13px;margin-top:26px}",
        "@media print{body{background:#fff;color:#111}.slide{box-shadow:none;border-color:#ddd;page-break-after:always}}",
        "</style></head><body>",
        f"<section class='slide'><h1>{html.escape(deck['title'])}</h1>",
        f"<div class='sub'>{html.escape(deck['subtitle'])}</div><div class='rule'></div>",
        f"<div class='kicker'>{html.escape(deck['kicker'])}</div>",
        "<div class='meta'>Воспроизводимо оффлайн · открытые данные · тесты в комплекте</div></section>",
    ]

    for slide in deck["slides"]:
        parts.append(f"<section class='slide'><h2>{html.escape(slide['title'])}</h2><div class='rule'></div>")
        kind = slide["type"]
        if kind == "bullets":
            parts.append("<ul>")
            for b in slide["bullets"]:
                text = html.escape(b)
                while "**" in text:
                    text = text.replace("**", "<b>", 1).replace("**", "</b>", 1)
                while "`" in text:
                    text = text.replace("`", "<code>", 1).replace("`", "</code>", 1)
                parts.append(f"<li>{text}</li>")
            parts.append("</ul>")
        elif kind == "table":
            parts.append("<table><tr>" + "".join(f"<th>{html.escape(h)}</th>" for h in slide["header"]) + "</tr>")
            for row in slide["rows"]:
                parts.append("<tr>" + "".join(f"<td>{html.escape(str(c))}</td>" for c in row) + "</tr>")
            parts.append("</table>")
            if slide.get("caption"):
                parts.append(f"<div class='meta'>{html.escape(slide['caption'])}</div>")
        elif kind == "metrics":
            parts.append("<div class='metrics'>")
            for label, value in slide["metrics"]:
                parts.append(f"<div>{html.escape(label)}</div><div class='v'>{html.escape(value)}</div>")
            parts.append("</div>")
        elif kind == "image":
            src = deck["images"].get(slide["image"])
            if src and Path(src).exists():
                parts.append(f"<figure><img src='{img_b64(src)}'>")
                if slide.get("caption"):
                    parts.append(f"<figcaption>{html.escape(slide['caption'])}</figcaption>")
                parts.append("</figure>")
        elif kind == "code":
            parts.append("<pre>" + html.escape("\n".join(slide["code"])) + "</pre>")
        parts.append("</section>")

    parts.append("<section class='slide'><h1>Спасибо! Вопросы?</h1>"
                 f"<div class='sub'>{html.escape(deck['title'])} · {html.escape(deck['subtitle'])}</div>"
                 "<div class='meta'>Репозиторий: README с запуском, архитектурой, данными и лицензиями.<br>"
                 "Демо поднимается одной командой, интернет не требуется.</div></section></body></html>")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(parts), encoding="utf-8")
    return path


def main() -> None:
    import sys

    preview = "--preview" in sys.argv
    preview_dir = OUT / "preview" if preview else None
    pdf = render_pdf(DECK, OUT / "presentation.pdf", preview_dir=preview_dir)
    page = render_html(DECK, OUT / "presentation.html")
    print(f"{DECK['title']}: {pdf} ({pdf.stat().st_size // 1024} КБ), {page} ({page.stat().st_size // 1024} КБ)")


if __name__ == "__main__":
    main()
