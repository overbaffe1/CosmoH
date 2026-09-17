"""Сборка презентаций (HTML + PDF) для обоих решений.

Запуск из корня `starter/`:
    python tools/build_slides.py

PDF собирается через matplotlib (PdfPages, шрифт DejaVu с кириллицей),
HTML — самодостаточный файл с встроенными изображениями (base64), открывается
оффлайн в любом браузере и корректно печатается в PDF (Ctrl+P).

Контент описан декларативно: список слайдов с типом (title/bullets/table/image/
two_col/quote), поэтому текст легко править прямо перед защитой.
"""

from __future__ import annotations

import base64
import html
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402
from matplotlib.patches import FancyBboxPatch, Rectangle  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT.parent / "docs" / "presentations"
ACCENT = "#4fc3ff"
ACCENT2 = "#ffb03a"
BG = "#0e1116"
FG = "#e6edf3"
MUTED = "#93a4b8"


# --------------------------------------------------------------------------- fires

FIRES_DECK: dict = {
    "slug": "cosmofire",
    "title": "КосмоФАЙР",
    "subtitle": "Оперативный мониторинг лесных пожаров",
    "kicker": "КосмоХакатон · Красноярск · 18–20 сентября 2026 · кейс «Оперативный мониторинг лесных пожаров»",
    "images": {
        "map": ROOT / "fires-krasnoyarsk" / "data" / "scene_map.png",
        "burn": ROOT / "fires-krasnoyarsk" / "data" / "burnscar.png",
        "quality": ROOT / "fires-krasnoyarsk" / "data" / "quality.png",
    },
    "slides": [
        {"type": "bullets", "title": "Проблема", "bullets": [
            "Лесные пожары в Сибири: десятки тысяч гектаров за сезон; решение о тушении принимается по данным, которые приходят с задержкой.",
            "Низкоорбитальные спутники видят очаг 2–4 раза в сутки: важно не только увидеть, но и **не потерять время на ложные срабатывания**.",
            "Диспетчеру нужен не сырой список точек, а **ранжированный список очагов** с площадью и уверенностью: куда отправлять силы первыми.",
            "Ручной отсев ложных детекций (факелы, ТЭЦ, НПЗ, блики) съедает часы дежурной смены.",
        ]},
        {"type": "table", "title": "Данные и источники", "header": ["Источник", "Что даёт", "Разрешение / задержка", "Лицензия"],
         "rows": [
             ["NASA FIRMS (MODIS)", "тепловые аномалии, яркость, FRP", "1 км · ≈ 3 ч", "NASA public domain"],
             ["NASA FIRMS (VIIRS)", "тепловые аномалии, яркость, FRP", "375 м · ≈ 3 ч", "NASA public domain"],
             ["Sentinel-2 L2A", "NBR до/после, классы тяжести гари", "20 м (SWIR) · до 5 сут", "Copernicus Open Access"],
             ["Справочник промзон", "признак «ложное срабатывание»", "статический слой", "OSM/Росреестр"],
         ]},
        {"type": "bullets", "title": "Решение: пять шагов", "bullets": [
            "**1. Детекции.** MODIS/VIIRS: координаты, время, яркость, FRP, уверенность, день/ночь.",
            "**2. Отсев ложных.** Интерпретируемая логистическая модель на физических признаках: яркость, FRP, плотность и разброс окрестности, близость к известной промзоне.",
            "**3. Очаги.** Собственная DBSCAN-подобная кластеризация по радиусу в километрах: число детекций, суммарный FRP, число спутников, уверенность.",
            "**4. Приоритет.** FRP × уверенность: диспетчер видит, какой очаг важнее прямо сейчас.",
            "**5. Площадь гари.** Sentinel-2, dNBR и пороги USGS: площадь в гектарах по классам тяжести.",
        ]},
        {"type": "code", "title": "Архитектура", "code": [
            "NASA FIRMS ──┐",
            "             ├─▶ providers.py ──▶ filter.py ──▶ cluster.py ──▶ приоритет очагов",
            "Sentinel-2 ──┘        (кэш,          отсев ложных    очаги + уверенность",
            "                    оффлайн-режим)                      │",
            "                                                        ▼",
            "   burnscar.py (dNBR → га) ──▶ service.py (FastAPI + веб-карта) ──▶ дежурный",
            "   metrics.py (F1 / IoU / ошибка га) ──▶ cli.py (report.json + фигуры) ──▶ отчёт",
        ]},
        {"type": "image", "title": "Отсев ложных срабатываний и очаги", "image": "map",
         "caption": "Красное — подтверждённые аномалии, серое — ложные (промзоны), жёлтые окружности — очаги с суммарным FRP. Видно и обратную ошибку: очаг у Саяногорска отброшен как промышленный — осознанный компромисс."},
        {"type": "table", "title": "Модель отсева: признаки и вклады", "header": ["Признак", "Знак вклада", "Физический смысл"],
         "rows": [
             ["Яркость (K) относительно 320 K", "+ 1.05 / 10 K", "у пожара ярче ИК-канал"],
             ["FRP (МВт) относительно 10 МВт", "+ 1.20 / 10 МВт", "мощность горения"],
             ["Число детекций в радиусе 15 км", "+ 0.30 × (√n − 2.4)", "пожар — «куст» подтверждений"],
             ["Разброс яркости окрестности", "+ 0.40 × (σ−8)/5", "у факела яркость стабильнее"],
             ["Ночь", "− 0.45", "ночные артефакты MODIS"],
             ["В радиусе 6 км от промзоны", "− 1.80", "факелы, ТЭЦ, НПЗ"],
         ]},
        {"type": "bullets", "title": "Кластеризация и приоритет", "bullets": [
            "Реализация DBSCAN-подобная, но **на numpy и детерминированная**: сортировка по FRP убирает зависимость результата от порядка строк.",
            "Параметры: радиус 12 км, минимум 2 детекции; радиус задаётся в километрах (haversine), а не в пикселях.",
            "Агрегаты очага: число детекций, суммарный и максимальный FRP, число разных спутников, окно времени, уверенность.",
            "Уверенность = f(число детекций, число спутников): несколько спутников независимо видят одно и то же — сильное подтверждение.",
            "Приоритет = суммарный FRP × (0.5 + уверенность) — простая и объяснимая формула для ранжирования.",
        ]},
        {"type": "image", "title": "Площадь гари по Sentinel-2", "image": "burn",
         "caption": "dNBR = NBR до − после; пороги USGS 0.10 / 0.27 / 0.66; чистка мелких пятен; площадь 226.16 га против 227.52 га эталона (−0.6 %), IoU 0.994 на синтетике (на реальных снимках ожидаем 0.80–0.93)."},
        {"type": "metrics", "title": "Результаты на демо-сцене", "metrics": [
            ("Детекции: precision / recall / F1", "0.978 / 0.900 / 0.938"),
            ("Очаги: precision / recall / F1", "1.000 / 1.000 / 1.000"),
            ("Средняя ошибка локализации очага", "0.18 км"),
            ("Площадь гари", "226.16 га против 227.52 га (−0.6 %)"),
            ("IoU / Dice по контуру гари", "0.994 / 0.997"),
            ("Скорость обработки сцены", "< 1 с (77 детекций, 3 источника данных)"),
        ]},
        {"type": "bullets", "title": "Демонстрация: API и веб-карта", "bullets": [
            "`GET /` — веб-карта без CDN и тайлов: работает на площадке без интернета.",
            "`GET /api/fires` — очаги с приоритетом; `GET /api/detections` — все аномалии с p(пожар).",
            "`GET /api/geojson` — выгрузка в QGIS/Mapbox для регионального штаба.",
            "`GET /api/burnscar` — площадь по классам тяжести; `GET /api/metrics` — качество модели.",
            "`POST /api/analyze` — принять свой список точек и получить разбор решения по каждой.",
            "Тесты: `pytest` — 7 тестов (генерация, фильтр, кластеризация, гарь, API).",
        ]},
        {"type": "bullets", "title": "Ценность и внедрение", "bullets": [
            "**Кому:** региональные диспетчерские службы (Авиалесоохрана), центры управления в кризисных ситуациях, службы лесоохраны.",
            "**Что меняется:** вместо списка из сотен точек — 5–10 ранжированных очагов с площадью и уверенностью; меньше времени на отсев ложных.",
            "**Эффект:** ранние решения о вылете/переброске сил; оценка площади позволяет планировать ресурсы, а не уточнять её постфактум.",
            "**Интеграция:** REST + GeoJSON — встраивается в существующие ГИС и в телеграм-оповещения дежурного.",
            "**Стоимость:** только открытые данные, сервис поднимается на одном контейнере.",
        ]},
        {"type": "bullets", "title": "Ограничения и что дальше", "bullets": [
            "Синтетическая сцена не отражает всю вариативность реальных данных: следующий шаг — прогон на живом срезе FIRMS за 2–3 суток.",
            "Ошибки у промзон: компромисс настраивается через порог и штраф `w_industry`; в будущем — обучение на подтверждениях Авиалесоохраны.",
            "Точность площади зависит от облачности: нужна маска облаков и учёт склона.",
            "Дальше: инкрементальный расчёт по новым детекциям, прогноз распространения огня, интеграция с моделями погоды.",
        ]},
        {"type": "bullets", "title": "Раскрытие (по положению хакатона)", "bullets": [
            "Использованы открытые библиотеки: numpy, pandas, FastAPI, uvicorn, pydantic, tifffile, matplotlib, pytest, httpx.",
            "Данные: NASA FIRMS и Copernicus Sentinel-2 — открытые, лицензии указаны в README; демо-данные синтетические.",
            "Каркас пайплайна подготовлен до старта хакатона; объём работы в окне 18–20.09.2026 фиксируется историей коммитов репозитория сдачи.",
            "Решение воспроизводимо: `python -m cosmofire.cli demo` + `uvicorn cosmofire.service:app` без доступа в интернет.",
        ]},
    ],
}


# --------------------------------------------------------------------------- risk

RISK_DECK: dict = {
    "slug": "cosmorisk",
    "title": "КосмоРиск",
    "subtitle": "Риск внекорабельной деятельности по космической погоде",
    "kicker": "КосмоХакатон · Санкт-Петербург · 18–20 сентября 2026 · кейс «Орбитальный риск»",
    "images": {
        "chart": ROOT / "orbital-risk-spb" / "data" / "risk_chart.png",
    },
    "slides": [
        {"type": "bullets", "title": "Проблема", "bullets": [
            "ВКД — самый опасный режим полёта: космонавт вне защиты станции, дозовые лимиты жёсткие (≈ 1 мЗв на выход по NASA STD-3001).",
            "Основные угрозы: солнечные протонные события (10–100+ pfu), геомагнитные бури (Kp ≥ 5, Dst ≤ −50 нТл), вспышки M/X.",
            "Дежурному нужен ответ на три вопроса: **можно ли выходить сейчас**, **какую дозу получит космонавт**, **когда ближайшее безопасное окно**.",
            "Прогноз и решение живут в разных системах: у NOAA — данные, у ЦУП — расписание выходов. Связки «данные → решение» не хватает.",
        ]},
        {"type": "table", "title": "Данные и пороги", "header": ["Фактор", "Порог", "Почему важен для ВКД"],
         "rows": [
             ["Kp-индекс", "≥ 5 (G1)", "рост потока захваченных частиц на низкой орбите"],
             ["Протоны ≥ 10 МэВ", "≥ 10 pfu", "основная радиационная опасность вне станции"],
             ["Dst-индекс", "≤ −50 нТл", "сильная буря: рост дозы на высокоширотных участках"],
             ["Рентген (0.1–0.8 нм)", "≥ 1e-5 Вт/м² (M)", "вспышка и маркер возможного SPE"],
             ["Доза за ВКД", "≥ 1 мЗв", "лимит на выход (упрощённо)"],
         ],
         "caption": "Источники: NOAA SWPC (Kp, Dst, GOES-протоны, рентген, F10.7), шкалы NOAA G/S/R, NASA STD-3001."},
        {"type": "bullets", "title": "Модель риска: правило доминирующей опасности", "bullets": [
            "Каждый фактор нормируется так, чтобы **пороговое событие давало вклад 0.5**: Kp 5, протоны 10 pfu, Dst −50 нТл, вспышка M.",
            "Композиция — не среднее, а **максимум**: в оперативных правилах ВКД выход отменяется, если хотя бы один критерий «красный».",
            "Пример: спокойный Kp 2 при SPE 250 pfu → индекс 0.75 (опасно), среднее по факторам дало бы ложное «спокойно».",
            "Индекс ≥ 0.45 или доза за 7 ч ≥ 1 мЗв → ВКД запрещена; выдаётся доминирующий фактор-причина.",
            "Классы: низкий / умеренный / повышенный / высокий / критический — для быстрого чтения статуса.",
        ]},
        {"type": "bullets", "title": "Дозовая модель и окна безопасности", "bullets": [
            "Доза = фон + вклад протонов (log-шкала потока) + вклад захваченных частиц (превышение Kp > 4).",
            "Считается за типовую ВКД 7 ч: получаем «сколько мЗв получит космонавт, если выйдет сейчас».",
            "Окна безопасности — непрерывные интервалы, где ВКД разрешена не менее N часов, с максимумом риска и дозы внутри окна.",
            "Для каждого окна указывается класс и запас до лимита — это готовое решение для планирования выхода.",
            "Дополнительно ведётся бюджет дозы (накопление за сутки/месяц) — учитывается история облучения экипажа.",
        ]},
        {"type": "image", "title": "Индекс риска и доза за 7 часов", "image": "chart",
         "caption": "Синяя линия — индекс риска, жёлтая — доза за типовую ВКД, красная штриховая — порог 0.45; красные полосы — часы, когда выход запрещён."},
        {"type": "metrics", "title": "Результаты на демо-ряду (168 ч)", "metrics": [
            ("precision / recall / F1 (опасные часы)", "1.000 / 0.944 / 0.971"),
            ("CSI (критический индекс успеха)", "0.944"),
            ("Заблаговременность предупреждения", "31 ч"),
            ("Опасных часов", "51 из 168"),
            ("Доза за первые сутки (запас)", "1.29 мЗв при лимите 10 мЗв"),
            ("Время отклика API", "< 0.3 с на 168 точек"),
        ]},
        {"type": "bullets", "title": "Демонстрация: API и дашборд", "bullets": [
            "`GET /` — дашборд: статус «сейчас», ведущие факторы, график риска, окна, метрики.",
            "`GET /api/recommend` — оперативная рекомендация: можно ли выходить и три ближайших окна.",
            "`GET /api/windows` — список безопасных окон; `GET /api/risk` — почасовой риск и доза.",
            "`POST /api/assess` — загрузить свой ряд (или прогноз модели) и получить решение.",
            "Данные подтягиваются из NOAA SWPC с дисковым кэшем: работает и при нестабильной сети.",
            "Тесты: `pytest` — 8 тестов (ряд, реакция на бурю, окна, дозовые лимиты, API).",
        ]},
        {"type": "bullets", "title": "Ценность и внедрение", "bullets": [
            "**Кому:** ЦУП и медицинская служба экипажа, планировщики ВКД, службы радиационной безопасности.",
            "**Что меняется:** решение о выходе опирается на единый индекс и дозовую оценку, а не на чтение графиков NOAA вручную.",
            "**Эффект:** меньше «отмен по факту», окна ВКД планируются заранее с запасом по дозе; риск экипажа снижается.",
            "**Интеграция:** REST API + веб-дашборд; подключается к расписанию витков и к системам ЦУП.",
            "**Данные бесплатны:** NOAA SWPC — public domain, ключи не нужны.",
        ]},
        {"type": "bullets", "title": "Ограничения и что дальше", "bullets": [
            "Демо-ряд синтетический и гладкий: на живых данных метрики будут ниже, часть SPE приходит без предвестников.",
            "Дозовая модель — инженерная оценка сверху; корректный путь — расчёт по спектру (AP-8/AE-8, SPENVIS) с моделью защиты скафандра.",
            "Дальше: прогноз на 2–3 суток (persistence + авторегрессия по Dst/Kp), связка с витками по TLE (Celestrak).",
            "Дальше: учёт накопленной дозы экипажа за месяц/год и уведомления при смене статуса.",
        ]},
        {"type": "bullets", "title": "Раскрытие (по положению хакатона)", "bullets": [
            "Использованы открытые библиотеки: numpy, pandas, FastAPI, uvicorn, pydantic, matplotlib, pytest, httpx.",
            "Пороги и физика — из открытых источников NOAA/NASA (SWPC, шкалы G/S/R, NASA STD-3001).",
            "Каркас пайплайна подготовлен до старта хакатона; объём работы в окне 18–20.09.2026 фиксируется историей коммитов репозитория сдачи.",
            "Воспроизводимость: `python -m cosmorisk.cli demo` + `uvicorn cosmorisk.service:app` без интернета.",
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
                widths = slide.get("widths") or [3, 3, 5, 3] if "Лицензия" in slide["header"] else slide.get("widths") or [3, 3, 6]
                weights = widths[: len(slide["header"])]
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
    for deck in (FIRES_DECK, RISK_DECK):
        preview_dir = OUT / "preview" / deck["slug"] if preview else None
        pdf = render_pdf(deck, OUT / f"{deck['slug']}_slides.pdf", preview_dir=preview_dir)
        page = render_html(deck, OUT / f"{deck['slug']}_slides.html")
        print(f"{deck['title']}: {pdf} ({pdf.stat().st_size // 1024} КБ), {page} ({page.stat().st_size // 1024} КБ)")


if __name__ == "__main__":
    main()
