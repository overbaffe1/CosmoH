"""Human-readable defense assets; every economic number comes from the suite.

HTML/notes need only core dependencies. Editable PPTX: install presentation-requirements.txt.
The presentation is not a second economic model.
"""
import html
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fuel.io import digest
from fuel.decision import decision_brief


def n(value, digits=2):
    return f'{value:,.{digits}f}'.replace(',', ' ').replace('.', ',')


def slides_for(s):
    e, l = (s['strategies'][k] for k in ('earth', 'lunar'))
    if any(v[tag]['violations'] for v in (e,l) for tag in ('base','planned_stress')) or decision_brief(s)['fixed_plans_feasible_in_both']:
        raise ValueError('DEFENSE_NARRATIVE_REVIEW_REQUIRED: control feasibility changed')
    cross = s['discount_rate_crossover']
    rate = sum(cross['bracket'])/2 if cross['bracket'] else None
    risk = next(r for r in l['risks'] if r['risk_id']=='LUNAR_OUTAGE')
    delta = l['decision_comparison']
    party_names = ['Оператор: минимальный запас, т','Критические клиенты: выдано, т',
                   'Коммерческие клиенты: выдано, т','Поставщики: закупка + резерв, млн','Финансирование: PV расходов, млн']
    slides = [
      dict(title='Чтобы миссия не осталась без топлива', kicker='ЗАДАЧА / 2035–2040', seconds=25,
           lines=['Мы — оператор условной «космической заправки».', 'Выбираем поставщиков, запас и инвестиции; проверяем, хватит ли топлива и денег.'],
           takeaway='Не проектируем ракету. Делаем проверяемый инструмент планирования снабжения.',
           notes='Начни без аббревиатур: топливо должно оказаться в нужном месте вовремя. Дешёвый контракт бесполезен, если поставка придёт после миссии. Цель — исполнить ограничения и объяснить цену решения, а не нарисовать самый дешёвый вариант.'),
      dict(title='Пять каналов. Один склад. Две группы клиентов.', kicker='ЦЕПОЧКА ПОСТАВОК', seconds=30,
           lines=['У каналов разные цены, мощности и сроки; часть требует строительства.'], chain=True,
           takeaway='Резерв мощности у поставщика ≠ физическое топливо в баке.',
           notes='Core — ранний долгосрочный заказ; Flex — дороже, но быстрее. New нужно подготовить, ISRU — построить на Луне. Emergency ограничен и не заменяет обычное снабжение. На схеме сроки модельные, месяц = 365/12 суток.'),
      dict(title='Сначала выполнимость. Потом цена.', kicker='КАК УСТРОЕН РАСЧЁТ', seconds=35,
           lines=['Исходные данные → решения и даты → суточный запас → расходы и нарушения.', 'Начальный запас + поставка − потери − выдача = конечный запас.'],
           headers=['Что проверяем','Контроль'], rows=[['Сервис по каждому году','Критический ≥99%; общий ≥97%'],['Запас и договоры','Резерв 45 дней; TOP; сроки; без двойного счёта'],['Инфраструктура','Ёмкость, мощности, CAPEX и фактический ввод']],
           takeaway='Критический спрос — часть общего. Ограничения нельзя спрятать средним за 6 лет.',
           notes='Тонны — агрегированные компоненты топлива; деньги — млн постоянных у.е. 2035. Оплата минимального отбора TOP и отдельная плата резервирования учитываются раздельно. Подготовка уже включена в первый год. Числа CASE_INPUT не изменяем ради красивого результата.'),
      dict(title='В обычных условиях обе архитектуры работают', kicker='BASE / ДВА ИСХОДНЫХ ПЛАНА', seconds=35,
           lines=['Сравниваем на одинаковых данных и при одной реальной ставке: здесь 0%.'],
           headers=['Архитектура','Расходы, млн','Дефицит, т','Нарушения'],
           rows=[['Земная',n(e['base']['total_cost_mln']),'0','0'],['С лунным каналом',n(l['base']['total_cost_mln']),'0','0']],
           takeaway=f"Экономия Lunar: {n(e['base']['total_cost_mln']-l['base']['total_cost_mln'])} млн. Это не прибыль и не доказательство глобального оптимума.",
           notes='Это сравнение двух прозрачных эвристик. Номинальные расходы включают все инвестиции, закупку, резервирование, хранение и OPEX, а не только цену тонны. Ставка 0 — раскрытое допущение, а не рыночная оценка.'),
      dict(title='Но тот же план не выдерживает обязательный стресс', kicker='ПЛАН НЕ МЕНЯЕМ / МЕНЯЕМ СРЕДУ', seconds=35,
           lines=['Применяем только заданные шоки — без удвоения надёжности и без подмешивания high demand.'],
           headers=['Архитектура','Дефицит, т','Мин. общий SL','Нарушения'],
           rows=[[name,n(v['stress']['shortage_t']),n(v['stress']['min_total_service']*100)+'%',str(v['stress']['violations'])] for name,v in [('Земная',e),('Лунная',l)]],
           takeaway='Критические клиенты обслужены ≈100%, но весь спрос — нет. Основной дефицит несут коммерческие клиенты.',
           notes='Не говори «у нас всё хорошо, критический сервис 100%». Общий сервис и резерв нарушены. У лунного плана минимальный коммерческий сервис ещё ниже; он показан в выгрузке. Обязательный стресс известен заранее, но физические сроки никто не отменял.'),
      dict(title='Объясняем причину, а не только показываем красную цифру', kicker='РАЗЛОЖЕНИЕ СТРЕССА / ЛУННЫЙ ПЛАН', seconds=45,
           lines=['Последовательно включаем рост спроса, цены и недопоставку лунного канала.'],
           headers=['Включённый фактор','Добавленный дефицит, т'],
           rows=[[label,n(row['delta_shortage_t'])] for label,row in zip(['Рост спроса','Повышение цен','Недопоставка Lunar'],l['stress_attribution']['steps'][1:4])],
           takeaway=f"Итог: {n(l['stress']['shortage_t'])} т. Цена меняет расходы; сама по себе она не создаёт физический дефицит в фиксированном плане.",
           notes='Это последовательная атрибуция, не единственное причинное разложение: взаимодействия отнесены к более позднему шагу. При повышенном спросе расходы хранения могут снизиться — бак быстрее пустеет; это не улучшение сервиса и не возврат платы за недопоставку.'),
      dict(title='Закрыть дефицит можно — если подготовиться заранее', kicker='НОВОЕ РЕШЕНИЕ / ТЕ ЖЕ ЛИМИТЫ', seconds=35,
           lines=['Отдельные планы сформированы до дедлайнов заказов. Уже оплаченные контракты не отменяются.'],
           headers=['Архитектура','Расходы в стрессе, млн','Доплата к старому стрессу','Дефицит / нарушения'],
           rows=[[name,n(v['planned_stress']['total_cost_mln']),n(v['decision_comparison']['incremental_stress_cost_mln']),'0 / 0'] for name,v in [('Земная',e),('Лунная',l)]],
           takeaway='Это НЕ универсальный план: в BASE подготовленные варианты дают 2 / 3 нарушения переполнения.',
           notes='Не сравнивай новые стрессовые расходы с обычным BASE как чистую цену защиты: там разный спрос и среда. Здесь доплата вычислена в одной стрессовой среде. Полная матрица 2×2 сохранена. Свободного переключения после события не обещаем.'),
      dict(title='Выбор зависит от цены ранних денег', kicker='УПРАВЛЕНЧЕСКОЕ РЕШЕНИЕ / BASE', seconds=35,
           lines=['Сначала исключаем невыполнимые планы. Затем сравниваем приведённые расходы допустимых.'],
           headers=['Реальная ставка','PV Earth, млн','PV Lunar, млн','Дешевле'],
           rows=[[n(r['rate']*100,0)+'%',n(r['earth_pv_mln']),n(r['lunar_pv_mln']),'Lunar' if r['lunar_minus_earth_mln']<0 else 'Earth'] for r in cross['samples']],
           takeaway=(f'Граница в исследованном интервале: около {n(rate*100)}%. Не выбираем Луну «потому что космос».' if rate is not None else 'В исследованном интервале граница не заключена между концами; универсальный порог не заявляем.'),
           notes='Для контрольных денежных потоков при 0 и 5% Lunar дешевле, при 10% — Earth. Более ранние инвестиции меняют предпочтение. Это не ставка рынка, не доходность проекта и не правило для любых других контрактов. При непрохождении ограничений низкая цена не даёт права рекомендовать план.'),
      dict(title='Собственный риск и мера: улучшение не равно устранению', kicker='ВНЕ ОБЯЗАТЕЛЬНОГО СТРЕССА', seconds=35,
           lines=[f"Событие: {risk['period']} — годовая недопоставка Lunar в отдельном TEAM-сценарии.", 'Мера: дополнительный оплаченный предстартовый запас. Точная вероятность не заявляется.'],
           headers=['Без меры: дефицит, т','Премия меры в BASE, млн','После меры: дефицит, т'],
           rows=[[n(risk['result_summary']['shortage_t']),n(risk['mitigation_baseline_cost_mln']),n(risk['residual_consequence']['shortage_t'])]],
           takeaway='Остаточный риск остаётся. Ответственный за производственный сбой — оператор производства; запас обеспечивает оператор узла.',
           notes='Реестр содержит причину, период, параметр, владельца и зависимости. Для ценового геориска мера другая — предварительная диверсификация, а не бессмысленное лечение цены дополнительным запасом. MC — исследовательская модель, не доказательство реальной вероятности срыва.'),
      dict(title='Кто выигрывает и кто оплачивает защиту', kicker='СТОРОНЫ / ЛУННЫЙ ПЛАН В СТРЕССЕ', seconds=40,
           lines=['Сравнение исходного и заранее подготовленного решения; обязательный сервис не торгуется весами MCDA.'],
           headers=['Сторона и показатель','До','После'],
           rows=[[name,n(r['before']),n(r['after'])] for name,r in zip(party_names,delta['stakeholders'])],
           takeaway=f"Финансирующая сторона добавляет {n(delta['incremental_stress_cost_mln'])} млн; коммерческим клиентам возвращаются {n(delta['avoided_stress_shortage_t'])} т.",
           notes='Это распределение последствий, а не доказанная готовность инвестора оплатить проект. Платежи поставщикам — не их прибыль. При нехватке денег нельзя просто ухудшить обязательный критический сервис или снять ограничения.'),
      dict(title='Демонстрация: от решения до проверяемого файла', kicker='ОПЕРАТОР / ЖИВАЯ ДЕМОНСТРАЦИЯ', seconds=40,
           lines=['1. Исходный Lunar: BASE → STRESS — видны дефицит и правила.', '2. Подготовленный Lunar: STRESS — ноль дефицита и нарушений.', '3. Сохранить проект → открыть → выгрузить результат.'],
           takeaway='Резервный путь: сохранённые CSV/JSON и PDF. Сеть и красивые слайды не заменяют ядро.',
           notes='Сервер должен быть уже запущен. Не набирай код на сцене. Если UI не открылся за 10 секунд, показывай заранее созданный экспорт с тем же plan_id. На дополнительные вопросы — изменить заказ, ставку или геосценарий и пересчитать.'),
      dict(title='Наш результат — проверяемый выбор, а не обещание', kicker='ВЫВОД / ЧЕСТНАЯ ГРАНИЦА', seconds=30,
           lines=['Работающий планировщик, контрольные примеры и воспроизводимые результаты.', 'Условный выбор по среде и ставке; инвестиции — только после подтверждения сроков и финансирования.', 'Из четырёх готовых планов ни один не проходит обе среды одновременно.'],
           takeaway='Внешний reference gate заблокирован отсутствующей upstream-ссылкой. Свои проверки отделены; исходники организатора не исправлены.',
           notes='Заверши одной фразой: оператор видит цену и последствия решения до того, как возьмёт обязательства. Это учебная модель, не управление реальными баками; нет глобального оптимума, откалиброванных отказов или автоматической реакции после срыва. Готов отвечать по каждому числу и показать исходный файл.')
    ]
    # Visuals retain raw suite values; formatting is presentation only.
    visuals = {
      0: {'type':'cover'}, 1: {'type':'network'},
      3: {'type':'cards','items':[{'label':'Земная архитектура','value':e['base']['total_cost_mln'],'unit':'млн у.е. / BASE'}, {'label':'С лунным каналом','value':l['base']['total_cost_mln'],'unit':'млн у.е. / BASE'}]},
      4: {'type':'bars','unit':'т дефицита','items':[{'label':'Земная','value':e['stress']['shortage_t']},{'label':'Лунная','value':l['stress']['shortage_t']}]},
      5: {'type':'bars','unit':'т дополнительного дефицита','items':[{'label':label,'value':row['delta_shortage_t']} for label,row in zip(['Рост спроса','Повышение цен','Недопоставка Lunar'],l['stress_attribution']['steps'][1:4])]},
      6: {'type':'cards','items':[{'label':name,'value':v['planned_stress']['total_cost_mln'],'unit':'млн у.е. / подготовленный STRESS','detail':'Доплата: '+n(v['decision_comparison']['incremental_stress_cost_mln'])+' млн · дефицит 0 · нарушений 0'} for name,v in [('Земная',e),('Лунная',l)]]},
      7: {'type':'rates','root':rate,'points':[{'rate':i/200,'difference':sum(r['total_mln']/(1+i/200)**(r['year']-l['costs_base'][0]['year']+1) for r in l['costs_base'])-sum(r['total_mln']/(1+i/200)**(r['year']-e['costs_base'][0]['year']+1) for r in e['costs_base'])} for i in range(21)]},
      9: {'type':'cards','items':[{'label':'Коммерческие потребители','value':delta['avoided_stress_shortage_t'],'unit':'т дополнительного снабжения','detail':'Критический сервис не ухудшается'}, {'label':'Финансирующая сторона','value':delta['incremental_stress_cost_mln'],'unit':'млн у.е. дополнительного финансирования','detail':'Платежи поставщикам — не их прибыль'}]},
      10: {'type':'demo'}, 11: {'type':'closing'}
    }
    for i,visual in visuals.items():slides[i]['visual']=visual
    if 'recourse' in s:
        rows=s['recourse']
        slides[8].update(title='42 дня, которые нельзя обойти', kicker='ПОСЛЕ НАБЛЮДЕНИЯ / ОТДЕЛЬНЫЙ СБОЙ LUNAR',
            lines=['Все исходные контракты и инвестиции зафиксированы. Добавляем только новый Emergency-заказ.', 'Сбой в 2038; ползунок меняет задержку наблюдения, не момент начала сбоя.'],
            headers=['Когда узнали','Заказ E, т','Осталось дефицита, т','Нарушения'],
            rows=[[str(r['observed_after_days'])+' дней',n(r['added_order_t']),n(r['after']['shortage_t']),str(r['after']['violations'])] for r in rows],
            visual={'type':'bars','unit':'т остаточного дефицита','items':[{'label':'Сразу' if r['observed_after_days']==0 else '+'+str(r['observed_after_days'])+' дней','value':r['after']['shortage_t'],'detail':str(r['after']['violations'])+' наруш.'} for r in rows]},
            takeaway=f"Сразу: {n(rows[0]['before']['shortage_t'])} → {n(rows[0]['after']['shortage_t'])} т, но остаются {rows[0]['after']['violations']} нарушения. Доплата {n(rows[0]['incremental_cost_mln'])} млн.",
            notes='Сбой отдельный, не mandatory stress. После сообщения о недопоставке новые физические поставки возможны не раньше 42 дней. Проверили совпадение всей истории до прибытия и сохранение всех старых решений. Покупаем минимум объявленного остатка потери, доступной доли мощности E и лимита оператора. Ни оптимизации по будущему результату, ни отмены оплаты Lunar. Свободный E по контрольному тарифу — TEAM-допущение. При позднем наблюдении дефицит остаётся; при раннем нулевой дефицит не отменяет нарушения резерва.')
    slides[10]['lines']=['Откройте сайт и запустите демонстрацию: BASE → STRESS → подготовка → обратная проверка.', 'Меняйте год на карте и задержку наблюдения сбоя. Сохраняйте реальный расчёт, не скриншот.']
    slides[10]['notes']='Главная / — наглядный сценарный центр. Подробный редактор сохранён в /planner. Для показа после четырёх шагов перейдите к реакции на сбой и сравните задержки 0 и 90 дней. JSON содержит оба полных результата и планы. Если сервер недоступен, честно переходите к сохранённому экспорту.'
    slides[11]['notes']=slides[11]['notes'].replace('или автоматической реакции после срыва','или универсальной политики после срыва; ограниченный Emergency-эксперимент показан отдельно')
    return slides



CHAIN_SVG = '''<svg xmlns="http://www.w3.org/2000/svg" width="1100" height="270" viewBox="0 0 1100 270" role="img" aria-label="Схема источники — узел — потребители">
<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0 0L8 4L0 8" fill="#29856a"/></marker></defs>
<g fill="#eef5f1" stroke="#bfd7cb"><rect x="1" y="1" width="345" height="267" rx="16"/><rect x="402" y="35" width="282" height="198" rx="16"/><rect x="740" y="55" width="358" height="158" rx="16"/></g>
<g stroke="#29856a" stroke-width="4" marker-end="url(#arrow)"><path d="M347 134H393"/><path d="M685 134H732"/></g>
<g font-family="Arial,sans-serif" font-size="19" fill="#173d37"><text x="18" y="34" font-weight="bold">Источники / сроки доставки</text><text x="18" y="75">A · Core: 12 месяцев</text><text x="18" y="113">B · Flex: 4 месяца</text><text x="18" y="151">C · New: 18–24 мес.; нужен ввод</text><text x="18" y="189">D · Lunar: 1–2 мес. после ввода</text><text x="18" y="227">E · Emergency: 6 недель</text><text x="423" y="83" font-weight="bold">Орбитальный узел</text><text x="423" y="126">Хранение и потери</text><text x="423" y="163">Физический резерв</text><text x="423" y="200">Доступная ёмкость</text><text x="761" y="96" font-weight="bold">Потребители</text><text x="761" y="141">Критические — первыми</text><text x="761" y="183">Коммерческие — остаток</text></g></svg>'''


def write_assets(summary, dest=None):
    dest = Path(dest or ROOT/'docs');dest.mkdir(parents=True, exist_ok=True)
    slides = slides_for(summary)
    from tools.deck_design import render_deck
    (dest/'PRESENTATION.html').write_text(render_deck(slides),encoding='utf-8')
    (dest/'SUPPLY_CHAIN.svg').write_text(CHAIN_SVG,encoding='utf-8')
    notes=['# Слова к слайдам — для выступающего, не для чтения с экрана',
           '\nРепетиционная версия на 7 минут, не официальный регламент. Уточните лимит времени у организаторов. '+
           'Вопросы и развёрнутый показ интерфейса — отдельно. При лимите 5 минут сокращайте пояснения, не скрывайте результаты стресса.',
           '\nЧисла и слайды генерируются из одного suite. SHA256 summary: `'+digest(summary)+'`.\n']
    for i,slide in enumerate(slides,1):
        notes.append(f'## {i}. {slide["title"]} — {slide["seconds"]} секунд\n\n{slide["notes"]}\n')
    (dest/'SPEAKER_NOTES.md').write_text('\n'.join(notes),encoding='utf-8')
    brief=decision_brief(summary)
    (dest/'DECISION_BRIEF.json').write_text(json.dumps(brief,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    (dest/'PRESENTATION_DATA.json').write_text(json.dumps({'summary_sha256':digest(summary),'slides':slides},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return slides


def write_pptx(slides, dest=None):
    from tools.deck_design import render_pptx
    render_pptx(slides, dest or ROOT/'docs/PRESENTATION.pptx')


if __name__=='__main__':
    summary=json.loads((ROOT/'results/summary.json').read_text())
    slides=write_assets(summary)
    if '--pptx' in sys.argv:write_pptx(slides)
    print('Built 12-slide defense, supply-chain diagram, speaker notes and decision evidence')
