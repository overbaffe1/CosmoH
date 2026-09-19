"""Explicit research scenarios, never mutations of CASE_INPUT or mandatory stress."""
import copy
import random
import statistics
from .engine import evaluate, commissioning


def research(label, **kwargs):
    return {'scenario_id': 'TEAM_'+label, 'status': 'TEAM_ASSUMPTION', **kwargs}

def demand_scenario(case, which):
    return research(which.upper(), demand_multiplier={r['year']: r[which+'_total_t']/r['base_total_t'] if r['base_total_t'] else 1 for r in case['demand']}, notes=['Organizer low/high demand; critical share retained; not mandatory stress'])

def service_ok(case, summary):
    limits = {r['constraint_id']: r['value'] for r in case['constraints']}
    return (summary['min_total_service'] >= limits['BASE_TOTAL_SERVICE']-1e-8 and
            summary['min_critical_service'] >= limits['BASE_CRITICAL_SERVICE']-1e-8)

def sensitivity(case, plan):
    points = []
    for factor in [0.8, 0.9, 1.0, 1.05, 1.1, 1.15, 1.2, 1.25]:
        s = research('DEMAND', demand_multiplier={'default': factor})
        result = evaluate(case, plan, s, trace=False)
        points.append({'factor': factor, **result['summary']})
    # Threshold for service only; storage and reserve reported separately above, not claimed monotone.
    low, high = 1., 2.
    low_ok = service_ok(case, evaluate(case, plan, research('THRESHOLD', demand_multiplier={'default': low}), trace=False)['summary'])
    high_ok = service_ok(case, evaluate(case, plan, research('THRESHOLD', demand_multiplier={'default': high}), trace=False)['summary'])
    bracketed = low_ok and not high_ok
    for _ in range(22 if bracketed else 0):
        mid = (low+high)/2
        r = evaluate(case, plan, research('THRESHOLD', demand_multiplier={'default': mid}), trace=False)
        if service_ok(case, r['summary']):
            low = mid
        else:
            high = mid
    return {'status': 'TEAM_ASSUMPTION', 'parameter': 'uniform demand multiplier all years',
            'range_basis': 'illustrative 0.8..1.25; low/high organizer vectors reported separately',
            'points': points, 'service_failure_bracket': [low, high] if bracketed else None,
            'threshold_status': 'bracketed' if bracketed else ('already_fails_at_one' if not low_ok else 'not_reached_at_two'),
            'threshold_search_bounds': [1, 2],
            'low_high': {k: evaluate(case, plan, demand_scenario(case, k), trace=False)['summary'] for k in ['low', 'high']}}

def risk_analysis(case, plan, base):
    specs = [
        ('LUNAR_OUTAGE', 'Lunar-ISRU', 'actual_delivery_share', 2038, 0., 'Plant unavailable for one year', 'ISRU operator', 'Earth diversification'),
        ('GEO', 'Earth-Core', 'variable_price_multiplier', 2039, 1.5, 'Illustrative trade restriction cost shock, not a forecast', 'Procurement lead', 'Switch contracts subject to lead time'),
        ('EARTH_DISRUPTION', 'Earth-Core', 'actual_delivery_share', 2039, .5, 'One-year partial delivery interruption', 'Logistics lead', 'Physical stock and alternate sources')]
    rows = []
    for ident, name, parameter, year, factor, event, owner, mitigation in specs:
        scenario = research(ident, **{parameter: {name: {year: factor}}}, notes=['Hypothetical range/event; no calibrated probability; applied separately to BASE'])
        result = evaluate(case, plan, scenario, trace=False)
        mitigated_plan = copy.deepcopy(plan)
        mitigated_plan['plan_id'] += '_STOCK_BUFFER'
        ceiling = next(s['capacity_t'] for s in case['storage_options'] if s['storage_id'] == 'BASE')
        mitigated_plan['decisions']['inventory_policy']['opening_stock_t'] = min(ceiling, plan['decisions']['inventory_policy']['opening_stock_t'] + 20.)
        mitigated_plan['assumptions']['risk_mitigation'] = 'TEAM_DECISION: extra 20 t paid pre-horizon stock, capped at initial storage; no hidden recourse'
        residual = evaluate(case, mitigated_plan, scenario, trace=False)
        rows.append(dict(risk_id=ident, event=event, cause='TEAM_ASSUMPTION research event', affected_parameter=f'{parameter}.{name}',
                         period=year, probability_basis_or_range='No probability claim; deterministic endpoint',
                         baseline_value=1., changed_value=factor, scenario=scenario,
                         physical_consequence_t=result['summary']['shortage_t']-base['summary']['shortage_t'],
                         financial_consequence_mln=result['summary']['total_cost_mln']-base['summary']['total_cost_mln'],
                         service_consequence=result['summary']['min_total_service']-base['summary']['min_total_service'],
                         dependencies='No automatic combination with mandatory stress or other events', owner=owner,
                         mitigation=mitigation, tested_mitigation='Explicit alternate plan: +20 t initial physical stock; may not address price shock',
                         residual_consequence=residual['summary'],
                         mitigation_incremental_cost_mln=residual['summary']['total_cost_mln']-result['summary']['total_cost_mln'],
                         mitigation_decision=mitigated_plan['decisions']['inventory_policy'],
                         result_summary=result['summary']))
    return rows

def reliability(source, year, operating_year):
    profile = dict(x.split(':') for x in source['reliability_profile'].split(';'))
    if 'constant' in profile:
        return float(profile['constant'])
    if 'first_operating_year' in profile:
        return float(profile['first_operating_year' if year == operating_year else 'later'])
    if str(year) not in profile:
        raise ValueError(f'No reliability assumption for {source["source_id"]}/{year}')
    return float(profile[str(year)])

def monte_carlo(case, plan, count=100, seed=2035):
    if not 1 <= count <= 1000:
        raise ValueError('MC count must be 1..1000')
    rng = random.Random(seed)
    runs = []
    active = {(o['source_id'], o['year']) for o in plan['decisions']['supply_orders'] if o['ordered_volume_t'] > 0}
    first = {sid: min(y for s, y in active if s == sid) for sid, _ in active}
    dates, _ = commissioning(case, plan)
    if 'C' in first and 'EARTH_NEW' in dates:
        first['C'] = min(r['year'] for r in case['demand']) + dates['EARTH_NEW']//365
    for _ in range(count):
        shares = {}
        for s in case['supply_sources']:
            for dr in case['demand']:
                y = dr['year']
                if (s['source_id'], y) in active:
                    p = reliability(s, y, first[s['source_id']])
                    shares.setdefault(s['name'], {})[y] = float(rng.random() < p)
        r = evaluate(case, plan, research('MC', actual_delivery_share=shares), trace=False)
        runs.append(r['summary'])
    failures = sum(not service_ok(case, r) for r in runs)
    # Wilson interval describes sampling error under this hypothetical distribution, not reality.
    z, n, p = 1.96, count, failures/count
    center = (p+z*z/(2*n))/(1+z*z/n)
    half = z*((p*(1-p)/n+z*z/(4*n*n))**.5)/(1+z*z/n)
    shortages = sorted(r['shortage_t'] for r in runs)
    return {'status': 'TEAM_ASSUMPTION', 'distribution': 'Independent source-year Bernoulli full-year availability; reliability interpreted as success probability',
            'limitation': 'Illustrative interpretation, not calibrated outages; no real-world probability claim. Correlations and partial outages excluded.',
            'seed': seed, 'count': count, 'service_failure_fraction': p, 'wilson_95_conditional_interval': [center-half, center+half],
            'mean_shortage_t': statistics.mean(shortages), 'p95_shortage_t': shortages[max(0, __import__('math').ceil(.95*n)-1)], 'runs': runs}

def mcda(alternatives):
    # Hard constraints are not relaxed by a high preference score.
    metrics = {'cost': [a['base']['total_cost_mln'] for a in alternatives],
               'stress_service': [a['stress']['min_critical_service'] for a in alternatives],
               'stress_shortage': [a['stress']['shortage_t'] for a in alternatives]}
    normalized = {}
    for name, values in metrics.items():
        lo, hi = min(values), max(values)
        normalized[name] = [1. if hi == lo else ((hi-v)/(hi-lo) if name != 'stress_service' else (v-lo)/(hi-lo)) for v in values]
    weights = {'operator': [.3, .4, .3], 'critical_consumers': [.1, .8, .1], 'commercial_consumers': [.2, .2, .6],
               'suppliers': [.5, .2, .3], 'investor': [.7, .2, .1]}
    rows = []
    for i, a in enumerate(alternatives):
        rows.append({'plan_id': a['plan_id'], 'base_violations': a['base']['violations'],
                     'scores': {stake: sum(w[j]*normalized[k][i] for j, k in enumerate(metrics)) for stake, w in weights.items()}})
    sweep = [{'cost_weight': w, 'scores': {a['plan_id']: w*normalized['cost'][i]+(1-w)*(normalized['stress_service'][i]+normalized['stress_shortage'][i])/2 for i, a in enumerate(alternatives)}} for w in [0., .25, .5, .75, 1.]]
    return {'status': 'TEAM_ASSUMPTION', 'weight_basis': 'Illustrative stakeholder preferences, not elicited from real stakeholders',
            'criteria_order': list(metrics), 'normalization': 'Alternative-set min/max benefit; equal values map to 1',
            'weights': weights, 'scores': rows, 'weight_sensitivity': sweep,
            'warning': 'Scores cannot override feasibility; supplier utility is only a proxy and requires elicitation'}

def extension_demo(case, plan):
    c, p = copy.deepcopy(case), copy.deepcopy(plan)
    x = copy.deepcopy(c['supply_sources'][1])
    x.update(source_id='Source-X', name='Synthetic-X', reliability_profile='constant:0.985')
    c['supply_sources'].append(x)
    # Replace B in plan: identical synthetic parameters must produce identical arithmetic.
    for section in ['supply_orders', 'capacity_reservations']:
        for row in p['decisions'][section]:
            if row['source_id'] == 'B':
                row['source_id'] = 'Source-X'
    last = copy.deepcopy(c['demand'][-1]); last['year'] += 1
    c['demand'].append(last)
    for section in ['supply_orders', 'capacity_reservations']:
        for row in list(p['decisions'][section]):
            if row['year'] == last['year']-1:
                r = copy.deepcopy(row); r['year'] += 1
                if 'order_day' in r:
                    r['order_day'] += 365
                p['decisions'][section].append(r)
    p['assumptions']['extension'] = {'status': 'TEAM_ASSUMPTION', 'demand': '2040 repeated in 2041',
                                   'prices': 'constant 2040 control values', 'availability': 'commissioned plants continue',
                                   'reliability': 'not used in deterministic research; no MC extension',
                                   'constraints': 'service/reserve/capacity continue; organizer CAPEX limits retain original dates',
                                   'source_x': 'Synthetic copy of B, not an organizer source'}
    c['version'] += '+TEAM_EXTENSION'
    return evaluate(c, p, research('EXTENSION'), trace=False)
