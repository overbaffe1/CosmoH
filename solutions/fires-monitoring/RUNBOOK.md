# Что запустить на своём железе (runbook)

Короткая версия: на любой машине с Python 3.11 и двумя ядрами решение работает из коробки —
`inference.py` на наборе организаторов занимает **≈25–45 с** при лимите 30 с на один запуск
(лимит трактуется на прогон, а не на набор; запас заложен параллельным пулом процессов).

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
python -m pytest tests -q              # 40 тестов, ≈10 с — проверка, что окружение живое
```

## 1. Данные

**Тестовая часть** — то, что открывается на платформе: скачать архив и распаковать
(`unrar x -o+ -ep <файл> <куда>`), раскладка та же, что в train, но без масок и без геопривязки.

**Обучающая часть** — если её нет под рукой, скрипт заберёт те же архивы из репозитория команды:

```bash
bash tools/fetch_data.sh               # → /tmp/firesdata/real/train (AF 420 + BS 224)
DEST=/data/fires bash tools/fetch_data.sh    # или в свой каталог
```

Проверка, что раскладка распознана (печатает каналы, маски и число чипов):

```bash
python -m fires.chips --data-dir /tmp/firesdata/real/train     # ОЖИДАЕМ n_meta=644, n_chips=644
```

## 2. Обучение (нужно один раз; ≈25 мин на 2 ядрах)

```bash
python train.py --data-dir /tmp/firesdata/real/train --out weights/weights.json
```

`train.py` делит набор по событиям пожара (`fire_event_id`), перебирает AF 108 конфигураций +
классификатор очагов и BS 64 тройки порогов + варианты Sentinel-1, и пишет в `weights.json`
победителя по валидации. Веса уже лежат в репозитории — этот шаг нужен, только если данных стало
больше или другой регион.

## 3. Оценка и абляции (≈1 мин + ≈7 мин)

```bash
python evaluate.py --data-dir /tmp/firesdata/real/train                    # метрика соревнования
python evaluate.py --data-dir /tmp/firesdata/real/train --ablation > /tmp/ablation.log
python tools/collect_numbers.py --data-dir /tmp/firesdata/real/train --out docs/numbers.json
python tools/update_report.py          # числа из numbers.json → docs/report.md и README.md
```

## 4. Ответ для организаторов (главная команда)

```bash
python inference.py --data-dir <тест> --output submission.csv --validate
```

* `--validate` сверяет результат с `sample_submission.csv` (если он найден рядом) и проверяет формат;
* печатает время, число чипов и строк;
* детерминирован: повторный запуск даёт побайтово одинаковый файл.

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

## 7. Что держать в голове по метрике (из Q&A с организаторами)

* **Очаги (AF) и контуры гари — то, что оценивается**; точность верификации точки возгорания — нет.
  Поэтому основной вес в работе — на AF и BS, а не на «объяснении» факелов.
* **Разметка степени поражения сделана по порогам dNBR** (экспертная проверка — выборочная), то есть
  пороговый подход — не упрощение, а ровно то, как построен эталон.
* **Полигон теста тот же** (Нижнее Поволжье и Подонье), климатические зоны не смещаются: пороги,
  подобранные на train, переносятся.
* **Пиксели под облаками оцениваются «как есть»**. Маскировка по SCL у нас подтверждена на эталоне
  организаторов (+0.018 IoU_burn): под облаком наблюдения недостоверны, и предсказание там не
  улучшает, а портит метрику.
* В тесте есть приватная часть; состав не раскрывается, поэтому никаких «подгонок под лидерборд»:
  все параметры подобраны только на train-части.
* Разрешено считать локально или в облаке (Colab, Yandex Cloud) — решение не требует GPU и работает
  на CPU, что и есть самый быстрый вариант развёртывания «здесь и сейчас».
