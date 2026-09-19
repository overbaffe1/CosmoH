"""Deterministic defense evidence; run after suite. No timings fabricated here."""
import csv
import html
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from fuel.io import load_case, load_scenario, save_json, digest
from fuel.planning import make_plan
from fuel.engine import evaluate
from fuel.study import response_grid


def heatmap(study):
    shares=study['delivery_shares'];delays=study['observation_delays']
    lookup={(r['delivery_share'],r['observed_after_days']):r for r in study['rows']}
    parts=['<svg xmlns="http://www.w3.org/2000/svg" width="1100" height="360" viewBox="0 0 1100 360" role="img" aria-label="Остаточный дефицит и нарушения по доле исполнения Lunar и задержке наблюдения"><rect width="1100" height="360" rx="16" fill="#f5f7f1"/><g font-family="Arial,sans-serif" fill="#234a3b">', '<text x="24" y="30" font-size="15">Доля заказа Lunar, которая исполнена ↓ · когда узнали о сбое →</text>']
    for j,d in enumerate(delays):parts.append(f'<text x="{232+j*124}" y="58" text-anchor="middle" font-size="15">{d} дней</text>')
    for i,share in enumerate(shares):
        y=72+i*49
        parts.append(f'<text x="25" y="{y+28}" font-size="{15 if share==1 else 18}">{share*100:g}%'+(' · без сбоя' if share==1 else '')+'</text>')
        for j,d in enumerate(delays):
            r=lookup[share,d];a=r['after'];x=173+j*124
            color='#e9edef' if share==1 else '#dcebdc' if a['violations']==0 else '#f3e4ce' if a['shortage_t']<1e-8 else '#edc9b8'
            value=f"{a['shortage_t']:.2f}".replace('.',',')
            parts.append(f'<g><title>{html.escape(str(r))}</title><rect x="{x}" y="{y}" width="116" height="43" rx="6" fill="{color}"/><text x="{x+58}" y="{y+20}" text-anchor="middle" font-size="18">{value} т</text><text x="{x+58}" y="{y+36}" text-anchor="middle" font-size="12">{a["violations"]} наруш.</text></g>')
    parts.append('<text x="24" y="343" font-size="14">Зелёный: проверки пройдены · песочный: нет дефицита, но есть нарушения · красный: дефицит</text></g></svg>')
    return ''.join(parts)


def build(dest=None):
    dest=Path(dest or ROOT/'docs/evidence');dest.mkdir(parents=True,exist_ok=True)
    c=load_case();p=make_plan(c,'lunar');study=response_grid(c,p)
    study['summary_sha256']=digest(json.loads((ROOT/'results/summary.json').read_text()))
    save_json(dest/'response-grid.json',study)
    fields=['delivery_share','observed_after_days','before_shortage_t','after_shortage_t','before_violations','after_violations','added_order_t','incremental_cost_mln','action']
    with (dest/'response-grid.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,lineterminator="\n");w.writeheader()
        for r in study['rows']:
            w.writerow({k:r[k] for k in fields if k in r}|{'before_shortage_t':r['before']['shortage_t'],'after_shortage_t':r['after']['shortage_t'],'before_violations':r['before']['violations'],'after_violations':r['after']['violations']})
    (dest/'response-grid.svg').write_text(heatmap(study))
    r=evaluate(c,p,load_scenario('BASE'));day=r['inventory_trace'][0]
    expected=day['opening_inventory_t']+day['delivered_t']-day['losses_t']-day['served_t']
    assert abs(expected-day['inventory_t'])<1e-10
    save_json(dest/'balance-example.json',{'status':'TEAM_ANALYSIS','plan_id':p['plan_id'],'scenario_id':'BASE','row':day,'independent_arithmetic_t':expected,'residual_t':expected-day['inventory_t']})
    (dest/'BALANCE.md').write_text(f'''# Один день — проверка руками

Критерии 1 / 5. Исходный Lunar, BASE, 1-й день 2035. Тонны. Это реальная строка ядра,
не подобранный учебный пример. [Полные значения](balance-example.json).

| Операция | Тонны |
|---|---:|
| Было в начале | {day['opening_inventory_t']:.9f} |
| + Принято (после отсечения переполнения, до потерь) | {day['delivered_t']:.9f} |
| − Потери | {day['losses_t']:.9f} |
| − Выдано клиентам | {day['served_t']:.9f} |
| = Осталось | {day['inventory_t']:.9f} |

Независимое сложение четырёх полей: **{expected:.12f} т**.
Расхождение с конечным запасом: **{expected-day['inventory_t']:.3g} т**.
Допуск проверки 1e-10 т, а не округление таблицы. Спрос клиентов в этом дне 100/365 т;
критический спрос входит в общий. За пределами этой иллюстрации все дни проверяют тесты.

Этот пример доказывает арифметику баланса, не инженерную точность модели реального бака.
''')
    print('Generated',len(study['rows']),'response cells and independent daily arithmetic')
    return study

if __name__=='__main__':build()
