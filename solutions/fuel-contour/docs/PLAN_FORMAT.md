# Portable envelope + предметный контракт команды

Верхний уровень строго совместим с `vendor/test_oil/schemas/plan.schema.json`.
Организатор не специфицирует внутренние свойства item объектов; ниже — явный контракт нашей реализации.
Любые неподдержанные решения нельзя считать автоматически смоделированными.

- `plan_id`: идентификатор решения, `scenario_id`: сохранённый исходный сценарий.
  CLI/API выбирает окружение отдельно, не меняя план; фактически применённое окружение — `result.scenario_id`.
- `status: TEAM_DECISION`, `assumptions`: объект TEAM_ASSUMPTION, `timing` фиксирует поддержанную конвенцию.
- `supply_orders[]`: `source_id`, `year`, `ordered_volume_t`, `start_day`, `end_day`, `order_day`.
  Одна строка на источник/год. Окно inclusive, сутки 1..365. Внутри окна поставки равномерны.
  `order_day` — абсолютные учебные сутки от начала первого года; отрицательные даты разрешены для
  своевременных предгоризонтных заказов.
- `capacity_reservations[]`: `source_id`, `year`, `reserved_capacity_t`, `start_day`, `end_day`.
  Объём в поле reserved имеет смысл годовой мощности, доступный контрактный объём равен
  `reserved × (end_day-start_day+1)/365`. Contract window должен покрывать окно поставок.
- `investments[]`: `investment_id`, `decision_day`, `commission_day`.
  Поддержаны организаторские EARTH_NEW/LUNAR_ISRU/ZBO. Опцион и exercise оплачиваются вместе
  в decision_day (явное ограничение выбранного контрактного дизайна). CAPEX берётся из CASE_INPUT.
  Дубликаты инвестиций запрещены. Неверный срок ввода — constraint violation, мощность не включается.
- `inventory_policy`: `opening_stock_t`, `opening_source_id` действующего канала, `allocation: critical_first`.
  Физический резерв проверяется на начало года. Contractual Emergency equivalence не заявляется.

Примеры: `configs/earth.json`, `configs/lunar.json`. Генератор — `fuel.planning.make_plan`.
Сохранённые планы не содержат рассчитанные поставки: это выход ядра, не decision.

## Сценарий

Организаторские BASE/STRESS загружаются только из фиксированных YAML. API запрещает выдавать
произвольный research JSON за CASE_INPUT. `TEAM_*` + `status: TEAM_ASSUMPTION` разрешает:

```json
{
  "scenario_id": "TEAM_GEO_CUSTOM",
  "status": "TEAM_ASSUMPTION",
  "variable_price_multiplier": {"Earth-Core": {"2039": 1.5}},
  "notes": ["Иллюстративный ценовой шок; вероятность не задаётся"]
}
```

`demand_multiplier` и `critical_demand_multiplier` индексируются годом/default,
`actual_delivery_share` и `variable_price_multiplier` — точным именем канала, затем годом.
Без отдельного critical multiplier доля critical сохраняется. Delivery share ограничен [0;1].
Сценарий сохраняется в `provenance.scenario_definition`; входы/план не мутируют.

## Выход

`export.schema.json` организатора + дополнительные `summary`, `pre_horizon`, `provenance`.
`constraint_checks` включает прошедшие и нарушенные ограничения с правилом, периодом, фактом,
порогом, оператором, единицей и источником. Отсутствующий ввод мощности кодируется null с reason,
не невалидным JSON Infinity. Численная tolerance проверок — 1e-8.

`source_schedule` различает заказ, предложенную после ограничений/сценария поставку, принятую поставку
и отклонённый по хранилищу объём. Цена оплачивается по ordered/TOP, не по принятому объёму.
В финансовый итог входят horizon costs плюс отдельный pre_horizon. CSV `pre_horizon.csv` и
`summary.csv` позволяют восстановить полную сумму без потери первоначального финансирования.
Вложенные объекты CSV сериализованы JSON, а не Python repr. Каждая строка несёт plan/scenario/units.
