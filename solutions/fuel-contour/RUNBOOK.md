# Runbook

## 1. Окружение и быстрый полный запуск

Linux/macOS, Python 3.11 (проверен 3.11), pip, venv. Интернет нужен только для установки открытых
Python-пакетов; данные уже включены в неизменённом снимке. Основной запуск не требует Node/browser.

```bash
cd solutions/fuel-contour
bash tools/setup.sh
bash tools/reproduce.sh
```

Будут созданы `results/{earth,lunar}/plan.json`, BASE/STRESS/result.json и CSV,
sensitivity.json, monte_carlo.json, extension.json, общий summary.json. Затем обновятся документы.
Последний gate завершится ошибкой до исправления upstream missing-link; команда не скрывает exit code.

## 2. Пошаговая проверка CLI

```bash
.venv/bin/python -m fuel.cli init --strategy earth --output results/my-plan.json
# Отредактировать решения в results/my-plan.json, не vendor/*
.venv/bin/python -m fuel.cli run --plan results/my-plan.json --scenario BASE --output results/my-base
.venv/bin/python -m fuel.cli run --plan results/my-plan.json --scenario MANDATORY_STRESS --output results/my-stress
.venv/bin/python -m fuel.cli run --plan results/my-plan.json --scenario BASE --output results/reopened
diff -u results/my-base/result.json results/reopened/result.json
```

`run` возвращает 0 для корректно рассчитанного, но нарушающего ограничения плана: нарушения — часть
результата, не exception. Ошибки формата дают ненулевой exit. API аналогично: 200 с violations или
422 с конкретной причиной. Использование неподдержанного scenario ID — ошибка, не fallback к BASE.

## 3. Web

```bash
.venv/bin/python -m uvicorn fuel.api:app --host 0.0.0.0 --port 8000
```

Порт 8000, `/` — калькулятор, `/demo` — контрольные примеры, `/planner` — полный редактор, `/presentation` — слайды, `/docs` — OpenAPI. Нет вызовов localhost из браузерного JS, нет CDN.
В UI сохранение и открытие выполняются через файл пользователя; сервер не хранит чужие планы.
Пересчёт выполняется синхронно. Monte Carlo ограничен 300 испытаниями в API.

## 4. Независимые gates

```bash
.venv/bin/python tools/verify_vendor.py
.venv/bin/python -m pytest -q
.venv/bin/python vendor/test_oil/tools/validate_reference_repo.py
```

Последняя команда: ожидаемый **неуспех** на `data/README.md → ../docs/ERRATA_AND_PROVENANCE.md`.
Запрещено создавать подставной документ внутри vendor ради зелёного статуса.
CI разделяет собственные tests и upstream-reference. CI на GitHub нельзя считать выполненным
только потому, что локально прошли те же команды.

## 5. Браузерные E2E и PDF (необязательно для расчётов)

Нужен Node 22 и системные NSS/NSPR библиотеки Chromium. Установка вне исходников:

```bash
npm install --prefix /tmp/fuel-browser @sparticuz/chromium@133.0.0 playwright-core@1.51.0
NODE_PATH=/tmp/fuel-browser/node_modules node tools/browser-check.cjs
```

Тест требует запущенный web-сервер, использует `APP_URL` (по умолчанию локальный порт 8000).
Проверяет BASE/STRESS, prepared-stress, изменение заказа/инвестиций/ставки, save/open плана,
research input copy и roundtrip полного проекта, sensitivity/parameters, матрицу 2×2, ZIP, mobile overflow.
Печатает REPORT/COMPARISON/PRESENTATION в `results/*.pdf` и сохраняет скриншоты.
В минимальном Linux без libnss3/libnspr4 можно распаковать пакетный `al2023.tar.br` из
`@sparticuz/chromium/bin` и добавить его каталог `lib` в LD_LIBRARY_PATH; бинарники не коммитить.
Или открыть HTML-документы в обычном браузере → Печать → Сохранить PDF, масштаб 100%.

## 6. Проверка детерминизма

```bash
.venv/bin/python -m fuel.cli suite --output results/repro-a
.venv/bin/python -m fuel.cli suite --output results/repro-b
diff -qr results/repro-a results/repro-b
```

Ожидается пустой diff. У MC seed=2035, число испытаний=100 по умолчанию. Изменение seed/count
обязано отражаться в сохранённых метаданных и не подменять ранее рассчитанные вероятности.

## 7. Порядок обновления источника

Получить исправленный organizer commit → сравнить с зафиксированным → явно пересмотреть rules/data
и provenance → обновить vendor и SHA256-манифест вместе → полный gate → сравнение до/после.
Сейчас никакие файлы организатора не изменены; source tree не содержит готового participant engine.
Полные trace/PNG/PDF от тестов в `results` игнорируются; сдаваемые небольшие PDF могут храниться в docs.

## 8. Подготовленные планы и новые исследования v0.2

```bash
.venv/bin/python -m fuel.cli init --strategy lunar --design-scenario MANDATORY_STRESS --output results/lunar-stress-plan.json
.venv/bin/python -m fuel.cli run --plan results/lunar-stress-plan.json --scenario MANDATORY_STRESS --output results/lunar-prepared
.venv/bin/python tools/package.py
```

В `suite` автоматически создаются четыре плана, матрицы 2×2, changes, parameter sensitivity,
последовательная атрибуция стресса, два варианта зависимости MC и roadmap. Полный список —
[docs/STRESS_PROTOCOL.md](docs/STRESS_PROTOCOL.md). Команда package создаёт `results/fuel-contour-submission.zip` с README в корне,
полными результатами, source/configs/tests/docs и манифестом SHA256; не выполняет upload.

В UI:
- варианты 03/04 — отдельно подготовленные stress планы, а не волшебная починка 01/02;
- «Сравнить решения» показывает все четыре комбинации; экспорт включает comparison и changes;
- реальная ставка и инвестиции редактируются формами, без изменения кода;
- копия входов поддерживает demand/supply_sources и basis, не допускает удаления контрольных
  строк и редактирования limits; BASE восстанавливает контроль, отдельная кнопка — исходный проект;
- сохранить план — portable JSON; сохранить проект — план + scenario + research input patch.
  Открытие поддерживает оба формата и result.json полного экспорта.

PDF стр.7 изменил семантику финансового CSV: initial costs теперь уже включены в 2035.
`pre_horizon.csv` — неаддитивная детализация. Сумма financial_breakdown.total_mln равна summary.total_cost_mln.
При импорте legacy v0.1 плана добавьте явные preparation_availability из актуального примера
и при необходимости opening_order_day / opening_delivery_day; отсутствие истории не подменяется
непроверенным бесплатным stock. Команда init создаёт совместимый v0.2 файл.

`tools/package.py` запускается из Git checkout и читает root workflow; архивировать сам себя
из распакованного ZIP без Git не требуется. В распакованном пакете installation/reproduce/web
работают из корня без CosmoH и без других решений. PDF-печать остаётся отдельным browser-шагом.

## Подготовка защиты и редактируемых слайдов

Основной `tools/report.py` теперь создаёт 10-слайдовую PRESENTATION.html, TALK_4_MIN.txt, SPEAKER_NOTES.md,
SUPPLY_CHAIN.svg и DECISION_BRIEF.json из того же suite; memo остаётся 10 страниц, comparison — 1.
`SCORECARD.md` — субъективная внутренняя самооценка, не выход экономического ядра.

```bash
.venv/bin/python -m pip install -r tools/presentation-requirements.txt
.venv/bin/python tools/defense.py --pptx
```

PPTX редактируется, заметки докладчика пустые. Речь находится только в отдельных TXT/MD. Авторские зависимости не нужны для запуска
планировщика. После пересчёта обновите и PPTX, и PDF: бинарные документы — снимки,
основная воспроизводимая команда обновляет HTML/JSON, а не печатную метаинформацию.
Проверьте PPTX в используемой версии Office; при отличиях переносов выступайте по PDF.
Формат: 4 минуты доклада и 2 минуты вопросов. GitVerse-передача требует действий владельца.

## Витрина и реакция после наблюдения

```bash
NODE_PATH=/tmp/fuel-browser/node_modules node tools/showcase-check.cjs
```

Этот тест проверяет `/demo`, тур, переключение всех 4 сочетаний, год, реакцию с задержкой,
сброс устаревшей выгрузки, JSON/ZIP, mobile и клавиатурную навигацию презентации.
`SHOWCASE_URL` — адрес примеров (по умолчанию http://127.0.0.1:8000/demo).
Старый `browser-check.cjs` по умолчанию ходит на `/planner` и отдельно печатает документы.
Для минимального Linux по-прежнему могут понадобиться библиотеки Chromium, см. раздел 5.

`results/recourse/` содержит полные планы/расчёты при задержках 0/90/180/330 дней и comparison.csv.
В отличие от исходных redesign-планов, здесь новый заказ принят после наблюдения события,
но только для одного свободного Emergency source/year. Старые обязательства, включая будущие,
заморожены. Положительный эффект не объявляется универсальной выполнимостью.

PPTX обновлён нативными фигурами и графиками, без заметок. HTML автономен: SVG и реальный снимок UI
встроены, внешние шрифты/CDN не нужны. Для выступления используйте браузер или PDF; PPTX
сохраняет редактируемость, но переносы в целевой версии Office нужно проверить отдельно.

## Светлая тема и навигация презентации

Сайт не загружает внешние библиотеки или шрифты во время показа. Тема общая для `/` и
`/planner`, светлая по умолчанию; отказ localStorage не ломает приложение. Параметры
`architecture`, `mode`, `year` в адресе `/demo` — только выбор контрольного вида, не сохранение проекта.

HTML-презентация содержит выбор слайда, но не речь или подсказки.
Текст для подготовки находится в `docs/TALK_4_MIN.txt`.
Стрелки/Home/End, полный экран и открытие файла без сети сохраняются.

Дополнительная необязательная проверка UI использует **axe-core 4.10.3** (MPL-2.0),
только в инструментарии тестов, не в приложении:

```bash
npm install --prefix /tmp/fuel-browser axe-core@4.10.3
NODE_PATH=/tmp/fuel-browser/node_modules node tools/usability-check.cjs
```

Сначала установите Chromium/Playwright из раздела 5 и запустите сервер. В минимальном Linux
может понадобиться LD_LIBRARY_PATH. Тест проверяет обе темы, сохранение/блокировку хранилища,
переход в лабораторию, восстановление вида из URL, сброс, таблицу значений, размеры
390/768/1440px, список слайдов, отсутствие подсказок и печать. `results/accessibility.json` содержит
автоматические axe-результаты и непроверенные автоматически пункты. Ноль serious/critical
не является сертификатом полной WCAG-совместимости или заменой проверки скринридером.

## Галерея доказательств и замеры

`/evidence` открывает автономную галерею. Это сохранённый протокол, не потоковая телеметрия.
`docs/JURY_GUIDE.md` — маршрут по всем 20 критериям. `tools/evidence.py` создаёт детерминированные
35 опытов и пример дневного баланса; теперь входит в reproduce/CI. `tools/evidence_publish.py`
связывает результаты с галереей, а генератор презентации включает карту и реальные снимки.

Браузерные времена **не перегенерируются как расчётные константы**: сохраняется честный снимок
сырых наблюдений, окружения и хешей исходников. Перед повторным захватом запустите сервер,
остановите другие тесты/нагрузки, установите Chromium/Playwright из раздела 5 и выполните:

```bash
NODE_PATH=/tmp/fuel-browser/node_modules node tools/demo-evidence.cjs
.venv/bin/python tools/evidence_publish.py
.venv/bin/python tools/defense.py --pptx
```

При изменении измеренного кода генератор остановится с `STALE_BROWSER_MEASUREMENT` —
нужен новый захват, а не отключение проверки. Старые времена не переносить в новую реализацию.
После замера снова печатайте PDF через `tools/browser-check.cjs`. Времена других машин будут отличаться:
нет обещания ускорения, нагрузки или SLA. Не путать тёплое переключение кеша и новый POST-расчёт.


## Калькулятор: собственные входы и проверки

Главная `/`: спрос по годам, множители цен и доля исполнения, запас и ставка,
заказы/резервы и даты, инвестиции. Расчёт выполняется только по кнопке.
После правки результат устаревает, ZIP блокируется до нового расчёта. JSON —
`fuel-calculator-v1`; прежние исследовательские проекты открываются через `/planner`.
Официальные среды не наследуют собственные условия. Начальные планы — заготовки,
не оптимизатор. Сохранение локальное; сервер не является хранилищем проектов.

После установки браузерных зависимостей и запуска API:

```bash
NODE_PATH=/tmp/fuel-browser/node_modules node tools/calculator-check.cjs
NODE_PATH=/tmp/fuel-browser/node_modules node tools/calculator-accessibility.cjs
```

`APP_ORIGIN` переопределяет адрес калькулятора (по умолчанию `http://127.0.0.1:8000`).
E2E проверяет реальные правки, смену года без потери договора, сравнение с ядром,
устаревший ответ/экспорт, JSON roundtrip, ZIP, ошибки, доказательства, mobile и темы.
Axe отдельно проверяет рассчитанный BASE в двух темах; это не полная WCAG-сертификация.
`calculator-check.cjs` обновляет настоящий снимок `docs/assets/calculator.png` для слайда 3.
После него пересоберите `tools/defense.py --pptx`, затем PDF через `browser-check.cjs`.
Перед публикацией скопируйте проверенный `results/PRESENTATION.pdf` в `docs/PRESENTATION.pdf`.
