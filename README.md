# CosmoH — КосмоХакатон 2026 (Красноярск + Санкт-Петербург, онлайн)

Репозиторий подготовки и сдачи двух окружных хакатонов КосмоХакатона (18–20.09.2026).
Внутри — разбор кейсов и регламента, технические заготовки двух решений, презентации и плейбук защиты.

## Что где лежит

| Путь | Что это |
|---|---|
| [`docs/kosmohack-2026/brief.md`](docs/kosmohack-2026/brief.md) | разбор Положения и чатов: кейсы, призы, расписание, риски, рекомендация по выбору |
| [`docs/kosmohack-2026/playbook.md`](docs/kosmohack-2026/playbook.md) | план по часам на 18–20.09, роли, сценарий защиты, ответы на вопросы жюри, чек-лист сдачи |
| [`docs/kosmohack-2026/regulation.txt`](docs/kosmohack-2026/regulation.txt) | текстовая выгрузка Положения (для поиска по пунктам) |
| [`docs/kosmohack-2026/chats/`](docs/kosmohack-2026/chats) | выгрузки Telegram-чатов Красноярска, СПб и Благовещенска |
| [`docs/presentations/`](docs/presentations) | презентации обоих решений: PDF и самодостаточный HTML (13 слайдов, кириллица, оффлайн) |
| [`starter/fires-krasnoyarsk/`](starter/fires-krasnoyarsk) | **КосмоФАЙР** — мониторинг лесных пожаров: детекции → отсев ложных → очаги → площадь гари → API и веб-карта |
| [`starter/orbital-risk-spb/`](starter/orbital-risk-spb) | **КосмоРиск** — риск ВКД по космической погоде: индекс риска, доза, окна безопасности, дашборд и API |
| [`starter/tools/build_slides.py`](starter/tools/build_slides.py) | генератор презентаций из декларативного описания слайдов |

## Быстрый старт

```bash
# Пожары (Красноярск)
cd starter/fires-krasnoyarsk
pip install -r requirements.txt
python -m pytest tests -q                 # 7 тестов
python -m cosmofire.cli demo --out data   # отчёт, CSV, фигуры, растр гари
uvicorn cosmofire.service:app --host 0.0.0.0 --port 8000
# → http://localhost:8000  (веб-карта, API, метрики)

# Орбитальный риск (СПб)
cd ../orbital-risk-spb
pip install -r requirements.txt
python -m pytest tests -q                 # 8 тестов
python -m cosmorisk.cli demo --out data   # ряд, окна, отчёт, график
uvicorn cosmorisk.service:app --host 0.0.0.0 --port 8001
# → http://localhost:8001  (дашборд, API, окна ВКД)
```

Интернет для демо не нужен: данные генерируются синтетически, но провайдеры реальных
источников (NASA FIRMS, Copernicus Sentinel-2, NOAA SWPC) подключены и работают с кэшем.

## Презентации

```bash
cd starter && python tools/build_slides.py            # PDF + HTML в docs/presentations/
cd starter && python tools/build_slides.py --preview  # + PNG каждого слайда
```

## Важно про правила хакатона

Положение (пп. 9.5, 9.6, 11.1) разрешает использовать свои ранее созданные компоненты и открытые
библиотеки, но требует раскрывать источники и не выдавать заранее созданное за результат команды.
Поэтому в каждом README есть раздел **Disclosure**, а в плейбуке описана схема: репозитории сдачи
создаются 18.09, первым коммитом идёт каркас с явным указанием, что сделано до старта, а вся
содержательная работа коммитится в окне хакатона.
