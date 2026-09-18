# Что запустить на своём железе (runbook)

Короткая версия: на любой машине с Python 3.11 решение работает из коробки. Тестовая часть (269 чипов:
180 AF + 89 BS) считается **≈10–12 с на 6-ядерной машине** и **≈35 с на двух ядрах** при лимите 30 с на прогон —
поэтому на слабой машине либо ставьте пул по числу ядер, либо переключайте режим BS на пороги (тогда ≈7 с):
в `weights/weights.json` замените `"bs_mode": "model"` на `"bs_mode": "thresholds"`. Цена переключения — 0.029
Score на отложенной части.

Ниже — полный порядок действий: от установки до проверки сабмита.

---

## 0. Что нужно

| Ресурс | Минимум | Комментарий |
|---|---|---|
| Python | 3.11 | проверено на 3.11, работает и на 3.10 |
| Ядра CPU | 2 | `inference.py` сам поднимает пул `min(4, ядра)` процессов |
| ОЗУ | 4 ГБ | один чип BS (512×512×13) занимает десятки МБ |
| Диск | ≈6 ГБ | 2.2 ГБ train + 2.2 ГБ распаковка + ≈1 ГБ тест |
| Утилиты | `git`, `unrar`, `tar` | `unrar` нужен только для распаковки архивов (собирается скриптом) |

```bash
cd solutions/fires-monitoring
pip install -r requirements.txt        # numpy, scipy, scikit-learn, tifffile, fastapi, uvicorn, pyshp, matplotlib, pytest
python -m pytest tests -q              # 53 теста, ≈12 с — проверка, что окружение живое
```

## 1. Данные

**Тестовая часть** (`fire-test-renamed.tar` ≈ 878 МБ) — то, что открывается на платформе. Внутри архива
каталог `test/` с `af/`, `bs/`, `meta.csv` и `sample_submission.csv`; масок и геопривязки нет.

Куда положить: **в любое место вне репозитория** — `--data-dir` указывает ровно на каталог, внутри которого
лежат `af/`, `bs/`, `meta.csv`, `sample_submission.csv` (то есть на `test/` из архива, а не на его родителя):

```bash
# 1) привести архив к рабочей раскладке (распаковка + снятие лишнего уровня + проверка)
bash tools/prepare_test.sh ~/Downloads/fire-test-renamed.tar ~/firesdata/test

# 2) и сразу ответ
cd solutions/fires-monitoring
python -m fires.chips --data-dir ~/firesdata/test                 # диагностика раскладки
python inference.py --data-dir ~/firesdata/test --output submission.csv --validate
```

Ожидаемая раскладка после распаковки (если делаете руками — `tar xf fire-test-renamed.tar -C ~/firesdata`
даёт `~/firesdata/test/...`):

```text
~/firesdata/test/            ← это и есть --data-dir
├── af/  (viirs/, aux/, images/)          AF-чипы без масок
├── bs/  (sentinel2_pre/post, sentinel1_pre/post, aux, pre, post, sar_pre, sar_post)
├── meta.csv
└── sample_submission.csv    ← 447 строк: по одной на AF-чип (class_id=1) и по три на BS-чип (1/2/3)
```

Проверки, которые стоит сделать глазами: в `sample_submission.csv` **447 строк** без заголовка (180 AF +
3 × 89 BS), каталогов `masks/` нет — `--validate` всё это проверит сам, но полезно знать ожидаемые числа.

**Репетиция до/вместо теста** — макет теста из обучающей части (чипы без масок + шаблон организаторов):

```bash
python tools/make_mock_test.py --data-dir /tmp/firesdata/real/train --out ~/firesdata/mock/test --n-af 4 --n-bs 2
python inference.py --data-dir ~/firesdata/mock/test --output /tmp/mock_submission.csv --validate   # должно быть ok: true
```

**Обучающая часть** — если её нет под рукой, скрипт заберёт те же архивы из репозитория команды:

```bash
bash tools/fetch_data.sh               # → /tmp/firesdata/real/train (AF 420 + BS 224)
DEST=/data/fires bash tools/fetch_data.sh    # или в свой каталог
```

Проверка, что раскладка распознана (печатает каналы, маски и число чипов):

```bash
python -m fires.chips --data-dir /tmp/firesdata/real/train     # ОЖИДАЕМ n_meta=644, n_chips=644
```

## 2. Обучение (нужно один раз; ≈30–60 мин, на 2 ядрах дольше)

```bash
python train.py --data-dir /tmp/firesdata/real/train --out weights/weights.json
```

`train.py` делит набор по событиям пожара (`fire_event_id`) и проходит четыре стадии:

1. **AF** — 108 конфигураций порогов плюс обученный классификатор очагов (отсев факелов и блика);
2. **BS** — 64 тройки порогов dNBR по группам покрова, затем восстановление гари под облаком по
   Sentinel-1 и выбор сглаживания dNBR (по двум фолдам);
3. **модель степени поражения** — градиентный бустинг на 23 признаках пикселя (dNBR, rdNBR,
   NDVI/NDMI, каналы, покров, рельеф, VV/VH и контекст); обучается на подвыборке пикселей
   (4 000 на чип, ≈670 тыс. строк) и **принимается только если обыгрывает пороги** на отложенных
   чипах, иначе решение остаётся пороговым;
4. **морфология режима модели** — чистка мелких контуров и заполнение дыр подбираются отдельно
   (модель различает дыры внутри гари, поэтому их не заполняют).

На выходе: `weights/weights.json` (пороги + `bs_mode`) и `weights/severity_model.pkl` (модель
степени поражения). Веса уже лежат в репозитории — этот шаг нужен, если данных стало больше,
другой регион или хочется повторить подбор у себя. Обучение детерминировано: тот же датасет и
`--seed` дают те же числа (сид по умолчанию 20260918).

## 3. Оценка и абляции (≈1 мин + ≈7 мин)

```bash
python evaluate.py --data-dir /tmp/firesdata/real/train                    # метрика соревнования
python evaluate.py --data-dir /tmp/firesdata/real/train --ablation > /tmp/ablation.log
python tools/collect_numbers.py --data-dir /tmp/firesdata/real/train --out docs/numbers.json
python tools/update_report.py          # числа из numbers.json → docs/report.md и README.md
```

## 4. Ответ для организаторов (главная команда)

```bash
python inference.py --data-dir ~/firesdata/test --output submission.csv --validate
```

**На платформу грузится именно `<data-dir>/submission.csv`** — не `sample_submission.csv` (в нём одни пустые
строки, это шаблон организаторов: платформа примет его и поставит почти нулевой Score).

* `--validate` сверяет результат с `sample_submission.csv` (если он найден рядом) и проверяет формат;
* печатает время, число чипов и строк;
* детерминирован: повторный запуск даёт побайтово одинаковый файл.

Проверка файла ответа без эталона (формат, полнота, RLE, правдоподобие относительно обучающей части):

```bash
python tools/check_submission.py --data-dir ~/firesdata/test --submission submission.csv
```

Итоговый Score на тесте локально посчитать нельзя — нужны скрытые маски организаторов, оценку даёт платформа
после загрузки файла. `check_submission.py` ловит грубые сбои (пустой ответ, «горит половина чипа», пропущенные
пары, битый RLE) и сравнивает статистику с прогоном на обучающей части.

Проверки перед загрузкой (то же делает `--validate`):

1. шапка ровно `chip_id,class_id,rle`, разделитель — запятая;
2. `rle` — серии отсчётов с 1, без пересечений и пропусков внутри строки;
3. все `chip_id` из шаблона присутствуют (AF — `class_id` 0/1, BS — 0–3);
4. время прогона < 30 с на полный тест.

## 5. Артефакты для защиты (по желанию, ≈2 мин)

```bash
python tools/make_figures.py --data-dir /tmp/firesdata/real/train --numbers docs/numbers.json --catalog service/catalog.json
python tools/build_slides.py                 # docs/presentation.html + docs/presentation.pdf
python -m service.catalog --data-dir /tmp/firesdata/real/train --out service/catalog.json --min-contour-ha 1.0
uvicorn service.app:app --host 0.0.0.0 --port 8100      # веб-карта на http://localhost:8100
```

## 6. Если времени в обрез (минимальный путь к сабмиту)

```bash
pip install -r requirements.txt
unrar x -o+ -ep test.rar ./test_data
python inference.py --data-dir ./test_data --output submission.csv --validate
```

Всё остальное (обучение, отчёт, презентация, сервис) уже посчитано и лежит в репозитории.

## 7. Windows (cmd.exe) — те же шаги, без bash

Команды — одной строкой в `cmd.exe` (не в Git Bash: `cd /d`, `\` в путях). Python вызывается как `py -3`.
`<путь>` ниже — папка, внутри которой лежат `af\` и `bs\` (в каждой свой `meta.csv`); найти её можно так:

```bat
dir /s /b %USERPROFILE%\Documents\*meta.csv
```

```bat
cd /d %USERPROFILE%\Documents\cosmo1\solutions\fires-monitoring
py -3 -m pip install -r requirements.txt
py -3 -m pytest tests -q

rem обучение (≈40–70 мин на i5-11400F; обучающая часть: 420 AF + 224 BS чипа)
py -3 train.py --data-dir <путь>\train --out weights\weights.json

rem проверка на обучающей части (метрика соревнования и вклад механизмов)
py -3 evaluate.py --data-dir <путь>\train
py -3 evaluate.py --data-dir <путь>\train --ablation > ablation.txt

rem ответ организаторам
py -3 inference.py --data-dir <путь>\test --output submission.csv --validate
py -3 tools\check_submission.py --data-dir <путь>\test --submission submission.csv
```

Грузить на платформу — файл `submission.csv` из папки `solutions\fires-monitoring`
(в шаблоне организаторов `sample_submission.csv` все строки пустые, его грузить нельзя).

## 8. Что держать в голове по метрике (из Q&A с организаторами)

* **Очаги (AF) и контуры гари — то, что оценивается**; точность верификации точки возгорания — нет.
  Поэтому основной вес в работе — на AF и BS, а не на «объяснении» факелов.
* **Разметка степени поражения сделана по порогам dNBR** (экспертная проверка — выборочная), то есть
  пороговый подход — не упрощение, а ровно то, как построен эталон.
* **Полигон теста тот же** (Нижнее Поволжье и Подонье), климатические зоны не смещаются: пороги,
  подобранные на train, переносятся.
* **Пиксели под облаками оцениваются «как есть»**. Маскировка по SCL у нас подтверждена на эталоне
  организаторов (+0.02 IoU_burn, +0.015 Score): под облаком наблюдения недостоверны, и предсказание там не
  улучшает, а портит метрику.
* В тесте есть приватная часть; состав не раскрывается, поэтому никаких «подгонок под лидерборд»:
  все параметры подобраны только на train-части.
* Разрешено считать локально или в облаке (Colab, Yandex Cloud) — решение не требует GPU и работает
  на CPU, что и есть самый быстрый вариант развёртывания «здесь и сейчас».
