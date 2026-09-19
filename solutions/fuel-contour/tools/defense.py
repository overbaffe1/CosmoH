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
    return [
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


CHAIN_SVG = '''<svg xmlns="http://www.w3.org/2000/svg" width="1100" height="270" viewBox="0 0 1100 270" role="img" aria-label="Схема источники — узел — потребители">
<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0 0L8 4L0 8" fill="#29856a"/></marker></defs>
<g fill="#eef5f1" stroke="#bfd7cb"><rect x="1" y="1" width="345" height="267" rx="16"/><rect x="402" y="35" width="282" height="198" rx="16"/><rect x="740" y="55" width="358" height="158" rx="16"/></g>
<g stroke="#29856a" stroke-width="4" marker-end="url(#arrow)"><path d="M347 134H393"/><path d="M685 134H732"/></g>
<g font-family="Arial,sans-serif" font-size="19" fill="#173d37"><text x="18" y="34" font-weight="bold">Источники / сроки доставки</text><text x="18" y="75">A · Core: 12 месяцев</text><text x="18" y="113">B · Flex: 4 месяца</text><text x="18" y="151">C · New: 18–24 мес.; нужен ввод</text><text x="18" y="189">D · Lunar: 1–2 мес. после ввода</text><text x="18" y="227">E · Emergency: 2–6 недель</text><text x="423" y="83" font-weight="bold">Орбитальный узел</text><text x="423" y="126">Хранение и потери</text><text x="423" y="163">Физический резерв</text><text x="423" y="200">Доступная ёмкость</text><text x="761" y="96" font-weight="bold">Потребители</text><text x="761" y="141">Критические — первыми</text><text x="761" y="183">Коммерческие — остаток</text></g></svg>'''

STYLE = '''@page{size:320mm 180mm;margin:0}*{box-sizing:border-box}body{margin:0;background:#dce5e0;color:#17352f;font-family:Arial,sans-serif}article{width:320mm;height:180mm;padding:13mm 17mm 16mm;position:relative;background:#fbfcf9;margin:18px auto;break-after:page;overflow:hidden}article:last-child{break-after:auto}.kicker{font-size:13px;letter-spacing:2px;color:#2c8266;font-weight:bold}h1{font-size:35px;line-height:1.15;margin:13px 0 20px;max-width:1080px}p{font-size:22px;line-height:1.35;margin:8px 0}.content{height:330px}table{border-collapse:collapse;width:100%;font-size:19px;margin-top:20px}th{text-align:left;background:#173d37;color:white}td,th{padding:10px 13px;border-bottom:1px solid #ccdcd3}tbody tr:nth-child(even){background:#edf4ef}.takeaway{position:absolute;bottom:22mm;left:17mm;right:17mm;padding:12px 16px;border-left:5px solid #2c8266;background:#e6f1e9;font-size:19px;line-height:1.3}footer{position:absolute;bottom:8mm;left:17mm;right:17mm;font-size:12px;color:#577168;border-top:1px solid #ccdad1;padding-top:9px}svg{width:100%;height:245px;margin-top:15px}@media print{article{margin:0}}'''


def write_assets(summary, dest=None):
    dest = Path(dest or ROOT/'docs');dest.mkdir(parents=True, exist_ok=True)
    slides = slides_for(summary)
    parts = []
    for i, slide in enumerate(slides, 1):
        body=''.join('<p>'+html.escape(line)+'</p>' for line in slide['lines'])
        if slide.get('chain'):body+=CHAIN_SVG
        if slide.get('rows'):
            body+='<table><thead><tr>'+''.join('<th>'+html.escape(x)+'</th>' for x in slide['headers'])+'</tr></thead><tbody>'
            body+=''.join('<tr>'+''.join('<td>'+html.escape(str(x))+'</td>' for x in row)+'</tr>' for row in slide['rows'])+'</tbody></table>'
        parts.append(f'<article><div class="kicker">{html.escape(slide["kicker"])}</div><h1>{html.escape(slide["title"])}</h1><div class="content">{body}</div><div class="takeaway">{html.escape(slide["takeaway"])}</div><footer>КОСМОКОНТУР / TEAM_ANALYSIS · Млн постоянных у.е. 2035, тонны · Страница {i} / {len(slides)}</footer></article>')
    (dest/'PRESENTATION.html').write_text('<!doctype html><html lang="ru"><meta charset="utf-8"><title>Космоконтур — защита</title><style>'+STYLE+'</style><body>'+''.join(parts)+'</body></html>',encoding='utf-8')
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
    from pptx import Presentation
    from pptx.util import Inches, Pt
    from pptx.dml.color import RGBColor
    from pptx.enum.shapes import MSO_SHAPE
    prs=Presentation();prs.slide_width=Inches(13.333);prs.slide_height=Inches(7.5)
    def text(slide,x,y,w,h,value,size=20,color='17352F',bold=False):
        shape=slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
        frame=shape.text_frame;frame.word_wrap=True
        for i,line in enumerate(value.split('\n')):
            p=frame.paragraphs[0] if i==0 else frame.add_paragraph()
            p.text=line;p.font.name='Arial';p.font.size=Pt(size);p.font.bold=bold;p.font.color.rgb=RGBColor.from_string(color)
        return shape
    for i,data in enumerate(slides,1):
        slide=prs.slides.add_slide(prs.slide_layouts[6]);slide.background.fill.solid();slide.background.fill.fore_color.rgb=RGBColor.from_string('FBFCF9')
        text(slide,.65,.28,12,.3,data['kicker'],11,'2C8266',True)
        text(slide,.65,.77,12,1.0,data['title'],28,bold=True)
        text(slide,.65,1.9,12,1.2,'\n'.join(data['lines']),18)
        if data.get('chain'):
            for x,w,label in [(.7,4.25,'ИСТОЧНИКИ\nCore · 12 мес. / Flex · 4 мес.\nNew · 18–24 мес.; нужен ввод\nLunar · 1–2 мес. после ввода\nEmergency · 2–6 недель'),(5.2,3.2,'УЗЕЛ\nЁмкость и потери\nФизический запас\nРезерв'),(8.7,3.9,'ПОТРЕБИТЕЛИ\nКритические — первыми\nКоммерческие — остаток')]:
                shape=slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,Inches(x), Inches(3.15), Inches(w), Inches(2.6))
                shape.fill.solid();shape.fill.fore_color.rgb=RGBColor.from_string('E6F1E9');shape.line.fill.background()
                text(slide,x+.1,3.35,w-.2,2.3,label,17)
            text(slide,4.9,4,.4,.6,'→',22);text(slide,8.35,4,.4,.6,'→',22)
        if data.get('rows'):
            rows=[data['headers']]+data['rows'];cols=len(rows[0])
            table=slide.shapes.add_table(len(rows),cols,Inches(.7),Inches(3.05),Inches(11.95),Inches(.47*len(rows))).table
            for ri,row in enumerate(rows):
                for ci,value in enumerate(row):
                    cell=table.cell(ri,ci);cell.text=str(value);cell.margin_left=Inches(.10);cell.margin_right=Inches(.08)
                    cell.fill.solid();cell.fill.fore_color.rgb=RGBColor.from_string('173D37' if ri==0 else 'EDF4EF' if ri%2==0 else 'FBFCF9')
                    for p in cell.text_frame.paragraphs:
                        p.font.name='Arial';p.font.size=Pt(15 if cols>=4 else 16);p.font.bold=ri==0
                        p.font.color.rgb=RGBColor.from_string('FFFFFF' if ri==0 else '17352F')
            if i==10:
                table.columns[0].width=Inches(6);table.columns[1].width=Inches(2.975);table.columns[2].width=Inches(2.975)
        text(slide,.7,6.05,11.95,.88,data['takeaway'],16,'21664F',True)
        text(slide,.7,7.05,12,.3,f'КОСМОКОНТУР · TEAM_ANALYSIS · Млн постоянных у.е. 2035 / тонны                         {i} / {len(slides)}',10,'577168')
        slide.notes_slide.notes_text_frame.text=data['notes']
    prs.save(str(dest or ROOT/'docs/PRESENTATION.pptx'))


if __name__=='__main__':
    summary=json.loads((ROOT/'results/summary.json').read_text())
    slides=write_assets(summary)
    if '--pptx' in sys.argv:write_pptx(slides)
    print('Built 12-slide defense, supply-chain diagram, speaker notes and decision evidence')
