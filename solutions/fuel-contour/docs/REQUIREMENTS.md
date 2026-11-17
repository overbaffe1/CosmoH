# Карта требований v0.2

Короткий маршрут по всем 20 пунктам: [JURY_GUIDE.md](JURY_GUIDE.md).
Реальные снимки и методика замеров: [DEMO_EVIDENCE.md](DEMO_EVIDENCE.md).

Основная карта после получения PDF: [PDF_AUDIT.md](PDF_AUDIT.md) — все 20 критериев с точными
страницами, изменениями, реализациями и тестами. Протокол: [STRESS_PROTOCOL.md](STRESS_PROTOCOL.md).

| Разделы README организатора | Реализация | Проверка |
|---|---|---|
| 1–4 / 24: цифровой контур, происхождение | engine, io, datasets, api/cli/web | API E2E, immutable snapshot, roundtrip |
| 5–8: граница, спрос, источники | load_case / research_copy | V09; input schemas, critical nesting |
| 9 / 16: инвестиции | commissioning, investment editor, roadmap | invalid/late commissioning, OPEX, CAPEX |
| 10–13: баланс и timing | balance_step, lead_days, evaluate | V01,V02,V06,V10; daily invariants |
| 14: reserve | reserve_required, preparation checks | V07, PREPARATION_*, stress redesign |
| 15 / 17: контракты и финансы | contract_cost, first-year prep, PV | V03–V05, partial year, first-year/PV tests |
| 18–20: сервис / reliability / stress | yearly_balance, scenario config | isolation + attribution + 2×2 |
| 21–22: sensitivity / risks / MC | analysis.py | intervals, threshold/crossover, residual, deterministic MC |
| 23: stakeholders | stakeholder_effects, mcda | same-rate guard, physical metrics independent of weights |
| 25–26: сохранение / ошибки | io, project, validation | complete ZIP, case CSV, reload, invalid numbers |
| 27: vectors | tests/test_vectors.py | V01–V10 |
| 28: развитие | research_copy, extension_demo | Source-X, 2041 explicit assumptions |
| 29–30: визуализация / критерии | web, tools/report.py, PDF_AUDIT | browser / print / generated values |
| 31: геополитика | TEAM scenario, price diversification | source/period/multiplier, price reset, residual |
| 32–34: сдача / источники | README, RUNBOOK, package.py, bibliography | clean snapshot, standalone package, reproducibility |

## Открытые вопросы после сверки

- Внешний reference validator: отсутствующая upstream-ссылка, не подставлять фиктивный документ.
- Конкретные исторические даты availability существующих каналов до горизонта — TEAM_ASSUMPTION.
  Сам подготовительный период и отнесение расходов в первый год разрешены и заданы PDF стр.7.
- Численный порог «Emergency как базовый канал» не дан. Conservative any-planned остаётся default;
  majority проверяется только в research-сценарии.
- Длительность строительства ZBO не дана. Исследованы 0/90/365 дней задержки, не физический прогноз.
- Reliability input не определяет полную вероятностную модель. MC показывает условные результаты,
  в том числе sensitivity к зависимости, без заявлений о реальных вероятностях.

Вопрос об автоматическом refund ISRU закрыт PDF: его нет в контрольном стрессе.
Не выдаём prepared-stress plan за реакцию после фиксации контрактов; новое решение должно
быть принято к датам заказа, которые экспортируются в сравнении.
