"""Pure functions: no filesystem, network, clock, or global mutable state."""
import math
from .validation import validate_plan, validate_scenario, InputError
from .io import digest

EPS = 1e-8

def reserve_required(demand, days=45):
    return demand * days / 365

def contract_cost(order, reserved, share, price, rate, fraction=1):
    payable = max(order, share * reserved * fraction)
    return {'payable_volume_t': payable, 'procurement_mln': payable * price,
            'reservation_mln': rate * reserved * fraction}

def balance_step(opening, delivered, losses, demand, critical):
    if critical > demand + EPS:
        raise InputError('CRITICAL_EXCEEDS_TOTAL')
    available = opening + delivered - losses
    served = min(demand, max(0, available))
    return {'closing_inventory_t': max(0, available - served), 'served_t': served,
            'served_critical_t': min(critical, served), 'shortage_t': max(0, demand - served)}

def throughput_loss(gross, rate):
    return gross * rate

def actual_delivery(planned, share):
    return planned * share

def capacity_check(reserved, maximum):
    return {'violation': 'CAPACITY_EXCEEDED', 'excess_t': reserved - maximum} if reserved > maximum + EPS else None

def lead_days(source):
    return math.ceil(source['lead_time_max_value'] * {'day': 1, 'week': 7, 'month': 365/12, 'year': 365}[source['lead_time_unit']])

def multiplier(scenario, section, year, name=None):
    values = scenario.get(section, {})
    default = values.get('default', 1)
    if name:
        values = values.get(name, {})
    return values.get(year, values.get(str(year), values.get('default', default)))

def commissioning(case, plan):
    """Return dates and explicit violations; invalid investments never enable capacity."""
    start_year = min(r['year'] for r in case['demand'])
    dates, issues = {}, []
    src = {s['source_id']: s for s in case['supply_sources']}
    for inv in plan['decisions']['investments']:
        ident = inv['investment_id']
        decision, requested = inv['decision_day'], inv['commission_day']
        minimum = decision
        valid = True
        if ident == 'EARTH_NEW':
            minimum = decision + lead_days(src['C'])
        elif ident == 'LUNAR_ISRU':
            minimum = max(decision, (src['D']['available_from_year'] - start_year) * 365)
            valid = decision < (src['D']['available_from_year'] - start_year) * 365
        elif ident == 'ZBO':
            zbo = next(s for s in case['storage_options'] if s['storage_id'] == 'ZBO')
            minimum = max(decision, (zbo['available_from_year'] - start_year) * 365)
        if requested < minimum or not valid:
            issues.append({'rule_id': 'COMMISSIONING_INVALID', 'period': decision, 'source': ident,
                           'actual': requested, 'limit': minimum, 'passed': False, 'unit': 'model_day'})
        else:
            dates[ident] = requested
    return dates, issues

def evaluate(case, plan, scenario, *, trace=True):
    validate_plan(case, plan)
    validate_scenario(case, scenario)
    demand_rows = sorted(case['demand'], key=lambda r: r['year'])
    years = [r['year'] for r in demand_rows]
    if years != list(range(years[0], years[-1] + 1)):
        raise InputError('NONCONTIGUOUS_YEARS')
    sources = {r['source_id']: r for r in case['supply_sources']}
    storage = {r['storage_id']: r for r in case['storage_options']}
    investments = {r['investment_id']: r for r in case['investment_options']}
    limits = {r['constraint_id']: r for r in case['constraints']}
    contracts = {(r['source_id'], r['year']): r for r in plan['decisions']['capacity_reservations']}
    orders = {(r['source_id'], r['year']): r for r in plan['decisions']['supply_orders']}
    dates, checks = commissioning(case, plan)
    policy = plan['decisions']['inventory_policy']
    opening = inventory = policy['opening_stock_t']
    bindings = {'C': 'EARTH_NEW', 'D': 'LUNAR_ISRU'}

    def check(rule, period, actual, limit, operator='<=', source='', unit='t'):
        passed = actual <= limit + EPS if operator == '<=' else actual >= limit - EPS
        checks.append(dict(rule_id=rule, period=period, source=source, actual=actual,
                           limit=limit, operator=operator, passed=passed, unit=unit))
        return passed

    def source_available(sid):
        s = sources[sid]
        base = (s['available_from_year'] - years[0]) * 365 if s['available_from_year'] is not None else 0
        return max(base, dates.get(bindings[sid], math.inf)) if sid in bindings else base

    # Explicit pre-horizon paid purchase; not counted a second time in horizon inflow.
    os = sources[policy['opening_source_id']]
    if os['source_id'] in bindings:
        raise InputError('OPENING_STOCK_MUST_USE_EXISTING_SOURCE')
    gross = opening / (1 - storage['BASE']['loss_rate_on_throughput'])
    check('OPENING_CONTRACT_CAPACITY', years[0]-1, gross, os['capacity_t_per_year'], source=os['source_id'])
    pre_cost = contract_cost(gross, gross, os['take_or_pay_share'], os['variable_cost_mln_per_t'], os['reservation_rate_mln_per_t_year_capacity'])
    pre_cost['holding_mln'] = opening * storage['BASE']['holding_cost_mln_per_t_year'] / 365
    pre_cost['total_mln'] = pre_cost['procurement_mln'] + pre_cost['reservation_mln'] + pre_cost['holding_mln']
    pre_cost.update(status='TEAM_ASSUMPTION', year=years[0]-1, source_id=os['source_id'],
                    ordered_volume_t=gross, delivered_gross_t=gross, opening_stock_t=opening,
                    losses_t=gross-opening, delivery_day=-1, order_day=-1-lead_days(os),
                    financing='Separate paid pre-horizon contract; no free initial stock')
    check('OPENING_STORAGE_CAPACITY', -1, opening, storage['BASE']['capacity_t'])
    yearly, schedule, daily, finance = [], [], [], []
    emergency_streak = 0
    for dr in demand_rows:
        y = dr['year']
        offset = (y-years[0])*365
        total = dr['base_total_t'] * multiplier(scenario, 'demand_multiplier', y)
        critical = dr['base_critical_t'] * multiplier(scenario, 'critical_demand_multiplier', y) if 'critical_demand_multiplier' in scenario else dr['base_critical_t'] * multiplier(scenario, 'demand_multiplier', y)
        if critical > total + EPS:
            raise InputError(f'CRITICAL_EXCEEDS_TOTAL year={y}')
        check('RESERVE_45D', y, inventory, reserve_required(total, limits['RESERVE_45D']['value']), '>=')
        annual = dict(year=y, opening_inventory_t=inventory, demand_t=total, critical_demand_t=critical,
                      delivered_t=0., losses_t=0., served_t=0., served_critical_t=0., shortage_t=0.,
                      rejected_delivery_t=0., min_inventory_t=inventory, max_inventory_t=inventory,
                      reserve_required_t=reserve_required(total, limits['RESERVE_45D']['value']))
        costs = dict(year=y, procurement_mln=0., reservation_mln=0., holding_mln=0., fixed_opex_mln=0., capex_mln=0.)
        arrivals = [[] for _ in range(365)]
        emergency_order = 0
        for sid, s in sources.items():
            r = contracts.get((sid, y))
            o = orders.get((sid, y))
            reserved = r['reserved_capacity_t'] if r else 0.
            amount = o['ordered_volume_t'] if o else 0.
            if sid == 'E':
                emergency_order = amount
            fraction = (r['end_day']-r['start_day']+1)/365 if r else 0.
            check('CAPACITY_EXCEEDED', y, reserved, s['capacity_t_per_year'], source=sid, unit='t/year')
            check('ORDER_EXCEEDS_CONTRACT', y, amount, reserved*fraction, source=sid)
            availability = source_available(sid)
            available_fraction = max(0., min(365., offset+365-availability))/365
            check('ORDER_EXCEEDS_AVAILABLE_CAPACITY', y, amount, s['capacity_t_per_year']*available_fraction, source=sid)
            valid = True
            if o and amount > 0:
                first = offset + o['start_day'] - 1
                valid &= check('LEAD_TIME', y, first-o['order_day'], lead_days(s), '>=', sid, 'days')
                # Lunar logistics can start only after plant commissioning.
                if sid == 'D':
                    valid &= check('LUNAR_POST_COMMISSION_LEAD', y, first, availability+lead_days(s), '>=', sid, 'model_day')
                valid &= check('SOURCE_NOT_COMMISSIONED', y, first, availability, '>=', sid, 'model_day')
                within = bool(r and o['start_day'] >= r['start_day'] and o['end_day'] <= r['end_day'])
                check('ORDER_OUTSIDE_CONTRACT', y, int(within), 1, '>=', sid, 'boolean')
                valid &= within
            price = s['variable_cost_mln_per_t'] * multiplier(scenario, 'variable_price_multiplier', y, s['name'])
            c = contract_cost(amount, reserved, s['take_or_pay_share'], price,
                              s['reservation_rate_mln_per_t_year_capacity'], fraction)
            costs['procurement_mln'] += c['procurement_mln']
            costs['reservation_mln'] += c['reservation_mln']
            offered = min(amount, reserved*fraction, s['capacity_t_per_year']*available_fraction) if valid else 0.
            offered = actual_delivery(offered, multiplier(scenario, 'actual_delivery_share', y, s['name']))
            row = dict(year=y, source_id=sid, reserved_capacity_t=reserved, ordered_volume_t=amount,
                       offered_volume_t=offered, delivered_volume_t=0., rejected_volume_t=0.,
                       start_day=o['start_day'] if o else None, end_day=o['end_day'] if o else None,
                       order_day=o['order_day'] if o else None, variable_price_mln_per_t=price, **c)
            schedule.append(row)
            if o and offered > 0:
                per_day = offered/(o['end_day']-o['start_day']+1)
                for day in range(o['start_day']-1, o['end_day']):
                    arrivals[day].append((row, per_day))
        emergency_streak = emergency_streak + 1 if emergency_order > EPS else 0
        check('EMERGENCY_BASE_STREAK', y, emergency_streak, limits['EMERGENCY_BASE_STREAK']['value'], unit='years')
        rejected_days, first_rejection, maximum_peak = 0, None, 0.
        for day in range(365):
            t = offset+day
            mode = storage['ZBO'] if t >= dates.get('ZBO', math.inf) else storage['BASE']
            loss_rate = mode['loss_rate_on_throughput']
            offered = sum(q for _, q in arrivals[day])
            peak = inventory + offered*(1-loss_rate)
            maximum_peak = max(maximum_peak, peak-mode['capacity_t'])
            accepted = min(offered, max(0., mode['capacity_t']-inventory)/(1-loss_rate))
            rejected = offered-accepted
            if rejected > EPS:
                rejected_days += 1
                first_rejection = t if first_rejection is None else first_rejection
            for row, q in arrivals[day]:
                share = accepted/offered if offered else 0.
                row['delivered_volume_t'] += q*share
                row['rejected_volume_t'] += q*(1-share)
            losses = throughput_loss(accepted, loss_rate)
            start = inventory
            b = balance_step(start, accepted, losses, total/365, critical/365)
            inventory = b['closing_inventory_t']
            post_delivery = start+accepted-losses
            # Exact integral for uniform withdrawal until exhausted within the day.
            daily_demand = total/365
            time_avg = (post_delivery+inventory)/2 if inventory > EPS or daily_demand == 0 else post_delivery**2/(2*daily_demand)
            costs['holding_mln'] += time_avg*mode['holding_cost_mln_per_t_year']/365
            costs['fixed_opex_mln'] += sum(investments[k]['fixed_opex_mln_per_year']/365 for k, date in dates.items() if t >= date)
            annual['delivered_t'] += accepted
            annual['losses_t'] += losses
            annual['rejected_delivery_t'] += rejected
            for k in ('served_t', 'served_critical_t', 'shortage_t'):
                annual[k] += b[k]
            annual['min_inventory_t'] = min(annual['min_inventory_t'], inventory)
            annual['max_inventory_t'] = max(annual['max_inventory_t'], post_delivery)
            if trace:
                daily.append(dict(year=y, day=day+1, opening_inventory_t=start, delivered_t=accepted,
                                  losses_t=losses, inventory_t=inventory, capacity_t=mode['capacity_t'],
                                  served_t=b['served_t'], shortage_t=b['shortage_t'], rejected_delivery_t=rejected,
                                  reserve_threshold_t=annual['reserve_required_t']))
        check('STORAGE_OVERFLOW', y, max(0., maximum_peak), 0., unit='t_excess_before_rejection')
        if rejected_days:
            checks[-1].update(first_model_day=first_rejection, affected_days=rejected_days)
        annual.update(closing_inventory_t=inventory, total_service_level=annual['served_t']/total if total else 1.,
                      critical_service_level=annual['served_critical_t']/critical if critical else 1.)
        for rule, field in [('BASE_TOTAL_SERVICE', 'total_service_level'), ('BASE_CRITICAL_SERVICE', 'critical_service_level')]:
            check(rule, y, annual[field], limits[rule]['value'], '>=', unit='share')
            checks[-1]['severity'] = 'hard' if scenario['scenario_id'] == 'BASE' else 'resilience_benchmark'
        ceiling = scenario.get('loss_ceiling', {})
        if ceiling.get('enabled') and y >= ceiling['from_year']:
            check('STRESS_LOSS_LIMIT', y, annual['losses_t']/annual['delivered_t'] if annual['delivered_t'] else 0., ceiling['max_losses_divided_by_throughput'], unit='share')
        costs['capex_mln'] = sum(investments[i['investment_id']]['option_fee_mln']+investments[i['investment_id']]['exercise_cost_mln'] for i in plan['decisions']['investments'] if offset <= i['decision_day'] < offset+365)
        costs['total_mln'] = sum(v for k, v in costs.items() if k.endswith('_mln'))
        finance.append(costs)
        yearly.append(annual)
    for rule in ['CAPEX_2037', 'CAPEX_2040']:
        through = int(rule.split('_')[1])
        check(rule, through, sum(r['capex_mln'] for r in finance if r['year'] <= through), limits[rule]['value'], unit='mln_units')
    for i in plan['decisions']['investments']:
        check('INVESTMENT_WITHIN_HORIZON', i['investment_id'], i['decision_day'], len(years)*365-1, unit='model_day')
    # Infinity is an internal unavailable sentinel, not valid JSON. Export explicit null instead.
    for c in checks:
        for k in ['actual', 'limit']:
            if isinstance(c[k], float) and not math.isfinite(c[k]):
                c[k] = None
                c['reason'] = 'required investment not commissioned'
    result = dict(scenario_id=scenario['scenario_id'], plan_id=plan['plan_id'],
                  units={'mass': 't', 'money': 'million constant-2035 units', 'time': '365-day model year'},
                  assumptions_reference=plan['assumptions'], yearly_balance=yearly, source_schedule=schedule,
                  inventory_trace=daily, financial_breakdown=finance, constraint_checks=checks, risk_register=[],
                  pre_horizon=pre_cost,
                  provenance={'CASE_INPUT': case['version'], 'TEAM_DECISION': digest(plan), 'scenario_definition': scenario,
                              'engine_version': '0.1.0', 'case_sha256': digest(case)},
                  summary={'total_cost_mln': pre_cost['total_mln']+sum(r['total_mln'] for r in finance),
                           'shortage_t': sum(r['shortage_t'] for r in yearly),
                           'min_total_service': min(r['total_service_level'] for r in yearly),
                           'min_critical_service': min(r['critical_service_level'] for r in yearly),
                           'violations': sum(not c['passed'] for c in checks)})
    return result
