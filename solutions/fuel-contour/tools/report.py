"""Generate every quantitative report table/chart from the reproducible suite, no copied totals."""
import html
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fuel.io import load_json, digest
from defense import write_assets


def f(v):
    if isinstance(v, int):
        return str(v)
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
    labels={'base':'BASE / исходный','stress':'STRESS / исходный','planned_stress':'STRESS / новый'}
    comparison=table(['Архитектура / план','Стоимость, млн','Дефицит, т','Общий SL, %','Нарушения'],
                     [[k+' · '+labels[tag],v[tag]['total_cost_mln'],v[tag]['shortage_t'],100*v[tag]['min_total_service'],v[tag]['violations']]
                      for k,v in s['strategies'].items() for tag in labels])
    delta=table(['Архитектура','Доп. расходы в стрессе','Устранённый дефицит, т','Ранний изменённый заказ, день'],
                [[k,v['decision_comparison']['incremental_stress_cost_mln'],v['decision_comparison']['avoided_stress_shortage_t'],v['decision_comparison']['earliest_changed_order_day']] for k,v in s['strategies'].items()])
    base_saving=earth['base']['total_cost_mln']-lunar['base']['total_cost_mln']
    prepared_saving=earth['planned_stress']['total_cost_mln']-lunar['planned_stress']['total_cost_mln']
    riskrows=[[k,r['risk_id'],r['physical_consequence_t'],r['financial_consequence_mln'],r['mitigation_baseline_cost_mln'],r['residual_consequence']['shortage_t']]
              for k,v in s['strategies'].items() for r in v['risks']]
    capex=table(['Год','Earth CAPEX','Lunar CAPEX','Ввод Earth','Ввод Lunar'],
                [[e['year'],e['capex_mln'],l['capex_mln'],', '.join(e['commissioned']),', '.join(l['commissioned'])]
                 for e,l in zip(earth['roadmap'],lunar['roadmap'])])
    budget=table(['Год','Earth BASE','Earth новый STRESS','Lunar BASE','Lunar новый STRESS'],
                 [[a['year'],a['total_mln'],b['total_mln'],c['total_mln'],d['total_mln']]
                  for a,b,c,d in zip(earth['costs_base'],earth['costs_planned_stress'],lunar['costs_base'],lunar['costs_planned_stress'])])
    recourse_table=table(['Наблюдение, сутки','Новый E, т','Доплата, млн','Остаток дефицита, т','Нарушения'],[[r['observed_after_days'],r['added_order_t'],r['incremental_cost_mln'],r['after']['shortage_t'],r['after']['violations']] for r in s.get('recourse',[])])
    pages=[]
    pages.append(f'''<h1>Топливный космоконтур<br>2035–2040</h1><p class="muted">Управленческое решение и воспроизводимый цифровой контур · версия 0.2</p>
    <p>Оператор меняет закупки, резерв мощности, запас, инвестиции и допущения. Суточное ядро пересчитывает физику, расходы и нарушения. Web и CLI используют одни функции; цифры этой записки построены из результатов, не вписаны вручную.</p>{comparison}
    <div class="callout">Подготовлены отдельные планы для двух известных условий. Исходные планы проходят BASE, но теряют общий сервис в обязательном стрессе. Заранее изменённые планы закрывают весь стрессовый спрос и резерв без увеличения контрольных лимитов.</div>
    <p>При ставке 0% Lunar дешевле Earth на <b>{f(base_saving)} млн</b> в BASE и на <b>{f(prepared_saving)} млн</b> при подготовленном стрессовом плане. Это сравнение двух эвристик, не доказательство оптимума. В BASE при ставке 10% Earth уже дешевле на <b>{f(s['discount_rate_crossover']['samples'][-1]['lunar_minus_earth_mln'])} млн</b>; граница в исследованном интервале — около <b>{f(100*s['discount_rate_crossover']['bracket'][0])}%</b>. Сначала отсеиваем невыполнимые планы, затем сравниваем PV. Готовность инвестора и нового производства требует отдельного подтверждения.</p>
    <p>Подготовленные stress планы нельзя автоматически использовать в BASE: избыток поставок может переполнить хранилище. В сравнении сохранена полная матрица 2×2, а не только удачные комбинации.</p>
    <div class="callout warn">Три PDF постановщика прочитаны и сверены. Единственный внешний verification-блокер: неизменённый upstream-валидатор падает на отсутствующей ссылке ERRATA_AND_PROVENANCE.md. Это не заменяет диагностику самих планов.</div>''')
    pages.append(f'''<h1>01 / Данные, происхождение и методы</h1><p><b>CASE_INPUT</b> — CSV/YAML/схемы организатора, commit <code>{s['case_version']}</code>. PDF постановки, критериев и дополнений сохранены отдельно с SHA256. Спрос, каналы, storage, CAPEX и графическая таблица обязательного стресса на стр.10 совпадают с машиночитаемой базой.</p>
    <p><b>TEAM_DECISION</b> — четыре сохранённых плана: Earth/Lunar для BASE и для обязательного стресса. <b>TEAM_ASSUMPTION</b> — календарная конвенция, история доступности до горизонта, timing ZBO, диапазоны исследований, модель отказов и предпочтения MCDA.</p>
    <h2>Что уточнили PDF</h2><p>Постановка, стр.7 прямо разрешает подготовительный период и требует включить его расходы в первый финансовый год. Проверяются дата заказа, поставки и доступность существующего канала. Недопоставка ISRU в обязательном стрессе не создаёт автоматического refund — это правило, а не незакрытый вопрос.</p>
    {table(['Научная опора организатора','Реализация','Граница применимости'],[['NASA-STD-7009B','Проверки, provenance, regression','Не NASA-сертификация'],['Ho, 2024; DOI 10.2514/1.A35982','Связанные supply/inventory/infrastructure','Не траекторная модель'],['Simonini et al., 2024; 10.1038/s41526-024-00377-5','Отдельные потери и хранение','Коэффициент кейса не универсальный ZBO'],['Linkov et al., 2006; 10.1016/j.envint.2006.06.013','Явные MCDA шкалы, веса, sweep','Веса не получены опросом'],['JCGM 101:2008; 10.59161/JCGM101-2008','Воспроизводимая MC-процедура','Не калибрует распределения отказов']])}
    <p>Полные авторы, названия, DOI и evidence map — в SCIENTIFIC_BASIS.md организатора. Литература обосновывает классы методов, но не учебные цены и не наши вероятности. Не заявляем независимую проверку всех первичных публикаций. Исходный XLSX из постановки в комплекте отсутствует; использованы согласованные PDF и CSV.</p>''')
    pages.append('''<h1>02 / Архитектура и физическая модель</h1><pre>Earth-Core / Earth-Flex / Earth-New / Lunar / Emergency
    ↓ доступность, инвестиции, заказ и lead time
    ↓ reserved ≠ ordered ≠ offered ≠ accepted
Один орбитальный узел → storage → critical / commercial
    ↓ daily balance, losses, reserve, overflow
Годовые контракты + CAPEX/OPEX → деньги → checks
    ↓
Одинаковое ядро → UI / CLI / JSON / CSV / записка</pre>
    <p>Сопоставимый условный ресурс поступает в один узел. Переменная цена уже включает доставку: стоимость конкретного носителя не прибавляется. Состав топлива, геометрия баков, тепловая динамика и траектории не моделируются.</p>
    <h2>Суточный баланс</h2><pre>I_end = I_start + accepted_gross − losses − served
losses = accepted_gross × active_storage_loss_rate
shortage = demand − served ≥ 0</pre>
    <p>Поставка принимается до выдачи текущих суток. Спрос равномерен, critical обслуживается первым и входит в total. Отрицательный запас не допускается. Избыточное поступление отклоняется до приёмки, показывается отдельно и создаёт STORAGE_OVERFLOW; обязательство оплатить исходный заказ сохраняется.</p>
    <p>Holding считается интегралом физического запаса при равномерном расходовании, в том числе если топливо заканчивается внутри суток. Потери не начисляются повторно на остаток. Суточная модель выявляет дефицит и переполнение, которые скрывает годовой баланс.</p>
    <p>Источник ограничен годовой мощностью и долей доступного года. Модель не задаёт необъявленный физический максимум мгновенной скорости подачи. Равномерные партии внутри выбранного окна — допущение команды, не расписание реальных запусков.</p>''')
    pages.append(f'''<h1>03 / Контракты, подготовка и экономика</h1><pre>Q_pay = max(Q_order, TOP × reserved × period_fraction)
Procurement = price × Q_pay
Reservation = tariff × annual_reserved × period_fraction</pre>
    <p>Годовой TOP не превращается в сумму независимых месячных минимумов. В source_schedule доступны контрагент, мощность, заказ, физическая приёмка, даты, lead time, оплачиваемый объём и платежи. Запуск включён в агрегированную цену. Не заданные кейсом штрафы, страховые выплаты и возвраты не добавляются.</p>
    <p>Заказы фиксируются до начала окна поставок с полным lead time. Для Earth-New подготовка и заказ идут параллельно; Lunar начинает поставки только после ввода плюс послевводовая логистика. Месяц = 365/12 суток с округлением вверх; границы диапазонов исследуются отдельно.</p>
    <h2>Подготовительный период</h2><p>Начальный запас приобретается у действующего канала, проходит отдельные availability/lead-time/capacity/storage проверки и не повторяется в inflow 2035. Историческая доступность до 2035 явно задана как TEAM_ASSUMPTION. Расходы закупки, резервирования и содержания подготовки включены в 2035; таблица pre_horizon — детализация, не дополнительное слагаемое.</p>
    <pre>Total = Σ Procurement + Reservation + Holding + OPEX + CAPEX
PV_y = Cost_y / (1+r)^(y−2035+1)
UnitCost = Total / actually_served_tonnes</pre>
    {table(['План / среда','Реальная ставка','Приведённые расходы','Млн / обслуженную т'],[[k+' / '+tag,v[tag]['discount_rate'],v[tag]['discounted_cost_mln'],v[tag]['cost_per_served_t_mln']] for k,v in s['strategies'].items() for tag in ['base','planned_stress']])}
    <p>Нулевая ставка — прозрачная основная база; дополнительно рассчитаны положительные ставки. Денежные потоки относятся к концу года и приводятся к началу 2035. В сравнении нельзя менять ставку между альтернативами. Нет выручки, прибыли, выдуманной стоимости миссии или terminal salvage.</p>''')
    pages.append(f'''<h1>04 / Бюджет и инвестиционные ворота</h1>{capex}<h2>Годовая потребность в финансировании, млн у.е.</h2>{budget}
    <p>Earth-New оплачивается суммой option fee и exercise, без третьего платежа total. ZBO включается в выбранную дату полной оплаты, не раньше доступности; отдельно исследована задержка. Lunar финансируется до допустимого ввода, fixed OPEX начинается после него. Проверки CAPEX накопительные, пороги берутся из CASE_INPUT.</p>
    <h2>Роли и зависимости</h2><p><b>Инвестор</b> открывает финансирование только после проверки лимитов и альтернатив; <b>инфраструктурный руководитель</b> подтверждает подготовку/ввод; <b>закупки</b> фиксируют договоры до их order_day; <b>оператор</b> подтверждает ёмкость, сервис и запас на следующий год. Подробные заказы по моментам фиксации включены в roadmap.csv.</p>
    <p>Инвестиционные ворота: обоснование опции → финансирование → завершение lead time → включение мощности → эксплуатационные платежи. Предлагаемый следующий этап Lunar требует подтверждения производственной готовности до финансирования; модель сама не доказывает её. Резерв на начало года проверяется отдельно от способности Emergency привезти топливо позднее.</p>
    <p>Заранее подготовленный стрессовый вариант не увеличивает мощности или CAPEX. Дополнительные расходы — закупка, reservation и содержание, а не скрытое расширение лимитов. Roadmap и бюджет автоматически пересчитываются при изменении решения в интерфейсе.</p>''')
    matrix=table(['Архитектура / роль плана','Среда','Cost, млн','Shortage, т','Нарушения'],
                 [[k+'/'+r['plan_role'],r['scenario_id'],r['total_cost_mln'],r['shortage_t'],r['violations']]
                  for k,v in s['strategies'].items() for r in v['decision_comparison']['matrix']])
    pages.append(f'''<h1>05 / Стресс и цена изменения решений</h1>{matrix}{delta}
    <p>В исходном плане обязательный шок спроса, переменных цен и фактической поставки Lunar применяется ровно один раз. Reliability не уменьшает BASE и не умножает повторно заданные доли ISRU. Reserve tariffs и CAPEX ценовым шоком не затронуты.</p>
    <p>Prepared-stress — отдельное решение при заранее известных условиях кейса. Новые объёмы размещаются в записанные даты заказов, часто до 2038; нет отмены уже оплаченных обязательств после наблюдения события. Если дедлайн прошёл, этот план нельзя выдавать за доступную реакцию текущего оператора.</p>
    <p>При перепланировании меняются объёмы, но не полномочия ядра: source capacity, storage, service thresholds и инвестиционные бюджеты остаются исходными. Проверены фактический запас на начало каждого года и внутригoдовая ёмкость. Избыточность нового плана в BASE честно отмечена в матрице.</p>
    <p>Сравнение по полям решения и source/year/date сохранено в decision_changes.csv. Это позволяет отделить ухудшение среды от эффекта заранее изменённой стратегии; одна удачная новая цифра не подменяет результат исходного stress test.</p>''')
    chosen=[r for r in lunar['parameter_sensitivity']['points'] if (r['parameter']=='Earth-Core price' and r['value']!=1) or r['parameter']=='lead_time_policy' or (r['parameter']=='zbo_delay_days' and r['value']!=0) or (r['parameter']=='real_discount_rate' and r['value']!=0)]
    pages.append(f'''<h1>06 / Чувствительность и протокол</h1>{table(['Lunar / параметр','Значение','Total, млн','PV, млн','Мин. запас, т'],[[r['parameter'],r['value'],r['total_cost_mln'],r['discounted_cost_mln'],r['min_inventory_t']] for r in chosen])}
    <p>Lead-time bounds взяты из организаторских диапазонов; задержки ZBO и ставки — исследовательские endpoints, не статистические прогнозы. Emergency проверен в трактовках «любой плановый заказ» и «не менее половины годового отбора»; физические потоки при этом не меняются. В контрольном расчёте остаётся консервативный вариант.</p>
    {table(['План','Low shortage','High shortage','Service-only threshold'],[[k,v['sensitivity']['low_high']['low']['shortage_t'],v['sensitivity']['low_high']['high']['shortage_t'],str(v['sensitivity']['service_failure_bracket'])] for k,v in s['strategies'].items()])}
    <p>При низком спросе возможен overflow неизменных заказов. Порог сервиса не является порогом всей исполнимости: reserve/storage проверяются отдельно. Граница смены nominal cost ranking при множителе цены Lunar: <b>{s['price_crossover']['bracket']}</b>; интервал поиска — исследовательский, не прогноз цены.</p>
    <p>Полный STRESS_PROTOCOL.md задаёт входы, сохраняемые условия, метрики и критерий нарушения. Последовательная атрибуция demand → price → delivery → loss check телескопически совпадает с joint stress. Взаимодействия относятся к более позднему шагу; результат зависит от порядка. Combined TEAM demand/price test изолирован от mandatory stress.</p>''')
    pages.append(f'''<h1>07 / Риски, меры и остаточный эффект</h1>{table(['План','Риск','Δ дефицит','Δ cost','Мера: Δ BASE cost','Остаточный дефицит'],riskrows)}
    <p>Для supply-risk исследован дополнительный оплаченный начальный запас; для ценового GEO — предварительное перераспределение отбора Core к доступным New/Flex. Мера считается новым ex-ante решением с полным lead time, не бесплатной отменой ранее оплаченного контракта. Планы мер и residual сохранены в risk_register.</p>
    <pre>TEAM_GEO: условное изменение торговых условий
 → агрегированная цена Earth-Core в выбранном году
 → неизменный план: cost / service / shortage
 → отдельная предварительная диверсификация
 → пересчёт остаточного эффекта и интересов сторон</pre>
    <p>Геосценарий меняет агрегированную цену, не выдаёт её за цену чистого топлива. Страна и точная вероятность не выдумываются; есть возврат BASE. Собственные риски не объединяются с mandatory stress автоматически.</p>
    <h3>После наблюдения сбоя: отдельный Lunar outage 2038</h3>{recourse_table}
    <p>Все старые обязательства сохранены. Только новый Emergency-заказ, не раньше наблюдения + 42 суток; физическая история до прибытия совпадает. Свободный E и объявленный режим недопоставки — TEAM_ASSUMPTION; новое финансирование не гарантировано. Ноль дефицита не снимает остаточные нарушения. Полный протокол — RECOURSE.md; это не универсальная политика и не mandatory stress.</p>''')
    mcrows=[[k,v['monte_carlo']['count'],v['monte_carlo']['service_failure_fraction'],v['monte_carlo_common_year']['service_failure_fraction'],v['monte_carlo']['mean_shortage_t'],v['monte_carlo_common_year']['mean_shortage_t']] for k,v in s['strategies'].items()]
    parties=earth['decision_comparison']['stakeholders']
    pages.append(f'''<h1>08 / Неопределённость и стороны</h1>{table(['План','N','Отказ SL: независ.','Общий фактор','Средний дефицит, независ.','Общий фактор, т'],mcrows)}
    <p>MC — Bernoulli доступности источника на целый год; reliability трактуется как вероятность успеха только в этом исследовании. Сравнены независимые draws и один общий годовой uniform draw при сохранении маргинальных reliabilities. Seed фиксирован; частичные отказы не моделируются. Wilson interval — ошибка выборки при выбранной гипотезе, не достоверность самой гипотезы и не вероятность срыва реальной миссии.</p>
    <h2>Earth: последствия заранее изменённого stress плана</h2>{table(['Сторона / показатель','До','После','Единица'],[[r['party']+' / '+r['metric'],r['before'],r['after'],r['unit']] for r in parties])}
    <p>Критические клиенты не должны терять обязательный сервис из-за уменьшения веса в MCDA. Коммерческие клиенты несут остаточный дефицит при critical-first; оператор отвечает за stock, поставщики за договорный поток, инвестор финансирует расходы. Эти последствия показаны физическими/денежными величинами, а не только итоговым рейтингом.</p>
    <p>MCDA использует раскрытые гипотетические профили пяти сторон, min/max нормировку и sweep веса стоимости. Профили не получены реальным опросом. Практически равные значения нормируются одинаково; infeasible-in-both отмечается независимо от scores. Для paired BASE/prepared-STRESS отдельно сохранён planned_stress_mcda, не смешанный с unchanged-plan analysis.</p>''')
    pages.append(f'''<h1>09 / Проверка и передача</h1>{table(['Проверяемый предмет','Артефакт'],[['Корректность','V01–V10, daily invariants, invalid input, preparation/PV tests'],['Требования PDF','PDF_AUDIT.md: все 20 критериев, source pages, тесты'],['Стресс / развитие','Матрица 2×2, Source-X и 2041 с явной экстраполяцией'],['Оператор','Редакторы контракта, инвестиций, ставки и research copy'],['Переносимость','Plan/project save-open, input CSV, comparison, roadmap, risk register'],['Сдача','Автономный ZIP, README в корне, исходники и результаты']])}
    <pre>bash tools/setup.sh
bash tools/reproduce.sh</pre><p>Вторая команда строит все результаты и HTML-материалы, затем выполняет проверки и reference gate. На текущем upstream gate возвращает ненулевой код из-за отсутствующего документа. Оригинал валидатора не исправлялся ради зелёного статуса. CI имеет отдельные jobs для ядра и upstream.</p>
    <h2>Ограничения, которые остаются</h2><ul><li>Неизвестны точная историческая availability действующих каналов, строительная длительность ZBO и численный смысл «Emergency как основа»; допущения видимы и проверяются.</li><li>Нет калиброванной вероятностной модели отказов и реальных stakeholder preferences.</li><li>Prepared-stress планы не являются гарантированной стратегией для любого будущего спроса и не отменяют совершённые обязательства.</li><li>Квартальные сроки реакции, экономические штрафы и реальная телеметрия не добавлялись как факты.</li></ul>
    <p>Следующие инвестиционные решения требуют подтверждения готовности и договорных условий, а не только пересчёта модели. Внешняя публикация на GitVerse выполняется владельцем проекта; пакет рассчитан на передачу без закрытых API и секретов.</p>
    <p>SHA256 сериализованного summary: <code>{digest(s)}</code>. Проверенные размеры контрольного набора и browser/PDF/clean-run evidence приведены в VERIFICATION.md; результаты воспроизводятся, но PDF metadata времени печати не являются финансовыми данными.</p>''')
    dest=ROOT/'docs'
    (dest/'REPORT.html').write_text(document('Топливный космоконтур 2035 · v0.2',pages),encoding='utf-8')
    one=f'''<h1>BASE, стресс и цена подготовки</h1><p>Две архитектуры, два заранее выбранных плана для каждой. Стоимость в млн постоянных у.е. 2035; подготовка включена в первый год; SL — минимум годовых уровней.</p>{comparison}{delta}<div class="callout">Lunar дешевле на {f(base_saving)} млн в BASE и на {f(prepared_saving)} млн в подготовленном стрессе. Это условное предпочтение при ставке 0%, не гарантия или оптимум. В BASE граница смены выбора по ставке — около {f(100*s['discount_rate_crossover']['bracket'][0])}%.</div><p>Исходный план в стрессе сохранён в сравнении. Redesign требует новых решений до указанных order_day, не отменяет уже оплаченные контракты и не использует повышенные мощности. Запуск подготовленного stress плана в BASE может дать overflow — полная матрица 2×2 экспортирована.</p><p>Три PDF сверены, модельные ограничения и допущения раскрыты. Полный verification gate остаётся красным из-за отсутствующей upstream-ссылки; это не скрыто и не исправлено подставным документом.</p>'''
    (dest/'COMPARISON.html').write_text(document('Одностраничное сравнение · v0.2',[one]),encoding='utf-8')
    write_assets(s, dest)
    (dest/'numbers.json').write_text(json.dumps(s,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print('Generated REPORT (10 pages), COMPARISON (1), PRESENTATION (12 slides) + speaker notes + decision brief, numbers.json from suite output')

if __name__=='__main__':main()
