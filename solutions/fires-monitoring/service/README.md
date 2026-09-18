# Сервис «КосмоФАЙР-2»

Информационно-аналитический сервис по требованиям критериев раздела 4 постановки: приём пространственно-временного
запроса, карта термоточек, векторные контуры гари с атрибутами, аналитическая справка по площадям и выгрузки.

## Запуск

```bash
# 1) собрать каталог сцен из подготовленного набора (train или test без эталона)
python -m service.catalog --data-dir /path/to/data --out service/catalog.json \
       --weights weights/weights.json

# 2) поднять сервис
CATALOG_PATH=service/catalog.json uvicorn service.app:app --host 0.0.0.0 --port 8000
# документация API: http://localhost:8000/docs
```

## Методы

| Метод | Параметры | Что возвращает |
|---|---|---|
| `GET /` | — | веб-карта (canvas, без CDN и тайлов) + справка |
| `GET /api/health` | — | состояние каталога, число точек и контуров |
| `GET /api/thermopoints` | `bbox`, `date_from`, `date_to`, `format=geojson\|json` | термоточки за период |
| `GET /api/burn-contours` | `bbox`, `date_from`, `date_to`, `severity=1,2,3` | контуры гари (GeoJSON) с id, классом, площадью |
| `GET /api/report` | `bbox`, `date_from`, `date_to`, `severity`, `format=json\|csv` | справка: га всего и по степеням |
| `POST /api/query` | JSON `{bbox | polygon, date_from, date_to, severity}` | точки + контуры + справка одним вызовом |
| `GET /api/export/contours.geojson` | `bbox`, `date_from`, `date_to` | файл GeoJSON |
| `GET /api/export/contours.shp` | то же | zip c .shp/.shx/.dbf/.prj (pyshp, без GDAL) |
| `GET /api/catalog/reload` | — | перечитать каталог без перезапуска |

Примеры:

```bash
curl 'http://localhost:8000/api/report?bbox=90,51,92,53&date_from=2024-08-01&date_to=2024-09-30'
curl -X POST http://localhost:8000/api/query -H 'Content-Type: application/json' \
     -d '{"polygon": [[90,51],[92,51],[92,53],[90,53],[90,51]], "severity": [2,3]}'
curl -OJ 'http://localhost:8000/api/export/contours.shp'
```

## Геопривязка

Тестовая часть кейса поставляется без координат, поэтому каталог умеет два режима:

* **geo** — если в наборе есть `chips_geo.csv` (`chip_id,origin_lon,origin_lat,gsd,date,kind`), контуры и точки
  переводятся в WGS84 с учётом размера пикселя;
* **demo** — если привязка скрыта, чипы раскладываются на регулярную сетку в демонстрационном регионе;
  режим явно возвращается в `GET /api/report` (`catalog_mode`) и подписан в веб-карте.

Ответ `submission.csv` от режима каталога не зависит: он считается по маскам чипов.

## Площади

Площадь считается по числу пикселей маски и размеру пикселя (для BS — 20 м, 400 м² на пиксель), поэтому числа в
справке воспроизводимы по выданным данным, как требует критерий. Для произвольных полигонов есть расчёт по формуле
Гаусса с поправкой на широту (`fires/vectorize.py:polygon_area_ha`).
