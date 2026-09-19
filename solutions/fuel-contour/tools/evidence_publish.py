"""Turn committed, traceable observations into readable proof pages and slide visuals."""
import base64
import hashlib
import html
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from fuel.io import digest


def read_evidence(summary):
    folder=ROOT/'docs/evidence'
    grid=json.loads((folder/'response-grid.json').read_text())
    measured=json.loads((folder/'browser-measurements.json').read_text())
    if grid['summary_sha256']!=digest(summary):raise ValueError('STALE_GRID: run tools/evidence.py after suite')
    for rel,expected in measured['source_hashes'].items():
        if hashlib.sha256((ROOT/rel).read_bytes()).hexdigest()!=expected:
            raise ValueError('STALE_BROWSER_MEASUREMENT: recapture tools/demo-evidence.cjs for '+rel)
    for example in measured['examples']:
        if hashlib.sha256((folder/example['image']).read_bytes()).hexdigest()!=example['sha256']:
            raise ValueError('SCREENSHOT_DIGEST_MISMATCH')
    return grid,measured


def enrich_slides(slides,summary):
    grid,m=read_evidence(summary)
    early=next(r for r in grid['rows'] if r['delivery_share']==.5 and r['observed_after_days']==90)['after']
    late=next(r for r in grid['rows'] if r['delivery_share']==.5 and r['observed_after_days']==180)['after']
    slides[8].update(title='Помощь сработает не при любом сбое.',
        lines=['35 сочетаний · исходный Lunar · отдельный сбой 2038 · аварийная поставка через 42 дня.'],
        visual={'type':'heatmap','study':grid},
        takeaway=f"Исполнение 50%: через 90 дней — {early['shortage_t']:.0f} т / {early['violations']} наруш.; через 180 — {late['shortage_t']:.0f} т, но {late['violations']} нарушения.",
        notes='ЧТО СКАЗАТЬ\nМы проверили не один удачный пример, а сетку тяжести сбоя и задержки наблюдения. В каждой клетке — остаточная нехватка и число нарушений. При исполнении половины заказа наблюдение через 90 дней даёт выполнимый результат, через 180 — уже нет, хотя дефицит остаётся нулевым. Значит, запас и сервис — разные проверки. Последняя строка без сбоя — контроль, а не успешное спасение.\n\nЕСЛИ СПРОСЯТ / ГРАНИЦЫ\nФизическая доля исполнения от нуля до единицы, шаг 25% — исследовательская сетка, не прогноз вероятности. Между точками границу не доказали. Действует прежняя ограниченная политика Emergency, без отмены договоров и без знания будущего результата. '+slides[8]['notes'].split('ЕСЛИ СПРОСЯТ / ГРАНИЦЫ')[-1].strip())
    slides[10].update(title='Не макет. Один клик — другой результат.',
        lines=['Реальные снимки: тот же лунный план в обычных условиях и обязательном стрессе.'],
        visual={'type':'demo_proof','measurement':m},
        takeaway='15 тёплых повторов после 3 прогревов · один локальный браузер и сервер · не SLA и не тест нагрузки.',
        notes=slides[10]['notes']+'\n\nЗамер отдельно: переключение использует кеш уже рассчитанных пресетов. POST /api/recourse заново считает до/после и возвращает JSON. Время включает декодирование JSON, но не Интернет-путь посетителя. Медиана и p95 — описательные статистики 15 повторов, не доверительный интервал.')
    return slides


def image(name):
    return 'data:image/png;base64,'+base64.b64encode((ROOT/'docs/evidence'/name).read_bytes()).decode()


def timing_svg(measured):
    import math
    ts=measured['timings'];limit=math.ceil(max(t['max_ms'] for t in ts.values())/50)*50 or 50
    x=lambda value:240+value/limit*805
    p=['<svg xmlns="http://www.w3.org/2000/svg" width="1100" height="270" viewBox="0 0 1100 270" role="img" aria-label="Все 15 наблюдений времени двух операций, медиана и p95"><rect width="1100" height="270" rx="14" fill="#f0f5ef"/><g font-family="Arial,sans-serif" fill="#294b3d"><text x="24" y="30" font-size="15">Каждая точка — один повтор · сплошная метка — медиана · пунктир — p95</text>']
    for i in range(5):
        value=limit*i/4;p.append(f'<line x1="{x(value)}" x2="{x(value)}" y1="55" y2="205" stroke="#cfdbd1"/><text x="{x(value)}" y="235" font-size="13" text-anchor="middle">{value:g} мс</text>')
    for index,(key,label) in enumerate([('switch','Кешированный вид'),('recourse','Новый расчёт + JSON')]):
        t=ts[key];y=95+index*90;color='#287652' if index==0 else '#365f88'
        p.append(f'<text x="24" y="{y+5}" font-size="17">{label}</text>')
        for j,value in enumerate(t['samples_ms']):p.append(f'<circle cx="{x(value)}" cy="{y+((j%5)-2)*5}" r="4" fill="{color}"><title>{value:.6f} ms</title></circle>')
        p.append(f'<line x1="{x(t["median_ms"])}" x2="{x(t["median_ms"])}" y1="{y-25}" y2="{y+25}" stroke="#173f2c" stroke-width="2"/><line x1="{x(t["p95_ms"])}" x2="{x(t["p95_ms"])}" y1="{y-25}" y2="{y+25}" stroke="#976432" stroke-width="2" stroke-dasharray="4 3"/>')
    return ''.join(p)+'</g></svg>'


def publish():
    summary=json.loads((ROOT/'results/summary.json').read_text());grid,m=read_evidence(summary)
    names={'base':'01 · Обычные условия','stress':'02 · Те же заказы в стрессе','prepared':'03 · Подготовились заранее','prepared_base':'04 · А если сбоя не будет?'}
    (ROOT/'docs/evidence/timings.svg').write_text(timing_svg(m))
    t=m['timings'];fmt=lambda v:f'{v:.1f}'.replace('.',',')
    rows=''.join(f'<tr><td>{label}</td><td>{fmt(t[key]["median_ms"])} мс</td><td>{fmt(t[key]["p95_ms"])} мс</td></tr>' for key,label in [('switch','Переключение кешированного вида'),('recourse','Новый расчёт реакции + JSON')])
    cards=''.join(f'<section class="example"><h3>{names[e["mode"]]}</h3><img src="{image(e["image"])}" alt="{html.escape(names[e["mode"]])}: стоимость, дефицит, сервис, нарушения"><p>Дефицит {e["summary"]["shortage_t"]:.2f} т · {e["summary"]["violations"]} нарушений. Полные расходы и входы доступны в выгрузке.</p><a href="/?architecture=lunar&amp;mode={e["mode"]}&amp;year=2038">Открыть этот контрольный вид ↗</a></section>' for e in m['examples'])
    grid_table='<details><summary>Числа и доплата: все 35 опытов</summary><div class="scroll"><table><thead><tr>'+''.join('<th scope="col">'+v+'</th>' for v in ['Исполнено Lunar','Узнали через, дней','Дефицит до, т','После, т','Нарушения после','Доплата, млн'])+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+v+'</td>' for v in [f'{r["delivery_share"]*100:g}%',str(r['observed_after_days']),f'{r["before"]["shortage_t"]:.2f}',f'{r["after"]["shortage_t"]:.2f}',str(r['after']['violations']),f'{r["incremental_cost_mln"]:.2f}'])+'</tr>' for r in grid['rows'])+'</tbody></table></div></details>'
    css='''*{box-sizing:border-box}body{margin:0;background:#f4f7f2;color:#193d32;font:16px/1.65 system-ui,Arial,sans-serif}main{max-width:1200px;margin:auto;padding:48px 30px}nav{display:flex;gap:20px;flex-wrap:wrap;font-size:13px}a{color:#196d51}h1{font-size:clamp(34px,5vw,64px);line-height:1.08;letter-spacing:-2px;font-weight:500;margin:32px 0 24px}h2{font-size:30px;font-weight:500;margin:12px 0}h3{font-size:20px;font-weight:500}p{color:#506b5e}.eyebrow{font-size:12px;letter-spacing:2px;color:#33755a}.lead{font-size:20px;max-width:800px}.block{border-top:1px solid #c7d7cd;margin-top:45px;padding-top:28px}.callout{background:#e4efdf;border-left:3px solid #397752;padding:18px 24px;border-radius:0 10px 10px 0}.examples{display:grid;gap:20px}.example{background:white;padding:22px;border:1px solid #d5e3d8;border-radius:14px}.example img{width:100%;height:auto;display:block}.example p,.small{font-size:13px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:30px}svg{width:100%;height:auto}table{border-collapse:collapse;width:100%;font-size:14px}td,th{padding:15px 8px;border-bottom:1px solid #ccdbd0;text-align:left}th{font-size:12px}footer{font-size:12px;color:#587265;margin-top:40px}code{overflow-wrap:anywhere}.response{width:100%;max-width:760px;border:1px solid #cbdcd1;border-radius:12px}@media(max-width:700px){main{padding:28px 16px}.grid{grid-template-columns:1fr}.scroll{overflow:auto}.scroll svg{min-width:800px}h2{font-size:25px}.example{padding:14px}table{font-size:12px}}'''
    page=f'''<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Космоконтур · доказательства</title><style>{css}</style><body><main><nav><a href="/">← Сценарный центр</a><a href="/presentation">12 слайдов ↗</a></nav><p class="eyebrow">ПРОВЕРЯЕМ, А НЕ ОБЕЩАЕМ</p><h1>От красивой цифры<br>к проверяемому результату.</h1><p class="lead">Реальные снимки приложения, карта границ реакции и измерения интерфейса. Каждый блок отвечает на конкретный вопрос жюри.</p><div class="callout">Это сохранённый протокол, не живой мониторинг. Для пересчёта откройте сценарный центр. Файлы и команды воспроизведения — в Git.</div><section class="block"><span class="eyebrow">КРИТЕРИИ 11 / 13 / 15 / 16</span><h2>Когда аварийной поставки недостаточно?</h2><p>Один план. Один годовой сбой Lunar. Доля исполнения меняется от 0 до 100%, задержка наблюдения — от 0 до 330 дней. В каждой клетке остаточный дефицит и все нарушения.</p><div class="scroll">{(ROOT/'docs/evidence/response-grid.svg').read_text()}</div><div class="callout"><b>Ноль дефицита ≠ выполнимость.</b> Исполнение 50%: наблюдение через 90 дней — все проверки пройдены; через 180 — два нарушения резерва. Значения между узлами сетки не исследованы.</div><p class="small">Не обязательный стресс, не вероятность аварии. 100% — отсутствие сбоя. Старые договоры сохранены; свободный Emergency-контракт и финансирование — допущения.</p>{grid_table}</section><section class="block"><span class="eyebrow">КРИТЕРИИ 4 / 10 / 19</span><h2>Четыре режима. Ни одного скрытого провала.</h2><p>Снимки получены Chromium автоматически. Показатели сверены с API; при захвате значения не подменялись.</p><div class="examples">{cards}</div></section><section class="block"><span class="eyebrow">ОТДЕЛЬНЫЙ ОПЫТ / РЕАКЦИЯ ПОСЛЕ НАБЛЮДЕНИЯ</span><h2>Узнали через 90 дней — история уже не отменяется.</h2><img class="response" src="{image('ui-response-90.png')}" alt="Результат реакции с задержкой 90 дней, с остаточным дефицитом и нарушениями"></section><section class="block"><span class="eyebrow">КРИТЕРИЙ 19 / ИЗМЕРЕНИЯ, НЕ ОБЕЩАНИЕ SLA</span><h2>Насколько быстро отвечает этот стенд?</h2>{timing_svg(m)}<div class="grid"><table><thead><tr><th>Операция</th><th>Медиана</th><th>p95</th></tr></thead><tbody>{rows}</tbody></table><div><p>По 15 последовательных повторов после 3 прогревов. Переключение — DOM-клик и два кадра; пересчёт — HTTP-запрос до декодирования JSON.</p><p class="small">Chromium {html.escape(m['environment']['browser'])}; {html.escape(m['environment']['cpu'])}; Linux; 1440×1080. Локальный браузер и сервер. Сеть посетителя, холодный запуск, параллельная нагрузка и гарантии времени не измерены. p95 при n=15 методом nearest rank совпадает с максимумом.</p></div></div></section><footer>Учебная модель. Самопроверка не равна оценке жюри. Внешний reference gate остаётся заблокирован отсутствующим ERRATA_AND_PROVENANCE.md. <a href="https://github.com/overbaffe1/CosmoH/tree/arena/01a0b7c5-cosmoh/solutions/fuel-contour/docs/evidence">Снимки и исходные файлы на GitHub ↗</a>.</footer></main></body></html>'''
    (ROOT/'docs/EVIDENCE.html').write_text(page)
    md=['# Замеры и примеры работы сайта','\nСнимки — из работающего Chromium, не макеты. Для просмотра галереи запустите `/evidence` или откройте [автономный HTML](EVIDENCE.html).','\n## Карта границ реакции','\n![Карта реакции](evidence/response-grid.svg)','\n[CSV](evidence/response-grid.csv) · [Полный JSON](evidence/response-grid.json). 35 точек, не вероятность и не непрерывная граница. Старые обязательства сохраняются. 100% исполнения — контроль без сбоя, не успешная мера.','\n## Реальный интерфейс']
    for e in m['examples']:md+=[f'\n### {names[e["mode"]]}',f'\n![{names[e["mode"]]}](evidence/{e["image"]})']
    md+=['\n## Тёплый локальный прогон','\n![Все замеры времени](evidence/timings.svg)','\n| Операция | Медиана, мс | p95, мс |\n|---|---:|---:|']
    for key,label in [('switch','Кешированный вид'),('recourse','Новый расчёт реакции + JSON')]:md.append(f'| {label} | {fmt(t[key]["median_ms"])} | {fmt(t[key]["p95_ms"])} |')
    md+=[f'\nChromium {m["environment"]["browser"]}; {m["environment"]["cpu"]}; {m["environment"]["platform"]} / {m["environment"]["arch"]}; viewport 1440×1080.','\n15 измерений после 3 прогревов, по одной операции. UI: программный DOM-клик → 2 кадра. API: HTTP POST → JSON decode. Не Интернет-задержка пользователя, не холодный запуск, не конкурентная нагрузка, не SLA. Перцентили — nearest rank; при n=15 p95 = максимум. Небольшая выборка, общего ускорения относительно прошлой версии не заявляем.','\n[Сырые измерения, окружение, хеши кода и скриншотов](evidence/browser-measurements.json). SHA256 файлов точнее идентифицируют проверенный код, чем source_revision, который мог предшествовать незакоммиченным изменениям. Повторный замер даст другие времена — их не подгонять под этот снимок.','\n## Как воспроизвести','\n```bash\n.venv/bin/python -m fuel.cli suite --output results\n.venv/bin/python tools/evidence.py\n# Сервер должен быть запущен; Playwright/Chromium — RUNBOOK\nNODE_PATH=/tmp/fuel-browser/node_modules node tools/demo-evidence.cjs\n.venv/bin/python tools/evidence_publish.py\n.venv/bin/python tools/defense.py --pptx\n```','\nДля проверки баланса вручную: [один день с настоящими числами](evidence/BALANCE.md). Не путать тёплый кеш витрины с новым запуском экономической модели.']
    (ROOT/'docs/DEMO_EVIDENCE.md').write_text('\n'.join(md)+'\n')
    print('Published evidence gallery and measurement protocol')

if __name__=='__main__':publish()
