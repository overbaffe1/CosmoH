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

Порт 8000, `/` — UI, `/docs` — OpenAPI. Нет вызовов localhost из браузерного JS, нет CDN.
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
