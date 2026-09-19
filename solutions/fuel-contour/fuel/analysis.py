"""Explicit research scenarios, never mutations of CASE_INPUT or mandatory stress."""
import copy
import random
import statistics
from .engine import evaluate, commissioning, lead_days
from .validation import InputError


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
        source_id = next(s['source_id'] for s in case['supply_sources'] if s['name']==name)
        exposure = sum(o['ordered_volume_t'] for o in plan['decisions']['supply_orders'] if o['source_id']==source_id and o['year']==year)
        mitigated_plan = copy.deepcopy(plan)
        mitigated_plan['plan_id'] += '_STOCK_BUFFER'
        ceiling = next(s['capacity_t'] for s in case['storage_options'] if s['storage_id'] == 'BASE')
        mitigated_plan['decisions']['inventory_policy']['opening_stock_t'] = plan['decisions']['inventory_policy']['opening_stock_t'] + min(20., max(0., ceiling-plan['decisions']['inventory_policy']['opening_stock_t']))
        mitigated_plan['assumptions']['risk_mitigation'] = 'TEAM_DECISION: extra 20 t paid pre-horizon stock, capped at initial storage; no hidden recourse'
        mitigation_label = 'Explicit alternate plan: +20 t paid initial stock, decided before horizon'
        if ident == 'GEO':
            mitigated_plan = diversify_price_exposure(case, plan, year)
            mitigation_label = 'Ex-ante shift from Earth-Core to spare Earth-New/Flex capacity, before order deadlines; not cancellation of paid contracts'
        if exposure <= 1e-8:
            mitigated_plan = copy.deepcopy(plan)
            mitigation_label = 'No source-year exposure; screened out, no mitigation purchase'
        residual = evaluate(case, mitigated_plan, scenario, trace=False)
        nominal_measure = evaluate(case, mitigated_plan, base['provenance']['scenario_definition'], trace=False)
        rows.append(dict(risk_id=ident, event=event, cause='TEAM_ASSUMPTION research event', affected_parameter=f'{parameter}.{name}',
                         period=year, exposure_t=exposure, material_exposure=exposure>1e-8, probability_basis_or_range='No probability claim; deterministic endpoint',
                         baseline_value=1., changed_value=factor, scenario=scenario,
                         physical_consequence_t=result['summary']['shortage_t']-base['summary']['shortage_t'],
                         financial_consequence_mln=result['summary']['total_cost_mln']-base['summary']['total_cost_mln'],
                         service_consequence=result['summary']['min_total_service']-base['summary']['min_total_service'],
                         dependencies='No automatic combination with mandatory stress or other events', owner=owner,
                         mitigation=mitigation, tested_mitigation=mitigation_label, baseline_scenario_id='BASE',
                         residual_consequence=residual['summary'],
                         mitigation_incremental_cost_mln=residual['summary']['total_cost_mln']-result['summary']['total_cost_mln'],
                         mitigation_baseline_cost_mln=nominal_measure['summary']['total_cost_mln']-base['summary']['total_cost_mln'],
                         mitigation_nominal_summary=nominal_measure['summary'],
                         mitigation_decision=mitigated_plan['decisions'],
                         mitigation_plan=mitigated_plan, stakeholder_effects=stakeholder_effects(result, residual),
                         residual_failed_rules=[c for c in residual['constraint_checks'] if not c['passed']],
                         result_summary=result['summary']))
    return rows

def reliability(source, year, operating_year):
    try:
        profile = dict(x.split(':') for x in source['reliability_profile'].split(';'))
        if 'constant' in profile:
            p = float(profile['constant'])
        elif 'first_operating_year' in profile:
            p = float(profile['first_operating_year' if year == operating_year else 'later'])
        else:
            p = float(profile[str(year)])
            if source['source_id'] == 'D' and year == operating_year:
                # PDF p.5: late commissioning must not turn year-one ISRU reliability into >0.78.
                p = min(p, float(profile[str(source['available_from_year'])]))
    except (ValueError, KeyError) as exc:
        raise InputError(f'RELIABILITY_PROFILE_INVALID source={source["source_id"]} year={year}') from exc
    if not __import__('math').isfinite(p) or not 0 <= p <= 1:
        raise InputError(f'RELIABILITY_OUT_OF_RANGE source={source["source_id"]} actual={p}')
    return p

def monte_carlo(case, plan, count=100, seed=2035, dependence='independent'):
    if dependence not in ('independent', 'common_year'):
        raise ValueError('dependence must be independent|common_year')
    if not 1 <= count <= 1000:
        raise ValueError('MC count must be 1..1000')
    rng = random.Random(seed)
    runs = []
    active = {(o['source_id'], o['year']) for o in plan['decisions']['supply_orders'] if o['ordered_volume_t'] > 0}
    first = {sid: min(y for s, y in active if s == sid) for sid, _ in active}
    dates, _ = commissioning(case, plan)
    if 'C' in first and 'EARTH_NEW' in dates:
        first['C'] = min(r['year'] for r in case['demand']) + dates['EARTH_NEW']//365
    if 'D' in first and 'LUNAR_ISRU' in dates:
        first['D'] = min(r['year'] for r in case['demand']) + dates['LUNAR_ISRU']//365
    for _ in range(count):
        shares = {}
        common = {r['year']: rng.random() for r in case['demand']} if dependence=='common_year' else {}
        for s in case['supply_sources']:
            for dr in case['demand']:
                y = dr['year']
                if (s['source_id'], y) in active:
                    p = reliability(s, y, first[s['source_id']])
                    shares.setdefault(s['name'], {})[y] = float((common[y] if dependence=='common_year' else rng.random()) < p)
        r = evaluate(case, plan, research('MC', actual_delivery_share=shares), trace=False)
        runs.append(r['summary'])
    failures = sum(not service_ok(case, r) for r in runs)
    # Wilson interval describes sampling error under this hypothetical distribution, not reality.
    z, n, p = 1.96, count, failures/count
    center = (p+z*z/(2*n))/(1+z*z/n)
    half = z*((p*(1-p)/n+z*z/(4*n*n))**.5)/(1+z*z/n)
    shortages = sorted(r['shortage_t'] for r in runs)
    return {'status': 'TEAM_ASSUMPTION', 'dependence': dependence, 'distribution': 'Bernoulli full-year availability; reliability interpreted as success probability. Common-year variant shares a uniform draw across sources, preserving marginals.',
            'limitation': 'Illustrative interpretation, not calibrated outages; no real-world probability claim. Independent and common-year variants are illustrative; partial outages excluded.',
            'seed': seed, 'count': count, 'service_failure_fraction': p, 'wilson_95_conditional_interval': [center-half, center+half],
            'mean_shortage_t': statistics.mean(shortages), 'p95_shortage_t': shortages[max(0, __import__('math').ceil(.95*n)-1)], 'runs': runs}

def mcda(alternatives):
    # Hard constraints are not relaxed by a high preference score.
    if len({a['base'].get('discount_rate', 0) for a in alternatives} | {a['stress'].get('discount_rate', 0) for a in alternatives}) > 1:
        raise InputError('DISCOUNT_BASIS_MISMATCH')
    metrics = {'cost': [a['base'].get('discounted_cost_mln', a['base']['total_cost_mln']) for a in alternatives],
               'stress_service': [a['stress']['min_critical_service'] for a in alternatives],
               'stress_shortage': [a['stress']['shortage_t'] for a in alternatives]}
    normalized = {}
    for name, values in metrics.items():
        lo, hi = min(values), max(values)
        normalized[name] = [1. if abs(hi-lo) < 1e-8 else ((hi-v)/(hi-lo) if name != 'stress_service' else (v-lo)/(hi-lo)) for v in values]
    weights = {'operator': [.3, .4, .3], 'critical_consumers': [.1, .8, .1], 'commercial_consumers': [.2, .2, .6],
               'suppliers': [.5, .2, .3], 'investor': [.7, .2, .1]}
    rows = []
    for i, a in enumerate(alternatives):
        rows.append({'plan_id': a['plan_id'], 'base_violations': a['base']['violations'], 'stress_violations': a['stress']['violations'],
                     'feasible_in_both': a['base']['violations']==0 and a['stress']['violations']==0,
                     'scores': {stake: sum(w[j]*normalized[k][i] for j, k in enumerate(metrics)) for stake, w in weights.items()}})
    sweep = [{'cost_weight': w, 'scores': {a['plan_id']: w*normalized['cost'][i]+(1-w)*(normalized['stress_service'][i]+normalized['stress_shortage'][i])/2 for i, a in enumerate(alternatives)}} for w in [0., .25, .5, .75, 1.]]
    return {'status': 'TEAM_ASSUMPTION', 'weight_basis': 'Illustrative stakeholder preferences, not elicited from real stakeholders',
            'criteria_order': list(metrics), 'normalization': 'Alternative-set min/max benefit; equal values map to 1',
            'weights': weights, 'scores': rows, 'weight_sensitivity': sweep,
            'warning': 'Scores cannot override feasibility; supplier utility is only a proxy and requires elicitation'}

def extension_demo(case, plan):
    c, p = copy.deepcopy(case), copy.deepcopy(plan)
    x = copy.deepcopy(c['supply_sources'][1])
    x.update(source_id='Source-X', name='Synthetic-X', reliability_profile='constant:0.985', status='TEAM_ASSUMPTION')
    c['supply_sources'].append(x)
    # Replace B in plan: identical synthetic parameters must produce identical arithmetic.
    for section in ['supply_orders', 'capacity_reservations']:
        for row in p['decisions'][section]:
            if row['source_id'] == 'B':
                row['source_id'] = 'Source-X'
    last = copy.deepcopy(c['demand'][-1]); last['year'] += 1; last['status'] = 'TEAM_ASSUMPTION'
    for source in c['supply_sources']:
        if source['source_id'] == 'D':
            source['reliability_profile'] += f';{last["year"]}:0.93'
            source['status'] = 'TEAM_ASSUMPTION'
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
                                   'reliability': 'TEAM extrapolation: D 2041=0.93 from last available year; constant profiles unchanged; C later=0.94',
                                   'constraints': 'service/reserve/capacity continue; organizer CAPEX limits retain original dates',
                                   'source_x': 'Synthetic copy of B, not an organizer source'}
    c['version'] += '+TEAM_EXTENSION'
    c['status'] = 'TEAM_ASSUMPTION'
    return evaluate(c, p, research('EXTENSION'), trace=False)


def compare_decisions(case, baseline_plan, alternative_plan, base_scenario, stress_scenario):
    """2x2 experiment: separate environmental effect from ex-ante redesign effect."""
    if baseline_plan['assumptions']['discount_rate']['value'] != alternative_plan['assumptions']['discount_rate']['value']:
        raise InputError('DISCOUNT_BASIS_MISMATCH: compare alternatives at the same real rate')
    evaluations = {}
    for name, plan in [('baseline', baseline_plan), ('redesign', alternative_plan)]:
        evaluations[name] = {key: evaluate(case, plan, scenario, trace=False)
                             for key, scenario in [('base', base_scenario), ('stress', stress_scenario)]}
    changes = []
    for section, amount in [('supply_orders', 'ordered_volume_t'), ('capacity_reservations', 'reserved_capacity_t')]:
        left = {(r['source_id'], r['year']): r for r in baseline_plan['decisions'][section]}
        right = {(r['source_id'], r['year']): r for r in alternative_plan['decisions'][section]}
        for sid, year in sorted(left.keys() | right.keys()):
            old, new = left.get((sid, year), {}), right.get((sid, year), {})
            if old != new:
                order = next((o for o in alternative_plan['decisions']['supply_orders'] if o['source_id']==sid and o['year']==year), {})
                changes.append({'decision': section, 'source_id': sid, 'year': year, 'unit': 't',
                                'before_t': old.get(amount, 0), 'after_t': new.get(amount, 0),
                                'delta_t': new.get(amount, 0)-old.get(amount, 0),
                                'order_day': order.get('order_day'), 'before': old, 'after': new})
    old = evaluations['baseline']['stress']['summary']
    new = evaluations['redesign']['stress']['summary']
    return {'status': 'TEAM_DECISION', 'method': '2x2 comparison; ex-ante alternative, not post-shock recourse',
            'timing': 'All changed orders are decided at their stored order_day, respecting full lead time. No paid baseline contract is cancelled.',
            'commitment_warning': 'Use redesigned plan only before those commitments. A late operator must retain original commitments and model separate new orders.',
            'changes': changes,
            'matrix': [{'plan_role': name, 'plan_id': r['plan_id'], 'scenario_id': r['scenario_id'], **r['summary']}
                       for name, value in evaluations.items() for r in value.values()],
            'incremental_stress_cost_mln': new['total_cost_mln']-old['total_cost_mln'],
            'avoided_stress_shortage_t': old['shortage_t']-new['shortage_t'],
            'earliest_changed_order_day': min((r['order_day'] for r in changes if r['order_day'] is not None), default=None),
            'stakeholders': stakeholder_effects(evaluations['baseline']['stress'], evaluations['redesign']['stress'])}


def stakeholder_effects(before, after):
    """Physical/financial deltas, never preference scores that erase a shortage."""
    b, a = before['summary'], after['summary']
    bc = sum(r['served_critical_t'] for r in before['yearly_balance'])
    ac = sum(r['served_critical_t'] for r in after['yearly_balance'])
    return [
        {'party': 'Operator', 'metric': 'min_inventory_t', 'before': b['min_inventory_t'], 'after': a['min_inventory_t'], 'unit': 't', 'responsibility': 'Maintain storage and annual reserve'},
        {'party': 'Critical consumers', 'metric': 'served_critical', 'before': bc, 'after': ac, 'unit': 't', 'responsibility': 'Critical service target unchanged'},
        {'party': 'Commercial consumers', 'metric': 'served_commercial', 'before': b['served_t']-bc, 'after': a['served_t']-ac, 'unit': 't', 'responsibility': 'Bear residual shortage under critical-first allocation'},
        {'party': 'Fuel/launch suppliers', 'metric': 'procurement_and_reservation', 'before': sum(r['procurement_mln']+r['reservation_mln'] for r in before['financial_breakdown']), 'after': sum(r['procurement_mln']+r['reservation_mln'] for r in after['financial_breakdown']), 'unit': 'mln_units', 'responsibility': 'Deliver under dates and contracted capacity; no invented refunds'},
        {'party': 'Investor', 'metric': 'discounted_cost', 'before': b['discounted_cost_mln'], 'after': a['discounted_cost_mln'], 'unit': 'mln_units', 'responsibility': 'Finance procurement, preparation, CAPEX and operating costs'}]


def stress_attribution(case, plan, stress):
    """Sequential decomposition; explicitly order-dependent, not independent causal effects."""
    scenario = research('ATTRIBUTION_0')
    previous = evaluate(case, plan, scenario, trace=False)['summary']
    rows = [{'step': 'baseline', 'delta_cost_mln': 0., 'delta_shortage_t': 0., **previous}]
    for index, sections in enumerate([['demand_multiplier', 'critical_demand_multiplier'], ['variable_price_multiplier'], ['actual_delivery_share'], ['loss_ceiling']], 1):
        for key in sections:
            scenario[key] = copy.deepcopy(stress.get(key, {}))
        scenario['scenario_id'] = f'TEAM_ATTRIBUTION_{index}'
        current = evaluate(case, plan, scenario, trace=False)['summary']
        rows.append({'step': '+'.join(sections), 'delta_cost_mln': current['total_cost_mln']-previous['total_cost_mln'],
                     'delta_shortage_t': current['shortage_t']-previous['shortage_t'], **current})
        previous = current
    return {'status': 'TEAM_ASSUMPTION', 'method': 'Sequential decomposition demand → prices → delivery → loss constraint; interaction effects assigned to later steps', 'steps': rows}


def parameter_sensitivity(case, plan):
    """One-at-a-time changes plus an explicitly combined TEAM scenario."""
    base = evaluate(case, plan, research('SENS_REFERENCE'), trace=False)
    points = []
    scenarios = []
    years = [r['year'] for r in case['demand']]
    for value in [1., 1.25, 1.5]:
        scenarios.append(('Earth-Core price', value, 'CASE_INPUT mandatory shock 1.25; TEAM research endpoint 1.50 (not a forecast)',
                          research('PRICE_'+str(value), variable_price_multiplier={'Earth-Core': {y: value for y in years}})))
    for value in [0., .05, .10]:
        p = copy.deepcopy(plan)
        p['assumptions']['discount_rate']['value'] = value
        r = evaluate(case, p, research('DISCOUNT_'+str(value)), trace=False)
        points.append({'parameter': 'real_discount_rate', 'value': value, 'basis': 'TEAM_ASSUMPTION 0/5/10% to test intertemporal preferences, not a market estimate',
                       'scenario_definition': research('DISCOUNT_'+str(value)), 'decision_override': {'discount_rate': value},
                       'delta_cost_mln': r['summary']['total_cost_mln']-base['summary']['total_cost_mln'], **r['summary']})
    for value in ['lower', 'upper']:
        scenarios.append(('lead_time_policy', value, 'CASE_INPUT bounds Earth-New 18–24 months / Lunar 1–2 months',
                          research('LEAD_'+value, implementation_assumptions={'lead_time_policy': value})))
    for value in [0, 90, 365]:
        scenarios.append(('zbo_delay_days', value, 'TEAM_ASSUMPTION illustrative implementation delay; duration unspecified by organizer',
                          research('ZBO_DELAY_'+str(value), implementation_assumptions={'zbo_delay_days': value})))
    for value in ['any_planned', 'majority']:
        scenarios.append(('emergency_base_definition', value, 'TEAM_ASSUMPTION ambiguous base-channel threshold: any scheduled vs ≥50% ordered volume',
                          research('EMERGENCY_'+value, implementation_assumptions={'emergency_base_definition': value})))
    scenarios.append(('combined_demand_price', '1.15/1.25', 'TEAM combination all years; not MANDATORY_STRESS',
                      research('COMBINED_RESEARCH', demand_multiplier={'default': 1.15}, variable_price_multiplier={'Earth-Core': {y: 1.25 for y in years}})))
    for parameter, value, basis, scenario in scenarios:
        result = evaluate(case, plan, scenario, trace=False)
        points.append({'parameter': parameter, 'value': value, 'basis': basis, 'scenario_definition': scenario,
                       'delta_cost_mln': result['summary']['total_cost_mln']-base['summary']['total_cost_mln'],
                       'failed_rules': sorted({c['rule_id'] for c in result['constraint_checks'] if not c['passed']}), **result['summary']})
    return {'status': 'TEAM_ASSUMPTION', 'points': points,
            'ranking_by_absolute_cost_impact': sorted(points, key=lambda r: abs(r['delta_cost_mln']), reverse=True),
            'limitation': 'No statistical probabilities attached to endpoints; invariant outcomes do not prove the assumption irrelevant for other plans.'}


def price_crossover(case, plan_a, plan_b, source_name='Lunar-ISRU', upper=3.):
    """Find a cost ranking reversal, explicitly reporting when none is bracketed."""
    def delta(x):
        scenario = research('PRICE_CROSSOVER', variable_price_multiplier={source_name: {r['year']: x for r in case['demand']}})
        return evaluate(case, plan_a, scenario, trace=False)['summary']['total_cost_mln']-evaluate(case, plan_b, scenario, trace=False)['summary']['total_cost_mln']
    lo, hi = 1., upper
    dlo, dhi = delta(lo), delta(hi)
    bracket = None
    if dlo*dhi <= 0:
        for _ in range(24):
            mid = (lo+hi)/2; dm = delta(mid)
            if dm*dlo > 0: lo = mid
            else: hi = mid
        bracket = [lo, hi]
    return {'status': 'TEAM_ASSUMPTION', 'source': source_name, 'parameter': 'variable price multiplier all applicable years',
            'range_basis': 'Research search interval [1,3], not a prediction', 'bracket': bracket,
            'status_detail': 'bracketed' if bracket is not None else 'no_reversal_in_range', 'endpoint_cost_difference_mln': [dlo, dhi]}


def diversify_price_exposure(case, plan, year):
    """Explicit prior design decision, not free recourse after a price event."""
    p = copy.deepcopy(plan)
    p['plan_id'] += '_PRICE_DIVERSIFIED'
    p['assumptions']['mitigation_timing'] = 'Ex-ante redesign before affected order dates. Existing paid contracts cannot be cancelled by this comparison.'
    orders = p['decisions']['supply_orders']
    reservations = p['decisions']['capacity_reservations']
    core = next((o for o in orders if o['source_id']=='A' and o['year']==year), None)
    if not core:
        return p
    sources = {s['source_id']: s for s in case['supply_sources']}
    dates, _ = commissioning(case, p)
    first = min(d['year'] for d in case['demand'])
    offset = (year-first)*365
    for sid in ['C','B']:
        if sid=='C' and dates.get('EARTH_NEW', float('inf')) > offset:
            continue
        source = sources[sid]
        other = next((o for o in orders if o['source_id']==sid and o['year']==year), None)
        if other is None:
            other = dict(source_id=sid, year=year, ordered_volume_t=0., start_day=1, end_day=365, order_day=offset-lead_days(source))
            orders.append(other)
        if other['start_day']!=1 or other['end_day']!=365:
            continue  # Do not silently rewrite operator-defined partial contracts.
        amount = min(core['ordered_volume_t'], max(0, source['capacity_t_per_year']-other['ordered_volume_t']))
        other['ordered_volume_t'] += amount
        core['ordered_volume_t'] -= amount
        other['order_day'] = min(other['order_day'], offset-lead_days(source))
        for changed in [core, other]:
            res = next((r for r in reservations if r['source_id']==changed['source_id'] and r['year']==year), None)
            if res is None:
                res = dict(source_id=changed['source_id'], year=year, start_day=1, end_day=365)
                reservations.append(res)
            res['reserved_capacity_t'] = changed['ordered_volume_t']
    return p
