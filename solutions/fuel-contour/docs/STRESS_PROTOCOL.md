# Протокол экспериментов v0.2

Все расчёты выполняет `fuel.engine.evaluate`; seed задан, входы не мутируют.
Единицы: т, млн постоянных у.е. 2035, модельные сутки. Физика шагом в сутки, договоры годовые.

| Опыт | Что меняем | Что сохраняем | Проверяемый результат |
|---|---|---|---|
| BASE | Ничего относительно CASE_INPUT | План | Годовые checks, cost, SL, daily balance |
| MANDATORY_STRESS | Только official YAML: demand/critical, Core/Flex price, Lunar shares, ceiling | Тот же план, даты, CAPEX | Разность со своим BASE; не с другим планом |
| 2×2 redesign | Отдельный заранее сформированный план | Одна CASE_INPUT, одна ставка, обе среды | Old BASE / old stress / new BASE / new stress; все изменённые заказы и даты |
| Атрибуция | По очереди demand → price → delivery → loss check | Тот же план | Телескопическая сумма дельт совпадает с joint stress; взаимодействия приписаны более позднему шагу, порядок существенен |
| Low/high | Organizer demand vectors, critical proportion retained | Заказы / storage / investments | Shortage и overflow, не только cost |
| Demand sweep | TEAM uniform factor 0.8..1.25 | Остальные параметры | Service-only threshold [1,2], все violations отдельно |
| Price sweep | Core 1 / 1.25 / 1.5 | Заказы | Расходы/stock/SL; 1.25 мотивирован mandatory shock, 1.5 — исследовательский endpoint |
| Timing | Lower/upper organizer ranges; ZBO delay 0/90/365 дней | Плановые даты решений | Реальная поставка/режим хранения и нарушения, не правка official lead time |
| Emergency semantics | Any scheduled use vs ≥50% of annual ordered volume | Все физические потоки | Только интерпретация ограничения меняется; обе помечены допущениями |
| Real rate | 0 / 0.05 / 0.10 | Физические решения | PV по формуле, исходный nominal cost неизменен; ставки не смешиваются в сравнении |
| Price crossover | Lunar price multiplier [1,3] | Две baseline стратегии, BASE demand | Бисекция границы смены cost ranking либо явный unbracketed status |
| Own risks | Lunar outage / Core delivery half / Core price ×1.5, указанный год | BASE-план | Событие → параметр → cost/shortage/service, owner и residual |
| Risk measure | Предстартовый запас +20 т либо prior price diversification | Control limits, lead times | BASE-премия меры отдельно от net cost эффекта в событии; residual и stakeholder deltas, исходный план сохранён |
| MC | Bernoulli whole-year availability from reliability | План, seed 2035, N=100 | Conditional Wilson interval, mean/P95 shortage; не вероятность реальной миссии |
| MC dependence | Independent draws vs общий годовой uniform draw | Marginal source reliabilities | Чувствительность к зависимости, не статистическая калибровка |
| Extension | Source-X copy of B + 2041 copy of 2040 | Original dated CAPEX limits | Explicit demand/price/availability/reliability/constraints assumptions |

## Правила сравнения

Критерии BASE: critical SL ≥0.99, total SL ≥0.97 по каждому году. В стрессах — те же
ориентиры плюс все применимые физические/контрактные проверки. Успешным prepared-stress
планом называем только план с нулём нарушенных checks, а не с хорошим средним сервисом.
Поиск service threshold не является поиском всех границ исполнимости: overflow при низком
спросе и reserve на начало года проверяются самостоятельно.

Готовые stress планы учитывают, что сценарии известны заранее. Они не представляются
действием после 2038: дополнительные заказы Core/New нужно сделать за год/два до поставок.
Если эти моменты уже прошли, оператор не может отменить оплаченные обязательства сравнением
планов. В этом случае нужен отдельный recourse experiment, которого текущая версия не обещает.

## Воспроизведение

`python -m fuel.cli suite --output results` создаёт summary, полные планы и все перечисленные
эксперименты; для ручного сравнения `results/{earth,lunar}/decision_comparison.json` и CSV.
`pytest tests/test_pdf_requirements.py` проверяет новую семантику, атрибуцию и prepared-stress feasibility.
Два suite-прогона должны иметь побайтово одинаковые JSON/CSV; различия wall-clock времени
или PDF metadata не являются частью расчётного результата.

Риск без заказанной экспозиции на соответствующий источник/год отмечается screened out: мера
не закупается, её стоимость равна нулю. У MC начало работы C/D определяется датой ввода;
для позднего ввода D надёжность первого года ограничена начальным коэффициентом исходного
профиля (0.78 в контроле), а не повышается до календарного коэффициента следующего года.
Невалидные вероятности вне [0;1] и нечисловые значения отвергаются. Остальные календарные
коэффициенты — исходная метаинформация, не доказанная калибровка распределения.
