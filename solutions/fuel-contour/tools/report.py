"""Generate every quantitative report table/chart from the reproducible suite, no copied totals."""
import html
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fuel.io import load_json, digest


def f(v):
    return f'{v:,.2f}'.replace(',', ' ').replace('.', ',') if isinstance(v, (float,int)) else html.escape(str(v))

def table(headers, rows):
    return '<table><thead><tr>'+''.join('<th>'+html.escape(x)+'</th>' for x in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+f(x)+'</td>' for x in row)+'</tr>' for row in rows)+'</tbody></table>'

CSS = '''@page{size:A4;margin:18mm}*{box-sizing:border-box}body{margin:0;font:13px/1.65 Arial,sans-serif;color:#162f3a;background:#e9eeec}article{background:white;max-width:210mm;margin:18px auto;padding:20mm;min-height:260mm;position:relative;break-after:page}article:last-child{break-after:auto}h1{font-size:32px;line-height:1.18;margin:14px 0 22px}h2{font-size:22px;line-height:1.3}h3{font-size:15px;color:#267958}p{margin:12px 0}small,.muted{color:#526771}.kicker{font-size:10px;letter-spacing:2px;text-transform:uppercase;color:#267958}table{width:100%;border-collapse:collapse;font-size:10px;margin:18px 0}th,td{padding:7px 6px;border-bottom:1px solid #dce6e2;text-align:left}th{background:#eef5f1}pre{white-space:pre-wrap;background:#edf4f0;padding:15px;font:11px/1.6 monospace}.callout{background:#eef5ef;border-left:4px solid #438967;padding:14px 18px;margin:18px 0}.warn{background:#fff3dc;border-left-color:#c79644}footer{font-size:9px;color:#667e77;margin-top:25px;border-top:1px solid #dae3de;padding-top:8px}svg{width:100%;height:auto}.columns{display:grid;grid-template-columns:1fr 1fr;gap:24px}@media print{body{background:white}article{margin:0;max-width:none;padding:0;min-height:0;height:258mm;overflow:visible}footer{position:absolute;bottom:0}}'''


def document(title, pages):
    return '<!doctype html><html lang="ru"><meta charset="utf-8"><title>'+html.escape(title)+'</title><style>'+CSS+'</style><body>'+''.join(f'<article><div class="kicker">КОСМОКОНТУР / УПРАВЛЕНЧЕСКАЯ ЗАПИСКА / {i+1:02}</div>{page}<footer>TEAM_ANALYSIS · {title} · Страница {i+1} / {len(pages)} · Все числа: python -m fuel.cli suite → python tools/report.py</footer></article>' for i,page in enumerate(pages))+'</body></html>'


def line_chart(rows, keys):
    maximum=max(float(r[k]) for r in rows for k,_,_ in keys)*1.12 or 1
    x=lambda i: 48+i*490/max(1,len(rows)-1)
    y=lambda v: 210-v/maximum*170
    paths=[]
    for k,label,color in keys:
        paths.append('<polyline fill="none" stroke="'+color+'" stroke-width="3" points="'+' '.join(f'{x(i)},{y(r[k])}' for i,r in enumerate(rows))+'"/>')
    axis=''.join(f'<text x="{x(i)}" y="238" font-size="11">{r["year"]}</text>' for i,r in enumerate(rows))
    ticks=''.join(f'<text x="0" y="{y(maximum*i/4)+4}" font-size="10">{maximum*i/4:.0f}</text><line x1="40" x2="570" y1="{y(maximum*i/4)}" y2="{y(maximum*i/4)}" stroke="#dee8e0"/>' for i in range(5))
    return '<svg viewBox="0 0 600 255">'+ticks+''.join(paths)+axis+'</svg><p class="muted">'+' · '.join(label for _,label,_ in keys)+'</p>'


def main():
    s=load_json(ROOT/'results/summary.json')
    earth,lunar=[s['strategies'][k] for k in ['earth','lunar']]
    comparison=table(['План / среда','Стоимость, млн','Дефицит, т','Мин. общий SL','Мин. крит. SL','Нарушения'],
                     [[k+' / '+scenario.upper(),v[scenario]['total_cost_mln'],v[scenario]['shortage_t'],100*v[scenario]['min_total_service'],100*v[scenario]['min_critical_service'],v[scenario]['violations']] for k,v in s['strategies'].items() for scenario in ['base','stress']])
    savings=earth['base']['total_cost_mln']-lunar['base']['total_cost_mln']
    added=lunar['stress']['shortage_t']-earth['stress']['shortage_t']
    pages=[]
    pages.append(f'''<h1>Топливный космоконтур<br>2035–2040</h1><p class="muted">Работающий инструмент планирования • управленческая записка • 19 сентября 2026</p>
    <h2>Решение для оператора, не готовый ответ организатора</h2><p>Разработан сценарный планировщик снабжения одного орбитального узла совместимым агрегированным ресурсом. Оператор изменяет заказы, резервируемые мощности, инвестиции и физический запас; расчёт показывает поставки, дефицит, деньги и нарушения. Все интерфейсы используют одно расчётное ядро.</p>
    {comparison}<p>В показанных альтернативах Lunar снижает стоимость BASE на <b>{f(savings)} млн у.е.</b>, но увеличивает дефицит обязательного стресса на <b>{f(added)} т</b>. Оба плана проходят BASE в принятой модели и сохраняют критический сервис в стрессе, но не весь коммерческий спрос и не годовой резерв.</p>
    <div class="callout">Предварительный управленческий выбор: земная диверсификация как более устойчивый из двух показанных планов. Lunar — экономическая альтернатива, а не обязательная технология. Выбор не является доказанным глобальным оптимумом.</div>
    <div class="callout warn">Не готово к безусловной сдаче: upstream-валидатор падает на отсутствующей ссылке; три PDF из orbit недоступны; предгоризонтный контракт требует подтверждения организатора.</div>''')
    pages.append(f'''<h1>01 / Источники и границы</h1><p><b>CASE_INPUT</b>: неизменённый снимок SpaceEconomyPolicy/test_oil, commit <code>{s['case_version']}</code>. Версия и SHA256 каждого файла фиксируются. В контрольной базе нет выручки, стоимости срыва миссии или детальной статистики отказов.</p>
    <p><b>TEAM_DECISION</b>: два стартовых плана и редактируемые пользователем объёмы. Начальный запас, моменты ввода и окна поставок не объявляются решениями организатора.</p><p><b>TEAM_ASSUMPTION</b>: временная конвенция, предгоризонтное приобретение запаса, условия оплаты недопоставок, распределение обслуживания, интерпретация reliability и веса MCDA.</p>
    <h2>Граница физики</h2><p>Модель не рассчитывает траектории, геометрию криобаков, состав топлива, теплообмен и технологическую готовность ISRU. Цена канала уже включает доставку в узел. Нельзя интерпретировать коэффициент потерь ZBO как универсальную характеристику реального оборудования.</p>
    <h2>Научная трассируемость</h2>{table(['Источник в SCIENTIFIC_BASIS.md','Применение','Ограничение'],[['NASA-STD-7009B','V&V, разделение верификации и достоверности','Тесты не подтверждают реальную надёжность'],['Ho (2024)','Запас и инфраструктура в логистике','Нет высокоточной динамики полёта'],['Simonini et al. (2024)','Контекст cryogenic management','Не источник чисел учебной модели'],['JCGM 101:2008','Процедура Monte Carlo','Не даёт распределения отказов'],['Linkov et al. (2006)','Явные веса MCDA и sensitivity','Веса не получены опросом']])}
    <p>Папка vendor содержит полный текст научного обоснования организатора. Закрытых API и внешних платных сервисов для расчёта нет. PDF из недоступного orbit не реконструировались и не заменялись предположениями.</p>''')
    pages.append('''<h1>02 / Расчётная архитектура</h1><pre>CASE_INPUT + TEAM_DECISION + TEAM_ASSUMPTION
                    ↓ validate
           commissioning / contracts
                    ↓
        daily inflow → storage → demand
                    ↓
        costs + constraints + annual SL
                    ↓
       BASE / STRESS / isolated TEAM_*
                    ↓
         UI = CLI = JSON/CSV exports</pre>
    <p>Расчётный слой не выполняет сетевые запросы и не записывает файлы. Загрузка CSV/YAML, сериализация и HTTP отделены. Проверки JSON Schema дополнены предметной валидацией: отрицательные/нечисловые объёмы, дубликаты контрактов, неизвестные источники, неверные периоды и вложенность спроса.</p>
    <h2>Суточный баланс</h2><pre>I_end = I_start + delivered − throughput_loss − served
shortage = demand − served ≥ 0
losses = accepted_gross_inflow × active_loss_rate</pre>
    <p>Поставка поступает в начале суток. Обслуживание равномерно внутри суток; критическая часть получает приоритет. Стоимость хранения — интеграл фактического запаса, включая случай исчерпания до конца суток. Потери не начисляются повторно на остаток.</p>
    <p>Переполнение не скрывается: показывается превышение до приёмки, непринимаемый валовый объём отклоняется, физический баланс использует принятый объём. Оплата исходного заказа сохраняется. Годовых сумм недостаточно: сжатие поставок в одни сутки даёт одновременно отказ приёмки и последующий дефицит.</p>''')
    pages.append('''<h1>03 / Управляемые решения и контракты</h1><p>Стартовый эвристический план покупает ресурс в порядке стоимости доступных каналов. Это воспроизводимая начальная точка для оператора, не оптимизатор. Конечный годовой запас ориентирован на резерв следующего года обязательного стресса с явно выбранным буфером. Пользователь может заменить каждое решение.</p>
    <h2>Контрактный период</h2><pre>Q_pay = max(Q_order, TOP_share × reserved × period_fraction)
Procurement = Q_pay × scenario_variable_price
Reservation = annual_reserved × reservation_rate × period_fraction</pre>
    <p>Один контракт источника на год; начало и конец периода редактируются. Суточное моделирование не создаёт суточных минимумов TOP. Ordered, offered, delivered и served сохранены отдельно. Недопоставка не превращается в неявный возврат оплаты.</p>
    <h2>Timing</h2><p>Учебный год содержит 365 суток, месяц — 365/12 суток, неделя — 7. Для диапазонов выбран верхний lead time с округлением вверх. Emergency сохраняет шесть недель, а не «полтора месяца». Заказ, сделанный слишком поздно, не создаёт немедленной поставки: модель показывает LEAD_TIME и недопоставку.</p>
    <h2>Начальный запас</h2><p>Он приобретён отдельным предгоризонтным контрактом действующего Earth-Core. Валовый объём включает потери базового хранения, тариф резервирования и день содержания. Эта стоимость добавляется к полной стоимости один раз; в inflow 2035 запас второй раз не входит. Допущение о доступности такого контракта в 2034 требует подтверждения.</p>
    <h2>Emergency</h2><p>Физический резерв на начало года не заменяется годовой мощностью Emergency. Консервативная трактовка ограничения серии: любой плановый положительный заказ считается годом базового использования. В стартовых планах аварийный канал не нужен; редактор позволяет увидеть нарушение при последовательном использовании.</p>''')
    capex=table(['Год','Earth CAPEX','Lunar CAPEX','Lunar fixed OPEX'],[[e['year'],e['capex_mln'],l['capex_mln'],l['fixed_opex_mln']] for e,l in zip(earth['costs_base'],lunar['costs_base'])])
    pages.append(f'''<h1>04 / Инфраструктура и бюджет</h1>{capex}<p>Earth-New оплачивается как option fee плюс exercise cost. Итоговая стоимость опции не начисляется третьим платежом. Подготовка отсчитывается от решения; контрактный lead time проверяется независимо. Нельзя получить мощность просто из наличия строки источника в CSV.</p>
    <p>ZBO включается после оплаты, не раньше года доступности. Дополнительный OPEX учитывается со дня ввода. Условия кейса не задают строительной длительности — мгновенное включение в выбранную дату является ограничением уровня детализации, а не прогнозом стройки.</p>
    <p>Lunar финансируется до установленного срока, вводится с допустимого года, первая поставка появляется после lead time послевводовой логистики. Нарушенная дата ввода не «исправляется» ядром: инвестиция остаётся в денежном плане, но мощность не включается.</p>
    <h2>Финансовая граница</h2><pre>Total = Procurement + Reservation + Holding + FixedOPEX + CAPEX
        + separately financed pre-horizon stock</pre><p>Суммы выражены в миллионах условных единиц в постоянных ценах 2035. Дисконтирование отключено одинаково для обеих альтернатив. Потери уже требуют оплаченного валового топлива; повторная денежная надбавка «за потери» не добавляется. Не рассчитаны выручка, прибыль или стоимость потерянной миссии.</p>
    <p>CAPEX проверяется накопленным итогом на контрольные даты. После горизонта не объявляется автоматическое продление лимита организатора: исследовательская копия будущего года раскрывает применяемые правила отдельно.</p>''')
    annual=table(['Год','Earth: дефицит','Earth: общий SL, %','Lunar: дефицит','Lunar: общий SL, %'],[[e['year'],e['shortage_t'],100*e['total_service_level'],l['shortage_t'],100*l['total_service_level']] for e,l in zip(earth['yearly_stress'],lunar['yearly_stress'])])
    pages.append(f'''<h1>05 / Обязательный стресс</h1><p>Проверка меняет только окружение, не план. Рост спроса, шок переменных цен Earth-Core/Flex и фактические доли Lunar применяются непосредственно из файла организатора. Резервные тарифы, CAPEX и другие цены не подменяются этим шоком.</p>{annual}
    {line_chart(lunar['yearly_stress'], [('demand_t','Синий: спрос, т','#5378af'),('served_t','Зелёный: обслужено, т','#318363')])}
    <p>Недопоставка ISRU не умножается повторно на reliability. Уровень обслуживания критических клиентов остаётся высоким за счёт приоритета, но это не устраняет коммерческий дефицит. Резерв на начало следующего года также может нарушаться даже при хорошем годовом critical SL.</p><div class="callout warn">Стартовые планы не являются stress-feasible. UI и экспорт сохраняют нарушения. Не добавляем «задним числом» внеплановый Emergency, расширение баков или бюджет.</div>''')
    sens=earth['sensitivity']
    sens_table=table(['Спрос ×','Стоимость Earth','Дефицит Earth','Нарушения'],[[r['factor'],r['total_cost_mln'],r['shortage_t'],r['violations']] for r in sens['points']])
    pages.append(f'''<h1>06 / Чувствительность и граница сервиса</h1>{sens_table}<p>Uniform multiplier — исследовательское изменение всех лет, а не mandatory stress. Отдельно проверены организаторские low/high с сохранением доли критической части каждого года.</p>{table(['План','Low: дефицит','High: дефицит','High: мин. общий SL, %'],[[k,v['sensitivity']['low_high']['low']['shortage_t'],v['sensitivity']['low_high']['high']['shortage_t'],100*v['sensitivity']['low_high']['high']['min_total_service']] for k,v in s['strategies'].items()])}
    <p>Бисекция ищет границу соблюдения service thresholds на диапазоне множителя [1; 2]. Полученный интервал Earth: <b>{sens['service_failure_bracket']}</b>. Это только граница сервиса, не всех ограничений. Если уже исходная точка нарушена или граница не достигнута, алгоритм возвращает отдельный статус, а не ложный порог.</p>
    <p>Низкий спрос способен вызвать переполнение, поскольку заказы не адаптируются. Стоимость при этом почти не падает: TOP и оплаченный заказ сохраняются. Поэтому требуются контрактные опции изменения отбора и явная политика принятия решений, а не только увеличение закупки.</p><p>В научно обоснованном следующем инкременте следует исследовать обе границы lead time, задержку ZBO и иную трактовку Emergency. Текущая реализация консервативно использует верхние границы; отдельный численный sweep этих допущений пока не реализован.</p>''')
    riskrows=[[k,r['risk_id'],r['physical_consequence_t'],r['financial_consequence_mln'],r['residual_consequence']['shortage_t']] for k,v in s['strategies'].items() for r in v['risks']]
    pages.append(f'''<h1>07 / Реестр рисков и геополитика</h1>{table(['План','Событие','Δ дефицит, т','Δ стоимость','Остаточный дефицит*'],riskrows)}<p>* Остаточный результат рассчитан на явно изменённом плане с дополнительным начальным запасом, оплаченным отдельным контрактом. Это не бесплатное скрытое реагирование в стрессе. Дополнительная стоимость и все нарушения альтернативы сохранены в JSON.</p>
    <h2>Причинная цепочка</h2><pre>TEAM_GEO: иллюстративное ограничение торговли
 → Earth-Core variable price, отдельный год
 → новый расчёт того же плана
 → изменение закупочной стоимости
 → интересы инвестора, поставщика и оператора</pre><p>Событие не приписывается реальной стране или организации и не получает выдуманную вероятность. Параметры, исходный множитель и изменённое значение экспортируются; возвращение к BASE восстанавливает контрольные значения.</p>
    <p>Для Lunar outage ответственность отнесена к оператору установки, для Earth disruption — к руководителю логистики, для ценового риска — к закупочной функции. Предлагаемые меры включают диверсификацию и запас; рассчитанная здесь мера — увеличение начального запаса. Она не устраняет причину ценового шока и не доказывает эффективность всех перечисленных мер.</p><p>Риски по умолчанию изолированы, зависимость между ними не оценивается. Поля owner, mitigation, changed parameter, period и residual result сохранены в машиночитаемом реестре.</p>''')
    mcrows=[[k,v['monte_carlo']['count'],v['monte_carlo']['service_failure_fraction'],v['monte_carlo']['mean_shortage_t'],v['monte_carlo']['p95_shortage_t']] for k,v in s['strategies'].items()]
    pages.append(f'''<h1>08 / Неопределённость и интересы сторон</h1>{table(['План','Испытания','Доля отказа сервиса*','Средний дефицит','P95 дефицита'],mcrows)}<p>* Только внутри явно гипотетической модели: source-year Bernoulli полного годового отказа, независимость между источниками и годами, фиксированный seed. Reliability из кейса трактуется как вероятность годовой доступности исключительно в этом исследовании.</p><p>Интервал Wilson отражает ошибку выборки при данном распределении, но не неопределённость самой интерпретации reliability. Распределение не калибровано; частичные отказы и корреляции исключены. Полученные доли нельзя называть реальными вероятностями срыва миссий.</p>
    <h2>MCDA не заменяет физику</h2>{table(['Сторона','Стоимость','Критический сервис стресса','Дефицит стресса'],[[k,*v] for k,v in s['mcda']['weights'].items()])}<p>Весовые векторы — TEAM_ASSUMPTION, не опрос реальных стейкхолдеров. Критерии нормируются min/max по сравниваемым альтернативам; одинаковые значения получают одинаковую оценку. Проведён sweep веса стоимости. При добавлении альтернатив нормировка и рейтинг пересчитываются.</p>
    <p>Критические потребители заинтересованы в непрерывности обслуживания, коммерческие — в доступном общем объёме, инвестор — в расходах и риске, поставщик — в предсказуемости контрактов, оператор — в запасе и исполнимости. Денежная стоимость служит лишь грубым proxy интересов поставщика; дальнейшее согласование предпочтений обязательно.</p>''')
    pages.append(f'''<h1>09 / Проверка, сдача и следующий шаг</h1><h2>Критерии</h2>{table(['Критерий','Артефакт'],[['Корректность','V01–V10, суточные инварианты, ошибки и нарушения'],['Архитектура/стратегия','Чистое ядро, два плана, раздельное происхождение'],['Стресс','Неизменный план, BASE/STRESS, low/high, threshold'],['Риски','Изолированные события, последствия, рассчитанная мера'],['Стейкхолдеры','Пять профилей, нормировка и sweep весов'],['Функциональность','Web/CLI, save/open, JSON и CSV, Source-X/2041']])}
    <h2>Две команды из каталога решения</h2><pre>bash tools/setup.sh
bash tools/reproduce.sh</pre><p>Вторая команда создаёт расчёты и записку, запускает тесты и неизменённый референсный валидатор. При известном дефекте upstream завершается ненулевым кодом: это честный блокирующий gate, не скрытое исключение.</p>
    <h2>Остаточные работы</h2><ol><li>Получить три PDF и сопоставить их правила с pinned control inputs.</li><li>Дождаться исправления отсутствующего upstream-документа и обновить снимок только через проверку diff.</li><li>Подтвердить предгоризонтное финансирование, условия оплаты недопоставок и трактовку Emergency.</li><li>Добавить договорную адаптацию с учётом lead time; добиться stress-feasible альтернативы, не маскируя нарушения.</li><li>Расширить sensitivity реализации lead time и ZBO; калибровать риск-модель при появлении статистики.</li></ol>
    <p>Контроль воспроизводимости отчёта: SHA256 summary.json <code>{digest(s)}</code>. Точные значения, неокруглённые таблицы, планы и параметры исследований доступны в results. HTML предназначен для печати на десяти страницах A4; одностраничное сравнение и презентация генерируются тем же скриптом.</p>''')
    dest=ROOT/'docs'
    (dest/'REPORT.html').write_text(document('Топливный космоконтур 2035',pages),encoding='utf-8')
    one=f'''<h1>Один план — два окружения</h1><p>Сравнение двух TEAM_DECISION на неизменённых BASE/MANDATORY_STRESS. Стоимость включает финансирование начального запаса; SL — минимум годовых уровней, %.</p>{comparison}<div class="callout">Lunar дешевле в BASE на {f(savings)} млн у.е.; в mandatory stress дефицит больше на {f(added)} т. Предварительное предпочтение: земная диверсификация, если важнее устойчивость общего обслуживания.</div><p>Критический сервис защищён приоритетной выдачей, но это не отменяет дефицит прочего спроса и нарушение физического резерва. Обе стартовые стратегии требуют адаптивного контрактного плана для соблюдения всех стрессовых ориентиров.</p><h2>Статус сдачи</h2><p>Расчёты и собственные тесты воспроизводимы. Полный gate заблокирован upstream-ссылкой; три PDF orbit не рассмотрены. Начальный запас и reliability interpretation — явные TEAM_ASSUMPTION.</p><pre>bash tools/setup.sh
bash tools/reproduce.sh</pre>'''
    (dest/'COMPARISON.html').write_text(document('Одностраничное сравнение',[one]),encoding='utf-8')
    slide_titles=['Продукт','Данные и границы','Архитектура','Контракты','Инвестиции','Стресс','Sensitivity','Риски','Стейкхолдеры','Проверка и ограничения']
    # Slides use concise generated content, not ten pages of pasted report.
    slides=[f'<h1>Топливный космоконтур 2035</h1><h2>Решения → физика → деньги → ограничения</h2><p>Работающий сценарный планировщик. Web + CLI, единое ядро, сохранение и экспорт.</p>',
            '<h1>Три слоя происхождения</h1><h2>CASE_INPUT / TEAM_DECISION / TEAM_ASSUMPTION</h2><p>Контрольные данные неизменяемы. Никакой бесплатной начальной массы или скрытых штрафов.</p>',
            '<h1>Суточный баланс</h1><pre>opening + delivered − losses − served = closing</pre><p>Внутригодовой shortage, отказ приёмки при overflow, time-weighted holding.</p>',
            '<h1>Заказ ≠ поставка ≠ запас</h1><p>Годовой take-or-pay начисляется один раз. Lead time проверяется до физической поставки. Critical входит в total.</p>',
            '<h1>Инвестиции включают мощность</h1>'+capex,
            '<h1>Цена устойчивости</h1>'+comparison,
            '<h1>Границы, а не одна цифра</h1>'+table(['План','Low shortage','High shortage'],[[k,v['sensitivity']['low_high']['low']['shortage_t'],v['sensitivity']['low_high']['high']['shortage_t']] for k,v in s['strategies'].items()]),
            '<h1>Риски связаны с расчётом</h1>'+table(['План','Событие','Δ shortage','Δ cost'],[r[:4] for r in riskrows]),
            '<h1>Приоритеты не отменяют дефицит</h1><p>Пять сторон, явные веса, min/max нормировка, sweep стоимости. MC — только гипотетическая модель, не реальные вероятности.</p>',
            '<h1>Демонстрация и честный gate</h1><p>Изменить заказ → BASE → STRESS → sensitivity → сохранить → открыть → экспорт.</p><div class="callout warn">Открыто: upstream-валидатор, PDF orbit, предгоризонтный контракт, stress-feasible адаптация.</div>']
    slide_doc=document('Презентация',slides).replace(CSS,CSS+'@page{size:297mm 167mm;margin:14mm}@media print{article{height:137mm}}article{min-height:150mm;max-width:297mm}h1{font-size:35px}p{font-size:18px}@media print{article{min-height:0;height:137mm}}')
    (dest/'PRESENTATION.html').write_text(slide_doc,encoding='utf-8')
    (dest/'numbers.json').write_text(json.dumps(s,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Generated docs/REPORT.html (10 pages), COMPARISON.html (1), PRESENTATION.html (10 slides), numbers.json')

if __name__=='__main__':main()
