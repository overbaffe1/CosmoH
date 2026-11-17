# Сверка PDF и карта закрытия требований — 2026-09-19

Прочитаны все три файла публичного `overbaffe1/orbit/main`, включая графическую таблицу стресса
на стр. 10 (она не извлекается текстовым PDF-парсером). Неизменённые оригиналы —
`references/orbit/`, tree SHA и SHA256 каждого файла — `references/orbit/manifest.json`.
Версия `test_oil` остаётся `cec6de1950276091689e71a67f9a875fb4ca6213`: upstream не обновился.

## Что действительно изменилось после чтения

| Источник | Требование | Было | Исправление / проверка |
|---|---|---|---|
| Постановка, стр. 7 | Подготовительный период разрешён, расходы относятся к первому финансовому году | Предстартовые расходы только в общей сумме | `engine.evaluate`: 2035 включает закупку, reservation, holding подготовки; pre_horizon — неаддитивная детализация; test_preparation_cost_recognized_in_first_year_only |
| Стр. 7 | Проверять availability и lead time предстартового контракта | Даты лишь вычислялись для справки | Явные даты в решении, история доступности в TEAM_ASSUMPTION; PREPARATION_* checks, невалидная подготовка не создаёт запас |
| Стр. 7 | ISRU short delivery не создаёт refund | Считалось открытым вопросом | Правило уже соответствовало PDF; переклассифицировано как CASE_INPUT, вопрос закрыт |
| Стр. 8–9 | Приведённые расходы, ставка, стоимость фактически обслуженной тонны | Только nominal total | Проверяемая ставка, end-year discounting, `discounted_cost_mln`, `cost_per_served_t_mln`; сравнение разных ставок запрещено |
| Стр. 8 | Контрагент, объём, даты, lead time, TOP, платежи, ответственность и пересмотр | В основном числа контракта | source_schedule + contract table UI; контрольный no-refund/no-cancellation, penalties не выдумываются |
| Стр. 9, 13 | Входы и сравнение в машиночитаемой выгрузке | Не было input CSV/сравнения/roadmap | ZIP: case/plan/scenario JSON, case_*.csv, scenario_comparison.csv, decision_changes.csv, roadmap.csv |
| Стр. 10–11 | Показать эффект изменённых решений, соблюдая сроки | Только неизменный план в стрессе | Два ex-ante stress plans, матрица 2×2, изменения и даты заказов, цена и результат redesign; без отмены уже оплаченных обязательств |
| Стр. 11 | Sensitivity существенных параметров и объяснение совместного стресса | Спрос + service threshold | Цены, ставка, границы lead time, ZBO delay, Emergency interpretation, combined TEAM test, price crossover; последовательная атрибуция эффекта |
| Стр. 12 | Меры соответствуют риску, остаточный риск и сторона | Только увеличение stock для всех рисков | Для GEO — предварительная диверсификация; stock для supply risks; каждый остаточный результат и стоимость пересчитываются; stakeholder_effects |
| Стр. 12 | Явная reliability для будущего периода | Для 2041 не раскрыто численное продолжение D | D=0.93 в TEAM-экстраполяции; не факт организатора; `extension_demo` |
| Стр. 13 | Инвестиционные ворота, владельцы, зависимости, бюджет | Неполная текстовая дорожная карта | `roadmap` из плана/денег/дат, CSV и UI; gate обязан сохранять control limits |
| Стр. 13–14 | README в корне передаваемого репозитория | Решение вложено в CosmoH | Автономный submission ZIP с README в корне; внешняя публикация GitVerse не выполнялась |

Таблицы спроса, мощности, цены, TOP, CAPEX, storage и обязательного стресса в PDF совпадают
с CSV/YAML снимка. Ни один organizer input, schema, test vector или validator не переписан.
`Дополнительно.pdf` содержит ссылку на README и внешнюю подборку литературы, а не новые коэффициенты.
Библиография организатора сохранена в `vendor/test_oil/docs/SCIENTIFIC_BASIS.md`.
Исходный XLSX «Анкета_постановщика_КосмоХакатон_ЕТ.xlsx» по-прежнему отсутствует в этих трёх PDF/репозитории;
машиночитаемая контрольная база используется вместе с проверкой таблиц PDF.

## Все 20 критериев (не самооценка баллами)

| №, критерий из PDF | Демонстрация | Проверка / артефакт |
|---|---|---|
| 1 Баланс | Суточный и годовой, критический вложен в общий | V01,V02,V06,V09; test_full_balance |
| 2 Мощность / сроки | Availability, комиссия, lead, reserved ≠ stock | test_lead_times, test_late_order_has_no_physical_supply, PREPARATION_* |
| 3 Экономика | Подготовка в 2035, TOP один раз, PV, стоимость/т | V03–V05; test_real_discount_rate_applied_with_declared_end_year_convention |
| 4 Ограничения | По годам, numeric actual/limit/unit/source | BASE и planned-stress checks; failures не спрятаны |
| 5 Воспроизводимость | Контрольные тесты + два чистых прогона | tools/check.sh; VERIFICATION.md; reference blocker отдельно |
| 6 Архитектура | io/validation → pure kernel → research → web/CLI | engine.py, PLAN_FORMAT.md |
| 7 Методы / источники | Evidence map и ограничения применимости | SCIENTIFIC_BASIS.md, REPORT.html |
| 8 Альтернативы | Earth/Lunar; unchanged vs ex-ante stress design | summary.json, comparison.csv, 2×2 matrices |
| 9 Инвестиции / контракты | Даты, зависимости, контрольные бюджеты | roadmap.csv, source_schedule.csv; UI investment editor |
| 10 Mandatory stress | Изолированные official multipliers | test_stress_isolation; PDF стр.10 ↔ mandatory_stress.yaml |
| 11 Sensitivity | Спрос, цена, rate, timing, ZBO, Emergency; thresholds | parameter_sensitivity.json/csv; price_crossover |
| 12 Методики | Фиксированный план, происхождение интервалов, seed | STRESS_PROTOCOL.md; attribution; independent/common-year MC |
| 13 Работа в стрессе | Старый дефицит сохранён, новые планы и цена | test_redesign_comparison_is_two_by_two_and_keeps_old_stress |
| 14 Реестр | Событие/причина/период/параметр/связи/owner | risk_register.csv/json |
| 15 Последствия | Δ тонн, cost, SL, без ordinal «ущерба» | risk_analysis; сценарий GEO не политический прогноз |
| 16 Меры | Финансируемый stock / prior diversification, residual checks | test_geopolitical_measure_addresses_price_exposure |
| 17 Стороны | Оператор, критические, коммерческие, поставщики, инвестор | stakeholder_effects + metrics + obligations |
| 18 Баланс интересов | Физические дельты при redesign/risk, MCDA sweep | compare_decisions.stakeholders, planned_stress_mcda |
| 19 Оператор | Менять планы и research input copy без кода | Web + API; инвестиции, ставка, JSON копии; E2E |
| 20 Save/export/extend | Проект и план, новые source/year, полный ZIP | roundtrip, test_api_research_copy_and_full_export, extension_demo |

Геополитический бонус: отдельный TEAM_ JSON, затронута агрегированная цена канала,
год и множитель редактируемы, возврат BASE, сохранение проекта и выгрузка before/after.
Разбивку на цену топлива и конкретный launch tariff не выдумываем — PDF стр.12 разрешает
сценарный множитель агрегированной цены при отсутствии разбивки.

## Оставшиеся ограничения и честная граница готовности

- Upstream reference validator всё ещё падает на отсутствующем ERRATA_AND_PROVENANCE.md.
  Это внешняя ошибка целостности; локальные тесты не превращают полный gate в зелёный.
- Численный порог «Emergency как базовый канал» не задан: контрольная реализация консервативна,
  альтернативная трактовка проверяется отдельно и не меняет BASE.
- Исторические даты доступности существующих каналов до начала 2035 не даны: они явно задаются
  как TEAM_ASSUMPTION и проверяются. Сам подготовительный период прямо разрешён PDF.
- ZBO construction duration не задана: default = оплата/ввод в одну дату, исследованы задержки.
- Добавлен ограниченный эксперимент после наблюдения сбоя: только новый Emergency-контракт,
  без отмены оплаченных/будущих обязательств, с 42 сутками lead time. RECOURSE.md фиксирует
  информацию, сроки, стоимость и residual. Универсальное перестроение не заявляется;
  прежние prepared-stress планы остаются отдельными решениями до дедлайнов.
- MC/MCDA иллюстративны, не калиброваны данными отказов или опросом. Сложность метода не
  выдаётся за независимую достоверность или гарантированную оценку жюри.
